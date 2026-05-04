from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user, require_admin
from app.core.security import now_utc
from app.models import Institution, InstitutionType, User
from app.services.audit_service import add_audit_log

router = APIRouter()


@router.get('/')
def list_institutions(
    q: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Institution).filter(Institution.is_deleted.is_(False))
    if q:
        query = query.filter(Institution.name.ilike(f'%{q}%'))
    if is_active is not None:
        query = query.filter(Institution.is_active == is_active)
    total = query.count()
    items = query.order_by(Institution.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        'total': total,
        'items': [
            {
                'id': i.id,
                'name': i.name,
                'short_name': i.short_name,
                'tax_no': i.tax_no,
                'tax_office': i.tax_office,
                'sector': i.sector,
                'contact_person': i.contact_person,
                'contact_email': i.contact_email,
                'contact_phone': i.contact_phone,
                'address': i.address,
                'description': i.description,
                'is_active': i.is_active,
                'created_at': str(i.created_at),
                'updated_at': str(i.updated_at),
            }
            for i in items
        ],
    }


@router.post('/', dependencies=[Depends(enforce_csrf)])
def create_institution(payload: dict, request: Request, _: User = Depends(require_admin), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not payload.get('name'):
        raise HTTPException(status_code=400, detail='Kurum adı zorunludur')
    ts = now_utc()
    row = Institution(
        name=payload.get('name'),
        short_name=payload.get('short_name'),
        tax_no=payload.get('tax_no'),
        tax_office=payload.get('tax_office'),
        institution_type_id=payload.get('institution_type_id'),
        sector=payload.get('sector'),
        contact_person=payload.get('contact_person'),
        contact_email=payload.get('contact_email'),
        contact_phone=payload.get('contact_phone'),
        address=payload.get('address'),
        description=payload.get('description'),
        is_active=bool(payload.get('is_active', True)),
        created_at=ts,
        updated_at=ts,
        is_deleted=False,
        deleted_at=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    add_audit_log(
        db,
        table_name='institutions',
        record_id=str(row.id),
        action='create',
        user=user,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        new_values={'name': row.name},
    )
    return {'ok': True, 'id': row.id}


@router.put('/{institution_id}', dependencies=[Depends(enforce_csrf)])
def update_institution(institution_id: int, payload: dict, request: Request, _: User = Depends(require_admin), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(Institution).filter(Institution.id == institution_id, Institution.is_deleted.is_(False)).first()
    if not row:
        raise HTTPException(status_code=404, detail='Kurum bulunamadı')

    previous = {
        'name': row.name,
        'short_name': row.short_name,
        'is_active': row.is_active,
    }

    for field in ['name', 'short_name', 'tax_no', 'tax_office', 'institution_type_id', 'sector', 'contact_person', 'contact_email', 'contact_phone', 'address', 'description', 'is_active']:
        if field in payload:
            setattr(row, field, payload[field])
    row.updated_at = now_utc()
    db.commit()

    add_audit_log(
        db,
        table_name='institutions',
        record_id=str(row.id),
        action='update',
        user=user,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values=previous,
        new_values={'name': row.name, 'short_name': row.short_name, 'is_active': row.is_active},
    )
    return {'ok': True}


@router.delete('/{institution_id}', dependencies=[Depends(enforce_csrf)])
def delete_institution(institution_id: int, request: Request, _: User = Depends(require_admin), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(Institution).filter(Institution.id == institution_id, Institution.is_deleted.is_(False)).first()
    if not row:
        raise HTTPException(status_code=404, detail='Kurum bulunamadı')
    row.is_deleted = True
    row.deleted_at = now_utc()
    row.updated_at = now_utc()
    db.commit()

    add_audit_log(
        db,
        table_name='institutions',
        record_id=str(row.id),
        action='delete',
        user=user,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values={'name': row.name},
    )
    return {'ok': True}


@router.get('/types')
def institution_types(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(InstitutionType).order_by(InstitutionType.name.asc()).all()
    return [{'id': r.id, 'name': r.name} for r in rows]
