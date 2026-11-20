from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from app.database import Base
from app.models import User
from app.security_services import consume_one_time_code, create_one_time_code


def test_email_code_is_six_digits_and_can_only_be_used_once():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with test_session() as db:
        user = User(email="otp-test@example.com", password_hash="test-hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        code = create_one_time_code(db, user, "register_email_code", 10)

        assert len(code) == 6
        assert code.isdigit()
        assert consume_one_time_code(db, user, "000000" if code != "000000" else "000001", "register_email_code") is False
        assert consume_one_time_code(db, user, code, "register_email_code") is True
        assert consume_one_time_code(db, user, code, "register_email_code") is False

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_resending_email_code_invalidates_previous_code():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with test_session() as db:
        user = User(email="otp-resend@example.com", password_hash="test-hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        with patch("app.security_services.secrets.randbelow", side_effect=[123456, 654321]):
            old_code = create_one_time_code(db, user, "register_email_code", 10)
            new_code = create_one_time_code(db, user, "register_email_code", 10)

        assert consume_one_time_code(db, user, old_code, "register_email_code") is False
        assert consume_one_time_code(db, user, new_code, "register_email_code") is True

    Base.metadata.drop_all(engine)
    engine.dispose()



def test_registration_requires_email_code_before_login(monkeypatch):
    from fastapi.testclient import TestClient
    import re
    from sqlalchemy.pool import StaticPool

    from app.config import settings
    from app.database import get_db
    from app.main import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        with TestSession() as db:
            yield db

    sent_messages = []

    def fake_send(recipient, subject, text_body):
        sent_messages.append((recipient, subject, text_body))
        return True

    old_verification = settings.require_email_verification
    old_app_env = settings.app_env
    old_overrides = dict(app.dependency_overrides)
    try:
        settings.require_email_verification = True
        settings.app_env = "test"
        app.dependency_overrides[get_db] = override_get_db
        monkeypatch.setattr("app.routers.accounts.send_account_email", fake_send)

        with TestClient(app, base_url="http://localhost:3000") as client:
            payload = {
                "email": "registration-otp@example.com",
                "password": "a-very-secure-password",
            }
            registered = client.post("/api/v1/auth/register", json=payload)
            assert registered.status_code == 202
            assert len(sent_messages) == 1
            code_match = re.search(r"验证码是：([0-9]{6})", sent_messages[0][2])
            assert code_match is not None
            code = code_match.group(1)

            blocked_login = client.post("/api/v1/auth/login", json=payload)
            assert blocked_login.status_code == 403

            verified = client.post(
                "/api/v1/auth/register/verify",
                json={"email": payload["email"], "code": code},
            )
            assert verified.status_code == 200
            assert "csrf_token" in verified.json()

            allowed_login = client.post("/api/v1/auth/login", json=payload)
            assert allowed_login.status_code == 200
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        settings.require_email_verification = old_verification
        settings.app_env = old_app_env
        Base.metadata.drop_all(engine)
        engine.dispose()
