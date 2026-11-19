from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
import app.routers.renders as renders_router


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


def test_render_endpoint_reports_missing_ffmpeg(monkeypatch):
    monkeypatch.setattr(renders_router.shutil, "which", lambda _: None)
    with TestClient(app, base_url="http://localhost:3000") as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": "render-user@example.com", "password": "a-very-secure-password"
        })
        assert registered.status_code == 201
        csrf = registered.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
        activation = client.post("/api/v1/license/activate", headers=headers, json={
            "device_id": "render-device-0001", "platform": "web"
        })
        assert activation.status_code == 200

        response = client.post("/api/v1/renders", headers=headers, json={
            "shots": [{"asset_id": 123, "duration_seconds": 3}],
            "resolution": "1280x720", "fps": 24
        })
        assert response.status_code == 503
        assert "FFmpeg" in response.json()["detail"]


def test_render_rejects_empty_timeline():
    with TestClient(app) as client:
        response = client.post("/api/v1/renders", json={"shots": []})
        assert response.status_code == 422
