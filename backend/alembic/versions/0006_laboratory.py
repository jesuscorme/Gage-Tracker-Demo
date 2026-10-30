"""Laboratory Operations.

Revision ID: 0006_laboratory
Revises: 0005_calibration
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_laboratory"
down_revision = "0005_calibration"
branch_labels = None
depends_on = None

# Frozen copy of the permissions, roles and grants introduced by this revision.
PERMISSIONS = {'lab:read': 'View laboratory requests, work orders and reports', 'lab:request': 'Create laboratory service requests', 'lab:manage': 'Review requests, create and schedule work orders, manage services and capacity', 'lab:execute': 'Execute work orders and capture measurements', 'lab:report': 'Issue measurement reports'}
NEW_ROLES = {}
GRANTS = {'org_admin': ['lab:read', 'lab:request', 'lab:manage', 'lab:execute', 'lab:report'], 'metrology_manager': ['lab:read', 'lab:request', 'lab:manage', 'lab:execute', 'lab:report'], 'metrology_technician': ['lab:read', 'lab:execute'], 'lab_technician': ['lab:read', 'lab:execute'], 'requester': ['lab:read', 'lab:request'], 'auditor': ['lab:read'], 'viewer': ['lab:read']}


def upgrade() -> None:
    op.create_table('lab_services',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=True),
    sa.Column('standard_hours', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('required_activity', sa.String(length=30), nullable=False),
    sa.Column('requires_inspection', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_lab_services_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lab_services')),
    sa.UniqueConstraint('organization_id', 'code', name=op.f('uq_lab_services_organization_id_code'))
    )
    op.create_index(op.f('ix_lab_services_organization_id'), 'lab_services', ['organization_id'], unique=False)
    op.create_table('lab_settings',
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('hours_per_technician_day', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('working_days', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_lab_settings_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('organization_id', name=op.f('pk_lab_settings'))
    )
    op.create_table('technician_absences',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('reason', sa.String(length=200), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('end_date >= start_date', name=op.f('ck_technician_absences_dates_ordered')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_technician_absences_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_technician_absences_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_technician_absences_user_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_technician_absences'))
    )
    op.create_index(op.f('ix_technician_absences_organization_id'), 'technician_absences', ['organization_id'], unique=False)
    op.create_table('service_requests',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('department_id', sa.Uuid(), nullable=True),
    sa.Column('request_code', sa.String(length=30), nullable=False),
    sa.Column('requester_id', sa.Uuid(), nullable=False),
    sa.Column('customer_type', sa.String(length=10), nullable=False),
    sa.Column('customer_name', sa.String(length=200), nullable=True),
    sa.Column('service_id', sa.Uuid(), nullable=False),
    sa.Column('part_number', sa.String(length=80), nullable=True),
    sa.Column('part_revision', sa.String(length=20), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=2000), nullable=False),
    sa.Column('priority', sa.String(length=10), nullable=False),
    sa.Column('requested_date', sa.Date(), nullable=False),
    sa.Column('committed_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('decision_by', sa.Uuid(), nullable=True),
    sa.Column('decision_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_comment', sa.String(length=1000), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("customer_type IN ('INTERNAL','EXTERNAL')", name=op.f('ck_service_requests_customer_type_valid')),
    sa.CheckConstraint("priority IN ('LOW', 'NORMAL', 'HIGH', 'URGENT')", name=op.f('ck_service_requests_priority_valid')),
    sa.CheckConstraint("status IN ('SUBMITTED', 'APPROVED', 'REJECTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')", name=op.f('ck_service_requests_status_valid')),
    sa.ForeignKeyConstraint(['decision_by'], ['users.id'], name=op.f('fk_service_requests_decision_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['department_id'], ['departments.id'], name=op.f('fk_service_requests_department_id_departments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_service_requests_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_service_requests_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['requester_id'], ['users.id'], name=op.f('fk_service_requests_requester_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['service_id'], ['lab_services.id'], name=op.f('fk_service_requests_service_id_lab_services'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_service_requests')),
    sa.UniqueConstraint('organization_id', 'request_code', name=op.f('uq_service_requests_organization_id_request_code'))
    )
    op.create_index('ix_service_requests_status', 'service_requests', ['organization_id', 'status'], unique=False)
    op.create_table('work_orders',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('plant_id', sa.Uuid(), nullable=False),
    sa.Column('work_order_code', sa.String(length=30), nullable=False),
    sa.Column('service_request_id', sa.Uuid(), nullable=False),
    sa.Column('service_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('priority', sa.String(length=10), nullable=False),
    sa.Column('planned_hours', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('technician_id', sa.Uuid(), nullable=True),
    sa.Column('scheduled_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('scheduled_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('observations', sa.Text(), nullable=True),
    sa.Column('cancel_reason', sa.String(length=1000), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('PENDING', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')", name=op.f('ck_work_orders_status_valid')),
    sa.CheckConstraint('scheduled_end IS NULL OR scheduled_end > scheduled_start', name=op.f('ck_work_orders_schedule_ordered')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_work_orders_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_work_orders_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plant_id'], ['plants.id'], name=op.f('fk_work_orders_plant_id_plants'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['service_id'], ['lab_services.id'], name=op.f('fk_work_orders_service_id_lab_services'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['service_request_id'], ['service_requests.id'], name=op.f('fk_work_orders_service_request_id_service_requests'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['technician_id'], ['users.id'], name=op.f('fk_work_orders_technician_id_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_work_orders')),
    sa.UniqueConstraint('organization_id', 'work_order_code', name=op.f('uq_work_orders_organization_id_work_order_code'))
    )
    op.create_index(op.f('ix_work_orders_service_request_id'), 'work_orders', ['service_request_id'], unique=False)
    op.create_index('ix_work_orders_tech', 'work_orders', ['organization_id', 'technician_id', 'status'], unique=False)
    op.create_table('inspection_results',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('work_order_id', sa.Uuid(), nullable=False),
    sa.Column('part_number', sa.String(length=80), nullable=False),
    sa.Column('drawing_revision', sa.String(length=20), nullable=True),
    sa.Column('sample_id', sa.String(length=40), nullable=True),
    sa.Column('characteristic_number', sa.String(length=20), nullable=False),
    sa.Column('characteristic', sa.String(length=200), nullable=False),
    sa.Column('nominal', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('lower_limit', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('upper_limit', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('measured', sa.Numeric(precision=18, scale=6), nullable=False),
    sa.Column('unit', sa.String(length=20), nullable=False),
    sa.Column('gage_id', sa.Uuid(), nullable=False),
    sa.Column('gage_status', sa.String(length=20), nullable=False),
    sa.Column('technician_id', sa.Uuid(), nullable=False),
    sa.Column('measured_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('result', sa.String(length=3), nullable=False),
    sa.Column('supersedes_id', sa.Uuid(), nullable=True),
    sa.Column('superseded', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('correction_reason', sa.String(length=500), nullable=True),
    sa.CheckConstraint("result IN ('OK','NOK')", name=op.f('ck_inspection_results_result_valid')),
    sa.CheckConstraint('lower_limit <= upper_limit', name=op.f('ck_inspection_results_limits_ordered')),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_inspection_results_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_inspection_results_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['supersedes_id'], ['inspection_results.id'], name=op.f('fk_inspection_results_supersedes_id_inspection_results'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['technician_id'], ['users.id'], name=op.f('fk_inspection_results_technician_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], name=op.f('fk_inspection_results_work_order_id_work_orders'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inspection_results'))
    )
    op.create_index('ix_inspection_results_wo', 'inspection_results', ['work_order_id'], unique=False)
    op.create_table('measurement_reports',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('work_order_id', sa.Uuid(), nullable=False),
    sa.Column('report_code', sa.String(length=30), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('acceptance', sa.String(length=10), nullable=False),
    sa.Column('snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('observations', sa.Text(), nullable=True),
    sa.Column('revision_reason', sa.String(length=500), nullable=True),
    sa.Column('technician_id', sa.Uuid(), nullable=True),
    sa.Column('reviewer_id', sa.Uuid(), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('attachment_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint("acceptance IN ('ACCEPTED','REJECTED')", name=op.f('ck_measurement_reports_acceptance_valid')),
    sa.CheckConstraint("status IN ('ISSUED','SUPERSEDED')", name=op.f('ck_measurement_reports_status_valid')),
    sa.ForeignKeyConstraint(['attachment_id'], ['attachments.id'], name=op.f('fk_measurement_reports_attachment_id_attachments'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_measurement_reports_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], name=op.f('fk_measurement_reports_reviewer_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['technician_id'], ['users.id'], name=op.f('fk_measurement_reports_technician_id_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], name=op.f('fk_measurement_reports_work_order_id_work_orders'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_measurement_reports')),
    sa.UniqueConstraint('organization_id', 'report_code', 'revision', name=op.f('uq_measurement_reports_organization_id_report_code_revision'))
    )
    op.create_index(op.f('ix_measurement_reports_work_order_id'), 'measurement_reports', ['work_order_id'], unique=False)
    op.create_table('work_order_equipment',
    sa.Column('work_order_id', sa.Uuid(), nullable=False),
    sa.Column('gage_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_work_order_equipment_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], name=op.f('fk_work_order_equipment_work_order_id_work_orders'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('work_order_id', 'gage_id', name=op.f('pk_work_order_equipment'))
    )
    op.create_table('work_order_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('work_order_id', sa.Uuid(), nullable=False),
    sa.Column('from_status', sa.String(length=20), nullable=True),
    sa.Column('to_status', sa.String(length=20), nullable=False),
    sa.Column('comment', sa.String(length=1000), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('changed_by', sa.Uuid(), nullable=False),
    sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['changed_by'], ['users.id'], name=op.f('fk_work_order_events_changed_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_work_order_events_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id'], name=op.f('fk_work_order_events_work_order_id_work_orders'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_work_order_events'))
    )
    op.create_index(op.f('ix_work_order_events_work_order_id'), 'work_order_events', ['work_order_id'], unique=False)
    op.execute("CREATE TRIGGER trg_work_order_events_append_only BEFORE UPDATE OR DELETE ON work_order_events FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")
    op.execute("CREATE TRIGGER trg_inspection_results_protect BEFORE UPDATE OR DELETE ON inspection_results FOR EACH ROW EXECUTE FUNCTION protect_measurement_row()")

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
    op.execute("DROP TRIGGER IF EXISTS trg_work_order_events_append_only ON work_order_events")
    op.execute("DROP TRIGGER IF EXISTS trg_inspection_results_protect ON inspection_results")
    op.drop_index(op.f('ix_work_order_events_work_order_id'), table_name='work_order_events')
    op.drop_table('work_order_events')
    op.drop_table('work_order_equipment')
    op.drop_index(op.f('ix_measurement_reports_work_order_id'), table_name='measurement_reports')
    op.drop_table('measurement_reports')
    op.drop_index('ix_inspection_results_wo', table_name='inspection_results')
    op.drop_table('inspection_results')
    op.drop_index('ix_work_orders_tech', table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_service_request_id'), table_name='work_orders')
    op.drop_table('work_orders')
    op.drop_index('ix_service_requests_status', table_name='service_requests')
    op.drop_table('service_requests')
    op.drop_index(op.f('ix_technician_absences_organization_id'), table_name='technician_absences')
    op.drop_table('technician_absences')
    op.drop_table('lab_settings')
    op.drop_index(op.f('ix_lab_services_organization_id'), table_name='lab_services')
    op.drop_table('lab_services')
