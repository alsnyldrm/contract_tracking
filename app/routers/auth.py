import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse, Response as FastAPIResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.logging_config import log_event
from app.models import User
from app.services.auth_service import (
    authenticate_local_user,
    clear_session,
    create_session,
    force_password_change,
    is_login_locked,
    log_auth_event,
    register_login_attempt,
)
from app.services.saml_service import get_metadata, process_acs, start_saml_login

router = APIRouter(tags=['auth'])


@router.post('/auth/login')
def local_login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    ip = request.client.host if request.client else None
    ua = request.headers.get('user-agent')

    if is_login_locked(db, username, ip):
        register_login_attempt(db, username, ip, False, 'rate_limit')
        log_event('security', logging.WARNING, 'Brute force koruması tetiklendi', module='security', action='login_rate_limit', ip_address=ip, user_agent=ua, request_id=getattr(request.state, 'request_id', None), details={'username': username})
        raise HTTPException(status_code=429, detail='Çok fazla başarısız deneme. Lütfen daha sonra tekrar deneyin.')

    user = authenticate_local_user(db, username, password)
    if not user:
        register_login_attempt(db, username, ip, False, 'invalid_credentials')
        log_auth_event('Başarısız giriş denemesi', action='login_failed', request_id=getattr(request.state, 'request_id', None), ip_address=ip, user_agent=ua, details={'username': username}, level=logging.WARNING)
        raise HTTPException(status_code=401, detail='Kullanıcı adı veya şifre hatalı')

    if not user.is_active:
        register_login_attempt(db, username, ip, False, 'inactive')
        raise HTTPException(status_code=401, detail='Kullanıcı pasif durumda')

    register_login_attempt(db, username, ip, True)
    create_session(db, response, user, ip, ua)
    log_auth_event('Başarılı giriş', action='login_success', user=user, request_id=getattr(request.state, 'request_id', None), ip_address=ip, user_agent=ua)

    return {'ok': True, 'must_change_password': user.must_change_password, 'role': user.role.name}


@router.post('/auth/logout')
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get('ct_session')
    clear_session(db, response, token)
    log_auth_event('Çıkış yapıldı', action='logout', request_id=getattr(request.state, 'request_id', None), ip_address=request.client.host if request.client else None, user_agent=request.headers.get('user-agent'))
    return {'ok': True}


@router.post('/auth/change-password')
def change_password(request: Request, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_password = payload.get('new_password', '')
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail='Şifre en az 8 karakter olmalı')
    force_password_change(db, user, new_password)
    log_auth_event('Şifre güncellendi', action='change_password', user=user, request_id=getattr(request.state, 'request_id', None), ip_address=request.client.host if request.client else None)
    return {'ok': True}


@router.get('/auth/saml/login')
def saml_login(request: Request, db: Session = Depends(get_db)):
    try:
        login_url = start_saml_login(db, request)
        log_event('saml', logging.INFO, 'SAML login başlatıldı', module='saml', action='start_login', ip_address=request.client.host if request.client else None, request_id=getattr(request.state, 'request_id', None))
        return RedirectResponse(login_url)
    except Exception as exc:
        log_event('saml', logging.ERROR, 'SAML login başlatılamadı', module='saml', action='start_login', request_id=getattr(request.state, 'request_id', None), details={'error': str(exc)}, exc_info=exc)
        return RedirectResponse('/login?error=saml')


@router.post('/auth/saml/acs')
async def saml_acs(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    post_data = {k: v for k, v in form.items()}
    try:
        user = process_acs(db, request, post_data)
        redirect = RedirectResponse('/dashboard', status_code=302)
        create_session(db, redirect, user, request.client.host if request.client else None, request.headers.get('user-agent'))
        return redirect
    except Exception as exc:
        log_event('saml', logging.ERROR, 'SAML ACS hatası', module='saml', action='acs', request_id=getattr(request.state, 'request_id', None), details={'error': str(exc)}, exc_info=exc)
        return RedirectResponse('/login?error=samlacs')


@router.get('/auth/saml/metadata')
def saml_metadata(request: Request, db: Session = Depends(get_db), download: bool = Query(default=False)):
    metadata = get_metadata(db, request)
    headers = {'Content-Disposition': 'attachment; filename="metadata.xml"'} if download else None
    return FastAPIResponse(content=metadata, media_type='application/samlmetadata+xml', headers=headers)
