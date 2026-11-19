from datetime import datetime, timedelta, timezone
import hmac
import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import DeviceActivation, License, User, UserSession, utc_now
from ..schemas import AuthOut, CsrfOut, CredentialsIn, DeviceActivationIn, EmailCodeIn, PhoneCodeIn, PhoneCredentialsIn, PhoneRegisterVerifyIn, LicenseOut, UserOut
from ..security import create_session_token, decode_session_token, hash_csrf_token, hash_password, verify_password
from ..security_services import create_one_time_code, consume_one_time_code, enforce_rate_limit, request_fingerprint, send_account_email
from ..licensing import trial_expires_at
from ..sms_service import send_phone_verification_code, check_phone_verification_code

router = APIRouter(prefix="/api/v1", tags=["accounts"])


def _cookie_options() -> dict:
    return {
        "httponly": True,
        "secure": settings.app_env.lower() == "production",
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
        secure=settings.app_env.lower() == "production",
        samesite=settings.session_cookie_samesite.lower(),
        path="/",
    )
    return AuthOut(user=UserOut.model_validate(user), csrf_token=csrf_token)


def _send_registration_code(user: User, request: Request, db: Session) -> dict[str, str]:
    email_key = hashlib.sha256(user.email.encode("utf-8")).hexdigest()
    enforce_rate_limit(
        db, f"register-email:{email_key}", settings.rate_limit_email_per_hour, 3600
    )
    enforce_rate_limit(
        db, f"register-email-ip:{request_fingerprint(request)}",
        settings.rate_limit_auth_per_minute, 60
    )
    code = create_one_time_code(db, user, "register_email_code", 10)
    try:
        send_account_email(
            user.email,
            "AI 漫剧手机版注册验证码",
            f"你的注册验证码是：{code}\n\n验证码10分钟内有效，请勿向任何人透露。",
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"验证码邮件发送失败（{exc}）。账号信息已暂存，可以稍后重新发送。",
        ) from None
    return {"message": "验证码已发送，请查收邮箱（也请检查垃圾邮件文件夹）。验证码10分钟内有效。"}


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(
    payload: CredentialsIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthOut | dict[str, str]:
    enforce_rate_limit(
        db, f"register:{request_fingerprint(request)}",
        settings.rate_limit_auth_per_minute, 60
    )
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is not None:
        if user.email_verified:
            raise HTTPException(status_code=409, detail="该邮箱已注册，请直接登录")
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=409,
                detail="该邮箱已有待验证账号，请使用注册时设置的密码重新发送验证码",
            )
    else:
        bootstrap_admins = {
            item.strip().lower()
            for item in settings.admin_bootstrap_emails.split(",")
            if item.strip()
        }
        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            is_admin=payload.email in bootstrap_admins,
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="该邮箱已注册") from None
    # Production configuration requires email verification. In development and CI,
    # verification is opt-in so existing API tests and local workflows can create
    # isolated accounts without contacting a real mail provider.
    if not settings.require_email_verification:
        user.email_verified = True
        if db.scalar(select(License).where(License.user_id == user.id)) is None:
            db.add(License(user_id=user.id))
        db.commit()
        db.refresh(user)
        return _issue_session(user, db, response)

    response.status_code = status.HTTP_202_ACCEPTED
    return _send_registration_code(user, request, db)


@router.post("/auth/register/resend-code", status_code=status.HTTP_202_ACCEPTED)
def resend_registration_code(
    payload: CredentialsIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="邮箱或密码不正确")
    if user.email_verified:
        raise HTTPException(status_code=409, detail="该邮箱已经验证，请直接登录")
    return _send_registration_code(user, request, db)


@router.post("/auth/register/verify", response_model=AuthOut)
def verify_registration_code(
    payload: EmailCodeIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthOut:
    enforce_rate_limit(
        db, f"register-verify:{request_fingerprint(request)}",
        settings.rate_limit_auth_per_minute, 60
    )
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or user.email_verified:
        raise HTTPException(status_code=400, detail="验证码无效或已过期")
    if not consume_one_time_code(db, user, payload.code, "register_email_code"):
        raise HTTPException(status_code=400, detail="验证码错误或已过期，请重新获取")
    user.email_verified = True
    if db.scalar(select(License).where(License.user_id == user.id)) is None:
        db.add(License(user_id=user.id))
    db.commit()
    db.refresh(user)
    return _issue_session(user, db, response)

@router.post("/auth/register/phone/send-code", status_code=status.HTTP_202_ACCEPTED)
def send_phone_registration_code(
    payload: PhoneCodeIn,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    phone = payload.phone
    if db.scalar(select(User).where(User.phone == phone)) is not None:
        raise HTTPException(status_code=409, detail="该手机号已注册，请直接登录")
    phone_key = hashlib.sha256(phone.encode("utf-8")).hexdigest()
    enforce_rate_limit(db, f"register-phone:{phone_key}", 5, 3600)
    enforce_rate_limit(db, f"register-phone-minute:{phone_key}", 1, 60)
    enforce_rate_limit(
        db, f"register-phone-ip:{request_fingerprint(request)}",
        settings.rate_limit_auth_per_minute, 60
    )
    try:
        send_phone_verification_code(phone)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return {"message": "短信验证码已发送，5分钟内有效。"}


@router.post("/auth/register/phone/verify", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def verify_phone_registration_code(
    payload: PhoneRegisterVerifyIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthOut:
    phone_key = hashlib.sha256(payload.phone.encode("utf-8")).hexdigest()
    enforce_rate_limit(
        db, f"register-phone-verify:{request_fingerprint(request)}",
        settings.rate_limit_auth_per_minute, 60
    )
    enforce_rate_limit(db, f"register-phone-verify-number:{phone_key}", 10, 3600)
    if db.scalar(select(User).where(User.phone == payload.phone)) is not None:
        raise HTTPException(status_code=409, detail="该手机号已注册，请直接登录")
    try:
        verified = check_phone_verification_code(payload.phone, payload.code)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    if not verified:
        raise HTTPException(status_code=400, detail="短信验证码错误或已过期")
    bootstrap_admins = {
        item.strip().lower()
        for item in settings.admin_bootstrap_emails.split(",")
        if item.strip()
    }
    user = User(
        email=None,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        phone_verified=True,
    )
    db.add(user)
    try:
        db.flush()
        db.add(License(user_id=user.id))
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该手机号已注册，请直接登录") from None
    return _issue_session(user, db, response)


@router.post("/auth/login/phone", response_model=AuthOut)
def login_with_phone(
    payload: PhoneCredentialsIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthOut:
    phone_key = hashlib.sha256(payload.phone.encode("utf-8")).hexdigest()
    enforce_rate_limit(
        db, f"login-phone:{request_fingerprint(request)}",
        settings.rate_limit_auth_per_minute, 60
    )
    enforce_rate_limit(db, f"login-phone-number:{phone_key}", 10, 3600)
    user = db.scalar(select(User).where(User.phone == payload.phone))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="手机号或密码错误")
    if not user.phone_verified:
        raise HTTPException(status_code=403, detail="手机号尚未验证")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    return _issue_session(user, db, response)


@router.post("/auth/login", response_model=AuthOut)
def login(payload: CredentialsIn, request: Request, response: Response, db: Session = Depends(get_db)) -> AuthOut:
    enforce_rate_limit(db, f"login:{request_fingerprint(request)}", settings.rate_limit_auth_per_minute, 60)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    bootstrap_admins = {item.strip().lower() for item in settings.admin_bootstrap_emails.split(",") if item.strip()}
    if user.email in bootstrap_admins and not user.is_admin:
        user.is_admin = True
        db.commit()
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    if not user.email_verified:
        raise HTTPException(status_code=403, detail="邮箱尚未验证，请在注册页面获取并填写邮箱验证码")
    return _issue_session(user, db, response)


@router.get("/auth/csrf", response_model=CsrfOut)
def csrf(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CsrfOut:
    session_token = request.cookies.get(settings.session_cookie_name, "")
    _, jti = decode_session_token(session_token)
    session = db.scalar(select(UserSession).where(UserSession.jti == jti, UserSession.user_id == user.id))
    if session is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    if cookie_token and hmac.compare_digest(hash_csrf_token(cookie_token), session.csrf_token_hash):
        return CsrfOut(csrf_token=cookie_token)
    token = secrets.token_urlsafe(32)
    session.csrf_token_hash = hash_csrf_token(token)
    db.commit()
    response.set_cookie(
        settings.csrf_cookie_name, token,
        max_age=settings.access_token_minutes * 60,
        httponly=False, secure=settings.app_env.lower() == "production",
        samesite=settings.session_cookie_samesite.lower(), path="/",
    )
    return CsrfOut(csrf_token=token)


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    token = request.cookies.get(settings.session_cookie_name, "")
    if token:
        try:
            _, jti = decode_session_token(token)
            session = db.scalar(select(UserSession).where(UserSession.jti == jti, UserSession.user_id == user.id))
            if session and session.revoked_at is None:
                session.revoked_at = utc_now()
                db.commit()
        except Exception:
            db.rollback()
    response.delete_cookie(settings.session_cookie_name, path="/", secure=settings.app_env.lower() == "production", httponly=True, samesite=settings.session_cookie_samesite.lower())
    response.delete_cookie(settings.csrf_cookie_name, path="/", secure=settings.app_env.lower() == "production", httponly=False, samesite=settings.session_cookie_samesite.lower())
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
        active_devices = db.scalars(select(DeviceActivation).where(DeviceActivation.user_id == user.id).with_for_update()).all()
        if len(active_devices) >= settings.max_active_devices:
            raise HTTPException(status_code=409, detail="已达到设备数量上限，请先在账号中心解除旧设备")
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


def _license_status(record: License) -> LicenseOut:
    now = datetime.now(timezone.utc)
    started = record.trial_started_at
    expires = trial_expires_at(started)

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
