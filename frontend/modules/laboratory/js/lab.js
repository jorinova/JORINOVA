/**
 * JORINOVA NEXUS ALIS-X — Laboratory Workflow Engine
 * Reception → TAT Engine → Analysis → Validation → Release
 * Spec: manual + automated source, entry_mode, chain of custody
 */
'use strict';

(function () {
  const NEXUS  = window.NEXUS || {};
  const API    = NEXUS.API   || { get:(u,p)=>fetch('/api/v1'+u+(p?'?'+new URLSearchParams(p):'')), json:r=>r.json(), checkError:async r=>{if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.statusText)} };
  const Toast  = NEXUS.Toast || { success:(t,m)=>console.log(t,m), error:(t,m)=>console.error(t,m), warning:(t,m)=>console.warn(t,m), info:(t,m)=>console.info(t,m) };
  const CSRF   = () => window.NEXUS?.csrf || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  const esc    = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt    = NEXUS.fmt || { datetime:d=>d?new Date(d).toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):'—', age:d=>{if(!d)return'—';const y=new Date().getFullYear()-new Date(d).getFullYear();return`${y}yrs`} };
  const $ = id => document.getElementById(id);

  /* ── Global state ─────────────────────────────────────────── */
  let activeDept     = 'all';
  let activeMode     = 'worklist';
  let worklist       = [];
  let activeRequest  = null;   // Currently open for result entry
  let resultDraft    = {};     // { rt_id: { value, flag, comment, source } }
  let resultSource   = 'MANUAL';
  let entryMode      = 'SINGLE';
  let scanLookup     = null;   // LabRequest from barcode scan
  let tatTimer       = null;
  let wlTimer        = null;
  let tatRefreshTimer= null;
  let recentReceptions = [];

  /* ── TAT constants (minutes by priority) ─────────────────── */
  const TAT_LIMITS = { emergency:60, urgent:120, routine:240, normal:480 };

  /* ════════════════════════════════════════════════════════════
     WORKFLOW NAV
  ════════════════════════════════════════════════════════════ */
  document.querySelectorAll('.wf-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.wf-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.wf-pane').forEach(p => p.style.display = 'none');
      tab.classList.add('active');
      activeMode = tab.dataset.mode;
      const pane = $(tab.dataset.pane);
      if (pane) pane.style.display = 'flex';
      onModeChange(activeMode);
    });
  });

  function onModeChange(mode) {
    if (mode === 'worklist')   loadWorklist();
    if (mode === 'reception')  focusScan();
    if (mode === 'analysis')   loadAnalysisQueue();
    if (mode === 'validation') loadValidationQueue();
    if (mode === 'tat')        loadTATMonitor();
  }

  /* ── Department strip ────────────────────────────────────── */
  document.querySelectorAll('.dept-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.dept-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      activeDept = chip.dataset.dept || 'all';
      if (activeMode === 'worklist') loadWorklist();
      if (activeMode === 'analysis') loadAnalysisQueue();
    });
  });

  /* ── Filters ──────────────────────────────────────────────── */
  $('filter-status')?.addEventListener('change', loadWorklist);
  $('filter-emerg')?.addEventListener('change',  loadWorklist);
  $('filter-date')?.addEventListener('change',   loadWorklist);
  $('refresh-btn')?.addEventListener('click',    loadWorklist);

  let searchTimer = null;
  $('worklist-search')?.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadWorklist, 300);
  });

  /* ════════════════════════════════════════════════════════════
     WORKLIST
  ════════════════════════════════════════════════════════════ */
  async function loadWorklist() {
    const tbody = $('worklist-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="8"><div class="worklist-loading"><i class="fas fa-spinner"></i> Loading…</div></td></tr>';

    const params = {};
    const statusVal = $('filter-status')?.value;
    const emergVal  = $('filter-emerg')?.value;
    const dateVal   = $('filter-date')?.value;
    const searchVal = $('worklist-search')?.value?.trim();
    if (statusVal)           params.status         = statusVal;
    if (activeDept !== 'all')params.department      = activeDept;
    if (emergVal)            params.emergency_level = emergVal;
    if (dateVal)             params.date_from       = dateVal;
    if (searchVal)           params.search          = searchVal;

    try {
      const r    = await API.get('/laboratory/requests/', params);
      const data = await API.json(r);
      worklist   = data.results ?? data;
      renderWorklist(worklist);
      updateDeptCounts(worklist);
      $('result-count') && ($('result-count').textContent = `${worklist.length} requests`);
      $('badge-worklist') && ($('badge-worklist').textContent = worklist.length);
      checkTATAlerts(worklist);
    } catch (e) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="8"><div class="worklist-loading">⚠️ ${esc(e.message)}</div></td></tr>`;
    }
  }

  function renderWorklist(requests) {
    const tbody = $('worklist-tbody');
    if (!tbody) return;
    if (!requests.length) {
      tbody.innerHTML = '<tr><td colspan="8"><div class="worklist-loading">No requests found</div></td></tr>';
      return;
    }
    tbody.innerHTML = requests.map(req => {
      const tat    = calcTAT(req);
      const tests  = (req.test_names || []).slice(0, 3).map(t => `<span class="wl-test-tag">${esc(t)}</span>`).join('');
      const extra  = (req.test_names || []).length > 3 ? `<span class="wl-test-tag">+${(req.test_names.length-3)}</span>` : '';
      return `<tr class="${req.emergency_level === 'emergency' ? 'row-stat' : ''}" data-id="${req.id}">
        <td>
          <div class="wl-patient-name">${esc(req.patient_name || '—')}</div>
          <div class="wl-patient-pid">${esc(req.patient_pid || '')} · ${req.patient_lid ? `<span style="color:var(--cyan)">🌐 ${esc(req.patient_lid)}</span>` : ''}</div>
        </td>
        <td><span class="wl-lab-id">${esc(req.lab_id)}</span></td>
        <td>${tests}${extra}</td>
        <td>${renderTATInline(tat)}</td>
        <td>${priorityBadge(req.emergency_level)}</td>
        <td>${statusBadge(req.status)}</td>
        <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(req.doctor_name || '—')}<br>${esc(req.ward || '')}</td>
        <td style="text-align:right">
          <button class="btn btn-primary btn-sm" onclick="window._enterResults(${req.id})">⚗️ Results</button>
          <button class="btn btn-ghost btn-sm" onclick="window._viewCustody(${req.id})" title="Chain of custody">🔗</button>
        </td>
      </tr>`;
    }).join('');

    tbody.querySelectorAll('tr[data-id]').forEach(row => {
      row.addEventListener('click', e => {
        if (!e.target.closest('button')) {
          window._enterResults(parseInt(row.dataset.id));
        }
      });
    });
  }

  function calcTAT(req) {
    if (!req.received_at) return null;
    const start    = new Date(req.received_at);
    const now      = new Date();
    const elapsed  = Math.floor((now - start) / 60000);
    const limitMin = TAT_LIMITS[req.emergency_level] || 240;
    const pct      = Math.min(100, Math.round((elapsed / limitMin) * 100));
    return { elapsed, limitMin, pct, status: pct < 60 ? 'green' : pct < 80 ? 'yellow' : pct < 100 ? 'orange' : 'red' };
  }

  function renderTATInline(tat) {
    if (!tat) return '<span style="font-size:10px;color:var(--text-muted)">Not started</span>';
    return `<div class="tat-inline">
      <div class="tat-inline-bar-bg"><div class="tat-inline-bar-fill tat-${tat.status}" style="width:${tat.pct}%"></div></div>
      <div class="tat-inline-elapsed">${tat.elapsed} min / ${tat.limitMin} min (${tat.pct}%)</div>
    </div>`;
  }

  function updateDeptCounts(requests) {
    const counts = {};
    requests.forEach(r => { (r.department_ids || []).forEach(did => { counts[did] = (counts[did] || 0) + 1; }); });
    document.querySelectorAll('.dept-chip[data-dept]').forEach(c => {
      const id = c.dataset.dept;
      const el = c.querySelector('.dept-chip-count');
      if (el && id !== 'all') el.textContent = counts[id] || 0;
    });
  }

  function checkTATAlerts(requests) {
    const breached = requests.filter(r => { const t = calcTAT(r); return t && t.status === 'red'; });
    const pill = $('tat-alert-pill');
    const cnt  = $('tat-alert-count');
    if (pill) pill.style.display = breached.length ? 'flex' : 'none';
    if (cnt)  cnt.textContent = breached.length;
  }

  /* ── Expose to inline onclick ──────────────────────────────── */
  window._enterResults = (id) => {
    const req = worklist.find(r => r.id === id);
    if (req) {
      // Switch to analysis tab and open this request
      document.querySelector('.wf-tab[data-mode="analysis"]')?.click();
      setTimeout(() => openResultEntry(req), 100);
    }
  };

  window._viewCustody = (id) => {
    window.open(`/laboratory/requests/${id}/custody/`, '_blank');
  };

  /* ════════════════════════════════════════════════════════════
     RECEPTION — BARCODE SCAN + TAT START
  ════════════════════════════════════════════════════════════ */
  function focusScan() {
    setTimeout(() => $('scan-barcode-input')?.focus(), 100);
    loadRecentReceptions();
  }

  $('scan-barcode-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); doScanLookup(); }
  });

  $('scan-lookup-btn')?.addEventListener('click', doScanLookup);

  async function doScanLookup() {
    const val = $('scan-barcode-input')?.value?.trim();
    if (!val) return;
    $('scan-result-card').style.display = 'none';
    $('tat-start-confirm').style.display = 'none';

    try {
      const r    = await API.get('/laboratory/requests/', { lab_id: val, page_size: 1 });
      const data = await API.json(r);
      const reqs = data.results ?? data;
      if (!reqs.length) { Toast.warning('Not Found', `No request found for barcode: ${val}`); return; }
      scanLookup = reqs[0];
      renderScanCard(scanLookup);
    } catch (e) { Toast.error('Lookup failed', e.message); }
  }

  function renderScanCard(req) {
    $('scan-result-card').style.display = 'block';
    $('src-patient-name').textContent = req.patient_name || '—';
    $('src-patient-meta').textContent = `${req.patient_pid || ''} · ${fmt.age(req.patient_dob)} · ${req.patient_lid ? '🌐 ' + req.patient_lid : ''}`;
    $('src-lab-id').textContent = req.lab_id;
    $('src-lid').textContent    = req.patient_lid || '—';
    $('src-priority').innerHTML = priorityBadge(req.emergency_level);
    $('src-doctor').textContent = req.doctor_name || '—';
    $('src-ward').textContent   = [req.ward, req.bed].filter(Boolean).join(' / ') || '—';
    $('src-clinical').textContent = req.clinical_info || '—';

    const samplesEl = $('src-samples-list');
    samplesEl.innerHTML = (req.samples || []).map(s => `
      <div class="sample-tube-chip">
        <div class="stc-tube" style="background:${s.label_color || '#E74C3C'}"></div>
        <div>
          <div class="stc-sid">${esc(s.sid)}</div>
          <div class="stc-dept">${esc(s.department_name || '')}</div>
        </div>
        <div class="stc-tube-type">${esc(s.tube_type || '')}</div>
        ${s.is_high_risk ? '<span class="badge badge-red" style="font-size:9px">⚠️ High Risk</span>' : ''}
      </div>
    `).join('') || '<div style="font-size:var(--text-xs);color:var(--text-muted)">No sample data</div>';

    $('src-rejection-row').style.display = 'none';
  }

  $('src-receive-btn')?.addEventListener('click', async () => {
    if (!scanLookup) return;
    const btn = $('src-receive-btn');
    btn.classList.add('btn-loading');
    try {
      const r = await fetch(`/api/v1/laboratory/requests/${scanLookup.id}/receive/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF() },
        body: JSON.stringify({ barcode: $('scan-barcode-input').value.trim() }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Failed to receive sample');

      // Show TAT confirmation
      $('scan-result-card').style.display = 'none';
      const conf = $('tat-start-confirm');
      conf.style.display = 'flex';
      $('tsc-lab-id').textContent = scanLookup.lab_id;
      const limit = TAT_LIMITS[scanLookup.emergency_level] || 240;
      const deadline = new Date(Date.now() + limit * 60000);
      $('tsc-deadline').textContent = `⏱️ TAT deadline: ${deadline.toLocaleTimeString('en-GB', {hour:'2-digit',minute:'2-digit'})} (${limit} min)`;

      // Add to recent
      recentReceptions.unshift({
        lab_id:   scanLookup.lab_id,
        patient:  scanLookup.patient_name,
        time:     new Date(),
        priority: scanLookup.emergency_level,
      });
      if (recentReceptions.length > 20) recentReceptions.pop();
      renderRecentReceptions();

      Toast.success('✅ Sample Received', `${scanLookup.lab_id} · TAT started`);
      scanLookup = null;
      $('scan-barcode-input').value = '';

      // Update worklist badge
      loadWLBadge();
    } catch (e) { Toast.error('Reception failed', e.message); }
    finally { btn.classList.remove('btn-loading'); }
  });

  $('src-reject-btn')?.addEventListener('click', () => {
    const row = $('src-rejection-row');
    if (row.style.display === 'none') {
      row.style.display = 'flex';
      $('src-reject-btn').innerHTML = '⚠️ Confirm Rejection';
      $('src-reject-btn').classList.add('btn-loading');
    } else {
      doRejectSample();
    }
  });

  async function doRejectSample() {
    if (!scanLookup) return;
    const reason = $('src-reject-reason')?.value;
    if (!reason) { Toast.warning('Required', 'Select a rejection reason.'); return; }
    try {
      await fetch(`/api/v1/laboratory/requests/${scanLookup.id}/reject/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF() },
        body: JSON.stringify({ reason, detail: $('src-reject-detail')?.value || '' }),
      });
      Toast.warning('Sample Rejected', `${scanLookup.lab_id} — ${reason}`);
      $('scan-result-card').style.display = 'none';
      $('src-rejection-row').style.display = 'none';
      $('scan-barcode-input').value = '';
      scanLookup = null;
    } catch (e) { Toast.error('Rejection failed', e.message); }
  }

  $('tsc-scan-next')?.addEventListener('click', () => {
    $('tat-start-confirm').style.display = 'none';
    $('scan-barcode-input')?.focus();
  });

  function renderRecentReceptions() {
    const el = $('recent-receptions-list');
    if (!el || !recentReceptions.length) return;
    el.innerHTML = recentReceptions.slice(0, 15).map(r => {
      const elapsed = Math.floor((Date.now() - r.time) / 60000);
      const color = r.priority === 'emergency' ? 'var(--alert-red)' : r.priority === 'urgent' ? 'var(--alert-orange)' : 'var(--alert-green)';
      return `<div class="rr-item">
        <div class="rr-tat-dot" style="background:${color}"></div>
        <span class="rr-lab-id">${esc(r.lab_id)}</span>
        <span class="rr-patient">${esc(r.patient)}</span>
        <span class="rr-time">${elapsed} min ago</span>
      </div>`;
    }).join('');
  }

  async function loadRecentReceptions() {
    try {
      const r    = await API.get('/laboratory/requests/', { status: 'received', page_size: 15 });
      const data = await API.json(r);
      const reqs = data.results ?? data;
      recentReceptions = reqs.map(r => ({ lab_id:r.lab_id, patient:r.patient_name, time:new Date(r.received_at||Date.now()), priority:r.emergency_level }));
      renderRecentReceptions();
    } catch (_) {}
  }

  /* ════════════════════════════════════════════════════════════
     ANALYSIS — RESULT ENTRY ENGINE
  ════════════════════════════════════════════════════════════ */
  async function loadAnalysisQueue() {
    const list = $('aqp-list');
    if (list) list.innerHTML = '<div class="tab-hint"><i class="fas fa-spinner fa-spin"></i><p>Loading…</p></div>';

    try {
      const params = { status: 'received,processing', page_size: 50 };
      if (activeDept !== 'all') params.department = activeDept;
      const dept = $('aqp-dept-filter')?.value;
      if (dept) params.department = dept;

      const r    = await API.get('/laboratory/requests/', params);
      const data = await API.json(r);
      const reqs = data.results ?? data;
      renderAnalysisQueue(reqs);
      $('badge-analysis') && ($('badge-analysis').textContent = reqs.length);
    } catch (e) {
      if (list) list.innerHTML = `<div class="tab-hint"><p>Failed: ${esc(e.message)}</p></div>`;
    }
  }

  $('aqp-dept-filter')?.addEventListener('change', loadAnalysisQueue);

  function renderAnalysisQueue(requests) {
    const list = $('aqp-list');
    if (!list) return;
    if (!requests.length) {
      list.innerHTML = '<div class="tab-hint"><i class="fas fa-flask-vial" style="font-size:28px;opacity:.2"></i><p>No samples in analysis queue</p></div>';
      return;
    }
    list.innerHTML = requests.map(req => {
      const tat  = calcTAT(req);
      const tatColor = tat ? { green:'var(--alert-green)', yellow:'var(--alert-yellow)', orange:'var(--alert-orange)', red:'var(--alert-red)' }[tat.status] : 'var(--text-muted)';
      return `<div class="aq-item ${activeRequest?.id === req.id ? 'active' : ''}" data-id="${req.id}">
        <div class="aq-dot" style="background:${tatColor}"></div>
        <div class="aq-info">
          <div class="aq-name">${esc(req.patient_name || '—')}</div>
          <div class="aq-lab-id">${esc(req.lab_id)}</div>
          <div class="aq-tat" style="color:${tatColor}">${tat ? `${tat.elapsed}/${tat.limitMin} min · ${tat.pct}%` : 'TAT not started'}</div>
        </div>
        ${priorityBadge(req.emergency_level, true)}
      </div>`;
    }).join('');
    list.querySelectorAll('.aq-item').forEach(el =>
      el.addEventListener('click', async () => {
        list.querySelectorAll('.aq-item').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
        const id = parseInt(el.dataset.id);
        const req = requests.find(r => r.id === id);
        if (req) await openResultEntry(req);
      })
    );
  }

  async function openResultEntry(req) {
    activeRequest = req;
    resultDraft   = {};
    $('rep-empty').style.display = 'none';
    $('rep-active').style.display = 'flex';
    $('rep-active').style.flexDirection = 'column';

    // Header
    $('rep-patient-name').textContent = req.patient_name || '—';
    $('rep-patient-meta').textContent = `${req.patient_pid || ''} · ${fmt.age(req.patient_dob)} · ${req.patient_gender || ''} · ${req.ward || ''}`;
    $('rep-pid').textContent = req.patient_pid || '—';
    $('rep-lid').textContent = req.patient_lid ? `🌐 ${req.patient_lid}` : '—';
    $('rep-lab-id').textContent = req.lab_id;

    // TAT bar
    updateRepTAT(req);

    // Load tests
    const wrap = $('result-entries-wrap');
    wrap.innerHTML = '<div class="worklist-loading"><i class="fas fa-spinner"></i></div>';
    try {
      const r    = await API.get(`/laboratory/requests/${req.id}/`);
      const data = await API.json(r);
      const tests = data.requested_tests || [];
      renderResultEntries(tests);
    } catch (e) {
      wrap.innerHTML = `<div class="tab-hint"><p>Failed to load tests: ${esc(e.message)}</p></div>`;
    }
  }

  function updateRepTAT(req) {
    const tat = calcTAT(req);
    if (!tat) { $('rep-tat-bar-wrap').style.display = 'none'; return; }
    $('rep-tat-bar-wrap').style.display = 'block';
    $('rep-tat-elapsed').textContent = `${tat.elapsed} min`;
    const fill = $('rep-tat-bar-fill');
    fill.style.width   = `${tat.pct}%`;
    fill.style.background = { green:'var(--alert-green)', yellow:'var(--alert-yellow)', orange:'var(--alert-orange)', red:'var(--alert-red)' }[tat.status];
    const deadline = req.received_at ? new Date(new Date(req.received_at).getTime() + (TAT_LIMITS[req.emergency_level]||240)*60000) : null;
    $('rep-tat-deadline').textContent = deadline ? `Deadline: ${deadline.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})}` : '';
  }

  function renderResultEntries(tests) {
    const wrap = $('result-entries-wrap');
    if (!tests.length) { wrap.innerHTML = '<div class="tab-hint"><p>No tests in this request</p></div>'; return; }
    wrap.innerHTML = tests.map(rt => {
      const isQual    = rt.result_type === 'qualitative' || rt.test_type === 'qualitative';
      const isValidated = rt.status === 'validated';
      const hasResult   = rt.result;
      const srcIcon     = hasResult ? (rt.result?.result_source === 'AUTOMATED' ? '🤖' : '👤') : '';

      return `<div class="result-entry-row ${isValidated ? 'row-validated' : ''} ${rt.result?.is_critical ? 'row-critical' : ''}" id="rer-${rt.id}">
        <div class="rer-header">
          <span class="rer-test-name">${esc(rt.test_name || rt.test || '—')}</span>
          ${rt.department_name ? `<span class="rer-dept-badge">${esc(rt.department_name)}</span>` : ''}
          ${srcIcon ? `<span class="rer-source-indicator" title="${rt.result?.result_source}">${srcIcon}</span>` : ''}
          ${isValidated ? '<span class="rer-validated-check" title="Validated">✅</span>' : ''}
          ${rt.result?.is_critical ? '<span class="badge badge-red" style="font-size:9px">🚨 CRITICAL</span>' : ''}
        </div>
        <div class="rer-body">
          <div class="rer-value-wrap">
            ${isQual
              ? `<div class="qual-btns" data-rtid="${rt.id}">
                  <button class="qual-btn" data-val="negative">Negative</button>
                  <button class="qual-btn" data-val="positive">Positive</button>
                  <button class="qual-btn" data-val="reactive">Reactive</button>
                  <button class="qual-btn" data-val="non_reactive">Non-Reactive</button>
                  <button class="qual-btn" data-val="weakly_reactive">Weakly Reactive</button>
                </div>`
              : `<div class="rer-value-row">
                  <input type="number" step="any" class="rer-value-input ${rt.result?.is_critical ? 'critical' : rt.result?.is_abnormal ? 'abnormal' : ''}"
                    id="rval-${rt.id}" placeholder="Enter value"
                    value="${rt.result?.value || ''}"
                    ${isValidated ? 'disabled' : ''}>
                  <span class="rer-unit">${esc(rt.unit || '')}</span>
                </div>
                <div class="rer-ref">Ref: ${esc(rt.reference_range || '—')}</div>`
            }
          </div>
          <select class="rer-flag-select" id="rflag-${rt.id}" ${isValidated ? 'disabled' : ''}>
            <option value="N" ${rt.result?.flag === 'N' ? 'selected' : ''}>Normal</option>
            <option value="H" ${rt.result?.flag === 'H' ? 'selected' : ''}>High ↑</option>
            <option value="L" ${rt.result?.flag === 'L' ? 'selected' : ''}>Low ↓</option>
            <option value="HH" ${rt.result?.flag === 'HH' ? 'selected' : ''}>Critical H ↑↑</option>
            <option value="LL" ${rt.result?.flag === 'LL' ? 'selected' : ''}>Critical L ↓↓</option>
            <option value="A" ${rt.result?.flag === 'A' ? 'selected' : ''}>Abnormal</option>
          </select>
          <span class="rer-source-indicator">${resultSource === 'AUTOMATED' ? '🤖' : '👤'}</span>
        </div>
        <div style="padding:0 var(--space-lg) var(--space-sm)">
          <textarea class="rer-comment" id="rcom-${rt.id}" placeholder="Technician comment…"
            ${isValidated ? 'disabled' : ''}>${rt.result?.technician_comment || ''}</textarea>
        </div>
      </div>`;
    }).join('');

    // Wire qualitative buttons
    wrap.querySelectorAll('.qual-btns').forEach(btns => {
      const rtId = btns.dataset.rtid;
      btns.querySelectorAll('.qual-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          btns.querySelectorAll('.qual-btn').forEach(b => b.className = 'qual-btn');
          btn.classList.add(`sel-${btn.dataset.val.split('_')[0]}`);
          resultDraft[rtId] = { ...(resultDraft[rtId] || {}), value: btn.dataset.val };
        });
        if (btn.dataset.val === activeRequest?.requested_tests?.find?.(rt => rt.id === parseInt(rtId))?.result?.value) {
          btn.classList.add(`sel-${btn.dataset.val.split('_')[0]}`);
        }
      });
    });

    // Wire value inputs for live flag suggestion
    wrap.querySelectorAll('.rer-value-input').forEach(inp => {
      const rtId  = inp.id.replace('rval-', '');
      const test  = tests.find(t => String(t.id) === rtId);
      inp.addEventListener('input', () => {
        const v = parseFloat(inp.value);
        if (isNaN(v) || !test?.reference_range) return;
        const range = parseRefRange(test.reference_range);
        if (range) {
          const flagSel = $(`rflag-${rtId}`);
          if (flagSel) {
            if (v > range.hi * 1.5 || v < range.lo * 0.5) { flagSel.value = v > range.hi ? 'HH' : 'LL'; inp.classList.add('critical'); inp.classList.remove('abnormal'); }
            else if (v > range.hi || v < range.lo) { flagSel.value = v > range.hi ? 'H' : 'L'; inp.classList.add('abnormal'); inp.classList.remove('critical'); }
            else { flagSel.value = 'N'; inp.classList.remove('critical','abnormal'); }
          }
        }
        resultDraft[rtId] = { ...(resultDraft[rtId] || {}), value: inp.value };
      });
    });
  }

  function parseRefRange(range) {
    const m = range.match(/([\d.]+)\s*[-–]\s*([\d.]+)/);
    return m ? { lo: parseFloat(m[1]), hi: parseFloat(m[2]) } : null;
  }

  /* ════════════════════════════════════════════════════════════
     CRITICAL RESULT DOCUMENTATION ENGINE
     Spec: When critical value detected → document upload MANDATORY
  ════════════════════════════════════════════════════════════ */
  let criticalValues = [];  // Accumulated critical values for current entry

  function checkAndShowCriticalDocPanel() {
    /* Scan all result rows for critical flags */
    criticalValues = [];
    document.querySelectorAll('[id^="rflag-"]').forEach(sel => {
      if (['HH', 'LL'].includes(sel.value)) {
        const rtId = sel.id.replace('rflag-', '');
        const valEl = $(`rval-${rtId}`);
        const nameEl = document.querySelector(`#rer-${rtId} .rer-test-name`);
        criticalValues.push({
          testName: nameEl?.textContent || '—',
          value: valEl?.value || '—',
          flag: sel.value,
        });
      }
    });

    const panel = $('critical-doc-panel');
    if (!panel) return;

    if (criticalValues.length) {
      panel.style.display = 'block';
      const valDisplay = $('cdp-critical-values');
      if (valDisplay) {
        valDisplay.innerHTML = `<span style="font-size:11px;font-weight:700;color:var(--alert-red);margin-right:8px">🚨 Critical Values:</span>` +
          criticalValues.map(cv => `<span class="cdp-crit-val">
            <strong>${esc(cv.testName)}</strong>
            <span style="font-family:var(--font-mono)">${esc(cv.value)}</span>
            <span class="badge badge-red" style="font-size:8px">${cv.flag}</span>
          </span>`).join('');
      }
      // Scroll into view
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      panel.style.display = 'none';
    }
  }

  /* Wire flag selects to auto-check critical panel on change */
  document.addEventListener('change', e => {
    if (e.target.id?.startsWith('rflag-')) {
      checkAndShowCriticalDocPanel();
    }
  });

  /* Wire value inputs too */
  document.addEventListener('input', e => {
    if (e.target.id?.startsWith('rval-')) {
      // Small delay to let flag auto-update first
      setTimeout(checkAndShowCriticalDocPanel, 200);
    }
  });

  /* Critical doc upload zone */
  $('cdp-upload-zone')?.addEventListener('click', () => $('cdp-file-input')?.click());
  $('cdp-file-input')?.addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { Toast.warning('Too large', 'Max file size 10 MB'); return; }
    const inner    = $('cdp-upload-inner');
    const selected = $('cdp-file-selected');
    const fname    = $('cdp-file-name');
    if (inner)    inner.style.display    = 'none';
    if (selected) selected.style.display = 'flex';
    if (fname)    fname.textContent      = file.name;
  });

  $('cdp-upload-zone')?.addEventListener('dragover', e => { e.preventDefault(); });
  $('cdp-upload-zone')?.addEventListener('drop', e => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) $('cdp-file-input').files = e.dataTransfer.files;
    $('cdp-file-input')?.dispatchEvent(new Event('change'));
  });

  /* Submit critical documentation */
  $('cdp-submit-btn')?.addEventListener('click', async () => {
    if (!activeRequest) return;
    const file     = $('cdp-file-input')?.files[0];
    const reason   = $('cdp-reason')?.value?.trim();
    const docType  = $('cdp-doc-type')?.value;
    const clinician= $('cdp-clinician-name')?.value?.trim();
    const notifMethod = $('cdp-notif-method')?.value;
    const readBack = $('cdp-readback-check')?.checked;

    if (!file)   { Toast.warning('Required', 'Upload a supporting document.'); return; }
    if (!reason) { Toast.warning('Required', 'Enter a clinical justification.'); return; }

    const btn = $('cdp-submit-btn');
    btn.classList.add('btn-loading');

    try {
      const fd = new FormData();
      fd.append('document_file', file);
      fd.append('document_type', docType);
      fd.append('reason', reason);
      fd.append('test_name', criticalValues.map(c => c.testName).join(', '));
      fd.append('clinician_name', clinician || '');
      fd.append('notification_method', notifMethod);
      fd.append('read_back_confirmed', readBack ? 'true' : 'false');
      fd.append('lab_request_id', activeRequest.id);

      const r = await fetch('/api/v1/laboratory/critical-documents/', {
        method: 'POST',
        headers: { 'X-CSRFToken': CSRF() },
        body: fd,
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || 'Upload failed');
      }

      Toast.success(
        '📄 Critical Documentation Submitted',
        `Linked to ${activeRequest.lab_id} · Critical results booked. ${readBack ? 'Read-back confirmed ✅' : ''}`
      );
      $('critical-doc-panel').style.display = 'none';
      criticalValues = [];
    } catch (e) {
      Toast.error('Upload failed', e.message);
    } finally {
      btn.classList.remove('btn-loading');
    }
  });

  /* ════════════════════════════════════════════════════════════
     REFERENCE RANGE ENGINE — live lookup per test + patient
  ════════════════════════════════════════════════════════════ */
  async function lookupReferenceRange(testId, sex, age, valueEl, refEl) {
    if (!testId) return;
    try {
      const params = { active_only: 'true' };
      if (sex) params.sex = sex;
      if (age) params.age = age;
      const r    = await API.get(`/laboratory/reference-ranges/for-test/${testId}/`, params);
      const data = await API.json(r);
      if (data.min_value !== null && data.max_value !== null && refEl) {
        refEl.textContent = `Ref: ${data.min_value}–${data.max_value} ${data.unit}`;
        refEl.dataset.min = data.min_value;
        refEl.dataset.max = data.max_value;
        refEl.dataset.critLo = data.critical_low || '';
        refEl.dataset.critHi = data.critical_high || '';
        // Trigger auto-flag if value already entered
        if (valueEl?.value) {
          const v = parseFloat(valueEl.value);
          const flagSel = valueEl.closest('.result-entry-row')?.querySelector('.rer-flag-select');
          if (flagSel && !isNaN(v)) {
            const clo = parseFloat(refEl.dataset.critLo) || null;
            const chi = parseFloat(refEl.dataset.critHi) || null;
            const lo  = parseFloat(refEl.dataset.min);
            const hi  = parseFloat(refEl.dataset.max);
            if (clo && v <= clo) flagSel.value = 'LL';
            else if (chi && v >= chi) flagSel.value = 'HH';
            else if (v < lo) flagSel.value = 'L';
            else if (v > hi) flagSel.value = 'H';
            else flagSel.value = 'N';
          }
        }
      }
    } catch (_) {}
  }

  /* ── Result source toggle ─────────────────────────────────── */
  document.querySelectorAll('.src-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.src-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      resultSource = btn.dataset.src;
      $('instrument-row').style.display = resultSource === 'AUTOMATED' ? 'block' : 'none';
    });
  });

  $('entry-mode-sel')?.addEventListener('change', e => { entryMode = e.target.value; });

  /* ── Save results ─────────────────────────────────────────── */
  $('rep-save-btn')?.addEventListener('click', () => saveResults(false));
  $('rep-validate-btn')?.addEventListener('click', () => saveResults(true));
  $('rep-clear-btn')?.addEventListener('click', () => {
    resultDraft = {};
    document.querySelectorAll('.rer-value-input').forEach(inp => { inp.value = ''; inp.classList.remove('critical','abnormal'); });
    document.querySelectorAll('.rflag-select').forEach(sel => sel.value = 'N');
  });

  async function saveResults(validate) {
    if (!activeRequest) return;
    const btn = validate ? $('rep-validate-btn') : $('rep-save-btn');
    btn?.classList.add('btn-loading');

    const results = [];
    document.querySelectorAll('[id^="rval-"],[id^="rflag-"],[id^="rcom-"]').forEach(el => {
      // Collect only value inputs
    });

    // Gather results from DOM
    const wrap = $('result-entries-wrap');
    const entries = [];
    wrap?.querySelectorAll('.result-entry-row').forEach(row => {
      const id = row.id.replace('rer-', '');
      const valEl  = $(`rval-${id}`);
      const flagEl = $(`rflag-${id}`);
      const comEl  = $(`rcom-${id}`);
      if (valEl || resultDraft[id]) {
        entries.push({
          requested_test_id: parseInt(id),
          value:   valEl?.value || resultDraft[id]?.value || '',
          flag:    flagEl?.value || resultDraft[id]?.flag || 'N',
          comment: comEl?.value || '',
          result_source: resultSource,
          entry_mode:    entryMode,
          instrument_id: $('instrument-sel')?.value || '',
        });
      }
    });

    if (!entries.length || entries.every(e => !e.value)) {
      Toast.warning('No results', 'Please enter at least one result value.');
      btn?.classList.remove('btn-loading');
      return;
    }

    try {
      const r = await fetch(`/api/v1/laboratory/requests/${activeRequest.id}/enter-results/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF() },
        body: JSON.stringify({ results: entries, validate_all: validate }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || 'Failed to save results');

      if (validate) {
        Toast.success('✅ Results Validated', `${activeRequest.lab_id} — ${entries.length} result(s) released to patient portal`);
        loadValidationQueue();
      } else {
        Toast.success('💾 Results Saved', `${entries.length} result(s) saved. Pending validation.`);
      }

      resultDraft = {};
      loadAnalysisQueue();
      loadWLBadge();
    } catch (e) { Toast.error('Save failed', e.message); }
    finally { btn?.classList.remove('btn-loading'); }
  }

  /* ════════════════════════════════════════════════════════════
     VALIDATION QUEUE
  ════════════════════════════════════════════════════════════ */
  async function loadValidationQueue() {
    const list = $('val-list');
    if (list) list.innerHTML = '<div class="tab-hint"><i class="fas fa-spinner fa-spin"></i><p>Loading…</p></div>';
    try {
      const r    = await API.get('/laboratory/requests/', { status: 'processing', has_results: 'true', page_size: 50 });
      const data = await API.json(r);
      const reqs = data.results ?? data;
      renderValidationList(reqs);
      $('badge-validation') && ($('badge-validation').textContent = reqs.length);
    } catch (e) {
      if (list) list.innerHTML = `<div class="tab-hint"><p>Error: ${esc(e.message)}</p></div>`;
    }
  }

  function renderValidationList(requests) {
    const list = $('val-list');
    if (!list) return;
    if (!requests.length) {
      list.innerHTML = '<div class="tab-hint"><i class="fas fa-check-double" style="font-size:28px;opacity:.2"></i><p>Validation queue is empty</p></div>';
      return;
    }
    list.innerHTML = requests.map(req => `
      <div class="val-item" data-id="${req.id}">
        <div style="font-size:12px">${req.emergency_level === 'emergency' ? '🚨' : req.emergency_level === 'urgent' ? '⚡' : '⚗️'}</div>
        <div class="val-item-info">
          <div class="val-item-name">${esc(req.patient_name || '—')}</div>
          <div class="val-item-id">${esc(req.lab_id)}</div>
          <div class="val-item-tests">${(req.test_names || []).join(', ')}</div>
        </div>
        ${statusBadge(req.status)}
      </div>
    `).join('');
    list.querySelectorAll('.val-item').forEach(el =>
      el.addEventListener('click', async () => {
        list.querySelectorAll('.val-item').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
        const id  = parseInt(el.dataset.id);
        const req = requests.find(r => r.id === id);
        if (req) await openValidationReview(req);
      })
    );
  }

  $('val-dept-filter')?.addEventListener('change', loadValidationQueue);

  async function openValidationReview(req) {
    $('val-empty').style.display = 'none';
    $('val-active').style.display = 'flex';
    $('val-active').style.flexDirection = 'column';
    $('val-patient-name').textContent = req.patient_name || '—';
    $('val-meta').textContent = `${req.lab_id} · ${req.patient_pid} · ${req.doctor_name || '—'} · ${req.ward || ''}`;

    const list = $('val-results-list');
    list.innerHTML = '<div class="worklist-loading"><i class="fas fa-spinner"></i></div>';
    try {
      const r    = await API.get(`/laboratory/requests/${req.id}/`);
      const data = await API.json(r);
      renderValResults(req, data.requested_tests || []);
    } catch (e) {
      list.innerHTML = `<div class="tab-hint"><p>Error: ${esc(e.message)}</p></div>`;
    }
  }

  function renderValResults(req, tests) {
    const list = $('val-results-list');
    if (!tests.length) { list.innerHTML = '<div class="tab-hint"><p>No results to validate</p></div>'; return; }

    list.innerHTML = tests.filter(t => t.result).map(t => {
      const src = t.result?.result_source === 'AUTOMATED' ? '🤖' : '👤';
      const isCritical = t.result?.is_critical;
      return `<div class="val-result-row ${isCritical ? 'val-critical' : ''}">
        <div class="vrr-source">${src}</div>
        <div class="vrr-test">${esc(t.test_name || '—')}</div>
        <div>
          <div class="vrr-value" style="color:${flagColor(t.result?.flag)}">${esc(t.result?.value || '—')}</div>
          <div class="vrr-unit">${esc(t.unit || '')}</div>
          <div class="vrr-ref">Ref: ${esc(t.reference_range || '—')}</div>
        </div>
        <div>${flagBadge(t.result?.flag)}</div>
        ${isCritical ? '<span class="badge badge-red" style="font-size:9px">🚨 CRITICAL</span>' : ''}
        ${t.result?.technician_comment ? `<div style="font-size:10px;color:var(--text-muted);font-style:italic">"${esc(t.result.technician_comment)}"</div>` : ''}
      </div>`;
    }).join('');

    // Wire validate/return buttons
    $('val-authorize-btn').__req = req;
    $('val-return-btn').__req = req;
  }

  $('val-authorize-btn')?.addEventListener('click', async function () {
    const req = this.__req;
    if (!req) return;
    this.classList.add('btn-loading');
    try {
      const r = await fetch(`/api/v1/laboratory/requests/${req.id}/validate/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF() },
      });
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail || 'Validation failed'); }
      Toast.success('✅ Results Validated & Released', `${req.lab_id} — Results released to patient portal. SMS notification queued.`);
      $('val-empty').style.display = 'flex';
      $('val-active').style.display = 'none';
      loadValidationQueue();
      loadWLBadge();
    } catch (e) { Toast.error('Validation failed', e.message); }
    finally { this.classList.remove('btn-loading'); }
  });

  $('val-return-btn')?.addEventListener('click', async function () {
    const req = this.__req;
    if (!req) return;
    Toast.info('Returned', `${req.lab_id} returned to analyst for correction.`);
    $('val-empty').style.display = 'flex';
    $('val-active').style.display = 'none';
    loadValidationQueue();
  });

  /* ════════════════════════════════════════════════════════════
     TAT MONITOR
  ════════════════════════════════════════════════════════════ */
  async function loadTATMonitor() {
    clearInterval(tatRefreshTimer);
    await refreshTAT();
    tatRefreshTimer = setInterval(refreshTAT, 30000);
  }

  async function refreshTAT() {
    $('tat-last-updated') && ($('tat-last-updated').textContent = `Updated: ${new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}`);
    try {
      const r    = await API.get('/laboratory/requests/', { status: 'received,processing', page_size: 100 });
      const data = await API.json(r);
      const reqs = data.results ?? data;
      renderTATTable(reqs);
      renderTATKPIs(reqs);
      renderDeptBreakdown(reqs);
    } catch (_) {}
  }

  function renderTATTable(reqs) {
    const tbody = $('tat-table-body');
    if (!tbody) return;
    if (!reqs.length) { tbody.innerHTML = '<tr><td colspan="9"><div class="worklist-loading">No active samples</div></td></tr>'; return; }
    tbody.innerHTML = reqs.map(req => {
      const tat = calcTAT(req);
      if (!tat) return '';
      const fill = `<div class="tat-full-bar-fill tat-${tat.status}" style="width:${tat.pct}%"></div>`;
      const deadline = req.received_at ? new Date(new Date(req.received_at).getTime() + tat.limitMin*60000) : null;
      return `<tr>
        <td><div class="wl-patient-name">${esc(req.patient_name||'—')}</div></td>
        <td><span class="wl-lab-id">${esc(req.lab_id)}</span></td>
        <td style="font-size:10px;font-family:var(--font-mono)">${esc(req.sample_ids?.join(', ')||'—')}</td>
        <td style="font-size:var(--text-xs)">${esc(req.department_name||'—')}</td>
        <td>${priorityBadge(req.emergency_level)}</td>
        <td><div class="tat-full-bar"><div class="tat-full-bar-bg">${fill}</div>
          <div class="tat-full-text"><span>${tat.elapsed} min</span><span>${tat.pct}%</span></div></div></td>
        <td style="font-family:var(--font-mono);font-size:11px;color:${tat.status==='red'?'var(--alert-red)':'var(--text-secondary)'}">${tat.elapsed} min</td>
        <td style="font-family:var(--font-mono);font-size:11px">${deadline?deadline.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}):'—'}</td>
        <td>${statusBadge(req.status)}</td>
      </tr>`;
    }).join('');
  }

  function renderTATKPIs(reqs) {
    const tats = reqs.map(r => calcTAT(r)).filter(Boolean);
    const ontime  = tats.filter(t => t.status === 'green').length;
    const warning = tats.filter(t => t.status === 'yellow').length;
    const breach  = tats.filter(t => t.status === 'red').length;
    const avg     = tats.length ? Math.round(tats.reduce((a,b) => a + b.elapsed, 0) / tats.length) : 0;
    $('tat-kpi-ontime')  && ($('tat-kpi-ontime').textContent  = ontime);
    $('tat-kpi-warning') && ($('tat-kpi-warning').textContent = warning);
    $('tat-kpi-breach')  && ($('tat-kpi-breach').textContent  = breach);
    $('tat-kpi-avg')     && ($('tat-kpi-avg').textContent     = avg + ' min');
    $('tat-kpi-active')  && ($('tat-kpi-active').textContent  = reqs.length);
  }

  function renderDeptBreakdown(reqs) {
    const el = $('tat-dept-breakdown');
    if (!el) return;
    const byDept = {};
    reqs.forEach(r => {
      const d = r.department_name || 'Unknown';
      if (!byDept[d]) byDept[d] = { total:0, breach:0, avg:0, elapsed:[] };
      byDept[d].total++;
      const tat = calcTAT(r);
      if (tat) { if (tat.status === 'red') byDept[d].breach++; byDept[d].elapsed.push(tat.elapsed); }
    });
    el.innerHTML = Object.entries(byDept).map(([dept, s]) => {
      const avg = s.elapsed.length ? Math.round(s.elapsed.reduce((a,b)=>a+b,0)/s.elapsed.length) : 0;
      return `<div class="tat-dept-card">
        <div class="tat-dept-name">${esc(dept)}</div>
        <div class="tat-dept-stat"><span>Active</span><strong>${s.total}</strong></div>
        <div class="tat-dept-stat"><span>Breach</span><strong style="color:${s.breach?'var(--alert-red)':'var(--alert-green)'}">${s.breach}</strong></div>
        <div class="tat-dept-stat"><span>Avg TAT</span><strong>${avg} min</strong></div>
      </div>`;
    }).join('');
  }

  /* ════════════════════════════════════════════════════════════
     UTILITY
  ════════════════════════════════════════════════════════════ */
  async function loadWLBadge() {
    try {
      const r    = await API.get('/laboratory/requests/', { status: 'submitted,received,processing', page_size: 1 });
      const data = await API.json(r);
      const cnt  = data.count ?? (data.results ?? data).length;
      $('badge-worklist') && ($('badge-worklist').textContent = cnt);
      $('badge-reception') && ($('badge-reception').textContent = '');
    } catch (_) {}
  }

  function priorityBadge(level, small) {
    const map = { emergency:'badge-red anim-pulse-critical', urgent:'badge-orange', routine:'badge-blue', normal:'badge-grey' };
    const labels = { emergency:'🚨 STAT', urgent:'⚡ Urgent', routine:'Routine', normal:'Normal' };
    const cls = map[level] || 'badge-grey';
    const lbl = labels[level] || level || '—';
    return `<span class="badge ${cls}" style="${small?'font-size:9px':''}}">${esc(lbl)}</span>`;
  }

  function statusBadge(status) {
    const map = { validated:'badge-green', completed:'badge-green', processing:'badge-blue', received:'badge-cyan', submitted:'badge-grey', cancelled:'badge-grey', draft:'badge-grey' };
    return `<span class="badge ${map[status]||'badge-grey'}">${esc(status||'—')}</span>`;
  }

  function flagColor(flag) {
    return { HH:'var(--alert-red)', LL:'var(--alert-red)', H:'var(--alert-orange)', L:'var(--alert-orange)', A:'var(--alert-orange)', N:'var(--text-primary)' }[flag] || 'var(--text-primary)';
  }

  function flagBadge(flag) {
    const map = { HH:'badge-red', LL:'badge-red', H:'badge-orange', L:'badge-orange', A:'badge-orange', N:'badge-green' };
    const lbl = { HH:'Critical H', LL:'Critical L', H:'High', L:'Low', A:'Abnormal', N:'Normal' };
    return flag ? `<span class="badge ${map[flag]||'badge-grey'}" style="font-size:9px">${lbl[flag]||flag}</span>` : '';
  }

  /* ════════════════════════════════════════════════════════════
     INIT
  ════════════════════════════════════════════════════════════ */
  loadWorklist();
  loadWLBadge();

  // Auto-refresh worklist every 60s
  wlTimer = setInterval(loadWorklist, 60000);

  // Expose global reload handle
  window._labReload = loadWorklist;

})();
