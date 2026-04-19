"""
Analytics service: compute aggregated stats across all platform accounts.
Results are cached in Redis.
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import CacheManager
from app.models.models import PlatformAccount, Submission
from app.schemas.schemas import (
    AnalyticsResponse, DailyActivity, PlatformSummary, TagBreakdown
)

logger = logging.getLogger(__name__)
ANALYTICS_TTL = 1800  # 30 minutes


async def get_user_analytics(
    user_id: int,
    db: AsyncSession,
    cache: CacheManager,
) -> AnalyticsResponse:
    """
    Return aggregated analytics for a user.
    Served from Redis if fresh; otherwise recomputed from DB.
    """
    # Try cache first
    cached = await cache.get("analytics", str(user_id))
    if cached:
        return AnalyticsResponse(**cached)

    analytics = await _compute_analytics(user_id, db)

    # Store in cache
    await cache.set("analytics", str(user_id), analytics.model_dump(mode="json"), ANALYTICS_TTL)

    return analytics


async def _compute_analytics(user_id: int, db: AsyncSession) -> AnalyticsResponse:
    # --- Platform summaries -------------------------------------------
    accounts_result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.user_id == user_id)
    )
    accounts: list[PlatformAccount] = accounts_result.scalars().all()

    platform_summaries = [
        PlatformSummary(
            platform=a.platform,
            handle=a.handle,
            problems_solved=a.problems_solved,
            contests_participated=a.contests_participated,
            current_rating=a.current_rating,
            max_rating=a.max_rating,
        )
        for a in accounts
    ]

    total_problems = sum(p.problems_solved for p in platform_summaries)
    total_contests = sum(p.contests_participated for p in platform_summaries)

    # --- Submissions analysis -----------------------------------------
    subs_result = await db.execute(
        select(Submission).where(Submission.user_id == user_id)
    )
    submissions: list[Submission] = subs_result.scalars().all()

    tag_counts: dict[str, int] = defaultdict(int)
    difficulty_counts: dict[str, int] = defaultdict(int)
    daily: dict[str, dict] = defaultdict(lambda: {"submissions": 0, "solved": 0})

    for s in submissions:
        for tag in (s.tags or []):
            tag_counts[tag] += 1
        if s.difficulty:
            difficulty_counts[s.difficulty] += 1
        day_key = s.submitted_at.strftime("%Y-%m-%d")
        daily[day_key]["submissions"] += 1
        if s.verdict in ("AC", "Accepted", "OK"):
            daily[day_key]["solved"] += 1

    tag_breakdown = [
        TagBreakdown(tag=t, count=c)
        for t, c in sorted(tag_counts.items(), key=lambda x: -x[1])
    ]

    daily_activity = [
        DailyActivity(date=d, **v)
        for d, v in sorted(daily.items(), reverse=True)[:90]  # last 90 days
    ]

    streak_days = _compute_streak(daily)

    return AnalyticsResponse(
        user_id=user_id,
        total_problems_solved=total_problems,
        total_contests=total_contests,
        platforms=platform_summaries,
        tag_breakdown=tag_breakdown,
        difficulty_breakdown=dict(difficulty_counts),
        daily_activity=daily_activity,
        streak_days=streak_days,
        last_updated=datetime.now(timezone.utc),
    )


def _compute_streak(daily: dict) -> int:
    """Count consecutive active days ending today or yesterday."""
    from datetime import date, timedelta
    today = date.today()
    streak = 0
    current = today
    while True:
        key = current.strftime("%Y-%m-%d")
        if key in daily and daily[key]["solved"] > 0:
            streak += 1
            current -= timedelta(days=1)
        else:
            # Allow one missed day (yesterday) before breaking
            if current == today:
                current -= timedelta(days=1)
                continue
            break
    return streak
