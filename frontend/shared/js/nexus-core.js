/**
 * JORINOVA NEXUS ALIS-X — Core Engine
 * ThemeEngine · ShiftIntelligence · API · Toast · Confirm · Sidebar
 */
'use strict';

(function (NEXUS) {

  /* ─────────────────────────────────────────────────────────────
     THEME ENGINE
     Reads NEXUS.module, applies [data-theme-mode] to .app-main
  ──────────────────────────────────────────────────────────────── */
  const ThemeEngine = {
    MAP: {
      epidemic:      'default',
      surveillance:  'default',
      outbreak:      'default',
      'public-health': 'default',
      'national-dashboard': 'default',
      clinical:      'white-cyan',
      patients:      'default',       // lab staff view stays dark
      'lab-results': 'white-cyan',
      genome:        'medgenome',
      molecular:     'medgenome',
      'blood-bank':  'default',
      telemedicine:   'remote-diagnostic',
      telediag:       'remote-diagnostic',
      security:       'ai-matrix',
      records:        'default',
      finaops:        'default',
      staffhub:       'default',
      genome:         'medgenome',
      molecular:      'medgenome',
      epidemic:       'default',
      surveillance:   'default',
      'ai-training':  'ai-matrix',
      nexuscore:     'ai-matrix',
      default:       'default',
    },

    init() {
      const mode = this.MAP[NEXUS.module] || 'default';
      const main = document.getElementById('app-main');
      if (main && mode !== 'default') {
        main.setAttribute('data-theme-mode', mode);
      }
    },

    switch(moduleId) {
      NEXUS.module = moduleId;
      this.init();
    },
  };

  /* ─────────────────────────────────────────────────────────────
     SHIFT INTELLIGENCE ENGINE
     Auto-detects shift from server config or fallback defaults.
     Lab Manager can override shift config via /api/v1/shifts/config
  ──────────────────────────────────────────────────────────────── */
  const ShiftEngine = {
    _config: null,
    _clockId: null,
    _DEFAULTS: [
      { name: 'Morning',   icon: '☀️',  start: '06:00', end: '14:00' },
      { name: 'Afternoon', icon: '🌤️', start: '14:00', end: '22:00' },
      { name: 'Night',     icon: '🌙',  start: '22:00', end: '06:00' },
    ],

    async init() {
      try {
        const r = await fetch('/api/v1/core-config/shifts/', {
          headers: { 'X-CSRFToken': NEXUS.csrf },
          credentials: 'same-origin',
        });
        if (r.ok) this._config = await r.json();
      } catch (_) { /* use fallback */ }
      this._tick();
      this._clockId = setInterval(() => this._tick(), 1000);
    },

    _shifts() {
      return (this._config && this._config.shifts) ? this._config.shifts : this._DEFAULTS;
    },

    _hhmm(d) {
      return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    },

    _inRange(time, start, end) {
      return start <= end
        ? time >= start && time < end
        : time >= start || time < end;     /* overnight cross-midnight */
    },

    current() {
      const now = this._hhmm(new Date());
      for (const s of this._shifts()) {
        if (this._inRange(now, s.start, s.end)) return s;
      }
      return this._shifts()[0];
    },

    currentTag() {
      const s = this.current();
      return { name: s.name, icon: s.icon };
    },

    _tick() {
      const shift = this.current();
      const now   = new Date();
      const iconEl = document.getElementById('shift-icon');
      const nameEl = document.getElementById('shift-name');
      const timeEl = document.getElementById('shift-time');
      if (iconEl) iconEl.textContent = shift.icon;
      if (nameEl) nameEl.textContent = shift.name + ' Shift';
      if (timeEl) timeEl.textContent = now.toLocaleTimeString('en-GB', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
    },
  };

  /* ─────────────────────────────────────────────────────────────
     JWT TOKEN REFRESH ENGINE
     Auto-refreshes the Bearer token 7 hours after the last refresh.
     Token lifetime is 8 hours; refreshing at 7h keeps the session alive.
     On failure (server returned 401) → redirects to login.
  ──────────────────────────────────────────────────────────────── */
  const TokenRefreshEngine = {
    _INTERVAL_MS: 7 * 60 * 60 * 1000,  /* 7 hours */
    _timerId: null,

    init() {
      if (!localStorage.getItem('access_token')) return;
      this._schedule();
    },

    _schedule() {
      clearTimeout(this._timerId);
      this._timerId = setTimeout(() => this._doRefresh(), this._INTERVAL_MS);
    },

    async _doRefresh() {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      try {
        const r = await fetch('/api/v1/auth/refresh', {
          method:  'POST',
          headers: {
            'Content-Type':  'application/json',
            'Authorization': 'Bearer ' + token,
          },
          body: JSON.stringify({ access_token: token }),
        });
        if (r.ok) {
          const data = await r.json();
          localStorage.setItem('access_token', data.access_token);
          console.debug('[NEXUS] Token refreshed, next refresh in 7h');
          this._schedule();
        } else {
          console.warn('[NEXUS] Token refresh failed (%d) — redirecting to login', r.status);
          localStorage.removeItem('access_token');
          window.location.href = '/auth/login/?timeout=1';
        }
      } catch (err) {
        console.warn('[NEXUS] Token refresh network error — will retry in 30 min', err);
        this._timerId = setTimeout(() => this._doRefresh(), 30 * 60 * 1000);
      }
    },

    /* Call after a successful login to start the refresh cycle immediately */
    start() { this.init(); },
  };

  /* ─────────────────────────────────────────────────────────────
     API CLIENT
     Wraps fetch with JWT Bearer token, shift tag, and base URL.
     Token is read from localStorage on every request so it stays fresh.
     Usage: NEXUS.API.get('/patients/', { q: 'Jean' })
            NEXUS.API.post('/patients/', { family_name: 'Doe', ... })
  ──────────────────────────────────────────────────────────────── */
  const API = {
    _headers(extra) {
      const shift = ShiftEngine.currentTag();
      const token = localStorage.getItem('access_token');
      const h = {
        'Content-Type':  'application/json',
        'X-CSRFToken':   NEXUS.csrf,
        'X-Shift-Name':  shift.name,
        'X-Shift-Icon':  shift.icon,
      };
      if (token) h['Authorization'] = 'Bearer ' + token;
      return Object.assign(h, extra);
    },

    _url(path, params) {
      const base = NEXUS.apiBase.replace(/\/$/, '');
      const url  = new URL(base + path, window.location.origin);
      if (params) Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) url.searchParams.set(k, v);
      });
      return url.toString();
    },

    get(path, params) {
      return fetch(this._url(path, params), {
        headers: this._headers(),
        credentials: 'same-origin',
      });
    },

    post(path, data) {
      return fetch(this._url(path), {
        method: 'POST',
        headers: this._headers(),
        body: JSON.stringify(data),
        credentials: 'same-origin',
      });
    },

    patch(path, data) {
      return fetch(this._url(path), {
        method: 'PATCH',
        headers: this._headers(),
        body: JSON.stringify(data),
        credentials: 'same-origin',
      });
    },

    put(path, data) {
      return fetch(this._url(path), {
        method: 'PUT',
        headers: this._headers(),
        body: JSON.stringify(data),
        credentials: 'same-origin',
      });
    },

    delete(path) {
      return fetch(this._url(path), {
        method: 'DELETE',
        headers: this._headers(),
        credentials: 'same-origin',
      });
    },

    postForm(path, formData) {
      const h = { 'X-CSRFToken': NEXUS.csrf };
      const t = localStorage.getItem('access_token');
      if (t) h['Authorization'] = 'Bearer ' + t;
      return fetch(this._url(path), {
        method: 'POST', headers: h, body: formData, credentials: 'same-origin',
      });
    },

    patchForm(path, formData) {
      const h = { 'X-CSRFToken': NEXUS.csrf };
      const t = localStorage.getItem('access_token');
      if (t) h['Authorization'] = 'Bearer ' + t;
      return fetch(this._url(path), {
        method: 'PATCH', headers: h, body: formData, credentials: 'same-origin',
      });
    },

    /* Handle API responses uniformly */
    async json(response) {
      const text = await response.text();
      try { return JSON.parse(text); } catch (_) { return { detail: text }; }
    },

    async checkError(response) {
      if (!response.ok) {
        const data = await this.json(response);
        const msg  = data.detail || data.message || data.non_field_errors?.[0]
                  || Object.values(data).flat().join(' ') || `Error ${response.status}`;
        throw new Error(msg);
      }
      return response;
    },
  };

  /* ─────────────────────────────────────────────────────────────
     TOAST NOTIFICATIONS
     Usage: NEXUS.Toast.success('Saved')
            NEXUS.Toast.error('Failed to load', 'Try again later')
  ──────────────────────────────────────────────────────────────── */
  const Toast = {
    _container: null,
    _ICONS: {
      success: 'fa-circle-check',
      error:   'fa-circle-xmark',
      warning: 'fa-triangle-exclamation',
      info:    'fa-circle-info',
    },

    _init() {
      this._container = document.getElementById('toast-container');
    },

    show(message, type = 'info', subtitle = '', duration = 4500) {
      if (!this._container) this._init();
      if (!this._container) return;

      const el = document.createElement('div');
      el.className = `toast toast-${type}`;
      el.setAttribute('role', 'alert');
      el.innerHTML = `
        <i class="fas ${this._ICONS[type] || this._ICONS.info} toast-icon"></i>
        <div class="toast-body">
          <div class="toast-title">${this._esc(message)}</div>
          ${subtitle ? `<div class="toast-msg">${this._esc(subtitle)}</div>` : ''}
        </div>
        <button class="toast-close" aria-label="Dismiss"><i class="fas fa-xmark"></i></button>
      `;

      el.querySelector('.toast-close').addEventListener('click', () => this._dismiss(el));
      this._container.appendChild(el);

      /* Trigger transition on next frame */
      requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('toast-in')));

      if (duration > 0) setTimeout(() => this._dismiss(el), duration);
      return el;
    },

    success: function (msg, sub, d) { return Toast.show(msg, 'success', sub, d); },
    error:   function (msg, sub, d) { return Toast.show(msg, 'error',   sub, d); },
    warning: function (msg, sub, d) { return Toast.show(msg, 'warning', sub, d); },
    info:    function (msg, sub, d) { return Toast.show(msg, 'info',    sub, d); },

    _dismiss(el) {
      el.classList.replace('toast-in', 'toast-out');
      el.addEventListener('transitionend', () => el.remove(), { once: true });
    },

    _esc(s) {
      return String(s)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    },
  };

  /* ─────────────────────────────────────────────────────────────
     CONFIRM DIALOG
     Usage: const ok = await NEXUS.Confirm.show('Delete this record?')
  ──────────────────────────────────────────────────────────────── */
  const Confirm = {
    _resolve: null,
    _modal:   null,

    _init() {
      this._modal = document.getElementById('confirm-modal');
      if (!this._modal) return;
      this._modal.querySelector('#confirm-ok')?.addEventListener('click',     () => this._close(true));
      this._modal.querySelector('#confirm-cancel')?.addEventListener('click', () => this._close(false));
      this._modal.addEventListener('click', e => {
        if (e.target === this._modal) this._close(false);
      });
      document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && this._modal.classList.contains('open')) this._close(false);
      });
    },

    show(message, title = 'Confirm Action', okLabel = 'Confirm', danger = true) {
      return new Promise(resolve => {
        this._resolve = resolve;
        if (!this._modal) this._init();
        if (!this._modal) { resolve(true); return; }

        this._modal.querySelector('#confirm-title').textContent   = title;
        this._modal.querySelector('#confirm-message').textContent = message;
        const okBtn = this._modal.querySelector('#confirm-ok');
        if (okBtn) {
          okBtn.textContent = okLabel;
          okBtn.className = `btn ${danger ? 'btn-danger' : 'btn-primary'}`;
        }
        this._modal.classList.add('open');
        this._modal.querySelector('#confirm-cancel')?.focus();
      });
    },

    _close(result) {
      this._modal?.classList.remove('open');
      if (this._resolve) { this._resolve(result); this._resolve = null; }
    },
  };

  /* ─────────────────────────────────────────────────────────────
     INACTIVITY ENGINE
     5-minute idle timer → 30-second warning modal → auto-logout
  ──────────────────────────────────────────────────────────────── */
  const InactivityEngine = {
    _TIMEOUT_MS:  300_000,   /* 5 min  */
    _WARN_MS:     270_000,   /* 4m30s  */
    _timerId:     null,
    _warnId:      null,
    _countdownId: null,
    _modal:       null,
    _secs:        30,

    init() {
      ['mousemove','keydown','click','touchstart','scroll','pointerdown'].forEach(ev => {
        document.addEventListener(ev, () => this._reset(), { passive: true, capture: true });
      });
      this._buildModal();
      this._reset();
    },

    _buildModal() {
      const el = document.createElement('div');
      el.id        = 'inactivity-modal';
      el.className = 'modal-overlay';
      el.setAttribute('role', 'alertdialog');
      el.setAttribute('aria-modal', 'true');
      el.setAttribute('aria-labelledby', 'inact-title');
      el.innerHTML = `
        <div class="modal" style="max-width:400px;text-align:center">
          <div class="modal-header" style="justify-content:center">
            <h3 class="modal-title" id="inact-title" style="display:flex;align-items:center;gap:10px">
              <i class="fas fa-hourglass-half" style="color:var(--alert-orange)"></i>
              Session Expiring
            </h3>
          </div>
          <div class="modal-body" style="padding:var(--space-xl) var(--space-xl) var(--space-md)">
            <p style="color:var(--text-secondary);font-size:var(--text-sm);line-height:1.7;margin-bottom:var(--space-lg)">
              No activity detected. You will be signed out in:
            </p>
            <div id="inact-countdown"
                 style="font-family:var(--font-display);font-size:64px;font-weight:700;
                        color:var(--alert-orange);line-height:1;
                        text-shadow:0 0 30px rgba(255,109,0,0.4);
                        transition:color var(--duration-fast),text-shadow var(--duration-fast)">30</div>
            <p style="font-size:var(--text-xs);color:var(--text-muted);margin-top:6px;letter-spacing:0.08em;text-transform:uppercase">seconds</p>
          </div>
          <div class="modal-footer" style="justify-content:center;gap:var(--space-sm);padding-bottom:var(--space-xl)">
            <button class="btn btn-primary" id="inact-stay" style="min-width:160px">
              <i class="fas fa-rotate-right"></i> Stay Logged In
            </button>
            <button class="btn btn-ghost" id="inact-out">
              <i class="fas fa-right-from-bracket"></i> Sign Out
            </button>
          </div>
        </div>`;
      document.body.appendChild(el);
      this._modal = el;
      el.querySelector('#inact-stay')?.addEventListener('click', () => {
        this._hideModal();
        this._reset();
      });
      el.querySelector('#inact-out')?.addEventListener('click', () => this._doLogout());
    },

    _reset() {
      clearTimeout(this._timerId);
      clearTimeout(this._warnId);
      this._hideModal();
      this._warnId  = setTimeout(() => this._showModal(),  this._WARN_MS);
      this._timerId = setTimeout(() => this._doLogout(),   this._TIMEOUT_MS);
    },

    _showModal() {
      if (!this._modal) return;
      this._modal.classList.add('open');
      this._secs = 30;
      const cd = document.getElementById('inact-countdown');
      if (cd) cd.textContent = this._secs;
      this._countdownId = setInterval(() => {
        this._secs--;
        if (cd) {
          cd.textContent = Math.max(this._secs, 0);
          if (this._secs <= 10) {
            cd.style.color      = 'var(--alert-red)';
            cd.style.textShadow = '0 0 30px rgba(255,23,68,0.55)';
          }
        }
        if (this._secs <= 0) clearInterval(this._countdownId);
      }, 1000);
    },

    _hideModal() {
      clearInterval(this._countdownId);
      if (!this._modal) return;
      this._modal.classList.remove('open');
      const cd = document.getElementById('inact-countdown');
      if (cd) {
        cd.textContent  = '30';
        cd.style.color      = 'var(--alert-orange)';
        cd.style.textShadow = '0 0 30px rgba(255,109,0,0.4)';
      }
    },

    _doLogout() {
      this._hideModal();
      const form = document.getElementById('logout-form');
      if (form) {
        const inp   = document.createElement('input');
        inp.type    = 'hidden';
        inp.name    = 'inactivity';
        inp.value   = '1';
        form.appendChild(inp);
        form.submit();
      } else {
        window.location.href = '/auth/login/?timeout=1';
      }
    },
  };

  /* ─────────────────────────────────────────────────────────────
     SIDEBAR TOOLTIPS
     Shows tooltip to the right of nav items when sidebar is collapsed
  ──────────────────────────────────────────────────────────────── */
  const Sidebar = {
    init() {
      const sidebar = document.getElementById('sidebar');
      if (!sidebar) return;

      sidebar.querySelectorAll('.nav-item[data-tooltip]').forEach(item => {
        let tip = null;

        item.addEventListener('mouseenter', () => {
          if (sidebar.matches(':hover') && sidebar.offsetWidth <= 80) {
            tip = document.createElement('div');
            tip.className = 'nav-tooltip';
            tip.textContent = item.dataset.tooltip;
            document.body.appendChild(tip);
            const rect = item.getBoundingClientRect();
            tip.style.top  = `${rect.top + (rect.height - tip.offsetHeight) / 2}px`;
            tip.style.left = `${rect.right + 8}px`;
          }
        });

        item.addEventListener('mouseleave', () => {
          tip?.remove();
          tip = null;
        });
      });
    },
  };

  /* ─────────────────────────────────────────────────────────────
     LOGOUT
  ──────────────────────────────────────────────────────────────── */
  function initLogout() {
    const btn  = document.getElementById('logout-btn');
    const form = document.getElementById('logout-form');
    if (!btn || !form) return;

    btn.addEventListener('click', async () => {
      const ok = await Confirm.show(
        'You will be signed out of NEXUS ALIS-X.',
        'Sign Out',
        'Sign Out',
        true
      );
      if (ok) form.submit();
    });
  }

  /* ─────────────────────────────────────────────────────────────
     GLOBAL KEY SHORTCUTS
  ──────────────────────────────────────────────────────────────── */
  function initShortcuts() {
    document.addEventListener('keydown', e => {
      /* Ctrl/Cmd+K → focus global search if exists */
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const s = document.getElementById('global-search');
        if (s) { s.focus(); s.select(); }
      }
    });
  }

  /* ─────────────────────────────────────────────────────────────
     FORMAT HELPERS  (attached to NEXUS.fmt)
  ──────────────────────────────────────────────────────────────── */
  const fmt = {
    date(iso) {
      if (!iso) return '—';
      return new Date(iso).toLocaleDateString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
      });
    },
    datetime(iso) {
      if (!iso) return '—';
      return new Date(iso).toLocaleString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
      });
    },
    time(iso) {
      if (!iso) return '—';
      return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
    },
    phone(p) {
      if (!p) return '—';
      return p.replace(/(\+?\d{3})(\d{3})(\d{3})(\d{3})/, '$1 $2 $3 $4');
    },
    capitalize(s) {
      return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
    },
    age(dob) {
      if (!dob) return '—';
      const d = new Date(dob);
      const now = new Date();
      let y = now.getFullYear() - d.getFullYear();
      const m = now.getMonth() - d.getMonth();
      if (m < 0 || (m === 0 && now.getDate() < d.getDate())) y--;
      if (y > 0) return y + 'y';
      const mo = Math.floor((now - d) / (1000*60*60*24*30));
      if (mo > 0) return mo + 'mo';
      return Math.floor((now - d) / (1000*60*60*24)) + 'd';
    },
  };

  /* ─────────────────────────────────────────────────────────────
     BOOT
  ──────────────────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    ThemeEngine.init();
    Confirm._init();
    Sidebar.init();
    ShiftEngine.init();
    initLogout();
    initShortcuts();
    InactivityEngine.init();
    TokenRefreshEngine.init();
  });

  /* ─── Export ─────────────────────────────────────────────── */
  Object.assign(NEXUS, {
    API,
    Toast,
    Confirm,
    ShiftEngine,
    ThemeEngine,
    InactivityEngine,
    TokenRefreshEngine,
    fmt,
  });

})(window.NEXUS = window.NEXUS || {});
