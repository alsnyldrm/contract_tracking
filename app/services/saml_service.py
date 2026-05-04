import json
import logging
from urllib.parse import urlparse

from fastapi import Request
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.errors import OneLogin_Saml2_Error
from sqlalchemy.orm import Session

from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import Role, SamlSetting, User


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
    base_url = f"{request.url.scheme}://{request.headers.get('host')}"
    return {
        'strict': False,
        'debug': False,
        'sp': {
            'entityId': f'{base_url}/auth/saml/metadata',
            'assertionConsumerService': {
                'url': f'{base_url}/auth/saml/acs',
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST',
            },
            'singleLogoutService': {
                'url': f'{base_url}/auth/saml/slo',
                'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect',
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


def create_saml_auth(request: Request, setting: SamlSetting) -> OneLogin_Saml2_Auth:
    req_data = _prepare_request(request)
    return OneLogin_Saml2_Auth(req_data, _build_settings(setting, request))


def start_saml_login(db: Session, request: Request) -> str:
    setting = get_saml_setting(db)
    if not setting or not setting.enabled:
        raise ValueError('SAML etkin değil')
    auth = create_saml_auth(request, setting)
    return auth.login()


def get_metadata(db: Session, request: Request) -> str:
    setting = get_saml_setting(db)
    if not setting:
        raise ValueError('SAML ayarları bulunamadı')
    auth = create_saml_auth(request, setting)
    metadata = auth.get_settings().get_sp_metadata()
    errors = auth.get_settings().validate_metadata(metadata)
    if errors:
        raise OneLogin_Saml2_Error(','.join(errors))
    return metadata


def process_acs(db: Session, request: Request, post_data: dict) -> User:
    setting = get_saml_setting(db)
    if not setting or not setting.enabled:
        raise ValueError('SAML etkin değil')

    req_data = _prepare_request(request)
    req_data['post_data'] = post_data
    auth = OneLogin_Saml2_Auth(req_data, _build_settings(setting, request))
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise ValueError('SAML doğrulama hatası: ' + ';'.join(errors))
    if not auth.is_authenticated():
        raise ValueError('SAML kimlik doğrulama başarısız')

    attrs = auth.get_attributes() or {}
    nameid = auth.get_nameid()

    email_attr = setting.email_attribute or 'email'
    display_attr = setting.display_name_attribute or 'displayName'
    email = (attrs.get(email_attr) or [None])[0]
    display_name = (attrs.get(display_attr) or [nameid])[0] or nameid

    username = nameid or email
    if not username:
        raise ValueError('SAML kullanıcısı için NameID bulunamadı')

    user = db.query(User).filter(User.username == username, User.is_deleted.is_(False)).first()
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
