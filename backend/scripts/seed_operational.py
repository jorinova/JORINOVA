"""
Operational seed data: specimens, daily rack counters, universal operators.

The training/AI workstreams don't need these, but the production HTTP layer
does — and so does the test_production_core P3 suite. Run once after
seed_database.py to bring a fresh install up to production-ready state.

Idempotent — re-running is safe.

Run
    cd backend
    python scripts/seed_operational.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault('DEBUG', 'false')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

from core.database import SessionLocal, engine, Base                              # noqa: E402
from models.worklist import SpecimenTypeConfig, Daily24hRackCounter               # noqa: E402
from models.universal import UniversalOperator                                    # noqa: E402
from models.core_config import Hospital                                           # noqa: E402

engine.echo = False
log = logging.getLogger('seed.operational')
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')


# ── Specimen types (Rwanda standard pre-analytical panel) ───────────────────

SPECIMEN_TYPES = [
    # (acronym, name, primary_department, tube_color, generates_cid, volume_ml, sort_order)
    ('SST', 'Serum Separator Tube',      'biochemistry', 'gold',     False, 4.0,  10),
    ('EDT', 'EDTA Whole Blood',          'hematology',   'lavender', False, 3.0,  20),
    ('CIT', 'Citrate Plasma',            'coagulation',  'blue',     False, 2.7,  30),
    ('FLU', 'Sodium Fluoride Plasma',    'biochemistry', 'grey',     False, 2.0,  40),
    ('URN', 'Urine (random / midstream)','urinalysis',   'yellow',   True,  10.0, 50),
    ('STL', 'Stool sample',              'microbiology', 'brown',    True,  5.0,  60),
    ('CSF', 'Cerebrospinal Fluid',       'microbiology', 'clear',    True,  2.0,  70),
    ('SWA', 'Swab (wound/throat/cervix)','microbiology', 'clear',    True,  1.0,  80),
    ('SPU', 'Sputum',                    'microbiology', 'clear',    True,  3.0,  90),
    ('BLD', 'Blood culture bottle',      'microbiology', 'navy',     True,  8.0,  100),
    ('BMR', 'Bone Marrow Aspirate',      'hematology',   'lavender', True,  2.0,  110),
    ('TIS', 'Tissue / biopsy',           'pathology',    'clear',    True,  1.0,  120),
]


def seed_specimens(db) -> int:
    have = db.query(SpecimenTypeConfig).count()
    if have >= len(SPECIMEN_TYPES):
        log.info('Specimens already at target (%d) — skipping', have)
        return 0
    added = 0
    for acronym, name, dept, tube, gen_cid, vol, order in SPECIMEN_TYPES:
        if db.query(SpecimenTypeConfig).filter(SpecimenTypeConfig.acronym == acronym).first():
            continue
        db.add(SpecimenTypeConfig(
            acronym=acronym, name=name, primary_department=dept,
            tube_color=tube, generates_cid=gen_cid, volume_ml=vol,
            sort_order=order, is_active=True,
        ))
        added += 1
    db.commit()
    log.info('Created %d specimen types (total %d)', added, have + added)
    return added


# ── Daily 24-hour rack counters (one per department for today) ───────────────

RACK_DEPARTMENTS = [
    'hematology', 'biochemistry', 'coagulation', 'urinalysis',
    'microbiology', 'molecular', 'serology', 'blood_bank',
]


def seed_today_rack_counters(db) -> int:
    today = date.today()
    have = db.query(Daily24hRackCounter).filter(
        Daily24hRackCounter.counter_date == today,
    ).count()
    if have >= len(RACK_DEPARTMENTS):
        log.info('Rack counters for %s already at target (%d)', today, have)
        return 0
    added = 0
    for dept in RACK_DEPARTMENTS:
        existing = db.query(Daily24hRackCounter).filter(
            Daily24hRackCounter.department == dept,
            Daily24hRackCounter.counter_date == today,
        ).first()
        if existing:
            continue
        db.add(Daily24hRackCounter(department=dept, counter_date=today, last_number=0))
        added += 1
    db.commit()
    log.info('Created %d rack counters for %s (total %d)', added, today, have + added)
    return added


# ── Universal operators (lab roster: lab manager + scientists + receptionist…)

OPERATORS = [
    # short_name, full_name, role_type, roles, email, phone, shift_start, shift_end
    ('AdminSys',  'System Administrator',    'super_admin',  ['admin', 'audit'],
     'admin@nexus.rw', '+250788000001', '08:00', '17:00'),
    ('Mutabazi',  'Jean Mutabazi',           'lab_manager',  ['manage', 'validate', 'release'],
     'jmutabazi@nexus.rw', '+250788000002', '07:00', '16:00'),
    ('Uwimana',   'Marie Uwimana',           'scientist',    ['hematology', 'validate'],
     'muwimana@nexus.rw', '+250788000003', '07:00', '15:00'),
    ('Nkurunziza','Patrick Nkurunziza',      'scientist',    ['hematology'],
     'pnkuru@nexus.rw',   '+250788000004', '15:00', '23:00'),
    ('Mukamana',  'Alice Mukamana',          'scientist',    ['biochemistry'],
     'amukamana@nexus.rw','+250788000005', '07:00', '15:00'),
    ('Ingabire',  'Grace Ingabire',          'receptionist', ['reception', 'phlebotomy'],
     'gingabire@nexus.rw','+250788000006', '07:00', '15:00'),
    ('Habimana',  'Dr. Paul Habimana',       'pathologist',  ['pathology', 'authorize'],
     'phabimana@nexus.rw','+250788000007', '08:00', '17:00'),
    ('Tuyisenge', 'Esther Tuyisenge',        'scientist',    ['serology', 'microbiology'],
     'etuyi@nexus.rw',    '+250788000008', '15:00', '23:00'),
    ('Karemera',  'Olivier Karemera',        'scientist',    ['molecular'],
     'okaremera@nexus.rw','+250788000009', '07:00', '15:00'),
    ('Bizimana',  'Bernard Bizimana',        'scientist',    ['blood_bank'],
     'bbizimana@nexus.rw','+250788000010', '07:00', '15:00'),
    ('Nzaramba',  'Cyprien Nzaramba',        'scientist',    ['coagulation', 'urinalysis'],
     'cnzaramba@nexus.rw','+250788000011', '15:00', '23:00'),
    ('Mbabazi',   'Liliane Mbabazi',         'scientist',    ['biochemistry', 'validate'],
     'lmbabazi@nexus.rw', '+250788000012', '23:00', '07:00'),
]


def seed_operators(db) -> int:
    have = db.query(UniversalOperator).count()
    if have >= len(OPERATORS):
        log.info('Operators already at target (%d) — skipping', have)
        return 0
    hospital = db.query(Hospital).first()
    added = 0
    for short, full, role_type, roles, email, phone, ss, se in OPERATORS:
        if db.query(UniversalOperator).filter(UniversalOperator.short_name == short).first():
            continue
        db.add(UniversalOperator(
            short_name=short, full_name=full, role_type=role_type,
            roles=json.dumps(roles),
            email=email, phone=phone,
            default_hours_per_day=8.0, shift_start=ss, shift_end=se,
            is_active=True, hospital_id=hospital.id if hospital else None,
        ))
        added += 1
    db.commit()
    log.info('Created %d universal operators (total %d)', added, have + added)
    return added


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_specimens(db)
        seed_today_rack_counters(db)
        seed_operators(db)
    print('Operational seed complete.')


if __name__ == '__main__':
    main()
