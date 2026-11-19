from __future__ import annotations

import json
import shutil
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import MediaAsset, Project, RenderJob
from ..security_services import enforce_rate_limit, request_fingerprint
from ..rendering import run_render_job
from .platform import require_active_license

router = APIRouter(prefix="/api/v1", tags=["rendering"])


class RenderShot(BaseModel):
    asset_id: int
    duration_seconds: float = Field(gt=0, le=60)


class RenderRequest(BaseModel):
    project_id: int | None = None
    shots: list[RenderShot] = Field(min_length=1, max_length=100)
    audio_asset_id: int | None = None
    resolution: Literal["1280x720", "1920x1080", "1080x1920"] = "1280x720"
    fps: Literal[24, 30] = 24


def _render_out(job: RenderJob) -> dict:
    return {
        "id": job.id, "job_uuid": job.job_uuid, "status": job.status,
        "output_asset_id": job.output_asset_id, "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.post("/renders")
def create_render(
    payload: RenderRequest, request: Request, background_tasks: BackgroundTasks,
    user=Depends(require_active_license), db: Session = Depends(get_db),
):
    enforce_rate_limit(db, f"render:{user.id}:{request_fingerprint(request)}", 10, 3600)
    if not shutil.which("ffmpeg"):
        raise HTTPException(status_code=503, detail="当前服务器未安装 FFmpeg，暂时不能执行分镜静帧合成")
    if payload.project_id is not None:
        project = db.scalar(select(Project).where(Project.id == payload.project_id, Project.user_id == user.id))
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")
    asset_ids = {shot.asset_id for shot in payload.shots}
    assets = db.scalars(select(MediaAsset).where(
        MediaAsset.id.in_(asset_ids), MediaAsset.user_id == user.id
    )).all()
    asset_map = {asset.id: asset for asset in assets}
    if len(asset_map) != len(asset_ids):
        raise HTTPException(status_code=404, detail="有分镜图片素材不存在或无权访问")
    for asset in assets:
        if asset.asset_type not in {"image", "character", "scene", "prop"}:
            raise HTTPException(status_code=422, detail="分镜素材必须是图片类型")
    if payload.audio_asset_id is not None:
        audio = db.scalar(select(MediaAsset).where(
            MediaAsset.id == payload.audio_asset_id,
            MediaAsset.user_id == user.id,
            MediaAsset.asset_type == "audio",
        ))
        if audio is None:
            raise HTTPException(status_code=404, detail="音频素材不存在或无权访问")

    timeline = {
        "shots": [shot.model_dump() for shot in payload.shots],
        "audio_asset_id": payload.audio_asset_id,
        "resolution": payload.resolution,
        "fps": payload.fps,
    }
    from uuid import uuid4
    job = RenderJob(
        job_uuid=str(uuid4()), user_id=user.id, project_id=payload.project_id,
        timeline_json=json.dumps(timeline, ensure_ascii=False), status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_render_job, job.id)
    return {**_render_out(job), "message": "分镜静帧合成任务已排队；这不是AI动态视频生成"}


@router.get("/renders")
def list_renders(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(RenderJob).where(RenderJob.user_id == user.id).order_by(desc(RenderJob.created_at)).limit(100)).all()
    return [_render_out(job) for job in rows]


@router.get("/renders/{job_id}")
def get_render(job_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.scalar(select(RenderJob).where(RenderJob.id == job_id, RenderJob.user_id == user.id))
    if job is None:
        raise HTTPException(status_code=404, detail="渲染任务不存在")
    return _render_out(job)
