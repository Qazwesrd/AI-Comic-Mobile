import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers.accounts import router as accounts_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # create_all is retained for the early prototype; production must use migrations.
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


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-comic-mobile-api", "version": app.version}


@app.get("/api/v1", tags=["system"])
async def api_root() -> dict[str, str]:
    return {"message": "AI 漫剧手机版 API 已启动", "version": app.version}
