"""add smtp sender_name column

Revision ID: 202605060001
Revises: 202605040001
Create Date: 2026-05-06 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = '202605060001'
down_revision = '202605040001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('smtp_settings')}
    if 'sender_name' not in cols:
        op.add_column('smtp_settings', sa.Column('sender_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('smtp_settings')}
    if 'sender_name' in cols:
        op.drop_column('smtp_settings', 'sender_name')
