import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import License, Product, User
from app.security_services import consume_one_time_token, create_one_time_token


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


def register(client, email):
    response = client.post("/api/v1/auth/register", json={
        "email": email, "password": "a-very-secure-password"
    })
    assert response.status_code == 201
    return response.json()["csrf_token"]


def test_project_novel_import_and_owner_isolation():
    with TestClient(app, base_url="http://localhost:3000") as client:
        csrf = register(client, "writer-one@example.com")
        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
        activation = client.post("/api/v1/license/activate", headers=headers,
                                 json={"device_id": "test-device-0101", "platform": "web"})
        assert activation.status_code == 200
        created = client.post("/api/v1/projects", headers=headers, json={"title": "测试小说"})
        assert created.status_code == 200
        project_id = created.json()["id"]
        imported = client.post(
            f"/api/v1/projects/{project_id}/novels", headers=headers,
            json={"title": "第一本小说", "text": "第一章 开始\n故事正文\n\n第二章 继续\n第二段正文"},
        )
        assert imported.status_code == 200
        assert imported.json()["chapter_count"] == 2
        assert client.get("/api/v1/projects").json()[0]["title"] == "测试小说"


def test_one_time_tokens_are_single_use():
    db = TestingSessionLocal()
    try:
        user = User(email="token-test@example.com", password_hash="not-used")
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_one_time_token(db, user, "password_reset", 20)
        first = consume_one_time_token(db, token, "password_reset")
        second = consume_one_time_token(db, token, "password_reset")
        assert first is not None and first.id == user.id
        assert second is None
    finally:
        db.close()


def test_payment_webhook_only_grants_after_valid_signature(monkeypatch):
    monkeypatch.setattr(settings, "payment_webhook_secret", "unit-test-secret")
    with TestClient(app, base_url="http://localhost:3000") as client:
        csrf = register(client, "buyer@example.com")
        db = TestingSessionLocal()
        product = Product(code="test-lifetime", name="测试永久授权", amount_minor=1999, currency="EUR")
        db.add(product)
        db.commit()
        db.refresh(product)
        db.close()

        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
        order_response = client.post("/api/v1/orders", headers=headers, json={"product_code": "test-lifetime"})
        assert order_response.status_code == 200
        order = order_response.json()
        payload = {
            "event_id": "evt-test-001", "order_no": order["order_no"], "status": "paid",
            "amount_minor": 1999, "currency": "EUR", "transaction_id": "txn-test-001"
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(b"unit-test-secret", raw, hashlib.sha256).hexdigest()
        paid = client.post("/api/v1/payments/webhook", content=raw, headers={"X-Payment-Signature": signature})
        assert paid.status_code == 200
        assert paid.json()["authorized"] is True
        db = TestingSessionLocal()
        try:
            license_record = db.scalar(select(License).join(User).where(User.email == "buyer@example.com"))
            assert license_record is not None and license_record.permanent is True
        finally:
            db.close()
        duplicate = client.post("/api/v1/payments/webhook", content=raw, headers={"X-Payment-Signature": signature})
        assert duplicate.status_code == 200
        assert duplicate.json()["duplicate"] is True


def test_payment_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(settings, "payment_webhook_secret", "unit-test-secret")
    with TestClient(app) as client:
        response = client.post("/api/v1/payments/webhook", content=b'{"event_id":"bad"}',
                               headers={"X-Payment-Signature": "invalid"})
        assert response.status_code == 401


def test_admin_manual_payment_confirmation_grants_only_matching_30_cny_order(monkeypatch):
    monkeypatch.setattr(settings, "admin_bootstrap_emails", "owner@example.com")
    monkeypatch.setattr(settings, "require_email_verification", False)
    with TestClient(app, base_url="http://localhost:3000") as client:
        buyer_csrf = register(client, "manual-buyer@example.com")
        admin_csrf = register(client, "owner@example.com")
        buyer_headers = {"X-CSRF-Token": buyer_csrf, "Origin": "http://localhost:3000"}
        admin_headers = {"X-CSRF-Token": admin_csrf, "Origin": "http://localhost:3000"}
        created_product = client.post("/api/v1/admin/products", headers=admin_headers, json={
            "code": "permanent-license", "name": "永久授权", "description": "一次性授权",
            "amount_minor": 3000, "currency": "CNY", "grants_permanent_license": True,
        })
        assert created_product.status_code == 200
        order_response = client.post("/api/v1/orders", headers=buyer_headers,
                                     json={"product_code": "permanent-license"})
        assert order_response.status_code == 200
        order_no = order_response.json()["order_no"]
        assert order_response.json()["status"] == "pending"
        denied = client.post(f"/api/v1/admin/orders/{order_no}/confirm-paid",
                             headers=buyer_headers, json={"transaction_id": "wx-txn-001"})
        assert denied.status_code == 403
        confirmed = client.post(f"/api/v1/admin/orders/{order_no}/confirm-paid",
                                headers=admin_headers, json={"transaction_id": "wx-txn-001", "note": "到账核实"})
        assert confirmed.status_code == 200
        assert confirmed.json()["permanent_license_granted"] is True
        duplicate = client.post(f"/api/v1/admin/orders/{order_no}/confirm-paid",
                                headers=admin_headers, json={"transaction_id": "wx-txn-001"})
        assert duplicate.status_code == 409


def test_expired_trial_blocks_writes_but_keeps_project_export():
    from datetime import timedelta
    from app.models import Project, utc_now

    with TestClient(app, base_url="http://localhost:3000") as client:
        csrf = register(client, "trial-expired@example.com")
        headers = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
        client.post("/api/v1/license/activate", headers=headers,
                    json={"device_id": "trial-device-0101", "platform": "web"})
        created = client.post("/api/v1/projects", headers=headers, json={"title": "保留数据项目"})
        assert created.status_code == 200
        project_id = created.json()["id"]

        db = TestingSessionLocal()
        try:
            user = db.scalar(select(User).where(User.email == "trial-expired@example.com"))
            expired_at = utc_now() - timedelta(days=3)
            db.execute(update(License).where(License.user_id == user.id).values(trial_started_at=expired_at))
            db.commit()
            refreshed = db.scalar(select(License).where(License.user_id == user.id))
            assert refreshed.trial_started_at.replace(tzinfo=expired_at.tzinfo) < utc_now() - timedelta(hours=48)
        finally:
            db.close()

        blocked = client.post("/api/v1/projects", headers=headers, json={"title": "到期后新项目"})
        assert blocked.status_code == 402
        exported = client.get(f"/api/v1/projects/{project_id}/export")
        assert exported.status_code == 200
        assert exported.json()["project"]["title"] == "保留数据项目"


def test_login_rate_limit_blocks_repeated_attempts(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 1)
    with TestClient(app, base_url="http://localhost:3000") as client:
        first = client.post("/api/v1/auth/login", json={
            "email": "unknown-user@example.com", "password": "wrong-password-long"
        })
        second = client.post("/api/v1/auth/login", json={
            "email": "unknown-user@example.com", "password": "wrong-password-long"
        })
        assert first.status_code == 401
        assert second.status_code == 429
