"""Platform foundation: tenants, plants, departments, users, RBAC and audit trail.

Revision ID: 0001_platform_foundation
Revises: 
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_platform_foundation"
down_revision = None
branch_labels = None
depends_on = None

APPEND_ONLY_FN = """
CREATE OR REPLACE FUNCTION forbid_append_only_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% is append-only: % is not allowed', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""


def append_only(table: str) -> str:
    return (
        f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()"
    )

# Frozen copy of the permission catalogue at this revision (see app/modules/identity/permissions.py).
PERMISSIONS = {
    "organization:read": "View organization, plants and departments",
    "organization:manage": "Edit organization settings",
    "plants:manage": "Create and edit plants and departments",
    "users:read": "View users of the organization",
    "users:manage": "Invite users, assign roles and plant scope",
    "audit:read": "View the audit trail",
}
ROLES = {
    "org_admin": ("Organization Administrator", list(PERMISSIONS)),
    "metrology_manager": ("Metrology Manager", ["organization:read", "users:read", "audit:read"]),
    "metrology_technician": ("Metrology Technician", ["organization:read", "users:read"]),
    "auditor": ("Auditor (read only)", ["organization:read", "users:read", "audit:read"]),
    "viewer": ("Viewer", ["organization:read"]),
}


def upgrade() -> None:
    op.create_table('organizations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('due_soon_days', sa.Integer(), server_default=sa.text('30'), nullable=False),
    sa.Column('timezone', sa.String(length=64), server_default='UTC', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organizations')),
    sa.UniqueConstraint('slug', name=op.f('uq_organizations_slug'))
    )
    op.create_table('permissions',
    sa.Column('code', sa.String(length=80), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.PrimaryKeyConstraint('code', name=op.f('pk_permissions'))
    )
    op.create_table('roles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('is_system', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_roles')),
    sa.UniqueConstraint('code', name=op.f('uq_roles_code'))
    )
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('password_hash', sa.String(length=200), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('preferred_language', sa.String(length=5), server_default='es', nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('audit_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=True),
    sa.Column('actor_user_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('entity_type', sa.String(length=60), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('reason', sa.String(length=1000), nullable=True),
    sa.Column('request_id', sa.String(length=64), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name=op.f('fk_audit_events_actor_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_audit_events_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )
    op.create_index('ix_audit_events_entity', 'audit_events', ['entity_type', 'entity_id'], unique=False)
    op.create_index('ix_audit_events_org_created', 'audit_events', ['organization_id', 'created_at'], unique=False)
    op.create_table('organization_memberships',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_organization_memberships_organization_id_organizations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_organization_memberships_role_id_roles'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_organization_memberships_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_organization_memberships')),
    sa.UniqueConstraint('user_id', 'organization_id', name=op.f('uq_organization_memberships_user_id_organization_id'))
    )
    op.create_index(op.f('ix_organization_memberships_organization_id'), 'organization_memberships', ['organization_id'], unique=False)
    op.create_index(op.f('ix_organization_memberships_user_id'), 'organization_memberships', ['user_id'], unique=False)
    op.create_table('plants',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_plants_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plants')),
    sa.UniqueConstraint('organization_id', 'code', name=op.f('uq_plants_organization_id_code'))
    )
    op.create_index(op.f('ix_plants_organization_id'), 'plants', ['organization_id'], unique=False)
    op.create_table('role_permissions',
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('permission_code', sa.String(length=80), nullable=False),
    sa.ForeignKeyConstraint(['permission_code'], ['permissions.code'], name=op.f('fk_role_permissions_permission_code_permissions'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], name=op.f('fk_role_permissions_role_id_roles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('role_id', 'permission_code', name=op.f('pk_role_permissions'))
    )
    op.create_table('departments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_departments_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_departments_plant_id_plants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_departments')),
    sa.UniqueConstraint('plant_id', 'code', name=op.f('uq_departments_plant_id_code'))
    )
    op.create_index(op.f('ix_departments_organization_id'), 'departments', ['organization_id'], unique=False)
    op.create_index(op.f('ix_departments_plant_id'), 'departments', ['plant_id'], unique=False)
    op.create_table('plant_memberships',
    sa.Column('membership_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['membership_id'], ['organization_memberships.id'], name=op.f('fk_plant_memberships_membership_id_organization_memberships'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_plant_memberships_plant_id_plants'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('membership_id', 'plant_id', name=op.f('pk_plant_memberships'))
    )

    op.execute(APPEND_ONLY_FN)
    op.execute(append_only("audit_events"))

    permissions = sa.table("permissions", sa.column("code", sa.String), sa.column("description", sa.String))
    op.bulk_insert(permissions, [{"code": c, "description": d} for c, d in PERMISSIONS.items()])
    for code, (name, perms) in ROLES.items():
        op.execute(
            sa.text("INSERT INTO roles (id, code, name, is_system) VALUES (gen_random_uuid(), :c, :n, true)")
            .bindparams(c=code, n=name)
        )
        for perm in perms:
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_code) "
                    "SELECT id, :p FROM roles WHERE code = :c"
                ).bindparams(p=perm, c=code)
            )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.drop_table('plant_memberships')
    op.drop_index(op.f('ix_departments_plant_id'), table_name='departments')
    op.drop_index(op.f('ix_departments_organization_id'), table_name='departments')
    op.drop_table('departments')
    op.drop_table('role_permissions')
    op.drop_index(op.f('ix_plants_organization_id'), table_name='plants')
    op.drop_table('plants')
    op.drop_index(op.f('ix_organization_memberships_user_id'), table_name='organization_memberships')
    op.drop_index(op.f('ix_organization_memberships_organization_id'), table_name='organization_memberships')
    op.drop_table('organization_memberships')
    op.drop_index('ix_audit_events_org_created', table_name='audit_events')
    op.drop_index('ix_audit_events_entity', table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_table('users')
    op.drop_table('roles')
    op.drop_table('permissions')
    op.drop_table('organizations')
    op.execute("DROP FUNCTION IF EXISTS forbid_append_only_change()")
