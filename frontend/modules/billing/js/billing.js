/**
 * JORINOVA NEXUS ALIS-X — Billing & Consumable Engine
 * Dual-Role: Receptionist (CREATOR) + Phlebotomist (VALIDATOR)
 * Segregation of Duties · Auto Consumable Mapping · Inventory Deduction
 * Spec: No single user can create AND validate billing completely.
 */
'use strict';

(function () {
  const NEXUS = window.NEXUS || {};
  const API   = NEXUS.API   || { get:(u,p)=>fetch('/api/v1'+u+(p?'?'+new URLSearchParams(p):'')), json:r=>r.json(), checkError:async r=>{if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||r.statusText)} };
  const Toast = NEXUS.Toast || { success:(t,m)=>console.log(t,m), error:(t,m)=>console.error(t,m), warning:(t,m)=>console.warn(t,m), info:(t,m)=>console.info(t,m) };
  const CSRF  = () => window.NEXUS?.csrf || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
  const esc   = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt   = { date:d=>d?new Date(d).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}):'—', time:d=>d?new Date(d).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}):'—', num:n=>n!=null?parseFloat(n).toLocaleString():'—' };
  const $     = id => document.getElementById(id);

  /* ── Test catalog with consumables mapping ─────────────────── */
  const TEST_CATALOG = [
    { id:1, code:'HEM-CBC', name:'Full Blood Count (CBC)', dept:'Hematology', price:3500, consumables:[
      { name:'EDTA Tube 3mL', qty:1, unit:'tube', unit_cost:200 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
      { name:'CBC Reagent Pack', qty:1, unit:'test', unit_cost:1800 },
    ]},
    { id:2, code:'CHM-GLU', name:'Glucose (Fasting)', dept:'Chemistry', price:2500, consumables:[
      { name:'Fluoride Tube 2mL', qty:1, unit:'tube', unit_cost:250 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
      { name:'Glucose Reagent', qty:1, unit:'test', unit_cost:900 },
    ]},
    { id:3, code:'CHM-CMP', name:'Comprehensive Metabolic Panel', dept:'Chemistry', price:12000, consumables:[
      { name:'SST Tube 5mL', qty:1, unit:'tube', unit_cost:300 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
      { name:'Chemistry Reagent Kit', qty:1, unit:'test', unit_cost:4500 },
    ]},
    { id:4, code:'SER-HIV', name:'HIV RDT (Combo)', dept:'Serology', price:3000, consumables:[
      { name:'HIV RDT Test Kit', qty:1, unit:'test', unit_cost:1200 },
      { name:'Lancet', qty:1, unit:'pcs', unit_cost:50 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
    ]},
    { id:5, code:'SER-MAL', name:'Malaria RDT', dept:'Serology', price:2000, consumables:[
      { name:'Malaria RDT Kit', qty:1, unit:'test', unit_cost:800 },
      { name:'Lancet', qty:1, unit:'pcs', unit_cost:50 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
    ]},
    { id:6, code:'MIC-CX', name:'Blood Culture', dept:'Microbiology', price:8500, consumables:[
      { name:'Blood Culture Bottle (Aerobic)', qty:1, unit:'bottle', unit_cost:3200 },
      { name:'Blood Culture Bottle (Anaerobic)', qty:1, unit:'bottle', unit_cost:3200 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
      { name:'Alcohol Swabs', qty:2, unit:'pcs', unit_cost:50 },
    ]},
    { id:7, code:'HEM-ESR', name:'Erythrocyte Sedimentation Rate (ESR)', dept:'Hematology', price:2000, consumables:[
      { name:'Citrate Tube 1.8mL', qty:1, unit:'tube', unit_cost:180 },
      { name:'Westergren Pipette', qty:1, unit:'pcs', unit_cost:120 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
    ]},
    { id:8, code:'CHM-HBA1C', name:'HbA1c', dept:'Chemistry', price:6000, consumables:[
      { name:'EDTA Tube 3mL', qty:1, unit:'tube', unit_cost:200 },
      { name:'HbA1c Cartridge', qty:1, unit:'test', unit_cost:2800 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
    ]},
    { id:9, code:'SER-HBsAG', name:'HBsAg (Hepatitis B surface antigen)', dept:'Serology', price:4000, consumables:[
      { name:'SST Tube 5mL', qty:1, unit:'tube', unit_cost:300 },
      { name:'HBsAg RDT Kit', qty:1, unit:'test', unit_cost:1500 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
    ]},
    { id:10, code:'COA-PT', name:'Prothrombin Time (PT/INR)', dept:'Coagulation', price:5000, consumables:[
      { name:'Citrate Tube 2.7mL', qty:1, unit:'tube', unit_cost:220 },
      { name:'PT Reagent', qty:1, unit:'test', unit_cost:2000 },
      { name:'Gloves (pair)', qty:1, unit:'pair', unit_cost:150 },
    ]},
  ];

  /* ── Demo data ─────────────────────────────────────────────── */
  const DEMO_PATIENTS = [
    { id:1, pid:'PID-2026-000142', full_name:'KAMANZI Jean', unique_lab_id:'RW-0000142', dob:'1990-03-12', gender:'male', phone:'+250788001122' },
    { id:2, pid:'PID-2026-000287', full_name:'UWIMANA Grace', unique_lab_id:'RW-0000287', dob:'1998-07-25', gender:'female', phone:'+250722334455' },
    { id:3, pid:'PID-2026-000388', full_name:'HABIMANA Eric', unique_lab_id:'RW-0000388', dob:'1972-11-08', gender:'male', phone:'+250733445566' },
    { id:4, pid:'PID-2026-000501', full_name:'MUKAMANA Rose', unique_lab_id:'RW-0000501', dob:'1984-02-14', gender:'female', phone:'+250710056789' },
  ];

  const DEMO_INVOICES = [
    { id:1, invoice_number:'INV-20260515-001', patient_name:'KAMANZI Jean', patient_pid:'PID-2026-000142', patient_lid:'RW-0000142', tests:['CBC','ESR'], consumables:3, total_amount:5500, insurance_coverage:0, patient_amount:5500, status:'pending', payment_type:'private', created_at:new Date().toISOString() },
    { id:2, invoice_number:'INV-20260515-002', patient_name:'UWIMANA Grace', patient_pid:'PID-2026-000287', patient_lid:'RW-0000287', tests:['HIV RDT','Malaria RDT','Glucose'], consumables:5, total_amount:7500, insurance_coverage:4500, patient_amount:3000, status:'provisional', payment_type:'mutuelle', created_at:new Date(Date.now()-1800000).toISOString() },
    { id:3, invoice_number:'INV-20260515-003', patient_name:'HABIMANA Eric', patient_pid:'PID-2026-000388', patient_lid:'RW-0000388', tests:['CMP','HbA1c','PT'], consumables:7, total_amount:23000, insurance_coverage:20700, patient_amount:2300, status:'paid', payment_type:'rssb', created_at:new Date(Date.now()-3600000).toISOString() },
    { id:4, invoice_number:'INV-20260514-008', patient_name:'MUKAMANA Rose', patient_pid:'PID-2026-000501', patient_lid:'RW-0000501', tests:['HBsAg','CBC'], consumables:4, total_amount:7500, insurance_coverage:0, patient_amount:7500, status:'paid', payment_type:'private', created_at:new Date(Date.now()-86400000).toISOString() },
  ];

  const DEMO_PAYMENTS = [
    { time:'09:14', patient:'KAMANZI Jean', amount:'5,500', method:'💵 Cash', status:'paid' },
    { time:'08:47', patient:'HABIMANA Eric', amount:'2,300', method:'📱 MTN MoMo', status:'paid' },
    { time:'08:22', patient:'MUKAMANA Rose', amount:'7,500', method:'💵 Cash', status:'paid' },
  ];

  /* ── State ─────────────────────────────────────────────────── */
  let activePane    = 'pane-invoices';
  let selectedInvoice = null;
  let newInvPatient   = null;
  let newInvTests     = [];   // [{test, qty}]
  let payMethod       = 'cash';
  let activeValItem   = null;
  let invoices        = [...DEMO_INVOICES];

  /* ════════════════════════════════════════════════════════════
     TABS
  ════════════════════════════════════════════════════════════ */
  document.querySelectorAll('.bill-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.bill-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.bill-pane').forEach(p => p.style.display = 'none');
      tab.classList.add('active');
      activePane = tab.dataset.pane;
      const pane = $(activePane);
      if (pane) { pane.style.display = 'flex'; pane.style.flexDirection = 'column'; }
      onPaneChange(activePane);
    });
  });

  function onPaneChange(pane) {
    if (pane === 'pane-invoices')   loadInvoices();
    if (pane === 'pane-validation') loadValidationQueue();
    if (pane === 'pane-payments')   loadPaymentLog();
    if (pane === 'pane-insurance')  loadInsurance();
    if (pane === 'pane-summary')    loadSummary();
  }

  /* ════════════════════════════════════════════════════════════
     INVOICES PANE
  ════════════════════════════════════════════════════════════ */
  function loadInvoices() {
    renderKPIs();
    renderInvoiceTable(getFilteredInvoices());
  }

  function renderKPIs() {
    const total       = invoices.length;
    const paid        = invoices.filter(i => i.status === 'paid').length;
    const pending     = invoices.filter(i => i.status === 'pending').length;
    const provisional = invoices.filter(i => i.status === 'provisional').length;
    const revenue     = invoices.filter(i => i.status === 'paid').reduce((s,i) => s + (i.patient_amount || 0), 0);

    $('kpi-total')       && ($('kpi-total').textContent = total);
    $('kpi-paid')        && ($('kpi-paid').textContent = paid);
    $('kpi-pending')     && ($('kpi-pending').textContent = pending);
    $('kpi-provisional') && ($('kpi-provisional').textContent = provisional);
    $('kpi-revenue')     && ($('kpi-revenue').textContent = revenue.toLocaleString());
    $('badge-invoices')  && ($('badge-invoices').textContent = total);
    $('badge-validation')&& ($('badge-validation').textContent = provisional);
    $('hkpi-today')      && ($('hkpi-today').textContent = revenue.toLocaleString());
    $('hkpi-pending')    && ($('hkpi-pending').textContent = pending);
    $('hkpi-validate')   && ($('hkpi-validate').textContent = provisional);
  }

  function getFilteredInvoices() {
    const search = $('inv-search')?.value?.trim().toLowerCase() || '';
    const status = $('inv-filter-status')?.value || '';
    return invoices.filter(i => {
      if (status && i.status !== status) return false;
      if (search && !i.patient_name?.toLowerCase().includes(search) && !i.invoice_number?.toLowerCase().includes(search)) return false;
      return true;
    });
  }

  function renderInvoiceTable(list) {
    const tbody = $('inv-tbody');
    if (!tbody) return;
    $('inv-count') && ($('inv-count').textContent = `${list.length} invoices`);
    if (!list.length) { tbody.innerHTML = '<tr><td colspan="9"><div class="bill-loading">No invoices found</div></td></tr>'; return; }
    tbody.innerHTML = list.map(inv => {
      const stsCls = { paid:'inv-paid', pending:'inv-pending', provisional:'inv-provisional', partial:'inv-partial', cancelled:'inv-cancelled', waived:'inv-waived' }[inv.status] || '';
      const stsLbl = { paid:'✅ Paid', pending:'⏳ Pending', provisional:'📝 Provisional', partial:'💳 Partial', cancelled:'❌ Cancelled', waived:'🆓 Waived' }[inv.status] || inv.status;
      return `<tr onclick="window._invDetail(${inv.id})">
        <td><span class="inv-num">${esc(inv.invoice_number)}</span></td>
        <td>
          <div class="inv-patient-name">${esc(inv.patient_name)}</div>
          <div class="inv-pid">${esc(inv.patient_pid)} · <span style="color:var(--cyan)">🌐 ${esc(inv.patient_lid||'')}</span></div>
        </td>
        <td>${(inv.tests||[]).map(t => `<span class="inv-test-tag">${esc(t)}</span>`).join('')}</td>
        <td style="font-size:10px;color:var(--text-muted)">${inv.consumables || 0} items</td>
        <td><span class="inv-amount">${fmt.num(inv.total_amount)}</span></td>
        <td style="font-size:10px;color:var(--alert-green)">${inv.insurance_coverage > 0 ? fmt.num(inv.insurance_coverage) + ' RWF' : '—'}</td>
        <td><strong style="font-family:var(--font-mono);color:#00d4aa">${fmt.num(inv.patient_amount)}</strong></td>
        <td><span class="inv-status ${stsCls}">${stsLbl}</span></td>
        <td style="text-align:right">
          <div style="display:flex;gap:4px;justify-content:flex-end">
            ${inv.status === 'pending' ? `<button class="btn btn-primary btn-sm" onclick="event.stopPropagation();window._processPayment(${inv.id})">💳 Pay</button>` : ''}
            ${inv.status === 'provisional' ? `<button class="btn btn-ghost btn-sm" style="color:var(--alert-orange)" onclick="event.stopPropagation();window._goValidate(${inv.id})">🩸 Validate</button>` : ''}
            <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();window._printInv(${inv.id})">🖨️</button>
          </div>
        </td>
      </tr>`;
    }).join('');
  }

  let searchTimer = null;
  $('inv-search')?.addEventListener('input', () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadInvoices, 300); });
  $('inv-filter-status')?.addEventListener('change', loadInvoices);
  $('inv-filter-date')?.addEventListener('change', loadInvoices);
  $('inv-refresh')?.addEventListener('click', loadInvoices);

  window._invDetail = id => {
    const inv = invoices.find(i => i.id === id);
    if (!inv) return;
    selectedInvoice = inv;
    $('inv-detail-title').textContent = `${inv.invoice_number}`;
    $('inv-detail-body').innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--space-md);padding:var(--space-md);background:var(--bg-glass);border-radius:var(--radius-md);border:1px solid var(--border-dim);margin-bottom:var(--space-lg)">
        ${[['Patient',inv.patient_name],['PID',inv.patient_pid],['LID',inv.patient_lid||'—'],['Payment Type',inv.payment_type],['Status',inv.status],['Created',fmt.date(inv.created_at)]].map(([l,v])=>`<div><div style="font-size:10px;color:var(--text-muted);font-weight:700;text-transform:uppercase">${esc(l)}</div><div style="font-size:var(--text-sm);font-weight:600;color:var(--text-primary);margin-top:2px">${esc(v)}</div></div>`).join('')}
      </div>
      <div style="margin-bottom:var(--space-md)">
        <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:var(--text-muted);margin-bottom:var(--space-sm)">Tests</div>
        ${(inv.tests||[]).map(t=>`<span class="inv-test-tag">${esc(t)}</span>`).join('')}
      </div>
      <div style="display:flex;justify-content:flex-end;gap:var(--space-lg);padding:var(--space-md);background:rgba(0,212,170,.06);border:1px solid rgba(0,212,170,.2);border-radius:var(--radius-md)">
        <div><div style="font-size:10px;color:var(--text-muted)">Gross Total</div><div style="font-family:var(--font-mono);font-weight:700">${fmt.num(inv.total_amount)} RWF</div></div>
        <div><div style="font-size:10px;color:var(--text-muted)">Insurance</div><div style="font-family:var(--font-mono);font-weight:700;color:var(--alert-green)">${fmt.num(inv.insurance_coverage)} RWF</div></div>
        <div><div style="font-size:10px;color:var(--text-muted)">Patient Pays</div><div style="font-family:var(--font-display);font-size:var(--text-xl);font-weight:700;color:#00d4aa">${fmt.num(inv.patient_amount)} RWF</div></div>
      </div>`;
    $('inv-detail-modal').style.display = 'flex';
  };

  $('inv-detail-close')?.addEventListener('click',  () => { $('inv-detail-modal').style.display = 'none'; });
  $('inv-detail-close2')?.addEventListener('click', () => { $('inv-detail-modal').style.display = 'none'; });
  $('inv-detail-pay')?.addEventListener('click', () => {
    $('inv-detail-modal').style.display = 'none';
    if (selectedInvoice) window._processPayment(selectedInvoice.id);
  });
  $('inv-detail-print')?.addEventListener('click', () => {
    Toast.info('Print', 'Invoice print coming — NexusSig PQC will sign the document.');
  });

  window._processPayment = id => {
    document.querySelector('.bill-tab[data-pane="pane-payments"]')?.click();
    const inv = invoices.find(i => i.id === id);
    if (inv && $('pay-amount')) $('pay-amount').value = inv.patient_amount;
  };

  window._goValidate = id => {
    document.querySelector('.bill-tab[data-pane="pane-validation"]')?.click();
    const inv = invoices.find(i => i.id === id);
    if (inv) openValidationItem(inv);
  };

  window._printInv = id => Toast.info('Print', 'Generating printable invoice…');

  /* ════════════════════════════════════════════════════════════
     NEW INVOICE MODAL (Receptionist)
  ════════════════════════════════════════════════════════════ */
  $('btn-new-invoice')?.addEventListener('click', openNewInv);
  $('new-inv-close')?.addEventListener('click',  () => { $('new-inv-modal').style.display = 'none'; });
  $('new-inv-cancel')?.addEventListener('click', () => { $('new-inv-modal').style.display = 'none'; });

  function openNewInv() {
    newInvPatient = null;
    newInvTests   = [];
    $('nim-patient-search').value = '';
    $('nim-test-search').value    = '';
    $('nim-selected-tests').innerHTML = '';
    $('nim-consumables-section').style.display = 'none';
    $('nim-billing-summary').style.display = 'none';
    $('nim-patient-selected').style.display = 'none';
    $('ngt-val').textContent = '0 RWF';
    $('new-inv-modal').style.display = 'flex';
  }

  /* Patient search */
  let pSearchTimer = null;
  $('nim-patient-search')?.addEventListener('input', () => {
    clearTimeout(pSearchTimer);
    const q = $('nim-patient-search').value.trim().toLowerCase();
    if (q.length < 2) { closeDrop('nim-patient-drop'); return; }
    pSearchTimer = setTimeout(() => {
      const matches = DEMO_PATIENTS.filter(p => p.full_name.toLowerCase().includes(q) || p.pid.toLowerCase().includes(q));
      const drop = $('nim-patient-drop');
      if (!matches.length) { closeDrop('nim-patient-drop'); return; }
      drop.innerHTML = matches.map(p => `
        <div class="nim-pd-item" data-id="${p.id}">
          <i class="fas fa-user" style="font-size:12px;color:var(--text-muted)"></i>
          <div>
            <div style="font-weight:700">${esc(p.full_name)}</div>
            <div style="font-size:10px;color:var(--text-muted);font-family:var(--font-mono)">${esc(p.pid)} · 🌐 ${esc(p.unique_lab_id)}</div>
          </div>
        </div>`).join('');
      drop.classList.add('open');
      drop.querySelectorAll('.nim-pd-item').forEach(el => {
        el.addEventListener('click', () => {
          const pat = DEMO_PATIENTS.find(p => p.id === parseInt(el.dataset.id));
          if (pat) selectPatient(pat);
        });
      });
    }, 200);
  });

  function selectPatient(pat) {
    newInvPatient = pat;
    $('nim-patient-search').value = pat.full_name;
    closeDrop('nim-patient-drop');
    const sel = $('nim-patient-selected');
    sel.style.display = 'flex';
    sel.innerHTML = `<i class="fas fa-check-circle" style="color:var(--alert-green)"></i> <span>${esc(pat.full_name)}</span> · <span style="font-family:var(--font-mono);color:var(--text-muted)">${esc(pat.pid)}</span> · <span style="color:var(--cyan)">🌐 ${esc(pat.unique_lab_id)}</span>`;
  }

  /* Test search */
  let tSearchTimer = null;
  $('nim-test-search')?.addEventListener('input', () => {
    clearTimeout(tSearchTimer);
    const q = $('nim-test-search').value.trim().toLowerCase();
    if (q.length < 2) { closeDrop('nim-test-drop'); return; }
    tSearchTimer = setTimeout(() => {
      const matches = TEST_CATALOG.filter(t => t.name.toLowerCase().includes(q) || t.code.toLowerCase().includes(q));
      const drop = $('nim-test-drop');
      drop.innerHTML = matches.map(t => `
        <div class="nim-td-item" data-id="${t.id}">
          <i class="fas fa-flask" style="font-size:11px;color:var(--text-muted)"></i>
          <div>
            <div style="font-weight:700">${esc(t.name)}</div>
            <div style="font-size:10px;color:var(--text-muted)">${esc(t.code)} · ${esc(t.dept)}</div>
          </div>
          <span class="nim-td-price">${t.price.toLocaleString()} RWF</span>
        </div>`).join('');
      drop.classList.add('open');
      drop.querySelectorAll('.nim-td-item').forEach(el => {
        el.addEventListener('click', () => {
          const test = TEST_CATALOG.find(t => t.id === parseInt(el.dataset.id));
          if (test && !newInvTests.find(t => t.id === test.id)) {
            newInvTests.push(test);
            $('nim-test-search').value = '';
            closeDrop('nim-test-drop');
            renderSelectedTests();
            renderConsumables();
            renderBillingSummary();
          }
        });
      });
      drop.classList.add('open');
    }, 200);
  });

  function renderSelectedTests() {
    const el = $('nim-selected-tests');
    el.innerHTML = newInvTests.map(t => `
      <div class="nim-test-chip">
        🧪 ${esc(t.name)}
        <span class="nim-test-chip-remove" onclick="removeTest(${t.id})">×</span>
      </div>`).join('');
  }

  window.removeTest = id => {
    newInvTests = newInvTests.filter(t => t.id !== id);
    renderSelectedTests();
    renderConsumables();
    renderBillingSummary();
  };

  function renderConsumables() {
    const sec = $('nim-consumables-section');
    const list = $('nim-consumables-list');
    if (!newInvTests.length) { sec.style.display = 'none'; return; }
    sec.style.display = 'block';
    const merged = {};
    newInvTests.forEach(test => {
      (test.consumables || []).forEach(c => {
        const key = c.name;
        if (!merged[key]) merged[key] = { ...c, qty: 0 };
        merged[key].qty += c.qty;
      });
    });
    list.innerHTML = Object.values(merged).map(c => `
      <div class="nim-consumable-row">
        <span class="ncr-name">${esc(c.name)}</span>
        <span class="ncr-qty">×${c.qty} ${esc(c.unit)}</span>
        <span class="ncr-cost">${(c.qty * c.unit_cost).toLocaleString()} RWF</span>
      </div>`).join('');
  }

  function renderBillingSummary() {
    const sec = $('nim-billing-summary');
    const rows = $('nim-bill-rows');
    if (!newInvTests.length) { sec.style.display = 'none'; return; }
    sec.style.display = 'block';

    let total = 0;
    rows.innerHTML = newInvTests.map(t => {
      total += t.price;
      return `<div class="nim-bill-row">
        <span class="nbr-name">🧪 ${esc(t.name)}</span>
        <span class="nbr-qty">×1</span>
        <span class="nbr-cost">${t.price.toLocaleString()} RWF</span>
      </div>`;
    }).join('');

    const disc = parseInt($('nim-discount')?.value || 0);
    const finalTotal = Math.round(total * (1 - disc / 100));
    $('ngt-val').textContent = `${finalTotal.toLocaleString()} RWF`;
  }

  $('nim-discount')?.addEventListener('input', renderBillingSummary);
  $('nim-payment-type')?.addEventListener('change', applyInsuranceRules);

  function applyInsuranceRules() {
    const type = $('nim-payment-type')?.value;
    const coverage = { rssb: 85, mutuelle: 80, insurance: 90, private: 0, free: 100 }[type] || 0;
    if (coverage > 0 && $('nim-discount')) {
      $('nim-discount').value = coverage;
      renderBillingSummary();
    }
  }

  $('new-inv-submit')?.addEventListener('click', () => createInvoice('pending'));
  $('new-inv-draft')?.addEventListener('click',  () => createInvoice('provisional'));

  function createInvoice(status) {
    if (!newInvPatient) { Toast.warning('Required', 'Please select a patient.'); return; }
    if (!newInvTests.length) { Toast.warning('Required', 'Please select at least one test.'); return; }

    const disc    = parseInt($('nim-discount')?.value || 0);
    const total   = newInvTests.reduce((s, t) => s + t.price, 0);
    const payType = $('nim-payment-type')?.value || 'private';
    const coverage= { rssb:85, mutuelle:80, insurance:90, private:0, free:100 }[payType] || 0;
    const insCov  = Math.round(total * coverage / 100);
    const patPays = Math.round((total - insCov) * (1 - Math.max(0, disc - coverage) / 100));

    const merged = {};
    newInvTests.forEach(t => (t.consumables||[]).forEach(c => {
      if (!merged[c.name]) merged[c.name] = { ...c, qty:0 };
      merged[c.name].qty += c.qty;
    }));

    const inv = {
      id:               invoices.length + 1,
      invoice_number:   `INV-${new Date().toISOString().slice(0,10).replace(/-/g,'')}-${String(invoices.length+1).padStart(3,'0')}`,
      patient_name:     newInvPatient.full_name,
      patient_pid:      newInvPatient.pid,
      patient_lid:      newInvPatient.unique_lab_id,
      tests:            newInvTests.map(t => t.name),
      consumables:      Object.keys(merged).length,
      consumable_data:  Object.values(merged),
      total_amount:     total,
      insurance_coverage: insCov,
      patient_amount:   patPays,
      status:           status,
      payment_type:     payType,
      created_by_role:  'receptionist',
      created_at:       new Date().toISOString(),
    };

    invoices.unshift(inv);
    $('new-inv-modal').style.display = 'none';
    Toast.success(status === 'provisional' ? '📝 Provisional Invoice Created' : '💳 Invoice Created', `${inv.invoice_number} — ${inv.patient_name} · ${patPays.toLocaleString()} RWF`);
    loadInvoices();
    if (status === 'provisional') Toast.info('🩸 Next Step', 'Send patient to phlebotomist for consumable validation.');
  }

  function closeDrop(id) { const el = $(id); if (el) { el.classList.remove('open'); el.innerHTML = ''; } }
  document.addEventListener('click', e => {
    if (!e.target.closest('#nim-patient-search') && !e.target.closest('#nim-patient-drop')) closeDrop('nim-patient-drop');
    if (!e.target.closest('#nim-test-search') && !e.target.closest('#nim-test-drop')) closeDrop('nim-test-drop');
  });

  /* ════════════════════════════════════════════════════════════
     PHLEBOTOMIST VALIDATION PANE
  ════════════════════════════════════════════════════════════ */
  function loadValidationQueue() {
    const list    = $('val-list');
    const pending = invoices.filter(i => i.status === 'provisional');
    $('badge-validation') && ($('badge-validation').textContent = pending.length);

    if (!pending.length) {
      if (list) list.innerHTML = '<div style="padding:var(--space-xl);text-align:center;color:var(--text-muted);font-size:var(--text-xs)">✅ No provisional invoices awaiting validation</div>';
      return;
    }
    list.innerHTML = pending.map(inv => `
      <div class="val-item" data-id="${inv.id}">
        <div class="val-item-info">
          <div class="val-item-name">${esc(inv.patient_name)}</div>
          <div class="val-item-inv">${esc(inv.invoice_number)}</div>
          <div class="val-item-tests">${(inv.tests||[]).join(', ')}</div>
        </div>
        <span class="badge badge-orange" style="font-size:9px">${(inv.consumable_data||[]).length || inv.consumables} consumables</span>
      </div>`).join('');
    list.querySelectorAll('.val-item').forEach(el =>
      el.addEventListener('click', () => {
        list.querySelectorAll('.val-item').forEach(e => e.classList.remove('active'));
        el.classList.add('active');
        const inv = invoices.find(i => i.id === parseInt(el.dataset.id));
        if (inv) openValidationItem(inv);
      })
    );
  }

  function openValidationItem(inv) {
    activeValItem = inv;
    $('val-empty').style.display = 'none';
    $('val-active').style.display = 'flex';
    $('val-active').style.flexDirection = 'column';
    $('val-patient-name').textContent = inv.patient_name;
    $('val-meta').textContent = `${inv.patient_pid} · 🌐 ${inv.patient_lid || '—'} · Tests: ${(inv.tests||[]).join(', ')}`;
    $('val-invoice-id').textContent = inv.invoice_number;

    const consumes = inv.consumable_data || TEST_CATALOG
      .filter(t => (inv.tests||[]).includes(t.name))
      .flatMap(t => t.consumables);

    const merged = {};
    consumes.forEach(c => { if (!merged[c.name]) merged[c.name] = {...c, qty:0}; merged[c.name].qty += c.qty; });
    const list = $('val-consumables-list');
    list.innerHTML = Object.values(merged).map((c, i) => `
      <div class="consumable-row" id="cr-${i}">
        <div class="cr-check checked" id="crchk-${i}"></div>
        <div>
          <div class="cr-name">${esc(c.name)}</div>
          <div class="cr-batch">Unit cost: ${c.unit_cost?.toLocaleString() || 0} RWF</div>
        </div>
        <div class="cr-qty">
          <input type="number" class="cr-qty-input" id="crq-${i}" value="${c.qty}" min="0" max="${c.qty*3}">
          <span class="cr-unit">${esc(c.unit)}</span>
        </div>
        <span class="cr-cost" id="crc-${i}">${(c.qty * (c.unit_cost||0)).toLocaleString()} RWF</span>
      </div>`).join('');

    // Wire checkboxes
    Object.values(merged).forEach((c, i) => {
      const chk = $(`crchk-${i}`);
      const qin = $(`crq-${i}`);
      const cst = $(`crc-${i}`);
      chk?.addEventListener('click', () => { chk.classList.toggle('checked'); });
      qin?.addEventListener('input', () => { if (cst) cst.textContent = (parseInt(qin.value||0) * (c.unit_cost||0)).toLocaleString() + ' RWF'; });
    });
  }

  $('val-confirm-btn')?.addEventListener('click', async () => {
    if (!activeValItem) return;
    const btn = $('val-confirm-btn');
    btn.classList.add('btn-loading');
    try {
      // Simulate: update invoice status, deduct inventory
      const idx = invoices.findIndex(i => i.id === activeValItem.id);
      if (idx >= 0) {
        invoices[idx] = { ...invoices[idx], status: 'pending', validated_by_role: 'phlebotomist', validated_at: new Date().toISOString() };
      }
      Toast.success('✅ Consumables Validated', `Invoice ${activeValItem.invoice_number} — Inventory deducted. Bill finalized. Patient can now pay.`);
      $('val-empty').style.display = 'flex';
      $('val-active').style.display = 'none';
      activeValItem = null;
      loadValidationQueue();
      loadInvoices();
    } catch (e) { Toast.error('Failed', e.message); }
    finally { btn.classList.remove('btn-loading'); }
  });

  $('val-reject-btn')?.addEventListener('click', () => {
    Toast.info('Returned', `Invoice returned to receptionist for review.`);
    $('val-empty').style.display = 'flex';
    $('val-active').style.display = 'none';
    activeValItem = null;
  });

  /* Barcode scan → find patient in validation queue */
  $('val-scan-input')?.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    const val = e.target.value.trim();
    if (!val) return;
    const inv = invoices.find(i => i.status === 'provisional' && (i.patient_pid?.includes(val) || i.invoice_number?.includes(val)));
    if (inv) { e.target.value = ''; openValidationItem(inv); Toast.success('Found', `Loaded ${inv.invoice_number}`); }
    else Toast.warning('Not found', `No provisional invoice for: ${val}`);
  });

  /* ════════════════════════════════════════════════════════════
     PAYMENTS PANE
  ════════════════════════════════════════════════════════════ */
  document.querySelectorAll('.pay-method-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.pay-method-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      payMethod = btn.dataset.method;
      $('pay-phone-row').style.display = ['mtn_momo','airtel_money'].includes(payMethod) ? 'block' : 'none';
    });
  });

  $('pay-submit-btn')?.addEventListener('click', async () => {
    const amount = parseFloat($('pay-amount')?.value);
    if (!amount || amount <= 0) { Toast.warning('Required', 'Enter a payment amount.'); return; }
    const btn = $('pay-submit-btn');
    btn.classList.add('btn-loading');
    await new Promise(r => setTimeout(r, 800));
    Toast.success('✅ Payment Recorded', `${amount.toLocaleString()} RWF via ${payMethod.replace('_',' ')} — Receipt generated.`);
    btn.classList.remove('btn-loading');
    $('pay-amount').value = '';
    loadPaymentLog();
  });

  function loadPaymentLog() {
    const tbody = $('pay-log-tbody');
    if (!tbody) return;
    tbody.innerHTML = DEMO_PAYMENTS.map(p => `<tr>
      <td style="font-family:var(--font-mono);font-size:11px">${p.time}</td>
      <td style="font-size:var(--text-xs)">${esc(p.patient)}</td>
      <td style="font-family:var(--font-mono);font-weight:700;color:#00d4aa">${p.amount} RWF</td>
      <td style="font-size:var(--text-xs)">${p.method}</td>
      <td><span class="inv-status inv-paid">✅ Paid</span></td>
    </tr>`).join('');
  }

  /* ════════════════════════════════════════════════════════════
     INSURANCE PANE
  ════════════════════════════════════════════════════════════ */
  function loadInsurance() {
    const insInvoices = invoices.filter(i => ['rssb','mutuelle','insurance'].includes(i.payment_type));
    $('ins-kpi-total')    && ($('ins-kpi-total').textContent    = insInvoices.length);
    $('ins-kpi-approved') && ($('ins-kpi-approved').textContent = insInvoices.filter(i => i.status === 'paid').length);
    $('ins-kpi-pending')  && ($('ins-kpi-pending').textContent  = insInvoices.filter(i => i.status === 'pending').length);
    $('ins-kpi-rejected') && ($('ins-kpi-rejected').textContent = 0);
    const claimed = insInvoices.reduce((s,i) => s+(i.insurance_coverage||0), 0);
    $('ins-kpi-amount')   && ($('ins-kpi-amount').textContent   = claimed.toLocaleString());
    const tbody = $('ins-tbody');
    if (!tbody) return;
    if (!insInvoices.length) { tbody.innerHTML = '<tr><td colspan="8"><div class="bill-loading">No insurance claims</div></td></tr>'; return; }
    tbody.innerHTML = insInvoices.map(inv => `<tr>
      <td><span style="font-family:var(--font-mono);font-size:11px;color:#00d4aa">${esc(inv.invoice_number)}</span></td>
      <td style="font-size:var(--text-xs)">${esc(inv.patient_name)}</td>
      <td><span class="badge badge-blue" style="font-size:9px">${esc(inv.payment_type?.toUpperCase())}</span></td>
      <td style="font-family:var(--font-mono)">${fmt.num(inv.total_amount)}</td>
      <td style="font-family:var(--font-mono);color:var(--alert-green)">${fmt.num(inv.insurance_coverage)}</td>
      <td><span class="inv-status ${inv.status === 'paid' ? 'inv-paid' : 'inv-pending'}">${inv.status === 'paid' ? '✅ Approved' : '⏳ Pending'}</span></td>
      <td style="font-size:10px;color:var(--text-muted)">${fmt.date(inv.created_at)}</td>
      <td><button class="btn btn-ghost btn-sm">📋 Claim</button></td>
    </tr>`).join('');
  }

  /* ════════════════════════════════════════════════════════════
     DAILY SUMMARY
  ════════════════════════════════════════════════════════════ */
  function loadSummary() {
    if (!window.Chart) return;
    // Revenue trend
    const rc = $('revenue-chart');
    if (rc && !rc._c) {
      rc._c = new Chart(rc, { type:'line', data:{ labels:['Mon','Tue','Wed','Thu','Fri','Sat','Sun'], datasets:[{ label:'Revenue (RWF)', data:[45000,62000,38000,71000,55000,48000,29000], borderColor:'#00d4aa', backgroundColor:'rgba(0,212,170,.1)', fill:true, tension:.4 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{display:false}}, scales:{ x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#8899aa'}}, y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#8899aa'}} } } });
    }
    // Payment methods
    const mc = $('method-chart');
    if (mc && !mc._c) {
      mc._c = new Chart(mc, { type:'doughnut', data:{ labels:['Cash','MTN MoMo','RSSB','Mutuelle','Bank'], datasets:[{ data:[45,22,18,12,3], backgroundColor:['#27AE60','#F39C12','#2980B9','#27AE60','#95A5A6'], borderWidth:0 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{color:'#8899aa',font:{size:9}}}} } });
    }
    // Insurance split
    const isc = $('ins-split-chart');
    if (isc && !isc._c) {
      isc._c = new Chart(isc, { type:'pie', data:{ labels:['Self-Pay','Insurance/RSSB','Mutuelle'], datasets:[{ data:[52,35,13], backgroundColor:['#0099FF','#00E676','#27AE60'], borderWidth:0 }] }, options:{ responsive:true, maintainAspectRatio:false, plugins:{legend:{labels:{color:'#8899aa',font:{size:9}}}} } });
    }
    // Shift summary
    const ss = $('shift-summary');
    if (ss) {
      const paid = invoices.filter(i => i.status === 'paid');
      const revenue = paid.reduce((s,i) => s+(i.patient_amount||0), 0);
      ss.innerHTML = [['Invoices Created', invoices.length],['Paid', paid.length],['Revenue', revenue.toLocaleString()+' RWF'],['Insurance Claimed', invoices.reduce((s,i)=>s+(i.insurance_coverage||0),0).toLocaleString()+' RWF']].map(([l,v]) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border-dim);font-size:var(--text-xs)"><span style="color:var(--text-muted)">${l}</span><strong>${v}</strong></div>`).join('');
    }
    // Top tests billed
    const ttb = $('top-tests-billed');
    if (ttb) {
      const counts = {};
      invoices.forEach(i => (i.tests||[]).forEach(t => { counts[t] = (counts[t]||0)+1; }));
      ttb.innerHTML = Object.entries(counts).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([t,c]) => `<div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--border-dim);font-size:var(--text-xs)"><span>${esc(t)}</span><strong style="font-family:var(--font-mono)">${c}</strong></div>`).join('');
    }
  }

  /* ── Init ─────────────────────────────────────────────────── */
  const p1 = $('pane-invoices');
  if (p1) { p1.style.display = 'flex'; p1.style.flexDirection = 'column'; }
  loadInvoices();
})();
