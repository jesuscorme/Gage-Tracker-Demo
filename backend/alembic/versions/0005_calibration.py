"""Calibration Management and in-app notifications.

Revision ID: 0005_calibration
Revises: 0004_standards_competency
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_calibration"
down_revision = "0004_standards_competency"
branch_labels = None
depends_on = None


PROTECT_FN = """
CREATE OR REPLACE FUNCTION protect_measurement_row() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND OLD.superseded = false AND NEW.superseded = true
       AND (to_jsonb(NEW) - 'superseded') = (to_jsonb(OLD) - 'superseded') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION '% rows are immutable: corrections must supersede (attempted %)', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""

# Frozen copy of the permissions, roles and grants introduced by this revision.
PERMISSIONS = {'calibration:read': 'View calibration and verification activities', 'calibration:manage': 'Plan, request, schedule and cancel calibration activities; manage certificates', 'calibration:execute': 'Execute activities and capture As Found / As Left results', 'calibration:review': 'Perform technical review of calibration activities', 'calibration:approve': 'Approve calibration activities', 'calibration:release': 'Release approved activities into the gage record', 'calibration:settings': 'Configure enabled activity types and evidence requirements'}
NEW_ROLES = {}
GRANTS = {'org_admin': ['calibration:read', 'calibration:manage', 'calibration:execute', 'calibration:review', 'calibration:approve', 'calibration:release', 'calibration:settings'], 'metrology_manager': ['calibration:read', 'calibration:manage', 'calibration:execute', 'calibration:review', 'calibration:approve', 'calibration:release', 'calibration:settings'], 'metrology_technician': ['calibration:read', 'calibration:execute'], 'lab_technician': ['calibration:read'], 'auditor': ['calibration:read'], 'viewer': ['calibration:read']}


def upgrade() -> None:
    op.create_table('notification_preferences',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_notification_preferences_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notification_preferences_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_preferences')),
    sa.UniqueConstraint('organization_id', 'user_id', 'kind', name=op.f('uq_notification_preferences_organization_id_user_id_kind'))
    )
    op.create_table('notifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.String(length=1000), nullable=True),
    sa.Column('link', sa.String(length=300), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_notifications_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index('ix_notifications_user', 'notifications', ['organization_id', 'user_id', 'read_at'], unique=False)
    op.create_table('calibration_settings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=True),
    sa.Column('activity_type', sa.String(length=30), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('require_certificate', sa.Boolean(), nullable=False),
    sa.Column('require_standard', sa.Boolean(), nullable=False),
    sa.Column('require_as_found', sa.Boolean(), nullable=False),
    sa.Column('require_environment', sa.Boolean(), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("activity_type IN ('EXTERNAL_CALIBRATION', 'INTERNAL_CALIBRATION', 'ROUTINE_VERIFICATION')", name=op.f('ck_calibration_settings_activity_type_valid')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_calibration_settings_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_calibration_settings_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], name=op.f('fk_calibration_settings_updated_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calibration_settings')),
    sa.UniqueConstraint('organization_id', 'plant_id', 'activity_type', name=op.f('uq_calibration_settings_organization_id_plant_id_activity_type'), postgresql_nulls_not_distinct=True)
    )
    op.create_table('calibration_activities',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('gage_id', sa.Uuid(), nullable=False),
    sa.Column('calibration_code', sa.String(length=30), nullable=False),
    sa.Column('activity_type', sa.String(length=30), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('planned_date', sa.Date(), nullable=False),
    sa.Column('requested_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('requested_by', sa.Uuid(), nullable=True),
    sa.Column('scheduled_date', sa.Date(), nullable=True),
    sa.Column('provider_name', sa.String(length=200), nullable=True),
    sa.Column('provider_accreditation', sa.String(length=120), nullable=True),
    sa.Column('technician_id', sa.Uuid(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('performed_date', sa.Date(), nullable=True),
    sa.Column('method', sa.String(length=300), nullable=True),
    sa.Column('environment_temperature', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('environment_humidity', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('environment_notes', sa.String(length=300), nullable=True),
    sa.Column('uncertainty', sa.String(length=200), nullable=True),
    sa.Column('adjusted', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('declared_result', sa.String(length=30), nullable=True),
    sa.Column('observations', sa.Text(), nullable=True),
    sa.Column('result', sa.String(length=30), nullable=True),
    sa.Column('as_found_in_tolerance', sa.Boolean(), nullable=True),
    sa.Column('as_left_in_tolerance', sa.Boolean(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('submitted_by', sa.Uuid(), nullable=True),
    sa.Column('reviewer_id', sa.Uuid(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_comments', sa.String(length=2000), nullable=True),
    sa.Column('approver_id', sa.Uuid(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('released_by', sa.Uuid(), nullable=True),
    sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('cancel_reason', sa.String(length=1000), nullable=True),
    sa.Column('gage_prior_control_status', sa.String(length=20), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("activity_type IN ('EXTERNAL_CALIBRATION', 'INTERNAL_CALIBRATION', 'ROUTINE_VERIFICATION')", name=op.f('ck_calibration_activities_activity_type_valid')),
    sa.CheckConstraint("result IS NULL OR result IN ('PASS', 'PASS_AFTER_ADJUSTMENT', 'FAIL')", name=op.f('ck_calibration_activities_result_valid')),
    sa.CheckConstraint("status IN ('PLANNED', 'REQUESTED', 'SCHEDULED', 'IN_PROGRESS', 'PENDING_REVIEW', 'PENDING_APPROVAL', 'APPROVED', 'RELEASED', 'CANCELLED')", name=op.f('ck_calibration_activities_status_valid')),
    sa.ForeignKeyConstraint(['approver_id'], ['users.id'], name=op.f('fk_calibration_activities_approver_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_calibration_activities_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_calibration_activities_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_calibration_activities_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_calibration_activities_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['released_by'], ['users.id'], name=op.f('fk_calibration_activities_released_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], name=op.f('fk_calibration_activities_requested_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], name=op.f('fk_calibration_activities_reviewer_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], name=op.f('fk_calibration_activities_submitted_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['technician_id'], ['users.id'], name=op.f('fk_calibration_activities_technician_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calibration_activities')),
    sa.UniqueConstraint('organization_id', 'calibration_code', name=op.f('uq_calibration_activities_organization_id_calibration_code'))
    )
    op.create_index('ix_calibration_activities_gage', 'calibration_activities', ['organization_id', 'gage_id'], unique=False)
    op.create_index('ix_calibration_activities_status', 'calibration_activities', ['organization_id', 'status'], unique=False)
    op.create_table('calibration_certificates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('calibration_id', sa.Uuid(), nullable=False),
    sa.Column('gage_id', sa.Uuid(), nullable=False),
    sa.Column('certificate_number', sa.String(length=80), nullable=False),
    sa.Column('issuer', sa.String(length=200), nullable=False),
    sa.Column('issue_date', sa.Date(), nullable=False),
    sa.Column('attachment_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('superseded_reason', sa.String(length=500), nullable=True),
    sa.Column('uploaded_by', sa.Uuid(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("status IN ('CURRENT','SUPERSEDED')", name=op.f('ck_calibration_certificates_status_valid')),
    sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], name=op.f('fk_calibration_certificates_attachment_id_attachments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['calibration_id'], ['calibration_activities.id'], name=op.f('fk_calibration_certificates_calibration_id_calibration_activities'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_calibration_certificates_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_calibration_certificates_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_calibration_certificates_uploaded_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calibration_certificates'))
    )
    op.create_index(op.f('ix_calibration_certificates_calibration_id'), 'calibration_certificates', ['calibration_id'], unique=False)
    op.create_index(op.f('ix_calibration_certificates_gage_id'), 'calibration_certificates', ['gage_id'], unique=False)
    op.create_table('calibration_points',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('calibration_id', sa.Uuid(), nullable=False),
    sa.Column('phase', sa.String(length=10), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=True),
    sa.Column('nominal', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('lower_limit', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('upper_limit', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('measured', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('uncertainty', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('in_tolerance', sa.Boolean(), nullable=False),
    sa.Column('supersedes_id', sa.Uuid(), nullable=True),
    sa.Column('superseded', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('correction_reason', sa.String(length=500), nullable=True),
    sa.Column('recorded_by', sa.Uuid(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("phase IN ('AS_FOUND','AS_LEFT')", name=op.f('ck_calibration_points_phase_valid')),
    sa.CheckConstraint('lower_limit <= upper_limit', name=op.f('ck_calibration_points_limits_ordered')),
    sa.ForeignKeyConstraint(['calibration_id'], ['calibration_activities.id'], name=op.f('fk_calibration_points_calibration_id_calibration_activities'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_calibration_points_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], name=op.f('fk_calibration_points_recorded_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['supersedes_id'], ['calibration_points.id'], name=op.f('fk_calibration_points_supersedes_id_calibration_points'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calibration_points'))
    )
    op.create_index('ix_calibration_points_activity', 'calibration_points', ['calibration_id', 'phase'], unique=False)
    op.create_table('calibration_standard_usages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('calibration_id', sa.Uuid(), nullable=False),
    sa.Column('standard_id', sa.Uuid(), nullable=False),
    sa.Column('used_on', sa.Date(), nullable=False),
    sa.Column('standard_status', sa.String(length=20), nullable=False),
    sa.Column('certificate_id', sa.Uuid(), nullable=True),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('is_exception', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('exception_reason', sa.String(length=500), nullable=True),
    sa.Column('exception_authorized_by', sa.Uuid(), nullable=True),
    sa.Column('recorded_by', sa.Uuid(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['calibration_id'], ['calibration_activities.id'], name=op.f('fk_calibration_standard_usages_calibration_id_calibration_activities'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['certificate_id'], ['standard_certificates.id'], name=op.f('fk_calibration_standard_usages_certificate_id_standard_certificates'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['exception_authorized_by'], ['users.id'], name=op.f('fk_calibration_standard_usages_exception_authorized_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_calibration_standard_usages_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], name=op.f('fk_calibration_standard_usages_recorded_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['standard_id'], ['standards.id'], name=op.f('fk_calibration_standard_usages_standard_id_standards'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calibration_standard_usages')),
    sa.UniqueConstraint('calibration_id', 'standard_id', name=op.f('uq_calibration_standard_usages_calibration_id_standard_id'))
    )
    op.create_index(op.f('ix_calibration_standard_usages_standard_id'), 'calibration_standard_usages', ['standard_id'], unique=False)
    op.create_table('calibration_status_history',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('calibration_id', sa.Uuid(), nullable=False),
    sa.Column('from_status', sa.String(length=20), nullable=True),
    sa.Column('to_status', sa.String(length=20), nullable=False),
    sa.Column('comment', sa.String(length=2000), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('changed_by', sa.Uuid(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['calibration_id'], ['calibration_activities.id'], name=op.f('fk_calibration_status_history_calibration_id_calibration_activities'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['changed_by'], ['users.id'], name=op.f('fk_calibration_status_history_changed_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_calibration_status_history_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_calibration_status_history'))
    )
    op.create_index(op.f('ix_calibration_status_history_calibration_id'), 'calibration_status_history', ['calibration_id'], unique=False)
    op.execute(PROTECT_FN)
    op.execute("CREATE TRIGGER trg_calibration_status_history_append_only BEFORE UPDATE OR DELETE ON calibration_status_history FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")
    op.execute("CREATE TRIGGER trg_calibration_points_protect BEFORE UPDATE OR DELETE ON calibration_points FOR EACH ROW EXECUTE FUNCTION protect_measurement_row()")

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
    op.execute("DROP TRIGGER IF EXISTS trg_calibration_status_history_append_only ON calibration_status_history")
    op.execute("DROP TRIGGER IF EXISTS trg_calibration_points_protect ON calibration_points")
    op.drop_index(op.f('ix_calibration_status_history_calibration_id'), table_name='calibration_status_history')
    op.drop_table('calibration_status_history')
    op.drop_index(op.f('ix_calibration_standard_usages_standard_id'), table_name='calibration_standard_usages')
    op.drop_table('calibration_standard_usages')
    op.drop_index('ix_calibration_points_activity', table_name='calibration_points')
    op.drop_table('calibration_points')
    op.drop_index(op.f('ix_calibration_certificates_gage_id'), table_name='calibration_certificates')
    op.drop_index(op.f('ix_calibration_certificates_calibration_id'), table_name='calibration_certificates')
    op.drop_table('calibration_certificates')
    op.drop_index('ix_calibration_activities_status', table_name='calibration_activities')
    op.drop_index('ix_calibration_activities_gage', table_name='calibration_activities')
    op.drop_table('calibration_activities')
    op.drop_table('calibration_settings')
    op.drop_index('ix_notifications_user', table_name='notifications')
    op.drop_table('notifications')
    op.drop_table('notification_preferences')
    op.execute("DROP FUNCTION IF EXISTS protect_measurement_row()")
