"""
Worklist Preparation Service
==============================
Core business logic for:
  - SID generation (HEM-01, HEM-02 on rejection, resets per new request/day)
  - CID generation (C-01, C-02 … global microbiology plate counter per day)
  - Rack number generation (1, 2, 3 … per department per shift)
  - Auto-routing ordered tests to department worklists
  - Specimen label data assembly

SID Rules (as per CLSI and user spec):
  1. Format: {ACRONYM}-{NN}  e.g. HEM-01
  2. Scoped to: patient_id + lab_request_id + specimen_acronym
  3. Increments for rejection replacements within the same request
  4. Each NEW request (new barcode) resets to 01 — even same-day
  5. New day always gives new barcode → SID resets to 01 automatically

CID Rules:
  1. Format: C-{NN}  e.g. C-01
  2. Global per microbiology per day (not patient-scoped)
  3. Assigned only to specimens with generates_cid=True

Rack Number Rules:
  1. Sequential integer: 1, 2, 3 …
  2. Scoped to department + date + shift
  3. Resets each shift (or daily if shift setting is 'daily')
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

log = logging.getLogger('worklist_service')

# ── Default specimen type catalogue (seeded on first use) ─────────────────────
# Format: (acronym, name, primary_department, tube_color, generates_cid, volume_ml)
# Tube colors follow CLSI/ISO standards:
#   lavender=EDTA, light-blue=Citrate, gold=SST, red=Plain, green=Heparin,
#   grey=Fluoride-oxalate, orange=Blood culture aerobic, dark-purple=Blood culture anaerobic,
#   royal-blue=Trace elements, yellow=Urine/SST, brown=Stool, clear=Sterile containers
SPECIMEN_CATALOGUE = [
    # ── Haematology ────────────────────────────────────────────────────────────
    ('HEM', 'EDTA Blood (K2/K3)',       'hematology',    'lavender',    False, 3.0),
    ('BNM', 'Bone Marrow Aspirate',     'hematology',    'lavender',    False, 2.0),
    ('ESR', 'EDTA (ESR Westergren)',    'hematology',    'royal-blue',  False, 1.6),
    # ── Coagulation ────────────────────────────────────────────────────────────
    ('CIT', 'Citrate Blood (3.2%)',     'coagulation',   'light-blue',  False, 2.7),
    # ── Biochemistry / Chemistry ───────────────────────────────────────────────
    ('SST', 'SST Serum (Gold/Tiger)',   'biochemistry',  'gold',        False, 5.0),
    ('SER', 'Plain Serum (Red top)',    'biochemistry',  'red',         False, 5.0),
    ('PLA', 'Lithium Heparin Plasma',  'biochemistry',  'green',       False, 3.0),
    ('PST', 'PST Plasma (Lt Green)',   'biochemistry',  'light-green', False, 3.0),
    ('FLU', 'Fluoride-Oxalate (Grey)', 'biochemistry',  'grey',        False, 2.0),
    ('GAS', 'Arterial Blood Gas',      'biochemistry',  'green',       False, 1.0),
    ('TRC', 'Trace Elements (Royal)',  'biochemistry',  'royal-blue',  False, 5.0),
    ('ACD', 'ACD Solution (Yellow)',   'hematology',    'yellow-acd',  False, 8.5),
    # ── Urinalysis ─────────────────────────────────────────────────────────────
    ('URI', 'Urine (Midstream)',        'urinalysis',    'yellow',      False, 10.0),
    ('URC', 'Urine (Culture)',          'microbiology',  'yellow',      True,  10.0),
    ('U24', '24-hour Urine',           'biochemistry',  'amber',       False, 50.0),
    ('TOX', 'Urine Toxicology',        'toxicology',    'yellow',      False, 30.0),
    # ── Microbiology specimens ─────────────────────────────────────────────────
    ('STL', 'Stool',                   'microbiology',  'brown',       True,  5.0),
    ('SPU', 'Sputum',                  'microbiology',  'white',       True,  3.0),
    ('SWB', 'Swab (Wound/Throat/Eye)', 'microbiology',  'white',       True,  None),
    ('PUS', 'Pus / Wound Discharge',   'microbiology',  'white',       True,  None),
    ('BLC', 'Blood Culture (Aerobic)', 'microbiology',  'orange',      True,  10.0),
    ('BLA', 'Blood Culture (Anaerob)', 'microbiology',  'dark-purple', True,  10.0),
    ('NAP', 'Nasopharyngeal Swab',     'microbiology',  'pink',        True,  None),
    ('SKN', 'Skin Scraping / Biopsy',  'microbiology',  'white',       True,  None),
    ('EAR', 'Ear Swab',               'microbiology',  'white',       True,  None),
    ('EYE', 'Conjunctival Swab',      'microbiology',  'white',       True,  None),
    ('CER', 'Cervical / HVS Swab',    'microbiology',  'pink',        True,  None),
    ('URE', 'Urethral Swab',          'microbiology',  'white',       True,  None),
    ('REC', 'Rectal Swab',            'microbiology',  'white',       True,  None),
    # ── Body fluids ────────────────────────────────────────────────────────────
    ('CSF', 'Cerebrospinal Fluid',     'biochemistry',  'clear',       True,  3.0),
    ('PLR', 'Pleural Fluid',           'biochemistry',  'clear',       True,  10.0),
    ('ASC', 'Ascitic / Peritoneal',    'biochemistry',  'clear',       True,  10.0),
    ('SYN', 'Synovial Fluid',          'biochemistry',  'clear',       True,  5.0),
    ('BAL', 'Bronchoalveolar Lavage',  'microbiology',  'clear',       True,  5.0),
    ('GAS', 'Gastric Aspirate',        'microbiology',  'clear',       True,  5.0),
    ('AMD', 'Amniotic Fluid',          'molecular',     'clear',       False, 5.0),
    ('PCD', 'Pericardial Fluid',       'biochemistry',  'clear',       True,  5.0),
    # ── Molecular / Genomics ───────────────────────────────────────────────────
    ('EXT', 'DNA/RNA Extract',         'molecular',     'clear',       False, 1.0),
    ('DBS', 'Dried Blood Spot (DBS)',  'molecular',     'white',       False, None),
    ('NPH', 'Nasopharyngeal (viral)',  'molecular',     'pink',        False, None),
    # ── Pathology / Histology ──────────────────────────────────────────────────
    ('BIO', 'Biopsy Tissue (Formalin)','pathology',    'formalin',    False, None),
    ('FNA', 'Fine Needle Aspirate',    'pathology',     'clear',       False, None),
    ('CYT', 'Cytology Specimen',       'pathology',     'clear',       False, None),
    ('PAP', 'Pap Smear',              'pathology',     'clear',       False, None),
    ('IMP', 'Imprint / Touch Prep',   'pathology',     'clear',       False, None),
    # ── Toxicology ─────────────────────────────────────────────────────────────
    ('TXB', 'Blood Toxicology',       'toxicology',    'grey',        False, 5.0),
    # ── Serology / Immunology ──────────────────────────────────────────────────
    ('SRL', 'Serum Serology (SST)',   'serology',      'gold',        False, 5.0),
    ('FNA', 'Fine Needle Aspirate',   'pathology',     'clear',    False, None),
    ('CYT', 'Cytology Specimen',      'pathology',     'clear',    False, None),
    # Toxicology
    ('TOX', 'Urine (Toxicology)',     'toxicology',    'yellow',   False, 30.0),
    ('TOX', 'Blood (Toxicology)',     'toxicology',    'red',      False, 5.0),
    # Serology / Immunology
    ('SER', 'Serum (Serology)',       'serology',      'red',      False, 5.0),
]

# Deduplicated by acronym (first occurrence wins for seeding)
_SPECIMEN_SEED: dict[str, tuple] = {}
for _row in SPECIMEN_CATALOGUE:
    if _row[0] not in _SPECIMEN_SEED:
        _SPECIMEN_SEED[_row[0]] = _row

# Department → list of specimen acronyms expected
DEPT_SPECIMENS: dict[str, list[str]] = {
    'hematology':   ['HEM', 'BNM'],
    'coagulation':  ['CIT'],
    'biochemistry': ['SER', 'PLA', 'FLU', 'CSF', 'PLR', 'ASC', 'SYN'],
    'urinalysis':   ['URI'],
    'microbiology': ['STL', 'SPU', 'SWB', 'PUS', 'BLC', 'NAP', 'SKN', 'BAL', 'URI', 'CSF', 'PLR'],
    'molecular':    ['SPU', 'SWB', 'EXT', 'DBS', 'NAP', 'BLC'],
    'serology':     ['SER'],
    'blood_bank':   ['HEM', 'SER'],
    'pathology':    ['BIO', 'FNA', 'CYT'],
    'toxicology':   ['TOX'],
}


# ── SID generation ────────────────────────────────────────────────────────────

def generate_sid(
    db: Session,
    patient_id: int,
    lab_request_id: int,
    acronym: str,
    today: Optional[date] = None,
) -> str:
    """
    Return the next SID for this patient+request+acronym combination.
    Thread-safe via SQLAlchemy row-level lock.

    e.g. first call → HEM-01
         rejection   → HEM-02
         next day or new request → HEM-01 (new row)
    """
    from models.worklist import DailySIDCounter
    today = today or date.today()
    acronym = acronym.upper()[:3]

    counter = (
        db.query(DailySIDCounter)
        .filter(
            DailySIDCounter.patient_id     == patient_id,
            DailySIDCounter.lab_request_id == lab_request_id,
            DailySIDCounter.acronym        == acronym,
            DailySIDCounter.counter_date   == today,
        )
        .with_for_update()
        .first()
    )

    if counter is None:
        counter = DailySIDCounter(
            patient_id=patient_id,
            lab_request_id=lab_request_id,
            acronym=acronym,
            counter_date=today,
            last_number=0,
        )
        db.add(counter)

    counter.last_number += 1
    db.flush()

    return f'{acronym}-{counter.last_number:02d}'


def generate_cid(db: Session, today: Optional[date] = None) -> str:
    """
    Return the next Culture ID for today (global microbiology counter).
    C-01, C-02, C-03 …
    """
    from models.worklist import DailyCIDCounter
    today = today or date.today()

    counter = (
        db.query(DailyCIDCounter)
        .filter(DailyCIDCounter.counter_date == today)
        .with_for_update()
        .first()
    )
    if counter is None:
        counter = DailyCIDCounter(counter_date=today, last_number=0)
        db.add(counter)

    counter.last_number += 1
    db.flush()

    return f'C-{counter.last_number:02d}'


def generate_rack_number(
    db: Session,
    department: str,
    shift_name: str = 'Morning',
    today: Optional[date] = None,
) -> int:
    """
    Return the next rack/analyzer position number for this department+shift.
    Resets to 1 on each new shift.
    """
    from models.worklist import DailyRackCounter
    today = today or date.today()
    department = department.lower()

    counter = (
        db.query(DailyRackCounter)
        .filter(
            DailyRackCounter.department   == department,
            DailyRackCounter.counter_date == today,
            DailyRackCounter.shift_name   == shift_name,
        )
        .with_for_update()
        .first()
    )
    if counter is None:
        counter = DailyRackCounter(
            department=department,
            counter_date=today,
            shift_name=shift_name,
            last_number=0,
        )
        db.add(counter)

    counter.last_number += 1
    db.flush()

    return counter.last_number


# ── Current shift helper ──────────────────────────────────────────────────────

def get_current_shift(db: Optional[Session] = None) -> str:
    """
    Return the current shift name based on wall-clock time.
    Tries to load shift config from DB; falls back to standard RW hospital shifts.
    """
    now_hhmm = datetime.now().strftime('%H:%M')
    defaults = [
        ('Morning',   '06:00', '14:00'),
        ('Afternoon', '14:00', '22:00'),
        ('Night',     '22:00', '06:00'),
    ]

    if db:
        try:
            from models.core_config import ShiftConfig
            configs = db.query(ShiftConfig).filter(ShiftConfig.is_active == True).all()
            if configs:
                defaults = [(c.name, c.start_time, c.end_time) for c in configs]
        except Exception:
            pass

    for name, start, end in defaults:
        if _in_time_range(now_hhmm, start, end):
            return name
    return defaults[0][0]


def _in_time_range(current: str, start: str, end: str) -> bool:
    if start <= end:
        return start <= current < end
    return current >= start or current < end


# ── Specimen type helpers ─────────────────────────────────────────────────────

def get_specimen_config(db: Session, acronym: str):
    """Return SpecimenTypeConfig for acronym, seeding if not exists."""
    from models.worklist import SpecimenTypeConfig
    cfg = db.query(SpecimenTypeConfig).filter(
        SpecimenTypeConfig.acronym == acronym.upper(),
        SpecimenTypeConfig.is_active == True,
    ).first()
    return cfg


def seed_specimen_types(db: Session) -> int:
    """Insert default specimen types if the table is empty. Returns count seeded."""
    from models.worklist import SpecimenTypeConfig
    if db.query(SpecimenTypeConfig).count() > 0:
        return 0

    seeded = 0
    for i, (acronym, name, dept, color, cid, vol) in enumerate(_SPECIMEN_SEED.values()):
        db.add(SpecimenTypeConfig(
            acronym=acronym, name=name, primary_department=dept,
            tube_color=color, generates_cid=cid,
            volume_ml=vol, is_active=True, sort_order=i,
        ))
        seeded += 1
    db.commit()
    log.info('Seeded %d specimen types', seeded)
    return seeded


# ── Auto-routing engine ───────────────────────────────────────────────────────

def route_request_to_worklist(
    db: Session,
    lab_request_id: int,
    received_by_id: int,
    shift_name: Optional[str] = None,
) -> list:
    """
    Core engine: take a received LabRequest and create WorklistEntry rows
    for every department that has tests in this request.

    Groups tests by (department, specimen_acronym) so that multiple tests
    sharing the same tube get ONE entry (and one SID / one label).

    Returns list of created WorklistEntry objects.
    """
    from models.laboratory import LabRequest
    from models.worklist import WorklistEntry, SpecimenTypeConfig

    req = db.query(LabRequest).filter(LabRequest.id == lab_request_id).first()
    if not req:
        raise ValueError(f'LabRequest {lab_request_id} not found')

    today      = date.today()
    shift_name = shift_name or get_current_shift(db)
    barcode    = req.lab_id

    # Gather ordered tests
    ordered_tests = _get_ordered_tests(db, lab_request_id)
    if not ordered_tests:
        log.warning('No ordered tests found for lab_request %d', lab_request_id)
        return []

    # Group by (department, specimen_acronym)
    groups: dict[tuple[str, str], list[dict]] = {}
    for test in ordered_tests:
        dept    = (test.get('department') or 'general').lower()
        acronym = (test.get('specimen_acronym') or _dept_default_acronym(dept)).upper()[:3]
        key = (dept, acronym)
        groups.setdefault(key, []).append(test)

    entries = []
    for (dept, acronym), tests in groups.items():
        # Check specimen config
        spec_cfg = get_specimen_config(db, acronym)
        generates_cid = spec_cfg.generates_cid if spec_cfg else False
        tube_color    = spec_cfg.tube_color    if spec_cfg else None
        spec_name     = spec_cfg.name          if spec_cfg else acronym
        volume_ml     = spec_cfg.volume_ml     if spec_cfg else None

        # SID
        sid = generate_sid(db, req.patient_id, lab_request_id, acronym, today)

        # Rack number
        rack_no = generate_rack_number(db, dept, shift_name, today)

        # CID for culture specimens
        cid = generate_cid(db, today) if generates_cid else None

        # Test names / IDs for display
        test_names = ', '.join(t['name'] for t in tests)
        test_ids   = ','.join(str(t['id']) for t in tests)

        entry = WorklistEntry(
            lab_request_id   = lab_request_id,
            patient_id       = req.patient_id,
            department       = dept,
            specimen_acronym = acronym,
            specimen_name    = spec_name,
            sid              = sid,
            rack_number      = rack_no,
            cid              = cid,
            barcode          = barcode,
            priority         = req.emergency_level or 'routine',
            status           = 'RECEIVED',
            test_names       = test_names,
            test_ids         = test_ids,
            tube_color       = tube_color,
            volume_ml        = volume_ml,
            is_high_risk     = req.is_high_risk or False,
            worklist_date    = today,
            shift_name       = shift_name,
            received_at      = datetime.now(timezone.utc),
        )
        db.add(entry)
        entries.append(entry)

    # Update request status
    req.status      = 'received'
    req.received_at = datetime.now(timezone.utc)
    req.received_by_id = received_by_id

    db.flush()
    log.info(
        'Routed lab_request %d → %d worklist entries (patient=%d)',
        lab_request_id, len(entries), req.patient_id,
    )
    return entries


def _get_ordered_tests(db: Session, lab_request_id: int) -> list[dict]:
    """
    Return list of ordered tests for a LabRequest.
    Tries TestCatalog join; falls back gracefully if not fully configured.
    """
    try:
        from sqlalchemy import text
        rows = db.execute(text("""
            SELECT tc.id, tc.name, tc.department, tc.specimen_acronym
            FROM ordered_tests ot
            JOIN test_catalog tc ON tc.id = ot.test_id
            WHERE ot.lab_request_id = :rid
        """), {'rid': lab_request_id}).fetchall()

        if rows:
            return [{'id': r[0], 'name': r[1],
                     'department': r[2], 'specimen_acronym': r[3]}
                    for r in rows]
    except Exception:
        pass

    # Fallback: read from LabResult stubs if tests were pre-created
    try:
        from models.laboratory import LabResult
        results = (db.query(LabResult)
                   .filter(LabResult.lab_request_id == lab_request_id)
                   .all())
        seen = set()
        tests = []
        for r in results:
            if r.test_id and r.test_id not in seen:
                seen.add(r.test_id)
                test_obj = getattr(r, 'test', None)
                tests.append({
                    'id':               r.test_id,
                    'name':             test_obj.name if test_obj else f'Test-{r.test_id}',
                    'department':       test_obj.department if test_obj else 'general',
                    'specimen_acronym': getattr(test_obj, 'specimen_acronym', 'SER'),
                })
        return tests
    except Exception as e:
        log.warning('Could not fetch ordered tests: %s', e)
        return []


def _dept_default_acronym(department: str) -> str:
    """Fallback specimen acronym when test catalogue doesn't specify one."""
    defaults = {
        'hematology':   'HEM',
        'coagulation':  'CIT',
        'biochemistry': 'SER',
        'urinalysis':   'URI',
        'microbiology': 'SWB',
        'molecular':    'SPU',
        'serology':     'SER',
        'blood_bank':   'HEM',
        'pathology':    'BIO',
        'toxicology':   'TOX',
    }
    return defaults.get(department.lower(), 'SER')


# ── Rejection replacement ─────────────────────────────────────────────────────

def create_rejection_replacement(
    db: Session,
    original_entry_id: int,
    rejection_reason: str,
    received_by_id: int,
) -> 'WorklistEntry':
    """
    Mark an existing WorklistEntry as REJECTED and create a new replacement
    entry with an incremented SID (e.g. HEM-01 → HEM-02).
    The new entry shares the same lab_request (barcode) so billing sees
    that the replacement was due to lab error.
    """
    from models.worklist import WorklistEntry

    orig = db.query(WorklistEntry).filter(WorklistEntry.id == original_entry_id).first()
    if not orig:
        raise ValueError(f'WorklistEntry {original_entry_id} not found')

    # Mark original rejected
    orig.status           = 'REJECTED'
    orig.rejection_reason = rejection_reason

    today  = date.today()
    shift  = get_current_shift(db)

    # New SID (increments)
    new_sid = generate_sid(db, orig.patient_id, orig.lab_request_id,
                           orig.specimen_acronym, today)
    new_rack = generate_rack_number(db, orig.department, shift, today)
    new_cid  = generate_cid(db, today) if orig.cid else None

    replacement = WorklistEntry(
        lab_request_id           = orig.lab_request_id,
        patient_id               = orig.patient_id,
        department               = orig.department,
        specimen_acronym         = orig.specimen_acronym,
        specimen_name            = orig.specimen_name,
        sid                      = new_sid,
        rack_number              = new_rack,
        cid                      = new_cid,
        barcode                  = orig.barcode,
        priority                 = orig.priority,
        status                   = 'RECEIVED',
        is_rejection_replacement = True,
        original_entry_id        = orig.id,
        rejection_reason         = rejection_reason,
        test_names               = orig.test_names,
        test_ids                 = orig.test_ids,
        tube_color               = orig.tube_color,
        volume_ml                = orig.volume_ml,
        is_high_risk             = orig.is_high_risk,
        worklist_date            = today,
        shift_name               = shift,
        received_at              = datetime.now(timezone.utc),
    )
    db.add(replacement)
    db.flush()

    log.info('Rejection replacement: %s → %s (reason: %s)',
             orig.sid, new_sid, rejection_reason)
    return replacement


# ── Label data assembly ───────────────────────────────────────────────────────

def build_label_data(db: Session, worklist_entry_id: int) -> dict:
    """
    Assemble all data needed to render a specimen label.
    Returns a dict consumed by the PDF label generator or frontend print template.
    """
    from models.worklist import WorklistEntry

    entry = db.query(WorklistEntry).filter(
        WorklistEntry.id == worklist_entry_id).first()
    if not entry:
        raise ValueError(f'WorklistEntry {worklist_entry_id} not found')

    # Patient data
    patient = entry.patient
    patient_name = '—'
    if patient:
        if hasattr(patient, 'full_name') and patient.full_name:
            patient_name = patient.full_name
        else:
            patient_name = f'{getattr(patient, "family_name", "")} {getattr(patient, "other_names", "") or ""}'.strip()

    pid  = patient.pid  if patient else '—'
    dob  = str(patient.date_of_birth) if patient and patient.date_of_birth else '—'
    sex  = patient.gender or '—' if patient else '—'

    # Lab request
    req  = entry.lab_request
    ward = req.ward or '—' if req else '—'
    doctor = req.doctor_name or '—' if req else '—'

    return {
        # Patient
        'patient_name': patient_name,
        'pid':          pid,
        'dob':          dob,
        'sex':          sex,
        # Identifiers
        'sid':          entry.sid,
        'cid':          entry.cid,
        'rack_number':  entry.rack_number,
        'barcode':      entry.barcode,
        # Tests
        'test_names':   entry.test_names or '—',
        'department':   entry.department.title(),
        'specimen':     entry.specimen_name or entry.specimen_acronym,
        'volume_ml':    entry.volume_ml,
        'tube_color':   entry.tube_color or 'white',
        # Context
        'priority':     entry.priority.upper(),
        'is_high_risk': entry.is_high_risk,
        'ward':         ward,
        'doctor':       doctor,
        'date':         entry.worklist_date.strftime('%d/%m/%Y'),
        'shift':        entry.shift_name,
        # For plate label (microbiology)
        'plate_id':     entry.cid,
        'label_type':   'PLATE' if entry.cid else 'TUBE',
    }


def record_label_printed(
    db: Session,
    worklist_entry_id: int,
    label_type: str,
    printed_by_id: Optional[int],
) -> 'SpecimenLabel':
    """Create an audit record for a printed label."""
    from models.worklist import WorklistEntry, SpecimenLabel

    entry = db.query(WorklistEntry).filter(
        WorklistEntry.id == worklist_entry_id).first()
    if not entry:
        raise ValueError(f'WorklistEntry {worklist_entry_id} not found')

    audit = SpecimenLabel(
        worklist_entry_id = worklist_entry_id,
        label_type        = label_type.upper(),
        barcode_value     = entry.barcode,
        sid               = entry.sid,
        cid               = entry.cid,
        printed_by_id     = printed_by_id,
    )
    db.add(audit)

    entry.label_printed     = True
    entry.label_print_count += 1
    db.flush()

    return audit
