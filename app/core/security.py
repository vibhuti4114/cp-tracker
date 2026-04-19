"""
JWT creation, decoding, and password hashing.
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.redis import get_cache, CacheManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain[:72])

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

bearer_scheme = HTTPBearer()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(user_id: int, email: str) -> str:
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "jti": jti,
        "iat": _now(),
        "exp": _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": _now(),
        "exp": _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    cache: CacheManager = Depends(get_cache),
) -> int:
    """
    Decode the Bearer token, verify it is not blacklisted, and return user_id.
    """
    token = credentials.credentials
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Expected an access token.")

    jti: str = payload.get("jti", "")
    if jti and await cache.is_token_blacklisted(jti):
        raise HTTPException(status_code=401, detail="Token has been revoked.")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload.")

    return int(user_id)


async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    cache: CacheManager = Depends(get_cache),
) -> Optional[int]:
    """
    Optional authentication: returns user_id if token is valid, else None.
    """
    if not credentials:
        return None
    try:
        token = credentials.credentials
        payload = decode_token(token)
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except Exception:
        return None


def remaining_ttl(payload: dict) -> int:
    """Seconds until the token expires (used when blacklisting)."""
    exp = payload.get("exp", 0)
    remaining = int(exp - _now().timestamp())
    return max(remaining, 0)
