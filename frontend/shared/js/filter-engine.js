/**
 * JORINOVA NEXUS ALIS-X — Universal Filter Engine
 * =================================================
 * Client-side filtering for any data table.
 * Supports: text search, date range, status, department, flag, custom.
 *
 * Usage:
 *   NexusFilter.init('my-table', { columns: [...], onFilter: fn })
 *   NexusFilter.addFilterIcon(toolbarEl, 'my-table')
 *   NexusFilter.open('my-table')
 *   NexusFilter.reset('my-table')
 */
'use strict';

(function (root) {

  const _instances = {};   // tableId → FilterInstance

  /* ─── Default filter config ──────────────────────────────────── */
  const FILTER_PRESETS = {
    status: {
      label: 'Status',
      options: ['All', 'Pending', 'In Progress', 'Processing', 'Validated', 'Released',
                'Critical', 'STAT', 'Urgent', 'Routine', 'Rejected', 'Cancelled'],
    },
    department: {
      label: 'Department',
      options: ['All', 'Hematology', 'Biochemistry', 'Microbiology', 'Molecular',
                'Serology', 'Immunology', 'Blood Bank', 'Toxicology', 'Pathology',
                'Coagulation', 'Urinalysis'],
    },
    flag: {
      label: 'Flag',
      options: ['All', 'Normal (N)', 'High (H)', 'Low (L)', 'Critical High (HH)',
                'Critical Low (LL)', 'Positive (POS)', 'Negative (NEG)', 'Abnormal (A)'],
    },
    priority: {
      label: 'Priority',
      options: ['All', 'STAT', 'Urgent', 'Routine'],
    },
  };

  /* ─── Init ───────────────────────────────────────────────────── */
  function init(tableId, opts = {}) {
    const tbl = document.getElementById(tableId);
    if (!tbl) return;

    const instance = {
      tableId,
      tbl,
      active:    {},        // field → value
      dateFrom:  null,
      dateTo:    null,
      searchText:'',
      columns:   opts.columns || [],       // [{key, label, colIndex}]
      onFilter:  opts.onFilter || null,    // optional callback for server-side filter
      preset:    opts.preset || null,      // 'status' | 'department' | etc.
    };
    _instances[tableId] = instance;
    return instance;
  }

  /* ─── Add filter icon to toolbar ─────────────────────────────── */
  function addFilterIcon(toolbarEl, tableId, opts = {}) {
    const container = typeof toolbarEl === 'string'
      ? document.querySelector(toolbarEl)
      : toolbarEl;
    if (!container) return;

    const wrap = document.createElement('div');
    wrap.className = 'filter-icon-wrap';
    wrap.id = `filter-wrap-${tableId}`;
    wrap.innerHTML = `
      <button class="filter-icon-btn" id="filter-btn-${tableId}"
        title="Filter (F)" onclick="NexusFilter.open('${tableId}')">
        ⚙️ <span class="filter-label">Filter</span>
        <span class="filter-badge" id="filter-badge-${tableId}" style="display:none">0</span>
      </button>
      <button class="filter-reset-btn" id="filter-reset-${tableId}"
        title="Reset filters" style="display:none"
        onclick="NexusFilter.reset('${tableId}')">✕</button>`;
    container.appendChild(wrap);

    if (!_instances[tableId]) init(tableId, opts);
    return wrap;
  }

  /* ─── Filter panel (modal) ───────────────────────────────────── */
  function open(tableId) {
    const inst = _instances[tableId];
    if (!inst) { console.warn('[Filter] Table not initialised:', tableId); return; }

    let panel = document.getElementById(`filter-panel-${tableId}`);
    if (!panel) {
      panel = _buildPanel(tableId, inst);
    }
    panel.style.display = 'flex';
    panel.querySelector('.fp-search')?.focus();
  }

  function _buildPanel(tableId, inst) {
    const panel = document.createElement('div');
    panel.id = `filter-panel-${tableId}`;
    panel.className = 'filter-panel-overlay';
    panel.innerHTML = `
      <div class="filter-panel">
        <div class="fp-header">
          <span>⚙️ Filter Results</span>
          <button onclick="NexusFilter.close('${tableId}')">✕</button>
        </div>

        <div class="fp-section">
          <label class="fp-label">Search</label>
          <input type="text" class="fp-search" id="fp-search-${tableId}"
            placeholder="Type to filter any column…"
            oninput="NexusFilter._applySearch('${tableId}',this.value)">
        </div>

        <div class="fp-section">
          <label class="fp-label">Date Range</label>
          <div class="fp-date-row">
            <input type="date" id="fp-date-from-${tableId}" class="fp-date"
              onchange="NexusFilter._applyDates('${tableId}')">
            <span>to</span>
            <input type="date" id="fp-date-to-${tableId}" class="fp-date"
              onchange="NexusFilter._applyDates('${tableId}')">
          </div>
        </div>

        ${Object.entries(FILTER_PRESETS).map(([key, cfg]) => `
        <div class="fp-section">
          <label class="fp-label">${cfg.label}</label>
          <select class="fp-select" id="fp-${key}-${tableId}"
            onchange="NexusFilter._applyPreset('${tableId}','${key}',this.value)">
            ${cfg.options.map(o => `<option>${o}</option>`).join('')}
          </select>
        </div>`).join('')}

        ${inst.columns.length ? `
        <div class="fp-section">
          <label class="fp-label">Column Filters</label>
          ${inst.columns.map(col => `
          <div class="fp-col-row">
            <span class="fp-col-name">${col.label}</span>
            <input type="text" class="fp-col-input" placeholder="Filter ${col.label}…"
              oninput="NexusFilter._applyColumn('${tableId}','${col.key}',this.value,${col.colIndex})">
          </div>`).join('')}
        </div>` : ''}

        <div class="fp-footer">
          <button class="fp-btn-reset" onclick="NexusFilter.reset('${tableId}')">
            ✕ Reset All
          </button>
          <button class="fp-btn-apply" onclick="NexusFilter.close('${tableId}')">
            ✓ Apply & Close
          </button>
        </div>
      </div>`;

    document.body.appendChild(panel);
    panel.addEventListener('click', e => { if (e.target === panel) close(tableId); });
    return panel;
  }

  function close(tableId) {
    const panel = document.getElementById(`filter-panel-${tableId}`);
    if (panel) panel.style.display = 'none';
  }

  /* ─── Filter application ─────────────────────────────────────── */
  function _applySearch(tableId, text) {
    const inst = _instances[tableId];
    if (!inst) return;
    inst.searchText = text.toLowerCase().trim();
    _runFilter(tableId);
  }

  function _applyDates(tableId) {
    const inst = _instances[tableId];
    if (!inst) return;
    inst.dateFrom = document.getElementById(`fp-date-from-${tableId}`)?.value || null;
    inst.dateTo   = document.getElementById(`fp-date-to-${tableId}`)?.value   || null;
    _runFilter(tableId);
  }

  function _applyPreset(tableId, key, value) {
    const inst = _instances[tableId];
    if (!inst) return;
    if (value === 'All' || !value) {
      delete inst.active[key];
    } else {
      // Extract the abbreviation part if format is "Critical High (HH)"
      const match = value.match(/\(([^)]+)\)$/);
      inst.active[key] = match ? match[1] : value;
    }
    _runFilter(tableId);
  }

  function _applyColumn(tableId, key, value, colIndex) {
    const inst = _instances[tableId];
    if (!inst) return;
    if (!value) {
      delete inst.active[`col_${key}`];
    } else {
      inst.active[`col_${key}`] = { value: value.toLowerCase(), colIndex };
    }
    _runFilter(tableId);
  }

  function _runFilter(tableId) {
    const inst = _instances[tableId];
    if (!inst) return;
    const rows = Array.from(inst.tbl.querySelectorAll('tbody tr'));
    let visible = 0;

    rows.forEach(row => {
      const rowText = row.innerText.toLowerCase();
      let show = true;

      // Text search
      if (inst.searchText && !rowText.includes(inst.searchText)) {
        show = false;
      }

      // Date range (looks for date-formatted cells)
      if (show && (inst.dateFrom || inst.dateTo)) {
        const dateMatches = rowText.match(/\d{4}-\d{2}-\d{2}/g) || [];
        if (dateMatches.length) {
          const rowDate = dateMatches[0];
          if (inst.dateFrom && rowDate < inst.dateFrom) show = false;
          if (inst.dateTo   && rowDate > inst.dateTo)   show = false;
        }
      }

      // Preset filters (status, dept, flag, priority)
      if (show) {
        for (const [key, val] of Object.entries(inst.active)) {
          if (key.startsWith('col_')) {
            const { value, colIndex } = val;
            const cellText = row.cells[colIndex]?.innerText?.toLowerCase() || '';
            if (!cellText.includes(value)) { show = false; break; }
          } else {
            if (!rowText.includes(val.toLowerCase())) { show = false; break; }
          }
        }
      }

      row.style.display = show ? '' : 'none';
      if (show) visible++;
    });

    _updateBadge(tableId, inst);
    _showEmptyState(inst.tbl, rows.length, visible);

    // Server-side callback
    if (inst.onFilter) {
      inst.onFilter({
        search:   inst.searchText,
        dateFrom: inst.dateFrom,
        dateTo:   inst.dateTo,
        filters:  { ...inst.active },
        visible,
      });
    }
  }

  function _updateBadge(tableId, inst) {
    const count = Object.keys(inst.active).length
      + (inst.searchText ? 1 : 0)
      + ((inst.dateFrom || inst.dateTo) ? 1 : 0);

    const badge  = document.getElementById(`filter-badge-${tableId}`);
    const reset  = document.getElementById(`filter-reset-${tableId}`);
    const btnLbl = document.querySelector(`#filter-btn-${tableId} .filter-label`);

    if (badge) { badge.textContent = count; badge.style.display = count ? 'inline' : 'none'; }
    if (reset) reset.style.display = count ? 'inline-flex' : 'none';
    if (btnLbl) btnLbl.textContent = count ? `Filter (${count})` : 'Filter';

    // Highlight active state
    const btn = document.getElementById(`filter-btn-${tableId}`);
    btn?.classList.toggle('filter-active', count > 0);
  }

  function _showEmptyState(tbl, total, visible) {
    let empty = tbl.querySelector('.filter-empty-state');
    if (visible === 0 && total > 0) {
      if (!empty) {
        empty = document.createElement('tr');
        empty.className = 'filter-empty-state';
        const cols = tbl.querySelector('thead tr')?.children.length || 5;
        empty.innerHTML = `<td colspan="${cols}" class="empty-state">
          ⚙️ No results match the current filter.
          <button onclick="NexusFilter.reset('${tbl.id}')" style="margin-left:.5rem">Clear filters</button>
        </td>`;
        tbl.querySelector('tbody')?.appendChild(empty);
      }
    } else if (empty) {
      empty.remove();
    }
  }

  /* ─── Reset ──────────────────────────────────────────────────── */
  function reset(tableId) {
    const inst = _instances[tableId];
    if (!inst) return;
    inst.active     = {};
    inst.searchText = '';
    inst.dateFrom   = null;
    inst.dateTo     = null;

    // Reset UI controls
    const panel = document.getElementById(`filter-panel-${tableId}`);
    if (panel) {
      panel.querySelectorAll('input, select').forEach(el => {
        if (el.type === 'checkbox') el.checked = false;
        else el.value = el.tagName === 'SELECT' ? el.options[0].value : '';
      });
    }

    // Show all rows
    inst.tbl.querySelectorAll('tbody tr').forEach(r => r.style.display = '');
    _updateBadge(tableId, inst);
    const empty = inst.tbl.querySelector('.filter-empty-state');
    if (empty) empty.remove();
  }

  /* ─── CSS ─────────────────────────────────────────────────────── */
  function _injectStyles() {
    if (document.getElementById('filter-engine-styles')) return;
    const s = document.createElement('style');
    s.id = 'filter-engine-styles';
    s.textContent = `
      .filter-icon-wrap { display:inline-flex;align-items:center;gap:4px;position:relative; }
      .filter-icon-btn {
        display:flex;align-items:center;gap:.35rem;
        background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);
        border-radius:8px;padding:.35rem .75rem;color:#cbd5e1;
        cursor:pointer;font-size:.82rem;transition:.15s;
      }
      .filter-icon-btn:hover,
      .filter-icon-btn.filter-active { background:rgba(99,102,241,.2);border-color:#6366f1;color:#c7d2fe; }
      .filter-badge {
        background:#ef4444;color:#fff;border-radius:10px;
        padding:0 5px;font-size:.68rem;font-weight:700;
        display:inline;min-width:16px;text-align:center;
      }
      .filter-reset-btn {
        background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.3);
        color:#fca5a5;border-radius:8px;padding:.3rem .6rem;cursor:pointer;font-size:.78rem;
      }
      .filter-reset-btn:hover { background:rgba(239,68,68,.3); }

      /* Filter panel */
      .filter-panel-overlay {
        position:fixed;inset:0;background:rgba(0,0,0,.65);
        z-index:9500;display:none;align-items:flex-start;justify-content:flex-end;
        padding:1rem;backdrop-filter:blur(4px);
      }
      .filter-panel {
        background:var(--bg-elevated,#1e293b);border:1px solid rgba(99,102,241,.25);
        border-radius:16px;width:min(380px,90vw);max-height:90vh;overflow-y:auto;
        box-shadow:0 10px 40px rgba(0,0,0,.6);display:flex;flex-direction:column;gap:0;
      }
      .fp-header {
        display:flex;justify-content:space-between;align-items:center;
        padding:.85rem 1rem;border-bottom:1px solid rgba(255,255,255,.06);
        font-weight:600;font-size:.92rem;color:#e2e8f0;position:sticky;top:0;
        background:var(--bg-elevated,#1e293b);z-index:1;
      }
      .fp-header button { background:none;border:none;color:#64748b;cursor:pointer;font-size:1rem; }
      .fp-header button:hover { color:#e2e8f0; }
      .fp-section { padding:.75rem 1rem;border-bottom:1px solid rgba(255,255,255,.04); }
      .fp-label { display:block;font-size:.72rem;font-weight:600;letter-spacing:.06em;
                  text-transform:uppercase;color:#64748b;margin-bottom:.35rem; }
      .fp-search, .fp-date, .fp-select, .fp-col-input {
        width:100%;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
        border-radius:8px;padding:.4rem .65rem;color:#e2e8f0;font-size:.84rem;
      }
      .fp-search:focus, .fp-date:focus, .fp-select:focus, .fp-col-input:focus {
        outline:none;border-color:#6366f1;background:rgba(99,102,241,.1);
      }
      .fp-date-row { display:flex;gap:.5rem;align-items:center;color:#64748b;font-size:.82rem; }
      .fp-date { flex:1; }
      .fp-col-row { display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem; }
      .fp-col-name { font-size:.8rem;color:#94a3b8;width:90px;flex-shrink:0; }
      .fp-col-input { flex:1; }
      .fp-footer {
        display:flex;gap:.5rem;padding:.85rem 1rem;
        border-top:1px solid rgba(255,255,255,.06);position:sticky;bottom:0;
        background:var(--bg-elevated,#1e293b);
      }
      .fp-btn-reset {
        flex:1;background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.2);
        border-radius:8px;color:#fca5a5;cursor:pointer;padding:.4rem;font-size:.83rem;
      }
      .fp-btn-apply {
        flex:2;background:#6366f1;border:none;border-radius:8px;
        color:#fff;cursor:pointer;padding:.4rem;font-size:.83rem;font-weight:600;
      }
    `;
    document.head.appendChild(s);
  }

  document.addEventListener('DOMContentLoaded', _injectStyles);

  root.NexusFilter = {
    init, addFilterIcon, open, close, reset,
    _applySearch, _applyDates, _applyPreset, _applyColumn,
  };

})(window);
