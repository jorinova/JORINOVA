"""/v1/ocr — scaffold OCR endpoint. Returns 501 until backed by a real engine."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ai_microservice.models import OcrRequest, OcrResponse

router = APIRouter(prefix='/ocr', tags=['ocr'])


@router.post('', response_model=OcrResponse)
def ocr(_req: OcrRequest) -> OcrResponse:
    """
    Placeholder OCR endpoint. When the split happens, this will delegate to
    `ai_microservice.utils.ocr_pipeline` which mirrors `backend/ai_services/ocr_service.py`.
    Until then, we 501 so callers know to use the in-process service in
    `backend/ai_services/ocr_service.py`.
    """
    raise HTTPException(
        status_code = 501,
        detail      = 'OCR microservice not yet active. Use backend/ai_services/ocr_service.py.',
    )
