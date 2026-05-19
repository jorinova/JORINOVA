/**
 * JORINOVA NEXUS ALIS-X — Biochemistry Department
 * Worklist · Result Entry · Validation · Critical Book
 */
'use strict';

const BIOCHEM_API = '/api/v1/biochemistry/';
let currentResultId = null;

// ─── Bootstrap ────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  loadDashboard();
});

function initTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const pane = document.getElementById('tab-' + btn.dataset.tab);
      if (pane) pane.classList.add('active');
      // Lazy-load tab data
      const tab = btn.dataset.tab;
      if (tab === 'worklist')   loadWorklist();
      if (tab === 'results')    loadResults();
      if (tab === 'validation') loadValidation();
      if (tab === 'book')       loadCriticalBook();
    });
  });
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const data = await apiFetch(BIOCHEM_API + 'stats/');
    setText('kpi-pending',    data.pending_results);
    setText('kpi-validated',  data.validated_today);
    setText('kpi-critical',   data.critical_today);
    setText('kpi-worklists',  data.worklists_active);
    setText('kpi-book',       data.critical_book_total);
    setText('stat-pending',   data.pending_results);
    setText('stat-critical',  data.critical_today);
    const s = data.sections || {};
    setText('sq-general',   (s.GENERAL  || 0) + ' pending');
    setText('sq-hormones',  (s.HORMONES || 0) + ' pending');
    setText('sq-markers',   (s.MARKERS  || 0) + ' pending');
  } catch (e) {
    console.warn('Dashboard load failed', e);
  }
}

// ─── Worklist ─────────────────────────────────────────────────────────────────

async function loadWorklist() {
  const grid = document.getElementById('worklist-grid');
  grid.innerHTML = '<div class="empty-state">Loading…</div>';
  const params = new URLSearchParams();
  const st = document.getElementById('wl-filter-status')?.value;
  const pr = document.getElementById('wl-filter-priority')?.value;
  const dt = document.getElementById('wl-filter-date')?.value;
  if (st) params.set('status', st);
  if (pr) params.set('priority', pr);
  if (dt) params.set('date', dt);

  try {
    const data = await apiFetch(BIOCHEM_API + 'worklists/?' + params);
    const list = data.results || data;
    if (!list.length) { grid.innerHTML = '<div class="empty-state">No worklists found</div>'; return; }
    grid.innerHTML = list.map(wl => worklistCard(wl)).join('');
  } catch (e) {
    grid.innerHTML = '<div class="empty-state">Error loading worklists</div>';
  }
}

function worklistCard(wl) {
  const pct = wl.items_total ? Math.round((wl.items_done / wl.items_total) * 100) : 0;
  return `
  <div class="wl-card">
    <div class="wl-card-header">
      <span class="wl-id">${wl.worklist_id}</span>
      <span class="wl-badge ${wl.status}">${wl.status.replace('_',' ').toUpperCase()}</span>
    </div>
    <div class="wl-badge ${wl.priority}" style="display:inline-block;margin-bottom:.5rem">${wl.priority}</div>
    <div class="wl-analyzer">🔬 ${wl.analyzer_name || 'No analyzer assigned'}</div>
    <div class="wl-analyzer">👤 ${wl.created_by_name || '—'}</div>
    <div class="wl-progress">
      <div class="wl-prog-bar"><div class="wl-prog-fill" style="width:${pct}%"></div></div>
      <div class="wl-prog-text">${wl.items_done} / ${wl.items_total} completed (${pct}%)</div>
    </div>
    <div class="wl-actions">
      ${wl.status !== 'completed' ? `<button class="btn-primary btn-sm" onclick="completeWorklist(${wl.id})">✔ Complete</button>` : ''}
      <button class="btn-secondary btn-sm" onclick="viewWorklistItems(${wl.id})">📋 Items</button>
    </div>
  </div>`;
}

async function completeWorklist(id) {
  if (!confirm('Mark this worklist as completed?')) return;
  try {
    await apiFetch(BIOCHEM_API + `worklists/${id}/complete/`, 'POST', {});
    loadWorklist();
    loadDashboard();
  } catch (e) { alert('Error: ' + e.message); }
}

async function viewWorklistItems(id) {
  // Placeholder — could open a detail modal
  alert('Worklist item detail coming soon.');
}

function openWorklistModal() {
  showModal('worklist-modal');
}

async function submitWorklist() {
  const payload = {
    analyzer_name: document.getElementById('wl-analyzer').value.trim(),
    priority:      document.getElementById('wl-priority').value,
    notes:         document.getElementById('wl-notes').value.trim(),
  };
  try {
    await apiFetch(BIOCHEM_API + 'worklists/', 'POST', payload);
    closeModal('worklist-modal');
    document.getElementById('wl-analyzer').value = '';
    document.getElementById('wl-notes').value = '';
    loadWorklist();
    loadDashboard();
    showNotif('Worklist created');
  } catch (e) { alert('Error: ' + e.message); }
}

// ─── Results ──────────────────────────────────────────────────────────────────

async function loadResults() {
  const tbody = document.getElementById('results-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading…</td></tr>';
  const params = new URLSearchParams();
  const sec = document.getElementById('res-filter-section')?.value;
  const st  = document.getElementById('res-filter-status')?.value;
  const fl  = document.getElementById('res-filter-flag')?.value;
  if (sec) params.set('section', sec);
  if (st)  params.set('status',  st);
  if (fl)  params.set('flag',    fl);

  try {
    const data = await apiFetch(BIOCHEM_API + 'results/?' + params);
    const list = data.results || data;
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No results found</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(r => resultRow(r)).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Error loading results</td></tr>';
  }
}

function resultRow(r) {
  const srcClass = r.result_source === 'AUTOMATED' ? 'src-automated' : 'src-manual';
  const srcLabel = r.result_source === 'AUTOMATED' ? '🤖 Auto' : '👤 Manual';
  const refRange = r.reference_range_text || (r.reference_min != null ? `${r.reference_min}–${r.reference_max}` : '—');
  return `
  <tr>
    <td>${r.patient_name || '—'}</td>
    <td>${r.test_name || '—'}</td>
    <td>${sectionLabel(r.section)}</td>
    <td><strong>${r.result_value || '—'}</strong></td>
    <td>${r.unit || '—'}</td>
    <td>${refRange}</td>
    <td><span class="flag-${r.flag || 'N'}">${r.flag || 'N'}</span></td>
    <td><span class="${srcClass}">${srcLabel}</span></td>
    <td><span class="status-${r.status}">${r.status}</span></td>
    <td>
      ${r.status === 'PENDING' ? `<button class="btn-primary btn-sm" onclick="openValidateModal(${r.id},'${r.test_name}','${r.result_value}','${r.flag}')">✅ Validate</button>` : ''}
      ${(r.flag === 'HH' || r.flag === 'LL') && r.is_validated && !r.archived_in_book
        ? `<button class="btn-danger btn-sm" onclick="openArchiveModal(${r.id})">📖 Archive</button>` : ''}
    </td>
  </tr>`;
}

function sectionLabel(s) {
  const map = { GENERAL:'🟡 General', HORMONES:'🟣 Hormones', MARKERS:'🔵 Markers' };
  return map[s] || s;
}

function openResultModal() {
  showModal('result-modal');
}

function updateSourceBadge() {
  const src   = document.getElementById('rmod-source').value;
  const badge = document.getElementById('result-source-badge');
  const row   = document.getElementById('analyzer-row');
  if (src === 'AUTOMATED') {
    badge.textContent = '🤖 Automated Entry';
    badge.classList.add('auto');
    row.style.display = 'block';
  } else {
    badge.textContent = '👤 Manual Entry';
    badge.classList.remove('auto');
    row.style.display = 'none';
  }
}

function flagChanged() {
  const flag  = document.getElementById('rmod-flag').value;
  const panel = document.getElementById('critical-panel');
  panel.style.display = (flag === 'HH' || flag === 'LL') ? 'block' : 'none';
}

function autoFlag() {
  const val = parseFloat(document.getElementById('rmod-value').value);
  const ref  = document.getElementById('rmod-ref').value;
  if (isNaN(val) || !ref) return;
  const parts = ref.match(/([0-9.]+)\s*[-–]\s*([0-9.]+)/);
  if (!parts) return;
  const lo = parseFloat(parts[1]), hi = parseFloat(parts[2]);
  let flag = 'N';
  if (val < lo * 0.7) flag = 'LL';
  else if (val < lo)  flag = 'L';
  else if (val > hi * 1.3) flag = 'HH';
  else if (val > hi)  flag = 'H';
  document.getElementById('rmod-flag').value = flag;
  flagChanged();
}

async function submitResult() {
  const labreqId = document.getElementById('rmod-labreq').value.trim();
  if (!labreqId) { alert('Please enter a Lab Request ID'); return; }

  const payload = {
    lab_request:    labreqId,
    section:        document.getElementById('rmod-section').value,
    result_value:   document.getElementById('rmod-value').value.trim(),
    unit:           document.getElementById('rmod-unit').value.trim(),
    reference_range_text: document.getElementById('rmod-ref').value.trim(),
    flag:           document.getElementById('rmod-flag').value,
    result_source:  document.getElementById('rmod-source').value,
    analyzer_name:  document.getElementById('rmod-analyzer').value.trim(),
    entry_mode:     'SINGLE',
    notes:          document.getElementById('rmod-notes').value.trim(),
  };

  // Numeric value
  const num = parseFloat(payload.result_value);
  if (!isNaN(num)) payload.numeric_value = num;

  try {
    await apiFetch(BIOCHEM_API + 'results/', 'POST', payload);
    closeModal('result-modal');
    loadResults();
    loadDashboard();
    showNotif('Result saved');
  } catch (e) { alert('Error: ' + e.message); }
}

// ─── Validation ───────────────────────────────────────────────────────────────

async function loadValidation() {
  const list = document.getElementById('validation-list');
  list.innerHTML = '<div class="empty-state">Loading…</div>';

  try {
    const data = await apiFetch(BIOCHEM_API + 'results/?pending_validation=true');
    const items = data.results || data;
    const count = document.getElementById('val-count');
    count.textContent = items.length + ' result' + (items.length !== 1 ? 's' : '') + ' awaiting validation';

    if (!items.length) {
      list.innerHTML = '<div class="empty-state">✅ No pending validations</div>';
      return;
    }
    list.innerHTML = items.map(r => validationItem(r)).join('');
  } catch (e) {
    list.innerHTML = '<div class="empty-state">Error loading validation queue</div>';
  }
}

function validationItem(r) {
  const isCrit = r.flag === 'HH' || r.flag === 'LL';
  return `
  <div class="val-item ${isCrit ? 'critical' : ''}">
    <div class="val-info">
      <div class="val-test">${r.test_name || 'Unknown test'} <span class="flag-${r.flag || 'N'}">${r.flag || 'N'}</span></div>
      <div class="val-patient">Patient: ${r.patient_name || '—'} &nbsp;|&nbsp; Section: ${sectionLabel(r.section)}</div>
    </div>
    <div class="val-result">${r.result_value} ${r.unit || ''}</div>
    <div class="val-actions">
      <button class="btn-primary btn-sm"
        onclick="openValidateModal(${r.id},'${r.test_name}','${r.result_value}','${r.flag}')">
        ✅ Validate
      </button>
    </div>
  </div>`;
}

function openValidateModal(id, test, value, flag) {
  currentResultId = id;
  document.getElementById('validate-summary').innerHTML = `
    <p><strong>Test:</strong> ${test}</p>
    <p><strong>Result:</strong> ${value} &nbsp; <span class="flag-${flag}">${flag}</span></p>
    <p style="color:#6c757d;font-size:.83rem">Confirm this result is technically correct before releasing.</p>`;
  showModal('validate-modal');
}

async function confirmValidate() {
  if (!currentResultId) return;
  try {
    await apiFetch(BIOCHEM_API + `results/${currentResultId}/validate/`, 'POST', {});
    closeModal('validate-modal');
    loadValidation();
    loadResults();
    loadDashboard();
    showNotif('Result validated ✅');
    currentResultId = null;
  } catch (e) { alert('Error: ' + e.message); }
}

// ─── Archive to Critical Book ─────────────────────────────────────────────────

function openArchiveModal(id) {
  currentResultId = id;
  showModal('archive-modal');
}

async function confirmArchive() {
  if (!currentResultId) return;
  const payload = {
    clinician_notified:  true,
    clinician_name:      document.getElementById('arch-clinician').value.trim(),
    notification_method: document.getElementById('arch-method').value,
    read_back_confirmed: document.getElementById('arch-readback').checked,
  };
  try {
    const data = await apiFetch(BIOCHEM_API + `results/${currentResultId}/archive-critical/`, 'POST', payload);
    closeModal('archive-modal');
    showNotif(`📖 Archived as ${data.entry_number}`);
    loadCriticalBook();
    currentResultId = null;
  } catch (e) { alert('Error: ' + e.message); }
}

// ─── Critical Book ────────────────────────────────────────────────────────────

async function loadCriticalBook() {
  const tbody = document.getElementById('book-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading…</td></tr>';
  const params = new URLSearchParams();
  const fl  = document.getElementById('book-filter-flag')?.value;
  const sec = document.getElementById('book-filter-section')?.value;
  if (fl)  params.set('flag',    fl);
  if (sec) params.set('section', sec);

  try {
    const data = await apiFetch(BIOCHEM_API + 'book/?' + params);
    const list = data.results || data;
    if (!list.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No critical book entries found</td></tr>';
      return;
    }
    tbody.innerHTML = list.map(b => bookRow(b)).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Error loading critical book</td></tr>';
  }
}

function bookRow(b) {
  return `
  <tr>
    <td><code>${b.entry_number}</code></td>
    <td>${b.patient_name || '—'}</td>
    <td>${b.test_name}</td>
    <td>${sectionLabel(b.section)}</td>
    <td><strong>${b.result_value} ${b.unit || ''}</strong></td>
    <td><span class="flag-${b.flag}">${b.flag}</span></td>
    <td>${b.clinician_notified
          ? '✅ ' + (b.clinician_name || 'Notified') + ' via ' + (b.notification_method || '—')
          : '❌ Not notified'}</td>
    <td>${b.read_back_confirmed ? '✅ Confirmed' : '—'}</td>
    <td>${fmtDate(b.archived_at)}</td>
    <td><code title="${b.pqc_hash}">${(b.pqc_hash || '').substring(0,10)}…</code></td>
  </tr>`;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function apiFetch(url, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(url, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(JSON.stringify(err));
  }
  return res.status === 204 ? {} : res.json();
}

function getCookie(name) {
  const m = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return m ? decodeURIComponent(m[1]) : '';
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? '—';
}

function fmtDate(str) {
  if (!str) return '—';
  return new Date(str).toLocaleString('en-GB', { day:'2-digit', month:'short', year:'numeric',
    hour:'2-digit', minute:'2-digit' });
}

function showModal(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'flex';
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}

function showNotif(msg) {
  // Use global NEXUS notif if available, else alert
  if (window.NEXUS?.notify) { window.NEXUS.notify(msg); return; }
  const n = document.createElement('div');
  n.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;background:#0D1F3E;color:#fff;'
    + 'padding:.7rem 1.2rem;border-radius:8px;z-index:9999;font-size:.87rem;';
  n.textContent = msg;
  document.body.appendChild(n);
  setTimeout(() => n.remove(), 3000);
}

function sectionChanged() {
  const section = document.getElementById('rmod-section')?.value;
  const unitHints = {
    GENERAL:  'mmol/L, U/L, g/L, µmol/L',
    HORMONES: 'mIU/L, pmol/L, nmol/L, IU/L',
    MARKERS:  'ng/mL, U/mL, µg/L, IU/mL',
  };
  const testEl = document.getElementById('rmod-test-name');
  if (testEl) testEl.placeholder = `e.g. ${section === 'HORMONES' ? 'TSH, FT4, Cortisol' : section === 'MARKERS' ? 'AFP, CEA, PSA' : 'Glucose, Creatinine, ALT'}`;
  const unitEl = document.getElementById('rmod-unit');
  if (unitEl && !unitEl.value) unitEl.placeholder = unitHints[section] || 'e.g. mmol/L';
}
