from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import StoryEntity


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


def register_and_activate(client, email, device):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "a-very-secure-password"
    })
    assert response.status_code == 201
    csrf = response.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
    activation = client.post("/api/v1/license/activate", headers=headers, json={
        "device_id": device, "platform": "web"
    })
    assert activation.status_code == 200
    return headers


def test_speech_generation_requires_provider_configuration(monkeypatch):
    monkeypatch.setattr(settings, "audio_api_base_url", "")
    monkeypatch.setattr(settings, "audio_api_key", "")
    monkeypatch.setattr(settings, "audio_model", "")
    with TestClient(app, base_url="http://localhost:3000") as client:
        headers = register_and_activate(client, "voice-user@example.com", "voice-device-0001")
        response = client.post("/api/v1/audio/speech", headers=headers, json={
            "text": "欢迎使用AI漫剧手机版", "voice": "alloy"
        })
        assert response.status_code == 503
        assert "AUDIO_API_BASE_URL" in response.json()["detail"]


def test_visual_generation_requires_provider_configuration(monkeypatch):
    monkeypatch.setattr(settings, "image_api_base_url", "")
    monkeypatch.setattr(settings, "image_api_key", "")
    monkeypatch.setattr(settings, "image_model", "")
    with TestClient(app, base_url="http://localhost:3000") as client:
        headers = register_and_activate(client, "image-user@example.com", "image-device-0001")
        project = client.post("/api/v1/projects", headers=headers, json={"title": "视觉测试项目"})
        project_id = project.json()["id"]
        novel = client.post(f"/api/v1/projects/{project_id}/novels", headers=headers, json={
            "title": "视觉测试小说", "text": "第一章 开始\n一个角色出现。"
        })
        novel_id = novel.json()["novel_id"]

        db = TestingSessionLocal()
        entity = StoryEntity(
            entity_uuid="11111111-2222-4333-8444-555555555555",
            novel_id=novel_id, entity_type="character", canonical_name="主角",
            description="穿着蓝色外套的年轻冒险者", approved=False,
        )
        db.add(entity)
        db.commit()
        db.refresh(entity)
        entity_id = entity.id
        db.close()

        image_url = f"/api/v1/projects/{project_id}/novels/{novel_id}/entities/{entity_id}/generate-image"
        unapproved = client.post(image_url, headers=headers, json={"style": "3d_anime"})
        assert unapproved.status_code == 409
        assert "先审核" in unapproved.json()["detail"]

        db = TestingSessionLocal()
        db.query(StoryEntity).filter(StoryEntity.id == entity_id).update({"approved": True})
        db.commit()
        db.close()

        response = client.post(
            image_url,
            headers=headers, json={"style": "3d_anime"},
        )
        assert response.status_code == 503
        assert "IMAGE_API_BASE_URL" in response.json()["detail"]


def test_subtitle_generation_requires_text_provider(monkeypatch):
    monkeypatch.setattr(settings, "ai_api_base_url", "")
    monkeypatch.setattr(settings, "ai_api_key", "")
    monkeypatch.setattr(settings, "ai_model", "")
    with TestClient(app, base_url="http://localhost:3000") as client:
        headers = register_and_activate(client, "subtitle-user@example.com", "subtitle-device-0001")
        response = client.post("/api/v1/audio/subtitles", headers=headers, json={
            "text": "第一句旁白。第二句旁白。"
        })
        assert response.status_code == 503
        assert "AI_API_BASE_URL" in response.json()["detail"]
