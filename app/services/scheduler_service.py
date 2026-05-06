import logging
import smtplib
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import (
    Contract,
    Institution,
    LogSetting,
    Notification,
    NotificationGroup,
    NotificationGroupExternalMember,
    NotificationGroupMember,
    SmtpSetting,
    User,
)

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


def _smtp_auth_mode(row: SmtpSetting | None) -> str:
    if not row:
        return 'auth'
    return 'auth' if (row.username and row.password) else 'relay'


def _send_expiry_mail_to_group(db: Session, contract: Contract, today: date) -> int:
    if not contract.notification_group_id:
        return 0

    group = (
        db.query(NotificationGroup)
        .filter(NotificationGroup.id == contract.notification_group_id, NotificationGroup.is_active.is_(True))
        .first()
    )
    if not group:
        return 0

    recipients = (
        db.query(User.email)
        .join(NotificationGroupMember, NotificationGroupMember.user_id == User.id)
        .filter(
            NotificationGroupMember.group_id == group.id,
            User.is_deleted.is_(False),
            User.is_active.is_(True),
            User.email.isnot(None),
            User.auth_source != 'ldap',
        )
        .all()
    )

    external_recipients = (
        db.query(NotificationGroupExternalMember.email)
        .filter(
            NotificationGroupExternalMember.group_id == group.id,
            NotificationGroupExternalMember.email.isnot(None),
        )
        .all()
    )

    emails = sorted(
        {
            (r.email or '').strip()
            for r in recipients + external_recipients
            if (r.email or '').strip()
        }
    )
    if not emails:
        log_event(
            'notification',
            logging.WARNING,
            'Bildirim grubu için e-posta alıcısı bulunamadı',
            module='scheduler',
            action='contract_expiry_group_mail_skip',
            details={'contract_id': contract.id, 'group_id': group.id, 'group_name': group.name},
        )
        return 0

    smtp = db.query(SmtpSetting).first()
    if not smtp or not smtp.host or not smtp.sender_email:
        log_event(
            'notification',
            logging.WARNING,
            'SMTP ayarları eksik olduğu için grup bildirimi gönderilemedi',
            module='scheduler',
            action='contract_expiry_group_mail_skip',
            details={'contract_id': contract.id, 'group_id': group.id},
        )
        return 0

    auth_mode = _smtp_auth_mode(smtp)
    if auth_mode == 'auth' and (not smtp.username or not smtp.password):
        log_event(
            'notification',
            logging.WARNING,
            'SMTP kimlik bilgileri eksik olduğu için grup bildirimi gönderilemedi',
            module='scheduler',
            action='contract_expiry_group_mail_skip',
            details={'contract_id': contract.id, 'group_id': group.id},
        )
        return 0

    institution_name = None
    if contract.institution_id:
        inst = db.query(Institution).filter(Institution.id == contract.institution_id).first()
        institution_name = inst.name if inst else None

    days_left = (contract.end_date - today).days if contract.end_date else None
    day_text = f'{days_left} gün kaldı' if days_left is not None else 'Bitiş tarihi yaklaştı'
    msg = EmailMessage()
    msg['Subject'] = f'Sözleşme Bitiş Uyarısı: {contract.contract_name}'
    msg['From'] = formataddr(((smtp.sender_name or '').strip(), smtp.sender_email))
    msg['To'] = ', '.join(emails)
    msg.set_content(
        '\n'.join(
            [
                f'"{contract.contract_name}" sözleşmesinin bitiş tarihi yaklaşıyor.',
                '',
                f'Sözleşme No: {contract.contract_number}',
                f'Kurum: {institution_name or "-"}',
                f'Bitiş Tarihi: {contract.end_date or "-"}',
                f'Hatırlatma: {day_text}',
                '',
                'Bu mesaj Contract Tracking tarafından otomatik gönderilmiştir.',
            ]
        )
    )

    try:
        with smtplib.SMTP(smtp.host, smtp.port, timeout=10) as smtp_client:
            if smtp.tls_ssl:
                smtp_client.starttls()
            if auth_mode == 'auth':
                smtp_client.login(smtp.username, smtp.password)
            smtp_client.send_message(msg)

        log_event(
            'notification',
            logging.INFO,
            'Sözleşme bitiş bildirimi gruba e-posta ile gönderildi',
            module='scheduler',
            action='contract_expiry_group_mail',
            details={
                'contract_id': contract.id,
                'group_id': group.id,
                'group_name': group.name,
                'recipient_count': len(emails),
            },
        )
        return len(emails)
    except Exception as exc:  # pragma: no cover
        log_event(
            'notification',
            logging.ERROR,
            'Sözleşme bitiş bildirimi e-posta gönderim hatası',
            module='scheduler',
            action='contract_expiry_group_mail',
            details={'contract_id': contract.id, 'group_id': group.id, 'error': str(exc)},
            exc_info=exc,
        )
        return 0


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
        if old_status != 'Yaklaşıyor' and contract.status == 'Yaklaşıyor':
            _send_expiry_mail_to_group(db, contract, today)
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
