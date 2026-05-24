"""
Side-by-side: baseline LLM vs. RAG-enhanced LLM on the same questions.

Picks a small slice (default 8 questions) so it finishes in a few minutes
on a CPU laptop. Useful answer to 'do they know what I asked about?'.

Run
    cd backend
    python -m training.probe_vs_rag                       # phi3:mini, 8 Qs
    python -m training.probe_vs_rag --model phi3:mini --n 12
    python -m training.probe_vs_rag --model tinyllama:latest
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path

os.environ.setdefault('DEBUG', 'false')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
try:
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
except Exception:
    pass

from ai_services             import local_llm                                  # noqa: E402
from ai_services.medical_rag import answer_with_kb                             # noqa: E402
from training.probe_medical  import PROBES, grade, SYSTEM                      # noqa: E402


def short_label(g: str) -> str:
    return {'CORRECT': '✓ correct', 'PARTIAL': '~ partial',
            'WRONG': '✗ WRONG', 'REFUSED': '? refused', 'ERROR': '! error'}[g]


async def baseline_answer(model: str, prompt: str, timeout_s: float) -> tuple[str, int]:
    r = await local_llm.generate(
        prompt=prompt, system=SYSTEM, model=model,
        max_tokens=160, temperature=0.0,
        use_cache=False, timeout_s=timeout_s,
    )
    if r.error:
        return f'[err] {r.error[:100]}', r.latency_ms
    return r.content.strip(), r.latency_ms


async def rag_answer(model: str, prompt: str, timeout_s: float) -> tuple[str, int, list]:
    r = await answer_with_kb(
        query=prompt, model=model, max_tokens=160, temperature=0.0,
        timeout_s=timeout_s,
    )
    cited = (r.metadata or {}).get('kb_chunks', [])
    if r.error:
        return f'[err] {r.error[:100]}', r.latency_ms, cited
    return r.content.strip(), r.latency_ms, cited


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--model',   default='phi3:mini')
    ap.add_argument('--n',       type=int, default=8, help='How many probes to run (max 27)')
    ap.add_argument('--timeout', type=float, default=60.0)
    args = ap.parse_args()

    # Pick a balanced slice across domains
    selected = []
    seen_domains: set[str] = set()
    for p in PROBES:
        domain = p[0]
        if domain not in seen_domains:
            selected.append(p); seen_domains.add(domain)
        if len(selected) >= args.n:
            break
    # If we have headroom, top up with more from any domain
    if len(selected) < args.n:
        for p in PROBES:
            if p not in selected:
                selected.append(p)
            if len(selected) >= args.n:
                break

    print(f'Model       : {args.model}')
    print(f'Probes      : {len(selected)} (across {len(seen_domains)} domains)')
    print(f'Per-Q budget: {args.timeout:.0f}s')
    print()

    base_score = {'CORRECT': 0, 'PARTIAL': 0, 'WRONG': 0, 'REFUSED': 0, 'ERROR': 0}
    rag_score  = {'CORRECT': 0, 'PARTIAL': 0, 'WRONG': 0, 'REFUSED': 0, 'ERROR': 0}
    t0 = time.time()

    for i, (domain, prompt, must) in enumerate(selected, 1):
        print(f'── Q{i} [{domain}] {prompt}')
        print(f'   must contain: {must}')

        # Baseline
        ans_b, lat_b = await baseline_answer(args.model, prompt, args.timeout)
        g_b = 'ERROR' if ans_b.startswith('[err]') else grade(ans_b, [m.lower() for m in must])
        base_score[g_b] += 1
        print(f'   baseline ({lat_b}ms)  {short_label(g_b)}')
        print(f'     "{ans_b[:160]}"')

        # RAG
        ans_r, lat_r, cited = await rag_answer(args.model, prompt, args.timeout)
        g_r = 'ERROR' if ans_r.startswith('[err]') else grade(ans_r, [m.lower() for m in must])
        rag_score[g_r] += 1
        cit_str = ', '.join(f'{c["kind"]}/{c["key"]}' for c in cited[:3]) or '(no chunks matched)'
        print(f'   RAG      ({lat_r}ms)  {short_label(g_r)}     cited: {cit_str}')
        print(f'     "{ans_r[:160]}"')
        print()

    elapsed = time.time() - t0
    n = len(selected)
    print('═' * 66)
    print(f'BASELINE   correct {base_score["CORRECT"]}/{n}  partial {base_score["PARTIAL"]}  '
          f'wrong {base_score["WRONG"]}  refused {base_score["REFUSED"]}  error {base_score["ERROR"]}')
    print(f'RAG        correct {rag_score["CORRECT"]}/{n}  partial {rag_score["PARTIAL"]}  '
          f'wrong {rag_score["WRONG"]}  refused {rag_score["REFUSED"]}  error {rag_score["ERROR"]}')
    lift_pct = (rag_score['CORRECT'] - base_score['CORRECT']) / max(n, 1) * 100
    print(f'LIFT       {lift_pct:+.0f} percentage points')
    print(f'Elapsed    {elapsed:.0f}s')
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
