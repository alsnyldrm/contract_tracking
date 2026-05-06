"""store ad members separately from app users

Revision ID: 202605060003
Revises: 202605060002
Create Date: 2026-05-06 06:20:00
"""

from alembic import op
import sqlalchemy as sa


revision = '202605060003'
down_revision = '202605060002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'notification_group_external_members' not in tables:
        op.create_table(
            'notification_group_external_members',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('group_id', sa.Integer(), sa.ForeignKey('notification_groups.id'), nullable=False),
            sa.Column('source', sa.String(length=30), nullable=False, server_default=sa.text("'ldap'")),
            sa.Column('username', sa.String(length=120), nullable=True),
            sa.Column('full_name', sa.String(length=255), nullable=True),
            sa.Column('email', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_ng_external_members_group_id', 'notification_group_external_members', ['group_id'])
        op.create_index('ix_ng_external_members_email', 'notification_group_external_members', ['email'])

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if 'notification_group_members' in tables and 'users' in tables:
        op.execute(
            sa.text(
                """
                INSERT INTO notification_group_external_members
                    (group_id, source, username, full_name, email, created_at, updated_at)
                SELECT
                    ngm.group_id,
                    'ldap',
                    u.username,
                    u.full_name,
                    u.email,
                    ngm.created_at,
                    COALESCE(u.updated_at, ngm.created_at)
                FROM notification_group_members ngm
                JOIN users u ON u.id = ngm.user_id
                WHERE u.auth_source = 'ldap'
                  AND NOT EXISTS (
                    SELECT 1
                    FROM notification_group_external_members em
                    WHERE em.group_id = ngm.group_id
                      AND (
                        (em.email IS NOT NULL AND u.email IS NOT NULL AND lower(em.email) = lower(u.email))
                        OR
                        (em.email IS NULL AND em.username IS NOT NULL AND u.username IS NOT NULL AND lower(em.username) = lower(u.username))
                      )
                  )
                """
            )
        )

        op.execute(
            sa.text(
                """
                DELETE FROM notification_group_members ngm
                USING users u
                WHERE ngm.user_id = u.id
                  AND u.auth_source = 'ldap'
                """
            )
        )

        op.execute(
            sa.text(
                """
                UPDATE users
                SET
                    is_active = false,
                    is_deleted = true,
                    deleted_at = NOW(),
                    updated_at = NOW()
                WHERE auth_source = 'ldap'
                  AND is_deleted = false
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if 'notification_group_external_members' in tables:
        index_names = {idx['name'] for idx in inspector.get_indexes('notification_group_external_members')}
        if 'ix_ng_external_members_email' in index_names:
            op.drop_index('ix_ng_external_members_email', table_name='notification_group_external_members')
        if 'ix_ng_external_members_group_id' in index_names:
            op.drop_index('ix_ng_external_members_group_id', table_name='notification_group_external_members')
        op.drop_table('notification_group_external_members')
