"""ASGI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import router
from app.config import get_settings
from app.middleware import MaxRequestBodySizeMiddleware
from app.web import STATIC_ROOT
from app.web import router as web_router

app = FastAPI(
    title="USGS 3DEP Elevation Service",
    summary="Retrieve bare-earth elevations for one point or an ordered batch of points.",
    description=(
        "Coordinates are WGS 84 geographic longitude/latitude values (EPSG:4326). "
        "Elevations are samples from a USGS 3DEP DEM and are not surveyed benchmarks."
    ),
    version=__version__,
    license_info={"name": "License to be selected before public release"},
)
app.add_middleware(
    MaxRequestBodySizeMiddleware,
    max_bytes=get_settings().max_request_body_bytes,
)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")
app.include_router(web_router)
