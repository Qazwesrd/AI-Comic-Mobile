from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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


def test_cookie_session_csrf_and_server_side_logout():
    with TestClient(app, base_url="http://localhost:3000") as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": "session-test@example.com", "password": "a-very-secure-password"},
        )
        assert registered.status_code == 201
        data = registered.json()
        csrf = data["csrf_token"]
        assert "access_token" not in data
        assert "ai_comic_session" in registered.cookies
        assert "httponly" in registered.headers.get("set-cookie", "").lower()

        assert client.get("/api/v1/auth/me").status_code == 200

        no_csrf = client.post(
            "/api/v1/license/activate",
            headers={"Origin": "http://localhost:3000"},
            json={"device_id": "test-device-0001", "platform": "web"},
        )
        assert no_csrf.status_code == 403

        activated = client.post(
            "/api/v1/license/activate",
            headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf},
            json={"device_id": "test-device-0001", "platform": "web"},
        )
        assert activated.status_code == 200
        assert activated.json()["status"] == "trial"

        logout = client.post(
            "/api/v1/auth/logout",
            headers={"Origin": "http://localhost:3000", "X-CSRF-Token": csrf},
        )
        assert logout.status_code == 200
        assert client.get("/api/v1/auth/me").status_code == 401


def test_cookie_mutation_rejects_untrusted_origin():
    with TestClient(app, base_url="http://localhost:3000") as client:
        registered = client.post(
            "/api/v1/auth/register",
            json={"email": "origin-test@example.com", "password": "another-secure-password"},
        )
        assert registered.status_code == 201
        csrf = registered.json()["csrf_token"]
        response = client.post(
            "/api/v1/license/activate",
            headers={"Origin": "https://attacker.invalid", "X-CSRF-Token": csrf},
            json={"device_id": "test-device-0002", "platform": "web"},
        )
        assert response.status_code == 403
