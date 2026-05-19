/**
 * JORINOVA NEXUS ALIS-X — Network Monitor
 * =========================================
 * Detects connection type (4G / 5G / Satellite / WiFi / Offline)
 * Measures real latency, throughput, and stability.
 * Emits events: nexus:online | nexus:offline | nexus:network-change
 *
 * Connection profiles:
 *   FIBER / 5G  → latency <30ms,  downlink ≥25 Mbps
 *   4G LTE      → latency <120ms, downlink ≥5 Mbps
 *   LEO SAT     → latency 20-80ms (Starlink), downlink ≥5 Mbps, type unknown
 *   GEO SAT     → latency 400-700ms, any speed
 *   3G / Edge   → latency >200ms, downlink <5 Mbps
 *   WiFi        → navigator.connection.type === 'wifi'
 *   Offline     → navigator.onLine === false OR ping fails
 */
'use strict';

window.NexusNetwork = (() => {

  // ── State ─────────────────────────────────────────────────────────────────
  let _state = {
    online:       navigator.onLine,
    type:         'unknown',   // 4g | 5g | leo_satellite | geo_satellite | wifi | 3g | offline
    label:        'Checking…',
    icon:         '📡',
    latency_ms:   null,
    downlink_mbps:null,
    quality:      'unknown',   // excellent | good | fair | poor | offline
    last_checked: null,
    ping_history: [],
    save_data:    false,
  };

  const PING_URL   = '/api/v1/health';      // tiny endpoint, no auth required
  const PING_MS    = 15_000;               // probe every 15s
  const HISTORY_N  = 6;                    // rolling window for jitter calc
  let   _pingTimer = null;
  let   _listeners = {};

  // ── Public API ─────────────────────────────────────────────────────────────

  function on(event, fn)  { (_listeners[event] = _listeners[event] || []).push(fn); }
  function off(event, fn) { _listeners[event] = (_listeners[event]||[]).filter(f => f !== fn); }
  function get()          { return { ..._state }; }
  function isOnline()     { return _state.online; }
  function isSatellite()  { return _state.type.includes('satellite'); }
  function is5G()         { return _state.type === '5g'; }
  function is4G()         { return _state.type === '4g'; }

  /** Recommended batch size for current connection (bytes). */
  function batchSizeBytes() {
    switch (_state.quality) {
      case 'excellent': return 1_000_000;   // 1 MB
      case 'good':      return 250_000;
      case 'fair':      return 64_000;
      case 'poor':      return 16_000;
      default:          return 8_000;
    }
  }

  /** Should we compress this payload before sending? */
  function shouldCompress() {
    return _state.type === 'geo_satellite' || _state.quality === 'poor' || _state.save_data;
  }

  /** Suggested request timeout for current connection. */
  function requestTimeout() {
    if (!_state.online)               return 5_000;
    if (_state.type === 'geo_satellite') return 30_000;
    if (_state.type === 'leo_satellite') return 15_000;
    if (_state.quality === 'poor')    return 20_000;
    return 10_000;
  }

  // ── Emit ──────────────────────────────────────────────────────────────────

  function _emit(event, data) {
    (_listeners[event] || []).forEach(fn => { try { fn(data); } catch(e){} });
    document.dispatchEvent(new CustomEvent(event, { detail: data }));
  }

  // ── Network Information API ───────────────────────────────────────────────

  function _readNavConnection() {
    const c = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (!c) return {};
    return {
      effective_type: c.effectiveType,   // 'slow-2g'|'2g'|'3g'|'4g'
      conn_type:      c.type,            // 'wifi'|'cellular'|'ethernet'|'none'|'unknown'
      rtt:            c.rtt,             // ms
      downlink:       c.downlink,        // Mbps
      save_data:      c.saveData || false,
    };
  }

  // ── Ping / latency measurement ─────────────────────────────────────────────

  async function _ping() {
    if (!navigator.onLine) return { latency: null, ok: false };
    const t0 = performance.now();
    try {
      const r = await fetch(PING_URL, {
        method: 'GET',
        cache:  'no-store',
        signal: AbortSignal.timeout(8_000),
      });
      const latency = Math.round(performance.now() - t0);
      return { latency, ok: r.ok };
    } catch {
      return { latency: null, ok: false };
    }
  }

  // ── Connection classification ──────────────────────────────────────────────

  function _classify(latency, nav) {
    if (!navigator.onLine || latency === null) {
      return { type: 'offline', label: 'Offline', icon: '🔴', quality: 'offline' };
    }

    const { effective_type, conn_type, rtt, downlink, save_data } = nav;

    // WiFi / Ethernet
    if (conn_type === 'wifi' || conn_type === 'ethernet') {
      if (latency < 30 && (downlink === undefined || downlink >= 25)) {
        return { type: '5g', label: 'WiFi 5G/Fiber', icon: '📶', quality: 'excellent' };
      }
      if (latency < 100) return { type: '4g', label: 'WiFi', icon: '📶', quality: 'good' };
      return { type: '3g', label: 'WiFi (slow)', icon: '📶', quality: 'fair' };
    }

    // GEO Satellite (classic Ku/Ka band — very high latency)
    if (latency >= 400) {
      return { type: 'geo_satellite', label: 'Satellite (GEO)', icon: '🛰️', quality: 'fair' };
    }

    // LEO Satellite (Starlink / OneWeb — low latency but inconsistent)
    // Heuristic: cellular unknown type + rtt 20-80ms + location context
    if ((conn_type === 'unknown' || conn_type === undefined) && latency >= 15 && latency <= 100) {
      return { type: 'leo_satellite', label: 'Satellite (LEO/Starlink)', icon: '🛰️', quality: 'good' };
    }

    // Cellular
    if (conn_type === 'cellular' || effective_type === '4g') {
      if (latency < 30 && downlink >= 50) {
        return { type: '5g', label: '5G', icon: '📱5G', quality: 'excellent' };
      }
      if (latency < 50 && downlink >= 10) {
        return { type: '5g', label: '5G', icon: '📱5G', quality: 'excellent' };
      }
      if (latency < 120) return { type: '4g', label: '4G LTE', icon: '📱4G', quality: 'good' };
      if (latency < 300) return { type: '3g', label: '3G',      icon: '📱3G', quality: 'fair' };
      return { type: '3g', label: 'Edge/2G', icon: '📱2G', quality: 'poor' };
    }

    // Fallback: use effective_type
    const etMap = {
      '4g':      { type: '4g',  label: '4G',    icon: '📡',  quality: 'good' },
      '3g':      { type: '3g',  label: '3G',    icon: '📡',  quality: 'fair' },
      '2g':      { type: '3g',  label: '2G',    icon: '📡',  quality: 'poor' },
      'slow-2g': { type: '3g',  label: 'Edge',  icon: '📡',  quality: 'poor' },
    };
    return etMap[effective_type] || { type: '4g', label: 'Connected', icon: '📡', quality: 'good' };
  }

  // ── Jitter (stability) calculation ────────────────────────────────────────

  function _jitter(history) {
    if (history.length < 2) return 0;
    const diffs = [];
    for (let i = 1; i < history.length; i++) {
      if (history[i] !== null && history[i-1] !== null)
        diffs.push(Math.abs(history[i] - history[i-1]));
    }
    return diffs.length ? Math.round(diffs.reduce((a, b) => a + b, 0) / diffs.length) : 0;
  }

  // ── Main probe ─────────────────────────────────────────────────────────────

  async function _probe() {
    const wasOnline   = _state.online;
    const wasType     = _state.type;
    const wasQuality  = _state.quality;

    const { latency, ok } = await _ping();
    const nav             = _readNavConnection();

    _state.ping_history.push(latency);
    if (_state.ping_history.length > HISTORY_N) _state.ping_history.shift();

    // Average latency over history (ignore nulls)
    const valid  = _state.ping_history.filter(v => v !== null);
    const avgLat = valid.length ? Math.round(valid.reduce((a,b) => a+b,0) / valid.length) : null;

    const classified = _classify(ok ? avgLat : null, nav);

    _state = {
      ..._state,
      online:       ok,
      latency_ms:   avgLat,
      downlink_mbps:nav.downlink || null,
      save_data:    nav.save_data || false,
      jitter_ms:    _jitter(_state.ping_history),
      last_checked: new Date().toISOString(),
      ...classified,
    };

    // Emit change events
    if (wasOnline && !_state.online) _emit('nexus:offline',  _state);
    if (!wasOnline && _state.online) _emit('nexus:online',   _state);
    if (wasType !== _state.type || wasQuality !== _state.quality)
      _emit('nexus:network-change', _state);

    _updateUI();
  }

  // ── UI indicator ──────────────────────────────────────────────────────────

  function _updateUI() {
    const bar  = document.getElementById('nexus-network-bar');
    const icon = document.getElementById('nn-icon');
    const lbl  = document.getElementById('nn-label');
    const lat  = document.getElementById('nn-latency');
    if (!bar) return;

    bar.className = `nexus-network-bar quality-${_state.quality}`;
    if (icon) icon.textContent  = _state.icon;
    if (lbl)  lbl.textContent   = _state.label;
    if (lat)  lat.textContent   = _state.latency_ms ? `${_state.latency_ms}ms` : '—';

    // Satellite warning badge
    const satWarn = document.getElementById('nn-satellite-warn');
    if (satWarn) {
      satWarn.style.display = isSatellite() ? 'inline' : 'none';
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  function init() {
    window.addEventListener('online',  () => _probe());
    window.addEventListener('offline', () => {
      _state.online  = false;
      _state.type    = 'offline';
      _state.quality = 'offline';
      _state.label   = 'Offline';
      _state.icon    = '🔴';
      _emit('nexus:offline', _state);
      _updateUI();
    });

    const c = navigator.connection || navigator.mozConnection;
    if (c) c.addEventListener('change', () => _probe());

    // First probe immediately, then on interval
    _probe();
    _pingTimer = setInterval(_probe, PING_MS);
  }

  return { on, off, get, isOnline, isSatellite, is5G, is4G,
           batchSizeBytes, shouldCompress, requestTimeout, init };
})();

// Auto-init when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => NexusNetwork.init());
} else {
  NexusNetwork.init();
}
