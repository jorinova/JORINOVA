/**
 * NEXUS ALIS-X — Department Worklist View
 * Shows all samples for one department, current shift.
 * Supports: status updates, rejection, label printing, TAT display.
 */
'use strict';

const API_BASE = '/api/v1';
const token    = () => localStorage.getItem('access_token') || '';
const headers  = () => ({ 'Content-Type': 'application/json',
                           'Authorization': 'Bearer ' + token() });

// Read department from page data attribute (set by main.py template context)
const DEPT = (() => {
  const el = document.getElementById('dept-wl-main');
  return (el?.dataset.department || window.location.pathname.split('/').filter(Boolean).pop() || 'hematology').toLowerCase();
})();

const DEPT_NAMES = {
  hematology:   'Hematology',
  biochemistry: 'Biochemistry',
  microbiology: 'Microbiology',
  urinalysis:   'Urinalysis',
  coagulation:  'Coagulation',
  serology:     'Serology',
  molecular:    'Molecular',
  blood_bank:   'Blood Bank',
  pathology:    'Pathology',
  toxicology:   'Toxicology',
};

let _rows     = [];
let _rejectId = null;

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const deptName = DEPT_NAMES[DEPT] || DEPT;
  document.title = `${deptName} Worklist — NEXUS ALIS-X`;
  const titleEl = document.getElementById('dept-title');
  const subEl   = document.getElementById('dept-sub');
  if (titleEl) titleEl.textContent = `${deptName} Worklist`;
  if (subEl)   subEl.textContent   = new Date().toLocaleDateString('en-GB',
    { weekday:'long', day:'numeric', month:'long', year:'numeric' });

  // Auto-detect shift
  const h = new Date().getHours();
  const shiftEl = document.getElementById('shift-filter');
  if (shiftEl) {
    if      (h >= 6  && h < 14) shiftEl.value = 'Morning';
    else if (h >= 14 && h < 22) shiftEl.value = 'Afternoon';
    else                         shiftEl.value = 'Night';
  }

  loadDeptWorklist();

  // Auto-refresh every 60s
  setInterval(loadDeptWorklist, 60_000);
});

// ── Load ──────────────────────────────────────────────────────────────────────
async function loadDeptWorklist() {
  const shift  = document.getElementById('shift-filter')?.value || '';
  const status = document.getElementById('status-filter')?.value  || '';

  let url = `${API_BASE}/worklist/department/${DEPT}`;
  const params = [];
  if (shift)  params.push(`shift=${encodeURIComponent(shift)}`);
  if (status) params.push(`status=${encodeURIComponent(status)}`);
  if (params.length) url += '?' + params.join('&');

  const tbody = document.getElementById('dept-tbody');
  try {
    const r = await fetch(url, { headers: headers() });
    if (!r.ok) {
      tbody.innerHTML = `<tr><td colspan="11" class="empty-row">Error ${r.status}</td></tr>`;
      return;
    }
    _rows = await r.json();
    updateKPI(_rows);
    renderRows(_rows);
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty-row">Network error: ${e.message}</td></tr>`;
  }
}

// ── KPI ───────────────────────────────────────────────────────────────────────
function updateKPI(rows) {
  const total    = rows.length;
  const stat     = rows.filter(r => r.priority === 'stat').length;
  const pending  = rows.filter(r => ['PENDING','RECEIVED'].includes(r.status)).length;
  const progress = rows.filter(r => r.status === 'IN_PROGRESS').length;
  const done     = rows.filter(r => ['COMPLETED','RELEASED'].includes(r.status)).length;

  setText('kpi-total',    total);
  setText('kpi-stat',     stat);
  setText('kpi-pending',  pending);
  setText('kpi-progress', progress);
  setText('kpi-done',     done);
  setText('dept-badge',   `${total} sample${total !== 1 ? 's' : ''} today`);
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderRows(rows) {
  const tbody = document.getElementById('dept-tbody');
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty-row">
      <i class="fas fa-inbox"></i> No samples for ${DEPT_NAMES[DEPT] || DEPT} in this shift
    </td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(r => rowHtml(r)).join('');
}

function rowHtml(r) {
  const isStat     = r.priority === 'stat';
  const isRejected = r.status   === 'REJECTED';
  let cls = isRejected ? 'row-rejected' : (isStat ? 'row-stat' : '');

  const tubeDot = r.tube_color
    ? `<span class="tube-dot" style="background:${tubeColorCss(r.tube_color)}" title="${esc(r.tube_color)}"></span>` : '';

  const tat = r.received_at ? tatDisplay(r.received_at, r.completed_at) : '—';

  const canStart    = r.status === 'RECEIVED';
  const canComplete = r.status === 'IN_PROGRESS';
  const canRelease  = r.status === 'COMPLETED';
  const canReject   = !['REJECTED','RELEASED','COMPLETED'].includes(r.status);

  return `
  <tr class="${cls}" data-id="${r.id}"
      data-search="${esc(((r.sid||'')+(r.patient_name||'')+(r.test_names||'')).toLowerCase())}">
    <td>
      <span class="rack-num">${r.rack_number ?? '—'}</span>
    </td>
    <td>
      <span class="sid-badge">${esc(r.sid)}</span>
      ${r.is_rejection ? '<span title="Rejection replacement" style="font-size:.65rem;color:#dc2626;margin-left:3px" title="Replacement for rejected sample">↺${esc(r.original_sid||"")}</span>' : ''}
    </td>
    <td>
      ${r.cid
        ? `<span class="cid-badge">${esc(r.cid)}</span><br><span style="font-size:.6rem;color:#7c3aed">Plate label</span>`
        : '<span style="color:#cbd5e1;font-size:.75rem">—</span>'}
    </td>
    <td>
      <div style="font-weight:600;font-size:.8rem">${esc(r.patient_name||'—')}</div>
      <div style="font-size:.68rem;color:#64748b">
        ${esc(r.pid||'')}
        ${r.is_high_risk ? '<span class="hr-badge"><i class="fas fa-biohazard"></i></span>' : ''}
      </div>
    </td>
    <td>
      ${tubeDot}${esc(r.specimen||r.specimen_acronym||'—')}
      ${r.volume_ml ? `<br><span style="font-size:.65rem;color:#94a3b8">${r.volume_ml} mL</span>` : ''}
    </td>
    <td style="white-space:normal;max-width:220px;line-height:1.5;font-size:.76rem">
      ${esc(r.test_names||'—')}
    </td>
    <td>
      <span class="badge ${priorityClass(r.priority)}">${esc((r.priority||'').toUpperCase())}</span>
    </td>
    <td>
      <span class="status-pill status-${r.status}">
        <i class="fas ${statusIcon(r.status)}"></i> ${r.status.replace('_',' ')}
      </span>
    </td>
    <td><span class="${tat.cls || ''}">${tat.text || tat}</span></td>
    <td>
      ${r.label_printed
        ? `<span class="label-printed" title="Printed ${r.label_print_count}×"><i class="fas fa-print"></i></span>`
        : `<button class="action-btn" title="Print label" onclick="printLabel(${r.id})">
             <i class="fas fa-print label-unprinted"></i>
           </button>`}
    </td>
    <td>
      <div style="display:flex;gap:3px;justify-content:center;flex-wrap:wrap">
        ${canStart    ? `<button class="action-btn" title="Start processing" onclick="updateStatus(${r.id},'IN_PROGRESS')"><i class="fas fa-flask"></i></button>` : ''}
        ${canComplete ? `<button class="action-btn success" title="Mark completed" onclick="updateStatus(${r.id},'COMPLETED')"><i class="fas fa-circle-check"></i></button>` : ''}
        ${canRelease  ? `<button class="action-btn success" title="Release to doctor" onclick="updateStatus(${r.id},'RELEASED')"><i class="fas fa-paper-plane"></i></button>` : ''}
        ${canReject   ? `<button class="action-btn danger" title="Reject sample" onclick="openRejectModal(${r.id},'${esc(r.sid)}')"><i class="fas fa-xmark"></i></button>` : ''}
        <a href="/api/v1/worklist/labels/${r.id}/pdf" class="action-btn" target="_blank" title="Download label PDF"><i class="fas fa-tag"></i></a>
      </div>
    </td>
  </tr>`;
}

// ── Filter ────────────────────────────────────────────────────────────────────
function filterRows() {
  const q    = (document.getElementById('wl-search')?.value || '').toLowerCase();
  const stat = (document.getElementById('status-filter')?.value || '').toUpperCase();

  const filtered = _rows.filter(r => {
    if (stat && r.status !== stat) return false;
    if (q) {
      const hay = ((r.sid||'') + (r.patient_name||'') + (r.test_names||'')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  renderRows(filtered);
}

// ── Status update ─────────────────────────────────────────────────────────────
async function updateStatus(id, newStatus) {
  try {
    const r = await fetch(`${API_BASE}/worklist/entry/${id}/status`, {
      method:  'PUT',
      headers: headers(),
      body:    JSON.stringify({ status: newStatus }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Update failed');
    NEXUS.Toast.success(`Status → ${newStatus}`);
    loadDeptWorklist();
  } catch(e) {
    NEXUS.Toast.error('Update failed', e.message);
  }
}

// ── Label print ───────────────────────────────────────────────────────────────
async function printLabel(id) {
  // Open PDF in new tab (browser print dialog will appear)
  window.open(`${API_BASE}/worklist/labels/${id}/pdf?copies=1`, '_blank');
  // Record print
  await fetch(`${API_BASE}/worklist/labels/${id}/print?label_type=TUBE`, {
    method: 'POST', headers: headers(),
  });
  loadDeptWorklist();
}

async function printLabels() {
  // Print all labels for today's entries in this department
  const ids = _rows.filter(r => r.status !== 'REJECTED').map(r => r.id);
  if (!ids.length) { NEXUS.Toast.info('No labels to print'); return; }
  // Print as batch by opening each PDF (or use multi-label endpoint)
  // For simplicity, open the first request's batch PDF
  const reqIds = [...new Set(_rows.filter(r => r.status !== 'REJECTED').map(r => r.lab_request_id))];
  for (const rid of reqIds) {
    window.open(`${API_BASE}/worklist/labels/request/${rid}/pdf?copies=1`, '_blank');
  }
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
  if (!reason) { NEXUS.Toast.error('Please enter the rejection reason'); return; }
  if (!_rejectId) return;

  try {
    const r = await fetch(`${API_BASE}/worklist/entry/${_rejectId}/reject`, {
      method:  'POST',
      headers: headers(),
      body:    JSON.stringify({ rejection_reason: reason }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Reject failed');
    NEXUS.Toast.success(
      `Sample rejected (${d.rejected_sid}). New SID: ${d.replacement?.sid} created.`
    );
    closeRejectModal();
    loadDeptWorklist();
  } catch(e) {
    NEXUS.Toast.error('Rejection failed', e.message);
  }
}

// ── TAT display ───────────────────────────────────────────────────────────────
function tatDisplay(receivedIso, completedIso) {
  const start = new Date(receivedIso);
  const end   = completedIso ? new Date(completedIso) : new Date();
  const mins  = Math.round((end - start) / 60000);
  if (mins < 0) return { text: '—', cls: '' };
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  const text = h > 0 ? `${h}h ${m}m` : `${m}m`;
  const cls  = mins > 120 ? 'tat-over' : mins > 60 ? 'tat-warn' : 'tat-ok';
  return { text, cls };
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v ?? '—'; }
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                         .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function priorityClass(p) {
  return ({ stat:'badge-stat', urgent:'badge-urgent', routine:'badge-routine' })[(p||'').toLowerCase()] || 'badge-routine';
}
function statusIcon(s) {
  return ({ PENDING:'fa-clock', RECEIVED:'fa-inbox', IN_PROGRESS:'fa-flask',
             COMPLETED:'fa-circle-check', RELEASED:'fa-paper-plane', REJECTED:'fa-circle-xmark' })[s] || 'fa-circle';
}
function tubeColorCss(n) {
  return ({ lavender:'#c4b5fd', blue:'#3b82f6', red:'#ef4444', green:'#22c55e',
             grey:'#94a3b8', yellow:'#eab308', orange:'#f97316', brown:'#78350f',
             purple:'#a855f7', clear:'#e0f2fe', white:'#f8fafc', formalin:'#bbf7d0' })[(n||'').toLowerCase()] || '#e4e8f0';
}
function printPage() { window.print(); }
