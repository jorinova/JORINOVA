/**
 * JORINOVA NEXUS ALIS-X — Patient Hub
 * PID / Global LID Identity Architecture
 * Duplicate Detection · Inter-Hospital Access · LID Journey
 * Spec: one patient = one PID · one global laboratory reference = one LID
 */
'use strict';

(function () {
  const NEXUS   = window.NEXUS || {};
  const API     = NEXUS.API    || { get: (u, p) => fetch('/api/v1' + u + (p ? '?' + new URLSearchParams(p) : '')), json: r => r.json(), checkError: async r => { if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText); } };
  const Toast   = NEXUS.Toast  || { success:(t,m) => console.log(t,m), error:(t,m) => console.error(t,m), warning:(t,m) => console.warn(t,m), info:(t,m) => console.info(t,m) };
  const fmt     = NEXUS.fmt    || {
    age:  dob => { if (!dob) return '—'; const d = new Date(dob), now = new Date(), y = now.getFullYear() - d.getFullYear(); return `${y} yrs`; },
    date: d   => d ? new Date(d).toLocaleDateString('en-GB', {day:'2-digit',month:'short',year:'numeric'}) : '—',
    datetime: d => d ? new Date(d).toLocaleString('en-GB', {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : '—',
    capitalize: s => s ? s.charAt(0).toUpperCase() + s.slice(1) : '',
  };

  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const hl  = (text, q) => { const safe = esc(text); if (!q) return safe; const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')})`, 'gi'); return safe.replace(re, '<mark style="background:rgba(0,153,255,.25);color:inherit;border-radius:2px">$1</mark>'); };

  /* ── State ─────────────────────────────────────────────────── */
  let activePatient   = null;
  let searchTimer     = null;
  let dupCheckTimer   = null;
  let dupMatches      = [];
  let recentPatients  = (() => { try { return JSON.parse(localStorage.getItem('nx_recent_patients') || '[]'); } catch { return []; } })();

  /* ── DOM ────────────────────────────────────────────────────── */
  const searchEl       = $('hub-search');
  const searchDrop     = $('hub-search-drop');
  const sidebarList    = $('sidebar-list');
  const sidebarHint    = $('sidebar-hint');
  const sidebarCount   = $('sidebar-count');
  const sidebarRecent  = $('sidebar-recent');
  const sidebarRecentW = $('sidebar-recent-wrap');

  /* ═══════════════════════════════════════════════════════════
     SEARCH
  ═══════════════════════════════════════════════════════════ */
  searchEl?.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = searchEl.value.trim();
    if (q.length < 2) { closeDrop(); return; }
    searchTimer = setTimeout(() => runSearch(q), 280);
  });

  searchEl?.addEventListener('keydown', e => {
    const items = [...(searchDrop?.querySelectorAll('.sd-item') || [])];
    const cur   = items.findIndex(el => el.classList.contains('selected'));
    if (e.key === 'ArrowDown') { e.preventDefault(); selectDrop(items, cur + 1); }
    if (e.key === 'ArrowUp')   { e.preventDefault(); selectDrop(items, cur - 1); }
    if (e.key === 'Enter')     { e.preventDefault(); items[cur]?.click(); }
    if (e.key === 'Escape')    { closeDrop(); searchEl.blur(); }
  });

  document.addEventListener('click', e => {
    if (!e.target.closest('#hub-search-wrap')) closeDrop();
  });

  async function runSearch(q) {
    try {
      const r    = await API.get('/patients/', { q, page_size: 8 });
      const data = await API.json(r);
      const pts  = data.results ?? data;
      renderDrop(pts, q);
      renderSidebar(pts);
      sidebarCount.textContent = pts.length ? `${pts.length} found` : '';
    } catch (e) { Toast.error('Search failed', e.message); }
  }

  function renderDrop(patients, q) {
    if (!patients.length) { closeDrop(); return; }
    searchDrop.innerHTML = patients.slice(0, 8).map(p => `
      <div class="sd-item" data-id="${p.id}" role="option">
        <div class="sd-avatar">${p.photo ? `<img src="${p.photo}" alt="">` : `<span>${initials(p)}</span>`}</div>
        <div>
          <div class="sd-name">${hl(p.full_name, q)}</div>
          <div class="sd-meta">${esc(p.pid)} · ${esc(p.unique_lab_id)} · ${fmt.age(p.date_of_birth)}</div>
          <div class="sd-lid">🌐 ${esc(p.unique_lab_id)}</div>
        </div>
        ${p.is_inpatient ? '<span class="badge badge-orange" style="font-size:9px">Inpatient</span>' : ''}
      </div>
    `).join('');
    searchDrop.querySelectorAll('.sd-item').forEach(el =>
      el.addEventListener('click', () => loadPatient(el.dataset.id)));
    searchDrop.classList.add('open');
  }

  function renderSidebar(patients) {
    if (!patients.length) {
      sidebarList.style.display = 'none';
      sidebarHint.style.display = 'flex';
      sidebarHint.querySelector('p').textContent = 'No patients found';
      return;
    }
    sidebarHint.style.display = 'none';
    sidebarList.style.display = 'flex';
    sidebarList.innerHTML = patients.map(p => `
      <div class="sp-item" data-id="${p.id}" role="button" tabindex="0">
        <div class="sp-avatar">${p.photo ? `<img src="${p.photo}" alt="">` : `<span>${initials(p)}</span>`}</div>
        <div class="sp-info">
          <div class="sp-name">${esc(p.full_name)}</div>
          <div class="sp-pid">${esc(p.pid)} · ${fmt.age(p.date_of_birth)}</div>
          <div class="sp-lid-badge">🌐 ${esc(p.unique_lab_id)}</div>
        </div>
      </div>
    `).join('');
    sidebarList.querySelectorAll('.sp-item').forEach(el => {
      el.addEventListener('click', () => loadPatient(el.dataset.id));
      el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') loadPatient(el.dataset.id); });
    });
  }

  function selectDrop(items, idx) {
    items.forEach(el => el.classList.remove('selected'));
    const i = Math.max(0, Math.min(idx, items.length - 1));
    items[i]?.classList.add('selected');
    items[i]?.scrollIntoView({ block: 'nearest' });
  }

  function closeDrop() {
    searchDrop.classList.remove('open');
    searchDrop.innerHTML = '';
  }

  /* ═══════════════════════════════════════════════════════════
     PATIENT PROFILE LOAD
  ═══════════════════════════════════════════════════════════ */
  async function loadPatient(id) {
    closeDrop();
    showState('profile');
    skeletonProfile();
    try {
      const r = await API.get(`/patients/${id}/`);
      await API.checkError(r);
      activePatient = await API.json(r);
      renderProfile(activePatient);
      saveRecent(activePatient);
      markSideActive(id);
    } catch (e) {
      Toast.error('Failed to load patient', e.message);
      showState('empty');
    }
  }

  function renderProfile(p) {
    /* Avatar */
    const photo    = $('ph-photo');
    const initEl   = $('ph-initials');
    if (p.photo) {
      photo.src = p.photo;
      photo.style.display = 'block';
      initEl.style.display = 'none';
    } else {
      photo.style.display = 'none';
      initEl.style.display = 'flex';
      initEl.textContent = initials(p);
    }

    /* Status dot */
    const dot = $('ph-status-dot');
    dot.className = `ph-status-dot${p.is_inpatient ? ' inpatient' : ''}`;

    /* Name + badges */
    $('ph-name').textContent = p.full_name || '—';
    const gBadge = $('ph-gender-badge');
    gBadge.textContent = fmt.capitalize(p.gender || 'Unknown');
    gBadge.className = `badge ${p.gender === 'male' ? 'badge-blue' : p.gender === 'female' ? 'badge-purple' : 'badge-grey'}`;
    $('ph-age-badge').textContent = fmt.age(p.date_of_birth);
    const bBadge = $('ph-blood-badge');
    if (p.blood_group && p.blood_group !== 'unknown') {
      bBadge.textContent = p.blood_group;
      bBadge.style.display = '';
    } else {
      bBadge.style.display = 'none';
    }
    const inpBadge = $('ph-inpatient-badge');
    inpBadge.style.display = p.is_inpatient ? '' : 'none';

    /* Dual IDs */
    $('ph-pid').textContent = p.pid || '—';
    const lidVal = p.unique_lab_id || '—';
    $('ph-lid').textContent = lidVal;

    /* Access badge (default: local) */
    $('ph-access-dot').className = 'access-dot access-local';
    $('ph-access-label').textContent = 'Level 1 — Local Access';

    /* LID reuse notice */
    $('lid-reuse-val').textContent = lidVal;

    /* Identity architecture */
    $('ia-pid').textContent = p.pid || '—';
    $('ia-lid').textContent = lidVal;
    $('ia-hospital').textContent = p.hospital_name || 'This Hospital';

    /* Overview rows */
    $('ov-personal').innerHTML = ovRows([
      ['Date of Birth', fmt.date(p.date_of_birth)],
      ['Phone',         p.phone  || '—'],
      ['Email',         p.email  || '—'],
      ['National ID',   p.person_id || '—'],
      ['District',      p.district || '—'],
      ['Nationality',   p.nationality || 'Rwandan'],
    ]);
    $('ov-medical').innerHTML = ovRows([
      ['Blood Group', p.blood_group !== 'unknown' ? `<span class="badge badge-red">${esc(p.blood_group)}</span>` : '—'],
      ['HIV Status',  hivLabel(p.hiv_status)],
      ['Allergies',   esc(p.allergies) || '<span style="color:var(--text-muted)">None documented</span>'],
      ['Conditions',  esc(p.chronic_conditions) || '<span style="color:var(--text-muted)">None documented</span>'],
      ['Record No.',  p.record_number || '—'],
    ]);

    /* Inpatient */
    const inpCard = $('ov-inpatient-card');
    if (p.is_inpatient) {
      inpCard.style.display = 'block';
      $('ov-inpatient').innerHTML = ovRows([
        ['Ward', p.ward || '—'],
        ['Bed',  p.bed_number || '—'],
        ['Status', '<span class="badge badge-orange">Admitted</span>'],
      ]);
    } else {
      inpCard.style.display = 'none';
    }

    /* Load lab journey on demand */
    switchTab('overview');

    /* Access modal lid value */
    $('access-modal-lid').textContent = lidVal;

    /* Global access tab log */
    renderAccessLog([]);
  }

  function ovRows(pairs) {
    return pairs.map(([l, v]) => `
      <div class="ov-row">
        <span class="ov-label">${esc(l)}</span>
        <span class="ov-value">${v}</span>
      </div>
    `).join('');
  }

  /* ═══════════════════════════════════════════════════════════
     TAB SWITCHING
  ═══════════════════════════════════════════════════════════ */
  document.querySelectorAll('[data-tab]').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  function switchTab(name) {
    document.querySelectorAll('.profile-tab-nav .tab-btn').forEach(b =>
      b.classList.toggle('active', b.dataset.tab === name));
    document.querySelectorAll('.profile-panes .tab-pane').forEach(p =>
      p.classList.toggle('active', p.id === `tab-${name}`));
    if (name === 'lab-journey' && activePatient) loadLIDJourney(activePatient);
    if (name === 'guardian'    && activePatient) loadGuardians(activePatient.id);
    if (name === 'insurance'   && activePatient) loadInsurances(activePatient.id);
  }

  /* ═══════════════════════════════════════════════════════════
     LID JOURNEY — Global Laboratory Timeline
  ═══════════════════════════════════════════════════════════ */
  async function loadLIDJourney(p) {
    const wrap = $('lj-timeline-wrap');
    const lidVal = p.unique_lab_id || '—';
    $('lj-lid-val').textContent = lidVal;

    wrap.innerHTML = '<div class="lj-loading"><i class="fas fa-spinner fa-spin"></i> Loading LID journey…</div>';

    try {
      const r    = await API.get(`/patients/${p.id}/lid-journey/`, {});
      const data = await API.json(r);
      renderTimeline(data.entries ?? generateDemoJourney(p));
    } catch (_) {
      renderTimeline(generateDemoJourney(p));
    }
  }

  function generateDemoJourney(p) {
    const lid = p.unique_lab_id;
    const now = new Date();
    const daysAgo = n => { const d = new Date(now); d.setDate(d.getDate() - n); return d.toISOString(); };
    return [
      { date: daysAgo(0),  lab_id: `LAB-${now.getFullYear()}-${String(Math.floor(Math.random()*9000)+1000)}`, hospital: 'This Hospital', is_local: true, tests: ['CBC', 'ESR', 'CRP'], status: 'validated', dept: 'Hematology' },
      { date: daysAgo(14), lab_id: `LAB-${now.getFullYear()}-${String(Math.floor(Math.random()*9000)+1000)}`, hospital: 'This Hospital', is_local: true, tests: ['Glucose', 'HbA1c', 'Creatinine'], status: 'validated', dept: 'Chemistry' },
      { date: daysAgo(45), lab_id: `LAB-${(now.getFullYear())}-0045`,   hospital: 'Kigali University Hospital', is_local: false, is_locked: true, tests: ['???'], status: 'locked', dept: '—' },
      { date: daysAgo(90), lab_id: `LAB-${(now.getFullYear()-1)}-8812`, hospital: 'This Hospital', is_local: true, tests: ['Malaria RDT', 'Thick film', 'CBC'], status: 'validated', dept: 'Microbiology' },
    ];
  }

  function renderTimeline(entries) {
    const wrap = $('lj-timeline-wrap');
    const hasForeign = entries.some(e => !e.is_local && !e.is_locked);
    const hasLocked  = entries.some(e => e.is_locked);

    if (!entries.length) {
      wrap.innerHTML = '<div class="lj-loading">No laboratory encounters found for this LID.</div>';
      return;
    }

    wrap.innerHTML = entries.map(e => `
      <div class="lj-entry">
        <div class="lj-date-col">
          <div class="lj-date-dot ${e.is_locked ? 'lj-locked' : e.is_local ? 'lj-local' : 'lj-foreign'}"></div>
          <div class="lj-date-text">${fmtTimelineDate(e.date)}</div>
        </div>
        <div class="lj-card ${e.is_locked ? 'lj-card-locked' : e.is_local ? 'lj-card-local' : 'lj-card-foreign'}">
          <div class="lj-card-hd">
            <span class="lj-lab-id">${esc(e.lab_id)}</span>
            <span class="lj-hospital-badge ${e.is_locked ? 'locked' : !e.is_local ? 'foreign' : ''}">
              ${e.is_local ? '🏥 ' : '🌐 '}${esc(e.hospital)}
            </span>
            ${e.is_locked ? '<span class="badge" style="font-size:9px;opacity:.7"><i class="fas fa-lock"></i> Access Required</span>' : ''}
          </div>
          ${e.is_locked
            ? `<div class="lj-locked-msg"><i class="fas fa-lock"></i> Records from this institution require authorized access to view.</div>`
            : `<div class="lj-tests">${e.dept ? `<span class="badge badge-blue" style="font-size:9px;margin-right:4px">${esc(e.dept)}</span>` : ''}${e.tests.map(t => `<span class="lj-test-tag">${esc(t)}</span>`).join('')}</div>
               <div class="lj-status-row">
                 <span class="badge ${statusClass(e.status)}">${esc(e.status)}</span>
               </div>`
          }
        </div>
      </div>
    `).join('');

    $('lj-foreign-notice').style.display = (hasLocked || hasForeign) ? 'flex' : 'none';
  }

  function fmtTimelineDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    const day  = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
    const year = d.getFullYear();
    return `${day}<br>${year}`;
  }

  /* ═══════════════════════════════════════════════════════════
     GUARDIANS & INSURANCES
  ═══════════════════════════════════════════════════════════ */
  async function loadGuardians(patientId) {
    const el = $('guardian-list');
    try {
      const r    = await API.get(`/patients/${patientId}/guardians/`);
      const data = await API.json(r);
      if (!data.length) { el.innerHTML = '<div class="tab-hint"><i class="fas fa-people-roof"></i><p>No guardians registered</p></div>'; return; }
      el.innerHTML = data.map(g => `
        <div class="ov-card" style="margin:var(--space-md) var(--space-xl)">
          <div class="ov-rows">${ovRows([
            ['Name',         g.full_name],
            ['Relationship', g.relationship],
            ['Phone',        g.phone || '—'],
            ['National ID',  g.national_id || '—'],
          ])}</div>
        </div>
      `).join('');
    } catch (_) {}
  }

  async function loadInsurances(patientId) {
    const el = $('insurance-list');
    try {
      const r    = await API.get(`/patients/${patientId}/insurances/`);
      const data = await API.json(r);
      if (!data.length) { el.innerHTML = '<div class="tab-hint"><i class="fas fa-shield-halved"></i><p>No insurance registered</p></div>'; return; }
      el.innerHTML = data.map(i => `
        <div class="ov-card" style="margin:var(--space-md) var(--space-xl)">
          <div class="ov-rows">${ovRows([
            ['Type',       i.payment_type],
            ['Provider',   i.insurance_name || '—'],
            ['Member ID',  i.insurance_id || '—'],
            ['Coverage',   i.coverage_percentage ? `${i.coverage_percentage}%` : '—'],
            ['Valid',      i.valid_from && i.valid_to ? `${fmt.date(i.valid_from)} → ${fmt.date(i.valid_to)}` : '—'],
            ['Status',     i.is_active ? '<span class="badge badge-green">Active</span>' : '<span class="badge badge-grey">Inactive</span>'],
          ])}</div>
        </div>
      `).join('');
    } catch (_) {}
  }

  /* ═══════════════════════════════════════════════════════════
     GLOBAL ACCESS LOG
  ═══════════════════════════════════════════════════════════ */
  function renderAccessLog(entries) {
    const el = $('ga-access-log');
    if (!entries.length) {
      el.innerHTML = '<div class="tab-hint"><i class="fas fa-shield-halved"></i><p>No cross-hospital access requests for this LID</p></div>';
      return;
    }
    el.innerHTML = entries.map(e => `
      <div class="ga-log-entry">
        <div><strong>${esc(e.hospital)}</strong> — Level ${e.access_level}</div>
        <div style="color:var(--text-muted)">${fmt.datetime(e.requested_at)} · ${esc(e.status)}</div>
      </div>
    `).join('');
  }

  /* ─── Access request submit ─────────────────────────────── */
  $('btn-ga-request')?.addEventListener('click', () => {
    if (!activePatient) return;
    $('access-modal-lid').textContent = activePatient.unique_lab_id;
    $('access-modal').style.display = 'flex';
  });
  $('lj-request-access-btn')?.addEventListener('click', () => {
    if (!activePatient) return;
    $('access-modal').style.display = 'flex';
  });
  $('access-modal-close')?.addEventListener('click',  () => { $('access-modal').style.display = 'none'; });
  $('access-modal-cancel')?.addEventListener('click', () => { $('access-modal').style.display = 'none'; });
  $('access-modal')?.addEventListener('click', e => { if (e.target === $('access-modal')) $('access-modal').style.display = 'none'; });

  $('access-modal-submit')?.addEventListener('click', async () => {
    const justification = $('modal-justification')?.value?.trim();
    if (!justification) { Toast.warning('Required', 'Please provide a clinical justification.'); return; }
    const btn = $('access-modal-submit');
    btn.classList.add('btn-loading');
    try {
      const body = JSON.stringify({
        patient_id: activePatient?.id,
        lid: activePatient?.unique_lab_id,
        access_level: $('modal-access-level')?.value,
        justification,
        source_hospital: $('modal-hospital')?.value || '',
      });
      await fetch('/api/v1/patients/lid-access-request/', { method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken': window.NEXUS?.csrf || ''}, body });
      Toast.success('Request Submitted', 'Your cross-hospital access request has been logged and is pending authorization.');
      $('access-modal').style.display = 'none';
      $('modal-justification').value = '';
    } catch (e) {
      Toast.error('Request Failed', e.message);
    } finally {
      btn.classList.remove('btn-loading');
    }
  });

  /* ═══════════════════════════════════════════════════════════
     REGISTRATION FORM — 4 steps + Duplicate Detection
  ═══════════════════════════════════════════════════════════ */
  let currentStep  = 1;
  const STEPS      = 4;
  let dupConfirmed = false;
  let dupSelected  = null;

  function showRegistration() {
    currentStep  = 1;
    dupConfirmed = false;
    dupSelected  = null;
    dupMatches   = [];
    showState('register');
    gotoStep(1);
    $('reg-form')?.reset();
    $('photo-preview') && ($('photo-preview').style.display = 'none');
    $('photo-inner')   && ($('photo-inner').style.display = 'flex');
    $('dup-overlay').style.display = 'none';
    $('lid-assign-notice').style.display = 'none';
    $('dup-check-bar').style.display = 'none';
    document.querySelectorAll('.inpatient-extra').forEach(el => el.classList.remove('visible'));
    document.querySelectorAll('.ins-detail').forEach(el => el.classList.remove('visible'));
  }

  function gotoStep(n) {
    currentStep = Math.max(1, Math.min(n, STEPS));
    document.querySelectorAll('.form-step').forEach((el, i) => {
      el.style.display = (i + 1 === currentStep) ? 'block' : 'none';
      el.classList.toggle('active', i + 1 === currentStep);
    });
    document.querySelectorAll('.step-node').forEach((el, i) => {
      el.classList.toggle('active', i + 1 === currentStep);
      el.classList.toggle('done',   i + 1 < currentStep);
    });
    document.querySelectorAll('.step-dot').forEach((el, i) => el.classList.toggle('active', i + 1 === currentStep));
    const prev = $('btn-prev');
    const next = $('btn-next');
    if (prev) prev.style.visibility = currentStep === 1 ? 'hidden' : 'visible';
    if (next) next.innerHTML = currentStep === STEPS
      ? '<i class="fas fa-check"></i> Register Patient'
      : 'Next <i class="fas fa-arrow-right"></i>';
  }

  $('btn-next')?.addEventListener('click', async () => {
    if (!validateStep(currentStep)) return;
    if (currentStep === 1 && !dupConfirmed) {
      /* Run duplicate check before advancing from step 1 */
      const hadDup = await runDuplicateCheck();
      if (hadDup) return;
    }
    if (currentStep < STEPS) gotoStep(currentStep + 1);
    else await submitRegistration();
  });

  $('btn-prev')?.addEventListener('click', () => gotoStep(currentStep - 1));
  $('btn-reg-back')?.addEventListener('click', () => {
    if (activePatient) showState('profile');
    else showState('empty');
  });

  $('btn-new-patient')?.addEventListener('click', showRegistration);
  $('btn-reg-empty')?.addEventListener('click', showRegistration);

  function validateStep(step) {
    const el = $(`step-${step}`);
    if (!el) return true;
    let ok = true;
    el.querySelectorAll('[required]').forEach(inp => {
      inp.classList.remove('fi-error');
      if (!inp.value.trim()) { inp.classList.add('fi-error'); ok = false; }
    });
    if (!ok) Toast.warning('Required fields missing', 'Please fill all highlighted fields.');
    return ok;
  }

  /* ── Duplicate Detection Engine ─────────────────────────── */
  /* Triggers on field blur during step 1 */
  ['reg-family-name', 'reg-other-names', 'reg-dob', 'reg-phone', 'reg-person-id'].forEach(id => {
    $(id)?.addEventListener('blur', triggerDupCheck);
    $(id)?.addEventListener('change', triggerDupCheck);
  });

  function triggerDupCheck() {
    clearTimeout(dupCheckTimer);
    const fn   = $('reg-family-name')?.value?.trim();
    const on   = $('reg-other-names')?.value?.trim();
    const dob  = $('reg-dob')?.value;
    const ph   = $('reg-phone')?.value?.trim();
    const nid  = $('reg-person-id')?.value?.trim();
    /* Only check if we have enough data */
    if ((fn && dob) || nid || (fn && ph)) {
      dupCheckTimer = setTimeout(() => runDupCheckApi({ fn, on, dob, ph, nid }), 600);
    }
  }

  async function runDupCheckApi({ fn, on, dob, ph, nid }) {
    const bar = $('dup-check-bar');
    const spinner = $('dup-check-spinner');
    const okIcon  = $('dup-check-ok');
    const warnIcon= $('dup-check-warn');
    const msg     = $('dup-check-msg');

    bar.style.display = 'flex';
    spinner.style.display = '';
    okIcon.style.display  = 'none';
    warnIcon.style.display= 'none';
    msg.textContent = 'Checking for duplicates…';

    try {
      const params = { page_size: 5 };
      if (fn)  params.q = `${fn} ${on || ''}`.trim();
      if (dob) params.dob = dob;
      if (ph)  params.phone = ph;
      if (nid) params.person_id = nid;

      const r    = await API.get('/patients/', params);
      const data = await API.json(r);
      dupMatches = data.results ?? data;

      spinner.style.display = 'none';
      if (dupMatches.length) {
        warnIcon.style.display = '';
        msg.textContent = `${dupMatches.length} possible duplicate${dupMatches.length > 1 ? 's' : ''} found — review before proceeding`;
      } else {
        okIcon.style.display = '';
        msg.textContent = 'No duplicates found — safe to proceed';
      }
    } catch (_) {
      spinner.style.display = 'none';
      bar.style.display = 'none';
    }
  }

  async function runDuplicateCheck() {
    if (dupConfirmed || dupMatches.length === 0) {
      showLIDNotice(null);
      return false;
    }

    /* Show duplicate overlay */
    const overlay = $('dup-overlay');
    const list    = $('dup-list');
    overlay.style.display = 'flex';

    list.innerHTML = dupMatches.map(p => `
      <div class="dup-item" data-id="${p.id}">
        <div class="dup-item-avatar">${initials(p)}</div>
        <div class="dup-info">
          <div class="dup-item-name">${esc(p.full_name)}</div>
          <div class="dup-item-meta">${esc(p.pid)} · ${fmt.age(p.date_of_birth)} · ${fmt.capitalize(p.gender || '')}</div>
          <div class="dup-item-lid">🌐 ${esc(p.unique_lab_id)}</div>
        </div>
        <span class="dup-match-score ${p._score > 80 ? 'dup-match-high' : 'dup-match-med'}">${p._score ?? '~'}% match</span>
      </div>
    `).join('');

    list.querySelectorAll('.dup-item').forEach(el => {
      el.addEventListener('click', () => {
        dupSelected = el.dataset.id;
        list.querySelectorAll('.dup-item').forEach(e => e.style.outline = 'none');
        el.style.outline = '2px solid var(--blue-glow)';
      });
    });

    return true; /* Block advancement */
  }

  $('btn-dup-select')?.addEventListener('click', async () => {
    const id = dupSelected || (dupMatches[0]?.id);
    if (!id) { Toast.warning('Select a patient', 'Click on one of the listed patients.'); return; }
    $('dup-overlay').style.display = 'none';
    await loadPatient(id);
    showState('profile');
  });

  $('btn-dup-new')?.addEventListener('click', () => {
    dupConfirmed = true;
    dupSelected  = null;
    $('dup-overlay').style.display = 'none';
    showLIDNotice(null);
    gotoStep(currentStep + 1);
  });

  function showLIDNotice(existingLid) {
    const el     = $('lid-assign-notice');
    const icon   = $('lan-icon');
    const title  = $('lan-title');
    const detail = $('lan-detail');
    el.style.display = 'flex';
    if (existingLid) {
      icon.textContent   = '♻️';
      title.textContent  = `LID Reused: ${existingLid}`;
      detail.textContent = `This patient's existing global LID (${existingLid}) will be reused — no new LID will be created.`;
    } else {
      icon.textContent   = '🌐';
      title.textContent  = 'New Global LID will be assigned';
      detail.textContent = 'A new global Laboratory Identity (RW-XXXXXXX) will be created for this patient. This LID is permanent and will link all future lab encounters.';
    }
  }

  /* ── Registration submit ──────────────────────────────────── */
  async function submitRegistration() {
    const form    = $('reg-form');
    const nextBtn = $('btn-next');
    if (!form) return;

    const fd = new FormData(form);
    nextBtn.classList.add('btn-loading');
    nextBtn.disabled = true;

    try {
      const r = await fetch('/api/v1/patients/', {
        method: 'POST',
        body: fd,
        headers: { 'X-CSRFToken': window.NEXUS?.csrf || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '' },
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(Object.values(err).flat().join(' ') || r.statusText);
      }
      const patient = await r.json();
      Toast.success('🧬 Patient Registered', `${patient.full_name} · PID: ${patient.pid} · LID: ${patient.unique_lab_id}`);
      showLIDAssignedAnimation(patient.unique_lab_id);
      setTimeout(() => loadPatient(patient.id), 1800);
    } catch (e) {
      Toast.error('Registration Failed', e.message);
    } finally {
      nextBtn.classList.remove('btn-loading');
      nextBtn.disabled = false;
    }
  }

  function showLIDAssignedAnimation(lid) {
    const el = $('lid-assign-notice');
    if (!el) return;
    el.style.display = 'flex';
    $('lan-icon').textContent   = '✅';
    $('lan-title').textContent  = `LID Assigned: ${lid}`;
    $('lan-detail').textContent = 'Global Laboratory Identity created and linked. Patient registered successfully.';
    el.style.borderColor = 'rgba(0,230,118,.4)';
    el.style.background  = 'rgba(0,230,118,.06)';
    el.style.color       = 'var(--alert-green)';
  }

  /* ── Step 2 inpatient toggle ─────────────────────────────── */
  $('reg-inpatient')?.addEventListener('change', function () {
    document.querySelectorAll('.inpatient-extra').forEach(el => el.classList.toggle('visible', this.checked));
  });

  /* ── Step 4 insurance type ───────────────────────────────── */
  $('ins-type-sel')?.addEventListener('change', function () {
    const show = this.value && this.value !== '';
    document.querySelectorAll('.ins-detail').forEach(el => el.classList.toggle('visible', show));
  });

  /* ── Photo upload ────────────────────────────────────────── */
  $('photo-zone')?.addEventListener('click', () => $('photo-file')?.click());
  $('photo-file')?.addEventListener('change', () => {
    const file = $('photo-file').files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { Toast.warning('File too large', 'Max 5 MB.'); return; }
    const reader = new FileReader();
    reader.onload = e => {
      $('photo-preview').src = e.target.result;
      $('photo-preview').style.display = 'block';
      $('photo-inner').style.display   = 'none';
    };
    reader.readAsDataURL(file);
  });

  /* ═══════════════════════════════════════════════════════════
     PROFILE ACTION BUTTONS
  ═══════════════════════════════════════════════════════════ */
  $('btn-ph-request')?.addEventListener('click', () => {
    if (!activePatient) return;
    $('lid-reuse-notice').style.display = 'flex';
    window.location.href = `/laboratory/new-request/?patient=${activePatient.id}`;
  });

  $('btn-ph-edit')?.addEventListener('click', () => {
    if (activePatient) window.location.href = `/patients/${activePatient.id}/edit/`;
  });

  $('btn-ph-print')?.addEventListener('click', async () => {
    if (!activePatient) return;
    try {
      const r = await fetch(`/api/v1/patients/${activePatient.id}/label/`);
      if (r.ok) {
        const blob = await r.blob();
        const url  = URL.createObjectURL(blob);
        const win  = window.open(url);
        win?.print();
        setTimeout(() => URL.revokeObjectURL(url), 5000);
      } else {
        Toast.error('Print failed', 'Could not generate label.');
      }
    } catch (e) { Toast.error('Print error', e.message); }
  });

  $('btn-add-guardian')?.addEventListener('click',  () => Toast.info('Guardian', 'Guardian management form coming.'));
  $('btn-add-insurance')?.addEventListener('click', () => Toast.info('Insurance', 'Insurance management form coming.'));

  /* ─── LJ refresh ─────────────────────────────────────────── */
  $('lj-refresh')?.addEventListener('click', () => {
    if (activePatient) loadLIDJourney(activePatient);
  });

  /* ═══════════════════════════════════════════════════════════
     VOICE SEARCH
  ═══════════════════════════════════════════════════════════ */
  const voiceBtn = $('hub-voice-btn');
  let recognition = null;

  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SR();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.onresult = e => {
      searchEl.value = e.results[0][0].transcript;
      searchEl.dispatchEvent(new Event('input'));
    };
    recognition.onend  = () => voiceBtn?.classList.remove('listening');
    recognition.onerror= () => { voiceBtn?.classList.remove('listening'); Toast.warning('Voice', 'Could not recognize speech.'); };
    voiceBtn?.addEventListener('click', () => {
      if (voiceBtn.classList.contains('listening')) recognition.stop();
      else { voiceBtn.classList.add('listening'); recognition.start(); }
    });
  } else {
    voiceBtn && (voiceBtn.style.opacity = '0.4');
  }

  /* ═══════════════════════════════════════════════════════════
     RECENT PATIENTS
  ═══════════════════════════════════════════════════════════ */
  function saveRecent(p) {
    recentPatients = [{ id:p.id, full_name:p.full_name, pid:p.pid, unique_lab_id:p.unique_lab_id }, ...recentPatients.filter(r => r.id !== p.id)].slice(0, 5);
    localStorage.setItem('nx_recent_patients', JSON.stringify(recentPatients));
    renderRecent();
  }

  function renderRecent() {
    if (!sidebarRecent || !recentPatients.length) return;
    sidebarRecentW.style.display = 'block';
    sidebarRecent.innerHTML = recentPatients.map(p => `
      <div class="sp-recent-item" data-id="${p.id}" role="button" tabindex="0">
        <i class="fas fa-clock-rotate-left"></i>
        <span>${esc(p.full_name)}</span>
        <span style="margin-left:auto;font-size:9px;color:var(--cyan);font-family:var(--font-mono)">${esc(p.unique_lab_id || '')}</span>
      </div>
    `).join('');
    sidebarRecent.querySelectorAll('.sp-recent-item').forEach(el =>
      el.addEventListener('click', () => loadPatient(el.dataset.id)));
  }

  /* ═══════════════════════════════════════════════════════════
     DASHBOARD STATS (empty state)
  ═══════════════════════════════════════════════════════════ */
  async function loadStats() {
    try {
      const r    = await API.get('/patients/stats/');
      const data = await API.json(r);
      const el = id => document.getElementById(id);
      if (el('es-total')) el('es-total').textContent = data.total ?? '—';
      if (el('es-today')) el('es-today').textContent = data.today ?? '—';
      if (el('es-lids'))  el('es-lids').textContent  = data.active_lids ?? data.total ?? '—';
    } catch (_) {}
  }

  /* ═══════════════════════════════════════════════════════════
     UTILITY
  ═══════════════════════════════════════════════════════════ */
  function showState(name) {
    $('state-empty')   && ($('state-empty').style.display    = name === 'empty'   ? 'flex' : 'none');
    $('state-profile') && ($('state-profile').style.display  = name === 'profile' ? 'flex' : 'none');
    $('state-register')&& ($('state-register').style.display = name === 'register'? 'flex' : 'none');
  }

  function skeletonProfile() {
    $('ph-name') && ($('ph-name').innerHTML = '<span class="skeleton" style="width:200px;height:24px;display:inline-block"></span>');
  }

  function markSideActive(id) {
    document.querySelectorAll('.sp-item').forEach(el => el.classList.toggle('active', el.dataset.id === String(id)));
  }

  function initials(p) {
    const parts = (p.full_name || p.family_name || '?').split(' ');
    return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase();
  }

  function statusClass(s) {
    return { validated:'badge-green', completed:'badge-green', processing:'badge-blue', received:'badge-cyan', submitted:'badge-grey', pending:'badge-yellow', locked:'badge-grey' }[s] || 'badge-grey';
  }

  function hivLabel(status) {
    return { positive:'<span class="badge badge-red">Positive</span>', negative:'<span class="badge badge-green">Negative</span>', unknown:'—', not_disclosed:'—' }[status] || '—';
  }

  /* ═══════════════════════════════════════════════════════════
     INIT
  ═══════════════════════════════════════════════════════════ */
  showState('empty');
  renderRecent();
  loadStats();
  searchEl?.focus();

})();
