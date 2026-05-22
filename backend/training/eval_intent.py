"""
Intent-classifier eval harness.

Loads training/golden/intent_golden.jsonl and runs every example through the
chosen cascade stage (regex-only, local-LLM, cloud, full-auto). Prints an
accuracy table + a confusion summary so you can see where the misses are.

Run
---
    cd backend
    python -m training.eval_intent                 # all stages
    python -m training.eval_intent --stage regex   # just the regex baseline
    python -m training.eval_intent --stage local   # add local LLM (needs Ollama)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

# Force UTF-8 stdout on Windows (box-drawing chars die under cp1252).
try:
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_services import training_intent as ti                         # noqa: E402

GOLDEN = Path(__file__).parent / 'golden' / 'intent_golden.jsonl'


def _load_golden() -> list[dict]:
    return [json.loads(line) for line in GOLDEN.read_text(encoding='utf-8').splitlines() if line.strip()]


async def _run_stage(rows: list[dict], stage: str) -> dict:
    """stage ∈ {'regex', 'local', 'cloud', 'auto'}"""
    use_llm  = stage != 'regex'
    provider = {'regex': 'none', 'local': 'local', 'cloud': 'cloud', 'auto': 'auto'}[stage]

    correct       = 0
    confusion     = defaultdict(Counter)            # gold → predicted → count
    by_lang_total = Counter()
    by_lang_ok    = Counter()
    misses        = []                              # (text, lang, gold, pred, src)
    t0 = time.time()

    for r in rows:
        pred = await ti.classify(r['text'], r['language'], use_llm=use_llm, provider=provider)  # type: ignore[arg-type]
        got  = pred.get('intent', 'unknown')
        gold = r['intent']
        ok   = got == gold

        confusion[gold][got] += 1
        by_lang_total[r['language']] += 1
        if ok:
            correct += 1
            by_lang_ok[r['language']] += 1
        else:
            misses.append((r['text'], r['language'], gold, got, pred.get('source', '?')))

    elapsed = time.time() - t0
    return {
        'stage':       stage,
        'n':           len(rows),
        'correct':     correct,
        'accuracy':    correct / len(rows) if rows else 0.0,
        'elapsed_s':   elapsed,
        'by_lang':     {lang: by_lang_ok[lang] / by_lang_total[lang] for lang in by_lang_total},
        'confusion':   {k: dict(v) for k, v in confusion.items()},
        'misses':      misses,
    }


def _print_report(report: dict, show_misses: bool) -> None:
    s = report
    print(f'\n── stage: {s["stage"]:<6}  ' + '─' * 56)
    print(f'   accuracy : {s["correct"]:>3}/{s["n"]:<3}  ({s["accuracy"]:.1%})   elapsed: {s["elapsed_s"]:.1f}s')
    print('   per lang :', ' '.join(f'{l}={v:.0%}' for l, v in sorted(s['by_lang'].items())))

    if show_misses and s['misses']:
        print(f'   misses   ({len(s["misses"])}):')
        for text, lang, gold, pred, src in s['misses']:
            print(f'     [{lang}] "{text[:60]}"  gold={gold:<8} pred={pred:<8} via={src}')


def main() -> None:
    ap = argparse.ArgumentParser(description='Score the intent classifier on the golden set')
    ap.add_argument('--stage', choices=['regex', 'local', 'cloud', 'auto', 'all'], default='all')
    ap.add_argument('--quiet', action='store_true', help='Suppress per-miss listing')
    args = ap.parse_args()

    rows = _load_golden()
    print(f'Golden set: {len(rows)} examples from {GOLDEN.relative_to(Path.cwd()) if str(GOLDEN).startswith(str(Path.cwd())) else GOLDEN}')

    stages = ['regex', 'local', 'cloud', 'auto'] if args.stage == 'all' else [args.stage]
    reports = []
    for stage in stages:
        try:
            reports.append(asyncio.run(_run_stage(rows, stage)))
        except Exception as e:
            print(f'\n── stage: {stage:<6}  SKIPPED: {e}')

    for r in reports:
        _print_report(r, show_misses=not args.quiet)

    if len(reports) > 1:
        print('\n── leaderboard ' + '─' * 60)
        for r in sorted(reports, key=lambda x: -x['accuracy']):
            print(f'   {r["stage"]:<6}  {r["accuracy"]:.1%}   ({r["correct"]}/{r["n"]})   {r["elapsed_s"]:.1f}s')


if __name__ == '__main__':
    main()
