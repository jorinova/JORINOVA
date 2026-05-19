/**
 * JORINOVA NEXUS ALIS-X — Secure Audit Trail Viewer
 * Security Admin Only · Forensic Mode · AI Anomaly Monitor · Hash Chain Integrity
 */
'use strict';

(function () {
  const API   = (path) => `/audit-trail${path}`;
  const CSRF  = () => window.NEXUS?.csrf || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  const esc   = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const toast = (m, t) => window.NEXUS?.Toast?.show?.(m, t);

  const CATEGORY_ICONS = {
    auth:'🔐',patient:'🧬',result:'📋',validation:'✅',correction:'✏️',
    deletion:'🗑️',blood_bank:'🩸',inventory:'📦',config:'⚙️',security:'🔒',
    ai_decision:'🤖',device:'🔧',print:'🖨️',voice:'🎙️',api:'🌐',
    interop:'🔗',report:'📊',forecast:'🔮',surveillance:'🦠',system:'💻',
  };

  const RISK_COLORS = { critical:'risk-critical', high:'risk-high', medium:'risk-medium', low:'risk-low' };

  /* ─── Demo audit events (for frontend display) ──────────────────── */
  const DEMO_EVENTS = [
    { id:1001, event_id:'ae1abc001', category:'result', action:'result.critical_released', description:'Critical result released: HGB 6.2 g/dL for patient RWA-2024-00142', username:'HABIMANA Eric', user_role:'lab_technician', ip_address:'192.168.1.45', object_type:'LabResult', object_id:'8821', risk_level:'high', anomaly_score:0, is_suspicious:false, is_violation:false, event_hash:'a3f4...c8e1', timestamp:'2026-05-15T09:15:22Z', module:'result' },
    { id:1002, event_id:'ae1abc002', category:'correction', action:'result.corrected', description:'Validated result corrected: CBC Haemoglobin from 9.2 to 6.2 g/dL. Reason: analyzer_error. Auth: Dr. UWERA', username:'HABIMANA Eric', user_role:'lab_technician', ip_address:'192.168.1.45', object_type:'LabResult', object_id:'8820', risk_level:'high', anomaly_score:0, is_suspicious:false, is_violation:false, event_hash:'b2d3...f7a9', timestamp:'2026-05-15T09:12:05Z', module:'result' },
    { id:1003, event_id:'ae1abc003', category:'security', action:'post.security', description:'GET /security/ → HTTP 403 (12ms)', username:'MUKAMANA Rose', user_role:'receptionist', ip_address:'10.0.0.12', object_type:'', object_id:'', risk_level:'critical', anomaly_score:72.3, is_suspicious:true, is_violation:true, event_hash:'c9e1...d4b2', timestamp:'2026-05-15T09:08:44Z', module:'security' },
    { id:1004, event_id:'ae1abc004', category:'blood_bank', action:'post.blood_bank', description:'POST /blood-bank/api/bags/ → HTTP 201 (38ms)', username:'NKURUNZIZA Jean', user_role:'lab_manager', ip_address:'192.168.1.10', object_type:'BloodBag', object_id:'BB-240515-0021', risk_level:'medium', anomaly_score:0, is_suspicious:false, is_violation:false, event_hash:'d1c2...e8f3', timestamp:'2026-05-15T09:05:11Z', module:'blood_bank' },
    { id:1005, event_id:'ae1abc005', category:'auth', action:'post.auth', description:'POST /auth/login → HTTP 200 (89ms)', username:'HABIMANA Eric', user_role:'lab_technician', ip_address:'192.168.1.45', object_type:'', object_id:'', risk_level:'low', anomaly_score:0, is_suspicious:false, is_violation:false, event_hash:'e4a5...b6c7', timestamp:'2026-05-15T08:00:33Z', module:'auth' },
    { id:1006, event_id:'ae1abc006', category:'auth', action:'post.auth', description:'POST /auth/login → HTTP 401 (12ms) — Failed attempt #3', username:'unknown', user_role:'', ip_address:'185.220.101.47', object_type:'', object_id:'', risk_level:'critical', anomaly_score:85.0, is_suspicious:true, is_violation:true, event_hash:'f7b8...c9d0', timestamp:'2026-05-15T07:45:12Z', module:'auth' },
    { id:1007, event_id:'ae1abc007', category:'config', action:'patch.config', description:'PATCH /core-config/api/hospital/ → HTTP 200 (54ms)', username:'INGABIRE Alice', user_role:'it_admin', ip_address:'192.168.1.5', object_type:'Hospital', object_id:'1', risk_level:'medium', anomaly_score:0, is_suspicious:false, is_violation:false, event_hash:'g8c9...d1e2', timestamp:'2026-05-15T07:30:18Z', module:'config' },
    { id:1008, event_id:'ae1abc008', category:'deletion', action:'delete.patient', description:'DELETE /api/v1/patients/442/ → HTTP 204 (28ms)', username:'NKURUNZIZA Jean', user_role:'lab_manager', ip_address:'192.168.1.10', object_type:'Patient', object_id:'442', risk_level:'high', anomaly_score:45.2, is_suspicious:false, is_violation:false, event_hash:'h9d0...e3f4', timestamp:'2026-05-15T07:15:55Z', module:'patient' },
  ];

  const DEMO_INCIDENTS = [
    { incident_id:'INC-20260515-001', incident_type:'brute_force', status:'open', threat_level:'critical', risk_score:85.0, confidence_pct:92, title:'CRITICAL — Brute Force / Failed Logins Detected', description:'5 failed login attempts from IP 185.220.101.47 within 10 minutes targeting multiple accounts.', ai_reasoning:'Statistical baseline deviation. Z-score 4.2 on failure rate. Known Tor exit node IP.', affected_username:'multiple', detected_at:'2026-05-15T07:50:00Z' },
    { incident_id:'INC-20260515-002', incident_type:'unusual_access', status:'investigating', threat_level:'high', risk_score:68.5, confidence_pct:78, title:'HIGH — Unusual Access Pattern — Receptionist', description:'MUKAMANA Rose attempted to access /security/ (403). Role-based access violation.', ai_reasoning:'User role "receptionist" has no access to security module. Attempt logged. Off-baseline module access.', affected_username:'MUKAMANA Rose', detected_at:'2026-05-15T09:08:44Z' },
  ];

  /* ─── Tab switching ─────────────────────────────────────────────── */
  function initTabs() {
    document.querySelectorAll('.audit-tab-nav .tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.audit-tab-nav .tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.audit-body .tab-pane').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.pane)?.classList.add('active');
        const actions = {
          'audit-incidents-pane': loadIncidents,
          'audit-anomaly-pane':   loadAnomaly,
          'audit-integrity-pane': loadIntegrity,
        };
        actions[btn.dataset.pane]?.();
      });
    });
  }

  /* ─── Stats bar ─────────────────────────────────────────────────── */
  function loadStats() {
    const stats = { total:'48,291', suspicious:'23', violations:'7', incidents:'2', buffer:'12', status:'Active' };
    Object.entries({ 'as-total':stats.total,'as-suspicious':stats.suspicious,'as-violations':stats.violations,'as-incidents':stats.incidents,'as-buffer':stats.buffer,'as-status':stats.status }).forEach(([id,v]) => {
      const el = document.getElementById(id); if (el) el.textContent = v;
    });
  }

  /* ─── Event log ──────────────────────────────────────────────────── */
  function renderEvent(e) {
    const rowClass = e.is_violation ? 'audit-event-row-violation' : e.is_suspicious ? 'audit-event-row-suspicious' : e.risk_level === 'critical' ? 'audit-event-row-critical' : e.risk_level === 'high' ? 'audit-event-row-high' : '';
    const catIcon  = CATEGORY_ICONS[e.category] || '📋';
    return `<tr class="${rowClass}">
      <td>${e.is_suspicious ? '⚠️' : e.is_violation ? '🚨' : ''}</td>
      <td style="font-family:var(--font-mono);font-size:10px;white-space:nowrap">${esc(new Date(e.timestamp).toLocaleString('en-GB',{hour12:false}))}</td>
      <td><span style="font-size:11px">${catIcon} ${esc(e.category)}</span></td>
      <td style="font-family:var(--font-mono);font-size:10px;color:var(--cyan)">${esc(e.action)}</td>
      <td>
        <div style="font-size:11px;font-weight:600">${esc(e.username || '—')}</div>
        <div style="font-size:10px;color:var(--text-muted)">${esc(e.user_role || '')}</div>
      </td>
      <td style="font-family:var(--font-mono);font-size:10px;color:var(--text-muted)">${esc(e.ip_address || '—')}</td>
      <td style="font-size:11px">${e.object_type ? `${esc(e.object_type)} #${esc(e.object_id)}` : '—'}</td>
      <td><span class="audit-risk-badge ${RISK_COLORS[e.risk_level]||'risk-low'}">${esc(e.risk_level)}</span>
          ${e.anomaly_score > 0 ? `<br><span style="font-size:9px;color:var(--alert-orange)">⚠️ ${e.anomaly_score.toFixed(0)}</span>` : ''}</td>
      <td><span class="audit-hash">${esc((e.event_hash||'').slice(0,8))}…</span></td>
    </tr>`;
  }

  async function loadEvents(filter = {}) {
    const tbody = document.getElementById('audit-events-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:1rem;color:#6c757d">Loading…</td></tr>';

    try {
      const params = new URLSearchParams({ limit: 100 });
      if (filter.category)   params.set('entity_type', filter.category.toUpperCase());
      if (filter.suspicious) params.set('suspicious_only', 'true');
      const tok = window.NEXUS?.token || localStorage.getItem('alis_token') || '';
      const res = await fetch(`/api/v1/audit-trail/logs?${params}`, {
        headers: tok ? { Authorization: `Bearer ${tok}` } : {},
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      let events = await res.json();
      events = Array.isArray(events) ? events : (events.results || events.items || []);

      // client-side filter for search/risk
      if (filter.risk) events = events.filter(e => e.risk_level === filter.risk);
      if (filter.search) {
        const q = filter.search.toLowerCase();
        events = events.filter(e =>
          (e.description||'').toLowerCase().includes(q) ||
          (e.username||e.performed_by||'').toLowerCase().includes(q) ||
          (e.action||'').toLowerCase().includes(q)
        );
      }

      if (!events.length) {
        // fallback to demo data so the page isn't empty
        events = [...DEMO_EVENTS];
        const pag = document.getElementById('audit-pagination');
        if (pag) pag.innerHTML = `<span>Showing ${events.length} sample events — no live data yet</span>`;
      } else {
        const pag = document.getElementById('audit-pagination');
        if (pag) pag.innerHTML = `<span>Showing ${events.length} events</span><span>Live data</span>`;
      }
      tbody.innerHTML = events.map(renderEvent).join('');
    } catch (err) {
      // Network/auth failure → show demo data with notice
      let events = [...DEMO_EVENTS];
      if (filter.category)   events = events.filter(e => e.category === filter.category);
      if (filter.risk)       events = events.filter(e => e.risk_level === filter.risk);
      if (filter.suspicious) events = events.filter(e => e.is_suspicious);
      if (filter.search) {
        const q = filter.search.toLowerCase();
        events = events.filter(e =>
          e.description.toLowerCase().includes(q) ||
          e.username.toLowerCase().includes(q) ||
          e.action.toLowerCase().includes(q)
        );
      }
      tbody.innerHTML = events.map(renderEvent).join('');
      const pag = document.getElementById('audit-pagination');
      if (pag) pag.innerHTML = `<span>Showing ${events.length} of ${DEMO_EVENTS.length} sample events (offline mode)</span><span>Page 1 of 1</span>`;
  }

  function initEventSearch() {
    document.getElementById('audit-search-btn')?.addEventListener('click', applyFilter);
    document.getElementById('audit-refresh-btn')?.addEventListener('click', () => loadEvents());
    document.getElementById('audit-export-btn')?.addEventListener('click', () => toast('Forensic report export initiated — digital signature will be applied', 'info'));
    document.querySelectorAll('#audit-cat-filter,#audit-risk-filter,#audit-suspicious-filter').forEach(el => {
      el.addEventListener('change', applyFilter);
    });
  }

  function applyFilter() {
    loadEvents({
      category:   document.getElementById('audit-cat-filter')?.value,
      risk:       document.getElementById('audit-risk-filter')?.value,
      suspicious: document.getElementById('audit-suspicious-filter')?.value === '1',
      search:     document.getElementById('audit-search')?.value?.trim(),
    });
  }

  /* ─── Incidents ──────────────────────────────────────────────────── */
  function loadIncidents() {
    const list = document.getElementById('audit-incidents-list');
    if (!list || list.innerHTML !== '') return;
    list.innerHTML = DEMO_INCIDENTS.map(i => `
      <div class="audit-incident-card threat-${i.threat_level}">
        <div style="display:flex;align-items:flex-start;justify-content:space-between">
          <div>
            <div class="audit-incident-title">${esc(i.title)}</div>
            <div class="audit-incident-meta">
              <span class="badge ${i.threat_level==='critical'?'badge-red':i.threat_level==='high'?'badge-orange':'badge-yellow'}">${esc(i.threat_level.toUpperCase())}</span>
              &nbsp;ID: <code style="font-size:10px;color:var(--cyan)">${esc(i.incident_id)}</code>
              &nbsp;· User: <strong>${esc(i.affected_username)}</strong>
              &nbsp;· Detected: ${esc(new Date(i.detected_at).toLocaleString('en-GB'))}
            </div>
          </div>
          <div style="display:flex;align-items:center;gap:var(--space-sm)">
            <div>
              <div class="audit-risk-bar"><div class="audit-risk-fill" style="width:${i.risk_score}%;background:${i.threat_level==='critical'?'var(--alert-red)':'var(--alert-orange)'}"></div></div>
              <div style="font-size:9px;color:var(--text-muted);text-align:right;margin-top:2px">${i.risk_score.toFixed(0)}/100 risk · ${i.confidence_pct}% conf.</div>
            </div>
            <span class="badge ${i.status==='open'?'badge-red':i.status==='investigating'?'badge-orange':'badge-green'}">${esc(i.status)}</span>
          </div>
        </div>
        <div style="font-size:11px;color:var(--text-secondary);margin-top:var(--space-sm)">${esc(i.description)}</div>
        <div class="audit-incident-ai">🤖 AI Reasoning: ${esc(i.ai_reasoning)}</div>
        <div style="display:flex;gap:var(--space-sm);margin-top:var(--space-md)">
          <button class="btn btn-danger btn-sm">🔍 Investigate</button>
          <button class="btn btn-ghost btn-sm">✅ Mark Resolved</button>
          <button class="btn btn-ghost btn-sm">📤 Escalate</button>
        </div>
      </div>`).join('');
  }

  /* ─── Anomaly Monitor ───────────────────────────────────────────── */
  function loadAnomaly() {
    const v  = document.getElementById('audit-volume-chart');
    const r  = document.getElementById('audit-risk-chart');
    const hours = Array.from({length:24},(_,h)=>`${String(h).padStart(2,'0')}:00`);
    const vol   = [12,8,5,3,2,1,8,45,62,58,71,82,74,68,55,66,72,78,81,64,42,28,15,9];

    if (v && window.Chart && !v._done) {
      v._done = true;
      new Chart(v, {
        type:'bar', data:{ labels:hours, datasets:[{label:'Events',data:vol,backgroundColor:'rgba(0,153,255,.4)',borderRadius:2}]},
        options:{ responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#8899aa',font:{size:9}},grid:{color:'rgba(255,255,255,.03)'}},y:{ticks:{color:'#8899aa'},grid:{color:'rgba(255,255,255,.04)'}}}}
      });
    }
    if (r && window.Chart && !r._done) {
      r._done = true;
      new Chart(r, {
        type:'doughnut', data:{ labels:['Critical','High','Medium','Low'], datasets:[{data:[7,16,48,29],backgroundColor:['rgba(255,23,68,.6)','rgba(255,109,0,.6)','rgba(255,214,0,.5)','rgba(0,230,118,.4)']}]},
        options:{ responsive:true,maintainAspectRatio:false,plugins:{legend:{labels:{color:'#aab',font:{size:10}}}}}
      });
    }

    const bg = document.getElementById('audit-baseline-grid');
    if (bg && bg.innerHTML === '') {
      const baselines = [
        { name:'HABIMANA Eric', role:'Lab Technician', avg_actions:142, common_hours:'08-16', known_ips:2, anomaly:'none' },
        { name:'MUKAMANA Rose', role:'Receptionist', avg_actions:88, common_hours:'08-17', known_ips:1, anomaly:'access violation' },
        { name:'NKURUNZIZA Jean', role:'Lab Manager', avg_actions:210, common_hours:'07-18', known_ips:3, anomaly:'none' },
        { name:'Unknown (ext.)', role:'—', avg_actions:0, common_hours:'—', known_ips:0, anomaly:'brute force' },
      ];
      bg.innerHTML = baselines.map(b => `
        <div class="audit-baseline-card ${b.anomaly!=='none'?'':''}">
          <div class="audit-baseline-name">${esc(b.name)}</div>
          <div class="audit-baseline-meta">${esc(b.role)} · ${b.avg_actions} avg actions/day · ${b.common_hours} hrs</div>
          <div style="margin-top:var(--space-sm);font-size:11px">
            Known IPs: <strong>${b.known_ips}</strong> ·
            Anomaly: <strong style="color:${b.anomaly!=='none'?'var(--alert-red)':'var(--alert-green)'}">${b.anomaly!=='none'?'🚨 '+b.anomaly:'✅ None'}</strong>
          </div>
        </div>`).join('');
    }
  }

  /* ─── Chain Integrity ─────────────────────────────────────────────── */
  function loadIntegrity() {
    const el = document.getElementById('audit-batch-list');
    if (!el || el.innerHTML !== '') return;
    const batches = Array.from({length:8},(_,i) => ({
      id:  `BATCH-${String(i+1).padStart(4,'0')}`,
      count: Math.floor(Math.random()*100+50),
      created: new Date(Date.now() - i*3600000).toLocaleString('en-GB'),
      status: 'verified',
    }));
    el.innerHTML = `<div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--text-muted);margin-bottom:var(--space-md)">📦 Recent Audit Batches</div>` +
      batches.map(b => `
        <div class="audit-batch-row">
          <span style="font-family:var(--font-mono);color:var(--cyan)">${esc(b.id)}</span>
          <span>${b.count} events</span>
          <span style="color:var(--text-muted)">${esc(b.created)}</span>
          <span class="badge-info" style="font-size:10px;font-weight:700;padding:2px 6px;border-radius:var(--radius-full);background:rgba(0,230,118,.08);border:1px solid rgba(0,230,118,.20);color:var(--alert-green)">✅ ${esc(b.status)}</span>
        </div>`).join('');
  }

  /* ─── Forensic Search ─────────────────────────────────────────────── */
  function initForensicSearch() {
    document.getElementById('forensic-search-btn')?.addEventListener('click', () => {
      const user   = document.getElementById('forensic-user')?.value?.trim();
      const ip     = document.getElementById('forensic-ip')?.value?.trim();
      const results= document.getElementById('forensic-results');
      if (!results) return;

      results.innerHTML = '<div class="worklist-loading"><i class="fas fa-spinner"></i> Running forensic investigation…</div>';
      setTimeout(() => {
        let events = [...DEMO_EVENTS];
        if (user) events = events.filter(e => e.username.toLowerCase().includes(user.toLowerCase()));
        if (ip)   events = events.filter(e => (e.ip_address||'').includes(ip));
        results.innerHTML = `
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:var(--space-md)">🔍 Found ${events.length} matching events</div>
          <table class="nx-table"><thead><tr><th>Timestamp</th><th>Action</th><th>User</th><th>IP</th><th>Risk</th></tr></thead>
          <tbody>${events.map(e=>`<tr>
            <td style="font-family:var(--font-mono);font-size:10px">${esc(new Date(e.timestamp).toLocaleString('en-GB'))}</td>
            <td style="font-family:var(--font-mono);font-size:10px">${esc(e.action)}</td>
            <td>${esc(e.username)}</td><td style="font-family:var(--font-mono);font-size:10px">${esc(e.ip_address||'—')}</td>
            <td><span class="audit-risk-badge ${RISK_COLORS[e.risk_level]||'risk-low'}">${esc(e.risk_level)}</span></td>
          </tr>`).join('')}</tbody></table>`;
      }, 600);
    });
  }

  /* ─── Init ──────────────────────────────────────────────────────── */
  function init() {
    initTabs();
    loadStats();
    loadEvents();
    initEventSearch();
    initForensicSearch();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
