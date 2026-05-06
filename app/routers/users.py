from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user, require_admin
from app.core.security import hash_password, now_utc
from app.models import (
    AuditLog,
    Contract,
    ContractDocument,
    Notification,
    NotificationGroup,
    NotificationGroupMember,
    Role,
    User,
    UserPreference,
    UserSession,
)
from app.services.audit_service import add_audit_log
from app.services.auth_service import create_local_user

router = APIRouter()


@router.get('/')
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(User)
        .options(joinedload(User.role))
        .filter(User.is_deleted.is_(False), User.auth_source != 'ldap')
        .order_by(User.created_at.desc())
        .all()
    )
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


@router.post('/', dependencies=[Depends(enforce_csrf)])
def create_user(payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    username = (payload.get('username') or '').strip()
    full_name = (payload.get('full_name') or '').strip()
    email = (payload.get('email') or '').strip() or None
    password = payload.get('password') or ''
    role_name = (payload.get('role') or '').strip()

    if not username or not full_name or not password or not role_name:
        raise HTTPException(status_code=400, detail='Kullanıcı adı, ad soyad, şifre ve rol zorunludur')
    if len(password) < 8:
        raise HTTPException(status_code=400, detail='Şifre en az 8 karakter olmalı')
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail='Bu kullanıcı adı zaten kullanılıyor')
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail='Bu e-posta zaten kayıtlı')
    if not db.query(Role).filter(Role.name == role_name).first():
        raise HTTPException(status_code=400, detail='Geçersiz rol')

    user = create_local_user(
        db=db,
        username=username,
        password=password,
        full_name=full_name,
        email=email,
        role_name=role_name,
        must_change_password=True,
    )

    add_audit_log(
        db,
        table_name='users',
        record_id=str(user.id),
        action='create',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values=None,
        new_values={'username': user.username, 'role': role_name, 'auth_source': 'local'},
    )
    return {'ok': True, 'id': user.id}


@router.put('/{user_id}', dependencies=[Depends(enforce_csrf)])
def update_user_profile(user_id: int, payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(status_code=404, detail='Kullanıcı bulunamadı')

    prev = {
        'username': target.username,
        'full_name': target.full_name,
        'email': target.email,
    }

    if 'full_name' in payload:
        full_name = (payload.get('full_name') or '').strip()
        if not full_name:
            raise HTTPException(status_code=400, detail='Ad Soyad boş olamaz')
        if len(full_name) > 255:
            raise HTTPException(status_code=400, detail='Ad Soyad çok uzun (maks. 255 karakter)')
        target.full_name = full_name

    if 'email' in payload:
        email = (payload.get('email') or '').strip() or None
        if email:
            exists = (
                db.query(User)
                .filter(User.id != target.id, User.is_deleted.is_(False), func.lower(User.email) == email.lower())
                .first()
            )
            if exists:
                raise HTTPException(status_code=409, detail='Bu e-posta zaten kayıtlı')
        target.email = email

    if 'username' in payload:
        username = (payload.get('username') or '').strip()
        if target.auth_source != 'local':
            raise HTTPException(status_code=400, detail='LDAP/SAML kullanıcılarında kullanıcı adı değiştirilemez')
        if not username:
            raise HTTPException(status_code=400, detail='Kullanıcı adı boş olamaz')
        exists = (
            db.query(User)
            .filter(User.id != target.id, User.is_deleted.is_(False), func.lower(User.username) == username.lower())
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail='Bu kullanıcı adı zaten kullanılıyor')
        target.username = username

    target.updated_at = now_utc()
    db.commit()

    add_audit_log(
        db,
        table_name='users',
        record_id=str(target.id),
        action='profile_update',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values=prev,
        new_values={'username': target.username, 'full_name': target.full_name, 'email': target.email},
    )
    return {'ok': True}


@router.put('/{user_id}/active', dependencies=[Depends(enforce_csrf)])
def toggle_active(user_id: int, payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(status_code=404, detail='Kullanıcı bulunamadı')
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail='Kendi hesabınızı pasifleştiremezsiniz')
    new_state = bool(payload.get('is_active'))
    prev = target.is_active
    target.is_active = new_state
    target.updated_at = now_utc()
    db.commit()
    add_audit_log(
        db,
        table_name='users',
        record_id=str(target.id),
        action='active_change',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values={'is_active': prev},
        new_values={'is_active': new_state},
    )
    return {'ok': True}


@router.put('/{user_id}/reset-password', dependencies=[Depends(enforce_csrf)])
def reset_password(user_id: int, payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(status_code=404, detail='Kullanıcı bulunamadı')
    if target.auth_source != 'local':
        raise HTTPException(status_code=400, detail='SAML kullanıcısının şifresi sıfırlanamaz')
    new_password = payload.get('password') or ''
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail='Şifre en az 8 karakter olmalı')
    target.password_hash = hash_password(new_password)
    target.must_change_password = True
    target.updated_at = now_utc()
    db.commit()
    add_audit_log(
        db,
        table_name='users',
        record_id=str(target.id),
        action='password_reset',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values=None,
        new_values=None,
    )
    return {'ok': True}


@router.delete('/{user_id}', dependencies=[Depends(enforce_csrf)])
def delete_user(user_id: int, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not target:
        raise HTTPException(status_code=404, detail='Kullanıcı bulunamadı')
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail='Kendi hesabınızı silemezsiniz')

    # Kritik iş kayıtlarında referans varsa kullanıcıyı fiziksel silmeyiz.
    blocking_refs = {
        'contracts_created': db.query(Contract).filter(Contract.created_by_user_id == target.id).count(),
        'contracts_updated': db.query(Contract).filter(Contract.updated_by_user_id == target.id).count(),
        'documents_uploaded': db.query(ContractDocument).filter(ContractDocument.uploaded_by_user_id == target.id).count(),
        'notification_groups_created': db.query(NotificationGroup).filter(NotificationGroup.created_by_user_id == target.id).count(),
        'notification_groups_updated': db.query(NotificationGroup).filter(NotificationGroup.updated_by_user_id == target.id).count(),
    }
    if any(blocking_refs.values()):
        raise HTTPException(
            status_code=409,
            detail='Kullanıcı kritik kayıtlarda referanslı olduğu için silinemedi. Önce sahip olduğu kayıtları başka kullanıcıya aktarın.',
        )

    # Eski oturum/tercih izleri kalmaması için ilişkili kayıtları temizle.
    db.query(UserSession).filter(UserSession.user_id == target.id).delete()
    db.query(UserPreference).filter(UserPreference.user_id == target.id).delete()
    db.query(Notification).filter(Notification.user_id == target.id).delete()
    db.query(NotificationGroupMember).filter(NotificationGroupMember.user_id == target.id).delete()
    db.query(AuditLog).filter(AuditLog.user_id == target.id).update({'user_id': None}, synchronize_session=False)
    db.delete(target)
    db.commit()

    add_audit_log(
        db,
        table_name='users',
        record_id=str(user_id),
        action='hard_delete',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values={'username': target.username},
        new_values=None,
    )
    return {'ok': True}


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
