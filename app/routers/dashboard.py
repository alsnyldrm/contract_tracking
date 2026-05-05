from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Contract, ContractType, Institution, Notification, User

router = APIRouter()


@router.get('/summary')
def dashboard_summary(
    q: str | None = None,
    institution_id: int | None = None,
    status: str | None = None,
    critical_level: str | None = None,
    expiring_days: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    in_7  = today + timedelta(days=7)
    in_30 = today + timedelta(days=30)
    in_60 = today + timedelta(days=60)
    in_90 = today + timedelta(days=90)
    month_start = today.replace(day=1)

    base = db.query(Contract).filter(Contract.is_deleted.is_(False))

    if q:
        inst_ids = [i.id for i in db.query(Institution.id).filter(Institution.name.ilike(f'%{q}%')).all()]
        base = base.filter(or_(
            Contract.contract_name.ilike(f'%{q}%'),
            Contract.contract_number.ilike(f'%{q}%'),
            Contract.institution_id.in_(inst_ids),
        ))
    if institution_id:
        base = base.filter(Contract.institution_id == institution_id)
    if status:
        base = base.filter(Contract.status == status)
    if critical_level:
        base = base.filter(Contract.critical_level == critical_level)
    if expiring_days:
        base = base.filter(Contract.end_date <= date.fromordinal(today.toordinal() + expiring_days), Contract.end_date >= today)

    total_contracts = base.count()
    active_q = base.filter(Contract.status == 'Aktif')

    widgets = {
        'toplam_kurum':       db.query(Institution).filter(Institution.is_deleted.is_(False)).count(),
        'toplam_sozlesme':    total_contracts,
        'aktif_sozlesme':     base.filter(Contract.status == 'Aktif').count(),
        'suresi_dolmus':      base.filter(Contract.status == 'Süresi Doldu').count(),
        'kritik_sozlesme':    base.filter(Contract.critical_level == 'Kritik').count(),
        'bitecek_7':          base.filter(Contract.end_date <= in_7,  Contract.end_date >= today).count(),
        'bitecek_30':         base.filter(Contract.end_date <= in_30, Contract.end_date >= today).count(),
        'bitecek_60':         base.filter(Contract.end_date <= in_60, Contract.end_date >= today).count(),
        'bitecek_90':         base.filter(Contract.end_date <= in_90, Contract.end_date >= today).count(),
        'aylik_yenilenecek':  base.filter(Contract.renewal_date <= in_30, Contract.renewal_date >= today).count(),
        'toplam_tutar_tl':    float(base.with_entities(func.coalesce(func.sum(Contract.amount), 0)).scalar() or 0),
        'taslak_sozlesme':    base.filter(Contract.status == 'Taslak').count(),
        'iptal_sozlesme':     base.filter(Contract.status == 'İptal').count(),
        'yenilendi_sozlesme': base.filter(Contract.status == 'Yenilendi').count(),
        'bu_ay_eklenen':      base.filter(Contract.created_at >= month_start).count(),
    }

    nearest = (
        base.filter(Contract.end_date.is_not(None))
        .order_by(Contract.end_date.asc())
        .limit(10).all()
    )
    latest = base.order_by(Contract.created_at.desc()).limit(10).all()

    by_status = (
        db.query(Contract.status, func.count(Contract.id))
        .filter(Contract.is_deleted.is_(False))
        .group_by(Contract.status).all()
    )
    by_contract_type = (
        db.query(ContractType.name, func.count(Contract.id))
        .join(Contract, Contract.contract_type_id == ContractType.id)
        .filter(Contract.is_deleted.is_(False))
        .group_by(ContractType.name).all()
    )
    by_responsible = (
        db.query(Contract.responsible_person_name, func.count(Contract.id))
        .filter(Contract.is_deleted.is_(False), Contract.responsible_person_name.is_not(None))
        .group_by(Contract.responsible_person_name)
        .order_by(func.count(Contract.id).desc())
        .limit(10).all()
    )

    return {
        'widgets': widgets,
        'nearest_contracts': [
            {
                'id': c.id,
                'contract_name': c.contract_name,
                'end_date': str(c.end_date),
                'status': c.status,
                'critical_level': c.critical_level,
            }
            for c in nearest
        ],
        'latest_contracts': [
            {
                'id': c.id,
                'contract_name': c.contract_name,
                'created_at': str(c.created_at),
                'status': c.status,
            }
            for c in latest
        ],
        'status_chart': [{'status': s, 'count': c} for s, c in by_status],
        'institution_type_chart': [{'name': n, 'count': c} for n, c in by_contract_type],
        'responsible_chart': [{'name': n or 'Belirtilmemiş', 'count': c} for n, c in by_responsible],
    }


@router.get('/notifications')
def my_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(30).all()
    )
    return [
        {
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': str(n.created_at),
        }
        for n in rows
    ]
