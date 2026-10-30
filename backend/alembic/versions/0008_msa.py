"""MSA Management: studies, raw observations, calculation runs, acceptance criteria and reports.

Revision ID: 0008_msa
Revises: 0007_configuration
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_msa"
down_revision = "0007_configuration"
branch_labels = None
depends_on = None

FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION protect_criteria_set() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND (to_jsonb(NEW) - 'status' - 'approved_by' - 'approved_at' - 'retired_at' - 'retired_reason')
         = (to_jsonb(OLD) - 'status' - 'approved_by' - 'approved_at' - 'retired_at' - 'retired_reason') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'acceptance criteria are versioned: create a new version instead (attempted %)', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;
"""

# Frozen copy of the permissions, roles and grants introduced by this revision.
PERMISSIONS = {'msa:read': 'View MSA studies, runs and reports', 'msa:manage': 'Create and configure MSA studies; capture and import study data', 'msa:calculate': 'Run MSA statistical calculations', 'msa:approve': 'Review and approve MSA studies; approve acceptance criteria', 'msa:criteria': 'Define MSA acceptance criteria'}
NEW_ROLES = {}
GRANTS = {'org_admin': ['msa:read', 'msa:manage', 'msa:calculate', 'msa:approve', 'msa:criteria'], 'metrology_manager': ['msa:read', 'msa:manage', 'msa:calculate', 'msa:approve', 'msa:criteria'], 'metrology_technician': ['msa:read', 'msa:manage', 'msa:calculate'], 'lab_technician': ['msa:read'], 'auditor': ['msa:read'], 'viewer': ['msa:read']}


def upgrade() -> None:
    op.create_table('msa_criteria_sets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('method', sa.String(length=30), nullable=False),
    sa.Column('scope', sa.String(length=15), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=True),
    sa.Column('customer', sa.String(length=200), nullable=True),
    sa.Column('rules', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source', sa.String(length=500), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('approved_by', sa.Uuid(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('retired_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('retired_reason', sa.String(length=500), nullable=True),
    sa.CheckConstraint("method IN ('GRR_CROSSED_AR', 'GRR_CROSSED_ANOVA', 'GRR_NESTED_ANOVA', 'ATTRIBUTE_AGREEMENT', 'BIAS', 'LINEARITY', 'STABILITY', 'TYPE1')", name=op.f('ck_msa_criteria_sets_method_valid')),
    sa.CheckConstraint("scope IN ('ORGANIZATION', 'PLANT', 'CUSTOMER')", name=op.f('ck_msa_criteria_sets_scope_valid')),
    sa.CheckConstraint("status IN ('DRAFT', 'APPROVED', 'RETIRED')", name=op.f('ck_msa_criteria_sets_status_valid')),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name=op.f('fk_msa_criteria_sets_approved_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_msa_criteria_sets_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_msa_criteria_sets_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_msa_criteria_sets_plant_id_plants'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_msa_criteria_sets')),
    sa.UniqueConstraint('organization_id', 'name', 'version', name=op.f('uq_msa_criteria_sets_organization_id_name_version'))
    )
    op.create_index(op.f('ix_msa_criteria_sets_organization_id'), 'msa_criteria_sets', ['organization_id'], unique=False)
    op.create_table('msa_studies',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('department_id', sa.Uuid(), nullable=True),
    sa.Column('study_code', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('method', sa.String(length=30), nullable=False),
    sa.Column('characteristic', sa.String(length=200), nullable=False),
    sa.Column('part_number', sa.String(length=80), nullable=True),
    sa.Column('part_revision', sa.String(length=20), nullable=True),
    sa.Column('customer', sa.String(length=200), nullable=True),
    sa.Column('gage_id', sa.Uuid(), nullable=False),
    sa.Column('responsible_id', sa.Uuid(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=40), nullable=False),
    sa.Column('workflow_version', sa.Integer(), nullable=False),
    sa.Column('design', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('criteria_set_id', sa.Uuid(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('final_decision', sa.String(length=20), nullable=True),
    sa.Column('final_comment', sa.String(length=2000), nullable=True),
    sa.Column('concluded_by', sa.Uuid(), nullable=True),
    sa.Column('concluded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("method IN ('GRR_CROSSED_AR', 'GRR_CROSSED_ANOVA', 'GRR_NESTED_ANOVA', 'ATTRIBUTE_AGREEMENT', 'BIAS', 'LINEARITY', 'STABILITY', 'TYPE1')", name=op.f('ck_msa_studies_method_valid')),
    sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name=op.f('ck_msa_studies_dates_ordered')),
    sa.ForeignKeyConstraint(['concluded_by'], ['users.id'], name=op.f('fk_msa_studies_concluded_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_msa_studies_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['criteria_set_id'], ['msa_criteria_sets.id'], name=op.f('fk_msa_studies_criteria_set_id_msa_criteria_sets'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_msa_studies_department_id_departments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_msa_studies_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_msa_studies_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_msa_studies_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['responsible_id'], ['users.id'], name=op.f('fk_msa_studies_responsible_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_msa_studies')),
    sa.UniqueConstraint('organization_id', 'study_code', name=op.f('uq_msa_studies_organization_id_study_code'))
    )
    op.create_index('ix_msa_studies_gage', 'msa_studies', ['gage_id'], unique=False)
    op.create_index(op.f('ix_msa_studies_organization_id'), 'msa_studies', ['organization_id'], unique=False)
    op.create_table('msa_observations',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('study_id', sa.Uuid(), nullable=False),
    sa.Column('operator', sa.String(length=60), nullable=True),
    sa.Column('part', sa.String(length=60), nullable=True),
    sa.Column('trial', sa.Integer(), nullable=True),
    sa.Column('subgroup', sa.Integer(), nullable=True),
    sa.Column('value', sa.Numeric(precision=24, scale=10), nullable=True),
    sa.Column('category', sa.String(length=60), nullable=True),
    sa.Column('reference', sa.Numeric(precision=24, scale=10), nullable=True),
    sa.Column('measured_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('source', sa.String(length=10), nullable=False),
    sa.Column('import_job_id', sa.Uuid(), nullable=True),
    sa.Column('device_reading_id', sa.Uuid(), nullable=True),
    sa.Column('supersedes_id', sa.Uuid(), nullable=True),
    sa.Column('superseded', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('correction_reason', sa.String(length=500), nullable=True),
    sa.Column('recorded_by', sa.Uuid(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("source IN ('MANUAL', 'IMPORT', 'DEVICE')", name=op.f('ck_msa_observations_source_valid')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_msa_observations_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], name=op.f('fk_msa_observations_recorded_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['study_id'], ['msa_studies.id'], name=op.f('fk_msa_observations_study_id_msa_studies'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['supersedes_id'], ['msa_observations.id'], name=op.f('fk_msa_observations_supersedes_id_msa_observations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_msa_observations'))
    )
    op.create_index('ix_msa_observations_study', 'msa_observations', ['study_id'], unique=False)
    op.create_table('msa_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('study_id', sa.Uuid(), nullable=False),
    sa.Column('run_number', sa.Integer(), nullable=False),
    sa.Column('method', sa.String(length=30), nullable=False),
    sa.Column('algorithm_version', sa.String(length=20), nullable=False),
    sa.Column('engine_version', sa.String(length=20), nullable=False),
    sa.Column('validation_status', sa.String(length=20), nullable=False),
    sa.Column('input_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('input_hash', sa.String(length=64), nullable=False),
    sa.Column('results', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('criteria_set_id', sa.Uuid(), nullable=True),
    sa.Column('criteria_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('evaluation', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('decision', sa.String(length=20), nullable=False),
    sa.Column('gage_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('calculated_by', sa.Uuid(), nullable=False),
    sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.CheckConstraint("decision IN ('ACCEPTABLE', 'CONDITIONAL', 'NOT_ACCEPTABLE', 'INCONCLUSIVE', 'NO_CRITERIA')", name=op.f('ck_msa_runs_decision_valid')),
    sa.ForeignKeyConstraint(['calculated_by'], ['users.id'], name=op.f('fk_msa_runs_calculated_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['criteria_set_id'], ['msa_criteria_sets.id'], name=op.f('fk_msa_runs_criteria_set_id_msa_criteria_sets'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_msa_runs_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['study_id'], ['msa_studies.id'], name=op.f('fk_msa_runs_study_id_msa_studies'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_msa_runs')),
    sa.UniqueConstraint('study_id', 'run_number', name=op.f('uq_msa_runs_study_id_run_number'))
    )
    op.create_index(op.f('ix_msa_runs_study_id'), 'msa_runs', ['study_id'], unique=False)
    op.create_table('msa_reports',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('study_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('attachment_id', sa.Uuid(), nullable=False),
    sa.Column('issued_by', sa.Uuid(), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], name=op.f('fk_msa_reports_attachment_id_attachments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['issued_by'], ['users.id'], name=op.f('fk_msa_reports_issued_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_msa_reports_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['run_id'], ['msa_runs.id'], name=op.f('fk_msa_reports_run_id_msa_runs'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['study_id'], ['msa_studies.id'], name=op.f('fk_msa_reports_study_id_msa_studies'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_msa_reports')),
    sa.UniqueConstraint('study_id', 'revision', name=op.f('uq_msa_reports_study_id_revision'))
    )
    op.create_index(op.f('ix_msa_reports_study_id'), 'msa_reports', ['study_id'], unique=False)
    op.execute(FUNCTION_SQL)
    op.execute("CREATE TRIGGER trg_msa_observations_protect BEFORE UPDATE OR DELETE ON msa_observations FOR EACH ROW EXECUTE FUNCTION protect_measurement_row()")
    op.execute("CREATE TRIGGER trg_msa_runs_append_only BEFORE UPDATE OR DELETE ON msa_runs FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")
    op.execute("CREATE TRIGGER trg_msa_reports_append_only BEFORE UPDATE OR DELETE ON msa_reports FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")
    op.execute("CREATE TRIGGER trg_msa_criteria_sets_criteria BEFORE UPDATE OR DELETE ON msa_criteria_sets FOR EACH ROW EXECUTE FUNCTION protect_criteria_set()")

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
    op.execute("DROP TRIGGER IF EXISTS trg_msa_observations_protect ON msa_observations")
    op.execute("DROP TRIGGER IF EXISTS trg_msa_runs_append_only ON msa_runs")
    op.execute("DROP TRIGGER IF EXISTS trg_msa_reports_append_only ON msa_reports")
    op.execute("DROP TRIGGER IF EXISTS trg_msa_criteria_sets_criteria ON msa_criteria_sets")
    op.drop_index(op.f('ix_msa_reports_study_id'), table_name='msa_reports')
    op.drop_table('msa_reports')
    op.drop_index(op.f('ix_msa_runs_study_id'), table_name='msa_runs')
    op.drop_table('msa_runs')
    op.drop_index('ix_msa_observations_study', table_name='msa_observations')
    op.drop_table('msa_observations')
    op.drop_index(op.f('ix_msa_studies_organization_id'), table_name='msa_studies')
    op.drop_index('ix_msa_studies_gage', table_name='msa_studies')
    op.drop_table('msa_studies')
    op.drop_index(op.f('ix_msa_criteria_sets_organization_id'), table_name='msa_criteria_sets')
    op.drop_table('msa_criteria_sets')
    op.execute("DROP FUNCTION IF EXISTS protect_criteria_set()")
