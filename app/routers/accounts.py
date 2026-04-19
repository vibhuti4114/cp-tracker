"""
Platform account management endpoints.
Link/unlink handles, list accounts, trigger sync.
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_cache, CacheManager
from app.core.security import get_current_user_id
from app.models.models import PlatformAccount
from app.schemas.schemas import (
    PlatformAccountCreateRequest, PlatformAccountResponse,
    MessageResponse, SyncResponse,
)
from app.services.platform_fetchers import get_fetcher, PlatformFetchError
from app.services.sync_service import sync_account

router = APIRouter(prefix="/accounts", tags=["Platform Accounts"])


async def _get_account_or_404(account_id: int, user_id: int, db: AsyncSession) -> PlatformAccount:
    result = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.id == account_id,
            PlatformAccount.user_id == user_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Platform account not found.")
    return account


@router.get("", response_model=list[PlatformAccountResponse])
async def list_accounts(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.user_id == user_id)
    )
    return result.scalars().all()


@router.post("", response_model=PlatformAccountResponse, status_code=status.HTTP_201_CREATED)
async def link_account(
    body: PlatformAccountCreateRequest,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    # Verify handle exists on platform
    fetcher = get_fetcher(body.platform)
    try:
        info = await fetcher.fetch_user_info(body.handle)
    except PlatformFetchError as exc:
        raise HTTPException(status_code=422, detail=f"Cannot verify handle: {exc}")

    # Prevent duplicates
    existing = await db.execute(
        select(PlatformAccount).where(
            PlatformAccount.user_id == user_id,
            PlatformAccount.platform == body.platform,
            PlatformAccount.handle == body.handle,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This handle is already linked.")

    account = PlatformAccount(
        user_id=user_id,
        platform=body.platform,
        handle=body.handle,
        is_primary=body.is_primary,
        is_verified=True,  # verified by successful fetch above
        current_rating=info.get("current_rating"),
        max_rating=info.get("max_rating"),
        problems_solved=info.get("problems_solved", 0),
    )
    db.add(account)
    await db.flush()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", response_model=MessageResponse)
async def unlink_account(
    account_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    cache: CacheManager = Depends(get_cache),
):
    account = await _get_account_or_404(account_id, user_id, db)
    await db.delete(account)
    await cache.invalidate_user_stats(user_id)
    return MessageResponse(message=f"Account '{account.handle}' unlinked.")


@router.post("/{account_id}/sync", response_model=SyncResponse)
async def sync_one_account(
    account_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    cache: CacheManager = Depends(get_cache),
):
    """Trigger an immediate sync for a specific account."""
    account = await _get_account_or_404(account_id, user_id, db)
    result = await sync_account(account, db, cache)
    return result


@router.post("/sync-all", response_model=list[SyncResponse])
async def sync_all_accounts(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    cache: CacheManager = Depends(get_cache),
):
    """Sync all linked accounts for the current user."""
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.user_id == user_id)
    )
    accounts = result.scalars().all()
    if not accounts:
        raise HTTPException(status_code=404, detail="No platform accounts linked.")

    responses = []
    for account in accounts:
        resp = await sync_account(account, db, cache)
        responses.append(resp)
    return responses
