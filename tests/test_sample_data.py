"""Checks that the documented Florida fixtures behave as intended."""

from __future__ import annotations

import csv
from pathlib import Path

from app.models import BulkElevationRequest, BulkPoint

SAMPLE_DATA = Path(__file__).parents[1] / "sample_data"


def test_valid_florida_tsv_builds_one_bulk_request() -> None:
    with (SAMPLE_DATA / "florida_valid.tsv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))

    points = [
        BulkPoint(
            db_key=row["DB_Key"],
            latitude=float(row["Latitude"]),
            longitude=float(row["Longitude"]),
        )
        for row in rows
    ]
    request = BulkElevationRequest(points=points)

    assert len(request.points) == 9
    assert request.points[-1].db_key == "FL-DUPLICATE-LOCATION"
    assert request.points[-1].latitude == request.points[2].latitude
    assert request.points[-1].longitude == request.points[2].longitude

