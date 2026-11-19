import hmac

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User, UserSession, utc_now
from .security import decode_session_token, hash_csrf_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    cookie_token = request.cookies.get(settings.session_cookie_name)
    token = cookie_token or (credentials.credentials if credentials else None)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    try:
        user_id, jti = decode_session_token(token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")

    session = db.scalar(select(UserSession).where(UserSession.jti == jti))
    if session is None or session.user_id != user_id or session.revoked_at is not None or session.expires_at <= utc_now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")

    if cookie_token:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin", "").rstrip("/")
            allowed = {item.strip().rstrip("/") for item in settings.cors_origins.split(",") if item.strip()}
            if not allowed:
                allowed = {settings.web_origin.rstrip("/"), "http://127.0.0.1:3000"}
            if origin not in allowed:
                raise HTTPException(status_code=403, detail="请求来源校验失败")
            csrf_cookie = request.cookies.get(settings.csrf_cookie_name, "")
            csrf_header = request.headers.get("x-csrf-token", "")
            if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
                raise HTTPException(status_code=403, detail="CSRF 校验失败")
            if not hmac.compare_digest(hash_csrf_token(csrf_header), session.csrf_token_hash):
                raise HTTPException(status_code=403, detail="CSRF 校验失败")

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    return user
