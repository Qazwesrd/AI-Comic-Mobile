from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def override_get_db():
    db = Session()
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


def test_text_upload_and_project_assignment(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    with TestClient(app, base_url="http://localhost:3000") as client:
        user = client.post("/api/v1/auth/register", json={
            "email": "handoff-owner@example.com", "password": "test-password-123456"
        })
        assert user.status_code == 201
        headers = {"X-CSRF-Token": user.json()["csrf_token"], "Origin": "http://localhost:3000"}
        assert client.post("/api/v1/license/activate", headers=headers, json={
            "device_id": "handoff-device-001", "platform": "android"
        }).status_code == 200

        project = client.post("/api/v1/projects", headers=headers, json={
            "title": "素材交接项目", "description": "测试项目"
        })
        assert project.status_code == 200
        data = "外部 AI 工具生成的文本".encode("utf-8")
        init = client.post("/api/v1/uploads/init", headers=headers, json={
            "file_name": "prompt.txt", "mime_type": "text/plain", "asset_type": "text",
            "size_bytes": len(data), "chunk_size": 1048576, "project_id": project.json()["id"]
        })
        assert init.status_code == 200
        upload_id = init.json()["upload_id"]
        assert client.put(f"/api/v1/uploads/{upload_id}/chunks/0", content=data, headers={
            **headers, "Content-Type": "application/octet-stream"
        }).status_code == 200
        completed = client.post(f"/api/v1/uploads/{upload_id}/complete", headers=headers)
        assert completed.status_code == 200
        asset_id = completed.json()["id"]

        listed = client.get("/api/v1/assets").json()
        asset = next(row for row in listed if row["id"] == asset_id)
        assert asset["asset_type"] == "text"
        assert asset["project_id"] == project.json()["id"]

        changed = client.patch(f"/api/v1/assets/{asset_id}", headers=headers, json={
            "project_id": None, "approved": True, "title": "已整理提示词"
        })
        assert changed.status_code == 200
        assert changed.json()["project_id"] is None
        assert changed.json()["approved"] is True

        other = client.post("/api/v1/auth/register", json={
            "email": "handoff-other@example.com", "password": "test-password-123456"
        })
        assert other.status_code == 201
        denied = client.patch(f"/api/v1/assets/{asset_id}", headers={
            "X-CSRF-Token": other.json()["csrf_token"], "Origin": "http://localhost:3000"
        }, json={"approved": True})
        assert denied.status_code == 404


def test_text_asset_type_cannot_be_changed_to_video(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    with TestClient(app, base_url="http://localhost:3000") as client:
        user = client.post("/api/v1/auth/register", json={
            "email": "handoff-type@example.com", "password": "test-password-123456"
        })
        headers = {"X-CSRF-Token": user.json()["csrf_token"], "Origin": "http://localhost:3000"}
        client.post("/api/v1/license/activate", headers=headers, json={
            "device_id": "handoff-device-002", "platform": "android"
        })
        data = b"plain text"
        init = client.post("/api/v1/uploads/init", headers=headers, json={
            "file_name": "notes.txt", "mime_type": "text/plain", "asset_type": "text",
            "size_bytes": len(data), "chunk_size": 1048576
        })
        assert init.status_code == 200
        upload_id = init.json()["upload_id"]
        client.put(f"/api/v1/uploads/{upload_id}/chunks/0", content=data, headers={
            **headers, "Content-Type": "application/octet-stream"
        })
        completed = client.post(f"/api/v1/uploads/{upload_id}/complete", headers=headers)
        response = client.patch(f"/api/v1/assets/{completed.json()['id']}", headers=headers,
                                json={"asset_type": "video"})
        assert response.status_code == 415
