"""
Auth endpoints: register, login, refresh, logout.
"""

from datetime import timezone, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_cache, CacheManager
from app.core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    decode_token, remaining_ttl, get_current_user_id,
    bearer_scheme,
)
from app.core.config import settings
from app.models.models import User
from app.schemas.schemas import (
    UserRegisterRequest, UserLoginRequest,
    TokenResponse, RefreshRequest, UserResponse, MessageResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check uniqueness
    existing = await db.execute(
        select(User).where((User.email == body.email) | (User.username == body.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email or username already registered.")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated.")

    access = create_access_token(user.id, user.email)
    refresh = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    cache: CacheManager = Depends(get_cache),
):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=400, detail="Expected a refresh token.")

    jti = payload.get("jti", "")
    if await cache.is_token_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked.")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user: User | None = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive.")

    # Blacklist old refresh token
    await cache.blacklist_token(jti, remaining_ttl(payload))

    access = create_access_token(user.id, user.email)
    refresh = create_refresh_token(user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    credentials=Depends(bearer_scheme),
    cache: CacheManager = Depends(get_cache),
):
    token = credentials.credentials
    payload = decode_token(token)
    jti = payload.get("jti", "")
    ttl = remaining_ttl(payload)
    if jti:
        await cache.blacklist_token(jti, ttl)
    return MessageResponse(message="Logged out successfully.")
