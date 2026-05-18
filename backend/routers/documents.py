"""
ALIS-X Document Reading API
============================
Endpoints for reading any document format via the AI reading services.
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ai_services.document_reader import read_bytes, supported_formats, detect_format
from ai_services.ocr_service import ocr, extract_lab_results_from_image, health_status as ocr_health
from ai_services.barcode_service import decode_bytes, parse_lab_code, health_status as bc_health
from ai_services.instrument_parser import parse, parse_file
from core.database import get_db
from core.security import get_current_user
from models.user import User

router = APIRouter(prefix='/documents', tags=['Document Reading'])

MAX_FILE_MB = 50


# ── Schemas ───────────────────────────────────────────────────────────────────

class InstrumentParseIn(BaseModel):
    content:       str
    filename:      str = ''
    instrument_id: str = ''
    format:        str = ''


# ── Universal reader ──────────────────────────────────────────────────────────

@router.post('/read')
async def read_document(
    file:        UploadFile = File(...),
    ai_enhance:  bool       = Form(False),
    cloud_ok:    bool       = Form(False),
    lang:        str        = Form('en'),
    max_pages:   int        = Form(30),
    user:        User       = Depends(get_current_user),
) -> dict:
    """
    Universal document reader.
    Supports: PDF, DOCX, XLSX, CSV, XML, HL7, JSON, YAML, TXT, Markdown, HTML, DICOM, audio.
    Returns: {ok, text, tables, structured, metadata, format, reader_used, ai_enhanced}
    """
    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, f'File too large (max {MAX_FILE_MB} MB)')

    result = await read_bytes(
        content   = content,
        filename  = file.filename or 'upload',
        mime_type = file.content_type or '',
        ai_enhance= ai_enhance,
        cloud_ok  = cloud_ok and user.role in ('super_admin', 'lab_manager', 'pathologist'),
        lang      = lang,
        max_pages = max_pages,
    )
    return result.to_dict()


@router.get('/formats')
async def list_supported_formats(
    _u: User = Depends(get_current_user),
) -> dict:
    """List all supported document formats and their reader status."""
    return {'formats': supported_formats()}


@router.get('/detect-format')
async def detect_document_format(
    filename:  str,
    mime_type: str = '',
    _u:        User = Depends(get_current_user),
) -> dict:
    """Detect document format from filename/MIME type."""
    fmt = detect_format(filename, mime_type)
    return {'filename': filename, 'detected_format': fmt}


# ── OCR endpoints ─────────────────────────────────────────────────────────────

@router.post('/ocr')
async def ocr_image(
    image:    UploadFile = File(...),
    lang:     str        = Form('en'),
    task:     str        = Form('general'),
    cloud_ok: bool       = Form(False),
    enhance:  bool       = Form(True),
    user:     User       = Depends(get_current_user),
) -> dict:
    """
    OCR an image file.
    Pipeline: Tesseract → EasyOCR → Claude Vision (if cloud_ok).
    task: general | lab_report | invoice | form
    """
    import tempfile
    from pathlib import Path

    content = await image.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(413, 'Image too large (max 20 MB)')

    suffix = Path(image.filename or 'img.jpg').suffix or '.jpg'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        tmp = f.name

    try:
        result = await ocr(
            tmp,
            lang     = lang,
            task     = task,
            cloud_ok = cloud_ok and user.role in ('super_admin', 'lab_manager', 'pathologist'),
            enhance  = enhance,
        )
        return result.to_dict()
    finally:
        Path(tmp).unlink(missing_ok=True)


@router.post('/ocr/extract-lab-results')
async def extract_lab_results(
    image:    UploadFile = File(...),
    lang:     str        = Form('en'),
    cloud_ok: bool       = Form(False),
    user:     User       = Depends(get_current_user),
) -> dict:
    """
    OCR a lab report image and extract structured test results.
    Returns: {ok, results: [{test_name, value, unit, reference_range, flag}], raw_text}
    Each result can be directly fed into the result entry system.
    """
    import tempfile
    from pathlib import Path

    content = await image.read()
    suffix  = Path(image.filename or 'report.jpg').suffix or '.jpg'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(content)
        tmp = f.name

    try:
        return await extract_lab_results_from_image(
            tmp,
            lang     = lang,
            cloud_ok = cloud_ok and user.role in ('super_admin', 'lab_manager'),
        )
    finally:
        Path(tmp).unlink(missing_ok=True)


@router.get('/ocr/health')
async def ocr_health_check(_u: User = Depends(get_current_user)) -> dict:
    """Check which OCR engines are available."""
    return ocr_health()


# ── Barcode endpoints ─────────────────────────────────────────────────────────

@router.post('/barcode/decode')
async def decode_barcode(
    image:    UploadFile = File(...),
    cloud_ok: bool       = Form(False),
    user:     User       = Depends(get_current_user),
) -> dict:
    """
    Decode barcode or QR code from image.
    Pipeline: pyzbar → OpenCV → zxing → Claude Vision.
    Returns: {ok, codes: [{data, type}], primary}
    """
    content = await image.read()
    result  = await decode_bytes(
        content,
        filename = image.filename or 'barcode.jpg',
        cloud_ok = cloud_ok,
    )
    d = result.__dict__.copy()
    # Parse lab codes
    if result.primary:
        d['lab_code'] = parse_lab_code(result.primary)
    return d


@router.post('/barcode/parse-code')
async def parse_barcode_text(
    barcode: str,
    _u:      User = Depends(get_current_user),
) -> dict:
    """Parse a raw barcode string into lab identifiers (SID/LID/PID)."""
    return parse_lab_code(barcode)


@router.get('/barcode/health')
async def barcode_health(_u: User = Depends(get_current_user)) -> dict:
    """Check barcode decoder availability."""
    return bc_health()


# ── Instrument output endpoints ───────────────────────────────────────────────

@router.post('/instrument/parse')
async def parse_instrument_text(
    body: InstrumentParseIn,
    user: User = Depends(get_current_user),
) -> dict:
    """
    Parse lab instrument output from raw text content.
    Supports: ASTM E1394, HL7 ORU, FHIR DiagnosticReport, GeneXpert XML, CSV, TSV.
    Returns: {ok, results: [{test_code, test_name, value, unit, flag, ...}]}
    """
    result = parse(
        content       = body.content,
        filename      = body.filename,
        instrument_id = body.instrument_id,
        fmt           = body.format or '',
    )
    return result.to_dict()


@router.post('/instrument/upload')
async def upload_instrument_file(
    file:          UploadFile = File(...),
    instrument_id: str        = Form(''),
    user:          User       = Depends(get_current_user),
) -> dict:
    """
    Upload and parse an instrument output file.
    Supports: .csv, .txt, .xml, .hl7, .json files.
    """
    import tempfile
    from pathlib import Path

    content = await file.read()
    suffix  = Path(file.filename or 'result.csv').suffix or '.csv'

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode='wb') as f:
        f.write(content)
        tmp = f.name

    try:
        result = await parse_file(tmp, instrument_id=instrument_id)
        return result.to_dict()
    finally:
        Path(tmp).unlink(missing_ok=True)


@router.post('/instrument/import-to-results')
async def import_instrument_to_results(
    file:          UploadFile = File(...),
    lab_req_id:    int        = Form(...),
    instrument_id: str        = Form(''),
    auto_validate: bool       = Form(False),
    user:          User       = Depends(get_current_user),
    db:            Session    = Depends(get_db),
) -> dict:
    """
    Parse instrument file and import results into the lab result system.
    Attaches results to the given lab request ID.
    auto_validate=False means results enter as PENDING validation (recommended).
    """
    import tempfile
    from pathlib import Path
    from datetime import datetime, timezone

    # Check lab request exists
    from models.laboratory import LabRequest, LabResult
    req = db.query(LabRequest).filter(LabRequest.id == lab_req_id).first()
    if not req:
        raise HTTPException(404, f'Lab request {lab_req_id} not found')

    content = await file.read()
    suffix  = Path(file.filename or 'result.csv').suffix or '.csv'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode='wb') as f:
        f.write(content)
        tmp = f.name

    imported = 0
    errors   = []
    try:
        parse_result = await parse_file(tmp, instrument_id=instrument_id)
        if not parse_result.ok:
            raise HTTPException(422, f'Parse failed: {"; ".join(parse_result.errors)}')

        for ir in parse_result.results:
            try:
                # Check rules engine for auto-flagging
                from ai_services.rules_engine import check_result, auto_flag
                if ir.numeric_value is not None and (ir.flag == 'N' or not ir.flag):
                    ir.flag = auto_flag(ir.test_code, ir.numeric_value)

                rules = check_result(
                    test_code = ir.test_code,
                    value     = ir.numeric_value or 0,
                    unit      = ir.unit,
                    flag      = ir.flag,
                    db        = db,
                )

                result_obj = LabResult(
                    lab_request_id   = lab_req_id,
                    pid              = req.pid,
                    lid              = req.lid,
                    sid              = ir.sample_id or req.lab_id,
                    result_value     = ir.value,
                    numeric_value    = ir.numeric_value,
                    unit             = ir.unit,
                    flag             = ir.flag,
                    result_source    = 'AUTOMATED',
                    instrument_id    = instrument_id or ir.instrument_id,
                    entry_mode       = 'AUTO_STREAM',
                    is_validated     = False,   # always requires human validation
                    status           = 'PENDING',
                    entered_by_id    = user.id,
                    entered_at       = datetime.now(timezone.utc),
                    is_critical      = rules.is_critical,
                    notes            = ir.comment or None,
                )
                db.add(result_obj)
                imported += 1
            except Exception as e:
                errors.append(f'Result {ir.test_code}: {e}')

        db.commit()
        return {
            'ok':           True,
            'imported':     imported,
            'total_parsed': len(parse_result.results),
            'errors':       errors,
            'message':      f'{imported} results imported. All require validation before release.',
        }
    finally:
        Path(tmp).unlink(missing_ok=True)


# ── AI-powered document Q&A ───────────────────────────────────────────────────

@router.post('/ask')
async def ask_about_document(
    file:      UploadFile = File(...),
    question:  str        = Form(...),
    lang:      str        = Form('en'),
    cloud_ok:  bool       = Form(True),
    user:      User       = Depends(get_current_user),
) -> dict:
    """
    Upload a document and ask the AI a question about it.
    Reads the document first, then queries local/cloud LLM with the content.
    Example: upload a PDF lab report and ask 'What is the patient's potassium level?'
    """
    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(413, f'File too large (max {MAX_FILE_MB} MB)')

    # Read the document
    read_result = await read_bytes(
        content,
        filename  = file.filename or 'doc',
        mime_type = file.content_type or '',
        lang      = lang,
    )
    if not read_result.ok or not read_result.text:
        return {
            'ok':    False,
            'error': read_result.error or 'Could not read document',
            'answer':''
        }

    # Build prompt
    doc_excerpt = read_result.text[:3000]
    prompt = (
        f'Document content:\n\n{doc_excerpt}\n\n'
        f'---\n'
        f'Question: {question}\n\n'
        f'Answer concisely and precisely based only on the document content. '
        f'If the information is not in the document, say so clearly.'
    )

    answer = ''
    layer  = 'unavailable'

    # Try cloud first for quality
    if cloud_ok:
        try:
            from ai_services.cloud_llm import generate as cloud_gen, is_available as cloud_avail
            if await cloud_avail():
                resp = await cloud_gen(prompt, max_tokens=600)
                if resp.ok:
                    answer = resp.content
                    layer  = 'cloud_llm'
        except Exception:
            pass

    # Local LLM fallback
    if not answer:
        try:
            from ai_services.local_llm import generate, is_available
            if await is_available():
                resp = await generate(prompt, max_tokens=400, timeout_s=20.0)
                if resp.ok:
                    answer = resp.content
                    layer  = 'local_llm'
        except Exception:
            pass

    if not answer:
        answer = 'AI is unavailable. Please read the document manually.'
        layer  = 'fallback'

    return {
        'ok':          True,
        'question':    question,
        'answer':      answer,
        'layer':       layer,
        'doc_format':  read_result.format,
        'doc_reader':  read_result.reader_used,
        'word_count':  read_result.word_count,
    }
