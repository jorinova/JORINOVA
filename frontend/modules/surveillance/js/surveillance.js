/**
 * JORINOVA NEXUS ALIS-X — Epidemiological Surveillance
 * Disease trends · Outbreak detection · Resistance monitoring · Public health reporting
 */
'use strict';

(function () {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function initTabs() {
    document.querySelectorAll('.surv-tab-nav .tab-btn, .tab-nav .tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const nav = btn.closest('.tab-nav, .surv-tab-nav');
        const body = document.querySelector('.surv-body, .tab-body');
        nav?.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const paneId = btn.dataset.pane;
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        document.getElementById(paneId)?.classList.add('active');
        const actions = {
          'surv-outbreak-pane':    loadOutbreakMap,
          'surv-resistance-pane':  loadResistanceData,
          'surv-analytics-pane':   loadAnalytics,
        };
        actions[paneId]?.();
      });
    });
  }

  function loadDashboard() {
    const kpis = [
      { id:'kpi-surv-diseases', val:'12', label:'Notifiable Diseases Tracked', color:'var(--blue-glow)' },
      { id:'kpi-surv-alerts',   val:'3',  label:'Active Outbreak Alerts',       color:'var(--alert-orange)' },
      { id:'kpi-surv-resist',   val:'8',  label:'AMR Events This Month',        color:'var(--alert-red)' },
      { id:'kpi-surv-reported', val:'47', label:'Reports Sent to MOH',          color:'var(--alert-green)' },
    ];
    kpis.forEach(k => {
      const el = document.getElementById(k.id);
      if (el) { el.textContent = k.val; el.style.color = k.color; }
    });

    /* Disease trend table */
    const tbody = document.getElementById('surv-disease-tbody');
    if (tbody && tbody.innerHTML === '') {
      const diseases = [
        { name:'Malaria (P. falciparum)', cases:124, last_week:98, trend:'↑ +27%', alert:true, level:'HIGH' },
        { name:'Pulmonary Tuberculosis', cases:18, last_week:21, trend:'↓ -14%', alert:false, level:'NORMAL' },
        { name:'Typhoid (S. typhi)', cases:31, last_week:27, trend:'↑ +15%', alert:false, level:'WATCH' },
        { name:'Cholera (V. cholerae)', cases:4, last_week:1, trend:'↑ +300%', alert:true, level:'ALERT' },
        { name:'COVID-19', cases:9, last_week:12, trend:'↓ -25%', alert:false, level:'NORMAL' },
        { name:'Meningococcal Disease', cases:2, last_week:0, trend:'↑ NEW', alert:true, level:'ALERT' },
        { name:'HIV (new diagnoses)', cases:7, last_week:8, trend:'↓ -12%', alert:false, level:'NORMAL' },
        { name:'Brucellosis', cases:5, last_week:3, trend:'↑ +67%', alert:false, level:'WATCH' },
      ];
      tbody.innerHTML = diseases.map(d => `<tr>
        <td><strong>${esc(d.name)}</strong></td>
        <td style="font-family:var(--font-mono);font-size:13px;font-weight:700;text-align:center">${d.cases}</td>
        <td style="font-family:var(--font-mono);font-size:11px;text-align:center;color:var(--text-muted)">${d.last_week}</td>
        <td style="font-weight:700;color:${d.trend.startsWith('↑')?'var(--alert-orange)':'var(--alert-green)'}">${esc(d.trend)}</td>
        <td><span class="badge ${d.level==='ALERT'?'badge-red':d.level==='HIGH'?'badge-orange':d.level==='WATCH'?'badge-yellow':'badge-blue'}">${esc(d.level)}</span></td>
        <td>${d.alert ? '<span style="color:var(--alert-red);font-size:12px">🚨 Alert active</span>' : '<span style="color:var(--text-muted);font-size:11px">—</span>'}</td>
      </tr>`).join('');
    }
  }

  function loadOutbreakMap() {
    const mapEl = document.getElementById('surv-map-placeholder');
    if (mapEl && mapEl.innerHTML === '') {
      mapEl.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:300px;gap:16px;color:var(--text-muted)">
        <div style="font-size:56px">🗺️</div>
        <div style="font-size:var(--text-sm)">Rwanda Province Map — GeoTrack Integration</div>
        <div style="font-size:var(--text-xs)">Live outbreak clustering requires GeoTrack module connection</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;justify-content:center">
          <span style="padding:4px 12px;background:rgba(255,23,68,.15);border-radius:20px;font-size:11px;color:var(--alert-red)">🔴 Eastern: Cholera alert</span>
          <span style="padding:4px 12px;background:rgba(255,109,0,.15);border-radius:20px;font-size:11px;color:var(--alert-orange)">🟠 Kigali: Malaria spike</span>
          <span style="padding:4px 12px;background:rgba(255,214,0,.15);border-radius:20px;font-size:11px;color:var(--alert-yellow)">🟡 Northern: Typhoid watch</span>
        </div>
      </div>`;
    }
  }

  function loadResistanceData() {
    const tbody = document.getElementById('surv-amr-tbody');
    if (!tbody || tbody.innerHTML !== '') return;
    const amr = [
      { organism:'E. coli', pattern:'ESBL producer', antibiotic:'Cephalosporins', rate:'34%', trend:'↑', color:'var(--alert-orange)' },
      { organism:'K. pneumoniae', pattern:'CRE/CPE', antibiotic:'Carbapenems', rate:'12%', trend:'↑', color:'var(--alert-red)' },
      { organism:'S. aureus', pattern:'MRSA', antibiotic:'Methicillin', rate:'22%', trend:'→', color:'var(--alert-orange)' },
      { organism:'M. tuberculosis', pattern:'MDR-TB', antibiotic:'INH + RIF', rate:'5%', trend:'↓', color:'var(--alert-yellow)' },
      { organism:'Enterococcus sp.', pattern:'VRE', antibiotic:'Vancomycin', rate:'7%', trend:'↑', color:'var(--alert-red)' },
      { organism:'P. aeruginosa', pattern:'Pan-resistant', antibiotic:'Multiple', rate:'18%', trend:'↑', color:'var(--alert-red)' },
    ];
    tbody.innerHTML = amr.map(a => `<tr>
      <td><em style="font-style:italic">${esc(a.organism)}</em></td>
      <td><span class="badge badge-red">${esc(a.pattern)}</span></td>
      <td style="font-size:var(--text-xs)">${esc(a.antibiotic)}</td>
      <td style="font-family:var(--font-mono);font-weight:700;color:${a.color}">${esc(a.rate)}</td>
      <td style="font-weight:700;color:${a.trend==='↑'?'var(--alert-red)':a.trend==='↓'?'var(--alert-green)':'var(--text-muted)'}">${a.trend}</td>
    </tr>`).join('');
  }

  function loadAnalytics() {
    const canvas = document.getElementById('surv-trend-chart');
    if (!canvas || canvas._done || !window.Chart) return;
    canvas._done = true;
    const months = ['Nov','Dec','Jan','Feb','Mar','Apr','May'];
    new Chart(canvas, {
      type: 'line',
      data: {
        labels: months,
        datasets: [
          { label:'Malaria', data:[88,102,95,118,132,98,124], borderColor:'#FF6D00', tension:0.4, fill:false, pointRadius:4 },
          { label:'Typhoid', data:[22,18,25,28,31,27,31],     borderColor:'#FFD600', tension:0.4, fill:false, pointRadius:4 },
          { label:'TB',      data:[25,22,19,21,18,21,18],     borderColor:'#00AAFF', tension:0.4, fill:false, pointRadius:4 },
          { label:'Cholera', data:[0,0,1,0,0,1,4],             borderColor:'#FF1744', tension:0.4, fill:false, pointRadius:5, borderWidth:3 },
        ],
      },
      options: {
        responsive:true, maintainAspectRatio:false,
        plugins:{ legend:{ labels:{ color:'#aab', font:{size:11} } } },
        scales:{
          x:{ grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#8899aa'} },
          y:{ grid:{color:'rgba(255,255,255,.06)'}, ticks:{color:'#8899aa'}, title:{display:true,text:'Cases',color:'#8899aa'} },
        },
      },
    });
  }

  /* ── Real-time alert engine ─────────────────────────────── */
  function startAlertEngine() {
    const banner = document.getElementById('surv-alert-banner');
    const threat = document.getElementById('surv-threat-level');
    const dot    = threat?.querySelector('.surv-threat-dot');
    const label  = threat?.querySelector('.surv-threat-label');

    // Simulate: cholera cluster triggers alert after 3 seconds
    setTimeout(() => {
      if (banner) banner.style.display = 'flex';
      if (dot)    { dot.className = 'surv-threat-dot high'; }
      if (label)  label.textContent = '🟠 Threat Level: MODERATE';
      const el = document.getElementById('sk-active-outbreaks');
      if (el) el.textContent = '2';
    }, 2500);

    // Auto-update KPIs
    const kpis = [
      { id:'sk-active-outbreaks', val:'2' },
      { id:'sk-suspected',  val:'47' },
      { id:'sk-confirmed',  val:'31' },
    ];
    kpis.forEach(k => {
      const el = document.getElementById(k.id);
      if (el) el.textContent = k.val;
    });
  }

  /* ── MOH Report Generation ─────────────────────────────── */
  function initMOHReporting() {
    document.querySelectorAll('[data-moh-report]').forEach(btn => {
      btn.addEventListener('click', () => {
        const type = btn.dataset.mohReport;
        window.NEXUS?.Toast?.show?.(`📡 ${type} submitted to Rwanda Biomedical Centre`, 'success')
          || alert(`${type} submitted to MOH/RBC`);
      });
    });
    const reportBtn = document.querySelector('.btn-danger, [class*="report"]');
    reportBtn?.addEventListener('click', () => {
      window.NEXUS?.Toast?.show?.('📡 Outbreak report submitted to Rwanda Biomedical Centre', 'success')
        || alert('Outbreak report submitted');
    });
  }

  function init() {
    initTabs();
    loadDashboard();
    startAlertEngine();
    initMOHReporting();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
