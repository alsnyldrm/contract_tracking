import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.logging_config import bootstrap_startup_logs, log_event
from app.core.middleware import RequestContextMiddleware
from app.routers import auth, contracts, dashboard, documents, institutions, logs, pages, profile, reports, settings, users
from app.services.scheduler_service import start_scheduler, stop_scheduler

app = FastAPI(title='Contract Tracking', docs_url='/api/docs', redoc_url=None)
app.add_middleware(RequestContextMiddleware)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))
app.state.templates = templates

app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')

app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(dashboard.router, prefix='/api/dashboard', tags=['dashboard'])
app.include_router(institutions.router, prefix='/api/institutions', tags=['institutions'])
app.include_router(contracts.router, prefix='/api/contracts', tags=['contracts'])
app.include_router(documents.router, prefix='/api/documents', tags=['documents'])
app.include_router(reports.router, prefix='/api/reports', tags=['reports'])
app.include_router(users.router, prefix='/api/users', tags=['users'])
app.include_router(settings.router, prefix='/api/settings', tags=['settings'])
app.include_router(logs.router, prefix='/api/logs', tags=['logs'])
app.include_router(profile.router, prefix='/api/profile', tags=['profile'])


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.on_event('startup')
def on_startup():
    bootstrap_startup_logs()
    start_scheduler()


@app.on_event('shutdown')
def on_shutdown():
    stop_scheduler()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log_event(
        'error',
        logging.ERROR,
        'Global exception',
        module='exception',
        action='global_handler',
        request_id=getattr(request.state, 'request_id', None),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get('user-agent'),
        details={'path': request.url.path, 'method': request.method},
        exc_info=exc,
    )
    return JSONResponse(status_code=500, content={'detail': 'Beklenmeyen bir hata oluştu'})
