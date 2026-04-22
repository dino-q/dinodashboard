/* ==========================================================================
   DinoDashboard — Client-side interactions
   ========================================================================== */

// ---------- Tag iOS / iPadOS early so CSS can target WebKit-mobile specifically ----------
// @supports (-webkit-touch-callout: none) misses modern iPadOS (presents itself as macOS),
// so detect explicitly: UA for iPhone/iPad/iPod, plus MacIntel + touch points for iPadOS.
(() => {
  const ua = navigator.userAgent || '';
  const isIOS = /iPad|iPhone|iPod/.test(ua) ||
                (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  if (isIOS) document.documentElement.classList.add('is-ios');
})();


// ---------- Always land at the top on navigation / login redirect ----------
// iOS Safari restores scroll position + CSS scroll-snap can latch to the
// Featured page mid-load, so explicitly reset unless the URL has a hash.
if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
function _resetScroll() {
  if (location.hash) return;
  const sc = document.getElementById('snap-container');
  if (sc) sc.scrollTop = 0;
  window.scrollTo(0, 0);
}
document.addEventListener('DOMContentLoaded', _resetScroll);
window.addEventListener('pageshow', _resetScroll);   // also handles bfcache restores


// ---------- Lucide icon init ----------
document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
});


// ---------- Hero particle sphere (Antigravity-style, follows cursor / finger) ----------
(() => {
  const hero = document.querySelector('.site-hero');
  const container = hero && hero.querySelector('.hero-spotlight');
  if (!hero || !container) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  container.innerHTML = '';
  const canvas = document.createElement('canvas');
  container.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  const DPR = Math.min(window.devicePixelRatio || 1, 2);

  let W = 0, H = 0;
  function resize() {
    const r = hero.getBoundingClientRect();
    W = r.width; H = r.height;
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  resize();
  window.addEventListener('resize', resize);

  const isMobile = window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
  // Mobile bumped to offset the lower density caused by the oversized sphere radius below.
  const N = isMobile ? 380 : 650;
  const PALETTE = [
    [129, 140, 248],  // indigo-400
    [99,  102, 241],  // indigo-500
    [167, 139, 250],  // violet-400
    [139, 92,  246],  // violet-500
    [56,  189, 248],  // sky-400
    [96,  165, 250],  // blue-400
  ];
  const ACCENT = [
    [244, 63,  94],   // rose-500
    [251, 146, 60],   // orange-400
    [236, 72,  153],  // pink-500
  ];

  const ANCHOR_RATIO = 0.25;   // fraction of particles that stay on the sphere to keep its outline
  const particles = [];
  for (let i = 0; i < N; i++) {
    const u = Math.random();
    const v = Math.random();
    const theta = 2 * Math.PI * u;
    const phi = Math.acos(2 * v - 1);
    const rJitter = 0.88 + Math.random() * 0.22;
    const isAccent = Math.random() < 0.1;
    const pool = isAccent ? ACCENT : PALETTE;
    const color = pool[(Math.random() * pool.length) | 0];
    const isAnchor = Math.random() < ANCHOR_RATIO;
    particles.push({
      theta, phi, rJitter,
      size: 0.9 + Math.random() * 1.9,
      r: color[0], g: color[1], b: color[2],
      isAnchor,
      pull: isAnchor ? 0 : (0.55 + Math.random() * 0.45),
      jitterX: (Math.random() - 0.5) * 80,
      jitterY: (Math.random() - 0.5) * 80,
      // Lock cycle — each free particle rotates in and out of the cursor's control set
      locked: false,
      ctrl: 0,
      holdUntil: 0,
      coolUntil: 0,
      sx: 0, sy: 0, sz: 0, sc: 1,  // cached sphere projection
    });
  }

  // Cursor/finger in hero-local coords. null = no active input → fall back to sphere centre.
  let tx = null, ty = null;
  let mx = null, my = null;

  const setTarget = (clientX, clientY) => {
    const rect = hero.getBoundingClientRect();
    tx = clientX - rect.left;
    ty = clientY - rect.top;
  };
  const clearTarget = () => { tx = null; ty = null; };

  hero.addEventListener('mousemove',  (e) => setTarget(e.clientX, e.clientY), { passive: true });
  hero.addEventListener('mouseleave', clearTarget, { passive: true });
  hero.addEventListener('touchstart', (e) => {
    if (e.touches[0]) setTarget(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  hero.addEventListener('touchmove', (e) => {
    if (e.touches[0]) setTarget(e.touches[0].clientX, e.touches[0].clientY);
  }, { passive: true });
  hero.addEventListener('touchend', clearTarget, { passive: true });

  let yaw = 0, pitch = 0, last = 0;

  const frame = (now) => {
    const dt = Math.min(50, last ? now - last : 16) / 1000;
    last = now;

    // Sphere centre — desktop: slightly right of middle; mobile: dead centre behind the text.
    const sphereX = W / 2 + (isMobile ? 0 : W * 0.07);
    const sphereY = H / 2;

    const aimX = tx == null ? sphereX : tx;
    const aimY = ty == null ? sphereY : ty;
    if (mx == null) { mx = sphereX; my = sphereY; }
    mx += (aimX - mx) * 0.12;
    my += (aimY - my) * 0.12;

    yaw   += dt * 0.35;
    pitch += dt * 0.1;
    const sinY = Math.sin(yaw),   cosY = Math.cos(yaw);
    const sinP = Math.sin(pitch), cosP = Math.cos(pitch);

    const R = Math.min(W, H) * (isMobile ? 0.88 : 0.32);
    const persp = R * 2.6;

    // Cursor reach — inside sphere: wide; outside: shrinks so the eligible pool drops.
    const biasDist  = Math.hypot(mx - sphereX, my - sphereY);
    const reach     = Math.max(R * 0.55, R * 2.0 - Math.max(0, biasDist - R) * 0.5);
    const hasInput  = tx != null;

    // Project every particle to its sphere position (cached for the lock pass / draw).
    for (let i = 0; i < N; i++) {
      const p = particles[i];
      const r  = R * p.rJitter;
      const sp = Math.sin(p.phi);
      const x0 = r * sp * Math.cos(p.theta);
      const y0 = r * Math.cos(p.phi);
      const z0 = r * sp * Math.sin(p.theta);
      const x1 = x0 * cosY + z0 * sinY;
      const z1 = -x0 * sinY + z0 * cosY;
      const y2 = y0 * cosP - z1 * sinP;
      const z2 = y0 * sinP + z1 * cosP;
      const scale = persp / (persp + z2);
      p.sx = sphereX + x1 * scale;
      p.sy = sphereY + y2 * scale;
      p.sz = z2;
      p.sc = scale;
    }

    // Mobile only: swarm-churn lock cycle (grab random / release random every frame).
    if (isMobile) {
      const BUDGET = hasInput ? (N * 0.5) | 0 : 0;
      let lockedCount = 0;
      for (let i = 0; i < N; i++) {
        const p = particles[i];
        if (p.locked && now > p.holdUntil) {
          p.locked = false;
          p.coolUntil = now + 220 + Math.random() * 380;
        }
        if (p.locked) lockedCount++;
      }
      if (lockedCount < BUDGET) {
        const startOffset = (Math.random() * N) | 0;
        let picked = 0;
        const need = BUDGET - lockedCount;
        for (let j = 0; j < N && picked < need; j++) {
          const idx = (startOffset + j) % N;
          const p = particles[idx];
          if (p.locked || p.isAnchor || now < p.coolUntil) continue;
          const d = Math.hypot(p.sx - mx, p.sy - my);
          if (d > reach) continue;
          p.locked = true;
          p.holdUntil = now + 320 + Math.random() * 620;
          picked++;
        }
      }
    }

    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';

    for (let i = 0; i < N; i++) {
      const p = particles[i];

      // Desktop: continuous proximity-based influence. Mobile: smoothed lock state.
      let k;
      if (isMobile) {
        const target = p.locked ? 1 : 0;
        p.ctrl += (target - p.ctrl) * 0.18;
        k = p.ctrl * p.pull;
      } else {
        const distP = Math.hypot(p.sx - mx, p.sy - my);
        const influence = Math.pow(Math.max(0, 1 - distP / reach), 1.4);
        k = influence * p.pull;
      }

      const targetPX = mx + p.jitterX;
      const targetPY = my + p.jitterY;
      const px = p.sx + (targetPX - p.sx) * k;
      const py = p.sy + (targetPY - p.sy) * k;

      const z2 = p.sz, scale = p.sc;
      const depthT = (z2 + R) / (2 * R);
      const baseOp = (1 - depthT) * 0.75 + 0.1;
      const op     = Math.min(1, baseOp + (0.85 - baseOp) * k);
      const sz     = Math.max(0.8, p.size * scale * (1 + k * 0.25));

      ctx.fillStyle = `rgba(${p.r},${p.g},${p.b},${op.toFixed(3)})`;
      ctx.beginPath();
      ctx.arc(px, py, sz * 0.65, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.globalCompositeOperation = 'source-over';
    if (_running) _rafId = requestAnimationFrame(frame);
  };

  // Pause when hero is off-screen or tab is hidden — the canvas otherwise eats
  // main-thread budget and makes card clicks / filter swaps feel laggy.
  let _running = false;
  let _rafId = null;
  const startParticles = () => {
    if (_running) return;
    _running = true;
    last = 0;
    _rafId = requestAnimationFrame(frame);
  };
  const stopParticles = () => {
    _running = false;
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
  };

  startParticles();

  if ('IntersectionObserver' in window) {
    const snapRoot = document.getElementById('snap-container');
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) startParticles();
        else stopParticles();
      }
    }, { root: snapRoot || null, threshold: 0 });
    io.observe(hero);
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopParticles();
    else {
      // Only resume if hero is still in view
      const r = hero.getBoundingClientRect();
      const inView = r.bottom > 0 && r.top < (window.innerHeight || document.documentElement.clientHeight);
      if (inView) startParticles();
    }
  });
})();

// Re-init icons after HTMX swaps
document.body.addEventListener('htmx:afterSwap', () => {
  lucide.createIcons();
});


// ---------- Preserve scroll position across grid swaps ----------
// When HTMX swaps #tool-grid (star toggle, filter change, reorder, etc.) + OOB regions (featured,
// toc), the browser's scroll-snap / layout passes can fling snap-container.scrollTop back to 0.
// Capture before and LOCK position for ~240ms via rAF to beat any auto-adjustment. The #tool-grid
// itself has a min-height (see CSS) so short result sets still fill enough vertical space to keep
// the user's scroll position valid — avoiding the browser clamp that would force 所有作品 into view.
let _preservedScrollTop = null;
let _scrollLockId = 0;         // bumps every afterSwap so older lock loops exit
document.body.addEventListener('htmx:beforeSwap', (e) => {
  const tgt = e.detail && e.detail.target;
  if (tgt && tgt.id === 'tool-grid') {
    const sc = document.getElementById('snap-container');
    if (sc) _preservedScrollTop = sc.scrollTop;
  }
});
document.body.addEventListener('htmx:afterSwap', (e) => {
  if (_preservedScrollTop == null) return;
  const tgt = e.detail && e.detail.target;
  if (!tgt || tgt.id !== 'tool-grid') return;
  const sc = document.getElementById('snap-container');
  if (!sc) { _preservedScrollTop = null; return; }
  const target = _preservedScrollTop;
  sc.scrollTop = target;

  const myId = ++_scrollLockId;   // invalidates any older lock loop still running
  let ticks = 0;
  const lock = () => {
    if (myId !== _scrollLockId) return;           // newer swap took over
    if (sc.scrollTop !== target) sc.scrollTop = target;
    if (++ticks < 15) requestAnimationFrame(lock);
    else if (myId === _scrollLockId) _preservedScrollTop = null;
  };
  requestAnimationFrame(lock);
});


// ---------- Full-page snap (hero + featured) + back to top ----------
(() => {
  const container = document.getElementById('snap-container');
  const btn = document.getElementById('back-to-top');
  if (!container) return;

  const snapCount = container.querySelectorAll('.snap-page:not(.projects-section)').length;
  let currentPage = 0;
  let isAnimating = false;

  // Read --zoom from CSS so snap math matches the compensated snap-page height
  function zoomFactor() {
    const v = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--zoom'));
    return (v && v > 0) ? v : 1;
  }
  function pageH() { return window.innerHeight / zoomFactor(); }
  function maxSnapPage() { return snapCount - 1; }
  function inSnapZone() { return currentPage <= maxSnapPage(); }

  function goToPage(idx) {
    if (isAnimating) return;
    currentPage = idx;
    isAnimating = true;
    container.scrollTo({ top: idx * pageH(), behavior: 'smooth' });
    setTimeout(() => { isAnimating = false; }, 500);
  }

  // Let inner scrollables (e.g. .cmd-list) consume the wheel before we snap-intercept
  function innerCanScroll(target, deltaY) {
    let el = target;
    while (el && el !== container) {
      const cs = getComputedStyle(el);
      if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll')
          && el.scrollHeight > el.clientHeight + 1) {
        if (deltaY > 0 && el.scrollTop + el.clientHeight < el.scrollHeight - 1) return true;
        if (deltaY < 0 && el.scrollTop > 0) return true;
      }
      el = el.parentElement;
    }
    return false;
  }

  // Wheel: intercept in snap zone, let through in free zone
  container.addEventListener('wheel', (e) => {
    // Don't hijack browser zoom (Ctrl/Cmd + wheel) or pinch-zoom trackpad gestures
    if (e.ctrlKey || e.metaKey) return;

    if (isAnimating) { e.preventDefault(); return; }

    // Inner scrollable can still absorb — don't hijack
    if (innerCanScroll(e.target, e.deltaY)) return;

    const st = container.scrollTop;
    const threshold = snapCount * pageH();

    // Currently in snap zone
    if (st < threshold - 5) {
      e.preventDefault();
      if (e.deltaY > 0) {
        // Scroll down
        if (currentPage < maxSnapPage()) {
          goToPage(currentPage + 1);
        } else {
          // Jump to projects (exit snap zone)
          currentPage = snapCount;
          isAnimating = true;
          container.scrollTo({ top: threshold, behavior: 'smooth' });
          setTimeout(() => { isAnimating = false; }, 500);
        }
      } else if (e.deltaY < 0 && currentPage > 0) {
        goToPage(currentPage - 1);
      }
      return;
    }

    // In free zone, scrolling up back into snap zone
    if (e.deltaY < 0 && st <= threshold + 10) {
      e.preventDefault();
      currentPage = maxSnapPage();
      goToPage(currentPage);
    }
    // Otherwise: free scroll, don't intercept
  }, { passive: false });

  // Track scroll position for back-to-top + TOC highlight
  const tocLinks = container.querySelectorAll('.toc-link');
  const groups = container.querySelectorAll('.project-group[id]');
  let tocTicking = false;

  container.addEventListener('scroll', () => {
    if (btn) btn.classList.toggle('visible', container.scrollTop > 400);

    // TOC active state — pick the group whose top is closest to (but not below)
    // a small threshold near the viewport top. Works regardless of group height
    // (important for list mode where groups are compact).
    if (tocLinks.length && !tocTicking && !tocClickLock) {
      tocTicking = true;
      requestAnimationFrame(() => {
        const preferLine = 80; // px below viewport top — what "currently reading" means
        let activeGroup = null;

        // Near-bottom override: if the user has scrolled to (or very close to) the
        // end of the container, force the last group active. Otherwise a short
        // final group whose heading never crosses preferLine gets skipped and the
        // previous group stays highlighted. (This used to bite 系統; now 其他.)
        const maxScroll = container.scrollHeight - container.clientHeight;
        const nearBottom = maxScroll > 0 && container.scrollTop >= maxScroll - 4;
        if (nearBottom && groups.length) {
          activeGroup = groups[groups.length - 1];
        } else {
          let bestDist = Infinity;
          groups.forEach(g => {
            const top = g.getBoundingClientRect().top;
            if (top > preferLine) return; // heading not yet reached
            const dist = preferLine - top; // 0 when heading is at preferLine; grows as it scrolls past
            if (dist < bestDist) { bestDist = dist; activeGroup = g; }
          });
        }

        const activeId = activeGroup ? activeGroup.id : '';
        tocLinks.forEach(link => {
          link.classList.toggle('active', link.getAttribute('href') === '#' + activeId);
        });
        tocTicking = false;
      });
    }
  }, { passive: true });

  // TOC click — scroll within snap container.
  // body has `zoom: 0.95`; getBoundingClientRect returns post-zoom visual px,
  // but scrollTop is in pre-zoom CSS px. Divide the rect delta by the zoom
  // factor to match scrollTop's unit, otherwise clicks undershoot.
  // Also highlight the clicked link IMMEDIATELY and lock out the scroll-driven
  // highlight for ~600ms so the smooth-scroll doesn't briefly flash the wrong item.
  let tocClickLock = false;
  tocLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      const target = container.querySelector(link.getAttribute('href'));
      if (!target) return;
      tocLinks.forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      tocClickLock = true;
      const cRect = container.getBoundingClientRect();
      const tRect = target.getBoundingClientRect();
      const top = container.scrollTop + (tRect.top - cRect.top) / zoomFactor() - 20;
      container.scrollTo({ top, behavior: 'smooth' });
      setTimeout(() => { tocClickLock = false; }, 600);
    });
  });

  // Back to top
  if (btn) {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      currentPage = 0;
      isAnimating = true;
      container.scrollTo({ top: 0, behavior: 'smooth' });
      setTimeout(() => { isAnimating = false; }, 500);
    });
  }

  // Jump to search: scroll to projects area (out of snap zone) and focus search
  window.jumpToSearch = function() {
    const input = document.querySelector('.search-input');
    if (!input) return;
    currentPage = snapCount;              // mark as exited snap zone so wheel handler doesn't drag back
    isAnimating = true;
    container.scrollTo({ top: snapCount * pageH(), behavior: 'smooth' });
    setTimeout(() => {
      isAnimating = false;
      input.focus({ preventScroll: true });  // don't let focus auto-scroll and undo our alignment
    }, 500);
  };
})();


// ---------- Theme toggle ----------
function getTheme() {
  return localStorage.getItem('dino-theme') || 'dark';
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('theme-icon');
  if (icon) {
    icon.setAttribute('data-lucide', theme === 'dark' ? 'moon' : 'sun');
    lucide.createIcons();
  }
}

function toggleTheme() {
  const current = getTheme();
  const next = current === 'dark' ? 'light' : 'dark';
  localStorage.setItem('dino-theme', next);
  applyTheme(next);
}

// Apply saved theme on load
applyTheme(getTheme());


// ---------- Language toggle ----------
function getLang() {
  return localStorage.getItem('dino-lang') || 'zh';
}

function applyLang(lang) {
  document.documentElement.setAttribute('data-lang', lang);
  // Update search placeholder
  const searchInput = document.querySelector('.search-input');
  if (searchInput) {
    searchInput.placeholder = lang === 'zh' ? '搜尋...' : 'Search...';
  }
}

function toggleLang() {
  const current = getLang();
  const next = current === 'zh' ? 'en' : 'zh';
  localStorage.setItem('dino-lang', next);
  applyLang(next);
}

// Apply saved language on load
applyLang(getLang());


// ---------- Collapsible category groups (click label to fold; double-click to fold all) ----------
(() => {
  const container = document.getElementById('snap-container');
  if (!container) return;
  let clickTimer = null;

  container.addEventListener('click', (e) => {
    const label = e.target.closest('.group-label');
    if (!label) return;
    // Ignore clicks on any interactive element inside the label (future-proof)
    if (e.target.closest('a, button')) return;
    const group = label.closest('.project-group');
    if (!group) return;

    if (clickTimer) {
      // Double-click: toggle ALL groups
      clearTimeout(clickTimer);
      clickTimer = null;
      const groups = document.querySelectorAll('.project-group');
      const anyExpanded = Array.from(groups).some(g => !g.classList.contains('collapsed'));
      groups.forEach(g => g.classList.toggle('collapsed', anyExpanded));
    } else {
      // Single-click: wait to see if becomes double-click
      clickTimer = setTimeout(() => {
        clickTimer = null;
        group.classList.toggle('collapsed');
      }, 220);
    }
  });
})();


// ---------- View mode toggle (cards / list) ----------
function isMobileViewport() {
  return window.matchMedia && window.matchMedia('(max-width: 768px)').matches;
}

function _viewKey() {
  return isMobileViewport() ? 'dino-view-mobile' : 'dino-view';
}

function getViewMode() {
  const saved = localStorage.getItem(_viewKey());
  if (saved) return saved;
  return isMobileViewport() ? 'list' : 'cards';
}

function setViewMode(mode) {
  localStorage.setItem(_viewKey(), mode);
  applyViewMode(mode);
}

function applyViewMode(mode) {
  const grid = document.getElementById('tool-grid');
  if (grid) {
    grid.classList.toggle('view-list', mode === 'list');
    grid.classList.toggle('view-cards', mode !== 'list');
  }
  document.querySelectorAll('.view-toggle-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.view === mode);
  });
}

// Apply on load + after any HTMX grid swap (so re-rendered grid keeps the mode)
applyViewMode(getViewMode());
document.body.addEventListener('htmx:afterSwap', (e) => {
  const tgt = e.detail && e.detail.target;
  if (tgt && tgt.id === 'tool-grid') applyViewMode(getViewMode());
});


// ---------- Smart suggest (translate + tags) ----------
function suggestFromZh() {
  const nameZh = document.getElementById('name_zh')?.value.trim();
  const desc = document.getElementById('description')?.value.trim();
  if (!nameZh && !desc) {
    showToast('Please fill in Chinese name or description first', 'error');
    return;
  }

  const btn = document.querySelector('.btn-suggest');
  const originalHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="suggest-spinner"></span> Loading...';

  const formData = new FormData();
  formData.append('name_zh', nameZh);
  formData.append('description', desc);

  fetch('/api/tool/suggest', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
      // Fill English name if empty or ask to overwrite
      const nameEn = document.getElementById('name');
      if (nameEn && data.name_en) {
        if (!nameEn.value.trim() || confirm('Overwrite English name?')) {
          nameEn.value = data.name_en;
        }
      }
      // Fill tags if empty or ask to overwrite
      const tagsInput = document.getElementById('tags');
      if (tagsInput && data.tags && data.tags.length) {
        const suggested = data.tags.join(', ');
        if (!tagsInput.value.trim()) {
          tagsInput.value = suggested;
        } else {
          // Merge: add new tags that aren't already there
          const existing = tagsInput.value.split(',').map(t => t.trim().toLowerCase());
          const newTags = data.tags.filter(t => !existing.includes(t));
          if (newTags.length) {
            tagsInput.value = tagsInput.value + ', ' + newTags.join(', ');
          }
        }
        showToast(`Suggested ${data.tags.length} tags`);
      }
      if (data.name_en) showToast('Suggested: ' + data.name_en);
    })
    .catch(() => showToast('Suggest failed', 'error'))
    .finally(() => {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
      lucide.createIcons();
    });
}


// ---------- Rolling number animation ----------
(() => {
  const nums = document.querySelectorAll('.stat-num[data-count]');
  if (!nums.length) return;

  nums.forEach(el => {
    const target = parseInt(el.dataset.count, 10) || 0;
    const digits = String(target).split('');
    el.textContent = '';
    el.classList.add('stat-rolling');

    digits.forEach((d, i) => {
      const col = document.createElement('span');
      col.className = 'roll-col';
      const digit = parseInt(d, 10);
      const totalSteps = 10 + digit;
      let strip = '';
      for (let n = 0; n < totalSteps; n++) strip += `<span>${n % 10}</span>`;
      strip += `<span>${d}</span>`;
      col.innerHTML = strip;

      // Start off-screen (no transition), then animate on next frame
      col.style.transition = 'none';
      col.style.transform = 'translateY(0)';
      el.appendChild(col);

      // Left digit faster, right digit rolls longer
      const duration = 2 + i * 0.5;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          col.style.transition = `transform ${duration}s cubic-bezier(0.22, 1, 0.36, 1)`;
          // iOS only: measure the real span height (px) because flex-stretched
          // roll-col resolves "100%" to a different value on WebKit-mobile. All
          // other platforms keep the original percentage path — zero change.
          if (document.documentElement.classList.contains('is-ios')) {
            const firstSpan = col.firstElementChild;
            const stepPx = firstSpan ? firstSpan.getBoundingClientRect().height : 0;
            col.style.transform = stepPx > 0
              ? `translateY(-${totalSteps * stepPx}px)`
              : `translateY(-${totalSteps * 100}%)`;
          } else {
            col.style.transform = `translateY(-${totalSteps * 100}%)`;
          }
        });
      });
    });
  });
})();




// ---------- New category toggle ----------
function toggleNewCategory(select) {
  const fields = document.getElementById('new-category-fields');
  if (fields) fields.style.display = select.value === '__new__' ? 'flex' : 'none';
}


// ---------- Icon preview ----------
function updateIconPreview(name) {
  const preview = document.getElementById('icon-preview');
  if (!preview) return;
  preview.innerHTML = `<i data-lucide="${name || 'box'}"></i>`;
  lucide.createIcons();
}


// ---------- Toast notifications ----------
document.body.addEventListener('showToast', (e) => {
  const msg = typeof e.detail === 'string' ? e.detail : (e.detail?.value || e.detail);
  showToast(msg);
});

// Open modal when auto-tag endpoint returned the cloud-info partial
document.body.addEventListener('openAutoTagModal', () => {
  openModal();
});

function showToast(msg, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'toastOut .3s ease-out forwards';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}


// ---------- Copy to clipboard ----------
function copyCmd(btn, cmd) {
  navigator.clipboard.writeText(cmd).then(() => {
    btn.classList.add('copied');
    showToast('Copied!');
    setTimeout(() => btn.classList.remove('copied'), 2000);
  }).catch(() => {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = cmd;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    btn.classList.add('copied');
    showToast('Copied!');
    setTimeout(() => btn.classList.remove('copied'), 2000);
  });
}


// ---------- Modal ----------
function openModal() {
  document.getElementById('modal-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
  // Re-init icons + auto-focus first input (a11y: focus-management)
  setTimeout(() => {
    lucide.createIcons();
    const first = document.querySelector('#modal-content input[autofocus], #modal-content input:first-of-type');
    if (first) first.focus();
  }, 100);
}

function closeModal() {
  // If the screenshots manager was active, reap this-session uploads.
  // - Save path sets window.__smSavedOk = true; we keep any object_key still referenced in state.items.
  // - Cancel path has no flag; all session uploads get purged from Storage.
  if (window.__SM__) smMaybeCleanup();
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

function smMaybeCleanup() {
  const state = window.__SM__;
  if (!state || !state.sessionUploads || !state.sessionUploads.length) {
    window.__smSavedOk = false;
    return;
  }
  let toDelete;
  if (window.__smSavedOk) {
    // Save succeeded — only purge uploads the user deleted from state before saving.
    const kept = new Set(state.items.map(it => it.object_key).filter(Boolean));
    toDelete = state.sessionUploads.filter(k => !kept.has(k));
  } else {
    // Cancel / ESC / outside-click — purge every this-session upload.
    toDelete = state.sessionUploads.slice();
  }
  state.sessionUploads = [];
  window.__smSavedOk = false;
  if (!toDelete.length) return;
  // Fire-and-forget; `keepalive` lets it survive if tab navigates away.
  fetch('/api/storage/screenshots/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keys: toDelete }),
    keepalive: true,
  }).catch(() => {});
}

function isEditMode() {
  return !!document.querySelector('#modal-content .tool-form');
}

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const overlay = document.getElementById('modal-overlay');
    if (overlay.classList.contains('open') && !isEditMode()) {
      closeModal();
    }
  }
});

// Click outside modal → close, but only in view (detail) mode, not when editing
document.addEventListener('click', (e) => {
  const overlay = document.getElementById('modal-overlay');
  if (!overlay || !overlay.classList.contains('open')) return;
  if (e.target !== overlay) return;  // only overlay background click (modal-content uses stopPropagation)
  if (isEditMode()) return;          // protect edit state from accidental close
  closeModal();
});

// Submit loading state (a11y: loading-buttons, submit-feedback)
document.body.addEventListener('htmx:beforeRequest', (e) => {
  const btn = e.target.querySelector('#form-submit-btn');
  if (btn) { btn.disabled = true; btn.dataset.origText = btn.innerHTML; btn.innerHTML = '<span class="suggest-spinner"></span>'; }
});
document.body.addEventListener('htmx:afterRequest', (e) => {
  const btn = e.target.querySelector('#form-submit-btn');
  if (btn && btn.dataset.origText) { btn.disabled = false; btn.innerHTML = btn.dataset.origText; }
});

// Modal content loading placeholder — avoids the blank backdrop flash while the
// detail / edit partial is in flight. Fires for any HTMX request that targets
// #modal-content (card click, Edit from card menu, New tool).
document.body.addEventListener('htmx:beforeRequest', (e) => {
  const target = e.detail && e.detail.target;
  if (!target || target.id !== 'modal-content') return;
  target.innerHTML = '<div class="modal-loading"><span class="suggest-spinner"></span></div>';
});


// ---------- Card context menu ----------
function toggleCardMenu(btn) {
  // Close all other menus first
  document.querySelectorAll('.card-menu.open').forEach(m => {
    if (m !== btn.nextElementSibling) m.classList.remove('open');
  });
  const menu = btn.nextElementSibling;
  menu.classList.toggle('open');
}

// Close menus when clicking outside
document.addEventListener('click', (e) => {
  if (!e.target.closest('.card-menu-wrap')) {
    document.querySelectorAll('.card-menu.open').forEach(m => m.classList.remove('open'));
  }
  if (!e.target.closest('.filter-menu-wrap')) {
    const fm = document.getElementById('filter-menu');
    if (fm) fm.classList.remove('open');
  }
});

// ---------- Filter menu (status + has_external/has_notion/has_github) ----------
function toggleFilterMenu(e) {
  if (e) e.stopPropagation();
  const menu = document.getElementById('filter-menu');
  if (menu) menu.classList.toggle('open');
}

function resetFilterMenu(btn) {
  const form = btn.closest('.filter-menu');
  if (!form) return;
  // Check "All" radio + uncheck all has_* checkboxes
  const allRadio = form.querySelector('input[name="status"][value=""]');
  if (allRadio) allRadio.checked = true;
  form.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
  // Trigger HTMX request via dispatching change on form
  form.dispatchEvent(new Event('change', { bubbles: true }));
  updateFilterBadge();
}

function updateFilterBadge() {
  const form = document.getElementById('filter-menu');
  const badge = document.getElementById('filter-badge');
  if (!form || !badge) return;
  let count = 0;
  // Non-empty status = 1 active filter
  const status = form.querySelector('input[name="status"]:checked');
  if (status && status.value) count++;
  // Each checked checkbox = 1 active filter
  count += form.querySelectorAll('input[type="checkbox"]:checked').length;
  if (count > 0) {
    badge.textContent = count;
    badge.hidden = false;
  } else {
    badge.hidden = true;
  }
}

// Initial badge state + update on every form change
document.addEventListener('change', (e) => {
  if (e.target.closest('#filter-menu')) updateFilterBadge();
});
document.addEventListener('DOMContentLoaded', updateFilterBadge);


// ---------- Dynamic command rows (form) ----------
let cmdRowCount = 0;

// Count existing rows on modal open
document.body.addEventListener('htmx:afterSwap', () => {
  const container = document.getElementById('commands-container');
  if (container) {
    cmdRowCount = container.querySelectorAll('.cmd-field-row').length;
  }
});

function addCmdRow() {
  const container = document.getElementById('commands-container');
  if (!container) return;

  const idx = cmdRowCount++;
  const row = document.createElement('div');
  row.className = 'cmd-field-row';
  row.dataset.cmdIndex = idx;
  const envTypes = window.__ENV_TYPES__ || ['local', 'docker', 'bat', 'github', 'Google Apps Script'];
  const defaultLabels = { local: 'Local', docker: 'Docker', bat: 'Bat', github: 'GitHub' };
  const envOpts = envTypes.map(e => {
    const label = defaultLabels[e] || e;
    const customAttr = defaultLabels[e] ? '' : ' data-custom="1"';
    return `<option value="${e}"${customAttr}>${label}</option>`;
  }).join('');

  row.innerHTML = `
    <input type="checkbox" name="cmd_pinned_${idx}" class="cmd-pin-checkbox" title="勾選後在卡片懸浮按鈕顯示此指令">
    <span class="drag-handle" draggable="true" title="拖曳排序" aria-label="Drag to reorder">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/>
        <circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/>
      </svg>
    </span>
    <input type="text" name="cmd_label_${idx}" placeholder="Label" class="cmd-label-input">
    <input type="text" name="cmd_cmd_${idx}" placeholder="Command" class="cmd-cmd-input">
    <select name="cmd_env_${idx}" class="cmd-env-select" onchange="handleEnvChange(this)">
      ${envOpts}
      <option value="__custom__">＋ 自訂…</option>
    </select>
    <button type="button" class="btn-icon-sm danger" onclick="removeCmdRow(this)">
      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
        <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
      </svg>
    </button>
  `;
  container.appendChild(row);
}

// ---------- Drag-and-drop reordering for command rows ----------
let draggingCmdRow = null;

document.body.addEventListener('dragstart', (e) => {
  const handle = e.target.closest('.drag-handle');
  if (!handle) return;
  const row = handle.closest('.cmd-field-row');
  if (!row) return;
  draggingCmdRow = row;
  e.dataTransfer.effectAllowed = 'move';
  try { e.dataTransfer.setDragImage(row, 12, 12); } catch (_) {}
  requestAnimationFrame(() => row.classList.add('dragging'));
});

document.body.addEventListener('dragend', () => {
  if (!draggingCmdRow) return;
  draggingCmdRow.classList.remove('dragging');
  draggingCmdRow = null;
  reindexCmdRows();
});

document.body.addEventListener('dragover', (e) => {
  if (!draggingCmdRow) return;
  const container = document.getElementById('commands-container');
  if (!container || !container.contains(e.target)) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  const rows = [...container.querySelectorAll('.cmd-field-row:not(.dragging)')];
  const after = rows.find(r => {
    const rect = r.getBoundingClientRect();
    return e.clientY < rect.top + rect.height / 2;
  });
  if (after == null) {
    if (container.lastElementChild !== draggingCmdRow) container.appendChild(draggingCmdRow);
  } else if (after !== draggingCmdRow.nextSibling) {
    container.insertBefore(draggingCmdRow, after);
  }
});

// ---------- Drag-and-drop reordering for project cards ----------
let draggingCardEl = null;
let draggingCardOriginParent = null;
let draggingCardOriginNext = null;

document.body.addEventListener('dragstart', (e) => {
  const handle = e.target.closest('.card-drag-handle');
  if (!handle) return;
  const card = handle.closest('.project-card');
  if (!card) return;
  draggingCardEl = card;
  draggingCardOriginParent = card.parentElement;
  draggingCardOriginNext = card.nextElementSibling;
  e.dataTransfer.effectAllowed = 'move';
  try { e.dataTransfer.setDragImage(card, 20, 20); } catch (_) {}
  requestAnimationFrame(() => card.classList.add('dragging'));
});

document.body.addEventListener('dragover', (e) => {
  if (!draggingCardEl) return;
  const grid = e.target.closest('.project-grid');
  if (!grid) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';

  const cards = [...grid.querySelectorAll('.project-card:not(.dragging)')];
  if (!cards.length) {
    if (grid.lastElementChild !== draggingCardEl) grid.appendChild(draggingCardEl);
    return;
  }
  // Pick closest card by 2D distance, insert before or after based on cursor side
  let best = null, bestDist = Infinity;
  for (const c of cards) {
    const r = c.getBoundingClientRect();
    const dx = e.clientX - (r.left + r.width / 2);
    const dy = e.clientY - (r.top + r.height / 2);
    const d = dx * dx + dy * dy;
    if (d < bestDist) { bestDist = d; best = c; }
  }
  const r = best.getBoundingClientRect();
  const pastMid = e.clientX > r.left + r.width / 2 || e.clientY > r.bottom;
  const anchor = pastMid ? best.nextElementSibling : best;
  if (anchor == null) {
    if (grid.lastElementChild !== draggingCardEl) grid.appendChild(draggingCardEl);
  } else if (anchor !== draggingCardEl && anchor !== draggingCardEl.nextSibling) {
    grid.insertBefore(draggingCardEl, anchor);
  }
});

document.body.addEventListener('dragend', () => {
  if (!draggingCardEl) return;
  const card = draggingCardEl;
  const originParent = draggingCardOriginParent;
  const originNext = draggingCardOriginNext;
  draggingCardEl = null;
  draggingCardOriginParent = null;
  draggingCardOriginNext = null;
  card.classList.remove('dragging');

  // No movement → no server call
  if (card.parentElement === originParent && card.nextElementSibling === originNext) return;

  const grid = card.closest('.project-grid');
  if (!grid) return;
  const group = grid.closest('.project-group');
  const categoryId = (group && group.id) ? group.id.replace(/^cat-/, '') : '';

  const siblings = [...grid.querySelectorAll('.project-card')];
  const idx = siblings.indexOf(card);
  const beforeCard = siblings[idx + 1] || null;
  const beforeId = beforeCard ? beforeCard.dataset.toolId : '';

  if (window.htmx) {
    htmx.ajax('POST', `/api/tool/${card.dataset.toolId}/reorder`, {
      target: '#tool-grid',
      swap: 'innerHTML',
      values: { category: categoryId, before: beforeId }
    });
  }
});

// Default label per env — auto-filled when the env dropdown changes, but only if the
// label field is empty OR currently holds another known default (so a user-typed
// custom label is preserved). Source of truth: window.__QUICK_INPUTS__ (loaded from
// the server-side quick_inputs presets).
function _qiKnownLabels() {
  const presets = window.__QUICK_INPUTS__ || [];
  const set = new Set();
  presets.forEach(p => { if (p && p.label) set.add(p.label); });
  return set;
}
function _qiLabelForEnv(envValue) {
  const presets = window.__QUICK_INPUTS__ || [];
  const target = (envValue || '').toLowerCase();
  const hit = presets.find(p => p && p.env && p.env.toLowerCase() === target && p.label);
  return hit ? hit.label : '';
}
function _applyDefaultLabel(select) {
  const row = select.closest('.cmd-field-row');
  if (!row) return;
  const labelInput = row.querySelector('.cmd-label-input');
  if (!labelInput) return;
  const defaultLabel = _qiLabelForEnv(select.value);
  if (!defaultLabel) return;
  const current = labelInput.value.trim();
  const isKnownDefault = !current || _qiKnownLabels().has(current);
  if (isKnownDefault) labelInput.value = defaultLabel;
}

// Custom env type: prompt for name, insert option in ALL selects on the form (global sync), select it.
// Right-click on a custom option to remove it.
function handleEnvChange(select) {
  if (select.value !== '__custom__') {
    select.dataset.prev = select.value;
    _applyDefaultLabel(select);
    return;
  }
  const name = (prompt('輸入自訂類型名稱（例：Prod、Notion、API）:') || '').trim();
  if (!name) {
    select.value = select.dataset.prev || 'local';
    return;
  }
  // Preserve original case; only normalize spaces to dashes for safe value
  const value = name.replace(/\s+/g, '-');
  // Add the option to ALL env selects in the form so the new type appears everywhere immediately
  document.querySelectorAll('.cmd-env-select').forEach(sel => {
    if (!sel.querySelector(`option[value="${CSS.escape(value)}"]`)) {
      const customOpt = sel.querySelector('option[value="__custom__"]');
      const newOpt = document.createElement('option');
      newOpt.value = value;
      newOpt.textContent = name;
      newOpt.dataset.custom = '1';
      customOpt.before(newOpt);
    }
  });
  // Keep in-memory global list in sync so new rows (addCmdRow) also include it
  if (window.__ENV_TYPES__ && !window.__ENV_TYPES__.includes(value)) {
    window.__ENV_TYPES__.push(value);
  }
  select.value = value;
  select.dataset.prev = value;
}

// Right-click on a custom option removes it (falls back to local)
document.body.addEventListener('contextmenu', (e) => {
  const select = e.target.closest('.cmd-env-select');
  if (!select) return;
  const current = select.options[select.selectedIndex];
  if (!current || !current.dataset.custom) return;
  e.preventDefault();
  if (confirm(`移除自訂類型「${current.textContent}」？`)) {
    current.remove();
    select.value = 'local';
    select.dataset.prev = 'local';
  }
});

function reindexCmdRows() {
  const container = document.getElementById('commands-container');
  if (!container) return;
  container.querySelectorAll('.cmd-field-row').forEach((row, i) => {
    row.dataset.cmdIndex = i;
    const pin = row.querySelector('.cmd-pin-checkbox');
    const label = row.querySelector('.cmd-label-input');
    const cmd = row.querySelector('.cmd-cmd-input');
    const env = row.querySelector('.cmd-env-select');
    if (pin) pin.name = `cmd_pinned_${i}`;
    if (label) label.name = `cmd_label_${i}`;
    if (cmd) cmd.name = `cmd_cmd_${i}`;
    if (env) env.name = `cmd_env_${i}`;
  });
  cmdRowCount = container.querySelectorAll('.cmd-field-row').length;
}

function removeCmdRow(btn) {
  btn.closest('.cmd-field-row').remove();
  // Re-index remaining rows
  const container = document.getElementById('commands-container');
  if (!container) return;
  container.querySelectorAll('.cmd-field-row').forEach((row, i) => {
    row.dataset.cmdIndex = i;
    const pin = row.querySelector('.cmd-pin-checkbox');
    if (pin) pin.name = `cmd_pinned_${i}`;
    row.querySelector('.cmd-label-input').name = `cmd_label_${i}`;
    row.querySelector('.cmd-cmd-input').name = `cmd_cmd_${i}`;
    row.querySelector('.cmd-env-select').name = `cmd_env_${i}`;
  });
  cmdRowCount = container.querySelectorAll('.cmd-field-row').length;
}


// ---------- Quick Input settings panel ----------
// Secondary overlay (z-index 300) that sits above the edit-form modal. Lets users
// manage env-type dropdown options AND a list of preset {env,label,cmd} quick-fills.
// Adding an env type auto-appends a matching table row (sync). Saving persists both
// lists to tools.yaml and refreshes every cmd-env-select currently on the form.

const QI_DEFAULT_ENV_TYPES = ['local', 'docker', 'bat', 'github', 'Google Apps Script'];
const QI_ENV_DISPLAY_LABELS = {
  local: 'Local', docker: 'Docker', bat: 'Bat', github: 'GitHub',
};
let _qiState = { env_types: [], quick_inputs: [] };

function openQuickInputPanel() {
  const overlay = document.getElementById('quick-input-overlay');
  if (!overlay) return;
  // Escape the edit-modal's backdrop-filter containing-block so position:fixed
  // on the overlay is pinned to the actual viewport.
  if (overlay.parentElement !== document.body) document.body.appendChild(overlay);
  fetch('/api/quick-inputs')
    .then(r => r.json())
    .then(data => {
      _qiState.env_types = Array.isArray(data.env_types) ? [...data.env_types] : [];
      // Include any env types the user just added via the form's "+ 自訂…" that
      // haven't been persisted yet — otherwise they'd be missing from the table.
      (window.__ENV_TYPES__ || []).forEach(e => {
        if (e && !_qiState.env_types.includes(e)) _qiState.env_types.push(e);
      });
      _qiState.quick_inputs = Array.isArray(data.quick_inputs) ? data.quick_inputs.map(x => ({...x})) : [];
      renderQiTable();
      overlay.hidden = false;
      lucide.createIcons();
    })
    .catch(() => showToast('載入快速輸入設定失敗', 'error'));
}

function closeQuickInputPanel() {
  const overlay = document.getElementById('quick-input-overlay');
  if (overlay) overlay.hidden = true;
}

document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  const o = document.getElementById('quick-input-overlay');
  if (o && !o.hidden) { e.stopPropagation(); closeQuickInputPanel(); }
});

function _qiEnvDisplay(name) {
  return QI_ENV_DISPLAY_LABELS[name] || name;
}

function _escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[c]));
}

// One row per env type. Presets are looked up by env — at most one per env.
function _qiPresetFor(env) {
  return _qiState.quick_inputs.find(p => p && p.env === env);
}

function renderQiTable() {
  const tbody = document.getElementById('qi-tbody');
  if (!tbody) return;
  const envs = _qiState.env_types;
  if (!envs.length) {
    tbody.innerHTML = '<tr><td colspan="5" class="qi-empty">尚無類型。先在啟動指令區用「＋ 自訂…」新增。</td></tr>';
    return;
  }
  const dragSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/>
    <circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/>
  </svg>`;
  const trashSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none"
       stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
  </svg>`;
  tbody.innerHTML = envs.map((env) => {
    const p = _qiPresetFor(env) || { env, label: '', cmd: '' };
    const locked = QI_DEFAULT_ENV_TYPES.includes(env);   // local/docker/bat/github/gas — protected
    return `
    <tr class="qi-row" data-orig-env="${_escapeHtml(env)}">
      <td class="qi-drag">
        <span class="qi-drag-handle" draggable="true" title="拖曳排序" aria-label="Drag">${dragSvg}</span>
      </td>
      <td class="qi-env-cell">
        <input type="text" class="qi-env-input" value="${_escapeHtml(env)}"
               ${locked ? 'readonly title="預設類型不可改名"' : 'placeholder="類型名稱"'}>
      </td>
      <td><input type="text" class="qi-field" data-field="label" value="${_escapeHtml(p.label||'')}"
                 placeholder="（空白）"></td>
      <td><input type="text" class="qi-field" data-field="cmd" value="${_escapeHtml(p.cmd||'')}"
                 placeholder="（空白）"></td>
      <td class="qi-delete">
        ${locked ? '' : `<button type="button" class="qi-del-btn" title="刪除此類型" aria-label="Delete" onclick="deleteQiRow(this)">${trashSvg}</button>`}
      </td>
    </tr>
  `;
  }).join('');
}

function deleteQiRow(btn) {
  const row = btn.closest('.qi-row');
  if (!row) return;
  const envInput = row.querySelector('.qi-env-input');
  const name = envInput ? envInput.value.trim() : (row.dataset.origEnv || '');
  if (!confirm(`刪除類型「${name || '?'}」？（儲存後才會真的寫回）`)) return;
  row.remove();
}

// --- Drag-reorder for quick-input rows (handle only) ---
let _qiDraggingRow = null;
document.body.addEventListener('dragstart', (e) => {
  const handle = e.target.closest('.qi-drag-handle');
  if (!handle) return;
  const row = handle.closest('.qi-row');
  if (!row) return;
  _qiDraggingRow = row;
  e.dataTransfer.effectAllowed = 'move';
  try { e.dataTransfer.setDragImage(row, 12, 12); } catch (_) {}
  requestAnimationFrame(() => row.classList.add('qi-dragging'));
});
document.body.addEventListener('dragover', (e) => {
  if (!_qiDraggingRow) return;
  const tbody = document.getElementById('qi-tbody');
  if (!tbody || !tbody.contains(e.target)) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  const rows = [...tbody.querySelectorAll('.qi-row:not(.qi-dragging)')];
  const after = rows.find(r => {
    const rect = r.getBoundingClientRect();
    return e.clientY < rect.top + rect.height / 2;
  });
  if (after == null) {
    if (tbody.lastElementChild !== _qiDraggingRow) tbody.appendChild(_qiDraggingRow);
  } else if (after !== _qiDraggingRow.nextSibling) {
    tbody.insertBefore(_qiDraggingRow, after);
  }
});
document.body.addEventListener('dragend', () => {
  if (!_qiDraggingRow) return;
  _qiDraggingRow.classList.remove('qi-dragging');
  _qiDraggingRow = null;
});

function saveQuickInputSettings() {
  const tbody = document.getElementById('qi-tbody');
  const rows = tbody ? [...tbody.querySelectorAll('.qi-row')] : [];
  const env_types = [];
  const quick_inputs = [];
  const seen = new Set();
  for (const tr of rows) {
    const envInput = tr.querySelector('.qi-env-input');
    const env = (envInput ? envInput.value : tr.dataset.origEnv || '').trim();
    if (!env || seen.has(env)) continue;
    seen.add(env);
    env_types.push(env);
    const labelInput = tr.querySelector('.qi-field[data-field="label"]');
    const cmdInput   = tr.querySelector('.qi-field[data-field="cmd"]');
    const label = (labelInput ? labelInput.value : '').trim();
    const cmd   = (cmdInput   ? cmdInput.value   : '').trim();
    if (label || cmd) quick_inputs.push({ env, label, cmd });
  }
  fetch('/api/quick-inputs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ env_types, quick_inputs }),
  })
    .then(r => r.json().then(data => ({ ok: r.ok, data })))
    .then(({ ok, data }) => {
      if (!ok || !data.ok) {
        showToast(data.error || '儲存失敗', 'error');
        return;
      }
      // Sync back: refresh env list + presets so both the form dropdowns and the
      // env→label auto-fill pick up what was just saved.
      const newTypes = data.env_types || [];
      window.__ENV_TYPES__ = [...newTypes];
      window.__QUICK_INPUTS__ = Array.isArray(data.quick_inputs) ? data.quick_inputs.map(x => ({...x})) : [];
      document.querySelectorAll('.cmd-env-select').forEach(sel => {
        const prev = sel.value;
        const customOpt = sel.querySelector('option[value="__custom__"]');
        // Remove old non-__custom__ options
        [...sel.querySelectorAll('option')].forEach(o => {
          if (o.value !== '__custom__') o.remove();
        });
        newTypes.forEach(name => {
          const opt = document.createElement('option');
          opt.value = name;
          opt.textContent = _qiEnvDisplay(name);
          if (!QI_DEFAULT_ENV_TYPES.includes(name)) opt.dataset.custom = '1';
          if (customOpt) sel.insertBefore(opt, customOpt); else sel.appendChild(opt);
        });
        // Restore previous selection if still valid, else default to local
        sel.value = newTypes.includes(prev) ? prev : 'local';
        sel.dataset.prev = sel.value;
      });
      showToast('已儲存快速輸入設定');
      closeQuickInputPanel();
    })
    .catch(() => showToast('儲存失敗', 'error'));
}


// ---------- Screenshots manager ----------
// State lives on `window.__SM__`; committed into #screenshots-json (hidden field) on every mutation.
// Upload API is stateless — add_tool/update_tool parses screenshots_json on submit.

const SM_STYLE_DEFAULTS = {
  pos_x: 50, pos_y: 50, scale: 100,
  // brightness 100 = 當前 theme 的預設（CSS 另外乘 --theme-img-brightness）。
  opacity: 100, brightness: 100, blur: 0,
};
const SM_STYLE_CLAMP = {
  pos_x: [0, 100], pos_y: [0, 100],
  scale: [50, 300], opacity: [0, 100],
  brightness: [0, 200], blur: [0, 50],
};

function smInit() {
  const root = document.getElementById('screenshots-manager');
  if (!root) return;
  let initial = [];
  try { initial = JSON.parse(root.dataset.initial || '[]'); } catch (e) { initial = []; }
  window.__SM__ = {
    toolId: root.dataset.toolId,
    items: (initial || []).map(smNormalize),
    sessionUploads: [],  // object_keys uploaded during this modal open; cleaned up on cancel/save
  };
  smSyncHidden();
  smRender();
  // Wire file input
  const fileInput = document.getElementById('sm-file-input');
  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      const files = Array.from(e.target.files || []);
      if (files.length) smUpload(files);
      e.target.value = '';  // allow re-selecting same file
    });
  }
  // Wire "no cover" button (click-driven, not a native radio to avoid group-management quirks)
  const none = root.querySelector('#sm-cover-none-btn');
  if (none) none.addEventListener('click', () => smSetCoverAt(-1));
  // Wire style sliders — input for continuous drag, dblclick to snap back to default
  root.querySelectorAll('.sm-sliders input[type=range]').forEach(slider => {
    slider.addEventListener('input', (e) => smOnSlider(e.target));
    slider.addEventListener('dblclick', (e) => {
      const key = e.currentTarget.dataset.style;
      const def = SM_STYLE_DEFAULTS[key];
      if (typeof def !== 'number') return;
      e.currentTarget.value = def;
      smOnSlider(e.currentTarget);
    });
  });
  // Paste-to-upload: Ctrl+V with image on clipboard → upload (auto-expands the section)
  if (!document.body.dataset.smPasteWired) {
    document.addEventListener('paste', smHandlePaste);
    document.body.dataset.smPasteWired = '1';
  }
}

function smHandlePaste(e) {
  // Only handle when a manager is in the DOM (i.e., new/edit form is open)
  const root = document.getElementById('screenshots-manager');
  if (!root) return;
  // Don't hijack paste in a text input / textarea / contenteditable
  const t = e.target;
  const tag = (t && t.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || (t && t.isContentEditable)) {
    // But still allow if clipboard has ONLY image data (e.g., screenshot copy)
    // — text inputs would receive "" in that case anyway.
    const hasText = Array.from(e.clipboardData?.items || [])
      .some(it => it.kind === 'string');
    if (hasText) return;
  }
  const items = Array.from(e.clipboardData?.items || []);
  const files = [];
  for (const it of items) {
    if (it.kind !== 'file' || !it.type.startsWith('image/')) continue;
    const blob = it.getAsFile();
    if (!blob) continue;
    const ext = (it.type.split('/')[1] || 'png').replace(/[^a-z0-9]/gi, '');
    const name = blob.name || `pasted-${Date.now()}.${ext}`;
    files.push(new File([blob], name, { type: it.type }));
  }
  if (!files.length) return;
  e.preventDefault();
  // Auto-expand the collapsible image section so user sees feedback
  const details = document.querySelector('details.form-collapse');
  if (details && !details.open) details.open = true;
  smUpload(files);
}

function smNormalize(raw) {
  const out = {
    url: String(raw.url || '').trim(),
    object_key: String(raw.object_key || '').trim(),
    is_cover: !!raw.is_cover,
  };
  for (const [k, def] of Object.entries(SM_STYLE_DEFAULTS)) {
    const v = parseInt(raw[k], 10);
    out[k] = Number.isFinite(v) ? v : def;
  }
  return out;
}

function smSyncHidden() {
  const hidden = document.getElementById('screenshots-json');
  if (hidden) hidden.value = JSON.stringify(window.__SM__.items);
}

function smUpload(files) {
  const state = window.__SM__;
  const fd = new FormData();
  files.forEach(f => fd.append('files', f));
  const btn = document.querySelector('.sm-upload-btn');
  if (btn) btn.classList.add('loading');
  fetch(`/api/tool/${state.toolId}/screenshots`, { method: 'POST', body: fd })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) throw new Error(data.error || 'Upload failed');
      // Append each as normalized item; first upload ever → auto-cover.
      // Also record in sessionUploads so cancel-close can reap them from Storage.
      const hadCover = state.items.some(it => it.is_cover);
      (data.added || []).forEach((up, i) => {
        const item = smNormalize({ ...up, is_cover: false });
        if (!hadCover && i === 0) item.is_cover = true;
        state.items.push(item);
        if (up.object_key) state.sessionUploads.push(up.object_key);
      });
      if (data.failed && data.failed.length) {
        showToast(`${data.failed.length} 張上傳失敗`, 'error');
      } else {
        showToast(`已上傳 ${(data.added || []).length} 張`);
      }
      smSyncHidden(); smRender();
    })
    .catch(err => showToast(err.message || 'Upload failed', 'error'))
    .finally(() => { if (btn) btn.classList.remove('loading'); });
}

function smRemoveAt(idx) {
  const state = window.__SM__;
  if (idx < 0 || idx >= state.items.length) return;
  state.items.splice(idx, 1);
  smSyncHidden(); smRender();
}

// idx = -1 → clear cover (nothing selected)
function smSetCoverAt(idx) {
  const state = window.__SM__;
  state.items.forEach((it, i) => { it.is_cover = (i === idx); });
  smSyncHidden(); smRender();
}

// Snap to the default value when the user lands within ±SNAP of it. Otherwise
// exact integer control. Prevents scale/opacity/etc from sticking at 99/101.
const SM_SNAP_RADIUS = 2;

function smOnSlider(slider) {
  const state = window.__SM__;
  const cover = state.items.find(it => it.is_cover);
  if (!cover) return;
  const key = slider.dataset.style;
  const [lo, hi] = SM_STYLE_CLAMP[key] || [0, 100];
  let v = Math.max(lo, Math.min(hi, parseInt(slider.value, 10) || 0));
  const def = SM_STYLE_DEFAULTS[key];
  if (typeof def === 'number' && Math.abs(v - def) <= SM_SNAP_RADIUS) {
    v = def;
    if (slider.value !== String(v)) slider.value = v;
  }
  cover[key] = v;
  smSyncHidden();
  smUpdateSliderLabel(key, v);
  smUpdatePreview(cover);
}

function smResetStyle() {
  const state = window.__SM__;
  const cover = state.items.find(it => it.is_cover);
  if (!cover) return;
  Object.assign(cover, SM_STYLE_DEFAULTS);
  smSyncHidden();
  smRender();
}

function smUpdateSliderLabel(key, v) {
  const el = document.getElementById(`sm-val-${key}`);
  if (!el) return;
  el.textContent = key === 'blur' ? `${v}px` : `${v}%`;
}

function smUpdatePreview(cover) {
  const img = document.getElementById('sm-preview-img');
  if (!img) return;
  if (img.src !== cover.url) img.src = cover.url;
  // Write all CSS vars; .sm-preview img uses the same vars as .card-img for a truthful preview.
  img.style.setProperty('--card-pos-x', `${cover.pos_x}%`);
  img.style.setProperty('--card-pos-y', `${cover.pos_y}%`);
  img.style.setProperty('--card-scale', cover.scale / 100);
  img.style.setProperty('--card-opacity', cover.opacity / 100);
  img.style.setProperty('--card-brightness', cover.brightness / 100);
  img.style.setProperty('--card-blur', `${cover.blur}px`);
}

function smRender() {
  const state = window.__SM__;
  const grid = document.getElementById('sm-grid');
  if (!grid) return;

  // Thumbnails — click anywhere on thumb to set it as cover; delete button separately.
  // We use array index (data-idx) as the click identifier. Using object_key fails for
  // legacy-synthesized items (object_key="") which would match smSetCoverAt(-1) semantics.
  grid.innerHTML = state.items.map((it, idx) => `
    <div class="sm-thumb${it.is_cover ? ' is-cover' : ''}" data-idx="${idx}"
         title="${it.is_cover ? '目前封面' : '點擊設為封面'}">
      <img src="${it.url}" alt="">
      ${it.is_cover ? `
        <span class="sm-cover-badge">
          <i data-lucide="star" style="width:12px;height:12px"></i>
          <span class="zh">封面</span><span class="en">Cover</span>
        </span>
      ` : ''}
      <button type="button" class="sm-thumb-del" title="刪除" aria-label="Delete">
        <i data-lucide="trash-2" style="width:13px;height:13px"></i>
      </button>
    </div>
  `).join('');

  // One delegated listener on the grid handles cover + delete based on click target.
  // Avoids re-attaching handlers every render and any stale-closure traps.
  if (!grid.dataset.wired) {
    grid.addEventListener('click', (e) => {
      const thumb = e.target.closest('.sm-thumb');
      if (!thumb) return;
      const idx = parseInt(thumb.dataset.idx, 10);
      if (!Number.isFinite(idx)) return;
      if (e.target.closest('.sm-thumb-del')) {
        e.stopPropagation();
        smRemoveAt(idx);
        return;
      }
      smSetCoverAt(idx);
    });
    grid.dataset.wired = '1';
  }

  // "No cover" button active state — mirrors the cover dot via class
  const noneBtn = document.getElementById('sm-cover-none-btn');
  if (noneBtn) noneBtn.classList.toggle('is-active', !state.items.some(it => it.is_cover));

  // Count badge on the collapsed section header — shows N when there are images
  const countBadge = document.getElementById('sm-count-badge');
  if (countBadge) {
    if (state.items.length) {
      countBadge.textContent = String(state.items.length);
      countBadge.hidden = false;
    } else {
      countBadge.hidden = true;
    }
  }

  // Style panel visibility + state
  const cover = state.items.find(it => it.is_cover);
  const panel = document.getElementById('sm-style-panel');
  if (panel) {
    panel.hidden = !cover;
    if (cover) {
      Object.keys(SM_STYLE_DEFAULTS).forEach(k => {
        const slider = panel.querySelector(`input[data-style="${k}"]`);
        if (slider) slider.value = cover[k];
        smUpdateSliderLabel(k, cover[k]);
      });
      smUpdatePreview(cover);
    }
  }

  // Re-render lucide icons inside the grid
  if (window.lucide) lucide.createIcons();
}

// Boot manager whenever a form is swapped in (both new and edit use the same form partial)
document.body.addEventListener('htmx:afterSwap', (e) => {
  if (e.detail && e.detail.target && e.detail.target.id === 'modal-content'
      && document.getElementById('screenshots-manager')) {
    smInit();
  }
});


// ---------- Detail screenshots carousel ----------
// Cycles through all screenshots in the detail view. Click image → new tab (default anchor behavior).
// Prev/next buttons wrap around. Arrow keys navigate when modal is open in detail mode.

function detailCarouselInit() {
  const root = document.querySelector('.detail-carousel');
  if (!root) return;
  const slides = Array.from(root.querySelectorAll('.detail-slide'));
  if (slides.length <= 1) return;
  const counter = root.querySelector('.cc-current');
  const start = parseInt(root.dataset.start || '0', 10) || 0;
  const state = { idx: start, count: slides.length };

  function show(idx) {
    state.idx = ((idx % state.count) + state.count) % state.count;
    slides.forEach((s, i) => s.classList.toggle('is-active', i === state.idx));
    if (counter) counter.textContent = String(state.idx + 1);
  }

  root.querySelector('.detail-carousel-nav.prev')
      ?.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); show(state.idx - 1); });
  root.querySelector('.detail-carousel-nav.next')
      ?.addEventListener('click', (e) => { e.preventDefault(); e.stopPropagation(); show(state.idx + 1); });
}

document.body.addEventListener('htmx:afterSwap', (e) => {
  if (e.detail && e.detail.target && e.detail.target.id === 'modal-content') {
    detailCarouselInit();
  }
});

// Arrow keys navigate when detail modal is open (not in edit form)
document.addEventListener('keydown', (e) => {
  const root = document.querySelector('#modal-overlay.open .detail-carousel');
  if (!root) return;
  if (document.querySelector('#modal-content .tool-form')) return;  // editing — don't hijack keys
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  const btn = root.querySelector(e.key === 'ArrowLeft' ? '.detail-carousel-nav.prev' : '.detail-carousel-nav.next');
  if (btn) { e.preventDefault(); btn.click(); }
});


// ---------- Auto-tag based on brand categories ----------
const CATEGORY_BRAND_TAGS = {
  github: 'github',
  netlify: 'netlify',
  notion: 'notion',
  vercel: 'vercel',
  aws: 'aws',
  railway: 'railway',
  heroku: 'heroku',
  supabase: 'supabase',
  firebase: 'firebase',
  cloudflare: 'cloudflare',
  gitlab: 'gitlab',
  bitbucket: 'bitbucket',
  docker: 'docker',
  'docker-hub': 'docker',
  discord: 'discord',
  slack: 'slack',
  telegram: 'telegram',
  line: 'line-api',
  stripe: 'stripe',
};

function autoTagFromCategory(categoryValue) {
  if (!categoryValue) return;
  const key = categoryValue.toLowerCase().trim();
  const tag = CATEGORY_BRAND_TAGS[key];
  if (!tag) return;
  const tagsInput = document.getElementById('tags');
  if (!tagsInput) return;
  const existing = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean);
  if (existing.some(t => t.toLowerCase() === tag.toLowerCase())) return;
  existing.push(tag);
  tagsInput.value = existing.join(', ');
}

// Fire on category select change (existing categories)
document.addEventListener('change', (e) => {
  if (e.target.id === 'category') autoTagFromCategory(e.target.value);
});
// Fire on new category id input (creating a new category)
document.addEventListener('input', (e) => {
  if (e.target.name === 'new_cat_id') autoTagFromCategory(e.target.value);
});


// ---------- Color picker sync ----------
document.addEventListener('input', (e) => {
  if (e.target.id === 'color') {
    const hex = document.getElementById('color-hex');
    if (hex) hex.textContent = e.target.value;
    syncSwatchActive(e.target.value);
  }
});

function pickSwatch(btn) {
  const color = btn.dataset.color;
  const input = document.getElementById('color');
  const hex = document.getElementById('color-hex');
  if (input) input.value = color;
  if (hex) hex.textContent = color;
  syncSwatchActive(color);
}

function syncSwatchActive(color) {
  const c = (color || '').toLowerCase();
  document.querySelectorAll('.color-swatch').forEach(s => {
    s.classList.toggle('active', s.dataset.color.toLowerCase() === c);
  });
}


// ---------- Filter category pill: update hidden input + active class immediately ----------
// onclick runs before HTMX fires so hx-include="#filter-category" picks up the new value.
function setFilterCategory(pillBtn, catId) {
  const hidden = document.getElementById('filter-category');
  if (hidden) hidden.value = catId;
  document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
  if (pillBtn) pillBtn.classList.add('active');
  // Keep the "..." dropdown's highlight in sync (menu + row use separate DOM nodes)
  document.querySelectorAll('.filter-pills-more-item').forEach(m => {
    m.classList.toggle('active', m.dataset.catId === catId);
  });
}

// ---------- Filter pills overflow dropdown ----------
function toggleFilterMore(ev) {
  if (ev) ev.stopPropagation();
  const menu = document.getElementById('filter-pills-more-menu');
  if (!menu) return;
  menu.hidden = !menu.hidden;
  if (window.lucide && !menu.hidden) lucide.createIcons();
}

function closeFilterMore() {
  const menu = document.getElementById('filter-pills-more-menu');
  if (menu) menu.hidden = true;
}

// Click a category from the overflow menu → mirror selection onto the matching
// pill (so the pill-row highlight stays correct), then close the menu.
function pickCategoryFromMore(item, catId) {
  const rowPill = document.querySelector(`.filter-pill[data-cat-id="${CSS.escape(catId)}"]`);
  setFilterCategory(rowPill, catId);
  // Also scroll the matching pill into view so the user sees which one they picked
  if (rowPill && rowPill.scrollIntoView) {
    rowPill.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }
  closeFilterMore();
}

// Show/hide "..." button based on actual overflow in the pill scroller
function updateFilterPillsOverflow() {
  const scroll = document.querySelector('.filter-pills-scroll');
  const wrap = document.getElementById('filter-pills-more-wrap');
  if (!scroll || !wrap) return;
  const overflowing = scroll.scrollWidth > scroll.clientWidth + 1;  // +1 tolerates rounding
  wrap.hidden = !overflowing;
  if (!overflowing) closeFilterMore();
}

document.addEventListener('DOMContentLoaded', updateFilterPillsOverflow);
window.addEventListener('resize', updateFilterPillsOverflow);
// Re-check after any HTMX swap (category add/remove re-renders the grid but
// the filter-bar itself isn't swapped — still, font-loading / zoom etc can change widths)
document.body.addEventListener('htmx:afterSwap', updateFilterPillsOverflow);

// Close menu on outside click / ESC
document.addEventListener('click', (e) => {
  const wrap = document.getElementById('filter-pills-more-wrap');
  if (!wrap || wrap.hidden) return;
  if (!wrap.contains(e.target)) closeFilterMore();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeFilterMore();
});
