from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai_service import chat_json
from ..auth import get_current_user
from ..database import get_db
from ..models import MediaAsset, Novel, Project, StoryEntity
from ..security_services import audit, enforce_rate_limit, request_fingerprint
from .platform import require_active_license

router = APIRouter(prefix="/api/v1", tags=["asset-recognition"])


class TextAssetRecognitionIn(BaseModel):
    max_entities: int = Field(default=40, ge=1, le=80)
    include_relationships: bool = True


@router.post("/projects/{project_id}/novels/{novel_id}/assets/{asset_id}/recognize")
async def recognize_text_asset(
    project_id: int, novel_id: int, asset_id: int,
    payload: TextAssetRecognitionIn, request: Request,
    user=Depends(require_active_license), db: Session = Depends(get_db),
):
    """Extract reviewable story entities from an uploaded text asset.

    Visual image/video recognition is deliberately not claimed here: it requires a
    configured vision-capable provider and a separate multimodal request path.
    """
    enforce_rate_limit(db, f"asset-recognition:{user.id}:{request_fingerprint(request)}", 10, 3600)
    project = db.scalar(select(Project).where(Project.id == project_id, Project.user_id == user.id))
    novel = db.scalar(select(Novel).where(Novel.id == novel_id, Novel.project_id == project_id))
    asset = db.scalar(select(MediaAsset).where(
        MediaAsset.id == asset_id, MediaAsset.user_id == user.id,
        MediaAsset.project_id == project_id,
    ))
    if project is None or novel is None or asset is None:
        raise HTTPException(status_code=404, detail="项目、小说或素材不存在")
    if asset.asset_type != "text" or Path(asset.file_name).suffix.lower() not in {".txt", ".md", ".markdown"}:
        raise HTTPException(status_code=415, detail="当前阶段仅支持 TXT、Markdown 剧情文本识别；图片和视频视觉识别将在多模态阶段接入")
    path = Path(asset.storage_path).resolve()
    if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="剧情文本不存在或超过2MB，请拆分后识别")
    raw = path.read_bytes()
    source_text = None
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            source_text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if source_text is None:
        raise HTTPException(status_code=422, detail="文本编码无法识别，请转换为 UTF-8 后重试")
    source_text = source_text.strip()
    if len(source_text) < 20:
        raise HTTPException(status_code=422, detail="文本内容太短，无法可靠识别")
    result = await chat_json(
        "你是专业影视剧本资产分析师。只根据输入原文提取明确出现的人物、场景和道具。"
        "不得臆造；不确定的信息写入uncertainties。只返回JSON对象，结构为："
        "{entities:[{entity_type:'character|scene|prop',name:string,description:string,"
        "attributes:object,evidence:string,confidence:number}],"
        "relationships:[{source:string,target:string,relation:string,evidence:string}],"
        "uncertainties:[string]}。confidence范围0到1。"
        "人物包含外貌/身份/行为等原文证据；场景包含地点/环境；道具包含名称/用途/归属。"
        "同名实体合并，名称简洁，证据必须是原文可核对的短句。",
        json.dumps({
            "max_entities": payload.max_entities,
            "include_relationships": payload.include_relationships,
            "source_text": source_text[:24000],
        }, ensure_ascii=False),
        db=db, user_id=user.id,
    )
    candidates = result.get("entities")
    if not isinstance(candidates, list):
        raise HTTPException(status_code=502, detail="AI 未返回有效实体列表")
    created = []
    seen = set()
    for item in candidates[:payload.max_entities]:
        if not isinstance(item, dict):
            continue
        entity_type = item.get("entity_type")
        name = str(item.get("name", "")).strip()[:180]
        description = str(item.get("description", "")).strip()[:4000]
        evidence = str(item.get("evidence", "")).strip()[:1000]
        try:
            confidence = max(0.0, min(1.0, float(item.get("confidence", 0))))
        except (TypeError, ValueError):
            confidence = 0.0
        if entity_type not in {"character", "scene", "prop"} or not name or not evidence:
            continue
        key = (entity_type, name.casefold())
        if key in seen:
            continue
        seen.add(key)
        existing = db.scalar(select(StoryEntity).where(
            StoryEntity.novel_id == novel_id,
            StoryEntity.entity_type == entity_type,
            StoryEntity.canonical_name == name,
        ))
        if existing:
            continue
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}
        attributes = {**attributes, "_recognition": {"evidence": evidence, "confidence": confidence, "source_asset_id": asset.id}}
        entity = StoryEntity(
            entity_uuid=str(uuid4()), novel_id=novel_id, entity_type=entity_type,
            canonical_name=name, description=description,
            attributes_json=json.dumps(attributes, ensure_ascii=False),
            approved=False,
        )
        db.add(entity)
        db.flush()
        created.append({"id": entity.id, "entity_type": entity_type, "name": name,
                        "description": description, "evidence": evidence,
                        "confidence": confidence, "approved": False})
    db.commit()
    audit(db, "text_asset_entities_recognized", "media_asset", str(asset.id), user.id)
    relationships = result.get("relationships", [])
    uncertainties = result.get("uncertainties", [])
    return {
        "source_asset_id": asset.id,
        "novel_id": novel_id,
        "created_count": len(created),
        "candidates": created,
        "relationships_for_review": relationships[:100] if isinstance(relationships, list) else [],
        "uncertainties": uncertainties[:100] if isinstance(uncertainties, list) else [],
        "requires_user_confirmation": True,
        "note": "识别结果均为待确认候选，不会自动批准或覆盖已有实体。当前仅支持文本素材。",
    }
