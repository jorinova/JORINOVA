"""Coagulation router — PT, INR, aPTT, Fibrinogen, D-Dimer, anticoagulant monitoring."""
from typing import Optional
from datetime import date as date_t, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.coagulation import CoagResult, CoagIQC

router = APIRouter(prefix='/coagulation', tags=['Coagulation'])

# Therapeutic ranges (offline)
RANGES = {
    'PT':    (11.0, 14.0, None, 30.0),     # lo, hi, crit_lo, crit_hi
    'INR':   (0.8, 1.2, None, 3.0),
    'APTT':  (25.0, 35.0, None, 70.0),
    'FIBRIN':(2.0, 4.0, 1.0, None),
    'DDIMER':(None, 0.5, None, 5.0),
    'TT':    (14.0, 21.0, None, None),
}


def _gen_id(db):
    year = date_t.today().year
    n = db.query(CoagResult).filter(CoagResult.coag_id.like(f'COA-{year}-%')).count()
    return f'COA-{year}-{str(n+1).zfill(5)}'


def _auto_flag(code: str, value: float) -> str:
    r = RANGES.get(code.upper())
    if not r or value is None: return 'N'
    lo, hi, crit_lo, crit_hi = r
    if crit_hi and value > crit_hi: return 'HH'
    if crit_lo and value < crit_lo: return 'LL'
    if hi and value > hi:           return 'H'
    if lo and value < lo:           return 'L'
    return 'N'


class CoagOut(BaseModel):
    id: int; coag_id: str; lab_request_id: int; patient_id: int
    pid: Optional[str]; lid: Optional[str]; test_code: str; test_name: str
    numeric_value: Optional[float]; unit: Optional[str]; flag: Optional[str]
    reference_lo: Optional[float]; reference_hi: Optional[float]
    anticoagulant: Optional[str]; anticoag_status: Optional[str]
    result_source: str; is_validated: bool; is_critical: bool; status: str
    ai_interpretation: Optional[str]; created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class CoagCreate(BaseModel):
    lab_request_id: int; patient_id: int
    pid: Optional[str] = None; lid: Optional[str] = None
    test_code: str; test_name: str
    numeric_value: Optional[float] = None; unit: Optional[str] = None
    result_source: str = 'MANUAL'; analyzer_name: Optional[str] = None
    anticoagulant: Optional[str] = None; anticoag_target: Optional[str] = None
    clinical_context: Optional[str] = None; notes: Optional[str] = None


class DashStats(BaseModel):
    pending: int; critical_today: int; inr_elevated: int
    aptt_prolonged: int; anticoag_monitoring: int


@router.get('/dashboard', response_model=DashStats)
def dashboard(db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    today = date_t.today()
    return DashStats(
        pending=db.query(CoagResult).filter(CoagResult.status=='PENDING').count(),
        critical_today=db.query(CoagResult).filter(CoagResult.is_critical==True, func.date(CoagResult.created_at)==today).count(),
        inr_elevated=db.query(CoagResult).filter(CoagResult.test_code=='INR', CoagResult.flag.in_(['H','HH'])).count(),
        aptt_prolonged=db.query(CoagResult).filter(CoagResult.test_code=='APTT', CoagResult.flag.in_(['H','HH'])).count(),
        anticoag_monitoring=db.query(CoagResult).filter(CoagResult.anticoagulant!=None).count(),
    )


@router.get('/results', response_model=list[CoagOut])
def list_results(
    test_code: Optional[str]=None, flag: Optional[str]=None,
    date: Optional[str]=None, validated: Optional[bool]=None,
    skip: int=0, limit: int=50,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    q = db.query(CoagResult)
    if test_code: q = q.filter(CoagResult.test_code==test_code.upper())
    if flag:      q = q.filter(CoagResult.flag==flag)
    if date:      q = q.filter(func.date(CoagResult.created_at)==date)
    if validated is not None: q = q.filter(CoagResult.is_validated==validated)
    return q.order_by(desc(CoagResult.created_at)).offset(skip).limit(limit).all()


@router.post('/results', response_model=CoagOut, status_code=201)
def create_result(body: CoagCreate, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    flag = _auto_flag(body.test_code, body.numeric_value or 0)
    r = RANGES.get(body.test_code.upper())
    ref_lo = r[0] if r else None; ref_hi = r[1] if r else None
    crit = flag in ('HH','LL')
    rec = CoagResult(
        coag_id=_gen_id(db), entered_by_id=user.id,
        flag=flag, reference_lo=ref_lo, reference_hi=ref_hi,
        is_critical=crit, **body.model_dump(),
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


@router.post('/results/{rid}/validate', response_model=CoagOut)
def validate(rid: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    r = db.query(CoagResult).filter(CoagResult.id==rid).first()
    if not r: raise HTTPException(404, 'Not found')
    r.is_validated=True; r.validated_by_id=user.id
    r.validated_at=datetime.now(timezone.utc); r.status='VALIDATED'
    db.commit(); db.refresh(r); return r


@router.get('/iqc')
def list_iqc(analyte: Optional[str]=None, skip: int=0, limit: int=100,
             db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(CoagIQC)
    if analyte: q = q.filter(CoagIQC.analyte_code==analyte)
    return q.order_by(desc(CoagIQC.created_at)).offset(skip).limit(limit).all()


@router.post('/iqc', status_code=201)
def create_iqc(
    analyte_code: str, analyte_name: str, control_level: str,
    target_mean: float, sd: float, result_value: float,
    lot_number: Optional[str]=None, analyzer_name: Optional[str]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    z = (result_value - target_mean) / sd if sd != 0 else 0
    status = 'REJECT' if abs(z) > 3 else ('WARN' if abs(z) > 2 else 'PASS')
    rule = '1_3s' if abs(z) > 3 else ('1_2s' if abs(z) > 2 else 'PASS')
    rec = CoagIQC(
        analyte_code=analyte_code, analyte_name=analyte_name,
        control_level=control_level, lot_number=lot_number,
        target_mean=target_mean, sd=sd, result_value=result_value,
        z_score=round(z, 3), westgard_rule=rule, status=status,
        analyzer_name=analyzer_name, operator_id=user.id,
        operator_name=f'{user.first_name} {user.last_name}'.strip() or user.username,
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return {'id': rec.id, 'z_score': round(z,3), 'status': status, 'rule': rule}
