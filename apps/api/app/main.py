from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Comic Mobile API",
    description="AI 漫剧手机版服务端 API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-comic-mobile-api", "version": app.version}


@app.get("/api/v1", tags=["system"])
async def api_root() -> dict[str, str]:
    return {"message": "AI 漫剧手机版 API 已启动", "version": app.version}
