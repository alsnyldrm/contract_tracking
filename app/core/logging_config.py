import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.security import mask_sensitive

settings = get_settings()

LOG_FILES = {
    'app': 'app.log',
    'error': 'error.log',
    'auth': 'auth.log',
    'saml': 'saml.log',
    'ldap': 'ldap.log',
    'db': 'db.log',
    'audit': 'audit.log',
    'document': 'document.log',
    'report': 'report.log',
    'security': 'security.log',
    'api': 'api.log',
    'scheduler': 'scheduler.log',
    'notification': 'notification.log',
    'profile': 'profile.log',
    'settings': 'settings.log',
}


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'timestamp': self.formatTime(record, '%Y-%m-%dT%H:%M:%S%z'),
            'level': record.levelname,
            'module': getattr(record, 'module_name', record.name),
            'action': getattr(record, 'action', ''),
            'user_id': getattr(record, 'user_id', None),
            'username': getattr(record, 'username', None),
            'user_role': getattr(record, 'user_role', None),
            'ip_address': getattr(record, 'ip_address', None),
            'user_agent': getattr(record, 'user_agent', None),
            'request_id': getattr(record, 'request_id', None),
            'message': record.getMessage(),
            'details': mask_sensitive(getattr(record, 'details', {})),
        }
        if record.exc_info:
            payload['stack_trace'] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


_LOGGERS: dict[str, logging.Logger] = {}


def ensure_log_directory() -> None:
    Path(settings.log_root).mkdir(parents=True, exist_ok=True)


def get_category_logger(category: str) -> logging.Logger:
    if category in _LOGGERS:
        return _LOGGERS[category]

    ensure_log_directory()
    logger = logging.getLogger(f'ct_{category}')
    logger.setLevel(logging.INFO)
    logger.propagate = False

    handler = RotatingFileHandler(
        Path(settings.log_root) / LOG_FILES.get(category, 'app.log'),
        maxBytes=settings.log_rotation_mb * 1024 * 1024,
        backupCount=10,
        encoding='utf-8',
    )
    handler.setFormatter(JsonLineFormatter())
    logger.addHandler(handler)

    _LOGGERS[category] = logger
    return logger


def log_event(
    category: str,
    level: int,
    message: str,
    *,
    module: str,
    action: str,
    user_id: int | None = None,
    username: str | None = None,
    user_role: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
    exc_info: Any = None,
) -> None:
    logger = get_category_logger(category)
    logger.log(
        level,
        message,
        extra={
            'module_name': module,
            'action': action,
            'user_id': user_id,
            'username': username,
            'user_role': user_role,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'request_id': request_id,
            'details': details or {},
        },
        exc_info=exc_info,
    )


def bootstrap_startup_logs() -> None:
    for category in LOG_FILES:
        get_category_logger(category)
    log_event('app', logging.INFO, 'Uygulama başlatıldı', module='system', action='startup')
