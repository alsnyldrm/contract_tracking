from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user, require_admin
from app.core.security import now_utc
from app.models import Contract, ContractTag, ContractType, Currency, Institution, Tag, User
from app.services.audit_service import add_audit_log
from app.services.ldap_service import search_ldap_users

router = APIRouter()

SAFE_SORT_COLUMNS = {
    'contract_number', 'contract_name', 'status', 'critical_level',
    'end_date', 'amount', 'updated_at', 'created_at', 'start_date',
}


def _get_tags(db: Session, contract_id: int) -> list[str]:
    rows = (
        db.query(Tag.name)
        .join(ContractTag, ContractTag.tag_id == Tag.id)
        .filter(ContractTag.contract_id == contract_id)
        .all()
    )
    return [r.name for r in rows]


def _serialize_contract(c: Contract, institution_name: str | None = None, tags: list | None = None, currency_symbol: str | None = None, contract_type_name: str | None = None):
    return {
        'id':                        c.id,
        'contract_number':           c.contract_number,
        'institution_id':            c.institution_id,
        'institution_name':          institution_name,
        'contract_name':             c.contract_name,
        'contract_type_id':          c.contract_type_id,
        'contract_type_name':        contract_type_name,
        'start_date':                str(c.start_date) if c.start_date else None,
        'end_date':                  str(c.end_date) if c.end_date else None,
        'signed_date':               str(c.signed_date) if c.signed_date else None,
        'renewal_date':              str(c.renewal_date) if c.renewal_date else None,
        'amount':                    float(c.amount) if c.amount else None,
        'currency_id':               c.currency_id,
        'currency_symbol':           currency_symbol,
        'vat_included':              c.vat_included,
        'payment_period':            c.payment_period,
        'responsible_person_name':   c.responsible_person_name,
        'responsible_person_email':  c.responsible_person_email,
        'responsible_person_username': c.responsible_person_username,
        'responsible_department':    c.responsible_department,
        'status':                    c.status,
        'critical_level':            c.critical_level,
        'reminder_days':             c.reminder_days,
        'auto_renewal':              c.auto_renewal,
        'termination_notice_days':   c.termination_notice_days,
        'description':               c.description,
        'internal_notes':            c.internal_notes,
        'tags':                      tags if tags is not None else [],
        'created_by_user_id':        c.created_by_user_id,
        'updated_by_user_id':        c.updated_by_user_id,
        'created_at':                str(c.created_at),
        'updated_at':                str(c.updated_at),
    }


def _coerce_int(value: str | None) -> int | None:
    if value is None or value == '':
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@router.get('/')
def list_contracts(
    q: str | None = None,
    institution_id: str | None = None,
    contract_type_id: str | None = None,
    status: str | None = None,
    critical_level: str | None = None,
    responsible: str | None = None,
    tag: str | None = None,
    expiring_days: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    sort_by: str = 'updated_at',
    sort_dir: str = 'desc',
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    institution_id_i = _coerce_int(institution_id)
    contract_type_id_i = _coerce_int(contract_type_id)
    expiring_days_i = _coerce_int(expiring_days)

    if sort_by not in SAFE_SORT_COLUMNS:
        sort_by = 'updated_at'

    query = (
        db.query(Contract, Institution.name)
        .join(Institution, Institution.id == Contract.institution_id)
        .filter(Contract.is_deleted.is_(False))
    )

    if q:
        query = query.filter(
            or_(
                Contract.contract_number.ilike(f'%{q}%'),
                Contract.contract_name.ilike(f'%{q}%'),
                Institution.name.ilike(f'%{q}%'),
                Contract.responsible_person_name.ilike(f'%{q}%'),
            )
        )
    if institution_id_i is not None:
        query = query.filter(Contract.institution_id == institution_id_i)
    if contract_type_id_i is not None:
        query = query.filter(Contract.contract_type_id == contract_type_id_i)
    if status:
        query = query.filter(Contract.status == status)
    if critical_level:
        query = query.filter(Contract.critical_level == critical_level)
    if responsible:
        query = query.filter(Contract.responsible_person_name.ilike(f'%{responsible}%'))
    if start_date:
        query = query.filter(Contract.start_date >= start_date)
    if end_date:
        query = query.filter(Contract.end_date <= end_date)
    if expiring_days_i is not None:
        today = date.today()
        target = date.fromordinal(today.toordinal() + expiring_days_i)
        query = query.filter(Contract.end_date <= target, Contract.end_date >= today)
    if tag:
        query = (
            query
            .join(ContractTag, ContractTag.contract_id == Contract.id)
            .join(Tag, Tag.id == ContractTag.tag_id)
            .filter(Tag.name == tag)
        )

    sort_col = getattr(Contract, sort_by, Contract.updated_at)
    query = query.order_by(sort_col.desc() if sort_dir == 'desc' else sort_col.asc())

    total = query.count()
    rows  = query.offset((page - 1) * page_size).limit(page_size).all()

    contract_ids = [c.id for c, _ in rows]
    tags_map: dict[int, list[str]] = {}
    if contract_ids:
        tag_rows = (
            db.query(ContractTag.contract_id, Tag.name)
            .join(Tag, Tag.id == ContractTag.tag_id)
            .filter(ContractTag.contract_id.in_(contract_ids))
            .all()
        )
        for cid, tname in tag_rows:
            tags_map.setdefault(cid, []).append(tname)

    currency_map: dict[int, str] = {}
    for c, _ in rows:
        if c.currency_id and c.currency_id not in currency_map:
            cur = db.query(Currency).filter(Currency.id == c.currency_id).first()
            if cur:
                currency_map[c.currency_id] = cur.symbol or cur.code

    type_map: dict[int, str] = {}
    for c, _ in rows:
        if c.contract_type_id and c.contract_type_id not in type_map:
            ct = db.query(ContractType).filter(ContractType.id == c.contract_type_id).first()
            if ct:
                type_map[c.contract_type_id] = ct.name

    return {
        'total': total,
        'items': [
            _serialize_contract(
                c, institution_name=name,
                tags=tags_map.get(c.id, []),
                currency_symbol=currency_map.get(c.currency_id),
                contract_type_name=type_map.get(c.contract_type_id),
            )
            for c, name in rows
        ],
    }


@router.get('/types')
def list_contract_types(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(ContractType).order_by(ContractType.name.asc()).all()
    return [{'id': r.id, 'name': r.name, 'is_active': r.is_active} for r in rows]


@router.get('/currencies')
def list_currencies(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Currency).order_by(Currency.code.asc()).all()
    return [{'id': r.id, 'code': r.code, 'name': r.name, 'symbol': r.symbol} for r in rows]


@router.get('/tags')
def list_tags(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Tag).order_by(Tag.name.asc()).all()
    return [{'id': r.id, 'name': r.name} for r in rows]


@router.get('/responsible-search')
def responsible_search(
    request: Request,
    q: str = Query(..., min_length=2),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    request_meta = {
        'request_id': getattr(request.state, 'request_id', None),
        'ip_address': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
    }
    return search_ldap_users(db, q, request_meta)


@router.get('/{contract_id}')
def get_contract(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted.is_(False)).first()
    if not row:
        raise HTTPException(status_code=404, detail='Sözleşme bulunamadı')
    institution = db.query(Institution).filter(Institution.id == row.institution_id).first()
    tags = _get_tags(db, row.id)
    currency_symbol = None
    if row.currency_id:
        cur = db.query(Currency).filter(Currency.id == row.currency_id).first()
        if cur:
            currency_symbol = cur.symbol or cur.code
    type_name = None
    if row.contract_type_id:
        ct = db.query(ContractType).filter(ContractType.id == row.contract_type_id).first()
        if ct:
            type_name = ct.name
    return _serialize_contract(
        row,
        institution_name=institution.name if institution else None,
        tags=tags,
        currency_symbol=currency_symbol,
        contract_type_name=type_name,
    )


@router.post('/', dependencies=[Depends(enforce_csrf)])
def create_contract(
    payload: dict,
    request: Request,
    _: User = Depends(require_admin),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    required = ['contract_number', 'institution_id', 'contract_name']
    for field in required:
        if not payload.get(field):
            raise HTTPException(status_code=400, detail=f'{field} zorunludur')

    ts = now_utc()
    row = Contract(
        contract_number=payload['contract_number'],
        institution_id=payload['institution_id'],
        contract_name=payload['contract_name'],
        contract_type_id=payload.get('contract_type_id'),
        start_date=payload.get('start_date'),
        end_date=payload.get('end_date'),
        signed_date=payload.get('signed_date'),
        renewal_date=payload.get('renewal_date'),
        amount=payload.get('amount'),
        currency_id=payload.get('currency_id'),
        vat_included=bool(payload.get('vat_included', False)),
        payment_period=payload.get('payment_period'),
        responsible_person_name=payload.get('responsible_person_name'),
        responsible_person_email=payload.get('responsible_person_email'),
        responsible_person_username=payload.get('responsible_person_username'),
        responsible_department=payload.get('responsible_department'),
        status=payload.get('status', 'Taslak'),
        critical_level=payload.get('critical_level', 'Düşük'),
        reminder_days=int(payload.get('reminder_days', 30)),
        auto_renewal=bool(payload.get('auto_renewal', False)),
        termination_notice_days=payload.get('termination_notice_days'),
        description=payload.get('description'),
        internal_notes=payload.get('internal_notes'),
        created_by_user_id=user.id,
        updated_by_user_id=user.id,
        created_at=ts,
        updated_at=ts,
        is_deleted=False,
        deleted_at=None,
    )
    db.add(row)
    db.flush()

    _sync_tags(db, row.id, payload.get('tags', []), ts)

    db.commit()
    db.refresh(row)

    add_audit_log(
        db, table_name='contracts', record_id=str(row.id), action='create',
        user=user,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        new_values={'contract_number': row.contract_number, 'status': row.status},
    )
    return {'ok': True, 'id': row.id}


@router.put('/{contract_id}', dependencies=[Depends(enforce_csrf)])
def update_contract(
    contract_id: int,
    payload: dict,
    request: Request,
    _: User = Depends(require_admin),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted.is_(False)).first()
    if not row:
        raise HTTPException(status_code=404, detail='Sözleşme bulunamadı')

    previous = {'status': row.status, 'critical_level': row.critical_level}
    editable = [
        'contract_number', 'institution_id', 'contract_name', 'contract_type_id',
        'start_date', 'end_date', 'signed_date', 'renewal_date', 'amount', 'currency_id',
        'vat_included', 'payment_period', 'responsible_person_name', 'responsible_person_email',
        'responsible_person_username', 'responsible_department', 'status', 'critical_level',
        'reminder_days', 'auto_renewal', 'termination_notice_days', 'description', 'internal_notes',
    ]
    for field in editable:
        if field in payload:
            setattr(row, field, payload[field])
    row.updated_by_user_id = user.id
    row.updated_at = now_utc()

    _sync_tags(db, row.id, payload.get('tags', []), now_utc())

    db.commit()

    add_audit_log(
        db, table_name='contracts', record_id=str(row.id), action='update',
        user=user,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values=previous,
        new_values={'status': row.status, 'critical_level': row.critical_level},
    )
    return {'ok': True}


@router.delete('/{contract_id}', dependencies=[Depends(enforce_csrf)])
def delete_contract(
    contract_id: int,
    request: Request,
    _: User = Depends(require_admin),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(Contract).filter(Contract.id == contract_id, Contract.is_deleted.is_(False)).first()
    if not row:
        raise HTTPException(status_code=404, detail='Sözleşme bulunamadı')

    row.is_deleted = True
    row.deleted_at = now_utc()
    row.updated_at = now_utc()
    row.updated_by_user_id = user.id
    db.commit()

    add_audit_log(
        db, table_name='contracts', record_id=str(row.id), action='delete',
        user=user,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        previous_values={'contract_number': row.contract_number},
    )
    return {'ok': True}


def _sync_tags(db: Session, contract_id: int, tag_names: list | str, ts) -> None:
    if isinstance(tag_names, str):
        tag_names = [t.strip() for t in tag_names.split(',') if t.strip()]
    db.query(ContractTag).filter(ContractTag.contract_id == contract_id).delete()
    for tag_name in tag_names:
        if not tag_name:
            continue
        tag_obj = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag_obj:
            tag_obj = Tag(name=tag_name, created_at=ts, updated_at=ts)
            db.add(tag_obj)
            db.flush()
        db.add(ContractTag(contract_id=contract_id, tag_id=tag_obj.id))
