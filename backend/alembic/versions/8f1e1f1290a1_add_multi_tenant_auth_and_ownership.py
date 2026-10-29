"""add_multi_tenant_auth_and_ownership

Revision ID: 8f1e1f1290a1
Revises: 280f02342909
Create Date: 2026-10-29 20:49:31.408382

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1e1f1290a1'
down_revision: Union[str, Sequence[str], None] = '280f02342909'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create all multi-tenant and authentication tables first
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, default=False),
        sa.Column('mfa_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_is_verified'), 'users', ['is_verified'], unique=False)
    op.create_index(op.f('ix_users_is_active'), 'users', ['is_active'], unique=False)
    op.create_index(op.f('ix_users_mfa_enabled'), 'users', ['mfa_enabled'], unique=False)
    op.create_index(op.f('ix_users_created_at'), 'users', ['created_at'], unique=False)

    op.create_table(
        'user_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('session_token_hash', sa.String(length=64), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('is_mfa_completed', sa.Boolean(), nullable=False, default=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_sessions_session_token_hash'), 'user_sessions', ['session_token_hash'], unique=True)
    op.create_index(op.f('ix_user_sessions_is_mfa_completed'), 'user_sessions', ['is_mfa_completed'], unique=False)
    op.create_index(op.f('ix_user_sessions_expires_at'), 'user_sessions', ['expires_at'], unique=False)

    op.create_table(
        'email_verification_tokens',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_verification_tokens_user_id'), 'email_verification_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_email_verification_tokens_token_hash'), 'email_verification_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_email_verification_tokens_expires_at'), 'email_verification_tokens', ['expires_at'], unique=False)

    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_tokens_user_id'), 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index(op.f('ix_password_reset_tokens_token_hash'), 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_password_reset_tokens_expires_at'), 'password_reset_tokens', ['expires_at'], unique=False)

    op.create_table(
        'mfa_configurations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('encrypted_secret', sa.Text(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mfa_configurations_user_id'), 'mfa_configurations', ['user_id'], unique=True)
    op.create_index(op.f('ix_mfa_configurations_is_enabled'), 'mfa_configurations', ['is_enabled'], unique=False)

    op.create_table(
        'recovery_codes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('code_hash', sa.String(length=64), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_codes_user_id'), 'recovery_codes', ['user_id'], unique=False)
    op.create_index(op.f('ix_recovery_codes_code_hash'), 'recovery_codes', ['code_hash'], unique=False)

    op.create_table(
        'gmail_connections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=True),
        sa.Column('token_path', sa.String(length=500), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, default=True),
        sa.Column('history_id', sa.String(length=100), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_sync_status', sa.String(length=100), default="idle"),
        sa.Column('calendar_sync_enabled', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'email', name='uq_user_gmail_email')
    )
    op.create_index(op.f('ix_gmail_connections_user_id'), 'gmail_connections', ['user_id'], unique=False)
    op.create_index(op.f('ix_gmail_connections_email'), 'gmail_connections', ['email'], unique=False)
    op.create_index(op.f('ix_gmail_connections_active'), 'gmail_connections', ['active'], unique=False)

    op.create_table(
        'notification_integrations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('target_id', sa.String(length=255), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_integrations_user_id'), 'notification_integrations', ['user_id'], unique=False)
    op.create_index(op.f('ix_notification_integrations_type'), 'notification_integrations', ['type'], unique=False)
    op.create_index(op.f('ix_notification_integrations_is_active'), 'notification_integrations', ['is_active'], unique=False)

    op.create_table(
        'notification_preferences',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('notification_mode', sa.String(length=50), nullable=False, default="immediate"),
        sa.Column('digest_interval_minutes', sa.Integer(), nullable=False, default=60),
        sa.Column('privacy_mode', sa.Boolean(), nullable=False, default=False),
        sa.Column('notification_cutoff_hours', sa.Integer(), nullable=False, default=24),
        sa.Column('reminder_offsets_min', sa.String(length=100), nullable=False, default="1440,360,60"),
        sa.Column('included_categories', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_preferences_user_id'), 'notification_preferences', ['user_id'], unique=True)

    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_user_id'), 'audit_events', ['user_id'], unique=False)
    op.create_index(op.f('ix_audit_events_event_type'), 'audit_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_audit_events_created_at'), 'audit_events', ['created_at'], unique=False)

    # 2. Alter existing tables to associate them with users
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_accounts_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_accounts_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('calendar_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_calendar_events_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_calendar_events_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('destinations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_destinations_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_destinations_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('emails', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_emails_user_created', ['user_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_emails_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_emails_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('notification_deliveries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_deliveries_user_created', ['user_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_deliveries_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_notification_deliveries_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_reminders_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_reminders_user_status', ['user_id', 'status'], unique=False)
        batch_op.create_foreign_key('fk_reminders_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('routing_rules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_routing_rules_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_routing_rules_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('sync_states', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.String(length=36), nullable=True))
        batch_op.create_index(batch_op.f('ix_sync_states_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_sync_states_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('sync_states', schema=None) as batch_op:
        batch_op.drop_constraint('fk_sync_states_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_sync_states_user_id'))
        batch_op.drop_column('user_id')

    with op.batch_alter_table('routing_rules', schema=None) as batch_op:
        batch_op.drop_constraint('fk_routing_rules_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_routing_rules_user_id'))
        batch_op.drop_column('user_id')

    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_reminders_user_id', type_='foreignkey')
        batch_op.drop_index('ix_reminders_user_status')
        batch_op.drop_index(batch_op.f('ix_reminders_user_id'))
        batch_op.drop_column('user_id')

    with op.batch_alter_table('notification_deliveries', schema=None) as batch_op:
        batch_op.drop_constraint('fk_notification_deliveries_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_notification_deliveries_user_id'))
        batch_op.drop_index('ix_deliveries_user_created')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('emails', schema=None) as batch_op:
        batch_op.drop_constraint('fk_emails_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_emails_user_id'))
        batch_op.drop_index('ix_emails_user_created')
        batch_op.drop_column('user_id')

    with op.batch_alter_table('destinations', schema=None) as batch_op:
        batch_op.drop_constraint('fk_destinations_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_destinations_user_id'))
        batch_op.drop_column('user_id')

    with op.batch_alter_table('calendar_events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_calendar_events_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_calendar_events_user_id'))
        batch_op.drop_column('user_id')

    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_accounts_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_accounts_user_id'))
        batch_op.drop_column('user_id')

    op.drop_table('audit_events')
    op.drop_table('notification_preferences')
    op.drop_table('notification_integrations')
    op.drop_table('gmail_connections')
    op.drop_table('recovery_codes')
    op.drop_table('mfa_configurations')
    op.drop_table('password_reset_tokens')
    op.drop_table('email_verification_tokens')
    op.drop_table('user_sessions')
    op.drop_table('users')
