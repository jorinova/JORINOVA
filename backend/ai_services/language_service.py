"""
ALIS-X Language Service
========================
Manages multilingual support across the entire platform.

Architecture:
  - Language packs are JSON files (offline-first, no DB required)
  - New languages added by dropping a JSON file — no code changes needed
  - Language detection uses Whisper's built-in detection for speech
  - Text language detection uses langdetect library (offline)
  - Translation via local LLM or cloud LLM (never required for core function)

Supported initial languages:
  - en  : English
  - fr  : French (common in Rwandan medical/academic settings)
  - rw  : Kinyarwanda (national language of Rwanda)

Language pack format (see language_packs/en.json for full schema).
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger('language_service')

# ── Pack loader ───────────────────────────────────────────────────────────────

_PACKS_DIR = Path(__file__).parent / 'language_packs'
_loaded:    dict[str, dict] = {}        # code → pack dict
_load_time: dict[str, float] = {}       # code → last load epoch


def load_pack(code: str, force: bool = False) -> Optional[dict]:
    """
    Load a language pack by code. Returns None if pack not found.
    Packs are cached in memory. Set force=True to reload from disk.
    """
    code = code.lower().strip()
    if code in _loaded and not force:
        return _loaded[code]

    pack_path = _PACKS_DIR / f'{code}.json'
    if not pack_path.exists():
        # Try partial match: 'en-US' → 'en'
        base = code.split('-')[0]
        pack_path = _PACKS_DIR / f'{base}.json'
        if not pack_path.exists():
            logger.warning('Language pack not found: %s', code)
            return None

    try:
        with pack_path.open(encoding='utf-8') as f:
            pack = json.load(f)
        _loaded[code] = pack
        _load_time[code] = time.time()
        logger.info('Language pack loaded: %s (%s)', code, pack.get('name', '?'))
        return pack
    except Exception as e:
        logger.error('Failed to load language pack %s: %s', code, e)
        return None


def list_available() -> list[dict]:
    """Return list of available language packs (from JSON files on disk)."""
    packs = []
    for f in sorted(_PACKS_DIR.glob('*.json')):
        if f.name.startswith('__'):
            continue
        try:
            with f.open(encoding='utf-8') as fp:
                data = json.load(fp)
            packs.append({
                'code':       data.get('code', f.stem),
                'name':       data.get('name', f.stem),
                'name_local': data.get('name_local', f.stem),
                'flag':       data.get('flag', '🌐'),
                'rtl':        data.get('rtl', False),
                'tts_rate':   data.get('tts', {}).get('default_rate', 0.9),
                'whisper':    data.get('stt', {}).get('whisper_code', f.stem),
            })
        except Exception:
            pass
    return packs


def get_string(code: str, key: str, fallback: str = '') -> str:
    """Get a UI string from a language pack. Falls back to English → fallback."""
    pack = load_pack(code)
    if pack:
        s = pack.get('ui', {}).get(key, '')
        if s:
            return s
    # English fallback
    en = load_pack('en')
    if en:
        s = en.get('ui', {}).get(key, '')
        if s:
            return s
    return fallback


def get_tts_config(code: str) -> dict:
    """Return TTS settings for a language code."""
    pack = load_pack(code) or load_pack('en') or {}
    return pack.get('tts', {
        'default_rate': 0.88,
        'slow_rate': 0.62,
        'accessibility_rate': 0.50,
        'default_pitch': 1.0,
        'default_volume': 0.95,
        'pause_between_sentences_ms': 350,
        'accessibility_pause_ms': 700,
        'voice_preference': ['en-US'],
    })


def get_whisper_code(lang_code: str) -> str:
    """Return the Whisper language code for a given language code."""
    pack = load_pack(lang_code)
    if pack:
        return pack.get('stt', {}).get('whisper_code', lang_code.split('-')[0])
    return lang_code.split('-')[0]


def get_wake_phrases(lang_code: str) -> list[str]:
    """Return wake phrases for a language, always include English fallback."""
    phrases = set()
    pack = load_pack(lang_code)
    if pack:
        phrases.update(pack.get('wake_phrases', []))
    # Always include English wake phrases
    en = load_pack('en')
    if en:
        phrases.update(en.get('wake_phrases', []))
    return list(phrases)


def get_confirm_phrases(lang_code: str) -> list[str]:
    """Return confirmation phrases (yes equivalents) for a language."""
    phrases = set()
    for code in [lang_code, 'en']:
        pack = load_pack(code)
        if pack:
            phrases.update(pack.get('voice_commands', {}).get('confirm', []))
    return list(phrases)


def get_cancel_phrases(lang_code: str) -> list[str]:
    """Return cancel phrases (no equivalents) for a language."""
    phrases = set()
    for code in [lang_code, 'en']:
        pack = load_pack(code)
        if pack:
            phrases.update(pack.get('voice_commands', {}).get('cancel', []))
    return list(phrases)


def get_repeat_phrases(lang_code: str) -> list[str]:
    """Return repeat-request phrases for a language."""
    phrases = set()
    for code in [lang_code, 'en']:
        pack = load_pack(code)
        if pack:
            phrases.update(pack.get('voice_commands', {}).get('repeat', []))
    return list(phrases)


# ── Language detection ────────────────────────────────────────────────────────

def detect_text_language(text: str) -> str:
    """
    Detect language from text. Returns ISO 639-1 code.
    Uses langdetect if installed, falls back to 'en'.
    Always offline.
    """
    if not text or len(text) < 5:
        return 'en'
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0  # deterministic
        code = detect(text)
        return code
    except ImportError:
        logger.debug('langdetect not installed — using default language en')
    except Exception as e:
        logger.debug('Language detection error: %s', e)
    return 'en'


def detect_speech_language(audio_path: str, whisper_model=None) -> str:
    """
    Detect language from audio using Whisper's built-in detection.
    Returns ISO 639-1 code. Falls back to 'en'.
    """
    if whisper_model is None:
        try:
            from ai_services.speech_service import _load_whisper
            whisper_model = _load_whisper('base')
        except Exception:
            return 'en'
    if whisper_model is None:
        return 'en'
    try:
        import whisper
        import numpy as np
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)
        mel   = whisper.log_mel_spectrogram(audio).to(whisper_model.device)
        _, probs = whisper_model.detect_language(mel)
        detected = max(probs, key=probs.get)
        logger.info('Whisper detected language: %s (p=%.2f)', detected, probs[detected])
        return detected
    except Exception as e:
        logger.warning('Speech language detection failed: %s', e)
        return 'en'


# ── Translation ───────────────────────────────────────────────────────────────

async def translate_text(
    text:        str,
    source_lang: str,
    target_lang: str,
    use_cloud:   bool = True,
) -> str:
    """
    Translate text between languages.
    Uses local LLM first, cloud for quality.
    Returns original text if translation fails.
    """
    if source_lang == target_lang:
        return text
    if len(text) < 2:
        return text

    prompt = (
        f'Translate the following text from {source_lang} to {target_lang}.\n'
        f'This is a laboratory/medical context. Keep medical terms precise.\n'
        f'Return ONLY the translated text, nothing else.\n\n'
        f'Text to translate:\n{text}'
    )

    # Try cloud first for quality
    if use_cloud:
        try:
            from ai_services.cloud_llm import generate, is_available
            if await is_available():
                resp = await generate(prompt, max_tokens=500, use_cache=True)
                if resp.content and not resp.error:
                    return resp.content.strip()
        except Exception as e:
            logger.debug('Cloud translation failed: %s', e)

    # Local LLM fallback
    try:
        from ai_services.local_llm import generate as local_gen, is_available as local_ok
        if await local_ok():
            resp = await local_gen(prompt, max_tokens=300, use_cache=True)
            if resp.content and not resp.error:
                return resp.content.strip()
    except Exception as e:
        logger.debug('Local translation failed: %s', e)

    logger.warning('Translation failed %s→%s, returning original', source_lang, target_lang)
    return text


async def translate_response_to_user_lang(
    text:      str,
    user_lang: str,
    ai_lang:   str = 'en',
) -> str:
    """Translate an AI response to the user's preferred language."""
    if user_lang == ai_lang or user_lang == 'en':
        return text
    return await translate_text(text, ai_lang, user_lang)


# ── Language-aware OCR ────────────────────────────────────────────────────────

def get_tesseract_lang(lang_code: str) -> str:
    """
    Map ISO 639-1 code to Tesseract OCR language code.
    Tesseract uses 3-letter codes and separate langdata files.
    """
    mapping = {
        'en': 'eng',
        'fr': 'fra',
        'rw': 'kin',    # Kinyarwanda
        'sw': 'swa',    # Swahili
        'am': 'amh',    # Amharic
        'ar': 'ara',
        'zh': 'chi_sim',
        'pt': 'por',
        'es': 'spa',
    }
    base = lang_code.split('-')[0].lower()
    return mapping.get(base, 'eng')


# ── Reload / update ───────────────────────────────────────────────────────────

def reload_pack(code: str) -> bool:
    """Hot-reload a language pack from disk without restarting the server."""
    pack = load_pack(code, force=True)
    return pack is not None


def pack_info() -> dict:
    """Return service info: loaded packs, available packs."""
    return {
        'loaded':    list(_loaded.keys()),
        'available': [p['code'] for p in list_available()],
        'packs_dir': str(_PACKS_DIR),
    }


# ── Pre-load defaults at import time ─────────────────────────────────────────

for _default_lang in ('en', 'fr', 'rw'):
    load_pack(_default_lang)
