"""add contract reminder control fields

Revision ID: 202605070001
Revises: 202605060003
Create Date: 2026-05-07 10:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = '202605070001'
down_revision = '202605060003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'contracts' not in tables:
        return

    existing_columns = {col['name'] for col in inspector.get_columns('contracts')}

    if 'reminder_enabled' not in existing_columns:
        op.add_column(
            'contracts',
            sa.Column('reminder_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        )
        op.alter_column('contracts', 'reminder_enabled', server_default=None)

    if 'last_reminder_sent_on' not in existing_columns:
        op.add_column('contracts', sa.Column('last_reminder_sent_on', sa.Date(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'contracts' not in tables:
        return

    existing_columns = {col['name'] for col in inspector.get_columns('contracts')}

    if 'last_reminder_sent_on' in existing_columns:
        op.drop_column('contracts', 'last_reminder_sent_on')
    if 'reminder_enabled' in existing_columns:
        op.drop_column('contracts', 'reminder_enabled')
