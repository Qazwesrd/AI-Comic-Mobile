"""Single source of truth for the server-enforced trial period."""

from datetime import datetime, timedelta, timezone

TRIAL_HOURS = 48


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def trial_expires_at(started_at: datetime | None) -> datetime | None:
    if started_at is None:
        return None
    return as_utc(started_at) + timedelta(hours=TRIAL_HOURS)


def trial_is_expired(started_at: datetime | None, now: datetime | None = None) -> bool:
    expires_at = trial_expires_at(started_at)
    if expires_at is None:
        return True
    current = as_utc(now) if now is not None else datetime.now(timezone.utc)
    return current >= expires_at
