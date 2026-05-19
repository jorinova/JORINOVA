/**
 * JORINOVA NEXUS ALIS-X — Offline Store (IndexedDB)
 * ===================================================
 * Persistent local storage for offline operation.
 * Stores: pending sync queue, cached API responses, draft lab results.
 *
 * Object stores:
 *   sync_queue     — operations pending server sync
 *   api_cache      — cached GET responses with TTL
 *   lab_drafts     — unsaved result/worklist drafts
 */
'use strict';

window.NexusStore = (() => {
  const DB_NAME    = 'nexus_alis_x';
  const DB_VERSION = 2;
  let   _db        = null;

  // ── Open ──────────────────────────────────────────────────────────────────

  function open() {
    if (_db) return Promise.resolve(_db);
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);

      req.onupgradeneeded = (e) => {
        const db = e.target.result;

        // Sync queue
        if (!db.objectStoreNames.contains('sync_queue')) {
          const sq = db.createObjectStore('sync_queue', { keyPath: 'id' });
          sq.createIndex('status',    'status',    { unique: false });
          sq.createIndex('timestamp', 'timestamp', { unique: false });
          sq.createIndex('endpoint',  'endpoint',  { unique: false });
        }

        // API cache (GET responses)
        if (!db.objectStoreNames.contains('api_cache')) {
          const ac = db.createObjectStore('api_cache', { keyPath: 'key' });
          ac.createIndex('expires_at', 'expires_at', { unique: false });
        }

        // Lab drafts (unsaved result forms)
        if (!db.objectStoreNames.contains('lab_drafts')) {
          const ld = db.createObjectStore('lab_drafts', { keyPath: 'id' });
          ld.createIndex('module',  'module',  { unique: false });
          ld.createIndex('saved_at','saved_at',{ unique: false });
        }
      };

      req.onsuccess = (e) => { _db = e.target.result; resolve(_db); };
      req.onerror   = (e) => reject(e.target.error);
    });
  }

  function _tx(store, mode, fn) {
    return open().then(db => new Promise((resolve, reject) => {
      const tx = db.transaction(store, mode);
      const os = tx.objectStore(store);
      const req = fn(os);
      if (req && req.onsuccess !== undefined) {
        req.onsuccess = () => resolve(req.result);
        req.onerror   = () => reject(req.error);
      } else {
        tx.oncomplete = () => resolve();
        tx.onerror    = () => reject(tx.error);
      }
    }));
  }

  // ── Sync Queue ─────────────────────────────────────────────────────────────

  const SyncQueue = {
    /** Add an operation to the queue. Returns queue entry id. */
    push(endpoint, method, payload, meta = {}) {
      const entry = {
        id:           crypto.randomUUID(),
        endpoint,
        method,      // GET (for retry) | POST | PATCH | PUT | DELETE
        payload,
        meta,
        status:       'pending',
        retries:      0,
        created_at:   Date.now(),
        timestamp:    Date.now(),
        synced_at:    null,
        error:        null,
      };
      return _tx('sync_queue', 'readwrite', os => os.put(entry))
             .then(() => entry.id);
    },

    /** Get all entries by status. */
    getByStatus(status = 'pending') {
      return open().then(db => new Promise((resolve, reject) => {
        const tx = db.transaction('sync_queue', 'readonly');
        const idx = tx.objectStore('sync_queue').index('status');
        const req = idx.getAll(status);
        req.onsuccess = () => resolve(req.result || []);
        req.onerror   = () => reject(req.error);
      }));
    },

    /** Get all pending + failed (retryable). */
    getPending() {
      return Promise.all([
        this.getByStatus('pending'),
        this.getByStatus('failed'),
      ]).then(([p, f]) =>
        [...p, ...f.filter(e => e.retries < 5)].sort((a,b) => a.timestamp - b.timestamp)
      );
    },

    /** Count pending operations. */
    count() {
      return this.getByStatus('pending').then(r => r.length);
    },

    /** Update entry status/fields. */
    update(id, fields) {
      return open().then(db => new Promise((resolve, reject) => {
        const tx = db.transaction('sync_queue', 'readwrite');
        const os = tx.objectStore('sync_queue');
        const req = os.get(id);
        req.onsuccess = () => {
          const entry = req.result;
          if (!entry) { resolve(); return; }
          const updated = { ...entry, ...fields };
          const put = os.put(updated);
          put.onsuccess = () => resolve();
          put.onerror   = () => reject(put.error);
        };
        req.onerror = () => reject(req.error);
      }));
    },

    /** Mark as synced (removes from queue). */
    markSynced(id) {
      return this.update(id, { status: 'synced', synced_at: Date.now() });
    },

    /** Mark as failed with error message. */
    markFailed(id, error, retries) {
      return this.update(id, { status: 'failed', error, retries });
    },

    /** Delete old synced entries (older than 24h). */
    cleanup() {
      const cutoff = Date.now() - 24 * 60 * 60 * 1000;
      return open().then(db => new Promise((resolve, reject) => {
        const tx  = db.transaction('sync_queue', 'readwrite');
        const os  = tx.objectStore('sync_queue');
        const idx = os.index('timestamp');
        const req = idx.openCursor(IDBKeyRange.upperBound(cutoff));
        req.onsuccess = (e) => {
          const cur = e.target.result;
          if (!cur) { resolve(); return; }
          if (cur.value.status === 'synced') cur.delete();
          cur.continue();
        };
        req.onerror = () => reject(req.error);
      }));
    },

    /** Clear ALL queue entries (danger — only on explicit user action). */
    clear() {
      return _tx('sync_queue', 'readwrite', os => os.clear());
    },
  };

  // ── API Cache ─────────────────────────────────────────────────────────────

  const ApiCache = {
    /** Cache a GET response. ttl = seconds. */
    set(key, data, ttlSeconds = 300) {
      const entry = {
        key,
        data,
        cached_at:  Date.now(),
        expires_at: Date.now() + ttlSeconds * 1000,
      };
      return _tx('api_cache', 'readwrite', os => os.put(entry));
    },

    /** Get cached entry if not expired. Returns null if missing/expired. */
    get(key) {
      return open().then(db => new Promise((resolve, reject) => {
        const req = db.transaction('api_cache', 'readonly')
                      .objectStore('api_cache').get(key);
        req.onsuccess = () => {
          const r = req.result;
          if (!r || Date.now() > r.expires_at) { resolve(null); return; }
          resolve(r.data);
        };
        req.onerror = () => reject(req.error);
      }));
    },

    /** Remove expired entries. */
    evictExpired() {
      const now = Date.now();
      return open().then(db => new Promise((resolve, reject) => {
        const tx  = db.transaction('api_cache', 'readwrite');
        const idx = tx.objectStore('api_cache').index('expires_at');
        const req = idx.openCursor(IDBKeyRange.upperBound(now));
        req.onsuccess = (e) => {
          const cur = e.target.result;
          if (!cur) { resolve(); return; }
          cur.delete();
          cur.continue();
        };
        req.onerror = () => reject(req.error);
      }));
    },
  };

  // ── Lab Drafts ─────────────────────────────────────────────────────────────

  const Drafts = {
    save(id, module, data) {
      return _tx('lab_drafts', 'readwrite', os => os.put({
        id, module, data, saved_at: Date.now(),
      }));
    },

    get(id) {
      return open().then(db => new Promise((resolve, reject) => {
        const req = db.transaction('lab_drafts', 'readonly')
                      .objectStore('lab_drafts').get(id);
        req.onsuccess = () => resolve(req.result?.data || null);
        req.onerror   = () => reject(req.error);
      }));
    },

    listByModule(module) {
      return open().then(db => new Promise((resolve, reject) => {
        const idx = db.transaction('lab_drafts', 'readonly')
                      .objectStore('lab_drafts').index('module');
        const req = idx.getAll(module);
        req.onsuccess = () => resolve(req.result || []);
        req.onerror   = () => reject(req.error);
      }));
    },

    delete(id) {
      return _tx('lab_drafts', 'readwrite', os => os.delete(id));
    },
  };

  return { open, SyncQueue, ApiCache, Drafts };
})();
