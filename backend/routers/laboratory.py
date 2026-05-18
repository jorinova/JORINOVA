"""Laboratory router — requests, samples, results, validation, critical book."""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.laboratory import LabRequest, Sample, LabResult, CriticalResultBook
from models.patient import Patient

router = APIRouter(prefix='/laboratory', tags=['Laboratory'])


# ── Lab Requests ───────────────────────────────────────────────────────────────

class LabRequestOut(BaseModel):
    id:             int
    lab_id:         str
    patient_id:     int
    pid:            Optional[str]
    lid:            Optional[str]
    status:         str
    emergency_level:str
    doctor_name:    Optional[str]
    ward:           Optional[str]
    diagnosis:      Optional[str]
    request_date:   datetime
    model_config = {'from_attributes': True}


class LabRequestCreate(BaseModel):
    patient_id:     int
    doctor_name:    Optional[str] = None
    ward:           Optional[str] = None
    diagnosis:      Optional[str] = None
    emergency_level:str = 'routine'
    is_high_risk:   bool = False
    notes:          Optional[str] = None


def _gen_lab_id(db: Session) -> str:
    from datetime import date as d
    year  = d.today().year
    count = db.query(LabRequest).filter(LabRequest.lab_id.like(f'LAB-{year}-%')).count()
    return f'LAB-{year}-{str(count+1).zfill(5)}'


@router.get('/requests', response_model=list[LabRequestOut])
def list_requests(
    status:  Optional[str] = None,
    date:    Optional[str] = None,
    skip:    int = 0, limit: int = 50,
    db:      Session = Depends(get_db),
    _user:   User    = Depends(get_current_user),
):
    q = db.query(LabRequest)
    if status: q = q.filter(LabRequest.status == status)
    if date:   q = q.filter(LabRequest.request_date >= date)
    return q.order_by(LabRequest.request_date.desc()).offset(skip).limit(limit).all()


@router.post('/requests', response_model=LabRequestOut, status_code=201)
def create_request(
    body:  LabRequestCreate,
    db:    Session = Depends(get_db),
    _user: User    = Depends(get_current_user),
):
    patient = db.query(Patient).filter(Patient.id == body.patient_id).first()
    if not patient:
        raise HTTPException(404, 'Patient not found')
    lab_id = _gen_lab_id(db)
    req = LabRequest(
        lab_id=lab_id, patient_id=body.patient_id,
        pid=patient.pid, lid=patient.unique_lab_id,
        doctor_name=body.doctor_name, ward=body.ward,
        diagnosis=body.diagnosis, emergency_level=body.emergency_level,
        is_high_risk=body.is_high_risk, notes=body.notes,
        requested_by_id=_user.id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.patch('/requests/{req_id}/status')
def update_request_status(
    req_id: int, status: str,
    db: Session = Depends(get_db), _user: User = Depends(get_current_user),
):
    req = db.query(LabRequest).filter(LabRequest.id == req_id).first()
    if not req:
        raise HTTPException(404)
    req.status = status
    if status == 'received':
        req.received_at = datetime.now(timezone.utc)
        req.received_by_id = _user.id
    db.commit()
    return {'status': status}


# ── Samples ────────────────────────────────────────────────────────────────────

class SampleOut(BaseModel):
    id:            int
    sid:           str
    barcode:       str
    lab_request_id:int
    tube_type:     Optional[str]
    status:        str
    tat_start:     Optional[datetime]
    label_printed: bool
    model_config = {'from_attributes': True}


class SampleCreate(BaseModel):
    lab_request_id: int
    tube_type:      Optional[str] = None
    volume_ml:      Optional[float] = None
    is_high_risk:   bool = False
    notes:          Optional[str] = None


def _gen_sid(db: Session) -> str:
    from datetime import date as d
    year  = d.today().year
    count = db.query(Sample).filter(Sample.sid.like(f'SID-{year}-%')).count()
    return f'SID-{year}-{str(count+1).zfill(5)}'


@router.post('/samples', response_model=SampleOut, status_code=201)
def receive_sample(
    body: SampleCreate,
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
):
    import secrets
    sid     = _gen_sid(db)
    barcode = f'BC{secrets.token_hex(4).upper()}'
    sample  = Sample(
        sid=sid, barcode=barcode,
        lab_request_id=body.lab_request_id,
        tube_type=body.tube_type, volume_ml=body.volume_ml,
        is_high_risk=body.is_high_risk, notes=body.notes,
        status='received', tat_start=datetime.now(timezone.utc),
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


@router.get('/samples/{sample_id}', response_model=SampleOut)
def get_sample(sample_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    s = db.query(Sample).filter(Sample.id == sample_id).first()
    if not s:
        raise HTTPException(404)
    return s


# ── Results ────────────────────────────────────────────────────────────────────

class ResultOut(BaseModel):
    id:               int
    lab_request_id:   int
    pid:              Optional[str]
    lid:              Optional[str]
    value:            Optional[str]
    numeric_value:    Optional[float]
    unit:             Optional[str]
    flag:             Optional[str]
    result_source:    str
    analyzer_name:    Optional[str]
    is_validated:     bool
    authorized:       bool
    status:           str
    requires_document:bool
    ai_interpretation:Optional[str]
    ai_layer:         Optional[str]
    model_config = {'from_attributes': True}


class ResultCreate(BaseModel):
    lab_request_id:   int
    sample_id:        Optional[int] = None
    test_id:          Optional[int] = None
    value:            Optional[str] = None
    numeric_value:    Optional[float] = None
    unit:             Optional[str] = None
    reference_min:    Optional[float] = None
    reference_max:    Optional[float] = None
    flag:             Optional[str] = None
    qualitative_value:Optional[str] = None
    result_source:    str = 'MANUAL'
    entry_mode:       str = 'SINGLE'
    analyzer_name:    Optional[str] = None
    notes:            Optional[str] = None
    run_ai:           bool = True


@router.post('/results', response_model=ResultOut, status_code=201)
def enter_result(
    body:       ResultCreate,
    background: BackgroundTasks,
    db:         Session = Depends(get_db),
    _user:      User    = Depends(get_current_user),
):
    req = db.query(LabRequest).filter(LabRequest.id == body.lab_request_id).first()
    if not req:
        raise HTTPException(404, 'Lab request not found')

    flag = (body.flag or '').upper() if body.flag is not None else None
    # Allow 0.0 reference bounds; only require they are not None
    if (not flag) and body.numeric_value is not None and body.reference_min is not None and body.reference_max is not None:

        v = body.numeric_value
        if v < body.reference_min * 0.7: flag = 'LL'
        elif v < body.reference_min:     flag = 'L'
        elif v > body.reference_max * 1.3: flag = 'HH'
        elif v > body.reference_max:     flag = 'H'
        else:                             flag = 'N'

    result = LabResult(
        lab_request_id=body.lab_request_id, sample_id=body.sample_id,
        test_id=body.test_id, pid=req.pid, lid=req.lid,
        value=body.value, numeric_value=body.numeric_value,
        unit=body.unit, reference_min=body.reference_min,
        reference_max=body.reference_max, flag=flag,
        qualitative_value=body.qualitative_value,
        result_source=body.result_source, entry_mode=body.entry_mode,
        analyzer_name=body.analyzer_name, notes=body.notes,
        entered_by_id=_user.id,
        requires_document=flag in ('HH', 'LL'),
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    # Always store AI interpretation only when flag is present
    if body.run_ai and flag:
        background.add_task(_run_ai_interpretation, result.id, body, flag, db)


    return result


async def _run_ai_interpretation(result_id: int, body: ResultCreate, flag: str, db: Session):
    from services.ai_engine import interpret_result
    from models.core_config import TestCatalog
    test_name = 'Unknown'
    if body.test_id:
        test = db.query(TestCatalog).filter(TestCatalog.id == body.test_id).first()
        if test:
            test_name = test.name
    interp = await interpret_result(
        test_code='', test_name=test_name,
        value=str(body.value or body.numeric_value or ''),
        unit=body.unit or '', flag=flag, db=db,
    )
    result = db.query(LabResult).filter(LabResult.id == result_id).first()
    if result:
        import json
        # Orchestrator returns keys like: {"rules": {...}, "layer": "..."}
        # Older ai_engine payloads used different keys.
        rules_payload = interp.get('rules', interp.get('rule_engine', {}))
        result.ai_interpretation = json.dumps(rules_payload, ensure_ascii=False)
        result.ai_layer = interp.get('layer', interp.get('ai_layer', ''))
        db.commit()



@router.post('/results/{result_id}/validate')
def validate_result(
    result_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    r = db.query(LabResult).filter(LabResult.id == result_id).first()
    if not r:
        raise HTTPException(404, 'Result not found')

    # Workflow preconditions
    if r.status != 'PENDING':
        raise HTTPException(400, f'Cannot validate result in status={r.status}')

    # Critical results require clinician doc confirmation
    if r.requires_document and not r.critical_doc_uploaded:
        raise HTTPException(400, 'Critical/require-document result must have clinician documentation uploaded before validation')

    r.is_validated = True
    r.validated_by_id = _user.id
    r.validated_at = datetime.now(timezone.utc)
    r.status = 'VALIDATED'
    db.commit()
    return {'status': 'validated'}


    



@router.post('/results/{result_id}/release')
def release_result(
    result_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    r = db.query(LabResult).filter(LabResult.id == result_id).first()
    if not r:
        raise HTTPException(404)
    # Workflow preconditions
    if r.status != 'VALIDATED' or not r.is_validated:
        raise HTTPException(400, f"Must be validated before release (status={r.status}, is_validated={r.is_validated})")
    if r.requires_document and not r.critical_doc_uploaded:
        raise HTTPException(400, 'Critical/require-document result must have clinician documentation uploaded before release')

    r.authorized    = True

    r.authorized_by_id = _user.id
    r.authorized_at = datetime.now(timezone.utc)
    r.status        = 'RELEASED'
    db.commit()
    return {'status': 'released'}


@router.get('/results/pending-validation', response_model=list[ResultOut])
def pending_validation(
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db), _: User = Depends(get_current_user),
):
    return db.query(LabResult).filter(
        LabResult.is_validated == False,
        LabResult.status == 'PENDING',
    ).order_by(LabResult.entered_at.desc()).offset(skip).limit(limit).all()


@router.get('/stats')
def lab_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from datetime import date as d
    today = d.today()
    return {
        'requests_today':   db.query(LabRequest).filter(LabRequest.request_date >= str(today)).count(),
        'pending_results':  db.query(LabResult).filter(LabResult.status == 'PENDING').count(),
        'pending_validation':db.query(LabResult).filter(LabResult.is_validated == False).count(),
        'critical_today':   db.query(LabResult).filter(
            LabResult.flag.in_(['HH','LL']),
            LabResult.entered_at >= str(today),
        ).count(),
    }
