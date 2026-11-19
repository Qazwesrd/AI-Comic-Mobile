from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


def _account(client, email, device):
    registered = client.post("/api/v1/auth/register", json={
        "email": email, "password": "a-very-secure-password"
    })
    assert registered.status_code == 201
    csrf = registered.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
    activated = client.post("/api/v1/license/activate", headers=headers, json={
        "device_id": device, "platform": "web"
    })
    assert activated.status_code == 200
    return headers


def _upload_video(client, headers, file_name="source.mp4"):
    content = b"test-video-content"
    init = client.post("/api/v1/uploads/init", headers=headers, json={
        "file_name": file_name, "mime_type": "video/mp4",
        "asset_type": "video", "size_bytes": len(content)
    })
    assert init.status_code == 200
    upload_id = init.json()["upload_id"]
    chunk = client.put(
        f"/api/v1/uploads/{upload_id}/chunks/0", content=content,
        headers={**headers, "Content-Type": "application/octet-stream"},
    )
    assert chunk.status_code == 200
    completed = client.post(f"/api/v1/uploads/{upload_id}/complete", headers=headers)
    assert completed.status_code == 200
    return completed.json()["id"]


def test_independent_video_edit_project_source_and_timeline(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    with TestClient(app, base_url="http://localhost:3000") as client:
        headers = _account(client, "video-editor@example.com", "video-device-001")
        project_response = client.post("/api/v1/video-editing/projects", headers=headers, json={
            "title": "旅行视频剪辑", "aspect_ratio": "9:16"
        })
        assert project_response.status_code == 201
        project_id = project_response.json()["id"]

        asset_id = _upload_video(client, headers)
        attached = client.post(
            f"/api/v1/video-editing/projects/{project_id}/sources",
            headers=headers, json={"asset_id": asset_id},
        )
        assert attached.status_code == 201
        source_id = attached.json()["id"]

        saved = client.put(
            f"/api/v1/video-editing/projects/{project_id}/timeline",
            headers=headers,
            json={"expected_revision": 0, "tracks": [{
                "id": "video-main", "type": "video", "clips": [{
                    "id": "clip-1", "source_id": source_id,
                    "start_ms": 0, "end_ms": 1200, "position_ms": 0
                }]
            }]},
        )
        assert saved.status_code == 200
        assert saved.json()["revision"] == 1

        stale = client.put(
            f"/api/v1/video-editing/projects/{project_id}/timeline",
            headers=headers,
            json={"expected_revision": 0, "tracks": [{"id": "video-main", "type": "video", "clips": []}]},
        )
        assert stale.status_code == 409

        timeline = client.get(f"/api/v1/video-editing/projects/{project_id}/timeline")
        assert timeline.status_code == 200
        assert timeline.json()["revision"] == 1
        assert timeline.json()["tracks"][0]["clips"][0]["source_id"] == source_id


def test_video_edit_project_is_private(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    with TestClient(app, base_url="http://localhost:3000") as client:
        owner_headers = _account(client, "video-owner@example.com", "video-owner-device")
        project = client.post("/api/v1/video-editing/projects", headers=owner_headers, json={
            "title": "Private project"
        })
        project_id = project.json()["id"]

        other_headers = _account(client, "video-other@example.com", "video-other-device")
        response = client.get(f"/api/v1/video-editing/projects/{project_id}", headers=other_headers)
        assert response.status_code == 404
