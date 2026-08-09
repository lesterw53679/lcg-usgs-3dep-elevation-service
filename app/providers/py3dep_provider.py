"""Py3DEP implementation of the elevation provider contract."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Sequence
from typing import Any

from app.providers.base import (
    Coordinate,
    ElevationProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class Py3DEPProvider:
    """Retrieve paired point elevations from the USGS 3DEP 10 m DEM."""

    name = "py3dep"
    dataset = "USGS 3DEP 1/3 arc-second bare-earth DEM"
    approximate_resolution_m = 10.0
    vertical_reference = "NAVD88 over CONUS; source metadata governs other areas"

    def __init__(
        self,
        *,
        source: str = "tep",
        timeout_seconds: float = 60.0,
        max_concurrency: int = 2,
        max_attempts: int = 3,
    ) -> None:
        if source not in {"tep", "tnm"}:
            raise ValueError("source must be 'tep' or 'tnm'")
        self.source = source
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def get_elevations(self, coordinates: Sequence[Coordinate]) -> list[float | None]:
        if not coordinates:
            return []

        async with self._semaphore:
            for attempt in range(1, self.max_attempts + 1):
                try:
                    return await asyncio.wait_for(
                        asyncio.to_thread(self._query, coordinates),
                        timeout=self.timeout_seconds,
                    )
                except TimeoutError as exc:
                    if attempt == self.max_attempts:
                        raise ProviderTimeoutError(
                            f"USGS 3DEP did not respond within {self.timeout_seconds:g} seconds"
                        ) from exc
                except ProviderUnavailableError:
                    raise
                except Exception as exc:
                    if attempt == self.max_attempts:
                        raise ElevationProviderError(
                            f"USGS 3DEP query failed after {self.max_attempts} attempts"
                        ) from exc

                await asyncio.sleep(0.25 * (2 ** (attempt - 1)))

        raise ElevationProviderError("USGS 3DEP query failed")

    def _query(self, coordinates: Sequence[Coordinate]) -> list[float | None]:
        try:
            import py3dep
        except ImportError as exc:
            raise ProviderUnavailableError(
                "py3dep is not installed; install the application dependencies"
            ) from exc

        coordinate_pairs = [
            (coordinate.longitude, coordinate.latitude) for coordinate in coordinates
        ]
        values: Any = py3dep.elevation_bycoords(
            coordinate_pairs,
            crs=4326,
            source=self.source,
        )
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            values = [values]
        if len(values) != len(coordinates):
            raise ElevationProviderError(
                "USGS 3DEP returned a different number of elevations than requested"
            )

        normalized: list[float | None] = []
        for value in values:
            if value is None:
                normalized.append(None)
                continue
            numeric_value = float(value)
            normalized.append(numeric_value if math.isfinite(numeric_value) else None)
        return normalized

