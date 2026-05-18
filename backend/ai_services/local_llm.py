"""
ALIS-X Local LLM Service
========================
Wraps Ollama (Phi-3 mini / Mistral 7B quantized).
Designed for CPU-only environments with <8 GB RAM.

Design principles:
  - Lazy connection: probe Ollama only when first request arrives
  - Short timeouts: never block lab workflow for AI
  - Quantized models: Q4_K_M preferred for CPU
  - Connection pool: reuse httpx client across requests
  - Graceful fail: always return something useful or empty string
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

import httpx

from ai_services.schemas import AILayer, AIResponse
from core.config import get_settings

logger   = logging.getLogger('local_llm')
settings = get_settings()

# ── LRU response cache ────────────────────────────────────────────────────────

class _LRUCache:
    """Thread-safe LRU with TTL. Shared across all local-LLM calls."""

    def __init__(self, max_size: int = 256, ttl_s: int = 3600):
        self._store: OrderedDict[str, tuple[dict, float]] = OrderedDict()
        self._max   = max_size
        self._ttl   = ttl_s

    def _key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:24]

    def get(self, prompt: str) -> Optional[dict]:
        k = self._key(prompt)
        if k not in self._store:
            return None
        payload, ts = self._store[k]
        if time.time() - ts > self._ttl:
            del self._store[k]
            return None
        self._store.move_to_end(k)
        return payload

    def set(self, prompt: str, payload: dict) -> None:
        k = self._key(prompt)
        self._store[k] = (payload, time.time())
        self._store.move_to_end(k)
        while len(self._store) > self._max:
            self._store.popitem(last=False)

    @property
    def size(self) -> int:
        return len(self._store)


_cache = _LRUCache(max_size=getattr(settings, 'ai_cache_size', 256))

# ── ALIS-X clinical system prompt ─────────────────────────────────────────────

SYSTEM_PROMPT = (
    'You are ALIS-X, a clinical decision-support assistant for '
    'JORINOVA NEXUS hospital laboratory system in Rwanda. '
    'You help laboratory scientists interpret results and suggest next steps. '
    'Rules: '
    '(1) Never provide a final diagnosis — offer differential support only. '
    '(2) Always recommend expert validation for critical values. '
    '(3) Base responses on WHO guidelines and evidence-based medicine. '
    '(4) Be concise and structured. '
    '(5) For critical flags, always recommend IMMEDIATE clinician notification. '
    '(6) Respond ONLY in the requested JSON format when specified.'
)

# ── Connectivity probe ────────────────────────────────────────────────────────

_last_probe:   float = 0.0
_last_status:  bool  = False
_PROBE_TTL:    float = 30.0   # re-probe at most every 30 seconds


async def is_available() -> bool:
    """Non-blocking Ollama availability check with 30s TTL probe cache."""
    global _last_probe, _last_status
    now = time.time()
    if now - _last_probe < _PROBE_TTL:
        return _last_status
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f'{settings.ollama_url}/api/tags')
            _last_status = r.status_code == 200
    except Exception:
        _last_status = False
    _last_probe = time.time()
    return _last_status


async def pull_model_if_missing() -> bool:
    """
    Pull the configured Ollama model if not already present.
    Called once at startup in the background — never blocks requests.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            tags = (await c.get(f'{settings.ollama_url}/api/tags')).json()
        models = [m.get('name', '') for m in tags.get('models', [])]
        target = settings.ollama_model
        if not any(target in m for m in models):
            logger.info('Pulling Ollama model %s …', target)
            async with httpx.AsyncClient(timeout=300.0) as c:
                await c.post(f'{settings.ollama_url}/api/pull',
                             json={'name': target, 'stream': False})
            logger.info('Model %s ready.', target)
            return True
        return True
    except Exception as e:
        logger.warning('Model pull failed (non-critical): %s', e)
        return False


# ── Core generation ───────────────────────────────────────────────────────────

async def generate(
    prompt:     str,
    system:     str  = '',
    use_cache:  bool = True,
    max_tokens: int  = 512,
    temperature:float = 0.15,
    timeout_s:  float = None,
) -> AIResponse:
    """
    Send prompt to Ollama. Returns AIResponse.
    Never raises — errors are returned in AIResponse.error.
    """
    t0 = time.time()

    # Cache hit
    if use_cache:
        cache_key = f'{system}|||{prompt}'
        hit = _cache.get(cache_key)
        if hit:
            logger.debug('Local LLM cache hit')
            resp = AIResponse(**hit)
            resp.cached = True
            return resp

    if not await is_available():
        return AIResponse(
            content='', layer_used=AILayer.LOCAL, model=settings.ollama_model,
            latency_ms=int((time.time()-t0)*1000),
            error='Ollama not reachable — offline fallback to rules engine',
        )

    effective_timeout = timeout_s or settings.local_ai_timeout
    messages = []
    if system or SYSTEM_PROMPT:
        messages.append({'role': 'system', 'content': system or SYSTEM_PROMPT})
    messages.append({'role': 'user', 'content': prompt})

    try:
        async with httpx.AsyncClient(timeout=effective_timeout) as c:
            r = await c.post(
                f'{settings.ollama_url}/api/chat',
                json={
                    'model':   settings.ollama_model,
                    'messages': messages,
                    'stream':  False,
                    'options': {
                        'temperature': temperature,
                        'num_predict': max_tokens,
                        'top_p':       0.9,
                        'repeat_penalty': 1.1,
                    },
                },
            )
            r.raise_for_status()
            content = r.json().get('message', {}).get('content', '').strip()
            resp = AIResponse(
                content=content,
                layer_used=AILayer.LOCAL,
                model=settings.ollama_model,
                latency_ms=int((time.time()-t0)*1000),
            )
            if use_cache and content:
                _cache.set(cache_key, resp.to_dict())
            return resp

    except httpx.TimeoutException:
        logger.warning('Ollama timeout after %.1fs for model %s', effective_timeout, settings.ollama_model)
        return AIResponse(
            content='', layer_used=AILayer.LOCAL, model=settings.ollama_model,
            latency_ms=int((time.time()-t0)*1000),
            error=f'Timeout ({effective_timeout}s) — reduce prompt length or switch to cloud',
        )
    except Exception as e:
        logger.error('Ollama error: %s', e)
        return AIResponse(
            content='', layer_used=AILayer.LOCAL, model=settings.ollama_model,
            latency_ms=int((time.time()-t0)*1000), error=str(e),
        )


# ── Convenience helpers ───────────────────────────────────────────────────────

async def interpret_lab_result(
    test_name: str,
    value:     str,
    unit:      str,
    flag:      str,
    ref_range: str = '',
    sex:       str = '',
    age:       int = 0,
) -> dict[str, Any]:
    """
    Structured local LLM interpretation of a single lab result.
    Returns a dict — never raises.
    """
    prompt = (
        f'Laboratory result to interpret:\n'
        f'Test: {test_name}  Value: {value} {unit}  Flag: {flag}\n'
        f'Reference range: {ref_range or "see standard ranges"}\n'
        f'Patient: sex={sex or "unknown"} age={age or "unknown"}\n\n'
        f'Respond ONLY in JSON (no markdown):\n'
        f'{{"significance":"CRITICAL|HIGH|MODERATE|LOW|NORMAL",'
        f'"differentials":["...","...","..."],'
        f'"action":"one-sentence recommended next step",'
        f'"critical_alert":true|false,'
        f'"summary":"one sentence clinical summary"}}'
    )
    resp = await generate(prompt, max_tokens=300, timeout_s=12.0)
    return _parse_json_response(resp, fallback={'summary': resp.content or 'Interpretation unavailable offline.'})


async def parse_voice_command(transcript: str) -> dict[str, Any]:
    """
    Parse a natural language voice command into a structured action.
    Runs locally — never requires cloud.
    """
    prompt = (
        f'Parse this voice command from a laboratory worker:\n'
        f'"{transcript}"\n\n'
        f'Valid actions: open_patient, search_patient, validate_result, '
        f'print_report, flag_critical, open_module, run_report, add_note, unknown\n\n'
        f'Respond ONLY in JSON:\n'
        f'{{"action":"<action>","entity":"<name/module/etc>","parameters":{{}},'
        f'"confidence":0.0-1.0}}'
    )
    resp = await generate(prompt, max_tokens=120, temperature=0.05, timeout_s=8.0)
    return _parse_json_response(resp, fallback={'action': 'unknown', 'confidence': 0.0})


async def draft_report_section(
    department:   str,
    test_results: list[dict],
    clinical_context: str = '',
) -> str:
    """
    Draft a short laboratory report narrative section.
    Suitable for local offline use (concise prompt).
    """
    lines = '\n'.join(
        f"  {r.get('test_name','?')}: {r.get('value','?')} {r.get('unit','')} [{r.get('flag','?')}]"
        for r in test_results[:12]  # limit context for CPU models
    )
    prompt = (
        f'Write a concise laboratory report narrative for {department} department.\n'
        f'Results:\n{lines}\n'
        f'Clinical context: {clinical_context or "not provided"}\n\n'
        f'Write 2-3 sentences of plain clinical language. '
        f'Do not repeat individual values — summarise the pattern. '
        f'Note any critical or abnormal findings. '
        f'End with a recommendation for clinical review.'
    )
    resp = await generate(prompt, max_tokens=200, timeout_s=15.0)
    return resp.content or 'Report narrative unavailable — AI offline.'


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_json_response(resp: AIResponse, fallback: dict) -> dict:
    """Extract JSON from LLM response, stripping markdown fences."""
    import json
    if not resp.content:
        return {**fallback, 'layer': resp.layer_used, 'error': resp.error}
    text = resp.content.strip()
    if '```json' in text:
        text = text.split('```json', 1)[1].rsplit('```', 1)[0]
    elif '```' in text:
        text = text.split('```', 1)[1].rsplit('```', 1)[0]
    try:
        data = json.loads(text.strip())
        data['layer']      = resp.layer_used
        data['latency_ms'] = resp.latency_ms
        return data
    except json.JSONDecodeError:
        return {**fallback, 'summary': text[:300], 'layer': resp.layer_used}


def cache_stats() -> dict:
    return {
        'cache_entries': _cache.size,
        'cache_max':     256,
        'ollama_url':    settings.ollama_url,
        'model':         settings.ollama_model,
        'last_status':   _last_status,
    }
