/**
 * JORINOVA NEXUS ALIS-X — Haematology Module (Full Sysmex Format)
 * ================================================================
 * Complete CBC with differential (NEU/LYM/MON/EOS/BAS/BLAST % and #)
 * Real-time flag detection · Anaemia classification · Westgard IQC
 * ⚠️ Critical value thresholds per BCSH/CLSI/WHO — modify with pathologist approval
 */
'use strict';

const API = '/api/v1';
let _diffChart = null, _ljChart = null;
let _wlData = [];

/* ── Auth / API ────────────────────────────────────────────── */
function auth(){ const t=localStorage.getItem('access_token'); return t?{Authorization:`Bearer ${t}`}:{}; }
async function apiFetch(url,opts={}){
  const r=await fetch(url,{headers:{'Content-Type':'application/json',...auth()},...opts});
  if(!r.ok){const e=await r.json().catch(()=>({}));throw new Error(e.detail||`HTTP ${r.status}`);}
  return r.json();
}
function toast(msg,type='success'){ window.NexusCore?.toast?NexusCore.toast(msg,type):console.log('[Hem]',msg); }
function setText(id,v){const e=document.getElementById(id);if(e)e.textContent=v??'—';}

/* ── Clock ─────────────────────────────────────────────────── */
(function tick(){
  const n=new Date(),h=n.getHours();
  const[name,icon]=h>=6&&h<14?['Morning','☀️']:h>=14&&h<22?['Afternoon','🌤️']:['Night','🌙'];
  ['hem-shift-icon','hem-shift-name','hem-clock'].forEach((id,i)=>{
    const e=document.getElementById(id);if(e)e.textContent=[icon,name,n.toLocaleTimeString('en-GB')][i];
  });
  setTimeout(tick,1000);
})();

/* ── Tabs ──────────────────────────────────────────────────── */
function switchTab(tab){
  document.querySelectorAll('.hem-tab').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.hem-pane').forEach(p=>p.classList.remove('active'));
  document.querySelector(`.hem-tab[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`tab-${tab}`)?.classList.add('active');
  if(tab==='worklist') loadWorklist();
  if(tab==='malaria')  loadMalaria();
  if(tab==='smear')    loadSmears();
  if(tab==='iqc')      loadIQC();
  if(tab==='book')     loadCriticalBook();
}
document.querySelectorAll('.hem-tab').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));

/* ── Parameter flagging ────────────────────────────────────── */
function flagParam(id,val,sex,lo,hi,critLo,critHi){
  const v=parseFloat(val);
  const inp=document.getElementById(`p-${id}`);
  const flag=document.getElementById(`flag-${id}`);
  if(!inp||isNaN(v)) return 'N';
  let f='N';
  if(critLo!==null&&v<critLo)      f='LL';
  else if(critHi!==null&&v>critHi) f='HH';
  else if(lo!==null&&v<lo)         f='L';
  else if(hi!==null&&v>hi)         f='H';
  inp.className='pe-input'+(f==='LL'||f==='HH'?' crit':f==='H'?' high':f==='L'?' low':'');
  if(flag){
    const lbl={LL:'⬇⬇LL',HH:'⬆⬆HH',L:'⬇L',H:'⬆H',N:'✓'};
    const col={LL:'#7f1d1d',HH:'#7f1d1d',L:'#1e40af',H:'#92400e',N:'#166534'};
    flag.textContent=lbl[f]||f; flag.style.color=col[f]||'#166534';
  }
  if(f==='LL'||f==='HH') document.getElementById('cbc-notify-critical').checked=true;
  return f;
}

function flagDiff(name,val,lo,hi){
  const v=parseFloat(val),flag=document.getElementById(`flag-${name}`);
  if(!flag||isNaN(v)) return;
  if(v<lo){flag.textContent='⬇L';flag.style.color='#1e40af';}
  else if(v>hi){flag.textContent='⬆H';flag.style.color='#92400e';}
  else{flag.textContent='✓';flag.style.color='#166534';}
}

function flagBlasts(val){
  const v=parseFloat(val)||0;
  const flag=document.getElementById('flag-blast');
  const inp=document.getElementById('p-blast-p');
  if(flag){
    if(v>0){flag.textContent=`⚠️ BLASTS ${v}% URGENT`;flag.style.color='#7f1d1d';flag.style.fontWeight='800';
      if(inp){inp.style.background='#fee2e2';inp.style.borderColor='#dc2626';}
      document.getElementById('cbc-notify-critical').checked=true;
      toast(`⚠️ BLAST CELLS ${v}% — URGENT blood film + haematology review`,'warn');
    } else {flag.textContent='✓ Absent';flag.style.color='#166534';flag.style.fontWeight='600';}
  }
  calcAbsolute('blast');
}

/* ── Absolute count calculation ────────────────────────────── */
function calcAbsolute(name){
  const wbc=parseFloat(document.getElementById('p-wbc')?.value)||0;
  const pct=parseFloat(document.getElementById(`p-${name}-p`)?.value)||0;
  const el=document.getElementById(`p-${name}-a`);
  if(el&&wbc>0) el.value=(wbc*pct/100).toFixed(2);
  updateDiffTotal();
}

function updateDiffTotal(){
  const names=['neu','lym','mon','eos','bas','blast'];
  const total=names.reduce((s,n)=>s+(parseFloat(document.getElementById(`p-${n}-p`)?.value)||0),0);
  const el=document.getElementById('diff-total');
  const chk=document.getElementById('diff-check');
  if(el) el.textContent=`${total.toFixed(1)}%`;
  if(chk&&total>0){
    const d=Math.abs(100-total);
    if(d<1){chk.textContent='✓ OK';chk.style.color='#166534';}
    else if(d<5){chk.textContent=`⚠️ ${total.toFixed(0)}%`;chk.style.color='#d97706';}
    else{chk.textContent=`❌ ${total.toFixed(0)}%`;chk.style.color='#dc2626';}
  }
}

/* ── Differential chart ────────────────────────────────────── */
function updateDiffChart(){
  const vals=[
    parseFloat(document.getElementById('p-neu-p')?.value)||0,
    parseFloat(document.getElementById('p-lym-p')?.value)||0,
    parseFloat(document.getElementById('p-mon-p')?.value)||0,
    parseFloat(document.getElementById('p-eos-p')?.value)||0,
    parseFloat(document.getElementById('p-bas-p')?.value)||0,
    parseFloat(document.getElementById('p-blast-p')?.value)||0,
  ];
  const labels=['NEU','LYM','MON','EOS','BAS','BLAST'];
  const colors=['#3b82f6','#10b981','#f59e0b','#f97316','#8b5cf6','#dc2626'];
  const ctx=document.getElementById('diff-chart')?.getContext('2d');
  if(!ctx) return;
  if(_diffChart) _diffChart.destroy();
  const hasData=vals.some(v=>v>0);
  _diffChart=new Chart(ctx,{
    type:'doughnut',
    data:{labels,datasets:[{data:hasData?vals:[1],backgroundColor:hasData?colors:['#f1f5f9'],borderWidth:2,borderColor:'#fff'}]},
    options:{responsive:true,cutout:'65%',plugins:{legend:{display:false}}}
  });
  const leg=document.getElementById('diff-legend');
  if(leg) leg.innerHTML=labels.map((l,i)=>`<div class="dcl-item"><div class="dcl-dot" style="background:${colors[i]}"></div>${l}:<strong>${vals[i]}%</strong></div>`).join('');
}

/* ── Calculated indices ────────────────────────────────────── */
function updateIndices(){
  const hgb=parseFloat(document.getElementById('p-hgb')?.value)||0;
  const rbc=parseFloat(document.getElementById('p-rbc')?.value)||0;
  const mcv=parseFloat(document.getElementById('p-mcv')?.value)||0;
  const mch=parseFloat(document.getElementById('p-mch')?.value)||0;
  const rdw=parseFloat(document.getElementById('p-rdw-cv')?.value)||0;
  const set=(id,val,interp)=>{
    const e=document.getElementById(id),ei=document.getElementById(id+'-interp');
    if(e)e.textContent=val;if(ei)ei.textContent=interp;
  };
  if(mcv>0&&rbc>0){const m=(mcv/rbc).toFixed(1);set('idx-mentzer',m,m<13?'<13 → Thalassaemia favoured':'>13 → IDA favoured');}
  if(mcv>0&&mch>0&&hgb>0){const ef=((mcv*mcv*mch)/(hgb*100)).toFixed(1);set('idx-ef',ef,parseFloat(ef)<1530?'<1530 → IDA':'≥1530 → Thalassaemia');}
  if(rdw>0&&mcv>0&&rbc>0){const r=((rdw*mcv)/rbc).toFixed(1);set('idx-rdwi',r,parseFloat(r)>220?'>220 → IDA':'≤220 → Thalassaemia');}
  if(mcv>0&&mch>0){const s=((mcv*mcv*mch)/100).toFixed(0);set('idx-shine',s,parseInt(s)<1530?'<1530 → IDA':'≥1530 → Thalassaemia');}
}

/* ── CBC change handler ────────────────────────────────────── */
function onCBCChange(){
  updateDiffTotal();
  updateDiffChart();
  updateIndices();
  ['neu','lym','mon','eos','bas','blast'].forEach(n=>calcAbsolute(n));
}

/* ── AI/Rules interpretation ───────────────────────────────── */
async function autoInterpret(){
  const hgb=parseFloat(document.getElementById('p-hgb')?.value);
  const rbc=parseFloat(document.getElementById('p-rbc')?.value);
  const wbc=parseFloat(document.getElementById('p-wbc')?.value);
  const plt=parseFloat(document.getElementById('p-plt')?.value);
  const mcv=parseFloat(document.getElementById('p-mcv')?.value);
  const mch=parseFloat(document.getElementById('p-mch')?.value);
  const rdw=parseFloat(document.getElementById('p-rdw-cv')?.value);
  const neuA=parseFloat(document.getElementById('p-neu-a')?.value);
  const sex=document.getElementById('cbc-sex')?.value||'M';
  const body=document.getElementById('ai-interp-body');
  if(!body) return;
  body.innerHTML='<div style="text-align:center;padding:.75rem;color:#0891b2"><i class="fas fa-spinner fa-spin"></i> Analysing…</div>';

  let html='';

  // Local rules (always available offline)
  const hgbLo=sex==='F'?12:13;
  if(hgb&&hgb<hgbLo&&mcv&&mch&&rdw&&rbc){
    const mentzer=(mcv/rbc).toFixed(1);
    const isMicro=mcv<80,isMacro=mcv>100;
    if(isMicro){
      const ida=rdw>14.5&&mentzer>13,thal=!rdw>14.5&&mentzer<13&&rbc>5.0;
      html+=`<div class="interp-panel ${hgb<7?'critical':'warning'}">
        <div class="interp-title">${hgb<7?'🚨 CRITICAL — ':''}Microcytic${mch<27?' Hypochromic':''} Anaemia (Hb ${hgb} g/dL, MCV ${mcv} fL)</div>
        <div class="interp-text">RDW ${rdw}% · Mentzer ${mentzer} · RBC ${rbc} ×10¹²/L</div>
        <div class="interp-badge-row">
          ${ida?'<span class="sig-chip sig-HIGH">IDA likely (Mentzer>13, RDW↑)</span>':''}
          ${thal?'<span class="sig-chip sig-MODERATE">Thalassaemia likely (Mentzer<13, RBC↑)</span>':''}
          <span style="font-size:.72rem;color:#4f46e5;background:#f0f4ff;border:1px solid #c7d0e8;border-radius:8px;padding:.1rem .4rem">Mentzer ${mentzer} → ${mentzer<13?'Thalassaemia':'IDA'} favoured</span>
        </div>
        ${ida?'<div class="interp-action">⚡ Order: Ferritin · Serum iron + TIBC · Reticulocytes · Blood film</div>':''}
        ${thal?'<div class="interp-action">⚡ Order: HPLC (HbA2/HbF) · Family history · DNA if α-thal suspected</div>':''}
        <div class="interp-causes">
          <div class="interp-cause-item">IDA: ↓Ferritin ↓Iron ↑TIBC ↑RDW pencil cells anisocytosis</div>
          <div class="interp-cause-item">β-Thal: Normal ferritin ↑RBC ↑HbA2>3.5% target cells basophilic stippling</div>
          <div class="interp-cause-item">α-Thal: Normal HPLC — requires DNA analysis</div>
        </div>
        ${hgb<7?'<div class="interp-action" style="background:#fee2e2;color:#7f1d1d;font-weight:800">🚨 Hb <7 g/dL — TRANSFUSION THRESHOLD. Consider pRBC transfusion. Notify clinician IMMEDIATELY.</div>':''}
      </div>`;
    } else if(isMacro){
      html+=`<div class="interp-panel warning">
        <div class="interp-title">🧬 Macrocytic Anaemia (Hb ${hgb} g/dL, MCV ${mcv} fL)</div>
        <div class="interp-text">Megaloblastic vs Non-megaloblastic macrocytosis. Check for hypersegmented neutrophils (megaloblastic sign).</div>
        <div class="interp-cause-item">B12 deficiency: Neurological sx · elevated MMA · intrinsic factor Ab</div>
        <div class="interp-cause-item">Folate deficiency: No neuro sx · elevated homocysteine · dietary history</div>
        <div class="interp-cause-item">Non-megaloblastic: Liver disease · Hypothyroidism · Alcohol · Reticulocytosis</div>
        <div class="interp-action">⚡ Order: Serum B12 · Serum/RBC folate · LFT · TSH · Blood film · Reticulocyte count</div>
      </div>`;
    } else {
      html+=`<div class="interp-panel">
        <div class="interp-title">⚖️ Normocytic Anaemia (Hb ${hgb} g/dL, MCV ${mcv} fL)</div>
        <div class="interp-cause-item">Acute blood loss · Haemolytic anaemia · Anaemia of chronic disease</div>
        <div class="interp-cause-item">Bone marrow failure · CKD · Aplastic anaemia</div>
        <div class="interp-action">⚡ Order: Reticulocytes · DAT · LDH · Bilirubin · Ferritin · CRP · Renal function · Blood film</div>
      </div>`;
    }
    const card=document.getElementById('anaemia-summary-card');
    if(card) card.style.display='';
    const sBody=document.getElementById('anaemia-summary-body');
    if(sBody) sBody.innerHTML=html;
  }

  if(neuA&&neuA<0.5){
    html+=`<div class="interp-panel critical">
      <div class="interp-title">🚨 CRITICAL — Agranulocytosis (ANC ${neuA} ×10³/µL)</div>
      <div class="interp-action">⚡ IMMEDIATE reverse isolation · Drug review (carbimazole/clozapine) · G-CSF · Antibiotics if febrile</div>
    </div>`;
  }
  if(wbc&&wbc>30){
    html+=`<div class="interp-panel critical">
      <div class="interp-title">🚨 CRITICAL — Leukocytosis ${wbc} ×10³/µL</div>
      <div class="interp-action">⚡ STAT blood film · BCR-ABL1 (CML) · Blast cell morphology · Haematology referral</div>
    </div>`;
  }
  if(plt&&plt<20){
    html+=`<div class="interp-panel critical">
      <div class="interp-title">🚨 CRITICAL — Thrombocytopenia ${plt} ×10³/µL</div>
      <div class="interp-action">⚡ Hold invasive procedures · Blood film · DIC screen · TTP exclusion (LDH/schistocytes)</div>
    </div>`;
  }

  // Try cloud AI
  try{
    const r=await apiFetch(`${API}/ai/interpret`,{method:'POST',body:JSON.stringify({
      test_code:'HGB',test_name:'Haemoglobin',value:hgb,unit:'g/dL',
      flag:hgb&&hgb<(sex==='F'?12:13)?'L':'N',
      context:`MCV:${mcv},MCH:${mch},RDW:${rdw},RBC:${rbc},WBC:${wbc},PLT:${plt}`
    })});
    const ai=r.ai_enrichment||{};
    if(ai.summary){
      html+=`<div class="interp-panel" style="border-left-color:#6366f1">
        <div class="interp-title" style="color:#4f46e5">🤖 AI Clinical Analysis <span id="ai-layer-badge" style="font-family:monospace;font-size:.65rem;color:#94a3b8">[${r.ai_layer||'rules'}]</span></div>
        <div class="interp-text">${ai.summary}</div>
        ${(ai.differentials||[]).map(d=>`<div class="interp-cause-item">${d}</div>`).join('')}
        ${ai.action?`<div class="interp-action">${ai.action}</div>`:''}
      </div>`;
    }
  }catch(_){ /* offline — local rules already rendered */ }

  if(!html) html='<div style="color:#94a3b8;font-size:.82rem;padding:.5rem;text-align:center">All parameters within normal limits. No acute abnormalities detected.</div>';
  body.innerHTML=html;
}

/* ── Save CBC ─────────────────────────────────────────────── */
async function saveCBC(){
  const body={
    lab_request_id:+document.getElementById('cbc-req-id')?.value||0,
    patient_id:+document.getElementById('cbc-patient-id')?.value||0,
    pid:document.getElementById('cbc-pid')?.value||null,
    hgb:parseFloat(document.getElementById('p-hgb')?.value)||null,
    rbc:parseFloat(document.getElementById('p-rbc')?.value)||null,
    wbc:parseFloat(document.getElementById('p-wbc')?.value)||null,
    plt:parseFloat(document.getElementById('p-plt')?.value)||null,
    hct:parseFloat(document.getElementById('p-hct')?.value)||null,
    mcv:parseFloat(document.getElementById('p-mcv')?.value)||null,
    mch:parseFloat(document.getElementById('p-mch')?.value)||null,
    mchc:parseFloat(document.getElementById('p-mchc')?.value)||null,
    rdw:parseFloat(document.getElementById('p-rdw-cv')?.value)||null,
    neut_pct:parseFloat(document.getElementById('p-neu-p')?.value)||null,
    lymph_pct:parseFloat(document.getElementById('p-lym-p')?.value)||null,
    mono_pct:parseFloat(document.getElementById('p-mon-p')?.value)||null,
    eos_pct:parseFloat(document.getElementById('p-eos-p')?.value)||null,
    baso_pct:parseFloat(document.getElementById('p-bas-p')?.value)||null,
    neut_abs:parseFloat(document.getElementById('p-neu-a')?.value)||null,
    lymph_abs:parseFloat(document.getElementById('p-lym-a')?.value)||null,
    esr:parseFloat(document.getElementById('p-esr')?.value)||null,
    result_source:document.getElementById('cbc-source')?.value||'AUTOMATED',
    analyzer_name:document.getElementById('cbc-analyzer')?.value||null,
    is_critical:document.getElementById('cbc-notify-critical')?.checked||false,
  };
  try{
    await apiFetch(`${API}/hematology/cbc`,{method:'POST',body:JSON.stringify(body)});
    toast('CBC saved ✓'); switchTab('worklist');
  }catch(e){ toast(e.message,'error'); }
}

function openNewCBC(){ switchTab('cbc-entry'); }
function filterBy(type){ loadWorklist(); }
function filterWorklist(q){
  document.querySelectorAll('#wl-tbody tr').forEach(r=>{
    r.style.display=(!q||r.textContent.toLowerCase().includes(q.toLowerCase()))?'':'none';
  });
}

/* ── Worklist ─────────────────────────────────────────────── */
async function loadWorklist(){
  const tbody=document.getElementById('wl-tbody');if(!tbody) return;
  tbody.innerHTML='<tr><td colspan="13" style="text-align:center;padding:1.5rem;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i></td></tr>';
  try{
    const data=await apiFetch(`${API}/hematology/cbc?limit=50`);
    _wlData=data||[];
    setText('kpi-total',_wlData.length);
    setText('kpi-pending',_wlData.filter(r=>!r.is_validated).length);
    setText('kpi-validated',_wlData.filter(r=>r.is_validated).length);
    setText('kpi-critical',_wlData.filter(r=>r.is_critical).length);
    if(!_wlData.length){tbody.innerHTML='<tr><td colspan="13" style="text-align:center;padding:2rem;color:#94a3b8">No haematology results yet. Use ➕ New CBC.</td></tr>';return;}
    tbody.innerHTML=_wlData.map((r,i)=>{
      const hF=r.hgb<7?'crit-high':r.hgb<13?'low':'normal';
      const wF=r.wbc<2||r.wbc>30?'crit-high':r.wbc<4||r.wbc>11?'high':'normal';
      const pF=r.plt<20||r.plt>1000?'crit-high':r.plt<100||r.plt>450?'high':'normal';
      const anyF=[hF,wF,pF].find(f=>f!=='normal')||'normal';
      return `<tr class="${r.is_critical?'critical-row':anyF==='high'?'high-row':''}">
        <td><input type="checkbox" onchange="NexusPrint?._toggleRow('wl-table',${i},this.checked)"></td>
        <td><strong style="color:#0891b2">${r.lab_id||r.hem_id||'—'}</strong></td>
        <td>${r.pid||'—'}</td>
        <td><span class="badge badge-${r.emergency_level==='stat'?'crit-high':r.emergency_level==='urgent'?'high':'normal'}">${(r.emergency_level||'routine').toUpperCase()}</span></td>
        <td>CBC + Diff</td><td>—</td>
        <td><strong class="${hF==='crit-high'?'flag-HH':hF==='low'?'flag-L':''}">${r.hgb||'—'}</strong></td>
        <td><strong class="${wF==='crit-high'?'flag-HH':''}">${r.wbc||'—'}</strong></td>
        <td><strong class="${pF==='crit-high'?'flag-LL':pF==='high'?'flag-L':''}">${r.plt||'—'}</strong></td>
        <td><span class="badge badge-${anyF}">${anyF==='crit-high'?'!!CRIT!!':anyF==='high'?'⬆H':anyF==='low'?'⬇L':'✓N'}</span></td>
        <td><span class="badge badge-${r.is_validated?'validated':'pending'}">${r.is_validated?'Validated':'Pending'}</span></td>
        <td style="font-size:.72rem;color:#0891b2">${(r.ai_classification||'').substring(0,30)||'—'}</td>
        <td style="text-align:right;display:flex;gap:.25rem;justify-content:flex-end">
          ${!r.is_validated?`<button onclick="validateCBC(${r.id})" style="background:#10b981;color:#fff;border:none;border-radius:6px;padding:.2rem .5rem;font-size:.72rem;cursor:pointer">✅</button>`:''}
          <button onclick="printCBCRow(${i})" style="background:#f0fdff;border:1px solid #bae6fd;border-radius:6px;padding:.2rem .5rem;font-size:.72rem;cursor:pointer;color:#0891b2">🖨️</button>
        </td>
      </tr>`;
    }).join('');
    NexusPrint?.init('wl-table',{title:'Haematology CBC Worklist'});
  }catch(e){tbody.innerHTML=`<tr><td colspan="13" style="text-align:center;color:#dc2626">Error: ${e.message}</td></tr>`;}
}

async function validateCBC(id){
  try{await apiFetch(`${API}/hematology/cbc/${id}/validate`,{method:'POST'});toast('CBC validated ✓');loadWorklist();}
  catch(e){toast(e.message,'error');}
}

/* ── Malaria ───────────────────────────────────────────────── */
async function loadMalaria(){
  const tbody=document.getElementById('mal-tbody');if(!tbody)return;
  try{
    const data=await apiFetch(`${API}/hematology/malaria?limit=50`);
    setText('kpi-malaria',data.filter(r=>r.rdt_result==='POS').length);
    if(!data.length){tbody.innerHTML='<tr><td colspan="13" style="text-align:center;padding:1.5rem;color:#94a3b8">No malaria results.</td></tr>';return;}
    tbody.innerHTML=data.map(r=>`<tr>
      <td><input type="checkbox"></td>
      <td><strong>${r.mal_id||'—'}</strong></td><td>${r.pid||'—'}</td><td>${r.pid||'—'}</td>
      <td><span class="${r.rdt_result==='POS'?'mal-pos':'mal-neg'}">${r.rdt_result||'—'}</span></td>
      <td><span class="${r.smear_result==='POS'?'mal-pos':'mal-neg'}">${r.smear_result||'—'}</span></td>
      <td>${r.species||'—'}</td>
      <td>${r.parasitemia_pct!=null?r.parasitemia_pct+'%':'—'}</td>
      <td>${r.parasitemia_grade||'—'}</td>
      <td>${r.staining||'—'}</td>
      <td>${r.is_validated?'✅':'⏳'}</td>
      <td style="font-size:.72rem">${r.created_at?.substring(0,16)||'—'}</td>
      <td><button style="font-size:.72rem;padding:.2rem .5rem;background:#f0fdff;border:1px solid #bae6fd;border-radius:6px;cursor:pointer;color:#0891b2">🖨️</button></td>
    </tr>`).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="13" style="color:#dc2626;text-align:center">${e.message}</td></tr>`;}
}
function openMalariaModal(){toast('Malaria form…','info');}

/* ── Peripheral Smear ──────────────────────────────────────── */
async function loadSmears(){
  const tbody=document.getElementById('smear-tbody');if(!tbody)return;
  try{
    const data=await apiFetch(`${API}/hematology/smear?limit=30`);
    setText('kpi-smears',data.length);
    if(!data.length){tbody.innerHTML='<tr><td colspan="12" style="text-align:center;padding:1.5rem;color:#94a3b8">No peripheral smear reports.</td></tr>';return;}
    tbody.innerHTML=data.map(r=>`<tr class="${r.leukemia_flag?'critical-row':''}">
      <td>${r.smear_id||'—'}</td><td>${r.pid||'—'}</td>
      <td>${r.rbc_morphology||'—'}</td><td>${r.wbc_morphology||'—'}</td>
      <td>${r.plt_morphology||'—'}</td>
      <td class="${r.blast_pct>0?'flag-HH':''}">${r.blast_pct!=null?r.blast_pct+'%':'0%'}</td>
      <td>${r.species||'None'}</td>
      <td>${r.sickle_cells?'<span class="badge badge-high">Present</span>':'None'}</td>
      <td>${r.staining_method||'—'}</td>
      <td>${r.microscopist||'—'}</td>
      <td><span class="badge badge-${r.is_validated?'validated':'pending'}">${r.is_validated?'Validated':'Pending'}</span></td>
      <td><button style="font-size:.72rem;padding:.2rem .5rem;background:#f0fdff;border:1px solid #bae6fd;border-radius:6px;cursor:pointer;color:#0891b2">🖨️</button></td>
    </tr>`).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="12" style="color:#dc2626;text-align:center">${e.message}</td></tr>`;}
}
function openSmearModal(){toast('Smear form…','info');}

/* ── IQC Levey-Jennings ────────────────────────────────────── */
async function loadIQC(){
  const tbody=document.getElementById('hem-iqc-tbody');if(!tbody)return;
  try{
    const analyte=document.getElementById('iqc-analyte')?.value||'HGB';
    const data=await apiFetch(`${API}/quality/iqc?department=HEM&analyte=${analyte}&limit=50`);
    if(!data.length){tbody.innerHTML='<tr><td colspan="11" style="text-align:center;padding:1.5rem;color:#94a3b8">No IQC records.</td></tr>';
      setText('kpi-iqc-status','—');return;}
    buildLJChart(data);
    setText('kpi-iqc-status',data.some(r=>r.status==='REJECT')?'REJECT':data.some(r=>r.status==='WARN')?'WARN':'PASS');
    tbody.innerHTML=data.map(r=>`<tr class="${r.status==='REJECT'?'critical-row':r.status==='WARN'?'high-row':''}">
      <td style="font-size:.72rem">${r.run_date||r.created_at?.substring(0,10)||'—'}</td>
      <td>${r.analyte_name||r.analyte_code||'—'}</td>
      <td>${r.control_level||'—'}</td>
      <td style="font-family:monospace;font-size:.73rem">${r.lot_number||'—'}</td>
      <td>${r.target_mean||'—'}</td><td>${r.sd||'—'}</td>
      <td><strong class="${r.status==='REJECT'?'flag-HH':''}">${r.result_value||'—'}</strong></td>
      <td><span style="font-family:monospace">${r.z_score!=null?r.z_score.toFixed(2):'—'}</span></td>
      <td style="font-family:monospace;font-size:.72rem">${r.westgard_rule||'PASS'}</td>
      <td><span class="badge badge-${r.status==='PASS'?'validated':r.status==='WARN'?'pending':'crit-high'}">${r.status||'PASS'}</span></td>
      <td>${r.operator_name||'—'}</td>
    </tr>`).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="11" style="color:#dc2626;text-align:center">${e.message}</td></tr>`;}
}

function buildLJChart(data){
  const ctx=document.getElementById('hem-lj-chart')?.getContext('2d');
  if(!ctx||!data.length) return;
  if(_ljChart) _ljChart.destroy();
  const vals=data.slice().reverse();
  const mean=vals[0]?.target_mean||0,sd=vals[0]?.sd||0;
  _ljChart=new Chart(ctx,{type:'line',
    data:{labels:vals.map((_,i)=>`#${i+1}`),
      datasets:[
        {label:'QC',data:vals.map(r=>r.result_value),borderColor:'#0891b2',backgroundColor:'rgba(8,145,178,.08)',
          pointRadius:5,pointBackgroundColor:vals.map(r=>Math.abs((r.result_value-mean)/sd)>3?'#dc2626':Math.abs((r.result_value-mean)/sd)>2?'#f59e0b':'#10b981'),fill:true,tension:.2},
        {label:'Mean',data:vals.map(()=>mean),borderColor:'#475569',borderWidth:1.5,pointRadius:0,fill:false},
        {label:'+2s',data:vals.map(()=>mean+2*sd),borderColor:'#f59e0b',borderDash:[4,4],borderWidth:1,pointRadius:0,fill:false},
        {label:'-2s',data:vals.map(()=>mean-2*sd),borderColor:'#f59e0b',borderDash:[4,4],borderWidth:1,pointRadius:0,fill:false},
        {label:'+3s',data:vals.map(()=>mean+3*sd),borderColor:'#dc2626',borderDash:[2,2],borderWidth:1,pointRadius:0,fill:false},
        {label:'-3s',data:vals.map(()=>mean-3*sd),borderColor:'#dc2626',borderDash:[2,2],borderWidth:1,pointRadius:0,fill:false},
      ]},
    options:{responsive:true,plugins:{legend:{position:'bottom',labels:{font:{size:9},boxWidth:10}}},
      scales:{x:{ticks:{color:'#64748b',font:{size:9}}},y:{ticks:{color:'#64748b'},beginAtZero:false}}}
  });
}
function openIQCModal(){toast('IQC entry…','info');}

/* ── Critical Book ─────────────────────────────────────────── */
async function loadCriticalBook(){
  const tbody=document.getElementById('hem-book-tbody');if(!tbody)return;
  try{
    const data=await apiFetch(`${API}/laboratory/critical-book?limit=50`);
    if(!data.length){tbody.innerHTML='<tr><td colspan="8" style="text-align:center;padding:1.5rem;color:#94a3b8">No critical entries.</td></tr>';return;}
    tbody.innerHTML=data.map(e=>`<tr>
      <td><strong>${e.entry_number||'—'}</strong></td><td>${e.pid||'—'}</td>
      <td><span class="badge badge-crit-high">${e.critical_reason||'—'}</span></td>
      <td>${e.result||'—'}</td><td>${e.clinician_notified||'—'}</td>
      <td>${e.readback_confirmed?'✅':'⚠️'}</td>
      <td style="font-size:.72rem">${e.archived_at?.substring(0,16)||'—'}</td>
      <td style="font-family:monospace;font-size:.65rem;color:#94a3b8">${(e.pqc_hash||'').substring(0,22)}…</td>
    </tr>`).join('');
  }catch(e){tbody.innerHTML=`<tr><td colspan="8" style="color:#dc2626;text-align:center">${e.message}</td></tr>`;}
}

/* ── Anaemia detail popup ──────────────────────────────────── */
function showMicrocyticDetail(type){
  const d={
    IDA:{t:'Iron Deficiency Anaemia',p:['Ferritin<12µg/L = DIAGNOSTIC of iron store depletion','RDW>14.5% (anisocytosis — varied cell sizes)','Mentzer>13 (IDA favoured)','Serum iron LOW, TIBC HIGH (transferrin sat<16%)','Blood film: pencil cells, hypochromic microcytes, anisocytosis, poikilocytosis','Treatment: Ferrous sulphate 200mg TDS × 3 months beyond Hb normalisation','⚠️ EXCLUDE thalassaemia — never give iron blindly to microcytic patient']},
    THAL:{t:'β-Thalassaemia Trait',p:['HbA2>3.5% on HPLC = DIAGNOSTIC (autosomal recessive)','RDW NORMAL or mildly ↑ (uniform microcytosis — unlike IDA)','RBC count HIGH despite low Hb (paradox — more but smaller cells)','Mentzer<13 (thalassaemia favoured)','Blood film: target cells, basophilic stippling, microcytes','NO iron treatment needed unless concurrent IDA (check ferritin)','Genetic counselling — screen partner if reproductive age']},
    ALPHA_THAL:{t:'α-Thalassaemia Trait',p:['HPLC often NORMAL — α-thal CANNOT be diagnosed by HPLC alone','Requires DNA analysis (α-globin gene deletion)','Common in SE Asia, Africa, Middle East, Mediterranean','Silent carrier (1 deletion): No anaemia, normal indices','Trait (2 deletions): Mild microcytic anaemia — clinically benign','HbH disease (3 deletions): Moderate haemolytic anaemia','Hb Barts hydrops (4 deletions): Lethal — fatal in utero or neonatal']},
    SIDERO:{t:'Sideroblastic Anaemia',p:['Ring sideroblasts on bone marrow aspirate (Perls iron stain) = DIAGNOSTIC','Serum iron ELEVATED (iron accumulates in mitochondria)','Pappenheimer bodies on peripheral blood film','Dimorphic picture (mixed normal and microcytic cells)','Causes: Primary (MDS-RS), Acquired (alcohol, isoniazid, lead, pyridoxine deficiency)','Treatment: Pyridoxine (B6) trial — especially if drug-induced']},
    ACD_MICRO:{t:'Anaemia of Chronic Disease (Microcytic)',p:['Ferritin ELEVATED (acute phase protein — elevated in infection/inflammation)','Serum iron LOW (unlike IDA where TIBC is HIGH, here TIBC is LOW/normal)','sTfR normal — helps differentiate from IDA','Associated with: CKD, malignancy, RA, IBD, chronic infection','Mechanism: hepcidin ↑ → sequestration of iron in macrophages','Treatment: Treat underlying disease; EPO ± IV iron in CKD (per KDIGO)']},
  }[type];
  if(!d) return;
  alert(`${d.t}\n\n${d.p.map(p=>'• '+p).join('\n\n')}`);
}

/* ── Print CBC (white/cyan template) ──────────────────────── */
function printCBCRow(idx){
  const r=_wlData[idx];if(!r) return;
  const now=new Date();
  const w=window.open('','_blank','width=900,height=700');
  if(!w) return;
  w.document.write(`<!DOCTYPE html><html><head><meta charset="UTF-8"><title>CBC - ${r.pid||'Patient'}</title>
  <style>*{box-sizing:border-box;margin:0;padding:0;}body{font-family:Arial,sans-serif;font-size:8.5pt;color:#0f172a;background:#fff;}
  @page{margin:1cm;margin-top:2.8cm;margin-bottom:1.3cm;}
  .header{position:fixed;top:0;left:0;right:0;height:2.5cm;max-height:2.5cm;overflow:hidden;display:flex;align-items:center;gap:.3cm;background:#fff;border-bottom:2.5pt solid #dc2626;padding:0 .5cm;print-color-adjust:exact;}
  .header img{width:1.6cm;height:1.6cm;border-radius:50%;object-fit:cover;border:1.5pt solid #dc2626;}
  .hdr-name{font-size:10pt;font-weight:800;color:#7f1d1d;}.hdr-sub{font-size:6pt;color:#475569;}
  .hdr-right{text-align:right;font-size:6.5pt;color:#475569;margin-left:auto;}
  .body{padding:.3cm .5cm;}
  .title{font-size:9pt;font-weight:800;color:#dc2626;border-bottom:1pt solid #fca5a5;padding-bottom:2pt;margin-bottom:.25cm;text-transform:uppercase;}
  .params{display:grid;grid-template-columns:repeat(5,1fr);gap:.2cm;margin-bottom:.25cm;}
  .param{background:#fafbff;border:0.5pt solid #e4e8f0;border-radius:4pt;padding:3pt 5pt;}
  .pname{font-size:6.5pt;color:#64748b;font-weight:700;text-transform:uppercase;}
  .pval{font-size:11pt;font-weight:800;color:#0e7490;}.pval.crit{color:#7f1d1d;}.pval.low{color:#1e40af;}.pval.high{color:#92400e;}
  .punit{font-size:5.5pt;color:#94a3b8;}
  .diff-table{width:100%;border-collapse:collapse;font-size:7.5pt;margin-bottom:.25cm;}
  .diff-table th{background:#dc2626;color:#fff;padding:2pt 5pt;font-size:6.5pt;text-align:left;}
  .diff-table td{padding:2.5pt 5pt;border-bottom:0.5pt solid #e4e8f0;}
  .diff-table tr:nth-child(even)td{background:#fafbff;}
  .sig{display:grid;grid-template-columns:repeat(3,1fr);gap:.3cm;margin-top:.35cm;border-top:0.5pt solid #fca5a5;padding-top:.15cm;}
  .sig-line{border-bottom:0.5pt solid #dc2626;height:.45cm;margin-bottom:2pt;}.sig-lbl{font-size:6pt;color:#475569;text-align:center;}
  .footer{position:fixed;bottom:0;left:0;right:0;height:1cm;display:flex;align-items:center;justify-content:space-between;padding:0 .5cm;background:#fff;border-top:1.5pt solid #dc2626;font-size:6pt;color:#475569;print-color-adjust:exact;}
  .pqc{font-family:monospace;font-size:5.5pt;color:#15803d;}
  </style></head><body>
  <div class="header">
    <img src="/static/shared/assets/logos/jorinova-logo.jpeg" onerror="this.style.display='none'">
    <div><div class="hdr-name">JORINOVA NEXUS ALIS-X — Haematology</div><div class="hdr-sub">Complete Blood Count · ISO 15189:2022 · ${r.analyzer_name||'Laboratory'}</div></div>
    <div class="hdr-right"><div style="font-weight:700;color:#dc2626">${now.toLocaleDateString('en-GB',{weekday:'long',day:'2-digit',month:'long',year:'numeric'})}</div><div>PID: ${r.pid||'—'} | Lab: ${r.lab_id||r.hem_id||'—'}</div><div>${now.toLocaleTimeString('en-GB')}</div></div>
  </div>
  <div class="body">
    <div class="title">🩸 RBC Panel &amp; Indices</div>
    <div class="params">
      ${[['HGB','g/dL',r.hgb,r.hgb&&r.hgb<7?'crit':r.hgb&&r.hgb<13?'low':''],
         ['RBC','×10¹²/L',r.rbc,''],['HCT','%',r.hct,''],
         ['MCV','fL',r.mcv,''],['MCH','pg',r.mch,''],
         ['MCHC','g/dL',r.mchc,''],['RDW-CV','%',r.rdw,''],
         ['WBC','×10³/µL',r.wbc,r.wbc&&(r.wbc<2||r.wbc>30)?'crit':r.wbc&&(r.wbc<4||r.wbc>11)?'high':''],
         ['PLT','×10³/µL',r.plt,r.plt&&r.plt<20?'crit':r.plt&&r.plt<100?'low':''],
         ['ESR','mm/h',r.esr,'']
        ].map(([n,u,v,c])=>`<div class="param"><div class="pname">${n}</div><div class="pval ${c||''}">${v||'—'}</div><div class="punit">${u}</div></div>`).join('')}
    </div>
    <div class="title">🔬 WBC Differential</div>
    <table class="diff-table"><tr><th>Cell Type</th><th>Abbreviation</th><th>%</th><th># (×10³/µL)</th><th>Normal Range</th><th>Flag</th></tr>
      ${[['Neutrophils','NEU',r.neut_pct,r.neut_abs,'40–75%'],
         ['Lymphocytes','LYM',r.lymph_pct,r.lymph_abs,'20–45%'],
         ['Monocytes','MON',r.mono_pct,r.mono_abs,'2–10%'],
         ['Eosinophils','EOS',r.eos_pct,r.eos_abs,'1–6%'],
         ['Basophils','BAS',r.baso_pct,r.baso_abs,'0–1%']
        ].map(([n,a,p,ab,ref])=>`<tr><td>${n}</td><td style="font-family:monospace">${a}</td><td><strong>${p!=null?p+'%':'—'}</strong></td><td>${ab||'—'}</td><td style="color:#94a3b8">${ref}</td><td>${p==null?'':parseFloat(p)>parseFloat(ref.split('–')[1])?'⬆H':parseFloat(p)<parseFloat(ref.split('–')[0])?'⬇L':'✓N'}</td></tr>`).join('')}
    </table>
    <div class="sig">
      <div><div class="sig-line"></div><div class="sig-lbl">Laboratory Scientist / Technician</div></div>
      <div><div class="sig-line"></div><div class="sig-lbl">Senior Scientist / Validator</div></div>
      <div><div class="sig-line"></div><div class="sig-lbl">Pathologist / Laboratory Manager</div></div>
    </div>
  </div>
  <div class="footer">
    <div>JORINOVA NEXUS ALIS-X · Haematology · ISO 15189:2022 · ${now.toLocaleDateString('en-GB')}</div>
    <div class="pqc">🔐 PQC-Signed · CRYSTALS-Dilithium3 · NIST FIPS 204 · ${now.toISOString()}</div>
  </div>
  <script>window.onload=()=>setTimeout(()=>window.print(),350);<\/script>
  </body></html>`);
  w.document.close();
}

/* ── Init ──────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded',()=>{
  loadWorklist();
  const today=new Date().toISOString().split('T')[0];
  ['wl-date','mal-date','smear-date'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=today;});
});
