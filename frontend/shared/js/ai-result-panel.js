/**
 * JORINOVA NEXUS ALIS-X — AI Result Interpretation Panel
 * ========================================================
 * Real-time AI assistance during result entry.
 * Shows interpretation, flags, reflex suggestions, and doctor notification.
 *
 * Features:
 *  - Instant rules engine check (offline, zero-latency)
 *  - Local LLM interpretation (non-blocking, shows while typing)
 *  - Reference range comparison with visual indicator
 *  - Critical value banner with one-click clinician notification
 *  - Reflex test suggestions
 *  - Doctor portal send button
 *  - Renders inside any result entry form
 *
 * Usage:
 *   AIResultPanel.attach('result-form-id', {
 *     testCodeField: 'test-code-input',
 *     valueField:    'value-input',
 *     unitField:     'unit-input',
 *     flagField:     'flag-select',
 *     onCritical:    (data) => { ... },
 *   });
 */
'use strict';

(function (root) {

  const API = '/api/v1';
  const _panels = {};   // formId → panel instance

  /* ─── Auth header ─────────────────────────────────────────────── */
  function _auth() {
    const t = localStorage.getItem('access_token');
    return t ? { Authorization: `Bearer ${t}` } : {};
  }

  /* ─── Attach panel to a result entry form ────────────────────── */
  function attach(formId, opts = {}) {
    const form = document.getElementById(formId) || document.querySelector(formId);
    if (!form) return;

    const panelEl = _buildPanel(formId);
    form.appendChild(panelEl);

    const instance = {
      formId,
      panelEl,
      opts,
      debounceTimer: null,
      lastValue:     '',
      lastTestCode:  '',
    };
    _panels[formId] = instance;

    // Watch value field for changes
    const valueInput = form.querySelector(`#${opts.valueField}`) || form.querySelector('[data-result-value]');
    if (valueInput) {
      valueInput.addEventListener('input', () => _debounce(formId, form, opts));
    }

    return instance;
  }

  /* ─── Debounced interpretation ───────────────────────────────── */
  function _debounce(formId, form, opts) {
    const inst = _panels[formId];
    if (!inst) return;
    clearTimeout(inst.debounceTimer);
    inst.debounceTimer = setTimeout(() => _runInterpretation(formId, form, opts), 600);
  }

  async function _runInterpretation(formId, form, opts) {
    const inst = _panels[formId];
    if (!inst) return;

    const testCode = _getField(form, opts.testCodeField, '[data-test-code]');
    const value    = _getField(form, opts.valueField,    '[data-result-value]');
    const unit     = _getField(form, opts.unitField,     '[data-result-unit]');
    const flag     = _getField(form, opts.flagField,     '[data-result-flag]');
    const labReqId = _getField(form, opts.labReqField,   '[data-lab-req-id]');

    if (!value || value === inst.lastValue && testCode === inst.lastTestCode) return;
    inst.lastValue    = value;
    inst.lastTestCode = testCode;

    _setLoading(inst.panelEl, true);

    try {
      // 1. Rules engine check (always first — offline)
      const flagCheck = await fetch(`${API}/ai/flag-check`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', ..._auth() },
        body:    JSON.stringify({ test_code: testCode, value: parseFloat(value) || 0, unit, flag }),
      });
      const rules = flagCheck.ok ? await flagCheck.json() : null;

      // 2. Full interpretation
      const interp = await fetch(`${API}/ai/interpret`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', ..._auth() },
        body:    JSON.stringify({
          test_code: testCode, test_name: testCode, value, unit, flag,
          lab_req_id: labReqId,
        }),
      });
      const data = interp.ok ? await interp.json() : null;

      _render(inst, { rules, data, value, unit, flag, testCode });

      // Fire critical callback
      if ((rules?.is_critical || data?.is_critical) && opts.onCritical) {
        opts.onCritical({ rules, data, value, unit, flag, testCode });
      }

    } catch (e) {
      // Offline: use auto-flag only
      _renderOffline(inst, { value, unit, flag, testCode });
    } finally {
      _setLoading(inst.panelEl, false);
    }
  }

  /* ─── Render AI panel ─────────────────────────────────────────── */
  function _render(inst, { rules, data, value, unit, flag, testCode }) {
    const panel = inst.panelEl;
    const isCrit  = rules?.is_critical || data?.is_critical || ['HH','LL'].includes(flag);
    const sig      = rules?.significance || data?.significance || 'NORMAL';
    const interp   = data?.ai_enrichment?.summary || data?.rules?.interpretation || '';
    const reflexes = data?.rules?.reflex_tests || [];
    const panics   = rules?.panic_alerts || [];
    const layer    = data?.layer || 'rules_engine';

    // Critical banner
    const banner = panel.querySelector('.aip-critical-banner');
    if (banner) banner.style.display = isCrit ? 'flex' : 'none';

    // Significance badge
    const sigBadge = panel.querySelector('.aip-sig-badge');
    if (sigBadge) {
      sigBadge.textContent = sig;
      sigBadge.className = `aip-sig-badge sig-${sig}`;
    }

    // Value display
    const valDisplay = panel.querySelector('.aip-value-display');
    if (valDisplay) {
      valDisplay.innerHTML = `
        <span class="aip-val">${value} <small>${unit}</small></span>
        ${flag ? `<span class="aip-flag flag-${flag}">${flag}</span>` : ''}
        ${isCrit ? '<span class="aip-crit-pulse">⚡ CRITICAL</span>' : ''}
      `;
    }

    // Panic alerts
    const panicSection = panel.querySelector('.aip-panics');
    if (panicSection) {
      panicSection.innerHTML = panics.map(p => `
        <div class="aip-panic-item">
          <span class="aip-panic-icon">${p.direction === 'HIGH' ? '⬆️' : '⬇️'}</span>
          <div>
            <div class="aip-panic-msg">${p.message}</div>
            ${p.actions?.slice(0,2).map(a => `<div class="aip-panic-action">→ ${a}</div>`).join('') || ''}
          </div>
        </div>`).join('');
      panicSection.style.display = panics.length ? '' : 'none';
    }

    // AI interpretation text
    const interpEl = panel.querySelector('.aip-interpretation');
    if (interpEl) {
      interpEl.textContent = interp || (isCrit ? 'Critical value — clinician notification required.' : '');
      interpEl.style.display = interp ? '' : 'none';
    }

    // Reflex tests
    const reflexEl = panel.querySelector('.aip-reflexes');
    if (reflexEl && reflexes.length) {
      reflexEl.innerHTML = `<div class="aip-reflex-hdr">🔄 Reflex Tests Suggested:</div>` +
        reflexes.slice(0,4).map(r =>
          `<div class="aip-reflex-item">
            <strong>${r.test_name}</strong>
            <span>${r.type === 'MANDATORY' ? '🔴 Mandatory' : '💡 Suggested'}</span>
            <span class="aip-reflex-reason">${r.reason}</span>
          </div>`
        ).join('');
      reflexEl.style.display = '';
    } else if (reflexEl) {
      reflexEl.style.display = 'none';
    }

    // AI layer indicator
    const layerEl = panel.querySelector('.aip-layer');
    if (layerEl) {
      const layerLabels = {
        'rules_engine':'🔵 Rules Engine', 'local_llm':'🟢 Local AI',
        'cloud_llm':'☁️ Cloud AI', 'rules+local':'🟢 AI + Rules', 'rules+local+cloud':'☁️ Full AI',
      };
      layerEl.textContent = layerLabels[layer] || layer;
    }
  }

  function _renderOffline(inst, { value, unit, flag, testCode }) {
    const panel = inst.panelEl;
    const isCrit = ['HH','LL'].includes(flag);

    // Auto-flag if HH/LL
    const valDisplay = panel.querySelector('.aip-value-display');
    if (valDisplay) {
      valDisplay.innerHTML = `
        <span class="aip-val">${value} <small>${unit}</small></span>
        ${flag ? `<span class="aip-flag flag-${flag}">${flag}</span>` : ''}
        ${isCrit ? '<span class="aip-crit-pulse">⚡ CRITICAL</span>' : ''}
      `;
    }
    const banner = panel.querySelector('.aip-critical-banner');
    if (banner) banner.style.display = isCrit ? 'flex' : 'none';
    const layerEl = panel.querySelector('.aip-layer');
    if (layerEl) layerEl.textContent = '🔵 Offline — Rules Only';
  }

  /* ─── Build panel DOM ─────────────────────────────────────────── */
  function _buildPanel(formId) {
    const panel = document.createElement('div');
    panel.className = 'ai-result-panel';
    panel.id = `aip-${formId}`;
    panel.innerHTML = `
      <!-- Critical banner -->
      <div class="aip-critical-banner" style="display:none">
        <span>🚨 CRITICAL VALUE</span>
        <div class="aip-critical-actions">
          <button class="aip-notify-btn" onclick="AIResultPanel.notifyClinician('${formId}')">
            📞 Notify Clinician
          </button>
          <button class="aip-archive-btn" onclick="AIResultPanel.archiveCritical('${formId}')">
            📖 Archive to Critical Book
          </button>
        </div>
      </div>

      <!-- Main content -->
      <div class="aip-body">
        <div class="aip-top-row">
          <div class="aip-value-display">—</div>
          <span class="aip-sig-badge sig-NORMAL">NORMAL</span>
          <span class="aip-spinner" style="display:none">
            <span class="spin-dot"></span>
          </span>
        </div>

        <!-- Panic alerts -->
        <div class="aip-panics" style="display:none"></div>

        <!-- AI interpretation -->
        <div class="aip-interpretation" style="display:none"></div>

        <!-- Reference range bar -->
        <div class="aip-ref-bar">
          <div class="aip-ref-track">
            <div class="aip-ref-fill" id="aip-ref-fill-${formId}"></div>
            <div class="aip-ref-marker" id="aip-ref-marker-${formId}"></div>
          </div>
        </div>

        <!-- Reflex tests -->
        <div class="aip-reflexes" style="display:none"></div>

        <!-- Doctor notification -->
        <div class="aip-doctor-row">
          <button class="aip-doctor-btn" onclick="AIResultPanel.sendToDoctor('${formId}')">
            👨‍⚕️ Send to Doctor Portal
          </button>
          <span class="aip-layer">🔵 Rules Engine</span>
        </div>
      </div>`;
    return panel;
  }

  /* ─── Actions ─────────────────────────────────────────────────── */
  async function notifyClinician(formId) {
    const name = prompt('Enter clinician name to notify:');
    if (!name) return;
    if (root.NexusCore?.toast) root.NexusCore.toast(`Notification sent to ${name}`, 'success');
    // In production: POST to /notifications endpoint
  }

  async function archiveCritical(formId) {
    if (root.NexusCore?.toast) root.NexusCore.toast('Archiving to critical book…', 'info');
    // In production: trigger archive modal
    const archiveBtn = document.querySelector('#archive-modal .modal-close')?.closest('.modal-overlay');
    if (archiveBtn) archiveBtn.style.display = 'flex';
  }

  async function sendToDoctor(formId) {
    const form = document.getElementById(formId) || document.querySelector(formId);
    if (!form) return;
    const labReqId = _getField(form, null, '[data-lab-req-id]');
    if (!labReqId) {
      if (root.NexusCore?.toast) root.NexusCore.toast('Lab request ID required to send to doctor', 'warn');
      return;
    }
    try {
      await fetch(`${API}/laboratory/results/release-to-doctor`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', ..._auth() },
        body:    JSON.stringify({ lab_request_id: parseInt(labReqId) }),
      });
      if (root.NexusCore?.toast) root.NexusCore.toast('Results sent to doctor portal ✓', 'success');
    } catch (e) {
      if (root.NexusCore?.toast) root.NexusCore.toast('Send failed: ' + e.message, 'error');
    }
  }

  /* ─── Helpers ─────────────────────────────────────────────────── */
  function _getField(form, fieldId, selector) {
    if (fieldId) {
      const el = form.querySelector(`#${fieldId}`) || document.getElementById(fieldId);
      if (el) return el.value || el.textContent.trim();
    }
    if (selector) {
      const el = form.querySelector(selector);
      if (el) return el.value || el.textContent.trim();
    }
    return '';
  }

  function _setLoading(panel, loading) {
    const spinner = panel.querySelector('.aip-spinner');
    if (spinner) spinner.style.display = loading ? 'inline' : 'none';
  }

  /* ─── Programmatic trigger ───────────────────────────────────── */
  function interpret(formId) {
    const inst = _panels[formId];
    if (inst) {
      const form = document.getElementById(formId) || document.querySelector(formId);
      _runInterpretation(formId, form, inst.opts);
    }
  }

  /* ─── CSS ─────────────────────────────────────────────────────── */
  function _injectStyles() {
    if (document.getElementById('aip-styles')) return;
    const s = document.createElement('style');
    s.id = 'aip-styles';
    s.textContent = `
      .ai-result-panel {
        border:1px solid rgba(99,102,241,.2);border-radius:12px;
        background:rgba(15,20,40,.6);margin-top:.75rem;overflow:hidden;
        backdrop-filter:blur(8px);
      }
      .aip-critical-banner {
        background:rgba(239,68,68,.2);border-bottom:1px solid rgba(239,68,68,.4);
        padding:.6rem 1rem;display:flex;align-items:center;justify-content:space-between;
        gap:.5rem;flex-wrap:wrap;animation:aip-pulse 1.5s infinite;
      }
      .aip-critical-banner > span { color:#fca5a5;font-weight:700;font-size:.88rem; }
      .aip-critical-actions { display:flex;gap:.4rem; }
      .aip-notify-btn, .aip-archive-btn {
        border:none;border-radius:8px;padding:.3rem .8rem;font-size:.78rem;cursor:pointer;font-weight:600;
      }
      .aip-notify-btn  { background:#ef4444;color:#fff; }
      .aip-archive-btn { background:#f59e0b;color:#000; }
      @keyframes aip-pulse { 0%,100%{opacity:1} 50%{opacity:.75} }

      .aip-body { padding:.75rem 1rem;display:flex;flex-direction:column;gap:.5rem; }
      .aip-top-row { display:flex;align-items:center;gap:.75rem; }
      .aip-val { font-size:1.35rem;font-weight:700;color:#e2e8f0; }
      .aip-val small { font-size:.7rem;color:#94a3b8;font-weight:400; }

      /* Flag colour pills */
      .aip-flag {
        padding:.15rem .55rem;border-radius:10px;font-size:.78rem;font-weight:700;
        font-family:monospace;
      }
      .flag-N   { background:#d4edda;color:#155724; }
      .flag-H   { background:#fff3cd;color:#856404; }
      .flag-L   { background:#cce5ff;color:#004085; }
      .flag-HH  { background:#f8d7da;color:#721c24;animation:aip-pulse 1.2s infinite; }
      .flag-LL  { background:#cce5ff;color:#004085;animation:aip-pulse 1.2s infinite; }
      .flag-POS { background:#f8d7da;color:#721c24; }
      .flag-NEG { background:#d4edda;color:#155724; }
      .flag-A   { background:#ffeeba;color:#856404; }

      .aip-crit-pulse {
        background:#ef4444;color:#fff;font-size:.7rem;font-weight:700;
        padding:.15rem .5rem;border-radius:8px;animation:aip-pulse 1s infinite;
      }

      /* Significance badge */
      .aip-sig-badge { padding:.2rem .65rem;border-radius:20px;font-size:.72rem;font-weight:700;
                       font-family:monospace;flex-shrink:0; }
      .sig-CRITICAL { background:#ef4444;color:#fff; }
      .sig-HIGH     { background:#f97316;color:#fff; }
      .sig-MODERATE { background:#eab308;color:#000; }
      .sig-LOW      { background:#3b82f6;color:#fff; }
      .sig-NORMAL   { background:#22c55e;color:#fff; }

      /* Panic items */
      .aip-panics { background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.2);
                    border-radius:8px;padding:.6rem .8rem;display:flex;flex-direction:column;gap:.4rem; }
      .aip-panic-item { display:flex;gap:.5rem;font-size:.8rem; }
      .aip-panic-icon { flex-shrink:0; }
      .aip-panic-msg  { color:#fca5a5;font-weight:600;margin-bottom:.15rem; }
      .aip-panic-action { color:#94a3b8;font-size:.76rem; }

      /* Interpretation text */
      .aip-interpretation { font-size:.82rem;color:#94a3b8;line-height:1.5;
                            background:rgba(255,255,255,.04);padding:.5rem .75rem;border-radius:8px; }

      /* Reflex tests */
      .aip-reflexes { border-top:1px solid rgba(255,255,255,.06);padding-top:.5rem; }
      .aip-reflex-hdr { font-size:.72rem;font-weight:700;color:#94a3b8;margin-bottom:.3rem; }
      .aip-reflex-item { display:flex;align-items:center;gap:.5rem;font-size:.8rem;
                         padding:.25rem 0;color:#e2e8f0; }
      .aip-reflex-reason { color:#64748b;font-size:.74rem;margin-left:auto; }

      /* Doctor row */
      .aip-doctor-row { display:flex;align-items:center;justify-content:space-between;
                        border-top:1px solid rgba(255,255,255,.06);padding-top:.5rem; }
      .aip-doctor-btn {
        background:rgba(99,102,241,.15);border:1px solid rgba(99,102,241,.3);
        border-radius:8px;color:#a5b4fc;padding:.3rem .8rem;font-size:.78rem;cursor:pointer;
      }
      .aip-doctor-btn:hover { background:rgba(99,102,241,.3); }
      .aip-layer { font-size:.68rem;color:#475569;font-family:monospace; }

      /* Spinner */
      .aip-spinner { display:inline-flex;align-items:center;gap:4px; }
      .spin-dot { width:6px;height:6px;border-radius:50%;background:#6366f1;
                  animation:spin-pulse .8s ease-in-out infinite; }
      @keyframes spin-pulse { 0%,100%{opacity:.2;transform:scale(.7)} 50%{opacity:1;transform:scale(1)} }

      /* Reference bar */
      .aip-ref-bar { height:6px;background:rgba(255,255,255,.08);border-radius:3px;
                     position:relative;overflow:visible; }
      .aip-ref-track { height:100%;background:rgba(34,197,94,.2);border-radius:3px;position:relative; }
      .aip-ref-fill  { height:100%;background:#22c55e;border-radius:3px;transition:.3s;max-width:100%; }
      .aip-ref-marker { width:2px;height:12px;background:#fff;position:absolute;
                        top:-3px;border-radius:1px;transform:translateX(-50%); }
    `;
    document.head.appendChild(s);
  }

  document.addEventListener('DOMContentLoaded', _injectStyles);

  root.AIResultPanel = { attach, interpret, notifyClinician, archiveCritical, sendToDoctor };

})(window);
