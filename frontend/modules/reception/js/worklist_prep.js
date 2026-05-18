/**
 * WORKLIST PREPARATION — ALIS-X
 * ================================
 * Full JS for the /reception/worklist-prep/{lab_request_id} page.
 *
 * Flow:
 *   1. Read lab_request_id from data attribute
 *   2. Fetch lab request + patient info from /api/v1/patients/lab-requests/{id}
 *   3. Fetch ordered tests via /api/v1/billing/autobill/{id} (reuses autobill to get tests+prices)
 *   4. Group tests by tube type, render tube cards
 *   5. On "CONFIRM & GENERATE WORKLIST":
 *      a. POST /api/v1/worklist/receive → worklist entries created
 *      b. GET  /api/v1/billing/autobill/{id} → suggested billing items
 *      c. Open billing modal
 *   6. On "Confirm Billing":
 *      POST /api/v1/billing/quick → billing record saved
 *   7. Show success → offer label printing
 */

'use strict';

/* ─── Tube colour map (hex values — no CSS vars) ─────────────────────────── */
const TUBE_COLORS = {
  'lavender':   '#c084fc',
  'purple':     '#c084fc',
  'blue':       '#7dd3fc',
  'light-blue': '#7dd3fc',
  'citrate':    '#7dd3fc',
  'gold':       '#fbbf24',
  'yellow':     '#fbbf24',
  'sst':        '#fbbf24',
  'red':        '#f87171',
  'green':      '#4ade80',
  'heparin':    '#4ade80',
  'grey':       '#9ca3af',
  'gray':       '#9ca3af',
  'fluoride':   '#9ca3af',
  'orange':     '#fb923c',
  'dark-purple':'#7c3aed',
  'anaerobic':  '#7c3aed',
  'brown':      '#92400e',
  'stool':      '#92400e',
  'clear':      '#e0f2fe',
  'white':      '#e0f2fe',
  'urine':      '#e0f2fe',
  'csf':        '#e0f2fe',
  'royal-blue': '#1d4ed8',
  'trace':      '#1d4ed8',
  'esr':        '#1d4ed8',
};

/* Tube emoji icons */
const TUBE_ICONS = {
  'lavender': '🟣',
  'purple':   '🟣',
  'blue':     '🔵',
  'gold':     '🟡',
  'yellow':   '🟡',
  'red':      '🔴',
  'green':    '🟢',
  'grey':     '⚫',
  'gray':     '⚫',
  'orange':   '🟠',
  'dark-purple':'🟣',
  'brown':    '🟤',
  'clear':    '⚪',
  'white':    '⚪',
  'royal-blue':'🔵',
};

/* Tube type full names (for display when only acronym is available) */
const TUBE_NAMES = {
  'HEM': { name: 'EDTA — Lavender',     color: 'lavender',   depts: 'Hematology, Immunology' },
  'BNM': { name: 'Bone Marrow',         color: 'purple',     depts: 'Hematology' },
  'CIT': { name: 'Citrate — Light Blue', color: 'blue',      depts: 'Coagulation' },
  'SER': { name: 'SST / Gold Serum',    color: 'gold',       depts: 'Biochemistry, Serology' },
  'PLA': { name: 'Heparin — Green',     color: 'green',      depts: 'Biochemistry' },
  'FLU': { name: 'Fluoride — Grey',     color: 'grey',       depts: 'Biochemistry' },
  'URI': { name: 'Urine Container',     color: 'clear',      depts: 'Urinalysis, Microbiology' },
  'STL': { name: 'Stool Container',     color: 'brown',      depts: 'Microbiology' },
  'SPU': { name: 'Sputum Container',    color: 'clear',      depts: 'Microbiology, Molecular' },
  'SWB': { name: 'Swab Container',      color: 'clear',      depts: 'Microbiology' },
  'PUS': { name: 'Pus / Wound Swab',   color: 'clear',      depts: 'Microbiology' },
  'BLC': { name: 'Blood Culture Bottle',color: 'orange',     depts: 'Microbiology' },
  'NAP': { name: 'NP Swab',            color: 'clear',      depts: 'Microbiology, Molecular' },
  'CSF': { name: 'CSF Tube',           color: 'clear',      depts: 'Biochemistry, Microbiology' },
  'PLR': { name: 'Pleural Fluid',      color: 'clear',      depts: 'Biochemistry, Microbiology' },
  'EXT': { name: 'DNA/RNA Extract',    color: 'clear',      depts: 'Molecular' },
  'DBS': { name: 'Dried Blood Spot',   color: 'clear',      depts: 'Molecular' },
  'BIO': { name: 'Biopsy / Tissue',    color: 'clear',      depts: 'Pathology' },
  'TOX': { name: 'Toxicology Sample',  color: 'yellow',     depts: 'Toxicology' },
};

/* ─── State ─────────────────────────────────────────────────────────────────── */
let STATE = {
  labRequestId:  null,
  labRequest:    null,
  patient:       null,
  rawTests:      [],        // [{test_id, item_code, item_name, unit_price, specimen_type, department}]
  tubeGroups:    [],        // grouped: [{acronym, name, color, tests[], depts Set}]
  isHighRisk:    false,
  shiftName:     null,
  worklist:      null,      // result from /worklist/receive
  billingItems:  [],        // items in billing modal
  paymentMethod: null,
  searchDebounce:null,
};

/* ─── API helpers ──────────────────────────────────────────────────────────── */
const API_BASE = '/api/v1';

async function apiFetch(path, options = {}) {
  const token = localStorage.getItem('access_token');
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try { const d = await res.json(); detail = d.detail || detail; } catch(_) {}
    throw new Error(detail);
  }
  return res.json();
}

/* ─── Shift helper ──────────────────────────────────────────────────────────── */
function getCurrentShift() {
  const h = new Date().getHours();
  if (h >= 6  && h < 14) return 'Morning';
  if (h >= 14 && h < 22) return 'Afternoon';
  return 'Night';
}

/* ─── Number formatting ─────────────────────────────────────────────────────── */
function fmtRWF(n) {
  return Number(n || 0).toLocaleString('en-US', { maximumFractionDigits: 0 }) + ' RWF';
}

/* ─── Toast ──────────────────────────────────────────────────────────────────── */
function toast(msg, type = 'info', duration = 4000) {
  const container = document.getElementById('wp-toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `wp-toast ${type}`;
  el.innerHTML = `<i class="fas fa-${
    type === 'success' ? 'check-circle' :
    type === 'error'   ? 'circle-xmark' :
    type === 'warning' ? 'triangle-exclamation' : 'circle-info'
  }"></i> ${msg}`;
  container.appendChild(el);
  requestAnimationFrame(() => { el.classList.add('show'); });
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 350);
  }, duration);
}

/* ─── Patient banner render ──────────────────────────────────────────────────── */
function renderPatientBanner(req, patient) {
  const name = patient
    ? (patient.full_name || `${patient.family_name || ''} ${patient.other_names || ''}`.trim())
    : '—';
  const initials = name.split(' ').map(w => w[0] || '').join('').slice(0, 2).toUpperCase() || '?';
  const age  = patient?.age   ? `${patient.age}y` : '—';
  const sex  = patient?.gender ? patient.gender.charAt(0).toUpperCase() : '—';
  const pid  = patient?.pid   || '—';

  document.getElementById('wp-avatar').textContent    = initials;
  document.getElementById('wp-patient-name').textContent = name;
  document.getElementById('wp-lab-id').textContent    = req.lab_id || `#${req.id}`;
  document.getElementById('wp-shift-display').textContent =
    `Shift: ${STATE.shiftName} · ${new Date().toLocaleDateString('en-GB', {weekday:'short',day:'2-digit',month:'short',year:'numeric'})}`;

  let badges = `
    <span class="wp-badge wp-badge-grey">${pid}</span>
    <span class="wp-badge wp-badge-blue">${sex} · ${age}</span>
  `;

  const priority = req.emergency_level || req.priority || 'routine';
  if (priority === 'stat' || priority === 'emergency') {
    badges += `<span class="wp-badge wp-badge-stat"><i class="fas fa-bolt"></i> STAT</span>`;
  } else if (priority === 'urgent') {
    badges += `<span class="wp-badge wp-badge-urgent"><i class="fas fa-exclamation-circle"></i> Urgent</span>`;
  } else {
    badges += `<span class="wp-badge wp-badge-routine">Routine</span>`;
  }

  if (req.is_high_risk || STATE.isHighRisk) {
    badges += `<span class="wp-badge wp-badge-biohazard"><i class="fas fa-biohazard"></i> High-Risk</span>`;
    document.getElementById('wp-highrisk-toggle').checked = true;
    STATE.isHighRisk = true;
  }

  document.getElementById('wp-patient-meta').innerHTML = badges;

  // Doctor / date info
  const docEl  = document.getElementById('wp-doctor-info');
  const dateEl = document.getElementById('wp-date-info');
  if (req.doctor_name) {
    docEl.textContent  = `Dr. ${req.doctor_name}`;
    docEl.style.cssText = 'font-size:12px;color:#64748b;font-weight:500';
  }
  if (req.ward) {
    docEl.textContent += ` · ${req.ward}`;
  }
  const reqDate = req.request_date || req.created_at;
  if (reqDate) {
    dateEl.textContent = new Date(reqDate).toLocaleDateString('en-GB',
      {day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'});
    dateEl.style.cssText = 'font-size:11px;color:#94a3b8';
  }

  document.getElementById('wp-highrisk-row').style.display = 'flex';
}

/* ─── Group tests by tube type ───────────────────────────────────────────────── */
function groupByTube(tests) {
  const groups = {};
  for (const t of tests) {
    // Derive acronym from specimen_type string (first 3 chars uppercase, or map)
    let acronym = deriveAcronym(t.specimen_type || t.department || 'SER');
    const key   = acronym;
    if (!groups[key]) {
      const meta  = TUBE_NAMES[acronym] || {};
      const color = meta.color || guessColor(t.specimen_type || '');
      groups[key] = {
        acronym,
        name:      meta.name || t.specimen_type || acronym,
        color,
        hexColor:  TUBE_COLORS[color] || '#94a3b8',
        icon:      TUBE_ICONS[color]  || '🧪',
        depts:     new Set(),
        tests:     [],
        altTubes:  getAlternateTubes(acronym),
        selectedTube: acronym,
      };
    }
    groups[key].tests.push(t);
    if (t.department) groups[key].depts.add(t.department);
  }
  return Object.values(groups);
}

function deriveAcronym(specimenType) {
  if (!specimenType) return 'SER';
  const s = specimenType.toUpperCase();

  if (s.includes('EDTA') || s.includes('HAEM') || s.includes('HEM') || s.includes('CBC'))  return 'HEM';
  if (s.includes('CITRATE') || s.includes('COAG') || s.includes('PT') || s.includes('INR')) return 'CIT';
  if (s.includes('SERUM') || s.includes('SST') || s.includes('GOLD') || s.includes('BIOCHEM')
      || s.includes('HORMONE') || s.includes('TUMOR') || s.includes('MARKER')) return 'SER';
  if (s.includes('PLASMA') || s.includes('HEPARIN'))  return 'PLA';
  if (s.includes('FLUORIDE') || s.includes('GLUCOSE') || s.includes('LACTATE')) return 'FLU';
  if (s.includes('URINE') || s.includes('URIN'))      return 'URI';
  if (s.includes('STOOL') || s.includes('FECE'))      return 'STL';
  if (s.includes('SPUTUM'))                           return 'SPU';
  if (s.includes('SWAB'))                             return 'SWB';
  if (s.includes('BLOOD CULTURE') || s.includes('BLC')) return 'BLC';
  if (s.includes('CSF') || s.includes('CEREBROSP'))   return 'CSF';
  if (s.includes('PLEURAL'))                          return 'PLR';
  if (s.includes('DNA') || s.includes('RNA') || s.includes('MOLECUL')) return 'EXT';
  if (s.includes('BIOPSY') || s.includes('TISSUE'))  return 'BIO';
  if (s.includes('TOXICOL'))                         return 'TOX';

  // Fallback: try first 3 chars
  const trimmed = s.replace(/[^A-Z]/g, '');
  return trimmed.slice(0, 3) || 'SER';
}

function guessColor(specimenType) {
  const s = (specimenType || '').toLowerCase();
  if (s.includes('edta') || s.includes('hem') || s.includes('cbc'))   return 'lavender';
  if (s.includes('citrate') || s.includes('coag'))                    return 'blue';
  if (s.includes('serum') || s.includes('sst') || s.includes('gold')) return 'gold';
  if (s.includes('plasma') || s.includes('heparin'))                  return 'green';
  if (s.includes('fluoride') || s.includes('glucose'))                return 'grey';
  if (s.includes('urine'))                                            return 'clear';
  if (s.includes('stool'))                                            return 'brown';
  if (s.includes('blood culture'))                                    return 'orange';
  return 'clear';
}

function getAlternateTubes(acronym) {
  /* Some tests can use multiple tube types — return alternatives */
  const alts = {
    'SER': ['SER', 'PLA'],
    'HEM': ['HEM', 'SER'],
    'URI': ['URI'],
    'STL': ['STL'],
    'SPU': ['SPU'],
  };
  return alts[acronym] || [acronym];
}

/* ─── Render tube group cards ──────────────────────────────────────────────── */
function renderTubeGroups(groups) {
  const container = document.getElementById('wp-tube-groups');
  container.innerHTML = '';

  if (!groups.length) {
    document.getElementById('wp-skeleton').style.display  = 'none';
    document.getElementById('wp-empty').style.display     = 'block';
    return;
  }

  let totalTests = 0;
  const allDepts = new Set();

  for (let gi = 0; gi < groups.length; gi++) {
    const g   = groups[gi];
    const hex = g.hexColor;
    totalTests += g.tests.length;
    g.depts.forEach(d => allDepts.add(d));

    /* Alternate tube options */
    let altOptions = '';
    if (g.altTubes && g.altTubes.length > 1) {
      altOptions = g.altTubes.map(a => {
        const meta = TUBE_NAMES[a] || {};
        return `<option value="${a}" ${a === g.acronym ? 'selected' : ''}>${meta.name || a}</option>`;
      }).join('');
    } else {
      /* At least show the current tube as a single option */
      altOptions = `<option value="${g.acronym}" selected>${g.name}</option>`;
    }

    /* Test rows */
    const testRows = g.tests.map(t => `
      <div class="wp-test-item">
        <i class="fas fa-flask wp-test-icon"></i>
        <span class="wp-test-name">${escHtml(t.item_name)}</span>
        ${t.item_code ? `<span class="billing-item-code">${escHtml(t.item_code)}</span>` : ''}
        <span class="wp-test-dept">${escHtml(t.department || '')}</span>
        ${t.unit_price > 0
          ? `<span class="wp-test-price">${fmtRWF(t.unit_price)}</span>`
          : ''}
      </div>
    `).join('');

    /* SID preview — will be assigned on confirm */
    const sidPreview = `${g.acronym}-??`;

    const card = document.createElement('div');
    card.className   = 'wp-tube-card';
    card.style.borderLeftColor = hex;
    card.dataset.tubeIndex = gi;

    card.innerHTML = `
      <div class="wp-tube-card-header">
        <div class="wp-tube-swatch" style="background:${hex}">
          ${g.icon}
        </div>
        <div class="wp-tube-info">
          <div class="wp-tube-name">${escHtml(g.name)}</div>
          <div class="wp-tube-dept">${Array.from(g.depts).join(' · ') || ''}</div>
        </div>
        <div style="display:flex;align-items:center;gap:12px;flex-shrink:0">
          <span class="wp-tube-vol">${g.tests.length} test${g.tests.length !== 1 ? 's' : ''}</span>
          <div class="wp-tube-selector">
            <select class="wp-tube-select" data-group-idx="${gi}" title="Change tube type">
              ${altOptions}
            </select>
          </div>
          <span class="wp-sid-preview" id="sid-preview-${gi}">${sidPreview}</span>
        </div>
      </div>
      <div class="wp-test-list">${testRows}</div>
    `;
    container.appendChild(card);
  }

  /* Summary */
  const estTotal = STATE.rawTests.reduce((s, t) => s + (t.unit_price || 0), 0);
  document.getElementById('sum-tubes').textContent = groups.length;
  document.getElementById('sum-tests').textContent = totalTests;
  document.getElementById('sum-depts').textContent = allDepts.size || groups.length;
  document.getElementById('sum-est').textContent   = fmtRWF(estTotal);

  /* Show everything */
  document.getElementById('wp-skeleton').style.display    = 'none';
  document.getElementById('wp-tube-groups').style.display = 'flex';
  document.getElementById('wp-summary-bar').style.display = 'flex';
  document.getElementById('wp-confirm-row').style.display = 'flex';

  /* Wire tube-selector change events */
  container.querySelectorAll('.wp-tube-select').forEach(sel => {
    sel.addEventListener('change', function () {
      const idx     = parseInt(this.dataset.groupIdx, 10);
      const newAcro = this.value;
      STATE.tubeGroups[idx].selectedTube = newAcro;
      /* Update SID preview */
      const preview = document.getElementById(`sid-preview-${idx}`);
      if (preview) preview.textContent = `${newAcro}-??`;
    });
  });
}

/* ─── Confirm worklist ──────────────────────────────────────────────────────── */
async function confirmWorklist() {
  const btn = document.getElementById('wp-btn-confirm');
  btn.disabled = true;
  btn.classList.add('loading');

  try {
    STATE.shiftName = STATE.shiftName || getCurrentShift();
    const wlResult = await apiFetch('/worklist/receive', {
      method: 'POST',
      body: JSON.stringify({
        lab_request_id: STATE.labRequestId,
        shift_name:     STATE.shiftName,
        is_high_risk:   STATE.isHighRisk,
      }),
    });
    STATE.worklist = wlResult;

    /* Update SID previews with real values */
    if (wlResult.entries) {
      const byDept = {};
      wlResult.entries.forEach(e => { byDept[e.department] = e; });
      document.querySelectorAll('.wp-sid-preview').forEach((el, idx) => {
        const g   = STATE.tubeGroups[idx];
        const ent = wlResult.entries.find(e =>
          e.specimen && (e.specimen.toUpperCase().startsWith(g.acronym)
            || e.department === Array.from(g.depts)[0])
        );
        if (ent) el.textContent = ent.sid;
      });
    }

    toast('Worklist created — ' + (wlResult.count || 0) + ' entries', 'success');

    /* Fetch autobill suggestions then open billing modal */
    const autobill = await apiFetch(`/billing/autobill/${STATE.labRequestId}`);
    STATE.billingItems = autobill.items || STATE.rawTests.map(t => ({
      ...t,
      quantity:      1,
      total_price:   t.unit_price,
      is_auto_billed: true,
      is_waived:     false,
    }));

    openBillingModal();

  } catch (err) {
    toast('Worklist error: ' + err.message, 'error', 6000);
    btn.disabled = false;
    btn.classList.remove('loading');
  }
}

/* ─── Billing modal ─────────────────────────────────────────────────────────── */
function openBillingModal() {
  /* Reset views */
  document.getElementById('billing-main-view').style.display    = 'block';
  document.getElementById('billing-success-view').style.display = 'none';
  document.getElementById('billing-modal-footer').style.display = 'flex';

  /* Patient subtitle */
  const patName = STATE.patient
    ? (STATE.patient.full_name ||
       `${STATE.patient.family_name || ''} ${STATE.patient.other_names || ''}`.trim())
    : '—';
  document.getElementById('billing-modal-patient').textContent =
    `Patient: ${patName} · ${STATE.labRequest?.lab_id || ''}`;

  renderBillingItems();
  updateBillingTotals();

  document.getElementById('billing-overlay').classList.add('active');
  document.getElementById('billing-search-input').value = '';
}

function closeBillingModal() {
  document.getElementById('billing-overlay').classList.remove('active');
}

function renderBillingItems() {
  const tbody = document.getElementById('billing-items-tbody');
  tbody.innerHTML = '';

  if (!STATE.billingItems.length) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:20px">
      No tests found. Add items manually below.</td></tr>`;
    return;
  }

  STATE.billingItems.forEach((item, idx) => {
    const tr = document.createElement('tr');
    tr.dataset.idx = idx;
    tr.innerHTML = `
      <td>
        <div class="billing-item-name ${item.is_waived ? 'billing-waived' : ''}">${escHtml(item.item_name)}</div>
        ${item.item_code ? `<div class="billing-item-code">${escHtml(item.item_code)}</div>` : ''}
        ${item.is_auto_billed ? '<span class="billing-auto-badge">AUTO</span>' : ''}
      </td>
      <td>
        <input type="number" class="billing-qty-input" value="${item.quantity}" min="1" max="99"
               data-idx="${idx}" title="Quantity">
      </td>
      <td style="text-align:right;color:#334155">${fmtRWF(item.unit_price)}</td>
      <td class="billing-price ${item.is_waived ? 'billing-waived' : ''}" id="bitem-total-${idx}">
        ${fmtRWF(item.is_waived ? 0 : item.total_price)}
      </td>
      <td>
        <label class="billing-waive-toggle" title="Waive this charge">
          <input type="checkbox" ${item.is_waived ? 'checked' : ''} data-waive-idx="${idx}">
          Waive
        </label>
      </td>
      <td>
        <button class="billing-remove-btn" data-remove-idx="${idx}" title="Remove item">
          <i class="fas fa-trash-alt"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  /* Quantity change */
  tbody.querySelectorAll('.billing-qty-input').forEach(input => {
    input.addEventListener('change', function () {
      const idx = parseInt(this.dataset.idx, 10);
      const qty = Math.max(1, parseInt(this.value, 10) || 1);
      STATE.billingItems[idx].quantity    = qty;
      STATE.billingItems[idx].total_price = round2(STATE.billingItems[idx].unit_price * qty);
      this.value = qty;
      const totEl = document.getElementById(`bitem-total-${idx}`);
      if (totEl) totEl.textContent = fmtRWF(STATE.billingItems[idx].is_waived ? 0 : STATE.billingItems[idx].total_price);
      updateBillingTotals();
    });
  });

  /* Waive toggle */
  tbody.querySelectorAll('[data-waive-idx]').forEach(cb => {
    cb.addEventListener('change', function () {
      const idx = parseInt(this.dataset.waiveIdx, 10);
      STATE.billingItems[idx].is_waived = this.checked;
      renderBillingItems();
      updateBillingTotals();
    });
  });

  /* Remove */
  tbody.querySelectorAll('[data-remove-idx]').forEach(btn => {
    btn.addEventListener('click', function () {
      const idx = parseInt(this.dataset.removeIdx, 10);
      STATE.billingItems.splice(idx, 1);
      renderBillingItems();
      updateBillingTotals();
    });
  });
}

function updateBillingTotals() {
  let subtotal  = 0;
  let waivedAmt = 0;
  STATE.billingItems.forEach(item => {
    const lineTotal = item.unit_price * item.quantity;
    subtotal += lineTotal;
    if (item.is_waived) waivedAmt += lineTotal;
  });
  const total = subtotal - waivedAmt;
  document.getElementById('bill-subtotal').textContent = fmtRWF(subtotal);
  document.getElementById('bill-waivers').textContent  = `−${fmtRWF(waivedAmt)}`;
  document.getElementById('bill-total').textContent    = fmtRWF(total);
}

/* ─── Billing search (typeahead) ───────────────────────────────────────────── */
function setupBillingSearch() {
  const input    = document.getElementById('billing-search-input');
  const dropdown = document.getElementById('billing-search-dropdown');
  if (!input || !dropdown) return;

  input.addEventListener('input', function () {
    clearTimeout(STATE.searchDebounce);
    const q = this.value.trim();
    if (q.length < 2) {
      dropdown.classList.remove('open');
      dropdown.innerHTML = '';
      return;
    }
    STATE.searchDebounce = setTimeout(() => fetchSearchResults(q), 280);
  });

  input.addEventListener('blur', function () {
    setTimeout(() => {
      dropdown.classList.remove('open');
    }, 200);
  });
}

async function fetchSearchResults(q) {
  const dropdown = document.getElementById('billing-search-dropdown');
  try {
    const results = await apiFetch(`/billing/search-items?q=${encodeURIComponent(q)}&limit=12`);
    if (!results.length) {
      dropdown.innerHTML = `<div class="billing-search-option" style="color:#94a3b8;cursor:default">No results for "${escHtml(q)}"</div>`;
    } else {
      dropdown.innerHTML = results.map((r, i) => `
        <div class="billing-search-option" data-search-idx="${i}"
             data-item='${JSON.stringify(r).replace(/'/g, "&#39;")}'>
          <span class="billing-search-opt-name">${escHtml(r.item_name)}</span>
          <span class="billing-search-opt-price">${fmtRWF(r.unit_price)}</span>
        </div>
      `).join('');
      dropdown.querySelectorAll('.billing-search-option').forEach(opt => {
        opt.addEventListener('mousedown', function () {
          const item = JSON.parse(this.dataset.item || '{}');
          addBillingItem(item);
          document.getElementById('billing-search-input').value = '';
          dropdown.classList.remove('open');
          dropdown.innerHTML = '';
        });
      });
    }
    dropdown.classList.add('open');
  } catch (err) {
    console.warn('Billing search error:', err);
  }
}

function addBillingItem(item) {
  /* If same test already in list, increment qty */
  const existing = STATE.billingItems.find(b => b.test_id && b.test_id === item.test_id);
  if (existing) {
    existing.quantity   += 1;
    existing.total_price = round2(existing.unit_price * existing.quantity);
  } else {
    STATE.billingItems.push({
      test_id:       item.test_id || null,
      item_code:     item.item_code || '',
      item_name:     item.item_name,
      unit_price:    item.unit_price || 0,
      quantity:      1,
      total_price:   item.unit_price || 0,
      is_auto_billed: false,
      is_waived:     false,
    });
  }
  renderBillingItems();
  updateBillingTotals();
  toast(`Added: ${item.item_name}`, 'info', 2000);
}

/* ─── Payment method pills ──────────────────────────────────────────────────── */
function setupPaymentPills() {
  document.querySelectorAll('.billing-payment-pill').forEach(pill => {
    pill.addEventListener('click', function () {
      document.querySelectorAll('.billing-payment-pill').forEach(p => p.classList.remove('selected'));
      this.classList.add('selected');
      STATE.paymentMethod = this.dataset.method;
      /* Show extra fields if insurance or momo */
      const extra    = document.getElementById('billing-extra-fields');
      const insInput = document.getElementById('billing-insurance-name');
      const momoInput= document.getElementById('billing-momo-ref');
      if (STATE.paymentMethod === 'INSURANCE' || STATE.paymentMethod === 'RSSB') {
        extra.style.display    = 'block';
        insInput.style.display = 'block';
        momoInput.style.display= 'none';
      } else if (STATE.paymentMethod === 'MOMO') {
        extra.style.display    = 'block';
        insInput.style.display = 'none';
        momoInput.style.display= 'block';
      } else {
        extra.style.display = 'none';
      }
    });
  });

  /* Default: CASH */
  const cashPill = document.querySelector('[data-method="CASH"]');
  if (cashPill) {
    cashPill.classList.add('selected');
    STATE.paymentMethod = 'CASH';
  }
}

/* ─── Confirm billing ───────────────────────────────────────────────────────── */
async function confirmBilling(asDraft = false) {
  const btn = document.getElementById('billing-confirm-btn');
  if (!asDraft) {
    btn.disabled   = true;
    btn.innerHTML  = `<i class="fas fa-spinner fa-spin"></i> Saving…`;
  }

  const insuranceName = document.getElementById('billing-insurance-name')?.value?.trim() || null;
  const momoRef       = document.getElementById('billing-momo-ref')?.value?.trim() || null;
  const notes         = document.getElementById('billing-notes')?.value?.trim() || null;

  const payload = {
    lab_request_id: STATE.labRequestId,
    items: STATE.billingItems.map(it => ({
      item_code:     it.item_code || '',
      item_name:     it.item_name,
      unit_price:    it.unit_price,
      quantity:      it.quantity,
      test_id:       it.test_id || null,
      is_auto_billed:it.is_auto_billed,
      is_waived:     it.is_waived,
      waiver_reason: it.waiver_reason || null,
    })),
    payment_method: STATE.paymentMethod || 'CASH',
    insurance_name: insuranceName,
    momo_ref:       momoRef,
    notes,
    auto_confirm:   !asDraft,
  };

  try {
    const result = await apiFetch('/billing/quick', {
      method: 'POST',
      body:   JSON.stringify(payload),
    });
    showBillingSuccess(result, asDraft);
  } catch (err) {
    toast('Billing error: ' + err.message, 'error', 6000);
    if (!asDraft) {
      btn.disabled  = false;
      btn.innerHTML = `<i class="fas fa-check-circle"></i> Confirm Billing`;
    }
  }
}

function showBillingSuccess(result, isDraft) {
  document.getElementById('billing-main-view').style.display    = 'none';
  document.getElementById('billing-modal-footer').style.display = 'none';
  document.getElementById('billing-success-view').style.display = 'block';

  const total  = fmtRWF(result.total_amount || 0);
  const status = isDraft ? 'saved as draft' : 'confirmed';
  document.getElementById('billing-success-msg').innerHTML =
    `Worklist created &amp; billing <b>${status}</b>.<br>
     Total: <strong style="color:#0369a1">${total}</strong> ·
     Method: ${result.payment_method || '—'}<br>
     Ready to print specimen labels.`;

  /* Set print link */
  const printLink = document.getElementById('billing-print-link');
  if (printLink) {
    printLink.href = `/api/v1/worklist/labels/request/${STATE.labRequestId}/pdf`;
  }

  toast(isDraft ? 'Billing saved as draft.' : 'Billing confirmed!', 'success');
}

/* ─── Skip billing (dismiss modal) ─────────────────────────────────────────── */
function skipBilling() {
  closeBillingModal();
  /* Show worklist-success without billing */
  showSkipSuccess();
}

function showSkipSuccess() {
  /* Use the billing success view in the modal for consistency */
  document.getElementById('billing-main-view').style.display    = 'none';
  document.getElementById('billing-modal-footer').style.display = 'none';
  document.getElementById('billing-success-view').style.display = 'block';
  document.getElementById('billing-success-msg').innerHTML =
    `Worklist entries created.<br>Billing skipped — can be completed from the Billing module.<br>
     Ready to print specimen labels.`;

  const printLink = document.getElementById('billing-print-link');
  if (printLink) {
    printLink.href = `/api/v1/worklist/labels/request/${STATE.labRequestId}/pdf`;
  }
  document.getElementById('billing-overlay').classList.add('active');
}

/* ─── Utility ───────────────────────────────────────────────────────────────── */
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g,  '&amp;')
    .replace(/</g,  '&lt;')
    .replace(/>/g,  '&gt;')
    .replace(/"/g,  '&quot;')
    .replace(/'/g,  '&#39;');
}

function round2(n) {
  return Math.round((n || 0) * 100) / 100;
}

/* ─── Load lab request data ─────────────────────────────────────────────────── */
async function loadLabRequest(id) {
  STATE.shiftName = getCurrentShift();
  try {
    /* Fetch lab request + patient detail via billing router */
    let req, patient;

    try {
      const data = await apiFetch(`/billing/lab-request/${id}`);
      req     = data;
      patient = data.patient || null;
    } catch (_) {
      /* Fallback: minimal stub so page doesn't crash */
      req = { id, lab_id: `REQ-${id}`, status: 'pending', emergency_level: 'routine' };
      patient = null;
    }

    STATE.labRequest = req;
    STATE.patient    = patient;
    STATE.isHighRisk = req.is_high_risk || false;
    document.getElementById('wp-highrisk-toggle').checked = STATE.isHighRisk;

    renderPatientBanner(req, patient);

    /* Load tests (use autobill endpoint — it fetches ordered tests with prices) */
    const autobill = await apiFetch(`/billing/autobill/${id}`);
    STATE.rawTests  = autobill.items || [];

    if (!STATE.rawTests.length) {
      document.getElementById('wp-skeleton').style.display = 'none';
      document.getElementById('wp-empty').style.display    = 'block';
      return;
    }

    STATE.tubeGroups = groupByTube(STATE.rawTests);
    renderTubeGroups(STATE.tubeGroups);

  } catch (err) {
    document.getElementById('wp-skeleton').style.display = 'none';
    document.getElementById('wp-empty').style.display    = 'block';
    toast('Failed to load request: ' + err.message, 'error', 8000);
    console.error('loadLabRequest error:', err);
  }
}

/* ─── Auto-refresh every 60s ────────────────────────────────────────────────── */
let _autoRefreshTimer = null;
function startAutoRefresh() {
  if (_autoRefreshTimer) clearInterval(_autoRefreshTimer);
  _autoRefreshTimer = setInterval(() => {
    /* Only refresh patient banner data — don't re-render tube groups mid-session */
    if (STATE.labRequestId && !document.getElementById('billing-overlay').classList.contains('active')) {
      apiFetch(`/billing/autobill/${STATE.labRequestId}`).then(data => {
        /* Silently update estimated total */
        const est = (data.items || []).reduce((s, t) => s + (t.unit_price || 0), 0);
        const sumEst = document.getElementById('sum-est');
        if (sumEst && sumEst.textContent !== fmtRWF(est)) {
          sumEst.textContent = fmtRWF(est);
        }
      }).catch(() => {});
    }
  }, 60000);
}

/* ─── Bootstrap ─────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  const page = document.getElementById('wp-page');
  if (!page) return;

  STATE.labRequestId = parseInt(page.dataset.requestId, 10);
  if (!STATE.labRequestId) {
    toast('No lab request ID specified.', 'error');
    return;
  }

  /* Load data */
  loadLabRequest(STATE.labRequestId);
  startAutoRefresh();

  /* High-risk toggle */
  document.getElementById('wp-highrisk-toggle')?.addEventListener('change', function () {
    STATE.isHighRisk = this.checked;
    const badge = document.querySelector('.wp-badge-biohazard');
    if (this.checked && !badge) {
      const meta = document.getElementById('wp-patient-meta');
      if (meta) meta.insertAdjacentHTML('beforeend',
        `<span class="wp-badge wp-badge-biohazard"><i class="fas fa-biohazard"></i> High-Risk</span>`);
    } else if (!this.checked && badge) {
      badge.remove();
    }
  });

  /* Confirm worklist button */
  document.getElementById('wp-btn-confirm')?.addEventListener('click', confirmWorklist);

  /* Billing modal: close (X) = skip */
  document.getElementById('billing-modal-close')?.addEventListener('click', closeBillingModal);

  /* Billing modal: skip billing */
  document.getElementById('billing-skip-btn')?.addEventListener('click', skipBilling);

  /* Billing modal: save draft */
  document.getElementById('billing-draft-btn')?.addEventListener('click', () => confirmBilling(true));

  /* Billing modal: confirm billing */
  document.getElementById('billing-confirm-btn')?.addEventListener('click', () => confirmBilling(false));

  /* Billing modal: click outside to close (skip) */
  document.getElementById('billing-overlay')?.addEventListener('click', function (e) {
    if (e.target === this) {
      /* Don't auto-close — require explicit skip or confirm */
    }
  });

  /* Payment pills */
  setupPaymentPills();

  /* Billing search */
  setupBillingSearch();
});
