import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user
from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import User, UserPreference
from app.services.auth_service import force_password_change

router = APIRouter()


@router.get('/')
def my_profile(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    log_event('profile', logging.INFO, 'Profil görüntülendi', module='profile', action='view', user_id=user.id, username=user.username, user_role=user.role.name, request_id=getattr(request.state, 'request_id', None), ip_address=request.client.host if request.client else None)
    return {
        'id': user.id,
        'username': user.username,
        'full_name': user.full_name,
        'email': user.email,
        'role': user.role.name,
        'auth_source': user.auth_source,
        'must_change_password': user.must_change_password,
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
        pref = UserPreference(user_id=user.id, dark_mode=False, sidebar_collapsed=False, filter_preferences={}, created_at=now_utc(), updated_at=now_utc())
        db.add(pref)

    if 'dark_mode' in payload:
        pref.dark_mode = bool(payload['dark_mode'])
    if 'sidebar_collapsed' in payload:
        pref.sidebar_collapsed = bool(payload['sidebar_collapsed'])
    if 'filter_preferences' in payload and isinstance(payload['filter_preferences'], dict):
        pref.filter_preferences = payload['filter_preferences']
    pref.updated_at = now_utc()
    db.commit()

    log_event('profile', logging.INFO, 'Profil tercihleri güncellendi', module='profile', action='preferences_update', user_id=user.id, username=user.username, user_role=user.role.name, request_id=getattr(request.state, 'request_id', None), ip_address=request.client.host if request.client else None)
    return {'ok': True}


@router.put('/password', dependencies=[Depends(enforce_csrf)])
def profile_password_change(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_password = payload.get('new_password')
    if not new_password or len(new_password) < 8:
        raise HTTPException(status_code=400, detail='Yeni şifre en az 8 karakter olmalı')
    force_password_change(db, user, new_password)
    log_event('auth', logging.INFO, 'Profil ekranından şifre değiştirildi', module='auth', action='change_password', user_id=user.id, username=user.username, user_role=user.role.name, request_id=getattr(request.state, 'request_id', None), ip_address=request.client.host if request.client else None)
    return {'ok': True}
