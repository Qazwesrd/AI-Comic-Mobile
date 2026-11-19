from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..ai_service import chat_json
from ..auth import get_current_user
from ..database import get_db
from ..models import MediaAsset, VideoEditPlan, VideoEditProject, VideoEditSource, VideoEditTimeline
from ..media_probe import probe_video
from ..security_services import enforce_rate_limit, request_fingerprint
from .platform import require_active_license

router = APIRouter(prefix="/api/v1/video-editing", tags=["video-editing"])


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=4000)
    aspect_ratio: Literal["16:9", "9:16", "1:1", "2.35:1"] = "16:9"


class SourceAttach(BaseModel):
    asset_id: int


class Clip(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    source_id: int | None = None
    start_ms: int = Field(default=0, ge=0)
    end_ms: int = Field(default=0, ge=0)
    position_ms: int = Field(default=0, ge=0)
    text: str | None = Field(default=None, max_length=2000)
    volume: float = Field(default=1.0, ge=0, le=2)
    transition: Literal["none", "fade", "dissolve"] = "none"


class Track(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    type: Literal["video", "audio", "music", "subtitle"]
    clips: list[Clip] = Field(default_factory=list, max_length=500)


class TimelineSave(BaseModel):
    expected_revision: int = Field(default=0, ge=0)
    tracks: list[Track] = Field(min_length=1, max_length=12)


class PlanRequest(BaseModel):
    instruction: str = Field(min_length=3, max_length=4000)


def _project(db: Session, project_id: int, user_id: int) -> VideoEditProject:
    project = db.scalar(select(VideoEditProject).where(
        VideoEditProject.id == project_id, VideoEditProject.user_id == user_id
    ))
    if project is None:
        raise HTTPException(status_code=404, detail="剪辑项目不存在")
    return project


def _project_out(project: VideoEditProject, source_count: int = 0, revision: int = 0) -> dict:
    return {
        "id": project.id, "title": project.title, "description": project.description,
        "aspect_ratio": project.aspect_ratio, "status": project.status,
        "source_count": source_count, "revision": revision,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, user=Depends(require_active_license), db: Session = Depends(get_db)):
    project = VideoEditProject(user_id=user.id, title=payload.title.strip(),
        description=payload.description, aspect_ratio=payload.aspect_ratio)
    db.add(project)
    db.commit()
    db.refresh(project)
    return _project_out(project)


@router.get("/projects")
def list_projects(user=Depends(require_active_license), db: Session = Depends(get_db)):
    projects = db.scalars(select(VideoEditProject).where(
        VideoEditProject.user_id == user.id
    ).order_by(desc(VideoEditProject.updated_at)).limit(100)).all()
    output = []
    for project in projects:
        count = db.query(VideoEditSource).filter(VideoEditSource.project_id == project.id).count()
        latest = db.scalar(select(VideoEditTimeline.revision).where(
            VideoEditTimeline.project_id == project.id
        ).order_by(desc(VideoEditTimeline.revision)).limit(1)) or 0
        output.append(_project_out(project, count, latest))
    return output


@router.get("/projects/{project_id}")
def get_project(project_id: int, user=Depends(require_active_license), db: Session = Depends(get_db)):
    project = _project(db, project_id, user.id)
    sources = db.scalars(select(VideoEditSource).where(
        VideoEditSource.project_id == project.id, VideoEditSource.user_id == user.id
    ).order_by(VideoEditSource.id)).all()
    revision = db.scalar(select(VideoEditTimeline.revision).where(
        VideoEditTimeline.project_id == project.id
    ).order_by(desc(VideoEditTimeline.revision)).limit(1)) or 0
    return {
        **_project_out(project, len(sources), revision),
        "sources": [{
            "id": item.id, "asset_id": item.asset_id, "title": db.get(MediaAsset, item.asset_id).title,
            "file_name": db.get(MediaAsset, item.asset_id).file_name,
            "duration_ms": item.duration_ms, "width": item.width, "height": item.height,
            "probe_status": item.probe_status,
        } for item in sources],
    }


@router.post("/projects/{project_id}/sources", status_code=201)
def attach_source(project_id: int, payload: SourceAttach,
                  user=Depends(require_active_license), db: Session = Depends(get_db)):
    project = _project(db, project_id, user.id)
    asset = db.scalar(select(MediaAsset).where(
        MediaAsset.id == payload.asset_id, MediaAsset.user_id == user.id,
        MediaAsset.asset_type == "video",
    ))
    if asset is None:
        raise HTTPException(status_code=404, detail="视频素材不存在或无权访问")
    existing = db.scalar(select(VideoEditSource).where(
        VideoEditSource.project_id == project.id, VideoEditSource.asset_id == asset.id
    ))
    if existing:
        return {"id": existing.id, "asset_id": asset.id, "message": "该视频已添加"}
    metadata = probe_video(asset.storage_path)
    source = VideoEditSource(
        project_id=project.id, user_id=user.id, asset_id=asset.id,
        duration_ms=metadata["duration_ms"] if metadata else None,
        width=metadata["width"] if metadata else None,
        height=metadata["height"] if metadata else None,
        fps=metadata["fps"] if metadata else None,
        probe_status="ready" if metadata else "unavailable",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"id": source.id, "asset_id": asset.id, "title": asset.title,
            "file_name": asset.file_name, "probe_status": source.probe_status}


@router.get("/projects/{project_id}/timeline")
def get_timeline(project_id: int, user=Depends(require_active_license), db: Session = Depends(get_db)):
    _project(db, project_id, user.id)
    timeline = db.scalar(select(VideoEditTimeline).where(
        VideoEditTimeline.project_id == project_id, VideoEditTimeline.user_id == user.id
    ).order_by(desc(VideoEditTimeline.revision)).limit(1))
    if timeline is None:
        return {"revision": 0, "tracks": []}
    return {"revision": timeline.revision, **json.loads(timeline.timeline_json)}


@router.put("/projects/{project_id}/timeline")
def save_timeline(project_id: int, payload: TimelineSave,
                  user=Depends(require_active_license), db: Session = Depends(get_db)):
    project = _project(db, project_id, user.id)
    latest = db.scalar(select(VideoEditTimeline).where(
        VideoEditTimeline.project_id == project_id, VideoEditTimeline.user_id == user.id
    ).order_by(desc(VideoEditTimeline.revision)).limit(1))
    current_revision = latest.revision if latest else 0
    if payload.expected_revision != current_revision:
        raise HTTPException(status_code=409, detail={
            "message": "时间线已在其他位置更新，请刷新后再保存",
            "current_revision": current_revision,
        })
    source_rows = db.scalars(select(VideoEditSource).where(
        VideoEditSource.project_id == project.id, VideoEditSource.user_id == user.id
    )).all()
    sources = {source.id: source for source in source_rows}
    for track in payload.tracks:
        for clip in track.clips:
            if track.type == "subtitle":
                if not clip.text:
                    raise HTTPException(status_code=422, detail="字幕片段必须包含文字")
                continue
            if clip.source_id is None or clip.source_id not in sources:
                raise HTTPException(status_code=422, detail="时间线引用了不属于此项目的视频/音频素材")
            if clip.end_ms <= clip.start_ms:
                raise HTTPException(status_code=422, detail="片段结束时间必须大于开始时间")
            source = sources[clip.source_id]
            if source.duration_ms is not None and clip.end_ms > source.duration_ms:
                raise HTTPException(status_code=422, detail="片段时间超出源视频时长")
    revision = current_revision + 1
    record = VideoEditTimeline(project_id=project.id, user_id=user.id,
        revision=revision, timeline_json=json.dumps(
            {"tracks": [track.model_dump() for track in payload.tracks]}, ensure_ascii=False
        ))
    db.add(record)
    project.status = "editing"
    db.commit()
    return {"revision": revision, "message": "时间线已保存"}


@router.post("/projects/{project_id}/ai-plan", status_code=201)
async def create_ai_plan(project_id: int, payload: PlanRequest, request: Request,
                         user=Depends(require_active_license), db: Session = Depends(get_db)):
    project = _project(db, project_id, user.id)
    enforce_rate_limit(db, f"video-edit-plan:{user.id}:{request_fingerprint(request)}", 10, 3600)
    sources = db.scalars(select(VideoEditSource).where(
        VideoEditSource.project_id == project.id, VideoEditSource.user_id == user.id
    )).all()
    if not sources:
        raise HTTPException(status_code=422, detail="请先添加至少一个视频素材")
    source_info = []
    for source in sources:
        asset = db.get(MediaAsset, source.asset_id)
        source_info.append({
            "source_id": source.id, "file_name": asset.file_name,
            "duration_ms": source.duration_ms, "probe_status": source.probe_status,
        })
    system = (
        "你是视频剪辑规划助手。只能根据给定素材元数据生成可编辑剪辑建议。"
        "不得声称看过视频画面或听过音频。duration_ms为空时，不得编造片段时间码；"
        "此时输出空clips并在limitations说明需要媒体分析。只输出JSON对象，结构为"
        '{"summary":"...","limitations":["..."],"clips":[{"source_id":1,"start_ms":0,'
        '"end_ms":1000,"position_ms":0,"reason":"..."}]}。'
        "source_id必须来自输入，时间必须非负且end_ms大于start_ms。"
    )
    result = await chat_json(system, json.dumps({
        "project_title": project.title, "instruction": payload.instruction,
        "sources": source_info,
    }, ensure_ascii=False))
    if not isinstance(result, dict) or not isinstance(result.get("clips"), list):
        raise HTTPException(status_code=502, detail="AI 返回的剪辑计划格式无效")
    allowed = {source["source_id"]: source for source in source_info}
    clean_clips = []
    for clip in result["clips"][:200]:
        try:
            source_id = int(clip["source_id"])
            start_ms = int(clip["start_ms"])
            end_ms = int(clip["end_ms"])
            position_ms = int(clip.get("position_ms", 0))
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=502, detail="AI 剪辑计划包含无效片段")
        source = allowed.get(source_id)
        if source is None or start_ms < 0 or end_ms <= start_ms or position_ms < 0:
            raise HTTPException(status_code=502, detail="AI 剪辑计划引用了无效素材或时间码")
        if source["duration_ms"] is None:
            raise HTTPException(status_code=422, detail="素材尚未完成媒体时长探测，暂不能生成时间码剪辑计划")
        if end_ms > source["duration_ms"]:
            raise HTTPException(status_code=502, detail="AI 剪辑计划时间超出素材时长")
        clean_clips.append({
            "source_id": source_id, "start_ms": start_ms, "end_ms": end_ms,
            "position_ms": position_ms, "reason": str(clip.get("reason", ""))[:500],
        })
    safe_result = {
        "summary": str(result.get("summary", ""))[:2000],
        "limitations": [str(x)[:500] for x in result.get("limitations", [])[:20]],
        "clips": clean_clips,
    }
    plan = VideoEditPlan(project_id=project.id, user_id=user.id,
        instruction=payload.instruction, plan_json=json.dumps(safe_result, ensure_ascii=False))
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return {"id": plan.id, "status": "draft", **safe_result}
