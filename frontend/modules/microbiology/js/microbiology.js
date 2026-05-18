/* Microbiology Module — NEXUS ALIS-X */
'use strict';

const API = '/api/v1/microbiology';
let _currentCultureId = null;
let _validateCtx      = null;  // {type, id, label}
let _archiveCtx       = null;  // {type, id, patient_id, pid, lid, organism}

// ── Auth header ──────────────────────────────────────────────────────────────
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

// ── Tab switching ────────────────────────────────────────────────────────────
function switchTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  const btn  = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
  const pane = document.getElementById(`tab-${tabName}`);
  if (btn)  btn.classList.add('active');
  if (pane) pane.classList.add('active');
  if (tabName === 'bacteriology') loadCultures();
  if (tabName === 'antibiogram')  loadMDRList();
  if (tabName === 'parasitology') loadParasitology();
  if (tabName === 'validation')   loadValidationQueue();
  if (tabName === 'book')         loadCriticalBook();
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

// ── Dashboard ────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const d = await apiFetch(`${API}/dashboard`);
    setText('kpi-pending',    d.cultures_pending);
    setText('kpi-today',      d.cultures_today);
    setText('kpi-critical',   d.critical_cultures);
    setText('kpi-mrsa',       d.mrsa_count);
    setText('kpi-esbl',       d.esbl_count);
    setText('kpi-para-pending',d.parasitology_pending);
    setText('kpi-malaria',    d.malaria_positive_today);
    setText('kpi-book',       d.critical_book_total);
    setText('stat-pending',   d.cultures_pending);
    setText('stat-critical',  d.critical_cultures);
    const mdr = d.mrsa_count + d.esbl_count;
    setText('stat-mdr', mdr);
    setText('sq-bacteriology', `${d.cultures_pending} pending`);
    setText('sq-parasitology', `${d.parasitology_pending} pending`);
    setText('sq-mdr', `${mdr} active`);
  } catch(e) { console.error('Dashboard load failed', e); }
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? '—';
}

// ── Cultures ─────────────────────────────────────────────────────────────────
async function loadCultures() {
  const status   = document.getElementById('bact-filter-status')?.value   || '';
  const specimen = document.getElementById('bact-filter-specimen')?.value  || '';
  const mdr      = document.getElementById('bact-filter-mdr')?.value       || '';
  const date     = document.getElementById('bact-filter-date')?.value       || '';
  const params   = new URLSearchParams();
  if (status)   params.set('status',        status);
  if (specimen) params.set('specimen_type', specimen);
  if (mdr)      params.set('mdr_flag',      mdr);
  if (date)     params.set('date',          date);

  const tbody = document.getElementById('cultures-tbody');
  tbody.innerHTML = '<tr><td colspan="9" class="empty-state">Loading…</td></tr>';
  try {
    const data = await apiFetch(`${API}/cultures?${params}`);
    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No cultures found.</td></tr>';
      return;
    }
    tbody.innerHTML = data.map(c => `
      <tr>
        <td><strong>${c.culture_id}</strong></td>
        <td>${c.pid || '—'}<br><small>${c.lid || ''}</small></td>
        <td>${specimenBadge(c.specimen_type)}</td>
        <td>${gramBadge(c)}</td>
        <td>${growthBadge(c.growth_status)}</td>
        <td>${c.organism_identified ? `<strong>${c.organism_identified}</strong>` : '<em class="text-muted">Pending</em>'}</td>
        <td>${mdrFlags(c)}</td>
        <td>${statusBadge(c.status)}</td>
        <td>
          <button class="btn-secondary btn-sm" onclick="openGrowthModal(${c.id})">Update</button>
          ${!c.is_validated ? `<button class="btn-primary btn-sm" onclick="openValidate('culture',${c.id},'${c.culture_id}')">Validate</button>` : ''}
          <button class="btn-secondary btn-sm" onclick="loadAntibiogram(${c.id},'${c.culture_id}','${c.organism_identified||''}')">ABG</button>
          ${c.is_critical && !c.is_validated ? `<button class="btn-danger btn-sm" onclick="openArchive('culture',${c.id},${c.patient_id},'${c.pid||''}','${c.lid||''}','${c.organism_identified||''}')">Archive 🔐</button>` : ''}
        </td>
      </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

function specimenBadge(s) {
  const icons = {blood:'🩸',urine:'🟡',stool:'🟤',sputum:'💨',wound:'🩹',csf:'💧',throat:'🔴',ear:'👂',eye:'👁'};
  return `<span title="${s}">${icons[s]||'🧫'} ${s}</span>`;
}

function gramBadge(c) {
  if (!c.gram_stain_done) return '<span style="color:#aaa">Not done</span>';
  const positive = c.gram_stain_morphology?.includes('positive');
  return `<span class="gram-${positive?'pos':'neg'}">${c.gram_stain_result || c.gram_stain_morphology || 'Done'}</span>`;
}

function growthBadge(g) {
  return `<span class="growth-badge growth-${g}">${g.replace('_',' ')}</span>`;
}

function mdrFlags(c) {
  let out = '';
  if (c.is_mrsa) out += '<span class="mdr-flag mdr-MRSA">MRSA</span>';
  if (c.is_esbl) out += '<span class="mdr-flag mdr-ESBL">ESBL</span>';
  if (c.is_cro)  out += '<span class="mdr-flag mdr-CRO">CRO</span>';
  if (c.is_vrsa) out += '<span class="mdr-flag mdr-VRSA">VRSA</span>';
  return out || '—';
}

function statusBadge(s) {
  return `<span class="status-badge status-${s}">${s.replace('_',' ')}</span>`;
}

// ── Culture modal ─────────────────────────────────────────────────────────────
function openCultureModal() { showModal('culture-modal'); }

function gramToggle() {
  const done = document.getElementById('cmod-gram-done').value === 'true';
  document.getElementById('gram-result-row').style.display = done ? '' : 'none';
  document.getElementById('gram-morph-row').style.display  = done ? '' : 'none';
}

async function submitCulture() {
  try {
    const body = {
      lab_request_id: +document.getElementById('cmod-labreq').value,
      patient_id:     +document.getElementById('cmod-patient').value,
      pid:            document.getElementById('cmod-pid').value || null,
      lid:            document.getElementById('cmod-lid').value || null,
      specimen_type:  document.getElementById('cmod-specimen').value,
      specimen_notes: document.getElementById('cmod-spec-notes').value || null,
      gram_stain_done: document.getElementById('cmod-gram-done').value === 'true',
      gram_stain_result: document.getElementById('cmod-gram-result').value || null,
      gram_stain_morphology: document.getElementById('cmod-gram-morph').value || null,
      notes: document.getElementById('cmod-notes').value || null,
    };
    await apiFetch(`${API}/cultures`, { method:'POST', body: JSON.stringify(body) });
    closeModal('culture-modal');
    toast('Culture submitted successfully.');
    loadCultures();
    loadDashboard();
  } catch(e) { toast(e.message, 'error'); }
}

// ── Growth update modal ───────────────────────────────────────────────────────
let _growthCultureId = null;

async function openGrowthModal(cultureId) {
  _growthCultureId = cultureId;
  try {
    const c = await apiFetch(`${API}/cultures/${cultureId}`);
    document.getElementById('gmod-growth').value     = c.growth_status  || 'PENDING';
    document.getElementById('gmod-days').value       = c.growth_days    || '';
    document.getElementById('gmod-colony').value     = c.colony_morphology || '';
    document.getElementById('gmod-organism').value   = c.organism_identified || '';
    document.getElementById('gmod-count').value      = c.organism_count || '';
    document.getElementById('gmod-id-method').value  = c.identification_method || '';
    document.getElementById('gmod-mrsa').checked     = c.is_mrsa;
    document.getElementById('gmod-esbl').checked     = c.is_esbl;
    document.getElementById('gmod-cro').checked      = c.is_cro;
    document.getElementById('gmod-vrsa').checked     = c.is_vrsa ?? false;
    document.getElementById('gmod-mdr-note').value   = c.mdr_note || '';
    document.getElementById('gmod-status').value     = c.status   || 'IN_PROGRESS';
    document.getElementById('gmod-critical').checked = c.is_critical;
    showModal('growth-modal');
  } catch(e) { toast(e.message, 'error'); }
}

async function submitGrowth() {
  if (!_growthCultureId) return;
  const body = {
    growth_status:      document.getElementById('gmod-growth').value,
    growth_days:        +document.getElementById('gmod-days').value || null,
    colony_morphology:  document.getElementById('gmod-colony').value || null,
    organism_identified:document.getElementById('gmod-organism').value || null,
    organism_count:     document.getElementById('gmod-count').value || null,
    identification_method: document.getElementById('gmod-id-method').value || null,
    is_mrsa:  document.getElementById('gmod-mrsa').checked,
    is_esbl:  document.getElementById('gmod-esbl').checked,
    is_cro:   document.getElementById('gmod-cro').checked,
    is_vrsa:  document.getElementById('gmod-vrsa').checked,
    mdr_note: document.getElementById('gmod-mdr-note').value || null,
    status:   document.getElementById('gmod-status').value,
    is_critical: document.getElementById('gmod-critical').checked,
  };
  try {
    await apiFetch(`${API}/cultures/${_growthCultureId}`, { method:'PATCH', body: JSON.stringify(body) });
    closeModal('growth-modal');
    toast('Culture updated.');
    loadCultures();
    loadDashboard();
  } catch(e) { toast(e.message, 'error'); }
}

// ── Antibiogram ───────────────────────────────────────────────────────────────
async function loadMDRList() {
  const mdr = document.getElementById('abg-filter-mdr')?.value || '';
  const params = new URLSearchParams();
  if (mdr) params.set('mdr_flag', mdr);
  params.set('status', 'FINAL,VALIDATED');
  try {
    const data = await apiFetch(`${API}/cultures?${params}`);
    const list = document.getElementById('mdr-list');
    const mdrs = data.filter(c => c.is_mrsa || c.is_esbl || c.is_cro);
    if (!mdrs.length) { list.innerHTML = '<em style="color:#856404">No MDR organisms currently flagged.</em>'; return; }
    list.innerHTML = mdrs.map(c => `
      <div class="mdr-item" onclick="loadAntibiogram(${c.id},'${c.culture_id}','${c.organism_identified||''}')">
        <div class="mdr-item-id">${c.culture_id}</div>
        <div class="mdr-item-org">${c.organism_identified||'Unknown organism'} ${mdrFlags(c)}</div>
      </div>`).join('');
  } catch(e) { console.error(e); }
}

async function loadAntibiogram(cultureId, cultureRef, organism) {
  _currentCultureId = cultureId;
  document.getElementById('abg-culture-id').textContent = cultureRef;
  document.getElementById('abg-organism').textContent   = organism || 'Organism pending identification';
  document.getElementById('abg-panel').style.display    = '';
  switchTab('antibiogram');

  const tbody = document.getElementById('abg-tbody');
  tbody.innerHTML = '<tr><td colspan="8">Loading…</td></tr>';
  try {
    const data = await apiFetch(`${API}/cultures/${cultureId}/antibiogram`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No antibiogram data. Add entries below.</td></tr>'; return; }
    // Group by drug class
    const byClass = {};
    data.forEach(e => {
      const cls = e.drug_class || 'Other';
      (byClass[cls] = byClass[cls] || []).push(e);
    });
    tbody.innerHTML = Object.entries(byClass).map(([cls, entries]) =>
      entries.map((e, i) => `<tr>
        ${i === 0 ? `<td rowspan="${entries.length}" style="font-weight:600;background:#f8f9fa">${cls}</td>` : ''}
        <td>${e.antibiotic}</td>
        <td class="sir-col S">${e.interpretation==='S'?'<span class="sir-dot dot-S"></span>S':''}</td>
        <td class="sir-col I">${e.interpretation==='I'?'<span class="sir-dot dot-I"></span>I':''}</td>
        <td class="sir-col R">${e.interpretation==='R'?'<span class="sir-dot dot-R"></span>R':''}</td>
        <td>${e.mic_value ? `${e.mic_value} ${e.mic_unit||''}` : '—'}</td>
        <td>${e.disk_zone_mm || '—'}</td>
        <td>${e.method || '—'}</td>
      </tr>`).join('')
    ).join('');
  } catch(e) { tbody.innerHTML = `<tr><td colspan="8" class="empty-state">Error: ${e.message}</td></tr>`; }
}

function closeABG() {
  document.getElementById('abg-panel').style.display = 'none';
  _currentCultureId = null;
}

function openAddABGModal() {
  document.getElementById('abg-entries').innerHTML = '';
  addABGRow();
  showModal('abg-modal');
}

function addABGRow() {
  const row = document.createElement('div');
  row.className = 'abg-entry-row';
  row.innerHTML = `
    <input type="text" placeholder="Antibiotic name" class="abg-drug">
    <select class="abg-sir">
      <option value="S">S — Sensitive</option>
      <option value="I">I — Intermediate</option>
      <option value="R">R — Resistant</option>
    </select>
    <input type="text" placeholder="MIC (e.g. 0.5 mg/L)" class="abg-mic">
    <input type="text" placeholder="Drug class" class="abg-class">`;
  document.getElementById('abg-entries').appendChild(row);
}

async function submitABG() {
  if (!_currentCultureId) return;
  const rows = document.querySelectorAll('#abg-entries .abg-entry-row');
  const entries = Array.from(rows).map(r => ({
    antibiotic:     r.querySelector('.abg-drug').value.trim(),
    interpretation: r.querySelector('.abg-sir').value,
    mic_value:      parseFloat(r.querySelector('.abg-mic').value) || null,
    drug_class:     r.querySelector('.abg-class').value.trim() || null,
  })).filter(e => e.antibiotic);

  if (!entries.length) { toast('Add at least one antibiotic entry.', 'error'); return; }
  try {
    await apiFetch(`${API}/cultures/${_currentCultureId}/antibiogram`, { method:'POST', body: JSON.stringify(entries) });
    closeModal('abg-modal');
    toast('Antibiogram saved.');
    loadAntibiogram(_currentCultureId,
      document.getElementById('abg-culture-id').textContent,
      document.getElementById('abg-organism').textContent);
  } catch(e) { toast(e.message, 'error'); }
}

// ── Parasitology ──────────────────────────────────────────────────────────────
const BLOOD_PARASITES = [
  'Plasmodium falciparum', 'Plasmodium vivax', 'Plasmodium malariae', 'Plasmodium ovale',
  'Trypanosoma brucei', 'Trypanosoma cruzi', 'Microfilaria (Wuchereria bancrofti)',
  'Microfilaria (Mansonella)', 'Babesia spp.',
];
const INTESTINAL_PARASITES = [
  'Giardia lamblia', 'Entamoeba histolytica', 'Ascaris lumbricoides',
  'Hookworm (Necator americanus)', 'Hookworm (Ancylostoma duodenale)',
  'Taenia saginata', 'Taenia solium', 'Strongyloides stercoralis',
  'Trichuris trichiura', 'Schistosoma mansoni', 'Cryptosporidium parvum',
];

function updateParasiteList() {
  const cat  = document.getElementById('pmod-category').value;
  const sel  = document.getElementById('pmod-parasite-select');
  const list = cat === 'BLOOD' ? BLOOD_PARASITES : cat === 'STOOL' ? INTESTINAL_PARASITES : [];
  sel.innerHTML = '<option value="">Select common parasite…</option>' +
    list.map(p => `<option value="${p}">${p}</option>`).join('');
}

function fillParasiteName() {
  const v = document.getElementById('pmod-parasite-select').value;
  if (v) document.getElementById('pmod-parasite-name').value = v;
}

function rdtToggle() {
  const done = document.getElementById('pmod-rdt-done').value === 'true';
  document.getElementById('rdt-result-row').style.display = done ? '' : 'none';
  document.getElementById('rdt-brand-row').style.display  = done ? '' : 'none';
}

function openParaModal() {
  updateParasiteList();
  showModal('para-modal');
}

async function loadParasitology() {
  const cat    = document.getElementById('para-filter-category')?.value || '';
  const result = document.getElementById('para-filter-result')?.value   || '';
  const date   = document.getElementById('para-filter-date')?.value      || '';
  const params = new URLSearchParams();
  if (cat)    params.set('category', cat);
  if (result) params.set('result',   result);
  if (date)   params.set('date',     date);

  const tbody = document.getElementById('para-tbody');
  tbody.innerHTML = '<tr><td colspan="11" class="empty-state">Loading…</td></tr>';
  try {
    const data = await apiFetch(`${API}/parasitology?${params}`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="11" class="empty-state">No parasitology results.</td></tr>'; return; }
    tbody.innerHTML = data.map(p => {
      const malaria = p.parasite_name?.toLowerCase().includes('plasmodium');
      const resultCls = `para-${p.result}${malaria && p.result==='POSITIVE' ? ' malaria' : ''}`;
      return `<tr>
        <td><strong>${p.para_id}</strong></td>
        <td>${p.pid||'—'}<br><small>${p.lid||''}</small></td>
        <td><span class="category-tag">${p.category}</span></td>
        <td>${p.specimen_type}</td>
        <td>${p.parasite_name ? `<strong>${p.parasite_name}</strong>${p.parasite_species?`<br><small>${p.parasite_species}</small>`:''}` : '<em>Pending</em>'}</td>
        <td><span class="${resultCls}">${p.result}</span></td>
        <td>${p.quantity || (p.parasitemia_pct ? `${p.parasitemia_pct}%` : '—')}</td>
        <td>${p.staining_technique || '—'}</td>
        <td>${p.rdt_done ? `<span class="para-${p.rdt_result||'PENDING'}">${p.rdt_result||'Done'}</span>` : '—'}</td>
        <td>${statusBadge(p.status)}</td>
        <td>
          ${!p.is_validated ? `<button class="btn-primary btn-sm" onclick="openValidate('parasitology',${p.id},'${p.para_id}')">Validate</button>` : '<span style="color:#28a745">✔ Validated</span>'}
          ${p.is_critical && !p.is_validated ? `<button class="btn-danger btn-sm" onclick="openArchive('parasitology',${p.id},${p.patient_id},'${p.pid||''}','${p.lid||''}','${p.parasite_name||''}')">Archive 🔐</button>` : ''}
        </td>
      </tr>`;
    }).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

async function submitParasitology() {
  try {
    const body = {
      lab_request_id: +document.getElementById('pmod-labreq').value,
      patient_id:     +document.getElementById('pmod-patient').value,
      pid:            document.getElementById('pmod-pid').value || null,
      lid:            document.getElementById('pmod-lid').value || null,
      category:       document.getElementById('pmod-category').value,
      specimen_type:  document.getElementById('pmod-specimen').value,
      parasite_name:  document.getElementById('pmod-parasite-name').value || null,
      parasite_species: document.getElementById('pmod-species').value || null,
      result:         document.getElementById('pmod-result').value,
      quantity:       document.getElementById('pmod-quantity').value || null,
      parasitemia_pct: +document.getElementById('pmod-parasitemia').value || null,
      staining_technique: document.getElementById('pmod-staining').value || null,
      preparation:    document.getElementById('pmod-prep').value || null,
      rdt_done:       document.getElementById('pmod-rdt-done').value === 'true',
      rdt_result:     document.getElementById('pmod-rdt-result')?.value || null,
      rdt_brand:      document.getElementById('pmod-rdt-brand')?.value || null,
      is_critical:    document.getElementById('pmod-critical').checked,
      notes:          document.getElementById('pmod-notes').value || null,
    };
    await apiFetch(`${API}/parasitology`, { method:'POST', body: JSON.stringify(body) });
    closeModal('para-modal');
    toast('Parasitology result saved.');
    loadParasitology();
    loadDashboard();
  } catch(e) { toast(e.message, 'error'); }
}

// ── Validation queue ──────────────────────────────────────────────────────────
async function loadValidationQueue() {
  const type = document.getElementById('val-filter-type')?.value || 'cultures';
  const list  = document.getElementById('validation-list');
  list.innerHTML = '<div class="empty-state">Loading…</div>';
  try {
    let data;
    if (type === 'cultures') {
      data = await apiFetch(`${API}/cultures?status=FINAL`);
    } else {
      data = await apiFetch(`${API}/parasitology?validated=false`);
    }
    data = data.filter(x => !x.is_validated);
    setText('val-count', `${data.length} awaiting validation`);
    if (!data.length) { list.innerHTML = '<div class="empty-state">No results awaiting validation.</div>'; return; }
    list.innerHTML = data.map(item => {
      const id      = type === 'cultures' ? item.culture_id : item.para_id;
      const label   = type === 'cultures' ? `Specimen: ${item.specimen_type}` : `Parasite: ${item.parasite_name||'Pending'}`;
      const detail  = type === 'cultures' ? `Organism: ${item.organism_identified||'Not identified'}` : `Result: ${item.result}`;
      return `<div class="val-card">
        <div class="val-card-body">
          <div class="val-card-id">${id}</div>
          <div class="val-card-sub">${label}</div>
          <div class="val-card-sub">${detail} · PID: ${item.pid||'—'} · LID: ${item.lid||'—'}</div>
          <div class="val-card-actions">
            <button class="btn-primary btn-sm" onclick="openValidate('${type.replace('cultures','culture').replace('parasitology','parasitology')}',${item.id},'${id}')">Validate</button>
          </div>
        </div>
        ${item.is_critical ? '<span class="stat-chip critical" style="align-self:center">🚨 Critical</span>' : ''}
      </div>`;
    }).join('');
  } catch(e) {
    list.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
  }
}

function openValidate(type, id, label) {
  _validateCtx = { type, id, label };
  document.getElementById('validate-summary').innerHTML =
    `<p>Validating <strong>${label}</strong> (${type})</p>`;
  showModal('validate-modal');
}

async function confirmValidate() {
  if (!_validateCtx) return;
  const { type, id } = _validateCtx;
  const endpoint = type === 'culture' ? `${API}/cultures/${id}/validate` : `${API}/parasitology/${id}/validate`;
  try {
    await apiFetch(endpoint, { method:'POST' });
    closeModal('validate-modal');
    toast('Result validated successfully.');
    loadDashboard();
    if (type === 'culture') loadCultures();
    else loadParasitology();
    _validateCtx = null;
  } catch(e) { toast(e.message, 'error'); }
}

// ── Critical Book ─────────────────────────────────────────────────────────────
async function loadCriticalBook() {
  const reason = document.getElementById('book-filter-reason')?.value || '';
  const params = new URLSearchParams();
  if (reason) params.set('critical_reason', reason);

  const tbody = document.getElementById('book-tbody');
  tbody.innerHTML = '<tr><td colspan="10" class="empty-state">Loading…</td></tr>';
  try {
    const data = await apiFetch(`${API}/critical-book?${params}`);
    if (!data.length) { tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No critical book entries.</td></tr>'; return; }
    tbody.innerHTML = data.map(e => `<tr>
      <td><strong>${e.entry_number}</strong></td>
      <td>${e.pid||'—'}<br><small>${e.lid||''}</small></td>
      <td>${e.organism||'—'}</td>
      <td><span class="mdr-flag mdr-${e.critical_reason}">${e.critical_reason.replace(/_/g,' ')}</span></td>
      <td><span class="severity-${e.severity}">${e.severity}</span></td>
      <td>${e.clinician_notified||'—'}<br><small>${e.notification_method||''}</small></td>
      <td>${e.readback_confirmed ? '✅ Yes' : '⚠️ No'}</td>
      <td>${e.rbc_notified ? '✅ Yes' : '—'}</td>
      <td>${new Date(e.archived_at).toLocaleString()}</td>
      <td><span class="pqc-hash" title="${e.pqc_hash||''}">${(e.pqc_hash||'').substring(0,30)}…</span></td>
    </tr>`).join('');
  } catch(e) {
    tbody.innerHTML = `<tr><td colspan="10" class="empty-state">Error: ${e.message}</td></tr>`;
  }
}

function openArchive(type, id, patient_id, pid, lid, organism) {
  _archiveCtx = { type, id, patient_id, pid, lid, organism };
  showModal('archive-modal');
}

async function confirmArchive() {
  if (!_archiveCtx) return;
  const reason = document.getElementById('arch-reason').value;
  const body = {
    lab_request_id:      0,
    patient_id:          _archiveCtx.patient_id,
    pid:                 _archiveCtx.pid || null,
    lid:                 _archiveCtx.lid || null,
    result_type:         _archiveCtx.type === 'culture' ? 'CULTURE' : 'PARASITOLOGY',
    result_ref_id:       _archiveCtx.id,
    organism:            _archiveCtx.organism || null,
    critical_reason:     reason,
    severity:            'CRITICAL',
    clinician_notified:  document.getElementById('arch-clinician').value || null,
    notification_method: document.getElementById('arch-method').value,
    readback_confirmed:  document.getElementById('arch-readback').checked,
  };
  try {
    await apiFetch(`${API}/critical-book`, { method:'POST', body: JSON.stringify(body) });
    closeModal('archive-modal');
    toast('Archived to Critical Book with PQC signature.');
    loadCriticalBook();
    loadDashboard();
    _archiveCtx = null;
  } catch(e) { toast(e.message, 'error'); }
}

// ── Modal utils ───────────────────────────────────────────────────────────────
function showModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

// Close modal on overlay click
document.querySelectorAll('.modal-overlay').forEach(o => {
  o.addEventListener('click', e => { if (e.target === o) o.style.display = 'none'; });
});

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  // Auto-refresh dashboard every 60s
  setInterval(loadDashboard, 60000);
});
