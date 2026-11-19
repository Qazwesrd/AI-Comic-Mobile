from __future__ import annotations

import base64
import binascii

import httpx
from fastapi import HTTPException

from .config import settings


async def generate_image(prompt: str) -> tuple[bytes, str, str]:
    if not all([settings.image_api_base_url, settings.image_api_key, settings.image_model]):
        raise HTTPException(status_code=503, detail="尚未配置 IMAGE_API_BASE_URL、IMAGE_API_KEY 和 IMAGE_MODEL")
    endpoint = settings.image_api_base_url.rstrip("/") + "/images/generations"
    headers = {"Authorization": f"Bearer {settings.image_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": settings.image_model, "prompt": prompt, "n": 1,
        "size": "1024x1024", "response_format": "b64_json",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.image_timeout_seconds) as client:
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
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, binascii.Error):
        raise HTTPException(status_code=502, detail="图片生成服务连接失败或返回格式不兼容")

    if not raw or len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=502, detail="生成图片为空或超过25MB")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return raw, "image/png", ".png"
    if raw.startswith(b"\xff\xd8\xff"):
        return raw, "image/jpeg", ".jpg"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return raw, "image/gif", ".gif"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return raw, "image/webp", ".webp"
    raise HTTPException(status_code=502, detail=f"图片服务返回了不支持的图片格式（{content_type}）")


async def generate_speech(text: str, voice: str = "alloy") -> bytes:
    if not all([settings.audio_api_base_url, settings.audio_api_key, settings.audio_model]):
        raise HTTPException(status_code=503, detail="尚未配置 AUDIO_API_BASE_URL、AUDIO_API_KEY 和 AUDIO_MODEL")
    endpoint = settings.audio_api_base_url.rstrip("/") + "/audio/speech"
    headers = {"Authorization": f"Bearer {settings.audio_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": settings.audio_model, "input": text,
        "voice": voice, "response_format": "mp3",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.audio_timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            content = response.content
            content_type = response.headers.get("content-type", "").lower()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"语音服务返回错误：HTTP {exc.response.status_code}")
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="语音生成服务连接失败")
    if not content or len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=502, detail="语音服务返回空文件或文件超过50MB")
    if content_type and not (content_type.startswith("audio/") or "octet-stream" in content_type):
        raise HTTPException(status_code=502, detail="语音服务返回的文件类型不是音频")
    return content
