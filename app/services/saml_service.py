import json
import logging
import re
from urllib.parse import urlparse

from fastapi import Request
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.errors import OneLogin_Saml2_Error
from sqlalchemy.orm import Session

from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import Role, SamlSetting, User


DEFAULT_EMAIL_ATTRIBUTES = (
    'email',
    'mail',
    'emailaddress',
    'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress',
    'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn',
    'urn:oid:0.9.2342.19200300.100.1.3',
)

DEFAULT_DISPLAY_NAME_ATTRIBUTES = (
    'displayName',
    'displayname',
    'name',
    'cn',
    'http://schemas.microsoft.com/identity/claims/displayname',
    'http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name',
)

EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
SAML_ACS_BINDING = 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
SAML_SLO_BINDING = 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'


def get_sp_runtime_config(request: Request) -> dict:
    base_url = f"{request.url.scheme}://{request.headers.get('host')}"
    return {
        'base_url': base_url,
        'entity_id': f'{base_url}/auth/saml/metadata',
        'metadata_url': f'{base_url}/auth/saml/metadata',
        'acs_url': f'{base_url}/auth/saml/acs',
        'acs_binding': SAML_ACS_BINDING,
        'sls_url': f'{base_url}/auth/saml/slo',
        'sls_binding': SAML_SLO_BINDING,
    }


def get_saml_setting(db: Session) -> SamlSetting | None:
    return db.query(SamlSetting).first()

def _prepare_request(request: Request) -> dict:
    url_data = urlparse(str(request.url))
    return {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.headers.get('host'),
        'server_port': url_data.port or (443 if request.url.scheme == 'https' else 80),
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
        'post_data': {},
    }


def _build_settings(setting: SamlSetting, request: Request) -> dict:
    sp = get_sp_runtime_config(request)
    return {
        'strict': False,
        'debug': False,
        'security': {
            # AuthnRequest içinde RequestedAuthnContext göndermeyerek
            # Entra'nın şifre/MFA/x509 gibi farklı yöntemlerle gelen oturumlarını kabul ederiz.
            'requestedAuthnContext': False,
        },
        'sp': {
            'entityId': sp['entity_id'],
            'assertionConsumerService': {
                'url': sp['acs_url'],
                'binding': sp['acs_binding'],
            },
            'singleLogoutService': {
                'url': sp['sls_url'],
                'binding': sp['sls_binding'],
            },
            'x509cert': '',
            'privateKey': '',
        },
        'idp': {
            'entityId': setting.entity_id or '',
            'singleSignOnService': {'url': setting.sso_url or ''},
            'singleLogoutService': {'url': setting.slo_url or ''},
            'x509cert': setting.x509_certificate or '',
        },
    }


def create_saml_auth(db: Session, request: Request, setting: SamlSetting) -> OneLogin_Saml2_Auth:
    req_data = _prepare_request(request)
    return OneLogin_Saml2_Auth(req_data, _build_settings(setting, request))


def start_saml_login(db: Session, request: Request) -> str:
    setting = get_saml_setting(db)
    if not setting or not setting.enabled:
        raise ValueError('SAML etkin değil')
    auth = create_saml_auth(db, request, setting)
    return auth.login()


def get_metadata(db: Session, request: Request) -> str:
    setting = get_saml_setting(db)
    if not setting:
        raise ValueError('SAML ayarları bulunamadı')
    auth = create_saml_auth(db, request, setting)
    metadata = auth.get_settings().get_sp_metadata()
    errors = auth.get_settings().validate_metadata(metadata)
    if errors:
        raise OneLogin_Saml2_Error(','.join(errors))
    return metadata


def _first_attr_value(value: object) -> str | None:
    if isinstance(value, (list, tuple)):
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                return text
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _get_attr_case_insensitive(attrs: dict, key: str | None) -> str | None:
    if not key:
        return None
    raw = attrs.get(key)
    if raw is not None:
        return _first_attr_value(raw)
    wanted = key.casefold()
    for attr_key, attr_value in attrs.items():
        if str(attr_key).casefold() == wanted:
            return _first_attr_value(attr_value)
    return None


def _find_attr_value(attr_sources: list[dict], candidates: list[str | None]) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        for source in attr_sources:
            value = _get_attr_case_insensitive(source, candidate)
            if value:
                return value
    return None


def _as_mapping_value(mapping: dict, *keys: str) -> str | None:
    for key in keys:
        raw = mapping.get(key)
        value = _first_attr_value(raw)
        if value:
            return value
    return None


def process_acs(db: Session, request: Request, saml_data: dict, method: str = 'POST') -> User:
    setting = get_saml_setting(db)
    if not setting or not setting.enabled:
        raise ValueError('SAML etkin değil')

    req_data = _prepare_request(request)
    if str(method or '').upper() == 'GET':
        req_data['get_data'] = dict(saml_data or {})
    else:
        req_data['post_data'] = dict(saml_data or {})
    auth = OneLogin_Saml2_Auth(req_data, _build_settings(setting, request))
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise ValueError('SAML doğrulama hatası: ' + ';'.join(errors))
    if not auth.is_authenticated():
        raise ValueError('SAML kimlik doğrulama başarısız')

    attrs = auth.get_attributes() or {}
    get_friendly_attrs = getattr(auth, 'get_friendlyname_attributes', None)
    friendly_attrs = get_friendly_attrs() if callable(get_friendly_attrs) else {}
    nameid = auth.get_nameid()

    configured_mapping = setting.attribute_mapping if isinstance(setting.attribute_mapping, dict) else {}
    email_from_mapping = _as_mapping_value(configured_mapping, 'email', 'mail', 'email_attribute')
    display_from_mapping = _as_mapping_value(
        configured_mapping,
        'display_name',
        'displayName',
        'name',
        'full_name',
    )

    email_candidates = [setting.email_attribute, email_from_mapping, *DEFAULT_EMAIL_ATTRIBUTES]
    display_candidates = [setting.display_name_attribute, display_from_mapping, *DEFAULT_DISPLAY_NAME_ATTRIBUTES]
    attr_sources = [attrs, friendly_attrs]

    email = _find_attr_value(attr_sources, email_candidates)
    display_name = _find_attr_value(attr_sources, display_candidates) or nameid

    username = nameid or email
    if not username:
        raise ValueError('SAML kullanıcısı için NameID bulunamadı')
    if not email and username and EMAIL_PATTERN.match(username):
        email = username

    user = db.query(User).filter(User.username == username).first()
    if not user and email:
        user = db.query(User).filter(User.email == email).first()
    if not user:
        readonly_role = db.query(Role).filter(Role.name == 'readonly').first()
        user = User(
            username=username,
            password_hash=None,
            email=email,
            full_name=display_name,
            auth_source='saml',
            must_change_password=False,
            is_active=True,
            role_id=readonly_role.id,
            created_at=now_utc(),
            updated_at=now_utc(),
            is_deleted=False,
            deleted_at=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        changed = False
        if user.is_deleted:
            user.is_deleted = False
            user.deleted_at = None
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if user.auth_source != 'saml':
            user.auth_source = 'saml'
            changed = True
        if user.username != username:
            username_owner = db.query(User).filter(User.username == username, User.id != user.id).first()
            if not username_owner:
                user.username = username
                changed = True
        if display_name and user.full_name != display_name:
            user.full_name = display_name
            changed = True
        if email and user.email != email:
            email_owner = (
                db.query(User)
                .filter(User.email == email, User.id != user.id, User.is_deleted.is_(False))
                .first()
            )
            if not email_owner:
                user.email = email
                changed = True
        if changed:
            user.updated_at = now_utc()
            db.commit()
            db.refresh(user)

    log_event(
        'saml',
        logging.INFO,
        'SAML ACS işlemi başarılı',
        module='saml',
        action='acs',
        user_id=user.id,
        username=user.username,
        user_role=user.role.name if user.role else None,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        request_id=getattr(request.state, 'request_id', None),
        details={'mapped_attributes': list(attrs.keys())},
    )

    return user


def serialize_attribute_mapping(input_json: str | dict | None) -> dict:
    if not input_json:
        return {}
    if isinstance(input_json, dict):
        return input_json
    try:
        return json.loads(input_json)
    except Exception:
        return {}
