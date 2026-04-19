"""
Leaderboard endpoints — powered by Redis Sorted Sets.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_cache, CacheManager
from app.core.security import get_current_user_id
from app.models.models import PlatformAccount, User

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])

VALID_BOARDS = {"problems_solved", "codeforces_rating", "leetcode_problems", "atcoder_rating"}


@router.get("/{board}")
async def get_leaderboard(
    board: str,
    top_n: int = Query(10, ge=1, le=100),
    cache: CacheManager = Depends(get_cache),
):
    """
    Return top-N users for a given board.
    Boards: problems_solved | codeforces_rating | leetcode_problems | atcoder_rating
    """
    if board not in VALID_BOARDS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown board. Choose from: {VALID_BOARDS}")

    entries = await cache.get_leaderboard(board, top_n=top_n, with_scores=True)
    return [{"rank": i + 1, "username": username, "score": score}
            for i, (username, score) in enumerate(entries)]


@router.post("/refresh")
async def refresh_leaderboards(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    cache: CacheManager = Depends(get_cache),
):
    """
    Rebuild all leaderboards from DB.
    (Admin / scheduled task endpoint — in production gate this behind an admin role.)
    """
    # problems_solved: aggregate across all accounts per user
    users_result = await db.execute(select(User).where(User.is_active == True))
    users = users_result.scalars().all()

    for user in users:
        accs_result = await db.execute(
            select(PlatformAccount).where(PlatformAccount.user_id == user.id)
        )
        accounts = accs_result.scalars().all()

        total_solved = sum(a.problems_solved for a in accounts)
        await cache.update_leaderboard("problems_solved", user.username, total_solved)

        for acc in accounts:
            if acc.platform == "codeforces" and acc.current_rating:
                await cache.update_leaderboard("codeforces_rating", user.username, acc.current_rating)
            if acc.platform == "leetcode":
                await cache.update_leaderboard("leetcode_problems", user.username, acc.problems_solved)
            if acc.platform == "atcoder" and acc.current_rating:
                await cache.update_leaderboard("atcoder_rating", user.username, acc.current_rating)

    return {"message": "Leaderboards refreshed.", "users_processed": len(users)}
