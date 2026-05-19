/**
 * JORINOVA NEXUS ALIS-X — Sync Manager
 * ======================================
 * Orchestrates online/offline data flow.
 *
 * Key behaviours:
 *  - All writes intercepted and queued in IndexedDB first
 *  - Background sync when online (every 30s or on reconnect)
 *  - Satellite mode: batches operations to reduce round-trips
 *  - Conflict detection: server timestamp wins for validated results
 *  - Visual sync badge in nav showing pending count
 *  - Retry with exponential back-off (max 5 attempts)
 */
'use strict';

window.NexusSync = (() => {

  const API_BASE      = '/api/v1';
  const SYNC_ENDPOINT = `${API_BASE}/sync/batch`;
  const SYNC_INTERVAL = 30_000;   // 30s when online
  const SAT_INTERVAL  = 60_000;   // 60s on satellite (batch more)
  const MAX_BATCH     = 50;       // operations per sync call
  const MAX_RETRIES   = 5;

  let _syncTimer  = null;
  let _syncing    = false;
  let _pendingCnt = 0;

  // ── Auth token helper ─────────────────────────────────────────────────────

  function _token() {
    return window.NEXUS?.token
        || localStorage.getItem('alis_token')
        || sessionStorage.getItem('alis_token')
        || '';
  }

  function _headers(extra = {}) {
    const h = { 'Content-Type': 'application/json' };
    const tok = _token();
    if (tok) h['Authorization'] = `Bearer ${tok}`;
    return { ...h, ...extra };
  }

  // ── Intercepted fetch ─────────────────────────────────────────────────────
  // Wraps fetch so that write operations are queued offline.

  async function apiFetch(endpoint, options = {}) {
    const method  = (options.method || 'GET').toUpperCase();
    const isWrite = ['POST', 'PATCH', 'PUT', 'DELETE'].includes(method);
    const timeout = NexusNetwork.requestTimeout();

    // For GET requests: try network, fall back to cache
    if (method === 'GET') {
      if (NexusNetwork.isOnline()) {
        try {
          const ctl = new AbortController();
          const tid = setTimeout(() => ctl.abort(), timeout);
          const res = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: _headers(options.headers || {}),
            signal:  ctl.signal,
          });
          clearTimeout(tid);
          if (res.ok) {
            const data = await res.json();
            // Cache successful GETs
            const ttl = NexusNetwork.isSatellite() ? 600 : 120;
            await NexusStore.ApiCache.set(endpoint, data, ttl);
            return { ok: true, data, source: 'network' };
          }
          return { ok: false, status: res.status, data: null, source: 'network' };
        } catch (err) {
          if (err.name === 'AbortError') {
            console.warn('[NexusSync] GET timeout:', endpoint);
          }
        }
      }
      // Offline or network failed → return cached data
      const cached = await NexusStore.ApiCache.get(endpoint);
      return { ok: !!cached, data: cached, source: 'cache', offline: true };
    }

    // For write operations: try direct POST, queue if offline
    if (isWrite) {
      if (NexusNetwork.isOnline()) {
        try {
          const ctl = new AbortController();
          const tid = setTimeout(() => ctl.abort(), timeout);
          const res = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: _headers(options.headers || {}),
            signal:  ctl.signal,
          });
          clearTimeout(tid);
          if (res.ok) {
            const data = res.status === 204 ? {} : await res.json();
            return { ok: true, data, source: 'network', queued: false };
          }
          // Server error (4xx/5xx) — don't queue, return error
          const err = await res.json().catch(() => ({}));
          return { ok: false, status: res.status, data: err, source: 'network', queued: false };
        } catch (netErr) {
          // Network failure → queue for later
        }
      }
      // Queue the write
      const payload = options.body ? JSON.parse(options.body) : null;
      const queueId = await NexusStore.SyncQueue.push(endpoint, method, payload);
      await _updateBadge();
      return { ok: false, data: null, source: 'queue', queued: true, queue_id: queueId };
    }

    return { ok: false, data: null, source: 'unknown' };
  }

  // ── Sync execution ─────────────────────────────────────────────────────────

  async function sync(force = false) {
    if (_syncing && !force) return { synced: 0, failed: 0 };
    if (!NexusNetwork.isOnline()) return { synced: 0, failed: 0, offline: true };

    const pending = await NexusStore.SyncQueue.getPending();
    if (!pending.length) { await _updateBadge(); return { synced: 0, failed: 0 }; }

    _syncing = true;
    _setSyncIndicator(true);
    let totalSynced = 0, totalFailed = 0;

    // Process in batches (smaller on satellite to reduce payload drops)
    const batchSize = NexusNetwork.isSatellite() ? 10 : MAX_BATCH;
    const batches   = _chunk(pending, batchSize);

    for (const batch of batches) {
      if (!NexusNetwork.isOnline()) break;   // went offline mid-sync

      // Mark batch as 'syncing'
      await Promise.all(batch.map(e => NexusStore.SyncQueue.update(e.id, { status: 'syncing' })));

      try {
        const payload = {
          device_id: _deviceId(),
          client_time: new Date().toISOString(),
          operations: batch.map(e => ({
            queue_id:   e.id,
            endpoint:   e.endpoint,
            method:     e.method,
            payload:    e.payload,
            created_at: new Date(e.created_at).toISOString(),
          })),
        };

        const res = await fetch(SYNC_ENDPOINT, {
          method:  'POST',
          headers: _headers(),
          body:    JSON.stringify(payload),
          signal:  AbortSignal.timeout(NexusNetwork.requestTimeout()),
        });

        if (!res.ok) throw new Error(`Sync HTTP ${res.status}`);
        const result = await res.json();

        // Process results
        for (const op of (result.synced || [])) {
          await NexusStore.SyncQueue.markSynced(op.queue_id);
          totalSynced++;
        }
        for (const op of (result.conflicts || [])) {
          await NexusStore.SyncQueue.update(op.queue_id, {
            status: 'conflict', error: op.reason,
          });
        }
        for (const op of (result.failed || [])) {
          const entry = batch.find(e => e.id === op.queue_id);
          const retries = (entry?.retries || 0) + 1;
          if (retries >= MAX_RETRIES) {
            await NexusStore.SyncQueue.update(op.queue_id, {
              status: 'abandoned', error: op.error, retries,
            });
          } else {
            await NexusStore.SyncQueue.markFailed(op.queue_id, op.error, retries);
          }
          totalFailed++;
        }

      } catch (err) {
        // Network failure during sync — revert to pending
        await Promise.all(batch.map(e =>
          NexusStore.SyncQueue.update(e.id, { status: 'pending' })
        ));
        console.warn('[NexusSync] Batch sync failed:', err.message);
        break;
      }
    }

    // Cleanup old synced entries
    await NexusStore.SyncQueue.cleanup();
    await _updateBadge();
    _syncing = false;
    _setSyncIndicator(false);

    if (totalSynced > 0) {
      _showToast(`✅ ${totalSynced} record${totalSynced>1?'s':''} synced to server`);
      document.dispatchEvent(new CustomEvent('nexus:sync-complete', {
        detail: { synced: totalSynced, failed: totalFailed }
      }));
    }

    return { synced: totalSynced, failed: totalFailed };
  }

  // ── Auto-sync scheduling ───────────────────────────────────────────────────

  function _scheduleSync() {
    if (_syncTimer) clearInterval(_syncTimer);
    const interval = NexusNetwork.isSatellite() ? SAT_INTERVAL : SYNC_INTERVAL;
    _syncTimer = setInterval(() => sync(), interval);
  }

  // ── UI helpers ─────────────────────────────────────────────────────────────

  async function _updateBadge() {
    const pending = await NexusStore.SyncQueue.getPending();
    _pendingCnt = pending.length;
    const badge = document.getElementById('sync-badge');
    if (!badge) return;
    badge.textContent  = _pendingCnt;
    badge.style.display = _pendingCnt > 0 ? 'inline-flex' : 'none';
    badge.title = `${_pendingCnt} operation${_pendingCnt!==1?'s':''} pending sync`;
  }

  function _setSyncIndicator(active) {
    const icon = document.getElementById('sync-spin-icon');
    if (icon) icon.className = active ? 'sync-spin active' : 'sync-spin';
  }

  function _showToast(msg) {
    if (window.NEXUS?.Toast?.show) { window.NEXUS.Toast.show(msg, 'success'); return; }
    const t = document.createElement('div');
    t.style.cssText = 'position:fixed;bottom:4.5rem;right:1.5rem;background:#0D1F3E;color:#fff;'
      + 'padding:.6rem 1rem;border-radius:8px;z-index:9999;font-size:.83rem;max-width:280px;';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4000);
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  function _chunk(arr, size) {
    const out = [];
    for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
    return out;
  }

  function _deviceId() {
    let id = localStorage.getItem('nexus_device_id');
    if (!id) {
      id = 'dev_' + crypto.randomUUID().replace(/-/g,'').slice(0,16);
      localStorage.setItem('nexus_device_id', id);
    }
    return id;
  }

  // ── Init ───────────────────────────────────────────────────────────────────

  function init() {
    // Sync on reconnect
    document.addEventListener('nexus:online', () => {
      _showToast('🌐 Back online — syncing data…');
      setTimeout(() => sync(), 1000);  // small delay to let connection stabilise
      _scheduleSync();
    });

    // Clear timer when offline
    document.addEventListener('nexus:offline', () => {
      if (_syncTimer) clearInterval(_syncTimer);
      _updateBadge();
    });

    // Re-schedule when network changes (satellite ↔ 4G)
    document.addEventListener('nexus:network-change', () => _scheduleSync());

    // Initial sync if online
    NexusStore.open().then(() => {
      _updateBadge();
      if (NexusNetwork.isOnline()) {
        sync();
        _scheduleSync();
      }
      // Evict expired cache entries periodically
      setInterval(() => NexusStore.ApiCache.evictExpired(), 5 * 60 * 1000);
    });
  }

  return { init, sync, apiFetch, pendingCount: () => _pendingCnt };
})();

// Auto-init
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => NexusSync.init());
} else {
  NexusSync.init();
}
