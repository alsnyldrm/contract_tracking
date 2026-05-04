from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Contract, ContractType, Institution, Notification, User

router = APIRouter()


@router.get('/summary')
def dashboard_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = date.today()
    in_30 = today + timedelta(days=30)
    in_60 = today + timedelta(days=60)
    in_90 = today + timedelta(days=90)

    contracts_q = db.query(Contract).filter(Contract.is_deleted.is_(False))
    total_contracts = contracts_q.count()

    data = {
        'toplam_kurum': db.query(Institution).filter(Institution.is_deleted.is_(False)).count(),
        'toplam_sozlesme': total_contracts,
        'aktif_sozlesme': contracts_q.filter(Contract.status == 'Aktif').count(),
        'suresi_dolmus': contracts_q.filter(Contract.status == 'Süresi Doldu').count(),
        'bitecek_30': contracts_q.filter(Contract.end_date <= in_30, Contract.end_date >= today).count(),
        'bitecek_60': contracts_q.filter(Contract.end_date <= in_60, Contract.end_date >= today).count(),
        'bitecek_90': contracts_q.filter(Contract.end_date <= in_90, Contract.end_date >= today).count(),
        'kritik_sozlesme': contracts_q.filter(Contract.critical_level == 'Kritik').count(),
        'toplam_tutar': float(contracts_q.with_entities(func.coalesce(func.sum(Contract.amount), 0)).scalar() or 0),
        'aylik_yenilenecek': contracts_q.filter(Contract.renewal_date <= in_30, Contract.renewal_date >= today).count(),
    }

    nearest = (
        contracts_q.filter(Contract.end_date.is_not(None))
        .order_by(Contract.end_date.asc())
        .limit(10)
        .all()
    )
    latest = contracts_q.order_by(Contract.created_at.desc()).limit(10).all()

    by_status = (
        db.query(Contract.status, func.count(Contract.id))
        .filter(Contract.is_deleted.is_(False))
        .group_by(Contract.status)
        .all()
    )

    by_contract_type = (
        db.query(ContractType.name, func.count(Contract.id))
        .join(Contract, Contract.contract_type_id == ContractType.id)
        .filter(Contract.is_deleted.is_(False))
        .group_by(ContractType.name)
        .all()
    )

    by_responsible = (
        db.query(Contract.responsible_person_name, func.count(Contract.id))
        .filter(Contract.is_deleted.is_(False))
        .group_by(Contract.responsible_person_name)
        .all()
    )

    return {
        'widgets': data,
        'nearest_contracts': [
            {'id': c.id, 'contract_name': c.contract_name, 'end_date': str(c.end_date), 'status': c.status}
            for c in nearest
        ],
        'latest_contracts': [
            {'id': c.id, 'contract_name': c.contract_name, 'created_at': str(c.created_at), 'status': c.status}
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
        .limit(20)
        .all()
    )
    return [
        {'id': n.id, 'title': n.title, 'message': n.message, 'is_read': n.is_read, 'created_at': str(n.created_at)}
        for n in rows
    ]
