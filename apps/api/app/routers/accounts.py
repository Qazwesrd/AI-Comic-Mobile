from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import DeviceActivation, License, User, UserSession, utc_now
from ..schemas import AuthOut, CsrfOut, CredentialsIn, DeviceActivationIn, LicenseOut, UserOut
from ..security import create_session_token, hash_csrf_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1", tags=["accounts"])


def _cookie_options() -> dict:
    return {
        "httponly": True,
        "secure": settings.app_env == "production",
        "samesite": settings.session_cookie_samesite.lower(),
        "path": "/",
    }


def _issue_session(user: User, db: Session, response: Response) -> AuthOut:
    token, jti, csrf_token, expires = create_session_token(user.id)
    db.add(UserSession(
        jti=jti,
        user_id=user.id,
        csrf_token_hash=hash_csrf_token(csrf_token),
        expires_at=expires,
    ))
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.access_token_minutes * 60,
        **_cookie_options(),
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        max_age=settings.access_token_minutes * 60,
        httponly=False,
        secure=settings.app_env == "production",
        samesite=settings.session_cookie_samesite.lower(),
        path="/",
    )
    return AuthOut(user=UserOut.model_validate(user), csrf_token=csrf_token)


@router.post("/auth/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(payload: CredentialsIn, response: Response, db: Session = Depends(get_db)) -> AuthOut:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=409, detail="该邮箱已注册")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.flush()
        db.add(License(user_id=user.id))
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该邮箱已注册")
    return _issue_session(user, db, response)


@router.post("/auth/login", response_model=AuthOut)
def login(payload: CredentialsIn, response: Response, db: Session = Depends(get_db)) -> AuthOut:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    return _issue_session(user, db, response)


@router.get("/auth/csrf", response_model=CsrfOut)
def csrf(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CsrfOut:
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if cookie_token:
        return CsrfOut(csrf_token=cookie_token)
    token = __import__("secrets").token_urlsafe(32)
    session_token = request.cookies.get(settings.session_cookie_name, "")
    from ..security import decode_session_token
    _, jti = decode_session_token(session_token)
    session = db.scalar(select(UserSession).where(UserSession.jti == jti, UserSession.user_id == user.id))
    if session is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    session.csrf_token_hash = hash_csrf_token(token)
    db.commit()
    response.set_cookie(
        settings.csrf_cookie_name, token,
        max_age=settings.access_token_minutes * 60,
        httponly=False, secure=settings.app_env == "production",
        samesite=settings.session_cookie_samesite.lower(), path="/",
    )
    return CsrfOut(csrf_token=token)


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    token = request.cookies.get(settings.session_cookie_name, "")
    if token:
        from ..security import decode_session_token
        try:
            _, jti = decode_session_token(token)
            session = db.scalar(select(UserSession).where(UserSession.jti == jti, UserSession.user_id == user.id))
            if session and session.revoked_at is None:
                session.revoked_at = utc_now()
                db.commit()
        except Exception:
            db.rollback()
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.app_env == "production", httponly=True, samesite=settings.session_cookie_samesite.lower())
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.app_env == "production", httponly=False, samesite=settings.session_cookie_samesite.lower())
    return {"message": "已安全退出登录"}


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/license/activate", response_model=LicenseOut)
def activate_device(
    payload: DeviceActivationIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LicenseOut:
    now = utc_now()
    license_record = db.scalar(select(License).where(License.user_id == user.id))
    if license_record is None:
        license_record = License(user_id=user.id)
        db.add(license_record)
        db.flush()

    device = db.scalar(select(DeviceActivation).where(
        DeviceActivation.user_id == user.id,
        DeviceActivation.device_id == payload.device_id,
    ))
    if device is None:
        db.add(DeviceActivation(
            user_id=user.id, device_id=payload.device_id,
            platform=payload.platform.strip().lower() or "unknown",
            first_seen_at=now, last_seen_at=now,
        ))
    else:
        device.last_seen_at = now
        device.platform = payload.platform.strip().lower() or device.platform

    if license_record.trial_started_at is None and not license_record.permanent:
        license_record.trial_started_at = now

    db.commit()
    db.refresh(license_record)
    return _license_status(license_record)


@router.get("/license/status", response_model=LicenseOut)
def license_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> LicenseOut:
    license_record = db.scalar(select(License).where(License.user_id == user.id))
    if license_record is None:
        license_record = License(user_id=user.id)
        db.add(license_record)
        db.commit()
        db.refresh(license_record)
    return _license_status(license_record)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _license_status(record: License) -> LicenseOut:
    now = datetime.now(timezone.utc)
    started = _as_utc(record.trial_started_at)
    expires = started + timedelta(hours=settings.trial_hours) if started else None

    if record.permanent:
        state, remaining, message = "permanent", 0, "永久授权已生效"
    elif expires is None:
        state, remaining, message = "not_activated", 0, "请先激活本设备以开始免费试用"
    elif now < expires:
        state = "trial"
        remaining = max(0, int((expires - now).total_seconds()))
        message = "免费试用进行中"
    else:
        state, remaining, message = "expired", 0, "免费试用已结束，请前往官网购买永久授权"

    return LicenseOut(
        status=state, permanent=record.permanent,
        trial_started_at=started.isoformat() if started else None,
        trial_expires_at=expires.isoformat() if expires else None,
        remaining_seconds=remaining, message=message,
    )
