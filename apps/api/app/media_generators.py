from __future__ import annotations

import base64
import binascii
from time import perf_counter

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .ai_config_models import AIProviderConfig, AIProviderUsageLog
from .ai_config_security import decrypt_api_key


def _provider(db: Session | None, user_id: int | None, capability: str):
    if db is not None and user_id is not None:
        row = db.scalar(select(AIProviderConfig).where(
            AIProviderConfig.user_id == user_id, AIProviderConfig.capability == capability
        ))
        if row is not None:
            if not row.enabled:
                raise HTTPException(status_code=503, detail=f"你配置的{capability} AI 服务已关闭，请先到 AI 服务配置中心启用")
            return row.provider, row.base_url.rstrip("/"), decrypt_api_key(row.encrypted_api_key), row.model
    if capability == "image":
        values = (settings.image_api_base_url, settings.image_api_key, settings.image_model)
    else:
        values = (settings.audio_api_base_url, settings.audio_api_key, settings.audio_model)
    if not all(values):
        raise HTTPException(status_code=503, detail=(f"请先在 AI 服务配置中心配置{capability} AI，或由服务部署方配置 " + ("IMAGE_API_BASE_URL、IMAGE_API_KEY、IMAGE_MODEL" if capability == "image" else "AUDIO_API_BASE_URL、AUDIO_API_KEY、AUDIO_MODEL")))
    return "默认服务", values[0].rstrip("/"), values[1], values[2]


def _record_usage(db: Session | None, user_id: int | None, capability: str, provider: str, model: str, started: float, status: str, error_code: str | None):
    if db is not None and user_id is not None:
        db.add(AIProviderUsageLog(
            user_id=user_id, capability=capability, provider=provider, model=model,
            action="generation", status=status,
            latency_ms=int((perf_counter() - started) * 1000), error_code=error_code,
        ))
        db.commit()


async def generate_image(prompt: str, *, db: Session | None = None, user_id: int | None = None) -> tuple[bytes, str, str]:
    provider, base_url, api_key, model = _provider(db, user_id, "image")
    endpoint = base_url + "/images/generations"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": prompt, "n": 1, "size": "1024x1024", "response_format": "b64_json"}
    started = perf_counter()
    status = "failed"
    error_code = None
    try:
        try:
            async with httpx.AsyncClient(timeout=settings.image_timeout_seconds, follow_redirects=False) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                if response.status_code == 400:
                    fallback = {key: value for key, value in payload.items() if key != "response_format"}
                    response = await client.post(endpoint, headers=headers, json=fallback)
                response.raise_for_status()
                result = response.json()["data"][0]
                if result.get("b64_json"):
                    raw = base64.b64decode(result["b64_json"], validate=True)
                    content_type = "image/png"
                elif result.get("url"):
                    image_url = str(result["url"])
                    if not image_url.startswith("https://"):
                        raise HTTPException(status_code=502, detail="图片服务返回了非 HTTPS 图片地址")
                    downloaded = await client.get(image_url)
                    downloaded.raise_for_status()
                    raw = downloaded.content
                    content_type = downloaded.headers.get("content-type", "image/png").split(";", 1)[0]
                else:
                    raise HTTPException(status_code=502, detail="图片服务没有返回可用图片")
        except HTTPException:
            raise
        except httpx.HTTPStatusError as exc:
            error_code = f"http_{exc.response.status_code}"
            raise HTTPException(status_code=502, detail=f"图片服务返回错误：HTTP {exc.response.status_code}")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, binascii.Error):
            error_code = "provider_error"
            raise HTTPException(status_code=502, detail="图片生成服务连接失败或返回格式不兼容")
        if not raw or len(raw) > 25 * 1024 * 1024:
            raise HTTPException(status_code=502, detail="生成图片为空或超过25MB")
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            result_tuple = (raw, "image/png", ".png")
        elif raw.startswith(b"\xff\xd8\xff"):
            result_tuple = (raw, "image/jpeg", ".jpg")
        elif raw.startswith((b"GIF87a", b"GIF89a")):
            result_tuple = (raw, "image/gif", ".gif")
        elif len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            result_tuple = (raw, "image/webp", ".webp")
        else:
            raise HTTPException(status_code=502, detail=f"图片服务返回了不支持的图片格式（{content_type}）")
        status = "success"
        return result_tuple
    finally:
        _record_usage(db, user_id, "image", provider, model, started, status, error_code)


async def generate_speech(text: str, voice: str = "alloy", *, db: Session | None = None, user_id: int | None = None) -> bytes:
    provider, base_url, api_key, model = _provider(db, user_id, "audio")
    endpoint = base_url + "/audio/speech"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "input": text, "voice": voice, "response_format": "mp3"}
    started = perf_counter()
    status = "failed"
    error_code = None
    try:
        try:
            async with httpx.AsyncClient(timeout=settings.audio_timeout_seconds, follow_redirects=False) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                content = response.content
                content_type = response.headers.get("content-type", "").lower()
        except httpx.HTTPStatusError as exc:
            error_code = f"http_{exc.response.status_code}"
            raise HTTPException(status_code=502, detail=f"语音服务返回错误：HTTP {exc.response.status_code}")
        except httpx.HTTPError:
            error_code = "provider_error"
            raise HTTPException(status_code=502, detail="语音生成服务连接失败")
        if not content or len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=502, detail="语音服务返回空文件或文件超过50MB")
        if content_type and not (content_type.startswith("audio/") or "octet-stream" in content_type):
            raise HTTPException(status_code=502, detail="语音服务返回的文件类型不是音频")
        status = "success"
        return content
    finally:
        _record_usage(db, user_id, "audio", provider, model, started, status, error_code)
