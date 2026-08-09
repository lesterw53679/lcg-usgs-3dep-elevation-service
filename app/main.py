"""ASGI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app import __version__
from app.api import router
from app.config import get_settings
from app.middleware import MaxRequestBodySizeMiddleware

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


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")
