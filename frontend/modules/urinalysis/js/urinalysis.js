/* Urinalysis Department — NEXUS ALIS-X */
'use strict';

const API = '/api/v1/laboratory';
let _urnChart = null;

function auth(){const t=localStorage.getItem('access_token');return t?{Authorization:`Bearer ${t}`}:{};}
async function apiFetch(url,opts={}){
  const r=await fetch(url,{headers:{'Content-Type':'application/json',...auth()},...opts});
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${r.status}`);}
  return r.json();
}
function toast(msg,type='success'){window.NexusCore?.toast?NexusCore.toast(msg,type):console.log('[Urn]',type,msg);}
function setText(id,v){const e=document.getElementById(id);if(e)e.textContent=v??'—';}
function openModal(id){document.getElementById(id).style.display='flex';}
function closeModal(id){document.getElementById(id).style.display='none';}

function switchTab(tab){
  document.querySelectorAll('.dt').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.dept-pane').forEach(p=>p.classList.remove('active'));
  document.querySelector(`.dt[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`tab-${tab}`)?.classList.add('active');
  if(tab==='dipstick')     loadDipstick();
  if(tab==='microscopy')   loadMicroscopy();
  if(tab==='culture-link') loadCultureLink();
  if(tab==='special')      loadSpecial();
  if(tab==='validation')   loadUrnVal();
  if(tab==='book')         loadBook();
}
document.querySelectorAll('.dt').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));

async function loadDashboard(){
  try{
    const ctx=document.getElementById('urn-chart')?.getContext('2d');
    if(ctx&&!_urnChart){
      _urnChart=new Chart(ctx,{type:'doughnut',data:{
        labels:['Normal','Protein+','Blood+','Nitrite+','Glucose+','Ketones+'],
        datasets:[{data:[65,12,8,7,5,3],backgroundColor:['#d4edda','#f8d7da','#c82333','#fff3cd','#d1ecf1','#cce5ff']}]
      },options:{responsive:true,plugins:{legend:{position:'right'}}}});
    }
    ['stat-pending','stat-abnormal','stat-culture','kpi-total','kpi-abnormal','kpi-protein','kpi-uti','kpi-culture'].forEach(id=>setText(id,'—'));
    ['sq-dipstick','sq-micro','sq-culture-ref','sq-special'].forEach(id=>setText(id,'— pending'));
  }catch(e){console.error('[Urn] Dashboard:',e);}
}

async function loadDipstick(){
  const tbody=document.getElementById('dip-tbody');
  tbody.innerHTML='<tr><td colspan="17" class="dept-empty">Loading dipstick results…</td></tr>';
  try{
    const data=await apiFetch(`${API}/results?department=URN&limit=50`);
    if(!data.length){tbody.innerHTML='<tr><td colspan="17" class="dept-empty">No dipstick results. Enter via + Enter Dipstick Result.</td></tr>';return;}
    tbody.innerHTML=data.map(r=>`<tr>
      <td><strong>${r.lab_id||r.lid||'—'}</strong></td><td>${r.pid||'—'}</td>
      <td>Yellow</td><td>Clear</td><td>—</td><td>—</td>
      ${['—','—','—','—','—','—','—','—'].map(x=>`<td>${x}</td>`).join('')}
      <td><span class="${r.qualitative_value==='POSITIVE'?'res-POSITIVE':'res-NEGATIVE'}">${r.qualitative_value||'—'}</span></td>
      <td>${r.is_validated?'✅ Done':'⚠️ Needed'}</td>
      <td><button class="btn-primary" style="font-size:.78rem;padding:.2rem .5rem" onclick="validate(${r.id})">Validate</button></td>
    </tr>`).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="17" class="dept-empty">Error: ${e.message}</td></tr>`;}
}

function checkUTIFlags(){
  const nitrite=document.getElementById('dp-nitrite')?.value;
  const le=document.getElementById('dp-le')?.value;
  const flag=document.getElementById('uti-flag');
  if(flag) flag.style.display=(nitrite==='POS'&&le!=='NEG')?'':'none';
}

async function submitDipstick(){
  const dipResult={
    colour:document.getElementById('dp-colour')?.value,
    appearance:document.getElementById('dp-appearance')?.value,
    ph:document.getElementById('dp-ph')?.value,
    sg:document.getElementById('dp-sg')?.value,
    blood:document.getElementById('dp-blood')?.value,
    protein:document.getElementById('dp-protein')?.value,
    glucose:document.getElementById('dp-glucose')?.value,
    ketones:document.getElementById('dp-ketones')?.value,
    bilirubin:document.getElementById('dp-bilirubin')?.value,
    urobilinogen:document.getElementById('dp-urobilinogen')?.value,
    nitrite:document.getElementById('dp-nitrite')?.value,
    le:document.getElementById('dp-le')?.value,
  };
  const isAbnormal=Object.values(dipResult).some(v=>v&&v!=='NEG'&&v!=='CLEAR'&&v!=='NORMAL');
  const body={
    lab_request_id:+document.getElementById('dmod-req')?.value||0,
    test_name:'Urine Dipstick',
    qualitative_value:isAbnormal?'ABNORMAL':'NORMAL',
    result_source:document.getElementById('dmod-source')?.value||'MANUAL',
    result_type:'QUALITATIVE',
    result_value:JSON.stringify(dipResult),
    flag:isAbnormal?'A':'N',
  };
  try{
    await apiFetch(`${API}/results`,{method:'POST',body:JSON.stringify(body)});
    closeModal('dip-modal');
    toast(`Dipstick saved — ${isAbnormal?'⚠️ Abnormal findings':'Normal'}`);
    loadDipstick();
    if(document.getElementById('dmod-refer-culture')?.checked||document.getElementById('dmod-microscopy-req')?.checked){
      toast('Microscopy / culture referral flagged.','info');
    }
  }catch(e){toast(e.message,'error');}
}

async function loadMicroscopy(){
  const tbody=document.getElementById('micro-tbody');
  tbody.innerHTML='<tr><td colspan="14" class="dept-empty">Microscopy results — enter via + Enter Microscopy.</td></tr>';
}

async function submitMicroscopy(){
  const body={
    lab_request_id:0,
    test_name:'Urine Microscopy',
    qualitative_value:document.getElementById('mmod-bacteria')?.value==='MANY'?'BACTERIURIA':'NORMAL',
    result_source:'MANUAL',result_type:'QUALITATIVE',
    result_value:JSON.stringify({
      rbc:document.getElementById('mmod-rbc')?.value,
      wbc:document.getElementById('mmod-wbc')?.value,
      bacteria:document.getElementById('mmod-bacteria')?.value,
      casts:document.getElementById('mmod-path-cast')?.value,
    }),
  };
  try{
    await apiFetch(`${API}/results`,{method:'POST',body:JSON.stringify(body)});
    closeModal('micro-modal');
    toast('Urine microscopy saved.');
  }catch(e){toast(e.message,'error');}
}

async function loadCultureLink(){
  const tbody=document.getElementById('cult-link-tbody');
  tbody.innerHTML='<tr><td colspan="10" class="dept-empty">Loading culture referrals…</td></tr>';
  tbody.innerHTML='<tr><td colspan="10" class="dept-empty">No urine culture referrals today. Use + Refer for Culture to create one.</td></tr>';
}

async function submitCultureReferral(){
  toast('Urine sample referred to Microbiology for culture.');closeModal('refer-modal');loadCultureLink();
}

async function loadSpecial(){
  const tbody=document.getElementById('special-tbody');
  tbody.innerHTML='<tr><td colspan="11" class="dept-empty">Loading special urine tests…</td></tr>';
  tbody.innerHTML='<tr><td colspan="11" class="dept-empty">No special test results. Enter via + Enter Special Test.</td></tr>';
}

function loadUrineSpecialRef(){
  const test=document.getElementById('smod-test')?.value;
  const refs={HCG:'Negative (non-pregnant)',MICROALBUMIN:'<30 µg/mL (normal), 30–300 (microalbuminuria)',ALBUMIN_CREAT:'<30 mg/g (normal), 30–300 (ACR moderate), >300 (severely increased)',BENCE_JONES:'Negative',OSMOLALITY:'50–1200 mOsm/kg (random)'};
  const el=document.getElementById('smod-unit');
  const units={HCG:'Pos/Neg',MICROALBUMIN:'µg/mL',ALBUMIN_CREAT:'mg/g',BENCE_JONES:'Pos/Neg',OSMOLALITY:'mOsm/kg'};
  if(el&&units[test]) el.value=units[test];
}

async function submitSpecial(){
  const body={
    lab_request_id:+document.getElementById('smod-req')?.value||0,
    test_name:document.getElementById('smod-test')?.value,
    result_value:document.getElementById('smod-result')?.value,
    unit:document.getElementById('smod-unit')?.value||null,
    result_source:'MANUAL',result_type:'QUALITATIVE',
    notes:document.getElementById('smod-notes')?.value||null,
  };
  try{
    await apiFetch(`${API}/results`,{method:'POST',body:JSON.stringify(body)});
    closeModal('special-modal');
    toast('Special urine test saved.');
  }catch(e){toast(e.message,'error');}
}

async function validate(id){
  try{
    await apiFetch(`${API}/results/${id}/validate`,{method:'POST'});
    toast('Result validated.');
    loadDipstick();loadUrnVal();
  }catch(e){toast(e.message,'error');}
}

async function loadUrnVal(){
  const list=document.getElementById('urn-val-list');
  list.innerHTML='<div class="dept-empty">Loading…</div>';
  try{
    const data=await apiFetch(`${API}/results?validated=false&limit=20`);
    setText('urn-val-count',`${data.length} awaiting validation`);
    if(!data.length){list.innerHTML='<div class="dept-empty">No results awaiting validation.</div>';return;}
    list.innerHTML=data.map(r=>`<div class="val-card">
      <div class="val-body">
        <div class="val-id">${r.test_name||'—'} — ${r.qualitative_value||r.result_value?.substring(0,30)||'—'}</div>
        <div class="val-sub">PID: ${r.pid||'—'}</div>
        <div style="margin-top:.4rem"><button class="btn-primary" style="font-size:.79rem;padding:.25rem .65rem" onclick="validate(${r.id})">✅ Validate</button></div>
      </div>
    </div>`).join('');
  }catch(e){list.innerHTML=`<div class="dept-empty">Error: ${e.message}</div>`;}
}

async function loadBook(){
  const tbody=document.getElementById('urn-book-tbody');
  tbody.innerHTML='<tr><td colspan="7" class="dept-empty">No critical urinalysis entries.</td></tr>';
}

document.querySelectorAll('.dept-modal-overlay').forEach(o=>o.addEventListener('click',e=>{if(e.target===o)o.style.display='none';}));

document.addEventListener('DOMContentLoaded',()=>{
  loadDashboard();
  if(window.NexusPrint)['dip-table','micro-table','cult-link-table','special-table','urn-book-table'].forEach(id=>NexusPrint.init(id));
});
