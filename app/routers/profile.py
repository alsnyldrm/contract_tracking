import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user
from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import User, UserPreference, UserSession
from app.services.auth_service import force_password_change

router = APIRouter()


def _log(module, msg, action, user, request, **kw):
    log_event(module, logging.INFO, msg, module=module, action=action,
              user_id=user.id, username=user.username, user_role=user.role.name,
              request_id=getattr(request.state, 'request_id', None),
              ip_address=request.client.host if request.client else None, **kw)


@router.get('/')
def my_profile(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()

    last_session = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id)
        .order_by(UserSession.created_at.desc())
        .first()
    )

    _log('profile', 'Profil görüntülendi', 'view', user, request)
    return {
        'id': user.id,
        'username': user.username,
        'full_name': user.full_name,
        'email': user.email,
        'role': user.role.name,
        'auth_source': user.auth_source,
        'is_active': user.is_active,
        'must_change_password': user.must_change_password,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'last_login': last_session.created_at.isoformat() if last_session else None,
        'preferences': {
            'dark_mode': pref.dark_mode if pref else False,
            'sidebar_collapsed': pref.sidebar_collapsed if pref else False,
            'filter_preferences': pref.filter_preferences if pref else {},
        },
    }


@router.put('/preferences', dependencies=[Depends(enforce_csrf)])
def update_preferences(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if not pref:
        pref = UserPreference(user_id=user.id, dark_mode=False, sidebar_collapsed=False,
                              filter_preferences={}, created_at=now_utc(), updated_at=now_utc())
        db.add(pref)

    if 'dark_mode' in payload:
        pref.dark_mode = bool(payload['dark_mode'])
    if 'sidebar_collapsed' in payload:
        pref.sidebar_collapsed = bool(payload['sidebar_collapsed'])
    if 'filter_preferences' in payload and isinstance(payload['filter_preferences'], dict):
        pref.filter_preferences = payload['filter_preferences']
    pref.updated_at = now_utc()
    db.commit()

    _log('profile', 'Profil tercihleri güncellendi', 'preferences_update', user, request)
    return {'ok': True}


@router.put('/fullname', dependencies=[Depends(enforce_csrf)])
def update_fullname(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = (payload.get('full_name') or '').strip()
    if not name:
        raise HTTPException(status_code=400, detail='Ad Soyad boş olamaz')
    if len(name) > 255:
        raise HTTPException(status_code=400, detail='Ad Soyad çok uzun (maks. 255 karakter)')
    user.full_name = name
    user.updated_at = now_utc()
    db.commit()
    _log('profile', 'Ad Soyad güncellendi', 'fullname_update', user, request)
    return {'ok': True}


@router.put('/account', dependencies=[Depends(enforce_csrf)])
def update_account(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    full_name = (payload.get('full_name') or '').strip()
    if not full_name:
        raise HTTPException(status_code=400, detail='Ad Soyad boş olamaz')
    if len(full_name) > 255:
        raise HTTPException(status_code=400, detail='Ad Soyad çok uzun (maks. 255 karakter)')

    email = (payload.get('email') or '').strip() or None
    if email:
        exists = (
            db.query(User)
            .filter(User.id != user.id, User.is_deleted.is_(False), func.lower(User.email) == email.lower())
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail='Bu e-posta zaten kayıtlı')

    user.full_name = full_name
    user.email = email
    user.updated_at = now_utc()
    db.commit()
    _log('profile', 'Hesap bilgileri güncellendi', 'account_update', user, request)
    return {'ok': True}


@router.put('/password', dependencies=[Depends(enforce_csrf)])
def profile_password_change(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_password = payload.get('new_password', '')
    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail='Yeni şifre en az 8 karakter olmalıdır')

    # Yerel kullanıcılar için mevcut şifre kontrolü
    if user.auth_source == 'local' and user.password_hash:
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
        current = payload.get('current_password', '')
        if not current or not ctx.verify(current, user.password_hash):
            raise HTTPException(status_code=400, detail='Mevcut şifre hatalı')

    force_password_change(db, user, new_password)
    _log('auth', 'Profil ekranından şifre değiştirildi', 'change_password', user, request)
    return {'ok': True}
