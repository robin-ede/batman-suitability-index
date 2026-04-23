/* map.js — Leaflet map setup, layer management, and interactivity
   Data is loaded via global <script> tags (HEX_DATA, etc.)           */

(function () {
  'use strict';

  // ── COLOUR HELPERS ──────────────────────────────────────────────
  const viridis  = ['#440154', '#31688e', '#35b779', '#fde724'];
  // Warm sequential palette for pop density (distinct from BSI viridis
  // and from the diverging blue-red used for Crime Gi*).
  const warmSequential = ['#1f2937', '#7c2d12', '#ea580c', '#fed7aa'];

  function hexToRgb(hex) {
    return hex.match(/\w\w/g).map(x => parseInt(x, 16));
  }
  function rgbToHex(r, g, b) {
    return '#' + [r, g, b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('');
  }
  function lerpColor(a, b, t) {
    const A = hexToRgb(a), B = hexToRgb(b);
    return rgbToHex(
      A[0] + (B[0]-A[0])*t,
      A[1] + (B[1]-A[1])*t,
      A[2] + (B[2]-A[2])*t
    );
  }
  function getInterpolatedColor(value, min, max, palette) {
    const t = Math.max(0, Math.min(1, max === min ? 0 : (value - min) / (max - min)));
    const idx = t * (palette.length - 1);
    const i = Math.floor(idx);
    const f = idx - i;
    if (i >= palette.length - 1) return palette[palette.length - 1];
    return lerpColor(palette[i], palette[i + 1], f);
  }

  // ── GET DATA PROPERTIES ─────────────────────────────────────────
  const hexFeatures = HEX_DATA?.features || [];
  const policeFeatures = POLICE_STATIONS?.features || [];
  const industrialFeatures = INDUSTRIAL_ZONES?.features || [];
  const boundaryFeatures = CHICAGO_BOUNDARY?.features || [];

  // compute ranges for colour scales
  const allBsi = hexFeatures.map(f => f.properties.bsi).filter(v => v != null);
  const allGi  = hexFeatures.map(f => f.properties.gi_z).filter(v => v != null);
  const allPop = hexFeatures.map(f => f.properties.pop_density_km2).filter(v => v != null);
  const bsiMin = Math.min(...allBsi), bsiMax = Math.max(...allBsi);
  const giAbsMax = Math.max(1.0, ...allGi.map(Math.abs));
  const popMin = Math.min(...allPop), popMax = Math.max(...allPop);

  // Populate continuous-legend min/max labels from the computed ranges.
  function formatPop(n) {
    if (n >= 1000) return (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k/km²';
    return Math.round(n) + '/km²';
  }
  const bsiMinEl = document.getElementById('legend-bsi-min');
  const bsiMaxEl = document.getElementById('legend-bsi-max');
  const popMinEl = document.getElementById('legend-pop-min');
  const popMaxEl = document.getElementById('legend-pop-max');
  if (bsiMinEl) bsiMinEl.textContent = bsiMin.toFixed(2);
  if (bsiMaxEl) bsiMaxEl.textContent = bsiMax.toFixed(2);
  if (popMinEl) popMinEl.textContent = formatPop(popMin);
  if (popMaxEl) popMaxEl.textContent = formatPop(popMax);

  // ── INITIALISE MAP ──────────────────────────────────────────────
  const map = L.map('map', {
    center: [41.83, -87.68],
    zoom: 11,
    zoomControl: true,
    attributionControl: true,
    minZoom: 9,
  });

  // CartoDB Dark Matter base layer
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20,
  }).addTo(map);

  // ── TOOLTIP STYLING ─────────────────────────────────────────────
  const tooltipOptions = { sticky: true, direction: 'top', opacity: 0.95, className: 'hex-tooltip' };

  // ── HEX LAYERS ──────────────────────────────────────────────────
  function styleHexBSI(f) {
    const val = f.properties.bsi;
    const color = getInterpolatedColor(val, bsiMin, bsiMax, viridis);
    return { fillColor: color, color: 'rgba(0,0,0,0.25)', weight: 0.4, fillOpacity: 0.75 };
  }
  function styleHexCrime(f) {
    const val = f.properties.gi_z || 0;
    const t = (val + giAbsMax) / (2 * giAbsMax);
    const color = getInterpolatedColor(t, 0, 1, ['#2166ac','#67a9cf','#ef8a62','#b2182b']);
    return { fillColor: color, color: 'rgba(0,0,0,0.25)', weight: 0.4, fillOpacity: 0.75 };
  }
  function styleHexPop(f) {
    const val = f.properties.pop_density_km2 || 0;
    const color = getInterpolatedColor(val, popMin, popMax, warmSequential);
    return { fillColor: color, color: 'rgba(0,0,0,0.25)', weight: 0.4, fillOpacity: 0.75 };
  }
  function onEachHex(f, layer) {
    const p = f.properties;
    const label = p.hotspot === 'Hot Spot' ? 'Crime Hot Spot'
                : p.hotspot === 'Cold Spot' ? 'Crime Cold Spot'
                : 'Hex Grid Cell';
    const tooltip = `
      <div style="font-family:sans-serif;font-size:12px;line-height:1.5">
        <strong style="color:#facc15">${label}</strong><br>
        BSI: <b>${p.bsi?.toFixed ? p.bsi.toFixed(4) : p.bsi}</b><br>
        Crime count: ${p.crime_count}<br>
        Gi* Z: ${p.gi_z?.toFixed ? p.gi_z.toFixed(2) : p.gi_z}<br>
        Pop density: ${Math.round(p.pop_density_km2 || 0)} /km²<br>
        Police dist: ${Math.round(p.police_dist_m || 0)} m<br>
        Industrial: ${p.industrial ? 'Yes' : 'No'}
      </div>`;
    layer.bindTooltip(tooltip, tooltipOptions);
  }

  const hexLayerBSI  = L.geoJSON(hexFeatures, { style: styleHexBSI, onEachFeature: onEachHex });
  const hexLayerCrime = L.geoJSON(hexFeatures, { style: styleHexCrime, onEachFeature: onEachHex });
  const hexLayerPop   = L.geoJSON(hexFeatures, { style: styleHexPop, onEachFeature: onEachHex });

  // ── BOUNDARY ────────────────────────────────────────────────────
  const boundaryLayer = L.geoJSON(boundaryFeatures, {
    style: { color: '#facc15', weight: 2, fill: false, dashArray: '5, 8', opacity: 0.35 }
  });

  // ── POLICE ──────────────────────────────────────────────────────
  const policeLayer = L.geoJSON(policeFeatures, {
    pointToLayer: (f, latlng) => L.circleMarker(latlng, {
      radius: 7,
      fillColor: '#3b82f6',
      color: '#bfdbfe',
      weight: 2,
      fillOpacity: 0.95
    }),
    onEachFeature: (f, layer) => {
      layer.bindTooltip(f.properties.name || 'Police Station', { direction: 'top' });
    }
  });

  // ── INDUSTRIAL ──────────────────────────────────────────────────
  const industrialLayer = L.geoJSON(industrialFeatures, {
    style: { color: '#9ca3af', fillColor: '#6b7280', weight: 1.5, fillOpacity: 0.55 }
  });

  // ── TOP 5 ───────────────────────────────────────────────────────
  // Fused circle+number into a single divIcon so the yellow disc and the
  // "#N" label are one visual unit (they stay in lockstep at any zoom).
  // featureGroup (not layerGroup) so we can call bringToFront() below.
  const top5Layer = L.featureGroup();
  (TOP5 || []).forEach(c => {
    const marker = L.marker([c.lat, c.lng], {
      icon: L.divIcon({
        className: 'top5-marker',
        html: `<div class="top5-pin">${c.rank}</div>`,
        iconSize: [30, 30],
        iconAnchor: [15, 15]
      }),
      riseOnHover: true
    });
    marker.bindTooltip(
      `<strong style="color:#facc15">Batcave #${c.rank}</strong><br>BSI: ${c.bsi}`,
      tooltipOptions
    );
    top5Layer.addLayer(marker);
  });

  // ── LEGEND UPDATES ──────────────────────────────────────────────
  function updateLegend(activeMode) {
    const ids = ['legend-bsi', 'legend-crime', 'legend-pop', 'legend-police', 'legend-industrial'];
    ids.forEach(id => document.getElementById(id)?.classList.add('hidden'));

    const show = {
      bsi:        ['legend-bsi'],
      crime:      ['legend-crime'],
      pop:        ['legend-pop'],
      police:     ['legend-police'],
      industrial: ['legend-industrial'],
      top5:       ['legend-bsi'],
      all:        ['legend-bsi', 'legend-police', 'legend-industrial'],
    };
    (show[activeMode] || ['legend-bsi']).forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.remove('hidden');
    });
  }

  // ── SOLO MODE SYSTEM ────────────────────────────────────────────
  // Each mode declares which layers should be visible. The dispatcher
  // below diffs against the current on-map set, so layers are reliably
  // added/removed via the map instance itself (avoids any .remove()
  // ambiguity when a layer's internal _map ref gets out of sync).
  const ALL_LAYERS = {
    hexBSI: hexLayerBSI,
    hexCrime: hexLayerCrime,
    hexPop: hexLayerPop,
    police: policeLayer,
    industrial: industrialLayer,
    top5: top5Layer,
    boundary: boundaryLayer,
  };

  const MODE_LAYERS = {
    bsi:        ['hexBSI', 'boundary'],
    crime:      ['hexCrime', 'boundary'],
    pop:        ['hexPop', 'boundary'],
    police:     ['boundary', 'police'],
    industrial: ['industrial', 'boundary'],
    top5:       ['hexBSI', 'boundary', 'top5'],
    all:        ['hexBSI', 'industrial', 'boundary', 'police', 'top5'],
  };

  function applyMode(mode) {
    const wanted = new Set(MODE_LAYERS[mode] || MODE_LAYERS.bsi);

    // Hex opacity depends on mode (dimmed under Top 5 so markers read clearly).
    if (wanted.has('hexBSI')) {
      hexLayerBSI.setStyle({ fillOpacity: mode === 'top5' ? 0.18 : 0.75 });
    }

    Object.entries(ALL_LAYERS).forEach(([key, layer]) => {
      const shouldBeOn = wanted.has(key);
      const isOn = map.hasLayer(layer);
      if (shouldBeOn && !isOn) layer.addTo(map);
      else if (!shouldBeOn && isOn) map.removeLayer(layer);
    });

    // Top 5 markers must render above the hex + industrial polygons.
    if (wanted.has('top5')) top5Layer.bringToFront();
    // Police markers must also render above polygons.
    if (wanted.has('police')) policeLayer.bringToFront();
  }

  const MODES = {
    bsi:        () => applyMode('bsi'),
    crime:      () => applyMode('crime'),
    pop:        () => applyMode('pop'),
    police:     () => applyMode('police'),
    industrial: () => applyMode('industrial'),
    top5:       () => applyMode('top5'),
    all:        () => applyMode('all'),
  };

  let activeMode = 'bsi';

  function setMode(mode) {
    if (!MODES[mode]) return;
    MODES[mode]();
    updateLegend(mode);
    activeMode = mode;
  }

  function resetMap() {
    setMode('bsi');
    const bounds = boundaryLayer.getBounds();
    if (bounds.isValid()) {
      map.flyToBounds(bounds, { padding: [30, 30], duration: 1.2 });
    }
  }

  // ── INITIAL VIEW ────────────────────────────────────────────────
  function setInitialView() {
    map.invalidateSize();
    setMode('bsi');
    const bounds = boundaryLayer.getBounds();
    if (bounds.isValid()) {
      map.flyToBounds(bounds, { padding: [30, 30], duration: 0.8 });
    }
  }

  if (document.readyState === 'complete') setInitialView();
  else window.addEventListener('load', setInitialView);

  // ── FLY-TO HELPERS ──────────────────────────────────────────────
  function flyToCandidate(rank, zoom = 15) {
    const c = (TOP5 || []).find(x => x.rank === rank);
    if (!c) return;
    setMode('top5');
    map.flyTo([c.lat, c.lng], zoom, { duration: 1.5 });
  }

  function flyToTop5() {
    const coords = (TOP5 || []).map(c => [c.lat, c.lng]);
    if (!coords.length) return;
    const bounds = L.latLngBounds(coords);
    map.flyToBounds(bounds, { padding: [80, 80], duration: 1.2, maxZoom: 14 });
  }

  function flyToCity() {
    const bounds = boundaryLayer.getBounds();
    if (bounds.isValid()) {
      map.flyToBounds(bounds, { padding: [30, 30], duration: 1.0 });
    }
  }

  // ── EXPOSE ──────────────────────────────────────────────────────
  window.bsiMap = {
    instance: map,
    setMode,
    resetMap,
    flyToCandidate,
    flyToTop5,
    flyToCity,
    layers: {
      hexBSI:      { layer: hexLayerBSI },
      hexCrime:    { layer: hexLayerCrime },
      police:      { layer: policeLayer },
      industrial:  { layer: industrialLayer },
      top5:        { layer: top5Layer },
      boundary:    { layer: boundaryLayer },
    },
  };
}());
