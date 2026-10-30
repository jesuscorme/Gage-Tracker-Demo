"""Integrations & Data (API clients, idempotency, webhooks, imports, devices) and compliance permission.

Revision ID: 0010_integrations
Revises: 0009_oot
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_integrations"
down_revision = "0009_oot"
branch_labels = None
depends_on = None

# Frozen copy of the permissions, roles and grants introduced by this revision.
PERMISSIONS = {'integrations:read': 'View integrations, import history and webhook deliveries', 'integrations:manage': 'Manage API clients, webhooks, devices and import jobs', 'connectors:submit': 'Submit readings from measurement devices', 'compliance:read': 'Query compliance evidence and export audit records'}
NEW_ROLES = {'edge_agent': 'Edge Connector (service account)'}
GRANTS = {'org_admin': ['integrations:read', 'integrations:manage', 'connectors:submit', 'compliance:read'], 'metrology_manager': ['integrations:read', 'integrations:manage', 'compliance:read'], 'auditor': ['integrations:read', 'compliance:read'], 'edge_agent': ['gages:read', 'connectors:submit']}


def upgrade() -> None:
    op.create_table('idempotency_records',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('scope_hash', sa.String(length=64), nullable=False),
    sa.Column('idempotency_key', sa.String(length=100), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('path', sa.String(length=300), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=True),
    sa.Column('response_body', sa.Text(), nullable=True),
    sa.Column('content_type', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_idempotency_records')),
    sa.UniqueConstraint('scope_hash', 'idempotency_key', name=op.f('uq_idempotency_records_scope_hash_idempotency_key'))
    )
    op.create_table('api_clients',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('key_prefix', sa.String(length=16), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_reason', sa.String(length=500), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_api_clients_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_api_clients_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_api_clients_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_clients')),
    sa.UniqueConstraint('key_prefix', name=op.f('uq_api_clients_key_prefix')),
    sa.UniqueConstraint('user_id', name=op.f('uq_api_clients_user_id'))
    )
    op.create_index(op.f('ix_api_clients_organization_id'), 'api_clients', ['organization_id'], unique=False)
    op.create_table('webhook_endpoints',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('url', sa.String(length=500), nullable=False),
    sa.Column('secret', sa.String(length=100), nullable=False),
    sa.Column('event_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_webhook_endpoints_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_webhook_endpoints_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_endpoints'))
    )
    op.create_index(op.f('ix_webhook_endpoints_organization_id'), 'webhook_endpoints', ['organization_id'], unique=False)
    op.create_table('api_request_log',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('client_id', sa.Uuid(), nullable=False),
    sa.Column('method', sa.String(length=10), nullable=False),
    sa.Column('path', sa.String(length=300), nullable=False),
    sa.Column('request_id', sa.String(length=64), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('requested_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['client_id'], ['api_clients.id'], name=op.f('fk_api_request_log_client_id_api_clients'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_api_request_log_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_request_log'))
    )
    op.create_index('ix_api_request_log_client_at', 'api_request_log', ['client_id', 'requested_at'], unique=False)
    op.create_table('import_jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('importer', sa.String(length=40), nullable=False),
    sa.Column('target_id', sa.Uuid(), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('attachment_id', sa.Uuid(), nullable=False),
    sa.Column('mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('total_rows', sa.Integer(), nullable=False),
    sa.Column('valid_rows', sa.Integer(), nullable=False),
    sa.Column('error_count', sa.Integer(), nullable=False),
    sa.Column('errors', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('preview', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('reprocess_of_id', sa.Uuid(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('committed_by', sa.Uuid(), nullable=True),
    sa.Column('committed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('VALIDATED', 'INVALID', 'COMMITTED')", name=op.f('ck_import_jobs_status_valid')),
    sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], name=op.f('fk_import_jobs_attachment_id_attachments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['committed_by'], ['users.id'], name=op.f('fk_import_jobs_committed_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_import_jobs_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_import_jobs_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reprocess_of_id'], ['import_jobs.id'], name=op.f('fk_import_jobs_reprocess_of_id_import_jobs'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_import_jobs'))
    )
    op.create_index(op.f('ix_import_jobs_organization_id'), 'import_jobs', ['organization_id'], unique=False)
    op.create_table('webhook_deliveries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('endpoint_id', sa.Uuid(), nullable=False),
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_status_code', sa.Integer(), nullable=True),
    sa.Column('last_error', sa.String(length=500), nullable=True),
    sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'DEAD')", name=op.f('ck_webhook_deliveries_status_valid')),
    sa.ForeignKeyConstraint(['endpoint_id'], ['webhook_endpoints.id'], name=op.f('fk_webhook_deliveries_endpoint_id_webhook_endpoints'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['event_id'], ['outbox_events.id'], name=op.f('fk_webhook_deliveries_event_id_outbox_events'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_webhook_deliveries_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_deliveries')),
    sa.UniqueConstraint('endpoint_id', 'event_id', name=op.f('uq_webhook_deliveries_endpoint_id_event_id'))
    )
    op.create_index('ix_webhook_deliveries_due', 'webhook_deliveries', ['status', 'next_attempt_at'], unique=False)
    op.create_table('webhook_attempts',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('delivery_id', sa.Uuid(), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=True),
    sa.Column('error', sa.String(length=500), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('attempted_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['delivery_id'], ['webhook_deliveries.id'], name=op.f('fk_webhook_attempts_delivery_id_webhook_deliveries'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_webhook_attempts'))
    )
    op.create_index(op.f('ix_webhook_attempts_delivery_id'), 'webhook_attempts', ['delivery_id'], unique=False)
    op.create_table('devices',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('device_code', sa.String(length=40), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('adapter', sa.String(length=40), nullable=False),
    sa.Column('serial_number', sa.String(length=80), nullable=True),
    sa.Column('gage_id', sa.Uuid(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_devices_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_devices_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_devices_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_devices_plant_id_plants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_devices')),
    sa.UniqueConstraint('organization_id', 'device_code', name=op.f('uq_devices_organization_id_device_code'))
    )
    op.create_index(op.f('ix_devices_organization_id'), 'devices', ['organization_id'], unique=False)
    op.create_table('device_readings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('device_id', sa.Uuid(), nullable=False),
    sa.Column('gage_id', sa.Uuid(), nullable=True),
    sa.Column('reading_uid', sa.String(length=80), nullable=False),
    sa.Column('value', sa.Numeric(precision=24, scale=10), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('raw', sa.String(length=500), nullable=False),
    sa.Column('gage_status', sa.String(length=20), nullable=True),
    sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('submitted_by', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], name=op.f('fk_device_readings_device_id_devices'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_device_readings_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_device_readings_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], name=op.f('fk_device_readings_submitted_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_device_readings')),
    sa.UniqueConstraint('device_id', 'reading_uid', name=op.f('uq_device_readings_device_id_reading_uid'))
    )
    op.create_index('ix_device_readings_gage_at', 'device_readings', ['gage_id', 'captured_at'], unique=False)
    op.execute("CREATE TRIGGER trg_device_readings_append_only BEFORE UPDATE OR DELETE ON device_readings FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")
    op.execute("CREATE TRIGGER trg_webhook_attempts_append_only BEFORE UPDATE OR DELETE ON webhook_attempts FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")
    op.execute("CREATE TRIGGER trg_api_request_log_append_only BEFORE UPDATE OR DELETE ON api_request_log FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")

    permissions = sa.table("permissions", sa.column("code", sa.String), sa.column("description", sa.String))
    op.bulk_insert(permissions, [{"code": c, "description": d} for c, d in PERMISSIONS.items()])
    for code, name in NEW_ROLES.items():
        op.execute(sa.text("INSERT INTO roles (id, code, name, is_system) VALUES (gen_random_uuid(), :c, :n, true)")
                   .bindparams(c=code, n=name))
    for role, perms in GRANTS.items():
        for perm in perms:
            op.execute(sa.text(
                "INSERT INTO role_permissions (role_id, permission_code) SELECT id, :p FROM roles WHERE code = :c"
            ).bindparams(p=perm, c=role))


def downgrade() -> None:
    for role, perms in GRANTS.items():
        op.execute(sa.text(
            "DELETE FROM role_permissions WHERE permission_code = ANY(:p) AND role_id = (SELECT id FROM roles WHERE code = :c)"
        ).bindparams(p=perms, c=role))
    op.execute(sa.text("DELETE FROM roles WHERE code = ANY(:c)").bindparams(c=list(NEW_ROLES)))
    op.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:c)").bindparams(c=list(PERMISSIONS)))
    op.execute("DROP TRIGGER IF EXISTS trg_device_readings_append_only ON device_readings")
    op.execute("DROP TRIGGER IF EXISTS trg_webhook_attempts_append_only ON webhook_attempts")
    op.execute("DROP TRIGGER IF EXISTS trg_api_request_log_append_only ON api_request_log")
    op.drop_index('ix_device_readings_gage_at', table_name='device_readings')
    op.drop_table('device_readings')
    op.drop_index(op.f('ix_devices_organization_id'), table_name='devices')
    op.drop_table('devices')
    op.drop_index(op.f('ix_webhook_attempts_delivery_id'), table_name='webhook_attempts')
    op.drop_table('webhook_attempts')
    op.drop_index('ix_webhook_deliveries_due', table_name='webhook_deliveries')
    op.drop_table('webhook_deliveries')
    op.drop_index(op.f('ix_import_jobs_organization_id'), table_name='import_jobs')
    op.drop_table('import_jobs')
    op.drop_index('ix_api_request_log_client_at', table_name='api_request_log')
    op.drop_table('api_request_log')
    op.drop_index(op.f('ix_webhook_endpoints_organization_id'), table_name='webhook_endpoints')
    op.drop_table('webhook_endpoints')
    op.drop_index(op.f('ix_api_clients_organization_id'), table_name='api_clients')
    op.drop_table('api_clients')
    op.drop_table('idempotency_records')
