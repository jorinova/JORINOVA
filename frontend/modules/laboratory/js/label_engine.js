/**
 * JORINOVA NEXUS ALIS-X — Label Print Engine
 * Tube label · Large sticker · Wristband · Report header
 * Barcode: Code 128 via JsBarcode · QR code via QRCode.js
 * Spec: color by dept/specimen, barcode, QR, LID, shift-based ID, high-risk flag
 */
'use strict';

(function () {
  const NEXUS = window.NEXUS || {};
  const API   = NEXUS.API   || { get:(u,p)=>fetch('/api/v1'+u+(p?'?'+new URLSearchParams(p):'')), json:r=>r.json() };
  const Toast = NEXUS.Toast || { success:(t,m)=>console.log(t,m), error:(t,m)=>console.error(t,m), warning:(t,m)=>console.warn(t,m) };
  const CSRF  = () => window.NEXUS?.csrf || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  const esc   = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const $     = id => document.getElementById(id);

  /* ── Tube color map ────────────────────────────────────────── */
  const TUBE_COLORS = {
    purple_edta:     { bg:'#9B59B6', text:'#fff', name:'EDTA' },
    red_plain:       { bg:'#E74C3C', text:'#fff', name:'Plain' },
    yellow_sst:      { bg:'#F39C12', text:'#fff', name:'SST' },
    blue_citrate:    { bg:'#2980B9', text:'#fff', name:'Citrate' },
    green_heparin:   { bg:'#27AE60', text:'#fff', name:'Heparin' },
    grey_fluoride:   { bg:'#95A5A6', text:'#fff', name:'Fluoride' },
    urine_container: { bg:'#F1C40F', text:'#333', name:'Urine' },
    stool_container: { bg:'#784212', text:'#fff', name:'Stool' },
    swab:            { bg:'#EB984E', text:'#fff', name:'Swab' },
    other:           { bg:'#BDC3C7', text:'#333', name:'Other' },
  };

  /* ── Dept color map (fallback) ─────────────────────────────── */
  const DEPT_COLORS = {
    Hematology:   '#E74C3C', Chemistry:'#3498DB', Microbiology:'#2ECC71',
    Serology:     '#9B59B6', 'Blood Bank':'#C0392B', Molecular:'#1ABC9C',
    Coagulation:  '#E67E22', Urinalysis:'#F1C40F', Immunology:'#8E44AD',
    Parasitology: '#27AE60', default:'#2C3E50',
  };

  /* ── State ─────────────────────────────────────────────────── */
  let activeSize    = 'tube';
  let labelQueue    = [];      // All requests in queue
  let activeLabelData = null;  // Labels for currently selected request
  let selectedLabels  = new Set();
  let printedToday  = 0;

  /* ── DOM ─────────────────────────────────────────────────────── */
  const queueList   = $('lpc-queue-list');
  const previewEmpty = $('lpc-preview-empty');
  const previewActive = $('lpc-preview-active');
  const labelsGrid  = $('lpc-labels-grid');
  const printFrame  = $('print-frame');
  const copies      = () => parseInt($('lpc-copies')?.value || '1');

  /* ════════════════════════════════════════════════════════════
     QUEUE LOAD
  ════════════════════════════════════════════════════════════ */
  async function loadQueue() {
    if (queueList) queueList.innerHTML = '<div class="lpc-hint"><i class="fas fa-spinner fa-spin" style="font-size:24px;opacity:.3"></i><p>Loading…</p></div>';

    const filter = $('lpc-filter-status')?.value || 'pending_label';
    const dept   = $('lpc-filter-dept')?.value || '';
    const search = $('lpc-search')?.value?.trim() || '';

    const params = { page_size: 100 };
    if (filter === 'pending_label') { params.status = 'submitted,received'; }
    else if (filter === 'all_today') { params.date_from = new Date().toISOString().slice(0,10); }
    else if (filter === 'emergency') { params.emergency_level = 'emergency'; }
    if (dept)   params.department = dept;
    if (search) params.search     = search;

    try {
      const r    = await API.get('/laboratory/requests/', params);
      const data = await API.json(r);
      labelQueue = data.results ?? data;
      renderQueue(labelQueue);
      updateKPIs(labelQueue);
    } catch (e) {
      if (queueList) queueList.innerHTML = `<div class="lpc-hint"><p>Error: ${esc(e.message)}</p></div>`;
    }
  }

  function renderQueue(requests) {
    if (!queueList) return;
    $('queue-count') && ($('queue-count').textContent = `${requests.length}`);

    if (!requests.length) {
      queueList.innerHTML = '<div class="lpc-hint"><i class="fas fa-check-circle" style="font-size:28px;color:var(--alert-green);opacity:.5"></i><p>No pending labels</p></div>';
      return;
    }

    queueList.innerHTML = requests.map(req => {
      const tubes = getTubeColors(req);
      const isSTAT = req.emergency_level === 'emergency';
      return `<div class="lpc-queue-item" data-id="${req.id}">
        <div class="lqi-info">
          <div class="lqi-name">${esc(req.patient_name || '—')}</div>
          <div class="lqi-id">${esc(req.lab_id)}${isSTAT ? ' <span class="lqi-stat-badge">STAT</span>' : ''}</div>
          <div class="lqi-meta">${esc((req.test_names||[]).slice(0,3).join(', '))}${(req.test_names||[]).length > 3 ? ` +${req.test_names.length-3}` : ''}</div>
          <div class="lqi-tubes">${tubes.map(t => `<div class="lqi-tube-dot" style="background:${t}" title="${t}"></div>`).join('')}</div>
        </div>
      </div>`;
    }).join('');

    queueList.querySelectorAll('.lpc-queue-item').forEach(el =>
      el.addEventListener('click', () => {
        queueList.querySelectorAll('.lpc-queue-item').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
        const id = parseInt(el.dataset.id);
        const req = labelQueue.find(r => r.id === id);
        if (req) loadLabelsForRequest(req);
      })
    );
  }

  function getTubeColors(req) {
    if (req.tube_types && Array.isArray(req.tube_types)) {
      return req.tube_types.map(t => TUBE_COLORS[t]?.bg || '#BDC3C7');
    }
    return ['#BDC3C7'];
  }

  function updateKPIs(requests) {
    const stat    = requests.filter(r => r.emergency_level === 'emergency').length;
    $('kpi-pending') && ($('kpi-pending').textContent = requests.length);
    $('kpi-printed') && ($('kpi-printed').textContent = printedToday);
    $('kpi-stat')    && ($('kpi-stat').textContent    = stat);
  }

  /* ════════════════════════════════════════════════════════════
     LOAD LABELS FOR A REQUEST
  ════════════════════════════════════════════════════════════ */
  async function loadLabelsForRequest(req) {
    previewEmpty.style.display  = 'none';
    previewActive.style.display = 'block';
    labelsGrid.innerHTML = '<div style="width:100%;text-align:center;padding:var(--space-xl);color:var(--text-muted)"><i class="fas fa-spinner fa-spin"></i> Generating labels…</div>';
    selectedLabels.clear();
    updateSelectedCount();

    try {
      const r    = await API.get(`/laboratory/requests/${req.id}/labels/`);
      const data = await API.json(r);
      activeLabelData = data.labels ?? [];

      $('lpc-preview-patient').innerHTML = `
        <span>${esc(data.patient_name)}</span>
        <span class="badge badge-blue" style="font-size:10px;margin-left:8px">${esc(data.lab_id)}</span>
        ${data.emergency === 'emergency' ? '<span class="badge badge-red" style="font-size:9px;margin-left:4px">🚨 STAT</span>' : ''}
        <span style="font-size:var(--text-xs);color:var(--text-muted);margin-left:8px">${activeLabelData.length} label${activeLabelData.length !== 1 ? 's' : ''}</span>
      `;

      renderLabelCards(activeLabelData);

      // Auto-select all
      activeLabelData.forEach((_, i) => selectedLabels.add(i));
      updateSelectedCount();
      refreshCardSelections();
    } catch (e) {
      labelsGrid.innerHTML = `<div style="width:100%;text-align:center;padding:var(--space-xl);color:var(--alert-red)">❌ ${esc(e.message)}</div>`;
    }
  }

  /* ════════════════════════════════════════════════════════════
     RENDER LABEL CARDS (screen preview)
  ════════════════════════════════════════════════════════════ */
  function renderLabelCards(labels) {
    labelsGrid.innerHTML = '';
    labels.forEach((lbl, idx) => {
      const card = buildLabelCard(lbl, idx);
      labelsGrid.appendChild(card);
      renderBarcode(card, lbl);
      renderQR(card, lbl);
    });
  }

  function buildLabelCard(lbl, idx) {
    const tube  = TUBE_COLORS[lbl.tube_type] || TUBE_COLORS.other;
    const dept  = lbl.department || 'Unknown';
    const deptColor = DEPT_COLORS[dept] || DEPT_COLORS.default;
    const isHR  = lbl.is_high_risk;
    const shift = NEXUS.ShiftEngine?.current?.name || 'Shift';
    const now   = new Date();
    const timeStr = now.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'2-digit'}) + ' ' + now.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});

    const wrap = document.createElement('div');
    wrap.className = 'label-card-outer';
    wrap.innerHTML = `
      <div class="label-card" data-size="${activeSize}" data-idx="${idx}" id="lcard-${idx}">

        <!-- Selection checkbox -->
        <div class="lc-select-check" id="chk-${idx}"></div>

        <!-- Tube color band -->
        <div class="lc-tube-band" style="background:${tube.bg}"></div>

        ${isHR ? '<div class="lc-high-risk">☣️ HIGH RISK / BSL-2 — HANDLE WITH CARE</div>' : ''}

        <!-- Hospital + Dept header -->
        <div class="lc-header">
          <div class="lc-hospital">${esc(lbl.hospital_name || 'NEXUS Hospital')}</div>
          <span class="lc-dept-badge" style="background:${deptColor}">${esc(lbl.dept_abbr || dept.slice(0,4).toUpperCase())}</span>
        </div>

        <!-- Patient -->
        <div class="lc-patient">
          <div class="lc-patient-name">${esc(lbl.patient_name || '—')}</div>
          <div class="lc-patient-meta">
            <span>${lbl.patient_dob || '—'}</span>
            <span>${lbl.patient_gender || ''}</span>
            <span>${lbl.patient_age ? lbl.patient_age + 'y' : ''}</span>
          </div>
          <div class="lc-patient-ids">
            <span class="lc-id-chip">PID: ${esc(lbl.patient_pid || '—')}</span>
            ${lbl.patient_lid ? `<span class="lc-id-chip lc-lid-chip">🌐 ${esc(lbl.patient_lid)}</span>` : ''}
          </div>
        </div>

        <!-- SID -->
        <div class="lc-sid">${esc(lbl.sid)}</div>

        <!-- Barcodes -->
        <div class="lc-barcodes">
          <div class="lc-barcode-wrap">
            <svg id="bc-${idx}" jsbarcode-format="CODE128"
              jsbarcode-value="${esc(lbl.barcode)}"
              jsbarcode-displayvalue="true"
              jsbarcode-fontsize="10"
              jsbarcode-height="40"
              jsbarcode-margin="0">
            </svg>
          </div>
          <div class="lc-qr-wrap" id="qr-${idx}"></div>
        </div>

        <!-- Tests -->
        <div class="lc-tests">
          <strong>Tests</strong>
          ${(lbl.test_names || []).map(t => `<span class="lc-test-item">${esc(t)}</span>`).join('')}
        </div>

        <!-- Sample details -->
        <div class="lc-sample">
          <div class="lc-sample-field"><strong>${esc(lbl.tube_display || lbl.tube_type || '—')}</strong></div>
          <div class="lc-sample-field"><strong>${esc(dept)}</strong></div>
          <div class="lc-sample-field">Vol: ${lbl.volume_ml ? lbl.volume_ml + ' mL' : '—'}</div>
          <div class="lc-sample-field">${esc(lbl.specimen_type || lbl.tube_display || '—')}</div>
        </div>

        <!-- Footer -->
        <div class="lc-footer">
          <span class="lc-footer-time">${timeStr}</span>
          <span class="lc-footer-shift">${esc(shift)}</span>
          <span class="lc-footer-nexus">NEXUS ALIS-X</span>
        </div>

      </div><!-- /label-card -->

      <!-- Card actions (screen only) -->
      <div class="lc-card-actions">
        <button class="btn btn-primary btn-sm" style="flex:1" onclick="window._printSingle(${idx})">
          🖨️ Print This Label
        </button>
        <button class="btn btn-ghost btn-sm" onclick="window._printSingle(${idx}, true)" title="Print ${copies()} copies">
          ×${copies()}
        </button>
      </div>
    `;

    // Checkbox click
    const chk = wrap.querySelector(`#chk-${idx}`);
    chk?.addEventListener('click', e => {
      e.stopPropagation();
      toggleSelect(idx);
    });

    // Card click = toggle select
    const card = wrap.querySelector('.label-card');
    card?.addEventListener('click', () => toggleSelect(idx));

    return wrap;
  }

  /* ── Barcode rendering via JsBarcode ──────────────────────── */
  function renderBarcode(card, lbl) {
    if (!window.JsBarcode) return;
    const svgEl = card.querySelector('[id^="bc-"]');
    if (!svgEl) return;
    try {
      JsBarcode(svgEl, lbl.barcode, {
        format:       'CODE128',
        displayValue: false,   // hide built-in text; we render our own below for full control
        fontSize:     11,
        height:       44,
        margin:       4,
        background:   '#ffffff',
        lineColor:    '#000000',
        width:        1.6,
        textAlign:    'center',
        font:         'JetBrains Mono, monospace',
      });
      // Inject human-readable barcode number below the bars (larger, formatted)
      const barcodeWrap = svgEl.closest('.lc-barcode-wrap') || svgEl.parentElement;
      if (barcodeWrap && !barcodeWrap.querySelector('.human-barcode-text')) {
        const htxt = document.createElement('div');
        htxt.className = 'human-barcode-text label-human-text';
        // Format: groups of 4 chars separated by spaces for readability
        const raw = lbl.barcode || '';
        const formatted = raw.replace(/(.{4})/g, '$1 ').trim();
        htxt.textContent = formatted;
        htxt.title = `Barcode: ${raw}`;
        barcodeWrap.appendChild(htxt);
      }
    } catch (e) {
      console.warn('Barcode render failed:', e);
    }
  }

  /* ── QR code rendering via QRCode.js ─────────────────────── */
  function renderQR(card, lbl) {
    if (!window.QRCode) return;
    const container = card.querySelector('[id^="qr-"]');
    if (!container) return;
    const qrData = JSON.stringify({
      lid: lbl.patient_lid || '',
      pid: lbl.patient_pid || '',
      sid: lbl.sid,
      bc:  lbl.barcode,
      lab: lbl.lab_id,
    });
    try {
      const size = activeSize === 'tube' ? 60 : activeSize === 'large' ? 80 : 56;
      new QRCode(container, {
        text:          qrData,
        width:         size,
        height:        size,
        colorDark:     '#000000',
        colorLight:    '#ffffff',
        correctLevel:  QRCode.CorrectLevel.M,
      });
    } catch (e) {
      console.warn('QR render failed:', e);
    }
  }

  /* ── Selection management ────────────────────────────────── */
  function toggleSelect(idx) {
    if (selectedLabels.has(idx)) selectedLabels.delete(idx);
    else selectedLabels.add(idx);
    updateSelectedCount();
    refreshCardSelections();
  }

  function refreshCardSelections() {
    document.querySelectorAll('[id^="chk-"]').forEach(chk => {
      const idx = parseInt(chk.id.replace('chk-', ''));
      chk.classList.toggle('checked', selectedLabels.has(idx));
      const card = document.getElementById(`lcard-${idx}`);
      card?.classList.toggle('selected', selectedLabels.has(idx));
    });
  }

  function updateSelectedCount() {
    $('selected-count') && ($('selected-count').textContent = selectedLabels.size);
  }

  $('btn-select-all-labels')?.addEventListener('click', () => {
    if (selectedLabels.size === (activeLabelData?.length || 0)) {
      selectedLabels.clear();
    } else {
      (activeLabelData || []).forEach((_, i) => selectedLabels.add(i));
    }
    updateSelectedCount();
    refreshCardSelections();
  });

  /* ════════════════════════════════════════════════════════════
     PRINT ENGINE
  ════════════════════════════════════════════════════════════ */

  /* Print selected labels */
  $('btn-print-selected')?.addEventListener('click', () => {
    if (!selectedLabels.size) { Toast.warning('No labels selected', 'Select at least one label to print.'); return; }
    const labels = [...selectedLabels].map(i => activeLabelData[i]).filter(Boolean);
    printLabels(labels, copies());
  });

  /* Print all pending */
  $('btn-print-all')?.addEventListener('click', async () => {
    if (!labelQueue.length) { Toast.warning('Empty queue', 'No pending labels to print.'); return; }
    Toast.info('Batch print', `Generating labels for ${labelQueue.length} requests…`);
    const allLabels = [];
    for (const req of labelQueue.slice(0, 20)) {
      try {
        const r    = await API.get(`/laboratory/requests/${req.id}/labels/`);
        const data = await API.json(r);
        allLabels.push(...(data.labels || []));
      } catch (_) {}
    }
    if (allLabels.length) printLabels(allLabels, 1);
  });

  /* Print single label (called from card) */
  window._printSingle = (idx, multiCopies) => {
    const lbl = activeLabelData?.[idx];
    if (!lbl) return;
    printLabels([lbl], multiCopies ? copies() : 1);
  };

  function printLabels(labels, numCopies = 1) {
    if (!printFrame) return;
    printFrame.innerHTML = '';

    const printClass = { tube:'print-label-tube', large:'print-label-large', wristband:'print-label-wristband', report:'print-label-report' }[activeSize] || 'print-label-tube';
    const shift = NEXUS.ShiftEngine?.current?.name || 'Shift';
    const now   = new Date();
    const timeStr = now.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'2-digit'}) + ' ' + now.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});

    labels.forEach(lbl => {
      for (let c = 0; c < numCopies; c++) {
        const tube = TUBE_COLORS[lbl.tube_type] || TUBE_COLORS.other;
        const dept = lbl.department || 'Unknown';
        const deptColor = DEPT_COLORS[dept] || DEPT_COLORS.default;
        const isHR = lbl.is_high_risk;

        const div = document.createElement('div');
        div.className = printClass;
        div.innerHTML = `
          <div class="pl-tube-band" style="background:${tube.bg};width:100%;height:3mm;display:block"></div>
          ${isHR ? '<div class="pl-high-risk" style="background:#ff1744;color:#fff;font-size:5pt;padding:1pt;text-align:center;font-weight:800">☣️ HIGH RISK — BSL-2</div>' : ''}
          <div style="display:flex;align-items:flex-start;justify-content:space-between;padding:1mm 2mm">
            <div style="flex:1">
              <div style="font-size:5pt;color:#777;text-transform:uppercase;letter-spacing:.06em">${esc(lbl.hospital_name || 'NEXUS')}</div>
              <div class="pl-patient-name" style="font-size:7pt;font-weight:800;text-transform:uppercase">${esc(lbl.patient_name || '—')}</div>
              <div class="pl-meta" style="font-size:5.5pt;color:#555">${lbl.patient_dob||'—'} · ${lbl.patient_gender||''} · ${lbl.patient_age||''}y</div>
              <div style="font-size:5pt;font-family:monospace;margin-top:0.5mm">
                <span style="background:#eef;padding:0 2pt;border-radius:1pt">PID: ${esc(lbl.patient_pid||'—')}</span>
                ${lbl.patient_lid ? `<span style="background:#e0f0ee;padding:0 2pt;border-radius:1pt;margin-left:2pt">LID: ${esc(lbl.patient_lid)}</span>` : ''}
              </div>
            </div>
            <span style="font-size:5pt;font-weight:800;padding:1pt 3pt;border-radius:1pt;background:${deptColor};color:#fff">${esc(lbl.dept_abbr || dept.slice(0,4).toUpperCase())}</span>
          </div>
          <div style="padding:0 2mm;display:flex;align-items:center;gap:2mm">
            <svg id="pbc-${lbl.barcode.replace(/[^a-z0-9]/gi,'')}-${c}" style="flex:1;max-height:12mm"></svg>
            <div id="pqr-${lbl.barcode.replace(/[^a-z0-9]/gi,'')}-${c}" style="width:12mm;height:12mm;flex-shrink:0"></div>
          </div>
          <div style="display:flex;justify-content:space-between;padding:0 2mm;font-size:5pt;font-family:monospace">
            <span style="font-weight:800;letter-spacing:.08em">${esc(lbl.sid)}</span>
            <span style="color:#888">${timeStr} · ${esc(shift)}</span>
          </div>
          <div style="padding:0 2mm;font-size:5pt;color:#555;border-top:0.3pt solid #ddd;margin-top:0.5mm">${(lbl.test_names||[]).join(' · ')}</div>
        `;

        printFrame.appendChild(div);

        // Render barcode inside the print div
        const svgId = `pbc-${lbl.barcode.replace(/[^a-z0-9]/gi,'')}-${c}`;
        const qrId  = `pqr-${lbl.barcode.replace(/[^a-z0-9]/gi,'')}-${c}`;

        setTimeout(() => {
          const svgEl = document.getElementById(svgId);
          if (svgEl && window.JsBarcode) {
            try { JsBarcode(svgEl, lbl.barcode, { format:'CODE128', displayValue:true, fontSize:8, height:28, margin:2, width:1.2, lineColor:'#000', background:'#fff' }); }
            catch (_) {}
          }
          const qrEl = document.getElementById(qrId);
          if (qrEl && window.QRCode) {
            try {
              new QRCode(qrEl, {
                text: JSON.stringify({ lid:lbl.patient_lid||'', pid:lbl.patient_pid||'', sid:lbl.sid, bc:lbl.barcode }),
                width:50, height:50, colorDark:'#000', colorLight:'#fff', correctLevel: QRCode.CorrectLevel.M,
              });
            } catch (_) {}
          }
        }, 50);
      }
    });

    // Wait for barcodes/QR to render, then print
    setTimeout(() => {
      window.print();
      printedToday += labels.length * numCopies;
      updateKPIs(labelQueue);

      // Log label print event
      labels.forEach(lbl => {
        try {
          fetch(`/api/v1/laboratory/samples/${lbl.sample_id || ''}/label-printed/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF() },
            body: JSON.stringify({ copies: numCopies }),
          }).catch(() => {});
        } catch (_) {}
      });

      Toast.success('🖨️ Labels sent to printer', `${labels.length * numCopies} label(s) printed`);
    }, 400);
  }

  /* ════════════════════════════════════════════════════════════
     REPRINT BY BARCODE
  ════════════════════════════════════════════════════════════ */
  async function doReprint() {
    const bc = $('lpc-reprint-input')?.value?.trim();
    if (!bc) return;
    try {
      const r    = await API.get('/laboratory/requests/', { lab_id: bc, page_size: 1 });
      const data = await API.json(r);
      const reqs = data.results ?? data;
      if (!reqs.length) {
        // Try searching by barcode (SID/barcode field)
        Toast.warning('Not found', `No request found for: ${bc}`);
        return;
      }
      const req = reqs[0];
      const lr  = await API.get(`/laboratory/requests/${req.id}/labels/`);
      const ld  = await API.json(lr);
      if (ld.labels?.length) {
        printLabels(ld.labels, copies());
        $('lpc-reprint-input').value = '';
      }
    } catch (e) { Toast.error('Reprint failed', e.message); }
  }

  $('btn-reprint')?.addEventListener('click', doReprint);
  $('lpc-reprint-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') doReprint();
  });

  /* ════════════════════════════════════════════════════════════
     LABEL SIZE SWITCHING
  ════════════════════════════════════════════════════════════ */
  document.querySelectorAll('.lpc-size-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.lpc-size-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeSize = btn.dataset.size;
      if (activeLabelData) renderLabelCards(activeLabelData);
    });
  });

  /* ════════════════════════════════════════════════════════════
     FILTERS + SEARCH
  ════════════════════════════════════════════════════════════ */
  let searchTimer = null;
  $('lpc-search')?.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadQueue, 350);
  });
  $('lpc-filter-dept')?.addEventListener('change',   loadQueue);
  $('lpc-filter-status')?.addEventListener('change', loadQueue);
  $('btn-refresh')?.addEventListener('click',        loadQueue);

  /* ════════════════════════════════════════════════════════════
     PHLEBOTOMY INTEGRATION
     - Auto-loads label for a specific request when navigated
       from phlebotomy with ?lab_id=XXXXXX
  ════════════════════════════════════════════════════════════ */
  const urlParams  = new URLSearchParams(window.location.search);
  const targetLID  = urlParams.get('lab_id');
  const autoReqId  = urlParams.get('req');

  if (targetLID || autoReqId) {
    window.addEventListener('DOMContentLoaded', async () => {
      await loadQueue();
      const req = labelQueue.find(r => r.lab_id === targetLID || String(r.id) === autoReqId);
      if (req) {
        const item = queueList?.querySelector(`[data-id="${req.id}"]`);
        item?.classList.add('active');
        await loadLabelsForRequest(req);
      }
    });
  }

  /* ════════════════════════════════════════════════════════════
     EXPOSE for phlebotomy.js to call
  ════════════════════════════════════════════════════════════ */
  window.NexusLabels = {
    printForRequest: async (reqId, numCopies = 1) => {
      try {
        const r    = await API.get(`/laboratory/requests/${reqId}/labels/`);
        const data = await API.json(r);
        if (data.labels?.length) printLabels(data.labels, numCopies);
      } catch (e) { Toast.error('Label print failed', e.message); }
    },
    printSingleLabel: (labelData, numCopies = 1) => printLabels([labelData], numCopies),
  };

  /* ── Init ─────────────────────────────────────────────────── */
  loadQueue();
})();
