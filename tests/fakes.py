"""Deterministic providers used by API and service tests."""

from __future__ import annotations

from collections.abc import Sequence

from app.providers import Coordinate


class FakeProvider:
    name = "fake-3dep"
    dataset = "Synthetic test DEM"
    approximate_resolution_m = 10.0
    vertical_reference = "Synthetic"

    def __init__(self, elevations: Sequence[float | None]) -> None:
        self.elevations = list(elevations)
        self.calls: list[list[Coordinate]] = []

    async def get_elevations(self, coordinates: Sequence[Coordinate]) -> list[float | None]:
        self.calls.append(list(coordinates))
        return self.elevations[: len(coordinates)]

