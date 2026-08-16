# Public web interface

The Logic Cloud Geo public interface is served by the same FastAPI process and Azure container as
the elevation API. This keeps the first browser client small, avoids a second hosting system, and
allows browser requests to use relative same-origin URLs such as `/api/v1/elevations`.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Logic Cloud Geo introduction, brand placeholders, contact, and founder profile |
| `/elevation` | Service contract, provenance, validation summary, and notebook downloads |
| `/elevation/demo` | MapLibre point and line demonstration |
| `/downloads/elevation-api-examples.ipynb` | Reviewed single-point and keyed-list notebook |
| `/downloads/topographic-profile.ipynb` | Reviewed topographic-profile notebook |
| `/docs` | FastAPI-generated OpenAPI interface |
| `/health` | Process health response |

Static HTML, CSS, and JavaScript are under `app/static/`. `app/web.py` serves the three HTML pages
and exposes only the two explicitly allow-listed notebooks. `Dockerfile` copies the notebook
directory into the deployed image. Notebook changes are therefore no longer excluded from the
Azure deployment workflow.

## Why the interface is served by FastAPI

The first release does not require a JavaScript framework or a separate frontend build:

1. FastAPI already owns the public custom hostname and TLS certificate.
2. The browser and API share an origin, so cross-origin configuration is unnecessary.
3. GitHub Actions builds and deploys one immutable container image.
4. HTML, CSS, and browser JavaScript remain inspectable for instructional use.
5. A separate frontend can still be introduced later if the interface grows substantially.

## Map sources and analytical source

The demonstration deliberately distinguishes display data from analysis data:

| Role | Source | Use |
| --- | --- | --- |
| Basemap | OpenFreeMap Liberty style and OpenStreetMap-derived vector tiles | Roads, places, boundaries, and reference context |
| Visual terrain | Mapzen Terrain Tiles hosted as an AWS Open Data dataset | MapLibre terrain mesh and hillshade |
| Analytical elevation | Logic Cloud Geo API using Py3DEP and USGS 3DEP | Returned point values, table, CSV, and profile chart |

The terrain-exaggeration slider changes only MapLibre's visual mesh. It never changes coordinates
or elevations returned by the API. The interface repeats this distinction next to the results.

External display services are convenient for the free demonstration but are runtime dependencies.
A later production-hardening phase can pin or self-host the required basemap style, fonts, and
terrain tiles if availability guarantees become important.

## Drawing workflow

### Point mode

1. The user clicks the map once.
2. A second click replaces the first point.
3. **Analyze point** calls `GET /api/v1/elevation` with named latitude and longitude parameters.
4. The response is shown in the summary and result table.

### Line mode

1. Each click adds a vertex to one `LineString`.
2. **Undo vertex** removes the last vertex; **Clear** removes the entire line.
3. The browser measures every segment with a WGS 84-compatible spherical geodesic calculation.
4. A readable interval is selected from 25, 50, 100, 250, 500 meters and progressively larger
   intervals for longer lines.
5. Both endpoints are included and the request is capped at 200 points.
6. Generated keys use `MAP-LINE-001`, `MAP-LINE-002`, and the same pattern for the remaining
   samples.
7. One request is sent to `POST /api/v1/elevations`.
8. The response becomes map samples, summary statistics, a line-only SVG profile, a table, and a
   downloadable CSV.

This is intentionally a demonstration sampling policy. It does not claim that sparse samples
reconstruct every unsampled terrain feature. Advanced users should use the downloadable profile
notebook when they need explicit control of point spacing, batching, source fields, and exports.

## Florida 3D presentation

The initial Tallahassee view uses a pitched and rotated camera and defaults to four-times terrain
exaggeration. Florida's relief is low enough that a one-times terrain surface can appear almost
flat at regional map scales. The slider ranges from one to eight times and is labeled as a display
setting so it cannot be confused with analytical elevation scaling.

## Current safeguards

- The UI retains only one point or one line at a time.
- A browser-generated line request contains no more than 200 points.
- The API independently enforces its 500-point batch limit and request-body size limit.
- Coordinates remain named longitude and latitude properties in EPSG:4326.
- Returned no-data values remain visible and are not interpolated.
- Notebook filenames are allow-listed instead of accepting arbitrary filesystem paths.
- Unit selection is passed to the API rather than converted independently in the browser.

Client-side limits improve the demonstration experience but are not security boundaries. Before a
high-traffic public launch, consider Azure request telemetry, server-side rate limiting, a written
acceptable-use policy, and alerts for unusual request volume or upstream errors.

## Local verification

Start the existing application from the repository root:

```powershell
uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/elevation
http://127.0.0.1:8000/elevation/demo
```

The normal automated checks cover page routes, static asset delivery, allow-listed notebook
downloads, notebook JSON validity, API behavior, lint, and documentation. The live map also needs a
browser with WebGL and internet access to OpenFreeMap, the MapLibre CDN, and the terrain-tile host.

## Deployment behavior

The web interface is part of the same application image as the API. A push to `main` that changes
`app/`, `Dockerfile`, or the included notebooks triggers the existing Azure workflow:

1. GitHub Actions runs Ruff and non-integration tests.
2. OIDC authenticates the workflow to Azure without a stored password.
3. The workflow builds and pushes a revision-tagged container to Azure Container Registry.
4. Azure App Service is updated to the new image.
5. The workflow verifies `/health` before reporting success.

The custom hostname and managed TLS binding require no change for these new routes.
