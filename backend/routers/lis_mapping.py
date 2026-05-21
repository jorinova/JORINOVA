"""
LIS Auto-Mapping API
====================
Three endpoints supporting fully-automatic and semi-automatic mapping of
uploaded lab request forms into LabRequests.

- POST /api/v1/lis-mapping/extract       → upload form, return draft (no writes)
- POST /api/v1/lis-mapping/confirm       → accept (possibly edited) draft, create LabRequest
- POST /api/v1/lis-mapping/auto-create   → upload + auto-create if confidence is high

Decision-support only: assisted mode is the default. Fully-automatic mode is
gated by a confidence threshold AND a role check.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ai_services import lis_mapping
from ai_services.document_reader import read_bytes
from ai_services.ocr_service import ocr as ocr_image_to_text
from core.database import get_db
from core.security import get_current_user
from models.user import User

router = APIRouter(prefix='/lis-mapping', tags=['LIS Auto-Mapping'])
log = logging.getLogger('alis_x.lis_mapping')

MAX_FILE_MB = 25
AUTO_CREATE_THRESHOLD = 0.85       # min overall_confidence for fully-auto mode
AUTO_CREATE_ROLES = {'super_admin', 'lab_manager', 'pathologist', 'receptionist'}


# ── OCR helper ────────────────────────────────────────────────────────────────

async def _ocr_upload(file: UploadFile, lang: str, cloud_ok: bool) -> tuple[str, str]:
    """Return (raw_text, source_used) from an uploaded file (image, PDF, doc)."""
    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, f'File too large (max {MAX_FILE_MB} MB)')

    suffix = Path(file.filename or 'upload').suffix.lower() or ''

    # Images go through OCR directly (Tesseract → EasyOCR → optional Claude Vision)
    if suffix in {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp'}:
        with tempfile.NamedTemporaryFile(suffix=suffix or '.jpg', delete=False) as f:
            f.write(content)
            tmp = f.name
        try:
            result = await ocr_image_to_text(tmp, lang=lang, task='form',
                                             cloud_ok=cloud_ok, enhance=True)
            return result.text, f'ocr/{result.engine}'
        finally:
            Path(tmp).unlink(missing_ok=True)

    # Everything else (PDF, DOCX, CSV …) → universal reader
    result = await read_bytes(
        content   = content,
        filename  = file.filename or 'upload',
        mime_type = file.content_type or '',
        ai_enhance= False,
        cloud_ok  = cloud_ok,
        lang      = lang,
        max_pages = 8,
    )
    return result.text or '', f'reader/{result.reader_used}'


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post('/extract')
async def extract_from_form(
    file:     UploadFile = File(...),
    lang:     str        = Form('en'),
    cloud_ok: bool       = Form(False),
    db:       Session    = Depends(get_db),
    user:     User       = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Upload a lab request form (image / PDF / DOCX) and return a structured draft
    showing extracted patient, tests, priority, doctor, ward, diagnosis, plus
    confidence scores and warnings. Performs no DB writes.
    """
    cloud = cloud_ok and user.role in {'super_admin', 'lab_manager', 'pathologist'}
    raw_text, source = await _ocr_upload(file, lang, cloud)

    if not raw_text.strip():
        raise HTTPException(422, 'No text extracted from the uploaded file.')

    draft = lis_mapping.map_request_form(db, raw_text)
    payload = draft.to_dict()
    payload['source'] = source
    return payload


@router.post('/confirm')
def confirm_draft(
    payload: dict = Body(...),
    db:      Session = Depends(get_db),
    user:    User    = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Persist a (possibly user-edited) mapping draft as a LabRequest + LabResult
    test stubs. Body shape: {draft: <draft from /extract>, auto_create_patient: bool}.
    """
    draft = payload.get('draft')
    if not isinstance(draft, dict):
        raise HTTPException(400, 'Missing "draft" object.')

    auto_create_patient = bool(payload.get('auto_create_patient', False))
    try:
        result = lis_mapping.confirm_draft(
            db, draft, user_id=user.id, auto_create_patient=auto_create_patient
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.exception('Failed to confirm LIS mapping draft')
        raise HTTPException(500, f'Confirmation failed: {e}')

    log.info('LIS mapping confirmed by user=%s lab_request_id=%s',
             user.username, result.get('lab_request_id'))
    return result


@router.post('/auto-create')
async def auto_create(
    file:                  UploadFile = File(...),
    lang:                  str        = Form('en'),
    cloud_ok:              bool       = Form(False),
    confidence_threshold:  float      = Form(AUTO_CREATE_THRESHOLD),
    auto_create_patient:   bool       = Form(False),
    db:                    Session    = Depends(get_db),
    user:                  User       = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Fully-automatic mode: upload → extract → if confidence ≥ threshold AND no
    blocking warnings, immediately create the LabRequest. Otherwise return the
    draft so the caller falls back to assisted review.

    Allowed roles: super_admin, lab_manager, pathologist, receptionist.
    """
    if user.role not in AUTO_CREATE_ROLES:
        raise HTTPException(403, 'Role not permitted to use auto-create.')

    cloud = cloud_ok and user.role in {'super_admin', 'lab_manager', 'pathologist'}
    raw_text, source = await _ocr_upload(file, lang, cloud)
    if not raw_text.strip():
        raise HTTPException(422, 'No text extracted from the uploaded file.')

    draft = lis_mapping.map_request_form(db, raw_text)
    payload = draft.to_dict()
    payload['source'] = source

    blocking = (
        draft.duplicate_of is not None
        or draft.patient.status in {'unmatched', 'new'}
        or not any(t.status == 'matched' for t in draft.tests)
        or draft.overall_confidence < confidence_threshold
    )
    if blocking:
        payload['auto_created'] = False
        payload['blocked_reason'] = (
            'duplicate'           if draft.duplicate_of is not None
            else 'patient_unmatched' if draft.patient.status in {'unmatched', 'new'}
            else 'no_tests_matched'  if not any(t.status == 'matched' for t in draft.tests)
            else 'low_confidence'
        )
        return payload

    try:
        result = lis_mapping.confirm_draft(
            db, payload, user_id=user.id, auto_create_patient=auto_create_patient
        )
    except Exception as e:
        log.exception('Auto-create failed during persistence')
        raise HTTPException(500, f'Auto-create failed: {e}')

    payload['auto_created'] = True
    payload.update(result)
    log.info('LIS auto-create completed user=%s lab_request_id=%s',
             user.username, result.get('lab_request_id'))
    return payload
