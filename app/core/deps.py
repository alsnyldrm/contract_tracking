from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import token_fingerprint
from app.models import User, UserSession

settings = get_settings()


class AuthContext:
    def __init__(self, user: User, session: UserSession):
        self.user = user
        self.session = session


def get_auth_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Oturum bulunamadı')

    session = (
        db.query(UserSession)
        .filter(UserSession.session_token_hash == token_fingerprint(token))
        .first()
    )
    if not session or session.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Oturum süresi doldu')

    user = db.query(User).filter(User.id == session.user_id, User.is_deleted.is_(False)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Kullanıcı pasif')

    session.last_seen_at = datetime.now(timezone.utc)
    db.commit()

    request.state.current_user = user
    return AuthContext(user=user, session=session)


def get_current_user(auth: AuthContext = Depends(get_auth_context)) -> User:
    return auth.user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role.name != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Bu işlem için admin yetkisi gerekli')
    return user


def enforce_csrf(request: Request, auth: AuthContext = Depends(get_auth_context)) -> None:
    if request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        token = request.headers.get('X-CSRF-Token')
        if not token or token != auth.session.csrf_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='CSRF doğrulaması başarısız')
