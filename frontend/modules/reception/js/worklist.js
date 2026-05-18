/**
 * NEXUS ALIS-X — Worklist Home (All Departments)
 * Loads today's worklist stats + full entry table.
 */
'use strict';

const API_BASE = '/api/v1';
const token    = () => localStorage.getItem('access_token') || '';
const headers  = () => ({ 'Content-Type': 'application/json',
                           'Authorization': 'Bearer ' + token() });

let _allRows  = [];     // cached full data set for client-side filter
let _rejectId = null;   // entry_id being rejected

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('wl-date').textContent =
    new Date().toLocaleDateString('en-GB', { weekday:'long', day:'numeric',
      month:'long', year:'numeric' });

  // Auto-detect current shift
  const h = new Date().getHours();
  const shiftEl = document.getElementById('shift-filter');
  if (shiftEl) {
    if (h >= 6  && h < 14) shiftEl.value = 'Morning';
    else if (h >= 14 && h < 22) shiftEl.value = 'Afternoon';
    else shiftEl.value = 'Night';
  }

  loadAll();
});

// ── Load all data ─────────────────────────────────────────────────────────────
async function loadAll() {
  await Promise.all([loadStats(), loadTable()]);
}

async function loadStats() {
  try {
    const r = await fetch(`${API_BASE}/worklist/stats`, { headers: headers() });
    if (!r.ok) return;
    const d = await r.json();
    setText('kpi-total',      d.total);
    setText('kpi-received',   d.received);
    setText('kpi-in-progress',d.in_progress);
    setText('kpi-completed',  d.completed);
    setText('kpi-rejected',   d.rejected);
    setText('kpi-pct',        d.completion_pct + '%');
    renderDeptCards(d.by_department || {});
  } catch(e) { console.error('Stats error', e); }
}

async function loadTable() {
  const shift  = document.getElementById('shift-filter')?.value || '';
  const dept   = document.getElementById('dept-filter')?.value  || '';
  const status = document.getElementById('status-filter')?.value || '';

  let url = `${API_BASE}/worklist/all?limit=500`;
  if (dept)   url += `&department=${encodeURIComponent(dept)}`;
  if (status) url += `&status=${encodeURIComponent(status)}`;

  const tbody = document.getElementById('wl-tbody');
  tbody.innerHTML = '<tr><td colspan="11" class="empty-row"><i class="fas fa-spinner fa-spin"></i> Loading…</td></tr>';

  try {
    const r = await fetch(url, { headers: headers() });
    if (!r.ok) { tbody.innerHTML = '<tr><td colspan="11" class="empty-row">Failed to load</td></tr>'; return; }
    _allRows = await r.json();
    renderTable(_allRows);
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty-row">Network error: ${e.message}</td></tr>`;
  }
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderDeptCards(byDept) {
  const container = document.getElementById('dept-cards');
  if (!container) return;
  const depts = [
    ['hematology',  'Hematology',   '#e53935'],
    ['biochemistry','Biochemistry',  '#1565c0'],
    ['microbiology','Microbiology',  '#2e7d32'],
    ['urinalysis',  'Urinalysis',    '#f57f17'],
    ['coagulation', 'Coagulation',   '#6a1b9a'],
    ['serology',    'Serology',      '#0277bd'],
    ['molecular',   'Molecular',     '#4a148c'],
    ['blood_bank',  'Blood Bank',    '#b71c1c'],
    ['pathology',   'Pathology',     '#37474f'],
    ['toxicology',  'Toxicology',    '#e65100'],
  ];
  container.innerHTML = depts.map(([key, name, color]) => {
    const cnt = byDept[key] || 0;
    return `
      <a href="/worklist/${key}" class="dept-card" title="Open ${name} worklist">
        <div class="dept-card-stripe" style="background:${color}"></div>
        <div class="dept-card-name">${name}</div>
        <div class="dept-card-count">${cnt}</div>
        <div class="dept-card-sub">samples today</div>
      </a>`;
  }).join('');
}

function renderTable(rows) {
  const tbody = document.getElementById('wl-tbody');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty-row"><i class="fas fa-inbox"></i> No entries for selected filters</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => rowHtml(r)).join('');
}

function rowHtml(r) {
  const isRejected = r.status === 'REJECTED';
  const isStat     = r.priority === 'stat';
  let cls = '';
  if (isStat)     cls = 'row-stat';
  if (isRejected) cls = 'row-rejected';

  const tubeDot  = r.tube_color
    ? `<span class="tube-dot" style="background:${tubeColorCss(r.tube_color)}" title="${r.tube_color}"></span>`
    : '';

  return `
  <tr class="${cls}" data-id="${r.id}" data-search="${esc((r.sid||'') + (r.patient_name||'') + (r.test_names||'') + (r.department||'')).toLowerCase()}">
    <td><span class="rack-num">${r.rack_number ?? '—'}</span></td>
    <td><span class="sid-badge">${esc(r.sid)}</span>
        ${r.is_rejection ? '<span title="Rejection replacement" style="font-size:.65rem;color:#dc2626;margin-left:3px">↺</span>' : ''}
    </td>
    <td>${r.cid ? `<span class="cid-badge">${esc(r.cid)}</span>` : '<span style="color:#cbd5e1">—</span>'}</td>
    <td>
      <div style="font-weight:600;font-size:.8rem">${esc(r.patient_name||'—')}</div>
      <div style="font-size:.68rem;color:#64748b">${esc(r.pid||'')}</div>
    </td>
    <td>${tubeDot}${esc(r.specimen||'—')}</td>
    <td style="white-space:normal;max-width:200px;font-size:.75rem">${esc(r.test_names||'—')}</td>
    <td><span style="font-size:.75rem;text-transform:capitalize">${esc(r.department||'—')}</span></td>
    <td><span class="badge ${priorityClass(r.priority)}">${esc((r.priority||'').toUpperCase())}</span></td>
    <td><span class="status-pill status-${r.status}">
          <i class="fas ${statusIcon(r.status)}"></i> ${r.status}
        </span>
        ${r.is_high_risk ? '<span class="hr-badge" title="High-Risk"><i class="fas fa-biohazard"></i> BSL</span>' : ''}
    </td>
    <td>${r.received_at ? formatTime(r.received_at) : '—'}</td>
    <td><i class="fas ${r.label_printed ? 'fa-print label-printed' : 'fa-print label-unprinted'}"
           title="${r.label_printed ? 'Label printed' : 'Not yet printed'}"></i></td>
    <td>
      <div style="display:flex;gap:4px;justify-content:center">
        <a href="/api/v1/worklist/labels/${r.id}/pdf?copies=1"
           class="action-btn success" target="_blank" title="Print label PDF">
          <i class="fas fa-tag"></i>
        </a>
        ${!isRejected ? `
        <button class="action-btn danger" title="Reject sample"
                onclick="openRejectModal(${r.id},'${esc(r.sid)}')">
          <i class="fas fa-xmark"></i>
        </button>` : ''}
        <a href="/worklist/${r.department}"
           class="action-btn" title="Open department worklist">
          <i class="fas fa-arrow-right"></i>
        </a>
      </div>
    </td>
  </tr>`;
}

// ── Filter ────────────────────────────────────────────────────────────────────
function filterTable() {
  const q    = (document.getElementById('wl-search')?.value || '').toLowerCase();
  const dept = (document.getElementById('dept-filter')?.value || '').toLowerCase();
  const stat = (document.getElementById('status-filter')?.value || '').toUpperCase();

  const filtered = _allRows.filter(r => {
    if (dept && r.department !== dept) return false;
    if (stat && r.status !== stat)     return false;
    if (q) {
      const hay = ((r.sid||'') + (r.patient_name||'') + (r.test_names||'') + (r.department||'')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  renderTable(filtered);
}

// ── Reject modal ──────────────────────────────────────────────────────────────
function openRejectModal(id, sid) {
  _rejectId = id;
  document.getElementById('reject-sid').textContent = sid;
  document.getElementById('reject-reason-select').value = '';
  document.getElementById('reject-reason-text').value   = '';
  document.getElementById('reject-modal').classList.add('open');
}
function closeRejectModal() {
  document.getElementById('reject-modal').classList.remove('open');
  _rejectId = null;
}
function syncRejectReason() {
  const sel = document.getElementById('reject-reason-select').value;
  if (sel && sel !== 'Other') {
    document.getElementById('reject-reason-text').value = sel;
  }
}
async function confirmReject() {
  const reason = document.getElementById('reject-reason-text').value.trim();
  if (!reason) { NEXUS.Toast.error('Enter rejection reason'); return; }
  if (!_rejectId) return;

  try {
    const r = await fetch(`${API_BASE}/worklist/entry/${_rejectId}/reject`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ rejection_reason: reason }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Reject failed');
    NEXUS.Toast.success(d.message || 'Sample rejected. Replacement: ' + d.replacement?.sid);
    closeRejectModal();
    loadAll();
  } catch(e) {
    NEXUS.Toast.error('Reject failed', e.message);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? '—';
}
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                         .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function formatTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('en-GB', { hour:'2-digit', minute:'2-digit' });
}
function priorityClass(p) {
  const m = { stat:'badge-stat', urgent:'badge-urgent', routine:'badge-routine' };
  return m[(p||'').toLowerCase()] || 'badge-routine';
}
function statusIcon(s) {
  const m = {
    PENDING:'fa-clock', RECEIVED:'fa-inbox', IN_PROGRESS:'fa-flask',
    COMPLETED:'fa-circle-check', RELEASED:'fa-paper-plane', REJECTED:'fa-circle-xmark',
  };
  return m[s] || 'fa-circle';
}
function tubeColorCss(name) {
  const m = {
    lavender:'#c4b5fd', blue:'#3b82f6', red:'#ef4444', green:'#22c55e',
    grey:'#94a3b8', yellow:'#eab308', orange:'#f97316', brown:'#78350f',
    purple:'#a855f7', clear:'#e0f2fe', white:'#f8fafc', formalin:'#bbf7d0',
  };
  return m[(name||'').toLowerCase()] || '#e4e8f0';
}
function printPage() { window.print(); }
