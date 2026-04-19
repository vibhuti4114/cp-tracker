"""
Pydantic v2 schemas (request/response models).
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


# ---------------------------------------------------------------------------
# Platform Account
# ---------------------------------------------------------------------------

class PlatformAccountCreateRequest(BaseModel):
    platform: str = Field(..., pattern=r"^(codeforces|leetcode|codechef|atcoder)$")
    handle: str = Field(..., min_length=1, max_length=128)
    is_primary: bool = False


class PlatformAccountResponse(BaseModel):
    id: int
    platform: str
    handle: str
    is_verified: bool
    is_primary: bool
    current_rating: Optional[float]
    max_rating: Optional[float]
    problems_solved: int
    contests_participated: int
    last_synced_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Rating History
# ---------------------------------------------------------------------------

class RatingHistoryEntry(BaseModel):
    id: int
    account_id: int
    contest_name: Optional[str]
    contest_id: Optional[str]
    old_rating: float
    new_rating: float
    rank: Optional[int]
    participated_at: datetime
    # joined from platform_accounts
    platform: Optional[str] = None
    handle: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------

class SubmissionResponse(BaseModel):
    id: int
    platform_submission_id: str
    problem_id: str
    problem_name: str
    problem_url: Optional[str]
    verdict: str
    language: Optional[str]
    difficulty: Optional[str]
    tags: Optional[list]
    submitted_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class PlatformSummary(BaseModel):
    platform: str
    handle: str
    problems_solved: int
    contests_participated: int
    current_rating: Optional[float]
    max_rating: Optional[float]


class TagBreakdown(BaseModel):
    tag: str
    count: int


class DailyActivity(BaseModel):
    date: str   # YYYY-MM-DD
    submissions: int
    solved: int


class AnalyticsResponse(BaseModel):
    user_id: int
    total_problems_solved: int
    total_contests: int
    platforms: list[PlatformSummary]
    tag_breakdown: list[TagBreakdown]
    difficulty_breakdown: dict[str, int]
    daily_activity: list[DailyActivity]
    streak_days: int
    last_updated: datetime


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

class SyncResponse(BaseModel):
    account_id: int
    platform: str
    handle: str
    status: str          # "success" | "failed" | "partial"
    problems_synced: int
    contests_synced: int
    message: str


# ---------------------------------------------------------------------------
# Generic
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    message: str
    detail: Optional[Any] = None


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[Any]
