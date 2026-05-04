from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import ReportModule, User
from app.services.report_service import REPORT_DEFS, build_report_data, export_csv_utf8_bom, export_excel, export_pdf, log_report_action

router = APIRouter()


@router.get('/modules')
def report_modules(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(ReportModule).order_by(ReportModule.id.asc()).all()
    return [{'id': r.id, 'code': r.code, 'name': r.name, 'is_active': r.is_active} for r in rows]


@router.get('/{report_code}')
def run_report(report_code: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    module = db.query(ReportModule).filter(ReportModule.code == report_code, ReportModule.is_active.is_(True)).first()
    if not module:
        raise HTTPException(status_code=404, detail='Rapor modülü aktif değil veya bulunamadı')
    filters = dict(request.query_params)
    data = build_report_data(db, report_code, filters)
    log_report_action(user, 'view', report_code, request_meta={'request_id': getattr(request.state, 'request_id', None), 'ip_address': request.client.host if request.client else None})
    return {'report': module.name, 'count': len(data), 'rows': data}


@router.get('/{report_code}/export/{fmt}')
def export_report(report_code: str, fmt: str, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    module = db.query(ReportModule).filter(ReportModule.code == report_code, ReportModule.is_active.is_(True)).first()
    if not module:
        raise HTTPException(status_code=404, detail='Rapor modülü aktif değil veya bulunamadı')

    filters = dict(request.query_params)
    data = build_report_data(db, report_code, filters)
    title = REPORT_DEFS.get(report_code, module.name)

    if fmt == 'csv':
        content = export_csv_utf8_bom(data)
        media = 'text/csv; charset=utf-8'
        ext = 'csv'
    elif fmt == 'xlsx':
        content = export_excel(data)
        media = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ext = 'xlsx'
    elif fmt == 'pdf':
        content = export_pdf(data, title)
        media = 'application/pdf'
        ext = 'pdf'
    else:
        raise HTTPException(status_code=400, detail='Desteklenmeyen export formatı')

    log_report_action(user, 'export', report_code, fmt=fmt, request_meta={'request_id': getattr(request.state, 'request_id', None), 'ip_address': request.client.host if request.client else None})

    return Response(
        content=content,
        media_type=media,
        headers={'Content-Disposition': f'attachment; filename="{report_code}.{ext}"'},
    )


@router.put('/modules/{module_id}')
def toggle_module(module_id: int, payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role.name != 'admin':
        raise HTTPException(status_code=403, detail='Admin yetkisi gerekli')
    row = db.query(ReportModule).filter(ReportModule.id == module_id).first()
    if not row:
        raise HTTPException(status_code=404, detail='Modül bulunamadı')
    row.is_active = bool(payload.get('is_active', row.is_active))
    db.commit()
    return {'ok': True}
