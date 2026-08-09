# Architecture

The HTTP and elevation-provider layers are intentionally separate. API clients depend only
on the versioned JSON contract, not on Py3DEP.

1. FastAPI and Pydantic validate the HTTP request.
2. `ElevationService` enforces the batch limit and preserves input order.
3. `Py3DEPProvider` converts named coordinates to `(longitude, latitude)` tuples.
4. The provider makes one paired-coordinate call through `py3dep.elevation_bycoords`.
5. The service converts meters to international feet if requested and formats the response.

This provider boundary will allow a future USGS EPQS, Seamless3DEP, or locally hosted DEM
implementation without changing ArcGIS Pro, notebook, or browser clients.

## Upstream resilience

The provider runs blocking geospatial work outside FastAPI's event loop. It also applies a
configurable timeout, retry count, exponential delay, and per-process concurrency limit.
The default HyRiver cache is redirected to `/tmp/hyriver` in the container.

The initial deployment should use one application instance while behavior and request volume
are measured. A shared cache or distributed rate limiter can be added before horizontal
scaling.

