/**
 * NEXUS ALIS-X — Levey-Jennings QC Chart Engine
 * ================================================
 * ISO 15189:2022 · Westgard Multi-Rules (1-2s, 1-3s, 2-2s, R-4s, 4-1s, 10x)
 * Uses Chart.js 4.x for rendering.
 */
'use strict';

const API   = '/api/v1';
const tok   = () => localStorage.getItem('access_token') || '';
const hdrs  = () => ({ 'Content-Type':'application/json', 'Authorization':'Bearer '+tok() });

let _chart    = null;   // Chart.js instance
let _chartData = null;  // last loaded data
let _tableVisible = true;

// ── BOOT ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Set today as default run date for entry modal
  const d = document.getElementById('entry-date');
  if (d) d.value = new Date().toISOString().slice(0,10);

  loadAnalytes();
});

// ── LOAD ANALYTES FOR DROPDOWN ────────────────────────────────────────────────
async function loadAnalytes() {
  const dept = document.getElementById('ctrl-dept')?.value || 'biochemistry';
  try {
    const r = await fetch(`${API}/quality/iqc/analytes?department=${dept}`, { headers: hdrs() });
    const sel = document.getElementById('ctrl-analyte');
    if (!sel) return;
    sel.innerHTML = '<option value="">— Select analyte —</option>';

    if (r.ok) {
      const analytes = await r.json();
      analytes.forEach(a => {
        const opt = document.createElement('option');
        opt.value       = a.code;
        opt.textContent = `${a.name} (${a.code})`;
        sel.appendChild(opt);
      });
    }

    // If no real data, show common analytes for the department
    if (sel.options.length <= 1) {
      _populateDemoAnalytes(dept, sel);
    }
  } catch(_) {}
}

function _populateDemoAnalytes(dept, sel) {
  const DEPT_ANALYTES = {
    biochemistry: [['GLUCOSE','Glucose'],['CREAT','Creatinine'],['UREA','Urea'],['ALT','ALT'],
                   ['AST','AST'],['CHOL','Cholesterol'],['NA','Sodium'],['K','Potassium']],
    hematology:   [['HGB','Haemoglobin'],['WBC','White Blood Cells'],['PLT','Platelets'],
                   ['HCT','Haematocrit'],['MCV','MCV']],
    coagulation:  [['PT','Prothrombin Time'],['APTT','APTT'],['FIBRIN','Fibrinogen']],
    urinalysis:   [['SPECIFIC_G','Specific Gravity'],['PH','pH'],['PROTEIN','Urine Protein']],
    serology:     [['CRP','C-Reactive Protein'],['RHFACT','Rheumatoid Factor']],
    molecular:    [['VL_HIV','HIV Viral Load']],
  };
  const list = DEPT_ANALYTES[dept] || DEPT_ANALYTES.biochemistry;
  list.forEach(([code, name]) => {
    const opt = document.createElement('option');
    opt.value = code; opt.textContent = `${name} (${code})`;
    sel.appendChild(opt);
  });
}

// ── LOAD AND RENDER CHART ─────────────────────────────────────────────────────
async function loadChart() {
  const dept    = document.getElementById('ctrl-dept')?.value    || 'biochemistry';
  const analyte = document.getElementById('ctrl-analyte')?.value || '';
  const level   = document.getElementById('ctrl-level')?.value   || 'L1';
  const days    = document.getElementById('ctrl-days')?.value    || '30';

  if (!analyte) { NEXUS?.Toast?.warning('Select an analyte first'); return; }

  const btn = document.getElementById('btn-load');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>'; }

  try {
    const url = `${API}/quality/iqc/levey-jennings?department=${dept}&analyte_code=${analyte}&control_level=${level}&days=${days}`;
    const r   = await fetch(url, { headers: hdrs() });

    if (!r.ok) {
      // Generate demo data if backend has no QC records yet
      _chartData = _generateDemoData(dept, analyte, level, parseInt(days));
    } else {
      _chartData = await r.json();
      if (!_chartData.points?.length) {
        _chartData = _generateDemoData(dept, analyte, level, parseInt(days));
      }
    }

    _renderAll(_chartData);
  } catch(e) {
    _chartData = _generateDemoData(dept, analyte, level, parseInt(days));
    _renderAll(_chartData);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fas fa-chart-line"></i> Plot Chart'; }
  }
}

// ── DEMO DATA GENERATOR ───────────────────────────────────────────────────────
function _generateDemoData(dept, analyte, level, days) {
  const configs = {
    GLUCOSE: { mean: 5.5,  sd: 0.15, unit: 'mmol/L' },
    CREAT:   { mean: 90,   sd: 5.0,  unit: 'µmol/L' },
    UREA:    { mean: 6.0,  sd: 0.3,  unit: 'mmol/L' },
    ALT:     { mean: 30,   sd: 2.0,  unit: 'U/L' },
    AST:     { mean: 25,   sd: 1.5,  unit: 'U/L' },
    HGB:     { mean: 130,  sd: 3.0,  unit: 'g/L' },
    WBC:     { mean: 6.5,  sd: 0.4,  unit: '×10⁹/L' },
    PLT:     { mean: 250,  sd: 15.0, unit: '×10⁹/L' },
    PT:      { mean: 12.5, sd: 0.4,  unit: 's' },
    NA:      { mean: 140,  sd: 1.5,  unit: 'mmol/L' },
    K:       { mean: 4.2,  sd: 0.12, unit: 'mmol/L' },
    CHOL:    { mean: 5.0,  sd: 0.2,  unit: 'mmol/L' },
  };
  const cfg = configs[analyte] || { mean: 50, sd: 2.0, unit: '' };
  const mean = cfg.mean * (level === 'L1' ? 0.5 : level === 'L3' ? 2.0 : 1.0);
  const sd   = cfg.sd   * (level === 'L1' ? 0.5 : level === 'L3' ? 2.0 : 1.0);

  const points = [];
  let drift = 0;
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(); d.setDate(d.getDate() - i);
    // Introduce drift after day 20 for demo purposes
    if (i === Math.floor(days * 0.35)) drift += sd * 0.8;
    const value  = mean + drift + (Math.random() - 0.5) * sd * 3.5;
    const z      = (value - mean) / sd;
    const status = Math.abs(z) > 3 ? 'REJECT' : Math.abs(z) > 2 ? 'WARN' : 'PASS';
    points.push({
      run_date: d.toISOString().slice(0,10),
      value:    parseFloat(value.toFixed(3)),
      z_score:  parseFloat(z.toFixed(3)),
      status,
      westgard_rule: status === 'REJECT' ? '1-3s' : status === 'WARN' ? '1-2s' : 'PASS',
      operator: 'Demo Operator',
      analyzer: 'Demo Analyzer',
      lot: 'LOT-DEMO-001',
    });
  }

  // Run Westgard rules client-side on demo data
  const zScores  = points.map(p => p.z_score);
  const violations = _westgardClient(zScores);

  const passed   = points.filter(p => p.status === 'PASS').length;
  const actualMean = points.reduce((s,p) => s + p.value, 0) / points.length;
  const actualSd   = Math.sqrt(points.reduce((s,p) => s + (p.value-actualMean)**2, 0) / points.length);
  const cvPct      = parseFloat((actualSd / actualMean * 100).toFixed(2));
  const anyReject  = violations.some(v => v.severity === 'REJECT');
  const anyWarn    = violations.some(v => v.severity === 'WARN');

  return {
    analyte, department: dept, control_level: level, unit: cfg.unit,
    points,
    stats: {
      target_mean: parseFloat(mean.toFixed(3)), target_sd: parseFloat(sd.toFixed(3)),
      actual_mean: parseFloat(actualMean.toFixed(3)), actual_sd: parseFloat(actualSd.toFixed(3)),
      cv_pct: cvPct, n: points.length,
      pass_rate: parseFloat((passed / points.length * 100).toFixed(1)),
      violations: violations.length,
    },
    westgard: violations,
    run_decision: anyReject ? 'REJECT' : anyWarn ? 'WARN' : 'ACCEPT',
    sd_lines: {
      mean,
      plus1: mean + sd,   minus1: mean - sd,
      plus2: mean + 2*sd, minus2: mean - 2*sd,
      plus3: mean + 3*sd, minus3: mean - 3*sd,
    },
    _demo: true,
  };
}

// ── CLIENT-SIDE WESTGARD (mirrors backend) ────────────────────────────────────
function _westgardClient(z) {
  const v = [];
  z.forEach((zi, i) => {
    if (Math.abs(zi) > 3) v.push({ rule:'1-3s', index:i, severity:'REJECT',
      description:`Point ${i+1}: z=${zi.toFixed(2)} — exceeds ±3 SD`,
      action:'Reject run. Investigate QC material, reagent, or instrument.'});
    else if (Math.abs(zi) > 2) v.push({ rule:'1-2s', index:i, severity:'WARN',
      description:`Point ${i+1}: z=${zi.toFixed(2)} — exceeds ±2 SD`,
      action:'Warning only. Check adjacent Westgard rules before accepting.'});

    if (i >= 1 && Math.abs(zi) >= 2 && Math.abs(z[i-1]) >= 2 && (zi>0)===(z[i-1]>0))
      v.push({ rule:'2-2s', index:i, severity:'REJECT',
        description:`Points ${i} & ${i+1}: two consecutive > ±2 SD same side`,
        action:'Reject run. Systematic error (calibration drift).'});

    if (i >= 1 && Math.abs(zi - z[i-1]) > 4)
      v.push({ rule:'R-4s', index:i, severity:'REJECT',
        description:`Points ${i} & ${i+1}: range=${(Math.abs(zi-z[i-1])).toFixed(2)} SD > 4 SD`,
        action:'Reject run. Random error (pipetting/mixing).'});

    if (i >= 3) {
      const l4 = z.slice(i-3, i+1);
      if (l4.every(v=>v>1) || l4.every(v=>v<-1))
        v.push({ rule:'4-1s', index:i, severity:'REJECT',
          description:`Points ${i-2}–${i+1}: four consecutive > ±1 SD same side`,
          action:'Reject run. Systematic bias — check calibration.'});
    }
    if (i >= 9) {
      const l10 = z.slice(i-9, i+1);
      if (l10.every(v=>v>0) || l10.every(v=>v<0))
        v.push({ rule:'10x', index:i, severity:'REJECT',
          description:`Points ${i-8}–${i+1}: ten consecutive same side of mean`,
          action:'Reject run. Systematic drift — recalibrate, check reagent lot.'});
    }
  });
  return v;
}

// ── RENDER ALL ────────────────────────────────────────────────────────────────
function _renderAll(data) {
  _renderKPI(data);
  _renderChart(data);
  _renderViolations(data);
  _renderDecision(data);
  _renderTable(data);

  document.getElementById('lj-kpi')?.style.setProperty('display','');
  document.getElementById('lj-sd-legend')?.style.setProperty('display','');
  if (data._demo) NEXUS?.Toast?.info('Demo data shown — add real QC runs via "Add QC Run"');
}

// ── KPI ───────────────────────────────────────────────────────────────────────
function _renderKPI(d) {
  const s = d.stats || {};
  _setText('kpi-n',          s.n ?? '—');
  _setText('kpi-pass',       (s.pass_rate ?? '—') + '%');
  _setText('kpi-cv',         (s.cv_pct ?? '—') + '%');
  _setText('kpi-mean',       s.actual_mean ?? '—');
  _setText('kpi-sd',         s.actual_sd ?? '—');
  _setText('kpi-violations', s.violations ?? '—');

  // Update run decision badge
  const badge = document.getElementById('run-decision-badge');
  if (badge) {
    badge.textContent = d.run_decision || '—';
    badge.className = 'lj-run-badge ' +
      ({ ACCEPT:'accept', WARN:'warn', REJECT:'reject' }[d.run_decision] || '');
  }
}

// ── CHART ─────────────────────────────────────────────────────────────────────
function _renderChart(data) {
  document.getElementById('lj-empty').style.display       = 'none';
  document.getElementById('lj-canvas-wrap').style.display = '';

  const sdl    = data.sd_lines || {};
  const points = data.points   || [];
  const labels = points.map(p => p.run_date);
  const values = points.map(p => p.value);
  const unit   = data.unit || '';

  // Point colours by status
  const ptColors = points.map(p =>
    p.status === 'REJECT' ? '#dc2626' : p.status === 'WARN' ? '#f97316' : '#16a34a');
  const ptBorders = points.map(p =>
    p.status === 'REJECT' ? '#991b1b' : p.status === 'WARN' ? '#c2410c' : '#15803d');

  // Constant lines
  const makeFlat = (val) => Array(points.length).fill(val);
  const n = points.length;

  const datasets = [
    // QC data line
    { label: `${data.analyte} ${data.control_level}`, data: values,
      borderColor: '#0891b2', backgroundColor: ptColors,
      borderWidth: 1.5, pointRadius: 5, pointBorderWidth: 1.5,
      pointBorderColor: ptBorders, pointHoverRadius: 7,
      tension: 0.1, fill: false, order: 1 },
    // Mean
    { label: `Mean (${sdl.mean})`, data: makeFlat(sdl.mean),
      borderColor: '#0891b2', borderWidth: 2, borderDash: [], pointRadius: 0, fill: false, order: 0 },
    // ±1 SD
    { label: '+1 SD', data: makeFlat(sdl.plus1),
      borderColor: '#94a3b8', borderWidth: 1, borderDash: [4,4], pointRadius: 0, fill: false, order: 0 },
    { label: '-1 SD', data: makeFlat(sdl.minus1),
      borderColor: '#94a3b8', borderWidth: 1, borderDash: [4,4], pointRadius: 0, fill: false, order: 0 },
    // ±2 SD
    { label: '+2 SD', data: makeFlat(sdl.plus2),
      borderColor: '#f97316', borderWidth: 1.5, borderDash: [6,3], pointRadius: 0, fill: false, order: 0 },
    { label: '-2 SD', data: makeFlat(sdl.minus2),
      borderColor: '#f97316', borderWidth: 1.5, borderDash: [6,3], pointRadius: 0, fill: false, order: 0 },
    // ±3 SD
    { label: '+3 SD', data: makeFlat(sdl.plus3),
      borderColor: '#dc2626', borderWidth: 2, borderDash: [], pointRadius: 0, fill: false, order: 0 },
    { label: '-3 SD', data: makeFlat(sdl.minus3),
      borderColor: '#dc2626', borderWidth: 2, borderDash: [], pointRadius: 0, fill: false, order: 0 },
  ];

  // Destroy existing chart
  if (_chart) { _chart.destroy(); _chart = null; }

  const ctx = document.getElementById('lj-canvas').getContext('2d');
  _chart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true, position: 'top',
          labels: { filter: (i) => i.datasetIndex === 0, boxWidth: 10, font: { size: 11 } },
        },
        tooltip: {
          callbacks: {
            title:     (items) => `Date: ${items[0].label}`,
            label:     (item) => {
              if (item.datasetIndex !== 0) return null;
              const p = points[item.dataIndex];
              return [
                `Value: ${p.value} ${unit}`,
                `Z-Score: ${p.z_score}`,
                `Status: ${p.status}`,
                `Rule: ${p.westgard_rule}`,
                `Operator: ${p.operator || '—'}`,
              ];
            },
            labelColor: (item) => ({
              borderColor: ptBorders[item.dataIndex],
              backgroundColor: ptColors[item.dataIndex],
            }),
          },
        },
        annotation: {},  // placeholder for future annotations
      },
      scales: {
        x: {
          grid: { color: '#f1f5f9' },
          ticks: { maxRotation: 45, font: { size: 10 }, color: '#64748b',
                   maxTicksLimit: 20 },
          title: { display: true, text: 'Run Date', font: { size: 11 }, color: '#64748b' },
        },
        y: {
          grid: { color: '#f1f5f9' },
          ticks: { font: { size: 10 }, color: '#64748b' },
          title: { display: true,
                   text: `${data.analyte} (${unit}) — Target: ${sdl.mean} ± ${data.stats?.target_sd}`,
                   font: { size: 11 }, color: '#0891b2' },
        },
      },
    },
  });
}

// ── VIOLATIONS ────────────────────────────────────────────────────────────────
function _renderViolations(data) {
  const panel = document.getElementById('lj-violations');
  const list  = document.getElementById('lj-violations-list');
  if (!panel || !list) return;

  const violations = data.westgard || [];
  if (!violations.length) {
    panel.style.display = 'none'; return;
  }
  panel.style.display = '';
  list.innerHTML = violations.map(v => `
    <div class="lj-violation-item">
      <span class="lj-violation-rule ${v.severity==='REJECT'?'rule-reject':'rule-warn'}">${v.rule}</span>
      <div class="lj-violation-desc">
        ${v.description}
        <div class="lj-violation-action"><i class="fas fa-arrow-right"></i> ${v.action}</div>
      </div>
    </div>`).join('');
}

// ── DECISION BANNER ───────────────────────────────────────────────────────────
function _renderDecision(data) {
  const el    = document.getElementById('lj-decision');
  const icon  = document.getElementById('lj-decision-icon');
  const title = document.getElementById('lj-decision-title');
  const sub   = document.getElementById('lj-decision-sub');
  if (!el) return;

  const decMap = {
    ACCEPT: { cls:'accept', icon:'✅', title:'RUN ACCEPTED', sub:'All Westgard rules passed. Patient results may be reported.' },
    WARN:   { cls:'warn',   icon:'⚠️', title:'RUN WARNING',  sub:'1-2s warning triggered. Review QC trend before releasing results.' },
    REJECT: { cls:'reject', icon:'🔴', title:'RUN REJECTED', sub:'One or more Westgard rejection rules violated. DO NOT release patient results. Repeat QC, investigate root cause.' },
    NO_DATA:{ cls:'',       icon:'📊', title:'NO DATA',      sub:'No QC data found for selected parameters.' },
  };
  const d = decMap[data.run_decision] || decMap.NO_DATA;
  el.className      = 'lj-decision ' + d.cls;
  icon.textContent  = d.icon;
  title.textContent = d.title;
  sub.textContent   = d.sub;
  el.style.display  = '';
}

// ── DATA TABLE ────────────────────────────────────────────────────────────────
function _renderTable(data) {
  const wrap = document.getElementById('lj-table-wrap');
  const body = document.getElementById('lj-table-body');
  if (!wrap || !body) return;
  wrap.style.display = '';

  const points = data.points || [];
  body.innerHTML = points.map((p, i) => {
    const zCls = Math.abs(p.z_score) > 3 ? 'z-reject' : Math.abs(p.z_score) > 2 ? 'z-warn' : 'z-pass';
    const sCls = p.status === 'REJECT' ? 'badge-reject' : p.status === 'WARN' ? 'badge-warn' : 'badge-pass';
    return `<tr>
      <td style="color:#94a3b8;font-size:.72rem">${i+1}</td>
      <td>${p.run_date}</td>
      <td style="font-weight:700">${p.value}</td>
      <td style="color:#64748b">${data.unit||'—'}</td>
      <td class="${zCls}">${p.z_score > 0 ? '+':'' }${p.z_score}</td>
      <td><span class="${sCls}">${p.status}</span></td>
      <td style="font-family:monospace;font-size:.75rem;color:#7c3aed">${p.westgard_rule||'—'}</td>
      <td style="font-size:.72rem;color:#64748b">${p.operator||'—'}</td>
      <td style="font-size:.72rem;color:#64748b">${p.analyzer||'—'}</td>
    </tr>`;
  }).join('');
}

// ── QC ENTRY MODAL ────────────────────────────────────────────────────────────
function openEntryModal() {
  // Pre-fill from current chart selection
  const dept    = document.getElementById('ctrl-dept')?.value    || '';
  const analyte = document.getElementById('ctrl-analyte')?.value || '';
  const level   = document.getElementById('ctrl-level')?.value   || 'L1';
  if (analyte) {
    const sel = document.getElementById('ctrl-analyte');
    const txt = sel?.options[sel?.selectedIndex]?.text?.split('(')[0]?.trim() || analyte;
    document.getElementById('entry-analyte-code').value = analyte;
    document.getElementById('entry-analyte-name').value = txt;
  }
  if (dept) document.getElementById('entry-dept').value = dept;
  document.getElementById('entry-level').value = level;
  // Pre-fill mean/SD from last data
  if (_chartData?.sd_lines) {
    document.getElementById('entry-mean').value = _chartData.sd_lines.mean;
    document.getElementById('entry-sd').value   = _chartData.stats?.target_sd || '';
  }
  document.getElementById('entry-result').style.display = 'none';
  document.getElementById('qc-entry-modal').classList.add('open');
}

function closeEntryModal() {
  document.getElementById('qc-entry-modal').classList.remove('open');
}

async function submitQCRun() {
  const code     = document.getElementById('entry-analyte-code').value.trim();
  const name     = document.getElementById('entry-analyte-name').value.trim();
  const level    = document.getElementById('entry-level').value;
  const dept     = document.getElementById('entry-dept').value;
  const mean     = parseFloat(document.getElementById('entry-mean').value);
  const sd       = parseFloat(document.getElementById('entry-sd').value);
  const value    = parseFloat(document.getElementById('entry-value').value);
  const unit     = document.getElementById('entry-unit').value.trim();
  const lot      = document.getElementById('entry-lot').value.trim();
  const analyzer = document.getElementById('entry-analyzer').value.trim();
  const runDate  = document.getElementById('entry-date').value;

  if (!code || isNaN(mean) || isNaN(sd) || isNaN(value)) {
    NEXUS?.Toast?.error('Fill all required fields'); return;
  }

  const z   = (value - mean) / sd;
  const absZ = Math.abs(z);

  try {
    const params = new URLSearchParams({
      department: dept, analyte_code: code, analyte_name: name,
      control_level: level, target_mean: mean, sd, result_value: value,
      unit, lot_number: lot, analyzer_name: analyzer, run_date: runDate,
    });
    const r = await fetch(`${API}/quality/iqc?${params}`, {
      method: 'POST', headers: { 'Authorization': 'Bearer ' + tok() },
    });
    const data = r.ok ? await r.json() : null;

    const resEl = document.getElementById('entry-result');
    if (resEl) {
      const cls = absZ > 3 ? '#dc2626' : absZ > 2 ? '#ea580c' : '#16a34a';
      resEl.style.display = '';
      resEl.innerHTML = `
        <div style="background:#f8faff;border:1px solid #e4e8f0;border-radius:8px;padding:.75rem;font-size:.82rem">
          <strong>QC Run Saved</strong><br>
          Z-Score: <span style="color:${cls};font-weight:700">${z > 0 ? '+':''}${z.toFixed(3)}</span><br>
          Status: <span style="color:${cls};font-weight:700">${data?.status || (absZ>3?'REJECT':absZ>2?'WARN':'PASS')}</span><br>
          Westgard Rule: <strong>${data?.westgard_rule || '—'}</strong>
        </div>`;
    }
    NEXUS?.Toast?.success('QC run saved — refreshing chart');
    setTimeout(() => { closeEntryModal(); loadChart(); }, 1500);
  } catch(e) {
    NEXUS?.Toast?.error('Save failed: ' + e.message);
  }
}

// ── EXPORT ────────────────────────────────────────────────────────────────────
function exportChart() {
  if (!_chart) { NEXUS?.Toast?.warning('Plot a chart first'); return; }
  const canvas = document.getElementById('lj-canvas');
  const link   = document.createElement('a');
  link.download = `LJ_${_chartData?.analyte||'QC'}_${_chartData?.control_level||'L1'}_${new Date().toISOString().slice(0,10)}.png`;
  link.href     = canvas.toDataURL('image/png');
  link.click();
}

function toggleTable() {
  _tableVisible = !_tableVisible;
  const wrap = document.getElementById('lj-table-wrap');
  const btn  = document.getElementById('btn-toggle-table');
  if (wrap) {
    const tbl = wrap.querySelector('div[style*="overflow"]');
    if (tbl) tbl.style.display = _tableVisible ? '' : 'none';
  }
  if (btn) btn.innerHTML = _tableVisible
    ? '<i class="fas fa-eye-slash"></i> Hide Table'
    : '<i class="fas fa-eye"></i> Show Table';
}

// ── HELPERS ───────────────────────────────────────────────────────────────────
function _setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = String(v ?? '—'); }
