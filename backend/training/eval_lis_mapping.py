"""
LIS-mapping eval harness — DB-free.

Scores the regex-driven extractors in ai_services.lis_mapping against
training/golden/lis_mapping_golden.jsonl. Targets the parts of the pipeline
that DON'T need a database session: patient fields, priority, and the raw
test-name candidates.

Run
---
    cd backend
    python -m training.eval_lis_mapping
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')   # type: ignore[attr-defined]
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_services.lis_mapping import (                                 # noqa: E402
    _detect_priority, _extract_patient_fields, _extract_test_candidates,
)

GOLDEN = Path(__file__).parent / 'golden' / 'lis_mapping_golden.jsonl'

# golden key  →  attr on PatientMatch dataclass
PATIENT_FIELD_MAP = {
    'patient_pid':  'pid',
    'family_name':  'family_name',
    'gender':       'gender',
    'national_id':  'national_id',
}
PATIENT_FIELDS = tuple(PATIENT_FIELD_MAP)


def _load_golden() -> list[dict]:
    return [json.loads(line) for line in GOLDEN.read_text(encoding='utf-8').splitlines() if line.strip()]


def _score_field(pred, gold) -> tuple[bool, bool]:
    """Returns (counted, correct). 'counted' is False when both are None."""
    if gold is None and (pred is None or pred == ''):
        return False, False
    return True, str(pred or '').strip().lower() == str(gold or '').strip().lower()


def _score_tests(predicted_candidates: list[str], expected: list[str]) -> tuple[int, int, int]:
    """Returns (true_positives, false_positives, false_negatives)."""
    pred_norm = {c.strip().lower() for c in predicted_candidates}
    gold_norm = {c.strip().lower() for c in expected}
    tp = len(pred_norm & gold_norm)
    fp = len(pred_norm - gold_norm)
    fn = len(gold_norm - pred_norm)
    return tp, fp, fn


def main() -> None:
    ap = argparse.ArgumentParser(description='Score LIS extractors on the golden set')
    ap.add_argument('--show-misses', action='store_true')
    args = ap.parse_args()

    rows = _load_golden()
    print(f'Golden set: {len(rows)} examples\n')

    field_total   = {f: 0 for f in PATIENT_FIELDS}
    field_correct = {f: 0 for f in PATIENT_FIELDS}
    priority_correct = 0
    tp_total = fp_total = fn_total = 0
    misses: list[str] = []

    for i, row in enumerate(rows, 1):
        raw      = row['raw_text']
        exp      = row['expected']

        pm       = _extract_patient_fields(raw)
        priority = _detect_priority(raw)
        tests    = _extract_test_candidates(raw)

        # Patient fields
        for f in PATIENT_FIELDS:
            pred = getattr(pm, PATIENT_FIELD_MAP[f], None)
            counted, ok = _score_field(pred, exp.get(f))
            if counted:
                field_total[f]   += 1
                if ok:
                    field_correct[f] += 1
                else:
                    misses.append(f'  #{i} {f}: pred={pred!r}  gold={exp.get(f)!r}')

        # Priority
        if (priority or '').lower() == (exp.get('priority') or 'routine').lower():
            priority_correct += 1
        else:
            misses.append(f'  #{i} priority: pred={priority!r}  gold={exp.get("priority")!r}')

        # Tests (set-overlap)
        tp, fp, fn = _score_tests(tests, exp.get('tests', []))
        tp_total += tp; fp_total += fp; fn_total += fn

    print('── Patient fields ' + '─' * 50)
    for f in PATIENT_FIELDS:
        denom = field_total[f] or 1
        acc   = field_correct[f] / denom
        print(f'   {f:<14}  {field_correct[f]:>2}/{field_total[f]:<2}  ({acc:.0%})')

    print('\n── Priority ' + '─' * 56)
    print(f'   accuracy       {priority_correct:>2}/{len(rows):<2}  ({priority_correct/len(rows):.0%})')

    print('\n── Tests (set-overlap) ' + '─' * 45)
    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) else 0.0
    recall    = tp_total / (tp_total + fn_total) if (tp_total + fn_total) else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    print(f'   tp={tp_total}  fp={fp_total}  fn={fn_total}')
    print(f'   precision={precision:.0%}   recall={recall:.0%}   f1={f1:.0%}')

    if args.show_misses and misses:
        print('\n── Misses ' + '─' * 58)
        for m in misses:
            print(m)


if __name__ == '__main__':
    main()
