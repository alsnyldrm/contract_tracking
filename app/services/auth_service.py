from __future__ import annotations

import logging
from datetime import timedelta

from fastapi import HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging_config import log_event
from app.core.security import (
    generate_csrf_token,
    generate_token,
    hash_password,
    now_utc,
    session_expiry,
    token_fingerprint,
    verify_password,
)
from app.models import LoginAttempt, Role, User, UserPreference, UserSession

settings = get_settings()


def ensure_user_preference(db: Session, user_id: int) -> None:
    pref = db.query(UserPreference).filter(UserPreference.user_id == user_id).first()
    if not pref:
        ts = now_utc()
        pref = UserPreference(
            user_id=user_id,
            dark_mode=False,
            sidebar_collapsed=False,
            filter_preferences={},
            created_at=ts,
            updated_at=ts,
        )
        db.add(pref)
        db.commit()


def get_role(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise RuntimeError(f'Rol bulunamadı: {role_name}')
    return role


def create_local_user(
    db: Session,
    username: str,
    password: str,
    full_name: str,
    email: str | None,
    role_name: str,
    must_change_password: bool = False,
) -> User:
    ts = now_utc()
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
        full_name=full_name,
        auth_source='local',
        must_change_password=must_change_password,
        is_active=True,
        role_id=get_role(db, role_name).id,
        created_at=ts,
        updated_at=ts,
        is_deleted=False,
        deleted_at=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    ensure_user_preference(db, user.id)
    return user


def register_login_attempt(db: Session, username: str, ip_address: str | None, success: bool, reason: str | None = None) -> None:
    db.add(
        LoginAttempt(
            username=username,
            ip_address=ip_address,
            success=success,
            reason=reason,
            created_at=now_utc(),
        )
    )
    db.commit()


def is_login_locked(db: Session, username: str, ip_address: str | None) -> bool:
    window_start = now_utc() - timedelta(minutes=settings.rate_limit_login_window_minutes)
    failed_count = (
        db.query(func.count(LoginAttempt.id))
        .filter(
            LoginAttempt.username == username,
            LoginAttempt.ip_address == ip_address,
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= window_start,
        )
        .scalar()
    )
    return failed_count >= settings.rate_limit_login_attempts


def authenticate_local_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username, User.is_deleted.is_(False)).first()
    if not user or user.auth_source != 'local':
        return None
    if not user.password_hash or not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: Session, response: Response, user: User, ip_address: str | None, user_agent: str | None) -> None:
    raw_token = generate_token(32)
    csrf_token = generate_csrf_token()
    ts = now_utc()
    db.add(
        UserSession(
            user_id=user.id,
            session_token_hash=token_fingerprint(raw_token),
            csrf_token=csrf_token,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=ts,
            expires_at=session_expiry(),
            last_seen_at=ts,
        )
    )
    db.commit()

    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        httponly=True,
        secure=False,
        samesite='lax',
        max_age=settings.session_expire_minutes * 60,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=False,
        samesite='lax',
        max_age=settings.session_expire_minutes * 60,
    )


def clear_session(db: Session, response: Response, token: str | None) -> None:
    if token:
        fingerprint = token_fingerprint(token)
        db.query(UserSession).filter(UserSession.session_token_hash == fingerprint).delete()
        db.commit()
    response.delete_cookie(settings.session_cookie_name)
    response.delete_cookie(settings.csrf_cookie_name)


def force_password_change(db: Session, user: User, new_password: str) -> None:
    if user.auth_source != 'local':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='SAML kullanıcılarında şifre değiştirilemez')
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    user.updated_at = now_utc()
    db.commit()


def log_auth_event(message: str, *, action: str, user: User | None = None, request_id: str | None = None, ip_address: str | None = None, user_agent: str | None = None, details: dict | None = None, level: int = logging.INFO) -> None:
    log_event(
        'auth',
        level,
        message,
        module='auth',
        action=action,
        user_id=getattr(user, 'id', None),
        username=getattr(user, 'username', None),
        user_role=getattr(getattr(user, 'role', None), 'name', None) if user else None,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        details=details or {},
    )
