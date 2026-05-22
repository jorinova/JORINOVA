"""
Training-runner intent classifier.

Three-stage cascade:
  1. Regex fast path  — instant, deterministic, covers ~90 % of phrases
  2. Local LLM        — Ollama via local_llm_router (task='chat')
  3. Cloud LLM        — Claude via cloud_llm

Returns the same shape regardless of source:
    { 'intent': '<one of the closed set>',
      'reply':  '<short persona-aligned spoken line>',
      'source': 'regex' | 'local' | 'cloud' | 'unknown' }

Closed intent set:
    start | next | pause | resume | restart | stop
    greet | wake | help | thanks | unknown
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, Optional

from ai_services import cloud_llm, local_llm_router

logger = logging.getLogger('alis_x.training_intent')

VALID_INTENTS = {
    'start', 'next', 'pause', 'resume', 'restart', 'stop',
    'greet', 'wake', 'help', 'thanks', 'unknown',
}

# ── Stage 1 : regex (mirrors the frontend matcher, kept slightly broader) ────

_WAKE_RE     = re.compile(r'\b(jorinova|nexus|alis[ -]?x|hey nexus|hi nexus|ok jorinova)\b', re.I)
_GREET_RE    = re.compile(r'\b(hello|hi|hey|good (morning|afternoon|evening)|mwaramutse|mwiriwe|muraho|bonjour|bonsoir)\b', re.I)
_HELP_RE     = re.compile(r'\b(help|what can you do|how (do|to) i|what (are|do) (you|the) commands?|ubufasha|aide)\b', re.I)
_THANKS_RE   = re.compile(r'\b(thank(s| you)?|murakoze|merci)\b', re.I)

_INTENT_REGEX: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b(start|begin|launch|let\'?s go|go ahead|tangira|d[eé]marrer|commencer)\b', re.I), 'start'),
    (re.compile(r'\b(next|next step|continue|move on|skip|forward|komeza|suivant)\b',          re.I), 'next'),
    (re.compile(r'\b(pause|wait|hold on|hold up|hagarara|attends|attendez)\b',                  re.I), 'pause'),
    (re.compile(r'\b(resume|continue now|go on|tangira nanone|reprendre|reprends)\b',           re.I), 'resume'),
    (re.compile(r'\b(restart|replay|again|from the start|from the beginning|subira|ongera|recommencer)\b', re.I), 'restart'),
    (re.compile(r'\b(stop|halt|cancel|reka|hagarika|arr[eê]te|arr[eê]ter)\b',                    re.I), 'stop'),
]


def _regex_match(text: str) -> Optional[str]:
    if _WAKE_RE.search(text):
        if _GREET_RE.search(text):
            return 'greet'
        return 'wake'
    if _GREET_RE.search(text):
        return 'greet'
    if _HELP_RE.search(text):
        return 'help'
    if _THANKS_RE.search(text):
        return 'thanks'
    for pattern, intent in _INTENT_REGEX:
        if pattern.search(text):
            return intent
    return None


# ── Stage 2 / 3 : LLM with strict JSON output ────────────────────────────────

LLM_PROMPT = """You are a strict intent classifier for the JORINOVA NEXUS training assistant.

The user speaks freely in English, French, or Kinyarwanda. Classify their utterance
into ONE intent from this closed list:

  start    - begin / launch the demo
  next     - move to the next step
  pause    - pause the demo
  resume   - resume after a pause
  restart  - start over from the beginning
  stop     - cancel and exit
  greet    - greeting (hello / hi / bonjour / muraho)
  wake     - calling the assistant by name (jorinova / nexus / alis-x)
  help     - asking what they can do
  thanks   - thanking
  unknown  - anything else, including chitchat, off-topic, or unclear speech

Rules:
- Output STRICT JSON only, no markdown, no commentary.
- Shape: {{"intent": "<one of the list>", "confidence": <0..1>, "reply": "<short spoken reply in the user's language, at most 18 words>"}}.
- Keep reply calm, simple, polite. Greet only when intent is greet/wake.
- If intent is start|next|pause|resume|restart|stop, reply can be empty.
- If intent is unknown, reply asks the user to repeat or say "help".

USER UTTERANCE ({language}): "{text}"
"""


_JSON_RE = re.compile(r'\{.*\}', re.S)


def _parse_llm_json(raw: str) -> Optional[dict[str, Any]]:
    raw = (raw or '').strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```[a-zA-Z0-9_-]*\s*', '', raw)
        raw = re.sub(r'\s*```\s*$', '', raw)
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        out = json.loads(m.group(0))
        if not isinstance(out, dict):
            return None
        intent = (out.get('intent') or '').lower().strip()
        if intent not in VALID_INTENTS:
            return None
        return {
            'intent': intent,
            'confidence': float(out.get('confidence') or 0.5),
            'reply': (out.get('reply') or '').strip()[:240],
        }
    except Exception:
        return None


async def classify(
    text:     str,
    language: str = 'en',
    use_llm:  bool = True,
    provider: Literal['auto', 'cloud', 'local', 'none'] = 'auto',
) -> dict[str, Any]:
    """Classify a transcript. Always returns a dict — never raises."""
    text = (text or '').strip()
    if not text:
        return {'intent': 'unknown', 'reply': '', 'source': 'empty'}

    # Stage 1 — regex
    hit = _regex_match(text)
    if hit:
        return {'intent': hit, 'reply': '', 'source': 'regex'}

    if not use_llm or provider == 'none':
        return {'intent': 'unknown', 'reply': '', 'source': 'regex-miss'}

    prompt = LLM_PROMPT.format(language=language, text=text.replace('"', "'"))

    # Stage 2 — local LLM (task='chat' uses nous-hermes → llama3 → fast → fallback)
    if provider in ('auto', 'local'):
        resp = await local_llm_router.route(
            task='chat', prompt=prompt, max_tokens=200, temperature=0.0,
        )
        if resp.content and not resp.error:
            parsed = _parse_llm_json(resp.content)
            if parsed:
                parsed['source'] = 'local'
                return parsed

    # Stage 3 — cloud LLM
    if provider in ('auto', 'cloud'):
        resp = await cloud_llm.generate(prompt, max_tokens=200, temperature=0.0)
        if resp.content and not resp.error:
            parsed = _parse_llm_json(resp.content)
            if parsed:
                parsed['source'] = 'cloud'
                return parsed

    return {'intent': 'unknown', 'reply': '', 'source': 'llm-miss'}
