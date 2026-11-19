from time import perf_counter
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai_config_models import AIProviderConfig, AIProviderUsageLog
from ..ai_config_security import decrypt_api_key, encrypt_api_key
from ..auth import get_current_user
from .platform import require_active_license
from ..database import get_db
from ..security_services import enforce_rate_limit

router = APIRouter(prefix="/api/v1/ai-provider-configs", tags=["ai-provider-configs"])
CAPABILITIES = {"text", "image", "audio"}


class ProviderConfigIn(BaseModel):
    capability: str
    provider: str = Field(min_length=1, max_length=48)
    base_url: str = Field(min_length=8, max_length=500)
    api_key: str | None = Field(default=None, min_length=8, max_length=4096)
    model: str = Field(min_length=1, max_length=160)
    enabled: bool = True

    @field_validator("capability")
    @classmethod
    def validate_capability(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in CAPABILITIES:
            raise ValueError("能力类型仅支持 text、image、audio")
        return value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        parsed = urlparse(value)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("请输入有效的 HTTP/HTTPS API Base URL，不要把密钥放进 URL")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("远程 AI 服务必须使用 HTTPS")
        return value


def _public(item: AIProviderConfig) -> dict:
    return {
        "id": item.id, "capability": item.capability, "provider": item.provider,
        "base_url": item.base_url, "model": item.model, "enabled": item.enabled,
        "api_key_configured": bool(item.encrypted_api_key),
        "updated_at": item.updated_at.isoformat(),
    }


@router.get("")
def list_configs(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AIProviderConfig).where(AIProviderConfig.user_id == user.id).order_by(AIProviderConfig.capability)).all()
    return {"configs": [_public(row) for row in rows], "supported_capabilities": sorted(CAPABILITIES)}


@router.put("")
def save_config(payload: ProviderConfigIn, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    enforce_rate_limit(db, f"ai-config-save:{user.id}", 20, 3600)
    row = db.scalar(select(AIProviderConfig).where(
        AIProviderConfig.user_id == user.id, AIProviderConfig.capability == payload.capability
    ))
    if row is None and not payload.api_key:
        raise HTTPException(status_code=422, detail="首次配置必须填写 API Key")
    if payload.api_key:
        encrypted = encrypt_api_key(payload.api_key)
    else:
        encrypted = row.encrypted_api_key
    if row is None:
        row = AIProviderConfig(user_id=user.id, capability=payload.capability,
            provider=payload.provider.strip(), base_url=payload.base_url,
            encrypted_api_key=encrypted, model=payload.model.strip(), enabled=payload.enabled)
        db.add(row)
    else:
        row.provider = payload.provider.strip()
        row.base_url = payload.base_url
        row.encrypted_api_key = encrypted
        row.model = payload.model.strip()
        row.enabled = payload.enabled
    db.commit()
    db.refresh(row)
    return _public(row)


@router.delete("/{capability}")
def delete_config(capability: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if capability not in CAPABILITIES:
        raise HTTPException(status_code=404, detail="AI 能力类型不存在")
    row = db.scalar(select(AIProviderConfig).where(
        AIProviderConfig.user_id == user.id, AIProviderConfig.capability == capability
    ))
    if row is None:
        return {"deleted": False}
    db.delete(row)
    db.commit()
    return {"deleted": True}


@router.post("/{capability}/test")
async def test_config(capability: str, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if capability not in CAPABILITIES:
        raise HTTPException(status_code=404, detail="AI 能力类型不存在")
    enforce_rate_limit(db, f"ai-config-test:{user.id}", 10, 3600)
    row = db.scalar(select(AIProviderConfig).where(
        AIProviderConfig.user_id == user.id, AIProviderConfig.capability == capability,
        AIProviderConfig.enabled.is_(True),
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="请先保存并启用该 AI 服务配置")
    api_key = decrypt_api_key(row.encrypted_api_key)
    started = perf_counter()
    status = "failed"
    error_code = None
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            response = await client.get(row.base_url + "/models", headers={"Authorization": f"Bearer {api_key}"})
        if response.is_success:
            status = "success"
            result = {"success": True, "message": "连接成功，服务端已响应模型列表接口。"}
        else:
            error_code = f"http_{response.status_code}"
            result = {"success": False, "message": f"服务返回 HTTP {response.status_code}，请检查地址、密钥和服务商兼容性。"}
    except httpx.TimeoutException:
        error_code = "timeout"
        result = {"success": False, "message": "连接超时，请检查网络和服务地址。"}
    except httpx.HTTPError:
        error_code = "connection_error"
        result = {"success": False, "message": "连接失败，请检查 API Base URL 和服务器网络。"}
    finally:
        db.add(AIProviderUsageLog(
            user_id=user.id, capability=capability, provider=row.provider, model=row.model,
            action="connection_test", status=status,
            latency_ms=int((perf_counter() - started) * 1000), error_code=error_code,
        ))
        db.commit()
    return result


@router.get("/usage-logs")
def usage_logs(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(AIProviderUsageLog).where(
        AIProviderUsageLog.user_id == user.id
    ).order_by(AIProviderUsageLog.created_at.desc()).limit(50)).all()
    return {"logs": [{
        "capability": row.capability, "provider": row.provider, "model": row.model,
        "action": row.action, "status": row.status, "latency_ms": row.latency_ms,
        "error_code": row.error_code, "created_at": row.created_at.isoformat(),
    } for row in rows]}
