"""
Cloud-cascade verifier — proves the cloud LLM stage is live after you
add ANTHROPIC_API_KEY to backend/.env.

What it does
1. Loads the running settings.
2. Confirms the key is present and the Anthropic SDK is importable.
3. Pings api.anthropic.com to verify the network reaches it.
4. Sends a single short prompt to Claude (haiku) so you see the actual
   token usage + latency numbers.
5. Runs the intent cascade in three modes — regex-only, cloud-only,
   and full auto — on a focused 10-example slice of the golden set so
   you can compare scores side by side.

Run
    cd backend
    python scripts/verify_cloud_cascade.py
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault('DEBUG', 'true')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
try:
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
except Exception:
    pass

from core.config         import get_settings                                  # noqa: E402
from ai_services         import cloud_llm, training_intent as ti              # noqa: E402

GOLDEN = Path(__file__).resolve().parents[1] / 'training' / 'golden' / 'intent_golden.jsonl'


def hr(title: str) -> None:
    bar = '═' * (62 - len(title))
    print(f'\n══ {title} {bar}')


async def main() -> int:
    hr('1. Configuration')
    s = get_settings()
    print(f'  ANTHROPIC_API_KEY set : {"yes" if s.anthropic_api_key else "NO  ← add it to backend/.env"}')
    print(f'  claude_model          : {s.claude_model}')
    print(f'  cloud_ai_timeout      : {s.cloud_ai_timeout}s')

    if not s.anthropic_api_key:
        print('\n  → Add this line to backend/.env then re-run:')
        print('      ANTHROPIC_API_KEY=sk-ant-...')
        return 1

    hr('2. SDK + network')
    try:
        import anthropic                                                       # noqa: F401
        print('  anthropic SDK         : importable')
    except ImportError:
        print('  anthropic SDK         : MISSING — pip install anthropic')
        return 1
    reachable = await cloud_llm.is_available()
    print(f'  api.anthropic.com     : {"reachable" if reachable else "UNREACHABLE"}')
    if not reachable:
        return 1

    hr('3. Single call to Claude')
    resp = await cloud_llm.generate(
        prompt='Reply with one short sentence confirming you can hear me.',
        max_tokens=80, temperature=0.0,
    )
    if resp.error:
        print(f'  ERROR: {resp.error}')
        return 1
    print(f'  content   : {resp.content[:200]}')
    print(f'  model     : {resp.model}')
    print(f'  latency   : {resp.latency_ms} ms')
    meta = resp.metadata or {}
    print(f'  tokens    : in={meta.get("input_tokens", 0)}  out={meta.get("output_tokens", 0)}'
          f'  cache_read={meta.get("cache_read", 0)}  cache_write={meta.get("cache_write", 0)}')

    hr('4. Intent cascade leaderboard (10 examples)')
    rows = [json.loads(l) for l in GOLDEN.read_text(encoding='utf-8').splitlines() if l.strip()][:10]

    async def run(stage: str) -> tuple[int, int, float]:
        from time import time
        use_llm  = stage != 'regex'
        provider = {'regex': 'none', 'cloud': 'cloud', 'auto': 'auto'}[stage]
        t0 = time(); ok = 0
        for r in rows:
            pred = await ti.classify(r['text'], r['language'], use_llm=use_llm, provider=provider)  # type: ignore[arg-type]
            if pred.get('intent') == r['intent']:
                ok += 1
        return ok, len(rows), time() - t0

    for stage in ('regex', 'cloud', 'auto'):
        try:
            ok, n, elapsed = await run(stage)
            print(f'  {stage:<6}  {ok}/{n}  ({ok/n:.0%})   {elapsed:.1f}s')
        except Exception as e:
            print(f'  {stage:<6}  FAILED: {str(e)[:120]}')

    hr('Done')
    print('  Cloud cascade is LIVE. Restart the backend so other endpoints')
    print('  pick up the new settings if you have not already.')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
