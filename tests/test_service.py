"""Elevation orchestration and conversion tests."""

from __future__ import annotations

import asyncio

import pytest

from app.models import BulkPoint, ElevationUnits, ResultStatus
from app.service import METERS_TO_INTERNATIONAL_FEET, BatchTooLargeError, ElevationService
from tests.fakes import FakeProvider


def test_preserves_order_keys_and_no_data() -> None:
    provider = FakeProvider([3.25, None, -0.5])
    service = ElevationService(provider)
    points = [
        BulkPoint(db_key="A", latitude=30.0, longitude=-84.0),
        BulkPoint(db_key="B", latitude=27.0, longitude=-85.0),
        BulkPoint(db_key="C", latitude=25.0, longitude=-80.0),
    ]

    response = asyncio.run(service.query(points, ElevationUnits.METERS))

    assert [result.db_key for result in response.results] == ["A", "B", "C"]
    assert response.results[0].elevation == 3.25
    assert response.results[1].status is ResultStatus.NO_DATA
    assert response.results[1].elevation is None
    assert response.results[2].elevation == -0.5
    assert [(c.longitude, c.latitude) for c in provider.calls[0]] == [
        (-84.0, 30.0),
        (-85.0, 27.0),
        (-80.0, 25.0),
    ]


def test_converts_meters_to_international_feet() -> None:
    provider = FakeProvider([1.0])
    service = ElevationService(provider)
    point = BulkPoint(db_key="ONE-METER", latitude=28.0, longitude=-81.0)

    response = asyncio.run(service.query([point], ElevationUnits.FEET))

    assert response.results[0].elevation == pytest.approx(METERS_TO_INTERNATIONAL_FEET)


def test_enforces_configured_batch_limit_before_provider_call() -> None:
    provider = FakeProvider([1.0, 2.0])
    service = ElevationService(provider, max_batch_size=1)
    points = [
        BulkPoint(db_key="A", latitude=28.0, longitude=-81.0),
        BulkPoint(db_key="B", latitude=29.0, longitude=-82.0),
    ]

    with pytest.raises(BatchTooLargeError):
        asyncio.run(service.query(points, ElevationUnits.METERS))

    assert provider.calls == []


def test_default_500_point_boundary_with_fake_provider() -> None:
    maximum = 500
    points = [
        BulkPoint(db_key=f"P-{index:03d}", latitude=30.0, longitude=-84.0)
        for index in range(maximum)
    ]
    provider = FakeProvider([1.0] * maximum)
    service = ElevationService(provider)

    response = asyncio.run(service.query(points, ElevationUnits.METERS))

    assert len(response.results) == maximum
    assert len(provider.calls) == 1
    assert len(provider.calls[0]) == maximum

    oversized_points = [
        *points,
        BulkPoint(db_key="P-500", latitude=30.0, longitude=-84.0),
    ]
    with pytest.raises(BatchTooLargeError):
        asyncio.run(service.query(oversized_points, ElevationUnits.METERS))

    assert len(provider.calls) == 1
