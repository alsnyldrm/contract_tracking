from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.models import AuditLog, User
from app.services.log_service import filter_logs, logs_to_csv, resolve_log_file, tail_json_logs

router = APIRouter()


@router.get('/types')
def log_types(_: User = Depends(require_admin)):
    return [
        'app',
        'error',
        'auth',
        'saml',
        'ldap',
        'db',
        'audit',
        'document',
        'report',
        'security',
        'api',
        'scheduler',
        'notification',
        'profile',
        'settings',
    ]


@router.get('/view')
def view_logs(
    log_type: str,
    limit: int = 100,
    level: str | None = None,
    username: str | None = None,
    ip: str | None = None,
    search: str | None = None,
    _: User = Depends(require_admin),
):
    if limit not in {100, 500, 1000}:
        limit = 100
    try:
        file_path = resolve_log_file(log_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    rows = tail_json_logs(file_path, limit=limit)
    filtered = filter_logs(rows, {'level': level, 'username': username, 'ip': ip, 'search': search})
    return {'count': len(filtered), 'rows': filtered}


@router.get('/download')
def download_log(log_type: str, _: User = Depends(require_admin)):
    file_path = resolve_log_file(log_type)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail='Log dosyası bulunamadı')
    return FileResponse(file_path, media_type='text/plain', filename=file_path.name)


@router.get('/export-csv')
def export_log_csv(log_type: str, limit: int = 1000, _: User = Depends(require_admin)):
    file_path = resolve_log_file(log_type)
    rows = tail_json_logs(file_path, limit=limit)
    content = logs_to_csv(rows)
    return Response(content=content, media_type='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="{log_type}.csv"'})


@router.get('/audit-db')
def audit_db_logs(
    limit: int = 200,
    table_name: str | None = None,
    action: str | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if table_name:
        query = query.filter(AuditLog.table_name == table_name)
    if action:
        query = query.filter(AuditLog.action == action)
    rows = query.limit(limit).all()
    return [
        {
            'id': r.id,
            'table_name': r.table_name,
            'record_id': r.record_id,
            'action': r.action,
            'previous_values': r.previous_values,
            'new_values': r.new_values,
            'user_id': r.user_id,
            'ip_address': r.ip_address,
            'created_at': str(r.created_at),
        }
        for r in rows
    ]
