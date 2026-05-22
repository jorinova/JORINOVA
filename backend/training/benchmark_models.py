"""
Per-worker Ollama benchmark.

Runs the intent golden set through each Ollama model individually (bypassing
the router's fallback ladder) so you can see which worker actually wins for
each task. Prints latency + accuracy for each model.

Run
---
    cd backend
    python -m training.benchmark_models                  # all 5 workers
    python -m training.benchmark_models --model phi3:mini
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_services import local_llm, training_intent as ti              # noqa: E402
from core.config import get_settings                                  # noqa: E402

GOLDEN = Path(__file__).parent / 'golden' / 'intent_golden.jsonl'


def _models_from_settings() -> list[tuple[str, str]]:
    s = get_settings()
    return [
        ('fast',     s.ollama_model_fast),
        ('deep',     s.ollama_model_deep),
        ('chat',     s.ollama_model_chat),
        ('general',  s.ollama_model_general),
        ('fallback', s.ollama_model_fallback),
    ]


async def _bench_one(model: str, rows: list[dict]) -> dict:
    correct = 0
    latencies: list[int] = []
    errors = 0
    t0 = time.time()

    for r in rows:
        prompt = ti.LLM_PROMPT.format(language=r['language'], text=r['text'].replace('"', "'"))
        resp = await local_llm.generate(
            prompt=prompt, max_tokens=200, temperature=0.0,
            use_cache=False, model=model,
        )
        if resp.error or not resp.content:
            errors += 1
            continue
        latencies.append(resp.latency_ms)
        parsed = ti._parse_llm_json(resp.content)
        if parsed and parsed['intent'] == r['intent']:
            correct += 1

    elapsed = time.time() - t0
    return {
        'model':       model,
        'n':           len(rows),
        'correct':     correct,
        'errors':      errors,
        'accuracy':    correct / len(rows) if rows else 0.0,
        'latency_avg': (sum(latencies) // len(latencies)) if latencies else 0,
        'latency_p95': (sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0),
        'elapsed_s':   elapsed,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description='Benchmark each Ollama worker on intent golden set')
    ap.add_argument('--model', help='Run only this exact model name (skips the worker pool)')
    ap.add_argument('--out',   help='Optional JSON path for results')
    args = ap.parse_args()

    rows = [json.loads(line) for line in GOLDEN.read_text(encoding='utf-8').splitlines() if line.strip()]
    print(f'Golden set: {len(rows)} examples')

    candidates = [('custom', args.model)] if args.model else _models_from_settings()

    results = []
    for role, model in candidates:
        print(f'\n── {role:<8} {model} ' + '─' * (52 - len(role) - len(model)))
        try:
            r = asyncio.run(_bench_one(model, rows))
            r['role'] = role
            results.append(r)
            print(f'   accuracy : {r["correct"]:>3}/{r["n"]:<3}  ({r["accuracy"]:.1%})'
                  f'   errors: {r["errors"]}')
            print(f'   latency  : avg {r["latency_avg"]}ms   p95 {r["latency_p95"]}ms   total {r["elapsed_s"]:.1f}s')
        except Exception as e:
            print(f'   FAILED: {e}')

    if len(results) > 1:
        print('\n── leaderboard ' + '─' * 60)
        for r in sorted(results, key=lambda x: (-x['accuracy'], x['latency_avg'])):
            print(f'   {r["role"]:<8} {r["model"]:<18} {r["accuracy"]:.1%}  avg {r["latency_avg"]}ms')

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(f'\nWrote {args.out}')


if __name__ == '__main__':
    main()
