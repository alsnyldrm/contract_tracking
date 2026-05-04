import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import enforce_csrf, get_current_user, require_admin
from app.core.logging_config import log_event
from app.models import ContractDocument, User
from app.services.audit_service import add_audit_log
from app.services.document_service import delete_document, save_document

router = APIRouter()


@router.get('/contract/{contract_id}')
def list_documents(contract_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(ContractDocument)
        .filter(ContractDocument.contract_id == contract_id, ContractDocument.is_deleted.is_(False))
        .order_by(ContractDocument.uploaded_at.desc())
        .all()
    )
    return [
        {
            'id': d.id,
            'contract_id': d.contract_id,
            'original_filename': d.original_filename,
            'mime_type': d.mime_type,
            'size_bytes': d.size_bytes,
            'uploaded_at': str(d.uploaded_at),
        }
        for d in rows
    ]


@router.post('/contract/{contract_id}', dependencies=[Depends(enforce_csrf)])
def upload_document(contract_id: int, request: Request, file: UploadFile = File(...), _: User = Depends(require_admin), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    request_meta = {
        'request_id': getattr(request.state, 'request_id', None),
        'ip_address': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
    }
    doc = save_document(db, contract_id, file, user, request_meta)
    add_audit_log(
        db,
        table_name='contract_documents',
        record_id=str(doc.id),
        action='create',
        user=user,
        ip_address=request_meta['ip_address'],
        request_id=request_meta['request_id'],
        new_values={'filename': doc.original_filename},
    )
    return {'ok': True, 'id': doc.id}


@router.get('/{document_id}/download')
def download_document(document_id: int, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(ContractDocument).filter(ContractDocument.id == document_id, ContractDocument.is_deleted.is_(False)).first()
    if not doc:
        raise HTTPException(status_code=404, detail='Belge bulunamadı')

    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail='Belge fiziksel olarak bulunamadı')

    log_event(
        'document',
        logging.INFO,
        'Belge indirildi',
        module='document',
        action='download',
        user_id=user.id,
        username=user.username,
        user_role=user.role.name,
        request_id=getattr(request.state, 'request_id', None),
        ip_address=request.client.host if request.client else None,
        details={'document_id': doc.id, 'filename': doc.original_filename},
    )

    return FileResponse(path, media_type=doc.mime_type, filename=doc.original_filename)


@router.delete('/{document_id}', dependencies=[Depends(enforce_csrf)])
def remove_document(document_id: int, request: Request, _: User = Depends(require_admin), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(ContractDocument).filter(ContractDocument.id == document_id, ContractDocument.is_deleted.is_(False)).first()
    if not doc:
        raise HTTPException(status_code=404, detail='Belge bulunamadı')

    request_meta = {
        'request_id': getattr(request.state, 'request_id', None),
        'ip_address': request.client.host if request.client else None,
        'user_agent': request.headers.get('user-agent'),
    }
    delete_document(db, doc, user, request_meta)
    add_audit_log(
        db,
        table_name='contract_documents',
        record_id=str(doc.id),
        action='delete',
        user=user,
        ip_address=request_meta['ip_address'],
        request_id=request_meta['request_id'],
        previous_values={'filename': doc.original_filename},
    )
    return {'ok': True}
