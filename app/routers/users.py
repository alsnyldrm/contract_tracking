from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user, require_admin
from app.core.security import now_utc
from app.models import Role, User
from app.services.audit_service import add_audit_log

router = APIRouter()


@router.get('/')
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(User).filter(User.is_deleted.is_(False)).order_by(User.created_at.desc()).all()
    return [
        {
            'id': r.id,
            'username': r.username,
            'full_name': r.full_name,
            'email': r.email,
            'role': r.role.name,
            'auth_source': r.auth_source,
            'is_active': r.is_active,
            'must_change_password': r.must_change_password,
            'created_at': str(r.created_at),
        }
        for r in rows
    ]


@router.put('/{user_id}/role', dependencies=[Depends(enforce_csrf)])
def change_role(user_id: int, payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(status_code=404, detail='Kullanıcı bulunamadı')
    role_name = payload.get('role')
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail='Geçersiz rol')

    prev = target.role.name
    target.role_id = role.id
    target.updated_at = now_utc()
    db.commit()

    add_audit_log(
        db,
        table_name='users',
        record_id=str(target.id),
        action='role_change',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values={'role': prev},
        new_values={'role': role.name},
    )
    return {'ok': True}
