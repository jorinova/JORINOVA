"""
ALIS-X Vision Service
=====================
Asynchronous image analysis for laboratory microscopy and smear images.

Processing strategy:
  - All image tasks are QUEUED (never block the request thread)
  - Offline: lightweight rule-based descriptors + basic CV
  - Online: optional cloud vision via Claude's vision API
  - Human review is always required — AI is decision support only

Supported image types:
  - blood_smear   : RBC/WBC morphology, parasite detection
  - slide         : histology / cytology preliminary description
  - gel           : electrophoresis bands (HbA1c, protein)
  - microscopy    : gram stain, AFB stain, culture plate
  - xray_cxr      : TB screening (CXR) — cloud preferred
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from pathlib import Path
from typing import Optional

from ai_services.schemas import VisionResult, VisionTask

logger = logging.getLogger('vision_service')

# ── In-memory task tracker (replace with Redis in production) ─────────────────

_task_store: dict[str, VisionResult] = {}   # task_id → VisionResult


def _task_id() -> str:
    return str(uuid.uuid4())[:12]


# ── Offline descriptors (no AI, no network) ───────────────────────────────────
# Rule-based image quality and basic feature checks.
# These run synchronously before any AI queue.

def _basic_image_check(file_path: str) -> dict:
    """
    Validate image file and extract basic metadata.
    Returns dict with is_valid, width, height, format, file_size_kb.
    """
    result = {'is_valid': False, 'error': ''}
    path = Path(file_path)
    if not path.exists():
        result['error'] = f'File not found: {file_path}'
        return result
    if path.stat().st_size < 1024:   # < 1 KB = likely empty/corrupt
        result['error'] = 'File too small — may be corrupt'
        return result
    result['file_size_kb'] = round(path.stat().st_size / 1024, 1)
    try:
        from PIL import Image
        with Image.open(file_path) as img:
            result.update({
                'is_valid': True,
                'width':    img.width,
                'height':   img.height,
                'format':   img.format or 'unknown',
                'mode':     img.mode,
            })
    except ImportError:
        # Pillow not installed — skip validation, proceed anyway
        result['is_valid'] = True
        result['note']     = 'Pillow not installed — skipping image validation'
    except Exception as e:
        result['error'] = f'Image read error: {e}'
    return result


def _offline_blood_smear_rules(file_path: str) -> dict:
    """
    Attempt lightweight offline blood smear analysis.
    Uses basic colour histogram analysis (no ML model required).
    Returns preliminary findings or empty if Pillow not available.
    """
    findings: list[str] = []
    confidence = 0.0

    try:
        import numpy as np
        from PIL import Image

        with Image.open(file_path) as img:
            img_rgb = img.convert('RGB')
            arr = np.array(img_rgb, dtype=np.float32)

        # Very basic colour statistics
        mean_r, mean_g, mean_b = arr[:,:,0].mean(), arr[:,:,1].mean(), arr[:,:,2].mean()

        # Rough heuristics for Giemsa-stained smear
        if mean_r > 180 and mean_b < 120:
            findings.append('Predominantly eosinophilic staining pattern — may indicate RBC-dominant smear')
        if mean_b > mean_r and mean_b > 140:
            findings.append('Basophilic staining present — possible nucleated cells or platelet clumping area')

        # Colour variance (rough cellularity proxy)
        variance = arr.var()
        if variance < 500:
            findings.append('Low image variance — smear may be too thin or image quality poor')
        elif variance > 4000:
            findings.append('High image variance — dense cellular area detected')

        confidence = 0.3 if findings else 0.1
        findings.append('⚠ Offline analysis only — quantitative morphology requires manual microscopy review')

    except Exception as e:
        logger.debug('Offline smear analysis: %s', e)
        findings = ['Offline image analysis unavailable — manual review required']

    return {'findings': findings, 'confidence': confidence, 'layer': 'offline_cv'}


# ── Cloud vision analysis ─────────────────────────────────────────────────────

async def _cloud_vision_analysis(
    image_type: str,
    file_path:  str,
    context:    str = '',
) -> dict:
    """
    Send image to Claude vision API for advanced analysis.
    Returns empty if cloud unavailable — never raises.
    """
    from ai_services.cloud_llm import is_available
    if not await is_available():
        return {'error': 'Cloud vision unavailable', 'layer': 'cloud_skipped'}

    path = Path(file_path)
    if not path.exists():
        return {'error': f'Image file not found: {file_path}'}

    try:
        import base64
        import anthropic
        from core.config import get_settings
        s = get_settings()

        with open(file_path, 'rb') as f:
            img_data = base64.standard_b64encode(f.read()).decode()

        suffix_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                      '.png': 'image/png', '.webp': 'image/webp'}
        media_type = suffix_map.get(path.suffix.lower(), 'image/jpeg')

        prompts = {
            'blood_smear': (
                'This is a Giemsa-stained peripheral blood smear from a hospital laboratory.\n'
                'Describe what you observe:\n'
                '1. Overall RBC morphology (size, shape, colour, inclusions)\n'
                '2. WBC types visible and any abnormalities\n'
                '3. Platelet distribution\n'
                '4. Any parasites or inclusions (malaria, trypanosoma, etc.)\n'
                '5. Overall impression\n\n'
                'Respond in JSON: {"rbc_morphology":"...","wbc_observations":"...",'
                '"parasites_seen":true|false,"parasite_description":"...",'
                '"platelet_comment":"...","overall_impression":"...",'
                '"requires_urgent_review":true|false,"caveats":["..."]}'
            ),
            'slide': (
                'This is a histology/cytology slide from a hospital pathology department.\n'
                f'Context: {context or "no additional context"}\n'
                'Describe the cellular pattern, staining characteristics, and any notable findings.\n'
                'Respond in JSON: {"pattern":"...","cellularity":"...","notable_findings":["..."],'
                '"impression":"...","requires_pathologist_review":true}'
            ),
            'xray_cxr': (
                'This is a chest X-ray (CXR) from a hospital TB screening program.\n'
                'Screen for: cavitation, consolidation, infiltrates, pleural effusion, '
                'lymphadenopathy, miliary pattern.\n'
                'Respond in JSON: {"findings":["..."],"tb_features_present":true|false,'
                '"tb_likelihood":"low|medium|high","other_findings":["..."],'
                '"recommendation":"...","requires_radiologist_review":true}'
            ),
            'microscopy': (
                f'This is a laboratory microscopy image.\n'
                f'Image context: {context or image_type}\n'
                'Describe observable features relevant to laboratory diagnosis.\n'
                'Respond in JSON: {"observations":["..."],"key_findings":["..."],'
                '"quality_assessment":"adequate|inadequate|poor","recommendation":"..."}'
            ),
        }

        prompt_text = prompts.get(image_type, prompts['microscopy'])

        client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key)
        t0 = time.time()
        msg = await client.messages.create(
            model=s.claude_model,
            max_tokens=800,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': img_data}},
                    {'type': 'text', 'text': prompt_text},
                ],
            }],
        )
        raw = msg.content[0].text.strip() if msg.content else ''
        import json
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {'raw_text': raw[:500]}
        result['layer']      = 'cloud_vision'
        result['latency_ms'] = int((time.time()-t0)*1000)
        result['requires_human_review'] = True
        return result

    except Exception as e:
        logger.error('Cloud vision error: %s', e)
        return {'error': str(e), 'layer': 'cloud_vision_failed'}


# ── Public API ────────────────────────────────────────────────────────────────

async def submit_image_task(task: VisionTask) -> str:
    """
    Submit image for analysis. Returns task_id immediately.
    Processing happens asynchronously in background.
    """
    task_id = task.task_id or _task_id()

    # Initial pending result
    _task_store[task_id] = VisionResult(
        task_id=task_id,
        findings=['Analysis queued — processing in background'],
        confidence=0.0,
        layer_used='pending',
        requires_review=True,
    )

    # Validate image first (synchronous, fast)
    check = _basic_image_check(task.file_path)
    if not check.get('is_valid'):
        _task_store[task_id] = VisionResult(
            task_id=task_id,
            findings=[f'Image validation failed: {check.get("error", "unknown")}'],
            confidence=0.0,
            layer_used='validation',
            requires_review=True,
            raw_output=check,
        )
        return task_id

    # Schedule background processing
    asyncio.create_task(_process_image_task(task_id, task))
    return task_id


async def _process_image_task(task_id: str, task: VisionTask) -> None:
    """Background coroutine: offline analysis first, then optionally cloud."""
    try:
        # Step 1: offline analysis
        if task.image_type in ('blood_smear', 'smear'):
            offline_result = _offline_blood_smear_rules(task.file_path)
        else:
            offline_result = {
                'findings':   ['Offline analysis: visual inspection recommended'],
                'confidence': 0.1,
                'layer':      'offline_rules',
            }

        findings   = offline_result.get('findings', [])
        confidence = offline_result.get('confidence', 0.1)
        layer      = 'offline'

        # Step 2: cloud vision (if online and not stat-priority waiting)
        cloud_result = {}
        from ai_services.cloud_llm import is_available
        if await is_available():
            cloud_result = await _cloud_vision_analysis(task.image_type, task.file_path)
            if not cloud_result.get('error'):
                cloud_findings = cloud_result.get('findings', []) or cloud_result.get('observations', [])
                if cloud_findings:
                    findings = cloud_findings
                confidence = 0.65
                layer      = 'cloud_vision'

        _task_store[task_id] = VisionResult(
            task_id=task_id,
            findings=findings,
            confidence=confidence,
            layer_used=layer,
            requires_review=True,   # always — AI is decision support
            raw_output={**offline_result, **cloud_result},
        )
        logger.info('Vision task %s complete (layer=%s)', task_id, layer)

    except Exception as e:
        logger.error('Vision task %s failed: %s', task_id, e)
        _task_store[task_id] = VisionResult(
            task_id=task_id,
            findings=['Analysis failed — manual review required'],
            confidence=0.0,
            layer_used='error',
            requires_review=True,
            raw_output={'error': str(e)},
        )


def get_task_result(task_id: str) -> Optional[VisionResult]:
    """Poll for vision task result. Returns None if unknown task_id."""
    return _task_store.get(task_id)


def clear_completed_tasks(older_than_hours: int = 24) -> int:
    """Housekeeping — remove old completed tasks from in-memory store."""
    # Simple implementation: clear all (in production use Redis TTL)
    count = len(_task_store)
    _task_store.clear()
    return count


def health_status() -> dict:
    pillow_ok = False
    try:
        from PIL import Image   # noqa: F401
        pillow_ok = True
    except ImportError:
        pass
    return {
        'pillow_installed': pillow_ok,
        'queued_tasks':     len(_task_store),
        'cloud_vision':     'available when cloud LLM is connected',
        'offline_capable':  True,
    }
