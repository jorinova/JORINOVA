/* Immunology Module — NEXUS ALIS-X */
'use strict';

const API = '/api/v1';
let _currentCategory = 'HIV';

function authHeader() {
  const t = localStorage.getItem('access_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
}
async function apiFetch(url, opts = {}) {
  const r = await fetch(url, { headers: { 'Content-Type': 'application/json', ...authHeader() }, ...opts });
  if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r.status}`); }
  return r.json();
}
function toast(msg, type = 'success') {
  if (window.NexusCore?.toast) { window.NexusCore.toast(msg, type); return; }
  console.log('[Immunology]', type, msg);
}
function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val ?? '—'; }

/* ── Tab switching ───────────────────────────────────────────── */
function switchTab(tab) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelector(`.tab-btn[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`tab-${tab}`)?.classList.add('active');
  if (tab === 'hiv')        loadHIV();
  if (tab === 'hepatitis')  loadHep();
  if (tab === 'autoimmune') loadAutoimmune();
  if (tab === 'allergy')    loadAllergy();
  if (tab === 'markers')    loadMarkers();
  if (tab === 'flowcyto')   loadFlowCyto();
  if (tab === 'validation') loadImmValidation();
}
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

/* ── Dashboard ───────────────────────────────────────────────── */
async function loadDashboard() {
  // For now uses biochemistry endpoint as proxy — department-specific endpoint to be added
  try {
    const r = await apiFetch(`${API}/laboratory/requests?status=submitted,received&limit=1`);
    setText('stat-pending', r.length ? '—' : '0');
  } catch(e) {}
}

/* ── Generic result table loader using lab results API ──────── */
async function loadResultsTable(tbodyId, filters = {}) {
  const tbody = document.getElementById(tbodyId);
  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="99" class="empty-state">Loading…</td></tr>';
  try {
    const params = new URLSearchParams(filters);
    const data = await apiFetch(`${API}/laboratory/results?${params}`);
    if (!data.length) {
      tbody.innerHTML = `<tr><td colspan="99" class="empty-state">No results found.</td></tr>`;
      return;
    }
    return data;
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="99" class="empty-state">Error: ${e.message}</td></tr>`;
    return [];
  }
}

/* ── HIV results ─────────────────────────────────────────────── */
async function loadHIV() {
  const test   = document.getElementById('hiv-filter-test')?.value  || '';
  const result = document.getElementById('hiv-filter-result')?.value || '';
  const date   = document.getElementById('hiv-filter-date')?.value   || '';
  const tbody  = document.getElementById('hiv-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading…</td></tr>';

  try {
    const params = new URLSearchParams();
    if (test)   params.set('test_code', test);
    if (date)   params.set('date', date);
    const data = await apiFetch(`${API}/laboratory/results?department=SERO&${params}&limit=50`);
    const filtered = result ? data.filter(r => r.qualitative_value === result || r.flag === result) : data;

    if (!filtered.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No HIV results found.</td></tr>'; return;
    }
    tbody.innerHTML = filtered.map(r => {
      const qval = r.qualitative_value || r.result_value || '—';
      const isReact = qval.toUpperCase().includes('REACTIVE') || r.flag === 'POS';
      return `<tr>
        <td><strong>${r.lab_id || r.lid || '—'}</strong></td>
        <td>${r.pid || '—'}<br><small>${r.lid || ''}</small></td>
        <td>${r.test_name || '—'}</td>
        <td>${r.analyzer_name || r.entry_mode || 'ELISA'}</td>
        <td><span class="res-${isReact ? 'REACTIVE' : 'NON_REACTIVE'}">${qval}</span></td>
        <td>${r.numeric_value ? r.numeric_value.toFixed(2) : '—'}</td>
        <td>${r.ai_interpretation ? '🔄 See note' : '—'}</td>
        <td>${isReact ? '<span style="color:#dc3545">⚠️ Required</span>' : '✓ N/A'}</td>
        <td><span class="status-badge">${r.status || 'PENDING'}</span></td>
        <td>
          ${!r.is_validated ? `<button class="btn-primary btn-sm" onclick="validate(${r.id})">Validate</button>` : '<span style="color:#28a745">✔</span>'}
        </td>
      </tr>`;
    }).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

/* ── Hepatitis results ───────────────────────────────────────── */
async function loadHep() {
  const tbody = document.getElementById('hep-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Hepatitis results coming from serology department integration…</td></tr>';
}

/* ── Autoimmune results ─────────────────────────────────────── */
async function loadAutoimmune() {
  const tbody = document.getElementById('auto-tbody');
  tbody.innerHTML = '<tr><td colspan="11" class="empty-state">Autoimmune panel linked to biochemistry/serology results…</td></tr>';
}

/* ── Allergy panel ──────────────────────────────────────────── */
async function loadAllergy() {
  const tbody = document.getElementById('alg-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Allergy panel results — enter via result modal…</td></tr>';
}

/* ── Tumour markers ─────────────────────────────────────────── */
async function loadMarkers() {
  const tbody = document.getElementById('mrk-tbody');
  tbody.innerHTML = '<tr><td colspan="11" class="empty-state">Tumour markers linked to biochemistry markers section…</td></tr>';
}

/* ── Flow cytometry ─────────────────────────────────────────── */
async function loadFlowCyto() {
  const tbody = document.getElementById('fc-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Flow cytometry results — specialized analyzer integration…</td></tr>';
}

/* ── Validation queue ───────────────────────────────────────── */
async function loadImmValidation() {
  const list = document.getElementById('imm-val-list');
  list.innerHTML = '<div class="empty-state">Validation queue loads from lab results system.</div>';
  setText('imm-val-count', '—');
}

/* ── Validate result ────────────────────────────────────────── */
async function validate(resultId) {
  try {
    await apiFetch(`${API}/laboratory/results/${resultId}/validate`, { method: 'POST' });
    toast('Result validated.');
    const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
    if (activeTab === 'hiv') loadHIV();
  } catch(e) { toast(e.message, 'error'); }
}

/* ── Modal ──────────────────────────────────────────────────── */
function openResultModal(category) {
  _currentCategory = category;
  const titles = {
    HIV: '🔴 Enter HIV Result', HEP: '🟡 Enter Hepatitis Result',
    AUTO: '🛡️ Enter Autoimmune Result', ALLERGY: '🌿 Enter Allergy Result',
    MARKER: '🔵 Enter Tumour Marker', FLOWCYTO: '🔬 Enter Flow Cytometry',
  };
  document.getElementById('result-modal-title').textContent = titles[category] || '🛡️ Enter Result';
  document.getElementById('result-modal').style.display = 'flex';

  // Attach AI panel to result modal
  if (window.AIResultPanel) {
    AIResultPanel.attach('aip-result-modal', {
      testCodeField: 'rmod-code',
      valueField:    'rmod-value',
      unitField:     'rmod-unit',
    });
  }
}

async function submitResult() {
  const labreq = +document.getElementById('rmod-labreq').value;
  if (!labreq) { toast('Lab request ID required', 'error'); return; }
  const body = {
    lab_request_id: labreq,
    test_name:       document.getElementById('rmod-test').value,
    result_value:    document.getElementById('rmod-result').value,
    numeric_value:   parseFloat(document.getElementById('rmod-value').value) || null,
    unit:            document.getElementById('rmod-unit').value || null,
    qualitative_value: document.getElementById('rmod-result').value,
    result_source:   document.getElementById('rmod-source').value,
    analyzer_name:   document.getElementById('rmod-method').value,
    flag:            document.getElementById('rmod-result').value === 'REACTIVE' ? 'POS' : 'N',
    notes:           document.getElementById('rmod-notes').value || null,
  };
  try {
    await apiFetch(`${API}/laboratory/results`, { method: 'POST', body: JSON.stringify(body) });
    closeModal('result-modal');
    toast('Immunology result saved.');
    const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
    if (activeTab === 'hiv') loadHIV();
  } catch(e) { toast(e.message, 'error'); }
}

function closeModal(id) { document.getElementById(id).style.display = 'none'; }
document.querySelectorAll('.modal-overlay').forEach(o => {
  o.addEventListener('click', e => { if (e.target === o) o.style.display = 'none'; });
});

/* ── Init ───────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  setInterval(loadDashboard, 60000);
});
