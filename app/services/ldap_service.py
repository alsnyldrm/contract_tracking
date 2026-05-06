import logging
from contextlib import contextmanager

from ldap3 import NONE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from sqlalchemy.orm import Session

from app.core.logging_config import log_event
from app.models import LdapSetting


LDAP_ATTRIBUTES = ['displayName', 'mail', 'sAMAccountName', 'department', 'title', 'telephoneNumber']


def get_ldap_setting(db: Session) -> LdapSetting | None:
    return db.query(LdapSetting).first()


def _build_server(setting: LdapSetting) -> Server:
    timeout = max(1, int(setting.timeout_seconds or 5))
    return Server(
        setting.server_address,
        port=setting.port,
        use_ssl=bool(setting.tls_enabled),
        get_info=NONE,
        tls=Tls(validate=0 if not setting.verify_cert else 2),
        connect_timeout=timeout,
    )


@contextmanager
def _ldap_connection(setting: LdapSetting):
    timeout = max(1, int(setting.timeout_seconds or 5))
    server = _build_server(setting)
    conn = Connection(
        server,
        user=setting.bind_dn,
        password=setting.bind_password,
        auto_bind=False,
        receive_timeout=timeout,
    )
    try:
        if not conn.bind():
            raise LDAPException(f'Bind reddedildi: {conn.result.get("description", "unknown")}')
        yield conn
    finally:
        try:
            conn.unbind()
        except Exception:
            pass


def test_ldap_connection(db: Session, request_meta: dict) -> tuple[bool, str]:
    setting = get_ldap_setting(db)
    if not setting or not setting.server_address:
        return False, 'LDAPS ayarları tanımlı değil'

    try:
        with _ldap_connection(setting):
            pass
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
        with _ldap_connection(setting) as conn:
            filt = setting.user_search_filter or '(|(sAMAccountName=*{query}*)(displayName=*{query}*)(mail=*{query}*))'
            ldap_filter = filt.replace('{query}', query)
            conn.search(setting.base_dn or '', ldap_filter, attributes=LDAP_ATTRIBUTES, size_limit=20)

            users = []
            for entry in conn.entries:
                users.append(
                    {
                        'full_name': str(entry.displayName.value or '') if 'displayName' in entry else '',
                        'email': str(entry.mail.value or '') if 'mail' in entry else '',
                        'username': str(entry.sAMAccountName.value or '') if 'sAMAccountName' in entry else '',
                        'department': str(entry.department.value or '') if 'department' in entry else '',
                        'title': str(entry.title.value or '') if 'title' in entry else '',
                        'phone': str(entry.telephoneNumber.value or '') if 'telephoneNumber' in entry else '',
                    }
                )

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
