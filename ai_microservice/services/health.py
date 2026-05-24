"""/v1/health — scaffold health endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from ai_microservice import __version__
from ai_microservice.models import HealthResponse

router = APIRouter(tags=['health'])


@router.get('/health', response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status     = 'ok',
        version    = __version__,
        components = {
            'ocr':  'not-implemented',
            'llm':  'not-implemented',
        },
    )
