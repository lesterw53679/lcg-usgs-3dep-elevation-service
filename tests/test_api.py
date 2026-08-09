"""FastAPI endpoint tests with a deterministic elevation provider."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_elevation_service
from app.main import app
from app.service import ElevationService
from tests.fakes import FakeProvider


@pytest.fixture
def client() -> Iterator[TestClient]:
    provider = FakeProvider([12.5, None, 3.0])
    app.dependency_overrides[get_elevation_service] = lambda: ElevationService(
        provider,
        max_batch_size=2,
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_does_not_contact_provider(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_single_point_response(client: TestClient) -> None:
    response = client.get(
        "/api/v1/elevation",
        params={"latitude": 30.4383, "longitude": -84.2807, "units": "meters"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["horizontal_crs"] == "EPSG:4326"
    assert payload["result"]["db_key"] is None
    assert payload["result"]["elevation"] == 12.5


def test_bulk_response_preserves_keys_and_reports_no_data(client: TestClient) -> None:
    response = client.post(
        "/api/v1/elevations",
        json={
            "units": "meters",
            "points": [
                {"db_key": "LAND", "latitude": 30.4383, "longitude": -84.2807},
                {"db_key": "GULF", "latitude": 27.0, "longitude": -85.0},
            ],
        },
    )
    payload = response.json()
    assert response.status_code == 200
    assert [result["db_key"] for result in payload["results"]] == ["LAND", "GULF"]
    assert payload["results"][1]["status"] == "no_data"


def test_invalid_bulk_request_never_reaches_service(client: TestClient) -> None:
    response = client.post(
        "/api/v1/elevations",
        json={
            "points": [
                {"db_key": "=FORMULA", "latitude": 30.0, "longitude": -84.0},
            ]
        },
    )
    assert response.status_code == 422


def test_batch_limit_returns_413(client: TestClient) -> None:
    response = client.post(
        "/api/v1/elevations",
        json={
            "points": [
                {"db_key": f"P-{index}", "latitude": 30.0, "longitude": -84.0}
                for index in range(3)
            ]
        },
    )
    assert response.status_code == 413
    assert response.json()["detail"]["maximum"] == 2


def test_request_body_limit_returns_413(client: TestClient) -> None:
    response = client.post(
        "/api/v1/elevations",
        content=b"x" * 1_000_001,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_body_too_large"


def test_invalid_query_coordinate_returns_422(client: TestClient) -> None:
    response = client.get(
        "/api/v1/elevation",
        params={"latitude": 91, "longitude": -84},
    )
    assert response.status_code == 422
