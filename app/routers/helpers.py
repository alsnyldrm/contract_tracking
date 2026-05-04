from fastapi import Request
from sqlalchemy.orm import Session

from app.models import UserPreference
from app.services.common import get_timezone


def build_base_context(request: Request, db: Session, user):
    pref = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    return {
        'request': request,
        'user': user,
        'role': user.role.name,
        'preferences': pref,
        'timezone': get_timezone(db),
        'csrf_token': request.cookies.get('ct_csrf', ''),
    }
