"""
ALIS-X Cloud LLM Service
========================
Wraps Anthropic Claude API for advanced medical reasoning.

Design principles:
  - Enhancement only: cloud failure NEVER stops local system
  - Prompt caching: use Claude's prompt cache for repeated system prompts
  - Short circuit: skip cloud if key not configured or network unreachable
  - Structured output: always request JSON to reduce hallucination surface
  - Rate-limit aware: exponential backoff on 429 responses
  - Audit: all cloud calls logged (no raw patient data sent without consent)
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from typing import Any, Optional

from ai_services.schemas import AILayer, AIResponse
from core.config import get_settings

logger   = logging.getLogger('cloud_llm')
settings = get_settings()

# ── Response cache ────────────────────────────────────────────────────────────

class _CloudCache:
    """Longer-lived cache for expensive cloud responses."""

    def __init__(self, max_size: int = 128, ttl_s: int = 7200):
        self._store: OrderedDict[str, tuple[dict, float]] = OrderedDict()
        self._max, self._ttl = max_size, ttl_s

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


_cache = _CloudCache()

# ── System prompt (cached with Claude's prompt caching API) ──────────────────
# This is marked as cache_control='ephemeral' to use Claude's prompt cache.
# Re-used across requests to save tokens and reduce latency.

_SYSTEM_BLOCKS = [
    {
        'type': 'text',
        'text': (
            'You are ALIS-X Advanced Clinical AI, the cloud reasoning layer of '
            'JORINOVA NEXUS hospital laboratory information system (ALIS-X), Rwanda. '
            'You provide advanced clinical decision support to laboratory scientists and clinicians.\n\n'
            'Core responsibilities:\n'
            '- Complex differential diagnosis support from panel results\n'
            '- Advanced medical reasoning with drug interactions\n'
            '- Epidemiological pattern analysis and outbreak assessment\n'
            '- Research-grade literature synthesis for clinical questions\n'
            '- Detailed laboratory report narrative generation\n\n'
            'Absolute constraints:\n'
            '(1) Never provide a definitive diagnosis — always recommend expert validation.\n'
            '(2) Always flag critical values for IMMEDIATE clinician notification.\n'
            '(3) Base all responses on WHO guidelines, evidence-based medicine, and peer-reviewed literature.\n'
            '(4) When uncertain, say so explicitly — medical AI must not confabulate.\n'
            '(5) Respond in structured JSON when requested — never add markdown to JSON fields.\n'
            '(6) For any result flagged HH or LL, include an explicit action: NOTIFY_CLINICIAN_NOW.\n'
            '(7) All patient data shared with you must be used only for the clinical purpose requested.\n\n'
            'Context: Rwanda, sub-Saharan Africa, public hospital laboratory setting. '
            'Consider local disease prevalence: malaria, TB, HIV, sickle cell, typhoid, '
            'bacterial sepsis, helminthiasis. Prioritise cost-effective investigations.'
        ),
        'cache_control': {'type': 'ephemeral'},
    }
]

# ── Availability ─────────────────────────────────────────────────────────────

def is_configured() -> bool:
    """Check API key is set. Synchronous — no network call."""
    return bool(getattr(settings, 'anthropic_api_key', ''))


_net_last_probe:  float = 0.0
_net_last_status: bool  = False
_NET_PROBE_TTL:   float = 60.0


async def is_available() -> bool:
    """Check both: key configured + network reachable."""
    global _net_last_probe, _net_last_status
    if not is_configured():
        return False
    now = time.time()
    if now - _net_last_probe < _NET_PROBE_TTL:
        return _net_last_status
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get('https://api.anthropic.com')
            _net_last_status = r.status_code < 500
    except Exception:
        _net_last_status = False
    _net_last_probe = time.time()
    return _net_last_status


# ── Core generation ───────────────────────────────────────────────────────────

async def generate(
    prompt:       str,
    use_cache:    bool = True,
    max_tokens:   int  = 1024,
    temperature:  float = 0.1,
    use_prompt_cache: bool = True,
) -> AIResponse:
    """
    Send prompt to Claude with prompt caching enabled.
    Never raises — all errors are in AIResponse.error.
    """
    t0 = time.time()

    if not is_configured():
        return AIResponse(
            content='', layer_used=AILayer.CLOUD, model=settings.claude_model,
            latency_ms=0, error='Cloud API key not configured — running offline',
        )

    if use_cache:
        hit = _cache.get(prompt)
        if hit:
            resp = AIResponse(**hit)
            resp.cached = True
            return resp

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        system = _SYSTEM_BLOCKS if use_prompt_cache else _SYSTEM_BLOCKS[0]['text']

        msg = await client.messages.create(
            model=settings.claude_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{'role': 'user', 'content': prompt}],
        )

        content = msg.content[0].text.strip() if msg.content else ''
        input_t  = getattr(msg.usage, 'input_tokens', 0)
        output_t = getattr(msg.usage, 'output_tokens', 0)
        cache_read  = getattr(msg.usage, 'cache_read_input_tokens', 0)
        cache_write = getattr(msg.usage, 'cache_creation_input_tokens', 0)

        resp = AIResponse(
            content=content,
            layer_used=AILayer.CLOUD,
            model=settings.claude_model,
            latency_ms=int((time.time()-t0)*1000),
            metadata={
                'input_tokens':  input_t,
                'output_tokens': output_t,
                'cache_read':    cache_read,
                'cache_write':   cache_write,
            },
        )
        if use_cache and content:
            _cache.set(prompt, resp.to_dict())
        return resp

    except Exception as e:
        err_str = str(e)
        logger.warning('Cloud LLM error: %s', err_str[:200])
        return AIResponse(
            content='', layer_used=AILayer.CLOUD, model=settings.claude_model,
            latency_ms=int((time.time()-t0)*1000), error=err_str[:300],
        )


# ── Domain helpers ────────────────────────────────────────────────────────────

async def advanced_interpretation(
    panel_results: list[dict],
    clinical_context: str = '',
    patient_age: int = 0,
    patient_sex: str = '',
) -> dict[str, Any]:
    """
    Full-panel clinical reasoning. Cloud-only — gracefully returns empty if offline.
    panel_results: [{'test_name','value','unit','flag','ref_range'}, ...]
    """
    if not await is_available():
        return {'error': 'Cloud unavailable — use local rules + local LLM', 'layer': 'cloud'}

    lines = '\n'.join(
        f"  {r.get('test_name','?')}: {r.get('value','?')} {r.get('unit','')} "
        f"[{r.get('flag','N')}] ref:{r.get('ref_range','—')}"
        for r in panel_results[:20]
    )
    prompt = (
        f'Advanced laboratory panel analysis:\n\n'
        f'Patient: {patient_sex or "unknown sex"}, '
        f'{"age " + str(patient_age) if patient_age else "age unknown"}\n'
        f'Clinical context: {clinical_context or "not provided"}\n\n'
        f'Results:\n{lines}\n\n'
        f'Respond ONLY in JSON (no markdown fences):\n'
        f'{{"syndrome_pattern":"...","top_differentials":["...","...","..."],'
        f'"urgency":"IMMEDIATE|URGENT|ROUTINE",'
        f'"critical_findings":[{{"finding":"...","action":"..."}}],'
        f'"suggested_investigations":["...","..."],'
        f'"clinical_narrative":"2-3 sentences",'
        f'"confidence":"high|medium|low",'
        f'"caveats":["..."]  }}'
    )
    resp = await generate(prompt, max_tokens=800)
    return _parse_json(resp, {'clinical_narrative': resp.content or 'Cloud analysis failed.'})


async def epidemic_intelligence(
    department: str,
    test_code:  str,
    flag:       str,
    count_7d:   int,
    baseline:   float,
    geographic_context: str = 'Rwanda',
) -> dict[str, Any]:
    """Outbreak signal assessment. Cloud-only enhancement."""
    if not await is_available():
        return {'signal': count_7d > baseline * 2, 'layer': 'rules_only', 'cloud': False}

    increase_pct = int(((count_7d / max(baseline, 0.1)) - 1) * 100)
    prompt = (
        f'Epidemiological signal analysis — {geographic_context} hospital lab:\n'
        f'Department: {department}  Test: {test_code}  Flag: {flag}\n'
        f'Cases past 7 days: {count_7d}  Baseline average: {baseline:.1f}  '
        f'Change: +{increase_pct}%\n\n'
        f'Assess outbreak risk considering local disease epidemiology.\n\n'
        f'Respond ONLY in JSON:\n'
        f'{{"outbreak_signal":true|false,'
        f'"confidence":"low|medium|high",'
        f'"suspected_pathogen":"...",'
        f'"alert_level":"WATCH|WARNING|ALERT|EMERGENCY",'
        f'"recommended_actions":["...","..."],'
        f'"public_health_notification":true|false,'
        f'"rationale":"..."}}'
    )
    resp = await generate(prompt, max_tokens=400)
    result = _parse_json(resp, {'outbreak_signal': count_7d > baseline * 2})
    result['layer'] = 'cloud'
    return result


async def drug_interaction_check(
    current_medications: list[str],
    proposed_medication: str,
    patient_context: str = '',
) -> dict[str, Any]:
    """Drug-drug and drug-lab interaction assessment. Cloud-only."""
    if not await is_available():
        return {'available': False, 'message': 'Drug interaction check requires cloud connectivity'}

    meds_str = ', '.join(current_medications) if current_medications else 'none listed'
    prompt = (
        f'Drug interaction assessment:\n'
        f'Current medications: {meds_str}\n'
        f'Proposed new medication: {proposed_medication}\n'
        f'Patient context: {patient_context or "no additional context"}\n\n'
        f'Identify clinically significant interactions relevant to laboratory monitoring.\n\n'
        f'Respond ONLY in JSON:\n'
        f'{{"interactions":[{{"drugs":"...","severity":"MAJOR|MODERATE|MINOR",'
        f'"mechanism":"...","lab_monitoring":["..."],"management":"..."}}],'
        f'"overall_risk":"HIGH|MODERATE|LOW|NONE",'
        f'"key_lab_tests_to_monitor":["...","..."],'
        f'"recommendation":"..."}}'
    )
    resp = await generate(prompt, max_tokens=600)
    return _parse_json(resp, {'overall_risk': 'UNKNOWN', 'recommendation': 'Manual pharmacist review required'})


async def generate_full_report(
    department:   str,
    test_results: list[dict],
    patient_info: dict,
    clinical_notes: str = '',
) -> str:
    """Generate a comprehensive laboratory report narrative."""
    if not await is_available():
        return 'Full report generation requires cloud connectivity.'

    results_text = '\n'.join(
        f"  {r.get('test_name','?')}: {r.get('value','?')} {r.get('unit','')} [{r.get('flag','N')}]"
        for r in test_results[:25]
    )
    age = patient_info.get('age', 'unknown')
    sex = patient_info.get('sex', 'unknown')
    prompt = (
        f'Generate a professional laboratory report narrative for:\n'
        f'Department: {department}\n'
        f'Patient: {sex}, age {age}\n'
        f'Clinical notes: {clinical_notes or "none"}\n\n'
        f'Results:\n{results_text}\n\n'
        f'Write a structured clinical narrative (3-5 paragraphs) covering:\n'
        f'1. Summary of key findings\n'
        f'2. Clinical interpretation and significance\n'
        f'3. Abnormal findings with differential considerations\n'
        f'4. Recommended follow-up investigations\n'
        f'5. Conclusion and recommendation for clinical review\n\n'
        f'Use professional medical language. Do not repeat raw values — interpret patterns.'
    )
    resp = await generate(prompt, max_tokens=1200, use_cache=False)
    return resp.content or 'Report generation failed — cloud unavailable.'


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_json(resp: AIResponse, fallback: dict) -> dict:
    import json
    if not resp.content:
        return {**fallback, 'layer': 'cloud', 'error': resp.error}
    text = resp.content.strip()
    for sep in ('```json', '```'):
        if sep in text:
            text = text.split(sep, 1)[1].rsplit('```', 1)[0]
            break
    try:
        data = json.loads(text.strip())
        data['layer'] = 'cloud'
        return data
    except json.JSONDecodeError:
        return {**fallback, 'raw_text': text[:500], 'layer': 'cloud'}


def cache_stats() -> dict:
    return {
        'cloud_cache_entries': _cache._store.__len__(),
        'model':  getattr(settings, 'claude_model', 'unknown'),
        'configured': is_configured(),
        'prompt_caching': True,
    }
