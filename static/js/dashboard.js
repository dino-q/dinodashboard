/* ==========================================================================
   DinoDashboard — Client-side interactions
   ========================================================================== */

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
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
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

  let ticks = 0;
  const lock = () => {
    if (sc.scrollTop !== target) sc.scrollTop = target;
    if (++ticks < 15) requestAnimationFrame(lock);
    else _preservedScrollTop = null;
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
        let bestDist = Infinity;
        groups.forEach(g => {
          const top = g.getBoundingClientRect().top;
          if (top > preferLine) return; // heading not yet reached
          const dist = preferLine - top; // 0 when heading is at preferLine; grows as it scrolls past
          if (dist < bestDist) { bestDist = dist; activeGroup = g; }
        });
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
          col.style.transform = `translateY(-${totalSteps * 100}%)`;
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
  document.getElementById('modal-overlay').classList.remove('open');
  document.body.style.overflow = '';
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


// ---------- Screenshot upload ----------
function uploadScreenshot(toolId, input) {
  const file = input.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);

  fetch(`/api/tool/${toolId}/screenshot`, {
    method: 'POST',
    body: formData,
  })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        showToast('Screenshot uploaded!');
        // Update hidden field
        const pathInput = document.getElementById('screenshot-path');
        if (pathInput) pathInput.value = data.path;
        // Update preview
        const container = input.closest('.screenshot-upload');
        let img = container.querySelector('.screenshot-thumb');
        if (!img) {
          img = document.createElement('img');
          img.className = 'screenshot-thumb';
          container.insertBefore(img, input);
        }
        img.src = `/static/${data.path}?t=${Date.now()}`;
      } else {
        showToast(data.error || 'Upload failed', 'error');
      }
    })
    .catch(() => showToast('Upload failed', 'error'));
}


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


// ---------- Filter pill active state ----------
document.body.addEventListener('htmx:afterSwap', (e) => {
  if (e.target.id === 'tool-grid') {
    // Update active filter pill based on the trigger element
    const trigger = e.detail?.requestConfig?.elt;
    if (trigger && trigger.classList.contains('filter-pill')) {
      document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
      trigger.classList.add('active');
    }
  }
});
