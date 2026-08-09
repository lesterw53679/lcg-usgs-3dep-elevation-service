"""Provider contracts and provider-specific exceptions."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Coordinate:
    longitude: float
    latitude: float


class ElevationProviderError(RuntimeError):
    """Base error raised when an upstream elevation provider fails."""


class ProviderUnavailableError(ElevationProviderError):
    """Raised when the configured provider cannot be loaded."""


class ProviderTimeoutError(ElevationProviderError):
    """Raised when the provider does not respond before the configured timeout."""


class ElevationProvider(Protocol):
    """Contract implemented by point-elevation backends."""

    name: str
    dataset: str
    approximate_resolution_m: float
    vertical_reference: str

    async def get_elevations(self, coordinates: Sequence[Coordinate]) -> list[float | None]: ...
