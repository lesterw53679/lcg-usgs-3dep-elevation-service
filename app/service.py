"""Application service for validation-independent elevation processing."""

from __future__ import annotations

from collections.abc import Sequence

from app.models import (
    BulkElevationResponse,
    BulkPoint,
    ElevationResult,
    ElevationUnits,
    ResultStatus,
)
from app.providers import Coordinate, ElevationProvider

METERS_TO_INTERNATIONAL_FEET = 3.280839895013123


class BatchTooLargeError(ValueError):
    def __init__(self, actual: int, maximum: int) -> None:
        super().__init__(f"request contains {actual} points; maximum batch size is {maximum}")
        self.actual = actual
        self.maximum = maximum


class ElevationService:
    """Coordinate calls to a provider and format stable API results."""

    def __init__(self, provider: ElevationProvider, *, max_batch_size: int = 500) -> None:
        self.provider = provider
        self.max_batch_size = max_batch_size

    async def query(
        self,
        points: Sequence[BulkPoint],
        units: ElevationUnits,
    ) -> BulkElevationResponse:
        if len(points) > self.max_batch_size:
            raise BatchTooLargeError(len(points), self.max_batch_size)

        coordinates = [
            Coordinate(longitude=point.longitude, latitude=point.latitude) for point in points
        ]
        elevations_m = await self.provider.get_elevations(coordinates)
        if len(elevations_m) != len(points):
            raise RuntimeError("provider returned a different number of elevations than requested")

        results = [
            self._result(point, elevation_m, units)
            for point, elevation_m in zip(points, elevations_m, strict=True)
        ]
        return BulkElevationResponse(
            units=units,
            horizontal_crs="EPSG:4326",
            dataset=self.provider.dataset,
            provider=self.provider.name,
            approximate_resolution_m=self.provider.approximate_resolution_m,
            vertical_reference=self.provider.vertical_reference,
            results=results,
        )

    @staticmethod
    def _result(
        point: BulkPoint,
        elevation_m: float | None,
        units: ElevationUnits,
    ) -> ElevationResult:
        if elevation_m is None:
            return ElevationResult(
                db_key=point.db_key,
                latitude=point.latitude,
                longitude=point.longitude,
                elevation=None,
                status=ResultStatus.NO_DATA,
                message="The elevation source returned no data for this coordinate.",
            )

        elevation = (
            elevation_m * METERS_TO_INTERNATIONAL_FEET
            if units is ElevationUnits.FEET
            else elevation_m
        )
        return ElevationResult(
            db_key=point.db_key,
            latitude=point.latitude,
            longitude=point.longitude,
            elevation=elevation,
            status=ResultStatus.SUCCESS,
        )

