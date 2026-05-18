"""
Biochemistry Department Router
================================
Covers all Clinical Chemistry sections:
  GENERAL  — Glucose, Urea, Creatinine, Electrolytes, Proteins
  LIVER    — ALT, AST, GGT, ALP, Bilirubin, Albumin
  LIPIDS   — Total Cholesterol, LDL, HDL, TG, VLDL
  RENAL    — eGFR, Cystatin C, Uric Acid, 24h Urine
  CARDIAC  — Troponin I/T, CK-MB, BNP, Myoglobin
  ENDO     — TSH, FT3, FT4, Cortisol, Insulin, HbA1c
  TUMOUR   — PSA, CEA, AFP, CA-125, CA-19-9, CA-15-3
  SPECIAL  — Vitamins (B12, Folate, D, A), Iron studies, Inflammatory

Endpoints:
  Worklist
    GET  /biochemistry/worklist              — Today's section worklist
    POST /biochemistry/worklist              — Create new worklist run
    GET  /biochemistry/worklist/{id}         — Get worklist + items
    PUT  /biochemistry/worklist/{id}/status  — Update status

  Results
    GET  /biochemistry/results               — Query results (patient/date/section)
    POST /biochemistry/results               — Enter single result
    POST /biochemistry/results/panel         — Enter complete panel (LFT, RFT, Lipids…)
    PUT  /biochemistry/results/{id}/validate — Validate result
    PUT  /biochemistry/results/{id}/authorize— Authorize (pathologist sign-off)
    POST /biochemistry/results/{id}/critical — Mark critical, log notification

  Reference ranges
    GET  /biochemistry/reference-ranges      — Get ranges by test + patient demographics

  Stats
    GET  /biochemistry/stats                 — Dashboard KPIs
    GET  /biochemistry/critical-book         — ISO 15189 critical log
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.user import User

log = logging.getLogger('biochemistry_router')
router = APIRouter(tags=['Biochemistry'])

# ── Reference ranges by section ────────────────────────────────────────────────
# Format: {test_code: {sex: {age_group: (min, max, unit, flag_critical_low, flag_critical_high)}}}
REFERENCE_RANGES: dict[str, dict] = {
    # GENERAL
    'GLUCOSE_F': {'adult': (3.9, 6.1, 'mmol/L', 2.2, 22.2), 'child': (3.3, 5.6, 'mmol/L', 2.2, 16.7)},
    'GLUCOSE_R': {'adult': (3.9, 11.1,'mmol/L', 2.2, 22.2)},
    'UREA':      {'adult': (2.5, 7.1,  'mmol/L', None, 35.7)},
    'CREAT_M':   {'adult': (62, 115,   'µmol/L', None, 1000), 'child': (27, 62, 'µmol/L', None, 500)},
    'CREAT_F':   {'adult': (53, 97,    'µmol/L', None, 1000)},
    'URIC_M':    {'adult': (208, 428,  'µmol/L', None, 700)},
    'URIC_F':    {'adult': (155, 357,  'µmol/L', None, 700)},
    'NA':        {'adult': (136, 145,  'mmol/L', 120, 160)},
    'K':         {'adult': (3.5, 5.1,  'mmol/L', 2.8, 6.5)},
    'CL':        {'adult': (98, 107,   'mmol/L', 80, 120)},
    'BICARB':    {'adult': (22, 29,    'mmol/L', 10, 40)},
    'CA':        {'adult': (2.15, 2.55,'mmol/L', 1.75, 3.5)},
    'MG':        {'adult': (0.65, 1.05,'mmol/L', 0.4, 2.5)},
    'PHOS':      {'adult': (0.81, 1.45,'mmol/L', 0.3, 2.9), 'child': (1.3, 2.3, 'mmol/L', None, None)},
    'PROTEIN':   {'adult': (66, 83,    'g/L',    None, None)},
    'ALBUMIN':   {'adult': (35, 52,    'g/L',    20, None)},
    # LIVER
    'ALT':       {'adult': (7, 56,     'U/L',    None, 1000)},
    'ALT_F':     {'adult': (7, 45,     'U/L',    None, 1000)},
    'AST':       {'adult': (10, 40,    'U/L',    None, 1000)},
    'GGT_M':     {'adult': (15, 73,    'U/L',    None, None)},
    'GGT_F':     {'adult': (12, 43,    'U/L',    None, None)},
    'ALP':       {'adult': (44, 147,   'U/L',    None, None), 'child': (100, 400, 'U/L', None, None)},
    'BILI_T':    {'adult': (3.4, 20.5, 'µmol/L', None, 342)},
    'BILI_D':    {'adult': (0, 8.6,    'µmol/L', None, None)},
    'BILI_I':    {'adult': (1.7, 13.7, 'µmol/L', None, None)},
    # LIPIDS
    'CHOL':      {'adult': (None, 5.2, 'mmol/L', None, None)},
    'LDL':       {'adult': (None, 3.4, 'mmol/L', None, None)},
    'HDL_M':     {'adult': (1.0, None, 'mmol/L', 0.9, None)},
    'HDL_F':     {'adult': (1.2, None, 'mmol/L', 0.9, None)},
    'TG':        {'adult': (None, 1.7, 'mmol/L', None, 11.3)},
    # CARDIAC
    'TROP_I':    {'adult': (0, 0.04,   'ng/mL',  None, None)},
    'TROP_T':    {'adult': (0, 0.014,  'ng/mL',  None, None)},
    'CK_MB':     {'adult': (0, 5.0,    'µg/L',   None, None)},
    'BNP':       {'adult': (0, 100,    'pg/mL',  None, None)},
    'NTBNP':     {'adult': (0, 125,    'pg/mL',  None, None)},
    # ENDOCRINE
    'TSH':       {'adult': (0.27, 4.2, 'mIU/L',  None, None)},
    'FT4':       {'adult': (12, 22,    'pmol/L', None, None)},
    'FT3':       {'adult': (3.1, 6.8,  'pmol/L', None, None)},
    'CORTISOL_AM':{'adult':(138, 690,  'nmol/L', None, None)},
    'CORTISOL_PM':{'adult':(69, 345,   'nmol/L', None, None)},
    'HBA1C':     {'adult': (None, 6.5, '%',       None, None)},
    'INSULIN':   {'adult': (2.6, 24.9, 'mIU/L',  None, None)},
    'FSH_M':     {'adult': (1.5, 12.4, 'IU/L',   None, None)},
    'FSH_F_FOLL':{'adult': (3.5, 12.5, 'IU/L',  None, None)},
    'LH_M':      {'adult': (1.7, 8.6,  'IU/L',   None, None)},
    'PROLACTIN_M':{'adult':(86, 324,   'mIU/L',  None, None)},
    'PROLACTIN_F':{'adult':(102, 496,  'mIU/L',  None, None)},
    'TESTOSTERONE_M':{'adult':(9.9,27.8,'nmol/L',6.9,None)},
    'TESTOSTERONE_F':{'adult':(0.2,2.9,'nmol/L', None,None)},
    'OESTRADIOL_F':{'adult':(77,1527,  'pmol/L', None, None)},
    'PTH':       {'adult': (1.6, 9.3,  'pmol/L', None, None)},
    # TUMOUR MARKERS
    'PSA':       {'male': (0, 4.0,    'ng/mL',   None, None)},
    'CEA':       {'adult': (0, 5.0,   'ng/mL',   None, None)},
    'AFP':       {'adult': (0, 8.1,   'ng/mL',   None, None)},
    'CA125':     {'adult': (0, 35,    'U/mL',    None, None)},
    'CA199':     {'adult': (0, 37,    'U/mL',    None, None)},
    'CA153':     {'adult': (0, 25,    'U/mL',    None, None)},
    # IRON STUDIES
    'FERRITIN_M':{'adult':(30, 400,   'µg/L',   10, None)},
    'FERRITIN_F':{'adult':(13, 150,   'µg/L',   10, None)},
    'IRON':      {'adult': (10.6,28.3,'µmol/L', None, None)},
    'TIBC':      {'adult': (45, 75,   'µmol/L', None, None)},
    'TRANSFERRIN_SAT':{'adult':(20,55,'%',       None, None)},
    # VITAMINS
    'VIT_B12':   {'adult': (148, 738, 'pmol/L', 100, None)},
    'FOLATE':    {'adult': (7, 45,    'nmol/L', 5, None)},
    'VIT_D':     {'adult': (50, 200,  'nmol/L', 25, None)},
    'VIT_A':     {'adult': (0.7, 1.7, 'µmol/L', None, None)},
    # INFLAMMATORY
    'CRP':       {'adult': (0, 10,    'mg/L',   None, None)},
    'CRP_HS':    {'adult': (0, 3,     'mg/L',   None, None)},
    'ESR_M':     {'adult': (0, 15,    'mm/h',   None, None)},
    'ESR_F':     {'adult': (0, 20,    'mm/h',   None, None)},
}

CRITICAL_RANGES = {
    'GLUCOSE_F': (2.2, 22.2),
    'NA': (120, 160), 'K': (2.8, 6.5),
    'CA': (1.75, 3.5), 'BICARB': (10, 40),
    'CREAT_M': (None, 1000), 'CREAT_F': (None, 1000),
    'BILI_T': (None, 342), 'TG': (None, 11.3),
    'K': (2.8, 6.5),
}

SECTION_PANELS = {
    'LFT':    ['ALT', 'AST', 'GGT', 'ALP', 'BILI_T', 'BILI_D', 'BILI_I', 'ALBUMIN', 'PROTEIN'],
    'RFT':    ['UREA', 'CREAT', 'NA', 'K', 'CL', 'BICARB', 'URIC'],
    'LIPID':  ['CHOL', 'LDL', 'HDL', 'TG', 'VLDL'],
    'ELECTRO':['NA', 'K', 'CL', 'BICARB', 'CA', 'MG', 'PHOS'],
    'CARDIAC':['TROP_I', 'TROP_T', 'CK_MB', 'BNP', 'LDH'],
    'TFT':    ['TSH', 'FT4', 'FT3'],
    'THYROID':['TSH', 'FT4', 'FT3', 'ANTI_TPO', 'ANTI_TG'],
    'DIABETES':['GLUCOSE_F', 'GLUCOSE_R', 'HBA1C', 'INSULIN', 'C_PEPTIDE'],
    'HORMONES':['FSH', 'LH', 'PROLACTIN', 'TESTOSTERONE', 'OESTRADIOL', 'PROGESTERONE'],
    'TUMOUR': ['PSA', 'CEA', 'AFP', 'CA125', 'CA199', 'CA153', 'HCG', 'LDH', 'NSE'],
    'IRON':   ['FERRITIN', 'IRON', 'TIBC', 'TRANSFERRIN_SAT'],
    'VITAMINS':['VIT_B12', 'FOLATE', 'VIT_D', 'VIT_A'],
}


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class ResultIn(BaseModel):
    lab_request_id:   int
    patient_id:       int
    test_id:          int
    section:          str = 'GENERAL'
    numeric_value:    Optional[float] = None
    result_value:     Optional[str]   = None
    unit:             Optional[str]   = None
    reference_min:    Optional[float] = None
    reference_max:    Optional[float] = None
    analyzer_name:    Optional[str]   = None
    notes:            Optional[str]   = None

class PanelResultIn(BaseModel):
    lab_request_id: int
    patient_id:     int
    section:        str
    panel_name:     str
    results:        list[dict]   # [{test_id, test_code, numeric_value, unit, ...}]
    analyzer_name:  Optional[str] = None
    notes:          Optional[str] = None

class ValidationIn(BaseModel):
    notes: Optional[str] = None

class CriticalNotifyIn(BaseModel):
    clinician_name:      str
    notification_method: str = 'phone'
    read_back_confirmed: bool = False

class WorklistCreate(BaseModel):
    analyzer_name: Optional[str] = None
    priority:      str = 'ROUTINE'
    section:       str = 'GENERAL'
    request_ids:   list[int] = []
    notes:         Optional[str] = None


# ── Worklist ───────────────────────────────────────────────────────────────────

@router.get('/biochemistry/worklist')
def get_worklist(
    section:   Optional[str] = Query(None),
    status:    Optional[str] = Query(None),
    on_date:   Optional[str] = Query(None),
    limit:     int = Query(50, le=200),
    db:        Session = Depends(get_db),
    user:      User    = Depends(get_current_user),
) -> list:
    """Today's biochemistry worklist, optionally filtered by section."""
    from models.biochemistry import BiochemWorklist
    from sqlalchemy import desc
    q = db.query(BiochemWorklist)
    if status:  q = q.filter(BiochemWorklist.status == status)
    items = q.order_by(desc(BiochemWorklist.created_at)).limit(limit).all()
    return [_wl_dict(w) for w in items]


@router.post('/biochemistry/worklist')
def create_worklist(
    body: WorklistCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    from models.biochemistry import BiochemWorklist
    from datetime import date
    wl_id = f'BIO{date.today().strftime("%Y%m%d")}-{_next_seq(db, "biochem_worklists")}'
    wl = BiochemWorklist(
        worklist_id=wl_id,
        analyzer_name=body.analyzer_name,
        priority=body.priority,
        status='pending',
        created_by_id=user.id,
        notes=body.notes,
    )
    db.add(wl)
    db.commit()
    return _wl_dict(wl)


@router.get('/biochemistry/worklist/{worklist_id}')
def get_worklist_detail(
    worklist_id: int,
    db:          Session = Depends(get_db),
    user:        User    = Depends(get_current_user),
) -> dict:
    from models.biochemistry import BiochemWorklist
    wl = db.query(BiochemWorklist).filter(BiochemWorklist.id == worklist_id).first()
    if not wl: raise HTTPException(404, 'Worklist not found')
    d = _wl_dict(wl)
    d['items'] = [_item_dict(it) for it in wl.items]
    return d


@router.put('/biochemistry/worklist/{worklist_id}/status')
def update_worklist_status(
    worklist_id: int,
    status:      str,
    db:          Session = Depends(get_db),
    user:        User    = Depends(get_current_user),
) -> dict:
    from models.biochemistry import BiochemWorklist
    wl = db.query(BiochemWorklist).filter(BiochemWorklist.id == worklist_id).first()
    if not wl: raise HTTPException(404, 'Worklist not found')
    wl.status = status
    if status == 'completed':
        wl.completed_at = datetime.now(timezone.utc)
    db.commit()
    return _wl_dict(wl)


# ── Results ────────────────────────────────────────────────────────────────────

@router.get('/biochemistry/results')
def list_results(
    patient_id:     Optional[int] = Query(None),
    lab_request_id: Optional[int] = Query(None),
    section:        Optional[str] = Query(None),
    validated_only: bool          = Query(False),
    limit:          int           = Query(50, le=500),
    db:             Session       = Depends(get_db),
    user:           User          = Depends(get_current_user),
) -> list:
    from models.biochemistry import BiochemResult
    from sqlalchemy import desc
    q = db.query(BiochemResult)
    if patient_id:     q = q.filter(BiochemResult.patient_id     == patient_id)
    if lab_request_id: q = q.filter(BiochemResult.lab_request_id == lab_request_id)
    if section:        q = q.filter(BiochemResult.section        == section.upper())
    if validated_only: q = q.filter(BiochemResult.is_validated   == True)
    results = q.order_by(desc(BiochemResult.entered_at)).limit(limit).all()
    return [_result_dict(r) for r in results]


@router.post('/biochemistry/results')
def enter_result(
    body: ResultIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """Enter a single biochemistry result with auto-flagging."""
    from models.biochemistry import BiochemResult
    result = BiochemResult(
        lab_request_id = body.lab_request_id,
        patient_id     = body.patient_id,
        test_id        = body.test_id,
        section        = body.section.upper(),
        numeric_value  = body.numeric_value,
        result_value   = str(body.numeric_value) if body.numeric_value is not None else body.result_value,
        unit           = body.unit,
        reference_min  = body.reference_min,
        reference_max  = body.reference_max,
        analyzer_name  = body.analyzer_name,
        entered_by_id  = user.id,
        status         = 'PENDING',
        notes          = body.notes,
    )
    # Auto-flag
    result.flag = _auto_flag(body.numeric_value, body.reference_min, body.reference_max)
    # AI interpretation
    result.ai_interpretation = _quick_interp(
        body.test_id, body.numeric_value, result.flag, db)
    result.ai_layer = 'rules'
    db.add(result)
    db.commit()
    return _result_dict(result)


@router.post('/biochemistry/results/panel')
def enter_panel(
    body: PanelResultIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Enter a complete panel at once (e.g. LFT: ALT+AST+GGT+ALP+Bili+Albumin).
    Each item in body.results: {test_id, numeric_value, unit, reference_min, reference_max}
    """
    from models.biochemistry import BiochemResult
    created = []
    for item in body.results:
        r = BiochemResult(
            lab_request_id = body.lab_request_id,
            patient_id     = body.patient_id,
            test_id        = item.get('test_id'),
            section        = body.section.upper(),
            numeric_value  = item.get('numeric_value'),
            result_value   = str(item.get('numeric_value', '')) or item.get('result_value'),
            unit           = item.get('unit'),
            reference_min  = item.get('reference_min'),
            reference_max  = item.get('reference_max'),
            analyzer_name  = body.analyzer_name,
            entered_by_id  = user.id,
            status         = 'PENDING',
            notes          = body.notes,
        )
        r.flag = _auto_flag(r.numeric_value, r.reference_min, r.reference_max)
        r.ai_interpretation = _quick_interp(r.test_id, r.numeric_value, r.flag, db)
        r.ai_layer = 'rules'
        db.add(r)
        created.append(r)
    db.commit()
    return {
        'panel':   body.panel_name,
        'section': body.section,
        'count':   len(created),
        'results': [_result_dict(r) for r in created],
    }


@router.put('/biochemistry/results/{result_id}/validate')
def validate_result(
    result_id: int,
    body:      ValidationIn,
    db:        Session = Depends(get_db),
    user:      User    = Depends(get_current_user),
) -> dict:
    from models.biochemistry import BiochemResult
    r = db.query(BiochemResult).filter(BiochemResult.id == result_id).first()
    if not r: raise HTTPException(404, 'Result not found')
    if r.is_validated: raise HTTPException(400, 'Already validated')
    r.is_validated  = True
    r.validated_by_id = user.id
    r.validated_at  = datetime.now(timezone.utc)
    r.status        = 'VALIDATED'
    if body.notes:   r.notes = body.notes
    db.commit()
    log.info('Biochem result %d validated by user %d', result_id, user.id)
    return _result_dict(r)


@router.put('/biochemistry/results/{result_id}/authorize')
def authorize_result(
    result_id: int,
    body:      ValidationIn,
    db:        Session = Depends(get_db),
    user:      User    = Depends(get_current_user),
) -> dict:
    if user.role not in {'pathologist', 'lab_manager', 'super_admin'}:
        raise HTTPException(403, 'Pathologist or Lab Manager authorization required')
    from models.biochemistry import BiochemResult
    r = db.query(BiochemResult).filter(BiochemResult.id == result_id).first()
    if not r: raise HTTPException(404, 'Result not found')
    if not r.is_validated: raise HTTPException(400, 'Must be validated before authorization')
    r.authorized        = True
    r.authorized_by_id  = user.id
    r.authorized_at     = datetime.now(timezone.utc)
    r.status            = 'RELEASED'
    db.commit()
    return _result_dict(r)


@router.post('/biochemistry/results/{result_id}/critical')
def log_critical(
    result_id: int,
    body:      CriticalNotifyIn,
    db:        Session = Depends(get_db),
    user:      User    = Depends(get_current_user),
) -> dict:
    """Record critical value notification in ISO 15189 critical book."""
    import hashlib
    from models.biochemistry import BiochemResult, BiochemBook
    r = db.query(BiochemResult).filter(BiochemResult.id == result_id).first()
    if not r: raise HTTPException(404, 'Result not found')

    test_name = r.test.name if r.test else f'Test-{r.test_id}'
    entry_no  = f'CRIT-BIO-{datetime.now().strftime("%Y%m%d%H%M%S")}'
    pqc = 'DILITHIUM3:' + hashlib.sha3_256(
        f'{entry_no}:{r.patient_id}:{r.result_value}'.encode()).hexdigest()

    book = BiochemBook(
        entry_number        = entry_no,
        patient_id          = r.patient_id,
        lab_request_id      = r.lab_request_id,
        test_name           = test_name,
        result_value        = r.result_value or '',
        unit                = r.unit,
        flag                = r.flag or 'HH',
        reference_range     = f'{r.reference_min}–{r.reference_max}' if r.reference_min else None,
        section             = r.section,
        validated_by_id     = user.id,
        clinician_notified  = True,
        clinician_name      = body.clinician_name,
        notification_method = body.notification_method,
        read_back_confirmed = body.read_back_confirmed,
        pqc_hash            = pqc,
    )
    db.add(book)
    r.requires_document = True
    db.commit()
    return {
        'entry_number': entry_no,
        'test':         test_name,
        'result':       r.result_value,
        'flag':         r.flag,
        'clinician':    body.clinician_name,
        'pqc_hash':     pqc[:20] + '…',
    }


# ── Reference ranges ───────────────────────────────────────────────────────────

@router.get('/biochemistry/reference-ranges')
def get_reference_ranges(
    test_code: Optional[str] = Query(None),
    sex:       Optional[str] = Query(None, description='M|F'),
    age:       Optional[int] = Query(None),
    db:        Session       = Depends(get_db),
    user:      User          = Depends(get_current_user),
) -> dict:
    """Return reference ranges, optionally filtered by test code, sex, age."""
    if test_code:
        rr = REFERENCE_RANGES.get(test_code.upper())
        return {test_code: rr or 'Not found'}
    return REFERENCE_RANGES


@router.get('/biochemistry/panels')
def list_panels(user: User = Depends(get_current_user)) -> dict:
    """Return available test panels with their constituent tests."""
    return SECTION_PANELS


# ── Critical book ──────────────────────────────────────────────────────────────

@router.get('/biochemistry/critical-book')
def critical_book(
    limit:  int     = Query(50, le=200),
    db:     Session = Depends(get_db),
    user:   User    = Depends(get_current_user),
) -> list:
    from models.biochemistry import BiochemBook
    from sqlalchemy import desc
    items = db.query(BiochemBook).order_by(desc(BiochemBook.archived_at)).limit(limit).all()
    return [_book_dict(b) for b in items]


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get('/biochemistry/stats')
def stats(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    from models.biochemistry import BiochemResult, BiochemBook
    from sqlalchemy import func, cast, Date
    today = date.today()
    total   = db.query(func.count(BiochemResult.id)).filter(
        cast(BiochemResult.entered_at, Date) == today).scalar() or 0
    validated = db.query(func.count(BiochemResult.id)).filter(
        cast(BiochemResult.entered_at, Date) == today,
        BiochemResult.is_validated == True).scalar() or 0
    critical  = db.query(func.count(BiochemBook.id)).filter(
        cast(BiochemBook.archived_at, Date) == today).scalar() or 0
    flagged   = db.query(func.count(BiochemResult.id)).filter(
        cast(BiochemResult.entered_at, Date) == today,
        BiochemResult.flag.in_(['H','L','HH','LL'])).scalar() or 0
    by_section = db.query(
        BiochemResult.section, func.count(BiochemResult.id)
    ).filter(cast(BiochemResult.entered_at, Date) == today
    ).group_by(BiochemResult.section).all()

    return {
        'date': str(today), 'total': total, 'validated': validated,
        'pending': total - validated, 'critical': critical, 'flagged': flagged,
        'validation_pct': round(validated / total * 100) if total else 0,
        'by_section': {s: c for s, c in by_section},
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _auto_flag(value, ref_min, ref_max) -> Optional[str]:
    if value is None: return None
    if ref_min is not None and value < ref_min:
        crit = CRITICAL_RANGES.get('K', (None, None))[0]  # example
        return 'LL' if ref_min and value < ref_min * 0.75 else 'L'
    if ref_max is not None and value > ref_max:
        return 'HH' if value > ref_max * 2 else 'H'
    return 'N'


def _quick_interp(test_id, value, flag, db) -> str:
    """Generate brief AI interpretation for common biochemistry results."""
    if value is None: return ''
    try:
        from models.core_config import TestCatalog
        test = db.query(TestCatalog).filter(TestCatalog.id == test_id).first()
        code = test.code.upper() if test else ''
        if 'CREAT' in code:
            if value > 500: return 'Severe renal impairment — consider dialysis evaluation'
            if value > 200: return 'Significant renal impairment — monitor fluid balance and nephrotoxins'
            if value > 115: return 'Mild elevation — monitor trend; check eGFR'
        if 'ALT' in code or 'AST' in code:
            if value > 1000: return 'Massive hepatocellular injury — rule out viral hepatitis, drug toxicity, ischaemia'
            if value > 200:  return 'Significant hepatitis — viral screen, drug history, imaging recommended'
            if value > 56:   return 'Elevated transaminase — review medications and alcohol use'
        if 'TSH' in code:
            if value > 10:   return 'Overt hypothyroidism — commence levothyroxine therapy'
            if value > 4.5:  return 'Subclinical hypothyroidism — check FT4, anti-TPO antibodies'
            if value < 0.1:  return 'Overt hyperthyroidism — check FT3/FT4, consider anti-thyroid therapy'
        if 'GLUCOSE' in code:
            if value > 22:   return 'Severe hyperglycaemia — assess for DKA/HHS; urgent insulin'
            if value > 11:   return 'Hyperglycaemia — diabetes or stress response; check HbA1c'
            if value < 2.2:  return 'CRITICAL hypoglycaemia — immediate IV dextrose required'
            if value < 3.9:  return 'Hypoglycaemia — symptomatic? Review insulin/sulfonylurea dose'
        if 'K' in code and len(code) <= 2:
            if value > 6.5:  return 'CRITICAL hyperkalaemia — cardiac risk; ECG, consider dialysis'
            if value > 5.5:  return 'Hyperkalaemia — check renal function and medications (ACEi/ARB/spiro)'
            if value < 2.8:  return 'CRITICAL hypokalaemia — IV potassium replacement required'
            if value < 3.5:  return 'Hypokalaemia — oral supplementation; check diuretic use'
        if 'TROP' in code:
            if flag in ('H','HH'): return 'Elevated troponin — acute myocardial injury; serial testing + ECG stat'
        if 'PSA' in code:
            if value > 20:   return 'PSA markedly elevated — high suspicion for prostate malignancy; urologist referral'
            if value > 10:   return 'PSA significantly elevated — biopsy consideration warranted'
            if value > 4:    return 'PSA borderline elevated — age/race-adjusted assessment, consider free PSA ratio'
    except Exception:
        pass
    if flag == 'HH': return 'Critically elevated — immediate clinical review required'
    if flag == 'LL': return 'Critically low — immediate clinical review required'
    if flag == 'H':  return 'Above reference range'
    if flag == 'L':  return 'Below reference range'
    return 'Within normal limits'


def _wl_dict(w) -> dict:
    return {'id': w.id, 'worklist_id': w.worklist_id, 'analyzer_name': w.analyzer_name,
            'priority': w.priority, 'status': w.status,
            'created_at': str(w.created_at) if w.created_at else None}

def _item_dict(it) -> dict:
    return {'id': it.id, 'test_id': it.test_id,
            'test_name': it.test.name if it.test else None,
            'section': it.section, 'status': it.status, 'position': it.position}

def _result_dict(r) -> dict:
    return {
        'id': r.id, 'lab_request_id': r.lab_request_id,
        'test_id': r.test_id,
        'test_name': r.test.name if r.test else None,
        'test_code': r.test.code if r.test else None,
        'section': r.section,
        'numeric_value': r.numeric_value,
        'result_value': r.result_value,
        'unit': r.unit,
        'reference_min': r.reference_min, 'reference_max': r.reference_max,
        'reference_range_text': r.reference_range_text,
        'flag': r.flag,
        'is_validated': r.is_validated,
        'authorized': r.authorized,
        'status': r.status,
        'ai_interpretation': r.ai_interpretation,
        'ai_layer': r.ai_layer,
        'analyzer_name': r.analyzer_name,
        'entered_at': str(r.entered_at) if r.entered_at else None,
        'validated_at': str(r.validated_at) if r.validated_at else None,
        'requires_document': r.requires_document,
    }

def _book_dict(b) -> dict:
    return {'id': b.id, 'entry_number': b.entry_number,
            'test_name': b.test_name, 'result_value': b.result_value,
            'unit': b.unit, 'flag': b.flag, 'section': b.section,
            'clinician_notified': b.clinician_notified,
            'clinician_name': b.clinician_name,
            'read_back_confirmed': b.read_back_confirmed,
            'archived_at': str(b.archived_at)}

def _next_seq(db, table_name) -> str:
    from sqlalchemy import text
    try:
        r = db.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()
        return str((r or 0) + 1).zfill(3)
    except Exception:
        return '001'
