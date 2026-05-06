"""add notification groups and contract link

Revision ID: 202605060002
Revises: 202605060001
Create Date: 2026-05-06 04:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = '202605060002'
down_revision = '202605060001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'notification_groups' not in tables:
        op.create_table(
            'notification_groups',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('updated_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('name', name='uq_notification_groups_name'),
        )

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'notification_group_members' not in tables:
        op.create_table(
            'notification_group_members',
            sa.Column('group_id', sa.Integer(), sa.ForeignKey('notification_groups.id'), primary_key=True),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    inspector = sa.inspect(bind)
    cols = {c['name'] for c in inspector.get_columns('contracts')}
    if 'notification_group_id' not in cols:
        op.add_column('contracts', sa.Column('notification_group_id', sa.Integer(), nullable=True))

    inspector = sa.inspect(bind)
    fk_exists = any(
        fk.get('referred_table') == 'notification_groups'
        and 'notification_group_id' in (fk.get('constrained_columns') or [])
        for fk in inspector.get_foreign_keys('contracts')
    )
    if not fk_exists:
        op.create_foreign_key(
            'fk_contracts_notification_group_id_notification_groups',
            'contracts',
            'notification_groups',
            ['notification_group_id'],
            ['id'],
        )

    idx_names = {idx['name'] for idx in inspector.get_indexes('contracts')}
    if 'ix_contracts_notification_group_id' not in idx_names:
        op.create_index('ix_contracts_notification_group_id', 'contracts', ['notification_group_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    idx_names = {idx['name'] for idx in inspector.get_indexes('contracts')}
    if 'ix_contracts_notification_group_id' in idx_names:
        op.drop_index('ix_contracts_notification_group_id', table_name='contracts')

    for fk in inspector.get_foreign_keys('contracts'):
        cols = fk.get('constrained_columns') or []
        if 'notification_group_id' in cols:
            fk_name = fk.get('name')
            if fk_name:
                op.drop_constraint(fk_name, 'contracts', type_='foreignkey')

    cols = {c['name'] for c in inspector.get_columns('contracts')}
    if 'notification_group_id' in cols:
        op.drop_column('contracts', 'notification_group_id')

    tables = set(inspector.get_table_names())
    if 'notification_group_members' in tables:
        op.drop_table('notification_group_members')
    if 'notification_groups' in tables:
        op.drop_table('notification_groups')
