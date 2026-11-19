from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import secrets
import smtplib
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import AuditEvent, OneTimeToken, RateLimitBucket, User, utc_now


def _pepper() -> str:
    if settings.token_pepper:
        return settings.token_pepper
    if settings.app_env == "production":
        raise RuntimeError("TOKEN_PEPPER must be configured in production.")
    return settings.app_secret_key


def token_digest(token: str) -> str:
    return hmac.new(_pepper().encode(), token.encode(), hashlib.sha256).hexdigest()


def create_one_time_token(db: Session, user: User, purpose: str, minutes: int = 30) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(OneTimeToken(
        user_id=user.id, purpose=purpose, token_hash=token_digest(raw),
        expires_at=utc_now() + timedelta(minutes=minutes),
    ))
    db.commit()
    return raw


def consume_one_time_token(db: Session, raw: str, purpose: str) -> User | None:
    digest = token_digest(raw)
    record = db.scalar(select(OneTimeToken).where(
        OneTimeToken.token_hash == digest,
        OneTimeToken.purpose == purpose,
        OneTimeToken.used_at.is_(None),
    ))
    if record is None:
        return None
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= utc_now():
        return None
    user = db.get(User, record.user_id)
    if user is None:
        return None
    record.used_at = utc_now()
    db.commit()
    return user


def send_account_email(recipient: str, subject: str, text_body: str) -> bool:
    if not all([settings.smtp_host, settings.smtp_from_email]):
        return False
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text_body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return True


def enforce_rate_limit(db: Session, key: str, limit: int, window_seconds: int) -> None:
    now = utc_now()
    start = datetime.fromtimestamp(int(now.timestamp()) // window_seconds * window_seconds, tz=timezone.utc)
    bucket = db.scalar(select(RateLimitBucket).where(
        RateLimitBucket.bucket_key == key,
        RateLimitBucket.window_start == start,
    ))
    if bucket is None:
        bucket = RateLimitBucket(bucket_key=key, window_start=start, count=0)
        db.add(bucket)
        db.flush()
    if bucket.count >= limit:
        from fastapi import HTTPException
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
    bucket.count += 1
    db.commit()


def request_fingerprint(request) -> str:
    address = request.client.host if request.client else "unknown"
    raw = f"{address}|{request.url.path}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def audit(db: Session, action: str, subject_type: str, subject_id: str | None = None,
          user_id: int | None = None, details: str = "{}") -> None:
    db.add(AuditEvent(
        user_id=user_id, action=action, subject_type=subject_type,
        subject_id=subject_id, details=details[:4000],
    ))
    db.commit()
