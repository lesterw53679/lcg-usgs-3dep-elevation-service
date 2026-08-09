"""Opt-in live smoke test for the external USGS/HyRiver data path."""

from __future__ import annotations

import asyncio
import os

import pytest

from app.providers import Coordinate, Py3DEPProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_USGS_TESTS") != "1",
        reason="set RUN_LIVE_USGS_TESTS=1 to contact the live USGS service",
    ),
]


def test_tallahassee_returns_plausible_low_elevation() -> None:
    provider = Py3DEPProvider(timeout_seconds=90, max_attempts=2)
    values = asyncio.run(
        provider.get_elevations([Coordinate(longitude=-84.2807, latitude=30.4383)])
    )
    assert len(values) == 1
    assert values[0] is not None
    assert -10 < values[0] < 100

