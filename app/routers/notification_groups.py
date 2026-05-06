from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user, require_admin
from app.core.security import now_utc
from app.models import Contract, NotificationGroup, NotificationGroupMember, Role, User
from app.services.audit_service import add_audit_log
from app.services.ldap_service import search_ldap_users

router = APIRouter()


def _normalize_user_ids(raw_user_ids) -> list[int]:
    if raw_user_ids is None:
        return []
    if not isinstance(raw_user_ids, list):
        raise HTTPException(status_code=400, detail='Kullanıcı listesi geçersiz')
    out: list[int] = []
    for item in raw_user_ids:
        try:
            uid = int(item)
        except (TypeError, ValueError):
            continue
        if uid > 0 and uid not in out:
            out.append(uid)
    return out


def _normalize_members(raw_members) -> list[dict]:
    if raw_members is None:
        return []
    if not isinstance(raw_members, list):
        raise HTTPException(status_code=400, detail='AD kullanıcı listesi geçersiz')

    out: list[dict] = []
    seen: set[str] = set()

    for item in raw_members:
        if not isinstance(item, dict):
            continue
        member_id = item.get('id')
        try:
            member_id = int(member_id) if member_id not in (None, '') else None
        except (TypeError, ValueError):
            member_id = None

        username = (item.get('username') or '').strip()
        email = (item.get('email') or '').strip().lower() or None
        full_name = (item.get('full_name') or item.get('display_name') or '').strip() or None

        if not username and not email and not member_id:
            continue

        key = str(member_id) if member_id else (f'u:{username.lower()}' if username else f'e:{email}')
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                'id': member_id,
                'username': username,
                'email': email,
                'full_name': full_name,
            }
        )
    return out


def _load_active_users(db: Session, user_ids: list[int]) -> list[User]:
    if not user_ids:
        return []
    users = (
        db.query(User)
        .filter(User.id.in_(user_ids), User.is_deleted.is_(False), User.is_active.is_(True))
        .all()
    )
    if len(users) != len(user_ids):
        raise HTTPException(status_code=400, detail='Seçilen kullanıcıların bir kısmı geçersiz veya pasif')
    return users


def _sanitize_username(value: str) -> str:
    cleaned = ''.join(ch for ch in value if ch.isalnum() or ch in '._-').strip('._-')
    return cleaned or 'ldap.user'


def _build_unique_username(db: Session, preferred_username: str | None, email: str | None) -> str:
    base = (preferred_username or '').strip()
    if not base and email:
        base = email.split('@', 1)[0]
    base = _sanitize_username(base or 'ldap.user')

    candidate = base
    idx = 1
    while db.query(User).filter(func.lower(User.username) == candidate.lower()).first():
        idx += 1
        candidate = f'{base}.{idx}'
    return candidate


def _get_readonly_role_id(db: Session) -> int:
    role = db.query(Role).filter(Role.name == 'readonly').first()
    if not role:
        raise HTTPException(status_code=500, detail='readonly rolü bulunamadı')
    return role.id


def _resolve_member_user_ids(db: Session, members: list[dict]) -> list[int]:
    if not members:
        return []

    role_id = _get_readonly_role_id(db)
    ts = now_utc()
    user_ids: list[int] = []

    for member in members:
        member_id = member.get('id')
        username = (member.get('username') or '').strip()
        email = (member.get('email') or '').strip().lower() or None
        full_name = (member.get('full_name') or '').strip() or None

        row = None
        if member_id:
            row = db.query(User).filter(User.id == member_id).first()

        if not row and username:
            row = db.query(User).filter(func.lower(User.username) == username.lower()).first()

        if not row and email:
            row = db.query(User).filter(func.lower(User.email) == email.lower()).first()

        if not row:
            row = User(
                username=_build_unique_username(db, username, email),
                password_hash=None,
                email=email,
                full_name=full_name or username or (email.split('@', 1)[0] if email else 'LDAP Kullanıcı'),
                auth_source='ldap',
                must_change_password=False,
                is_active=True,
                role_id=role_id,
                created_at=ts,
                updated_at=ts,
                is_deleted=False,
                deleted_at=None,
            )
            db.add(row)
            db.flush()
        else:
            if row.is_deleted:
                row.is_deleted = False
                row.deleted_at = None
            row.is_active = True
            if full_name and row.auth_source == 'ldap':
                row.full_name = full_name
            if email and row.email != email and row.auth_source == 'ldap':
                conflict = db.query(User).filter(User.id != row.id, func.lower(User.email) == email.lower()).first()
                if not conflict:
                    row.email = email
            row.updated_at = ts

        if row.id not in user_ids:
            user_ids.append(row.id)

    return user_ids


@router.get('/users')
def list_users_for_groups(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = (
        db.query(User)
        .filter(User.is_deleted.is_(False), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )
    return [
        {
            'id': r.id,
            'username': r.username,
            'full_name': r.full_name,
            'email': r.email,
            'auth_source': r.auth_source,
        }
        for r in rows
    ]


@router.get('/ad-search')
def ad_search_users(
    request: Request,
    q: str = Query(..., min_length=2),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    request_meta = {
        'request_id': getattr(request.state, 'request_id', None),
        'ip_address': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
    }

    rows = search_ldap_users(db, q, request_meta)
    out: list[dict] = []

    for row in rows:
        username = (row.get('username') or '').strip()
        email = (row.get('email') or '').strip().lower() or None

        existing = None
        if username:
            existing = db.query(User).filter(func.lower(User.username) == username.lower()).first()
        if not existing and email:
            existing = db.query(User).filter(func.lower(User.email) == email.lower()).first()

        out.append(
            {
                'id': existing.id if existing else None,
                'username': username,
                'full_name': (row.get('full_name') or row.get('display_name') or '').strip(),
                'email': email,
                'department': row.get('department') or '',
                'title': row.get('title') or '',
                'auth_source': 'ldap',
            }
        )

    return out


@router.get('/options')
def list_group_options(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(NotificationGroup)
        .order_by(NotificationGroup.is_active.desc(), NotificationGroup.name.asc())
        .all()
    )

    counts: dict[int, int] = {}
    if rows:
        group_ids = [r.id for r in rows]
        member_rows = (
            db.query(NotificationGroupMember.group_id)
            .filter(NotificationGroupMember.group_id.in_(group_ids))
            .all()
        )
        for mr in member_rows:
            counts[mr.group_id] = counts.get(mr.group_id, 0) + 1

    return [
        {
            'id': r.id,
            'name': r.name,
            'is_active': r.is_active,
            'member_count': counts.get(r.id, 0),
        }
        for r in rows
    ]


@router.get('/')
def list_groups(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(NotificationGroup).order_by(NotificationGroup.updated_at.desc()).all()
    group_ids = [r.id for r in rows]

    members_map: dict[int, list[dict]] = {}
    if group_ids:
        member_rows = (
            db.query(NotificationGroupMember.group_id, User.id, User.username, User.full_name, User.email, User.auth_source)
            .join(User, User.id == NotificationGroupMember.user_id)
            .filter(NotificationGroupMember.group_id.in_(group_ids), User.is_deleted.is_(False), User.is_active.is_(True))
            .order_by(User.full_name.asc())
            .all()
        )
        for group_id, uid, username, full_name, email, auth_source in member_rows:
            members_map.setdefault(group_id, []).append(
                {
                    'id': uid,
                    'username': username,
                    'full_name': full_name,
                    'email': email,
                    'auth_source': auth_source,
                }
            )

    return [
        {
            'id': r.id,
            'name': r.name,
            'description': r.description,
            'is_active': r.is_active,
            'members': members_map.get(r.id, []),
            'member_count': len(members_map.get(r.id, [])),
            'created_at': str(r.created_at),
            'updated_at': str(r.updated_at),
        }
        for r in rows
    ]


@router.post('/', dependencies=[Depends(enforce_csrf)])
def create_group(
    payload: dict,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    name = (payload.get('name') or '').strip()
    description = (payload.get('description') or '').strip() or None
    is_active = bool(payload.get('is_active', True))
    members = _normalize_members(payload.get('members'))
    user_ids = _normalize_user_ids(payload.get('user_ids')) if not members else _resolve_member_user_ids(db, members)

    if not name:
        raise HTTPException(status_code=400, detail='Grup adı zorunludur')

    exists = db.query(NotificationGroup).filter(NotificationGroup.name.ilike(name)).first()
    if exists:
        raise HTTPException(status_code=409, detail='Bu grup adı zaten kullanılıyor')

    if members:
        if not user_ids:
            raise HTTPException(status_code=400, detail='AD üzerinde seçilen kullanıcılar eklenemedi')
    else:
        _load_active_users(db, user_ids)

    if not user_ids:
        raise HTTPException(status_code=400, detail='En az bir kullanıcı seçmelisiniz')

    ts = now_utc()
    row = NotificationGroup(
        name=name,
        description=description,
        is_active=is_active,
        created_by_user_id=admin.id,
        updated_by_user_id=admin.id,
        created_at=ts,
        updated_at=ts,
    )
    db.add(row)
    db.flush()

    for uid in user_ids:
        db.add(NotificationGroupMember(group_id=row.id, user_id=uid, created_at=ts))

    db.commit()

    add_audit_log(
        db,
        table_name='notification_groups',
        record_id=str(row.id),
        action='create',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        new_values={'name': row.name, 'is_active': row.is_active, 'member_count': len(user_ids)},
    )
    return {'ok': True, 'id': row.id}


@router.put('/{group_id}', dependencies=[Depends(enforce_csrf)])
def update_group(
    group_id: int,
    payload: dict,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(NotificationGroup).filter(NotificationGroup.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Bildirim grubu bulunamadı')

    previous = {
        'name': row.name,
        'description': row.description,
        'is_active': row.is_active,
    }

    if 'name' in payload:
        new_name = (payload.get('name') or '').strip()
        if not new_name:
            raise HTTPException(status_code=400, detail='Grup adı zorunludur')
        conflict = (
            db.query(NotificationGroup)
            .filter(NotificationGroup.id != row.id, NotificationGroup.name.ilike(new_name))
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail='Bu grup adı zaten kullanılıyor')
        row.name = new_name

    if 'description' in payload:
        row.description = (payload.get('description') or '').strip() or None

    if 'is_active' in payload:
        row.is_active = bool(payload.get('is_active'))

    member_count = None
    if 'members' in payload or 'user_ids' in payload:
        members = _normalize_members(payload.get('members')) if 'members' in payload else []
        user_ids = _normalize_user_ids(payload.get('user_ids')) if not members else _resolve_member_user_ids(db, members)

        if members:
            if not user_ids:
                raise HTTPException(status_code=400, detail='AD üzerinde seçilen kullanıcılar eklenemedi')
        else:
            _load_active_users(db, user_ids)

        if not user_ids:
            raise HTTPException(status_code=400, detail='En az bir kullanıcı seçmelisiniz')

        db.query(NotificationGroupMember).filter(NotificationGroupMember.group_id == row.id).delete()
        ts = now_utc()
        for uid in user_ids:
            db.add(NotificationGroupMember(group_id=row.id, user_id=uid, created_at=ts))
        member_count = len(user_ids)

    row.updated_by_user_id = admin.id
    row.updated_at = now_utc()
    db.commit()

    add_audit_log(
        db,
        table_name='notification_groups',
        record_id=str(row.id),
        action='update',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values=previous,
        new_values={
            'name': row.name,
            'description': row.description,
            'is_active': row.is_active,
            'member_count': member_count,
        },
    )
    return {'ok': True}


@router.delete('/{group_id}', dependencies=[Depends(enforce_csrf)])
def delete_group(
    group_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(NotificationGroup).filter(NotificationGroup.id == group_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Bildirim grubu bulunamadı')

    in_use = (
        db.query(Contract)
        .filter(Contract.is_deleted.is_(False), Contract.notification_group_id == row.id)
        .count()
    )
    if in_use > 0:
        raise HTTPException(
            status_code=400,
            detail='Bu grup bir veya daha fazla sözleşmede kullanılıyor. Önce sözleşmelerden kaldırın.',
        )

    previous = {'name': row.name}

    db.query(NotificationGroupMember).filter(NotificationGroupMember.group_id == row.id).delete()
    db.delete(row)
    db.commit()

    add_audit_log(
        db,
        table_name='notification_groups',
        record_id=str(group_id),
        action='delete',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values=previous,
    )
    return {'ok': True}
