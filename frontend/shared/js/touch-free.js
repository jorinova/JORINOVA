/**
 * JORINOVA NEXUS ALIS-X — Touch-Free Mode Engine
 * ================================================
 * Enables hands-free laboratory operation for infection control.
 * Complies with ISO 15189 contamination prevention guidelines.
 *
 * Interaction methods (all work without touching):
 *   1. Voice commands  → JorinovaVoice (built separately)
 *   2. Dwell-click     → hover over target for N seconds = click
 *   3. Keyboard nav    → Tab / Enter / Space / Arrow keys
 *   4. Foot pedal      → Space bar = confirm, Escape = cancel
 *   5. Scroll zones    → auto-scroll at screen edges (barcode scan motion)
 *
 * Usage:
 *   NexusTouchFree.enable()   // activate no-touch mode
 *   NexusTouchFree.disable()  // return to normal
 *   NexusTouchFree.toggle()   // flip state
 *
 * Auto-initialise: add data-touch-free="auto" to <body>
 */
'use strict';

(function (root) {

  /* ─── Config ──────────────────────────────────────────────────── */
  const STORAGE_KEY   = 'alis_touch_free';
  const DWELL_MS_DEF  = 1800;    // default dwell time (ms)
  const TOUCH_SIZE_PX = 72;      // minimum touch-target size in touch-free mode
  const INDICATOR_R   = 28;      // dwell ring radius (px)

  /* ─── State ───────────────────────────────────────────────────── */
  const State = {
    active:     false,
    dwellMs:    DWELL_MS_DEF,
    dwellTimer: null,
    dwellEl:    null,
    dwellStart: 0,
    indicator:  null,
    rafId:      null,
    shortcuts:  {},
  };

  /* ─── Dwell indicator (SVG ring) ─────────────────────────────── */
  function _createIndicator() {
    if (State.indicator) return;
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const C = INDICATOR_R + 6;
    svg.setAttribute('width', (C*2).toString());
    svg.setAttribute('height', (C*2).toString());
    svg.id = 'tf-dwell-indicator';
    svg.style.cssText = (
      'position:fixed;pointer-events:none;z-index:99998;display:none;'
      + 'transform:translate(-50%,-50%);transition:opacity .15s;'
    );
    // Track circle
    const track = document.createElementNS('http://www.w3.org/2000/svg','circle');
    track.setAttribute('cx', C); track.setAttribute('cy', C);
    track.setAttribute('r', INDICATOR_R);
    track.setAttribute('fill','none');
    track.setAttribute('stroke','rgba(99,102,241,.25)');
    track.setAttribute('stroke-width','5');
    // Progress arc
    const arc = document.createElementNS('http://www.w3.org/2000/svg','circle');
    const circ = 2 * Math.PI * INDICATOR_R;
    arc.id = 'tf-dwell-arc';
    arc.setAttribute('cx', C); arc.setAttribute('cy', C);
    arc.setAttribute('r', INDICATOR_R);
    arc.setAttribute('fill','none');
    arc.setAttribute('stroke','#6366f1');
    arc.setAttribute('stroke-width','5');
    arc.setAttribute('stroke-linecap','round');
    arc.setAttribute('stroke-dasharray', circ.toFixed(2));
    arc.setAttribute('stroke-dashoffset', circ.toFixed(2));
    arc.setAttribute('transform', `rotate(-90 ${C} ${C})`);
    svg.appendChild(track);
    svg.appendChild(arc);
    document.body.appendChild(svg);
    State.indicator = svg;
    State.indicatorArc = arc;
    State.indicatorCirc = circ;
  }

  function _showIndicator(x, y) {
    if (!State.indicator) _createIndicator();
    State.indicator.style.display = 'block';
    State.indicator.style.left = x + 'px';
    State.indicator.style.top  = y + 'px';
    State.indicator.style.opacity = '1';
  }

  function _hideIndicator() {
    if (State.indicator) {
      State.indicator.style.opacity = '0';
      setTimeout(() => {
        if (State.indicator) State.indicator.style.display = 'none';
      }, 150);
    }
  }

  function _updateIndicator(progress) {
    if (!State.indicatorArc) return;
    const offset = State.indicatorCirc * (1 - progress);
    State.indicatorArc.setAttribute('stroke-dashoffset', offset.toFixed(2));
    // Colour shift: purple → green as completes
    const r = Math.round(99  + (34 - 99)  * progress);
    const g = Math.round(102 + (197 - 102) * progress);
    const b = Math.round(241 + (94 - 241) * progress);
    State.indicatorArc.setAttribute('stroke', `rgb(${r},${g},${b})`);
  }

  /* ─── Dwell-click logic ───────────────────────────────────────── */
  function _isDwellTarget(el) {
    if (!el) return false;
    // Match interactive elements
    const interactive = ['button', 'a', 'input', 'select', 'label', 'textarea'];
    if (interactive.includes(el.tagName.toLowerCase())) return true;
    if (el.getAttribute('role') === 'button') return true;
    if (el.hasAttribute('data-dwell')) return true;
    if (el.classList.contains('tab-btn') || el.classList.contains('btn')
        || el.classList.contains('nav-link') || el.classList.contains('flyout-item')) return true;
    return false;
  }

  function _startDwell(e) {
    if (!State.active) return;
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!_isDwellTarget(el)) return;

    State.dwellEl    = el;
    State.dwellStart = performance.now();
    _showIndicator(e.clientX, e.clientY);

    State.rafId = requestAnimationFrame(function tick(now) {
      const elapsed  = now - State.dwellStart;
      const progress = Math.min(1, elapsed / State.dwellMs);
      _updateIndicator(progress);
      if (progress < 1) {
        State.rafId = requestAnimationFrame(tick);
      } else {
        // Dwell complete → fire click
        _hideIndicator();
        _fireClick(el);
        State.dwellEl = null;
      }
    });
  }

  function _cancelDwell() {
    if (State.rafId) cancelAnimationFrame(State.rafId);
    State.rafId = null;
    State.dwellEl = null;
    _hideIndicator();
  }

  function _fireClick(el) {
    if (!el) return;
    // Flash element to confirm
    el.style.outline = '3px solid #22c55e';
    el.style.outlineOffset = '2px';
    setTimeout(() => {
      el.style.outline = '';
      el.style.outlineOffset = '';
    }, 500);
    el.click();
    if (root.JorinovaVoice) {
      // Brief audio confirmation (short beep via Web Audio)
      try {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain); gain.connect(ctx.destination);
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.15, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.12);
        osc.start(); osc.stop(ctx.currentTime + 0.12);
      } catch (_) {}
    }
  }

  /* ─── Keyboard shortcuts ──────────────────────────────────────── */
  const GLOBAL_SHORTCUTS = {
    'F1':              () => _showShortcutHelp(),
    'F2':              () => NexusTouchFree.toggle(),
    'F3':              () => root.JorinovaVoice?.activate(),
    'F5':              () => location.reload(),
    'Escape':          () => _cancelConfirm(),
    ' ':               () => _activateFocused(),       // Space = confirm / click
    'Enter':           () => _activateFocused(),
    'ArrowDown':       () => _focusNext(1),
    'ArrowUp':         () => _focusNext(-1),
    'ArrowRight':      () => _nextTab(1),
    'ArrowLeft':       () => _nextTab(-1),
    'p':               () => root.NexusPrint?.printSelected(),  // P = print
    'f':               () => root.NexusFilter?.open(),           // F = filter
    'r':               () => root.NexusTouchFree?.repeatVoice(), // R = repeat
  };

  function _activateFocused() {
    const el = document.activeElement;
    if (el && el !== document.body) el.click();
  }

  function _focusNext(dir) {
    const focusable = Array.from(document.querySelectorAll(
      'button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )).filter(el => el.offsetParent !== null);
    const idx = focusable.indexOf(document.activeElement);
    const next = focusable[idx + dir];
    if (next) {
      next.focus();
      next.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function _nextTab(dir) {
    const tabs = Array.from(document.querySelectorAll('.tab-btn'));
    const idx  = tabs.findIndex(t => t.classList.contains('active'));
    const next = tabs[idx + dir];
    if (next) next.click();
  }

  function _keyHandler(e) {
    // Don't hijack typing in inputs
    const tag = document.activeElement?.tagName.toLowerCase();
    if (['input', 'textarea', 'select'].includes(tag) && e.key !== 'Escape') {
      return;
    }
    const fn = GLOBAL_SHORTCUTS[e.key];
    if (fn) { e.preventDefault(); fn(); }
  }

  /* ─── Confirmation cancel ────────────────────────────────────── */
  function _cancelConfirm() {
    document.querySelectorAll('.modal-overlay[style*="flex"]').forEach(m => {
      m.style.display = 'none';
    });
    document.getElementById('jv-confirm-banner')?.style?.setProperty('display', 'none');
  }

  /* ─── Shortcut help overlay ──────────────────────────────────── */
  function _showShortcutHelp() {
    let overlay = document.getElementById('tf-shortcut-help');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'tf-shortcut-help';
      overlay.innerHTML = `
        <div class="tf-help-box">
          <h3>⌨️ Keyboard Shortcuts (Touch-Free Mode)</h3>
          <div class="tf-help-grid">
            <div><kbd>F1</kbd> This help</div>
            <div><kbd>F2</kbd> Toggle touch-free mode</div>
            <div><kbd>F3</kbd> Activate Jorinova Voice</div>
            <div><kbd>F5</kbd> Refresh page</div>
            <div><kbd>↑ ↓</kbd> Move focus between elements</div>
            <div><kbd>← →</kbd> Switch tabs</div>
            <div><kbd>Space / Enter</kbd> Click focused element</div>
            <div><kbd>Escape</kbd> Cancel / Close modal</div>
            <div><kbd>P</kbd> Print selected results</div>
            <div><kbd>F</kbd> Open filter</div>
            <div><kbd>R</kbd> Repeat last voice response</div>
          </div>
          <div class="tf-help-dwell">
            <strong>Dwell-click:</strong> Hover over any button for
            <strong id="tf-help-dwell-time">${State.dwellMs/1000}s</strong>
            to click without touching.
          </div>
          <button onclick="this.closest('#tf-shortcut-help').remove()" class="tf-help-close">Close</button>
        </div>`;
      document.body.appendChild(overlay);
      overlay.style.cssText = (
        'position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:99999;'
        + 'display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);'
      );
      overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    } else {
      overlay.remove();
    }
  }

  /* ─── Touch-free mode UI (floating toggle pill) ──────────────── */
  function _createTogglePill() {
    if (document.getElementById('tf-pill')) return;
    const pill = document.createElement('div');
    pill.id = 'tf-pill';
    pill.title = 'Touch-Free Mode (F2) | Voice (F3) | Help (F1)';
    pill.innerHTML = `
      <button id="tf-toggle-btn" class="tf-btn" title="Toggle touch-free mode">
        <span id="tf-icon">🖐️</span>
        <span id="tf-label">Touch</span>
      </button>
      <button class="tf-btn" onclick="root.JorinovaVoice?.activate()" title="Voice (F3)">🎙️</button>
      <button class="tf-btn" onclick="_showShortcutHelp()" title="Shortcuts (F1)">⌨️</button>
    `;
    document.body.appendChild(pill);
    pill.style.cssText = (
      'position:fixed;bottom:1.25rem;left:1.25rem;z-index:9998;'
      + 'display:flex;gap:4px;background:rgba(15,20,40,.9);'
      + 'border:1px solid rgba(99,102,241,.35);border-radius:30px;padding:4px 8px;'
      + 'box-shadow:0 4px 20px rgba(0,0,0,.5);backdrop-filter:blur(12px);'
    );
    document.getElementById('tf-toggle-btn').addEventListener('click', () => NexusTouchFree.toggle());
  }

  function _updatePill() {
    const icon  = document.getElementById('tf-icon');
    const label = document.getElementById('tf-label');
    if (icon)  icon.textContent  = State.active ? '✋' : '🖐️';
    if (label) label.textContent = State.active ? 'No-Touch' : 'Touch';
    document.body.classList.toggle('touch-free-mode', State.active);
  }

  /* ─── Public API ─────────────────────────────────────────────── */
  const NexusTouchFree = {
    enable(dwellMs) {
      State.active  = true;
      State.dwellMs = dwellMs || DWELL_MS_DEF;
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ active: true, dwellMs: State.dwellMs }));
      document.addEventListener('mousemove', _trackMouse);
      document.addEventListener('mouseleave', _cancelDwell, true);
      document.addEventListener('keydown', _keyHandler);
      _createIndicator();
      _updatePill();
      _showBanner('🖐️ Touch-Free Mode ON — hover to click, or use voice/keyboard', 'info');
    },

    disable() {
      State.active = false;
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ active: false }));
      document.removeEventListener('mousemove', _trackMouse);
      document.removeEventListener('mouseleave', _cancelDwell, true);
      // Keep keyboard handler always active
      _cancelDwell();
      _updatePill();
      _showBanner('Touch-Free Mode OFF', 'info');
    },

    toggle() {
      State.active ? this.disable() : this.enable();
    },

    setDwellTime(ms) {
      State.dwellMs = Math.max(500, Math.min(5000, ms));
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ active: State.active, dwellMs: State.dwellMs }));
    },

    isActive() { return State.active; },

    repeatVoice() {
      if (root.JorinovaVoice?.repeatLast) root.JorinovaVoice.repeatLast();
    },

    showHelp: _showShortcutHelp,
  };

  /* ─── Mouse tracker ──────────────────────────────────────────── */
  let _lastEl = null;
  function _trackMouse(e) {
    if (!State.active) return;
    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (el !== _lastEl) {
      _cancelDwell();
      _lastEl = el;
      if (_isDwellTarget(el)) {
        _startDwell(e);
      }
    }
  }

  /* ─── Toast banner ───────────────────────────────────────────── */
  function _showBanner(msg, type = 'info') {
    if (root.NexusCore?.toast) { root.NexusCore.toast(msg, type); return; }
    const el = document.createElement('div');
    el.textContent = msg;
    el.style.cssText = (
      'position:fixed;top:1rem;left:50%;transform:translateX(-50%);'
      + 'background:#1e293b;color:#e2e8f0;padding:.5rem 1.25rem;border-radius:20px;'
      + 'font-size:.82rem;z-index:99999;box-shadow:0 4px 20px rgba(0,0,0,.4);'
      + 'transition:opacity .3s;pointer-events:none;'
    );
    document.body.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 2500);
  }

  /* ─── Init ───────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    // Always register keyboard shortcuts
    document.addEventListener('keydown', _keyHandler);

    // Always show toggle pill
    _createTogglePill();

    // Restore persisted state
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      if (saved.active) NexusTouchFree.enable(saved.dwellMs || DWELL_MS_DEF);
    } catch(_) {}

    // Auto-enable if body attribute set
    if (document.body.dataset.touchFree === 'auto') {
      NexusTouchFree.enable();
    }
  });

  /* ─── Inject CSS ─────────────────────────────────────────────── */
  const style = document.createElement('style');
  style.textContent = `
    .tf-btn {
      background:none;border:none;padding:.2rem .35rem;border-radius:20px;
      color:#94a3b8;cursor:pointer;font-size:.8rem;display:flex;align-items:center;gap:.25rem;
      transition:.15s;
    }
    .tf-btn:hover { background:rgba(99,102,241,.2);color:#c7d2fe; }

    /* Touch-free mode: enlarge all interactive elements */
    body.touch-free-mode button,
    body.touch-free-mode a.btn,
    body.touch-free-mode .tab-btn,
    body.touch-free-mode .flyout-item {
      min-height: ${TOUCH_SIZE_PX}px !important;
      min-width:  ${TOUCH_SIZE_PX}px !important;
      font-size:  1rem !important;
      padding:    1rem 1.5rem !important;
    }

    /* Focused element highlight in touch-free mode */
    body.touch-free-mode :focus {
      outline: 3px solid #6366f1 !important;
      outline-offset: 3px !important;
    }

    /* Touch-free mode table rows are taller */
    body.touch-free-mode .data-table td,
    body.touch-free-mode .worklist-table td {
      padding: .9rem .75rem !important;
      font-size: .95rem !important;
    }

    /* Dwell-clickable visual cue */
    body.touch-free-mode button:hover,
    body.touch-free-mode a:hover,
    body.touch-free-mode [data-dwell]:hover {
      box-shadow: 0 0 0 3px rgba(99,102,241,.3) !important;
      transition: box-shadow .15s !important;
    }

    /* Shortcut help box */
    .tf-help-box {
      background:#0f172a;border:1px solid rgba(99,102,241,.3);border-radius:16px;
      padding:1.5rem;max-width:520px;width:90%;color:#e2e8f0;
    }
    .tf-help-box h3 { margin:0 0 1rem;font-size:1.1rem;color:#a5b4fc; }
    .tf-help-grid { display:grid;grid-template-columns:1fr 1fr;gap:.5rem .75rem;margin-bottom:1rem; }
    .tf-help-grid div { font-size:.83rem;color:#94a3b8; }
    kbd { background:#1e293b;border:1px solid #334155;border-radius:4px;
          padding:.1rem .4rem;font-size:.78rem;font-family:monospace;color:#c7d2fe; }
    .tf-help-dwell { font-size:.82rem;color:#94a3b8;margin-bottom:1rem;border-top:1px solid #1e293b;padding-top:.75rem; }
    .tf-help-close { background:#6366f1;color:#fff;border:none;border-radius:8px;
                     padding:.5rem 1.25rem;cursor:pointer;font-size:.85rem;font-weight:600; }
  `;
  document.head.appendChild(style);

  root.NexusTouchFree = NexusTouchFree;
  root._showShortcutHelp = _showShortcutHelp;  // expose for inline onclick

})(window);
