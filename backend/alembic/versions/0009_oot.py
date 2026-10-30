"""OOT & Impact Analysis: cases, impact items, actions and settings.

Revision ID: 0009_oot
Revises: 0008_msa
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_oot"
down_revision = "0008_msa"
branch_labels = None
depends_on = None

# Frozen copy of the permissions, roles and grants introduced by this revision.
PERMISSIONS = {'oot:read': 'View out-of-tolerance cases', 'oot:manage': 'Register and investigate out-of-tolerance cases', 'oot:approve': 'Approve and close OOT cases; release gages restricted by OOT'}
NEW_ROLES = {}
GRANTS = {'org_admin': ['oot:read', 'oot:manage', 'oot:approve'], 'metrology_manager': ['oot:read', 'oot:manage', 'oot:approve'], 'metrology_technician': ['oot:read', 'oot:manage'], 'lab_technician': ['oot:read'], 'auditor': ['oot:read'], 'viewer': ['oot:read']}


def upgrade() -> None:
    op.create_table('oot_settings',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('restrict_on_detection', sa.Boolean(), nullable=False),
    sa.Column('auto_create_from_calibration', sa.Boolean(), nullable=False),
    sa.Column('close_requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_oot_settings_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_oot_settings_updated_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('organization_id', name=op.f('pk_oot_settings'))
    )
    op.create_table('oot_cases',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('case_code', sa.String(length=30), nullable=False),
    sa.Column('gage_id', sa.Uuid(), nullable=False),
    sa.Column('calibration_id', sa.Uuid(), nullable=True),
    sa.Column('detection_source', sa.String(length=15), nullable=False),
    sa.Column('detected_on', sa.Date(), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('found_result', sa.String(length=500), nullable=True),
    sa.Column('tolerance', sa.String(length=200), nullable=True),
    sa.Column('max_deviation', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('as_found', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('as_left', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('responsible_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('workflow_version', sa.Integer(), nullable=False),
    sa.Column('restriction_applied', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('gage_prior_control_status', sa.String(length=20), nullable=True),
    sa.Column('gage_released_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('gage_released_by', sa.Uuid(), nullable=True),
    sa.Column('gage_release_reason', sa.String(length=1000), nullable=True),
    sa.Column('last_acceptable_calibration_id', sa.Uuid(), nullable=True),
    sa.Column('impact_start', sa.Date(), nullable=True),
    sa.Column('impact_end', sa.Date(), nullable=True),
    sa.Column('analysis_generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('limitations', sa.Text(), nullable=True),
    sa.Column('risk_level', sa.String(length=10), nullable=True),
    sa.Column('risk_assessment', sa.Text(), nullable=True),
    sa.Column('investigation_scope', sa.Text(), nullable=True),
    sa.Column('reinspection', sa.Text(), nullable=True),
    sa.Column('containment', sa.Text(), nullable=True),
    sa.Column('disposition', sa.Text(), nullable=True),
    sa.Column('corrective_actions', sa.Text(), nullable=True),
    sa.Column('customer_notification_required', sa.Boolean(), nullable=True),
    sa.Column('customer_notification', sa.Text(), nullable=True),
    sa.Column('customer_notified_on', sa.Date(), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("risk_level IS NULL OR risk_level IN ('LOW', 'MEDIUM', 'HIGH')", name=op.f('ck_oot_cases_risk_valid')),
    sa.ForeignKeyConstraint(['calibration_id'], ['calibration_activities.id'], name=op.f('fk_oot_cases_calibration_id_calibration_activities'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_oot_cases_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_oot_cases_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_released_by'], ['users.id'], name=op.f('fk_oot_cases_gage_released_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['last_acceptable_calibration_id'], ['calibration_activities.id'], name=op.f('fk_oot_cases_last_acceptable_calibration_id_calibration_activities'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_oot_cases_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_oot_cases_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['responsible_id'], ['users.id'], name=op.f('fk_oot_cases_responsible_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_oot_cases')),
    sa.UniqueConstraint('calibration_id', name=op.f('uq_oot_cases_calibration_id')),
    sa.UniqueConstraint('organization_id', 'case_code', name=op.f('uq_oot_cases_organization_id_case_code'))
    )
    op.create_index('ix_oot_cases_gage', 'oot_cases', ['gage_id'], unique=False)
    op.create_index(op.f('ix_oot_cases_organization_id'), 'oot_cases', ['organization_id'], unique=False)
    op.create_table('oot_actions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('action_type', sa.String(length=25), nullable=False),
    sa.Column('description', sa.String(length=2000), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('result_note', sa.String(length=2000), nullable=True),
    sa.Column('completed_by', sa.Uuid(), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("action_type IN ('CONTAINMENT', 'REINSPECTION', 'CORRECTIVE', 'CUSTOMER_NOTIFICATION', 'OTHER')", name=op.f('ck_oot_actions_action_type_valid')),
    sa.CheckConstraint("status IN ('OPEN', 'DONE', 'CANCELLED')", name=op.f('ck_oot_actions_status_valid')),
    sa.ForeignKeyConstraint(['case_id'], ['oot_cases.id'], name=op.f('fk_oot_actions_case_id_oot_cases'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['completed_by'], ['users.id'], name=op.f('fk_oot_actions_completed_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_oot_actions_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_oot_actions_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_oot_actions_owner_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_oot_actions'))
    )
    op.create_index(op.f('ix_oot_actions_case_id'), 'oot_actions', ['case_id'], unique=False)
    op.create_table('oot_impact_items',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('case_id', sa.Uuid(), nullable=False),
    sa.Column('item_type', sa.String(length=20), nullable=False),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('ref_id', sa.Uuid(), nullable=True),
    sa.Column('ref_code', sa.String(length=80), nullable=True),
    sa.Column('description', sa.String(length=1000), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('assessment', sa.String(length=12), nullable=False),
    sa.Column('assessment_note', sa.String(length=2000), nullable=True),
    sa.Column('assessed_by', sa.Uuid(), nullable=True),
    sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("assessment IN ('PENDING', 'NO_IMPACT', 'IMPACT', 'REINSPECT')", name=op.f('ck_oot_impact_items_assessment_valid')),
    sa.CheckConstraint("item_type IN ('INSPECTION_RESULT', 'WORK_ORDER', 'GAGE_MOVEMENT', 'MSA_STUDY', 'DEVICE_READINGS', 'MANUAL')", name=op.f('ck_oot_impact_items_item_type_valid')),
    sa.ForeignKeyConstraint(['assessed_by'], ['users.id'], name=op.f('fk_oot_impact_items_assessed_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['case_id'], ['oot_cases.id'], name=op.f('fk_oot_impact_items_case_id_oot_cases'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_oot_impact_items_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_oot_impact_items_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_oot_impact_items'))
    )
    op.create_index(op.f('ix_oot_impact_items_case_id'), 'oot_impact_items', ['case_id'], unique=False)
    op.create_index('uq_oot_impact_items_ref', 'oot_impact_items', ['case_id', 'item_type', 'ref_id'], unique=True, postgresql_where=sa.text('ref_id IS NOT NULL'))

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
    op.drop_index('uq_oot_impact_items_ref', table_name='oot_impact_items', postgresql_where=sa.text('ref_id IS NOT NULL'))
    op.drop_index(op.f('ix_oot_impact_items_case_id'), table_name='oot_impact_items')
    op.drop_table('oot_impact_items')
    op.drop_index(op.f('ix_oot_actions_case_id'), table_name='oot_actions')
    op.drop_table('oot_actions')
    op.drop_index(op.f('ix_oot_cases_organization_id'), table_name='oot_cases')
    op.drop_index('ix_oot_cases_gage', table_name='oot_cases')
    op.drop_table('oot_cases')
    op.drop_table('oot_settings')
