import logging
from datetime import date, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import Contract, LogSetting, Notification, User

settings = get_settings()
scheduler = BackgroundScheduler(timezone=settings.timezone_default)


def _cleanup_logs(db: Session):
    cfg = db.query(LogSetting).first()
    retention = cfg.retention_days if cfg else settings.log_retention_days
    cutoff = now_utc() - timedelta(days=retention)
    root = Path(settings.log_root)
    if not root.exists():
        return
    for file in root.glob('*.log*'):
        if file.is_file() and file.stat().st_mtime < cutoff.timestamp():
            try:
                file.unlink()
            except Exception:
                pass


def _update_contract_statuses(db: Session):
    today = date.today()
    contracts = db.query(Contract).filter(Contract.is_deleted.is_(False)).all()
    for contract in contracts:
        old_status = contract.status
        if contract.end_date and contract.end_date < today:
            contract.status = 'Süresi Doldu'
        elif contract.start_date and contract.end_date and contract.start_date <= today <= contract.end_date:
            if (contract.end_date - today).days <= contract.reminder_days:
                contract.status = 'Yaklaşıyor'
            else:
                contract.status = 'Aktif'
        if old_status != contract.status:
            db.add(
                Notification(
                    user_id=contract.updated_by_user_id,
                    title='Sözleşme Durumu Güncellendi',
                    message=f"{contract.contract_name} durumu {contract.status} oldu",
                    is_read=False,
                    created_at=now_utc(),
                    updated_at=now_utc(),
                )
            )
    db.commit()


def scheduler_job():
    db = SessionLocal()
    try:
        _update_contract_statuses(db)
        _cleanup_logs(db)
        log_event('scheduler', logging.INFO, 'Günlük job çalıştı', module='scheduler', action='daily_job')
    except Exception as exc:  # pragma: no cover
        log_event('scheduler', logging.ERROR, 'Scheduler job hatası', module='scheduler', action='daily_job', details={'error': str(exc)}, exc_info=exc)
    finally:
        db.close()


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(scheduler_job, 'interval', hours=24, id='daily-contract-job', replace_existing=True)
        scheduler.start()
        log_event('scheduler', logging.INFO, 'Scheduler başlatıldı', module='scheduler', action='startup')


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log_event('scheduler', logging.INFO, 'Scheduler durduruldu', module='scheduler', action='shutdown')
