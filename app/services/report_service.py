import csv
import io
import logging
from datetime import date, datetime

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.core.logging_config import log_event
from app.models import Contract, ContractDocument, Institution, User


REPORT_DEFS = {
    'all_contracts': 'Tüm sözleşmeler raporu',
    'expiring_contracts': 'Süresi yaklaşan sözleşmeler raporu',
    'expired_contracts': 'Süresi dolmuş sözleşmeler raporu',
    'by_institution': 'Kuruma göre sözleşmeler raporu',
    'by_responsible': 'Sorumlu personele göre sözleşmeler raporu',
    'critical_contracts': 'Kritik sözleşmeler raporu',
    'amount_based': 'Tutar bazlı sözleşmeler raporu',
    'date_range': 'Tarih aralığına göre sözleşmeler raporu',
    'missing_documents': 'Belgesi eksik sözleşmeler raporu',
    'renewals': 'Yenilenecek sözleşmeler raporu',
}


def _base_rows(db: Session):
    rows = (
        db.query(Contract, Institution)
        .join(Institution, Institution.id == Contract.institution_id)
        .filter(Contract.is_deleted.is_(False), Institution.is_deleted.is_(False))
        .all()
    )
    return rows


def build_report_data(db: Session, report_code: str, filters: dict | None = None) -> list[dict]:
    filters = filters or {}
    today = date.today()
    rows = _base_rows(db)

    data = []
    for contract, institution in rows:
        if report_code == 'expiring_contracts' and (not contract.end_date or (contract.end_date - today).days > 90):
            continue
        if report_code == 'expired_contracts' and (not contract.end_date or contract.end_date >= today):
            continue
        if report_code == 'critical_contracts' and contract.critical_level != 'Kritik':
            continue
        if report_code == 'missing_documents':
            doc_count = db.query(ContractDocument).filter(ContractDocument.contract_id == contract.id, ContractDocument.is_deleted.is_(False)).count()
            if doc_count > 0:
                continue
        if report_code == 'renewals' and not contract.renewal_date:
            continue

        if filters.get('institution_id') and int(filters['institution_id']) != institution.id:
            continue
        if filters.get('status') and filters['status'] != contract.status:
            continue

        data.append(
            {
                'Sözleşme No': contract.contract_number,
                'Kurum': institution.name,
                'Sözleşme Adı': contract.contract_name,
                'Durum': contract.status,
                'Kritik Seviye': contract.critical_level,
                'Başlangıç': str(contract.start_date or ''),
                'Bitiş': str(contract.end_date or ''),
                'Tutar': float(contract.amount or 0),
                'Sorumlu': contract.responsible_person_name or '',
            }
        )
    return data


def export_csv_utf8_bom(rows: list[dict]) -> bytes:
    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return ('\ufeff' + output.getvalue()).encode('utf-8')


def export_excel(rows: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = 'Rapor'
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(col, '') for col in headers])
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()


def export_pdf(rows: list[dict], title: str) -> bytes:
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=A4)
    width, height = A4
    y = height - 40
    pdf.setFont('Helvetica-Bold', 14)
    pdf.drawString(40, y, f'Contract Tracking - {title}')
    y -= 30
    pdf.setFont('Helvetica', 9)
    for idx, row in enumerate(rows[:300], 1):
        line = f"{idx}. {row.get('Sözleşme No')} | {row.get('Kurum')} | {row.get('Durum')} | {row.get('Bitiş')}"
        pdf.drawString(40, y, line[:120])
        y -= 14
        if y < 50:
            pdf.showPage()
            y = height - 40
            pdf.setFont('Helvetica', 9)
    pdf.save()
    return stream.getvalue()


def log_report_action(user: User, action: str, report_code: str, fmt: str | None = None, request_meta: dict | None = None):
    log_event(
        'report',
        logging.INFO,
        'Rapor işlemi',
        module='report',
        action=action,
        user_id=user.id,
        username=user.username,
        user_role=user.role.name,
        request_id=(request_meta or {}).get('request_id'),
        ip_address=(request_meta or {}).get('ip_address'),
        details={'report_code': report_code, 'format': fmt, 'timestamp': datetime.utcnow().isoformat()},
    )
