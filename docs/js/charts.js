/* charts.js — Chart.js initialisation for all charts
   Weights bar chart + top-5 candidate component mini bar charts   */

(function () {
  'use strict';

  Chart.defaults.color = '#9194a3';
  Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
  Chart.defaults.font.size = 11;

  const accent = '#facc15';

  // ── 1. BSI WEIGHTS BAR CHART ────────────────────────────────────
  const weightsCtx = document.getElementById('chart-weights');
  if (weightsCtx) {
    new Chart(weightsCtx, {
      type: 'bar',
      data: {
        labels: [
          STATS.weight_labels?.crime_hotspot || 'Crime',
          STATS.weight_labels?.pop_density || 'Pop Density',
          STATS.weight_labels?.police_proximity || 'Police',
          STATS.weight_labels?.industrial || 'Industrial',
        ],
        datasets: [{
          data: [
            STATS.bsi_formula?.crime_hotspot || 0.35,
            STATS.bsi_formula?.pop_density || 0.30,
            STATS.bsi_formula?.police_proximity || 0.20,
            STATS.bsi_formula?.industrial || 0.15,
          ],
          backgroundColor: [
            STATS.weight_colors?.crime_hotspot || '#ef4444',
            STATS.weight_colors?.pop_density || '#f59e0b',
            STATS.weight_colors?.police_proximity || '#3b82f6',
            STATS.weight_colors?.industrial || '#22c55e',
          ],
          borderRadius: 6,
          borderSkipped: false,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, max: 0.5, ticks: { stepSize: 0.1, callback: v => (v * 100) + '%' } },
          x: { grid: { display: false } },
        },
      }
    });
  }

  // ── 2. TOP 5 CANDIDATE MINI CHARTS + METADATA ───────────────────
  const labels = [
    STATS.weight_labels?.crime_hotspot || 'Crime',
    STATS.weight_labels?.pop_density || 'Pop Density',
    STATS.weight_labels?.police_proximity || 'Police',
    STATS.weight_labels?.industrial || 'Industrial',
  ];
  const bg = [
    STATS.weight_colors?.crime_hotspot || '#ef4444',
    STATS.weight_colors?.pop_density || '#f59e0b',
    STATS.weight_colors?.police_proximity || '#3b82f6',
    STATS.weight_colors?.industrial || '#22c55e',
  ];

  (TOP5 || []).forEach(c => {
    // inject metadata text into corresponding card
    const meta = document.getElementById('meta-' + c.rank);
    if (meta) {
      const hotspotBadge = c.hotspot === 'Hot Spot'
        ? '<span style="color:#ef4444;font-weight:700">Hot Spot</span>'
        : (c.hotspot === 'Cold Spot'
            ? '<span style="color:#3b82f6;font-weight:700">Cold Spot</span>'
            : 'Not Significant');
      meta.innerHTML = `
        <span class="bsi-val">BSI ${c.bsi}</span> &middot;
        ${hotspotBadge} &middot;
        ${Math.round(c.police_dist_m)} m to police &middot;
        ${Math.round(c.pop_density_km2)} /km²
      `;
    }

    // build mini radar bar chart
    const ctx = document.getElementById('chart-cand-' + c.rank);
    if (!ctx) return;
    new Chart(ctx, {
      type: 'bar',
      data: {
        labels, datasets: [{
          data: [c.crime_score, c.pop_score, c.police_score, c.industrial_score],
          backgroundColor: bg,
          borderRadius: 4,
          borderSkipped: false,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: {
          callbacks: {
            title: items => items?.[0]?.label || '',
            label: item => 'Normalized score: ' + (item.raw?.toFixed ? item.raw.toFixed(3) : item.raw)
          }
        }},
        scales: {
          y: { beginAtZero: true, max: 1.05, ticks: { stepSize: 0.25 } },
          x: { grid: { display: false }, ticks: { font: { size: 10 } } },
        },
      }
    });
  });

  // ── 3. POPULATE HERO STATS ──────────────────────────────────────
  function animateNumber(el, target, dur = 1200) {
    const start = performance.now();
    const from = 0;
    (function step(now) {
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(from + (target - from) * eased).toLocaleString();
      if (t < 1) requestAnimationFrame(step);
    })(start);
  }

  document.addEventListener('DOMContentLoaded', () => {
    const crimes = document.getElementById('stat-crimes');
    const hexes  = document.getElementById('stat-hexes');
    const hs     = document.getElementById('stat-hotspots');
    if (crimes && typeof STATS.total_crimes === 'number') animateNumber(crimes, STATS.total_crimes);
    if (hexes  && typeof STATS.total_hexes === 'number')  animateNumber(hexes,  STATS.total_hexes);
    if (hs     && typeof STATS.hot_spots === 'number')    animateNumber(hs,     STATS.hot_spots);
  });
}());
