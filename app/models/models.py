"""
ORM models for the CP Tracker database.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float,
    ForeignKey, Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlatformEnum(str, enum.Enum):
    codeforces = "codeforces"
    leetcode   = "leetcode"
    codechef   = "codechef"
    atcoder    = "atcoder"


class DifficultyEnum(str, enum.Enum):
    easy   = "easy"
    medium = "medium"
    hard   = "hard"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    platform_accounts: Mapped[list["PlatformAccount"]] = relationship(
        "PlatformAccount", back_populates="user", cascade="all, delete-orphan"
    )
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Platform Account (one user → many handles per platform)
# ---------------------------------------------------------------------------

class PlatformAccount(Base):
    __tablename__ = "platform_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "platform", "handle", name="uq_user_platform_handle"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(Enum(PlatformEnum), nullable=False)
    handle: Mapped[str] = mapped_column(String(128), nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    # Snapshot of the latest fetched stats (denormalized for quick reads)
    current_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    problems_solved: Mapped[int] = mapped_column(Integer, default=0)
    contests_participated: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="platform_accounts")
    rating_history: Mapped[list["RatingHistory"]] = relationship(
        "RatingHistory", back_populates="account", cascade="all, delete-orphan"
    )
    submissions: Mapped[list["Submission"]] = relationship(
        "Submission", back_populates="account", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Rating History
# ---------------------------------------------------------------------------

class RatingHistory(Base):
    __tablename__ = "rating_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    contest_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contest_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    old_rating: Mapped[float] = mapped_column(Float, nullable=False)
    new_rating: Mapped[float] = mapped_column(Float, nullable=False)
    rank: Mapped[str | None] = mapped_column(String(128), nullable=True)
    participated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    account: Mapped["PlatformAccount"] = relationship("PlatformAccount", back_populates="rating_history")


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------

class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("account_id", "platform_submission_id", name="uq_account_submission"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("platform_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    platform_submission_id: Mapped[str] = mapped_column(String(128), nullable=False)
    problem_id: Mapped[str] = mapped_column(String(128), nullable=False)
    problem_name: Mapped[str] = mapped_column(String(255), nullable=False)
    problem_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    verdict: Mapped[str] = mapped_column(String(64), nullable=False)  # AC, WA, TLE, etc.
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(Enum(DifficultyEnum), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    user: Mapped["User"] = relationship("User", back_populates="submissions")
    account: Mapped["PlatformAccount"] = relationship("PlatformAccount", back_populates="submissions")
