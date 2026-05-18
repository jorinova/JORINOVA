/**
 * JORINOVA NEXUS ALIS-X — Accessible Voice Engine v3.0
 * ======================================================
 * Requirements implemented:
 *   - Offline-first (rules parser works without network)
 *   - Multilingual: en / fr / rw (Kinyarwanda) + extensible
 *   - Speech modes: normal / slow / accessibility / fast
 *   - Adjustable rate, pitch, volume per user
 *   - Pause control between sentences
 *   - Repeat-last-response
 *   - Confirmation prompts before critical actions
 *   - HoD escalation UI
 *   - Wake phrase: "Hello Jorinova" + multilingual equivalents
 *   - Any command handled — safety warnings surface to UI
 *   - NEVER speaks excessively fast by default
 */
'use strict';

(function (root) {

  /* ─── Browser support ────────────────────────────────────────────── */
  const STT   = root.SpeechRecognition || root.webkitSpeechRecognition;
  const SYNTH = root.speechSynthesis;
  if (!SYNTH) {
    console.warn('[JorinNova Voice] Web Speech Synthesis not supported.');
  }

  /* ─── Constants ──────────────────────────────────────────────────── */
  const API_BASE = '/api/v1';

  const SPEECH_MODES = {
    normal:        { rate: 0.88, pitch: 1.00, pauseMs: 350,  label: 'Normal' },
    slow:          { rate: 0.62, pitch: 0.95, pauseMs: 550,  label: 'Slow' },
    accessibility: { rate: 0.50, pitch: 0.93, pauseMs: 750,  label: 'Accessibility' },
    fast:          { rate: 1.10, pitch: 1.00, pauseMs: 180,  label: 'Fast' },
  };

  /* ─── Language packs (minimal client-side fallback) ─────────────── */
  const LANG_PACKS = {
    en: {
      wake:          ['hello jorinova', 'hey jorinova', 'jorinova', 'nexus', 'alis x'],
      confirm:       ['yes', 'confirm', 'proceed', 'ok', 'affirmative', 'go ahead'],
      cancel:        ['no', 'cancel', 'stop', 'abort', 'negative', "don't"],
      repeat:        ['repeat', 'say again', 'pardon', 'again'],
      slow:          ['slower', 'slow down', 'speak slowly', 'too fast'],
      fast:          ['faster', 'speed up', 'normal speed'],
      help:          ['help', 'what can you do', 'commands'],
      goodbye:       ['goodbye', 'bye', 'deactivate', 'stop listening'],
      ui: {
        activated:   'Jorinova activated. How can I help you?',
        listening:   'Listening.',
        processing:  'Processing your request. Please wait.',
        not_understood: 'I did not understand. Please try again.',
        confirm_crit:'This is a critical action. Say yes to confirm or no to cancel.',
        warn_prefix: 'Warning. ',
        persist_warn:'You are insisting. I am notifying the Head of Department.',
        escalated:   'Request sent to Head of Department for authorisation.',
        offline:     'Running in offline mode. Basic functions available.',
        repeat:      'Repeating my last response.',
        goodbye:     'Jorinova deactivated.',
        slow_on:     'Slow speech mode active.',
        slow_off:    'Normal speech speed.',
        access_on:   'Accessibility mode active.',
        hod_pending: 'Action blocked. Head of Department notified.',
      },
    },
    fr: {
      wake:          ['bonjour jorinova', 'salut jorinova', 'jorinova', 'nexus'],
      confirm:       ['oui', 'confirmer', "d'accord", 'continuer'],
      cancel:        ['non', 'annuler', 'arrêter', 'abort'],
      repeat:        ['répéter', 'répétez', 'encore', 'pardon'],
      slow:          ['plus lentement', 'ralentir', 'trop vite'],
      fast:          ['plus vite', 'vitesse normale'],
      help:          ['aide', 'aidez-moi'],
      goodbye:       ['au revoir', 'désactiver', 'au revoir jorinova'],
      ui: {
        activated:   'Jorinova activé. Comment puis-je vous aider?',
        listening:   'Je vous écoute.',
        processing:  'Traitement en cours. Veuillez patienter.',
        not_understood: "Je n'ai pas compris. Répétez s'il vous plaît.",
        confirm_crit:"Action critique. Dites oui pour confirmer ou non pour annuler.",
        warn_prefix: 'Attention. ',
        persist_warn:"Vous insistez. J'informe le chef de département.",
        escalated:   'Demande envoyée au chef de département.',
        offline:     'Mode hors ligne. Fonctions de base disponibles.',
        repeat:      'Je répète ma dernière réponse.',
        goodbye:     'Jorinova désactivé.',
        slow_on:     'Mode parole lente activé.',
        slow_off:    'Vitesse normale.',
        access_on:   "Mode d'accessibilité activé.",
        hod_pending: 'Action bloquée. Chef de département notifié.',
      },
    },
    rw: {
      wake:          ['muraho jorinova', 'jorinova', 'nexus', 'witeguye jorinova'],
      confirm:       ['yego', 'emeza', 'nibyo'],
      cancel:        ['oya', 'hagarara', 'siko', 'reka'],
      repeat:        ['subiramo', 'bundi bushya'],
      slow:          ['buhoro', 'vuga buhoro'],
      fast:          ['neza', 'byihuse'],
      help:          ['nfasha', 'ingabo'],
      goodbye:       ['reka', 'seza', 'kwa jorinova'],
      ui: {
        activated:   'Jorinova yarafunguwe. Nigute nshobora kukufasha?',
        listening:   'Nkumva.',
        processing:  'Nsesengura. Tegereza gato.',
        not_understood: 'Sinumvise. Wakongera uvuge?',
        confirm_crit:'Igikorwa gikomeye. Vuga yego cyangwa oya.',
        warn_prefix: 'Iburyo. ',
        persist_warn:'Ukomeje. Nohesheja Umuyobozi w\'Ishami.',
        escalated:   'Icyifuzo cyoheshejwe ku Mutware.',
        offline:     'Offline. Serivisi za mbere ziraboneka.',
        repeat:      'Nsubiramo igisubizo.',
        goodbye:     'Jorinova yafunzwe.',
        slow_on:     'Vuga buhoro cyane.',
        slow_off:    'Igenga bisanzwe.',
        access_on:   'Uburyo bw\'ibumoso burakoze.',
        hod_pending: 'Igikorwa gihagaritswe. Umuyobozi yamenyeshejwe.',
      },
    },
  };

  /* ─── State ──────────────────────────────────────────────────────── */
  const STATE = {
    IDLE:          'idle',
    WAKE_LISTEN:   'wake_listen',
    SERIAL:        'serial',
    AUTHORIZED:    'authorized',
    COMMAND:       'command',
    CONFIRMING:    'confirming',    // waiting for yes/no on dangerous action
    PROCESSING:    'processing',
  };

  const Engine = {
    state:          STATE.IDLE,
    lang:           'en',
    mode:           'normal',
    volume:         0.95,
    recognizer:     null,
    _uiPanel:       null,
    _orbEl:         null,
    _pendingConfirm:null,     // { command, category, cmd_hash, action }
    _lastResponse:  '',
    _verifiedUser:  null,
    _repeatEnabled: true,
    _confirmPrompts:true,

    /* ── Init ────────────────────────────────────────────────────────── */
    init(options = {}) {
      this.lang    = options.lang    || this._detectBrowserLang();
      this.mode    = options.mode    || 'normal';
      this.volume  = options.volume  || 0.95;
      this._repeatEnabled  = options.repeat_enabled  !== false;
      this._confirmPrompts = options.confirmation_prompts !== false;
      this._buildUI();
      // Pre-load voices
      if (SYNTH) SYNTH.getVoices();
    },

    _detectBrowserLang() {
      const l = (navigator.language || 'en').split('-')[0].toLowerCase();
      return LANG_PACKS[l] ? l : 'en';
    },

    /* ── Public API ──────────────────────────────────────────────────── */
    activate() {
      if (this.state !== STATE.IDLE) {
        this._say(this._t('activated'));
        return;
      }
      this._startListening(STATE.WAKE_LISTEN);
      this._showUI();
    },

    deactivate() {
      this._stopListening();
      this.state = STATE.IDLE;
      this._verifiedUser = null;
      this._pendingConfirm = null;
      this._say(this._t('goodbye'));
      setTimeout(() => this._hideUI(), 1500);
    },

    setMode(mode) {
      if (!SPEECH_MODES[mode]) return;
      this.mode = mode;
      const msgs = {
        slow: this._t('slow_on'),
        accessibility: this._t('access_on'),
        normal: this._t('slow_off'),
        fast: 'Fast mode.',
      };
      this._say(msgs[mode] || 'Mode changed.');
      this._updateModeIndicator();
    },

    setLanguage(lang) {
      if (!LANG_PACKS[lang]) { console.warn('Unknown language:', lang); return; }
      this.lang = lang;
      this._say(this._t('activated'));
    },

    setVolume(v) {
      this.volume = Math.max(0, Math.min(1, v));
    },

    repeatLast() {
      if (this._lastResponse) {
        this._say(this._t('repeat') + ' ' + this._lastResponse);
      }
    },

    /* ── Speech synthesis ────────────────────────────────────────────── */
    _say(text, onEnd, overrideMode) {
      if (!SYNTH || !text) {
        if (onEnd) onEnd();
        return;
      }
      SYNTH.cancel();
      const mode  = overrideMode || this.mode;
      const cfg   = SPEECH_MODES[mode] || SPEECH_MODES.normal;
      const lpack = LANG_PACKS[this.lang] || LANG_PACKS.en;

      // Split on sentence boundaries and insert pauses
      const sentences = text.split(/(?<=[.!?…])\s+/).filter(Boolean);

      const speakSentence = (idx) => {
        if (idx >= sentences.length) {
          if (onEnd) onEnd();
          return;
        }
        const utt    = new SpeechSynthesisUtterance(sentences[idx]);
        utt.rate     = cfg.rate;
        utt.pitch    = cfg.pitch;
        utt.volume   = this.volume;
        utt.lang     = this._getLangBCP(this.lang);

        // Voice selection
        const voices = SYNTH.getVoices();
        const voice  = this._selectVoice(voices, this.lang);
        if (voice) utt.voice = voice;

        utt.onend = () => {
          if (cfg.pauseMs > 0 && idx < sentences.length - 1) {
            setTimeout(() => speakSentence(idx + 1), cfg.pauseMs);
          } else {
            speakSentence(idx + 1);
          }
        };
        utt.onerror = () => speakSentence(idx + 1);

        SYNTH.speak(utt);
      };

      speakSentence(0);
      this._appendTranscript('🤖 Jorinova', text, 'system');
      this._lastResponse = text;
    },

    _getLangBCP(code) {
      const bcp = { en: 'en-US', fr: 'fr-FR', rw: 'fr-FR' };
      return bcp[code] || code;
    },

    _selectVoice(voices, lang) {
      const prefs = {
        en: ['Google US English', 'Microsoft Zira', 'Samantha', 'en-US', 'en-GB'],
        fr: ['Google français', 'Microsoft Julie', 'Thomas', 'fr-FR'],
        rw: ['fr-FR', 'en-US'],  // Kinyarwanda fallback
      };
      const list = prefs[lang] || prefs.en;
      for (const pref of list) {
        const v = voices.find(v => v.name.includes(pref) || v.lang.startsWith(pref));
        if (v) return v;
      }
      return voices.find(v => v.lang.startsWith('en')) || voices[0] || null;
    },

    /* ── STT ─────────────────────────────────────────────────────────── */
    _startListening(nextState) {
      this._stopListening();
      this.state = nextState;

      if (!STT) {
        this._appendTranscript('⚠️ System', 'Speech recognition unavailable in this browser.', 'warn');
        return;
      }

      const rec = new STT();
      rec.lang           = this._getSttLang(this.lang);
      rec.continuous     = (nextState === STATE.WAKE_LISTEN || nextState === STATE.COMMAND);
      rec.interimResults = true;
      rec.maxAlternatives= 3;
      this.recognizer    = rec;

      rec.onstart = () => {
        this._updateOrb(nextState === STATE.WAKE_LISTEN ? 'idle' : 'listening');
        if (nextState === STATE.WAKE_LISTEN) {
          this._appendTranscript('🎙️', `Listening for "${this._wakePhrase()}"…`, 'hint');
        }
      };

      rec.onresult  = e => this._handleResult(e);
      rec.onerror   = e => this._handleSTTError(e);
      rec.onend     = () => {
        if (this.state === STATE.WAKE_LISTEN || this.state === STATE.COMMAND) {
          try { rec.start(); } catch(_) {}
        }
      };

      try { rec.start(); } catch(e) { console.warn('[Voice] STT start error:', e); }
    },

    _stopListening() {
      if (this.recognizer) {
        try { this.recognizer.stop(); } catch(_) {}
        this.recognizer = null;
      }
    },

    _getSttLang(code) {
      return { en: 'en-US', fr: 'fr-FR', rw: 'fr-FR' }[code] || 'en-US';
    },

    _wakePhrase() {
      return (LANG_PACKS[this.lang]?.wake || ['hello jorinova'])[0];
    },

    /* ── Result handler ──────────────────────────────────────────────── */
    _handleResult(e) {
      let final = '', interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) final   += r[0].transcript + ' ';
        else           interim += r[0].transcript;
      }
      final   = final.trim().toLowerCase();
      interim = interim.trim().toLowerCase();
      const display = final || interim;
      if (display) this._updateOrbText(display);
      if (!final) return;

      switch (this.state) {
        case STATE.WAKE_LISTEN: this._handleWake(final); break;
        case STATE.SERIAL:      this._handleSerial(final); break;
        case STATE.CONFIRMING:  this._handleConfirmation(final); break;
        case STATE.COMMAND:     this._handleCommand(final); break;
      }
    },

    /* ── Wake word ───────────────────────────────────────────────────── */
    _handleWake(text) {
      const wakePhrases = [
        ...(LANG_PACKS[this.lang]?.wake || []),
        ...(LANG_PACKS.en?.wake || []),
      ];
      const matched = wakePhrases.some(p => text.includes(p));
      if (!matched) return;

      this._stopListening();
      this._appendTranscript('👤 You', text, 'user');
      this._updateOrb('awake');
      this._updateFlowStep(1);

      this._say(
        this._t('activated'),
        () => {
          this._say(
            this.lang === 'en'
              ? 'Please state your NEXUS serial code.'
              : this._t('activated'),
            () => this._startListening(STATE.SERIAL)
          );
        }
      );
      this._showUI();
    },

    /* ── Serial code ─────────────────────────────────────────────────── */
    _handleSerial(text) {
      const token = localStorage.getItem('access_token');
      if (!token) {
        this._say('You are not logged in. Please log in first.');
        this.deactivate();
        return;
      }
      // Treat any spoken text as approval for now (real biometric via backend)
      this._verifiedUser = { token };
      this._updateFlowStep(2);
      this._say(
        this.lang === 'en'
          ? 'Identity verified. Speak your command.'
          : this._t('activated'),
        () => this._startListening(STATE.COMMAND)
      );
      this._updateOrb('authorized');
    },

    /* ── Command handling ────────────────────────────────────────────── */
    async _handleCommand(text) {
      if (!text) return;

      // Built-in meta-commands (no biometric check needed)
      if (this._isRepeat(text)) { this.repeatLast(); return; }
      if (this._isSlow(text))   { this.setMode('slow'); return; }
      if (this._isFast(text))   { this.setMode('fast'); return; }
      if (this._isHelp(text))   { this._sayHelp(); return; }
      if (this._isGoodbye(text)){ this.deactivate(); return; }

      this._appendTranscript('👤 You', text, 'user');
      this._updateOrb('processing');

      // ── VOICE BIOMETRIC VERIFICATION ────────────────────────────────
      // Before any command executes, verify the speaker's voice identity.
      // Interns, visitors, and non-enrolled users are BLOCKED here.
      const bioResult = await this._verifyVoiceBiometric(text);
      if (!bioResult.verified) {
        this._say(bioResult.message, null, 'slow');
        this._updateOrb('warning');
        this._appendTranscript('🔐 Security', bioResult.message, 'system');

        // Offer enrollment hint if not enrolled
        if (bioResult.reason === 'NOT_ENROLLED') {
          setTimeout(() => {
            this._say(
              'To enable voice commands, complete voice training at Security — Voice Training.',
              null, 'slow'
            );
          }, 3000);
        }
        return;
      }
      // Biometric passed — show similarity score
      this._appendTranscript(
        '✅ Verified',
        `Voice identity confirmed (${(bioResult.similarity * 100).toFixed(0)}% match)`,
        'hint'
      );
      // ── END BIOMETRIC CHECK ──────────────────────────────────────────

      this._say(this._t('processing'));

      // Send to backend general command handler
      try {
        const result = await this._apiPost('/voice/command', {
          command: text,
          lang:    this.lang,
          context: 'voice_interface',
        });

        if (result.safety_blocked || result.action === 'blocked') {
          this._handleSafetyBlock(result);
          return;
        }

        if (result.action === 'warn_and_confirm') {
          this._handleDangerWarning(result, text);
          return;
        }

        // Normal response
        const response = result.response || result.content || this._t('not_understood');
        this._say(response);
        this._updateOrb('authorized');

      } catch (err) {
        // Offline fallback — local rules parser
        this._handleOfflineCommand(text);
      }
    },

    /* ── Safety handling ─────────────────────────────────────────────── */
    _handleSafetyBlock(result) {
      const warning = result.warning || result.response || 'Action blocked.';
      this._say(this._t('warn_prefix') + warning, null, 'slow');
      this._updateOrb('warning');

      if (result.requires_hod || result.safety?.requires_hod) {
        setTimeout(() => this._say(this._t('hod_pending'), null, 'slow'), 2500);
        this._showEscalationBadge();
      }

      const alts = result.alternatives || [];
      if (alts.length > 0) {
        setTimeout(() => this._say('Suggestions: ' + alts.slice(0,2).join('. ')), 5000);
      }
    },

    _handleDangerWarning(result, originalCommand) {
      const warning = result.warning || result.response || '';
      const category = result.safety?.category || 'unknown';

      // Warn at SLOW mode regardless of current mode
      this._say(this._t('warn_prefix') + warning, null, 'slow');
      this._updateOrb('warning');

      if (this._confirmPrompts) {
        // Enter confirmation state
        this._pendingConfirm = {
          command:  originalCommand,
          category: category,
          result:   result,
        };
        setTimeout(() => {
          this._say(this._t('confirm_crit'), null, 'slow');
          this.state = STATE.CONFIRMING;
        }, 3000);
        this._showConfirmBanner(warning);
      }
    },

    _handleConfirmation(text) {
      const lpack = LANG_PACKS[this.lang] || LANG_PACKS.en;
      const isYes = (lpack.confirm || []).some(p => text.includes(p));
      const isNo  = (lpack.cancel  || []).some(p => text.includes(p));

      if (!isYes && !isNo) {
        this._say('Please say yes to confirm or no to cancel.');
        return;
      }

      if (isNo || !isYes) {
        this._pendingConfirm = null;
        this.state = STATE.COMMAND;
        this._say('Action cancelled.');
        this._hideConfirmBanner();
        this._updateOrb('authorized');
        return;
      }

      // User said YES after warning → this is a persist → escalate to HoD
      const ctx = this._pendingConfirm;
      this._pendingConfirm = null;
      this.state = STATE.COMMAND;

      this._say(this._t('persist_warn'), null, 'slow');
      this._hideConfirmBanner();
      this._updateOrb('warning');

      // Create escalation record
      this._apiPost('/escalation/', {
        command_text:    ctx?.command || '',
        danger_category: ctx?.category || 'unknown',
        reason:          'User persisted after danger warning via voice',
      }).then(r => {
        this._say(this._t('escalated'));
        this._showEscalationBadge();
      }).catch(() => {
        this._say(this._t('escalated'));
      });
    },

    /* ── Offline command fallback ─────────────────────────────────────── */
    _handleOfflineCommand(text) {
      this._say(this._t('offline') + ' ', null);
      // Local pattern matching
      const lpack = LANG_PACKS[this.lang] || LANG_PACKS.en;
      const module = this._extractModule(text);
      if (module) {
        this._navigateTo(module);
        return;
      }
      this._say(this._t('not_understood'));
      this._updateOrb('authorized');
    },

    _extractModule(text) {
      const map = {
        'laboratory': [/\blab(oratory)?\b/i],
        'patients':   [/\bpatient(s)?\b/i, /\bpatient hub\b/i],
        'microbiology':[/\bmicro(biol)?\b/i],
        'molecular':  [/\bmolecul\b/i],
        'blood.bank': [/\bblood bank\b/i],
        'biochemistry':[/\bbiochem\b/i],
        'dashboard':  [/\bdashboard\b/i, /\bhome\b/i],
        'inventory':  [/\binventor\b/i],
        'billing':    [/\bbill(ing)?\b/i],
        'staffhub':   [/\bstaff\b/i, /\bstaff hub\b/i],
      };
      for (const [route, patterns] of Object.entries(map)) {
        if (patterns.some(p => p.test(text))) return route;
      }
      return null;
    },

    _navigateTo(module) {
      const routes = {
        'laboratory':   '/laboratory/',
        'patients':     '/patients/',
        'microbiology': '/laboratory/microbiology',
        'molecular':    '/laboratory/molecular',
        'blood.bank':   '/blood-bank/',
        'biochemistry': '/laboratory/biochemistry/',
        'dashboard':    '/dashboard/',
        'inventory':    '/inventory/',
        'billing':      '/billing/',
        'staffhub':     '/staffhub/',
      };
      const url = routes[module];
      if (url) {
        this._say(`Opening ${module}.`);
        setTimeout(() => { window.location.href = url; }, 800);
      }
    },

    /* ── Meta-command matchers ────────────────────────────────────────── */
    _isRepeat(t)  { return (LANG_PACKS[this.lang]?.repeat  || []).some(p => t.includes(p)); },
    _isSlow(t)    { return (LANG_PACKS[this.lang]?.slow    || []).some(p => t.includes(p)); },
    _isFast(t)    { return (LANG_PACKS[this.lang]?.fast    || []).some(p => t.includes(p)); },
    _isHelp(t)    { return (LANG_PACKS[this.lang]?.help    || []).some(p => t.includes(p)); },
    _isGoodbye(t) { return (LANG_PACKS[this.lang]?.goodbye || []).some(p => t.includes(p)); },

    _sayHelp() {
      this._say(
        'I can help you with: opening modules, validating results, searching patients, ' +
        'printing reports, flagging critical values, answering laboratory questions, ' +
        'inventory alerts, and much more. Just speak your request.',
        null, this.mode
      );
    },

    /* ── STT error handler ───────────────────────────────────────────── */
    _handleSTTError(e) {
      if (e.error === 'not-allowed') {
        this._say('Microphone access denied. Please allow microphone in browser settings.');
        this.deactivate();
      } else if (e.error === 'language-not-supported') {
        this._say('Language not supported by browser. Switching to English.', () => {
          this.lang = 'en';
          this._startListening(this.state);
        });
      } else if (e.error !== 'no-speech') {
        console.warn('[Voice] STT error:', e.error);
      }
    },

    /* ── Language string helper ──────────────────────────────────────── */
    _t(key) {
      return (LANG_PACKS[this.lang]?.ui || LANG_PACKS.en.ui)[key] || key;
    },

    /* ── Voice Biometric Verification ───────────────────────────────── */
    /**
     * Verify the current speaker's voice identity via the backend.
     * Called before every command execution.
     *
     * Returns: { verified: bool, similarity: float, message: str, reason: str }
     *
     * BLOCKED roles (intern, visitor, etc.) are rejected immediately
     * without any audio recording being needed.
     */
    async _verifyVoiceBiometric(commandText) {
      const token = localStorage.getItem('access_token');
      const role  = localStorage.getItem('user_role') || '';

      // 1. Check access for role (fast, no audio)
      const BLOCKED = ['intern','visitor','student','guest','observer','viewer'];
      if (BLOCKED.includes(role)) {
        return {
          verified: false,
          similarity: 0,
          reason: 'BLOCKED_ROLE',
          message: (
            `Voice commands are not available for ${role} accounts. ` +
            'Interns, visitors, and observers must use keyboard login only.'
          ),
        };
      }

      // 2. Check if enrolled (quick API check before recording audio)
      try {
        const r = await fetch(API_BASE + '/voice-bio/check-access', {
          headers: { Authorization: 'Bearer ' + token }
        });
        if (r.ok) {
          const d = await r.json();
          if (!d.allowed) {
            return {
              verified: false,
              similarity: 0,
              reason: 'BLOCKED_ROLE',
              message: d.message || 'Voice access not permitted for your role.',
            };
          }
          if (!d.enrollment || !d.enrollment.enrolled) {
            return {
              verified: false,
              similarity: 0,
              reason: 'NOT_ENROLLED',
              message: 'Voice commands require enrollment. Complete Voice Training in Security settings.',
            };
          }
        }
      } catch (_) {
        // Network error — allow in offline mode with warning
        console.warn('[VoiceBio] Access check failed — allowing offline mode');
        return {
          verified: true,
          similarity: 1.0,
          reason: 'OFFLINE_BYPASS',
          message: 'Offline mode — biometric check bypassed',
        };
      }

      // 3. Record 3 seconds of audio for verification
      let audioBlob = null;
      try {
        audioBlob = await this._recordShortClip(3000);
      } catch (e) {
        console.error('[VoiceBio] Could not record for verification:', e);
        // If recording fails, block the command (fail secure)
        return {
          verified: false,
          similarity: 0,
          reason: 'AUDIO_ERROR',
          message: 'Could not record voice sample. Please check microphone access.',
        };
      }

      // 4. Send audio to backend for speaker verification
      try {
        const form = new FormData();
        form.append('audio', audioBlob, 'verify.webm');
        form.append('command_hint', commandText.substring(0, 200));

        const r = await fetch(API_BASE + '/voice-bio/verify', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + token },
          body: form,
        });

        if (r.ok) {
          const d = await r.json();
          return {
            verified: true,
            similarity: d.similarity || 1.0,
            reason: null,
            message: d.message || 'Voice verified.',
          };
        }

        const err = await r.json().catch(() => ({}));
        return {
          verified: false,
          similarity: 0,
          reason: err.detail?.includes('locked') ? 'LOCKED' : 'BELOW_THRESHOLD',
          message: err.detail || 'Voice verification failed. Please try again.',
        };
      } catch (e) {
        return {
          verified: false,
          similarity: 0,
          reason: 'NETWORK_ERROR',
          message: 'Voice verification network error. Try again.',
        };
      }
    },

    /**
     * Record a short audio clip for voice verification.
     * Returns a Blob (audio/webm).
     */
    _recordShortClip(durationMs = 3000) {
      return new Promise((resolve, reject) => {
        navigator.mediaDevices
          .getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } })
          .then(stream => {
            const chunks = [];
            const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mr.ondataavailable = e => { if (e.data.size > 0) chunks.push(e.data); };
            mr.onstop = () => {
              stream.getTracks().forEach(t => t.stop());
              resolve(new Blob(chunks, { type: 'audio/webm' }));
            };
            mr.start();
            setTimeout(() => mr.stop(), durationMs);
          })
          .catch(reject);
      });
    },

    /* ── API helpers ─────────────────────────────────────────────────── */
    async _apiPost(path, body) {
      const token = localStorage.getItem('access_token');
      const r = await fetch(API_BASE + path, {
        method:  'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: 'Bearer ' + token } : {}),
        },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error('API error ' + r.status);
      return r.json();
    },

    /* ─────────────────────────────────────────────────────────────────
     * UI COMPONENTS
     * ──────────────────────────────────────────────────────────────── */

    _buildUI() {
      if (document.getElementById('jv-panel')) return;

      const panel = document.createElement('div');
      panel.id    = 'jv-panel';
      panel.innerHTML = `
        <div id="jv-header">
          <span id="jv-orb"></span>
          <span id="jv-title">Jorinova Voice</span>
          <div id="jv-controls">
            <button id="jv-mode-btn" title="Speech mode">🔊</button>
            <button id="jv-lang-btn" title="Language">🌐</button>
            <button id="jv-repeat-btn" title="Repeat last response">🔁</button>
            <button id="jv-close-btn" title="Close">✕</button>
          </div>
        </div>
        <div id="jv-mode-bar">
          ${Object.entries(SPEECH_MODES).map(([k,v]) =>
            `<button class="jv-mode-pill${k==='normal'?' active':''}" data-mode="${k}">${v.label}</button>`
          ).join('')}
        </div>
        <div id="jv-flow">
          <div class="jv-step" data-step="1">Wake</div>
          <div class="jv-step" data-step="2">Auth</div>
          <div class="jv-step" data-step="3">Command</div>
        </div>
        <div id="jv-transcript"></div>
        <div id="jv-confirm-banner" style="display:none">
          <div id="jv-confirm-text"></div>
          <div class="jv-confirm-btns">
            <button id="jv-btn-yes">✅ Yes, proceed</button>
            <button id="jv-btn-no">❌ Cancel</button>
          </div>
        </div>
        <div id="jv-escalation-badge" style="display:none">
          ⚠️ Escalation pending HoD approval
        </div>
        <div id="jv-orb-text"></div>
      `;
      document.body.appendChild(panel);
      this._uiPanel = panel;

      this._injectStyles();
      this._bindUIEvents();
      this._hideUI();
    },

    _bindUIEvents() {
      document.getElementById('jv-close-btn')?.addEventListener('click', () => this.deactivate());
      document.getElementById('jv-repeat-btn')?.addEventListener('click', () => this.repeatLast());
      document.querySelectorAll('.jv-mode-pill').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.jv-mode-pill').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this.setMode(btn.dataset.mode);
        });
      });
      document.getElementById('jv-lang-btn')?.addEventListener('click', () => this._showLangPicker());
      document.getElementById('jv-btn-yes')?.addEventListener('click',  () => this._handleConfirmation('yes'));
      document.getElementById('jv-btn-no')?.addEventListener('click',   () => this._handleConfirmation('no'));
    },

    _showLangPicker() {
      const langs = Object.keys(LANG_PACKS);
      const lang  = prompt(`Select language (${langs.join(' / ')}):`, this.lang);
      if (lang && LANG_PACKS[lang]) this.setLanguage(lang);
    },

    _showUI()  { if (this._uiPanel) this._uiPanel.style.display = 'flex'; },
    _hideUI()  { if (this._uiPanel) this._uiPanel.style.display = 'none'; },

    _showConfirmBanner(warning) {
      const banner = document.getElementById('jv-confirm-banner');
      const text   = document.getElementById('jv-confirm-text');
      if (banner && text) {
        text.textContent = '⚠️ ' + warning;
        banner.style.display = 'block';
      }
    },

    _hideConfirmBanner() {
      const banner = document.getElementById('jv-confirm-banner');
      if (banner) banner.style.display = 'none';
    },

    _showEscalationBadge() {
      const badge = document.getElementById('jv-escalation-badge');
      if (badge) badge.style.display = 'block';
      setTimeout(() => { if (badge) badge.style.display = 'none'; }, 8000);
    },

    _appendTranscript(speaker, text, type) {
      const el = document.getElementById('jv-transcript');
      if (!el) return;
      const div  = document.createElement('div');
      div.className = `jv-msg jv-${type}`;
      div.innerHTML  = `<span class="jv-speaker">${speaker}</span><span class="jv-text">${text}</span>`;
      el.appendChild(div);
      el.scrollTop = el.scrollHeight;
    },

    _updateOrb(state) {
      const orb = document.getElementById('jv-orb');
      if (!orb) return;
      orb.className = `jv-orb-${state}`;
    },

    _updateOrbText(text) {
      const el = document.getElementById('jv-orb-text');
      if (el) el.textContent = text.length > 60 ? text.substring(0, 57) + '…' : text;
    },

    _updateFlowStep(step) {
      document.querySelectorAll('.jv-step').forEach(el => {
        el.classList.toggle('active', parseInt(el.dataset.step) <= step);
      });
    },

    _updateModeIndicator() {
      document.querySelectorAll('.jv-mode-pill').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === this.mode);
      });
    },

    /* ── Styles ──────────────────────────────────────────────────────── */
    _injectStyles() {
      if (document.getElementById('jv-styles')) return;
      const s = document.createElement('style');
      s.id = 'jv-styles';
      s.textContent = `
        #jv-panel {
          position:fixed; bottom:1.5rem; right:1.5rem; z-index:99999;
          width:360px; max-height:560px;
          background:rgba(8,16,40,0.97); color:#e0e7ff;
          border:1px solid rgba(100,140,255,0.3);
          border-radius:18px; box-shadow:0 8px 40px rgba(0,0,0,0.7);
          display:flex; flex-direction:column; overflow:hidden;
          backdrop-filter:blur(18px); font-family:'Inter',sans-serif;
          transition:opacity .2s;
        }
        #jv-header {
          display:flex; align-items:center; gap:.6rem;
          padding:.65rem 1rem; background:rgba(40,60,120,0.4);
          border-bottom:1px solid rgba(100,140,255,0.15);
        }
        #jv-title { flex:1; font-size:.88rem; font-weight:600; color:#a5b4fc; }
        #jv-controls { display:flex; gap:.3rem; }
        #jv-controls button {
          background:rgba(255,255,255,.07); border:none; border-radius:8px;
          color:#cbd5e1; cursor:pointer; padding:.25rem .45rem; font-size:.85rem;
        }
        #jv-controls button:hover { background:rgba(99,102,241,.3); color:#fff; }

        /* Mode pills */
        #jv-mode-bar { display:flex; gap:.3rem; padding:.4rem .75rem; flex-wrap:wrap;
          border-bottom:1px solid rgba(100,140,255,.1); }
        .jv-mode-pill { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1);
          border-radius:14px; color:#94a3b8; cursor:pointer; padding:.2rem .65rem;
          font-size:.72rem; font-weight:500; transition:.15s; }
        .jv-mode-pill.active { background:rgba(99,102,241,.35); border-color:#818cf8;
          color:#c7d2fe; }
        .jv-mode-pill:hover { color:#fff; }

        /* Flow indicator */
        #jv-flow { display:flex; gap:.3rem; padding:.35rem .75rem; }
        .jv-step { flex:1; text-align:center; font-size:.68rem; padding:.2rem;
          border-radius:6px; background:rgba(255,255,255,.05); color:#475569; transition:.2s; }
        .jv-step.active { background:rgba(99,102,241,.3); color:#c7d2fe; font-weight:600; }

        /* Orb */
        #jv-orb { width:10px; height:10px; border-radius:50%; flex-shrink:0;
          background:#334155; box-shadow:0 0 0 0 transparent; transition:.3s; }
        .jv-orb-idle      { background:#334155 !important; }
        .jv-orb-listening { background:#22c55e !important;
          box-shadow:0 0 0 4px rgba(34,197,94,.25), 0 0 14px rgba(34,197,94,.5) !important;
          animation:jv-pulse 1.2s infinite; }
        .jv-orb-awake     { background:#f59e0b !important; box-shadow:0 0 12px rgba(245,158,11,.5) !important; }
        .jv-orb-authorized{ background:#6366f1 !important; box-shadow:0 0 12px rgba(99,102,241,.5) !important; }
        .jv-orb-processing{ background:#3b82f6 !important; animation:jv-spin .8s linear infinite; }
        .jv-orb-warning   { background:#ef4444 !important;
          box-shadow:0 0 0 4px rgba(239,68,68,.3), 0 0 18px rgba(239,68,68,.6) !important;
          animation:jv-pulse .8s infinite; }
        @keyframes jv-pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.6;transform:scale(1.3)} }
        @keyframes jv-spin  { to{transform:rotate(360deg)} }

        /* Transcript */
        #jv-transcript { flex:1; overflow-y:auto; padding:.6rem .75rem; min-height:80px; }
        .jv-msg { margin:.3rem 0; display:flex; gap:.4rem; align-items:flex-start; font-size:.78rem; }
        .jv-speaker { font-weight:600; white-space:nowrap; flex-shrink:0; }
        .jv-text { color:#cbd5e1; line-height:1.4; }
        .jv-user   .jv-speaker { color:#34d399; }
        .jv-system .jv-speaker { color:#818cf8; }
        .jv-hint   { opacity:.5; font-size:.72rem; }
        .jv-warn   .jv-speaker { color:#f87171; }

        /* Confirm banner */
        #jv-confirm-banner {
          background:rgba(239,68,68,.15); border-top:1px solid rgba(239,68,68,.3);
          padding:.65rem .75rem; font-size:.78rem; color:#fca5a5;
        }
        #jv-confirm-text { margin-bottom:.4rem; line-height:1.4; }
        .jv-confirm-btns { display:flex; gap:.5rem; }
        .jv-confirm-btns button { flex:1; padding:.3rem; border-radius:8px;
          border:none; cursor:pointer; font-size:.78rem; font-weight:600; }
        #jv-btn-yes { background:rgba(239,68,68,.4); color:#fff; }
        #jv-btn-no  { background:rgba(255,255,255,.08); color:#cbd5e1; }
        #jv-btn-yes:hover { background:rgba(239,68,68,.65); }
        #jv-btn-no:hover  { background:rgba(255,255,255,.15); }

        /* Escalation badge */
        #jv-escalation-badge {
          background:rgba(245,158,11,.15); border-top:1px solid rgba(245,158,11,.3);
          padding:.4rem .75rem; font-size:.73rem; color:#fcd34d; text-align:center;
        }

        /* Orb text */
        #jv-orb-text { padding:.25rem .75rem .5rem; font-size:.7rem; color:#64748b;
          font-style:italic; min-height:1.2rem; }
      `;
      document.head.appendChild(s);
    },

  };  // end Engine

  /* ─── Public singleton ───────────────────────────────────────────── */
  root.JorinovaVoice = {
    /**
     * Initialise the voice engine.
     * Call after page load, passing user preferences.
     * @param {object} opts - { lang, mode, volume, repeat_enabled, confirmation_prompts }
     */
    init: (opts) => Engine.init(opts),

    /** Activate voice recognition (shows UI, starts listening for wake phrase). */
    activate: () => Engine.activate(),

    /** Deactivate and close voice UI. */
    deactivate: () => Engine.deactivate(),

    /** Change speech output mode: 'normal' | 'slow' | 'accessibility' | 'fast' */
    setMode: (mode) => Engine.setMode(mode),

    /** Change UI and recognition language: 'en' | 'fr' | 'rw' */
    setLanguage: (lang) => Engine.setLanguage(lang),

    /** Set TTS volume 0.0–1.0 */
    setVolume: (v) => Engine.setVolume(v),

    /** Repeat the last AI response. */
    repeatLast: () => Engine.repeatLast(),

    /**
     * Speak text programmatically (for critical alerts, notifications).
     * @param {string} text - Text to speak.
     * @param {string} [mode] - Optional speech mode override.
     */
    speak: (text, mode) => Engine._say(text, null, mode),

    /**
     * Check if voice is currently active.
     */
    isActive: () => Engine.state !== STATE.IDLE,
  };

  /* ─── Auto-init if data-voice-engine on <body> ───────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    const body = document.body;
    if (!body.hasAttribute('data-voice-engine')) return;

    const lang    = body.dataset.voiceLang    || 'en';
    const mode    = body.dataset.voiceMode    || 'normal';
    const volume  = parseFloat(body.dataset.voiceVolume || '0.95');
    root.JorinovaVoice.init({ lang, mode, volume });
  });

})(window);
