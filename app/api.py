"""HTTP routes for the elevation service."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app import __version__
from app.config import get_settings
from app.dependencies import get_elevation_service
from app.models import (
    BulkElevationRequest,
    BulkElevationResponse,
    BulkPoint,
    ElevationUnits,
    HealthResponse,
    SingleElevationResponse,
)
from app.providers.base import (
    ElevationProviderError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.service import BatchTooLargeError, ElevationService

router = APIRouter()

LatitudeQuery = Annotated[
    float,
    Query(ge=-90.0, le=90.0, allow_inf_nan=False, description="EPSG:4326 latitude"),
]
LongitudeQuery = Annotated[
    float,
    Query(ge=-180.0, le=180.0, allow_inf_nan=False, description="EPSG:4326 longitude"),
]
ServiceDependency = Annotated[ElevationService, Depends(get_elevation_service)]


def _raise_http_error(exc: Exception) -> None:
    if isinstance(exc, BatchTooLargeError):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "batch_too_large",
                "message": str(exc),
                "maximum": exc.maximum,
            },
        ) from exc
    if isinstance(exc, ProviderUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "provider_unavailable", "message": str(exc)},
        ) from exc
    if isinstance(exc, ProviderTimeoutError):
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"code": "provider_timeout", "message": str(exc)},
        ) from exc
    if isinstance(exc, ElevationProviderError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "upstream_failure", "message": str(exc)},
        ) from exc
    raise exc


@router.get("/health", response_model=HealthResponse, tags=["Operations"])
async def health() -> HealthResponse:
    """Report process health without calling the upstream USGS service."""

    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="USGS Elevation Service",
        version=__version__,
        provider=settings.provider,
    )


@router.get(
    "/api/v1/elevation",
    response_model=SingleElevationResponse,
    tags=["Elevation"],
)
async def point_elevation(
    latitude: LatitudeQuery,
    longitude: LongitudeQuery,
    service: ServiceDependency,
    units: ElevationUnits = ElevationUnits.METERS,
) -> SingleElevationResponse:
    """Return a 3DEP bare-earth elevation for one EPSG:4326 coordinate."""

    point = BulkPoint(db_key="point", latitude=latitude, longitude=longitude)
    try:
        bulk_response = await service.query([point], units)
    except Exception as exc:
        _raise_http_error(exc)
        raise

    result = bulk_response.results[0].model_copy(update={"db_key": None})
    metadata = bulk_response.model_dump(exclude={"results"})
    return SingleElevationResponse(**metadata, result=result)


@router.post(
    "/api/v1/elevations",
    response_model=BulkElevationResponse,
    tags=["Elevation"],
)
async def bulk_elevations(
    request: BulkElevationRequest,
    service: ServiceDependency,
) -> BulkElevationResponse:
    """Return elevations for an ordered list of keyed EPSG:4326 points."""

    try:
        return await service.query(request.points, request.units)
    except Exception as exc:
        _raise_http_error(exc)
        raise

