from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import token_fingerprint
from app.models import User, UserPreference, UserSession
from app.services.common import get_timezone, now_local

router = APIRouter()
settings = get_settings()


def _get_user_from_cookie(request: Request, db: Session) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    session = db.query(UserSession).filter(UserSession.session_token_hash == token_fingerprint(token)).first()
    if not session or session.expires_at < datetime.now(timezone.utc):
        return None
    user = db.query(User).filter(User.id == session.user_id, User.is_deleted.is_(False), User.is_active.is_(True)).first()
    return user


def _protected_context(request: Request, db: Session):
    user = _get_user_from_cookie(request, db)
    if not user:
        return None
    pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    return {
        'request': request,
        'user': user,
        'preferences': {
            'dark_mode': pref.dark_mode if pref else False,
            'sidebar_collapsed': pref.sidebar_collapsed if pref else False,
            'filter_preferences': pref.filter_preferences if pref else {},
        },
        'timezone': get_timezone(db),
        'now_local': now_local(db),
        'csrf_token': request.cookies.get(settings.csrf_cookie_name, ''),
        'current_path': request.url.path,
    }


@router.get('/')
def home(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_cookie(request, db)
    return RedirectResponse('/dashboard' if user else '/login')


@router.get('/login')
def login_page(request: Request, db: Session = Depends(get_db)):
    user = _get_user_from_cookie(request, db)
    if user:
        return RedirectResponse('/dashboard')
    return request.app.state.templates.TemplateResponse('login.html', {'request': request})


@router.get('/dashboard')
def dashboard_page(request: Request, db: Session = Depends(get_db)):
    ctx = _protected_context(request, db)
    if not ctx:
        return RedirectResponse('/login')
    return request.app.state.templates.TemplateResponse('dashboard.html', ctx)


@router.get('/institutions')
def institutions_page(request: Request, db: Session = Depends(get_db)):
    ctx = _protected_context(request, db)
    if not ctx:
        return RedirectResponse('/login')
    return request.app.state.templates.TemplateResponse('institutions.html', ctx)


@router.get('/contracts')
def contracts_page(request: Request, db: Session = Depends(get_db)):
    ctx = _protected_context(request, db)
    if not ctx:
        return RedirectResponse('/login')
    return request.app.state.templates.TemplateResponse('contracts.html', ctx)


@router.get('/reports')
def reports_page(request: Request, db: Session = Depends(get_db)):
    ctx = _protected_context(request, db)
    if not ctx:
        return RedirectResponse('/login')
    return request.app.state.templates.TemplateResponse('reports.html', ctx)


@router.get('/users')
def users_page(request: Request, db: Session = Depends(get_db)):
    ctx = _protected_context(request, db)
    if not ctx:
        return RedirectResponse('/login')
    if ctx['user'].role.name != 'admin':
        return RedirectResponse('/dashboard')
    return request.app.state.templates.TemplateResponse('users.html', ctx)


@router.get('/logs')
def logs_page(request: Request, db: Session = Depends(get_db)):
    ctx = _protected_context(request, db)
    if not ctx:
        return RedirectResponse('/login')
    if ctx['user'].role.name != 'admin':
        return RedirectResponse('/dashboard')
    return request.app.state.templates.TemplateResponse('logs.html', ctx)


@router.get('/settings')
def settings_page(request: Request, db: Session = Depends(get_db)):
    ctx = _protected_context(request, db)
    if not ctx:
        return RedirectResponse('/login')
    if ctx['user'].role.name != 'admin':
        return RedirectResponse('/dashboard')
    return request.app.state.templates.TemplateResponse('settings.html', ctx)


@router.get('/profile')
def profile_page(request: Request, db: Session = Depends(get_db)):
    ctx = _protected_context(request, db)
    if not ctx:
        return RedirectResponse('/login')
    return request.app.state.templates.TemplateResponse('profile.html', ctx)
