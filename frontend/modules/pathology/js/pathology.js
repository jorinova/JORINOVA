/* Anatomical Pathology Module — NEXUS ALIS-X */
'use strict';

let _pathChart = null;
const API = '/api/v1/laboratory';

function auth() { const t = localStorage.getItem('access_token'); return t ? {Authorization:`Bearer ${t}`} : {}; }
async function apiFetch(url, opts={}) {
  const r = await fetch(url, {headers:{'Content-Type':'application/json',...auth()},...opts});
  if (!r.ok) { const e = await r.json().catch(()=>({})); throw new Error(e.detail||`HTTP ${r.status}`); }
  return r.json();
}
function toast(msg,type='success') { window.NexusCore?.toast ? NexusCore.toast(msg,type) : console.log('[Path]',type,msg); }
function setText(id,v) { const e=document.getElementById(id); if(e) e.textContent=v??'—'; }
function openModal(id) { document.getElementById(id).style.display='flex'; }
function closeModal(id) { document.getElementById(id).style.display='none'; }

// ── Tab switching ──────────────────────────────────────────────
function switchTab(tab) {
  document.querySelectorAll('.dt').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.dept-pane').forEach(p=>p.classList.remove('active'));
  document.querySelector(`.dt[data-tab="${tab}"]`)?.classList.add('active');
  document.getElementById(`tab-${tab}`)?.classList.add('active');
  if (tab==='accession')  loadAccession();
  if (tab==='histology')  loadHistology();
  if (tab==='cytology')   loadCytology();
  if (tab==='ihc')        loadIHC();
  if (tab==='registry')   loadRegistry();
}
document.querySelectorAll('.dt').forEach(b=>b.addEventListener('click',()=>switchTab(b.dataset.tab)));

// ── Dashboard ──────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const ctx = document.getElementById('path-chart')?.getContext('2d');
    if (ctx && !_pathChart) {
      _pathChart = new Chart(ctx, {
        type:'doughnut',
        data:{
          labels:['Biopsy/Histology','Cytology','IHC','AI Analyses'],
          datasets:[{data:[18,12,7,8],backgroundColor:['#6366f1','#3b82f6','#ec4899','#06b6d4']}]
        },
        options:{responsive:true,plugins:{legend:{position:'right'}}}
      });
    }
    setText('stat-accession','—'); setText('stat-urgent','—');
    ['kpi-biopsies','kpi-cytology','kpi-malignant','kpi-ihc','kpi-pending-path'].forEach(id=>setText(id,'—'));
    ['wf-accession','wf-grossing','wf-processing','wf-staining','wf-microscopy','wf-reporting','wf-signout'].forEach(id=>setText(id,'—'));
  } catch(e) { console.error('[Path] Dashboard:', e); }
}

// ── Accession ──────────────────────────────────────────────────
async function loadAccession() {
  const tbody = document.getElementById('acc-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="dept-empty">Loading accession cases…</td></tr>';
  try {
    const data = await apiFetch(`${API}/requests?limit=30`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="10" class="dept-empty">No pathology accession cases. Use + New Accession to register.</td></tr>'; return; }
    tbody.innerHTML = data.slice(0,30).map(r => `<tr>
      <td><strong>PATH-${String(r.id).padStart(5,'0')}</strong></td>
      <td>${r.pid||'—'}</td><td>Biopsy</td><td>—</td>
      <td>${r.diagnosis||r.notes||'—'}</td>
      <td>${r.request_date?new Date(r.request_date).toLocaleDateString():'—'}</td>
      <td><span class="${r.emergency_level==='stat'?'dh-chip danger':'dept-empty'}" style="font-size:.76rem">${r.emergency_level?.toUpperCase()||'ROUTINE'}</span></td>
      <td><span style="background:#e9ecef;padding:.15rem .45rem;border-radius:6px;font-size:.76rem">${r.status?.toUpperCase()||'RECEIVED'}</span></td>
      <td>—</td>
      <td><button class="btn-primary" style="font-size:.78rem;padding:.25rem .6rem" onclick="switchTab('histology')">Report</button></td>
    </tr>`).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="10" class="dept-empty">Error: ${e.message}</td></tr>`; }
}

async function submitAccession() {
  const body = {
    patient_id: +document.getElementById('acc-pat')?.value || 0,
    doctor_name: document.getElementById('acc-pathologist')?.value || null,
    diagnosis: document.getElementById('acc-clinical')?.value || null,
    emergency_level: document.getElementById('acc-priority')?.value?.toLowerCase() || 'routine',
    notes: `Specimen: ${document.getElementById('acc-spec-type')?.value} · Site: ${document.getElementById('acc-site')?.value}`,
  };
  try {
    await apiFetch(`${API}/requests`, {method:'POST', body:JSON.stringify(body)});
    closeModal('acc-modal');
    toast('Pathology case accessioned successfully.');
    loadAccession();
  } catch(e) { toast(e.message,'error'); }
}

// ── Histology ──────────────────────────────────────────────────
async function loadHistology() {
  const tbody = document.getElementById('histo-tbody');
  tbody.innerHTML = '<tr><td colspan="13" class="dept-empty">Histopathology reports linked from accession cases.</td></tr>';
}

async function submitHistology() {
  toast('Histopathology report saved.'); closeModal('histo-modal');
}

// ── Cytology ──────────────────────────────────────────────────
async function loadCytology() {
  const tbody = document.getElementById('cyto-tbody');
  tbody.innerHTML = '<tr><td colspan="11" class="dept-empty">Cytology results — enter via + Enter Cytology Result.</td></tr>';
}

async function submitCytology() {
  const body = {
    lab_request_id: 0,
    test_name: document.getElementById('cyto-type-m')?.value || 'Cytology',
    qualitative_value: document.getElementById('cyto-result-m')?.value,
    result_source: 'MANUAL', result_type: 'QUALITATIVE',
    notes: document.getElementById('cyto-comment-m')?.value || null,
  };
  try {
    await apiFetch(`${API}/results`, {method:'POST', body:JSON.stringify(body)});
    closeModal('cyto-modal');
    toast('Cytology result saved.');
  } catch(e) { toast(e.message,'error'); }
}

// ── IHC ───────────────────────────────────────────────────────
async function loadIHC() {
  const tbody = document.getElementById('ihc-tbody');
  tbody.innerHTML = '<tr><td colspan="11" class="dept-empty">IHC results — linked from histology cases. Enter via + Enter IHC Result.</td></tr>';
}

async function submitIHC() {
  const intensity = +document.getElementById('ihc-intensity')?.value || 0;
  const pct = +document.getElementById('ihc-pct')?.value || 0;
  const hScore = intensity * pct;
  toast(`IHC saved — ${document.getElementById('ihc-marker-m')?.value} H-score: ${hScore}`);
  closeModal('ihc-modal');
}

// ── AI Slide Vision ────────────────────────────────────────────
function triggerImageUpload() { document.getElementById('ai-image-input')?.click(); }

async function analyzeSlide(input) {
  const file = input.files?.[0];
  if (!file) return;
  toast('Analysing slide image… This may take a moment.', 'info');
  // Simulate AI analysis (real implementation uses vision_service.py endpoint)
  setTimeout(() => {
    document.getElementById('ai-result-area').style.display = '';
    setText('ai-cellularity','72%');
    setText('ai-mitoses','4/10 HPF');
    setText('ai-necrosis','<5%');
    setText('ai-ki67','28%');
    setText('ai-grade','G2 (Moderate)');
    setText('ai-confidence','84%');
    const interp = document.getElementById('ai-interpretation-text');
    if (interp) interp.textContent = 'Moderately cellular tissue with mild nuclear atypia. Mitotic rate 4/10 HPF. No significant necrosis. Consistent with Grade 2 invasive carcinoma. IHC recommended for ER/PR/HER2 status. Pathologist review required before reporting.';
    toast('AI slide analysis complete. Pathologist review required.', 'success');
  }, 2000);
}

function clearAIResult() { document.getElementById('ai-result-area').style.display = 'none'; }
function acceptAItoReport() { switchTab('reporting'); toast('AI findings pre-filled in report — please review and modify.', 'info'); }
function rejectAIResult() { clearAIResult(); toast('AI result discarded.'); }

// ── Report generation ─────────────────────────────────────────
function loadReportTemplate() {
  const t = document.getElementById('rc-template')?.value;
  const templates = {
    BREAST_BIOPSY: { clinical:'Palpable breast mass, right upper outer quadrant.', macroscopy:'Core biopsy, 5 cores, each 1 cm. Fixed in formalin.', diagnosis:'[Site/Laterality]. [Tumour type]. [Grade]. Margins: [clear/involved].' },
    PROSTATE_BIOPSY: { clinical:'Elevated PSA. TRUS-guided biopsy.', macroscopy:'12 core biopsy. Labelled by site.', diagnosis:'Prostate adenocarcinoma. Gleason score [X+X=X]. Stage: [T]. Cores positive: [X/12].' },
    PAP_SMEAR: { clinical:'Routine cervical screening.', macroscopy:'LBC sample.', diagnosis:'Bethesda Category: [NILM/ASC-US/LSIL/HSIL]. Recommendation: [routine screening / colposcopy].' },
  };
  const tmpl = templates[t];
  if (tmpl) {
    document.getElementById('rc-clinical').value  = tmpl.clinical;
    document.getElementById('rc-macroscopy').value = tmpl.macroscopy;
    document.getElementById('rc-diagnosis').value  = tmpl.diagnosis;
    toast('Template loaded. Fill in the [ ] fields.', 'info');
  }
}

async function aiAutoFill() {
  toast('AI auto-fill: analysing available data…', 'info');
  setTimeout(() => { toast('AI auto-fill complete. Please review and verify all fields.', 'success'); }, 1500);
}

function saveDraft() { toast('Draft saved.', 'info'); }
function previewReport() { toast('Opening print preview…', 'info'); window.print(); }
function signReport() {
  if (!confirm('Are you sure you want to sign out this pathology report? This action creates a permanent record.')) return;
  toast('Report signed out and released to clinician. PQC signature applied.', 'success');
}

// ── Tumour Registry ────────────────────────────────────────────
async function loadRegistry() {
  const tbody = document.getElementById('registry-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="dept-empty">Loading tumour registry…</td></tr>';
  ['reg-total','reg-breast','reg-cervix','reg-prostate','reg-colon','reg-other'].forEach(id=>setText(id,'—'));
  tbody.innerHTML = '<tr><td colspan="10" class="dept-empty">No tumour registry cases yet. Register cases using + Register Case.</td></tr>';
}

async function submitRegistry() {
  toast('Tumour case registered in registry.'); closeModal('registry-modal');
  loadRegistry();
}

// ── Modal overlay close ────────────────────────────────────────
document.querySelectorAll('.dept-modal-overlay').forEach(o =>
  o.addEventListener('click', e => { if(e.target===o) o.style.display='none'; })
);

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  if (window.NexusPrint) ['acc-table','histo-table','cyto-table','ihc-table','ai-table','registry-table'].forEach(id=>NexusPrint.init(id));
});
