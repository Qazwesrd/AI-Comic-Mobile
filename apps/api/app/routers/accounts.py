from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..config import settings
from ..database import get_db
from ..models import DeviceActivation, License, User, utc_now
from ..schemas import CredentialsIn, DeviceActivationIn, LicenseOut, TokenOut, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/v1", tags=["accounts"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/auth/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: CredentialsIn, db: Session = Depends(get_db)) -> TokenOut:
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
    return _token_response(user)


@router.post("/auth/login", response_model=TokenOut)
def login(payload: CredentialsIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    return _token_response(user)


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

    device = db.scalar(
        select(DeviceActivation).where(
            DeviceActivation.user_id == user.id,
            DeviceActivation.device_id == payload.device_id,
        )
    )
    if device is None:
        db.add(DeviceActivation(
            user_id=user.id,
            device_id=payload.device_id,
            platform=payload.platform.strip().lower() or "unknown",
            first_seen_at=now,
            last_seen_at=now,
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
def license_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LicenseOut:
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
        status=state,
        permanent=record.permanent,
        trial_started_at=started.isoformat() if started else None,
        trial_expires_at=expires.isoformat() if expires else None,
        remaining_seconds=remaining,
        message=message,
    )
