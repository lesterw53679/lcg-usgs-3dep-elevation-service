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

Open <http://127.0.0.1:8000/docs> for the interactive API documentation.

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
planned ArcGIS Pro line-to-points integration.

The deployment chapters provide the complete reproducible Azure installation and the ongoing
GitHub Actions/OIDC delivery pattern:

- `docs/azure-deployment.md`: one-time Azure resources, bootstrap image, managed-identity ACR
  pull, application settings, verification, and the exact original workarounds.
- `docs/github-actions-oidc.md`: passwordless GitHub-to-Azure authentication, least-privilege
  roles, repository configuration, automatic deployments, verification, rollback, and
  troubleshooting.
