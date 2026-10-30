"""Security hardening: token versioning (session revocation), password reset tokens, encrypted webhook secrets.

Revision ID: 0011_security
Revises: 0010_integrations
Create Date: 2026-10-30
"""
import sqlalchemy as sa
from alembic import op

revision = "0011_security"
down_revision = "0010_integrations"
branch_labels = None
depends_on = None


def _secrets(transform) -> None:
    from app.core import crypto  # uses SECRET_ENCRYPTION_KEY / JWT_SECRET of the running environment

    conn = op.get_bind()
    for row_id, secret in conn.execute(sa.text("SELECT id, secret FROM webhook_endpoints")).all():
        conn.execute(sa.text("UPDATE webhook_endpoints SET secret = :s WHERE id = :i"),
                     {"s": transform(crypto, secret), "i": row_id})


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_password_reset_tokens_created_by_users"),
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_password_reset_tokens_user_id_users"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(op.f("ix_password_reset_tokens_user_id"), "password_reset_tokens", ["user_id"], unique=False)
    op.add_column("users", sa.Column("token_version", sa.Integer(), server_default="0", nullable=False))
    op.alter_column("webhook_endpoints", "secret", existing_type=sa.VARCHAR(length=100), type_=sa.String(length=300),
                    existing_nullable=False)
    _secrets(lambda c, s: s if s.startswith(c.PREFIX) else c.encrypt(s))


def downgrade() -> None:
    _secrets(lambda c, s: c.decrypt(s))
    op.alter_column("webhook_endpoints", "secret", existing_type=sa.String(length=300), type_=sa.VARCHAR(length=100),
                    existing_nullable=False)
    op.drop_column("users", "token_version")
    op.drop_index(op.f("ix_password_reset_tokens_user_id"), table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
