from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import uuid

import jwt
from pwdlib import PasswordHash

from .config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def hash_csrf_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session_token(user_id: int) -> tuple[str, str, str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=settings.access_token_minutes)
    jti = uuid.uuid4().hex
    csrf_token = secrets.token_urlsafe(32)
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": now,
        "exp": expires,
    }
    token = jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)
    return token, jti, csrf_token, expires


def decode_session_token(token: str) -> tuple[int, str]:
    payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
    return int(payload["sub"]), str(payload["jti"])
