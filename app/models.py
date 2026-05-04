from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Role(Base):
    __tablename__ = 'roles'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_source: Mapped[str] = mapped_column(String(20), nullable=False, default='local')
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role_id: Mapped[int] = mapped_column(ForeignKey('roles.id'), nullable=False)

    role: Mapped[Role] = relationship(Role)


class UserSession(Base):
    __tablename__ = 'user_sessions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token: Mapped[str] = mapped_column(String(255), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UserPreference(Base, TimestampMixin):
    __tablename__ = 'user_preferences'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True, nullable=False)
    dark_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sidebar_collapsed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    filter_preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class InstitutionType(Base, TimestampMixin):
    __tablename__ = 'institution_types'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class Institution(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'institutions'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    tax_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tax_office: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    institution_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey('institution_types.id'), nullable=True)
    sector: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    contact_person: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


contract_status_enum = Enum('Taslak', 'Aktif', 'Yaklaşıyor', 'Süresi Doldu', 'İptal', 'Yenilendi', name='contract_status_enum')
critical_level_enum = Enum('Düşük', 'Orta', 'Yüksek', 'Kritik', name='critical_level_enum')


class ContractType(Base, TimestampMixin):
    __tablename__ = 'contract_types'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Currency(Base, TimestampMixin):
    __tablename__ = 'currencies'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)


class Contract(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = 'contracts'
    __table_args__ = (UniqueConstraint('contract_number', name='uq_contract_number'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_number: Mapped[str] = mapped_column(String(120), nullable=False)
    institution_id: Mapped[int] = mapped_column(ForeignKey('institutions.id'), nullable=False)
    contract_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey('contract_types.id'), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    signed_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    renewal_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    currency_id: Mapped[Optional[int]] = mapped_column(ForeignKey('currencies.id'), nullable=True)
    vat_included: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payment_period: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    responsible_person_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    responsible_person_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    responsible_person_username: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    responsible_department: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(contract_status_enum, nullable=False, default='Taslak')
    critical_level: Mapped[str] = mapped_column(critical_level_enum, nullable=False, default='Düşük')
    reminder_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    auto_renewal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    termination_notice_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    updated_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)


class Tag(Base, TimestampMixin):
    __tablename__ = 'tags'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)


class ContractTag(Base):
    __tablename__ = 'contract_tags'

    contract_id: Mapped[int] = mapped_column(ForeignKey('contracts.id'), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey('tags.id'), primary_key=True)


class ContractDocument(Base):
    __tablename__ = 'contract_documents'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey('contracts.id'), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by_user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class LdapSetting(Base, TimestampMixin):
    __tablename__ = 'ldap_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    port: Mapped[int] = mapped_column(Integer, default=636, nullable=False)
    base_dn: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bind_dn: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bind_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_search_filter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    group_search_filter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tls_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verify_cert: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=5, nullable=False)


class SamlSetting(Base, TimestampMixin):
    __tablename__ = 'saml_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sso_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    slo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    x509_certificate: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attribute_mapping: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    nameid_mapping: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    email_attribute: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    display_name_attribute: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    role_mapping: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class SmtpSetting(Base, TimestampMixin):
    __tablename__ = 'smtp_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    port: Mapped[int] = mapped_column(Integer, default=587, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tls_ssl: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sender_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class AppSetting(Base, TimestampMixin):
    __tablename__ = 'app_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class ReportModule(Base, TimestampMixin):
    __tablename__ = 'report_modules'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AuditLog(Base):
    __tablename__ = 'audit_logs'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    table_name: Mapped[str] = mapped_column(String(120), nullable=False)
    record_id: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    previous_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    new_values: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey('users.id'), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Notification(Base, TimestampMixin):
    __tablename__ = 'notifications'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class LogSetting(Base, TimestampMixin):
    __tablename__ = 'log_settings'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    max_file_size_mb: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    auto_refresh_seconds: Mapped[int] = mapped_column(Integer, default=5, nullable=False)


class LoginAttempt(Base):
    __tablename__ = 'login_attempts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SystemEvent(Base):
    __tablename__ = 'system_events'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
