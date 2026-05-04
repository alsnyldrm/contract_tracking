import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import log_event


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.started_at = time.time()

        try:
            response = await call_next(request)
        except Exception as exc:  # pragma: no cover
            log_event(
                'error',
                logging.ERROR,
                'İşlenmeyen hata',
                module='middleware',
                action='unhandled_exception',
                request_id=request_id,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get('user-agent'),
                details={'path': request.url.path, 'method': request.method},
                exc_info=exc,
            )
            raise

        duration_ms = int((time.time() - request.state.started_at) * 1000)
        user = getattr(request.state, 'current_user', None)
        log_event(
            'api',
            logging.INFO,
            'API isteği işlendi',
            module='api',
            action='request',
            user_id=getattr(user, 'id', None),
            username=getattr(user, 'username', None),
            user_role=getattr(getattr(user, 'role', None), 'name', None),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent'),
            request_id=request_id,
            details={
                'path': request.url.path,
                'method': request.method,
                'status_code': response.status_code,
                'duration_ms': duration_ms,
            },
        )
        response.headers['X-Request-ID'] = request_id
        return response
