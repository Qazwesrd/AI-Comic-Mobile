import json
import re
from time import perf_counter

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .ai_config_models import AIProviderConfig, AIProviderUsageLog
from .ai_config_security import decrypt_api_key


def _text_provider(db: Session | None, user_id: int | None) -> tuple[str, str, str, str]:
    if db is not None and user_id is not None:
        row = db.scalar(select(AIProviderConfig).where(
            AIProviderConfig.user_id == user_id,
            AIProviderConfig.capability == "text",
        ))
        if row is not None:
            if not row.enabled:
                raise HTTPException(status_code=503, detail="你配置的文本 AI 服务已关闭，请先到 AI 服务配置中心启用")
            return row.provider, row.base_url.rstrip("/"), decrypt_api_key(row.encrypted_api_key), row.model
    if not all([settings.ai_api_base_url, settings.ai_api_key, settings.ai_model]):
        raise HTTPException(status_code=503, detail="请先在 AI 服务配置中心配置文本 AI，或由服务部署方配置默认文本 AI（AI_API_BASE_URL、AI_API_KEY、AI_MODEL）")
    return "默认服务", settings.ai_api_base_url.rstrip("/"), settings.ai_api_key, settings.ai_model


async def chat_json(system_prompt: str, user_prompt: str, *, db: Session | None = None, user_id: int | None = None) -> dict:
    provider, base_url, api_key, model = _text_provider(db, user_id)
    endpoint = base_url + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model, "temperature": 0.3, "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
    }
    started = perf_counter()
    status = "failed"
    error_code = None
    try:
        try:
            async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds, follow_redirects=False) as client:
                response = await client.post(endpoint, headers=headers, json=payload)
                if response.status_code == 400:
                    fallback_payload = {key: value for key, value in payload.items() if key != "response_format"}
                    response = await client.post(endpoint, headers=headers, json=fallback_payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            error_code = f"http_{exc.response.status_code}"
            raise HTTPException(status_code=502, detail=f"AI 服务返回错误：HTTP {exc.response.status_code}")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
            error_code = "provider_error"
            raise HTTPException(status_code=502, detail="AI 服务连接失败或返回格式不兼容")
        try:
            result = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            match = re.search(r"\{.*\}", str(content), re.S)
            if match:
                try:
                    result = json.loads(match.group(0))
                except json.JSONDecodeError:
                    result = {"raw_text": str(content)}
            else:
                result = {"raw_text": str(content)}
        status = "success"
        return result
    finally:
        if db is not None and user_id is not None:
            db.add(AIProviderUsageLog(
                user_id=user_id, capability="text", provider=provider, model=model,
                action="generation", status=status,
                latency_ms=int((perf_counter() - started) * 1000), error_code=error_code,
            ))
            db.commit()
