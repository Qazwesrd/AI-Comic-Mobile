from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


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


def test_chunked_video_upload_download_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    with TestClient(app, base_url="http://localhost:3000") as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": "media-user@example.com", "password": "a-very-secure-password"
        })
        assert registered.status_code == 201
        csrf = registered.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
        activated = client.post("/api/v1/license/activate", headers=headers, json={
            "device_id": "media-device-0001", "platform": "web"
        })
        assert activated.status_code == 200

        content = b"sample-video-bytes"
        init = client.post("/api/v1/uploads/init", headers=headers, json={
            "file_name": "episode.mp4", "mime_type": "video/mp4",
            "asset_type": "video", "size_bytes": len(content)
        })
        assert init.status_code == 200
        upload_id = init.json()["upload_id"]

        chunk = client.put(
            f"/api/v1/uploads/{upload_id}/chunks/0",
            content=content,
            headers={**headers, "Content-Type": "application/octet-stream"},
        )
        assert chunk.status_code == 200

        complete = client.post(f"/api/v1/uploads/{upload_id}/complete", headers=headers)
        assert complete.status_code == 200
        asset_id = complete.json()["id"]
        assert complete.json()["size_bytes"] == len(content)

        listed = client.get("/api/v1/assets")
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        downloaded = client.get(f"/api/v1/assets/{asset_id}/download")
        assert downloaded.status_code == 200
        assert downloaded.content == content

        deleted = client.delete(f"/api/v1/assets/{asset_id}", headers=headers)
        assert deleted.status_code == 200
        assert client.get("/api/v1/assets").json() == []


def test_upload_rejects_unsupported_file_type(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    with TestClient(app, base_url="http://localhost:3000") as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": "media-invalid@example.com", "password": "a-very-secure-password"
        })
        csrf = registered.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
        client.post("/api/v1/license/activate", headers=headers, json={
            "device_id": "media-device-0002", "platform": "web"
        })
        response = client.post("/api/v1/uploads/init", headers=headers, json={
            "file_name": "unsupported.bin", "mime_type": "application/octet-stream",
            "asset_type": "video", "size_bytes": 100
        })
        assert response.status_code == 415
