import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
SENSITIVE_KEYS = {
    'password',
    'db_password',
    'token',
    'cookie',
    'assertion',
    'bind_password',
    'smtp_password',
    'x509_certificate',
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def generate_token(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def token_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def session_expiry() -> datetime:
    settings = get_settings()
    return now_utc() + timedelta(minutes=settings.session_expire_minutes)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def mask_sensitive(data: Any) -> Any:
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_KEYS:
                cleaned[key] = '***MASKED***'
            else:
                cleaned[key] = mask_sensitive(value)
        return cleaned
    if isinstance(data, list):
        return [mask_sensitive(item) for item in data]
    return data
