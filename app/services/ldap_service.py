import logging

from ldap3 import ALL, Connection, Server, Tls
from sqlalchemy.orm import Session

from app.core.logging_config import log_event
from app.models import LdapSetting


LDAP_ATTRIBUTES = ['displayName', 'mail', 'sAMAccountName', 'department', 'title', 'telephoneNumber']


def get_ldap_setting(db: Session) -> LdapSetting | None:
    return db.query(LdapSetting).first()


def test_ldap_connection(db: Session, request_meta: dict) -> tuple[bool, str]:
    setting = get_ldap_setting(db)
    if not setting or not setting.server_address:
        return False, 'LDAPS ayarları tanımlı değil'

    try:
        server = Server(
            setting.server_address,
            port=setting.port,
            use_ssl=setting.tls_enabled,
            get_info=ALL,
            tls=Tls(validate=0 if not setting.verify_cert else 2),
            connect_timeout=setting.timeout_seconds,
        )
        conn = Connection(server, user=setting.bind_dn, password=setting.bind_password, auto_bind=True)
        conn.unbind()
        log_event(
            'ldap',
            logging.INFO,
            'LDAPS bağlantı testi başarılı',
            module='ldap',
            action='connection_test',
            request_id=request_meta.get('request_id'),
            ip_address=request_meta.get('ip_address'),
            user_agent=request_meta.get('user_agent'),
        )
        return True, 'Bağlantı başarılı'
    except Exception as exc:  # pragma: no cover
        log_event(
            'ldap',
            logging.ERROR,
            'LDAPS bağlantı testi başarısız',
            module='ldap',
            action='connection_test',
            request_id=request_meta.get('request_id'),
            ip_address=request_meta.get('ip_address'),
            user_agent=request_meta.get('user_agent'),
            details={'error': str(exc)},
            exc_info=exc,
        )
        return False, f'Bağlantı hatası: {exc}'


def search_ldap_users(db: Session, query: str, request_meta: dict) -> list[dict]:
    setting = get_ldap_setting(db)
    if not setting or not setting.server_address:
        return []

    try:
        server = Server(
            setting.server_address,
            port=setting.port,
            use_ssl=setting.tls_enabled,
            get_info=ALL,
            tls=Tls(validate=0 if not setting.verify_cert else 2),
            connect_timeout=setting.timeout_seconds,
        )
        conn = Connection(server, user=setting.bind_dn, password=setting.bind_password, auto_bind=True)
        filt = setting.user_search_filter or '(sAMAccountName={query})'
        ldap_filter = filt.replace('{query}', query)
        conn.search(setting.base_dn or '', ldap_filter, attributes=LDAP_ATTRIBUTES, size_limit=20)

        users = []
        for entry in conn.entries:
            users.append(
                {
                    'full_name': str(entry.displayName.value or ''),
                    'email': str(entry.mail.value or ''),
                    'username': str(entry.sAMAccountName.value or ''),
                    'department': str(entry.department.value or ''),
                    'title': str(entry.title.value or ''),
                    'phone': str(entry.telephoneNumber.value or ''),
                }
            )
        conn.unbind()

        log_event(
            'ldap',
            logging.INFO,
            'LDAPS personel araması',
            module='ldap',
            action='search_users',
            request_id=request_meta.get('request_id'),
            ip_address=request_meta.get('ip_address'),
            details={'query': query, 'result_count': len(users)},
        )
        return users
    except Exception as exc:  # pragma: no cover
        log_event(
            'ldap',
            logging.ERROR,
            'LDAPS personel araması başarısız',
            module='ldap',
            action='search_users',
            request_id=request_meta.get('request_id'),
            ip_address=request_meta.get('ip_address'),
            details={'query': query, 'error': str(exc)},
            exc_info=exc,
        )
        return []
