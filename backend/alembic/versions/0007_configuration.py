"""Platform configuration (versioned items, custom fields, workflow history) and the domain event outbox.

Revision ID: 0007_configuration
Revises: 0006_laboratory
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_configuration"
down_revision = "0006_laboratory"
branch_labels = None
depends_on = None

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION protect_config_version() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND (to_jsonb(NEW) - 'status' - 'decided_by' - 'decided_at' - 'decision_comment')
       = (to_jsonb(OLD) - 'status' - 'decided_by' - 'decided_at' - 'decision_comment') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'configuration versions are immutable (attempted %)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""

# Frozen copy of the permissions, roles and grants introduced by this revision.
PERMISSIONS = {'config:read': 'View platform configuration', 'config:manage': 'Edit custom fields, forms, workflows, approval matrices and business rules', 'config:approve': 'Approve configuration changes'}
NEW_ROLES = {}
GRANTS = {'org_admin': ['config:read', 'config:manage', 'config:approve'], 'metrology_manager': ['config:read', 'config:manage', 'config:approve'], 'auditor': ['config:read']}


def upgrade() -> None:
    op.create_table('config_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('key', sa.String(length=120), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('active_version', sa.Integer(), nullable=True),
    sa.Column('is_retired', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('CUSTOM_FIELD', 'FORM', 'WORKFLOW', 'APPROVAL_MATRIX', 'BUSINESS_RULE')", name=op.f('ck_config_items_kind_valid')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_config_items_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_config_items_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_config_items')),
    sa.UniqueConstraint('organization_id', 'kind', 'key', name=op.f('uq_config_items_organization_id_kind_key'))
    )
    op.create_index(op.f('ix_config_items_organization_id'), 'config_items', ['organization_id'], unique=False)
    op.create_table('custom_field_values',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('field_key', sa.String(length=60), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('field_version', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_custom_field_values_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_custom_field_values_updated_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_custom_field_values')),
    sa.UniqueConstraint('organization_id', 'entity_type', 'entity_id', 'field_key', name=op.f('uq_custom_field_values_organization_id_entity_type_entity_id_field_key'))
    )
    op.create_index('ix_custom_field_values_entity', 'custom_field_values', ['entity_type', 'entity_id'], unique=False)
    op.create_table('outbox_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=60), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('dedupe_key', sa.String(length=200), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_outbox_events_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_events')),
    sa.UniqueConstraint('organization_id', 'dedupe_key', name=op.f('uq_outbox_events_organization_id_dedupe_key'))
    )
    op.create_index('ix_outbox_events_org_created', 'outbox_events', ['organization_id', 'created_at'], unique=False)
    op.create_table('workflow_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('workflow_version', sa.Integer(), nullable=False),
    sa.Column('transition', sa.String(length=40), nullable=True),
    sa.Column('action', sa.String(length=20), nullable=True),
    sa.Column('from_state', sa.String(length=40), nullable=True),
    sa.Column('to_state', sa.String(length=40), nullable=True),
    sa.Column('comment', sa.String(length=2000), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_workflow_events_actor_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_workflow_events_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workflow_events'))
    )
    op.create_index('ix_workflow_events_entity', 'workflow_events', ['entity_type', 'entity_id'], unique=False)
    op.create_table('config_versions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('item_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('change_summary', sa.String(length=1000), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('decided_by', sa.Uuid(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_comment', sa.String(length=1000), nullable=True),
    sa.CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED', 'REJECTED')", name=op.f('ck_config_versions_status_valid')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_config_versions_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], name=op.f('fk_config_versions_decided_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['item_id'], ['config_items.id'], name=op.f('fk_config_versions_item_id_config_items'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_config_versions_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_config_versions')),
    sa.UniqueConstraint('item_id', 'version', name=op.f('uq_config_versions_item_id_version'))
    )
    op.create_index(op.f('ix_config_versions_item_id'), 'config_versions', ['item_id'], unique=False)
    op.execute(FUNCTION_SQL)
    op.execute("CREATE TRIGGER trg_workflow_events_append_only BEFORE UPDATE OR DELETE ON workflow_events FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")
    op.execute("CREATE TRIGGER trg_outbox_events_append_only BEFORE UPDATE OR DELETE ON outbox_events FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")
    op.execute("CREATE TRIGGER trg_config_versions_config BEFORE UPDATE OR DELETE ON config_versions FOR EACH ROW EXECUTE FUNCTION protect_config_version()")

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
    op.execute("DROP TRIGGER IF EXISTS trg_workflow_events_append_only ON workflow_events")
    op.execute("DROP TRIGGER IF EXISTS trg_outbox_events_append_only ON outbox_events")
    op.execute("DROP TRIGGER IF EXISTS trg_config_versions_config ON config_versions")
    op.drop_index(op.f('ix_config_versions_item_id'), table_name='config_versions')
    op.drop_table('config_versions')
    op.drop_index('ix_workflow_events_entity', table_name='workflow_events')
    op.drop_table('workflow_events')
    op.drop_index('ix_outbox_events_org_created', table_name='outbox_events')
    op.drop_table('outbox_events')
    op.drop_index('ix_custom_field_values_entity', table_name='custom_field_values')
    op.drop_table('custom_field_values')
    op.drop_index(op.f('ix_config_items_organization_id'), table_name='config_items')
    op.drop_table('config_items')
    op.execute("DROP FUNCTION IF EXISTS protect_config_version()")
