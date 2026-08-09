"""Request validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import BulkElevationRequest, BulkPoint


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("latitude", 90.0001),
        ("latitude", -90.0001),
        ("longitude", 180.0001),
        ("longitude", -180.0001),
        ("latitude", float("nan")),
        ("longitude", float("inf")),
        ("latitude", "27.95"),
        ("longitude", True),
    ],
)
def test_rejects_invalid_coordinates(field: str, value: object) -> None:
    data = {"db_key": "FL-001", "latitude": 27.95, "longitude": -82.46}
    data[field] = value
    with pytest.raises(ValidationError):
        BulkPoint.model_validate(data)


@pytest.mark.parametrize("db_key", ["", "=1+1", "+cmd", "has space", "a" * 65])
def test_rejects_unsafe_or_oversized_db_keys(db_key: str) -> None:
    with pytest.raises(ValidationError):
        BulkPoint(db_key=db_key, latitude=27.95, longitude=-82.46)


def test_rejects_duplicate_keys() -> None:
    point = {"db_key": "FL-001", "latitude": 27.95, "longitude": -82.46}
    with pytest.raises(ValidationError, match="must be unique"):
        BulkElevationRequest(points=[point, point])


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BulkPoint(
            db_key="FL-001",
            latitude=27.95,
            longitude=-82.46,
            unexpected="not allowed",
        )

