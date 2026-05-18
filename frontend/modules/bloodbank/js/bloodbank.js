/**
 * JORINOVA NEXUS ALIS-X — Blood Bank Module
 * Donors · Blood Inventory · Blood Requests · Crossmatch · Haemovigilance
 */
'use strict';

const BB_API = '/api/v1/blood-bank/';

const BLOOD_GROUPS = ['A+','A-','B+','B-','AB+','AB-','O+','O-'];
const BG_CSS = { 'A+':'Apos','A-':'Aneg','B+':'Bpos','B-':'Bneg',
                 'AB+':'ABpos','AB-':'ABneg','O+':'Opos','O-':'Oneg' };

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
      document.getElementById('tab-' + btn.dataset.tab)?.classList.add('active');
      const tab = btn.dataset.tab;
      if (tab === 'donors')         loadDonors();
      if (tab === 'inventory')      loadInventory();
      if (tab === 'requests')       loadRequests();
      if (tab === 'crossmatch')     loadCrossmatch();
      if (tab === 'haemovigilance') loadHaemovigilance();
    });
  });
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const d = await apiFetch(BB_API + 'stats/');
    setText('hdr-avail', d.total_available);
    setText('hdr-exp',   d.expiring_3d);
    setText('hdr-req',   d.pending_requests);
    setText('kpi-avail',   d.total_available);
    setText('kpi-quar',    d.in_quarantine);
    setText('kpi-res',     d.reserved);
    setText('kpi-exp3',    d.expiring_3d);
    setText('kpi-exp7',    d.expiring_7d);
    setText('kpi-expired', d.expired);
    setText('sum-donors',   d.donors_total);
    setText('sum-eligible', d.donors_eligible + ' eligible');
    setText('sum-hv',       d.hv_reports_total);
    setText('sum-req',      d.pending_requests);
    renderBGBar(d.group_stock || {});
    renderBGGrid(d.group_stock || {});
  } catch (e) { console.warn('Dashboard load error', e); }
}

function renderBGBar(stock) {
  const bar = document.getElementById('bg-inventory-bar');
  if (!bar) return;
  bar.innerHTML = BLOOD_GROUPS.map(bg => {
    const cnt = stock[bg] || 0;
    return `<div class="bg-chip bg-${BG_CSS[bg]}">
      <div class="bg-chip-label">${bg}</div>
      <div class="bg-chip-count">${cnt}</div>
      <div class="bg-chip-sub">units</div>
    </div>`;
  }).join('');
}

function renderBGGrid(stock) {
  const grid = document.getElementById('bg-grid');
  if (!grid) return;
  grid.innerHTML = BLOOD_GROUPS.map(bg => {
    const cnt = stock[bg] || 0;
    const cls = cnt === 0 ? 'zero' : cnt < 3 ? 'low' : 'ok';
    return `<div class="bg-grid-card ${cls}">
      <div class="bg-label">${bg}</div>
      <div class="bg-val">${cnt}</div>
      <div class="bg-tag">available</div>
    </div>`;
  }).join('');
}

// ─── Donors ───────────────────────────────────────────────────────────────────

async function loadDonors() {
  const tbody = document.getElementById('donors-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Loading…</td></tr>';
  const params = new URLSearchParams();
  const search = document.getElementById('donor-search')?.value.trim();
  const bg     = document.getElementById('donor-bg-filter')?.value;
  const elig   = document.getElementById('donor-eligible-filter')?.value;
  if (search) params.set('search', search);
  if (bg)     params.set('blood_group', bg);
  if (elig)   params.set('is_eligible', elig);
  try {
    const data = await apiFetch(BB_API + 'donors/?' + params);
    const list = data.results || data;
    if (!list.length) { tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No donors found</td></tr>'; return; }
    tbody.innerHTML = list.map(d => `
      <tr>
        <td><code>${d.donor_id}</code></td>
        <td>${d.family_name} ${d.other_names}</td>
        <td><strong>${d.blood_group}</strong></td>
        <td>${d.gender === 'M' ? '♂ Male' : '♀ Female'}</td>
        <td>${d.phone}</td>
        <td>${d.total_donations}</td>
        <td>${d.last_donation || '—'}</td>
        <td>${d.is_eligible
          ? '<span class="bag-available">✅ Eligible</span>'
          : '<span class="bag-expired">⛔ Deferred</span>'}</td>
        <td><button class="btn-secondary btn-sm" onclick="viewDonor(${d.id})">View</button></td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Error loading donors</td></tr>';
  }
}

function openDonorModal() { showModal('donor-modal'); }

async function submitDonor() {
  const payload = {
    family_name:   document.getElementById('don-fname').value.trim(),
    other_names:   document.getElementById('don-oname').value.trim(),
    blood_group:   document.getElementById('don-bg').value,
    gender:        document.getElementById('don-gender').value,
    date_of_birth: document.getElementById('don-dob').value,
    phone:         document.getElementById('don-phone').value.trim(),
    national_id:   document.getElementById('don-nid').value.trim(),
  };
  if (!payload.family_name || !payload.date_of_birth) { alert('Fill required fields'); return; }
  try {
    await apiFetch(BB_API + 'donors/', 'POST', payload);
    closeModal('donor-modal');
    loadDonors();
    loadDashboard();
    showNotif('Donor registered ✅');
  } catch (e) { alert('Error: ' + e.message); }
}

function viewDonor(id) { alert('Donor detail view coming soon.'); }

// ─── Blood Inventory ──────────────────────────────────────────────────────────

async function loadInventory() {
  const tbody = document.getElementById('inventory-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Loading…</td></tr>';
  const params = new URLSearchParams();
  const bg   = document.getElementById('inv-bg-filter')?.value;
  const comp = document.getElementById('inv-comp-filter')?.value;
  const st   = document.getElementById('inv-status-filter')?.value;
  if (bg)   params.set('blood_group', bg);
  if (comp) params.set('component',   comp);
  if (st)   params.set('status',      st);
  try {
    const data = await apiFetch(BB_API + 'bags/?' + params);
    const list = data.results || data;
    if (!list.length) { tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No bags found</td></tr>'; return; }
    tbody.innerHTML = list.map(b => {
      const expClass = b.expiry_status === 'ok' ? 'exp-ok'
                     : b.expiry_status === 'warning'  ? 'exp-warning'
                     : b.expiry_status === 'critical' ? 'exp-critical' : 'exp-expired';
      return `
      <tr>
        <td><code>${b.bag_number}</code></td>
        <td><strong>${b.blood_group}</strong></td>
        <td>${b.component}</td>
        <td>${b.volume_ml} mL</td>
        <td>${b.location || '—'}</td>
        <td>${b.expiry_date}</td>
        <td class="${expClass}">${b.days_to_expiry}d</td>
        <td><span class="bag-${b.status}">${b.status}</span></td>
        <td>
          ${b.status === 'available'
            ? `<button class="btn-primary btn-sm" onclick="reserveBag(${b.id})">📌 Reserve</button>` : ''}
          ${b.status === 'reserved'
            ? `<button class="btn-danger btn-sm" onclick="issueBag(${b.id})">🏥 Issue</button>` : ''}
        </td>
      </tr>`;
    }).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Error loading inventory</td></tr>';
  }
}

async function reserveBag(id) {
  const pid = prompt('Enter Patient ID to reserve for (or leave blank):');
  try {
    await apiFetch(BB_API + `bags/${id}/reserve/`, 'POST', { patient_id: pid || null });
    loadInventory();
    showNotif('Bag reserved 📌');
  } catch (e) { alert('Error: ' + e.message); }
}

async function issueBag(id) {
  if (!confirm('Issue this blood bag to patient?')) return;
  try {
    await apiFetch(BB_API + `bags/${id}/issue/`, 'POST', {});
    loadInventory();
    loadDashboard();
    showNotif('Bag issued 🏥');
  } catch (e) { alert('Error: ' + e.message); }
}

function openAddBagModal() { alert('Add blood bag — requires donation event. Coming soon.'); }

// ─── Blood Requests ───────────────────────────────────────────────────────────

async function loadRequests() {
  const tbody = document.getElementById('requests-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading…</td></tr>';
  const params = new URLSearchParams();
  const st  = document.getElementById('req-status-filter')?.value;
  const urg = document.getElementById('req-urgency-filter')?.value;
  if (st)  params.set('status',  st);
  if (urg) params.set('urgency', urg);
  try {
    const data = await apiFetch(BB_API + 'requests/?' + params);
    const list = data.results || data;
    if (!list.length) { tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No requests</td></tr>'; return; }
    tbody.innerHTML = list.map(r => `
      <tr>
        <td><code>${r.request_id}</code></td>
        <td>${r.patient_name || '—'}</td>
        <td><strong>${r.blood_group}</strong></td>
        <td>${r.component}</td>
        <td>${r.units_requested}</td>
        <td><span class="urg-${r.urgency}">${r.urgency}</span></td>
        <td>${r.ward || '—'}</td>
        <td><span class="bag-${r.status || 'quarantine'}">${r.status}</span></td>
        <td>${fmtDate(r.created_at)}</td>
        <td><button class="btn-secondary btn-sm" onclick="viewRequest(${r.id})">View</button></td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Error</td></tr>';
  }
}

function openRequestModal() { alert('Blood request form — linked to patient registry. Coming soon.'); }
function viewRequest(id) { alert('Request detail view coming soon.'); }

// ─── Crossmatch ───────────────────────────────────────────────────────────────

async function loadCrossmatch() {
  const tbody = document.getElementById('crossmatch-tbody');
  tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Loading…</td></tr>';
  const params = new URLSearchParams();
  const res = document.getElementById('xm-result-filter')?.value;
  if (res) params.set('result', res);
  try {
    const data = await apiFetch(BB_API + 'crossmatch/?' + params);
    const list = data.results || data;
    if (!list.length) { tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No crossmatch records</td></tr>'; return; }
    tbody.innerHTML = list.map(x => `
      <tr>
        <td><code>${x.blood_bag?.bag_number || x.blood_bag || '—'}</code></td>
        <td>${x.patient_name || '—'}</td>
        <td><span class="xm-${x.result}">${x.result}</span></td>
        <td>${x.method}</td>
        <td>${x.performed_by_name || '—'}</td>
        <td>${fmtDate(x.performed_at)}</td>
        <td>${x.ai_flag ? '🤖 ' + (x.ai_note || 'AI flagged') : '—'}</td>
        <td><button class="btn-secondary btn-sm" onclick="viewXM(${x.id})">View</button></td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Error loading crossmatch</td></tr>';
  }
}

function openCrossmatchModal() { alert('Crossmatch form — linked to blood request. Coming soon.'); }
function viewXM(id) { alert('Crossmatch detail view coming soon.'); }

// ─── Haemovigilance ───────────────────────────────────────────────────────────

async function loadHaemovigilance() {
  const tbody = document.getElementById('hv-tbody');
  tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Loading…</td></tr>';
  const params = new URLSearchParams();
  const sev = document.getElementById('hv-severity-filter')?.value;
  const rxn = document.getElementById('hv-reaction-filter')?.value;
  if (sev) params.set('severity',      sev);
  if (rxn) params.set('reaction_type', rxn);
  try {
    const data = await apiFetch(BB_API + 'haemovigilance/?' + params);
    const list = data.results || data;
    if (!list.length) { tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No HV reports</td></tr>'; return; }
    tbody.innerHTML = list.map(h => `
      <tr>
        <td><code>${h.report_id}</code></td>
        <td>${h.patient_name || '—'}</td>
        <td>${h.reaction_type}</td>
        <td><span class="sev-${h.severity}">${h.severity}</span></td>
        <td>${fmtDate(h.onset_time)}</td>
        <td>${h.reported_by_name || '—'}</td>
        <td>${h.is_notified_to_rbc ? '✅ Yes' : '❌ No'}</td>
        <td><button class="btn-secondary btn-sm" onclick="viewHV(${h.id})">View</button></td>
      </tr>`).join('');
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Error loading HV reports</td></tr>';
  }
}

function openHVModal() { showModal('hv-modal'); }

async function submitHV() {
  const patientInput = document.getElementById('hv-patient').value.trim();
  if (!patientInput) { alert('Patient ID required'); return; }
  const onset = document.getElementById('hv-onset').value;
  if (!onset) { alert('Onset time required'); return; }

  const payload = {
    patient:             patientInput,
    blood_bag:           document.getElementById('hv-bag').value.trim() || null,
    reaction_type:       document.getElementById('hv-reaction').value,
    severity:            document.getElementById('hv-severity').value,
    onset_time:          onset,
    volume_transfused_ml:parseInt(document.getElementById('hv-volume').value) || 0,
    symptoms:            document.getElementById('hv-symptoms').value.trim(),
    clinical_management: document.getElementById('hv-management').value.trim(),
    outcome:             document.getElementById('hv-outcome').value.trim(),
    transfusion_stopped: document.getElementById('hv-stopped').checked,
    is_notified_to_rbc:  document.getElementById('hv-rbc').checked,
  };

  try {
    await apiFetch(BB_API + 'haemovigilance/', 'POST', payload);
    closeModal('hv-modal');
    loadHaemovigilance();
    loadDashboard();
    showNotif('⚠️ Haemovigilance report filed');
  } catch (e) { alert('Error: ' + e.message); }
}

function viewHV(id) { alert('HV report detail view coming soon.'); }

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

function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val ?? '—'; }
function fmtDate(str) {
  if (!str) return '—';
  return new Date(str).toLocaleString('en-GB', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });
}
function showModal(id) { const el = document.getElementById(id); if (el) el.style.display = 'flex'; }
function closeModal(id) { const el = document.getElementById(id); if (el) el.style.display = 'none'; }

function showNotif(msg) {
  if (window.NEXUS?.notify) { window.NEXUS.notify(msg); return; }
  const n = document.createElement('div');
  n.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;background:#8B0000;color:#fff;'
    + 'padding:.7rem 1.2rem;border-radius:8px;z-index:9999;font-size:.87rem;';
  n.textContent = msg;
  document.body.appendChild(n);
  setTimeout(() => n.remove(), 3000);
}
