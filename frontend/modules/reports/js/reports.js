/**
 * JORINOVA NEXUS ALIS-X — Reports & Analytics Intelligence
 * Live KPIs · Charts · Lab Results · TAT Analysis · Epidemiology · Financial
 */
'use strict';

(function () {
  const NEXUS = window.NEXUS || {};
  const API   = NEXUS.API   || { get:(u,p)=>fetch('/api/v1'+u+(p?'?'+new URLSearchParams(p):'')), json:r=>r.json() };
  const Toast = NEXUS.Toast || { info:(t,m)=>console.log(t,m), error:(t,m)=>console.error(t,m) };
  const esc   = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt   = { date:d=>d?new Date(d).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}):'—', datetime:d=>d?new Date(d).toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):'—' };
  const $     = id => document.getElementById(id);

  /* ── State ─────────────────────────────────────────────────── */
  let activePane  = 'overview-pane';
  let period      = 'month';
  let charts      = {};  // cached chart instances

  /* ── Demo data ─────────────────────────────────────────────── */
  const DEMO = {
    overview: { patients:1247, tests:3891, tat_avg:42, critical:87, revenue:18750000 },
    daily_volume: [38,52,44,61,48,55,63,41,58,67,45,52,48,71,39,55,62,48,53,44,59,66,41,57,62,47,54,48,61,58],
    dept_distribution: { Hematology:38, Chemistry:29, Microbiology:14, Serology:11, 'Blood Bank':5, Coagulation:3 },
    dept_summary: [
      { name:'Hematology', tests:1478, completed:1401, pending:77, critical:28, tat:38 },
      { name:'Chemistry',  tests:1129, completed:1089, pending:40, critical:31, tat:52 },
      { name:'Microbiology',tests:544, completed:501,  pending:43, critical:12, tat:72 },
      { name:'Serology',   tests:428,  completed:418,  pending:10, critical:9,  tat:34 },
      { name:'Blood Bank', tests:194,  completed:189,  pending:5,  critical:5,  tat:28 },
      { name:'Coagulation',tests:118,  completed:115,  pending:3,  critical:2,  tat:41 },
    ],
    results_log: [
      { lab_id:'LAB-240515-001', patient:'KAMANZI Jean', test:'Full Blood Count', result:'HGB 6.2 g/dL', ref:'13–17', flag:'LL', validated_by:'Dr. MUGENZI', date:new Date().toISOString() },
      { lab_id:'LAB-240515-002', patient:'UWIMANA Grace', test:'Glucose (Fasting)', result:'3.1 mmol/L', ref:'3.9–6.1', flag:'L', validated_by:'Lab Tech NKUSI', date:new Date(Date.now()-3600000).toISOString() },
      { lab_id:'LAB-240515-003', patient:'HABIMANA Eric', test:'Prothrombin Time', result:'28.4 sec', ref:'11–13', flag:'HH', validated_by:'Dr. UWIMANA', date:new Date(Date.now()-7200000).toISOString() },
      { lab_id:'LAB-240514-089', patient:'MUKAMANA Rose', test:'HBsAg', result:'Reactive', ref:'Non-reactive', flag:'A', validated_by:'Lab Tech BIGIRIMANA', date:new Date(Date.now()-86400000).toISOString() },
      { lab_id:'LAB-240514-077', patient:'NIYOMUGABO Paul', test:'Creatinine', result:'312 µmol/L', ref:'62–106', flag:'HH', validated_by:'Dr. NSENGIMANA', date:new Date(Date.now()-90000000).toISOString() },
      { lab_id:'LAB-240513-042', patient:'INGABIRE Marie', test:'HIV Viral Load', result:'<50 cp/mL', ref:'Undetectable', flag:'N', validated_by:'Dr. MUGENZI', date:new Date(Date.now()-172800000).toISOString() },
    ],
    tat_by_dept: { Hematology:38, Chemistry:52, Microbiology:72, Serology:34, 'Blood Bank':28, Coagulation:41 },
    sla_compliance: { 'On-Time':72, Warning:16, Breach:12 },
    epi_diseases: [
      { name:'Malaria', cases:142, this_month:38, trend:'↑', alert:'warning', last_week:29 },
      { name:'Typhoid', cases:67, this_month:18, trend:'→', alert:'normal', last_week:17 },
      { name:'HIV (new)', cases:23, this_month:6, trend:'↓', alert:'normal', last_week:8 },
      { name:'Tuberculosis', cases:31, this_month:9, trend:'↑', alert:'warning', last_week:6 },
      { name:'Hepatitis B', cases:18, this_month:4, trend:'→', alert:'normal', last_week:4 },
      { name:'Septicaemia', cases:12, this_month:5, trend:'↑↑', alert:'critical', last_week:2 },
    ],
    resistance: [
      { organism:'E. coli', resistant:['Ampicillin','Cotrimoxazole'], susceptible:['Meropenem','Fosfomycin'], rate:68 },
      { organism:'Staphylococcus aureus (MRSA)', resistant:['Methicillin','Oxacillin'], susceptible:['Vancomycin','Linezolid'], rate:34 },
      { organism:'K. pneumoniae (ESBL)', resistant:['Cephalosporins','Augmentin'], susceptible:['Carbapenems'], rate:41 },
    ],
    financial: {
      revenue_trend:[45000,62000,38000,71000,55000,48000,29000],
      top_tests:[['CBC',342,1197000],['Chemistry Panel',218,2616000],['HIV RDT',285,855000],['Malaria RDT',312,624000],['HbA1c',89,534000]],
      payment_methods:{ Cash:45, 'MTN MoMo':22, RSSB:18, Mutuelle:12, Bank:3 },
      dept_revenue:{ Hematology:7450000, Chemistry:5820000, Microbiology:2720000, Serology:1710000, 'Blood Bank':980000, Coagulation:70000 },
    },
  };

  /* ════════════════════════════════════════════════════════════
     TAB SWITCHING
  ════════════════════════════════════════════════════════════ */
  document.querySelectorAll('.reports-tab-nav .tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.reports-tab-nav .tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      activePane = btn.dataset.pane;
      const pane = $(activePane);
      if (pane) pane.classList.add('active');
      onPaneChange(activePane);
    });
  });

  function onPaneChange(pane) {
    if (pane === 'overview-pane')    loadOverview();
    if (pane === 'lab-results-pane') loadLabResults();
    if (pane === 'tat-pane')         loadTATAnalysis();
    if (pane === 'epi-pane')         loadEpidemiology();
    if (pane === 'financial-pane')   loadFinancial();
  }

  /* ── Period change ─────────────────────────────────────────── */
  $('report-period')?.addEventListener('change', e => {
    period = e.target.value;
    onPaneChange(activePane);
  });

  $('export-btn')?.addEventListener('click', () => Toast.info('Export', 'Generating PDF/Excel report…'));

  /* ════════════════════════════════════════════════════════════
     OVERVIEW
  ════════════════════════════════════════════════════════════ */
  function loadOverview() {
    const d = DEMO.overview;
    setKPI('kpi-patients', d.patients.toLocaleString());
    setKPI('kpi-tests',    d.tests.toLocaleString());
    setKPI('kpi-tat',      d.tat_avg);
    setKPI('kpi-critical', d.critical.toLocaleString());
    setKPI('kpi-revenue',  (d.revenue/1000000).toFixed(2)+'M');

    renderDailyVolumeChart();
    renderDeptPieChart();
    renderDeptTable();
  }

  function setKPI(id, val) { const el = $(id); if (el) el.textContent = val; }

  function renderDailyVolumeChart() {
    const canvas = $('rpt-bar-chart');
    if (!canvas || !window.Chart) return;
    if (charts.bar) { charts.bar.destroy(); }
    const now = new Date();
    const days = Array.from({length:30}, (_,i) => { const d=new Date(now); d.setDate(d.getDate()-(29-i)); return d.getDate().toString(); });
    charts.bar = new Chart(canvas, {
      type:'bar',
      data:{ labels:days, datasets:[{ label:'Tests', data:DEMO.daily_volume, backgroundColor:'rgba(0,153,255,.4)', borderColor:'var(--blue-glow)', borderWidth:1.5, borderRadius:3 }] },
      options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{grid:{color:'rgba(255,255,255,.03)'}, ticks:{color:'#8899aa',font:{size:9}}}, y:{grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#8899aa'}} } }
    });
  }

  function renderDeptPieChart() {
    const canvas = $('rpt-dept-pie');
    if (!canvas || !window.Chart) return;
    if (charts.pie) charts.pie.destroy();
    const labels = Object.keys(DEMO.dept_distribution);
    const data   = Object.values(DEMO.dept_distribution);
    const colors = ['#FF4466','#3498DB','#2ECC71','#9B59B6','#E74C3C','#E67E22'];
    charts.pie = new Chart(canvas, {
      type:'doughnut',
      data:{ labels, datasets:[{ data, backgroundColor:colors, borderWidth:0 }] },
      options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{ display:false } } }
    });
    const legend = $('rpt-dept-legend');
    if (legend) legend.innerHTML = labels.map((l,i) => `<div style="display:flex;align-items:center;gap:4px;font-size:10px;color:var(--text-muted)"><div style="width:10px;height:10px;border-radius:50%;background:${colors[i]};flex-shrink:0"></div>${esc(l)}: ${data[i]}%</div>`).join('');
  }

  function renderDeptTable() {
    const tbody = $('dept-summary-tbody');
    if (!tbody) return;
    tbody.innerHTML = DEMO.dept_summary.map(d => {
      const pct = Math.round((d.completed / d.tests) * 100);
      const pctColor = pct >= 90 ? 'var(--alert-green)' : pct >= 75 ? 'var(--alert-yellow)' : 'var(--alert-orange)';
      return `<tr>
        <td style="font-weight:700;color:var(--text-primary)">${esc(d.name)}</td>
        <td style="font-family:var(--font-mono)">${d.tests.toLocaleString()}</td>
        <td style="font-family:var(--font-mono);color:var(--alert-green)">${d.completed.toLocaleString()}</td>
        <td style="font-family:var(--font-mono);color:${d.pending > 50 ? 'var(--alert-orange)' : 'var(--text-muted)'}">${d.pending}</td>
        <td style="font-family:var(--font-mono);color:${d.critical > 20 ? 'var(--alert-red)' : 'var(--text-muted)'}">${d.critical}</td>
        <td style="font-family:var(--font-mono)">${d.tat} min</td>
        <td>
          <div style="display:flex;align-items:center;gap:var(--space-sm)">
            <div style="flex:1;height:6px;background:var(--bg-glass);border-radius:3px;overflow:hidden">
              <div style="height:100%;width:${pct}%;background:${pctColor};border-radius:3px"></div>
            </div>
            <span style="font-size:11px;font-family:var(--font-mono);color:${pctColor}">${pct}%</span>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  /* ════════════════════════════════════════════════════════════
     LAB RESULTS LOG
  ════════════════════════════════════════════════════════════ */
  function loadLabResults() {
    const filter = $('results-filter')?.value || '';
    let list = DEMO.results_log;
    if (filter === 'critical') list = list.filter(r => r.flag === 'HH' || r.flag === 'LL');
    else if (filter === 'abnormal') list = list.filter(r => ['H','L','A','HH','LL'].includes(r.flag));
    else if (filter === 'normal') list = list.filter(r => r.flag === 'N');

    const tbody = $('results-tbody');
    if (!tbody) return;
    const flagColors = { HH:'var(--alert-red)', LL:'var(--alert-red)', H:'var(--alert-orange)', L:'var(--alert-orange)', A:'var(--alert-orange)', N:'var(--alert-green)' };
    const flagLabels = { HH:'🔴 Critical H', LL:'🔴 Critical L', H:'🟠 High', L:'🟠 Low', A:'⚠️ Abnormal', N:'✅ Normal' };
    tbody.innerHTML = list.map(r => `<tr>
      <td style="font-family:var(--font-mono);font-size:11px;color:var(--blue-glow)">${esc(r.lab_id)}</td>
      <td style="font-size:var(--text-xs);font-weight:700">${esc(r.patient)}</td>
      <td style="font-size:var(--text-xs)">${esc(r.test)}</td>
      <td style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:${flagColors[r.flag]||'var(--text-primary)'}">${esc(r.result)}</td>
      <td style="font-size:10px;color:var(--text-muted)">${esc(r.ref)}</td>
      <td><span style="font-size:10px;padding:2px 7px;border-radius:3px;background:rgba(255,255,255,.06);color:${flagColors[r.flag]||'var(--text-muted)'};">${flagLabels[r.flag]||r.flag}</span></td>
      <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(r.validated_by)}</td>
      <td style="font-size:10px;color:var(--text-muted)">${fmt.datetime(r.date)}</td>
    </tr>`).join('');
  }

  let resultsSearchTimer = null;
  $('results-search')?.addEventListener('input', () => { clearTimeout(resultsSearchTimer); resultsSearchTimer = setTimeout(loadLabResults, 300); });
  $('results-filter')?.addEventListener('change', loadLabResults);

  /* ════════════════════════════════════════════════════════════
     TAT ANALYSIS
  ════════════════════════════════════════════════════════════ */
  function loadTATAnalysis() {
    const c1 = $('tat-bar-chart');
    if (c1 && window.Chart) {
      if (charts.tatBar) charts.tatBar.destroy();
      const depts = Object.keys(DEMO.tat_by_dept);
      const tats  = Object.values(DEMO.tat_by_dept);
      const colors = tats.map(t => t <= 45 ? 'rgba(0,230,118,.5)' : t <= 60 ? 'rgba(255,214,0,.5)' : 'rgba(255,109,0,.5)');
      charts.tatBar = new Chart(c1, {
        type:'bar',
        data:{ labels:depts, datasets:[{ label:'Avg TAT (min)', data:tats, backgroundColor:colors, borderColor:colors.map(c=>c.replace('.5','1')), borderWidth:1.5, borderRadius:4 }] },
        options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{display:false}, tooltip:{ callbacks:{ label: ctx => `${ctx.raw} min (${ctx.raw <= 45 ? '✅ OK' : ctx.raw <= 60 ? '⚠️ Warning' : '❌ Breach'})` } } }, scales:{ x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#8899aa'}}, y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#8899aa'},title:{display:true,text:'Minutes',color:'#8899aa'}} } }
      });
    }
    const c2 = $('sla-pie-chart');
    if (c2 && window.Chart) {
      if (charts.sla) charts.sla.destroy();
      const d = DEMO.sla_compliance;
      charts.sla = new Chart(c2, {
        type:'doughnut',
        data:{ labels:Object.keys(d), datasets:[{ data:Object.values(d), backgroundColor:['rgba(0,230,118,.7)','rgba(255,214,0,.7)','rgba(255,23,68,.7)'], borderWidth:0 }] },
        options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{ labels:{ color:'#8899aa', font:{size:10} } } } }
      });
    }
  }

  /* ════════════════════════════════════════════════════════════
     EPIDEMIOLOGY
  ════════════════════════════════════════════════════════════ */
  function loadEpidemiology() {
    const pane = $('epi-pane');
    if (!pane) return;
    pane.innerHTML = `
      <div style="padding:var(--space-xl);display:flex;flex-direction:column;gap:var(--space-lg)">

        <!-- Threat level -->
        <div style="display:flex;align-items:center;gap:var(--space-lg);padding:var(--space-lg);background:rgba(255,109,0,.06);border:1px solid rgba(255,109,0,.25);border-radius:var(--radius-lg)">
          <div style="font-size:40px">⚠️</div>
          <div>
            <div style="font-family:var(--font-display);font-size:var(--text-xl);font-weight:700;color:var(--alert-orange)">THREAT LEVEL: MODERATE</div>
            <div style="font-size:var(--text-xs);color:var(--text-secondary);margin-top:4px">Malaria cases ↑12% this week · Septicaemia cluster detected · Routine surveillance active</div>
          </div>
          <div style="margin-left:auto;text-align:right">
            <div style="font-size:10px;color:var(--text-muted)">Last updated</div>
            <div style="font-size:var(--text-sm);font-weight:700;color:var(--text-primary)">${new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})}</div>
          </div>
        </div>

        <!-- Disease table -->
        <div class="glass-panel" style="overflow:hidden">
          <div style="padding:var(--space-md) var(--space-lg);border-bottom:1px solid var(--border-dim);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted)">🦠 Disease Surveillance — ${new Date().toLocaleDateString('en-GB',{month:'long',year:'numeric'})}</div>
          <table class="nx-table">
            <thead><tr><th>Disease</th><th>Total Cases (Period)</th><th>This Month</th><th>Last Week</th><th>Trend</th><th>Alert Level</th></tr></thead>
            <tbody>
              ${DEMO.epi_diseases.map(d => `<tr>
                <td style="font-weight:700">${esc(d.name)}</td>
                <td style="font-family:var(--font-mono)">${d.cases}</td>
                <td style="font-family:var(--font-mono);font-weight:700">${d.this_month}</td>
                <td style="font-family:var(--font-mono)">${d.last_week}</td>
                <td style="font-size:16px;font-weight:700;color:${d.trend.includes('↑↑') ? 'var(--alert-red)' : d.trend.includes('↑') ? 'var(--alert-orange)' : d.trend.includes('↓') ? 'var(--alert-green)' : 'var(--text-muted)'}">${d.trend}</td>
                <td><span class="badge ${d.alert==='critical'?'badge-red':d.alert==='warning'?'badge-orange':'badge-green'}">${d.alert==='critical'?'🚨 Critical':d.alert==='warning'?'⚠️ Warning':'✅ Normal'}</span></td>
              </tr>`).join('')}
            </tbody>
          </table>
        </div>

        <!-- Antibiotic resistance -->
        <div class="glass-panel" style="padding:var(--space-lg)">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:var(--space-md)">🧬 Antimicrobial Resistance Patterns</div>
          <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:var(--space-md)">
            ${DEMO.resistance.map(r => `
              <div style="padding:var(--space-md);background:var(--bg-glass);border:1px solid var(--border-dim);border-radius:var(--radius-md)">
                <div style="font-weight:700;font-size:var(--text-sm);margin-bottom:var(--space-sm)">${esc(r.organism)}</div>
                <div style="display:flex;align-items:center;gap:var(--space-sm);margin-bottom:var(--space-sm)">
                  <div style="flex:1;height:8px;background:var(--bg-deep);border-radius:4px;overflow:hidden">
                    <div style="height:100%;width:${r.rate}%;background:var(--alert-red);border-radius:4px"></div>
                  </div>
                  <span style="font-family:var(--font-mono);font-size:12px;font-weight:700;color:var(--alert-red)">${r.rate}%</span>
                </div>
                <div style="font-size:10px;color:var(--alert-red)">Resistant: ${r.resistant.join(', ')}</div>
                <div style="font-size:10px;color:var(--alert-green);margin-top:2px">Susceptible: ${r.susceptible.join(', ')}</div>
              </div>`).join('')}
          </div>
        </div>

      </div>`;
  }

  /* ════════════════════════════════════════════════════════════
     FINANCIAL REPORTS
  ════════════════════════════════════════════════════════════ */
  function loadFinancial() {
    const pane = $('financial-pane');
    if (!pane) return;
    const f = DEMO.financial;
    pane.innerHTML = `
      <div style="padding:var(--space-xl);display:grid;grid-template-columns:1fr 1fr 1fr;gap:var(--space-lg)">

        <!-- Revenue trend -->
        <div class="glass-panel" style="grid-column:span 2;padding:var(--space-lg)">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:var(--space-md)">📈 Revenue Trend (7 days)</div>
          <div style="height:180px"><canvas id="fin-revenue-chart"></canvas></div>
        </div>

        <!-- Payment methods -->
        <div class="glass-panel" style="padding:var(--space-lg)">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:var(--space-md)">💳 Payment Methods</div>
          <div style="height:180px"><canvas id="fin-method-chart"></canvas></div>
        </div>

        <!-- Top tests -->
        <div class="glass-panel" style="padding:var(--space-lg)">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:var(--space-md)">🧪 Top Revenue Tests</div>
          ${f.top_tests.map(([t,count,rev]) => `
            <div style="display:flex;justify-content:space-between;align-items:center;padding:5px 0;border-bottom:1px solid var(--border-dim);font-size:var(--text-xs)">
              <div>
                <div style="font-weight:700;color:var(--text-primary)">${esc(t)}</div>
                <div style="font-size:10px;color:var(--text-muted)">${count} tests</div>
              </div>
              <div style="font-family:var(--font-mono);font-weight:700;color:#00d4aa">${(rev/1000).toFixed(0)}K RWF</div>
            </div>`).join('')}
        </div>

        <!-- Dept revenue -->
        <div class="glass-panel" style="grid-column:span 2;padding:var(--space-lg)">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:var(--space-md)">🏢 Revenue by Department</div>
          ${Object.entries(f.dept_revenue).map(([dept,rev]) => {
            const max = Math.max(...Object.values(f.dept_revenue));
            const pct = Math.round(rev/max*100);
            return `<div style="margin-bottom:var(--space-sm)">
              <div style="display:flex;justify-content:space-between;font-size:var(--text-xs);margin-bottom:3px">
                <span style="color:var(--text-primary);font-weight:600">${esc(dept)}</span>
                <span style="font-family:var(--font-mono);color:#00d4aa">${(rev/1000).toFixed(0)}K RWF</span>
              </div>
              <div style="height:6px;background:var(--bg-glass);border-radius:3px;overflow:hidden">
                <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,rgba(0,212,170,.6),rgba(0,153,255,.4));border-radius:3px"></div>
              </div>
            </div>`;
          }).join('')}
        </div>

      </div>`;

    // Render charts after DOM update
    setTimeout(() => {
      const rc = $('fin-revenue-chart');
      if (rc && window.Chart) {
        new Chart(rc, { type:'line', data:{ labels:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'], datasets:[{ data:f.revenue_trend, borderColor:'#00d4aa', backgroundColor:'rgba(0,212,170,.1)', fill:true, tension:.4, pointRadius:4 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#8899aa'}}, y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#8899aa',callback:v=>(v/1000)+'K'}} } } });
      }
      const mc = $('fin-method-chart');
      if (mc && window.Chart) {
        new Chart(mc, { type:'doughnut', data:{ labels:Object.keys(f.payment_methods), datasets:[{ data:Object.values(f.payment_methods), backgroundColor:['#27AE60','#F39C12','#2980B9','#16A085','#95A5A6'], borderWidth:0 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{ legend:{ position:'right', labels:{ color:'#8899aa', font:{size:9} } } } } });
      }
    }, 100);
  }

  /* ── Init ─────────────────────────────────────────────────── */
  loadOverview();
})();
