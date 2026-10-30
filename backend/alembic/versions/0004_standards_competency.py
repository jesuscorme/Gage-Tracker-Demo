"""Standards and Competency Management.

Revision ID: 0004_standards_competency
Revises: 0003_gage_completion
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_standards_competency"
down_revision = "0003_gage_completion"
branch_labels = None
depends_on = None

# Frozen copy of the permissions, roles and grants introduced by this revision.
PERMISSIONS = {'standards:read': 'View reference standards', 'standards:manage': 'Register standards and their certificates', 'standards:exception': 'Authorize use of an expired or restricted standard (documented exception)', 'competency:read': 'View personnel profiles, competency matrix and authorizations', 'competency:manage': 'Manage personnel profiles, competencies, training and evaluations', 'competency:authorize': 'Grant and revoke activity authorizations'}
NEW_ROLES = {}
GRANTS = {'org_admin': ['standards:read', 'standards:manage', 'standards:exception', 'competency:read', 'competency:manage', 'competency:authorize'], 'metrology_manager': ['standards:read', 'competency:read', 'standards:manage', 'standards:exception', 'competency:manage', 'competency:authorize'], 'metrology_technician': ['standards:read', 'competency:read'], 'lab_technician': ['standards:read', 'competency:read'], 'auditor': ['standards:read', 'competency:read'], 'viewer': ['standards:read']}


def upgrade() -> None:
    op.create_table('competencies',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=True),
    sa.Column('validity_months', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_competencies_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_competencies')),
    sa.UniqueConstraint('organization_id', 'code', name=op.f('uq_competencies_organization_id_code'))
    )
    op.create_index(op.f('ix_competencies_organization_id'), 'competencies', ['organization_id'], unique=False)
    op.create_table('competency_records',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('competency_id', sa.Uuid(), nullable=False),
    sa.Column('record_type', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('provider', sa.String(length=200), nullable=True),
    sa.Column('completed_on', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('result', sa.String(length=20), nullable=False),
    sa.Column('score', sa.String(length=40), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('recorded_by', sa.Uuid(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("record_type IN ('TRAINING', 'EVALUATION', 'CERTIFICATION')", name=op.f('ck_competency_records_record_type_valid')),
    sa.CheckConstraint("result IN ('PASSED', 'FAILED', 'NOT_APPLICABLE')", name=op.f('ck_competency_records_result_valid')),
    sa.CheckConstraint('valid_until IS NULL OR valid_until >= completed_on', name=op.f('ck_competency_records_validity_after_completion')),
    sa.ForeignKeyConstraint(['competency_id'], ['competencies.id'], name=op.f('fk_competency_records_competency_id_competencies'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_competency_records_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], name=op.f('fk_competency_records_recorded_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_competency_records_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_competency_records'))
    )
    op.create_index('ix_competency_records_user', 'competency_records', ['organization_id', 'user_id'], unique=False)
    op.create_table('standards',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('standard_code', sa.String(length=50), nullable=False),
    sa.Column('description', sa.String(length=300), nullable=False),
    sa.Column('category', sa.String(length=30), nullable=False),
    sa.Column('subtype', sa.String(length=120), nullable=True),
    sa.Column('manufacturer', sa.String(length=120), nullable=True),
    sa.Column('model', sa.String(length=120), nullable=True),
    sa.Column('serial_number', sa.String(length=120), nullable=True),
    sa.Column('range_min', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('range_max', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('unit', sa.String(length=20), nullable=True),
    sa.Column('resolution', sa.Numeric(precision=18, scale=6), nullable=True),
    sa.Column('accuracy', sa.String(length=120), nullable=True),
    sa.Column('location', sa.String(length=200), nullable=True),
    sa.Column('custodian_user_id', sa.Uuid(), nullable=True),
    sa.Column('calibration_frequency_days', sa.Integer(), nullable=False),
    sa.Column('last_calibration_date', sa.Date(), nullable=True),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('current_certificate_id', sa.Uuid(), nullable=True),
    sa.Column('control_status', sa.String(length=20), server_default='ACTIVE', nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("category IN ('GAUGE_BLOCK', 'REFERENCE_STANDARD', 'MASTER_PART', 'SETTING_MASTER', 'REFERENCE_INSTRUMENT', 'TEMPERATURE', 'PRESSURE', 'OTHER')", name=op.f('ck_standards_category_valid')),
    sa.CheckConstraint("control_status IN ('ACTIVE','RESTRICTED','INACTIVE')", name=op.f('ck_standards_control_status_valid')),
    sa.CheckConstraint('calibration_frequency_days > 0', name=op.f('ck_standards_frequency_positive')),
    sa.CheckConstraint('range_min IS NULL OR range_max IS NULL OR range_min <= range_max', name=op.f('ck_standards_range_ordered')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_standards_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['custodian_user_id'], ['users.id'], name=op.f('fk_standards_custodian_user_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_standards_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_standards_plant_id_plants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_standards')),
    sa.UniqueConstraint('organization_id', 'standard_code', name=op.f('uq_standards_organization_id_standard_code'))
    )
    op.create_index(op.f('ix_standards_organization_id'), 'standards', ['organization_id'], unique=False)
    op.create_table('authorizations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('activity', sa.String(length=30), nullable=False),
    sa.Column('gage_type_id', sa.Uuid(), nullable=True),
    sa.Column('plant_id', sa.Uuid(), nullable=True),
    sa.Column('valid_from', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=True),
    sa.Column('basis', sa.String(length=500), nullable=True),
    sa.Column('competency_record_id', sa.Uuid(), nullable=True),
    sa.Column('granted_by', sa.Uuid(), nullable=False),
    sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_by', sa.Uuid(), nullable=True),
    sa.Column('revoke_reason', sa.String(length=500), nullable=True),
    sa.CheckConstraint("activity IN ('INTERNAL_CALIBRATION', 'ROUTINE_VERIFICATION', 'TECHNICAL_REVIEW', 'APPROVAL', 'LAB_SERVICE', 'DIMENSIONAL_INSPECTION', 'MSA_EVALUATION')", name=op.f('ck_authorizations_activity_valid')),
    sa.CheckConstraint('valid_until IS NULL OR valid_until >= valid_from', name=op.f('ck_authorizations_validity_order')),
    sa.ForeignKeyConstraint(['competency_record_id'], ['competency_records.id'], name=op.f('fk_authorizations_competency_record_id_competency_records'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_type_id'], ['gage_types.id'], name=op.f('fk_authorizations_gage_type_id_gage_types'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['granted_by'], ['users.id'], name=op.f('fk_authorizations_granted_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_authorizations_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_authorizations_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], name=op.f('fk_authorizations_revoked_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_authorizations_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_authorizations'))
    )
    op.create_index('ix_authorizations_lookup', 'authorizations', ['organization_id', 'user_id', 'activity'], unique=False)
    op.create_table('personnel_profiles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('employee_number', sa.String(length=40), nullable=True),
    sa.Column('job_title', sa.String(length=120), nullable=True),
    sa.Column('plant_id', sa.Uuid(), nullable=True),
    sa.Column('department_id', sa.Uuid(), nullable=True),
    sa.Column('profile_types', postgresql.ARRAY(sa.String(length=30)), server_default='{}', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_personnel_profiles_department_id_departments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_personnel_profiles_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_personnel_profiles_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_personnel_profiles_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_personnel_profiles')),
    sa.UniqueConstraint('organization_id', 'user_id', name=op.f('uq_personnel_profiles_organization_id_user_id'))
    )
    op.create_index(op.f('ix_personnel_profiles_organization_id'), 'personnel_profiles', ['organization_id'], unique=False)
    op.create_table('standard_certificates',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('standard_id', sa.Uuid(), nullable=False),
    sa.Column('certificate_number', sa.String(length=80), nullable=False),
    sa.Column('issuer', sa.String(length=200), nullable=False),
    sa.Column('accreditation', sa.String(length=120), nullable=True),
    sa.Column('calibration_date', sa.Date(), nullable=False),
    sa.Column('issue_date', sa.Date(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=False),
    sa.Column('uncertainty', sa.String(length=200), nullable=True),
    sa.Column('traceability', sa.String(length=300), nullable=True),
    sa.Column('attachment_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("status IN ('CURRENT','SUPERSEDED')", name=op.f('ck_standard_certificates_status_valid')),
    sa.CheckConstraint('valid_until > calibration_date', name=op.f('ck_standard_certificates_validity_after_calibration')),
    sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], name=op.f('fk_standard_certificates_attachment_id_attachments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_standard_certificates_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_standard_certificates_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['standard_id'], ['standards.id'], name=op.f('fk_standard_certificates_standard_id_standards'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_standard_certificates'))
    )
    op.create_index(op.f('ix_standard_certificates_standard_id'), 'standard_certificates', ['standard_id'], unique=False)
    op.execute("CREATE TRIGGER trg_competency_records_append_only BEFORE UPDATE OR DELETE ON competency_records FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")

    op.create_foreign_key('fk_standards_current_certificate_id_standard_certificates', 'standards',
                          'standard_certificates', ['current_certificate_id'], ['id'], ondelete='RESTRICT')

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
    op.execute("DROP TRIGGER IF EXISTS trg_competency_records_append_only ON competency_records")
    op.drop_constraint('fk_standards_current_certificate_id_standard_certificates', 'standards', type_='foreignkey')
    op.drop_index(op.f('ix_standard_certificates_standard_id'), table_name='standard_certificates')
    op.drop_table('standard_certificates')
    op.drop_index(op.f('ix_personnel_profiles_organization_id'), table_name='personnel_profiles')
    op.drop_table('personnel_profiles')
    op.drop_index('ix_authorizations_lookup', table_name='authorizations')
    op.drop_table('authorizations')
    op.drop_index(op.f('ix_standards_organization_id'), table_name='standards')
    op.drop_table('standards')
    op.drop_index('ix_competency_records_user', table_name='competency_records')
    op.drop_table('competency_records')
    op.drop_index(op.f('ix_competencies_organization_id'), table_name='competencies')
    op.drop_table('competencies')
