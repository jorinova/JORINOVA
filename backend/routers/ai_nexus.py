"""
ALIS-X AI Nexus Router — Refactored
=====================================
All endpoints route through the orchestrator.
No AI logic lives in this file — it is a thin HTTP adapter.

Endpoint map:
  POST /ai/dispatch           — universal orchestrator endpoint
  POST /ai/interpret          — single result interpretation (rules + AI)
  POST /ai/panel              — multi-result panel analysis
  POST /ai/flag-check         — rules-only panic value check
  POST /ai/sepsis-screen      — SIRS/qSOFA screen
  POST /ai/speech/transcribe  — Whisper STT (upload audio)
  POST /ai/speech/command     — parse voice command text
  POST /ai/vision/submit      — queue image for analysis
  GET  /ai/vision/{task_id}   — poll vision task result
  POST /ai/epidemic           — epidemic signal analysis
  POST /ai/drug-interaction   — drug interaction check (cloud)
  GET  /ai/status             — system health and available services
  GET  /ai/cache              — cache statistics
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai_services.orchestrator import dispatch, get_system_status
from ai_services.schemas import AIRequest, TaskType
from core.database import get_db
from core.security import get_current_user
from models.user import User

logger = logging.getLogger('ai_nexus_router')
router = APIRouter(prefix='/ai', tags=['AI Nexus'])


# ── Shared request/response models ────────────────────────────────────────────

class InterpretIn(BaseModel):
    test_code:   str
    test_name:   str
    value:       str
    unit:        str = ''
    flag:        str = 'N'
    ref_range:   str = ''
    patient_sex: str = ''
    patient_age: int = 0
    lab_req_id:  Optional[int] = None


class PanelIn(BaseModel):
    results: list[dict]
    context: str = ''
    age:     int = 0
    sex:     str = ''


class FlagCheckIn(BaseModel):
    test_code: str
    value:     float
    unit:      str = ''
    flag:      str = ''
    sex:       str = ''
    age:       int = 0


class SepsisScreenIn(BaseModel):
    wbc:              Optional[float] = None
    temp_c:           Optional[float] = None
    hr:               Optional[float] = None
    rr:               Optional[float] = None
    crp:              Optional[float] = None
    lactate:          Optional[float] = None
    culture_positive: bool = False


class VoiceCommandIn(BaseModel):
    text: str


class EpidemicIn(BaseModel):
    department: str
    test_code:  str
    flag:       str
    count_7d:   int
    baseline:   float


class DrugCheckIn(BaseModel):
    current_medications: list[str] = []
    proposed_medication: str
    context:             str = ''


class GenericDispatchIn(BaseModel):
    task_type:  str
    payload:    dict[str, Any] = {}
    use_cache:  bool = True
    timeout_s:  float = 30.0
    patient_id: Optional[int] = None
    lab_req_id: Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post('/dispatch')
async def universal_dispatch(
    body: GenericDispatchIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Universal endpoint — accepts any task type.
    Use this for custom integrations; prefer specific endpoints for standard tasks.
    """
    try:
        task = TaskType(body.task_type)
    except ValueError:
        raise HTTPException(400, f'Unknown task_type: {body.task_type}. '
                            f'Valid types: {[t.value for t in TaskType]}')
    request = AIRequest(
        task_type  = task,
        payload    = body.payload,
        use_cache  = body.use_cache,
        timeout_s  = body.timeout_s,
        patient_id = body.patient_id,
        lab_req_id = body.lab_req_id,
        user_id    = user.id,
    )
    return await dispatch(request, db=db)


@router.post('/interpret')
async def interpret_result(
    body: InterpretIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Single result interpretation.
    Rules engine runs FIRST (always offline).
    Local/cloud LLM enrichment added as available.
    """
    return await dispatch(
        AIRequest(
            task_type  = TaskType.BASIC_INTERPRET,
            payload    = body.model_dump(),
            lab_req_id = body.lab_req_id,
            user_id    = user.id,
        ),
        db=db,
    )


@router.post('/panel')
async def panel_analysis(
    body: PanelIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """Multi-result panel analysis: rules → local LLM → cloud (waterfall)."""
    return await dispatch(
        AIRequest(
            task_type = TaskType.PANEL_ANALYSIS,
            payload   = body.model_dump(),
            user_id   = user.id,
        ),
        db=db,
    )


@router.post('/flag-check')
async def flag_check(
    body: FlagCheckIn,
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
) -> dict:
    """
    Deterministic rules-only panic value check.
    No AI — always available offline. Zero latency.
    """
    return await dispatch(
        AIRequest(
            task_type = TaskType.FLAG_CHECK,
            payload   = body.model_dump(),
        ),
        db=db,
    )


@router.post('/sepsis-screen')
async def sepsis_screen(
    body: SepsisScreenIn,
    _u:   User    = Depends(get_current_user),
) -> dict:
    """
    SIRS/qSOFA-based sepsis screening heuristic.
    Runs offline, deterministic. NOT a diagnosis.
    """
    from ai_services.rules_engine import sepsis_screen as _screen
    return _screen(
        wbc             = body.wbc,
        temp_c          = body.temp_c,
        hr              = body.hr,
        rr              = body.rr,
        crp             = body.crp,
        lactate         = body.lactate,
        culture_positive= body.culture_positive,
    )


@router.post('/speech/transcribe')
async def transcribe_audio(
    audio:    UploadFile = File(...),
    language: str        = Form('en'),
    model:    str        = Form('base'),
    _u:       User       = Depends(get_current_user),
) -> dict:
    """
    Offline speech-to-text via Whisper.
    Accepts any audio file (webm, wav, mp3, ogg).
    All processing is local — no network call.
    """
    audio_bytes = await audio.read()
    if len(audio_bytes) < 512:
        raise HTTPException(400, 'Audio file too small or empty')
    return await dispatch(
        AIRequest(
            task_type = TaskType.SPEECH_TO_TEXT,
            payload   = {'audio_bytes': audio_bytes.hex(),   # serialise for dispatch
                         'language': language, 'model': model},
        ),
    )


@router.post('/speech/command')
async def voice_command(
    body: VoiceCommandIn,
    _u:   User = Depends(get_current_user),
) -> dict:
    """Parse voice command text → structured action (rules + local LLM)."""
    return await dispatch(
        AIRequest(
            task_type = TaskType.VOICE_COMMAND,
            payload   = {'text': body.text},
        ),
    )


@router.post('/vision/submit')
async def submit_vision(
    image:      UploadFile = File(...),
    image_type: str        = Form('microscopy'),
    priority:   str        = Form('routine'),
    patient_id: Optional[int] = Form(None),
    lab_req_id: Optional[int] = Form(None),
    user:       User       = Depends(get_current_user),
) -> dict:
    """
    Submit image for async analysis. Returns task_id immediately.
    Processing happens in background (online or offline CV).
    Poll GET /ai/vision/{task_id} for result.
    """
    import uuid, os
    from pathlib import Path

    # Save uploaded file to media directory
    upload_dir = Path('media') / 'vision'
    upload_dir.mkdir(parents=True, exist_ok=True)
    task_id  = str(uuid.uuid4())[:12]
    ext      = Path(image.filename or 'image.jpg').suffix or '.jpg'
    file_path= upload_dir / f'{task_id}{ext}'

    content = await image.read()
    file_path.write_bytes(content)

    return await dispatch(
        AIRequest(
            task_type  = TaskType(f'smear_analysis' if 'smear' in image_type else 'slide_analysis'),
            payload    = {
                'task_id':    task_id,
                'file_path':  str(file_path),
                'image_type': image_type,
                'priority':   priority,
            },
            patient_id = patient_id,
            lab_req_id = lab_req_id,
            user_id    = user.id,
        ),
    )


@router.get('/vision/{task_id}')
async def get_vision_result(
    task_id: str,
    _u:      User = Depends(get_current_user),
) -> dict:
    """Poll for async vision task result."""
    from ai_services.vision_service import get_task_result
    result = get_task_result(task_id)
    if result is None:
        raise HTTPException(404, f'Vision task {task_id} not found')
    return result.model_dump()


@router.post('/epidemic')
async def epidemic_analysis(
    body: EpidemicIn,
    _u:   User = Depends(get_current_user),
) -> dict:
    """Epidemic signal analysis: rules threshold + optional cloud intelligence."""
    return await dispatch(
        AIRequest(
            task_type = TaskType.EPIDEMIC_ANALYSIS,
            payload   = body.model_dump(),
        ),
    )


@router.post('/drug-interaction')
async def drug_interaction(
    body: DrugCheckIn,
    _u:   User = Depends(get_current_user),
) -> dict:
    """Drug-drug and drug-lab interaction check (cloud preferred)."""
    return await dispatch(
        AIRequest(
            task_type = TaskType.DRUG_INTERACTION,
            payload   = body.model_dump(),
        ),
    )


@router.post('/auto-flag')
async def auto_flag_result(
    test_code: str,
    value:     float,
    sex:       str = '',
    age:       int = 0,
    _u:        User = Depends(get_current_user),
) -> dict:
    """
    Compute flag automatically from coded reference ranges.
    Runs offline. Returns flag string: HH | LL | H | L | N
    """
    from ai_services.rules_engine import auto_flag, get_reference_range
    flag = auto_flag(test_code, value, sex, age)
    ref  = get_reference_range(test_code, sex, age)
    return {
        'test_code': test_code,
        'value':     value,
        'flag':      flag,
        'ref_range': {'low': ref[0], 'high': ref[1]} if ref else None,
        'layer':     'rules_engine',
    }


@router.get('/status')
async def system_status(
    _u: User = Depends(get_current_user),
) -> dict:
    """
    Full AI system health status.
    Shows which services are available and recommended layer.
    Always returns — offline_capable is always True.
    """
    status = await get_system_status()
    return status.model_dump()


@router.get('/cache')
async def cache_info(
    _u: User = Depends(get_current_user),
) -> dict:
    """Cache statistics for all AI layers."""
    from ai_services.local_llm import cache_stats as local_cache
    from ai_services.cloud_llm import cache_stats as cloud_cache
    return {
        'local_llm': local_cache(),
        'cloud_llm': cloud_cache(),
    }
