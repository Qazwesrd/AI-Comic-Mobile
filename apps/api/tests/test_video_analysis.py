from types import SimpleNamespace

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


def _account(client, email):
    registered = client.post("/api/v1/auth/register", json={
        "email": email, "password": "a-very-secure-password"
    })
    assert registered.status_code == 201
    headers = {"X-CSRF-Token": registered.json()["csrf_token"], "Origin": "http://localhost:3000"}
    activated = client.post("/api/v1/license/activate", headers=headers, json={
        "device_id": "video-analysis-device", "platform": "web"
    })
    assert activated.status_code == 200
    return headers


def _source(client, headers, monkeypatch):
    from app.routers import video_editing
    monkeypatch.setattr(video_editing, "probe_video", lambda _: {
        "duration_ms": 12000, "width": 1280, "height": 720, "fps": "30"
    })
    project = client.post("/api/v1/video-editing/projects", headers=headers, json={
        "title": "测试视频", "aspect_ratio": "16:9"
    })
    assert project.status_code == 201
    project_id = project.json()["id"]
    content = b"fake-video-content"
    init = client.post("/api/v1/uploads/init", headers=headers, json={
        "file_name": "source.mp4", "mime_type": "video/mp4",
        "asset_type": "video", "size_bytes": len(content)
    })
    upload_id = init.json()["upload_id"]
    assert client.put(f"/api/v1/uploads/{upload_id}/chunks/0", content=content,
        headers={**headers, "Content-Type": "application/octet-stream"}).status_code == 200
    completed = client.post(f"/api/v1/uploads/{upload_id}/complete", headers=headers)
    asset_id = completed.json()["id"]
    attached = client.post(f"/api/v1/video-editing/projects/{project_id}/sources",
        headers=headers, json={"asset_id": asset_id})
    assert attached.status_code == 201
    return project_id, attached.json()["id"]


def test_extract_keyframes_creates_unapproved_image_assets(tmp_path, monkeypatch):
    from app.config import settings
    from app.routers import video_analysis
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    monkeypatch.setattr(video_analysis.shutil, "which", lambda _: "/usr/bin/ffmpeg")

    def fake_run(command, **kwargs):
        from pathlib import Path
        Path(command[-1]).write_bytes(b"fake-jpeg")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(video_analysis.subprocess, "run", fake_run)
    with TestClient(app, base_url="http://localhost:3000") as client:
        headers = _account(client, "video-keyframes@example.com")
        project_id, source_id = _source(client, headers, monkeypatch)
        response = client.post(
            f"/api/v1/video-editing/projects/{project_id}/sources/{source_id}/keyframes?interval_seconds=5",
            headers=headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert data["requires_user_review"] is True
        assert all(not frame["approved"] for frame in data["frames"])


def test_export_saved_video_timeline_to_mp4(tmp_path, monkeypatch):
    from pathlib import Path
    from app.config import settings
    from app.routers import video_analysis
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    monkeypatch.setattr(video_analysis.shutil, "which", lambda _: "/usr/bin/ffmpeg")

    def fake_run(command, **kwargs):
        Path(command[-1]).write_bytes(b"fake-mp4-output")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(video_analysis.subprocess, "run", fake_run)
    with TestClient(app, base_url="http://localhost:3000") as client:
        headers = _account(client, "video-export@example.com")
        project_id, source_id = _source(client, headers, monkeypatch)
        saved = client.put(f"/api/v1/video-editing/projects/{project_id}/timeline",
            headers=headers, json={"expected_revision": 0, "tracks": [{
                "id": "video-main", "type": "video", "clips": [{
                    "id": "clip-1", "source_id": source_id, "start_ms": 0,
                    "end_ms": 5000, "position_ms": 0, "volume": 1,
                    "transition": "fade"
                }]
            }, {
                "id": "subtitle-main", "type": "subtitle", "clips": [{
                    "id": "subtitle-1", "start_ms": 0, "end_ms": 2000,
                    "position_ms": 0, "text": "测试字幕", "volume": 1,
                    "transition": "none"
                }]
            }]})
        assert saved.status_code == 200
        exported = client.post(f"/api/v1/video-editing/projects/{project_id}/export",
            headers=headers, json={"resolution": "1280x720", "fps": 30})
        assert exported.status_code == 200
        assert exported.json()["status"] == "completed"
        assert exported.json()["approved"] is False
        assert exported.json()["file_name"].endswith(".mp4")
        assert exported.json()["subtitle_asset_id"] is not None
        subtitle = client.get("/api/v1/assets/" + str(exported.json()["subtitle_asset_id"]) + "/download")
        assert subtitle.status_code == 200
        assert "测试字幕" in subtitle.content.decode("utf-8-sig")
