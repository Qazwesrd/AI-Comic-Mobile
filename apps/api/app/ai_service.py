import json
import re

import httpx
from fastapi import HTTPException

from .config import settings


async def chat_json(system_prompt: str, user_prompt: str) -> dict:
    if not all([settings.ai_api_base_url, settings.ai_api_key, settings.ai_model]):
        raise HTTPException(status_code=503, detail="尚未配置 AI_API_BASE_URL、AI_API_KEY 和 AI_MODEL")
    endpoint = settings.ai_api_base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {settings.ai_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": settings.ai_model,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=settings.ai_timeout_seconds) as client:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"AI 服务返回错误：HTTP {exc.response.status_code}")
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="AI 服务连接失败或返回格式不兼容")
    try:
        return json.loads(content)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"\{.*\}", str(content), re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return {"raw_text": str(content)}
