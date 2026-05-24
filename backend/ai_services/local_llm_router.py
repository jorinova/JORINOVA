"""
Local LLM Task Router
=====================
Picks the right Ollama worker for each task type, with automatic fallback
down the worker pool if the chosen model fails (unavailable, OOM, timeout).

Worker pool (configured in core/config.py, overridable via .env):

    fast      → phi3:mini      — structured output, JSON, low latency
    deep      → mistral        — clinical interpretation, multi-hop reasoning
    chat      → nous-hermes    — conversational narration, training scripts
    general   → llama3         — anything not specialised
    fallback  → tinyllama      — always-on safety net (small, fast, low quality)

Public API:

    await route(task='fast' | 'deep' | 'chat' | 'general', prompt=..., ...)
    → returns AIResponse from the first model that succeeds.

The router never raises; an unrecoverable failure surfaces as an empty
AIResponse with `error` set. Callers can then degrade to a non-LLM path
(e.g. the stub-fallback in training_generator.py).
"""
from __future__ import annotations

import logging
from typing import Literal, Optional

from ai_services import local_llm
from ai_services.schemas import AIResponse, AILayer
from core.config import get_settings


TaskKind = Literal['fast', 'deep', 'chat', 'general', 'fallback']

logger = logging.getLogger('alis_x.llm_router')


def model_for_task(task: TaskKind) -> str:
    """Resolve a task kind to a concrete Ollama model name (from settings)."""
    s = get_settings()
    return {
        'fast':     s.ollama_model_fast,
        'deep':     s.ollama_model_deep,
        'chat':     s.ollama_model_chat,
        'general':  s.ollama_model_general,
        'fallback': s.ollama_model_fallback,
    }.get(task, s.ollama_model)


# Fallback ladder — when the chosen worker fails, walk this list. Each task
# kind has a different preferred order so we don't, say, retry a chat task
# on a tiny model before trying a richer one.
_FALLBACK_LADDER: dict[TaskKind, tuple[TaskKind, ...]] = {
    'fast':     ('fast',     'general', 'chat',    'fallback'),
    'deep':     ('deep',     'general', 'chat',    'fast',    'fallback'),
    'chat':     ('chat',     'general', 'fast',    'fallback'),
    'general':  ('general',  'fast',    'chat',    'fallback'),
    'fallback': ('fallback',),
}


def _ladder(task: TaskKind) -> list[str]:
    """Resolve a task to its de-duplicated model fallback ladder."""
    seen: set[str] = set()
    out:  list[str] = []
    for kind in _FALLBACK_LADDER.get(task, ('fast', 'fallback')):
        model = model_for_task(kind)
        if model and model not in seen:
            seen.add(model)
            out.append(model)
    return out


async def route(
    task:       TaskKind,
    prompt:     str,
    system:     str   = '',
    max_tokens: int   = 1024,
    temperature:float = 0.15,
    timeout_s:  Optional[float] = None,
    use_cache:  bool  = True,
) -> AIResponse:
    """
    Run a prompt through the router. Tries the task's preferred model first,
    walks the fallback ladder on failure. Returns the AIResponse of the first
    success, or the last error if everything fails.
    """
    last: Optional[AIResponse] = None

    for model in _ladder(task):
        resp = await local_llm.generate(
            prompt      = prompt,
            system      = system,
            max_tokens  = max_tokens,
            temperature = temperature,
            timeout_s   = timeout_s,
            use_cache   = use_cache,
            model       = model,
        )
        last = resp
        if resp.content and not resp.error:
            if resp.cached:
                logger.debug('Router cache-hit task=%s model=%s', task, model)
            else:
                logger.info(
                    'Router task=%s model=%s latency=%dms',
                    task, model, resp.latency_ms,
                )
            return resp

        logger.warning(
            'Router model=%s failed for task=%s: %s — walking ladder',
            model, task, (resp.error or 'no content')[:120],
        )

    # All models failed
    if last is None:
        last = AIResponse(
            content='', layer_used=AILayer.LOCAL,
            error='No models available in router ladder',
        )
    return last


def ladder_for(task: TaskKind) -> list[str]:
    """Public helper — useful for /api/v1/training/diagnostics or admin pages."""
    return _ladder(task)
