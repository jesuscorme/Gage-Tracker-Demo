"""Gage Management: gage type catalogue, gages and status history.

Revision ID: 0002_gage_management
Revises: 0001_platform_foundation
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op

revision = "0002_gage_management"
down_revision = "0001_platform_foundation"
branch_labels = None
depends_on = None

# Frozen copy of the permissions introduced by this revision.
PERMISSIONS = {
    "gage_types:manage": "Manage the gage type catalogue",
    "gages:read": "View gages",
    "gages:create": "Register gages",
    "gages:update": "Edit descriptive gage data",
    "gages:retire": "Retire gages (logical deletion)",
    "gages:restrict": "Place gages Out of Service or In Calibration",
    "gages:release": "Release restricted gages and change calibration dates/frequency",
}
GRANTS = {
    "org_admin": list(PERMISSIONS),
    "metrology_manager": list(PERMISSIONS),
    "metrology_technician": ["gages:read", "gages:create", "gages:update", "gages:restrict"],
    "auditor": ["gages:read"],
    "viewer": ["gages:read"],
}


def upgrade() -> None:
    op.create_table('gage_types',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('default_frequency_days', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_gage_types_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_gage_types')),
    sa.UniqueConstraint('organization_id', 'code', name=op.f('uq_gage_types_organization_id_code'))
    )
    op.create_index(op.f('ix_gage_types_organization_id'), 'gage_types', ['organization_id'], unique=False)
    op.create_table('gages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('department_id', sa.Uuid(), nullable=True),
    sa.Column('gage_type_id', sa.Uuid(), nullable=False),
    sa.Column('responsible_user_id', sa.Uuid(), nullable=True),
    sa.Column('gage_code', sa.String(length=50), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.Column('manufacturer', sa.String(length=120), nullable=True),
    sa.Column('model', sa.String(length=120), nullable=True),
    sa.Column('serial_number', sa.String(length=120), nullable=True),
    sa.Column('range_min', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('range_max', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('resolution', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('accuracy', sa.String(length=120), nullable=True),
    sa.Column('criticality', sa.String(length=10), nullable=True),
    sa.Column('location', sa.String(length=200), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('calibration_frequency_days', sa.Integer(), nullable=False),
    sa.Column('last_calibration_date', sa.Date(), nullable=True),
    sa.Column('next_due_date', sa.Date(), nullable=True),
    sa.Column('control_status', sa.String(length=20), server_default='ACTIVE', nullable=False),
    sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("control_status IN ('ACTIVE','OUT_OF_SERVICE','IN_CALIBRATION','INACTIVE')", name=op.f('ck_gages_control_status_valid')),
    sa.CheckConstraint('calibration_frequency_days > 0', name=op.f('ck_gages_frequency_positive')),
    sa.CheckConstraint('range_min IS NULL OR range_max IS NULL OR range_min <= range_max', name=op.f('ck_gages_range_ordered')),
    sa.CheckConstraint('resolution IS NULL OR resolution > 0', name=op.f('ck_gages_resolution_positive')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_gages_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_gages_department_id_departments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_type_id'], ['gage_types.id'], name=op.f('fk_gages_gage_type_id_gage_types'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_gages_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_gages_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['responsible_user_id'], ['users.id'], name=op.f('fk_gages_responsible_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_gages_updated_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_gages')),
    sa.UniqueConstraint('organization_id', 'gage_code', name=op.f('uq_gages_organization_id_gage_code'))
    )
    op.create_index('ix_gages_org_due', 'gages', ['organization_id', 'next_due_date'], unique=False)
    op.create_index('ix_gages_org_plant', 'gages', ['organization_id', 'plant_id'], unique=False)
    op.create_table('gage_status_history',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('gage_id', sa.Uuid(), nullable=False),
    sa.Column('from_control_status', sa.String(length=20), nullable=True),
    sa.Column('to_control_status', sa.String(length=20), nullable=False),
    sa.Column('from_status', sa.String(length=20), nullable=True),
    sa.Column('to_status', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.String(length=1000), nullable=True),
    sa.Column('changed_by', sa.Uuid(), nullable=True),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['changed_by'], ['users.id'], name=op.f('fk_gage_status_history_changed_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_gage_status_history_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_gage_status_history_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_gage_status_history'))
    )
    op.create_index(op.f('ix_gage_status_history_gage_id'), 'gage_status_history', ['gage_id'], unique=False)

    op.execute(
        "CREATE TRIGGER trg_gage_status_history_append_only BEFORE UPDATE OR DELETE ON gage_status_history "
        "FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()"
    )
    op.create_index("ix_gages_org_serial", "gages", ["organization_id", "serial_number"])

    permissions = sa.table("permissions", sa.column("code", sa.String), sa.column("description", sa.String))
    op.bulk_insert(permissions, [{"code": c, "description": d} for c, d in PERMISSIONS.items()])
    for role, perms in GRANTS.items():
        for perm in perms:
            op.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_code) "
                    "SELECT id, :p FROM roles WHERE code = :c"
                ).bindparams(p=perm, c=role)
            )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code = ANY(:codes)").bindparams(codes=list(PERMISSIONS))
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:codes)").bindparams(codes=list(PERMISSIONS)))
    op.drop_index("ix_gages_org_serial", table_name="gages")
    op.execute("DROP TRIGGER IF EXISTS trg_gage_status_history_append_only ON gage_status_history")
    op.drop_index(op.f('ix_gage_status_history_gage_id'), table_name='gage_status_history')
    op.drop_table('gage_status_history')
    op.drop_index('ix_gages_org_plant', table_name='gages')
    op.drop_index('ix_gages_org_due', table_name='gages')
    op.drop_table('gages')
    op.drop_index(op.f('ix_gage_types_organization_id'), table_name='gage_types')
    op.drop_table('gage_types')
