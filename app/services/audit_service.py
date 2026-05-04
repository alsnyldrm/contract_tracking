import logging
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging_config import log_event
from app.core.security import now_utc
from app.models import AuditLog, User


def add_audit_log(
    db: Session,
    *,
    table_name: str,
    record_id: str,
    action: str,
    user: User | None,
    ip_address: str | None,
    request_id: str | None,
    previous_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            table_name=table_name,
            record_id=record_id,
            action=action,
            previous_values=previous_values,
            new_values=new_values,
            user_id=user.id if user else None,
            ip_address=ip_address,
            created_at=now_utc(),
        )
    )
    db.commit()

    log_event(
        'audit',
        logging.INFO,
        f'{table_name} kaydında {action} işlemi',
        module='audit',
        action=action,
        user_id=user.id if user else None,
        username=user.username if user else None,
        user_role=user.role.name if user else None,
        ip_address=ip_address,
        request_id=request_id,
        details={
            'table_name': table_name,
            'record_id': record_id,
            'previous_values': previous_values,
            'new_values': new_values,
        },
    )
