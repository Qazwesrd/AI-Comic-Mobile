from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from cryptography.fernet import Fernet

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
    from app import ai_config_models as _ai_config_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db


def teardown_module():
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_ai_provider_config_is_encrypted_and_never_returned(monkeypatch):
    monkeypatch.setattr(settings, "ai_config_encryption_key", Fernet.generate_key().decode())
    with TestClient(app, base_url="http://localhost:3000") as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": "ai-config-user@example.com", "password": "a-very-secure-password",
        })
        assert registered.status_code == 201
        csrf = registered.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
        secret = "test-secret-key-123456789"
        response = client.put("/api/v1/ai-provider-configs", headers=headers, json={
            "capability": "text", "provider": "DeepSeek", "base_url": "https://api.example.com/v1",
            "api_key": secret, "model": "deepseek-chat", "enabled": True,
        })
        assert response.status_code == 200
        assert secret not in response.text
        assert response.json()["api_key_configured"] is True
        assert "encrypted_api_key" not in response.text
        listing = client.get("/api/v1/ai-provider-configs")
        assert listing.status_code == 200
        assert secret not in listing.text
        update = client.put("/api/v1/ai-provider-configs", headers=headers, json={
            "capability": "text", "provider": "DeepSeek", "base_url": "https://api.example.com/v1",
            "model": "deepseek-reasoner", "enabled": True,
        })
        assert update.status_code == 200
        assert update.json()["model"] == "deepseek-reasoner"


def test_ai_provider_config_requires_login():
    with TestClient(app, base_url="http://localhost:3000") as client:
        assert client.get("/api/v1/ai-provider-configs").status_code == 401
