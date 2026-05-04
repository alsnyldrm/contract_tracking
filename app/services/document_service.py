import logging
import mimetypes
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import ContractDocument, User

settings = get_settings()

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/png',
    'image/jpeg',
}


def ensure_upload_root() -> Path:
    path = Path(settings.upload_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_upload(file: UploadFile, size_bytes: int) -> None:
    ext = Path(file.filename or '').suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Desteklenmeyen dosya uzantısı')
    mime = file.content_type or mimetypes.guess_type(file.filename or '')[0]
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Desteklenmeyen dosya tipi')
    if size_bytes > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Dosya boyutu limiti aşıldı')


def save_document(db: Session, contract_id: int, file: UploadFile, user: User, request_meta: dict) -> ContractDocument:
    content = file.file.read()
    size_bytes = len(content)
    validate_upload(file, size_bytes)

    ext = Path(file.filename or '').suffix.lower()
    stored_name = f'{uuid4().hex}{ext}'
    target_dir = ensure_upload_root()
    target_path = (target_dir / stored_name).resolve()

    if not str(target_path).startswith(str(target_dir.resolve())):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Geçersiz dosya yolu')

    with open(target_path, 'wb') as f:
        f.write(content)

    doc = ContractDocument(
        contract_id=contract_id,
        original_filename=file.filename or stored_name,
        stored_filename=stored_name,
        file_path=str(target_path),
        mime_type=file.content_type or 'application/octet-stream',
        size_bytes=size_bytes,
        uploaded_by_user_id=user.id,
        uploaded_at=now_utc(),
        is_deleted=False,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    log_event(
        'document',
        logging.INFO,
        'Belge yüklendi',
        module='document',
        action='upload',
        user_id=user.id,
        username=user.username,
        user_role=user.role.name,
        request_id=request_meta.get('request_id'),
        ip_address=request_meta.get('ip_address'),
        user_agent=request_meta.get('user_agent'),
        details={'contract_id': contract_id, 'document_id': doc.id, 'filename': doc.original_filename, 'size': size_bytes},
    )
    return doc


def delete_document(db: Session, doc: ContractDocument, user: User, request_meta: dict) -> None:
    doc.is_deleted = True
    db.commit()

    try:
        if Path(doc.file_path).exists():
            os.remove(doc.file_path)
    except Exception:
        pass

    log_event(
        'document',
        logging.INFO,
        'Belge silindi',
        module='document',
        action='delete',
        user_id=user.id,
        username=user.username,
        user_role=user.role.name,
        request_id=request_meta.get('request_id'),
        ip_address=request_meta.get('ip_address'),
        user_agent=request_meta.get('user_agent'),
        details={'document_id': doc.id, 'filename': doc.original_filename},
    )
