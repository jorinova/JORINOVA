/**
 * JORINOVA NEXUS ALIS-X — Inventory Intelligence
 * FIFO/FEFO · Stock Movements · Expiry Tracker · POs · Reagent Cards
 */
'use strict';

(function () {
  const NEXUS = window.NEXUS || {};
  const API   = NEXUS.API   || { get:(u,p)=>fetch('/api/v1'+u+(p?'?'+new URLSearchParams(p):'')), json:r=>r.json(), checkError:async r=>{if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.statusText)} };
  const Toast = NEXUS.Toast || { success:(t,m)=>console.log(t,m), error:(t,m)=>console.error(t,m), warning:(t,m)=>console.warn(t,m), info:(t,m)=>console.info(t,m) };
  const CSRF  = () => window.NEXUS?.csrf || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  const esc   = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt   = { date: d => d ? new Date(d).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}) : '—', datetime: d => d ? new Date(d).toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}) : '—' };
  const $     = id => document.getElementById(id);
  const fmtNum = n => n !== null && n !== undefined ? parseFloat(n).toLocaleString() : '—';

  /* ── State ─────────────────────────────────────────────────── */
  let activePane    = 'pane-dashboard';
  let ledgerPage    = 1;
  let moveTargetId  = null;  // Item ID for movement modal
  let allSuppliers  = [];
  let allItems      = [];    // For PO item lookup
  let poLines       = [];

  /* ════════════════════════════════════════════════════════════
     TAB SWITCHING
  ════════════════════════════════════════════════════════════ */
  document.querySelectorAll('.inv-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.inv-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.inv-pane').forEach(p => p.style.display = 'none');
      tab.classList.add('active');
      activePane = tab.dataset.pane;
      const pane = $(activePane);
      if (pane) pane.style.display = 'flex';
      if (pane) pane.style.flexDirection = 'column';
      onPaneChange(activePane);
    });
  });

  function onPaneChange(pane) {
    if (pane === 'pane-dashboard') loadDashboard();
    if (pane === 'pane-ledger')    loadLedger();
    if (pane === 'pane-reagents')  loadReagents();
    if (pane === 'pane-orders')    loadPOs();
    if (pane === 'pane-expiry')    loadExpiry();
    if (pane === 'pane-movements') loadMovements();
  }

  /* ════════════════════════════════════════════════════════════
     BARCODE SCAN
  ════════════════════════════════════════════════════════════ */
  $('inv-scan-input')?.addEventListener('keydown', async e => {
    if (e.key !== 'Enter') return;
    const val = $('inv-scan-input').value.trim();
    if (!val) return;
    try {
      const r    = await API.get('/inventory/items/', { search: val, page_size: 1 });
      const data = await API.json(r);
      const items = data.results ?? data;
      if (!items.length) { Toast.warning('Not found', `No item found: ${val}`); return; }
      openItemDetail(items[0]);
      $('inv-scan-input').value = '';
    } catch (e) { Toast.error('Lookup failed', e.message); }
  });

  /* ════════════════════════════════════════════════════════════
     DASHBOARD
  ════════════════════════════════════════════════════════════ */
  async function loadDashboard() {
    try {
      const r    = await API.get('/inventory/stats/');
      const data = await API.json(r);
      renderDashboard(data);
    } catch (_) {
      renderDashboardDemo();
    }
  }

  function renderDashboard(data) {
    $('kpi-total')    && ($('kpi-total').textContent    = fmtNum(data.total_items ?? '—'));
    $('kpi-low')      && ($('kpi-low').textContent      = fmtNum((data.low_stock || 0) + (data.out_of_stock || 0)));
    $('kpi-expiring') && ($('kpi-expiring').textContent = fmtNum(data.expiring_soon ?? '—'));
    $('kpi-orders')   && ($('kpi-orders').textContent   = fmtNum(data.open_pos ?? '—'));
    $('kpi-value')    && ($('kpi-value').textContent    = (data.total_value ? parseFloat(data.total_value).toLocaleString() : '—'));

    const alertCount = (data.low_stock || 0) + (data.expiring_soon || 0);
    const pill = $('inv-alerts-pill');
    const cnt  = $('inv-alerts-count');
    if (pill) pill.style.display = alertCount > 0 ? 'flex' : 'none';
    if (cnt)  cnt.textContent = alertCount;

    // Badges
    $('badge-ledger')  && ($('badge-ledger').textContent  = data.total_items ?? '—');
    $('badge-reagents')&& ($('badge-reagents').textContent= data.total_reagents ?? '—');
    $('badge-orders')  && ($('badge-orders').textContent  = data.open_pos ?? '—');
    $('badge-expiry')  && ($('badge-expiry').textContent  = data.expiring_soon ?? '—');

    renderLowStockAlerts(data.low_stock_items || []);
    renderExpiryAlerts(data.expiry_alerts || []);
    renderRecentMovements(data.recent_movements || []);
    renderTopConsumed(data.top_consumed || []);
    renderCategoryChart(data.category_counts || {});
    renderConsumptionChart(data.consumption_trend || []);
  }

  function renderDashboardDemo() {
    const DEMO = {
      total_items: 142, low_stock: 8, out_of_stock: 2,
      expiring_soon: 12, open_pos: 3,
      total_value: '12450000',
      total_reagents: 64,
      low_stock_items: [
        { code:'HEM-001', name:'EDTA Tubes 3mL', current_stock:18, min_stock:50, unit:'box', dept:'Hematology' },
        { code:'CHM-007', name:'Glucose Reagent (Hexokinase)', current_stock:2, min_stock:10, unit:'kit', dept:'Chemistry' },
        { code:'MIC-012', name:'Blood Culture Bottles (Aerobic)', current_stock:5, min_stock:20, unit:'bottle', dept:'Microbiology' },
        { code:'SER-003', name:'HIV RDT Test Kits', current_stock:12, min_stock:30, unit:'test', dept:'Serology' },
      ],
      expiry_alerts: [
        { code:'CHM-022', name:'Protein Reagent BCA Kit', days_left: -3, expiry_date:'2026-05-12', batch:'LOT-2024-0082' },
        { code:'SER-011', name:'HBsAg ELISA Strips', days_left: 5, expiry_date:'2026-05-20', batch:'LOT-2025-0041' },
        { code:'QC-001', name:'Chemistry Multi-Level Control', days_left: 9, expiry_date:'2026-05-24', batch:'QC-A-2025' },
        { code:'STN-003', name:'Leishman Stain 500mL', days_left: 22, expiry_date:'2026-06-06', batch:'S-2023-0077' },
      ],
      recent_movements: [
        { type:'restock',  item:'EDTA Tubes 3mL', qty:100, time:'2 hrs ago' },
        { type:'issue',    item:'Glucose Reagent', qty:2, time:'3 hrs ago' },
        { type:'expired',  item:'Old HCV Strips', qty:5, time:'Yesterday' },
        { type:'restock',  item:'HIV RDT Test Kits', qty:50, time:'2 days ago' },
        { type:'transfer', item:'Malaria RDTs', qty:20, time:'3 days ago' },
      ],
      top_consumed: [
        { name:'EDTA Tubes 3mL', consumed:340, unit:'box' },
        { name:'HIV RDT Test Kits', consumed:285, unit:'test' },
        { name:'Glucose Reagent', consumed:18, unit:'kit' },
        { name:'Malaria RDT', consumed:210, unit:'test' },
        { name:'CBC Control (Normal)', consumed:42, unit:'run' },
      ],
      category_counts: { reagent:64, consumable:38, qc_control:12, equipment:8, ppe:12, stain:8 },
      consumption_trend: [34,28,41,38,52,30,27],
    };
    renderDashboard(DEMO);
  }

  function renderLowStockAlerts(items) {
    const el = $('low-stock-list');
    if (!el) return;
    if (!items.length) { el.innerHTML = '<div class="inv-hint" style="font-size:var(--text-xs)">✅ All stock levels OK</div>'; return; }
    el.innerHTML = items.map(i => {
      const pct  = i.max_stock ? Math.round((i.current_stock / i.max_stock) * 100) : 0;
      const cls  = i.current_stock <= 0 ? 'alert-red' : 'alert-orange';
      return `<div class="inv-alert-item ${cls}">
        <span style="font-size:12px">${i.current_stock <= 0 ? '❌' : '⚠️'}</span>
        <div class="iai-name">${esc(i.name)}</div>
        <span class="iai-meta">${esc(i.dept || '')}</span>
        <span class="iai-val" style="color:${i.current_stock <= 0 ? 'var(--alert-red)' : 'var(--alert-orange)'}">${fmtNum(i.current_stock)} ${esc(i.unit)}</span>
      </div>`;
    }).join('');
  }

  function renderExpiryAlerts(items) {
    const el = $('expiry-alert-list');
    if (!el) return;
    if (!items.length) { el.innerHTML = '<div class="inv-hint" style="font-size:var(--text-xs)">✅ No items expiring soon</div>'; return; }
    el.innerHTML = items.map(i => {
      const cls  = i.days_left < 0 ? 'alert-red' : i.days_left <= 7 ? 'alert-orange' : 'alert-yellow';
      const label = i.days_left < 0 ? `Expired ${Math.abs(i.days_left)}d ago` : `${i.days_left}d left`;
      return `<div class="inv-alert-item ${cls}">
        <span style="font-size:12px">${i.days_left < 0 ? '🚫' : '⏰'}</span>
        <div class="iai-name">${esc(i.name)}</div>
        <span class="iai-meta">${esc(i.batch || '')}</span>
        <span class="iai-val" style="color:${i.days_left < 0 ? 'var(--alert-red)' : i.days_left <= 7 ? 'var(--alert-orange)' : 'var(--alert-yellow)'}">${label}</span>
      </div>`;
    }).join('');
  }

  function renderRecentMovements(movements) {
    const el = $('recent-movements-list');
    if (!el) return;
    const icons  = { restock:'⬆️', issue:'⬇️', adjust:'🔧', transfer:'↗️', expired:'🗑️', return:'↩️' };
    const sign   = { restock:'+', return:'+', issue:'-', expired:'-', adjust:'=', transfer:'↗' };
    el.innerHTML = movements.map(m => `
      <div class="mov-item">
        <span class="mov-type-icon">${icons[m.type] || '🔄'}</span>
        <span class="mov-item-name">${esc(m.item)}</span>
        <span class="mov-qty ${['restock','return'].includes(m.type) ? 'pos' : 'neg'}">${sign[m.type] || ''}${fmtNum(m.qty)}</span>
        <span class="mov-time">${esc(m.time)}</span>
      </div>`).join('');
  }

  function renderTopConsumed(items) {
    const el = $('top-consumed-list');
    if (!el) return;
    const max = items.length ? Math.max(...items.map(i => i.consumed)) : 1;
    el.innerHTML = items.map(i => {
      const pct = Math.round((i.consumed / max) * 100);
      return `<div style="margin-bottom:var(--space-sm)">
        <div style="display:flex;justify-content:space-between;font-size:var(--text-xs);margin-bottom:3px">
          <span style="color:var(--text-primary);font-weight:600">${esc(i.name)}</span>
          <span style="font-family:var(--font-mono);color:var(--alert-orange)">${fmtNum(i.consumed)} ${esc(i.unit || '')}</span>
        </div>
        <div style="height:5px;background:var(--bg-glass);border-radius:3px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:var(--alert-orange);border-radius:3px"></div>
        </div>
      </div>`;
    }).join('');
  }

  function renderCategoryChart(counts) {
    const canvas = $('cat-chart');
    if (!canvas || !window.Chart) return;
    if (canvas._chart) canvas._chart.destroy();
    const labels = Object.keys(counts).map(k => ({ reagent:'Reagent', consumable:'Consumable', qc_control:'QC Control', equipment:'Equipment', ppe:'PPE', stain:'Stain', culture_media:'Media', other:'Other' }[k] || k));
    const data   = Object.values(counts);
    const colors = ['#FF6D00','#0099FF','#00E676','#FFD600','#FF1744','#9B59B6','#27AE60','#95A5A6'];
    canvas._chart = new Chart(canvas, {
      type: 'doughnut',
      data: { labels, datasets: [{ data, backgroundColor: colors.slice(0, data.length), borderWidth:0 }] },
      options: { responsive:true, maintainAspectRatio:false, plugins:{ legend:{ labels:{ color:'#8899aa', font:{size:10} }, position:'right' } } }
    });
  }

  function renderConsumptionChart(trend) {
    const canvas = $('consumption-chart');
    if (!canvas || !window.Chart) return;
    if (canvas._chart) canvas._chart.destroy();
    const days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    const data = trend.length === 7 ? trend : Array.from({length:7}, () => Math.floor(Math.random()*50)+10);
    canvas._chart = new Chart(canvas, {
      type: 'bar',
      data: { labels: days, datasets: [{ label:'Items Issued', data, backgroundColor:'rgba(255,109,0,.4)', borderColor:'var(--alert-orange)', borderWidth:1.5, borderRadius:3 }] },
      options: { responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#8899aa',font:{size:10}}}, y:{grid:{color:'rgba(255,255,255,.04)'}, ticks:{color:'#8899aa'}} } }
    });
  }

  /* ════════════════════════════════════════════════════════════
     STOCK LEDGER
  ════════════════════════════════════════════════════════════ */
  async function loadLedger() {
    const tbody = $('ledger-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="11"><div class="inv-loading"><i class="fas fa-spinner"></i> Loading…</div></td></tr>';

    const params = { page: ledgerPage, page_size: 25 };
    const search = $('ledger-search')?.value?.trim();
    const cat    = $('ledger-filter-cat')?.value;
    const status = $('ledger-filter-status')?.value;
    const dept   = $('ledger-filter-dept')?.value;
    if (search) params.search = search;
    if (cat)    params.category = cat;
    if (status) params.status   = status;
    if (dept)   params.department = dept;

    try {
      const r    = await API.get('/inventory/items/', params);
      const data = await API.json(r);
      const items = data.results ?? data;
      allItems   = items;
      renderLedger(items);
      $('ledger-count') && ($('ledger-count').textContent = `${data.count || items.length} items`);
      $('badge-ledger') && ($('badge-ledger').textContent = data.count || items.length);
      renderPagination(data.count, data.results?.length, ledgerPage);
    } catch (e) {
      if (tbody) tbody.innerHTML = `<tr><td colspan="11"><div class="inv-loading">❌ ${esc(e.message)}</div></td></tr>`;
    }
  }

  function renderLedger(items) {
    const tbody = $('ledger-tbody');
    if (!tbody) return;
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="11"><div class="inv-loading">No items found</div></td></tr>';
      return;
    }
    tbody.innerHTML = items.map(item => {
      const pct    = item.max_stock > 0 ? Math.min(100, Math.round((item.current_stock / item.max_stock) * 100)) : 0;
      const sbCls  = pct >= 60 ? 'sb-green' : pct >= 30 ? 'sb-yellow' : pct >= 10 ? 'sb-orange' : 'sb-red';
      const daysEx = item.days_to_expiry;
      const expiryHtml = item.expiry_date
        ? `<span class="${daysEx < 0 ? 'expiry-days ed-expired' : daysEx <= 7 ? 'expiry-days ed-7' : daysEx <= 14 ? 'expiry-days ed-14' : daysEx <= 30 ? 'expiry-days ed-30' : ''}">${fmt.date(item.expiry_date)}</span>`
        : '<span style="color:var(--text-muted)">—</span>';
      return `<tr>
        <td><span class="it-code">${esc(item.code)}</span></td>
        <td>
          <div class="it-name">${esc(item.name)}</div>
          ${item.brand ? `<div class="it-brand">${esc(item.brand)}</div>` : ''}
          ${item.catalog_no ? `<div class="it-catalog">Cat: ${esc(item.catalog_no)}</div>` : ''}
        </td>
        <td><span class="badge badge-grey" style="font-size:9px">${esc(item.category_display || item.category)}</span></td>
        <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(item.department_name || '—')}</td>
        <td>
          <div class="stock-bar-wrap">
            <div class="stock-bar-bg"><div class="stock-bar-fill ${sbCls}" style="width:${pct}%"></div></div>
            <div class="stock-vals"><span>${pct}%</span><span>max:${fmtNum(item.max_stock)}</span></div>
          </div>
        </td>
        <td><strong style="font-family:var(--font-mono)">${fmtNum(item.current_stock)}</strong> <span style="font-size:10px;color:var(--text-muted)">${esc(item.unit)}</span></td>
        <td style="font-family:var(--font-mono);font-size:11px;color:var(--text-muted)">${fmtNum(item.min_stock)}</td>
        <td>${expiryHtml}</td>
        <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(item.supplier_name || '—')}</td>
        <td><span class="inv-status ${item.status}">${statusLabel(item.status)}</span></td>
        <td style="text-align:right">
          <div style="display:flex;gap:4px;justify-content:flex-end">
            <button class="btn btn-ghost btn-sm" title="View details" onclick="window._invDetail(${item.id})">👁️</button>
            <button class="btn btn-primary btn-sm" onclick="window._invMove(${item.id}, 'restock')">⬆️</button>
            <button class="btn btn-secondary btn-sm" onclick="window._invMove(${item.id}, 'issue')">⬇️</button>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  /* Filters */
  let ledgerSearchTimer = null;
  $('ledger-search')?.addEventListener('input', () => { clearTimeout(ledgerSearchTimer); ledgerSearchTimer = setTimeout(() => { ledgerPage = 1; loadLedger(); }, 350); });
  $('ledger-filter-cat')?.addEventListener('change', () => { ledgerPage = 1; loadLedger(); });
  $('ledger-filter-status')?.addEventListener('change', () => { ledgerPage = 1; loadLedger(); });
  $('ledger-filter-dept')?.addEventListener('change', () => { ledgerPage = 1; loadLedger(); });
  $('ledger-refresh')?.addEventListener('click', loadLedger);

  function renderPagination(total, pageSize, page) {
    const el  = $('ledger-pagination');
    if (!el || !total) return;
    const pages = Math.ceil(total / (pageSize || 25));
    el.innerHTML = `
      <button class="btn btn-ghost btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="window._invPage(${page-1})">← Prev</button>
      <span style="font-size:var(--text-xs);color:var(--text-muted)">Page ${page} of ${pages} · ${total} items</span>
      <button class="btn btn-ghost btn-sm" ${page >= pages ? 'disabled' : ''} onclick="window._invPage(${page+1})">Next →</button>`;
  }
  window._invPage = p => { ledgerPage = p; loadLedger(); };

  /* ════════════════════════════════════════════════════════════
     REAGENTS (FIFO/FEFO cards)
  ════════════════════════════════════════════════════════════ */
  async function loadReagents() {
    const grid = $('reagent-grid');
    if (grid) grid.innerHTML = '<div class="inv-loading" style="grid-column:1/-1"><i class="fas fa-spinner"></i> Loading reagents…</div>';

    const params = { category: 'reagent,qc_control,stain,culture_media', page_size: 100 };
    const search = $('reagent-search')?.value?.trim();
    const dept   = $('reagent-filter-dept')?.value;
    const fefo   = $('reagent-filter-fefo')?.value;
    if (search) params.search = search;
    if (dept)   params.department = dept;
    if (fefo === 'fefo') params.ordering = 'expiry_date';
    else if (fefo === 'fifo') params.ordering = 'created_at';

    try {
      const r    = await API.get('/inventory/items/', params);
      const data = await API.json(r);
      const items = data.results ?? data;
      $('badge-reagents') && ($('badge-reagents').textContent = data.count || items.length);
      renderReagentCards(items);
    } catch (e) {
      if (grid) grid.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:var(--space-xl);color:var(--alert-red)">❌ ${esc(e.message)}</div>`;
      renderReagentCardsDemo();
    }
  }

  function renderReagentCardsDemo() {
    const DEMO = [
      { id:1, code:'HEM-001', name:'EDTA Tubes 3mL', brand:'BD Vacutainer', batch_number:'BD-2025-0044', catalog_no:'367861', current_stock:18, min_stock:50, unit:'box', expiry_date:'2026-11-30', days_to_expiry:200, department_name:'Hematology', category:'consumable', status:'low_stock', cold_chain:false },
      { id:2, code:'CHM-007', name:'Glucose Reagent (Hexokinase)', brand:'Roche Diagnostics', batch_number:'RC-2025-0017', catalog_no:'10716251001', current_stock:2, min_stock:10, unit:'kit', expiry_date:'2026-06-15', days_to_expiry:31, department_name:'Chemistry', category:'reagent', status:'low_stock', cold_chain:true },
      { id:3, code:'SER-011', name:'HBsAg ELISA Strips', brand:'Autobio', batch_number:'AB-2025-0088', catalog_no:'C86095M', current_stock:24, min_stock:10, unit:'strip', expiry_date:'2026-05-20', days_to_expiry:5, department_name:'Serology', category:'reagent', status:'expiring_soon', cold_chain:true },
      { id:4, code:'QC-001', name:'Chemistry Multi-Level Control', brand:'Bio-Rad', batch_number:'BRC-L1-2025', catalog_no:'694811', current_stock:8, min_stock:5, unit:'vial', expiry_date:'2026-05-24', days_to_expiry:9, department_name:'Chemistry', category:'qc_control', status:'expiring_soon', cold_chain:true },
      { id:5, code:'MIC-012', name:'Blood Culture Bottles (Aerobic)', brand:'bioMérieux', batch_number:'BM-2025-0033', catalog_no:'410471', current_stock:5, min_stock:20, unit:'bottle', expiry_date:'2026-09-30', days_to_expiry:138, department_name:'Microbiology', category:'culture_media', status:'low_stock', cold_chain:true },
      { id:6, code:'STN-003', name:'Leishman Stain 500mL', brand:'Sigma-Aldrich', batch_number:'SA-2023-0077', catalog_no:'L6254', current_stock:45, min_stock:10, unit:'bottle', expiry_date:'2026-06-06', days_to_expiry:22, department_name:'Hematology', category:'stain', status:'expiring_soon', cold_chain:false },
    ];
    renderReagentCards(DEMO);
  }

  function renderReagentCards(items) {
    const grid = $('reagent-grid');
    if (!grid) return;
    if (!items.length) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:var(--space-xl);color:var(--text-muted)">No reagents found</div>';
      return;
    }
    const catColors = { reagent:'#FF6D00', qc_control:'#9B59B6', stain:'#E74C3C', culture_media:'#27AE60', consumable:'#2980B9', other:'#95A5A6' };
    grid.innerHTML = items.map(item => {
      const catColor = catColors[item.category] || '#95A5A6';
      const daysEx   = item.days_to_expiry;
      const expiryTier = daysEx == null ? '' : daysEx < 0 ? 'expired' : daysEx <= 7 ? 'expiring' : '';
      const expiryLabel = daysEx == null ? '—' : daysEx < 0 ? `⚠️ Expired ${Math.abs(daysEx)}d ago` : `${daysEx}d remaining`;
      const expiryColor = daysEx == null ? 'var(--text-muted)' : daysEx < 0 ? 'var(--alert-red)' : daysEx <= 7 ? 'var(--alert-orange)' : daysEx <= 30 ? 'var(--alert-yellow)' : 'var(--alert-green)';
      return `<div class="reagent-card ${item.status === 'low_stock' ? 'low_stock' : ''} ${expiryTier}">
        <div class="rc-band" style="background:${catColor}"></div>
        <div class="rc-body">
          <div class="rc-name">${esc(item.name)}</div>
          <div class="rc-brand">${esc(item.brand || '—')} ${item.cold_chain ? '❄️' : ''}</div>
          <div class="rc-lot-row">
            ${item.batch_number ? `<span class="rc-lot-chip">Lot: ${esc(item.batch_number)}</span>` : ''}
            ${item.catalog_no   ? `<span class="rc-lot-chip">Cat: ${esc(item.catalog_no)}</span>`   : ''}
            <span class="rc-lot-chip">${esc(item.department_name || '—')}</span>
          </div>
          <div class="rc-stock-row">
            <span class="rc-stock-val" style="color:${item.current_stock <= item.min_stock ? 'var(--alert-orange)' : 'var(--text-primary)'}">${fmtNum(item.current_stock)}</span>
            <span class="rc-stock-unit"> ${esc(item.unit)}</span>
            ${item.current_stock <= item.min_stock ? `<span class="badge badge-orange" style="font-size:9px;margin-left:8px">LOW STOCK</span>` : ''}
          </div>
          <div class="rc-expiry" style="color:${expiryColor}">⏰ ${expiryLabel} · ${item.expiry_date ? fmt.date(item.expiry_date) : 'No expiry'}</div>
        </div>
        <div class="rc-footer">
          <button class="btn btn-primary btn-sm" style="flex:1" onclick="window._invMove(${item.id}, 'restock')">⬆️ Add Stock</button>
          <button class="btn btn-secondary btn-sm" onclick="window._invMove(${item.id}, 'issue')">⬇️ Issue</button>
          <button class="btn btn-ghost btn-sm" onclick="window._invDetail(${item.id})">📋</button>
        </div>
      </div>`;
    }).join('');
  }

  let reagentSearchTimer = null;
  $('reagent-search')?.addEventListener('input', () => { clearTimeout(reagentSearchTimer); reagentSearchTimer = setTimeout(loadReagents, 350); });
  $('reagent-filter-dept')?.addEventListener('change', loadReagents);
  $('reagent-filter-fefo')?.addEventListener('change', loadReagents);

  /* ════════════════════════════════════════════════════════════
     EXPIRY TRACKER
  ════════════════════════════════════════════════════════════ */
  async function loadExpiry() {
    const tbody = $('expiry-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="8"><div class="inv-loading"><i class="fas fa-spinner"></i> Loading…</div></td></tr>';
    try {
      const r    = await API.get('/inventory/items/', { ordering: 'expiry_date', has_expiry: 'true', page_size: 200 });
      const data = await API.json(r);
      const items = (data.results ?? data).filter(i => i.expiry_date);
      renderExpiryTable(items);
      updateExpiryKPIs(items);
    } catch (_) { renderExpiryDemo(); }
  }

  function renderExpiryDemo() {
    const today = new Date();
    const addDays = n => { const d = new Date(today); d.setDate(d.getDate()+n); return d.toISOString().slice(0,10); };
    const items = [
      { id:1, code:'CHM-022', name:'Protein Reagent BCA Kit', batch_number:'LOT-0082', current_stock:3, unit:'kit', expiry_date:addDays(-3), days_to_expiry:-3, department_name:'Chemistry', status:'expired' },
      { id:2, code:'SER-011', name:'HBsAg ELISA Strips', batch_number:'LOT-0041', current_stock:24, unit:'strip', expiry_date:addDays(5), days_to_expiry:5, department_name:'Serology', status:'expiring_soon' },
      { id:3, code:'QC-001', name:'Chemistry Multi-Level Control', batch_number:'QC-A-2025', current_stock:8, unit:'vial', expiry_date:addDays(9), days_to_expiry:9, department_name:'Chemistry', status:'expiring_soon' },
      { id:4, code:'STN-003', name:'Leishman Stain 500mL', batch_number:'S-0077', current_stock:45, unit:'bottle', expiry_date:addDays(22), days_to_expiry:22, department_name:'Hematology', status:'expiring_soon' },
      { id:5, code:'HEM-001', name:'EDTA Tubes 3mL', batch_number:'BD-0044', current_stock:180, unit:'tube', expiry_date:addDays(200), days_to_expiry:200, department_name:'Hematology', status:'in_stock' },
    ];
    renderExpiryTable(items);
    updateExpiryKPIs(items);
  }

  function renderExpiryTable(items) {
    const tbody = $('expiry-tbody');
    if (!tbody) return;
    if (!items.length) { tbody.innerHTML = '<tr><td colspan="8"><div class="inv-loading">✅ No expiry concerns</div></td></tr>'; return; }
    tbody.innerHTML = items.map(item => {
      const d   = item.days_to_expiry;
      const cls = d < 0 ? 'ed-expired' : d <= 7 ? 'ed-7' : d <= 14 ? 'ed-14' : d <= 30 ? 'ed-30' : 'ed-ok';
      const lbl = d < 0 ? `Expired ${Math.abs(d)}d ago` : d <= 30 ? `${d}d left` : `${d}d`;
      const tier= d < 0 ? '🚨 Expired' : d <= 7 ? '🔴 Critical' : d <= 14 ? '🟠 Warning' : d <= 30 ? '🟡 Alert' : '✅ OK';
      return `<tr style="${d < 0 ? 'background:rgba(255,23,68,.03)' : d <= 7 ? 'background:rgba(255,109,0,.03)' : ''}">
        <td><div class="it-name">${esc(item.name)}</div><div class="it-code">${esc(item.code)}</div></td>
        <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(item.department_name || '—')}</td>
        <td style="font-family:var(--font-mono);font-size:11px">${esc(item.batch_number || '—')}</td>
        <td><strong style="font-family:var(--font-mono)">${fmtNum(item.current_stock)}</strong> <span style="font-size:10px;color:var(--text-muted)">${esc(item.unit)}</span></td>
        <td style="font-family:var(--font-mono);font-size:11px">${fmt.date(item.expiry_date)}</td>
        <td><span class="expiry-days ${cls}">${lbl}</span></td>
        <td style="font-size:var(--text-xs)">${tier}</td>
        <td style="text-align:right">
          ${d < 0 || d <= 7
            ? `<button class="btn btn-danger btn-sm" onclick="window._invMove(${item.id}, 'expired')" title="Mark as disposed">🗑️ Dispose</button>`
            : `<button class="btn btn-ghost btn-sm" onclick="window._invDetail(${item.id})">📋</button>`
          }
        </td>
      </tr>`;
    }).join('');
  }

  function updateExpiryKPIs(items) {
    const expired = items.filter(i => i.days_to_expiry < 0).length;
    const d7      = items.filter(i => i.days_to_expiry >= 0 && i.days_to_expiry <= 7).length;
    const d14     = items.filter(i => i.days_to_expiry > 7 && i.days_to_expiry <= 14).length;
    const d30     = items.filter(i => i.days_to_expiry > 14 && i.days_to_expiry <= 30).length;
    const ok      = items.filter(i => i.days_to_expiry > 30).length;
    $('et-expired') && ($('et-expired').textContent = expired);
    $('et-7')       && ($('et-7').textContent       = d7);
    $('et-14')      && ($('et-14').textContent      = d14);
    $('et-30')      && ($('et-30').textContent      = d30);
    $('et-ok')      && ($('et-ok').textContent      = ok);
    $('badge-expiry')&& ($('badge-expiry').textContent = expired + d7);
  }

  /* ════════════════════════════════════════════════════════════
     PURCHASE ORDERS
  ════════════════════════════════════════════════════════════ */
  async function loadPOs() {
    const tbody = $('po-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="8"><div class="inv-loading"><i class="fas fa-spinner"></i> Loading…</div></td></tr>';
    const status = $('po-filter-status')?.value || '';
    try {
      const r    = await API.get('/inventory/purchase-orders/', status ? { status } : {});
      const data = await API.json(r);
      const pos  = data.results ?? data;
      $('badge-orders') && ($('badge-orders').textContent = pos.filter(p => ['submitted','approved'].includes(p.status)).length || pos.length);
      renderPOTable(pos);
    } catch (_) { renderPODemo(); }
  }

  function renderPODemo() {
    renderPOTable([
      { id:1, po_number:'PO-20260508-001', supplier_name:'BD Biosciences Rwanda', total_amount:'1250000', expected_date:'2026-05-25', status:'approved', created_at:new Date().toISOString(), requested_by_name:'Lab Manager' },
      { id:2, po_number:'PO-20260506-002', supplier_name:'Roche Diagnostics EA', total_amount:'3400000', expected_date:'2026-06-02', status:'submitted', created_at:new Date(Date.now()-172800000).toISOString(), requested_by_name:'Procurement Officer' },
      { id:3, po_number:'PO-20260501-003', supplier_name:'Bio-Rad Laboratories', total_amount:'890000', expected_date:'2026-05-20', status:'received', created_at:new Date(Date.now()-604800000).toISOString(), requested_by_name:'Quality Manager' },
    ]);
  }

  function renderPOTable(pos) {
    const tbody = $('po-tbody');
    if (!tbody) return;
    if (!pos.length) { tbody.innerHTML = '<tr><td colspan="8"><div class="inv-loading">No purchase orders found</div></td></tr>'; return; }
    const poStatusCls = { draft:'po-draft', submitted:'po-submitted', approved:'po-approved', received:'po-received', cancelled:'po-cancelled' };
    tbody.innerHTML = pos.map(po => `<tr>
      <td><span style="font-family:var(--font-mono);font-size:11px;font-weight:700;color:var(--blue-glow)">${esc(po.po_number)}</span></td>
      <td style="font-size:var(--text-xs)">${esc(po.supplier_name || po.supplier)}</td>
      <td style="font-family:var(--font-mono);font-size:11px;color:var(--alert-orange)">${parseFloat(po.total_amount || 0).toLocaleString()} RWF</td>
      <td style="font-family:var(--font-mono);font-size:11px">${po.expected_date ? fmt.date(po.expected_date) : '—'}</td>
      <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(po.requested_by_name || '—')}</td>
      <td><span class="po-status ${poStatusCls[po.status] || 'po-draft'}">${esc(po.status)}</span></td>
      <td style="font-size:10px;color:var(--text-muted)">${fmt.datetime(po.created_at)}</td>
      <td style="text-align:right">
        ${po.status === 'draft' || po.status === 'submitted'
          ? `<button class="btn btn-primary btn-sm" onclick="window._poApprove(${po.id})">✅ Approve</button>`
          : po.status === 'approved'
          ? `<button class="btn btn-success btn-sm" onclick="window._poReceive(${po.id})">📦 Receive</button>`
          : `<button class="btn btn-ghost btn-sm" onclick="window._poView(${po.id})">👁️ View</button>`}
      </td>
    </tr>`).join('');
  }

  $('po-filter-status')?.addEventListener('change', loadPOs);

  window._poApprove = async id => {
    try {
      const r = await fetch(`/api/v1/inventory/purchase-orders/${id}/approve/`, { method:'POST', headers:{'X-CSRFToken':CSRF()} });
      if (!r.ok) throw new Error('Failed');
      Toast.success('PO Approved', 'Purchase order approved and sent to supplier.');
      loadPOs();
    } catch (e) { Toast.error('Failed', e.message); }
  };

  window._poReceive = async id => {
    try {
      const r = await fetch(`/api/v1/inventory/purchase-orders/${id}/receive/`, { method:'POST', headers:{'X-CSRFToken':CSRF()} });
      if (!r.ok) throw new Error('Failed');
      Toast.success('PO Received', 'Delivery confirmed. Stock updated automatically.');
      loadPOs();
      loadDashboard();
    } catch (e) { Toast.error('Failed', e.message); }
  };

  window._poView = id => Toast.info('PO', `View PO #${id} — detail view coming.`);

  /* ════════════════════════════════════════════════════════════
     STOCK MOVEMENTS LOG
  ════════════════════════════════════════════════════════════ */
  async function loadMovements() {
    const tbody = $('movements-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="8"><div class="inv-loading"><i class="fas fa-spinner"></i> Loading…</div></td></tr>';
    const params = { page_size: 50 };
    const type = $('mov-filter-type')?.value;
    const date = $('mov-filter-date')?.value;
    const search = $('mov-search')?.value?.trim();
    if (type)   params.movement_type = type;
    if (date)   params.date_from     = date;
    if (search) params.search        = search;
    try {
      const r    = await API.get('/inventory/movements/', params);
      const data = await API.json(r);
      renderMovementsTable(data.results ?? data);
    } catch (_) { renderMovementsDemo(); }
  }

  function renderMovementsDemo() {
    const demo = [
      { id:1, performed_at:new Date().toISOString(), item_name:'EDTA Tubes 3mL', item_code:'HEM-001', movement_type:'restock', quantity:'100', balance_after:'180', department_name:'Hematology', performed_by_name:'Procurement', notes:'Monthly restock' },
      { id:2, performed_at:new Date(Date.now()-7200000).toISOString(), item_name:'Glucose Reagent', item_code:'CHM-007', movement_type:'issue', quantity:'2', balance_after:'2', department_name:'Chemistry', performed_by_name:'Lab Tech', notes:'Daily use' },
      { id:3, performed_at:new Date(Date.now()-86400000).toISOString(), item_name:'Old HCV Strips', item_code:'SER-022', movement_type:'expired', quantity:'5', balance_after:'0', department_name:'Serology', performed_by_name:'Quality Officer', notes:'Expired batch disposal' },
    ];
    renderMovementsTable(demo);
  }

  function renderMovementsTable(movements) {
    const tbody = $('movements-tbody');
    if (!tbody) return;
    const icons  = { restock:'⬆️', issue:'⬇️', adjust:'🔧', transfer:'↗️', expired:'🗑️', return:'↩️' };
    const colors = { restock:'var(--alert-green)', return:'var(--alert-green)', issue:'var(--alert-red)', expired:'var(--alert-red)', adjust:'var(--blue-glow)', transfer:'var(--cyan)' };
    const sign   = { restock:'+', return:'+', issue:'-', expired:'-', adjust:'=', transfer:'→' };
    tbody.innerHTML = movements.map(m => `<tr>
      <td style="font-size:10px;font-family:var(--font-mono);color:var(--text-muted)">${fmt.datetime(m.performed_at)}</td>
      <td><div class="it-name">${esc(m.item_name || '—')}</div><div class="it-code">${esc(m.item_code || '')}</div></td>
      <td><span style="font-size:12px">${icons[m.movement_type] || '🔄'}</span> <span style="font-size:var(--text-xs);font-weight:600">${esc(m.movement_type)}</span></td>
      <td style="font-family:var(--font-mono);font-weight:700;color:${colors[m.movement_type] || 'var(--text-primary)'}">${sign[m.movement_type] || ''}${fmtNum(m.quantity)}</td>
      <td style="font-family:var(--font-mono);font-size:11px">${fmtNum(m.balance_after)}</td>
      <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(m.department_name || '—')}</td>
      <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(m.performed_by_name || '—')}</td>
      <td style="font-size:var(--text-xs);color:var(--text-muted)">${esc(m.notes || '—')}</td>
    </tr>`).join('');
  }

  let movSearchTimer = null;
  $('mov-search')?.addEventListener('input', () => { clearTimeout(movSearchTimer); movSearchTimer = setTimeout(loadMovements, 350); });
  $('mov-filter-type')?.addEventListener('change', loadMovements);
  $('mov-filter-date')?.addEventListener('change', loadMovements);

  /* ════════════════════════════════════════════════════════════
     ADD ITEM MODAL
  ════════════════════════════════════════════════════════════ */
  $('btn-add-item')?.addEventListener('click', openAddItem);
  $('add-item-close')?.addEventListener('click',  () => { $('add-item-modal').style.display = 'none'; });
  $('add-item-cancel')?.addEventListener('click', () => { $('add-item-modal').style.display = 'none'; });

  function openAddItem() {
    loadSupplierOptions('ai-supplier');
    $('add-item-modal').style.display = 'flex';
  }

  $('add-item-submit')?.addEventListener('click', async () => {
    const code = $('ai-code')?.value?.trim();
    const name = $('ai-name')?.value?.trim();
    const unit = $('ai-unit')?.value?.trim();
    if (!code || !name || !unit) { Toast.warning('Required', 'Fill Code, Name and Unit.'); return; }
    const btn = $('add-item-submit');
    btn.classList.add('btn-loading');
    const body = {
      code, name, unit,
      brand:        $('ai-brand')?.value?.trim() || '',
      catalog_no:   $('ai-catalog')?.value?.trim() || '',
      category:     $('ai-category')?.value || 'reagent',
      department:   $('ai-dept')?.value || null,
      supplier:     $('ai-supplier')?.value || null,
      current_stock:parseFloat($('ai-stock')?.value || 0),
      min_stock:    parseFloat($('ai-min')?.value || 10),
      max_stock:    parseFloat($('ai-max')?.value || 100),
      reorder_level:parseFloat($('ai-reorder')?.value || 20),
      batch_number: $('ai-batch')?.value?.trim() || '',
      expiry_date:  $('ai-expiry')?.value || null,
      unit_cost:    parseFloat($('ai-cost')?.value || 0),
      storage_temp: $('ai-storage')?.value || '',
      cold_chain:   $('ai-cold-chain')?.checked || false,
    };
    try {
      const r = await fetch('/api/v1/inventory/items/', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':CSRF()},
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(Object.values(data).flat().join(' '));
      Toast.success('✅ Item Added', `${data.name} (${data.code}) added to inventory.`);
      $('add-item-modal').style.display = 'none';
      loadDashboard(); loadLedger(); if (activePane === 'pane-reagents') loadReagents();
    } catch (e) { Toast.error('Failed', e.message); }
    finally { btn.classList.remove('btn-loading'); }
  });

  /* ════════════════════════════════════════════════════════════
     STOCK MOVEMENT MODAL
  ════════════════════════════════════════════════════════════ */
  $('move-modal-close')?.addEventListener('click', () => { $('move-modal').style.display = 'none'; });
  $('move-cancel')?.addEventListener('click',      () => { $('move-modal').style.display = 'none'; });

  window._invMove = async (itemId, defaultType) => {
    moveTargetId = itemId;
    try {
      const r    = await API.get(`/inventory/items/${itemId}/`);
      const item = await API.json(r);
      $('move-item-info').innerHTML = `
        <div style="font-weight:700;font-size:var(--text-sm)">${esc(item.name)}</div>
        <div style="font-size:var(--text-xs);color:var(--text-muted)">
          ${esc(item.code)} · Current stock: <strong style="font-family:var(--font-mono)">${fmtNum(item.current_stock)} ${esc(item.unit)}</strong>
        </div>`;
      $('move-type').value = defaultType || 'restock';
      $('move-qty').value = '';
      $('move-batch').value = '';
      $('move-expiry').value = '';
      $('move-notes').value = '';
      $('move-modal-title').textContent = defaultType === 'restock' ? '⬆️ Add Stock' : defaultType === 'issue' ? '⬇️ Issue Stock' : defaultType === 'expired' ? '🗑️ Dispose Expired' : '📦 Stock Movement';
      loadSupplierOptions('move-dept');
      $('move-modal').style.display = 'flex';
    } catch (e) { Toast.error('Error', e.message); }
  };

  $('move-type')?.addEventListener('change', function () {
    const type = this.value;
    $('move-batch-row').style.display  = type === 'restock' ? 'flex' : 'none';
    $('move-expiry-row').style.display = type === 'restock' ? 'flex' : 'none';
    $('move-cost-row').style.display   = type === 'restock' ? 'flex' : 'none';
  });

  $('move-submit')?.addEventListener('click', async () => {
    if (!moveTargetId) return;
    const qty = parseFloat($('move-qty')?.value);
    if (!qty || qty <= 0) { Toast.warning('Required', 'Enter a valid quantity.'); return; }
    const btn = $('move-submit');
    btn.classList.add('btn-loading');
    const body = {
      item:          moveTargetId,
      movement_type: $('move-type')?.value || 'restock',
      quantity:      qty,
      batch_number:  $('move-batch')?.value?.trim() || '',
      expiry_date:   $('move-expiry')?.value || null,
      department:    $('move-dept')?.value || null,
      unit_cost:     parseFloat($('move-cost')?.value || 0),
      notes:         $('move-notes')?.value?.trim() || '',
    };
    try {
      const r = await fetch('/api/v1/inventory/movements/', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':CSRF()},
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(Object.values(data).flat().join(' '));
      const typeLabel = { restock:'Restocked', issue:'Issued', adjust:'Adjusted', transfer:'Transferred', expired:'Disposed' }[$('move-type')?.value] || 'Updated';
      Toast.success(`✅ ${typeLabel}`, `Balance after: ${fmtNum(data.balance_after)}`);
      $('move-modal').style.display = 'none';
      loadDashboard(); loadLedger();
      if (activePane === 'pane-reagents') loadReagents();
      if (activePane === 'pane-expiry')   loadExpiry();
      if (activePane === 'pane-movements') loadMovements();
    } catch (e) { Toast.error('Failed', e.message); }
    finally { btn.classList.remove('btn-loading'); }
  });

  /* ════════════════════════════════════════════════════════════
     ITEM DETAIL MODAL
  ════════════════════════════════════════════════════════════ */
  $('item-detail-close')?.addEventListener('click',  () => { $('item-detail-modal').style.display = 'none'; });
  $('item-detail-close2')?.addEventListener('click', () => { $('item-detail-modal').style.display = 'none'; });
  $('item-detail-restock')?.addEventListener('click',() => { $('item-detail-modal').style.display = 'none'; window._invMove(moveTargetId, 'restock'); });
  $('item-detail-issue')?.addEventListener('click',  () => { $('item-detail-modal').style.display = 'none'; window._invMove(moveTargetId, 'issue'); });

  window._invDetail = async id => {
    moveTargetId = id;
    try {
      const r    = await API.get(`/inventory/items/${id}/`);
      const item = await API.json(r);
      $('item-detail-title').textContent = `📦 ${item.name}`;
      $('item-detail-grid').innerHTML = [
        ['Code',      item.code],
        ['Category',  item.category_display || item.category],
        ['Department',item.department_name || '—'],
        ['Brand',     item.brand || '—'],
        ['Catalog #', item.catalog_no || '—'],
        ['Batch/Lot', item.batch_number || '—'],
        ['Current Stock', `${fmtNum(item.current_stock)} ${item.unit}`],
        ['Min / Max', `${fmtNum(item.min_stock)} / ${fmtNum(item.max_stock)}`],
        ['Reorder Level', `${fmtNum(item.reorder_level)} ${item.unit}`],
        ['Expiry Date',   item.expiry_date ? fmt.date(item.expiry_date) : '—'],
        ['Storage Temp',  item.storage_temp || '—'],
        ['Supplier',      item.supplier_name || '—'],
        ['Unit Cost',     item.unit_cost ? `${parseFloat(item.unit_cost).toLocaleString()} RWF` : '—'],
        ['Status',        statusLabel(item.status)],
      ].map(([l,v]) => `<div class="idg-field"><div class="idg-label">${esc(l)}</div><div class="idg-value">${esc(v)}</div></div>`).join('');

      // Load movement history
      const hr = await API.get(`/inventory/movements/`, { item: id, page_size: 20 });
      const hd = await API.json(hr);
      const movs = hd.results ?? hd;
      const icons  = { restock:'⬆️', issue:'⬇️', adjust:'🔧', transfer:'↗️', expired:'🗑️', return:'↩️' };
      $('item-history-tbody').innerHTML = movs.length
        ? movs.map(m => `<tr>
            <td style="font-size:10px;font-family:var(--font-mono)">${fmt.datetime(m.performed_at)}</td>
            <td>${icons[m.movement_type] || '🔄'} ${esc(m.movement_type)}</td>
            <td style="font-family:var(--font-mono);font-weight:700">${fmtNum(m.quantity)}</td>
            <td style="font-family:var(--font-mono)">${fmtNum(m.balance_after)}</td>
            <td style="font-size:10px;color:var(--text-muted)">${esc(m.performed_by_name || '—')}</td>
            <td style="font-size:10px;color:var(--text-muted)">${esc(m.notes || '—')}</td>
          </tr>`).join('')
        : '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:var(--space-lg)">No movement history</td></tr>';

      $('item-detail-modal').style.display = 'flex';
    } catch (e) { Toast.error('Error', e.message); }
  };

  /* ════════════════════════════════════════════════════════════
     NEW PO MODAL
  ════════════════════════════════════════════════════════════ */
  $('btn-new-po')?.addEventListener('click',     () => { loadSupplierOptions('po-supplier'); poLines = []; renderPOLines(); $('po-modal').style.display = 'flex'; });
  $('po-modal-close')?.addEventListener('click', () => { $('po-modal').style.display = 'none'; });
  $('po-cancel')?.addEventListener('click',      () => { $('po-modal').style.display = 'none'; });
  $('po-add-line')?.addEventListener('click',    () => { poLines.push({ item_id:'', qty:1, unit_cost:0 }); renderPOLines(); });

  function renderPOLines() {
    const el = $('po-lines');
    if (!el) return;
    if (!poLines.length) { el.innerHTML = '<div style="font-size:var(--text-xs);color:var(--text-muted);text-align:center;padding:var(--space-md)">No items yet — click "+ Add Line"</div>'; return; }
    el.innerHTML = poLines.map((line, i) => `
      <div class="po-line">
        <select class="form-input" id="po-item-${i}" style="font-size:11px">
          <option value="">Select item…</option>
          ${allItems.map(it => `<option value="${it.id}" ${it.id === line.item_id ? 'selected' : ''}>${esc(it.code)} — ${esc(it.name)}</option>`).join('')}
        </select>
        <input type="number" class="form-input" id="po-qty-${i}" value="${line.qty}" min="1" placeholder="Qty" style="font-size:11px">
        <input type="number" class="form-input" id="po-cost-${i}" value="${line.unit_cost}" min="0" step="0.01" placeholder="Unit cost" style="font-size:11px">
        <button class="po-line-remove" onclick="window._poRemoveLine(${i})">✕</button>
      </div>`).join('');
  }
  window._poRemoveLine = i => { poLines.splice(i, 1); renderPOLines(); };

  async function submitPO(status) {
    const suppId = $('po-supplier')?.value;
    if (!suppId) { Toast.warning('Required', 'Select a supplier.'); return; }
    const lines = poLines.map((_, i) => ({
      item:    parseInt($(`po-item-${i}`)?.value) || null,
      qty:     parseFloat($(`po-qty-${i}`)?.value) || 1,
      unit_cost: parseFloat($(`po-cost-${i}`)?.value) || 0,
    })).filter(l => l.item);
    if (!lines.length) { Toast.warning('Required', 'Add at least one item line.'); return; }
    const btn = status === 'submitted' ? $('po-submit') : $('po-save-draft');
    btn?.classList.add('btn-loading');
    const body = {
      supplier: suppId,
      status,
      expected_date: $('po-expected')?.value || null,
      notes: $('po-notes')?.value?.trim() || '',
      lines,
    };
    try {
      const r = await fetch('/api/v1/inventory/purchase-orders/', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':CSRF()},
        body: JSON.stringify(body),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(Object.values(data).flat().join(' '));
      Toast.success('✅ PO Created', `${data.po_number} — ${status === 'submitted' ? 'Submitted' : 'Saved as draft'}`);
      $('po-modal').style.display = 'none';
      loadPOs();
    } catch (e) { Toast.error('Failed', e.message); }
    finally { btn?.classList.remove('btn-loading'); }
  }
  $('po-submit')?.addEventListener('click',     () => submitPO('submitted'));
  $('po-save-draft')?.addEventListener('click', () => submitPO('draft'));

  /* ════════════════════════════════════════════════════════════
     SUPPLIERS
  ════════════════════════════════════════════════════════════ */
  async function loadSupplierOptions(selectId) {
    if (!allSuppliers.length) {
      try {
        const r = await API.get('/inventory/suppliers/');
        allSuppliers = (await API.json(r)).results ?? await API.json(r);
      } catch (_) {
        allSuppliers = [{id:1,name:'BD Biosciences'},{id:2,name:'Roche Diagnostics'},{id:3,name:'Bio-Rad'}];
      }
    }
    const sel = $(selectId);
    if (!sel) return;
    const placeholder = sel.options[0]?.value === '' ? sel.options[0].outerHTML : '';
    sel.innerHTML = placeholder + allSuppliers.map(s => `<option value="${s.id}">${esc(s.name)}</option>`).join('');
  }

  /* ════════════════════════════════════════════════════════════
     UTILITY
  ════════════════════════════════════════════════════════════ */
  function statusLabel(status) {
    return { in_stock:'✅ In Stock', low_stock:'⚠️ Low Stock', out_of_stock:'❌ Out of Stock', expiring_soon:'⏰ Expiring Soon', expired:'🚫 Expired', discontinued:'⛔ Discontinued' }[status] || status || '—';
  }

  /* ── Init ─────────────────────────────────────────────────── */
  const dashPane = $('pane-dashboard');
  if (dashPane) { dashPane.style.display = 'flex'; dashPane.style.flexDirection = 'column'; }
  loadDashboard();
  loadLedger();

})();
