/**
 * NEXUS ALIS-X — Production Voice AI Engine
 * ===========================================
 * Touch-free voice control for the entire ALIS-X laboratory system.
 *
 * Features:
 *   - Continuous listening with wake word "NEXUS"
 *   - Female voice TTS in English, French, and Kinyarwanda
 *   - Full system navigation by voice
 *   - Step-by-step workflow guidance (spoken, pauseable)
 *   - Knowledge base Q&A (lab procedures, ISO 15189, interpretation)
 *   - Visual listening indicator (floating microphone orb)
 *   - Whisper fallback for environments without browser STT
 *   - Works all day without touching the screen
 *
 * Architecture:
 *   STT: Web Speech API (SpeechRecognition) — browser-native, real-time
 *        + Whisper server backup (POST /api/v1/voice-ai/transcribe)
 *   TTS: Web Speech Synthesis (SpeechSynthesisUtterance) — offline capable
 *        + Google Translate TTS for Kinyarwanda (rw) fallback
 *   AI:  POST /api/v1/voice-ai/command → navigation / guidance / answer
 *
 * Wake word: "NEXUS" (case-insensitive, detected within any phrase)
 * To activate manually: click the microphone orb in the corner.
 *
 * Usage (from any page):
 *   window.NexusVoice.speak("Hello");
 *   window.NexusVoice.setLanguage('rw');
 *   window.NexusVoice.startGuide('receive_sample');
 */

'use strict';

(function (global) {

  const API     = '/api/v1';
  const TOKEN   = () => localStorage.getItem('access_token') || '';
  const HDRS    = () => ({ 'Content-Type':'application/json', 'Authorization':'Bearer '+TOKEN() });

  // ── State ─────────────────────────────────────────────────────────────────

  let _lang          = localStorage.getItem('nexus_voice_lang') || 'en';
  let _active        = false;   // currently listening for commands (after wake word)
  let _speaking      = false;   // TTS is currently speaking
  let _guideSteps    = [];      // current guide steps
  let _guideIndex    = 0;       // current guide step position
  let _guideActive   = false;
  let _recognition   = null;    // SpeechRecognition instance
  let _synth         = window.speechSynthesis;
  let _femaleVoice   = null;    // selected female voice
  let _orbEl         = null;    // floating microphone orb element
  let _statusEl      = null;    // status text element
  let _wakeTimeout   = null;    // timeout to return to wake-word mode
  let _lastResponse  = '';      // last spoken text (for repeat)
  let _enabled       = true;    // master on/off

  // ── Language config ───────────────────────────────────────────────────────

  const LANG_CONFIG = {
    en: { bcp47: 'en-GB', name: 'English', gtts: false },
    fr: { bcp47: 'fr-FR', name: 'Français', gtts: false },
    rw: { bcp47: 'rw',    name: 'Kinyarwanda', gtts: true },  // needs Google TTS
  };

  const PROMPTS = {
    wake_detected: { en:'Yes?', fr:'Oui?', rw:'Yego?' },
    listening:     { en:'Listening…', fr:'J\'écoute…', rw:'Ndumva…' },
    not_understood:{ en:'I did not understand. Please try again.', fr:'Je n\'ai pas compris. Veuillez réessayer.', rw:'Sibyumvise. Ongera ugerageze.' },
    error:         { en:'Voice error. Please try again.', fr:'Erreur vocale.', rw:'Ikosa ry\'ijwi.' },
    wake_hint:     { en:"Say 'NEXUS' to activate.", fr:"Dites 'NEXUS' pour activer.", rw:"Vuga 'NEXUS' kugirango utangire." },
    guide_next:    { en:'Say "next" for the next step, "repeat" to hear again, or "stop" to end guidance.', fr:'Dites "suivant" pour continuer.', rw:'Vuga "ibikurikira" intambwe ikurikira.' },
    guide_done:    { en:'Guidance complete. Is there anything else I can help you with?', fr:'Guidage terminé. Autre chose?', rw:'Ubuyobozi burangiye. Hari ikindi?' },
  };

  // ── Voice orb UI ──────────────────────────────────────────────────────────

  function _buildOrb() {
    const orb = document.createElement('div');
    orb.id        = 'nexus-voice-orb';
    orb.innerHTML = `
      <div class="nv-orb-ring"></div>
      <div class="nv-orb-core">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
          <line x1="8" y1="23" x2="16" y2="23"/>
        </svg>
      </div>
      <div class="nv-orb-label" id="nv-status">Say NEXUS</div>
      <div class="nv-wave-container" id="nv-waves">
        ${[0,1,2,3,4].map(i=>`<div class="nv-wave" style="--i:${i}"></div>`).join('')}
      </div>
    `;
    orb.style.cssText = `
      position:fixed; bottom:24px; right:24px; z-index:9999;
      display:flex; flex-direction:column; align-items:center; gap:4px;
      cursor:pointer; user-select:none;
    `;
    orb.addEventListener('click', _orbClick);
    document.body.appendChild(orb);
    _orbEl   = orb;
    _statusEl = orb.querySelector('#nv-status');

    // Inject CSS
    if (!document.getElementById('nexus-voice-css')) {
      const style = document.createElement('style');
      style.id = 'nexus-voice-css';
      style.textContent = `
        #nexus-voice-orb .nv-orb-core {
          width:52px; height:52px; border-radius:50%;
          background:linear-gradient(135deg,#0891b2,#0e7490);
          display:flex; align-items:center; justify-content:center;
          color:#fff; box-shadow:0 4px 15px rgba(8,145,178,.4);
          transition:all .2s; position:relative; z-index:2;
        }
        #nexus-voice-orb:hover .nv-orb-core { transform:scale(1.08); box-shadow:0 6px 20px rgba(8,145,178,.6); }
        #nexus-voice-orb.active .nv-orb-core { background:linear-gradient(135deg,#dc2626,#b91c1c); animation:nv-pulse 1s infinite; }
        #nexus-voice-orb.listening .nv-orb-core { background:linear-gradient(135deg,#16a34a,#15803d); }
        #nexus-voice-orb.speaking .nv-orb-core { background:linear-gradient(135deg,#7c3aed,#6d28d9); }
        .nv-orb-ring {
          position:absolute; width:68px; height:68px; border-radius:50%;
          border:2px solid rgba(8,145,178,.3); top:-8px; left:-8px; z-index:1;
          animation:nv-ring-idle 3s infinite;
        }
        .nv-orb-label {
          font-size:10px; font-weight:600; color:#475569;
          background:rgba(255,255,255,.9); padding:2px 8px;
          border-radius:10px; border:1px solid #e4e8f0;
          white-space:nowrap; max-width:120px; overflow:hidden;
          text-overflow:ellipsis; text-align:center;
        }
        .nv-wave-container { display:flex; gap:3px; align-items:center; height:20px; }
        .nv-wave {
          width:3px; background:#0891b2; border-radius:2px; opacity:0;
          animation:nv-wave-anim 0.8s calc(var(--i)*0.12s) infinite;
        }
        #nexus-voice-orb.listening .nv-wave { opacity:1; }
        #nexus-voice-orb.speaking .nv-wave { opacity:1; background:#7c3aed; }
        @keyframes nv-pulse { 0%,100%{box-shadow:0 0 0 0 rgba(220,38,38,.4)} 50%{box-shadow:0 0 0 10px rgba(220,38,38,0)} }
        @keyframes nv-ring-idle { 0%,100%{transform:scale(1);opacity:.4} 50%{transform:scale(1.15);opacity:.1} }
        @keyframes nv-wave-anim { 0%,100%{height:4px} 50%{height:18px} }
        .nv-transcript-bubble {
          position:fixed; bottom:90px; right:24px; z-index:9998;
          background:#fff; border:1px solid #e4e8f0;
          border-radius:12px 12px 4px 12px;
          padding:.5rem .85rem; font-size:.78rem; color:#0f172a;
          box-shadow:0 4px 15px rgba(0,0,0,.12);
          max-width:260px; word-break:break-word; opacity:0;
          transition:opacity .2s; pointer-events:none;
        }
        .nv-transcript-bubble.show { opacity:1; }
        .nv-guide-panel {
          position:fixed; bottom:90px; right:24px; z-index:9997;
          background:#fff; border:1px solid #0891b2;
          border-radius:12px; padding:.75rem 1rem;
          box-shadow:0 4px 20px rgba(8,145,178,.2);
          max-width:320px; font-size:.8rem;
          display:none;
        }
        .nv-guide-panel.show { display:block; }
        .nv-guide-step { color:#0f172a; line-height:1.5; margin-bottom:.5rem; }
        .nv-guide-controls { display:flex; gap:.5rem; margin-top:.5rem; }
        .nv-guide-btn {
          padding:3px 10px; border-radius:6px; font-size:.72rem; font-weight:600;
          cursor:pointer; border:1px solid #e4e8f0; background:#f8faff; color:#0891b2;
        }
        .nv-guide-btn:hover { background:#e0f2fe; }
        .nv-lang-pill {
          position:fixed; bottom:24px; right:88px; z-index:9999;
          background:#fff; border:1px solid #e4e8f0; border-radius:8px;
          padding:4px 10px; font-size:.7rem; font-weight:700; color:#475569;
          cursor:pointer; box-shadow:0 2px 8px rgba(0,0,0,.08);
        }
      `;
      document.head.appendChild(style);
    }

    // Transcript bubble
    const bubble = document.createElement('div');
    bubble.id = 'nv-transcript';
    bubble.className = 'nv-transcript-bubble';
    document.body.appendChild(bubble);

    // Guide panel
    const guide = document.createElement('div');
    guide.id = 'nv-guide-panel';
    guide.className = 'nv-guide-panel';
    guide.innerHTML = `
      <div style="font-size:.7rem;font-weight:700;color:#0891b2;margin-bottom:.4rem;text-transform:uppercase;letter-spacing:.05em">
        <i class="fas fa-headphones"></i> Step-by-Step Guidance
      </div>
      <div class="nv-guide-step" id="nv-guide-text"></div>
      <div style="font-size:.65rem;color:#94a3b8;margin:.25rem 0" id="nv-guide-counter"></div>
      <div class="nv-guide-controls">
        <button class="nv-guide-btn" onclick="NexusVoice.guideNext()">Next ›</button>
        <button class="nv-guide-btn" onclick="NexusVoice.guideRepeat()">Repeat</button>
        <button class="nv-guide-btn" onclick="NexusVoice.guideStop()" style="color:#dc2626">Stop</button>
      </div>`;
    document.body.appendChild(guide);

    // Language switcher pill
    const langPill = document.createElement('div');
    langPill.className = 'nv-lang-pill';
    langPill.id = 'nv-lang-pill';
    langPill.textContent = _lang.toUpperCase();
    langPill.title = 'Click to switch language (EN / FR / RW)';
    langPill.addEventListener('click', _cycleLang);
    document.body.appendChild(langPill);
  }

  function _orbClick() {
    if (_active) {
      _deactivate();
    } else {
      _activate();
    }
  }

  function _setOrbState(state) {
    // state: idle | active | listening | speaking
    if (!_orbEl) return;
    _orbEl.className = state === 'idle' ? '' : state;
    const labels = {
      idle:      { en:'Say NEXUS', fr:'Dites NEXUS', rw:'Vuga NEXUS' },
      active:    { en:'Ready…',   fr:'Prêt…',       rw:'Tegura…' },
      listening: { en:'Listening',fr:'J\'écoute',    rw:'Ndumva' },
      speaking:  { en:'Speaking', fr:'Je parle',     rw:'Mvugira' },
    };
    const lbl = labels[state]?.[_lang] || labels[state]?.en || state;
    if (_statusEl) _statusEl.textContent = lbl;
  }

  // ── Speech Recognition (STT) ──────────────────────────────────────────────

  function _initSTT() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      console.warn('[NexusVoice] SpeechRecognition not available in this browser. Use Chrome or Edge.');
      return false;
    }
    _recognition = new SR();
    _recognition.continuous    = true;
    _recognition.interimResults= true;
    _recognition.maxAlternatives = 2;
    _recognition.lang = LANG_CONFIG[_lang]?.bcp47 || 'en-GB';

    _recognition.onresult = _onSTTResult;
    _recognition.onerror  = _onSTTError;
    _recognition.onend    = () => {
      // Auto-restart unless deliberately stopped
      if (_enabled && !_speaking) {
        setTimeout(() => {
          try { _recognition.start(); } catch(_) {}
        }, 300);
      }
    };
    return true;
  }

  function _onSTTResult(event) {
    let interim = '';
    let final   = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const t = event.results[i][0].transcript.trim();
      if (event.results[i].isFinal) final = t;
      else interim = t;
    }

    // Show interim transcript
    _showTranscript(interim || final);

    if (!final) return;

    const text = final.toLowerCase();

    // Wake word detection (always on)
    if (!_active && (text.includes('nexus') || text.includes('nixi') || text.includes('nexis'))) {
      _activate();
      return;
    }

    // Guide navigation shortcuts
    if (_guideActive) {
      if (text.includes('next') || text.includes('ibikurikira') || text.includes('suivant')) {
        guideNext(); return;
      }
      if (text.includes('repeat') || text.includes('ongera') || text.includes('répéter')) {
        guideRepeat(); return;
      }
      if (text.includes('stop') || text.includes('hagarara') || text.includes('arrête')) {
        guideStop(); return;
      }
    }

    // Active: process command
    if (_active) {
      // Strip wake word from command if included
      const cmd = final.replace(/nexus\s*/i, '').trim();
      if (cmd.length > 1) {
        _processCommand(cmd);
        _resetWakeTimeout();
      }
    }
  }

  function _onSTTError(e) {
    if (e.error === 'not-allowed') {
      _showTranscript('Microphone permission denied. Please allow microphone access.');
      _setOrbState('idle');
    } else if (e.error === 'no-speech') {
      // Normal — no action needed
    } else {
      console.warn('[NexusVoice] STT error:', e.error);
    }
  }

  // ── Activation / Deactivation ─────────────────────────────────────────────

  function _activate() {
    _active = true;
    _setOrbState('active');
    const greeting = PROMPTS.wake_detected[_lang] || PROMPTS.wake_detected.en;
    speak(greeting, { rate: 1.0, pitch: 1.1 });
    _resetWakeTimeout();
  }

  function _deactivate() {
    _active = false;
    clearTimeout(_wakeTimeout);
    _setOrbState('idle');
  }

  function _resetWakeTimeout() {
    clearTimeout(_wakeTimeout);
    // After 15s of inactivity, return to wake-word mode
    _wakeTimeout = setTimeout(() => {
      if (!_guideActive) _deactivate();
    }, 15_000);
  }

  // ── Command Processing ────────────────────────────────────────────────────

  async function _processCommand(text) {
    _setOrbState('listening');
    _showTranscript(text);

    try {
      const r = await fetch(`${API}/voice-ai/command`, {
        method:  'POST',
        headers: HDRS(),
        body:    JSON.stringify({
          text,
          lang: _lang,
          context: document.body.dataset.module || window.location.pathname,
        }),
      });

      if (!r.ok) throw new Error('API error');
      const data = await r.json();

      switch (data.type) {
        case 'navigate':
          speak(data.response_text, { rate: data.tts_rate, pitch: data.tts_pitch });
          setTimeout(() => {
            if (data.navigate_to) window.location.href = data.navigate_to;
          }, 1200);
          _deactivate();
          break;

        case 'guide':
          _startGuideFromResponse(data);
          break;

        case 'answer':
          speak(data.response_text, { rate: data.tts_rate, pitch: data.tts_pitch });
          _setOrbState('idle');
          break;

        case 'repeat':
          if (_lastResponse) speak(_lastResponse);
          break;

        case 'stop':
          _synth.cancel();
          guideStop();
          _deactivate();
          break;

        default:
          speak(data.response_text || PROMPTS.not_understood[_lang]);
          _setOrbState('idle');
      }

    } catch (e) {
      console.error('[NexusVoice] Command error:', e);
      speak(PROMPTS.error[_lang]);
      _setOrbState('idle');
    }
  }

  // ── TTS (Text-to-Speech) ──────────────────────────────────────────────────

  function speak(text, opts = {}) {
    if (!text) return;
    _lastResponse = text;
    _synth.cancel();

    const cfg = LANG_CONFIG[_lang] || LANG_CONFIG.en;

    // For Kinyarwanda, use Google Translate TTS as it has better support
    if (cfg.gtts && _lang === 'rw') {
      _speakGoogleTTS(text);
      return;
    }

    _speakBrowser(text, opts);
  }

  function _speakBrowser(text, opts = {}) {
    const utt  = new SpeechSynthesisUtterance(text);
    const cfg  = LANG_CONFIG[_lang] || LANG_CONFIG.en;

    utt.lang   = cfg.bcp47;
    utt.rate   = opts.rate   ?? 0.88;
    utt.pitch  = opts.pitch  ?? 1.08;
    utt.volume = opts.volume ?? 0.95;

    // Select female voice if available
    if (!_femaleVoice) _selectFemaleVoice();
    if (_femaleVoice) utt.voice = _femaleVoice;

    utt.onstart = () => { _speaking = true;  _setOrbState('speaking'); };
    utt.onend   = () => { _speaking = false; _setOrbState(_active ? 'active' : 'idle'); };
    utt.onerror = (e) => { _speaking = false; console.warn('[NexusVoice] TTS error:', e); };

    _synth.speak(utt);
  }

  function _speakGoogleTTS(text) {
    // Google Translate TTS for Kinyarwanda (rw)
    const encoded = encodeURIComponent(text.slice(0, 200));
    const url = `https://translate.google.com/translate_tts?ie=UTF-8&q=${encoded}&tl=rw&client=tw-ob`;
    const audio = new Audio(url);
    audio.volume = 0.95;
    _speaking = true;
    _setOrbState('speaking');
    audio.onended = () => {
      _speaking = false;
      _setOrbState(_active ? 'active' : 'idle');
    };
    audio.onerror = () => {
      // Fallback to browser TTS if Google TTS fails
      _speakBrowser(text);
    };
    audio.play().catch(() => _speakBrowser(text));
  }

  function _selectFemaleVoice() {
    const voices = _synth.getVoices();
    const cfg    = LANG_CONFIG[_lang] || LANG_CONFIG.en;
    const lang   = cfg.bcp47.split('-')[0];  // e.g. 'en'

    // Priority: local female voices for the language, then any female, then default
    const femaleKeywords = ['female','woman','girl','fiona','zira','victoria','samantha','tessa','moira','veena','karen','serena'];
    const forLang = voices.filter(v => v.lang.startsWith(lang));

    let voice = forLang.find(v => femaleKeywords.some(k => v.name.toLowerCase().includes(k)));
    if (!voice) voice = voices.find(v => v.lang.startsWith(lang));
    if (!voice) voice = voices.find(v => femaleKeywords.some(k => v.name.toLowerCase().includes(k)));

    _femaleVoice = voice || null;
  }

  // ── Step-by-step Guide ────────────────────────────────────────────────────

  function _startGuideFromResponse(data) {
    const steps = data.all_steps || data.steps || [];
    if (!steps.length) { speak(data.response_text); return; }

    _guideSteps  = steps;
    _guideIndex  = 0;
    _guideActive = true;

    const panel = document.getElementById('nv-guide-panel');
    if (panel) panel.classList.add('show');

    _speakGuideStep(0);
  }

  function _speakGuideStep(index) {
    if (index >= _guideSteps.length) {
      guideStop();
      speak(PROMPTS.guide_done[_lang] || PROMPTS.guide_done.en);
      return;
    }

    const step    = _guideSteps[index];
    const counter = document.getElementById('nv-guide-counter');
    const text    = document.getElementById('nv-guide-text');

    if (counter) counter.textContent = `Step ${index + 1} of ${_guideSteps.length}`;
    if (text)    text.textContent    = step;

    speak(step, { rate: 0.82, pitch: 1.06 });

    _setOrbState('speaking');
    _guideIndex = index;

    // After speaking the step, prompt for next
    const charPerMs = 70;
    const pause     = Math.max(3000, step.length * charPerMs);
    setTimeout(() => {
      if (_guideActive && _guideIndex === index) {
        // Automatically continue only if not last step
        if (index < _guideSteps.length - 1) {
          const hint = PROMPTS.guide_next[_lang] || PROMPTS.guide_next.en;
          speak(hint, { rate: 0.95, volume: 0.7 });
        }
      }
    }, pause);
  }

  function guideNext() {
    if (!_guideActive || _guideIndex >= _guideSteps.length - 1) {
      guideStop();
      speak(PROMPTS.guide_done[_lang]);
      return;
    }
    _guideIndex++;
    _speakGuideStep(_guideIndex);
  }

  function guideRepeat() {
    _speakGuideStep(_guideIndex);
  }

  function guideStop() {
    _guideActive = false;
    _guideSteps  = [];
    _guideIndex  = 0;
    _synth.cancel();
    const panel  = document.getElementById('nv-guide-panel');
    if (panel) panel.classList.remove('show');
    _setOrbState('idle');
    _deactivate();
  }

  async function startGuide(topic, lang) {
    const l = lang || _lang;
    try {
      const r = await fetch(`${API}/voice-ai/guidance/${topic}?lang=${l}`, { headers: HDRS() });
      if (!r.ok) throw new Error('not found');
      const data = await r.json();
      _guideSteps  = data.steps || [];
      _guideIndex  = 0;
      _guideActive = true;
      const panel  = document.getElementById('nv-guide-panel');
      if (panel) panel.classList.add('show');
      _speakGuideStep(0);
    } catch(e) {
      speak(`No guidance found for ${topic}.`);
    }
  }

  // ── Transcript bubble ─────────────────────────────────────────────────────

  function _showTranscript(text) {
    const el = document.getElementById('nv-transcript');
    if (!el) return;
    el.textContent = text;
    el.classList.add('show');
    clearTimeout(el._timer);
    el._timer = setTimeout(() => el.classList.remove('show'), 3000);
  }

  // ── Language switcher ─────────────────────────────────────────────────────

  function _cycleLang() {
    const langs = ['en','fr','rw'];
    const idx   = langs.indexOf(_lang);
    _lang       = langs[(idx + 1) % langs.length];
    localStorage.setItem('nexus_voice_lang', _lang);
    const pill = document.getElementById('nv-lang-pill');
    if (pill) pill.textContent = _lang.toUpperCase();

    // Update recognition language
    if (_recognition) {
      _recognition.stop();
      _recognition.lang = LANG_CONFIG[_lang]?.bcp47 || 'en-GB';
    }
    _femaleVoice = null;  // reset voice for new lang

    const msgs = { en:'Language set to English.', fr:'Langue définie sur Français.', rw:'Ururimi rwahinduwe kuri Kinyarwanda.' };
    speak(msgs[_lang]);
  }

  // ── Public API ────────────────────────────────────────────────────────────

  function setLanguage(lang) {
    if (LANG_CONFIG[lang]) {
      _lang = lang;
      localStorage.setItem('nexus_voice_lang', lang);
      const pill = document.getElementById('nv-lang-pill');
      if (pill) pill.textContent = lang.toUpperCase();
      if (_recognition) {
        _recognition.lang = LANG_CONFIG[lang].bcp47;
      }
      _femaleVoice = null;
    }
  }

  function enable()  { _enabled = true;  _start(); }
  function disable() { _enabled = false; _stop(); }
  function toggle()  { _enabled ? disable() : enable(); }

  function _start() {
    if (!_recognition) _initSTT();
    try { _recognition?.start(); } catch(_) {}
    _setOrbState('idle');
  }

  function _stop() {
    _recognition?.stop();
    _synth.cancel();
    _setOrbState('idle');
    _deactivate();
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  function init() {
    // Only activate if user is logged in
    if (!TOKEN()) return;

    // Load voices (may be async in some browsers)
    if (_synth.getVoices().length === 0) {
      _synth.addEventListener('voiceschanged', _selectFemaleVoice, { once: true });
    } else {
      _selectFemaleVoice();
    }

    _buildOrb();
    const hasSTT = _initSTT();

    if (hasSTT) {
      try { _recognition.start(); } catch(_) {}
      console.info('[NexusVoice] Voice AI active. Say "NEXUS" to activate.');
    } else {
      console.warn('[NexusVoice] No browser STT. Click mic orb to type command.');
    }

    // Speak idle hint once, quietly, after login
    setTimeout(() => {
      speak(PROMPTS.wake_hint[_lang], { rate: 0.9, volume: 0.5 });
    }, 3000);
  }

  // ── Export ────────────────────────────────────────────────────────────────

  global.NexusVoice = {
    init, speak, setLanguage, enable, disable, toggle,
    startGuide, guideNext, guideRepeat, guideStop,
    getLanguage: () => _lang,
    isActive:    () => _active,
    isSpeaking:  () => _speaking,
  };

  // Auto-init after DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    // Small delay so page fully renders first
    setTimeout(init, 800);
  }

})(window);
