"""
Voice, TTS, and Language API Router
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai_services.tts_service import build_config, SpeechMode, MODE_LABELS, MODE_DESCRIPTIONS, update_user_settings, get_user_settings
from ai_services.language_service import list_available, pack_info, reload_pack, get_tts_config, detect_text_language
from ai_services.safety_guard import assess_command, handle_general_command, create_escalation, DangerLevel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.voice_settings import VoiceSettings

router = APIRouter(prefix='/voice', tags=['Voice & Language'])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text:     str
    lang:     str   = 'en'
    mode:     str   = 'normal'
    volume:   float = 0.95
    rate_mult:float = 1.0


class VoiceSettingsUpdate(BaseModel):
    language:             Optional[str]   = None
    speech_mode:          Optional[str]   = None
    speech_rate:          Optional[float] = None
    speech_volume:        Optional[float] = None
    speech_pitch:         Optional[float] = None
    accessibility_mode:   Optional[bool]  = None
    repeat_enabled:       Optional[bool]  = None
    confirmation_prompts: Optional[bool]  = None
    pause_between_ms:     Optional[int]   = None
    preferred_voice:      Optional[str]   = None
    stt_language:         Optional[str]   = None
    tts_language:         Optional[str]   = None
    report_language:      Optional[str]   = None
    critical_audio_alert: Optional[bool]  = None


class GeneralCommandRequest(BaseModel):
    command:  str
    lang:     str = 'en'
    context:  str = ''


class ConfirmDangerousRequest(BaseModel):
    command:   str
    category:  str
    cmd_hash:  str


# ── TTS endpoints ─────────────────────────────────────────────────────────────

@router.post('/tts/config')
async def get_tts_config_for_text(
    body: TTSRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """
    Build a SpeechConfig for a given text.
    The frontend uses this to configure Web Speech API TTS.
    Respects user speech mode and language preferences.
    """
    try:
        mode = SpeechMode(body.mode)
    except ValueError:
        mode = SpeechMode.NORMAL
    cfg = build_config(
        text      = body.text,
        lang      = body.lang,
        mode      = mode,
        volume    = body.volume,
        rate_mult = body.rate_mult,
        user_id   = user.id,
    )
    return cfg.to_dict()


@router.get('/tts/modes')
async def list_speech_modes(_u: User = Depends(get_current_user)) -> dict:
    """List available speech modes with descriptions."""
    return {
        mode.value: {
            'label':       MODE_LABELS[mode],
            'description': MODE_DESCRIPTIONS[mode],
        }
        for mode in SpeechMode
    }


@router.post('/tts/synthesize')
async def synthesize_audio(
    body: TTSRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """
    Generate server-side audio file (fallback when Web Speech API unavailable).
    Returns path to audio file or error if synthesis unavailable.
    """
    from ai_services.tts_service import synthesize_to_file
    import uuid
    out_path = f'/tmp/alis_tts_{uuid.uuid4().hex[:8]}.wav'
    try:
        mode = SpeechMode(body.mode)
    except ValueError:
        mode = SpeechMode.NORMAL
    result = await synthesize_to_file(body.text, body.lang, mode, out_path)
    if result:
        return {'audio_path': result, 'available': True}
    return {'available': False, 'message': 'Server-side TTS unavailable. Use Web Speech API (browser-based).'}


# ── User voice settings ───────────────────────────────────────────────────────

@router.get('/settings')
async def get_voice_settings(
    user: User = Depends(get_current_user),
    db:   Session = Depends(get_db),
) -> dict:
    """Get voice settings for the current user."""
    db_settings = db.query(VoiceSettings).filter(VoiceSettings.user_id == user.id).first()
    if db_settings:
        return {
            'language':              db_settings.language,
            'stt_language':          db_settings.stt_language,
            'tts_language':          db_settings.tts_language,
            'report_language':       db_settings.report_language,
            'speech_mode':           db_settings.speech_mode,
            'speech_rate':           db_settings.speech_rate,
            'speech_pitch':          db_settings.speech_pitch,
            'speech_volume':         db_settings.speech_volume,
            'accessibility_mode':    db_settings.accessibility_mode,
            'repeat_enabled':        db_settings.repeat_enabled,
            'confirmation_prompts':  db_settings.confirmation_prompts,
            'pause_between_ms':      db_settings.pause_between_ms,
            'preferred_voice':       db_settings.preferred_voice,
            'wake_phrase':           db_settings.wake_phrase,
            'critical_audio_alert':  db_settings.critical_audio_alert,
        }
    # Return defaults
    return {
        'language': 'en', 'stt_language': 'en', 'tts_language': 'en',
        'report_language': 'en', 'speech_mode': 'normal',
        'speech_rate': 0.88, 'speech_pitch': 1.0, 'speech_volume': 0.95,
        'accessibility_mode': False, 'repeat_enabled': True,
        'confirmation_prompts': True, 'pause_between_ms': 350,
        'preferred_voice': None, 'wake_phrase': 'hello jorinova',
        'critical_audio_alert': True,
    }


@router.patch('/settings')
async def update_voice_settings(
    body: VoiceSettingsUpdate,
    user: User = Depends(get_current_user),
    db:   Session = Depends(get_db),
) -> dict:
    """Update voice settings for the current user."""
    settings = db.query(VoiceSettings).filter(VoiceSettings.user_id == user.id).first()
    if not settings:
        settings = VoiceSettings(user_id=user.id)
        db.add(settings)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(settings, field, value)

    # Sync in-memory cache for TTS service
    update_user_settings(user.id, body.model_dump(exclude_none=True))

    db.commit()
    return {'status': 'updated', 'message': 'Voice settings saved.'}


# ── Language management ───────────────────────────────────────────────────────

@router.get('/languages')
async def list_languages(_u: User = Depends(get_current_user)) -> dict:
    """List all available language packs."""
    return {'languages': list_available(), **pack_info()}


@router.get('/languages/{code}/tts')
async def get_language_tts_config(
    code: str,
    _u:   User = Depends(get_current_user),
) -> dict:
    """Get TTS configuration for a specific language."""
    cfg = get_tts_config(code)
    if not cfg:
        raise HTTPException(404, f'Language pack not found: {code}')
    return cfg


@router.post('/languages/{code}/reload')
async def reload_language_pack(
    code:  str,
    _u:    User = Depends(get_current_user),
) -> dict:
    """Hot-reload a language pack from disk (no server restart needed)."""
    if _u.role not in ('super_admin', 'lab_manager'):
        raise HTTPException(403, 'Only lab managers can reload language packs')
    ok = reload_pack(code)
    if not ok:
        raise HTTPException(404, f'Language pack not found: {code}')
    return {'status': 'reloaded', 'code': code}


@router.post('/detect-language')
async def detect_language(
    text: str,
    _u:   User = Depends(get_current_user),
) -> dict:
    """Detect the language of a text string (offline, no network)."""
    detected = detect_text_language(text)
    return {'detected_language': detected, 'text_preview': text[:50]}


# ── General command (any request) ────────────────────────────────────────────

@router.post('/command')
async def general_voice_command(
    body: GeneralCommandRequest,
    user: User = Depends(get_current_user),
    db:   Session = Depends(get_db),
) -> dict:
    """
    Handle ANY user command via AI.
    - Safety assessment runs first (always offline)
    - Dangerous commands generate warnings
    - Blocked commands trigger HoD escalation
    - Safe commands are processed by local/cloud LLM
    - Response is translated to user's preferred language
    """
    result = await handle_general_command(
        command   = body.command,
        user_id   = user.id,
        user_role = user.role,
        lang      = body.lang,
        context   = body.context,
    )

    # If escalation required, create the record
    if result.get('safety', {}).get('requires_hod'):
        escalation = await create_escalation(
            user_id   = user.id,
            user_name = f'{user.first_name} {user.last_name}'.strip() or user.username,
            user_role = user.role,
            command   = body.command,
            category  = result.get('safety', {}).get('category', 'unknown'),
            reason    = result.get('safety', {}).get('reason', 'Safety escalation'),
            db        = db,
        )
        result['escalation'] = escalation

    # Build TTS config for response
    us = get_user_settings(user.id)
    try:
        mode = SpeechMode(us.get('mode', 'normal'))
    except ValueError:
        mode = SpeechMode.NORMAL
    tts = build_config(
        text    = result.get('response', ''),
        lang    = body.lang,
        mode    = mode,
        user_id = user.id,
    )
    result['tts_config'] = tts.to_dict()
    return result


@router.post('/command/confirm')
async def confirm_dangerous_command(
    body: ConfirmDangerousRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """
    User explicitly confirms a CAUTION/DANGEROUS action after being warned.
    Clears the repeat tracker and allows the action to proceed.
    """
    from ai_services.safety_guard import confirm_proceed
    confirm_proceed(user.id, body.category, body.cmd_hash)
    return {'status': 'confirmed', 'message': 'Action authorized after user confirmation.', 'user_id': user.id}


@router.post('/command/safety-check')
async def check_command_safety(
    command: str,
    lang:    str = 'en',
    user:    User = Depends(get_current_user),
) -> dict:
    """Check the safety level of a command before executing it."""
    assessment = assess_command(command, user.id, user.role, lang)
    return {
        'level':       assessment.level,
        'category':    assessment.category,
        'warning':     assessment.warning_text,
        'requires_confirmation': assessment.requires_confirmation,
        'requires_hod':assessment.requires_hod,
        'action_allowed': assessment.action_allowed,
        'alternatives':assessment.alternatives,
    }
