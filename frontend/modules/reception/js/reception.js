/**
 * JORINOVA NEXUS ALIS-X — Reception
 * New request form: patient search · test catalog · tube summary · submit
 * Today's queue: live table with status
 */
'use strict';

(function () {
  const { API, Toast, Confirm, fmt } = window.NEXUS;

  /* ─── State ─────────────────────────────────────────────────── */
  let selectedPatient  = null;
  let catalog          = [];   /* flat list of all tests */
  let departments      = [];
  let selectedTestIds  = new Set();
  let emergencyLevel   = 'routine';
  let isHighRisk       = false;
  let searchDebounce   = null;
  let catalogDebounce  = null;

  /* ─── DOM ────────────────────────────────────────────────────── */
  const patientInput   = document.getElementById('patient-search-input');
  const patientDrop    = document.getElementById('patient-dropdown');
  const patientCard    = document.getElementById('selected-patient-card');
  const noPatientHint  = document.getElementById('no-patient-hint');
  const catalogSearch  = document.getElementById('catalog-search');
  const catalogTests   = document.getElementById('catalog-tests');
  const summaryTests   = document.getElementById('summary-tests');
  const tubesSection   = document.getElementById('tubes-section');
  const selectedCount  = document.getElementById('selected-count');
  const submitBtn      = document.getElementById('btn-submit-request');
  const queueTbody     = document.getElementById('queue-tbody');

  /* ════════════════════════════════════════════════════════════
     TAB SWITCHING
  ════════════════════════════════════════════════════════════ */
  document.querySelectorAll('.reception-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.reception-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.rec-pane').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(tab.dataset.pane)?.classList.add('active');
      if (tab.dataset.pane === 'queue-pane') loadQueue();
    });
  });

  /* ════════════════════════════════════════════════════════════
     PATIENT SEARCH
  ════════════════════════════════════════════════════════════ */
  patientInput?.addEventListener('input', () => {
    const q = patientInput.value.trim();
    clearTimeout(searchDebounce);
    if (q.length < 2) { closePatientDrop(); return; }
    searchDebounce = setTimeout(() => searchPatients(q), 280);
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('#patient-search-wrap')) closePatientDrop();
  });

  async function searchPatients(q) {
    try {
      const r    = await API.get('/patients/', { q, page_size: 8 });
      const data = await API.json(r);
      const pts  = data.results ?? data;
      renderPatientDropdown(pts);
    } catch (_) {}
  }

  function renderPatientDropdown(patients) {
    if (!patients.length) { closePatientDrop(); return; }
    patientDrop.innerHTML = patients.map(p => `
      <div class="pd-item" data-id="${p.id}" role="option">
        <div class="pd-avatar">
          ${p.photo_url ? `<img src="${p.photo_url}" alt="">` : initials(p.full_name)}
        </div>
        <div class="pd-info">
          <div class="pd-name">${escHtml(p.full_name)}</div>
          <div class="pd-meta">${escHtml(p.pid)} · ${fmt.age(p.date_of_birth)}</div>
        </div>
      </div>
    `).join('');
    patientDrop.querySelectorAll('.pd-item').forEach(el => {
      el.addEventListener('click', () => selectPatient(patients.find(p => p.id == el.dataset.id)));
    });
    patientDrop.classList.add('open');
  }

  function selectPatient(p) {
    if (!p) return;
    selectedPatient = p;
    closePatientDrop();
    patientInput.value = p.full_name;

    /* Show card */
    document.getElementById('spc-name').textContent = p.full_name;
    document.getElementById('spc-pid').textContent  = p.pid;
    document.getElementById('spc-age').textContent  = fmt.age(p.date_of_birth);
    document.getElementById('spc-gender').textContent = p.gender || '';
    if (p.blood_group && p.blood_group !== 'unknown') {
      const bg = document.getElementById('spc-blood');
      if (bg) { bg.textContent = p.blood_group; bg.style.display = ''; }
    }
    patientCard?.classList.add('visible');
    noPatientHint && (noPatientHint.style.display = 'none');
    updateSubmitState();
  }

  document.getElementById('spc-change-btn')?.addEventListener('click', () => {
    selectedPatient = null;
    patientInput.value = '';
    patientCard?.classList.remove('visible');
    noPatientHint && (noPatientHint.style.display = 'flex');
    patientInput.focus();
    updateSubmitState();
  });

  function closePatientDrop() {
    patientDrop?.classList.remove('open');
  }

  /* ════════════════════════════════════════════════════════════
     CATALOG LOADING
  ════════════════════════════════════════════════════════════ */
  async function loadCatalog() {
    try {
      const [deptRes, testRes] = await Promise.all([
        API.get('/laboratory/departments/'),
        API.get('/laboratory/tests/', { page_size: 500 }),
      ]);
      departments = await API.json(deptRes);
      const testData = await API.json(testRes);
      catalog = testData.results ?? testData;
      renderCatalog(catalog, departments);
    } catch (err) {
      catalogTests && (catalogTests.innerHTML = `<p class="text-muted-c text-xs" style="padding:1rem">Failed to load tests: ${escHtml(err.message)}</p>`);
    }
  }

  function renderCatalog(tests, depts) {
    if (!catalogTests) return;
    const byDept = {};
    depts.forEach(d => { byDept[d.id] = { dept: d, tests: [] }; });
    tests.forEach(t => {
      const deptName = t.department_name;
      const dept = depts.find(d => d.name === deptName);
      if (dept) byDept[dept.id]?.tests.push(t);
    });

    catalogTests.innerHTML = Object.values(byDept).filter(g => g.tests.length).map(g => `
      <div class="dept-section" data-dept-id="${g.dept.id}">
        <div class="dept-section-header" role="button" tabindex="0">
          <div class="dept-color-bar" style="background:${escHtml(g.dept.color_hex)}"></div>
          <span class="dept-section-name">${escHtml(g.dept.name)}</span>
          <span class="dept-section-count">${g.tests.length}</span>
          <i class="fas fa-chevron-right dept-chevron"></i>
        </div>
        <div class="dept-tests-list">
          ${g.tests.map(t => `
            <div class="test-item" data-test-id="${t.id}" data-tube="${escHtml(t.tube_type)}" data-color="${escHtml(t.tube_label_color)}" role="checkbox" aria-checked="false" tabindex="0">
              <div class="test-checkbox"><i class="fas fa-check"></i></div>
              <div class="test-tube-dot" style="background:${escHtml(t.tube_label_color)}"></div>
              <div class="test-info">
                <div class="test-name">${escHtml(t.name)}</div>
                <div class="test-meta">${escHtml(t.department_name)} · ${t.tat_hours}h TAT</div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');

    /* Dept accordion */
    catalogTests.querySelectorAll('.dept-section-header').forEach(hdr => {
      hdr.addEventListener('click', () => {
        hdr.parentElement.classList.toggle('open');
      });
      hdr.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') hdr.click();
      });
    });

    /* Test selection */
    catalogTests.querySelectorAll('.test-item').forEach(el => {
      el.addEventListener('click', () => toggleTest(el));
      el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') toggleTest(el); });
    });
  }

  function toggleTest(el) {
    const id = parseInt(el.dataset.testId);
    if (selectedTestIds.has(id)) {
      selectedTestIds.delete(id);
      el.classList.remove('selected');
      el.setAttribute('aria-checked', 'false');
    } else {
      selectedTestIds.add(id);
      el.classList.add('selected');
      el.setAttribute('aria-checked', 'true');
    }
    updateSummary();
    updateSubmitState();
  }

  /* ─── Catalog search ─────────────────────────────────────────── */
  catalogSearch?.addEventListener('input', () => {
    clearTimeout(catalogDebounce);
    catalogDebounce = setTimeout(() => filterCatalog(catalogSearch.value.trim().toLowerCase()), 200);
  });

  function filterCatalog(q) {
    document.querySelectorAll('.test-item').forEach(el => {
      const name = el.querySelector('.test-name')?.textContent.toLowerCase() || '';
      el.classList.toggle('hidden', q.length > 0 && !name.includes(q));
    });
    /* Auto-open matching dept sections */
    if (q) {
      document.querySelectorAll('.dept-section').forEach(sec => {
        const visible = [...sec.querySelectorAll('.test-item')].some(el => !el.classList.contains('hidden'));
        sec.classList.toggle('open', visible);
      });
    }
  }

  /* ════════════════════════════════════════════════════════════
     SUMMARY PANEL
  ════════════════════════════════════════════════════════════ */
  function updateSummary() {
    if (!summaryTests) return;
    const selected = catalog.filter(t => selectedTestIds.has(t.id));
    selectedCount && (selectedCount.textContent = selected.length
      ? `${selected.length} test${selected.length > 1 ? 's' : ''} selected`
      : '');

    if (!selected.length) {
      summaryTests.innerHTML = '<div class="no-tests-msg">No tests selected yet</div>';
      tubesSection && (tubesSection.style.display = 'none');
      return;
    }

    summaryTests.innerHTML = selected.map(t => `
      <div class="sum-test-row">
        <div class="test-tube-dot" style="background:${escHtml(t.tube_label_color)}"></div>
        <span class="sum-test-name">${escHtml(t.short_name || t.name)}</span>
        <button class="sum-remove" data-test-id="${t.id}" type="button" aria-label="Remove ${escHtml(t.name)}">
          <i class="fas fa-xmark"></i>
        </button>
      </div>
    `).join('');
    summaryTests.querySelectorAll('.sum-remove').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.dataset.testId);
        selectedTestIds.delete(id);
        document.querySelector(`.test-item[data-test-id="${id}"]`)?.classList.remove('selected');
        updateSummary();
        updateSubmitState();
      });
    });

    /* Tubes required */
    const tubeMap = {};
    selected.forEach(t => {
      const key = t.tube_type;
      if (!tubeMap[key]) tubeMap[key] = { color: t.tube_label_color, label: t.tube_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()), count: 0 };
      tubeMap[key].count++;
    });

    if (tubesSection) {
      tubesSection.style.display = 'block';
      const tubesList = document.getElementById('tubes-list');
      if (tubesList) {
        tubesList.innerHTML = Object.values(tubeMap).map(tube => `
          <div class="tube-requirement">
            <div class="tube-circle" style="background:${escHtml(tube.color)}"></div>
            <span class="tube-label-text">${escHtml(tube.label)}</span>
            <span class="tube-count">×${tube.count}</span>
          </div>
        `).join('');
      }
    }
  }

  /* ════════════════════════════════════════════════════════════
     PRIORITY PILLS
  ════════════════════════════════════════════════════════════ */
  document.querySelectorAll('.priority-pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.priority-pill').forEach(p => p.classList.remove('selected'));
      pill.classList.add('selected');
      emergencyLevel = pill.dataset.level || 'routine';
    });
  });

  /* ─── High-risk toggle ───────────────────────────────────────── */
  const highRiskToggle = document.getElementById('high-risk-toggle');
  const highRiskRow    = document.getElementById('high-risk-row');
  highRiskToggle?.addEventListener('change', function () {
    isHighRisk = this.checked;
    highRiskRow?.classList.toggle('active', isHighRisk);
  });

  /* ════════════════════════════════════════════════════════════
     SUBMIT REQUEST
  ════════════════════════════════════════════════════════════ */
  function updateSubmitState() {
    if (!submitBtn) return;
    const ready = selectedPatient && selectedTestIds.size > 0;
    submitBtn.disabled = !ready;
  }

  submitBtn?.addEventListener('click', submitRequest);

  async function submitRequest() {
    if (!selectedPatient) { Toast.warning('No patient selected', 'Search and select a patient first.'); return; }
    if (!selectedTestIds.size) { Toast.warning('No tests selected', 'Select at least one test from the catalog.'); return; }

    submitBtn.classList.add('btn-loading');
    submitBtn.disabled = true;

    const payload = {
      patient:          selectedPatient.id,
      hospital:         NEXUS.hospitalId || selectedPatient.hospital,
      doctor_name:      document.getElementById('doctor-name')?.value.trim() || '',
      ward:             document.getElementById('ward-input')?.value.trim()   || '',
      bed:              document.getElementById('bed-input')?.value.trim()    || '',
      clinical_info:    document.getElementById('clinical-info')?.value.trim() || '',
      provisional_diagnosis: document.getElementById('diagnosis')?.value.trim() || '',
      emergency_level:  emergencyLevel,
      is_high_risk:     isHighRisk,
      biosafety_warning: isHighRisk ? document.getElementById('biosafety-warning')?.value.trim() || '' : '',
      test_ids:         [...selectedTestIds],
    };

    try {
      const r = await API.post('/laboratory/requests/', payload);
      await API.checkError(r);
      const req = await API.json(r);
      Toast.success('Request Submitted', `Lab ID: ${req.lab_id} · ${req.test_count} test${req.test_count > 1 ? 's' : ''}`);
      resetForm();
    } catch (err) {
      Toast.error('Submission Failed', err.message);
    } finally {
      submitBtn.classList.remove('btn-loading');
      updateSubmitState();
    }
  }

  function resetForm() {
    selectedPatient = null;
    selectedTestIds.clear();
    emergencyLevel  = 'routine';
    isHighRisk      = false;
    patientInput && (patientInput.value = '');
    patientCard?.classList.remove('visible');
    noPatientHint && (noPatientHint.style.display = 'flex');
    document.getElementById('doctor-name')  && (document.getElementById('doctor-name').value  = '');
    document.getElementById('ward-input')   && (document.getElementById('ward-input').value   = '');
    document.getElementById('bed-input')    && (document.getElementById('bed-input').value     = '');
    document.getElementById('clinical-info')&& (document.getElementById('clinical-info').value = '');
    document.getElementById('diagnosis')    && (document.getElementById('diagnosis').value     = '');
    if (highRiskToggle)  { highRiskToggle.checked = false; highRiskRow?.classList.remove('active'); }
    document.querySelectorAll('.priority-pill').forEach(p => p.classList.remove('selected'));
    document.querySelector('.priority-pill[data-level="routine"]')?.classList.add('selected');
    document.querySelectorAll('.test-item').forEach(el => { el.classList.remove('selected'); el.setAttribute('aria-checked','false'); });
    updateSummary();
    updateSubmitState();
    patientInput?.focus();
  }

  /* ════════════════════════════════════════════════════════════
     TODAY'S QUEUE
  ════════════════════════════════════════════════════════════ */
  async function loadQueue() {
    if (!queueTbody) return;
    queueTbody.innerHTML = `<tr><td colspan="7">
      <div class="queue-loading" style="padding:2rem;display:flex;align-items:center;gap:1rem;color:var(--text-muted)">
        <i class="fas fa-spinner" style="animation:spin 1s linear infinite;font-size:18px"></i> Loading queue…
      </div>
    </td></tr>`;
    const today = new Date().toISOString().split('T')[0];
    try {
      const r    = await API.get('/laboratory/requests/', { date_from: today });
      const data = await API.json(r);
      const reqs = data.results ?? data;
      renderQueue(reqs);
    } catch (err) {
      queueTbody.innerHTML = `<tr><td colspan="7"><div class="text-muted-c text-xs" style="padding:2rem">Failed: ${escHtml(err.message)}</div></td></tr>`;
    }
  }

  function renderQueue(items) {
    if (!queueTbody) return;
    document.getElementById('queue-total') && (document.getElementById('queue-total').textContent = `${items.length} total`);
    if (!items.length) {
      queueTbody.innerHTML = `<tr><td colspan="7">
        <div style="display:flex;flex-direction:column;align-items:center;padding:3rem;gap:1rem;color:var(--text-muted);text-align:center">
          <i class="fas fa-inbox" style="font-size:36px;opacity:0.3"></i>
          <p class="text-sm">No requests today yet</p>
        </div>
      </td></tr>`;
      return;
    }
    queueTbody.innerHTML = items.map(req => `
      <tr>
        <td>
          <div style="display:flex;flex-direction:column;gap:2px">
            <span style="font-family:var(--font-mono);font-size:13px;font-weight:700;color:var(--blue-glow)">${escHtml(req.lab_id)}</span>
            ${req.emergency_level === 'emergency' ? '<span class="badge badge-red" style="font-size:10px">STAT</span>' : ''}
          </div>
        </td>
        <td>
          <div style="font-size:var(--text-sm);font-weight:600;color:var(--text-primary)">${escHtml(req.patient_name)}</div>
          <div style="font-size:10px;color:var(--text-muted);font-family:var(--font-mono)">${escHtml(req.patient_pid)}</div>
        </td>
        <td>
          <div style="display:flex;flex-wrap:wrap;gap:3px">
            ${(req.test_names || []).slice(0,3).map(t => `<span class="badge badge-blue" style="font-size:10px">${escHtml(t)}</span>`).join('')}
            ${(req.test_names?.length || 0) > 3 ? `<span class="text-muted-c" style="font-size:10px">+${req.test_names.length-3}</span>` : ''}
          </div>
        </td>
        <td>${emergencyBadge(req.emergency_level)}</td>
        <td>${statusBadge(req.status)}</td>
        <td><span class="text-xs text-secondary-c">${fmt.datetime(req.request_date)}</span></td>
        <td style="text-align:right;white-space:nowrap">
          ${req.status === 'pending' || req.status === 'submitted'
            ? `<a href="/reception/worklist-prep/${req.id}" class="btn btn-sm" style="background:linear-gradient(135deg,#06b6d4,#0284c7);color:#fff;border:none;border-radius:7px;padding:5px 12px;font-size:11px;font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:5px;margin-right:4px" title="Prepare Worklist"><i class="fas fa-vials"></i> Prep</a>`
            : ''
          }
          <a href="/patients/hub/?patient=${req.patient_pid}" class="btn btn-ghost btn-xs" title="View patient">
            <i class="fas fa-user"></i>
          </a>
        </td>
      </tr>
    `).join('');
  }

  /* ─── Filter queue ───────────────────────────────────────────── */
  document.getElementById('queue-search-input')?.addEventListener('input', function () {
    const q = this.value.toLowerCase();
    document.querySelectorAll('#queue-tbody tr').forEach(row => {
      row.style.display = q ? (row.textContent.toLowerCase().includes(q) ? '' : 'none') : '';
    });
  });

  document.getElementById('queue-status-filter')?.addEventListener('change', loadQueue);

  /* ════════════════════════════════════════════════════════════
     HELPERS
  ════════════════════════════════════════════════════════════ */
  function emergencyBadge(lvl) {
    const map = {
      emergency: `<span class="badge badge-red anim-pulse-critical">STAT</span>`,
      urgent:    `<span class="badge badge-orange">Urgent</span>`,
      routine:   `<span class="badge badge-grey">Routine</span>`,
      normal:    `<span class="badge badge-grey">Normal</span>`,
    };
    return map[lvl] ?? `<span class="badge badge-grey">${escHtml(lvl)}</span>`;
  }

  function statusBadge(s) {
    const map = {
      submitted:  `<span class="badge badge-blue">Submitted</span>`,
      received:   `<span class="badge badge-cyan">Received</span>`,
      processing: `<span class="badge badge-orange">Processing</span>`,
      validated:  `<span class="badge badge-green">Validated</span>`,
      cancelled:  `<span class="badge badge-grey">Cancelled</span>`,
    };
    return map[s] ?? `<span class="badge badge-grey">${escHtml(s)}</span>`;
  }

  function initials(name) {
    const p = (name || '?').split(' ');
    return (p[0]?.[0] || '') + (p[1]?.[0] || '');
  }

  function escHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }

  /* ════════════════════════════════════════════════════════════
     BOOT
  ════════════════════════════════════════════════════════════ */
  updateSubmitState();
  loadCatalog();
  patientInput?.focus();

})();
