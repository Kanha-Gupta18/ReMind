"""replace single patient links with revocable access grants

Revision ID: 7b31d9f45a20
Revises: 3987ffa7601b
Create Date: 2026-09-08
"""

from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "7b31d9f45a20"
down_revision: Union[str, Sequence[str], None] = "3987ffa7601b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("patient_id", sa.String(), nullable=True))
    op.add_column("notifications", sa.Column("required_action", sa.String(), nullable=True))
    op.create_foreign_key(
        "notifications_patient_id_fkey",
        "notifications",
        "users",
        ["patient_id"],
        ["id"],
    )
    op.add_column("patient_profiles", sa.Column("preferred_name", sa.String(), nullable=True))
    op.add_column(
        "patient_profiles",
        sa.Column("preferred_language", sa.String(), server_default="en", nullable=False),
    )
    op.add_column(
        "patient_profiles",
        sa.Column("accessibility_profile", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
    )
    op.add_column(
        "patient_profiles",
        sa.Column("status", sa.String(), server_default="active", nullable=False),
    )
    op.execute(sa.text("""
        UPDATE patient_profiles AS profile
        SET preferred_name = users.full_name
        FROM users
        WHERE users.id = profile.user_id
    """))
    op.alter_column("patient_profiles", "preferred_name", nullable=False)
    op.create_unique_constraint(
        "uq_patient_profiles_user_id",
        "patient_profiles",
        ["user_id"],
    )

    op.add_column(
        "consent_directives",
        sa.Column("signed_by_user_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "consent_directives_signed_by_user_id_fkey",
        "consent_directives",
        "users",
        ["signed_by_user_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_consent_directive_patient_version",
        "consent_directives",
        ["patient_id", "version"],
    )
    op.drop_column("consent_directives", "updated_at")
    op.execute(sa.text("""
        UPDATE consent_directives
        SET post_death_policy = '{"mode": "keep_private"}'::json
        WHERE post_death_policy IS NULL
    """))
    op.alter_column("consent_directives", "post_death_policy", nullable=False)

    op.create_table(
        "patient_access_grants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("patient_id", sa.String(), nullable=False),
        sa.Column("relationship", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("granted_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "patient_id",
            name="uq_patient_access_grant_user_patient",
        ),
    )
    op.create_index(
        op.f("ix_patient_access_grants_patient_id"),
        "patient_access_grants",
        ["patient_id"],
    )
    op.create_index(
        op.f("ix_patient_access_grants_user_id"),
        "patient_access_grants",
        ["user_id"],
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_auth_sessions_user_id"),
        "auth_sessions",
        ["user_id"],
    )

    connection = op.get_bind()
    legacy_links = connection.execute(sa.text(
        "SELECT id, patient_id, role FROM users WHERE patient_id IS NOT NULL"
    )).mappings()
    grants = sa.table(
        "patient_access_grants",
        sa.column("id", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("patient_id", sa.String()),
        sa.column("relationship", sa.String()),
        sa.column("status", sa.String()),
    )
    for link in legacy_links:
        connection.execute(grants.insert().values(
            id=str(uuid4()),
            user_id=link["id"],
            patient_id=link["patient_id"],
            relationship=link["role"],
            status="active",
        ))

    op.drop_constraint("users_patient_id_fkey", "users", type_="foreignkey")
    op.drop_column("users", "patient_id")


def downgrade() -> None:
    op.drop_constraint("notifications_patient_id_fkey", "notifications", type_="foreignkey")
    op.drop_column("notifications", "required_action")
    op.drop_column("notifications", "patient_id")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.add_column("users", sa.Column("patient_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "users_patient_id_fkey",
        "users",
        "users",
        ["patient_id"],
        ["id"],
    )
    op.execute(sa.text("""
        UPDATE users AS account
        SET patient_id = selected.patient_id
        FROM (
            SELECT DISTINCT ON (user_id) user_id, patient_id
            FROM patient_access_grants
            WHERE status = 'active'
            ORDER BY user_id, created_at
        ) AS selected
        WHERE account.id = selected.user_id
    """))
    op.drop_index(
        op.f("ix_patient_access_grants_user_id"),
        table_name="patient_access_grants",
    )
    op.drop_index(
        op.f("ix_patient_access_grants_patient_id"),
        table_name="patient_access_grants",
    )
    op.drop_table("patient_access_grants")
    op.add_column(
        "consent_directives",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("consent_directives", "post_death_policy", nullable=True)
    op.drop_constraint(
        "uq_consent_directive_patient_version",
        "consent_directives",
        type_="unique",
    )
    op.drop_constraint(
        "consent_directives_signed_by_user_id_fkey",
        "consent_directives",
        type_="foreignkey",
    )
    op.drop_column("consent_directives", "signed_by_user_id")
    op.drop_constraint("uq_patient_profiles_user_id", "patient_profiles", type_="unique")
    op.drop_column("patient_profiles", "status")
    op.drop_column("patient_profiles", "accessibility_profile")
    op.drop_column("patient_profiles", "preferred_language")
    op.drop_column("patient_profiles", "preferred_name")
