/**
 * JORINOVA NEXUS ALIS-X — Language Engine
 * =========================================
 * Client-side language management.
 * Loads language packs from the API, caches locally,
 * and provides localisation helpers to all modules.
 *
 * Usage:
 *   await LangEngine.init('en');
 *   LangEngine.t('welcome');              // UI string
 *   LangEngine.tts();                     // TTS config object
 *   LangEngine.setLang('fr');             // switch language
 *   LangEngine.detect(text);              // detect language of text
 */
'use strict';

(function (root) {

  const API = '/api/v1';
  const STORAGE_KEY = 'alis_lang';
  const CACHE_KEY   = 'alis_lang_packs';
  const CACHE_TTL   = 6 * 60 * 60 * 1000;   // 6 hours

  /* ─── Minimal built-in packs (offline fallback) ─────────────────── */
  const BUILTIN = {
    en: { code:'en', name:'English', flag:'🇬🇧', stt_lang:'en-US' },
    fr: { code:'fr', name:'Français', flag:'🇫🇷', stt_lang:'fr-FR' },
    rw: { code:'rw', name:'Ikinyarwanda', flag:'🇷🇼', stt_lang:'fr-FR' },
  };

  const Engine = {
    _current:   'en',
    _packs:     { ...BUILTIN },
    _available: [],
    _ready:     false,

    /* ── Init ─────────────────────────────────────────────────────── */
    async init(defaultLang) {
      // Restore saved language
      const saved = localStorage.getItem(STORAGE_KEY);
      this._current = saved || defaultLang || this._detectBrowser();

      // Load from cache first (offline-first)
      this._loadFromCache();

      // Fetch updated packs from API (non-blocking)
      this._fetchFromAPI().catch(e => console.debug('[LangEngine] API fetch skipped:', e));

      this._ready = true;
      this._applyToDOM();
      return this;
    },

    _detectBrowser() {
      const l = (navigator.language || 'en').split('-')[0].toLowerCase();
      return BUILTIN[l] ? l : 'en';
    },

    /* ── Language switching ───────────────────────────────────────── */
    setLang(code) {
      if (!this._packs[code] && !BUILTIN[code]) {
        console.warn('[LangEngine] Unknown language:', code);
        return;
      }
      this._current = code;
      localStorage.setItem(STORAGE_KEY, code);
      this._applyToDOM();
      this._dispatchChange(code);
    },

    get current() { return this._current; },
    get currentPack() { return this._packs[this._current] || BUILTIN[this._current] || {}; },

    /* ── String lookup ────────────────────────────────────────────── */
    t(key, fallback) {
      const pack = this.currentPack;
      const ui   = pack.ui || {};
      return ui[key] || BUILTIN.en?.ui?.[key] || fallback || key;
    },

    /* ── TTS config ───────────────────────────────────────────────── */
    tts(mode) {
      const pack = this.currentPack;
      const tts  = pack.tts || {};
      const rates = {
        normal:        tts.default_rate        || 0.88,
        slow:          tts.slow_rate           || 0.62,
        accessibility: tts.accessibility_rate  || 0.50,
        fast:          Math.min(1.2, (tts.default_rate || 0.88) * 1.25),
      };
      return {
        rate:           rates[mode || 'normal'] || 0.88,
        pitch:          tts.default_pitch       || 1.0,
        volume:         tts.default_volume      || 0.95,
        pauseMs:        mode === 'accessibility' ? (tts.accessibility_pause_ms || 700)
                                                 : (tts.pause_between_sentences_ms || 350),
        voicePrefs:     tts.voice_preference    || ['en-US'],
        lang:           this._current,
      };
    },

    /* ── STT language ─────────────────────────────────────────────── */
    sttLang() {
      return this.currentPack?.stt?.browser_lang
          || BUILTIN[this._current]?.stt_lang
          || 'en-US';
    },

    /* ── Wake phrases ─────────────────────────────────────────────── */
    wakePhrases() {
      const pack = this.currentPack;
      const en   = this._packs.en || BUILTIN.en;
      const phrases = new Set([
        ...(pack.wake_phrases || []),
        ...(en.wake_phrases   || ['hello jorinova', 'jorinova', 'nexus']),
      ]);
      return Array.from(phrases);
    },

    /* ── Available languages ──────────────────────────────────────── */
    available() {
      return this._available.length ? this._available
           : Object.entries(BUILTIN).map(([code, p]) => ({
               code, name: p.name, flag: p.flag || '🌐',
             }));
    },

    /* ── DOM application ──────────────────────────────────────────── */
    _applyToDOM() {
      document.documentElement.lang = this._current;
      document.documentElement.dir  = this.currentPack?.rtl ? 'rtl' : 'ltr';

      // Update any [data-i18n] elements
      document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.dataset.i18n;
        const val = this.t(key);
        if (val && val !== key) el.textContent = val;
      });

      // Update page title if [data-i18n-title]
      const titleKey = document.documentElement.dataset.i18nTitle;
      if (titleKey) {
        const translated = this.t(titleKey);
        if (translated && translated !== titleKey) document.title = translated;
      }
    },

    /* ── API fetch ────────────────────────────────────────────────── */
    async _fetchFromAPI() {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      const r = await fetch(`${API}/voice/languages`, {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (!r.ok) return;
      const data = await r.json();

      // Update available list
      if (data.languages) {
        this._available = data.languages;
      }

      // Fetch individual pack configs
      for (const lang of (data.languages || [])) {
        try {
          const r2 = await fetch(`${API}/voice/languages/${lang.code}/tts`, {
            headers: { Authorization: 'Bearer ' + token },
          });
          if (r2.ok) {
            const tts = await r2.json();
            this._packs[lang.code] = { ...BUILTIN[lang.code], ...lang, tts };
          }
        } catch(_) {}
      }

      // Cache to localStorage
      this._saveToCache();
    },

    /* ── Cache ────────────────────────────────────────────────────── */
    _saveToCache() {
      try {
        localStorage.setItem(CACHE_KEY, JSON.stringify({
          ts:    Date.now(),
          packs: this._packs,
          avail: this._available,
        }));
      } catch(_) {}
    },

    _loadFromCache() {
      try {
        const raw = localStorage.getItem(CACHE_KEY);
        if (!raw) return;
        const { ts, packs, avail } = JSON.parse(raw);
        if (Date.now() - ts < CACHE_TTL) {
          this._packs     = { ...BUILTIN, ...packs };
          this._available = avail || [];
        }
      } catch(_) {}
    },

    /* ── Event ────────────────────────────────────────────────────── */
    _dispatchChange(code) {
      window.dispatchEvent(new CustomEvent('alis-lang-change', { detail: { code } }));
      // Sync voice engine if loaded
      if (root.JorinovaVoice?.setLanguage) {
        root.JorinovaVoice.setLanguage(code);
      }
    },

    /* ── Text language detection (heuristic, client-side) ─────────── */
    detect(text) {
      if (!text) return 'en';
      const lower = text.toLowerCase();

      // Kinyarwanda heuristics
      const rw_words = ['nkumva', 'yego', 'oya', 'murakoze', 'amakuru', 'muraho', 'ubuvuzi', 'inzuki'];
      if (rw_words.some(w => lower.includes(w))) return 'rw';

      // French heuristics
      const fr_words = ['bonjour', 'merci', 'valider', 'résultat', 'patient', "j'ai", "s'il", 'je'];
      if (fr_words.some(w => lower.includes(w))) return 'fr';

      return 'en';
    },
  };

  /* ─── Language switcher widget ───────────────────────────────────── */
  function renderSwitcher(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const render = () => {
      container.innerHTML = Engine.available().map(l =>
        `<button class="lang-pill${l.code===Engine.current?' active':''}"
          data-code="${l.code}" title="${l.name}">
          ${l.flag || '🌐'} ${l.name}
        </button>`
      ).join('');
      container.querySelectorAll('.lang-pill').forEach(btn => {
        btn.addEventListener('click', () => {
          Engine.setLang(btn.dataset.code);
          render();
        });
      });
    };
    render();
    window.addEventListener('alis-lang-change', render);
  }

  /* ─── Exports ────────────────────────────────────────────────────── */
  root.LangEngine = Engine;
  root.renderLangSwitcher = renderSwitcher;

})(window);
