"""Initial schema — users, platform_accounts, rating_history, submissions

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""

from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Enums -----------------------------------------------------------
    platform_enum = sa.Enum(
        "codeforces", "leetcode", "codechef", "atcoder",
        name="platformenum",
    )
    difficulty_enum = sa.Enum("easy", "medium", "hard", name="difficultyenum")

    # -- users -----------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # -- platform_accounts -----------------------------------------------
    op.create_table(
        "platform_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("handle", sa.String(128), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("current_rating", sa.Float(), nullable=True),
        sa.Column("max_rating", sa.Float(), nullable=True),
        sa.Column("problems_solved", sa.Integer(), server_default="0", nullable=False),
        sa.Column("contests_participated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "platform", "handle", name="uq_user_platform_handle"),
    )
    op.create_index("ix_platform_accounts_user_id", "platform_accounts", ["user_id"])

    # -- rating_history --------------------------------------------------
    op.create_table(
        "rating_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("contest_name", sa.String(255), nullable=True),
        sa.Column("contest_id", sa.String(128), nullable=True),
        sa.Column("old_rating", sa.Float(), nullable=False),
        sa.Column("new_rating", sa.Float(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("participated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["platform_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rating_history_account_id", "rating_history", ["account_id"])

    # -- submissions -----------------------------------------------------
    op.create_table(
        "submissions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("platform_submission_id", sa.String(128), nullable=False),
        sa.Column("problem_id", sa.String(128), nullable=False),
        sa.Column("problem_name", sa.String(255), nullable=False),
        sa.Column("problem_url", sa.String(512), nullable=True),
        sa.Column("verdict", sa.String(64), nullable=False),
        sa.Column("language", sa.String(64), nullable=True),
        sa.Column("difficulty", difficulty_enum, nullable=True),
        sa.Column("tags", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["platform_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "platform_submission_id", name="uq_account_submission"),
    )
    op.create_index("ix_submissions_user_id", "submissions", ["user_id"])
    op.create_index("ix_submissions_submitted_at", "submissions", ["submitted_at"])


def downgrade() -> None:
    op.drop_table("submissions")
    op.drop_table("rating_history")
    op.drop_table("platform_accounts")
    op.drop_table("users")
    sa.Enum(name="difficultyenum").drop(op.get_bind())
    sa.Enum(name="platformenum").drop(op.get_bind())
