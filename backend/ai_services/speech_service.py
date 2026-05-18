"""
ALIS-X Speech Service
=====================
Offline-capable speech recognition using OpenAI Whisper (local).
Also provides a rule-based command parser that works without any AI.

Architecture:
  Layer 0: Rule-based command matching (always available, zero latency)
  Layer 1: Local Whisper STT (CPU, no internet required)
  Layer 2: Local LLM NLU (for complex/ambiguous commands)
  No cloud dependency for speech — patient data stays local.

Whisper model selection by RAM availability:
  - tiny  : ~400 MB RAM — fastest, use for pilot/CPU-only
  - base  : ~750 MB RAM — balanced (recommended)
  - small : ~1.5 GB RAM — better accuracy
  - medium: ~3 GB RAM   — high accuracy (GPU preferred)
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Optional

from ai_services.schemas import ParsedCommand, VoiceCommandAction

logger = logging.getLogger('speech_service')

# ── Whisper lazy loader ───────────────────────────────────────────────────────

_whisper_model = None
_whisper_name  = 'base'   # override via env/config


def _load_whisper(model_name: str = 'base'):
    """Load Whisper only when first used. Thread-safe via GIL."""
    global _whisper_model, _whisper_name
    if _whisper_model is not None:
        return _whisper_model
    try:
        import whisper
        logger.info('Loading Whisper model "%s" …', model_name)
        t0 = time.time()
        _whisper_model = whisper.load_model(model_name)
        _whisper_name  = model_name
        logger.info('Whisper ready in %.1fs.', time.time()-t0)
        return _whisper_model
    except ImportError:
        logger.warning('openai-whisper not installed. Install: pip install openai-whisper')
        return None
    except Exception as e:
        logger.error('Whisper load failed: %s', e)
        return None


def whisper_available() -> bool:
    """Check if Whisper package is installed (does not load model)."""
    try:
        import whisper  # noqa: F401
        return True
    except ImportError:
        return False


# ── Offline STT ───────────────────────────────────────────────────────────────

def transcribe_audio(
    audio_path:  str | Path,
    model_name:  str = 'base',
    language:    str = 'en',
    task:        str = 'transcribe',   # transcribe | translate
) -> dict:
    """
    Transcribe audio file using local Whisper.
    Returns {'text': str, 'language': str, 'confidence': float, 'error': str}
    All processing is LOCAL — no network call.
    """
    result = {'text': '', 'language': language, 'confidence': 0.0, 'error': '', 'model': model_name}
    model = _load_whisper(model_name)
    if model is None:
        result['error'] = 'Whisper not available — install openai-whisper'
        return result
    try:
        t0 = time.time()
        out = model.transcribe(
            str(audio_path),
            language=language,
            task=task,
            fp16=False,   # CPU-safe
            condition_on_previous_text=False,
        )
        text = out.get('text', '').strip()
        # Average log-probability as confidence proxy
        segs = out.get('segments', [])
        if segs:
            avg_logprob = sum(s.get('avg_logprob', -1.0) for s in segs) / len(segs)
            confidence  = min(1.0, max(0.0, 1.0 + avg_logprob))
        else:
            confidence = 0.5 if text else 0.0

        result.update({
            'text':       text,
            'language':   out.get('language', language),
            'confidence': round(confidence, 3),
            'latency_ms': int((time.time()-t0)*1000),
        })
        logger.info('Whisper transcribed: "%s" (%.1fs)', text[:80], time.time()-t0)
    except Exception as e:
        result['error'] = str(e)
        logger.error('Whisper transcription error: %s', e)
    return result


def transcribe_bytes(
    audio_bytes: bytes,
    model_name:  str = 'base',
    language:    str = 'en',
) -> dict:
    """Transcribe from raw bytes (WebSocket audio stream)."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        return transcribe_audio(tmp_path, model_name, language)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ── Rule-based command parser ─────────────────────────────────────────────────
# Runs BEFORE any AI — pattern matching on transcribed text.
# Handles the most common lab voice commands with zero AI dependency.

_COMMAND_PATTERNS: list[tuple[re.Pattern, VoiceCommandAction, str]] = [
    # Patient operations
    (re.compile(r'\b(open|show|view|display)\s+(patient|record)\b', re.I),
     VoiceCommandAction.OPEN_PATIENT, 'patient'),
    (re.compile(r'\b(search|find|look up|locate)\s+(patient|record|name)\b', re.I),
     VoiceCommandAction.SEARCH_PATIENT, 'patient'),

    # Result operations
    (re.compile(r'\b(validate|approve|confirm)\s+(\w+\s+)?(result|test|report|cbc|rbc|wbc|hgb)\b', re.I),
     VoiceCommandAction.VALIDATE_RESULT, 'result'),
    (re.compile(r'\b(flag|mark|set).{0,20}(critical|urgent|stat)\b', re.I),
     VoiceCommandAction.FLAG_CRITICAL, 'result'),

    # Report operations
    (re.compile(r'\b(print|generate|export)\s+(\w+\s+)?(report|lab report|results)\b', re.I),
     VoiceCommandAction.PRINT_REPORT, 'report'),
    (re.compile(r'\brun\s+report\b', re.I),
     VoiceCommandAction.RUN_REPORT, 'report'),

    # Navigation
    (re.compile(r'\b(open|go to|navigate to|switch to)\s+(\w+)\s*(module|section|page|tab)?\b', re.I),
     VoiceCommandAction.OPEN_MODULE, 'module'),
    (re.compile(r'\b(open|go to)\s+(laboratory|lab|microbiology|biochemistry|hematology|molecular|blood bank|inventory|billing|patients|dashboard)\b', re.I),
     VoiceCommandAction.OPEN_MODULE, 'module'),

    # Note
    (re.compile(r'\b(add|write|record|note)\s+(note|comment|remark)\b', re.I),
     VoiceCommandAction.ADD_NOTE, 'note'),
]

# Extract entity name from common patterns
_ENTITY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'patient\s+(?:named?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', re.I), 'name'),
    (re.compile(r'(?:open|go to|navigate to)\s+(laboratory|lab|microbiology|biochemistry|hematology|molecular|blood bank|inventory|billing|patients|dashboard)', re.I), 'module'),
    (re.compile(r'result\s+(?:for|of)\s+([A-Za-z0-9\-\s]+)', re.I), 'result_ref'),
    (re.compile(r'report\s+(?:for|of)\s+([A-Za-z0-9\-\s]+)', re.I), 'report_ref'),
]

_MODULE_ALIASES: dict[str, str] = {
    'lab':        'laboratory',
    'micro':      'microbiology',
    'biochem':    'biochemistry',
    'haem':       'hematology',
    'hem':        'hematology',
    'mol':        'molecular',
    'blood bank': 'blood_bank',
    'inventory':  'inventory',
    'billing':    'billing',
    'patients':   'patients',
    'dashboard':  'dashboard',
    'nexus':      'dashboard',
}


def parse_command_text(text: str) -> ParsedCommand:
    """
    Rule-based NLU — no AI required.
    Handles most common lab voice commands instantly.
    Returns ParsedCommand with action, entity, and confidence.
    """
    text_clean = text.strip()
    if not text_clean:
        return ParsedCommand(action=VoiceCommandAction.UNKNOWN, raw_text=text)

    # Match action
    matched_action = VoiceCommandAction.UNKNOWN
    confidence     = 0.0

    for pattern, action, _ in _COMMAND_PATTERNS:
        if pattern.search(text_clean):
            matched_action = action
            confidence     = 0.85
            break

    # Extract entity
    entity = ''
    for ep, _etype in _ENTITY_PATTERNS:
        m = ep.search(text_clean)
        if m:
            raw_entity = m.group(1).strip()
            entity     = _MODULE_ALIASES.get(raw_entity.lower(), raw_entity)
            break

    # Module navigation: extract module from text directly if entity empty
    if matched_action == VoiceCommandAction.OPEN_MODULE and not entity:
        for alias, canonical in _MODULE_ALIASES.items():
            if alias in text_clean.lower():
                entity = canonical
                break

    return ParsedCommand(
        action     = matched_action,
        entity     = entity,
        parameters = {},
        confidence = confidence,
        raw_text   = text_clean,
    )


async def process_voice_command(
    text: str,
    use_ai_fallback: bool = True,
) -> ParsedCommand:
    """
    Full pipeline: rule-based → local LLM fallback.
    Never requires cloud.
    """
    # Layer 0: rule-based parse (always first)
    cmd = parse_command_text(text)
    if cmd.action != VoiceCommandAction.UNKNOWN and cmd.confidence >= 0.8:
        logger.debug('Voice command resolved by rules: %s', cmd.action)
        return cmd

    # Layer 1: local LLM for ambiguous commands
    if use_ai_fallback:
        try:
            from ai_services.local_llm import parse_voice_command
            ai_result = await parse_voice_command(text)
            action_str = ai_result.get('action', 'unknown')
            try:
                action = VoiceCommandAction(action_str)
            except ValueError:
                action = VoiceCommandAction.UNKNOWN
            return ParsedCommand(
                action     = action,
                entity     = ai_result.get('entity', cmd.entity),
                parameters = ai_result.get('parameters', {}),
                confidence = float(ai_result.get('confidence', 0.5)),
                raw_text   = text,
            )
        except Exception as e:
            logger.warning('LLM NLU fallback failed: %s', e)

    return cmd


# ── Supported wake phrases ────────────────────────────────────────────────────

WAKE_PHRASES = {'hello jorinova', 'hey jorinova', 'nexus', 'alis x', 'alis-x'}


def detect_wake_phrase(text: str) -> bool:
    """Check if transcribed text starts with a recognized wake phrase."""
    lower = text.lower().strip()
    return any(lower.startswith(phrase) for phrase in WAKE_PHRASES)


def strip_wake_phrase(text: str) -> str:
    """Remove wake phrase from the beginning of command text."""
    lower = text.lower()
    for phrase in sorted(WAKE_PHRASES, key=len, reverse=True):
        if lower.startswith(phrase):
            return text[len(phrase):].strip(' ,.')
    return text


# ── Health check ──────────────────────────────────────────────────────────────

def health_status() -> dict:
    return {
        'whisper_installed': whisper_available(),
        'model_loaded':      _whisper_model is not None,
        'model_name':        _whisper_name,
        'rule_parser':       True,   # always available
    }
