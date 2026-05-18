/* Toxicology Module — NEXUS ALIS-X */
'use strict';

const API = '/api/v1/laboratory';
let _toxChart = null;

// ── TDM therapeutic ranges (offline reference) ────────────────
const TDM_RANGES = {
  VANCO:  {name:'Vancomycin', trough_lo:10, trough_hi:20, peak_lo:20, peak_hi:40, toxic:20, unit:'mg/L'},
  DIGOX:  {name:'Digoxin',    trough_lo:.8, trough_hi:2.0, toxic:2.0, unit:'ng/mL'},
  PHENY:  {name:'Phenytoin',  trough_lo:10, trough_hi:20, toxic:20, unit:'mg/L'},
  LITHI:  {name:'Lithium',    trough_lo:.6, trough_hi:1.2, toxic:1.5, unit:'mmol/L'},
  CARBA:  {name:'Carbamazepine', trough_lo:4, trough_hi:12, toxic:15, unit:'mg/L'},
  TACRO:  {name:'Tacrolimus', trough_lo:5, trough_hi:15, toxic:20, unit:'ng/mL'},
  THEO:   {name:'Theophylline', trough_lo:10, trough_hi:20, toxic:20, unit:'mg/L'},
  METHO:  {name:'Methotrexate', trough_lo:0, trough_hi:.1, toxic:1, unit:'µmol/L (24h)'},
  GENTA:  {name:'Gentamicin', trough_lo:0, trough_hi:1, peak_lo:5, peak_hi:10, toxic:12, unit:'mg/L'},
  VALP:   {name:'Valproate',  trough_lo:50, trough_hi:100, toxic:100, unit:'mg/L'},
};

// ── Poisoning antidotes (offline reference) ────────────────────
const ANTIDOTES = {
  PARACETAMOL:   'N-Acetylcysteine (NAC) — IV loading dose',
  LEAD:          'DMSA (succimer) or EDTA chelation',
  ARSENIC:       'Dimercaprol (BAL) or DMSA',
  MERCURY:       'Dimercaprol (BAL) or DMSA',
  CO_HGB:        '100% O₂ / Hyperbaric O₂ if COHb >25%',
  CHOLINESTERASE:'Atropine + Pralidoxime (2-PAM) — STAT',
  ETHANOL:       'Supportive care / thiamine',
  METHANOL:      'Fomepizole (4-MP) + dialysis',
  SALICYLATE:    'Urinary alkalinisation + haemodialysis if severe',
  CADMIUM:       'Supportive — no specific antidote; EDTA may worsen',
  CYANIDE:       'Hydroxocobalamin 5g IV',
  DIGOX:         'Digoxin-specific Fab fragments (DigiFab)',
  LITHI:         'Haemodialysis if severe; stop lithium',
};

function auth() { const t = localStorage.getItem('access_token'); return t ? {Authorization:`Bearer ${t}`} : {}; }
async function apiFetch(url, opts={}) {
  const r = await fetch(url, {headers:{'Content-Type':'application/json',...auth()},...opts});
  if (!r.ok) { const e = await r.json().catch(()=>({})); throw new Error(e.detail||`HTTP ${r.status}`); }
  return r.json();
}
function toast(msg,type='success') { window.NexusCore?.toast ? NexusCore.toast(msg,type) : console.log('[Tox]',type,msg); }
function setText(id,v) { const e=document.getElementById(id); if(e) e.textContent=v??'—'; }
function openModal(id) { document.getElementById(id).style.display='flex'; }
function closeModal(id) { document.getElementById(id).style.display='none'; }

// ── Tab switching ──────────────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.dt').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.dept-pane').forEach(p=>p.classList.remove('active'));
  document.querySelector(`.dt[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`tab-${tab}`)?.classList.add('active');
  if (tab==='uds')        loadUDS();
  if (tab==='tdm')        loadTDM();
  if (tab==='poison')     loadPoison();
  if (tab==='bio')        loadBio();
  if (tab==='validation') loadToxVal();
  if (tab==='book')       loadBook();
}
document.querySelectorAll('.dt').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));

// ── Dashboard ──────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const r = await apiFetch(`${API}/requests?limit=1`);
    setText('stat-pending','—');
    setText('stat-emerg','—');
    // Render a placeholder trend chart
    const ctx = document.getElementById('tox-chart')?.getContext('2d');
    if (ctx && !_toxChart) {
      _toxChart = new Chart(ctx, {
        type:'bar',
        data:{
          labels:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
          datasets:[
            {label:'UDS',data:[4,6,3,8,5,2,1],backgroundColor:'rgba(220,53,69,.6)'},
            {label:'TDM',data:[8,5,7,9,6,4,3],backgroundColor:'rgba(249,115,22,.6)'},
            {label:'Poisoning',data:[1,2,0,1,2,0,0],backgroundColor:'rgba(124,58,237,.6)'},
          ]
        },
        options:{responsive:true,plugins:{legend:{position:'bottom'}},scales:{x:{stacked:false},y:{beginAtZero:true}}}
      });
    }
  } catch(e) { console.error('[Tox] Dashboard:', e); }
}

// ── UDS ────────────────────────────────────────────────────────
async function loadUDS() {
  const tbody = document.getElementById('uds-tbody');
  tbody.innerHTML = '<tr><td colspan="15" class="dept-empty">Loading drug screen results…</td></tr>';
  try {
    const data = await apiFetch(`${API}/results?department=TOX&limit=50`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="15" class="dept-empty">No drug screen results found.</td></tr>'; return; }
    tbody.innerHTML = data.map(r => `<tr>
      <td><strong>${r.lab_id||r.lid||'—'}</strong></td>
      <td>${r.pid||'—'}</td>
      <td><span style="background:#e9ecef;padding:.15rem .4rem;border-radius:6px;font-size:.78rem">Standard</span></td>
      ${['—','—','—','—','—','—','—'].map(d=>`<td>${d}</td>`).join('')}
      <td><span class="res-${r.qualitative_value||'NEGATIVE'}">${r.qualitative_value||'Negative'}</span></td>
      <td>—</td>
      <td><span class="status-badge">${r.status||'PENDING'}</span></td>
      <td><button class="dept-print-btn" onclick="NexusPrint?.printLast('uds-table')">🖨️</button></td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="15" class="dept-empty">Error: ${e.message}</td></tr>`; }
}

async function submitUDS() {
  const drugs = {
    thc:document.getElementById('d-thc')?.value,opi:document.getElementById('d-opi')?.value,
    coc:document.getElementById('d-coc')?.value,amp:document.getElementById('d-amp')?.value,
    benz:document.getElementById('d-benz')?.value,meth:document.getElementById('d-meth')?.value,
    mdma:document.getElementById('d-mdma')?.value,barb:document.getElementById('d-barb')?.value,
  };
  const overall = Object.values(drugs).includes('POSITIVE') ? 'POSITIVE' : 'NEGATIVE';
  const body = {
    lab_request_id: +document.getElementById('uds-req')?.value || 0,
    qualitative_value: overall,
    result_source: 'MANUAL',
    result_type: 'QUALITATIVE',
    result_value: JSON.stringify(drugs),
    notes: document.getElementById('uds-notes-m')?.value || null,
  };
  try {
    await apiFetch(`${API}/results`, {method:'POST', body:JSON.stringify(body)});
    closeModal('uds-modal');
    toast(`Drug screen saved — Overall: ${overall}`);
    loadUDS();
  } catch(e) { toast(e.message,'error'); }
}

// ── TDM ────────────────────────────────────────────────────────
async function loadTDM() {
  const tbody = document.getElementById('tdm-tbody');
  tbody.innerHTML = '<tr><td colspan="12" class="dept-empty">Loading TDM results…</td></tr>';
  try {
    const data = await apiFetch(`${API}/results?test_type=TDM&limit=50`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="12" class="dept-empty">No TDM results found. Enter results using + Enter TDM button.</td></tr>'; return; }
    tbody.innerHTML = data.map(r => `<tr>
      <td>${r.lab_id||r.lid||'—'}</td><td>${r.pid||'—'}</td>
      <td>${r.test_name||'—'}</td><td>Trough</td>
      <td><strong>${r.numeric_value||r.result_value||'—'}</strong></td>
      <td>${r.unit||'—'}</td><td>—</td>
      <td>${interpretTDMRange(r)}</td><td>—</td><td>${r.ai_interpretation||'—'}</td>
      <td>${r.is_validated?'✅':'⏳'}</td>
      <td><button class="btn-primary" style="font-size:.78rem;padding:.2rem .5rem" onclick="validate(${r.id})">Validate</button></td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="12" class="dept-empty">Error: ${e.message}</td></tr>`; }
}

function interpretTDMRange(result) {
  const drug = TDM_RANGES[result.test_code?.toUpperCase()] || {};
  const val = parseFloat(result.numeric_value);
  if (!drug.trough_hi || isNaN(val)) return '—';
  if (val > drug.toxic) return '<span class="res-TOXIC">TOXIC</span>';
  if (val >= drug.trough_lo && val <= drug.trough_hi) return '<span class="res-THERAPEUTIC">Therapeutic</span>';
  return '<span class="res-SUBTHERAPEUTIC">Sub-therapeutic</span>';
}

function tdmInterp() {
  const drug = document.getElementById('tdm-drug-m')?.value;
  const conc = parseFloat(document.getElementById('tdm-conc-m')?.value);
  const r = TDM_RANGES[drug];
  if (!r || isNaN(conc)) return;
  const box = document.getElementById('tdm-interp-box');
  const txt = document.getElementById('tdm-interp-txt');
  if (!box || !txt) return;
  box.style.display = '';
  if (conc > r.toxic) { txt.innerHTML = `<strong style="color:#dc3545">⚠️ TOXIC RANGE</strong> — ${r.name}: ${conc} ${r.unit} is above toxic threshold (${r.toxic} ${r.unit}). Consider dose reduction / hold dose. Monitor closely.`; }
  else if (r.trough_hi && conc >= r.trough_lo && conc <= r.trough_hi) { txt.innerHTML = `<strong style="color:#28a745">✓ THERAPEUTIC</strong> — ${r.name}: ${conc} ${r.unit} is within therapeutic range (${r.trough_lo}–${r.trough_hi} ${r.unit}).`; }
  else { txt.innerHTML = `<strong style="color:#0c5460">↓ SUB-THERAPEUTIC</strong> — ${r.name}: ${conc} ${r.unit} is below therapeutic range. Consider dose increase.`; }
}

async function submitTDM() {
  const drug = document.getElementById('tdm-drug-m')?.value;
  const conc = parseFloat(document.getElementById('tdm-conc-m')?.value);
  const r = TDM_RANGES[drug];
  let flag = 'N';
  if (r && conc > r.toxic) flag = 'HH';
  else if (r && conc < r.trough_lo) flag = 'L';
  const body = {
    lab_request_id: +document.getElementById('tdm-req')?.value || 0,
    test_name: r?.name || drug,
    numeric_value: conc,
    unit: document.getElementById('tdm-unit-m')?.value || r?.unit || '',
    flag, result_source: 'MANUAL', result_type: 'QUANTITATIVE',
    notes: document.getElementById('tdm-notes-m')?.value || null,
  };
  try {
    await apiFetch(`${API}/results`, {method:'POST', body:JSON.stringify(body)});
    closeModal('tdm-modal');
    toast(`TDM saved — ${r?.name || drug}: ${conc} ${body.unit}`);
    loadTDM();
  } catch(e) { toast(e.message,'error'); }
}

// ── Poisoning ──────────────────────────────────────────────────
async function loadPoison() {
  const tbody = document.getElementById('poison-tbody');
  tbody.innerHTML = '<tr><td colspan="11" class="dept-empty">Loading poisoning cases…</td></tr>';
  try {
    const data = await apiFetch(`${API}/results?test_type=POISON&limit=50`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="11" class="dept-empty">No poisoning cases on record.</td></tr>'; return; }
    tbody.innerHTML = data.map(r => `<tr>
      <td>${r.lab_id||r.lid||'—'}</td><td>${r.pid||'—'}</td><td>${r.test_name||'—'}</td>
      <td><strong>${r.result_value||r.numeric_value||'—'}</strong></td><td>${r.unit||'—'}</td>
      <td>${r.flag==='HH'?'<span class="res-TOXIC">CRITICAL</span>':'—'}</td>
      <td>${r.qualitative_value||'—'}</td>
      <td>${ANTIDOTES[r.test_code?.toUpperCase()] ? '✅ Required' : '—'}</td>
      <td>${r.ai_interpretation?.substring(0,60)||'—'}</td>
      <td>${r.is_validated?'✅':'⏳'}</td>
      <td><button class="btn-primary" style="font-size:.78rem;padding:.2rem .5rem" onclick="validate(${r.id})">Validate</button></td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="11" class="dept-empty">Error: ${e.message}</td></tr>`; }
}

function poisonSeverity() {
  const type = document.getElementById('pois-type-m')?.value;
  const val = parseFloat(document.getElementById('pois-val-m')?.value);
  const box = document.getElementById('pois-interp-box');
  const txt = document.getElementById('pois-interp-txt');
  const ant = document.getElementById('pois-antidote-txt');
  if (!box || !txt || isNaN(val)) return;
  box.style.display = '';
  const antidote = ANTIDOTES[type] || 'Supportive care — consult toxicology';
  txt.innerHTML = `<strong>${type?.replace('_',' ')}</strong>: Detected value ${val}`;
  ant.innerHTML = `Antidote / Treatment: ${antidote}`;
}

async function submitPoison() {
  const type = document.getElementById('pois-type-m')?.value;
  const val = parseFloat(document.getElementById('pois-val-m')?.value);
  const body = {
    lab_request_id: +document.getElementById('pois-req')?.value || 0,
    test_name: type?.replace('_',' ') || 'Unknown Poison',
    numeric_value: val,
    unit: document.getElementById('pois-unit-m')?.value || '',
    flag: 'HH', result_source: 'MANUAL', result_type: 'QUANTITATIVE',
    qualitative_value: document.getElementById('pois-sev-m')?.value,
    notes: document.getElementById('pois-clinical-m')?.value || null,
  };
  try {
    await apiFetch(`${API}/results`, {method:'POST', body:JSON.stringify(body)});
    closeModal('poison-modal');
    toast('Poisoning case recorded. Critical notification required.', 'warn');
    loadPoison();
  } catch(e) { toast(e.message,'error'); }
}

// ── Bio-Toxins ────────────────────────────────────────────────
async function loadBio() {
  const tbody = document.getElementById('bio-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="dept-empty">Loading bio-toxin results…</td></tr>';
  try {
    const data = await apiFetch(`${API}/results?test_type=BIOTOXIN&limit=50`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="10" class="dept-empty">No bio-toxin cases recorded.</td></tr>'; return; }
    tbody.innerHTML = data.map(r => `<tr>
      <td>${r.lab_id||r.lid||'—'}</td><td>${r.pid||'—'}</td><td>${r.test_name||'—'}</td>
      <td>—</td><td><span class="res-${r.qualitative_value||'NEGATIVE'}">${r.qualitative_value||'—'}</span></td>
      <td>${r.numeric_value||'—'}</td><td>${r.unit||'—'}</td>
      <td>—</td><td>—</td>
      <td><button class="btn-primary" style="font-size:.78rem;padding:.2rem .5rem">Validate</button></td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="10" class="dept-empty">Error: ${e.message}</td></tr>`; }
}

async function submitBio() {
  const body = {
    lab_request_id: +document.getElementById('bio-req')?.value || 0,
    test_name: document.getElementById('bio-cat-m')?.value?.replace('_',' '),
    qualitative_value: document.getElementById('bio-result-m')?.value,
    numeric_value: parseFloat(document.getElementById('bio-level-m')?.value) || null,
    unit: document.getElementById('bio-unit-m')?.value || null,
    flag: document.getElementById('bio-result-m')?.value === 'POSITIVE' ? 'POS' : 'N',
    result_source: 'MANUAL', result_type: 'QUALITATIVE',
    notes: document.getElementById('bio-notes-m')?.value || null,
  };
  try {
    await apiFetch(`${API}/results`, {method:'POST', body:JSON.stringify(body)});
    closeModal('bio-modal');
    toast('Bio-toxin result saved.');
    loadBio();
  } catch(e) { toast(e.message,'error'); }
}

async function submitEmerg() {
  const body = {
    lab_request_id: +document.getElementById('emerg-req')?.value || 0,
    test_name: document.getElementById('emerg-test-m')?.value,
    numeric_value: parseFloat(document.getElementById('emerg-val-m')?.value) || null,
    unit: document.getElementById('emerg-unit-m')?.value || null,
    flag: 'HH', result_source: 'MANUAL', result_type: 'QUANTITATIVE',
    notes: `STAT Emergency: ${document.getElementById('emerg-notes-m')?.value || ''}`,
  };
  try {
    await apiFetch(`${API}/results`, {method:'POST', body:JSON.stringify(body)});
    closeModal('emerg-modal');
    toast('🚨 STAT Emergency result recorded. Critical notification sent.', 'warn');
  } catch(e) { toast(e.message,'error'); }
}

// ── Validation queue ──────────────────────────────────────────
async function loadToxVal() {
  const list = document.getElementById('tox-val-list');
  list.innerHTML = '<div class="dept-empty">Loading…</div>';
  try {
    const data = await apiFetch(`${API}/results?validated=false&limit=30`);
    setText('tox-val-count', `${data.length} awaiting validation`);
    if (!data.length) { list.innerHTML = '<div class="dept-empty">No results awaiting validation.</div>'; return; }
    list.innerHTML = data.map(r => `
      <div class="val-card">
        <div class="val-body">
          <div class="val-id">${r.lab_id||r.test_name||'—'}</div>
          <div class="val-sub">PID: ${r.pid||'—'} · Result: ${r.result_value||r.numeric_value||'—'} ${r.unit||''} · Flag: ${r.flag||'N'}</div>
          <div style="margin-top:.4rem;display:flex;gap:.4rem">
            <button class="btn-primary" style="font-size:.79rem;padding:.25rem .65rem" onclick="validate(${r.id})">✅ Validate</button>
          </div>
        </div>
        ${r.flag==='HH'||r.flag==='LL'?'<span class="dh-chip danger">🚨 Critical</span>':''}
      </div>`).join('');
  } catch(e) { list.innerHTML = `<div class="dept-empty">Error: ${e.message}</div>`; }
}

async function validate(id) {
  try {
    await apiFetch(`${API}/results/${id}/validate`, {method:'POST'});
    toast('Result validated ✓');
    loadToxVal();
  } catch(e) { toast(e.message,'error'); }
}

async function loadBook() {
  const tbody = document.getElementById('book-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="dept-empty">Loading critical book…</td></tr>';
  try {
    const data = await apiFetch(`${API}/critical-book?limit=50`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="9" class="dept-empty">No critical book entries for Toxicology.</td></tr>'; return; }
    tbody.innerHTML = data.map(e => `<tr>
      <td><strong>${e.entry_number}</strong></td>
      <td>${e.pid||'—'}</td><td>${e.test_name||'—'}</td>
      <td>${e.critical_reason||'—'}</td><td>—</td>
      <td>${e.clinician_notified||'—'}</td>
      <td>${e.readback_confirmed?'✅':'⚠️'}</td>
      <td>${e.archived_at?new Date(e.archived_at).toLocaleString():'—'}</td>
      <td><span style="font-family:monospace;font-size:.7rem">${(e.pqc_hash||'').substring(0,20)}…</span></td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="9" class="dept-empty">Error: ${e.message}</td></tr>`; }
}

// ── Close modals on overlay click ─────────────────────────────
document.querySelectorAll('.dept-modal-overlay').forEach(o =>
  o.addEventListener('click', e => { if(e.target===o) o.style.display='none'; })
);

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  // Init print and filter
  if (window.NexusPrint) { ['uds-table','tdm-table','poison-table','bio-table','emerg-table','book-table'].forEach(id => NexusPrint.init(id)); }
  setInterval(loadDashboard, 60000);
});
