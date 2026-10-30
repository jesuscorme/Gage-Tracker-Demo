"""Gage Management completion: documents, code sequences, gage dates and movement history.

Revision ID: 0003_gage_completion
Revises: 0002_gage_management
Create Date: 2026-10-29
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_gage_completion"
down_revision = "0002_gage_management"
branch_labels = None
depends_on = None

# Frozen copy of the permissions, roles and grants introduced by this revision.
PERMISSIONS = {'gages:transfer': 'Reassign responsible and transfer gages between plants, departments or locations', 'gages:import': 'Import gage inventory from CSV/Excel'}
NEW_ROLES = {'lab_technician': 'Laboratory Technician', 'requester': 'Laboratory Requester'}
GRANTS = {'org_admin': ['gages:transfer', 'gages:import'], 'metrology_manager': ['gages:transfer', 'gages:import'], 'lab_technician': ['organization:read', 'users:read', 'gages:read'], 'requester': ['organization:read', 'gages:read']}


def upgrade() -> None:
    op.create_table('attachments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('storage_key', sa.String(length=200), nullable=False),
    sa.Column('is_locked', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('uploaded_by', sa.Uuid(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.Column('removed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('removed_by', sa.Uuid(), nullable=True),
    sa.Column('removal_reason', sa.String(length=500), nullable=True),
    sa.CheckConstraint("category IN ('PHOTO', 'DOCUMENT', 'CERTIFICATE', 'EVIDENCE', 'REPORT')", name=op.f('ck_attachments_category_valid')),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_attachments_organization_id_organizations'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['removed_by'], ['users.id'], name=op.f('fk_attachments_removed_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], name=op.f('fk_attachments_uploaded_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attachments')),
    sa.UniqueConstraint('storage_key', name=op.f('uq_attachments_storage_key'))
    )
    op.create_index('ix_attachments_entity', 'attachments', ['organization_id', 'entity_type', 'entity_id'], unique=False)
    op.create_table('code_sequences',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('prefix', sa.String(length=10), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('last_value', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_code_sequences_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_code_sequences')),
    sa.UniqueConstraint('organization_id', 'prefix', 'year', name=op.f('uq_code_sequences_organization_id_prefix_year'))
    )
    op.create_table('gage_movements',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('gage_id', sa.Uuid(), nullable=False),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('reason', sa.String(length=1000), nullable=False),
    sa.Column('moved_by', sa.Uuid(), nullable=False),
    sa.Column('moved_at', sa.DateTime(timezone=True), server_default=sa.text('clock_timestamp()'), nullable=False),
    sa.ForeignKeyConstraint(['gage_id'], ['gages.id'], name=op.f('fk_gage_movements_gage_id_gages'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['moved_by'], ['users.id'], name=op.f('fk_gage_movements_moved_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], name=op.f('fk_gage_movements_organization_id_organizations'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_gage_movements'))
    )
    op.create_index(op.f('ix_gage_movements_gage_id'), 'gage_movements', ['gage_id'], unique=False)
    op.add_column('gages', sa.Column('acquisition_date', sa.Date(), nullable=True))
    op.add_column('gages', sa.Column('in_service_date', sa.Date(), nullable=True))
    op.add_column('gages', sa.Column('last_verification_date', sa.Date(), nullable=True))
    op.execute("CREATE TRIGGER trg_gage_movements_append_only BEFORE UPDATE OR DELETE ON gage_movements FOR EACH ROW EXECUTE FUNCTION forbid_append_only_change()")

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
    op.execute("DROP TRIGGER IF EXISTS trg_gage_movements_append_only ON gage_movements")
    op.drop_column('gages', 'last_verification_date')
    op.drop_column('gages', 'in_service_date')
    op.drop_column('gages', 'acquisition_date')
    op.drop_index(op.f('ix_gage_movements_gage_id'), table_name='gage_movements')
    op.drop_table('gage_movements')
    op.drop_table('code_sequences')
    op.drop_index('ix_attachments_entity', table_name='attachments')
    op.drop_table('attachments')
