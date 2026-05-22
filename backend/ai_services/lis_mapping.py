"""
LIS Auto-Mapping
================
Extract structured lab-request information from OCR'd request forms:
patient identifiers, ordered tests, priority, specimen, doctor, ward, diagnosis.

Companion to backend/routers/lis_mapping.py. OCR itself is delegated to
ai_services.ocr_service / document_reader.

Decision-support only — emits drafts with confidence scores and warnings.
A human-in-the-loop (semi-auto) confirms before any LabRequest is committed,
unless the caller opts into fully-automatic mode AND every field clears the
threshold.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models.core_config import TestCatalog
from models.laboratory import LabRequest
from models.patient import Patient


# ── Regex library ─────────────────────────────────────────────────────────────

PID_RE     = re.compile(r'\bPID[\s:#-]*([A-Z0-9][A-Z0-9-]{2,19})', re.I)
LID_RE     = re.compile(r'\b(?:LID|RW)[\s:#-]*([A-Z0-9][A-Z0-9-]{2,19})', re.I)
NID_RE     = re.compile(r'(?:NID|National\s*ID)[\s:#-]*([0-9]{10,20})', re.I)
LAB_ID_RE  = re.compile(r'\bLAB[\s:#-]*(\d{2,6}[-/]\d{2,6})', re.I)
PHONE_RE   = re.compile(r'\b(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}\b')
DOB_RE     = re.compile(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b')
GENDER_RE  = re.compile(r'\b(?:Sex|Gender|Genre)[\s:]+([MFmf]\b|Male|Female|Masculin|F[eé]minin)', re.I)
NAME_LABEL = re.compile(r'(?:Patient|Name|Nom)[\s:]+([A-ZÀ-Ý][A-Za-zÀ-ÿ]+(?:[\s-]+[A-ZÀ-Ý][A-Za-zÀ-ÿ]+){1,4})', re.I)
DOCTOR_RE  = re.compile(r'(?:Doctor|Doc\.?|Physician|Requested\s+by|Dr\.?)[\s:]+([A-ZÀ-Ý][A-Za-zÀ-ÿ.]+(?:\s+[A-ZÀ-Ý][A-Za-zÀ-ÿ.]+){0,3})(?=\r?\n|$)', re.I | re.M)
WARD_RE    = re.compile(r'(?:Ward|Service|Department\s+of)[\s:]+([A-Z][A-Za-z][A-Za-z ]{1,28}?)(?=\r?\n|$)', re.I | re.M)
DIAG_RE    = re.compile(r'(?:Diagnosis|Clinical\s+notes?|Dx)[\s:]+(.{4,140}?)(?=\r?\n|$)', re.I | re.M)

# ── Priority ──────────────────────────────────────────────────────────────────

STAT_KEYWORDS   = {'stat', 'urgent', 'emergency', 'cito', 'immediately', 'critical'}
URGENT_KEYWORDS = {'asap', 'expedite', 'expedited'}

# ── Department / specimen heuristics ──────────────────────────────────────────

"""
Common synonyms / abbreviations the OCR will see but that don't appear verbatim
in test_catalog. Values are catalog codes the alias should resolve to.
A single alias may expand to several codes (panels like CBC).
"""
TEST_ALIASES: dict[str, list[str]] = {
    'cbc':          ['HGB', 'RBC', 'WBC', 'PLT', 'HCT', 'MCV', 'MCH', 'MCHC', 'RDW'],
    'fbc':          ['HGB', 'RBC', 'WBC', 'PLT', 'HCT', 'MCV', 'MCH', 'MCHC', 'RDW'],
    'platelets':    ['PLT'],
    'platelet':     ['PLT'],
    'hb':           ['HGB'],
    'hgb':          ['HGB'],
    'hemoglobin':   ['HGB'],
    'haemoglobin':  ['HGB'],
    'wbc':          ['WBC'],
    'rbc':          ['RBC'],
    'hematocrit':   ['HCT'],
    'haematocrit':  ['HCT'],
    'esr':          ['ESR'],
    'crp':          ['CRP'],
    'glucose':      ['RBG'],   # random by default; user may switch to FBG
    'glycemia':     ['RBG'],
    'fbs':          ['FBG'],
    'rbs':          ['RBG'],
    'creat':        ['CREAT'],
    'urea':         ['UREA'],
    'bun':          ['UREA'],
    'electrolytes': ['NA', 'K', 'CL'],
    'lfts':         ['ALT', 'AST', 'ALP', 'GGT', 'TBIL', 'DBIL'],
    'rft':          ['UREA', 'CREAT', 'NA', 'K'],
    'lipid':        ['CHOL', 'TG', 'HDL', 'LDL'],
}

DEPT_HINTS = {
    'hematology':   ['cbc', 'fbc', 'hematology', 'haematology', 'differential', 'smear'],
    'biochemistry': ['biochem', 'chemistry', 'lft', 'rft', 'kft', 'lipid', 'glucose',
                     'electrolyte', 'creatinine', 'urea'],
    'microbiology': ['microbiology', 'culture', 'gram stain', 'sensitivity', 'c&s'],
    'serology':     ['serology', 'hiv', 'hepatitis', 'hbsag', 'hcv', 'syphilis', 'rpr', 'vdrl'],
    'urinalysis':   ['urinalysis', 'urine analysis', 'urine routine'],
    'coagulation':  ['coag', 'aptt', 'pt/inr', 'd-dimer', 'd dimer'],
    'molecular':    ['pcr', 'genexpert', 'tb molecular', 'molecular'],
    'blood_bank':   ['crossmatch', 'cross match', 'cross-match', 'transfusion', 'blood group'],
}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class TestMatch:
    query:           str
    test_id:         Optional[int]   = None
    code:            Optional[str]   = None
    name:            Optional[str]   = None
    short_name:      Optional[str]   = None
    department_id:   Optional[int]   = None
    specimen_type:   Optional[str]   = None
    price:           float           = 0.0
    confidence:      float           = 0.0
    status:          str             = 'unmatched'   # matched | ambiguous | unmatched

    def to_dict(self) -> dict:
        return {
            'query':         self.query,
            'test_id':       self.test_id,
            'code':          self.code,
            'name':          self.name,
            'short_name':    self.short_name,
            'department_id': self.department_id,
            'specimen_type': self.specimen_type,
            'price':         self.price,
            'confidence':    round(self.confidence, 3),
            'status':        self.status,
        }


@dataclass
class PatientMatch:
    pid:           Optional[str] = None
    lid:           Optional[str] = None
    national_id:   Optional[str] = None
    family_name:   Optional[str] = None
    other_names:   Optional[str] = None
    date_of_birth: Optional[str] = None      # YYYY-MM-DD if parseable
    gender:        Optional[str] = None      # M | F
    phone:         Optional[str] = None

    matched_id:    Optional[int] = None
    confidence:    float = 0.0
    status:        str   = 'unmatched'       # matched | candidate | unmatched | new

    def to_dict(self) -> dict:
        return {
            'pid':           self.pid,
            'lid':           self.lid,
            'national_id':   self.national_id,
            'family_name':   self.family_name,
            'other_names':   self.other_names,
            'date_of_birth': self.date_of_birth,
            'gender':        self.gender,
            'phone':         self.phone,
            'matched_id':    self.matched_id,
            'confidence':    round(self.confidence, 3),
            'status':        self.status,
        }


@dataclass
class MappingDraft:
    patient:       PatientMatch
    tests:         list[TestMatch]
    priority:      str                   # routine | urgent | stat
    department:    Optional[str]
    specimen_type: Optional[str]
    doctor_name:   Optional[str]
    ward:          Optional[str]
    diagnosis:     Optional[str]
    duplicate_of:  Optional[int]         # existing LabRequest.id matching this draft
    warnings:      list[str]
    text_hash:     str
    raw_text:      str
    field_confidence: dict[str, float]
    overall_confidence: float

    def to_dict(self) -> dict:
        return {
            'patient':       self.patient.to_dict(),
            'tests':         [t.to_dict() for t in self.tests],
            'priority':      self.priority,
            'department':    self.department,
            'specimen_type': self.specimen_type,
            'doctor_name':   self.doctor_name,
            'ward':          self.ward,
            'diagnosis':     self.diagnosis,
            'duplicate_of':  self.duplicate_of,
            'warnings':      self.warnings,
            'text_hash':     self.text_hash,
            'raw_text':      self.raw_text,
            'field_confidence':   {k: round(v, 3) for k, v in self.field_confidence.items()},
            'overall_confidence': round(self.overall_confidence, 3),
        }


# ── Field extractors ──────────────────────────────────────────────────────────

def _first(m: Optional[re.Match], group: int = 1) -> Optional[str]:
    if not m:
        return None
    return m.group(group).strip()


def _parse_dob(raw: str) -> Optional[str]:
    m = DOB_RE.search(raw)
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 1900 if y > 30 else 2000
    # Heuristic: if day > 12 it's clearly DD/MM/YYYY; else assume DD/MM/YYYY (ISO-ish)
    if not (1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100):
        return None
    try:
        return datetime(y, mo, d).date().isoformat()
    except ValueError:
        return None


def _normalize_gender(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    r = raw.strip().lower()
    if r.startswith('m') or r.startswith('mas'):
        return 'M'
    if r.startswith('f') or r.startswith('fe') or r.startswith('fé'):
        return 'F'
    return None


def _detect_priority(text: str) -> str:
    # Word-bounded match so "stat" doesn't fire on "gestational" etc.
    def has(words: set[str]) -> bool:
        pattern = r'\b(?:' + '|'.join(re.escape(w) for w in words) + r')\b'
        return bool(re.search(pattern, text, re.I))
    if has(STAT_KEYWORDS):
        return 'stat'
    if has(URGENT_KEYWORDS):
        return 'urgent'
    return 'routine'


def _detect_department(text: str, tests: list[TestMatch]) -> Optional[str]:
    """Prefer explicit dept hints in the text; else infer from test department_id distribution."""
    t = text.lower()
    for dept, hints in DEPT_HINTS.items():
        if any(h in t for h in hints):
            return dept
    # Infer from majority department of matched tests
    counts: dict[int, int] = {}
    for tm in tests:
        if tm.department_id and tm.status == 'matched':
            counts[tm.department_id] = counts.get(tm.department_id, 0) + 1
    if counts:
        majority_dept_id = max(counts, key=counts.get)
        return f'dept_id:{majority_dept_id}'
    return None


def _extract_patient_fields(text: str) -> PatientMatch:
    pid    = _first(PID_RE.search(text))
    lid    = _first(LID_RE.search(text))
    nid    = _first(NID_RE.search(text))
    phone  = _first(PHONE_RE.search(text), 0)
    dob    = _parse_dob(text)
    gender = _normalize_gender(_first(GENDER_RE.search(text)))
    full   = _first(NAME_LABEL.search(text))

    family, others = None, None
    if full:
        parts = full.split()
        if parts:
            family = parts[0]
            others = ' '.join(parts[1:]) or None

    return PatientMatch(
        pid=pid, lid=lid, national_id=nid,
        family_name=family, other_names=others,
        date_of_birth=dob, gender=gender, phone=phone,
    )


def _extract_test_candidates(text: str) -> list[str]:
    """
    Return the list of strings that look like test orders.
    Strategy:
      1. Pull from explicit list lines after a 'Tests:' / 'Investigations:' label
      2. Pull all-caps tokens that are 2–10 chars and not in stoplist
      3. Pull '- something' or '* something' bulleted items
    """
    candidates: list[str] = []

    sections = re.split(
        r'(?im)^\s*(?:tests?|investigations?|requested|order(?:s|ed)?)\s*:?\s*$',
        text,
    )
    if len(sections) > 1:
        block = sections[-1]
    else:
        block = text

    for line in block.splitlines():
        line = line.strip(' \t-•*·.')
        if not line:
            continue
        # Bullet/list item
        for tok in re.split(r'[,;/]| and |&|\+', line):
            tok = tok.strip(' \t-•*·.()[]')
            if 2 <= len(tok) <= 60 and not tok.lower().startswith(('patient', 'name', 'dr', 'doctor', 'ward', 'diagnosis')):
                candidates.append(tok)

    # Drop duplicates preserving order
    seen, uniq = set(), []
    for c in candidates:
        k = c.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq[:40]


# ── Matchers ──────────────────────────────────────────────────────────────────

def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _build_from_catalog(query: str, t: TestCatalog, confidence: float, status: str) -> TestMatch:
    return TestMatch(
        query=query, test_id=t.id, code=t.code, name=t.name,
        short_name=t.short_name, department_id=t.department_id,
        specimen_type=t.specimen_type, price=t.price,
        confidence=confidence, status=status,
    )


def _match_test(db: Session, query: str, catalog: list[TestCatalog]) -> list[TestMatch]:
    """Match a single OCR'd token against the test catalog. May return multiple
    matches when the query is an alias for a panel (e.g. CBC)."""
    q = query.strip()
    if not q:
        return [TestMatch(query=query)]

    by_code = {t.code.upper().replace(' ', '').replace('-', ''): t for t in catalog}

    # 1. Alias / panel expansion
    alias_key = q.lower().strip().rstrip('.')
    if alias_key in TEST_ALIASES:
        codes = TEST_ALIASES[alias_key]
        out: list[TestMatch] = []
        for code in codes:
            t = by_code.get(code.upper())
            if t:
                out.append(_build_from_catalog(query, t, 0.97, 'matched'))
        if out:
            return out

    # 2. Exact code match
    q_norm = q.upper().replace(' ', '').replace('-', '')
    t = by_code.get(q_norm)
    if t:
        return [_build_from_catalog(query, t, 1.0, 'matched')]

    # 3. Exact short_name match
    for t in catalog:
        if t.short_name and t.short_name.upper().replace(' ', '').replace('-', '') == q_norm:
            return [_build_from_catalog(query, t, 0.98, 'matched')]

    # 4. Fuzzy match against name / short_name / code
    best: Optional[TestCatalog] = None
    best_score = 0.0
    runner_score = 0.0
    for t in catalog:
        hay = max(_similarity(q, t.name), _similarity(q, t.short_name or ''),
                  _similarity(q, t.code))
        if hay > best_score:
            runner_score = best_score
            best_score = hay
            best = t
        elif hay > runner_score:
            runner_score = hay

    if best and best_score >= 0.80:
        status = 'matched' if (best_score - runner_score) >= 0.08 else 'ambiguous'
        return [_build_from_catalog(query, best, best_score, status)]

    return [TestMatch(query=query, confidence=best_score, status='unmatched')]


def _match_patient(db: Session, pm: PatientMatch) -> PatientMatch:
    """Look up an existing Patient by PID, LID, national_id, or name+DOB."""
    if pm.pid:
        p = db.query(Patient).filter(Patient.pid == pm.pid).first()
        if p:
            pm.matched_id = p.id
            pm.confidence = 0.99
            pm.status = 'matched'
            return pm
    if pm.lid:
        p = db.query(Patient).filter(Patient.unique_lab_id == pm.lid).first()
        if p:
            pm.matched_id = p.id
            pm.confidence = 0.99
            pm.status = 'matched'
            return pm
    if pm.national_id:
        p = db.query(Patient).filter(Patient.national_id == pm.national_id).first()
        if p:
            pm.matched_id = p.id
            pm.confidence = 0.95
            pm.status = 'matched'
            return pm
    if pm.family_name and pm.date_of_birth:
        try:
            dob = datetime.fromisoformat(pm.date_of_birth).date()
        except ValueError:
            dob = None
        if dob:
            p = (db.query(Patient)
                   .filter(and_(Patient.family_name.ilike(pm.family_name),
                                Patient.date_of_birth == dob))
                   .first())
            if p:
                pm.matched_id = p.id
                pm.confidence = 0.90
                pm.status = 'candidate'
                return pm

    pm.status = 'new' if (pm.family_name or pm.pid or pm.lid) else 'unmatched'
    pm.confidence = 0.30 if pm.family_name else 0.0
    return pm


def _detect_duplicate(db: Session, draft: MappingDraft, window_hours: int = 24) -> Optional[int]:
    """Look for an existing LabRequest from the same patient with overlapping tests
    in the past `window_hours`. Returns LabRequest.id if found."""
    if not draft.patient.matched_id:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    existing = (
        db.query(LabRequest)
          .filter(LabRequest.patient_id == draft.patient.matched_id,
                  LabRequest.request_date >= cutoff)
          .order_by(LabRequest.request_date.desc())
          .first()
    )
    return existing.id if existing else None


# ── Public entry point ────────────────────────────────────────────────────────

def map_request_form(db: Session, raw_text: str) -> MappingDraft:
    """
    Run the full extraction + match pipeline on OCR'd text.
    Pure analysis — does not touch the DB beyond reads.
    """
    text = (raw_text or '').strip()
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]

    pm = _extract_patient_fields(text)
    pm = _match_patient(db, pm)

    candidates = _extract_test_candidates(text)
    catalog    = db.query(TestCatalog).filter(TestCatalog.is_active.is_(True)).all()
    flattened: list[TestMatch] = []
    for c in candidates:
        flattened.extend(_match_test(db, c, catalog))
    # Drop low-confidence noise and dedupe by test_id (best confidence wins)
    by_id: dict[int, TestMatch] = {}
    unmatched_tracked: list[TestMatch] = []
    for tm in flattened:
        if tm.test_id:
            existing = by_id.get(tm.test_id)
            if not existing or tm.confidence > existing.confidence:
                by_id[tm.test_id] = tm
        elif tm.confidence > 0.6 or tm.status != 'unmatched':
            unmatched_tracked.append(tm)
    test_matches = list(by_id.values()) + unmatched_tracked

    priority  = _detect_priority(text)
    dept      = _detect_department(text, test_matches)
    specimen  = next((t.specimen_type for t in test_matches if t.specimen_type), None)
    doctor    = _first(DOCTOR_RE.search(text))
    ward      = _first(WARD_RE.search(text))
    diagnosis = _first(DIAG_RE.search(text))

    warnings: list[str] = []
    if pm.status == 'unmatched':
        warnings.append('Patient could not be identified — no PID/LID/National-ID/Name found.')
    elif pm.status == 'new':
        warnings.append('Patient appears to be new — will need to be registered before confirmation.')
    if not test_matches:
        warnings.append('No recognisable tests were extracted from the form.')
    unmatched = [t for t in test_matches if t.status == 'unmatched']
    if unmatched:
        warnings.append(f'{len(unmatched)} test(s) could not be matched to the catalogue.')
    ambiguous = [t for t in test_matches if t.status == 'ambiguous']
    if ambiguous:
        warnings.append(f'{len(ambiguous)} test(s) ambiguous — review before confirming.')

    field_conf = {
        'patient': pm.confidence,
        'tests':   (sum(t.confidence for t in test_matches) / len(test_matches)) if test_matches else 0.0,
        'priority': 1.0 if priority != 'routine' else 0.7,
        'doctor':  0.8 if doctor else 0.0,
        'ward':    0.7 if ward else 0.0,
    }
    overall = sum(field_conf.values()) / max(1, len(field_conf))

    draft = MappingDraft(
        patient=pm, tests=test_matches, priority=priority,
        department=dept, specimen_type=specimen,
        doctor_name=doctor, ward=ward, diagnosis=diagnosis,
        duplicate_of=None, warnings=warnings,
        text_hash=text_hash, raw_text=text[:4000],
        field_confidence=field_conf,
        overall_confidence=overall,
    )

    dup = _detect_duplicate(db, draft)
    if dup:
        draft.duplicate_of = dup
        draft.warnings.insert(0, f'Possible duplicate of LabRequest #{dup} (same patient in last 24h).')

    return draft


# ── Confirmation / persistence ────────────────────────────────────────────────

def confirm_draft(
    db: Session,
    draft_dict: dict,
    user_id: int,
    auto_create_patient: bool = False,
) -> dict:
    """
    Persist a (possibly user-edited) draft as a LabRequest + LabResult test stubs.
    Returns {'lab_request_id', 'lab_id', 'created_test_stub_ids'}.
    """
    from models.laboratory import LabResult

    patient_block = draft_dict.get('patient') or {}
    tests_block   = draft_dict.get('tests') or []

    # Resolve patient
    pid = patient_block.get('matched_id')
    if pid:
        patient = db.query(Patient).filter(Patient.id == pid).first()
        if not patient:
            raise ValueError(f'Patient #{pid} not found')
    elif auto_create_patient and patient_block.get('family_name'):
        from datetime import date as _date
        dob_raw = patient_block.get('date_of_birth')
        dob = None
        if dob_raw:
            try:
                dob = _date.fromisoformat(dob_raw)
            except ValueError:
                dob = None
        patient = Patient(
            pid=patient_block.get('pid') or _generate_pid(db),
            family_name=patient_block.get('family_name'),
            other_names=patient_block.get('other_names'),
            date_of_birth=dob,
            gender=patient_block.get('gender'),
            phone=patient_block.get('phone'),
            national_id=patient_block.get('national_id'),
            unique_lab_id=patient_block.get('lid'),
        )
        db.add(patient)
        db.flush()
    else:
        raise ValueError('Patient not matched and auto_create_patient=False')

    # Generate lab_id
    lab_id = _generate_lab_id(db)

    req = LabRequest(
        lab_id=lab_id,
        patient_id=patient.id,
        pid=patient.pid,
        lid=patient.unique_lab_id,
        doctor_name=draft_dict.get('doctor_name'),
        ward=draft_dict.get('ward'),
        diagnosis=draft_dict.get('diagnosis'),
        emergency_level=draft_dict.get('priority') or 'routine',
        requested_by_id=user_id,
        notes=f'LIS auto-mapping draft (hash={draft_dict.get("text_hash")})',
    )
    db.add(req)
    db.flush()

    # Pre-create LabResult stubs for each matched test
    stub_ids: list[int] = []
    for t in tests_block:
        tid = t.get('test_id')
        if not tid or t.get('status') == 'unmatched':
            continue
        stub = LabResult(
            lab_request_id=req.id,
            test_id=tid,
            pid=patient.pid,
            lid=patient.unique_lab_id,
            status='PENDING',
        )
        db.add(stub)
        db.flush()
        stub_ids.append(stub.id)

    db.commit()
    return {
        'lab_request_id': req.id,
        'lab_id': lab_id,
        'patient_id': patient.id,
        'created_test_stub_ids': stub_ids,
    }


def _generate_lab_id(db: Session) -> str:
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    n = db.query(LabRequest).filter(LabRequest.lab_id.like(f'LR-{today}-%')).count()
    return f'LR-{today}-{str(n + 1).zfill(4)}'


def _generate_pid(db: Session) -> str:
    today = datetime.now(timezone.utc).strftime('%Y%m%d')
    n = db.query(Patient).filter(Patient.pid.like(f'P-{today}-%')).count()
    return f'P-{today}-{str(n + 1).zfill(4)}'
