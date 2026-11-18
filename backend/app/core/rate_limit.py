"""Rate limiting helpers using slowapi."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import Settings, get_settings


@lru_cache()
def get_rate_limiter() -> Limiter:
    settings = get_settings()
    return Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_bucket()],
        headers_enabled=True,
        storage_uri=settings.rate_limit_storage_uri or "memory://",
    )


def login_rate_limit() -> str:
    """Return the rate limit expression applied to auth flows."""
    return "5/minute"


def summary_rate_key(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    return f"user:{user_id}" if user_id else get_remote_address(request)
