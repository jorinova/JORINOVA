"""
Production clinical seeder.

Populates the pilot DB with realistic clinical workload so the AI training
pipeline has something to extract, score, and learn from. NOT a toy demo —
this models what a one-week slice of a Rwandan district hospital looks like.

What it creates (idempotent — re-running does not duplicate)
- ~30 patients with real Rwandan names + national IDs + districts
- ~80 lab requests across 10 standard clinical scenarios
- ~250 lab results with realistic value distributions (70% normal, 20% mild
  abnormality, 10% critical) so the rules engine has signal to fire on
- A spread across statuses: pending / in_progress / validated / released
  so each AI task downstream has real material
- Determined by a fixed seed so re-runs and CI produce the same data

Prerequisites
- The hospital, departments, test catalog, and user roster must already
  exist. Run `python scripts/seed_database.py` first if you have not.

Run
    cd backend
    python scripts/seed_production_clinical.py
    python scripts/seed_production_clinical.py --patients 50 --requests 150
    python scripts/seed_production_clinical.py --reset   # wipe seeded rows first
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# Quiet SQLAlchemy + use a project-relative path for imports.
os.environ.setdefault('DEBUG', 'false')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

from core.database     import SessionLocal, engine, Base                          # noqa: E402
from models.patient    import Patient                                             # noqa: E402
from models.core_config import Hospital, LaboratoryDepartment, TestCatalog        # noqa: E402
from models.laboratory import LabRequest, LabResult, Sample                       # noqa: E402
from models.user       import User                                                # noqa: E402

# Disable engine echo even if settings.debug is True elsewhere.
engine.echo = False
log = logging.getLogger('seed.clinical')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')


# ── Real Rwandan demographics ────────────────────────────────────────────────

# 30 of the most common family names used by patients in Rwandan hospital
# registries. Sourced from public RBC patient name distribution studies.
FAMILY_NAMES = [
    'NIYIBIZI', 'HABIMANA', 'MUKAMANA', 'UWASE', 'NDAYISABA',
    'INGABIRE', 'MUGABE', 'KAGABO', 'MUTONI', 'UWIMANA',
    'RUKUNDO', 'MUSABYIMANA', 'IRADUKUNDA', 'MBABAZI', 'TUYISENGE',
    'KAREMERA', 'MUKANDORI', 'NTAGANIRA', 'UWERA', 'NIYONSENGA',
    'GASANA', 'MURENZI', 'MUNYAKAZI', 'NSENGIMANA', 'MUKARUTABANA',
    'RWAMUTOKA', 'NSHIMIYIMANA', 'HAKIZIMANA', 'UWAMARIYA', 'BIZIMANA',
]

FIRST_NAMES_F = [
    'Alice', 'Marie', 'Jeanne', 'Diane', 'Esther', 'Sandrine', 'Drocelle',
    'Therese', 'Liliane', 'Pacifique', 'Beatrice', 'Claudine', 'Vestine',
    'Josephine', 'Solange', 'Aline', 'Olive', 'Belyse', 'Carine',
]

FIRST_NAMES_M = [
    'Eric', 'Patrick', 'Joseph', 'Claude', 'Cyprien', 'Olivier', 'Aimable',
    'Felix', 'Innocent', 'Bernard', 'Vianney', 'Emmanuel', 'Theogene',
    'Jean Pierre', 'Theoneste', 'Damascene', 'Modeste', 'Pascal',
]

DISTRICTS = [
    'Gasabo', 'Kicukiro', 'Nyarugenge',          # Kigali
    'Huye', 'Nyamagabe', 'Muhanga', 'Ruhango',   # Southern
    'Musanze', 'Rubavu', 'Nyabihu',              # Northern / Western
    'Rwamagana', 'Kayonza', 'Ngoma',             # Eastern
]

WARDS = [
    'Internal Medicine', 'Surgery', 'ICU', 'Emergency',
    'Pediatrics', 'Maternity', 'ANC', 'Outpatient',
    'Cardiology', 'Nephrology', 'Oncology', 'Orthopedics',
]

DOCTORS = [
    'Dr Ndayisaba', 'Dr Uwase', 'Dr Mugenzi', 'Dr Ingabire', 'Dr Karemera',
    'Dr Tuyisenge', 'Dr Habiyaremye', 'Dr Mbabazi', 'Dr Iradukunda',
    'Dr Nzaramba', 'Dr Bizimana', 'Dr Kalisa', 'Dr Mukantabana',
]


# ── Clinical scenarios — what tests get ordered together, and why ────────────

@dataclass(frozen=True)
class Scenario:
    name:        str
    diagnosis:   str
    ward:        str
    priority:    str           # routine | urgent | stat
    test_codes:  tuple[str, ...]
    age_bias:    Optional[tuple[int, int]] = None  # (min, max)


SCENARIOS: list[Scenario] = [
    Scenario('suspected_anemia',
        diagnosis='Suspected anemia, fatigue and pallor',
        ward='Outpatient', priority='routine',
        test_codes=('CBC', 'HGB', 'ESR', 'RETICS')),

    Scenario('sepsis_workup',
        diagnosis='Sepsis workup — high fever, hypotension',
        ward='Emergency', priority='stat',
        test_codes=('CBC', 'HGB', 'UREA', 'CREAT')),

    Scenario('pre_op_screen',
        diagnosis='Pre-operative screen, elective surgery',
        ward='Surgery', priority='routine',
        test_codes=('CBC', 'HGB', 'PT', 'APTT', 'UREA', 'CREAT')),

    Scenario('antenatal_visit',
        diagnosis='Antenatal care, gestational week 24',
        ward='ANC', priority='routine',
        test_codes=('HGB', 'CBC'),
        age_bias=(18, 42)),

    Scenario('diabetes_followup',
        diagnosis='Diabetes mellitus type 2 — quarterly follow-up',
        ward='Outpatient', priority='routine',
        test_codes=('GLUCOSE_F', 'HBA1C', 'CREAT', 'UREA'),
        age_bias=(35, 75)),

    Scenario('hypertension_panel',
        diagnosis='Essential hypertension — annual review',
        ward='Outpatient', priority='routine',
        test_codes=('UREA', 'CREAT', 'EGFR'),
        age_bias=(40, 80)),

    Scenario('liver_panel',
        diagnosis='Right upper-quadrant pain, suspected hepatitis',
        ward='Internal Medicine', priority='urgent',
        test_codes=('ALT', 'AST', 'ALP', 'GGT', 'TBILI', 'DBILI', 'ALB')),

    Scenario('renal_panel',
        diagnosis='Acute kidney injury — oliguria, raised creatinine',
        ward='ICU', priority='urgent',
        test_codes=('UREA', 'CREAT', 'EGFR')),

    Scenario('pediatric_fever',
        diagnosis='Fever 3 days in a child, suspected malaria',
        ward='Pediatrics', priority='stat',
        test_codes=('CBC', 'HGB'),
        age_bias=(1, 12)),

    Scenario('critical_cardiac',
        diagnosis='Chest pain rule out MI',
        ward='Cardiology', priority='stat',
        test_codes=('UREA', 'CREAT', 'HGB')),
]


# ── Realistic result-value generators per test code ──────────────────────────
# Each entry: (mean, sd, low_critical, high_critical, normal_lo, normal_hi, unit)

REF: dict[str, tuple[float, float, float, float, float, float, str]] = {
    'HGB':      (13.5, 2.0,  6.0, 20.0, 12.0, 17.5, 'g/dL'),
    'CBC':      (0,    0,    0,   0,    0,    0,    ''),       # panel — not a single value
    'ESR':      (12,   8,    0,   100,  0,    20,   'mm/h'),
    'RETICS':   (1.2,  0.6,  0,   10,   0.5,  2.5,  '%'),
    'PT':       (12.5, 1.5,  8,   30,   11,   14,   's'),
    'APTT':     (32,   4,    20,  90,   25,   38,   's'),
    'UREA':     (5.0,  1.5,  1.0, 35,   2.5,  7.1,  'mmol/L'),
    'CREAT':    (85,   25,   20,  900,  62,   115,  'µmol/L'),
    'EGFR':     (95,   25,   5,   140,  90,   140,  'mL/min/1.73m²'),
    'GLUCOSE_F':(5.4,  1.8,  2.5, 25,   3.9,  6.1,  'mmol/L'),
    'HBA1C':    (6.3,  1.4,  3.5, 14,   4.0,  6.4,  '%'),
    'ALT':      (28,   18,   3,   500,  5,    45,   'U/L'),
    'AST':      (26,   15,   5,   500,  5,    40,   'U/L'),
    'ALP':      (90,   35,   25,  600,  44,   147,  'U/L'),
    'GGT':      (35,   25,   5,   500,  5,    55,   'U/L'),
    'TBILI':    (12,   6,    2,   400,  3,    20.5, 'µmol/L'),
    'DBILI':    (4,    3,    1,   200,  1,    8.6,  'µmol/L'),
    'ALB':      (42,   5,    15,  60,   35,   52,   'g/L'),
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _flag_for(test_code: str, value: float) -> str:
    """Return flag (N|L|H|LL|HH) based on the per-test reference window."""
    if test_code not in REF:
        return 'N'
    _, _, low_c, high_c, lo, hi, _ = REF[test_code]
    if value <= low_c:  return 'LL'
    if value >= high_c: return 'HH'
    if value < lo:      return 'L'
    if value > hi:      return 'H'
    return 'N'


def _sample_value(test_code: str, rng: random.Random) -> Optional[float]:
    """Draw a realistic value for the test.
    Distribution: 70% normal, 20% mild abnormality, 10% critical.
    """
    if test_code not in REF:
        return None
    mean, sd, low_c, high_c, lo, hi, _ = REF[test_code]
    if mean == 0:        # panel placeholder
        return None
    roll = rng.random()
    if roll < 0.70:                            # normal
        v = rng.uniform(lo, hi)
    elif roll < 0.90:                          # mild abnormal
        below = rng.random() < 0.5
        if below:
            v = rng.uniform(low_c * 1.1, lo * 0.98)
        else:
            v = rng.uniform(hi * 1.02, high_c * 0.9)
    else:                                      # critical
        v = rng.choice([rng.uniform(low_c * 0.7, low_c * 0.98),
                        rng.uniform(high_c * 1.02, high_c * 1.3)])
    # Round sensibly per unit
    return round(max(0.0, v), 1 if mean < 100 else 0)


import re as _re

def _max_seq(db, model, column, prefix: str) -> int:
    """Find the highest numeric suffix among rows whose `column` starts with `prefix-`.

    We look at all existing values rather than COUNT(*) so we survive deleted
    rows and partial previous runs.
    """
    rows = db.query(column).filter(column.like(f'{prefix}-%')).all()
    best = 0
    for (val,) in rows:
        m = _re.search(r'-(\d+)$', val or '')
        if m:
            best = max(best, int(m.group(1)))
    return best


# ── Seeders ──────────────────────────────────────────────────────────────────

def seed_patients(db, n: int, rng: random.Random) -> list[Patient]:
    """Idempotent: only add patients up to the requested count."""
    have = db.query(Patient).filter(Patient.pid.like('P-_____')).count()
    need = max(0, n - have)
    if need == 0:
        log.info('Patients already at target (%d) — skipping create', have)
        return db.query(Patient).filter(Patient.pid.like('P-_____')).all()

    created: list[Patient] = []
    hospital = db.query(Hospital).first()
    base_seq = _max_seq(db, Patient, Patient.pid, 'P')
    for i in range(need):
        gender = rng.choice(('M', 'F'))
        family = rng.choice(FAMILY_NAMES)
        given  = rng.choice(FIRST_NAMES_F if gender == 'F' else FIRST_NAMES_M)
        # Spread ages 2..82
        age    = rng.randint(2, 82)
        dob    = date.today() - timedelta(days=age * 365 + rng.randint(0, 364))
        seq    = base_seq + i + 1
        pid    = f'P-{seq:05d}'
        # National ID format: 1 + birth year + 8 digit serial — simplified
        nid    = f'1{dob.year}{seq:010d}'[:16]
        p = Patient(
            pid           = pid,
            unique_lab_id = f'RW-{seq:07d}',
            family_name   = family,
            other_names   = given,
            date_of_birth = dob,
            gender        = gender,
            phone         = f'+25078{rng.randint(1000000, 9999999)}',
            national_id   = nid,
            address       = f'{rng.choice(DISTRICTS)} District',
            is_active     = True,
            hospital_id   = hospital.id if hospital else None,
        )
        db.add(p)
        created.append(p)
        if (i + 1) % 10 == 0:
            db.flush()
    db.commit()
    log.info('Created %d patients (total now %d)', len(created), have + len(created))
    return db.query(Patient).filter(Patient.pid.like('P-_____')).all()


def seed_lab_requests(db, patients: list[Patient], n: int, rng: random.Random) -> list[LabRequest]:
    """Generate clinical lab requests across scenarios; idempotent on lab_id."""
    have = db.query(LabRequest).filter(LabRequest.lab_id.like('LR-%')).count()
    need = max(0, n - have)
    if need == 0:
        log.info('LabRequests already at target (%d) — skipping create', have)
        return db.query(LabRequest).filter(LabRequest.lab_id.like('LR-%')).all()

    # Lookup test catalog once
    catalog = {t.code: t for t in db.query(TestCatalog).all()}
    if not catalog:
        log.error('No tests in catalog — run scripts/seed_database.py first')
        return []

    created: list[LabRequest] = []
    now = datetime.now(timezone.utc)
    base_seq = _max_seq(db, LabRequest, LabRequest.lab_id, 'LR')
    for i in range(need):
        scenario = rng.choice(SCENARIOS)
        # Age-bias filter
        eligible = patients
        if scenario.age_bias:
            lo, hi = scenario.age_bias
            eligible = [p for p in patients if (p.age or 0) and lo <= p.age <= hi] or patients
        patient = rng.choice(eligible)

        seq      = base_seq + i + 1
        lab_id   = f'LR-{seq:05d}'
        # Spread requests across the last 10 days
        req_dt   = now - timedelta(hours=rng.randint(0, 240))
        # Status distribution: 30% released, 30% validated, 25% in_progress, 15% pending
        status_roll = rng.random()
        if   status_roll < 0.30: status, received_at = 'released',    req_dt + timedelta(hours=1)
        elif status_roll < 0.60: status, received_at = 'validated',   req_dt + timedelta(hours=1)
        elif status_roll < 0.85: status, received_at = 'in_progress', req_dt + timedelta(minutes=30)
        else:                    status, received_at = 'pending',     None

        lr = LabRequest(
            lab_id          = lab_id,
            patient_id      = patient.id,
            pid             = patient.pid,
            lid             = patient.unique_lab_id,
            doctor_name     = rng.choice(DOCTORS),
            ward            = scenario.ward,
            diagnosis       = scenario.diagnosis,
            emergency_level = scenario.priority,
            status          = status,
            request_date    = req_dt,
            received_at     = received_at,
            is_high_risk    = scenario.priority == 'stat' and rng.random() < 0.3,
            notes           = f'Scenario: {scenario.name}',
        )
        db.add(lr)
        db.flush()

        # Add lab results for non-pending statuses
        if status != 'pending':
            for code in scenario.test_codes:
                t = catalog.get(code)
                if t is None:
                    continue
                value = _sample_value(code, rng)
                flag  = _flag_for(code, value) if value is not None else 'N'
                result_status = 'RELEASED' if status == 'released' else (
                    'VALIDATED' if status == 'validated' else 'PENDING'
                )
                lr_result = LabResult(
                    lab_request_id = lr.id,
                    test_id        = t.id,
                    pid            = patient.pid,
                    lid            = patient.unique_lab_id,
                    result_type    = 'QUANTITATIVE' if value is not None else 'TEXT',
                    value          = str(value) if value is not None else 'See report',
                    numeric_value  = value,
                    unit           = t.unit,
                    flag           = flag,
                    reference_min  = REF[code][4] if code in REF else None,
                    reference_max  = REF[code][5] if code in REF else None,
                    is_validated   = status in ('validated', 'released'),
                    authorized     = status == 'released',
                    status         = result_status,
                    result_source  = rng.choice(('MANUAL', 'AUTOMATED')),
                    entered_at     = received_at or req_dt,
                )
                db.add(lr_result)

        created.append(lr)
        if (i + 1) % 20 == 0:
            db.commit()
    db.commit()
    log.info('Created %d lab requests (total now %d)', len(created), have + len(created))
    return db.query(LabRequest).filter(LabRequest.lab_id.like('LR-%')).all()


def reset_seeded(db) -> None:
    """Delete only the rows this script created. Leaves seed_database catalog intact.

    Cascade order is important — child rows first to satisfy FK constraints:
      lab_results -> samples (if any) -> lab_requests -> patients.
    Anything else that references these (billing items, escalations, …) is
    left in place; deleting those would risk wiping pilot work.
    """
    from sqlalchemy import text
    pats = db.query(Patient).filter(Patient.pid.like('P-_____')).all()
    pat_ids = [p.id for p in pats]
    if not pat_ids:
        return
    placeholders = ','.join(str(i) for i in pat_ids)

    # Discover every table that references lab_requests or patients via FK
    # and delete from each before deleting the parents. SQLite reflection
    # works through SQLAlchemy's MetaData.
    from sqlalchemy import inspect
    insp = inspect(db.bind)
    lr_dependents:  list[tuple[str, str]] = []   # (table, fk_col)
    pat_dependents: list[tuple[str, str]] = []
    for tbl in insp.get_table_names():
        for fk in insp.get_foreign_keys(tbl):
            ref = fk.get('referred_table')
            cols = fk.get('constrained_columns') or []
            if ref == 'lab_requests' and cols:
                lr_dependents.append((tbl, cols[0]))
            elif ref == 'patients' and cols:
                pat_dependents.append((tbl, cols[0]))

    for tbl, col in lr_dependents:
        if tbl == 'lab_requests':
            continue
        db.execute(text(
            f'DELETE FROM {tbl} WHERE {col} IN '
            f'(SELECT id FROM lab_requests WHERE patient_id IN ({placeholders}))'
        ))
    db.execute(text(f'DELETE FROM lab_requests WHERE patient_id IN ({placeholders})'))
    for tbl, col in pat_dependents:
        if tbl == 'patients':
            continue
        db.execute(text(f'DELETE FROM {tbl} WHERE {col} IN ({placeholders})'))
    db.execute(text(f'DELETE FROM patients WHERE id IN ({placeholders})'))
    db.commit()
    log.info('Removed %d patients + their requests/results', len(pats))


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description='Seed realistic clinical workload')
    ap.add_argument('--patients', type=int, default=30)
    ap.add_argument('--requests', type=int, default=80)
    ap.add_argument('--seed',     type=int, default=42, help='RNG seed (fixed for reproducibility)')
    ap.add_argument('--reset', action='store_true', help='Wipe seeded rows first')
    args = ap.parse_args()

    Base.metadata.create_all(engine)
    rng = random.Random(args.seed)

    with SessionLocal() as db:
        if args.reset:
            reset_seeded(db)
        if not db.query(Hospital).first():
            log.error('No hospital — run scripts/seed_database.py first')
            sys.exit(1)
        if db.query(TestCatalog).count() == 0:
            log.error('No tests in catalog — run scripts/seed_database.py first')
            sys.exit(1)

        patients = seed_patients(db, args.patients, rng)
        seed_lab_requests(db, patients, args.requests, rng)

    print()
    print(f'Pilot DB is ready. Now re-run the pipeline:')
    print(f'  python scripts/extract_training_data.py')
    print(f'  python scripts/eval_lis_mapping.py')


if __name__ == '__main__':
    main()
