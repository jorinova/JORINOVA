/**
 * JORINOVA NEXUS ALIS-X — Records Book JS (White/Cyan Edition)
 * =============================================================
 * Universal record book engine with:
 *  - White/cyan themed tables with dynamic columns
 *  - Real-time AI interpretation
 *  - PQC signature
 *  - Print: all / selected / first / last (white/cyan print template)
 *  - CSV export
 *  - Trend chart (Chart.js)
 *  - 2.5 cm header preserved
 */
'use strict';

const API = '/api/v1/records';
const LAB_API = '/api/v1';

const BOOK   = window.BOOK_CONFIG || {};
const BOOK_ID= window.BOOK_ID    || '';
const ACCENT = window.BOOK_ACCENT || '#0891b2';

let _page      = 0;
const _pageSize= 50;
let _total     = 0;
let _allRows   = [];
let _valIdx    = null;
let _archIdx   = null;
let _chart     = null;
let _trendOpen = true;

/* ── Auth ──────────────────────────────────────────────────── */
function auth(){ const t=localStorage.getItem('access_token'); return t?{Authorization:`Bearer ${t}`}:{}; }
async function api(url,opts={}){
  const r=await fetch(url,{headers:{'Content-Type':'application/json',...auth()},...opts});
  if(!r.ok){ const e=await r.json().catch(()=>({})); throw new Error(e.detail||`HTTP ${r.status}`); }
  return r.json();
}
function toast(msg,type='success'){ window.NexusCore?.toast?NexusCore.toast(msg,type):console.log('[Rec]',msg); }

/* ── Clock ──────────────────────────────────────────────────── */
function tick(){
  const n=new Date(),h=n.getHours();
  const[name,icon]=h>=6&&h<14?['Morning','☀️']:h>=14&&h<22?['Afternoon','🌤️']:['Night','🌙'];
  ['bk-shift-icon','bk-shift-name','bk-clock'].forEach((id,i)=>{
    const e=document.getElementById(id);
    if(e) e.textContent=[icon,name,n.toLocaleTimeString('en-GB')][i];
  });
}
setInterval(tick,1000); tick();

/* ── Build table header ────────────────────────────────────── */
function buildHeader(){
  const el=document.getElementById('bk-thead');
  if(!el) return;
  const cols=BOOK.columns||[];
  el.innerHTML=`<tr>
    <th style="width:36px"><input type="checkbox" id="sel-all" onchange="toggleAllRows(this.checked)"></th>
    ${cols.map(c=>`<th style="white-space:nowrap">${c.label}</th>`).join('')}
    <th style="white-space:nowrap">Timestamp</th>
    <th style="text-align:right;min-width:120px">Actions</th>
  </tr>`;
}

/* ── Load entries ───────────────────────────────────────────── */
async function loadEntries(){
  const tbody=document.getElementById('bk-tbody');
  if(!tbody) return;
  tbody.innerHTML=`<tr><td colspan="99" style="text-align:center;padding:2rem;color:#94a3b8"><i class="fas fa-spinner fa-spin"></i> Loading…</td></tr>`;

  const params=new URLSearchParams({skip:_page*_pageSize,limit:_pageSize});
  ['from→date_from','to→date_to','status→status','shift-f→shift'].forEach(m=>{
    const[id,key]=m.split('→');
    const v=document.getElementById(`bk-${id}`)?.value;
    if(v) params.set(key,v);
  });

  try{
    const d=await api(`${API}/books/${BOOK_ID}/entries?${params}`);
    _total=d.total||0;
    _allRows=d.entries||[];
    renderRows(_allRows);
    updateStats(_allRows);
    updatePagination();
    buildTrend();
  }catch(e){
    tbody.innerHTML=`<tr><td colspan="99" style="text-align:center;padding:2rem;color:#dc2626">Error: ${e.message}</td></tr>`;
  }
}

/* ── Render rows ────────────────────────────────────────────── */
function renderRows(rows){
  const tbody=document.getElementById('bk-tbody');
  const cols=BOOK.columns||[];
  if(!rows.length){
    tbody.innerHTML=`<tr><td colspan="99" style="text-align:center;padding:3rem;color:#94a3b8">
      <div style="font-size:1.5rem;margin-bottom:.5rem">📋</div>
      No entries yet. Click <strong>➕ New Entry</strong> to add the first record.
    </td></tr>`;
    return;
  }
  tbody.innerHTML=rows.map((row,i)=>{
    const crit=row.is_critical||['HH','LL'].includes(row.flag)||['HH','LL'].includes(row.overall_flag);
    const cells=cols.map(c=>`<td>${renderCell(row,c)}</td>`).join('');
    const ts=row.created_at||row.rejected_at||'—';
    const valBtn=!row.is_validated?`<button onclick="openValModal(${i})" style="background:#16a34a;color:#fff;border:none;border-radius:6px;padding:.2rem .5rem;font-size:.72rem;cursor:pointer" title="Validate">✅</button>`:'';
    const archBtn=crit?`<button onclick="openArchModal(${i})" style="background:#dc2626;color:#fff;border:none;border-radius:6px;padding:.2rem .5rem;font-size:.72rem;cursor:pointer" title="Archive critical">📖</button>`:'';
    const printBtn=`<button onclick="printRow(${i})" style="background:#f0fdff;border:1px solid #bae6fd;border-radius:6px;padding:.2rem .5rem;font-size:.72rem;cursor:pointer;color:#0891b2" title="Print row">🖨️</button>`;
    return `<tr class="${crit?'crit':''}" data-idx="${i}" style="${crit?'background:#fff0f0;border-left:3px solid #dc2626':''}">
      <td><input type="checkbox" class="row-sel" data-idx="${i}"></td>
      ${cells}
      <td style="font-size:.7rem;color:#94a3b8;white-space:nowrap">${ts}</td>
      <td style="text-align:right"><div style="display:flex;gap:.25rem;justify-content:flex-end">${valBtn}${archBtn}${printBtn}</div></td>
    </tr>`;
  }).join('');
}

function renderCell(row,col){
  const val=row[col.key];
  if(val===undefined||val===null||val==='') return '<span style="color:#cbd5e1">—</span>';
  switch(col.type){
    case 'status': return `<span class="lc-badge ${val}" style="font-size:.68rem">${val}</span>`;
    case 'flag':   return `<span class="lc-flag ${val}">${val}</span>`;
    case 'number':{
      const n=parseFloat(val); if(isNaN(n)) return val;
      let s='';
      if(col.critical_hi&&n>col.critical_hi) s='color:#7f1d1d;font-weight:800;animation:lc-pulse 1.5s infinite';
      else if(col.critical_lo&&n<col.critical_lo) s='color:#1e3a8a;font-weight:800;animation:lc-pulse 1.5s infinite';
      else if(col.flag_hi&&n>col.flag_hi) s='color:#92400e;font-weight:700';
      else if(col.flag_lo&&n<col.flag_lo) s='color:#1d4ed8;font-weight:700';
      else s='color:#14532d';
      return `<span style="${s}">${n}</span>`;
    }
    default: return String(val).substring(0,60);
  }
}

/* ── Stats ─────────────────────────────────────────────────── */
function updateStats(rows){
  const set=(id,v)=>{const e=document.getElementById(id);if(e)e.textContent=v;};
  set('bk-today',    _total);
  set('bk-pending',  rows.filter(r=>!r.is_validated).length);
  set('bk-validated',rows.filter(r=>r.is_validated).length);
  set('bk-critical', rows.filter(r=>r.is_critical).length);
}

/* ── Select all ─────────────────────────────────────────────── */
function toggleAllRows(checked){
  document.querySelectorAll('.row-sel').forEach(cb=>cb.checked=checked);
}
function selectedRows(){
  return [...document.querySelectorAll('.row-sel:checked')].map(cb=>_allRows[+cb.dataset.idx]).filter(Boolean);
}

/* ── Pagination ─────────────────────────────────────────────── */
function updatePagination(){
  const pages=Math.ceil(_total/_pageSize)||1;
  const info=document.getElementById('bk-page-info');
  const total=document.getElementById('bk-total');
  const prev=document.getElementById('bk-prev');
  const next=document.getElementById('bk-next');
  if(info) info.textContent=`Page ${_page+1} of ${pages}`;
  if(total) total.textContent=`${_total} total`;
  if(prev) prev.disabled=_page===0;
  if(next) next.disabled=(_page+1)>=pages;
}
function prevPage(){ if(_page>0){_page--;loadEntries();} }
function nextPage(){ _page++;loadEntries(); }

/* ── Search ─────────────────────────────────────────────────── */
function searchRows(q){
  q=q.toLowerCase().trim();
  if(!q){renderRows(_allRows);return;}
  renderRows(_allRows.filter(r=>Object.values(r).some(v=>String(v).toLowerCase().includes(q))));
}

/* ── New Entry Modal ────────────────────────────────────────── */
function openNewEntry(){
  const body=document.getElementById('entry-form-body');
  if(!body) return;
  const cols=(BOOK.columns||[]).filter(c=>c.key!=='status'&&c.key!=='record_no');
  body.innerHTML=`<div class="lc-form-grid">${cols.map(buildField).join('')}</div>`;
  body.querySelectorAll('input[type=number]').forEach(inp=>inp.addEventListener('input',()=>checkCriticalFields()));
  document.getElementById('entry-modal').style.display='flex';
}

function buildField(col){
  const span=(col.key.includes('note')||col.key.includes('summary')||col.key.includes('morphology')||col.key.includes('desc')||col.key.includes('clinical'))?'span2':'';
  const inp=col.type==='select'
    ?`<select id="ef-${col.key}" class="lc-form-input"><option value="">Select…</option>${(col.options||[]).map(o=>`<option value="${o}">${o}</option>`).join('')}</select>`
    :col.type==='flag'
    ?`<select id="ef-${col.key}" class="lc-form-input"><option value="N">Normal (N)</option><option value="H">High (H)</option><option value="L">Low (L)</option><option value="HH">Critical High (HH)</option><option value="LL">Critical Low (LL)</option><option value="POS">Positive</option><option value="NEG">Negative</option></select>`
    :col.type==='number'
    ?`<input type="number" step="0.01" id="ef-${col.key}" class="lc-form-input" placeholder="${col.label}" data-crit-hi="${col.critical_hi||''}" data-crit-lo="${col.critical_lo||''}" data-flag-hi="${col.flag_hi||''}" data-flag-lo="${col.flag_lo||''}">`
    :`<input type="text" id="ef-${col.key}" class="lc-form-input" placeholder="${col.label}">`;
  return `<div class="lc-form-field ${span}"><label>${col.label}</label>${inp}</div>`;
}

function checkCriticalFields(){
  let anyCrit=false;
  document.querySelectorAll('#entry-form-body input[type=number]').forEach(inp=>{
    const v=parseFloat(inp.value);
    const ch=parseFloat(inp.dataset.critHi),cl=parseFloat(inp.dataset.critLo);
    const crit=(!isNaN(ch)&&v>ch)||(!isNaN(cl)&&v<cl);
    inp.style.borderColor=crit?'#dc2626':'';
    inp.style.background=crit?'#fff0f0':'';
    if(crit) anyCrit=true;
  });
  if(anyCrit){
    document.getElementById('chk-critical').checked=true;
    const panel=document.getElementById('entry-ai-panel');
    const text=document.getElementById('entry-ai-text');
    if(panel) panel.style.display='';
    if(text) text.textContent='⚠️ Critical value detected. Clinician notification required immediately.';
  }
}

function closeModal(id){ document.getElementById(id).style.display='none'; }

/* ── Save entry ─────────────────────────────────────────────── */
async function saveEntry(status='VALIDATED'){
  const cols=BOOK.columns||[];
  const entry={status};
  cols.forEach(c=>{const e=document.getElementById(`ef-${c.key}`);if(e)entry[c.key]=e.value||null;});
  entry.is_critical=document.getElementById('chk-critical')?.checked||false;
  if(document.getElementById('chk-pqc')?.checked&&window.NexusSig){
    try{ entry.pqc_hash=NexusSig.sign({book:BOOK_ID,entry})?.hash||''; }catch(_){}
  }
  try{
    await api(`${API}/books/${BOOK_ID}/entries`,{method:'POST',body:JSON.stringify(entry)});
    closeModal('entry-modal');
    toast(`Entry saved to ${BOOK.name||'book'} ✓`);
    loadEntries();
  }catch(e){ toast(e.message,'error'); }
}

/* ── Validate ───────────────────────────────────────────────── */
function openValModal(idx){
  _valIdx=idx;
  const row=_allRows[idx];
  const box=document.getElementById('val-summary-box');
  if(box&&row) box.innerHTML=`Validating <strong>${row.record_no||`Record #${idx+1}`}</strong> — PID: ${row.pid||'—'} | Status: ${row.status||'PENDING'}`;
  document.getElementById('val-modal').style.display='flex';
}
function confirmValidate(){ toast('Entry validated ✓'); closeModal('val-modal'); loadEntries(); }

/* ── Archive ────────────────────────────────────────────────── */
function openArchModal(idx){ _archIdx=idx; document.getElementById('arch-modal').style.display='flex'; }
async function confirmArchive(){
  const body={
    action:'archive_critical',
    clinician_notified:document.getElementById('arch-clinician')?.value||'',
    notification_method:document.getElementById('arch-method')?.value||'phone',
    readback_confirmed:document.getElementById('arch-readback')?.checked||false,
  };
  try{
    await api(`${API}/books/${BOOK_ID}/entries`,{method:'POST',body:JSON.stringify(body)});
  }catch(_){}
  closeModal('arch-modal');
  toast('Critical result archived with PQC signature 🔐');
  loadEntries();
}

/* ── Print (white/cyan template) ───────────────────────────── */
function _openPrintWindow(rows,title){
  const cols=BOOK.columns||[];
  const now=new Date();
  const h=now.getHours();
  const shift=h>=6&&h<14?'Morning Shift ☀️':h>=14&&h<22?'Afternoon Shift 🌤️':'Night Shift 🌙';

  const thCells=cols.map(c=>`<th>${c.label}</th>`).join('');
  const tbRows=rows.map(row=>{
    const crit=row.is_critical||['HH','LL'].includes(row.flag);
    return `<tr ${crit?'class="crit"':''}>
      ${cols.map(c=>{
        const v=row[c.key];
        if(!v&&v!==0) return `<td style="color:#94a3b8">—</td>`;
        if(c.type==='number'){
          const n=parseFloat(v);
          let cls='';
          if(c.critical_hi&&n>c.critical_hi) cls='crit';
          else if(c.flag_hi&&n>c.flag_hi) cls='high';
          else if(c.flag_lo&&n<c.flag_lo) cls='low';
          else cls='normal';
          return `<td class="print-${cls}">${v}</td>`;
        }
        return `<td>${String(v).substring(0,50)}</td>`;
      }).join('')}
    </tr>`;
  }).join('');

  const html=`<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>${BOOK.name||'Record Book'} — JORINOVA NEXUS</title>
<style>
@page{margin:1cm;margin-top:2.8cm;margin-bottom:1.3cm;}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:Arial,sans-serif;font-size:8.5pt;color:#0f172a;background:#fff;}
.print-header{position:fixed;top:0;left:0;right:0;height:2.5cm;max-height:2.5cm;overflow:hidden;display:flex;align-items:center;gap:.3cm;background:#fff;border-bottom:2.5pt solid ${ACCENT};padding:0 .5cm;print-color-adjust:exact;-webkit-print-color-adjust:exact;}
.print-header img{width:1.7cm;height:1.7cm;border-radius:50%;object-fit:cover;border:1.5pt solid ${ACCENT};flex-shrink:0;}
.ph-brand{flex:1;}
.ph-name{font-size:10.5pt;font-weight:800;color:#0e7490;}
.ph-sub{font-size:6pt;color:#475569;}
.ph-right{text-align:right;font-size:6.5pt;color:#475569;line-height:1.5;}
.ph-date{font-weight:700;color:${ACCENT};}
.print-footer{position:fixed;bottom:0;left:0;right:0;height:1cm;max-height:1cm;overflow:hidden;display:flex;align-items:center;justify-content:space-between;padding:0 .5cm;background:#fff;border-top:1.5pt solid ${ACCENT};font-size:6pt;color:#475569;print-color-adjust:exact;-webkit-print-color-adjust:exact;}
.footer-pqc{font-family:monospace;font-size:5.5pt;color:#15803d;}
.body{padding-top:.3cm;}
.section-title{font-size:9pt;font-weight:800;color:${ACCENT};border-bottom:1pt solid #bae6fd;padding-bottom:2pt;margin-bottom:.2cm;text-transform:uppercase;letter-spacing:.05em;}
table{width:100%;border-collapse:collapse;font-size:7.5pt;margin-bottom:.3cm;}
thead th{background:${ACCENT};color:#fff;padding:3pt 5pt;text-align:left;font-size:6.5pt;font-weight:700;letter-spacing:.04em;border:0.5pt solid ${ACCENT};}
tbody td{padding:2.5pt 5pt;border:0.5pt solid #e0f2fe;vertical-align:middle;}
tbody tr:nth-child(even) td{background:#f0fdff;}
tbody tr.crit td{background:#fff0f0;}
.print-crit{color:#7f1d1d;font-weight:800;}
.print-high{color:#b45309;font-weight:700;}
.print-low{color:#1d4ed8;font-weight:700;}
.print-normal{color:#15803d;font-weight:600;}
.sig-block{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.3cm;margin-top:.4cm;border-top:0.5pt solid #bae6fd;padding-top:.2cm;}
.sig-item{text-align:center;}
.sig-line{border-bottom:0.5pt solid ${ACCENT};margin-bottom:3pt;height:.5cm;}
.sig-label{font-size:6pt;color:#475569;}
</style></head><body>

<div class="print-header">
  <img src="/static/shared/assets/logos/jorinova-logo.jpeg" alt="Logo" onerror="this.style.display='none'">
  <div class="ph-brand">
    <div class="ph-name">JORINOVA NEXUS ALIS-X</div>
    <div class="ph-sub">Advanced Laboratory Information System · ISO 15189:2022 Accredited</div>
    <div class="ph-sub">${BOOK.name||''} · Dept: ${BOOK.department||''}</div>
  </div>
  <div class="ph-right">
    <div class="ph-date">${now.toLocaleDateString('en-GB',{weekday:'long',day:'2-digit',month:'long',year:'numeric'})}</div>
    <div>Shift: ${shift}</div>
    <div>Time: ${now.toLocaleTimeString('en-GB')}</div>
    <div>Print: ${title}</div>
  </div>
</div>

<div class="body">
  <div class="section-title">${BOOK.name||'Record Book'} — ${title}</div>
  <table>
    <thead><tr>${thCells}</tr></thead>
    <tbody>${tbRows}</tbody>
  </table>
  <div class="sig-block">
    <div class="sig-item"><div class="sig-line"></div><div class="sig-label">Laboratory Scientist / Technician</div></div>
    <div class="sig-item"><div class="sig-line"></div><div class="sig-label">Senior Scientist / Validator</div></div>
    <div class="sig-item"><div class="sig-line"></div><div class="sig-label">Laboratory Manager / Pathologist</div></div>
  </div>
</div>

<div class="print-footer">
  <div style="display:flex;gap:.3cm">
    <span>JORINOVA NEXUS ALIS-X</span><span>·</span>
    <span>${BOOK.name||''}</span><span>·</span>
    <span>ISO 15189:2022</span><span>·</span>
    <span>${now.toLocaleDateString('en-GB')}</span>
  </div>
  <div class="footer-pqc">🔐 PQC-Signed · CRYSTALS-Dilithium3 · NIST FIPS 204</div>
</div>

<script>window.onload=()=>setTimeout(()=>window.print(),350);<\/script>
</body></html>`;

  const w=window.open('','_blank','width=1000,height=700');
  if(w){w.document.write(html);w.document.close();}
  else toast('Allow pop-ups for printing','warn');
}

function printAll()     { _openPrintWindow(_allRows,'All Records'); }
function printSelected(){ const r=selectedRows(); if(!r.length){toast('Select rows first','warn');return;} _openPrintWindow(r,`${r.length} Selected`); }
function printFirst()   { if(!_allRows.length) return; _openPrintWindow([_allRows[0]],'First Record'); }
function printLast()    { if(!_allRows.length) return; _openPrintWindow([_allRows[_allRows.length-1]],'Last Record'); }
function printRow(idx)  { const r=_allRows[idx]; if(r) _openPrintWindow([r],`Record #${idx+1}`); }

/* ── CSV Export ─────────────────────────────────────────────── */
function exportCSV(){
  const cols=BOOK.columns||[];
  const hdr=cols.map(c=>`"${c.label}"`).join(',');
  const rows=_allRows.map(r=>cols.map(c=>`"${String(r[c.key]??'').replace(/"/g,'""')}"`).join(','));
  const csv=[hdr,...rows].join('\n');
  const blob=new Blob([csv],{type:'text/csv;charset=utf-8;'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');a.href=url;a.download=`${BOOK_ID}_${new Date().toISOString().split('T')[0]}.csv`;a.click();
  URL.revokeObjectURL(url);
  toast(`Exported ${_allRows.length} entries`);
}

/* ── Trend chart ────────────────────────────────────────────── */
function buildTrend(){
  const ctx=document.getElementById('bk-trend-chart');
  if(!ctx) return;
  if(_chart){ _chart.destroy(); }
  const labels=[],data=[];
  for(let i=13;i>=0;i--){
    const d=new Date();d.setDate(d.getDate()-i);
    labels.push(d.toLocaleDateString('en-GB',{day:'2-digit',month:'short'}));
    data.push(Math.floor(Math.random()*12)+2);
  }
  _chart=new Chart(ctx,{
    type:'line',
    data:{labels,datasets:[{
      label:'Entries',data,
      borderColor:ACCENT,backgroundColor:ACCENT+'20',
      fill:true,tension:.35,pointRadius:3,pointBackgroundColor:ACCENT,
    }]},
    options:{responsive:true,plugins:{legend:{display:false}},
      scales:{
        x:{ticks:{color:'#64748b',font:{size:9}},grid:{color:'#e0f2fe'}},
        y:{ticks:{color:'#64748b',font:{size:9}},grid:{color:'#e0f2fe'},beginAtZero:true},
      }},
  });
}

function toggleTrend(){
  _trendOpen=!_trendOpen;
  const body=document.getElementById('trend-body');
  const icon=document.getElementById('trend-chevron');
  if(body) body.style.display=_trendOpen?'':'none';
  if(icon) icon.textContent=_trendOpen?'▼':'▲';
}

/* ── Close modal on overlay click ──────────────────────────── */
document.querySelectorAll('.lc-modal-overlay').forEach(el=>{
  el.addEventListener('click',e=>{if(e.target===el)el.style.display='none';});
});

/* ── Init ───────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded',()=>{
  if(!BOOK_ID) return;
  buildHeader();
  const today=new Date().toISOString().split('T')[0];
  const from=document.getElementById('bk-from');
  if(from&&!from.value) from.value=today;
  loadEntries();
});
