import json
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user, require_admin
from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import AppSetting, LdapSetting, LogSetting, SamlSetting, SmtpSetting, User
from app.services.audit_service import add_audit_log
from app.services.ldap_service import test_ldap_connection
from app.services.saml_service import (
    DEFAULT_DISPLAY_NAME_ATTRIBUTES,
    DEFAULT_EMAIL_ATTRIBUTES,
    get_sp_runtime_config,
    serialize_attribute_mapping,
)

router = APIRouter()
DEFAULT_ENTRA_EMAIL_ATTRIBUTE = 'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress'
DEFAULT_ENTRA_DISPLAY_ATTRIBUTE = 'http://schemas.microsoft.com/identity/claims/displayname'
DEFAULT_NAMEID_FORMAT = 'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress'
SMTP_AUTH_MODES = {'auth', 'relay'}


def _masked(value: str | None) -> str | None:
    if not value:
        return value
    return '********'


def _smtp_auth_mode(row: SmtpSetting | None) -> str:
    if not row:
        return 'auth'
    return 'auth' if (row.username and row.password) else 'relay'


@router.get('/')
def get_settings_bundle(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    ldap = db.query(LdapSetting).first()
    saml = db.query(SamlSetting).first()
    smtp = db.query(SmtpSetting).first()
    logs = db.query(LogSetting).first()
    timezone = db.query(AppSetting).filter(AppSetting.key == 'system.timezone').first()

    return {
        'timezone': timezone.value if timezone else 'Europe/Istanbul',
        'ldap': {
            'server_address': ldap.server_address if ldap else '',
            'port': ldap.port if ldap else 636,
            'base_dn': ldap.base_dn if ldap else '',
            'bind_dn': ldap.bind_dn if ldap else '',
            'bind_password': _masked(ldap.bind_password if ldap else ''),
            'user_search_filter': ldap.user_search_filter if ldap else '(|(sAMAccountName=*{query}*)(displayName=*{query}*)(mail=*{query}*))',
            'group_search_filter': ldap.group_search_filter if ldap else '',
            'tls_enabled': ldap.tls_enabled if ldap else True,
            'verify_cert': ldap.verify_cert if ldap else True,
            'timeout_seconds': ldap.timeout_seconds if ldap else 5,
        },
        'saml': {
            'enabled': saml.enabled if saml else False,
            'entity_id': saml.entity_id if saml else '',
            'sso_url': saml.sso_url if saml else '',
            'slo_url': saml.slo_url if saml else '',
            'x509_certificate': _masked(saml.x509_certificate if saml else ''),
            'attribute_mapping': saml.attribute_mapping if saml else {},
            'nameid_mapping': saml.nameid_mapping if saml and saml.nameid_mapping else DEFAULT_NAMEID_FORMAT,
            'email_attribute': saml.email_attribute if saml and saml.email_attribute else DEFAULT_ENTRA_EMAIL_ATTRIBUTE,
            'display_name_attribute': saml.display_name_attribute if saml and saml.display_name_attribute else DEFAULT_ENTRA_DISPLAY_ATTRIBUTE,
            'role_mapping': saml.role_mapping if saml else {},
        },
        'smtp': {
            'host': smtp.host if smtp else '',
            'port': smtp.port if smtp else 587,
            'username': smtp.username if smtp else '',
            'password': _masked(smtp.password if smtp else ''),
            'auth_mode': _smtp_auth_mode(smtp),
            'relay_mode': _smtp_auth_mode(smtp) == 'relay',
            'tls_ssl': smtp.tls_ssl if smtp else True,
            'sender_name': smtp.sender_name if smtp else '',
            'sender_email': smtp.sender_email if smtp else '',
        },
        'log_settings': {
            'max_file_size_mb': logs.max_file_size_mb if logs else 20,
            'retention_days': logs.retention_days if logs else 30,
            'auto_refresh_seconds': logs.auto_refresh_seconds if logs else 5,
        },
    }


@router.get('/saml/bootstrap')
def saml_bootstrap_info(request: Request, _: User = Depends(require_admin)):
    sp = get_sp_runtime_config(request)
    return {
        'sp': sp,
        'recommended': {
            'email_attribute': DEFAULT_ENTRA_EMAIL_ATTRIBUTE,
            'display_name_attribute': DEFAULT_ENTRA_DISPLAY_ATTRIBUTE,
            'nameid_mapping': DEFAULT_NAMEID_FORMAT,
            'fallback_email_attributes': list(DEFAULT_EMAIL_ATTRIBUTES),
            'fallback_display_attributes': list(DEFAULT_DISPLAY_NAME_ATTRIBUTES),
        },
    }


@router.put('/timezone', dependencies=[Depends(enforce_csrf)])
def update_timezone(payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    tz = payload.get('timezone', 'Europe/Istanbul')
    row = db.query(AppSetting).filter(AppSetting.key == 'system.timezone').first()
    if not row:
        row = AppSetting(key='system.timezone', value=tz, created_at=now_utc(), updated_at=now_utc())
        db.add(row)
    else:
        row.value = tz
        row.updated_at = now_utc()
    db.commit()

    log_event('settings', logging.INFO, 'Timezone güncellendi', module='settings', action='timezone_update', user_id=admin.id, username=admin.username, user_role=admin.role.name, request_id=getattr(request.state, 'request_id', None), ip_address=request.client.host if request.client else None, details={'timezone': tz})
    return {'ok': True}


@router.put('/ldap', dependencies=[Depends(enforce_csrf)])
def update_ldap(payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(LdapSetting).first()
    if not row:
        row = LdapSetting(created_at=now_utc(), updated_at=now_utc())
        db.add(row)

    for field in ['server_address', 'port', 'base_dn', 'bind_dn', 'user_search_filter', 'group_search_filter', 'tls_enabled', 'verify_cert', 'timeout_seconds']:
        if field in payload:
            setattr(row, field, payload[field])
    if payload.get('bind_password') and payload.get('bind_password') != '********':
        row.bind_password = payload['bind_password']
    row.updated_at = now_utc()
    db.commit()

    add_audit_log(
        db,
        table_name='ldap_settings',
        record_id=str(row.id),
        action='update',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        new_values={'server_address': row.server_address, 'port': row.port},
    )
    log_event('settings', logging.INFO, 'LDAPS ayarları güncellendi', module='settings', action='ldap_update', user_id=admin.id, username=admin.username, user_role=admin.role.name, request_id=getattr(request.state, 'request_id', None))
    return {'ok': True}


@router.post('/ldap/test', dependencies=[Depends(enforce_csrf)])
def ldap_test(request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    ok, msg = test_ldap_connection(db, {'request_id': getattr(request.state, 'request_id', None), 'ip_address': request.client.host if request.client else None, 'user_agent': request.headers.get('user-agent')})
    return {'ok': ok, 'message': msg}


@router.put('/saml', dependencies=[Depends(enforce_csrf)])
def update_saml(payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(SamlSetting).first()
    if not row:
        row = SamlSetting(created_at=now_utc(), updated_at=now_utc())
        db.add(row)

    row.enabled = bool(payload.get('enabled', row.enabled if row.id else False))
    row.entity_id = payload.get('entity_id', row.entity_id)
    row.sso_url = payload.get('sso_url', row.sso_url)
    row.slo_url = payload.get('slo_url', row.slo_url)
    if payload.get('x509_certificate') and payload.get('x509_certificate') != '********':
        row.x509_certificate = payload.get('x509_certificate')
    row.attribute_mapping = serialize_attribute_mapping(payload.get('attribute_mapping', row.attribute_mapping))
    row.nameid_mapping = payload.get('nameid_mapping', row.nameid_mapping)
    row.email_attribute = payload.get('email_attribute', row.email_attribute)
    row.display_name_attribute = payload.get('display_name_attribute', row.display_name_attribute)
    role_mapping = payload.get('role_mapping', row.role_mapping)
    if isinstance(role_mapping, str):
        try:
            role_mapping = json.loads(role_mapping)
        except Exception:
            role_mapping = {}
    row.role_mapping = role_mapping or {}
    row.updated_at = now_utc()
    db.commit()

    add_audit_log(
        db,
        table_name='saml_settings',
        record_id=str(row.id),
        action='update',
        user=admin,
        ip_address=request.client.host if request.client else None,
        request_id=getattr(request.state, 'request_id', None),
        new_values={'enabled': row.enabled, 'entity_id': row.entity_id},
    )
    log_event('settings', logging.INFO, 'SAML ayarları güncellendi', module='settings', action='saml_update', user_id=admin.id, username=admin.username, user_role=admin.role.name, request_id=getattr(request.state, 'request_id', None))
    return {'ok': True}


@router.put('/smtp', dependencies=[Depends(enforce_csrf)])
def update_smtp(payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(SmtpSetting).first()
    if not row:
        row = SmtpSetting(created_at=now_utc(), updated_at=now_utc())
        db.add(row)

    for field in ['host', 'port', 'tls_ssl', 'sender_name', 'sender_email']:
        if field in payload:
            setattr(row, field, payload[field])
    if isinstance(row.sender_name, str):
        row.sender_name = row.sender_name.strip() or None
    if isinstance(row.sender_email, str):
        row.sender_email = row.sender_email.strip() or None

    relay_mode = payload.get('relay_mode')
    if relay_mode is None:
        auth_mode = str(payload.get('auth_mode') or _smtp_auth_mode(row)).lower()
    else:
        auth_mode = 'relay' if bool(relay_mode) else 'auth'
    if auth_mode not in SMTP_AUTH_MODES:
        raise HTTPException(status_code=400, detail='Geçersiz SMTP modu')

    if auth_mode == 'relay':
        row.username = None
        row.password = None
    else:
        if 'username' in payload:
            row.username = (payload.get('username') or '').strip() or None
        if payload.get('password') and payload.get('password') != '********':
            row.password = payload['password']
        if not row.username:
            raise HTTPException(status_code=400, detail='Kimlik doğrulama modunda SMTP kullanıcı adı zorunludur')
        if not row.password:
            raise HTTPException(status_code=400, detail='Kimlik doğrulama modunda SMTP şifresi zorunludur')

    if not row.host:
        raise HTTPException(status_code=400, detail='SMTP host zorunludur')
    if not row.sender_email:
        raise HTTPException(status_code=400, detail='Gönderen e-posta zorunludur')

    row.updated_at = now_utc()
    db.commit()
    log_event('settings', logging.INFO, 'SMTP ayarları güncellendi', module='settings', action='smtp_update', user_id=admin.id, username=admin.username, user_role=admin.role.name, request_id=getattr(request.state, 'request_id', None))
    return {'ok': True}


@router.post('/smtp/test', dependencies=[Depends(enforce_csrf)])
def smtp_test(payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(SmtpSetting).first()
    if not row or not row.host or not row.sender_email:
        raise HTTPException(status_code=400, detail='SMTP ayarları eksik')
    to_email = payload.get('to') or row.sender_email
    if not to_email:
        raise HTTPException(status_code=400, detail='Test e-posta alıcısı gerekli')

    auth_mode = _smtp_auth_mode(row)
    if auth_mode == 'auth' and (not row.username or not row.password):
        raise HTTPException(status_code=400, detail='SMTP kimlik doğrulama bilgileri eksik')

    msg = EmailMessage()
    msg['Subject'] = 'Contract Tracking SMTP Test'
    msg['From'] = formataddr(((row.sender_name or '').strip(), row.sender_email))
    msg['To'] = to_email
    msg.set_content('Bu bir test e-postasıdır.')

    try:
        with smtplib.SMTP(row.host, row.port, timeout=10) as smtp:
            if row.tls_ssl:
                smtp.starttls()
            if auth_mode == 'auth':
                smtp.login(row.username, row.password)
            smtp.send_message(msg)
        log_event('notification', logging.INFO, 'SMTP test mail başarılı', module='smtp', action='test_mail', user_id=admin.id, username=admin.username, request_id=getattr(request.state, 'request_id', None))
        return {'ok': True, 'message': 'Test e-postası gönderildi'}
    except Exception as exc:
        log_event('notification', logging.ERROR, 'SMTP test mail hatası', module='smtp', action='test_mail', user_id=admin.id, username=admin.username, request_id=getattr(request.state, 'request_id', None), details={'error': str(exc)}, exc_info=exc)
        return {'ok': False, 'message': f'Gönderim başarısız: {exc}'}


@router.put('/logs', dependencies=[Depends(enforce_csrf)])
def update_log_settings(payload: dict, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(LogSetting).first()
    if not row:
        row = LogSetting(created_at=now_utc(), updated_at=now_utc())
        db.add(row)
    for field in ['max_file_size_mb', 'retention_days', 'auto_refresh_seconds']:
        if field in payload:
            setattr(row, field, payload[field])
    row.updated_at = now_utc()
    db.commit()
    log_event('settings', logging.INFO, 'Log ayarları güncellendi', module='settings', action='log_settings_update', user_id=admin.id, username=admin.username, user_role=admin.role.name, request_id=getattr(request.state, 'request_id', None))
    return {'ok': True}
