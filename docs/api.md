# API reference

Interactive OpenAPI documentation is available at `/docs` when the application is running.

## Coordinate order

The named JSON fields remove coordinate-order ambiguity:

- `longitude`: x-coordinate in EPSG:4326 decimal degrees
- `latitude`: y-coordinate in EPSG:4326 decimal degrees

The internal Py3DEP provider sends tuples in `(longitude, latitude)` order.

## Single point

```http
GET /api/v1/elevation?latitude=30.4383&longitude=-84.2807&units=meters
```

`units` can be `meters` or `feet`. Feet are international feet.

## Bulk points

```http
POST /api/v1/elevations
Content-Type: application/json
```

```json
{
  "units": "meters",
  "points": [
    {
      "db_key": "FL-TALLAHASSEE",
      "latitude": 30.4383,
      "longitude": -84.2807
    },
    {
      "db_key": "FL-GULF-01",
      "latitude": 27.0,
      "longitude": -85.0
    }
  ]
}
```

The service preserves row order. A point for which the source has no elevation is returned
with `status: "no_data"` and `elevation: null`.

## Validation

- Latitude must be a JSON number from -90 through 90.
- Longitude must be a JSON number from -180 through 180.
- `db_key` must be unique in the request, contain 1–64 characters, begin with a letter or
  number, and otherwise contain only letters, numbers, underscores, periods, or hyphens.
- Unexpected JSON fields are rejected.
- The default maximum batch size is 500 points.
- The default maximum request-body size is 1,000,000 bytes.

Structurally invalid requests return HTTP 422 without contacting the elevation provider.
Oversized valid batches return HTTP 413.
