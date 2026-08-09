"""Validated API request and response models."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

DbKey = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$",
    ),
]
Latitude = Annotated[float, Field(ge=-90.0, le=90.0, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180.0, le=180.0, allow_inf_nan=False)]


class ApiModel(BaseModel):
    """Base model that rejects unexpected request fields."""

    model_config = ConfigDict(extra="forbid")


class ElevationUnits(StrEnum):
    METERS = "meters"
    FEET = "feet"


class ResultStatus(StrEnum):
    SUCCESS = "success"
    NO_DATA = "no_data"


class BulkPoint(ApiModel):
    """One keyed point in EPSG:4326 longitude/latitude coordinates."""

    db_key: DbKey
    latitude: Latitude
    longitude: Longitude

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def require_json_number(cls, value: Any) -> Any:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("coordinate must be a JSON number")
        return value


class BulkElevationRequest(ApiModel):
    """A validated batch of keyed points."""

    units: ElevationUnits = ElevationUnits.METERS
    points: Annotated[list[BulkPoint], Field(min_length=1)]

    @model_validator(mode="after")
    def require_unique_keys(self) -> Self:
        keys = [point.db_key for point in self.points]
        if len(keys) != len(set(keys)):
            raise ValueError("db_key values must be unique within a request")
        return self


class ElevationResult(ApiModel):
    db_key: str | None
    latitude: float
    longitude: float
    elevation: float | None
    status: ResultStatus
    message: str | None = None


class ResponseMetadata(ApiModel):
    units: ElevationUnits
    horizontal_crs: str
    dataset: str
    provider: str
    approximate_resolution_m: float
    vertical_reference: str


class SingleElevationResponse(ResponseMetadata):
    result: ElevationResult


class BulkElevationResponse(ResponseMetadata):
    results: list[ElevationResult]


class HealthResponse(ApiModel):
    status: str
    service: str
    version: str
    provider: str
