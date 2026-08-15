"""Structural tests for the topographic-profile notebook and demonstration input."""

from __future__ import annotations

import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "topographic_profile.ipynb"
SAMPLE_PATH = PROJECT_ROOT / "sample_data" / "florida_profile_points.csv"


def test_topographic_profile_notebook_is_valid_json_with_compilable_code() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert notebook["nbformat_minor"] == 5
    assert len(notebook["cells"]) >= 20

    cell_ids: set[str] = set()
    for position, cell in enumerate(notebook["cells"], start=1):
        assert cell["cell_type"] in {"code", "markdown"}
        assert cell["id"] not in cell_ids
        cell_ids.add(cell["id"])

        if cell["cell_type"] == "code":
            source = "".join(cell["source"])
            compile(source, f"{NOTEBOOK_PATH}:cell-{position}", "exec")


def test_florida_profile_sample_has_ordered_valid_coordinates() -> None:
    with SAMPLE_PATH.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) >= 2
    assert set(rows[0]) >= {"db_key", "sequence", "latitude", "longitude"}

    keys = [row["db_key"] for row in rows]
    sequences = [int(row["sequence"]) for row in rows]
    latitudes = [float(row["latitude"]) for row in rows]
    longitudes = [float(row["longitude"]) for row in rows]

    assert len(keys) == len(set(keys))
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))
    assert all(-90.0 <= latitude <= 90.0 for latitude in latitudes)
    assert all(-180.0 <= longitude <= 180.0 for longitude in longitudes)
