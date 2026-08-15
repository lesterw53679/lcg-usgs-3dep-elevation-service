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

## Local verification completed on Windows

The OIDC and deployment documentation update was validated in the project's Python 3.12.10
virtual environment with:

```powershell
python -m ruff check .
python -m pytest -m "not integration"
python -m mkdocs build --strict
```

Results:

- Ruff: all checks passed.
- Pytest: 27 passed and 1 live integration test was intentionally deselected.
- MkDocs: the documentation built successfully in strict mode.

Two Starlette deprecation warnings were reported by the tests. They did not indicate test
failures and can be handled as a separate dependency/API-maintenance change. Material for
MkDocs also printed an informational warning about a future MkDocs 2.0 transition; the current
documentation build completed successfully.

The checks cover:

- Python compilation of application and test modules
- `pyproject.toml` parsing and editable package build
- GitHub Actions YAML parsing
- Pydantic validation and rejection checks
- Ordered provider tuple construction as `(longitude, latitude)`
- Provider no-data normalization
- Meter-to-international-foot conversion
- Florida valid-fixture parsing, including duplicate coordinates with unique keys

## Azure deployment verification

The automatic deployment workflow successfully authenticated to Azure using GitHub OIDC after
the federated credential was updated to the immutable GitHub repository subject. This proves
that no Azure client secret is required by the workflow.

The custom domain installation was then verified in four layers:

1. Public DNS resolved `elevation.logiccloudgeo.com` to the Web App's default hostname.
2. Azure listed the custom hostname as verified.
3. Azure listed the TLS state as `SniEnabled` after the managed certificate was bound.
4. The live service returned a successful response over HTTPS at the custom hostname.

The stable public verification targets are:

```text
https://elevation.logiccloudgeo.com/health
https://elevation.logiccloudgeo.com/docs
```

The health route does not contact the upstream elevation service. It verifies DNS, TLS, App
Service routing, container startup, and the FastAPI process. A separate call to the elevation
endpoint verifies the additional upstream USGS/Py3DEP path.
