(function () {
  "use strict";

  const EARTH_RADIUS_METERS = 6371008.8;
  const METERS_PER_MILE = 1609.344;
  const MAX_LINE_SAMPLES = 200;
  const TALLAHASSEE_VIEW = {
    center: [-84.2807, 30.4383],
    zoom: 9,
    pitch: 58,
    bearing: -18,
  };

  const state = {
    mode: "point",
    coordinates: [],
    sampledPoints: [],
    resultRows: [],
    resultMetadata: null,
    spacingMeters: null,
  };

  const elements = {
    analyze: document.getElementById("analyze"),
    clear: document.getElementById("clear"),
    chart: document.getElementById("profile-chart"),
    chartContainer: document.getElementById("chart-container"),
    download: document.getElementById("download-results"),
    drawHelp: document.getElementById("draw-help"),
    exaggeration: document.getElementById("exaggeration"),
    exaggerationValue: document.getElementById("exaggeration-value"),
    mapStatus: document.getElementById("map-status"),
    resetView: document.getElementById("reset-view"),
    results: document.getElementById("results"),
    resultsBody: document.getElementById("results-body"),
    resultsTitle: document.getElementById("results-title"),
    summary: document.getElementById("summary-grid"),
    undo: document.getElementById("undo"),
    units: document.getElementById("units"),
  };

  if (typeof maplibregl === "undefined") {
    setStatus("The map library could not be loaded. Check the browser connection and reload.", true);
    return;
  }

  const map = new maplibregl.Map({
    container: "map",
    style: "https://tiles.openfreemap.org/styles/liberty",
    ...TALLAHASSEE_VIEW,
    maxPitch: 80,
    maxZoom: 18,
    cooperativeGestures: true,
  });

  map.addControl(
    new maplibregl.NavigationControl({
      showCompass: true,
      showZoom: true,
      visualizePitch: true,
    }),
    "top-right",
  );
  map.addControl(new maplibregl.FullscreenControl(), "top-right");
  map.addControl(new maplibregl.ScaleControl({ maxWidth: 130, unit: "imperial" }), "bottom-left");

  map.on("load", () => {
    map.addSource("terrain-dem", {
      type: "raster-dem",
      tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 15,
      encoding: "terrarium",
      attribution: "Terrain data: Mapzen Terrain Tiles",
    });

    const firstSymbolLayer = map.getStyle().layers.find((layer) => layer.type === "symbol");
    map.addLayer(
      {
        id: "terrain-hillshade",
        type: "hillshade",
        source: "terrain-dem",
        paint: {
          "hillshade-exaggeration": 0.35,
          "hillshade-highlight-color": "#fff3cf",
          "hillshade-shadow-color": "#173f43",
        },
      },
      firstSymbolLayer ? firstSymbolLayer.id : undefined,
    );
    map.setTerrain({ source: "terrain-dem", exaggeration: Number(elements.exaggeration.value) });

    map.addSource("drawn-geometry", {
      type: "geojson",
      data: emptyFeatureCollection(),
    });
    map.addSource("sampled-points", {
      type: "geojson",
      data: emptyFeatureCollection(),
    });

    map.addLayer({
      id: "drawn-line",
      type: "line",
      source: "drawn-geometry",
      filter: ["==", ["geometry-type"], "LineString"],
      paint: {
        "line-color": "#a95032",
        "line-width": 5,
        "line-opacity": 0.94,
      },
    });
    map.addLayer({
      id: "drawn-vertices",
      type: "circle",
      source: "drawn-geometry",
      filter: ["==", ["geometry-type"], "Point"],
      paint: {
        "circle-radius": 6,
        "circle-color": "#fffdf7",
        "circle-stroke-color": "#a95032",
        "circle-stroke-width": 3,
      },
    });
    map.addLayer({
      id: "api-samples",
      type: "circle",
      source: "sampled-points",
      paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 2, 12, 5],
        "circle-color": "#b9d889",
        "circle-stroke-color": "#142d32",
        "circle-stroke-width": 1.5,
      },
    });

    updateMapGeometry();
    setStatus("Point mode is ready. Click the map once to choose a location.");
  });

  map.on("click", (event) => {
    const coordinate = [event.lngLat.lng, event.lngLat.lat];
    if (state.mode === "point") {
      state.coordinates = [coordinate];
      setStatus(`Point selected at ${coordinate[1].toFixed(5)}, ${coordinate[0].toFixed(5)}.`);
    } else {
      state.coordinates.push(coordinate);
      const count = state.coordinates.length;
      setStatus(
        count < 2
          ? "First line vertex placed. Add at least one more vertex."
          : `${count} line vertices placed. Add more bends or analyze the line.`,
      );
    }
    resetResults();
    updateMapGeometry();
    updateControls();
  });

  document.querySelectorAll("[data-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      state.coordinates = [];
      resetResults();
      document.querySelectorAll("[data-mode]").forEach((candidate) => {
        candidate.classList.toggle("is-active", candidate === button);
      });
      elements.drawHelp.textContent =
        state.mode === "point"
          ? "Click the map once to place or replace the point."
          : "Click to add line vertices. Only one line is retained; use Undo for the last vertex.";
      setStatus(
        state.mode === "point"
          ? "Point mode selected. Click the map once."
          : "Line mode selected. Click at least two locations to create one line.",
      );
      updateMapGeometry();
      updateControls();
    });
  });

  elements.undo.addEventListener("click", () => {
    state.coordinates.pop();
    resetResults();
    updateMapGeometry();
    updateControls();
    setStatus(
      state.coordinates.length
        ? `${state.coordinates.length} line vertices remain.`
        : "The line is empty. Click the map to start again.",
    );
  });

  elements.clear.addEventListener("click", () => {
    state.coordinates = [];
    resetResults();
    updateMapGeometry();
    updateControls();
    setStatus(`Cleared. Click the map to draw a new ${state.mode}.`);
  });

  elements.analyze.addEventListener("click", analyzeGeometry);
  elements.download.addEventListener("click", downloadCsv);
  elements.resetView.addEventListener("click", () => map.easeTo({ ...TALLAHASSEE_VIEW, duration: 900 }));
  elements.exaggeration.addEventListener("input", () => {
    const exaggeration = Number(elements.exaggeration.value);
    elements.exaggerationValue.value = `${exaggeration}×`;
    elements.exaggerationValue.textContent = `${exaggeration}×`;
    if (map.getSource("terrain-dem")) {
      map.setTerrain({ source: "terrain-dem", exaggeration });
    }
  });

  updateControls();
  document.getElementById("map").classList.add("is-drawing-point");

  function emptyFeatureCollection() {
    return { type: "FeatureCollection", features: [] };
  }

  function updateControls() {
    const canAnalyze =
      (state.mode === "point" && state.coordinates.length === 1) ||
      (state.mode === "line" && state.coordinates.length >= 2);
    elements.analyze.disabled = !canAnalyze;
    elements.analyze.textContent = state.mode === "point" ? "Analyze point" : "Analyze line";
    elements.undo.disabled = state.mode !== "line" || state.coordinates.length === 0;
    elements.clear.disabled = state.coordinates.length === 0;

    const mapElement = document.getElementById("map");
    mapElement.classList.toggle("is-drawing-point", state.mode === "point");
    mapElement.classList.toggle("is-drawing-line", state.mode === "line");
  }

  function updateMapGeometry() {
    const source = map.getSource("drawn-geometry");
    if (!source) return;

    const features = state.coordinates.map((coordinate, index) => ({
      type: "Feature",
      properties: { sequence: index + 1 },
      geometry: { type: "Point", coordinates: coordinate },
    }));
    if (state.mode === "line" && state.coordinates.length >= 2) {
      features.unshift({
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: state.coordinates },
      });
    }
    source.setData({ type: "FeatureCollection", features });
  }

  function updateSampledPoints() {
    const source = map.getSource("sampled-points");
    if (!source) return;
    source.setData({
      type: "FeatureCollection",
      features: state.sampledPoints.map((sample) => ({
        type: "Feature",
        properties: { sequence: sample.sequence },
        geometry: { type: "Point", coordinates: sample.coordinate },
      })),
    });
  }

  async function analyzeGeometry() {
    elements.analyze.disabled = true;
    elements.analyze.textContent = "Requesting elevations…";
    setStatus("Sending coordinates to the elevation service.");

    try {
      if (state.mode === "point") {
        await analyzePoint();
      } else {
        await analyzeLine();
      }
      elements.results.hidden = false;
      elements.results.scrollIntoView({ behavior: "smooth", block: "start" });
      setStatus("Elevation request completed successfully.");
    } catch (error) {
      setStatus(error.message || "The elevation request failed.", true);
    } finally {
      updateControls();
    }
  }

  async function analyzePoint() {
    const [longitude, latitude] = state.coordinates[0];
    const query = new URLSearchParams({
      latitude: String(latitude),
      longitude: String(longitude),
      units: elements.units.value,
    });
    const response = await fetch(`/api/v1/elevation?${query.toString()}`);
    const payload = await parseApiResponse(response);
    state.resultMetadata = payload;
    state.resultRows = [
      {
        sequence: 1,
        distance_m: 0,
        ...payload.result,
      },
    ];
    state.sampledPoints = [{ sequence: 1, coordinate: [longitude, latitude], distance_m: 0 }];
    state.spacingMeters = null;
    updateSampledPoints();
    renderResults();
  }

  async function analyzeLine() {
    const sampled = sampleLine(state.coordinates);
    state.sampledPoints = sampled;
    updateSampledPoints();
    const request = {
      units: elements.units.value,
      points: sampled.map((sample) => ({
        db_key: `MAP-LINE-${String(sample.sequence).padStart(3, "0")}`,
        longitude: sample.coordinate[0],
        latitude: sample.coordinate[1],
      })),
    };
    const response = await fetch("/api/v1/elevations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
    const payload = await parseApiResponse(response);
    state.resultMetadata = payload;
    state.resultRows = payload.results.map((result, index) => ({
      sequence: sampled[index].sequence,
      distance_m: sampled[index].distance_m,
      ...result,
    }));
    renderResults();
  }

  async function parseApiResponse(response) {
    let payload;
    try {
      payload = await response.json();
    } catch (_error) {
      throw new Error(`The service returned HTTP ${response.status} without a JSON response.`);
    }
    if (!response.ok) {
      const detail = payload.detail;
      const message = typeof detail === "string" ? detail : detail?.message;
      throw new Error(message || `The service returned HTTP ${response.status}.`);
    }
    return payload;
  }

  function sampleLine(coordinates) {
    const segments = [];
    let totalMeters = 0;
    for (let index = 1; index < coordinates.length; index += 1) {
      const start = coordinates[index - 1];
      const end = coordinates[index];
      const length = haversineDistance(start, end);
      if (length > 0) {
        segments.push({ start, end, startDistance: totalMeters, length });
        totalMeters += length;
      }
    }
    if (segments.length === 0) {
      throw new Error("The line needs at least two different locations.");
    }

    const spacing = chooseSpacing(totalMeters);
    state.spacingMeters = spacing;
    const distances = [0];
    for (let distance = spacing; distance < totalMeters; distance += spacing) {
      distances.push(distance);
    }
    if (distances[distances.length - 1] !== totalMeters) distances.push(totalMeters);

    if (distances.length > MAX_LINE_SAMPLES) {
      distances.length = 0;
      const adjusted = totalMeters / (MAX_LINE_SAMPLES - 1);
      state.spacingMeters = adjusted;
      for (let index = 0; index < MAX_LINE_SAMPLES; index += 1) {
        distances.push(index === MAX_LINE_SAMPLES - 1 ? totalMeters : index * adjusted);
      }
    }

    return distances.map((distance, index) => ({
      sequence: index + 1,
      distance_m: distance,
      coordinate: coordinateAlongSegments(segments, distance),
    }));
  }

  function chooseSpacing(totalMeters) {
    const targetSamples =
      totalMeters <= 2000 ? 20 : totalMeters <= 25000 ? 50 : totalMeters <= 100000 ? 75 : 100;
    const rawSpacing = totalMeters / Math.max(1, targetSamples - 1);
    const candidates = [25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000];
    return candidates.find((candidate) => candidate >= rawSpacing) || rawSpacing;
  }

  function coordinateAlongSegments(segments, targetDistance) {
    const finalSegment = segments[segments.length - 1];
    if (targetDistance >= finalSegment.startDistance + finalSegment.length) {
      return [...finalSegment.end];
    }
    const segment =
      segments.find(
        (candidate) => targetDistance <= candidate.startDistance + candidate.length,
      ) || finalSegment;
    const distanceWithin = Math.max(0, targetDistance - segment.startDistance);
    return destinationPoint(segment.start, initialBearing(segment.start, segment.end), distanceWithin);
  }

  function haversineDistance(start, end) {
    const latitude1 = toRadians(start[1]);
    const latitude2 = toRadians(end[1]);
    const deltaLatitude = latitude2 - latitude1;
    const deltaLongitude = toRadians(end[0] - start[0]);
    const value =
      Math.sin(deltaLatitude / 2) ** 2 +
      Math.cos(latitude1) * Math.cos(latitude2) * Math.sin(deltaLongitude / 2) ** 2;
    return 2 * EARTH_RADIUS_METERS * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
  }

  function initialBearing(start, end) {
    const latitude1 = toRadians(start[1]);
    const latitude2 = toRadians(end[1]);
    const deltaLongitude = toRadians(end[0] - start[0]);
    const y = Math.sin(deltaLongitude) * Math.cos(latitude2);
    const x =
      Math.cos(latitude1) * Math.sin(latitude2) -
      Math.sin(latitude1) * Math.cos(latitude2) * Math.cos(deltaLongitude);
    return Math.atan2(y, x);
  }

  function destinationPoint(start, bearing, distanceMeters) {
    const angularDistance = distanceMeters / EARTH_RADIUS_METERS;
    const latitude1 = toRadians(start[1]);
    const longitude1 = toRadians(start[0]);
    const latitude2 = Math.asin(
      Math.sin(latitude1) * Math.cos(angularDistance) +
        Math.cos(latitude1) * Math.sin(angularDistance) * Math.cos(bearing),
    );
    const longitude2 =
      longitude1 +
      Math.atan2(
        Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(latitude1),
        Math.cos(angularDistance) - Math.sin(latitude1) * Math.sin(latitude2),
      );
    return [normalizeLongitude(toDegrees(longitude2)), toDegrees(latitude2)];
  }

  function toRadians(value) {
    return (value * Math.PI) / 180;
  }

  function toDegrees(value) {
    return (value * 180) / Math.PI;
  }

  function normalizeLongitude(value) {
    return ((value + 540) % 360) - 180;
  }

  function renderResults() {
    const successful = state.resultRows.filter(
      (row) => row.status === "success" && Number.isFinite(row.elevation),
    );
    const elevations = successful.map((row) => row.elevation);
    const totalDistance = state.resultRows.at(-1)?.distance_m || 0;
    const unitLabel = state.resultMetadata.units;

    elements.resultsTitle.textContent =
      state.mode === "point" ? "Point elevation" : "Sampled line elevations";
    const summaries = [
      ["Samples", String(state.resultRows.length)],
      ["Profile length", state.mode === "line" ? formatDistance(totalDistance) : "Single point"],
      [
        "Elevation range",
        elevations.length
          ? `${Math.min(...elevations).toFixed(1)}–${Math.max(...elevations).toFixed(1)} ${shortUnit(unitLabel)}`
          : "No data",
      ],
      [
        "Sample spacing",
        state.mode === "line" && state.spacingMeters
          ? formatSpacing(state.spacingMeters)
          : "Not applicable",
      ],
    ];
    elements.summary.replaceChildren(
      ...summaries.map(([label, value]) => {
        const card = document.createElement("div");
        card.className = "summary-card";
        const labelElement = document.createElement("span");
        labelElement.textContent = label;
        const valueElement = document.createElement("strong");
        valueElement.textContent = value;
        card.append(labelElement, valueElement);
        return card;
      }),
    );

    elements.resultsBody.replaceChildren(
      ...state.resultRows.map((row) => {
        const tr = document.createElement("tr");
        const values = [
          row.sequence,
          state.mode === "line" ? formatDistance(row.distance_m) : "—",
          Number(row.latitude).toFixed(6),
          Number(row.longitude).toFixed(6),
          Number.isFinite(row.elevation)
            ? `${Number(row.elevation).toFixed(2)} ${shortUnit(unitLabel)}`
            : "—",
          row.status,
        ];
        values.forEach((value, index) => {
          const td = document.createElement("td");
          td.textContent = String(value);
          if (index === values.length - 1) {
            td.className = row.status === "success" ? "result-success" : "result-no-data";
          }
          tr.append(td);
        });
        return tr;
      }),
    );

    if (state.mode === "line" && successful.length >= 2) {
      elements.chart.hidden = false;
      renderChart(successful, unitLabel);
    } else {
      elements.chart.hidden = true;
      elements.chartContainer.replaceChildren();
    }
  }

  function renderChart(rows, units) {
    const width = 920;
    const height = 300;
    const margin = { top: 15, right: 20, bottom: 45, left: 62 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const maxDistance = Math.max(...rows.map((row) => row.distance_m / METERS_PER_MILE), 0.001);
    let minElevation = Math.min(...rows.map((row) => row.elevation));
    let maxElevation = Math.max(...rows.map((row) => row.elevation));
    const padding = Math.max((maxElevation - minElevation) * 0.1, units === "feet" ? 2 : 0.5);
    minElevation -= padding;
    maxElevation += padding;

    const x = (distance) => margin.left + (distance / maxDistance) * plotWidth;
    const y = (elevation) =>
      margin.top + ((maxElevation - elevation) / (maxElevation - minElevation)) * plotHeight;
    const points = rows.map(
      (row) => `${x(row.distance_m / METERS_PER_MILE).toFixed(2)},${y(row.elevation).toFixed(2)}`,
    );
    const baseline = margin.top + plotHeight;
    const areaPoints = `${margin.left},${baseline} ${points.join(" ")} ${margin.left + plotWidth},${baseline}`;
    const horizontalGrid = Array.from({ length: 5 }, (_, index) => {
      const fraction = index / 4;
      const gridY = margin.top + fraction * plotHeight;
      const label = maxElevation - fraction * (maxElevation - minElevation);
      return `<line class="chart-grid-line" x1="${margin.left}" y1="${gridY}" x2="${margin.left + plotWidth}" y2="${gridY}" /><text class="chart-label" x="${margin.left - 10}" y="${gridY + 4}" text-anchor="end">${label.toFixed(0)}</text>`;
    }).join("");
    const verticalGrid = Array.from({ length: 5 }, (_, index) => {
      const fraction = index / 4;
      const gridX = margin.left + fraction * plotWidth;
      return `<line class="chart-grid-line" x1="${gridX}" y1="${margin.top}" x2="${gridX}" y2="${baseline}" /><text class="chart-label" x="${gridX}" y="${baseline + 24}" text-anchor="middle">${(fraction * maxDistance).toFixed(1)}</text>`;
    }).join("");

    elements.chartContainer.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Elevation profile chart">
        <defs>
          <linearGradient id="profile-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stop-color="#0d6c65" stop-opacity="0.28"></stop>
            <stop offset="100%" stop-color="#0d6c65" stop-opacity="0.02"></stop>
          </linearGradient>
        </defs>
        ${horizontalGrid}
        ${verticalGrid}
        <polygon class="chart-area" points="${areaPoints}"></polygon>
        <polyline class="chart-profile-line" points="${points.join(" ")}"></polyline>
        <text class="chart-label" x="${margin.left + plotWidth / 2}" y="${height - 5}" text-anchor="middle">Distance along line (miles)</text>
        <text class="chart-label" transform="translate(15 ${margin.top + plotHeight / 2}) rotate(-90)" text-anchor="middle">Elevation (${units})</text>
      </svg>`;
  }

  function formatDistance(meters) {
    const miles = meters / METERS_PER_MILE;
    return miles < 0.1 ? `${meters.toFixed(0)} m` : `${miles.toFixed(2)} mi`;
  }

  function formatSpacing(meters) {
    return meters < 1000 ? `${meters.toFixed(0)} m` : `${(meters / 1000).toFixed(1)} km`;
  }

  function shortUnit(units) {
    return units === "feet" ? "ft" : "m";
  }

  function downloadCsv() {
    if (!state.resultRows.length) return;
    const header = ["sequence", "distance_m", "latitude", "longitude", "elevation", "units", "status"];
    const lines = [
      header.join(","),
      ...state.resultRows.map((row) =>
        [
          row.sequence,
          Number(row.distance_m).toFixed(3),
          Number(row.latitude).toFixed(8),
          Number(row.longitude).toFixed(8),
          Number.isFinite(row.elevation) ? Number(row.elevation).toFixed(6) : "",
          state.resultMetadata.units,
          row.status,
        ].join(","),
      ),
    ];
    const blob = new Blob([`${lines.join("\r\n")}\r\n`], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `logic-cloud-geo-${state.mode}-elevations.csv`;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function resetResults() {
    state.sampledPoints = [];
    state.resultRows = [];
    state.resultMetadata = null;
    state.spacingMeters = null;
    elements.results.hidden = true;
    elements.summary.replaceChildren();
    elements.resultsBody.replaceChildren();
    elements.chartContainer.replaceChildren();
    updateSampledPoints();
  }

  function setStatus(message, isError) {
    elements.mapStatus.textContent = message;
    elements.mapStatus.classList.toggle("is-error", Boolean(isError));
  }
})();
