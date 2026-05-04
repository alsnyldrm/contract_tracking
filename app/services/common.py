from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.security import now_utc
from app.models import AppSetting


def utc_now() -> datetime:
    return now_utc()


def get_timezone(db: Session, default_tz: str = 'Europe/Istanbul') -> str:
    row = db.query(AppSetting).filter(AppSetting.key == 'system.timezone').first()
    return row.value if row else default_tz


def to_local(dt: datetime, tz_name: str) -> datetime:
    if dt is None:
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo('UTC'))
    return dt.astimezone(ZoneInfo(tz_name))


def now_local(db: Session, default_tz: str = 'Europe/Istanbul') -> datetime:
    tz_name = get_timezone(db, default_tz)
    return now_utc().astimezone(ZoneInfo(tz_name))
