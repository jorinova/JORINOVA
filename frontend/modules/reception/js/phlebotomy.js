/**
 * JORINOVA NEXUS ALIS-X — Phlebotomy Collection
 * Collection queue · Mark collected · Label print modal
 */
'use strict';

(function () {
  const { API, Toast, Confirm, fmt } = window.NEXUS;

  /* ─── State ─────────────────────────────────────────────────── */
  let queue         = [];
  let refreshTimer  = null;
  const REFRESH_MS  = 30_000;

  /* ─── DOM ────────────────────────────────────────────────────── */
  const tbody          = document.getElementById('queue-tbody');
  const labelOverlay   = document.getElementById('label-modal-overlay');
  const labelGrid      = document.getElementById('label-preview-grid');
  const labelModalTitle= document.getElementById('label-modal-title');
  const statPending    = document.getElementById('stat-pending-count');
  const statStat       = document.getElementById('stat-stat-count');
  const statTotal      = document.getElementById('stat-total-count');

  /* ════════════════════════════════════════════════════════════
     LOAD QUEUE
  ════════════════════════════════════════════════════════════ */
  async function loadQueue() {
    const today = new Date().toISOString().split('T')[0];
    try {
      const r    = await API.get('/laboratory/requests/', {
        status:    'submitted',
        date_from: today,
        page_size: 100,
      });
      const data = await API.json(r);
      queue      = data.results ?? data;
      renderQueue(queue);
      updateStats(queue);
    } catch (err) {
      showError(err.message);
    }
  }

  /* ════════════════════════════════════════════════════════════
     RENDER QUEUE
  ════════════════════════════════════════════════════════════ */
  function renderQueue(items) {
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="6">
        <div class="queue-empty">
          <i class="fas fa-check-circle" style="color:var(--alert-green);opacity:0.5"></i>
          <h3>All Collected</h3>
          <p>No pending samples in the collection queue.</p>
        </div>
      </td></tr>`;
      return;
    }

    tbody.innerHTML = items.map(req => {
      const isEmerg  = req.emergency_level === 'emergency';
      const wait     = waitTime(req.request_date);
      const tubes    = buildTubeList(req.samples || []);
      return `
      <tr class="${isEmerg ? 'row-stat-request' : ''}" data-id="${req.id}">
        <td>
          <div class="cell-patient-info">
            <div class="cell-avatar">
              ${req.patient_photo ? `<img src="${req.patient_photo}" alt="">` : patInitials(req.patient_name)}
            </div>
            <div>
              <div class="cell-pname">${escHtml(req.patient_name)}</div>
              <div class="cell-pmeta">${escHtml(req.patient_pid)} · ${escHtml(req.patient_age || '—')}</div>
            </div>
          </div>
        </td>
        <td>
          <div class="cell-labid">${escHtml(req.lab_id)}</div>
          ${isEmerg ? '<span class="badge badge-red anim-pulse-critical">STAT</span>' : ''}
          ${req.emergency_level === 'urgent' ? '<span class="badge badge-orange">Urgent</span>' : ''}
        </td>
        <td>
          <div class="tubes-required">
            ${tubes.map(t => `
              <div class="tube-chip">
                <div class="tube-swatch" style="background:${escHtml(t.color)};box-shadow:0 0 5px ${escHtml(t.color)}"></div>
                <span>${escHtml(t.label)}</span>
              </div>
            `).join('')}
          </div>
        </td>
        <td>
          <span class="wait-time ${wait.cls}">${wait.label}</span>
        </td>
        <td>
          <span class="text-xs text-muted-c">${escHtml(req.doctor_name || '—')}</span>
          ${req.ward ? `<span class="badge badge-grey" style="margin-left:4px;font-size:10px">${escHtml(req.ward)}</span>` : ''}
        </td>
        <td style="text-align:right">
          <div style="display:flex;align-items:center;gap:6px;justify-content:flex-end">
            <button class="btn btn-xs btn-primary btn-collect" data-id="${req.id}" type="button">
              <i class="fas fa-syringe"></i> Collect
            </button>
            <button class="btn btn-xs btn-secondary btn-labels" data-id="${req.id}" type="button" title="Print labels">
              <i class="fas fa-tags"></i> Labels
            </button>
          </div>
        </td>
      </tr>`;
    }).join('');

    /* Bind actions */
    tbody.querySelectorAll('.btn-collect').forEach(btn => {
      btn.addEventListener('click', () => markCollected(btn.dataset.id));
    });
    tbody.querySelectorAll('.btn-labels').forEach(btn => {
      btn.addEventListener('click', () => {
        const req = queue.find(r => r.id == btn.dataset.id);
        if (req) window.location.href = `/laboratory/labels/?lab_id=${req.lab_id}`;
        else openLabelModal(btn.dataset.id);
      });
    });
  }

  function updateStats(items) {
    const total   = items.length;
    const statCnt = items.filter(r => r.emergency_level === 'emergency').length;
    statPending && (statPending.textContent = total);
    statStat    && (statStat.textContent    = statCnt);
    statTotal   && (statTotal.textContent   = total);
  }

  /* ════════════════════════════════════════════════════════════
     MARK COLLECTED
  ════════════════════════════════════════════════════════════ */
  async function markCollected(reqId) {
    const req = queue.find(r => r.id == reqId);
    if (!req) return;

    const ok = await Confirm.show(
      `Mark all samples for ${req.patient_name} as collected?`,
      '🩸 Confirm Collection',
      'Collected',
      false
    );
    if (!ok) return;

    const samples = req.samples || [];
    if (!samples.length) { Toast.warning('No samples', 'No samples found for this request.'); return; }

    let success = 0;
    for (const sample of samples) {
      try {
        const r = await API.patch(`/laboratory/samples/${sample.id}/status/`, {
          status: 'collected',
        });
        await API.checkError(r);
        success++;
      } catch (err) {
        Toast.error(`Sample ${sample.sid}`, err.message);
      }
    }

    if (success === samples.length) {
      Toast.success('Samples Collected', `${success} tube${success > 1 ? 's' : ''} marked — ${req.patient_name}`);

      // Offer label print
      const printNow = await Confirm.show(
        `Print tube labels for ${req.patient_name} now?`,
        '🏷️ Print Labels',
        'Print Labels',
        false
      );
      if (printNow) {
        window.location.href = `/laboratory/labels/?lab_id=${req.lab_id}`;
        return;
      }
      loadQueue();
    }
  }

  /* ════════════════════════════════════════════════════════════
     LABEL MODAL
  ════════════════════════════════════════════════════════════ */
  async function openLabelModal(reqId) {
    if (!labelOverlay) return;
    labelGrid && (labelGrid.innerHTML = `
      <div style="grid-column:1/-1;display:flex;align-items:center;justify-content:center;gap:1rem;padding:2rem;color:var(--text-muted)">
        <i class="fas fa-spinner" style="animation:spin 1s linear infinite;font-size:20px"></i> Loading labels…
      </div>`);
    labelOverlay.classList.add('open');

    try {
      const r    = await API.get(`/laboratory/requests/${reqId}/labels/`);
      await API.checkError(r);
      const data = await API.json(r);
      renderLabels(data);
    } catch (err) {
      Toast.error('Labels Failed', err.message);
      closeLabelModal();
    }
  }

  function renderLabels(data) {
    if (!labelGrid) return;
    const labels = data.labels || [];
    if (labelModalTitle) labelModalTitle.textContent = `Labels — ${data.patient_name} · ${data.lab_id}`;
    if (!labels.length) {
      labelGrid.innerHTML = '<p class="text-muted-c text-xs">No samples found.</p>';
      return;
    }
    labelGrid.innerHTML = labels.map(lbl => `
      <div class="label-preview" style="--label-color:${escHtml(lbl.label_color)}">
        <div class="label-color-bar"></div>
        <div class="label-body">
          <div class="label-patient-name">${escHtml(lbl.patient_name)}</div>
          <div class="label-pid">${escHtml(lbl.patient_pid)}</div>
          <div class="label-dob-gender">${escHtml(lbl.patient_dob)} · ${escHtml(lbl.patient_gender?.toUpperCase() || '')} · ${escHtml(lbl.patient_age)}</div>
          <div class="label-barcode-row">
            <span class="label-barcode-text">${escHtml(lbl.barcode)}</span>
            <span class="label-dept">${escHtml(lbl.dept_abbr)}</span>
          </div>
          <div class="label-tests-line">${escHtml((lbl.test_names || []).join(', ') || '—')}</div>
        </div>
        <div class="label-footer">
          <span class="label-lab-id">REQ-${escHtml(lbl.lab_id)}</span>
          ${lbl.is_high_risk ? '<span class="label-biohazard">☣️</span>' : ''}
          <span class="label-date">${escHtml(lbl.collected_at)}</span>
        </div>
      </div>
    `).join('');
  }

  function closeLabelModal() {
    labelOverlay?.classList.remove('open');
    if (labelGrid) labelGrid.innerHTML = '';
  }

  /* Label modal controls */
  document.getElementById('label-close-btn')?.addEventListener('click', closeLabelModal);
  labelOverlay?.addEventListener('click', e => { if (e.target === labelOverlay) closeLabelModal(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && labelOverlay?.classList.contains('open')) closeLabelModal();
  });
  document.getElementById('label-print-btn')?.addEventListener('click', () => window.print());

  /* ════════════════════════════════════════════════════════════
     SEARCH FILTER
  ════════════════════════════════════════════════════════════ */
  document.getElementById('phlebo-search')?.addEventListener('input', function () {
    const q = this.value.toLowerCase();
    document.querySelectorAll('#queue-tbody tr[data-id]').forEach(row => {
      row.style.display = q ? (row.textContent.toLowerCase().includes(q) ? '' : 'none') : '';
    });
  });

  document.getElementById('priority-filter')?.addEventListener('change', function () {
    const val = this.value;
    document.querySelectorAll('#queue-tbody tr[data-id]').forEach(row => {
      if (!val) { row.style.display = ''; return; }
      row.style.display = row.dataset.emerg === val ? '' : 'none';
    });
  });

  document.getElementById('btn-print-all')?.addEventListener('click', () => {
    if (!queue.length) { Toast.info('No samples', 'Queue is empty.'); return; }
    /* Open labels for first pending item for demo; production would batch */
    openLabelModal(queue[0].id);
  });

  /* ════════════════════════════════════════════════════════════
     HELPERS
  ════════════════════════════════════════════════════════════ */
  const TUBE_NAMES = {
    purple_edta:    'Purple EDTA',    red_plain:     'Red Plain',
    yellow_sst:     'Yellow SST',     blue_citrate:  'Blue Citrate',
    green_heparin:  'Green Heparin',  grey_fluoride: 'Grey Fluoride',
    urine_container:'Urine',          stool_container:'Stool',
    swab:           'Swab',
  };
  const TUBE_COLORS = {
    purple_edta:'#9B59B6', red_plain:'#E74C3C', yellow_sst:'#F39C12',
    blue_citrate:'#2980B9', green_heparin:'#27AE60', grey_fluoride:'#95A5A6',
    urine_container:'#F1C40F', stool_container:'#784212', swab:'#EB984E',
  };

  function buildTubeList(samples) {
    const map = {};
    samples.forEach(s => {
      if (!map[s.tube_type]) map[s.tube_type] = { color: s.label_color || TUBE_COLORS[s.tube_type] || '#BDC3C7', label: TUBE_NAMES[s.tube_type] || s.tube_type, count: 0 };
      map[s.tube_type].count++;
    });
    return Object.values(map);
  }

  function waitTime(dateStr) {
    if (!dateStr) return { label: '—', cls: '' };
    const mins = Math.floor((Date.now() - new Date(dateStr)) / 60000);
    if (mins < 15)  return { label: `${mins}m`,    cls: 'low' };
    if (mins < 30)  return { label: `${mins}m`,    cls: 'mid' };
    if (mins < 60)  return { label: `${mins}m`,    cls: 'high' };
    const h = Math.floor(mins / 60);
    return { label: `${h}h ${mins % 60}m`, cls: 'urgent' };
  }

  function patInitials(name) {
    const p = (name || '?').split(' ');
    return (p[0]?.[0] || '') + (p[1]?.[0] || '');
  }

  function escHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }

  function showError(msg) {
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6">
      <div class="queue-empty">
        <i class="fas fa-triangle-exclamation" style="color:var(--alert-red)"></i>
        <h3>Error</h3><p>${escHtml(msg)}</p>
      </div>
    </td></tr>`;
  }

  /* ════════════════════════════════════════════════════════════
     BOOT
  ════════════════════════════════════════════════════════════ */
  loadQueue();
  refreshTimer = setInterval(loadQueue, REFRESH_MS);

})();
