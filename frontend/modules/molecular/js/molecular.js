/* Molecular Biology Module — NEXUS ALIS-X */
'use strict';

const API = '/api/v1/molecular';
let _molValidateCtx = null;
let _molArchiveCtx  = null;
let _pcrCategory    = 'TB';

// ── Auth ──────────────────────────────────────────────────────────────────────
function authHeader() {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(url, opts = {}) {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    ...opts,
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

function toast(msg, type = 'success') {
  if (window.NexusCore?.toast) { window.NexusCore.toast(msg, type); return; }
  alert(msg);
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? '—';
}

// ── Tab switching ────────────────────────────────────────────────────────────
function switchTab(tabName) {
  document.querySelectorAll('#mol-tabs .tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('#mol-app .tab-pane').forEach(p => p.classList.remove('active'));
  const btn  = document.querySelector(`#mol-tabs .tab-btn[data-tab="${tabName}"]`);
  const pane = document.getElementById(`tab-${tabName}`);
  if (btn)  btn.classList.add('active');
  if (pane) pane.classList.add('active');
  if (tabName === 'genexpert')   loadGeneXpert();
  if (tabName === 'viral-pcr')   loadViralPCR();
  if (tabName === 'viral-load')  loadViralLoad();
  if (tabName === 'genetic')     loadGenetic();
  if (tabName === 'validation')  loadMolValidation();
  if (tabName === 'book')        loadMolBook();
}

document.querySelectorAll('#mol-tabs .tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ── Dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const d = await apiFetch(`${API}/dashboard`);
    setText('kpi-pcr-pending',  d.pcr_pending);
    setText('kpi-pcr-today',    d.pcr_today);
    setText('kpi-tb-detected',  d.genexpert_detected_today);
    setText('kpi-mdr-tb',       d.mdr_tb_total);
    setText('kpi-xdr-tb',       d.xdr_tb_total);
    setText('kpi-vl-pending',   d.vl_pending);
    setText('kpi-hiv-high',     d.hiv_high_vl_today);
    setText('kpi-book',         d.critical_book_total);
    setText('stat-pcr-pending', d.pcr_pending);
    setText('stat-mdr',         d.mdr_tb_total);
    setText('stat-xdr',         d.xdr_tb_total);
    setText('sq-tb',   `${d.pcr_pending} pending`);
    setText('sq-viral', '— pending');
    setText('sq-vl',   `${d.vl_pending} pending`);
  } catch(e) { console.error('Dashboard load failed', e); }
}

// ── PCR Test menus ────────────────────────────────────────────────────────────
const PCR_TESTS = {
  TB: [
    'GeneXpert MTB/RIF Ultra', 'GeneXpert MTB/RIF',
    'MTB PCR (in-house)', 'LPA (Line Probe Assay)',
    'Xpert Ultra (sputum)', 'Xpert Ultra (EPTB)',
  ],
  VIRAL: [
    'HIV-1 RNA PCR', 'HBV DNA PCR', 'HCV RNA PCR',
    'CMV DNA PCR', 'EBV DNA PCR', 'HSV PCR',
  ],
  STI: [
    'Chlamydia trachomatis PCR', 'Neisseria gonorrhoeae PCR',
    'Trichomonas vaginalis PCR', 'Mycoplasma genitalium PCR',
    'Treponema pallidum PCR', 'HPV genotyping',
    'HSV-1/2 PCR (genital)',
  ],
  RESPIRATORY: [
    'BioFire Respiratory Panel', 'SARS-CoV-2 PCR',
    'Influenza A/B PCR', 'RSV PCR', 'Adenovirus PCR',
  ],
  FUNGAL: [
    'Aspergillus PCR', 'Candida PCR', 'Cryptococcus PCR',
  ],
  OTHER: [],
};

function pcrCategoryChanged() {
  const cat  = document.getElementById('pcr-category').value;
  _pcrCategory = cat;
  const sel  = document.getElementById('pcr-test-select');
  const list = PCR_TESTS[cat] || [];
  sel.innerHTML = '<option value="">Select test…</option>' +
    list.map(t => `<option value="${t}">${t}</option>`).join('');
  // Show/hide TB-specific fields
  const isTB = cat === 'TB';
  document.getElementById('pcr-rif-row').style.display       = isTB ? '' : 'none';
  document.getElementById('pcr-tb-class-row').style.display  = isTB ? '' : 'none';
  document.getElementById('pcr-semi-row').style.display      = isTB ? '' : 'none';
}

function fillPCRTestName() {
  const v = document.getElementById('pcr-test-select').value;
  if (v) document.getElementById('pcr-test-name').value = v;
}

function pcrResultChanged() {
  const result = document.getElementById('pcr-result').value;
  if (_pcrCategory === 'TB' && result === 'DETECTED') {
    document.getElementById('pcr-critical').checked = true;
  }
}

function rifChanged() {
  const rif = document.getElementById('pcr-rif').value;
  if (rif === 'DETECTED') {
    document.getElementById('pcr-tb-class').value = 'RR_TB';
    document.getElementById('pcr-critical').checked = true;
  }
}

// ── GeneXpert / TB PCR ────────────────────────────────────────────────────────
async function loadGeneXpert() {
  const result   = document.getElementById('gx-filter-result')?.value  || '';
  const rif      = document.getElementById('gx-filter-rif')?.value     || '';
  const tbClass  = document.getElementById('gx-filter-class')?.value   || '';
  const date     = document.getElementById('gx-filter-date')?.value    || '';
  const params   = new URLSearchParams({ category: 'TB' });
  if (result)   params.set('result',    result);
  if (date)     params.set('date',      date);

  const tbody = document.getElementById('gx-tbody');
  tbody.innerHTML = '<tr><td colspan="11" class="empty-state">Loading…</td></tr>';
  try {
    let data = await apiFetch(`${API}/pcr?${params}`);
    if (rif)     data = data.filter(r => r.rifampicin_resistance === rif);
    if (tbClass) data = data.filter(r => r.tb_classification === tbClass);

    // MDR/XDR alert strip
    const mdrXdr = data.filter(r => ['MDR_TB','XDR_TB','PRE_XDR_TB'].includes(r.tb_classification));
    const strip  = document.getElementById('tb-alert-strip');
    const alertList = document.getElementById('tb-alert-list');
    if (mdrXdr.length) {
      strip.style.display = '';
      alertList.innerHTML = mdrXdr.map(r => `
        <div class="tb-alert-item">
          <strong>${r.pcr_id}</strong> — ${r.pid||'—'} —
          <span class="tb-${r.tb_classification}">${r.tb_classification.replace(/_/g,' ')}</span>
        </div>`).join('');
    } else { strip.style.display = 'none'; }

    if (!data.length) { tbody.innerHTML = '<tr><td colspan="11" class="empty-state">No GeneXpert results found.</td></tr>'; return; }
    tbody.innerHTML = data.map(r => `<tr>
      <td><strong>${r.pcr_id}</strong></td>
      <td>${r.pid||'—'}<br><small>${r.lid||''}</small></td>
      <td>${r.test_name}</td>
      <td>${r.instrument||'—'}</td>
      <td><span class="pcr-${r.result}">${r.result.replace('_',' ')}</span></td>
      <td>${r.semi_quant ? semiQuantBadge(r.semi_quant) : '—'}</td>
      <td>${rifBadge(r.rifampicin_resistance)}</td>
      <td>${r.tb_classification ? `<span class="tb-${r.tb_classification}">${r.tb_classification.replace(/_/g,' ')}</span>` : '—'}</td>
      <td>${r.ct_value ? r.ct_value.toFixed(2) : '—'}</td>
      <td><span class="status-badge status-${r.status}">${r.status}</span></td>
      <td>
        ${!r.is_validated ? `<button class="btn-primary btn-sm" onclick="openMolValidate('pcr',${r.id},'${r.pcr_id}')">Validate</button>` : '<span style="color:#28a745">✔</span>'}
        ${r.is_critical && !r.is_validated ? `<button class="btn-danger btn-sm" onclick="openMolArchive('PCR',${r.id},${r.patient_id},'${r.pid||''}','${r.lid||''}','${r.test_name}')">Archive 🔐</button>` : ''}
      </td>
    </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

function semiQuantBadge(sq) {
  const colors = { VERY_LOW:'#cce5ff', LOW:'#d4edda', MEDIUM:'#fff3cd', HIGH:'#f8d7da' };
  return `<span style="background:${colors[sq]||'#e2e3e5'};padding:.2rem .45rem;border-radius:8px;font-size:.78rem">${sq.replace('_',' ')}</span>`;
}

function rifBadge(rif) {
  if (!rif) return '—';
  const cls = `rif-${rif}`;
  const icon = rif==='DETECTED' ? '⚠️' : rif==='NOT_DETECTED' ? '✅' : '❓';
  return `<span class="${cls}">${icon} ${rif.replace('_',' ')}</span>`;
}

// ── Viral PCR ─────────────────────────────────────────────────────────────────
async function loadViralPCR() {
  const cat    = document.getElementById('vpcr-filter-cat')?.value     || '';
  const result = document.getElementById('vpcr-filter-result')?.value  || '';
  const date   = document.getElementById('vpcr-filter-date')?.value    || '';
  const params = new URLSearchParams();
  if (cat && cat !== 'TB') params.set('category', cat);
  if (result)  params.set('result', result);
  if (date)    params.set('date',   date);

  const tbody = document.getElementById('vpcr-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading…</td></tr>';
  try {
    const data = (await apiFetch(`${API}/pcr?${params}`)).filter(r => r.pcr_category !== 'TB');
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No viral PCR results found.</td></tr>'; return; }
    tbody.innerHTML = data.map(r => `<tr>
      <td><strong>${r.pcr_id}</strong></td>
      <td>${r.pid||'—'}<br><small>${r.lid||''}</small></td>
      <td><span class="cat-badge cat-${r.pcr_category}">${r.pcr_category}</span></td>
      <td>${r.test_name}</td>
      <td>${r.target_organism||'—'}</td>
      <td><span class="pcr-${r.result}">${r.result.replace('_',' ')}</span></td>
      <td>${r.ct_value ? r.ct_value.toFixed(2) : '—'}</td>
      <td>${r.instrument||'—'}</td>
      <td><span class="status-badge status-${r.status}">${r.status}</span></td>
      <td>
        ${!r.is_validated ? `<button class="btn-primary btn-sm" onclick="openMolValidate('pcr',${r.id},'${r.pcr_id}')">Validate</button>` : '<span style="color:#28a745">✔</span>'}
        ${r.is_critical ? `<button class="btn-danger btn-sm" onclick="openMolArchive('PCR',${r.id},${r.patient_id},'${r.pid||''}','${r.lid||''}','${r.test_name}')">Archive 🔐</button>` : ''}
      </td>
    </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

// ── PCR Modal ─────────────────────────────────────────────────────────────────
function openPCRModal(category = 'TB') {
  _pcrCategory = category;
  document.getElementById('pcr-category').value = category;
  document.getElementById('pcr-modal-title').textContent =
    category === 'TB' ? '🦠 New GeneXpert / TB PCR' : '🔬 New Viral / STI PCR';
  pcrCategoryChanged();
  showModal('pcr-modal');
}

async function submitPCR() {
  try {
    const body = {
      lab_request_id:       +document.getElementById('pcr-labreq').value,
      patient_id:           +document.getElementById('pcr-patient').value,
      pid:                  document.getElementById('pcr-pid').value  || null,
      lid:                  document.getElementById('pcr-lid').value  || null,
      pcr_category:         document.getElementById('pcr-category').value,
      test_name:            document.getElementById('pcr-test-name').value,
      target_organism:      document.getElementById('pcr-target').value || null,
      instrument:           document.getElementById('pcr-instrument').value || null,
      specimen_type:        document.getElementById('pcr-specimen').value,
      specimen_quality:     document.getElementById('pcr-spec-quality').value,
      result:               document.getElementById('pcr-result').value,
      ct_value:             parseFloat(document.getElementById('pcr-ct').value) || null,
      semi_quant:           document.getElementById('pcr-semi')?.value || null,
      rifampicin_resistance: document.getElementById('pcr-rif')?.value || null,
      tb_classification:    document.getElementById('pcr-tb-class')?.value || null,
      is_critical:          document.getElementById('pcr-critical').checked,
      notes:                document.getElementById('pcr-notes').value || null,
    };
    await apiFetch(`${API}/pcr`, { method:'POST', body: JSON.stringify(body) });
    closeModal('pcr-modal');
    toast('PCR result saved.');
    loadDashboard();
    if (_pcrCategory === 'TB') loadGeneXpert(); else loadViralPCR();
  } catch(e) { toast(e.message, 'error'); }
}

// ── Viral Load ────────────────────────────────────────────────────────────────
async function loadViralLoad() {
  const virus = document.getElementById('vl-filter-virus')?.value || '';
  const val   = document.getElementById('vl-filter-val')?.value   || '';
  const date  = document.getElementById('vl-filter-date')?.value  || '';
  const params = new URLSearchParams();
  if (virus) params.set('virus', virus);
  if (val)   params.set('validated', val);
  if (date)  params.set('date', date);

  const tbody = document.getElementById('vl-tbody');
  tbody.innerHTML = '<tr><td colspan="12" class="empty-state">Loading…</td></tr>';
  try {
    const data = await apiFetch(`${API}/viral-load?${params}`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="12" class="empty-state">No viral load results.</td></tr>'; return; }
    tbody.innerHTML = data.map(r => {
      const copies = r.copies_per_ml ? formatCopies(r.copies_per_ml) : '—';
      const log10  = r.log10_value   ? r.log10_value.toFixed(2)       : '—';
      return `<tr>
        <td><strong>${r.vl_id}</strong></td>
        <td>${r.pid||'—'}<br><small>${r.lid||''}</small></td>
        <td><span class="virus-badge virus-${r.virus}">${r.virus}</span></td>
        <td>${r.assay_name||'—'}</td>
        <td>${copies}</td>
        <td>${log10}</td>
        <td>${r.vl_category ? `<span class="vl-${r.vl_category}">${r.vl_category.replace(/_/g,' ')}</span>` : '—'}</td>
        <td>${r.on_art ? `✅ ART<br><small>${r.art_regimen||''}</small>` : '—'}</td>
        <td>${r.vl_trend ? `<span class="trend-${r.vl_trend}">${trendIcon(r.vl_trend)} ${r.vl_trend}</span>` : '—'}</td>
        <td>${r.specimen_type||'—'}</td>
        <td><span class="status-badge status-${r.status}">${r.status}</span></td>
        <td>
          ${!r.is_validated ? `<button class="btn-primary btn-sm" onclick="openMolValidate('viral-load',${r.id},'${r.vl_id}')">Validate</button>` : '<span style="color:#28a745">✔</span>'}
          ${r.is_critical ? `<button class="btn-danger btn-sm" onclick="openMolArchive('VIRAL_LOAD',${r.id},${r.patient_id},'${r.pid||''}','${r.lid||''}','${r.virus} VL')">Archive 🔐</button>` : ''}
        </td>
      </tr>`;
    }).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="12" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

function formatCopies(n) {
  if (n >= 1000000) return `${(n/1000000).toFixed(2)}M`;
  if (n >= 1000)    return `${(n/1000).toFixed(1)}K`;
  return n.toLocaleString();
}

function trendIcon(t) {
  return { DECLINING:'📉', STABLE:'➡️', RISING:'📈', REBOUNDING:'🔴' }[t] || '';
}

function openVLModal() { showModal('vl-modal'); }

async function submitVL() {
  try {
    const copies = parseFloat(document.getElementById('vl-copies').value) || null;
    let log10    = parseFloat(document.getElementById('vl-log').value)    || null;
    if (copies && !log10) log10 = +(Math.log10(copies)).toFixed(2);

    const body = {
      lab_request_id: +document.getElementById('vl-labreq').value,
      patient_id:     +document.getElementById('vl-patient').value,
      pid:            document.getElementById('vl-pid').value   || null,
      lid:            document.getElementById('vl-lid').value   || null,
      virus:          document.getElementById('vl-virus').value,
      assay_name:     document.getElementById('vl-assay').value || null,
      instrument:     document.getElementById('vl-instrument').value || null,
      specimen_type:  document.getElementById('vl-specimen').value,
      copies_per_ml:  copies,
      iu_per_ml:      parseFloat(document.getElementById('vl-iu').value) || null,
      log10_value:    log10,
      lower_limit_detection: parseFloat(document.getElementById('vl-lld').value) || null,
      vl_category:    document.getElementById('vl-category').value || null,
      on_art:         document.getElementById('vl-on-art').checked,
      art_regimen:    document.getElementById('vl-regimen').value || null,
      art_months:     +document.getElementById('vl-art-months').value || null,
      previous_vl:    parseFloat(document.getElementById('vl-prev').value) || null,
      vl_trend:       document.getElementById('vl-trend').value || null,
      is_critical:    document.getElementById('vl-critical').checked,
      notes:          document.getElementById('vl-notes').value || null,
    };
    await apiFetch(`${API}/viral-load`, { method:'POST', body: JSON.stringify(body) });
    closeModal('vl-modal');
    toast('Viral load result saved.');
    loadViralLoad();
    loadDashboard();
  } catch(e) { toast(e.message, 'error'); }
}

// ── Genetic Analysis ──────────────────────────────────────────────────────────
async function loadGenetic() {
  const type = document.getElementById('ga-filter-type')?.value || '';
  const params = new URLSearchParams();
  if (type) params.set('analysis_type', type);

  const tbody = document.getElementById('ga-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Loading…</td></tr>';
  try {
    const data = await apiFetch(`${API}/genetic?${params}`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No genetic analyses.</td></tr>'; return; }
    tbody.innerHTML = data.map(r => `<tr>
      <td><strong>${r.ga_id}</strong></td>
      <td>${r.pid||'—'}<br><small>${r.lid||''}</small></td>
      <td>${r.analysis_type.replace(/_/g,' ')}</td>
      <td>${r.gene_target||'—'}</td>
      <td>${r.mutation_detected ? `<code style="font-size:.78rem">${r.mutation_detected}</code>` : '—'}</td>
      <td>${r.pathogenicity ? `<span class="path-${r.pathogenicity}">${r.pathogenicity.replace(/_/g,' ')}</span>` : '—'}</td>
      <td>${r.method||'—'}</td>
      <td><span class="status-badge status-${r.status}">${r.status}</span></td>
      <td>
        ${!r.is_validated ? `<button class="btn-primary btn-sm" onclick="openMolValidate('genetic',${r.id},'${r.ga_id}')">Validate</button>` : '<span style="color:#28a745">✔</span>'}
      </td>
    </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

function openGAModal() { showModal('ga-modal'); }

async function submitGA() {
  try {
    const body = {
      lab_request_id:       +document.getElementById('ga-labreq').value,
      patient_id:           +document.getElementById('ga-patient').value,
      pid:                  document.getElementById('ga-pid').value  || null,
      lid:                  document.getElementById('ga-lid').value  || null,
      analysis_type:        document.getElementById('ga-type').value,
      gene_target:          document.getElementById('ga-gene').value || null,
      mutation_detected:    document.getElementById('ga-mutation').value || null,
      mutation_type:        document.getElementById('ga-mut-type').value || null,
      pathogenicity:        document.getElementById('ga-path').value || null,
      clinical_significance:document.getElementById('ga-significance').value || null,
      method:               document.getElementById('ga-method').value || null,
      result_summary:       document.getElementById('ga-summary').value || null,
      notes:                document.getElementById('ga-notes').value || null,
    };
    await apiFetch(`${API}/genetic`, { method:'POST', body: JSON.stringify(body) });
    closeModal('ga-modal');
    toast('Genetic analysis saved.');
    loadGenetic();
  } catch(e) { toast(e.message, 'error'); }
}

// ── Validation ────────────────────────────────────────────────────────────────
async function loadMolValidation() {
  const type = document.getElementById('molval-filter-type')?.value || 'pcr';
  const list = document.getElementById('molval-list');
  list.innerHTML = '<div class="empty-state">Loading…</div>';
  try {
    const endpoint = type === 'pcr' ? `${API}/pcr?validated=false` : `${API}/viral-load?validated=false`;
    const data = await apiFetch(endpoint);
    const pending = data.filter(x => !x.is_validated);
    setText('molval-count', `${pending.length} awaiting validation`);
    if (!pending.length) { list.innerHTML = '<div class="empty-state">No results awaiting validation.</div>'; return; }
    list.innerHTML = pending.map(item => {
      const id     = type === 'pcr' ? item.pcr_id : item.vl_id;
      const label  = type === 'pcr' ? `${item.test_name} — ${item.result}` : `${item.virus} VL — ${item.vl_category||'—'}`;
      return `<div class="val-card">
        <div class="val-card-body">
          <div class="val-card-id">${id}</div>
          <div class="val-card-sub">${label}</div>
          <div class="val-card-sub">PID: ${item.pid||'—'} · LID: ${item.lid||'—'}</div>
          <div class="val-card-actions">
            <button class="btn-primary btn-sm" onclick="openMolValidate('${type}',${item.id},'${id}')">Validate</button>
          </div>
        </div>
        ${item.is_critical ? '<span class="stat-chip danger" style="align-self:center">🚨 Critical</span>' : ''}
      </div>`;
    }).join('');
  } catch(e) {
    list.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
  }
}

function openMolValidate(type, id, label) {
  _molValidateCtx = { type, id, label };
  document.getElementById('mol-validate-summary').innerHTML =
    `<p>Validating <strong>${label}</strong> (${type})</p>`;
  showModal('validate-modal');
}

async function confirmMolValidate() {
  if (!_molValidateCtx) return;
  const { type, id } = _molValidateCtx;
  const endpoints = {
    pcr: `${API}/pcr/${id}/validate`,
    'viral-load': `${API}/viral-load/${id}/validate`,
  };
  const endpoint = endpoints[type] || `${API}/pcr/${id}/validate`;
  try {
    await apiFetch(endpoint, { method:'POST' });
    closeModal('validate-modal');
    toast('Result validated.');
    loadDashboard();
    loadMolValidation();
    _molValidateCtx = null;
  } catch(e) { toast(e.message, 'error'); }
}

// ── Critical Book ─────────────────────────────────────────────────────────────
async function loadMolBook() {
  const reason = document.getElementById('molbook-filter-reason')?.value || '';
  const params = new URLSearchParams();
  if (reason) params.set('critical_reason', reason);

  const tbody = document.getElementById('molbook-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading…</td></tr>';
  try {
    const data = await apiFetch(`${API}/critical-book?${params}`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No critical book entries.</td></tr>'; return; }
    tbody.innerHTML = data.map(e => `<tr>
      <td><strong>${e.entry_number}</strong></td>
      <td>${e.pid||'—'}<br><small>${e.lid||''}</small></td>
      <td>${e.test_name||'—'}</td>
      <td><span class="tb-${e.critical_reason.replace(/_/g,'_')}">${e.critical_reason.replace(/_/g,' ')}</span></td>
      <td>${e.severity}</td>
      <td>${e.clinician_notified||'—'}<br><small>${e.notification_method||''}</small></td>
      <td>${e.readback_confirmed ? '✅ Yes' : '⚠️ No'}</td>
      <td>${e.public_health_notified ? '✅ Notified' : '—'}</td>
      <td>${new Date(e.archived_at).toLocaleString()}</td>
      <td><span class="pqc-hash" title="${e.pqc_hash||''}">${(e.pqc_hash||'').substring(0,30)}…</span></td>
    </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

function openMolArchive(type, id, patient_id, pid, lid, testName) {
  _molArchiveCtx = { type, id, patient_id, pid, lid, testName };
  showModal('archive-modal');
}

async function confirmMolArchive() {
  if (!_molArchiveCtx) return;
  const reason = document.getElementById('molarch-reason').value;
  const body = {
    lab_request_id:          0,
    patient_id:              _molArchiveCtx.patient_id,
    pid:                     _molArchiveCtx.pid  || null,
    lid:                     _molArchiveCtx.lid  || null,
    result_type:             _molArchiveCtx.type,
    result_ref_id:           _molArchiveCtx.id,
    test_name:               _molArchiveCtx.testName || null,
    critical_reason:         reason,
    severity:                'CRITICAL',
    clinician_notified:      document.getElementById('molarch-clinician').value || null,
    notification_method:     document.getElementById('molarch-method').value,
    readback_confirmed:      document.getElementById('molarch-readback').checked,
    public_health_notified:  document.getElementById('molarch-pubhealth').checked,
  };
  try {
    await apiFetch(`${API}/critical-book`, { method:'POST', body: JSON.stringify(body) });
    closeModal('archive-modal');
    toast('Archived to TB Critical Book with PQC signature.');
    loadMolBook();
    loadDashboard();
    _molArchiveCtx = null;
  } catch(e) { toast(e.message, 'error'); }
}

// ── Modal utils ───────────────────────────────────────────────────────────────
function showModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

document.querySelectorAll('.modal-overlay').forEach(o => {
  o.addEventListener('click', e => { if (e.target === o) o.style.display = 'none'; });
});

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  pcrCategoryChanged();
  setInterval(loadDashboard, 60000);
});
