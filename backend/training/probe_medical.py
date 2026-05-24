"""
Medical-knowledge probe.

Asks each Ollama worker a fixed set of lab-grade questions and compares
the answer against the curated truth in medical_knowledge.py. Grades:

  CORRECT     — answer contains every must-have keyword
  PARTIAL     — answer contains some keywords but is incomplete
  WRONG       — answer contradicts truth (hallucination)
  REFUSED     — model declined / unknown

Why this matters
- Tells you exactly what the local model is allowed to answer alone
  vs. what MUST go through RAG or the rules engine.
- Re-run after any model swap or fine-tune to track progress.

Run
    cd backend
    python -m training.probe_medical
    python -m training.probe_medical --model phi3:mini --only "stain,parasit"
"""
from __future__ import annotations

import argparse
import asyncio
import json
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

from ai_services import local_llm                                              # noqa: E402
from core.config import get_settings                                           # noqa: E402


# ── Probe questions ──────────────────────────────────────────────────────────
# Each: prompt → list of substrings that MUST appear in a correct answer.
# (lowercase comparison). Grouped by domain so --only filtering is useful.

PROBES = [
    # ── Common abbreviations (LLMs should crush these) ───────────────────
    ('abbrev', 'What does CBC stand for in laboratory medicine?',
        ['complete blood count']),
    ('abbrev', 'What does TAT mean in lab workflow?',
        ['turnaround', 'time']),
    ('abbrev', 'What does GE refer to in Rwandan / French laboratory practice?',
        ['goutte', 'thick']),
    ('abbrev', 'What does PTME stand for? (Rwandan/French medical context)',
        ['prevention', 'mother', 'child', 'transmission']),

    # ── Staining methods (where LLMs hallucinate) ────────────────────────
    ('stain', 'What are the four reagents used in a Gram stain in order?',
        ['crystal violet', 'iodine', 'alcohol', 'safranin']),
    ('stain', 'In a positive Ziehl-Neelsen (ZN) acid-fast stain, what colour are the bacilli and on what background?',
        ['red', 'blue']),
    ('stain', 'Which stain is the gold standard for malaria parasite identification and quantification?',
        ['giemsa']),
    ('stain', 'On CHROMagar, what colour does Candida albicans appear?',
        ['green']),
    ('stain', 'India ink is used to visualise the capsule of which yeast pathogen?',
        ['cryptococcus']),

    # ── Parasitology / mycology ──────────────────────────────────────────
    ('parasit', 'Which Plasmodium species causes the most severe form of malaria?',
        ['falciparum']),
    ('parasit', 'In a Giemsa-stained blood smear, what intracellular form is diagnostic of Leishmania?',
        ['amastigote']),
    ('mycol', 'For Cryptococcus neoformans, what specimen + stain combination is the rapid bedside diagnostic?',
        ['csf', 'india ink']),

    # ── Critical / panic values (LLMs invent numbers) ────────────────────
    ('critical', 'What is the adult critical low haemoglobin (Hgb) value below which the lab must notify the clinician immediately?',
        ['7', 'g/dl']),
    ('critical', 'What potassium value (in mmol/L) is considered an adult critical high requiring immediate notification?',
        ['6']),
    ('critical', 'What random blood glucose value (in mmol/L) is the critical high threshold?',
        ['22']),

    # ── Reference ranges ─────────────────────────────────────────────────
    ('ref', 'What is the adult male reference range for haemoglobin in g/dL?',
        ['13', '17']),
    ('ref', 'What is the adult reference range for fasting blood glucose in mmol/L?',
        ['3.9', '6.1']),
    ('ref', 'For an adult non-pregnant patient, what is the normal TSH reference range in mIU/L?',
        ['0.27', '4.2']),

    # ── Specimen / tube colour (lab-bench essentials) ───────────────────
    ('tube', 'Which tube colour (additive) is required for a CBC?',
        ['edta', 'lavender']),
    ('tube', 'Which tube colour is required for a fasting glucose?',
        ['fluoride', 'grey']),
    ('tube', 'Which tube colour is required for prothrombin time (PT) / coagulation?',
        ['citrate', 'blue']),

    # ── Immunology / serology ────────────────────────────────────────────
    ('immuno', 'In hepatitis B serology, what does a positive HBsAg with negative anti-HBs indicate?',
        ['active', 'infection']),
    ('immuno', 'A 4th-generation HIV test detects which two markers?',
        ['p24', 'antibod']),

    # ── Histotechnology ──────────────────────────────────────────────────
    ('histo', 'Which stain is used routinely on paraffin-embedded tissue sections to show basic histological architecture?',
        ['haematoxylin', 'eosin']),
    ('histo', 'What stain is used to demonstrate connective tissue (collagen) in a tissue section?',
        ['masson', 'trichrome']),
    ('histo', 'Which stain demonstrates Pneumocystis jirovecii cysts in lung tissue?',
        ['silver']),
]


# Normalise tuples to a uniform dict so the loader is happy
def _to_record(item):
    domain, prompt, must = item
    return {'domain': domain, 'prompt': prompt, 'must': [m.lower() for m in must]}


def _build_probes():
    out = []
    for it in PROBES:
        domain, prompt, must = it
        out.append({'domain': domain, 'prompt': prompt, 'must': [m.lower() for m in must]})
    return out


def grade(answer: str, must: list[str]) -> str:
    """CORRECT if every keyword present; PARTIAL if some; WRONG if direct
    negation of truth; REFUSED if the model said it didn't know."""
    a = (answer or '').lower()
    if not a.strip():
        return 'REFUSED'
    if 'i do not know' in a or "i don't know" in a or 'cannot determine' in a:
        return 'REFUSED'
    hits = sum(1 for m in must if m in a)
    if hits == len(must):
        return 'CORRECT'
    if hits == 0:
        return 'WRONG'
    return 'PARTIAL'


SYSTEM = (
    'You are a clinical laboratory assistant. Answer briefly and factually. '
    'If you do not know, say so. Do not invent numbers.'
)


async def ask_one(model: str, prompt: str) -> tuple[str, int]:
    resp = await local_llm.generate(
        prompt=prompt, system=SYSTEM,
        model=model, max_tokens=160, temperature=0.0,
        use_cache=False, timeout_s=45.0,
    )
    if resp.error:
        return f'ERROR: {resp.error[:120]}', resp.latency_ms
    return resp.content.strip(), resp.latency_ms


async def run_probe(model: str, probes: list[dict]) -> dict:
    by_grade  = {'CORRECT': 0, 'PARTIAL': 0, 'WRONG': 0, 'REFUSED': 0, 'ERROR': 0}
    by_domain: dict[str, dict] = {}
    rows = []
    t0 = time.time()
    for p in probes:
        ans, lat = await ask_one(model, p['prompt'])
        g = 'ERROR' if ans.startswith('ERROR:') else grade(ans, p['must'])
        by_grade[g] = by_grade.get(g, 0) + 1
        d = by_domain.setdefault(p['domain'], {'CORRECT': 0, 'PARTIAL': 0, 'WRONG': 0, 'REFUSED': 0, 'ERROR': 0, 'n': 0})
        d['n'] += 1; d[g] = d.get(g, 0) + 1
        rows.append({'domain': p['domain'], 'prompt': p['prompt'], 'must': p['must'],
                     'answer': ans, 'grade': g, 'latency_ms': lat})
    return {'model': model, 'n': len(probes), 'by_grade': by_grade,
            'by_domain': by_domain, 'rows': rows,
            'elapsed_s': time.time() - t0}


def print_report(r: dict, show_rows: bool = False) -> None:
    print(f"\n── {r['model']} {'─' * (56 - len(r['model']))}")
    g = r['by_grade']
    n = r['n']
    print(f'  correct   : {g["CORRECT"]}/{n}  ({g["CORRECT"]/n:.0%})')
    print(f'  partial   : {g["PARTIAL"]}/{n}  ({g["PARTIAL"]/n:.0%})')
    print(f'  wrong     : {g["WRONG"]}/{n}  ({g["WRONG"]/n:.0%})')
    print(f'  refused   : {g["REFUSED"]}/{n}  ({g["REFUSED"]/n:.0%})')
    if g.get('ERROR'):
        print(f'  errors    : {g["ERROR"]}/{n}')
    print(f'  elapsed   : {r["elapsed_s"]:.1f}s')

    print('  by domain :')
    for dom in sorted(r['by_domain']):
        d = r['by_domain'][dom]
        nn = d['n']
        print(f'    {dom:<10}  C={d["CORRECT"]}/{nn} '
              f'P={d["PARTIAL"]}/{nn} W={d["WRONG"]}/{nn} R={d["REFUSED"]}/{nn}')

    if show_rows:
        print('\n  hallucinations + refusals:')
        for row in r['rows']:
            if row['grade'] in ('WRONG', 'REFUSED'):
                print(f"    [{row['grade']:<7}] {row['domain']:<8}  {row['prompt'][:75]}…")
                print(f"            ans: {row['answer'][:140]}")


def main() -> None:
    ap = argparse.ArgumentParser(description='Probe Ollama workers on lab-grade medical knowledge')
    ap.add_argument('--model',   help='Run only this model name')
    ap.add_argument('--only',    help='Comma-separated domain filter (e.g. stain,parasit,mycol)')
    ap.add_argument('--detail',  action='store_true', help='Show every wrong / refused answer')
    ap.add_argument('--out',     help='Optional JSON file to write the full results to')
    args = ap.parse_args()

    s = get_settings()
    probes = _build_probes()
    if args.only:
        wanted = set(p.strip() for p in args.only.split(','))
        probes = [p for p in probes if p['domain'] in wanted]
        print(f'Filtered to {len(probes)} probes (domains: {sorted(wanted)})')

    if args.model:
        models = [args.model]
    else:
        models = [s.ollama_model_fast, s.ollama_model_deep, s.ollama_model_chat,
                  s.ollama_model_general, s.ollama_model_fallback]
        models = [m for m in dict.fromkeys(models) if m]   # de-dupe, preserve order

    print(f'Probing {len(models)} model(s) against {len(probes)} questions...')
    results = []
    for m in models:
        try:
            r = asyncio.run(run_probe(m, probes))
            results.append(r)
            print_report(r, show_rows=args.detail)
        except Exception as e:
            print(f'\n── {m} FAILED: {e}')

    if len(results) > 1:
        print('\n── leaderboard ' + '─' * 56)
        ranked = sorted(results,
                        key=lambda r: (-r['by_grade']['CORRECT'], r['elapsed_s']))
        for r in ranked:
            c = r['by_grade']['CORRECT']; w = r['by_grade']['WRONG']
            print(f"  {r['model']:<22}  C={c}/{r['n']} ({c/r['n']:.0%})  "
                  f"W={w}/{r['n']}  {r['elapsed_s']:.0f}s")

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(f'\nWrote {args.out}')


if __name__ == '__main__':
    main()
