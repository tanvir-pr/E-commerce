"""Week 2: TOTP, recovery codes, password reset, staff invites, phone OTP, deletion."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_week2"
down_revision: str | None = "0001_week1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret_ciphertext", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("totp_pending_ciphertext", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("totp_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column(
        "users",
        "email",
        existing_type=postgresql.CITEXT(),
        nullable=True,
    )
    op.create_index(
        "uq_users_phone_active",
        "users",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_table(
        "recovery_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_recovery_codes_user_id"),
        sa.UniqueConstraint("code_hash", name="uq_recovery_codes_code_hash"),
    )
    op.create_index("ix_recovery_codes_user_id", "recovery_codes", ["user_id"])
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_password_reset_tokens_user_id"
        ),
        sa.UniqueConstraint("token_hash", name="uq_password_reset_tokens_token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_table(
        "staff_invite_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_staff_invite_tokens_user_id"),
        sa.UniqueConstraint("token_hash", name="uq_staff_invite_tokens_token_hash"),
    )
    op.create_index("ix_staff_invite_tokens_user_id", "staff_invite_tokens", ["user_id"])
    op.create_table(
        "phone_otp_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_phone_otp_challenges_phone", "phone_otp_challenges", ["phone"])


def downgrade() -> None:
    op.drop_index("ix_phone_otp_challenges_phone", table_name="phone_otp_challenges")
    op.drop_table("phone_otp_challenges")
    op.drop_index("ix_staff_invite_tokens_user_id", table_name="staff_invite_tokens")
    op.drop_table("staff_invite_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_recovery_codes_user_id", table_name="recovery_codes")
    op.drop_table("recovery_codes")
    op.drop_index("uq_users_phone_active", table_name="users")
    op.execute(
        """
        UPDATE audit_logs SET actor_id = NULL
        WHERE actor_id IN (SELECT id FROM users WHERE email IS NULL)
        """
    )
    op.execute(
        """
        DELETE FROM email_verification_tokens
        WHERE user_id IN (SELECT id FROM users WHERE email IS NULL)
        """
    )
    op.execute(
        """
        UPDATE refresh_tokens SET replaced_by_id = NULL
        WHERE user_id IN (SELECT id FROM users WHERE email IS NULL)
           OR replaced_by_id IN (
                SELECT id FROM refresh_tokens
                WHERE user_id IN (SELECT id FROM users WHERE email IS NULL)
           )
        """
    )
    op.execute(
        """
        DELETE FROM refresh_tokens
        WHERE user_id IN (SELECT id FROM users WHERE email IS NULL)
        """
    )
    op.execute(
        """
        DELETE FROM staff_permissions
        WHERE user_id IN (SELECT id FROM users WHERE email IS NULL)
        """
    )
    op.execute(
        """
        DELETE FROM user_roles
        WHERE user_id IN (SELECT id FROM users WHERE email IS NULL)
        """
    )
    op.execute("DELETE FROM users WHERE email IS NULL")
    op.alter_column(
        "users",
        "email",
        existing_type=postgresql.CITEXT(),
        nullable=False,
    )
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "totp_confirmed_at")
    op.drop_column("users", "totp_pending_ciphertext")
    op.drop_column("users", "totp_secret_ciphertext")
