# ArcGIS Pro integration roadmap

An ArcGIS Pro geoprocessing tool can generate points along a line and submit those points to
the bulk endpoint. The web service does not require ArcPy and can therefore run in a standard
Linux container in Azure.

For the first ArcGIS integration:

1. Generate points along the selected line using the existing geoprocessing workflow.
2. Project point geometries to EPSG:4326 when necessary.
3. Create a stable `db_key` from the feature identifier or sequence number.
4. Serialize each point using named `longitude` and `latitude` properties.
5. Break lists larger than the advertised API maximum into ordered batches.
6. Join returned elevations to the original features using `db_key`.

A future request model can add `wkid` and projected `x`/`y` fields. That should be introduced
as a new, explicitly versioned input type so EPSG:4326 clients remain unambiguous.

Line-profile calculations should retain both sequence and distance-along-line values. Those
attributes can be returned alongside elevation and plotted without reconstructing order from
coordinates.

The [topographic-profile notebook](topographic-profile-notebook.md) implements this client
pattern independently of ArcPy. It is the reference workflow for local validation, sequential
batching, WGS 84 geodesic distance, result-order checks, no-data handling, and profile exports.
The first ArcGIS tool integration should reproduce those behaviors while reading and writing
feature classes directly.
