from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import base64
import hmac
import secrets
import smtplib
import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
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


def create_one_time_code(db: Session, user: User, purpose: str, minutes: int = 10) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.execute(update(OneTimeToken).where(
        OneTimeToken.user_id == user.id,
        OneTimeToken.purpose == purpose,
        OneTimeToken.used_at.is_(None),
    ).values(used_at=utc_now()))
    db.add(OneTimeToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=token_digest(f"{user.id}:{purpose}:{code}"),
        expires_at=utc_now() + timedelta(minutes=minutes),
    ))
    db.commit()
    return code


def consume_one_time_code(db: Session, user: User, code: str, purpose: str) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    digest = token_digest(f"{user.id}:{purpose}:{code}")
    record = db.scalar(select(OneTimeToken).where(
        OneTimeToken.user_id == user.id,
        OneTimeToken.token_hash == digest,
        OneTimeToken.purpose == purpose,
        OneTimeToken.used_at.is_(None),
    ))
    if record is None:
        return False
    expires = record.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= utc_now():
        return False
    claimed = db.execute(update(OneTimeToken).where(
        OneTimeToken.id == record.id,
        OneTimeToken.used_at.is_(None),
    ).values(used_at=utc_now()))
    if claimed.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True


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
    claimed = db.execute(update(OneTimeToken).where(OneTimeToken.id == record.id, OneTimeToken.used_at.is_(None)).values(used_at=utc_now()))
    if claimed.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    return user


def send_account_email(recipient: str, subject: str, text_body: str) -> bool:
    required = [
        settings.gmail_client_id,
        settings.gmail_client_secret,
        settings.gmail_refresh_token,
        settings.gmail_sender_email,
    ]
    if not all(required):
        raise RuntimeError("Gmail API email settings are incomplete.")

    message = EmailMessage()
    message["From"] = settings.gmail_sender_email
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(text_body)
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    try:
        with httpx.Client(timeout=20.0) as client:
            token_response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": settings.gmail_client_id,
                    "client_secret": settings.gmail_client_secret,
                    "refresh_token": settings.gmail_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")
            if not access_token:
                raise RuntimeError("Gmail OAuth did not return an access token.")
            send_response = client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": raw_message},
            )
            send_response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"Gmail API request failed with HTTP {exc.response.status_code}.") from None
    except httpx.RequestError:
        raise RuntimeError("Gmail API network request failed.") from None
    return True

def enforce_rate_limit(db: Session, key: str, limit: int, window_seconds: int) -> None:
    now = utc_now()
    start = datetime.fromtimestamp(int(now.timestamp()) // window_seconds * window_seconds, tz=timezone.utc)
    values = {"bucket_key": key, "window_start": start, "count": 1}
    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect == "sqlite":
        statement = sqlite_insert(RateLimitBucket).values(**values).on_conflict_do_update(
            index_elements=["bucket_key", "window_start"],
            set_={"count": RateLimitBucket.count + 1},
        ).returning(RateLimitBucket.count)
        count = db.scalar(statement)
    elif dialect == "postgresql":
        statement = postgres_insert(RateLimitBucket).values(**values).on_conflict_do_update(
            index_elements=["bucket_key", "window_start"],
            set_={"count": RateLimitBucket.count + 1},
        ).returning(RateLimitBucket.count)
        count = db.scalar(statement)
    else:
        bucket = db.scalar(select(RateLimitBucket).where(RateLimitBucket.bucket_key == key, RateLimitBucket.window_start == start))
        if bucket is None:
            bucket = RateLimitBucket(**values)
            db.add(bucket)
            db.flush()
        else:
            bucket.count += 1
        count = bucket.count
    if count > limit:
        db.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=429, detail="操作过于频繁，请稍后再试")
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
