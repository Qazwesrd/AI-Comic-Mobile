from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import User


def test_phone_registration_and_login(monkeypatch):
    from fastapi.testclient import TestClient
    from app.config import settings
    from app.main import app

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        with TestSession() as db:
            yield db

    sent_numbers = []
    monkeypatch.setattr("app.routers.accounts.send_phone_verification_code", lambda phone: sent_numbers.append(phone))
    monkeypatch.setattr("app.routers.accounts.check_phone_verification_code", lambda phone, code: phone == "13800138000" and code == "123456")
    old_verification = settings.require_email_verification
    old_app_env = settings.app_env
    old_overrides = dict(app.dependency_overrides)
    try:
        settings.require_email_verification = True
        settings.app_env = "test"
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, base_url="http://localhost:3000") as client:
            sent = client.post("/api/v1/auth/register/phone/send-code", json={"phone": "13800138000"})
            assert sent.status_code == 202
            assert sent_numbers == ["13800138000"]
            verified = client.post("/api/v1/auth/register/phone/verify", json={"phone": "13800138000", "code": "123456", "password": "a-very-secure-password"})
            assert verified.status_code == 201
            assert verified.json()["user"]["phone"] == "13800138000"
            assert verified.json()["user"]["email"] is None
            assert verified.json()["csrf_token"]
            login = client.post("/api/v1/auth/login/phone", json={"phone": "13800138000", "password": "a-very-secure-password"})
            assert login.status_code == 200
            assert login.json()["user"]["phone"] == "13800138000"
            duplicate = client.post("/api/v1/auth/register/phone/send-code", json={"phone": "13800138000"})
            assert duplicate.status_code == 409
            with TestSession() as db:
                user = db.scalar(select(User).where(User.phone == "13800138000"))
                assert user is not None and user.phone_verified is True
                assert user.email is None
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        settings.require_email_verification = old_verification
        settings.app_env = old_app_env
        Base.metadata.drop_all(engine)
        engine.dispose()
