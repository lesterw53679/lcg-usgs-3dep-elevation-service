"""Tests for public website pages and reviewed notebook downloads."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app


def test_home_page_replaces_api_redirect() -> None:
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Logic Cloud Geo" in response.text
    assert 'href="/elevation/demo"' in response.text


def test_elevation_service_page_links_notebooks() -> None:
    with TestClient(app) as client:
        response = client.get("/elevation")

    assert response.status_code == 200
    assert "/downloads/elevation-api-examples.ipynb" in response.text
    assert "/downloads/topographic-profile.ipynb" in response.text


def test_map_demonstration_contains_accessible_workspace() -> None:
    with TestClient(app) as client:
        response = client.get("/elevation/demo")

    assert response.status_code == 200
    assert 'id="map"' in response.text
    assert "Terrain exaggeration" in response.text
    assert 'id="results-body"' in response.text


def test_static_assets_are_served() -> None:
    with TestClient(app) as client:
        response = client.get("/static/js/demo.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert "MAX_LINE_SAMPLES = 200" in response.text


def test_reviewed_notebooks_download_as_valid_json() -> None:
    names = ["elevation-api-examples.ipynb", "topographic-profile.ipynb"]

    with TestClient(app) as client:
        responses = [client.get(f"/downloads/{name}") for name in names]

    for name, response in zip(names, responses, strict=True):
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ipynb+json")
        assert f'filename="{name}"' in response.headers["content-disposition"]
        notebook = json.loads(response.content)
        assert notebook["nbformat"] == 4
        assert notebook["cells"]


def test_unlisted_download_is_not_exposed() -> None:
    with TestClient(app) as client:
        response = client.get("/downloads/private.ipynb")

    assert response.status_code == 404
