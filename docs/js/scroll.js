/* scroll.js — IntersectionObserver-driven narrative + map sync
   Also attaches layer button click handlers                        */

(function () {
  'use strict';

  const narrative = document.getElementById('narrative');
  const mapPanel  = document.getElementById('map-panel');
  const progressBar = document.getElementById('scroll-bar');

  // ── RESPONSIVE LAYOUT ───────────────────────────────────────────
  function applyLayout() {
    if (window.innerWidth <= 900) {
      mapPanel.style.position = 'relative';
      mapPanel.style.width = '100%';
      mapPanel.style.height = '50vh';
      narrative.style.width = '100%';
      narrative.style.borderRight = 'none';
    } else {
      mapPanel.style.position = '';
      mapPanel.style.width = '';
      mapPanel.style.height = '';
      narrative.style.width = '';
      narrative.style.borderRight = '';
    }
    window.bsiMap?.instance?.invalidateSize();
  }
  window.addEventListener('resize', applyLayout);
  applyLayout();

  // ── SCROLL PROGRESS ─────────────────────────────────────────────
  function updateProgress() {
    const st = window.scrollY || document.documentElement.scrollTop;
    const total = document.documentElement.scrollHeight - window.innerHeight;
    progressBar.style.width = (total > 0 ? (st / total) * 100 : 0) + '%';
  }
  window.addEventListener('scroll', updateProgress);

  // ── BUTTON SYNC ─────────────────────────────────────────────────
  const buttons = document.querySelectorAll('.layer-btn');
  const btnLayerMap = {};
  buttons.forEach(btn => {
    const key = btn.getAttribute('data-layer');
    btnLayerMap[key] = btn;
  });

  function syncButtons(activeKey) {
    buttons.forEach(btn => btn.classList.toggle('active', btn.getAttribute('data-layer') === activeKey));
  }

  // ── LAYER BUTTON HANDLERS ───────────────────────────────────────
  // Once the user manually picks a layer, the IntersectionObserver
  // is not allowed to silently override it with the default overview
  // mode. The narrative tour (top5-all, fly) still takes control when
  // the user scrolls into the candidate chapters.
  let userOverride = false;

  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const key = btn.getAttribute('data-layer');
      userOverride = true;
      syncButtons(key);
      if (!window.bsiMap) return;
      window.bsiMap.setMode(key);
      // Re-frame the camera so each toggle lands on a sensible view,
      // instead of leaving the user wherever the last fly-to left them.
      if (key === 'top5') {
        window.bsiMap.flyToTop5();
      } else {
        window.bsiMap.flyToCity();
      }
    });
  });

  // ── CHAPTER TRIGGERS ──────────────────────────────────────────
  const chapters = document.querySelectorAll('.chapter');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const section = entry.target;
        section.classList.add('is-visible');
        const mapMode = section.getAttribute('data-map');
        handleMapMode(mapMode, section);
      }
    });
  }, { threshold: 0.4 });

  chapters.forEach(sec => observer.observe(sec));

  function handleMapMode(mode, section) {
    if (!window.bsiMap) return;
    // Respect manual selection: don't revert the user's choice just
    // because they scrolled past an "overview" chapter.
    if (userOverride && mode === 'overview') return;

    switch (mode) {
      case 'overview':
        window.bsiMap.setMode('bsi');
        syncButtons('bsi');
        break;
      case 'top5-all':
        userOverride = false;
        window.bsiMap.setMode('top5');
        window.bsiMap.flyToTop5();
        syncButtons('top5');
        break;
      case 'fly': {
        userOverride = false;
        const rank = parseInt(section.getAttribute('data-rank'), 10);
        if (rank) {
          window.bsiMap.setMode('top5');
          syncButtons('top5');
          window.bsiMap.flyToCandidate(rank, 15);
        }
        break;
      }
      default:
        window.bsiMap.setMode('bsi');
        syncButtons('bsi');
    }
  }

  // ── INITIAL STATE ───────────────────────────────────────────────
  syncButtons('bsi');
}());
