"""/v1/llm — scaffold LLM endpoint. Returns 501 until backed by a real provider."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ai_microservice.models import LlmRequest, LlmResponse

router = APIRouter(prefix='/llm', tags=['llm'])


@router.post('/generate', response_model=LlmResponse)
def generate(_req: LlmRequest) -> LlmResponse:
    """
    Placeholder LLM endpoint. The split version will mirror the abstractions
    in `backend/ai_services/{cloud_llm,local_llm}.py` and route via the same
    'auto' fallback chain.
    """
    raise HTTPException(
        status_code = 501,
        detail      = 'LLM microservice not yet active. Use backend/ai_services/{cloud,local}_llm.py.',
    )
