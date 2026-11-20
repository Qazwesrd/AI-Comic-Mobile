from __future__ import annotations

from pathlib import Path
import json
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..media_generators import generate_image, generate_speech
from ..ai_service import chat_json
from ..models import MediaAsset, Novel, Project, StoryEntity
from ..security_services import audit, enforce_rate_limit, request_fingerprint
from .platform import require_active_license

router = APIRouter(prefix="/api/v1", tags=["ai-media"])


class GenerateEntityImageIn(BaseModel):
    style: Literal["realistic", "3d_anime", "2d_anime", "guofeng", "ink"] = "3d_anime"
    extra_prompt: str = Field(default="", max_length=1000)


class SubtitleIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    project_id: int | None = None


class SpeechIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    voice: Literal["alloy", "echo", "fable", "onyx", "nova", "shimmer"] = "alloy"
    project_id: int | None = None


STYLE_LABELS = {
    "realistic": "真人电影写实风格",
    "3d_anime": "高品质3D动漫电影风格",
    "2d_anime": "精致2D动漫风格",
    "guofeng": "国风漫画风格",
    "ink": "水墨动画风格",
}


def _save_media(user_id: int, asset_type: str, title: str, file_name: str,
                mime_type: str, content: bytes, project_id: int | None, db: Session) -> MediaAsset:
    asset_uuid = str(uuid4())
    root = Path(settings.media_root).expanduser().resolve()
    folder = root / "assets" / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{asset_uuid}{Path(file_name).suffix.lower()}"
    path.write_bytes(content)
    import hashlib
    asset = MediaAsset(
        asset_uuid=asset_uuid, user_id=user_id, project_id=project_id,
        asset_type=asset_type, title=title[:180], file_name=file_name[:255],
        mime_type=mime_type, size_bytes=len(content),
        sha256=hashlib.sha256(content).hexdigest(), storage_path=str(path),
        approved=False,
    )
    db.add(asset)
    db.flush()
    return asset


@router.post("/projects/{project_id}/novels/{novel_id}/entities/{entity_id}/generate-image")
async def generate_story_entity_image(
    project_id: int, novel_id: int, entity_id: int, payload: GenerateEntityImageIn,
    request: Request, user=Depends(require_active_license), db: Session = Depends(get_db),
):
    enforce_rate_limit(db, f"image-generation:{user.id}:{request_fingerprint(request)}", 5, 3600)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    novel = db.scalar(select(Novel).where(Novel.id == novel_id, Novel.project_id == project_id))
    entity = db.scalar(select(StoryEntity).where(StoryEntity.id == entity_id, StoryEntity.novel_id == novel_id))
    if project is None or novel is None or entity is None:
        raise HTTPException(status_code=404, detail="项目、小说或识别素材不存在")
    if not entity.approved:
        raise HTTPException(status_code=409, detail="请先审核并确认该人物、场景或道具，再生成视觉参考图")

    style = STYLE_LABELS[payload.style]
    if entity.entity_type == "character":
        view_instruction = "角色三视图设定图，同一角色正面、侧面、背面全身并列展示，三视图服装、发型、面部和比例完全一致，干净中性背景，不要文字、水印或额外人物。"
    elif entity.entity_type == "scene":
        view_instruction = "电影级场景概念设计图，清晰空间布局、光照和环境细节，宽画幅构图，不要文字和水印。"
    else:
        view_instruction = "道具三视图设定图，同一物品正面、侧面、背面并列展示，结构和材质一致，干净中性背景，不要文字和水印。"
    try:
        attributes = json.loads(entity.attributes_json or "{}")
    except (TypeError, ValueError):
        attributes = {}
    continuity = json.dumps(attributes, ensure_ascii=False)[:5000]
    prompt = (
        f"风格：{style}。素材名称：{entity.canonical_name}。"
        f"原文描述：{entity.description}。原文识别出的外观与设定属性：{continuity}。"
        f"补充要求：{payload.extra_prompt}。"
        f"{view_instruction}"
        "严格遵守原文已知设定，不擅自改变角色性别、年龄观感、发型、服装主色、标志性配饰或道具结构；"
        "未提供的信息采用合理且克制的设计，不要添加与原文冲突的细节。"
        "高质量专业动画/影视前期美术设定。"
    )
    content, mime, extension = await generate_image(prompt, db=db, user_id=user.id)
    file_name = f"{entity.canonical_name}-reference{extension}"
    asset = _save_media(
        user.id, entity.entity_type, f"{entity.canonical_name}-AI视觉参考图",
        file_name, mime, content, project.id, db,
    )
    entity.visual_asset_id = asset.id
    db.commit()
    db.refresh(asset)
    audit(db, "story_entity_image_generated", "media_asset", str(asset.id), user.id)
    return {"entity_id": entity.id, "asset_id": asset.id, "asset_type": asset.asset_type,
            "file_name": asset.file_name, "mime_type": asset.mime_type,
            "size_bytes": asset.size_bytes, "approved": asset.approved}


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{millis:03d}"


@router.post("/audio/subtitles")
async def create_subtitle_asset(
    payload: SubtitleIn, request: Request,
    user=Depends(require_active_license), db: Session = Depends(get_db),
):
    enforce_rate_limit(db, f"subtitle-generation:{user.id}:{request_fingerprint(request)}", 20, 3600)
    if payload.project_id is not None:
        project = db.scalar(select(Project).where(Project.id == payload.project_id, Project.user_id == user.id))
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
    result = await chat_json(
        "你是专业字幕编辑。把输入文本切分为便于手机观看的中文字幕片段，按语义断句，单条尽量不超过20个汉字。只返回JSON，格式为 {segments:[{start_seconds:number,end_seconds:number,text:string}]}。时间从0开始，顺序递增，片段之间不要重叠，语速按自然中文口播估算。",
        payload.text, db=db, user_id=user.id,
    )
    segments = result.get("segments")
    if not isinstance(segments, list) or not segments or len(segments) > 500:
        raise HTTPException(status_code=502, detail="AI字幕服务没有返回有效片段")
    normalized = []
    previous_end = 0.0
    for segment in segments:
        try:
            start = float(segment["start_seconds"])
            end = float(segment["end_seconds"])
            text = str(segment["text"]).strip()
        except (KeyError, TypeError, ValueError):
            raise HTTPException(status_code=502, detail="AI字幕时间格式无效")
        if not text or start < previous_end or end <= start or end > 3600:
            raise HTTPException(status_code=502, detail="AI字幕时间顺序或区间无效")
        normalized.append((start, end, text))
        previous_end = end
    srt = "\n\n".join(
        f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}"
        for index, (start, end, text) in enumerate(normalized, start=1)
    ) + "\n"
    file_name = f"subtitles-{uuid4().hex[:12]}.srt"
    asset = _save_media(
        user.id, "subtitle", "AI字幕-" + file_name, file_name,
        "application/x-subrip", srt.encode("utf-8"), payload.project_id, db,
    )
    db.commit()
    db.refresh(asset)
    audit(db, "subtitle_asset_generated", "media_asset", str(asset.id), user.id)
    return {"asset_id": asset.id, "file_name": asset.file_name,
            "segments": len(normalized), "size_bytes": asset.size_bytes}


@router.post("/audio/speech")
async def create_speech_asset(
    payload: SpeechIn, request: Request,
    user=Depends(require_active_license), db: Session = Depends(get_db),
):
    enforce_rate_limit(db, f"speech-generation:{user.id}:{request_fingerprint(request)}", 20, 3600)
    if payload.project_id is not None:
        project = db.scalar(select(Project).where(Project.id == payload.project_id, Project.user_id == user.id))
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
    audio = await generate_speech(payload.text, payload.voice, db=db, user_id=user.id)
    file_name = f"voiceover-{uuid4().hex[:12]}.mp3"
    asset = _save_media(
        user.id, "audio", "AI配音-" + file_name, file_name,
        "audio/mpeg", audio, payload.project_id, db,
    )
    db.commit()
    db.refresh(asset)
    audit(db, "speech_asset_generated", "media_asset", str(asset.id), user.id)
    return {"asset_id": asset.id, "file_name": asset.file_name,
            "size_bytes": asset.size_bytes, "mime_type": asset.mime_type}
