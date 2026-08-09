"""FastAPI dependency factories."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.providers import Py3DEPProvider
from app.service import ElevationService


@lru_cache
def get_elevation_service() -> ElevationService:
    settings = get_settings()
    provider = Py3DEPProvider(
        source=settings.source,
        timeout_seconds=settings.upstream_timeout_seconds,
        max_concurrency=settings.upstream_max_concurrency,
        max_attempts=settings.upstream_max_attempts,
    )
    return ElevationService(provider, max_batch_size=settings.max_batch_size)

