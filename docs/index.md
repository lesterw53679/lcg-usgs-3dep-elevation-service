# USGS 3DEP Elevation Service

This project provides a small REST API for retrieving bare-earth elevations from the USGS
3D Elevation Program (3DEP). It is intended for browser applications, Jupyter notebooks,
ArcGIS Pro geoprocessing tools, and other HTTP clients.

The first release accepts WGS 84 geographic coordinates (EPSG:4326) as longitude and
latitude in decimal degrees. It supports a single point or an ordered batch of keyed points.

!!! warning "Appropriate use"
    Returned values are samples from an approximately 10-meter bare-earth DEM. They are not
    surveyed benchmarks and should not be represented as survey-grade elevations.

## Current milestone

- Single-point JSON endpoint
- Bulk JSON endpoint with stable `db_key` values
- Meters or international feet
- Strict coordinate and identifier validation
- Configurable batch size, upstream timeout, retry, and concurrency controls
- Automated tests that do not contact USGS by default
- Passwordless GitHub Actions deployments using Azure OIDC
- Public custom hostname with Azure-managed TLS
- Jupyter workflow for ordered topographic profiles

## Deployed development service

- API base URL: <https://elevation.logiccloudgeo.com>
- Interactive OpenAPI documentation: <https://elevation.logiccloudgeo.com/docs>
- Health check: <https://elevation.logiccloudgeo.com/health>
