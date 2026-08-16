# USGS 3DEP Elevation Service

A small FastAPI application that returns USGS 3DEP bare-earth elevations for one WGS 84
point or an ordered list of keyed points. The service is designed for future use by ArcGIS
Pro geoprocessing tools, Jupyter notebooks, and a browser interface.

## Important coordinate conventions

- Inputs are EPSG:4326 geographic coordinates in decimal degrees.
- JSON uses named `longitude` and `latitude` properties.
- Py3DEP receives tuples in `(longitude, latitude)` order.
- The source is an approximately 10-meter DEM, not a surveyed benchmark.

## Run locally in VS Code

Use a Python 3.12 environment separate from the ArcGIS Pro Python environment.

### Windows PowerShell

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,docs,notebooks]"
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000> for the Logic Cloud Geo website and
<http://127.0.0.1:8000/docs> for the interactive API documentation.

If native geospatial dependencies make local installation difficult, use Docker:

```powershell
docker build -t usgs-elevation-service .
docker run --rm -p 8000:8000 usgs-elevation-service
```

## Try a point

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8000/api/v1/elevation?latitude=30.4383&longitude=-84.2807&units=feet"
```

## Try a batch

From Bash, Git Bash, or WSL:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/elevations \
  -H 'Content-Type: application/json' \
  --data @sample_data/bulk_request.json
```

## Test

Normal tests use a deterministic fake provider and do not contact USGS:

```powershell
pytest -m "not integration"
```

Run the opt-in live provider smoke test sparingly:

```powershell
$env:RUN_LIVE_USGS_TESTS = "1"
pytest -m integration
```

The synthetic Florida datasets are in `sample_data/`. The Gulf coordinate intentionally
exercises the no-data path; it is not considered structurally invalid because it is a valid
EPSG:4326 coordinate.

## Documentation

```powershell
mkdocs serve
```

Project documentation covers the API contract, architecture, Azure preparation, and the
ArcGIS Pro line-to-points integration.

The deployment chapters provide the complete reproducible Azure installation and the ongoing
GitHub Actions/OIDC delivery pattern:

- `docs/azure-deployment.md`: one-time Azure resources, bootstrap image, managed-identity ACR
  pull, application settings, verification, and the exact original workarounds.
- `docs/github-actions-oidc.md`: passwordless GitHub-to-Azure authentication, least-privilege
  roles, repository configuration, automatic deployments, verification, rollback, and
  troubleshooting.
- `docs/custom-domain-tls.md`: GoDaddy CNAME and ownership records, Azure hostname mapping,
  App Service managed certificate creation, SNI binding, HTTPS enforcement, verification,
  renewal, and the empty-thumbprint recovery used during installation.
- `docs/topographic-profile-notebook.md`: ordered point input, local validation, sequential API
  batching, WGS 84 geodesic distance, no-data review, plotting, exports, and the path toward
  ArcGIS Pro and browser clients.
- `docs/elevation-api-examples-notebook.md`: compact single-coordinate and user-keyed point-list
  requests with a `db_key` join and CSV export.
- `docs/web-interface.md`: public-site routes, MapLibre terrain architecture, point and line
  interaction, adaptive sparse sampling, notebook downloads, test boundaries, and deployment.

The deployed development website is available at <https://elevation.logiccloudgeo.com>.
Interactive API documentation remains available at
<https://elevation.logiccloudgeo.com/docs>.

## Public website

FastAPI serves a framework-light public interface from the same Azure container as the API:

- `/`: Logic Cloud Geo introduction and founder-profile placeholder;
- `/elevation`: service description, validation summary, and notebook downloads;
- `/elevation/demo`: MapLibre point and line demonstration with 3D terrain; and
- `/docs`: the existing OpenAPI interface.

The map uses OpenFreeMap for the basemap and Mapzen Terrain Tiles for visual terrain. Those
display sources are independent of the numerical elevations returned by the 3DEP API. The line
client selects a sparse geodesic sample interval and caps a demonstration request at 200 points.

## Topographic profile notebook

Install the notebook dependencies and start JupyterLab from the repository root:

```powershell
python -m pip install -e ".[notebooks]"
python -m jupyter lab
```

Open `notebooks/topographic_profile.ipynb`. The notebook reads an ordered WGS 84 point table,
queries the public bulk-elevation endpoint, calculates WGS 84 geodesic distance along the
profile, plots the elevations, and exports CSV, GeoJSON, and PNG results. A small synthetic
Florida transect is provided in both CSV and ArcGIS-style TSV forms.

Open `notebooks/elevation_api_examples.ipynb` for the smaller instructional examples: one
latitude/longitude request and one user-keyed list whose results are joined back by `db_key`.
