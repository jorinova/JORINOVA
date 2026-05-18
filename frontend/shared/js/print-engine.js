/**
 * JORINOVA NEXUS ALIS-X — Universal Print Engine
 * ================================================
 * Provides print capabilities to every module.
 * Supports: last result, first result, selected rows, all visible.
 * All printouts are auto-signed with NexusSig (PQC).
 *
 * Usage:
 *   NexusPrint.init(tableId, options)  — attach to a table
 *   NexusPrint.printLast(tableId)      — print last row
 *   NexusPrint.printFirst(tableId)     — print first row
 *   NexusPrint.printSelected(tableId)  — print checked rows
 *   NexusPrint.printAll(tableId)       — print all visible rows
 *   NexusPrint.addIcons(toolbarEl)     — inject print icon group into toolbar
 */
'use strict';

(function (root) {

  const _tables   = {};   // tableId → { el, cols, title, patientFn }
  const _selected = {};   // tableId → Set of row indices

  /* ─── Attach to a table ──────────────────────────────────────── */
  function init(tableId, opts = {}) {
    const el = document.getElementById(tableId);
    if (!el) return;
    _tables[tableId] = {
      el,
      title:     opts.title     || document.title,
      patientFn: opts.patientFn || null,   // fn() → {name, pid, lid, dob, sex}
      cols:      opts.cols      || [],     // optional explicit column names
    };
    _selected[tableId] = new Set();

    // Add checkboxes to each data row
    _addCheckboxes(tableId);

    // Watch for new rows (dynamic tables)
    const observer = new MutationObserver(() => _addCheckboxes(tableId));
    observer.observe(el, { childList: true, subtree: true });

    return _tables[tableId];
  }

  /* ─── Add print icon group to a toolbar element ─────────────── */
  function addIcons(toolbarSelector, tableId, opts = {}) {
    const toolbar = typeof toolbarSelector === 'string'
      ? document.querySelector(toolbarSelector)
      : toolbarSelector;
    if (!toolbar) return;

    const group = document.createElement('div');
    group.className = 'print-icon-group';
    group.setAttribute('title', 'Print options');
    group.innerHTML = `
      <div class="print-menu-wrap">
        <button class="print-icon-btn" id="print-trigger-${tableId}" title="Print (P)">
          🖨️ <span class="print-label">Print</span>
          <span class="print-arrow">▾</span>
        </button>
        <div class="print-dropdown" id="print-dropdown-${tableId}">
          <div class="pd-header">Print Options</div>
          <button class="pd-item" onclick="NexusPrint.printSelected('${tableId}')">
            <span>☑️</span> Print Selected Rows
            <span class="pd-hint">Mark rows with ✓ first</span>
          </button>
          <button class="pd-item" onclick="NexusPrint.printAll('${tableId}')">
            <span>📋</span> Print All Visible
            <span class="pd-hint">All rows currently shown</span>
          </button>
          <hr class="pd-divider">
          <button class="pd-item" onclick="NexusPrint.printFirst('${tableId}')">
            <span>⏫</span> Print First Result
            <span class="pd-hint">Top row of table</span>
          </button>
          <button class="pd-item" onclick="NexusPrint.printLast('${tableId}')">
            <span>⏬</span> Print Last Result
            <span class="pd-hint">Bottom row of table</span>
          </button>
          <hr class="pd-divider">
          <button class="pd-item" onclick="NexusPrint.printPage()">
            <span>🖥️</span> Print Full Page
            <span class="pd-hint">Current screen layout</span>
          </button>
        </div>
      </div>`;
    toolbar.appendChild(group);

    // Toggle dropdown
    const trigger  = document.getElementById(`print-trigger-${tableId}`);
    const dropdown = document.getElementById(`print-dropdown-${tableId}`);
    trigger?.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.classList.toggle('open');
    });
    document.addEventListener('click', () => dropdown?.classList.remove('open'));

    return group;
  }

  /* ─── Add selection checkboxes ───────────────────────────────── */
  function _addCheckboxes(tableId) {
    const tbl = _tables[tableId]?.el;
    if (!tbl) return;

    // Add header checkbox
    const thead = tbl.querySelector('thead tr');
    if (thead && !thead.querySelector('.print-check-th')) {
      const th = document.createElement('th');
      th.className = 'print-check-th';
      th.innerHTML = `<input type="checkbox" class="print-select-all"
        title="Select all" onchange="NexusPrint._toggleAll('${tableId}',this.checked)">`;
      thead.insertBefore(th, thead.firstChild);
    }

    // Add row checkboxes
    tbl.querySelectorAll('tbody tr').forEach((row, idx) => {
      if (row.querySelector('.print-check-td')) return;
      const td = document.createElement('td');
      td.className = 'print-check-td';
      td.innerHTML = `<input type="checkbox" class="row-select"
        onchange="NexusPrint._toggleRow('${tableId}',${idx},this.checked)">`;
      row.insertBefore(td, row.firstChild);
    });
  }

  function _toggleAll(tableId, checked) {
    const tbl = _tables[tableId]?.el;
    if (!tbl) return;
    _selected[tableId] = new Set();
    tbl.querySelectorAll('tbody tr').forEach((row, idx) => {
      const cb = row.querySelector('.row-select');
      if (cb) cb.checked = checked;
      if (checked) _selected[tableId].add(idx);
    });
    _updateSelectionBadge(tableId);
  }

  function _toggleRow(tableId, idx, checked) {
    const set = _selected[tableId] || new Set();
    checked ? set.add(idx) : set.delete(idx);
    _selected[tableId] = set;
    _updateSelectionBadge(tableId);
  }

  function _updateSelectionBadge(tableId) {
    const n   = _selected[tableId]?.size || 0;
    const lbl = document.querySelector(`#print-trigger-${tableId} .print-label`);
    if (lbl) lbl.textContent = n > 0 ? `Print (${n})` : 'Print';
  }

  /* ─── Row data extraction ─────────────────────────────────────── */
  function _getRows(tableId, mode) {
    const tbl = _tables[tableId]?.el;
    if (!tbl) return [];
    const rows = Array.from(tbl.querySelectorAll('tbody tr'))
      .filter(r => r.style.display !== 'none');

    switch (mode) {
      case 'first':    return rows.slice(0, 1);
      case 'last':     return rows.slice(-1);
      case 'selected': {
        const sel = _selected[tableId] || new Set();
        if (sel.size === 0) {
          _toast('No rows selected. Use checkboxes to select rows.', 'warn');
          return [];
        }
        return rows.filter((_, i) => sel.has(i));
      }
      case 'all':
      default:         return rows;
    }
  }

  function _rowToData(row) {
    return Array.from(row.querySelectorAll('td:not(.print-check-td)'))
      .map(td => td.innerText.trim());
  }

  function _getHeaders(tableId) {
    const tbl = _tables[tableId]?.el;
    if (!tbl) return [];
    return Array.from(tbl.querySelectorAll('thead th:not(.print-check-th)'))
      .map(th => th.innerText.trim());
  }

  /* ─── Print functions ─────────────────────────────────────────── */
  function printFirst(tableId)    { _doPrint(tableId, 'first'); }
  function printLast(tableId)     { _doPrint(tableId, 'last'); }
  function printSelected(tableId) { _doPrint(tableId, 'selected'); }
  function printAll(tableId)      { _doPrint(tableId, 'all'); }
  function printPage()            { window.print(); }

  function _doPrint(tableId, mode) {
    const rows = _getRows(tableId, mode);
    if (!rows.length) return;
    const headers  = _getHeaders(tableId);
    const data     = rows.map(_rowToData);
    const meta     = _tables[tableId];
    const patient  = meta?.patientFn?.() || {};
    _openPrintWindow(meta?.title || 'ALIS-X Report', headers, data, patient, mode);
  }

  function _openPrintWindow(title, headers, data, patient, mode) {
    const now     = new Date().toLocaleString();
    const modeMap = {
      first:'First Result', last:'Last Result',
      selected:'Selected Results', all:'All Results',
    };

    // PQC signature
    let sigBlock = '';
    try {
      const sig = root.NexusSig?.sign({
        docType:  title,
        entries:  data.length,
        printedBy: '',
      });
      if (sig) sigBlock = root.NexusSig.renderHTML(sig);
    } catch(_) {}

    const patientBlock = patient.name ? `
      <div class="pt-block">
        <div class="pt-row"><label>Patient</label><span>${patient.name}</span></div>
        ${patient.pid  ? `<div class="pt-row"><label>PID</label><span>${patient.pid}</span></div>` : ''}
        ${patient.lid  ? `<div class="pt-row"><label>LID</label><span>${patient.lid}</span></div>` : ''}
        ${patient.dob  ? `<div class="pt-row"><label>DOB</label><span>${patient.dob}</span></div>` : ''}
        ${patient.sex  ? `<div class="pt-row"><label>Sex</label><span>${patient.sex}</span></div>` : ''}
      </div>` : '';

    const headerCells = headers.map(h => `<th>${_esc(h)}</th>`).join('');
    const bodyRows    = data.map(row =>
      `<tr>${row.map(c => `<td>${_esc(c)}</td>`).join('')}</tr>`
    ).join('');

    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${_esc(title)}</title>
  <style>
    * { box-sizing:border-box; margin:0; padding:0; }
    body { font-family:Arial,sans-serif; font-size:11pt; color:#000; padding:12mm; }
    .header { display:flex; justify-content:space-between; align-items:flex-start;
              border-bottom:2px solid #000; padding-bottom:8px; margin-bottom:12px; }
    .brand  { font-size:16pt; font-weight:700; color:#0D1F3E; }
    .brand-sub { font-size:8pt; color:#555; }
    .doc-meta { text-align:right; font-size:8pt; color:#555; }
    .print-type { font-size:9pt; font-weight:600; color:#0D1F3E;
                  border:1px solid #0D1F3E; padding:2px 8px; border-radius:4px;
                  display:inline-block; margin-bottom:4px; }
    .pt-block { background:#f5f7fa; border:1px solid #ddd; border-radius:4px;
                padding:8px 12px; margin-bottom:12px; display:grid;
                grid-template-columns:1fr 1fr; gap:4px; }
    .pt-row   { display:flex; gap:8px; font-size:9pt; }
    .pt-row label { font-weight:600; width:60px; color:#555; }
    table { width:100%; border-collapse:collapse; font-size:9pt; margin-bottom:16px; }
    th { background:#0D1F3E; color:#fff; padding:5px 8px; text-align:left; }
    td { padding:4px 8px; border-bottom:1px solid #e0e0e0; }
    tr:nth-child(even) td { background:#f9f9f9; }
    .sig-block { border-top:1px solid #ccc; padding-top:8px; font-size:8pt; color:#555; }
    .footer { margin-top:20px; font-size:8pt; color:#888; text-align:center; border-top:1px solid #eee; padding-top:8px; }
    @media print {
      body { padding:0; }
      button { display:none; }
    }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="brand">JORINOVA NEXUS ALIS-X</div>
      <div class="brand-sub">Advanced Laboratory Information System</div>
    </div>
    <div class="doc-meta">
      <div class="print-type">${modeMap[mode] || 'Report'}</div>
      <div>${_esc(title)}</div>
      <div>Printed: ${now}</div>
    </div>
  </div>

  ${patientBlock}

  <table>
    <thead><tr>${headerCells}</tr></thead>
    <tbody>${bodyRows}</tbody>
  </table>

  <div class="sig-block">${sigBlock}</div>

  <div class="footer">
    JORINOVA NEXUS ALIS-X · ISO 15189 Compliant · PQC-Signed · ${now}
  </div>
  <script>window.onload=()=>setTimeout(()=>window.print(),250);<\/script>
</body>
</html>`;

    const win = window.open('', '_blank', 'width=900,height=700,scrollbars=yes');
    if (win) {
      win.document.write(html);
      win.document.close();
    } else {
      _toast('Pop-up blocked. Allow pop-ups for printing.', 'warn');
    }
  }

  /* ─── Quick print button (inject into any element) ───────────── */
  function quickPrintButton(containerSel, tableId, mode = 'all', label = '') {
    const container = typeof containerSel === 'string'
      ? document.querySelector(containerSel)
      : containerSel;
    if (!container) return;
    const btn = document.createElement('button');
    btn.className = 'btn btn-ghost btn-sm print-quick-btn';
    btn.title = `Print ${mode} results`;
    btn.innerHTML = `🖨️ ${label || mode}`;
    btn.onclick = () => _doPrint(tableId, mode);
    container.appendChild(btn);
    return btn;
  }

  /* ─── CSS injection ──────────────────────────────────────────── */
  function _injectStyles() {
    if (document.getElementById('print-engine-styles')) return;
    const s = document.createElement('style');
    s.id = 'print-engine-styles';
    s.textContent = `
      .print-icon-group { position:relative; display:inline-flex; }
      .print-icon-btn {
        display:flex;align-items:center;gap:.35rem;
        background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);
        border-radius:8px;padding:.35rem .75rem;color:#cbd5e1;
        cursor:pointer;font-size:.82rem;white-space:nowrap;
        transition:.15s;
      }
      .print-icon-btn:hover { background:rgba(99,102,241,.2);color:#c7d2fe;border-color:#6366f1; }
      .print-arrow { font-size:.65rem;opacity:.7; }
      .print-dropdown {
        position:absolute;top:calc(100% + 6px);right:0;min-width:220px;
        background:var(--bg-elevated,#1e293b);border:1px solid rgba(99,102,241,.25);
        border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.5);
        padding:4px;z-index:9999;
        opacity:0;pointer-events:none;transform:translateY(-6px);
        transition:opacity .15s,transform .15s;
      }
      .print-dropdown.open { opacity:1;pointer-events:all;transform:translateY(0); }
      .pd-header { font-size:.72rem;font-weight:700;letter-spacing:.08em;
                   color:var(--text-muted,#64748b);padding:6px 10px 4px;text-transform:uppercase; }
      .pd-item {
        display:flex;align-items:center;gap:.5rem;width:100%;
        background:none;border:none;border-radius:8px;
        padding:7px 10px;color:var(--text-secondary,#94a3b8);
        font-size:.82rem;cursor:pointer;text-align:left;
        transition:.12s;position:relative;
      }
      .pd-item:hover { background:rgba(99,102,241,.12);color:#e2e8f0; }
      .pd-hint { font-size:.7rem;color:var(--text-muted,#64748b);margin-left:auto; }
      .pd-divider { border:none;border-top:1px solid rgba(255,255,255,.06);margin:3px 8px; }
      .print-check-th, .print-check-td { width:36px;text-align:center; }
      .row-select, .print-select-all { width:15px;height:15px;cursor:pointer; }
      @media print {
        .print-icon-group, .print-check-th, .print-check-td,
        .no-print, nav, .sidebar, #tf-pill, #jv-panel { display:none !important; }
        table { page-break-inside:auto; }
        tr { page-break-inside:avoid; }
      }
    `;
    document.head.appendChild(s);
  }

  /* ─── Helpers ─────────────────────────────────────────────────── */
  function _esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function _toast(msg, type = 'info') {
    if (root.NexusCore?.toast) root.NexusCore.toast(msg, type);
    else console.warn('[Print]', msg);
  }

  /* ─── Init ───────────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', _injectStyles);

  root.NexusPrint = {
    init, addIcons,
    printFirst, printLast, printSelected, printAll, printPage,
    quickPrintButton,
    _toggleAll, _toggleRow,
  };

})(window);
