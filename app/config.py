"""Environment-based application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _positive_int(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be at least 1")
    return value


def _positive_float(name: str, default: float) -> float:
    value = float(os.getenv(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings read from environment variables."""

    provider: str
    source: str
    max_batch_size: int
    max_request_body_bytes: int
    upstream_timeout_seconds: float
    upstream_max_concurrency: int
    upstream_max_attempts: int

    @classmethod
    def from_environment(cls) -> Settings:
        provider = os.getenv("ELEVATION_PROVIDER", "py3dep").strip().lower()
        source = os.getenv("ELEVATION_SOURCE", "tep").strip().lower()
        if provider != "py3dep":
            raise ValueError("ELEVATION_PROVIDER currently supports only 'py3dep'")
        if source not in {"tep", "tnm"}:
            raise ValueError("ELEVATION_SOURCE must be 'tep' or 'tnm'")
        return cls(
            provider=provider,
            source=source,
            max_batch_size=_positive_int("MAX_BATCH_SIZE", 500),
            max_request_body_bytes=_positive_int("MAX_REQUEST_BODY_BYTES", 1_000_000),
            upstream_timeout_seconds=_positive_float("UPSTREAM_TIMEOUT_SECONDS", 60.0),
            upstream_max_concurrency=_positive_int("UPSTREAM_MAX_CONCURRENCY", 2),
            upstream_max_attempts=_positive_int("UPSTREAM_MAX_ATTEMPTS", 3),
        )


@lru_cache
def get_settings() -> Settings:
    """Return one validated Settings instance per process."""

    return Settings.from_environment()
