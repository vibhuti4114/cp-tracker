"""
Analytics endpoints: aggregated stats, rating history, submissions feed.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_cache, CacheManager
from app.core.security import get_current_user_id, get_optional_user_id
from app.models.models import PlatformAccount, RatingHistory, Submission
from app.schemas.schemas import AnalyticsResponse, RatingHistoryEntry, SubmissionResponse
from app.services.analytics_service import get_user_analytics

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics(
    target_user_id: int | None = Query(None, description="View analytics for this user"),
    current_user_id: int | None = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db),
    cache: CacheManager = Depends(get_cache),
):
    """Return aggregated analytics for target_user_id or current user."""
    user_id = target_user_id or current_user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required or target_user_id needed.")
    return await get_user_analytics(user_id, db, cache)


@router.get("/rating-history", response_model=list[RatingHistoryEntry])
async def get_rating_history(
    platform: str | None = Query(None, description="Filter by platform"),
    account_id: int | None = Query(None, description="Filter by account id"),
    target_user_id: int | None = Query(None, description="View history for this user"),
    current_user_id: int | None = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Return rating change history for target_user_id or current user."""
    user_id = target_user_id or current_user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required or target_user_id needed.")

    query = (
        select(
            RatingHistory.id,
            RatingHistory.account_id,
            RatingHistory.contest_name,
            RatingHistory.contest_id,
            RatingHistory.old_rating,
            RatingHistory.new_rating,
            RatingHistory.rank,
            RatingHistory.participated_at,
            PlatformAccount.platform,
            PlatformAccount.handle,
        )
        .join(PlatformAccount, PlatformAccount.id == RatingHistory.account_id)
        .where(PlatformAccount.user_id == user_id)
        .order_by(RatingHistory.participated_at.desc())
    )
    if platform:
        query = query.where(PlatformAccount.platform == platform)
    if account_id:
        query = query.where(RatingHistory.account_id == account_id)

    result = await db.execute(query)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.get("/submissions", response_model=list[SubmissionResponse])
async def get_submissions(
    platform: str | None = Query(None),
    verdict: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    target_user_id: int | None = Query(None, description="View submissions for this user"),
    current_user_id: int | None = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Paginated submission feed for target_user_id or current user."""
    user_id = target_user_id or current_user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required or target_user_id needed.")

    query = (
        select(Submission)
        .where(Submission.user_id == user_id)
        .order_by(Submission.submitted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if verdict:
        query = query.where(Submission.verdict == verdict.upper())
    if platform:
        query = (
            query.join(PlatformAccount)
            .where(PlatformAccount.platform == platform)
        )

    result = await db.execute(query)
    return result.scalars().all()


@router.delete("/cache", summary="Invalidate analytics cache")
async def bust_cache(
    user_id: int = Depends(get_current_user_id),
    cache: CacheManager = Depends(get_cache),
):
    """Force-expire the analytics cache for the current user."""
    await cache.delete("analytics", str(user_id))
    return {"message": "Analytics cache cleared."}
