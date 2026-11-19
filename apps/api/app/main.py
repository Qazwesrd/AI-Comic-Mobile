import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers.accounts import router as accounts_router
from .routers.platform import router as platform_router
from .routers.assets import router as assets_router
from .routers.renders import router as renders_router
from .routers.ai_media import router as ai_media_router
from .routers.video_editing import router as video_editing_router
from .routers.ai_tools import router as ai_tools_router
from .routers.ai_provider_configs import router as ai_provider_configs_router
from .routers.asset_recognition import router as asset_recognition_router
from . import ai_config_models  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Development convenience only. Production schema changes must be applied with Alembic.
    if settings.app_env.lower() == "development":
        Base.metadata.create_all(bind=engine)
    yield


def _cors_origins() -> list[str]:
    configured = settings.cors_origins or os.getenv("CORS_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    if origins:
        return origins
    if settings.app_env.lower() == "development":
        return [settings.web_origin.rstrip("/"), "http://127.0.0.1:3000"]
    return []


app = FastAPI(
    title="AI Comic Mobile API",
    description="AI 漫剧手机版服务端 API",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
app.include_router(accounts_router)
app.include_router(platform_router)
app.include_router(assets_router)
app.include_router(renders_router)
app.include_router(ai_media_router)
app.include_router(video_editing_router)
app.include_router(ai_tools_router)
app.include_router(ai_provider_configs_router)
app.include_router(asset_recognition_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-comic-mobile-api", "version": app.version}


@app.get("/api/v1", tags=["system"])
async def api_root() -> dict[str, str]:
    return {"message": "AI 漫剧手机版 API 已启动", "version": app.version}
