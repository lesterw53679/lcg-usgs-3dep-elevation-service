"""Unit tests for Py3DEP normalization without external network calls."""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

from app.providers import Coordinate, Py3DEPProvider


def test_sends_one_ordered_coordinate_list_and_normalizes_no_data(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def elevation_bycoords(coordinates, *, crs, source):
        captured.update(coordinates=coordinates, crs=crs, source=source)
        return [4.5, float("nan")]

    monkeypatch.setitem(
        sys.modules,
        "py3dep",
        SimpleNamespace(elevation_bycoords=elevation_bycoords),
    )
    provider = Py3DEPProvider(source="tep", max_attempts=1)
    values = asyncio.run(
        provider.get_elevations(
            [
                Coordinate(longitude=-84.0, latitude=30.0),
                Coordinate(longitude=-85.0, latitude=27.0),
            ]
        )
    )

    assert captured == {
        "coordinates": [(-84.0, 30.0), (-85.0, 27.0)],
        "crs": 4326,
        "source": "tep",
    }
    assert values == [4.5, None]

