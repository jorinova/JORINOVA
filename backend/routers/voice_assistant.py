"""
Voice AI Assistant Router — JORINOVA NEXUS ALIS-X
===================================================
Endpoints for the production voice control system.

  POST /voice-ai/command     — Parse voice command, return action + speech
  GET  /voice-ai/guidance/{topic} — Get step-by-step guidance
  GET  /voice-ai/navigation  — Full navigation map for frontend
  POST /voice-ai/transcribe  — Transcribe audio blob (Whisper)
  GET  /voice-ai/status      — Voice system health check
  GET  /voice-ai/help        — List all available commands
"""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.user import User
from ai_services.voice_assistant import (
    parse_command, NAVIGATION_MAP, WORKFLOW_GUIDES,
    SYSTEM_HELP, get_greeting, get_idle_prompt,
)

log = logging.getLogger('voice_assistant_router')
router = APIRouter(prefix='/voice-ai', tags=['Voice AI Assistant'])


class CommandRequest(BaseModel):
    text:    str
    lang:    str = 'en'
    context: str = ''    # current page/module name for context


class CommandResponse(BaseModel):
    type:          str           # navigate | guide | answer | stop | repeat | ai_query
    navigate_to:   Optional[str] = None
    response_text: str = ''
    steps:         Optional[list] = None
    all_steps:     Optional[list] = None
    topic:         Optional[str]  = None
    lang:          str = 'en'
    # TTS config
    tts_rate:      float = 0.85
    tts_pitch:     float = 1.05   # slightly higher = female-leaning
    tts_volume:    float = 0.95


@router.post('/command', response_model=CommandResponse)
async def voice_command(
    body: CommandRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Process a recognised voice command.
    Returns the action type, navigation URL if needed, and the text
    the TTS engine should speak back to the user.
    """
    result = parse_command(body.text, body.lang)
    log.info('Voice command [%s] "%s" → type=%s', body.lang, body.text, result.get('type'))

    # If it's an AI query, try to answer from the AI engine
    if result.get('type') == 'ai_query':
        try:
            from services.ai_engine import ask_clinical_question
            answer = await ask_clinical_question(body.text, {'page': body.context}, body.lang)
            result['response_text'] = answer
        except Exception:
            pass  # keep fallback response

    return CommandResponse(
        type          = result.get('type', 'answer'),
        navigate_to   = result.get('navigate_to'),
        response_text = result.get('response_text', ''),
        steps         = result.get('steps'),
        all_steps     = result.get('all_steps'),
        topic         = result.get('topic'),
        lang          = result.get('lang', body.lang),
        tts_rate      = 0.82 if result.get('type') == 'guide' else 0.88,
        tts_pitch     = 1.08,
        tts_volume    = 0.95,
    )


@router.get('/guidance/{topic}')
def get_guidance(
    topic: str,
    lang:  str     = 'en',
    user:  User    = Depends(get_current_user),
) -> dict:
    """Return complete step-by-step guidance for a workflow topic."""
    guide = WORKFLOW_GUIDES.get(topic)
    if not guide:
        raise HTTPException(404, f'No guidance found for topic: {topic}')
    steps = guide.get(lang, guide.get('en', []))
    return {
        'topic':     topic,
        'lang':      lang,
        'steps':     steps,
        'step_count':len(steps),
        'intro':     steps[0] if steps else '',
    }


@router.get('/navigation')
def get_navigation(user: User = Depends(get_current_user)) -> dict:
    """Return full navigation map for the frontend voice engine."""
    return {
        key: {'url': url, 'response': resp}
        for key, (url, resp) in NAVIGATION_MAP.items()
    }


@router.get('/help')
def get_help(
    lang: str = 'en',
    user: User = Depends(get_current_user),
) -> dict:
    """Return list of available voice commands with examples."""
    examples = {
        'en': {
            'navigation': [
                "Open Hematology", "Go to Worklist", "Open Blood Bank",
                "Show me Quality Control", "Navigate to Reception", "Open Dashboard",
            ],
            'workflow_guidance': [
                "How do I receive a sample?", "Guide me through result entry",
                "How do I validate a result?", "How do I reject a sample?",
                "Explain the Levey-Jennings chart",
            ],
            'knowledge': [
                "What is a critical value?", "What are Westgard rules?",
                "What is ISO 15189?", "Explain the SID number",
                "What is the Mentzer index?", "Explain malaria GE FS",
            ],
            'system': [
                "What can you do?", "Help", "Stop", "Repeat",
            ],
        },
        'fr': {
            'navigation': [
                "Ouvrir Hématologie", "Aller à la Biochimie",
                "Ouvrir la Banque du Sang", "Réception",
            ],
            'workflow_guidance': [
                "Comment réceptionner un échantillon?",
                "Comment valider un résultat?",
                "Comment rejeter un échantillon?",
            ],
            'knowledge': [
                "Qu'est-ce qu'une valeur critique?",
                "Expliquez les règles de Westgard",
                "Qu'est-ce que l'ISO 15189?",
            ],
        },
        'rw': {
            'navigation': [
                "Fungura Hematology", "Jya ku Worklist",
                "Fungura Banki y'amaraso",
            ],
            'workflow_guidance': [
                "Nshobora gute gukiria ingano?",
                "Emeza ibisubizo",
                "Guhakana ingano",
            ],
            'knowledge': [
                "Sobanura agaciro gasumba urugero",
                "Ibindi bisobanuro bya Westgard",
            ],
        },
    }
    return {
        'greeting':  get_greeting(lang),
        'idle':      get_idle_prompt(lang),
        'commands':  examples.get(lang, examples['en']),
        'topics':    list(WORKFLOW_GUIDES.keys()),
    }


@router.post('/transcribe')
async def transcribe_audio(
    audio:    UploadFile = File(...),
    lang:     str        = Form('en'),
    user:     User       = Depends(get_current_user),
) -> dict:
    """
    Transcribe an audio blob using Whisper (offline).
    Falls back to empty string if Whisper is not installed.
    The frontend uses Web Speech API for real-time STT;
    this endpoint is a server-side backup for lab workstations
    where browser STT may be unavailable.
    """
    try:
        from ai_services.speech_service import transcribe_audio_bytes
        audio_bytes = await audio.read()
        result = await transcribe_audio_bytes(audio_bytes, lang)
        return {'transcript': result.get('text', ''), 'lang': result.get('lang', lang)}
    except Exception as e:
        log.warning('Transcription failed: %s', e)
        return {'transcript': '', 'lang': lang, 'error': str(e)}


@router.get('/status')
def voice_status(user: User = Depends(get_current_user)) -> dict:
    """Voice system component health check."""
    from ai_services.speech_service import whisper_available

    # Check TTS language support
    tts_langs = ['en-GB', 'fr-FR', 'rw']  # browser-based, always true

    return {
        'whisper_available': whisper_available(),
        'voice_assistant':   True,
        'navigation_entries':len(NAVIGATION_MAP),
        'workflow_guides':   list(WORKFLOW_GUIDES.keys()),
        'knowledge_topics':  list(SYSTEM_HELP.keys()),
        'tts_languages':     tts_langs,
        'stt_backend':       'browser_webspeech + whisper_fallback',
        'female_voice':      True,
        'wake_word':         'NEXUS',
    }
