"""
ALIS-X AI Orchestrator
======================
Central router that decides WHICH AI service handles each task.

Decision hierarchy (offline-first):
  1. Rules Engine   — always first; deterministic; zero-latency
  2. Local LLM      — Ollama; CPU-capable; offline
  3. Cloud LLM      — enhancement; fails gracefully to local/rules
  4. Speech Service — Whisper; local-first
  5. Vision Service — async queued; offline + optional cloud

Routing table by task type:
  ┌─────────────────────┬─────────────────────────────────────────┐
  │ Task type           │ Service chain                           │
  ├─────────────────────┼─────────────────────────────────────────┤
  │ FLAG_CHECK          │ Rules Engine only                       │
  │ INVENTORY_ALERT     │ Rules Engine only                       │
  │ SOP_ALERT           │ Rules Engine only                       │
  │ BASIC_INTERPRET     │ Rules → Local LLM fallback              │
  │ REFLEX_SUGGEST      │ Rules (DB) → Local LLM if no DB match   │
  │ VOICE_COMMAND       │ Speech rules → Local LLM NLU            │
  │ SPEECH_TO_TEXT      │ Whisper local                           │
  │ COMMAND_PARSE       │ Speech rules → Local LLM                │
  │ PANEL_ANALYSIS      │ Rules → Local LLM → Cloud (waterfall)  │
  │ CLINICAL_REASON     │ Local LLM → Cloud preferred             │
  │ EPIDEMIC_ANALYSIS   │ Rules signal → Cloud intelligence       │
  │ DRUG_INTERACTION    │ Cloud preferred → Local fallback        │
  │ ADVANCED_SUMMARY    │ Cloud preferred → Local fallback        │
  │ SLIDE_ANALYSIS      │ Vision service (async)                  │
  │ SMEAR_ANALYSIS      │ Vision service (async)                  │
  │ XRAY_SCREEN         │ Vision service (async, cloud preferred) │
  │ REPORT_DRAFT        │ Local LLM → Cloud for full report       │
  │ CRITICAL_TRIAGE     │ Rules ALWAYS + Local LLM context        │
  └─────────────────────┴─────────────────────────────────────────┘

The orchestrator NEVER blocks. All AI calls have a timeout budget.
Medical safety rules ALWAYS run first, independently of AI availability.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from ai_services import rules_engine, local_llm, cloud_llm, speech_service, vision_service
from ai_services.schemas import (
    AILayer, AIRequest, AIResponse, RulesResult, ServiceHealth,
    SystemStatus, TaskType, VisionTask,
)

logger = logging.getLogger('orchestrator')

# ── Task → layer mapping ──────────────────────────────────────────────────────

_RULES_ONLY: frozenset[TaskType] = frozenset({
    TaskType.FLAG_CHECK,
    TaskType.INVENTORY_ALERT,
    TaskType.SOP_ALERT,
})

_LOCAL_PREFERRED: frozenset[TaskType] = frozenset({
    TaskType.BASIC_INTERPRET,
    TaskType.REFLEX_SUGGEST,
    TaskType.VOICE_COMMAND,
    TaskType.COMMAND_PARSE,
    TaskType.OFFLINE_ASSISTANT,
    TaskType.REPORT_DRAFT,
})

_CLOUD_PREFERRED: frozenset[TaskType] = frozenset({
    TaskType.CLINICAL_REASON,
    TaskType.DRUG_INTERACTION,
    TaskType.ADVANCED_SUMMARY,
    TaskType.RESEARCH_ASSIST,
    TaskType.EPIDEMIC_ANALYSIS,
})

_VISION_TASKS: frozenset[TaskType] = frozenset({
    TaskType.SLIDE_ANALYSIS,
    TaskType.SMEAR_ANALYSIS,
    TaskType.XRAY_SCREEN,
})

_DOCUMENT_TASKS: frozenset[TaskType] = frozenset({
    TaskType.READ_DOCUMENT,
    TaskType.OCR_IMAGE,
    TaskType.DECODE_BARCODE,
    TaskType.PARSE_INSTRUMENT,
    TaskType.EXTRACT_LAB_RESULTS,
    TaskType.ASK_DOCUMENT,
})

_SPEECH_TASKS: frozenset[TaskType] = frozenset({
    TaskType.SPEECH_TO_TEXT,
    TaskType.COMMAND_PARSE,
    TaskType.VOICE_COMMAND,
})

_HYBRID: frozenset[TaskType] = frozenset({
    TaskType.PANEL_ANALYSIS,
    TaskType.CRITICAL_TRIAGE,
})


# ── System status ─────────────────────────────────────────────────────────────

async def get_system_status() -> SystemStatus:
    """
    Probe all services and return current availability.
    Called by health endpoint — never blocks for more than 3s total.
    """
    async def probe_local():
        t0 = time.time()
        ok = await local_llm.is_available()
        return ServiceHealth(
            name='local_llm', available=ok,
            latency_ms=int((time.time()-t0)*1000),
            model=settings().ollama_model if ok else None,
        )

    async def probe_cloud():
        t0 = time.time()
        ok = await cloud_llm.is_available()
        return ServiceHealth(
            name='cloud_llm', available=ok,
            latency_ms=int((time.time()-t0)*1000),
            model=settings().claude_model if ok else None,
        )

    async def probe_redis():
        try:
            import redis.asyncio as redis
            r = redis.from_url('redis://localhost:6379', socket_connect_timeout=1)
            await r.ping()
            await r.aclose()
            return ServiceHealth(name='redis', available=True, latency_ms=1)
        except Exception as e:
            return ServiceHealth(name='redis', available=False, error=str(e)[:60])

    results = await asyncio.gather(probe_local(), probe_cloud(), probe_redis(),
                                   return_exceptions=True)

    local_h = results[0] if isinstance(results[0], ServiceHealth) else ServiceHealth(name='local_llm', available=False, error=str(results[0]))
    cloud_h = results[1] if isinstance(results[1], ServiceHealth) else ServiceHealth(name='cloud_llm', available=False, error=str(results[1]))
    redis_h = results[2] if isinstance(results[2], ServiceHealth) else ServiceHealth(name='redis', available=False, error=str(results[2]))

    speech_h  = ServiceHealth(name='speech',  available=speech_service.whisper_available())
    vision_h  = ServiceHealth(name='vision',  available=True)  # always available (offline CV)

    # Recommend best layer
    if cloud_h.available:
        recommended = AILayer.CLOUD
    elif local_h.available:
        recommended = AILayer.LOCAL
    else:
        recommended = AILayer.RULES

    return SystemStatus(
        offline_capable   = True,   # rules engine never fails
        rules_engine      = ServiceHealth(name='rules_engine', available=True, latency_ms=0, model='coded+db'),
        local_llm         = local_h,
        cloud_llm         = cloud_h,
        speech            = speech_h,
        vision            = vision_h,
        redis             = redis_h,
        recommended_layer = recommended,
    )


def settings():
    from core.config import get_settings
    return get_settings()


# ── Core dispatch ─────────────────────────────────────────────────────────────

async def dispatch(request: AIRequest, db=None, lang: str = 'en') -> dict[str, Any]:
    """
    Main entry point. Routes request to appropriate AI service(s).
    Always returns a dict — never raises.

    The rules engine runs for every lab-result task regardless of route.
    """
    t0 = time.time()
    task = request.task_type
    payload = request.payload

    try:
        result: dict[str, Any] = {}

        # ── Safety check for ANY command ──────────────────────────────────────
        if task == TaskType.OFFLINE_ASSISTANT or task == TaskType.VOICE_COMMAND:
            from ai_services.safety_guard import assess_command
            safety = assess_command(
                command   = payload.get('prompt', '') or payload.get('text', '') or payload.get('command', ''),
                user_id   = request.user_id or 0,
                lang      = lang,
            )
            if not safety.action_allowed and safety.level != 'safe':
                return {
                    'safety_blocked': True,
                    'danger_level':   safety.level,
                    'warning':        safety.warning_text,
                    'alternatives':   safety.alternatives,
                    'requires_hod':   safety.requires_hod,
                    'task_type':      task,
                    'total_ms':       int((time.time()-t0)*1000),
                }

        # ── Rules-only tasks ─────────────────────────────────────────────────
        if task in _RULES_ONLY:
            result = await _dispatch_rules_only(task, payload, db)

        # ── Speech tasks ─────────────────────────────────────────────────────
        elif task == TaskType.SPEECH_TO_TEXT:
            result = await _dispatch_stt(payload)

        elif task in (TaskType.VOICE_COMMAND, TaskType.COMMAND_PARSE):
            result = await _dispatch_voice_command(payload)

        # ── Vision tasks ─────────────────────────────────────────────────────
        elif task in _VISION_TASKS:
            result = await _dispatch_vision(task, payload, request.patient_id, request.lab_req_id)

        # ── Local-preferred tasks ─────────────────────────────────────────────
        elif task in _LOCAL_PREFERRED:
            result = await _dispatch_local_preferred(task, payload, db)

        # ── Cloud-preferred tasks ─────────────────────────────────────────────
        elif task in _CLOUD_PREFERRED:
            result = await _dispatch_cloud_preferred(task, payload, db)

        # ── Document reading tasks ────────────────────────────────────────────
        elif task in _DOCUMENT_TASKS:
            result = await _dispatch_document(task, payload)

        # ── Hybrid (rules → local → cloud waterfall) ──────────────────────────
        elif task in _HYBRID:
            result = await _dispatch_hybrid(task, payload, db)

        else:
            result = {'error': f'Unknown task type: {task}', 'layer': 'orchestrator'}

        result['task_type']   = task
        result['total_ms']    = int((time.time()-t0)*1000)
        result['orchestrated']= True
        return result

    except Exception as e:
        logger.error('Orchestrator dispatch error for %s: %s', task, e)
        return {
            'error':      str(e),
            'task_type':  task,
            'layer':      'orchestrator_error',
            'total_ms':   int((time.time()-t0)*1000),
            'fallback':   'rules_engine_active',
        }


# ── Dispatch implementations ──────────────────────────────────────────────────

async def _dispatch_rules_only(task: TaskType, payload: dict, db) -> dict:
    """Pure rules engine — no AI, always offline."""
    if task == TaskType.FLAG_CHECK:
        result: RulesResult = rules_engine.check_result(
            test_code = payload.get('test_code', ''),
            value     = payload.get('value', 0),
            unit      = payload.get('unit', ''),
            flag      = payload.get('flag', ''),
            sex       = payload.get('sex', ''),
            age       = int(payload.get('age', 0)),
            db        = db,
        )
        return {**result.model_dump(), 'layer': 'rules_engine'}

    if task == TaskType.INVENTORY_ALERT:
        return rules_engine.check_inventory(
            current_stock = float(payload.get('current_stock', 0)),
            daily_usage   = float(payload.get('daily_usage', 1)),
            expiry_days   = payload.get('expiry_days'),
        )

    if task == TaskType.SOP_ALERT:
        code = payload.get('test_code', '').upper()
        flag = payload.get('flag', '').upper()
        notes = rules_engine.SOP_RULES.get((code, flag), [])
        return {'sop_notes': notes, 'layer': 'rules_engine', 'found': bool(notes)}

    return {'error': f'Unknown rules task: {task}'}


async def _dispatch_stt(payload: dict) -> dict:
    """Speech-to-text via Whisper (local, async)."""
    audio_path = payload.get('audio_path', '')
    model      = payload.get('model', 'base')
    language   = payload.get('language', 'en')
    if not audio_path:
        return {'error': 'audio_path required', 'layer': 'speech'}
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        speech_service.transcribe_audio,
        audio_path, model, language,
    )
    return {**result, 'layer': 'speech_whisper'}


async def _dispatch_voice_command(payload: dict) -> dict:
    """Parse voice command text → structured action."""
    text = payload.get('text', '') or payload.get('transcript', '')
    if not text:
        return {'error': 'text or transcript required', 'layer': 'speech'}

    # Strip wake phrase if present
    if speech_service.detect_wake_phrase(text):
        text = speech_service.strip_wake_phrase(text)

    cmd = await speech_service.process_voice_command(text, use_ai_fallback=True)
    return {
        'action':     cmd.action,
        'entity':     cmd.entity,
        'parameters': cmd.parameters,
        'confidence': cmd.confidence,
        'raw_text':   cmd.raw_text,
        'layer':      'speech_rules' if cmd.confidence >= 0.8 else 'speech_llm',
    }


async def _dispatch_vision(task: TaskType, payload: dict, patient_id, lab_req_id) -> dict:
    """Queue image analysis task. Returns task_id immediately."""
    image_map = {
        TaskType.SMEAR_ANALYSIS: 'blood_smear',
        TaskType.SLIDE_ANALYSIS: 'slide',
        TaskType.XRAY_SCREEN:   'xray_cxr',
    }
    vtask = VisionTask(
        task_id    = payload.get('task_id', ''),
        image_type = image_map.get(task, payload.get('image_type', 'microscopy')),
        file_path  = payload.get('file_path', ''),
        patient_id = patient_id,
        lab_req_id = lab_req_id,
        priority   = payload.get('priority', 'routine'),
    )
    task_id = await vision_service.submit_image_task(vtask)
    return {
        'task_id':  task_id,
        'status':   'queued',
        'message':  'Image queued for analysis. Poll /ai/vision/{task_id} for result.',
        'layer':    'vision_queue',
    }


async def _dispatch_local_preferred(task: TaskType, payload: dict, db) -> dict:
    """Try local LLM; fall back to rules engine if unavailable."""

    # BASIC_INTERPRET: rules FIRST, then AI enrichment
    if task == TaskType.BASIC_INTERPRET:
        # Step 1: rules (always)
        rules_result = rules_engine.check_result(
            test_code = payload.get('test_code', ''),
            value     = payload.get('value', 0),
            unit      = payload.get('unit', ''),
            flag      = payload.get('flag', ''),
            sex       = payload.get('sex', ''),
            age       = int(payload.get('age', 0)),
            db        = db,
        )
        # Step 2: local LLM enrichment (best-effort, non-blocking)
        ai_enrichment: dict = {}
        if await local_llm.is_available():
            ai_enrichment = await local_llm.interpret_lab_result(
                test_name = payload.get('test_name', payload.get('test_code', '')),
                value     = str(payload.get('value', '')),
                unit      = payload.get('unit', ''),
                flag      = payload.get('flag', ''),
                ref_range = payload.get('ref_range', ''),
                sex       = payload.get('sex', ''),
                age       = int(payload.get('age', 0)),
            )
        return {
            'rules':        rules_result.model_dump(),
            'ai_enrichment':ai_enrichment,
            'layer':        'rules+local' if ai_enrichment else 'rules_only',
            'is_critical':  rules_result.is_critical,
            'significance': rules_result.significance,
        }

    if task == TaskType.VOICE_COMMAND:
        return await _dispatch_voice_command(payload)

    if task == TaskType.REPORT_DRAFT:
        content = await local_llm.draft_report_section(
            department       = payload.get('department', ''),
            test_results     = payload.get('results', []),
            clinical_context = payload.get('context', ''),
        )
        return {'report_text': content, 'layer': 'local_llm'}

    if task == TaskType.OFFLINE_ASSISTANT:
        resp = await local_llm.generate(
            prompt   = payload.get('prompt', ''),
            system   = payload.get('system', ''),
            use_cache= payload.get('use_cache', True),
        )
        return {'content': resp.content, 'layer': resp.layer_used, 'error': resp.error}

    return {'error': f'No local handler for {task}', 'layer': 'local'}


async def _dispatch_cloud_preferred(task: TaskType, payload: dict, db) -> dict:
    """Try cloud LLM; fall back to local LLM; then rules engine."""
    cloud_available = await cloud_llm.is_available()

    if task == TaskType.CLINICAL_REASON or task == TaskType.ADVANCED_SUMMARY:
        if cloud_available:
            return await cloud_llm.advanced_interpretation(
                panel_results    = payload.get('results', []),
                clinical_context = payload.get('context', ''),
                patient_age      = payload.get('age', 0),
                patient_sex      = payload.get('sex', ''),
            )
        # Local fallback
        resp = await local_llm.generate(payload.get('prompt', ''))
        return {'content': resp.content, 'layer': 'local_llm_fallback', 'cloud_unavailable': True}

    if task == TaskType.EPIDEMIC_ANALYSIS:
        rules_signal = payload.get('count_7d', 0) > payload.get('baseline', 1) * 2
        if cloud_available:
            return await cloud_llm.epidemic_intelligence(
                department = payload.get('department', ''),
                test_code  = payload.get('test_code', ''),
                flag       = payload.get('flag', ''),
                count_7d   = payload.get('count_7d', 0),
                baseline   = payload.get('baseline', 1.0),
            )
        return {'outbreak_signal': rules_signal, 'layer': 'rules_only', 'cloud_unavailable': True}

    if task == TaskType.DRUG_INTERACTION:
        if cloud_available:
            return await cloud_llm.drug_interaction_check(
                current_medications = payload.get('current_medications', []),
                proposed_medication = payload.get('proposed_medication', ''),
                patient_context     = payload.get('context', ''),
            )
        return {'available': False, 'message': 'Drug interaction check requires cloud. Use pharmacist review offline.'}

    if task == TaskType.RESEARCH_ASSIST:
        if cloud_available:
            resp = await cloud_llm.generate(payload.get('prompt', ''), max_tokens=1200)
            return {'content': resp.content, 'layer': 'cloud_llm'}
        return {'content': '', 'error': 'Research assistant requires cloud connectivity', 'layer': 'unavailable'}

    return {'error': f'No cloud handler for {task}'}


async def _dispatch_hybrid(task: TaskType, payload: dict, db) -> dict:
    """
    Hybrid waterfall: Rules → Local LLM → Cloud.
    Rules ALWAYS run. Higher layers are additive enrichment.
    """
    result: dict = {}

    if task == TaskType.PANEL_ANALYSIS:
        results_list = payload.get('results', [])

        # Step 1: Flag each result through rules engine
        critical_flags: list[dict] = []
        for r in results_list:
            check = rules_engine.check_result(
                test_code = r.get('test_code', ''),
                value     = r.get('value', 0),
                unit      = r.get('unit', ''),
                flag      = r.get('flag', ''),
                db        = db,
            )
            if check.is_critical:
                critical_flags.append({
                    'test_code': r.get('test_code'),
                    'value':     r.get('value'),
                    'flag':      r.get('flag'),
                    'message':   check.panic_alerts[0].message if check.panic_alerts else '',
                })

        result['critical_flags'] = critical_flags
        result['layer']          = 'rules_engine'

        # Step 2: Local LLM panel summary
        if await local_llm.is_available():
            try:
                lines = '\n'.join(
                    f"  {r.get('test_name','?')}: {r.get('value','?')} {r.get('unit','')} [{r.get('flag','N')}]"
                    for r in results_list[:15]
                )
                prompt = (
                    f'Summarise these lab results concisely:\n{lines}\n\n'
                    f'Respond in JSON: {{"pattern":"...","urgency":"IMMEDIATE|URGENT|ROUTINE",'
                    f'"summary":"1-2 sentences","at_risk":true|false}}'
                )
                resp = await local_llm.generate(prompt, max_tokens=250, timeout_s=10.0)
                import json
                try:
                    local_data = json.loads(resp.content.strip())
                    result.update(local_data)
                    result['layer'] = 'rules+local'
                except Exception:
                    result['local_summary'] = resp.content[:300]
            except Exception as e:
                logger.debug('Local panel summary failed: %s', e)

        # Step 3: Cloud advanced reasoning (best-effort)
        if await cloud_llm.is_available():
            cloud_result = await cloud_llm.advanced_interpretation(
                panel_results    = results_list,
                clinical_context = payload.get('context', ''),
                patient_age      = payload.get('age', 0),
                patient_sex      = payload.get('sex', ''),
            )
            if not cloud_result.get('error'):
                result.update({k: v for k, v in cloud_result.items() if k not in result})
                result['layer'] = 'rules+local+cloud'

        return result

    if task == TaskType.CRITICAL_TRIAGE:
        # Rules ALWAYS run for triage
        triage = rules_engine.check_result(
            test_code = payload.get('test_code', ''),
            value     = payload.get('value', 0),
            unit      = payload.get('unit', ''),
            flag      = payload.get('flag', ''),
            db        = db,
        )
        result = {**triage.model_dump(), 'layer': 'rules_engine'}

        # Sepsis screen if multiple results provided
        if payload.get('run_sepsis_screen'):
            sepsis = rules_engine.sepsis_screen(
                wbc             = payload.get('wbc'),
                temp_c          = payload.get('temp_c'),
                hr              = payload.get('hr'),
                rr              = payload.get('rr'),
                crp             = payload.get('crp'),
                lactate         = payload.get('lactate'),
                culture_positive= payload.get('culture_positive', False),
            )
            result['sepsis_screen'] = sepsis

        # Local LLM context if critical
        if triage.is_critical and await local_llm.is_available():
            local_context = await local_llm.interpret_lab_result(
                test_name = payload.get('test_name', payload.get('test_code', '')),
                value     = str(payload.get('value', '')),
                unit      = payload.get('unit', ''),
                flag      = payload.get('flag', 'HH'),
            )
            result['ai_context'] = local_context
            result['layer']      = 'rules+local'

        return result

    return {'error': f'No hybrid handler for {task}'}


# ── Convenience wrappers (backward-compat with old ai_engine API) ─────────────

async def _dispatch_document(task: TaskType, payload: dict) -> dict:
    """Route document reading tasks to appropriate service."""
    if task == TaskType.READ_DOCUMENT:
        from ai_services.document_reader import read
        r = await read(
            path       = payload.get('path', ''),
            mime_type  = payload.get('mime_type', ''),
            ai_enhance = payload.get('ai_enhance', False),
            cloud_ok   = payload.get('cloud_ok', False),
            lang       = payload.get('lang', 'en'),
        )
        return r.to_dict()

    if task == TaskType.OCR_IMAGE:
        from ai_services.ocr_service import ocr
        r = await ocr(
            image_path = payload.get('path', ''),
            lang       = payload.get('lang', 'en'),
            task       = payload.get('task', 'general'),
            cloud_ok   = payload.get('cloud_ok', False),
        )
        return r.to_dict()

    if task == TaskType.DECODE_BARCODE:
        from ai_services.barcode_service import decode
        r = await decode(
            image_path = payload.get('path', ''),
            cloud_ok   = payload.get('cloud_ok', False),
        )
        d = r.__dict__.copy()
        if r.primary:
            from ai_services.barcode_service import parse_lab_code
            d['lab_code'] = parse_lab_code(r.primary)
        return d

    if task == TaskType.PARSE_INSTRUMENT:
        from ai_services.instrument_parser import parse
        r = parse(
            content       = payload.get('content', ''),
            filename      = payload.get('filename', ''),
            instrument_id = payload.get('instrument_id', ''),
            fmt           = payload.get('format', ''),
        )
        return r.to_dict()

    if task == TaskType.EXTRACT_LAB_RESULTS:
        from ai_services.ocr_service import extract_lab_results_from_image
        return await extract_lab_results_from_image(
            image_path = payload.get('path', ''),
            lang       = payload.get('lang', 'en'),
            cloud_ok   = payload.get('cloud_ok', False),
        )

    return {'error': f'Unknown document task: {task}'}


async def interpret_result(
    test_code: str, test_name: str, value: str, unit: str,
    flag: str, ref_range: str = '', patient_sex: str = '',
    patient_age: int = 0, db=None,
) -> dict:
    """Drop-in replacement for the old ai_engine.interpret_result()."""
    return await dispatch(
        AIRequest(
            task_type = TaskType.BASIC_INTERPRET,
            payload   = {
                'test_code': test_code, 'test_name': test_name,
                'value': value, 'unit': unit, 'flag': flag,
                'ref_range': ref_range, 'sex': patient_sex, 'age': patient_age,
            },
        ),
        db=db,
    )


async def analyze_panel(results: list[dict], db=None) -> dict:
    """Drop-in replacement for the old ai_engine.analyze_panel()."""
    return await dispatch(
        AIRequest(task_type=TaskType.PANEL_ANALYSIS, payload={'results': results}),
        db=db,
    )


async def check_epidemic(dept: str, test_code: str, flag: str,
                         count_7d: int, baseline: float) -> dict:
    """Drop-in replacement for the old ai_engine.check_epidemic()."""
    return await dispatch(
        AIRequest(
            task_type = TaskType.EPIDEMIC_ANALYSIS,
            payload   = {
                'department': dept, 'test_code': test_code,
                'flag': flag, 'count_7d': count_7d, 'baseline': baseline,
            },
        ),
    )
