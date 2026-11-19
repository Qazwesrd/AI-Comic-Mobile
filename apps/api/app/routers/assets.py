from __future__ import annotations

from datetime import timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import MediaAsset, Project, UploadSession, utc_now
from ..security_services import audit, enforce_rate_limit, request_fingerprint
from .platform import require_active_license

router = APIRouter(prefix="/api/v1", tags=["media-assets"])

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}
TEXT_EXTENSIONS = {".srt", ".vtt"}
PLAIN_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".json", ".csv"}
PDF_EXTENSIONS = {".pdf"}
ASSET_TYPES = {"character", "scene", "prop", "image", "reference", "video", "audio", "subtitle", "text"}


class UploadInitIn(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(default="application/octet-stream", max_length=128)
    asset_type: str = Field(pattern="^(character|scene|prop|image|reference|video|audio|subtitle|text)$")
    size_bytes: int = Field(gt=0)
    project_id: int | None = None
    chunk_size: int = Field(default=8 * 1024 * 1024, ge=1024 * 1024, le=8 * 1024 * 1024)


class AssetUpdateIn(BaseModel):
    project_id: int | None = None
    asset_type: str | None = Field(default=None, pattern="^(character|scene|prop|image|reference|video|audio|subtitle|text)$")
    title: str | None = Field(default=None, min_length=1, max_length=180)
    approved: bool | None = None


def _media_root() -> Path:
    root = Path(settings.media_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _owned_project(db: Session, project_id: int | None, user_id: int) -> None:
    if project_id is None:
        return
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user_id))
    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")


def _safe_file_name(value: str) -> str:
    name = Path(value.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        raise HTTPException(status_code=422, detail="文件名无效")
    return name[:255]


def _allowed_extensions(asset_type: str) -> set[str]:
    if asset_type in {"character", "scene", "prop", "image"}:
        return IMAGE_EXTENSIONS
    if asset_type == "reference":
        return IMAGE_EXTENSIONS | PDF_EXTENSIONS
    if asset_type == "video":
        return VIDEO_EXTENSIONS
    if asset_type == "audio":
        return AUDIO_EXTENSIONS
    if asset_type == "subtitle":
        return TEXT_EXTENSIONS
    if asset_type == "text":
        return PLAIN_TEXT_EXTENSIONS
    return set()


def _get_upload(db: Session, upload_id: str, user_id: int) -> UploadSession:
    session = db.scalar(select(UploadSession).where(
        UploadSession.upload_id == upload_id, UploadSession.user_id == user_id
    ))
    if session is None or session.status != "uploading":
        raise HTTPException(status_code=404, detail="上传任务不存在或已完成")
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= utc_now():
        raise HTTPException(status_code=410, detail="上传任务已过期，请重新创建")
    return session


@router.post("/uploads/init")
def init_upload(
    payload: UploadInitIn, request: Request,
    user=Depends(require_active_license), db: Session = Depends(get_db),
):
    enforce_rate_limit(db, f"upload-init:{user.id}:{request_fingerprint(request)}", 30, 3600)
    if payload.size_bytes > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"单个文件不能超过{settings.max_upload_bytes // (1024 * 1024)}MB")
    file_name = _safe_file_name(payload.file_name)
    extension = Path(file_name).suffix.lower()
    if extension not in _allowed_extensions(payload.asset_type):
        raise HTTPException(status_code=415, detail="文件格式与素材类型不匹配或暂不支持")
    mime = payload.mime_type.lower().split(";", 1)[0].strip()
    expected_prefix = {
        "character": "image/", "scene": "image/", "prop": "image/", "image": "image/",
        "reference": ("image/", "application/pdf"), "video": "video/",
        "audio": "audio/", "subtitle": ("text/", "application/x-subrip"),
        "text": ("text/", "application/json"),
    }[payload.asset_type]
    accepted = expected_prefix if isinstance(expected_prefix, tuple) else (expected_prefix,)
    if mime != "application/octet-stream" and not any(mime.startswith(prefix) if prefix.endswith("/") else mime == prefix for prefix in accepted):
        raise HTTPException(status_code=415, detail="文件 MIME 类型与素材类型不匹配")
    _owned_project(db, payload.project_id, user.id)
    active_uploads = db.query(UploadSession).filter(
        UploadSession.user_id == user.id, UploadSession.status == "uploading",
        UploadSession.expires_at > utc_now(),
    ).count()
    if active_uploads >= 5:
        raise HTTPException(status_code=429, detail="同时进行的上传任务最多5个")

    upload_id = str(uuid4())
    total_chunks = (payload.size_bytes + payload.chunk_size - 1) // payload.chunk_size
    folder = _media_root() / "tmp" / upload_id
    folder.mkdir(parents=True, exist_ok=False)
    session = UploadSession(
        upload_id=upload_id, user_id=user.id, project_id=payload.project_id,
        file_name=file_name, mime_type=payload.mime_type or "application/octet-stream",
        asset_type=payload.asset_type, total_size=payload.size_bytes,
        chunk_size=payload.chunk_size, total_chunks=total_chunks,
        received_chunks_json="[]", status="uploading",
        expires_at=utc_now() + timedelta(hours=24),
    )
    db.add(session)
    db.commit()
    return {"upload_id": upload_id, "chunk_size": payload.chunk_size,
            "total_chunks": total_chunks, "expires_in_hours": 24}


@router.put("/uploads/{upload_id}/chunks/{chunk_index}")
async def upload_chunk(
    upload_id: str, chunk_index: int, request: Request,
    x_chunk_sha256: str = Header(default=""),
    user=Depends(require_active_license), db: Session = Depends(get_db),
):
    session = _get_upload(db, upload_id, user.id)
    enforce_rate_limit(db, f"upload-chunk:{user.id}:{upload_id}", session.total_chunks * 3, 3600)
    if chunk_index < 0 or chunk_index >= session.total_chunks:
        raise HTTPException(status_code=404, detail="分片序号无效")
    body = await request.body()
    expected_size = min(session.chunk_size, session.total_size - chunk_index * session.chunk_size)
    if len(body) != expected_size:
        raise HTTPException(status_code=422, detail="分片大小不正确")
    digest = sha256(body).hexdigest()
    if x_chunk_sha256 and digest.lower() != x_chunk_sha256.lower():
        raise HTTPException(status_code=422, detail="分片校验失败")

    folder = _media_root() / "tmp" / upload_id
    target = folder / f"chunk-{chunk_index:06d}.part"
    temporary = folder / f"chunk-{chunk_index:06d}.tmp"
    temporary.write_bytes(body)
    temporary.replace(target)
    received = set(json.loads(session.received_chunks_json))
    received.add(chunk_index)
    session.received_chunks_json = json.dumps(sorted(received))
    db.commit()
    return {"chunk_index": chunk_index, "received_chunks": len(received), "total_chunks": session.total_chunks}


@router.post("/uploads/{upload_id}/complete")
def complete_upload(
    upload_id: str, user=Depends(require_active_license), db: Session = Depends(get_db),
):
    session = _get_upload(db, upload_id, user.id)
    received = set(json.loads(session.received_chunks_json))
    expected = set(range(session.total_chunks))
    if received != expected:
        missing = sorted(expected - received)
        raise HTTPException(status_code=409, detail={"message": "仍有分片未上传", "missing_chunks": missing[:100]})

    root = _media_root()
    folder = root / "tmp" / upload_id
    asset_uuid = str(uuid4())
    extension = Path(session.file_name).suffix.lower()
    asset_folder = root / "assets" / str(user.id)
    asset_folder.mkdir(parents=True, exist_ok=True)
    destination = asset_folder / f"{asset_uuid}{extension}"
    checksum = sha256()
    written = 0
    try:
        with destination.open("wb") as output:
            for index in range(session.total_chunks):
                chunk_path = folder / f"chunk-{index:06d}.part"
                with chunk_path.open("rb") as chunk:
                    while True:
                        block = chunk.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        checksum.update(block)
                        written += len(block)
        if written != session.total_size:
            raise HTTPException(status_code=422, detail="合并后的文件大小不正确")
        asset = MediaAsset(
            asset_uuid=asset_uuid, user_id=user.id, project_id=session.project_id,
            asset_type=session.asset_type, title=Path(session.file_name).stem[:180],
            file_name=session.file_name, mime_type=session.mime_type,
            size_bytes=written, sha256=checksum.hexdigest(),
            storage_path=str(destination), approved=False,
        )
        db.add(asset)
        db.delete(session)
        db.commit()
        db.refresh(asset)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    shutil.rmtree(folder, ignore_errors=True)
    audit(db, "media_asset_uploaded", "media_asset", str(asset.id), user.id)
    return {"id": asset.id, "asset_uuid": asset.asset_uuid, "asset_type": asset.asset_type,
            "title": asset.title, "file_name": asset.file_name, "size_bytes": asset.size_bytes,
            "sha256": asset.sha256, "approved": asset.approved}


@router.get("/assets")
def list_assets(
    project_id: int | None = None, asset_type: str | None = None,
    user=Depends(get_current_user), db: Session = Depends(get_db),
):
    query = select(MediaAsset).where(MediaAsset.user_id == user.id)
    if project_id is not None:
        query = query.where(MediaAsset.project_id == project_id)
    if asset_type:
        query = query.where(MediaAsset.asset_type == asset_type)
    rows = db.scalars(query.order_by(MediaAsset.created_at.desc()).limit(200)).all()
    return [{"id": a.id, "asset_uuid": a.asset_uuid, "project_id": a.project_id,
             "asset_type": a.asset_type, "title": a.title, "file_name": a.file_name,
             "mime_type": a.mime_type, "size_bytes": a.size_bytes,
             "approved": a.approved, "created_at": a.created_at.isoformat()} for a in rows]


@router.patch("/assets/{asset_id}")
def update_asset(
    asset_id: int, payload: AssetUpdateIn,
    user=Depends(get_current_user), db: Session = Depends(get_db),
):
    asset = db.scalar(select(MediaAsset).where(
        MediaAsset.id == asset_id, MediaAsset.user_id == user.id
    ))
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="没有需要更新的素材信息")
    if "project_id" in changes:
        _owned_project(db, changes["project_id"], user.id)
        asset.project_id = changes["project_id"]
    if "asset_type" in changes and changes["asset_type"] is not None:
        new_type = changes["asset_type"]
        extension = Path(asset.file_name).suffix.lower()
        if extension not in _allowed_extensions(new_type):
            raise HTTPException(status_code=415, detail="文件格式与所选素材类型不匹配")
        asset.asset_type = new_type
    if "title" in changes and changes["title"] is not None:
        asset.title = changes["title"].strip()
    if "approved" in changes and changes["approved"] is not None:
        asset.approved = changes["approved"]
    db.commit()
    db.refresh(asset)
    audit(db, "media_asset_updated", "media_asset", str(asset.id), user.id)
    return {
        "id": asset.id, "project_id": asset.project_id, "asset_type": asset.asset_type,
        "title": asset.title, "file_name": asset.file_name, "approved": asset.approved,
    }


@router.get("/assets/{asset_id}/download")
def download_asset(asset_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.scalar(select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.user_id == user.id))
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    path = Path(asset.storage_path).resolve()
    if not path.is_file() or not path.is_relative_to(_media_root()):
        raise HTTPException(status_code=404, detail="素材文件不存在")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.file_name)


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    asset = db.scalar(select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.user_id == user.id))
    if asset is None:
        raise HTTPException(status_code=404, detail="素材不存在")
    path = Path(asset.storage_path).resolve()
    root = _media_root()
    if path.is_relative_to(root):
        path.unlink(missing_ok=True)
    db.delete(asset)
    db.commit()
    audit(db, "media_asset_deleted", "media_asset", str(asset_id), user.id)
    return {"message": "素材已删除"}
