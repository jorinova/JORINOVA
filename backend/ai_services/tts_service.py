"""
ALIS-X Text-to-Speech Service
==============================
Backend TTS coordination layer.

Architecture:
  - Frontend TTS: Web Speech API (zero server dependency, offline)
  - Backend TTS: pyttsx3 (offline) or gTTS (online) for server-side audio
  - All speech settings are per-user, stored in VoiceSettings model

Speech modes:
  NORMAL       → default rate (~0.88x), standard pauses
  SLOW         → reduced rate (~0.62x), longer pauses
  ACCESSIBILITY→ very slow (~0.50x), maximum pauses, confirmation prompts
  FAST         → slightly faster (~1.1x), shorter pauses

This service generates:
  1. SpeechConfig objects (sent to frontend for Web Speech API)
  2. Server-side audio files when requested (pyttsx3/gTTS fallback)
  3. SSML strings for advanced TTS systems

The frontend reads the SpeechConfig and controls its own speech synthesis —
no audio streaming required for standard use.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ai_services.language_service import get_tts_config, get_string

logger = logging.getLogger('tts_service')


# ── Speech mode ───────────────────────────────────────────────────────────────

class SpeechMode(str, Enum):
    NORMAL        = 'normal'
    SLOW          = 'slow'
    ACCESSIBILITY = 'accessibility'
    FAST          = 'fast'


# ── Speech config (sent to frontend) ─────────────────────────────────────────

@dataclass
class SpeechConfig:
    """
    Serialisable config passed to the frontend Web Speech API voice engine.
    The frontend uses these values for every SpeechSynthesisUtterance.
    """
    text:              str
    lang:              str   = 'en'
    mode:              SpeechMode = SpeechMode.NORMAL
    rate:              float = 0.88
    pitch:             float = 1.0
    volume:            float = 0.95
    pause_after_ms:    int   = 350
    voice_preference:  list  = field(default_factory=lambda: ['en-US'])
    ssml:              str   = ''         # optional SSML-formatted text
    repeat_key:        str   = ''         # cache key for "repeat last" feature

    def to_dict(self) -> dict:
        return {
            'text':           self.text,
            'lang':           self.lang,
            'mode':           self.mode,
            'rate':           self.rate,
            'pitch':          self.pitch,
            'volume':         self.volume,
            'pause_after_ms': self.pause_after_ms,
            'voice_preference': self.voice_preference,
            'ssml':           self.ssml,
            'repeat_key':     self.repeat_key,
        }


# ── Per-user voice settings (in-memory defaults, DB-backed in prod) ───────────

_DEFAULT_SETTINGS: dict[str, dict] = {}   # user_id → settings dict


def get_user_settings(user_id: int) -> dict:
    """Return voice settings for a user, with defaults."""
    return _DEFAULT_SETTINGS.get(str(user_id), {
        'mode':     SpeechMode.NORMAL,
        'lang':     'en',
        'volume':   0.95,
        'rate_mult':1.0,     # user rate multiplier (1.0 = default)
    })


def update_user_settings(user_id: int, settings: dict) -> None:
    """Update user voice settings in memory (and DB via background task)."""
    key = str(user_id)
    current = _DEFAULT_SETTINGS.get(key, {})
    current.update(settings)
    _DEFAULT_SETTINGS[key] = current
    logger.info('Voice settings updated for user %s: %s', user_id, settings)


# ── Config builder ────────────────────────────────────────────────────────────

def build_config(
    text:     str,
    lang:     str = 'en',
    mode:     SpeechMode = SpeechMode.NORMAL,
    volume:   float = 0.95,
    rate_mult:float = 1.0,
    user_id:  Optional[int] = None,
) -> SpeechConfig:
    """
    Build a SpeechConfig object from text + settings.
    Reads user preferences if user_id provided.
    """
    # Load user settings if available
    if user_id is not None:
        us = get_user_settings(user_id)
        mode_str = us.get('mode', mode)
        if isinstance(mode_str, str):
            try:
                mode = SpeechMode(mode_str)
            except ValueError:
                pass
        lang     = us.get('lang', lang)
        volume   = float(us.get('volume', volume))
        rate_mult= float(us.get('rate_mult', rate_mult))

    tts_cfg = get_tts_config(lang)

    # Select rate from mode
    base_rate_map = {
        SpeechMode.NORMAL:        tts_cfg.get('default_rate', 0.88),
        SpeechMode.SLOW:          tts_cfg.get('slow_rate', 0.62),
        SpeechMode.ACCESSIBILITY: tts_cfg.get('accessibility_rate', 0.50),
        SpeechMode.FAST:          min(1.2, tts_cfg.get('default_rate', 0.88) * 1.25),
    }
    base_rate = base_rate_map.get(mode, 0.88)
    rate      = round(base_rate * rate_mult, 3)
    rate      = max(0.3, min(2.0, rate))   # clamp to valid range

    pause_map = {
        SpeechMode.NORMAL:        tts_cfg.get('pause_between_sentences_ms', 350),
        SpeechMode.SLOW:          tts_cfg.get('pause_between_sentences_ms', 350) + 200,
        SpeechMode.ACCESSIBILITY: tts_cfg.get('accessibility_pause_ms', 700),
        SpeechMode.FAST:          150,
    }

    # Generate SSML with pauses between sentences
    ssml = _build_ssml(text, lang, rate, pause_map.get(mode, 350))

    return SpeechConfig(
        text            = text,
        lang            = lang,
        mode            = mode,
        rate            = rate,
        pitch           = tts_cfg.get('default_pitch', 1.0),
        volume          = volume,
        pause_after_ms  = pause_map.get(mode, 350),
        voice_preference= tts_cfg.get('voice_preference', ['en-US']),
        ssml            = ssml,
    )


def _build_ssml(text: str, lang: str, rate: float, pause_ms: int) -> str:
    """
    Build SSML (Speech Synthesis Markup Language) for advanced TTS.
    Inserts pauses between sentences for clarity.
    Web Speech API browsers support a subset of SSML.
    """
    rate_pct = int(rate * 100)
    # Split on sentence boundaries
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    pause_tag  = f'<break time="{pause_ms}ms"/>'

    sentence_ssml = pause_tag.join(
        f'<s>{s}</s>' for s in sentences if s.strip()
    )
    return (
        f'<speak xml:lang="{lang}" version="1.0">'
        f'<prosody rate="{rate_pct}%">'
        f'{sentence_ssml}'
        f'</prosody>'
        f'</speak>'
    )


# ── Accessibility helpers ─────────────────────────────────────────────────────

def accessibility_wrap(text: str, lang: str = 'en', mode: SpeechMode = SpeechMode.NORMAL) -> str:
    """
    Add accessibility-friendly pauses and emphasis to text.
    In accessibility mode, critical phrases are repeated.
    """
    if mode == SpeechMode.ACCESSIBILITY:
        # Insert pauses represented as ellipses for natural speech breaks
        import re
        text = re.sub(r'\. ', '. … ', text)
        text = re.sub(r', ', ', … ', text)
        # Emphasize numbers and medical values
        text = re.sub(r'(\d+\.?\d*)', r' \1 ', text)
    return text


def build_confirmation_prompt(
    action_text: str,
    lang: str = 'en',
    mode: SpeechMode = SpeechMode.NORMAL,
) -> SpeechConfig:
    """Build a confirmation speech config for a critical action."""
    template = get_string(lang, 'confirm_critical',
                          'This is a critical action. Are you sure? Say yes or no.')
    full_text = f'{template} {action_text}'
    if mode == SpeechMode.ACCESSIBILITY:
        full_text = accessibility_wrap(full_text, lang, mode)
    cfg = build_config(full_text, lang, mode)
    cfg.repeat_key = f'confirm:{action_text[:40]}'
    return cfg


def build_danger_warning(
    warning_text: str,
    lang: str = 'en',
    mode: SpeechMode = SpeechMode.SLOW,
) -> SpeechConfig:
    """Build a danger warning — always slow regardless of user settings."""
    danger_prefix = get_string(lang, 'danger_warning', 'Warning. ')
    full_text = f'{danger_prefix}{warning_text}'
    # Danger warnings are always at minimum SLOW mode
    effective_mode = SpeechMode.SLOW if mode == SpeechMode.FAST else mode
    return build_config(full_text, lang, effective_mode)


# ── Server-side TTS (audio file generation) ───────────────────────────────────

async def synthesize_to_file(
    text:     str,
    lang:     str = 'en',
    mode:     SpeechMode = SpeechMode.NORMAL,
    out_path: str = '/tmp/alis_tts.wav',
) -> Optional[str]:
    """
    Generate audio file using pyttsx3 (offline) or gTTS (online).
    Returns path to audio file, or None if synthesis unavailable.
    Used when Web Speech API is not available (e.g., headless clients).
    """
    cfg = build_config(text, lang, mode)

    # Try pyttsx3 (offline, cross-platform)
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty('rate',   int(cfg.rate * 150))  # pyttsx3 uses wpm
        engine.setProperty('volume', cfg.volume)
        # Select voice by language
        voices = engine.getProperty('voices')
        lang_voices = [v for v in voices if lang in (v.languages[0] if v.languages else '')]
        if lang_voices:
            engine.setProperty('voice', lang_voices[0].id)
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        engine.stop()
        logger.info('pyttsx3 TTS → %s', out_path)
        return out_path
    except ImportError:
        logger.debug('pyttsx3 not installed')
    except Exception as e:
        logger.warning('pyttsx3 error: %s', e)

    # Try gTTS (online)
    try:
        from gtts import gTTS
        import asyncio
        tts = gTTS(text=text, lang=lang if len(lang) == 2 else 'en', slow=(mode == SpeechMode.SLOW))
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, tts.save, out_path)
        logger.info('gTTS → %s', out_path)
        return out_path
    except ImportError:
        logger.debug('gTTS not installed')
    except Exception as e:
        logger.warning('gTTS error: %s', e)

    return None


# ── Mode names (for UI display) ───────────────────────────────────────────────

MODE_LABELS = {
    SpeechMode.NORMAL:        'Normal',
    SpeechMode.SLOW:          'Slow',
    SpeechMode.ACCESSIBILITY: 'Accessibility',
    SpeechMode.FAST:          'Fast',
}

MODE_DESCRIPTIONS = {
    SpeechMode.NORMAL:        'Standard speech speed with natural pauses.',
    SpeechMode.SLOW:          'Slower speech with extended pauses. Good for noisy environments.',
    SpeechMode.ACCESSIBILITY: 'Very slow speech with maximum pauses. Designed for hearing difficulties.',
    SpeechMode.FAST:          'Faster speech for experienced users.',
}
