/**
 * JORINOVA NEXUS ALIS-X — NexusCare (Nursing & Clinical Management)
 * Patient care, medication, vital signs, nursing notes, ward management
 */
'use strict';

(function () {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  const PATIENTS = [
    { id:'RWA-2024-00142', name:'KAMANZI Jean', age:34, gender:'M', ward:'Medical Ward A', bed:'A-12', admission:'2026-05-13', dx:'Severe Malaria + Anaemia', attending:'Dr. UWERA', vitals:{ bp:'110/70', hr:88, temp:38.2, spo2:97, rr:18 }, alerts:['Critical CBC pending','IV Artesunate Day 2'] },
    { id:'RWA-2024-00287', name:'UWIMANA Grace', age:28, gender:'F', ward:'Maternity', bed:'M-04', admission:'2026-05-14', dx:'Pre-eclampsia (G2P1)', attending:'Dr. HABIMANA', vitals:{ bp:'150/95', hr:92, temp:36.8, spo2:99, rr:16 }, alerts:['BP monitoring Q1hr','Magnesium sulphate infusion'] },
    { id:'RWA-2024-00388', name:'HABIMANA Eric', age:52, gender:'M', ward:'ICU', bed:'ICU-03', admission:'2026-05-12', dx:'Septic Shock — Gram-negative bacteraemia', attending:'Dr. NKURUNZIZA', vitals:{ bp:'85/50', hr:118, temp:39.4, spo2:94, rr:24 }, alerts:['🚨 CRITICAL — Vasopressors','BSL-2 enhanced precautions','Blood culture ×2 pending'] },
    { id:'RWA-2024-00501', name:'MUKAMANA Rose', age:42, gender:'F', ward:'Oncology', bed:'O-07', admission:'2026-05-10', dx:'Ca Cervix Stage IIB — Chemoradiation', attending:'Dr. UWIMANA', vitals:{ bp:'118/76', hr:74, temp:36.6, spo2:98, rr:14 }, alerts:['Cisplatin Day 5','CBC monitoring'] },
  ];

  function initTabs() {
    document.querySelectorAll('.care-tab-nav .tab-btn, .tab-nav .tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const nav = btn.closest('.care-tab-nav, .tab-nav');
        nav?.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        document.getElementById(btn.dataset.pane)?.classList.add('active');
      });
    });
  }

  function loadWardBoard() {
    const grid = document.getElementById('ward-board');
    if (!grid || grid.innerHTML !== '') return;
    grid.innerHTML = PATIENTS.map(p => {
      const isCritical = p.ward === 'ICU';
      const tempAlert  = p.vitals.temp > 38;
      const bpAlert    = parseInt(p.vitals.bp) > 140;
      return `<div class="care-patient-card ${isCritical ? 'care-card-critical' : ''}" onclick="window.CareModule.openPatient('${p.id}')">
        <div class="care-card-header">
          <div>
            <div class="care-patient-name">${esc(p.name)}</div>
            <div class="care-patient-meta">${p.age}y ${p.gender} · ${esc(p.ward)} · Bed ${esc(p.bed)}</div>
          </div>
          <div class="care-ward-badge ${isCritical ? 'care-badge-critical' : ''}">${isCritical ? '🚨 ICU' : '🏥 ' + p.ward.split(' ')[0]}</div>
        </div>
        <div class="care-dx">${esc(p.dx)}</div>
        <div class="care-vitals-strip">
          <div class="care-vital ${bpAlert ? 'vital-alert' : ''}"><span>💉 BP</span><strong>${esc(p.vitals.bp)}</strong></div>
          <div class="care-vital ${p.vitals.hr > 100 ? 'vital-alert' : ''}"><span>💓 HR</span><strong>${p.vitals.hr}</strong></div>
          <div class="care-vital ${tempAlert ? 'vital-alert' : ''}"><span>🌡️ Temp</span><strong>${p.vitals.temp}°C</strong></div>
          <div class="care-vital ${p.vitals.spo2 < 95 ? 'vital-alert' : ''}"><span>🫁 SpO₂</span><strong>${p.vitals.spo2}%</strong></div>
        </div>
        ${p.alerts.length ? `<div class="care-alerts">${p.alerts.map(a => `<div class="care-alert-pill ${a.startsWith('🚨')?'alert-critical':''}">${esc(a)}</div>`).join('')}</div>` : ''}
      </div>`;
    }).join('');
  }

  /* ── Census stats ───────────────────────────────────────── */
  function loadCensus() {
    const CENSUS = { total_beds:120, occupied:78, available:42, icu:8, icu_occupied:6, admissions_today:12, discharges_today:9 };
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('census-total',     CENSUS.occupied + '/' + CENSUS.total_beds);
    set('census-available', CENSUS.available);
    set('census-icu',       CENSUS.icu_occupied + '/' + CENSUS.icu);
    set('census-admit',     CENSUS.admissions_today);
    set('census-discharge', CENSUS.discharges_today);
  }

  /* ── Patient detail modal ───────────────────────────────── */
  function showPatientDetail(p) {
    let modal = document.getElementById('care-patient-modal');
    if (!modal) {
      modal = document.createElement('div');
      modal.id = 'care-patient-modal';
      modal.className = 'modal-overlay';
      modal.style.cssText = 'position:fixed;inset:0;z-index:999;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.6);backdrop-filter:blur(4px)';
      document.body.appendChild(modal);
    }
    const vitals = p.vitals;
    modal.innerHTML = `
      <div class="glass-card" style="max-width:640px;width:95%;max-height:85vh;overflow-y:auto;border-radius:var(--radius-xl);border:1px solid var(--border-muted)">
        <div style="display:flex;align-items:center;justify-content:space-between;padding:var(--space-lg);border-bottom:1px solid var(--border-dim);background:var(--bg-deep)">
          <div>
            <div style="font-family:var(--font-display);font-size:var(--text-xl);font-weight:700;color:var(--text-primary)">${esc(p.name)}</div>
            <div style="font-size:var(--text-xs);color:var(--text-muted)">${p.age}y · ${p.gender} · ${esc(p.ward)} · Bed ${esc(p.bed)} · Dr. ${esc(p.attending)}</div>
          </div>
          <button onclick="document.getElementById('care-patient-modal').style.display='none'" style="background:none;border:none;color:var(--text-muted);font-size:20px;cursor:pointer">✕</button>
        </div>
        <div style="padding:var(--space-lg);display:flex;flex-direction:column;gap:var(--space-lg)">
          <div>
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text-muted);letter-spacing:.07em;margin-bottom:var(--space-sm)">Diagnosis</div>
            <div style="font-size:var(--text-sm);color:var(--text-primary)">${esc(p.dx)}</div>
          </div>
          <div>
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text-muted);letter-spacing:.07em;margin-bottom:var(--space-sm)">Current Vitals</div>
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:var(--space-sm)">
              ${[['💉 BP', vitals.bp, parseInt(vitals.bp)>140?'var(--alert-red)':'var(--alert-green)'],['💓 HR', vitals.hr+' bpm', vitals.hr>100?'var(--alert-orange)':'var(--alert-green)'],['🌡️ Temp', vitals.temp+'°C', vitals.temp>38?'var(--alert-orange)':'var(--alert-green)'],['🫁 SpO₂', vitals.spo2+'%', vitals.spo2<95?'var(--alert-red)':'var(--alert-green)'],['🫀 RR', vitals.rr+' /min', vitals.rr>20?'var(--alert-orange)':'var(--alert-green)']].map(([l,v,c]) => `
                <div style="padding:var(--space-sm);background:var(--bg-glass);border:1px solid var(--border-dim);border-radius:var(--radius-md);text-align:center">
                  <div style="font-size:10px;color:var(--text-muted)">${l}</div>
                  <div style="font-family:var(--font-display);font-size:15px;font-weight:700;color:${c};margin-top:3px">${v}</div>
                </div>`).join('')}
            </div>
          </div>
          ${p.alerts.length ? `<div>
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text-muted);letter-spacing:.07em;margin-bottom:var(--space-sm)">Active Alerts</div>
            ${p.alerts.map(a => `<div style="padding:6px var(--space-md);background:rgba(255,23,68,.08);border:1px solid rgba(255,23,68,.2);border-radius:var(--radius-sm);font-size:var(--text-xs);color:var(--alert-red);margin-bottom:4px">${esc(a)}</div>`).join('')}
          </div>` : ''}
          <div>
            <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text-muted);letter-spacing:.07em;margin-bottom:var(--space-sm)">Quick Actions</div>
            <div style="display:flex;gap:var(--space-sm);flex-wrap:wrap">
              <button class="btn btn-primary btn-sm" onclick="window.NEXUS?.Toast?.show?.('Lab request created','success')">🧪 Order Labs</button>
              <button class="btn btn-ghost btn-sm" onclick="window.NEXUS?.Toast?.show?.('Nursing note saved','success')">📝 Nursing Note</button>
              <button class="btn btn-secondary btn-sm" onclick="window.location.href='/laboratory/?patient='+encodeURIComponent('${p.id}')">📋 View Lab History</button>
            </div>
          </div>
        </div>
      </div>`;
    modal.style.display = 'flex';
    modal.addEventListener('click', e => { if (e.target === modal) modal.style.display = 'none'; });
  }

  window.CareModule = {
    openPatient(pid) {
      const p = PATIENTS.find(x => x.id === pid);
      if (p) showPatientDetail(p);
    }
  };

  function init() { initTabs(); loadWardBoard(); loadCensus(); }
  document.addEventListener('DOMContentLoaded', init);
})();
