"""
Sync service: orchestrates fetching data from external platforms
and persisting it to the database + cache.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import CacheManager
from app.models.models import PlatformAccount, RatingHistory, Submission
from app.schemas.schemas import SyncResponse
from app.services.platform_fetchers import get_fetcher, PlatformFetchError

logger = logging.getLogger(__name__)


async def sync_account(
    account: PlatformAccount,
    db: AsyncSession,
    cache: CacheManager,
) -> SyncResponse:
    """
    Full sync for a single PlatformAccount:
      1. Fetch user info (rating, problems solved, etc.)
      2. Fetch rating history
      3. Fetch recent submissions
      4. Persist to DB
      5. Update Redis cache
    Returns a SyncResponse summary.
    """
    fetcher = get_fetcher(account.platform)
    problems_synced = 0
    contests_synced = 0
    status = "success"
    message = "Sync completed successfully."

    try:
        # --- User Info ---------------------------------------------------
        info = await fetcher.fetch_user_info(account.handle)
        account.current_rating = info.get("current_rating")
        account.max_rating = info.get("max_rating")
        account.problems_solved = info.get("problems_solved", account.problems_solved)
        account.last_synced_at = datetime.now(timezone.utc)

        # --- Rating History ----------------------------------------------
        history = await fetcher.fetch_rating_history(account.handle)
        contests_synced = len(history)
        account.contests_participated = contests_synced

        # Replace existing history for this account
        await db.execute(
            delete(RatingHistory).where(RatingHistory.account_id == account.id)
        )
        for entry in history:
            db.add(RatingHistory(account_id=account.id, **entry))

        # --- Submissions -------------------------------------------------
        submissions_raw = await fetcher.fetch_submissions(account.handle)

        # Fetch existing submission IDs to avoid duplicates
        existing_ids_result = await db.execute(
            select(Submission.platform_submission_id).where(
                Submission.account_id == account.id
            )
        )
        existing_ids = {row[0] for row in existing_ids_result.fetchall()}

        ac_problem_ids = set()
        for s in submissions_raw:
            if s["platform_submission_id"] in existing_ids:
                continue
            sub = Submission(
                user_id=account.user_id,
                account_id=account.id,
                **{k: v for k, v in s.items() if k != "difficulty"},
                difficulty=None,
            )
            db.add(sub)
            problems_synced += 1
            if s["verdict"] in ("AC", "Accepted", "OK"):
                ac_problem_ids.add(s["problem_id"])

        # Update problems_solved from AC count if platform didn't return it
        if not info.get("problems_solved") and ac_problem_ids:
            account.problems_solved += len(ac_problem_ids)

        await db.flush()

        # --- Cache -------------------------------------------------------
        await cache.set_platform_stats(
            account.user_id,
            account.platform,
            {
                "handle": account.handle,
                "current_rating": account.current_rating,
                "max_rating": account.max_rating,
                "problems_solved": account.problems_solved,
                "contests_participated": account.contests_participated,
                "last_synced_at": account.last_synced_at.isoformat(),
            },
        )
        # Bust aggregated analytics cache
        await cache.delete("analytics", str(account.user_id))

    except PlatformFetchError as exc:
        logger.warning("Sync failed for %s/%s: %s", account.platform, account.handle, exc)
        status = "failed"
        message = str(exc)
        await db.rollback()

    return SyncResponse(
        account_id=account.id,
        platform=account.platform,
        handle=account.handle,
        status=status,
        problems_synced=problems_synced,
        contests_synced=contests_synced,
        message=message,
    )
