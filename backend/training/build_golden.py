"""
Build the per-language golden set files.

Reads the combined `golden/intent_golden.jsonl` and splits it into
`golden_set/intent_en.json`, `intent_fr.json`, `intent_rw.json`. Also copies
the LIS-mapping golden and seeds a small OCR-samples golden.

Why split by language?
  - language-specific accuracy is the metric that actually matters in the field
  - keeps each file small enough to hand-review

Run
---
    cd backend
    python -m training.build_golden --out golden_set
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / 'golden'


def _load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]


def split_intent(out: Path) -> dict[str, int]:
    rows = _load_jsonl(GOLDEN_DIR / 'intent_golden.jsonl')
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_lang[r['language']].append(r)
    written: dict[str, int] = {}
    for lang, items in by_lang.items():
        path = out / f'intent_{lang}.json'
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding='utf-8')
        written[lang] = len(items)
    return written


def copy_lis(out: Path) -> int:
    rows = _load_jsonl(GOLDEN_DIR / 'lis_mapping_golden.jsonl')
    (out / 'lis_mapping.json').write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8',
    )
    return len(rows)


def seed_ocr_samples(out: Path) -> int:
    """Small hand-curated OCR samples (noisy → clean). Locked truth."""
    samples = [
        {
            'noisy': 'P1D: PA-OO1234\nPatient: MUKAMANA Al1ce\nDOB: 14/O3/1992\nSex: F',
            'clean': 'PID: PA-001234\nPatient: MUKAMANA Alice\nDOB: 14/03/1992\nSex: F',
        },
        {
            'noisy': 'Patient: HAB1MANA Er1c\nN1D: 1199580O12345678',
            'clean': 'Patient: HABIMANA Eric\nNID: 1199580012345678',
        },
        {
            'noisy': 'URGENT P1D: PA-OO9876\nDiagnosis: Septlc shock',
            'clean': 'URGENT PID: PA-009876\nDiagnosis: Septic shock',
        },
        {
            'noisy': 'Tests requested: HGB, PLT, PT/1NR, APTT',
            'clean': 'Tests requested: HGB, PLT, PT/INR, APTT',
        },
        {
            'noisy': 'Doctor: Dr NdaylSaba\nWard: 1nternal Medicine',
            'clean': 'Doctor: Dr Ndayisaba\nWard: Internal Medicine',
        },
    ]
    (out / 'ocr_samples.json').write_text(
        json.dumps(samples, indent=2, ensure_ascii=False), encoding='utf-8',
    )
    return len(samples)


def main() -> None:
    ap = argparse.ArgumentParser(description='Build per-language golden set files')
    ap.add_argument('--out', default='golden_set', help='Output directory')
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f'Writing golden sets to {out.resolve()}')

    counts = split_intent(out)
    for lang, n in sorted(counts.items()):
        print(f'  intent_{lang}.json     : {n:>3} rows')

    n_lis = copy_lis(out)
    print(f'  lis_mapping.json    : {n_lis:>3} rows')

    n_ocr = seed_ocr_samples(out)
    print(f'  ocr_samples.json    : {n_ocr:>3} rows')


if __name__ == '__main__':
    main()
