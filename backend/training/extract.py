"""
Dataset extractor: pilot DB → JSONL training files.

One JSONL per task. Each line is a self-describing record so the file can be
loaded by any downstream trainer (LoRA, RAG index, eval harness, …) without
extra plumbing.

Run
---
    cd backend
    python -m training.extract --out training/datasets

Output files (created if absent, overwritten if present):
    intent.jsonl         {text, language, intent}
    lis_mapping.jsonl    {raw_text, patient_pid, tests[], priority}
    clinical.jsonl       {request, results[], interpretation}
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Iterable

# Force-disable debug *before* any backend module loads — otherwise
# settings.debug=True causes SQLAlchemy to echo every query.
import os                                                              # noqa: E402
os.environ.setdefault('DEBUG', 'false')

# Allow `python -m training.extract` from the backend directory
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.database import SessionLocal, engine                         # noqa: E402
from models.laboratory import LabRequest, LabResult                   # noqa: E402
from models.patient import Patient                                    # noqa: E402

# Belt + suspenders: turn off engine echo and the SQLAlchemy loggers.
engine.echo = False
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy').setLevel(logging.WARNING)

log = logging.getLogger('training.extract')


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open('w', encoding='utf-8') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            n += 1
    return n


# ── Task 1: intent (real DB has no transcripts; pull from synthetic) ──────────

def extract_intent(out_dir: Path) -> int:
    """Intent training data is fully synthetic today — see synthetic.py."""
    from training.synthetic import intent_corpus
    rows = list(intent_corpus())
    return _write_jsonl(out_dir / 'intent.jsonl', rows)


# ── Task 2: LIS mapping (real lab requests → reverse-engineered raw text) ─────

def extract_lis_mapping(out_dir: Path) -> int:
    """
    Each LabRequest in the DB becomes one training row by reconstructing what
    the OCR'd request form would have said. This is *weak supervision* —
    perfect ground truth, imperfect input — but it's free and gives the
    extractor real distributional samples.
    """
    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        reqs = db.query(LabRequest).limit(2000).all()
        for r in reqs:
            patient = r.patient
            if patient is None:
                continue

            test_codes = [
                res.test.code for res in r.results
                if res.test and res.test.code
            ]
            raw_text = _synthesize_request_form(patient, r, test_codes)

            rows.append({
                'raw_text':    raw_text,
                'patient_pid': patient.pid,
                'patient_lid': patient.unique_lab_id,
                'tests':       test_codes,
                'priority':    r.emergency_level or 'routine',
                'doctor':      r.doctor_name,
                'ward':        r.ward,
                'diagnosis':   r.diagnosis,
            })
    return _write_jsonl(out_dir / 'lis_mapping.jsonl', rows)


def _synthesize_request_form(p: Patient, r: LabRequest, tests: list[str]) -> str:
    """Cheap text reconstruction of what an OCR'd form would have read."""
    parts = [
        f'PID: {p.pid}',
        f'Patient: {p.family_name} {p.other_names or ""}'.strip(),
    ]
    if p.date_of_birth:
        parts.append(f'DOB: {p.date_of_birth.strftime("%d/%m/%Y")}')
    if p.gender:
        parts.append(f'Sex: {p.gender}')
    if p.national_id:
        parts.append(f'NID: {p.national_id}')
    if r.doctor_name:
        parts.append(f'Doctor: {r.doctor_name}')
    if r.ward:
        parts.append(f'Ward: {r.ward}')
    if r.diagnosis:
        parts.append(f'Diagnosis: {r.diagnosis}')
    if (r.emergency_level or '').lower() in ('stat', 'urgent'):
        parts.append(r.emergency_level.upper())
    parts.append('Tests requested: ' + ', '.join(tests) if tests else 'Tests requested: -')
    return '\n'.join(parts)


# ── Task 3: clinical interpretation (results → human-readable summary) ────────

def extract_clinical(out_dir: Path) -> int:
    """
    Pair each completed LabRequest with its results so a downstream trainer
    can learn the interpretation task. Interpretation field is left blank
    when we don't have one — the trainer fills it via Claude/clinician later.
    """
    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        reqs = (
            db.query(LabRequest)
              .filter(LabRequest.status.in_(('validated', 'released')))
              .limit(2000)
              .all()
        )
        for r in reqs:
            results = [
                {
                    'test_code': res.test.code if res.test else None,
                    'test_name': res.test.name if res.test else None,
                    'value':     getattr(res, 'value_text', None) or getattr(res, 'value_numeric', None),
                    'unit':      getattr(res, 'unit', None),
                    'flag':      getattr(res, 'flag', None),
                }
                for res in r.results
            ]
            if not results:
                continue
            rows.append({
                'request_id':     r.lab_id,
                'patient_pid':    r.patient.pid if r.patient else None,
                'diagnosis':      r.diagnosis,
                'results':        results,
                'interpretation': '',                       # to be filled by trainer
            })
    return _write_jsonl(out_dir / 'clinical.jsonl', rows)


# ── CLI ───────────────────────────────────────────────────────────────────────

# ── Task 4: OCR cleanup pairs (noisy → clean) ────────────────────────────────

def extract_ocr(out_dir: Path, n_per_seed: int = 3) -> int:
    """
    Build (noisy, clean) pairs for the OCR-cleanup task. Real lab-request
    rows in the DB become the clean half; the noisy half is synthesised by
    applying OCR-style perturbations. If the DB is empty, we still emit
    rows from a small fallback template set so downstream eval has data.
    """
    from training.ocr_synth import ocr_pairs

    seeds: list[str] = []
    try:
        with SessionLocal() as db:
            reqs = db.query(LabRequest).limit(500).all()
            for r in reqs:
                p = r.patient
                if p is None:
                    continue
                test_codes = [res.test.code for res in r.results if res.test and res.test.code]
                seeds.append(_synthesize_request_form(p, r, test_codes))
    except Exception:
        seeds = []

    rows = list(ocr_pairs(seed_texts=seeds, n_per_seed=n_per_seed))
    return _write_jsonl(out_dir / 'ocr.jsonl', rows)


def main() -> None:
    ap = argparse.ArgumentParser(description='Extract training data from the pilot DB')
    ap.add_argument('--out', default='training/datasets', help='Output directory')
    ap.add_argument('--task', choices=['intent', 'lis', 'ocr', 'clinical', 'all'], default='all')
    args = ap.parse_args()

    out = Path(args.out)
    print(f'Writing datasets to {out.resolve()}')

    if args.task in ('intent', 'all'):
        n = extract_intent(out)
        print(f'  intent.jsonl       : {n:>6} rows')
    if args.task in ('lis', 'all'):
        try:
            n = extract_lis_mapping(out)
            print(f'  lis_mapping.jsonl  : {n:>6} rows')
        except Exception as e:
            print(f'  lis_mapping.jsonl  : SKIPPED ({e})')
    if args.task in ('ocr', 'all'):
        try:
            n = extract_ocr(out)
            print(f'  ocr.jsonl          : {n:>6} rows')
        except Exception as e:
            print(f'  ocr.jsonl          : SKIPPED ({e})')
    if args.task in ('clinical', 'all'):
        try:
            n = extract_clinical(out)
            print(f'  clinical.jsonl     : {n:>6} rows')
        except Exception as e:
            print(f'  clinical.jsonl     : SKIPPED ({e})')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    main()
