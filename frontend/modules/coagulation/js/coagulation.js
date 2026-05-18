/* Coagulation Department — NEXUS ALIS-X */
'use strict';

const API = '/api/v1/laboratory';
let _coagChart = null, _ljChart = null;

const COAG_RANGES = {
  PT:     {name:'Prothrombin Time (PT)', lo:11, hi:14, crit_hi:30, crit_lo:null, unit:'seconds'},
  INR:    {name:'INR', lo:0.8, hi:1.2, crit_hi:3.0, crit_lo:null, unit:'ratio'},
  APTT:   {name:'aPTT', lo:25, hi:35, crit_hi:70, crit_lo:null, unit:'seconds'},
  FIBRIN: {name:'Fibrinogen', lo:2.0, hi:4.0, crit_hi:null, crit_lo:1.0, unit:'g/L'},
  DDIMER: {name:'D-Dimer', lo:null, hi:0.5, crit_hi:5.0, crit_lo:null, unit:'mg/L FEU'},
  TT:     {name:'Thrombin Time', lo:14, hi:21, crit_hi:null, crit_lo:null, unit:'seconds'},
};

const ANTICOAG_TARGETS = {
  WARFARIN: {test:'INR', range:'2.0–3.0 (AF/VTE) | 2.5–3.5 (mechanical valve)'},
  UFH:      {test:'aPTT', range:'1.5–2.5× control (60–100 seconds)'},
  LMWH:     {test:'anti-Xa', range:'0.5–1.0 IU/mL (therapeutic) | 0.2–0.5 (prophylactic)'},
  DOAC:     {test:'anti-Xa', range:'Drug-specific — check SPC for peak/trough targets'},
};

function auth() { const t=localStorage.getItem('access_token'); return t?{Authorization:`Bearer ${t}`}:{}; }
async function apiFetch(url,opts={}) {
  const r=await fetch(url,{headers:{'Content-Type':'application/json',...auth()},...opts});
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${r.status}`);}
  return r.json();
}
function toast(msg,type='success'){window.NexusCore?.toast?NexusCore.toast(msg,type):console.log('[Coag]',type,msg);}
function setText(id,v){const e=document.getElementById(id);if(e)e.textContent=v??'—';}
function openModal(id){document.getElementById(id).style.display='flex';}
function closeModal(id){document.getElementById(id).style.display='none';}

function switchTab(tab) {
  document.querySelectorAll('.dt').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.dept-pane').forEach(p=>p.classList.remove('active'));
  document.querySelector(`.dt[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`tab-${tab}`)?.classList.add('active');
  if(tab==='worklist')      loadWorklist();
  if(tab==='routine')       loadRoutine();
  if(tab==='anticoagulant') loadAnticoag();
  if(tab==='thrombophilia') loadThrombophilia();
  if(tab==='factor-assays') loadFactors();
  if(tab==='iqc')           renderCoagLJ();
  if(tab==='validation')    loadCoagVal();
  if(tab==='book')          loadBook();
}
document.querySelectorAll('.dt').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));

async function loadDashboard() {
  try {
    const ctx=document.getElementById('coag-chart')?.getContext('2d');
    if(ctx&&!_coagChart) {
      _coagChart=new Chart(ctx,{type:'bar',data:{
        labels:['INR <1.2','INR 1.2–2','INR 2–3','INR 3–4','INR >4'],
        datasets:[{label:'Patients',data:[45,12,18,7,3],backgroundColor:['#d4edda','#d1ecf1','#fff3cd','#f8d7da','#dc3545']}]
      },options:{responsive:true,plugins:{legend:{display:false}},scales:{y:{beginAtZero:true}}}});
    }
    ['stat-pending','stat-critical','stat-anticoag','kpi-pt','kpi-aptt','kpi-ddimer','kpi-anticoag','kpi-val-q'].forEach(id=>setText(id,'—'));
  } catch(e){console.error('[Coag] Dashboard:',e);}
}

async function loadWorklist() {
  const tbody=document.getElementById('coag-wl-tbody');
  tbody.innerHTML='<tr><td colspan="13" class="dept-empty">Loading…</td></tr>';
  try {
    const data=await apiFetch(`${API}/requests?limit=30`);
    if(!data.length){tbody.innerHTML='<tr><td colspan="13" class="dept-empty">No coagulation worklist items.</td></tr>';return;}
    tbody.innerHTML=data.slice(0,30).map(r=>`<tr>
      <td><strong>${r.lab_id||'—'}</strong></td><td>${r.pid||'—'}</td>
      <td>PT/INR/aPTT</td><td>Blue citrate</td>
      <td><span style="background:${r.emergency_level==='stat'?'#f8d7da':'#fff3cd'};padding:.15rem .4rem;border-radius:6px;font-size:.76rem">${r.emergency_level?.toUpperCase()||'ROUTINE'}</span></td>
      <td>—</td><td>—</td><td>—</td><td>—</td><td>—</td><td>—</td>
      <td><span style="background:#e9ecef;padding:.15rem .4rem;border-radius:6px;font-size:.76rem">${r.status?.toUpperCase()||'PENDING'}</span></td>
      <td><button class="btn-primary" style="font-size:.78rem;padding:.25rem .6rem" onclick="openModal('result-modal')">Enter</button></td>
    </tr>`).join('');
  } catch(e){tbody.innerHTML=`<tr><td colspan="13" class="dept-empty">Error: ${e.message}</td></tr>`;}
}

async function loadRoutine() {
  const tbody=document.getElementById('routine-tbody');
  tbody.innerHTML='<tr><td colspan="12" class="dept-empty">Loading routine coagulation results…</td></tr>';
  try {
    const data=await apiFetch(`${API}/results?department=COAG&limit=50`);
    if(!data.length){tbody.innerHTML='<tr><td colspan="12" class="dept-empty">No coagulation results. Enter results using + Enter Result.</td></tr>';return;}
    tbody.innerHTML=data.map(r=>interpretCoagRow(r)).join('');
  } catch(e){tbody.innerHTML=`<tr><td colspan="12" class="dept-empty">Error: ${e.message}</td></tr>`;}
}

function interpretCoagRow(r) {
  const ref=COAG_RANGES[r.test_code?.toUpperCase()];
  const val=parseFloat(r.numeric_value);
  let flagBadge='';
  if(r.flag==='HH') flagBadge='<span class="res-TOXIC">CRITICAL HIGH</span>';
  else if(r.flag==='LL') flagBadge='<span class="res-SUBTHERAPEUTIC">CRITICAL LOW</span>';
  else if(r.flag==='H') flagBadge='<span style="background:#fff3cd;color:#856404;padding:.15rem .45rem;border-radius:6px;font-size:.77rem">HIGH</span>';
  else if(r.flag==='L') flagBadge='<span style="background:#d1ecf1;color:#0c5460;padding:.15rem .45rem;border-radius:6px;font-size:.77rem">LOW</span>';
  else flagBadge='<span style="background:#d4edda;color:#155724;padding:.15rem .45rem;border-radius:6px;font-size:.77rem">Normal</span>';
  return `<tr>
    <td><strong>${r.lab_id||r.lid||'—'}</strong></td><td>${r.pid||'—'}</td>
    <td>${r.test_name||r.test_code||'—'}</td>
    <td><strong>${r.numeric_value||r.result_value||'—'}</strong></td>
    <td>${r.unit||''}</td>
    <td>${ref?`${ref.lo||'—'}–${ref.hi||'—'} ${ref.unit}`:'—'}</td>
    <td>${flagBadge}</td>
    <td>${r.result_source==='AUTOMATED'?'🤖 Auto':'👤 Manual'}</td>
    <td>${r.notes||'—'}</td>
    <td>${r.ai_interpretation?.substring(0,60)||'—'}</td>
    <td>${r.is_validated?'✅':'⏳'}</td>
    <td>
      ${!r.is_validated?`<button class="btn-primary" style="font-size:.78rem;padding:.2rem .5rem" onclick="validate(${r.id})">Validate</button>`:''}
      ${r.flag==='HH'||r.flag==='LL'?`<button class="btn-primary" style="background:#dc3545;font-size:.78rem;padding:.2rem .5rem">🚨 Archive</button>`:''}
    </td>
  </tr>`;
}

function loadCoagReference() {
  const test=document.getElementById('cres-test')?.value;
  const ref=COAG_RANGES[test];
  const card=document.getElementById('coag-ref-display');
  if(ref&&card){
    card.style.display='';
    setText('coag-ref-name',ref.name);
    document.getElementById('coag-ref-range').textContent=`Reference: ${ref.lo||'—'}–${ref.hi||'—'} ${ref.unit}`;
    const crit=[];
    if(ref.crit_hi) crit.push(`Critical HIGH: >${ref.crit_hi} ${ref.unit}`);
    if(ref.crit_lo) crit.push(`Critical LOW: <${ref.crit_lo} ${ref.unit}`);
    document.getElementById('coag-ref-critical').textContent=crit.join(' | ')||'No critical threshold defined';
    document.getElementById('cres-unit').value=ref.unit;
  }
}

function autoCoagFlag() {
  const test=document.getElementById('cres-test')?.value;
  const val=parseFloat(document.getElementById('cres-value')?.value);
  const ref=COAG_RANGES[test];
  if(!ref||isNaN(val)) return;
  let flag='N';
  if(ref.crit_hi&&val>ref.crit_hi) flag='HH';
  else if(ref.crit_lo&&val<ref.crit_lo) flag='LL';
  else if(ref.hi&&val>ref.hi) flag='H';
  else if(ref.lo&&val<ref.lo) flag='L';
  const sel=document.getElementById('cres-flag');
  if(sel) sel.value=flag;
}

async function submitCoagResult() {
  autoCoagFlag();
  const body={
    lab_request_id:+document.getElementById('cres-req')?.value||0,
    test_name:document.getElementById('cres-test')?.options[document.getElementById('cres-test').selectedIndex]?.text||'',
    numeric_value:parseFloat(document.getElementById('cres-value')?.value)||null,
    unit:document.getElementById('cres-unit')?.value||null,
    flag:document.getElementById('cres-flag')?.value,
    result_source:document.getElementById('cres-source')?.value||'MANUAL',
    analyzer_name:document.getElementById('cres-analyzer')?.value||null,
    result_type:'QUANTITATIVE',
    notes:document.getElementById('cres-context')?.value||null,
  };
  try {
    await apiFetch(`${API}/results`,{method:'POST',body:JSON.stringify(body)});
    closeModal('result-modal');
    toast('Coagulation result saved.');
    loadRoutine();
  } catch(e){toast(e.message,'error');}
}

function loadAcTarget() {
  const drug=document.getElementById('ac-drug-m')?.value;
  const t=ANTICOAG_TARGETS[drug];
  const el=document.getElementById('ac-target-display');
  if(el&&t) el.value=t.range;
}

function interpretAnticoag() {
  const drug=document.getElementById('ac-drug-m')?.value;
  const val=parseFloat(document.getElementById('ac-value-m')?.value);
  const t=ANTICOAG_TARGETS[drug];
  const box=document.getElementById('ac-interp-box');
  const txt=document.getElementById('ac-interp-txt');
  if(!box||!txt||!t||isNaN(val)) return;
  box.style.display='';
  txt.textContent=`${drug}: ${val}. Target: ${t.range}. ${val>3.5?'⚠️ SUPRATHERAPEUTIC — bleeding risk elevated. Consider dose reduction or hold.':val<1.5?'↓ SUBTHERAPEUTIC — thrombosis risk. Consider dose increase.':'✓ Within therapeutic range.'}`;
}

async function submitAnticoag() {
  const body={
    lab_request_id:+document.getElementById('ac-req')?.value||0,
    test_name:document.getElementById('ac-drug-m')?.value,
    numeric_value:parseFloat(document.getElementById('ac-value-m')?.value)||null,
    unit:document.getElementById('ac-unit-m')?.value||null,
    result_source:'MANUAL',result_type:'QUANTITATIVE',
    notes:document.getElementById('ac-notes-m')?.value||null,
  };
  try {
    await apiFetch(`${API}/results`,{method:'POST',body:JSON.stringify(body)});
    closeModal('anticoag-modal');
    toast('Anticoagulant result saved.');
    loadAnticoag();
  } catch(e){toast(e.message,'error');}
}

async function loadAnticoag() {
  const tbody=document.getElementById('anticoag-tbody');
  tbody.innerHTML='<tr><td colspan="12" class="dept-empty">Loading anticoagulant monitoring…</td></tr>';
  try {
    const data=await apiFetch(`${API}/results?department=COAG&limit=30`);
    if(!data.length){tbody.innerHTML='<tr><td colspan="12" class="dept-empty">No anticoagulant monitoring results.</td></tr>';return;}
    tbody.innerHTML=data.map(r=>`<tr>
      <td>${r.lab_id||r.lid||'—'}</td><td>${r.pid||'—'}</td>
      <td>${r.notes?.split(':')[0]||'—'}</td><td>${r.test_name||'—'}</td>
      <td><strong>${r.numeric_value||r.result_value||'—'}</strong></td>
      <td>${r.unit||'—'}</td><td>—</td>
      <td>${r.flag==='H'?'<span class="res-TOXIC">Supra-therapeutic</span>':r.flag==='L'?'<span class="res-SUBTHERAPEUTIC">Sub-therapeutic</span>':'<span class="res-THERAPEUTIC">Therapeutic</span>'}</td>
      <td>—</td><td>${r.ai_interpretation?.substring(0,50)||'—'}</td>
      <td>${r.is_validated?'✅':'⏳'}</td>
      <td><button class="btn-primary" style="font-size:.78rem;padding:.2rem .5rem" onclick="validate(${r.id})">Validate</button></td>
    </tr>`).join('');
  } catch(e){tbody.innerHTML=`<tr><td colspan="12" class="dept-empty">Error: ${e.message}</td></tr>`;}
}

async function loadThrombophilia() {
  const tbody=document.getElementById('thrombo-tbody');
  tbody.innerHTML='<tr><td colspan="12" class="dept-empty">Thrombophilia screen results — enter via + Enter Thrombophilia Result.</td></tr>';
}
async function loadFactors() {
  const tbody=document.getElementById('factor-tbody');
  tbody.innerHTML='<tr><td colspan="10" class="dept-empty">Factor assay results — enter via + Enter Factor Assay.</td></tr>';
}

function renderCoagLJ() {
  const ctx=document.getElementById('coag-lj-chart')?.getContext('2d');
  if(!ctx) return;
  const mean=12.5, sd=0.6;
  const values=[12.1,12.8,12.3,13.1,11.9,12.5,12.7,12.2,13.5,12.4,12.6,11.8,12.9,12.3,12.7];
  if(_ljChart) _ljChart.destroy();
  _ljChart=new Chart(ctx,{type:'line',data:{
    labels:values.map((_,i)=>`Day ${i+1}`),
    datasets:[
      {label:'QC Result',data:values,borderColor:'#1a0a0a',backgroundColor:'rgba(26,10,10,.1)',pointBackgroundColor:values.map(v=>Math.abs(v-mean)>3*sd?'#dc3545':Math.abs(v-mean)>2*sd?'#ffc107':'#28a745'),pointRadius:5,tension:.3},
      {label:'Mean',data:values.map(()=>mean),borderColor:'#6366f1',borderDash:[],borderWidth:1.5,pointRadius:0},
      {label:'+2s',data:values.map(()=>mean+2*sd),borderColor:'#ffc107',borderDash:[4,4],borderWidth:1,pointRadius:0},
      {label:'-2s',data:values.map(()=>mean-2*sd),borderColor:'#ffc107',borderDash:[4,4],borderWidth:1,pointRadius:0},
      {label:'+3s',data:values.map(()=>mean+3*sd),borderColor:'#dc3545',borderDash:[2,2],borderWidth:1,pointRadius:0},
      {label:'-3s',data:values.map(()=>mean-3*sd),borderColor:'#dc3545',borderDash:[2,2],borderWidth:1,pointRadius:0},
    ]
  },options:{responsive:true,plugins:{legend:{position:'bottom'}},scales:{y:{title:{display:true,text:'seconds'}}}}});
}

async function validate(id) {
  try {
    await apiFetch(`${API}/results/${id}/validate`,{method:'POST'});
    toast('Coagulation result validated.');
    loadRoutine();loadCoagVal();
  } catch(e){toast(e.message,'error');}
}

async function loadCoagVal() {
  const list=document.getElementById('coag-val-list');
  list.innerHTML='<div class="dept-empty">Loading…</div>';
  try {
    const data=await apiFetch(`${API}/results?validated=false&limit=20`);
    setText('coag-val-count',`${data.length} awaiting validation`);
    if(!data.length){list.innerHTML='<div class="dept-empty">No results awaiting validation.</div>';return;}
    list.innerHTML=data.map(r=>`<div class="val-card">
      <div class="val-body">
        <div class="val-id">${r.test_name||'—'} — ${r.numeric_value||r.result_value||'—'} ${r.unit||''}</div>
        <div class="val-sub">PID: ${r.pid||'—'} · Flag: ${r.flag||'N'}</div>
        <div style="margin-top:.4rem"><button class="btn-primary" style="font-size:.79rem;padding:.25rem .65rem" onclick="validate(${r.id})">✅ Validate</button></div>
      </div>
      ${r.flag==='HH'||r.flag==='LL'?'<span class="dh-chip danger" style="align-self:center">🚨 Critical</span>':''}
    </div>`).join('');
  } catch(e){list.innerHTML=`<div class="dept-empty">Error: ${e.message}</div>`;}
}

async function loadBook() {
  const tbody=document.getElementById('coag-book-tbody');
  tbody.innerHTML='<tr><td colspan="8" class="dept-empty">Loading coagulation critical book…</td></tr>';
  try {
    const data=await apiFetch(`${API}/critical-book?limit=30`);
    if(!data.length){tbody.innerHTML='<tr><td colspan="8" class="dept-empty">No coagulation critical book entries.</td></tr>';return;}
    tbody.innerHTML=data.map(e=>`<tr>
      <td><strong>${e.entry_number}</strong></td><td>${e.pid||'—'}</td>
      <td>${e.test_name||'—'}</td><td>—</td>
      <td>${e.clinician_notified||'—'}</td>
      <td>${e.readback_confirmed?'✅':'⚠️'}</td>
      <td>${e.archived_at?new Date(e.archived_at).toLocaleString():'—'}</td>
      <td><span style="font-family:monospace;font-size:.7rem">${(e.pqc_hash||'').substring(0,20)}…</span></td>
    </tr>`).join('');
  } catch(e){tbody.innerHTML=`<tr><td colspan="8" class="dept-empty">Error: ${e.message}</td></tr>`;}
}

document.querySelectorAll('.dept-modal-overlay').forEach(o=>o.addEventListener('click',e=>{if(e.target===o)o.style.display='none';}));

document.addEventListener('DOMContentLoaded',()=>{
  loadDashboard();
  if(window.NexusPrint)['coag-wl-table','routine-table','anticoag-table','coag-iqc-table','coag-book-table'].forEach(id=>NexusPrint.init(id));
});
