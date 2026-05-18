/**
 * JORINOVA NEXUS ALIS-X — AI Nexus (Command Centre)
 * AI training, model management, analytics intelligence, research pipelines
 */
'use strict';

(function () {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function initTabs() {
    document.querySelectorAll('.ai-tab-nav .tab-btn, .tab-nav .tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const nav = btn.closest('.ai-tab-nav, .tab-nav');
        nav?.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        document.getElementById(btn.dataset.pane)?.classList.add('active');
        if (btn.dataset.pane === 'ai-models-pane') loadModels();
        if (btn.dataset.pane === 'ai-analytics-pane') loadAnalytics();
      });
    });
  }

  function loadDashboard() {
    const kpis = [
      { id:'kpi-ai-models', val:'12', label:'AI Models Active',      color:'var(--blue-glow)' },
      { id:'kpi-ai-preds',  val:'1,247', label:'Predictions Today',  color:'var(--cyan)' },
      { id:'kpi-ai-acc',    val:'94.3%', label:'Model Accuracy (avg)',color:'var(--alert-green)' },
      { id:'kpi-ai-flags',  val:'23',  label:'AI Flags Reviewed',    color:'var(--alert-yellow)' },
    ];
    kpis.forEach(k => {
      const el = document.getElementById(k.id); if (el) { el.textContent = k.val; el.style.color = k.color; }
    });
  }

  function loadModels() {
    const grid = document.getElementById('ai-model-grid');
    if (!grid || grid.innerHTML !== '') return;
    const models = [
      { name:'CBC Anemia Classifier', type:'Classification', dept:'Hematology', accuracy:96.2, predictions:247, status:'Active', last_trained:'2026-04-10' },
      { name:'Malaria Blood Film AI', type:'Image Recognition', dept:'Parasitology', accuracy:94.8, predictions:89, status:'Active', last_trained:'2026-03-22' },
      { name:'Gram Stain Morphology', type:'Image Segmentation', dept:'Microbiology', accuracy:91.5, predictions:134, status:'Active', last_trained:'2026-04-01' },
      { name:'Sepsis Early Warning', type:'Regression', dept:'Clinical', accuracy:88.3, predictions:312, status:'Active', last_trained:'2026-04-15' },
      { name:'Drug Interaction Checker', type:'NLP / Rules', dept:'Pharmacy', accuracy:99.1, predictions:58, status:'Active', last_trained:'2026-05-01' },
      { name:'Histopathology AI (Breast)', type:'Image CNN', dept:'Pathology', accuracy:93.7, predictions:42, status:'Beta', last_trained:'2026-04-28' },
      { name:'TB Resistance Predictor', type:'Genomic ML', dept:'Molecular', accuracy:97.4, predictions:18, status:'Active', last_trained:'2026-03-15' },
      { name:'EQA Performance Predictor', type:'Time Series', dept:'Quality', accuracy:82.1, predictions:12, status:'Experimental', last_trained:'2026-02-20' },
    ];
    grid.innerHTML = models.map(m => `
      <div class="ai-model-card">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:var(--space-sm)">
          <div>
            <div style="font-family:var(--font-display);font-size:var(--text-sm);font-weight:700;color:var(--text-primary)">${esc(m.name)}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:2px">${esc(m.type)} · ${esc(m.dept)}</div>
          </div>
          <span class="badge ${m.status==='Active'?'badge-green':m.status==='Beta'?'badge-blue':'badge-yellow'}">${esc(m.status)}</span>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:var(--space-sm)">
          <div style="font-size:11px"><span style="color:var(--text-muted)">Accuracy:</span>
            <strong style="color:${m.accuracy>95?'var(--alert-green)':m.accuracy>90?'var(--alert-yellow)':'var(--alert-orange)'}">${m.accuracy}%</strong></div>
          <div style="font-size:11px"><span style="color:var(--text-muted)">Predictions:</span> <strong>${m.predictions.toLocaleString()}</strong></div>
        </div>
        <div style="background:var(--bg-glass);border-radius:var(--radius-full);height:4px;overflow:hidden;margin-bottom:6px">
          <div style="height:100%;border-radius:var(--radius-full);background:${m.accuracy>95?'var(--alert-green)':m.accuracy>90?'var(--blue-glow)':'var(--alert-yellow)'};width:${m.accuracy}%"></div>
        </div>
        <div style="font-size:10px;color:var(--text-muted)">Last trained: ${esc(m.last_trained)}</div>
      </div>`).join('');
  }

  function loadAnalytics() {
    const canvas = document.getElementById('ai-accuracy-chart');
    if (!canvas || canvas._done || !window.Chart) return;
    canvas._done = true;
    new Chart(canvas, {
      type: 'bar',
      data: {
        labels: ['CBC Anemia','Malaria Film','Gram Stain','Sepsis Warning','Drug Interact.','Histopath','TB Resistance'],
        datasets: [{ label: 'Model Accuracy %', data:[96.2,94.8,91.5,88.3,99.1,93.7,97.4], backgroundColor:'rgba(0,153,255,.5)', borderColor:'var(--blue-glow)', borderWidth:1.5, borderRadius:4 }],
      },
      options: {
        responsive:true, maintainAspectRatio:false, indexAxis:'y',
        plugins:{ legend:{display:false} },
        scales:{
          x:{ min:75, max:100, grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#8899aa',callback:v=>v+'%'} },
          y:{ grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#aab',font:{size:10}} },
        },
      },
    });
  }

  /* ── Anomaly detection feed ─────────────────────────────── */
  function loadAnomalyFeed() {
    const feed = document.getElementById('ai-anomaly-feed');
    if (!feed) return;
    const ANOMALIES = [
      { time:'09:42', type:'🧪 Lab Pattern', msg:'Unusual spike in malaria positivity rate — 3× baseline (Eastern District cluster)', severity:'high' },
      { time:'09:15', type:'📦 Inventory',   msg:'Glucose reagent consumption +40% vs 7-day avg — possible analyzer calibration drift', severity:'warning' },
      { time:'08:51', type:'⏱️ TAT Alert',   msg:'Microbiology dept avg TAT: 108 min (threshold: 90 min) — workload peak detected', severity:'warning' },
      { time:'08:22', type:'🩸 Blood Bank',  msg:'B+ blood group stock critically low — 2 units remaining, reorder threshold breached', severity:'high' },
      { time:'07:44', type:'🔐 Security',    msg:'Unusual login pattern: user accessed 47 patient records in 4 minutes (baseline: 5)', severity:'critical' },
    ];
    const sevColors = { critical:'rgba(255,23,68,.1)', high:'rgba(255,109,0,.08)', warning:'rgba(255,214,0,.06)' };
    const sevBorder = { critical:'rgba(255,23,68,.3)', high:'rgba(255,109,0,.25)', warning:'rgba(255,214,0,.2)' };
    feed.innerHTML = ANOMALIES.map(a => `
      <div style="padding:var(--space-sm) var(--space-md);background:${sevColors[a.severity]};border:1px solid ${sevBorder[a.severity]};border-radius:var(--radius-md);margin-bottom:var(--space-sm)">
        <div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:3px">
          <span style="font-size:11px;font-weight:700;color:var(--text-primary)">${esc(a.type)}</span>
          <span style="font-size:10px;color:var(--text-muted);margin-left:auto">${esc(a.time)}</span>
          <span class="badge ${a.severity==='critical'?'badge-red':a.severity==='high'?'badge-orange':'badge-yellow'}" style="font-size:8px">${a.severity}</span>
        </div>
        <div style="font-size:var(--text-xs);color:var(--text-secondary);line-height:1.5">${esc(a.msg)}</div>
      </div>`).join('');
  }

  /* ── Predictions feed ───────────────────────────────────── */
  function loadPredictionsFeed() {
    const feed = document.getElementById('ai-predictions-feed');
    if (!feed) return;
    const PREDS = [
      { model:'Sepsis Early Warning', patient:'HABIMANA Eric (ICU-03)', prediction:'HIGH RISK — Septic shock progression 78%', action:'Escalate vasopressors', time:'09:44' },
      { model:'CBC Anemia Classifier', patient:'KAMANZI Jean', prediction:'Severe Iron Deficiency Anemia — transfusion threshold', action:'Haematology review', time:'09:28' },
      { model:'Drug Interaction', patient:'MUKAMANA Rose', prediction:'Potential Cisplatin + Metronidazole interaction (low risk)', action:'Monitor renal function', time:'08:55' },
    ];
    feed.innerHTML = PREDS.map(p => `
      <div style="padding:var(--space-md);background:var(--bg-glass);border:1px solid var(--border-dim);border-radius:var(--radius-md);margin-bottom:var(--space-sm)">
        <div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:4px">
          <span style="font-size:11px;font-weight:700;color:var(--blue-glow)">${esc(p.model)}</span>
          <span style="font-size:10px;color:var(--text-muted);margin-left:auto">${esc(p.time)}</span>
        </div>
        <div style="font-size:var(--text-xs);color:var(--text-muted);margin-bottom:3px">👤 ${esc(p.patient)}</div>
        <div style="font-size:var(--text-xs);font-weight:600;color:var(--text-primary);margin-bottom:3px">${esc(p.prediction)}</div>
        <div style="font-size:10px;color:var(--cyan)">→ Suggested: ${esc(p.action)}</div>
      </div>`).join('');
  }

  /* Flag check + interpret (AI Nexus) */
  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': window.NEXUS?.csrf || '',
      },
      credentials: 'same-origin',
      body: JSON.stringify(payload),
    });
    const txt = await res.text();
    let data;
    try { data = JSON.parse(txt); } catch (_) { data = { detail: txt }; }
    if (!res.ok) {
      const msg = data?.detail || data?.message || `HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  function readForm() {
    const test_code = document.getElementById('ai-test-code')?.value?.trim() || '';
    const valueStr  = document.getElementById('ai-test-value')?.value;
    const unit       = document.getElementById('ai-test-unit')?.value?.trim() || '';
    const sex        = document.getElementById('ai-test-sex')?.value || '';
    const ageStr     = document.getElementById('ai-test-age')?.value;
    const ref_range  = document.getElementById('ai-test-ref')?.value?.trim() || '';

    const value = valueStr === '' || valueStr === null || valueStr === undefined ? null : Number(valueStr);
    const age   = ageStr   === '' || ageStr   === null || ageStr   === undefined ? 0 : Number(ageStr);

    return { test_code, value, unit, sex, age, ref_range };
  }

  function showResult(obj) {
    const wrap = document.getElementById('ai-flag-result');
    const pre  = document.getElementById('ai-flag-result-pre');
    if (!wrap || !pre) return;
    pre.textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
    wrap.style.display = 'block';
  }

  function toastError(msg) {
    window.NEXUS?.Toast?.error?.('AI Nexus Error', msg);
  }

  function initFlagInterpret() {
    const btnFlag = document.getElementById('ai-btn-flag-check');
    const btnFull = document.getElementById('ai-btn-interpret');
    if (!btnFlag || !btnFull) return;

    btnFlag.addEventListener('click', async () => {
      const f = readForm();
      if (!f.test_code) return toastError('Test code is required');
      if (f.value === null || Number.isNaN(f.value)) return toastError('Test value must be a number');

      try {
        const payload = {
          test_code: f.test_code,
          value: f.value,
          unit: f.unit,
          sex: f.sex,
          age: f.age,
        };
        const data = await postJSON('/api/v1/ai/flag-check', payload);
        showResult({ layer: data?.layer || 'rules_engine', result: data });
      } catch (e) {
        toastError(e?.message || String(e));
      }
    });

    btnFull.addEventListener('click', async () => {
      const f = readForm();
      if (!f.test_code) return toastError('Test code is required');
      if (f.value === null || Number.isNaN(f.value)) return toastError('Test value must be a number');

      try {
        const payload = {
          test_code: f.test_code,
          test_name: f.test_code, // UI doesn’t have name; backend accepts any string
          value: String(f.value),
          unit: f.unit,
          sex: f.sex,
          age: f.age,
          flag: '',
          ref_range: f.ref_range,
        };
        const data = await postJSON('/api/v1/ai/interpret', payload);
        showResult({ result: data });
      } catch (e) {
        toastError(e?.message || String(e));
      }
    });
  }

  function init() {
    initTabs();
    loadDashboard();
    setTimeout(() => { loadAnomalyFeed(); loadPredictionsFeed(); }, 100);
    initFlagInterpret();
  }
  document.addEventListener('DOMContentLoaded', init);
})();

