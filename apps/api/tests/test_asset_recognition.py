from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import MediaAsset, StoryEntity

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def override_get_db():
    db = SessionLocal()
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


def test_text_recognition_creates_unapproved_candidates(tmp_path, monkeypatch):
    import app.routers.asset_recognition as recognition

    async def fake_chat_json(*args, **kwargs):
        return {
            "entities": [{
                "entity_type": "character", "name": "林风",
                "description": "年轻剑客，身穿青衣",
                "attributes": {"clothing": "青衣"},
                "evidence": "林风身穿青衣，握紧长剑。",
                "confidence": 0.94,
            }],
            "relationships": [],
            "uncertainties": ["林风的年龄不明确"],
        }

    monkeypatch.setattr(recognition, "chat_json", fake_chat_json)
    text_path = Path(tmp_path) / "story.txt"
    text_path.write_text("林风身穿青衣，握紧长剑。他走进古老的山门，准备寻找失落的宝物。", encoding="utf-8")

    with TestClient(app, base_url="http://localhost:3000") as client:
        registered = client.post("/api/v1/auth/register", json={
            "email": "recognition-user@example.com", "password": "a-very-secure-password"
        })
        assert registered.status_code == 201
        headers = {"X-CSRF-Token": registered.json()["csrf_token"], "Origin": "http://localhost:3000"}
        activated = client.post("/api/v1/license/activate", headers=headers, json={
            "device_id": "recognition-device-0001", "platform": "web"
        })
        assert activated.status_code == 200
        project = client.post("/api/v1/projects", headers=headers, json={"title": "识别测试项目"})
        project_id = project.json()["id"]
        novel = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers, json={
            "title": "识别测试小说", "text": "林风身穿青衣，握紧长剑。他走进古老的山门。"
        })
        novel_id = novel.json()["novel_id"]

        db = SessionLocal()
        asset = MediaAsset(
            asset_uuid="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            user_id=registered.json()["user"]["id"], project_id=project_id,
            asset_type="text", title="剧情文本", file_name="story.txt",
            mime_type="text/plain", size_bytes=text_path.stat().st_size,
            sha256="0" * 64, storage_path=str(text_path), approved=False,
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)
        asset_id = asset.id
        db.close()

        response = client.post(
            f"/api/v1/projects/{project_id}/novels/{novel_id}/assets/{asset_id}/recognize",
            headers=headers, json={"max_entities": 20},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created_count"] == 1
        assert data["requires_user_confirmation"] is True
        assert data["candidates"][0]["name"] == "林风"
        assert data["candidates"][0]["approved"] is False

        db = SessionLocal()
        entity = db.query(StoryEntity).filter_by(novel_id=novel_id, canonical_name="林风").one()
        assert entity.approved is False
        db.close()


def test_visual_asset_recognition_is_not_misrepresented_as_supported():
    with TestClient(app, base_url="http://localhost:3000") as client:
        response = client.post("/api/v1/auth/register", json={
            "email": "visual-recognition-user@example.com", "password": "a-very-secure-password"
        })
        assert response.status_code == 201
        headers = {"X-CSRF-Token": response.json()["csrf_token"], "Origin": "http://localhost:3000"}
        client.post("/api/v1/license/activate", headers=headers, json={
            "device_id": "visual-recognition-device-0001", "platform": "web"
        })
        project = client.post("/api/v1/projects", headers=headers, json={"title": "视觉识别项目"})
        project_id = project.json()["id"]
        novel = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers, json={
            "title": "视觉识别小说", "text": "这是一个足够长的测试故事内容。"
        })
        novel_id = novel.json()["novel_id"]
        response = client.post(
            f"/api/v1/projects/{project_id}/novels/{novel_id}/assets/999/recognize",
            headers=headers, json={},
        )
        assert response.status_code == 404
