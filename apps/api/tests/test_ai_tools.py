from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_module():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db


def teardown_module():
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_ai_tools_endpoint_reports_android_clients_without_exposing_secrets(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_base_url", "https://example.invalid/v1")
    monkeypatch.setattr(settings, "ai_api_key", "do-not-return-this-secret")
    monkeypatch.setattr(settings, "ai_model", "test-model")
    with TestClient(app, base_url="http://localhost:3000") as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": "ai-tools-user@example.com",
            "password": "a-very-secure-password",
        })
        assert registered.status_code == 201
        response = client.get("/api/v1/ai-tools")
        assert response.status_code == 200
        payload = response.json()
        modes = {item["id"]: item for item in payload["modes"]}
        assert modes["built-in"]["capabilities"]["text"] is True
        assert modes["android-client"]["capabilities"]["video_editing"] is True
        clients = {item["id"]: item for item in payload["android_apps"]}
        assert clients["chatgpt"]["package_name"] == "com.openai.chatgpt"
        assert clients["deepseek"]["package_name"] == "com.deepseek.chat"
        assert clients["claude"]["package_name"] == "com.anthropic.claude"
        assert clients["doubao"]["package_name"] == "com.larus.nova"
        assert clients["jimeng"]["package_name"] == "com.bytedance.dreamina"
        assert "web_tools" not in payload
        assert "do-not-return-this-secret" not in response.text
        assert all(item["store_url"].startswith("https://") for item in payload["android_apps"])


def test_ai_tools_endpoint_requires_login():
    with TestClient(app, base_url="http://localhost:3000") as client:
        response = client.get("/api/v1/ai-tools")
        assert response.status_code == 401
