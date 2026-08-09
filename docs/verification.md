# Verification

The default automated suite uses a deterministic provider and does not consume USGS capacity.
It covers request validation, duplicate keys, coordinate ordering, no-data values, unit
conversion, batch limits, request-body limits, and the single and bulk HTTP contracts.

The live integration test is deliberately opt-in:

```powershell
$env:RUN_LIVE_USGS_TESTS = "1"
pytest -m integration
```

It queries one Tallahassee coordinate and checks that a finite, plausible low-elevation value
is returned. This is a connectivity smoke test rather than an accuracy benchmark.

## Initial workspace verification

During initial scaffolding, the following checks passed:

- Python compilation of application and test modules
- `pyproject.toml` parsing and editable package build
- GitHub Actions YAML parsing
- Pydantic validation and rejection checks
- Ordered provider tuple construction as `(longitude, latitude)`
- Provider no-data normalization
- Meter-to-international-foot conversion
- Florida valid-fixture parsing, including duplicate coordinates with unique keys

The initial workspace could not download third-party packages from PyPI, so the complete
FastAPI/pytest suite and live Py3DEP call must run in VS Code, Docker, or GitHub Actions where
declared dependencies and outbound USGS access are available.

