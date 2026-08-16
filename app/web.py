"""Public website pages and downloadable notebook artifacts."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
STATIC_ROOT = PACKAGE_ROOT / "static"
NOTEBOOK_ROOT = PROJECT_ROOT / "notebooks"

NOTEBOOK_DOWNLOADS = {
    "elevation-api-examples.ipynb": "elevation_api_examples.ipynb",
    "topographic-profile.ipynb": "topographic_profile.ipynb",
}

router = APIRouter(include_in_schema=False)


def _page(filename: str) -> FileResponse:
    return FileResponse(STATIC_ROOT / filename, media_type="text/html")


@router.get("/", response_class=FileResponse)
async def home_page() -> FileResponse:
    """Serve the Logic Cloud Geo introduction page."""

    return _page("index.html")


@router.get("/elevation", response_class=FileResponse)
async def elevation_page() -> FileResponse:
    """Serve the public elevation-service overview."""

    return _page("elevation.html")


@router.get("/elevation/demo", response_class=FileResponse)
async def elevation_demo_page() -> FileResponse:
    """Serve the interactive MapLibre elevation demonstration."""

    return _page("demo.html")


@router.get("/downloads/{download_name}", response_class=FileResponse)
async def download_notebook(download_name: str) -> FileResponse:
    """Download one of the reviewed instructional Jupyter notebooks."""

    source_name = NOTEBOOK_DOWNLOADS.get(download_name)
    if source_name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Download not found")

    notebook_path = NOTEBOOK_ROOT / source_name
    if not notebook_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notebook download is temporarily unavailable",
        )

    return FileResponse(
        notebook_path,
        media_type="application/x-ipynb+json",
        filename=download_name,
    )
