import logging

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging_config import bootstrap_startup_logs, log_event
from app.core.security import now_utc
from app.models import (
    AppSetting,
    ContractType,
    Currency,
    InstitutionType,
    LogSetting,
    ReportModule,
    Role,
    User,
)
from app.services.auth_service import create_local_user


DEFAULT_CONTRACT_TYPES = ['Hizmet', 'Bakım', 'Lisans', 'Tedarik', 'Danışmanlık']
DEFAULT_INSTITUTION_TYPES = ['Kamu', 'Özel', 'STK', 'Üniversite']
DEFAULT_CURRENCIES = [
    ('TRY', 'Türk Lirası', '₺'),
    ('USD', 'Amerikan Doları', '$'),
    ('EUR', 'Euro', '€'),
]
DEFAULT_REPORT_MODULES = [
    ('all_contracts', 'Tüm sözleşmeler raporu'),
    ('expiring_contracts', 'Süresi yaklaşan sözleşmeler raporu'),
    ('expired_contracts', 'Süresi dolmuş sözleşmeler raporu'),
    ('by_institution', 'Kuruma göre sözleşmeler raporu'),
    ('by_responsible', 'Sorumlu personele göre sözleşmeler raporu'),
    ('critical_contracts', 'Kritik sözleşmeler raporu'),
    ('amount_based', 'Tutar bazlı sözleşmeler raporu'),
    ('date_range', 'Tarih aralığına göre sözleşmeler raporu'),
    ('missing_documents', 'Belgesi eksik sözleşmeler raporu'),
    ('renewals', 'Yenilenecek sözleşmeler raporu'),
]


def seed_roles(db: Session):
    for name, desc in [('admin', 'Tam yetkili yönetici'), ('readonly', 'Salt okunur kullanıcı')]:
        if not db.query(Role).filter(Role.name == name).first():
            db.add(Role(name=name, description=desc))
    db.commit()


def seed_defaults(db: Session):
    ts = now_utc()
    if not db.query(AppSetting).filter(AppSetting.key == 'system.timezone').first():
        db.add(AppSetting(key='system.timezone', value='Europe/Istanbul', created_at=ts, updated_at=ts))

    if not db.query(LogSetting).first():
        db.add(LogSetting(max_file_size_mb=20, retention_days=30, auto_refresh_seconds=5, created_at=ts, updated_at=ts))

    for item in DEFAULT_CONTRACT_TYPES:
        if not db.query(ContractType).filter(ContractType.name == item).first():
            db.add(ContractType(name=item, is_active=True, created_at=ts, updated_at=ts))

    for item in DEFAULT_INSTITUTION_TYPES:
        if not db.query(InstitutionType).filter(InstitutionType.name == item).first():
            db.add(InstitutionType(name=item, created_at=ts, updated_at=ts))

    for code, name, symbol in DEFAULT_CURRENCIES:
        if not db.query(Currency).filter(Currency.code == code).first():
            db.add(Currency(code=code, name=name, symbol=symbol, created_at=ts, updated_at=ts))

    for code, name in DEFAULT_REPORT_MODULES:
        if not db.query(ReportModule).filter(ReportModule.code == code).first():
            db.add(ReportModule(code=code, name=name, is_active=True, created_at=ts, updated_at=ts))

    db.commit()


def seed_admin(db: Session):
    if db.query(User).filter(User.username == 'admin', User.is_deleted.is_(False)).first():
        return
    create_local_user(
        db,
        username='admin',
        password='Aa123456',
        full_name='Sistem Yöneticisi',
        email='admin@local',
        role_name='admin',
        must_change_password=True,
    )


def main():
    bootstrap_startup_logs()
    db = SessionLocal()
    try:
        seed_roles(db)
        seed_defaults(db)
        seed_admin(db)
        log_event('db', logging.INFO, 'Seed işlemi tamamlandı', module='seed', action='seed_complete')
        print('Seed tamamlandı.')
    except Exception as exc:
        log_event('db', logging.ERROR, 'Seed işlemi hatası', module='seed', action='seed_error', details={'error': str(exc)}, exc_info=exc)
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
