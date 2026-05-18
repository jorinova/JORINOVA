"""Serology router — HIV, Hepatitis, VDRL, Widal, CRP, tumour markers."""
from typing import Optional
from datetime import date as date_t, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.serology import SerologyResult

router = APIRouter(prefix='/serology', tags=['Serology'])


def _gen_id(db):
    year = date_t.today().year
    n = db.query(SerologyResult).filter(SerologyResult.sero_id.like(f'SER-{year}-%')).count()
    return f'SER-{year}-{str(n+1).zfill(5)}'


BSL2_TESTS = {'HIV_1_2','HBSAG','ANTI_HCV','ANTI_HIV','HIV_RAPID'}


class SeroOut(BaseModel):
    id: int; sero_id: str; lab_request_id: int; patient_id: int
    pid: Optional[str]; lid: Optional[str]; test_code: str; test_name: str
    test_category: str; qualitative: Optional[str]; numeric_value: Optional[float]
    unit: Optional[str]; sco_ratio: Optional[float]; titre: Optional[str]
    method: Optional[str]; flag: Optional[str]; bsl_2_alert: bool
    confirmatory_required: bool; confirmatory_done: bool
    is_validated: bool; is_critical: bool; status: str
    ai_interpretation: Optional[str]; created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class SeroCreate(BaseModel):
    lab_request_id: int; patient_id: int
    pid: Optional[str] = None; lid: Optional[str] = None
    test_code: str; test_name: str
    test_category: str = 'SEROLOGY'
    qualitative: Optional[str] = None
    numeric_value: Optional[float] = None; unit: Optional[str] = None
    sco_ratio: Optional[float] = None; titre: Optional[str] = None
    method: Optional[str] = None; result_source: str = 'MANUAL'
    notes: Optional[str] = None


@router.get('/dashboard')
def dashboard(db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    today = date_t.today()
    return {
        'pending': db.query(SerologyResult).filter(SerologyResult.status=='PENDING').count(),
        'today': db.query(SerologyResult).filter(func.date(SerologyResult.created_at)==today).count(),
        'reactive_today': db.query(SerologyResult).filter(SerologyResult.qualitative=='REACTIVE', func.date(SerologyResult.created_at)==today).count(),
        'bsl2_today': db.query(SerologyResult).filter(SerologyResult.bsl_2_alert==True, func.date(SerologyResult.created_at)==today).count(),
        'confirmatory_pending': db.query(SerologyResult).filter(SerologyResult.confirmatory_required==True, SerologyResult.confirmatory_done==False).count(),
    }


@router.get('/results', response_model=list[SeroOut])
def list_results(
    category: Optional[str]=None, test_code: Optional[str]=None,
    qualitative: Optional[str]=None, date: Optional[str]=None,
    validated: Optional[bool]=None, skip: int=0, limit: int=50,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    q = db.query(SerologyResult)
    if category:   q = q.filter(SerologyResult.test_category==category)
    if test_code:  q = q.filter(SerologyResult.test_code==test_code.upper())
    if qualitative:q = q.filter(SerologyResult.qualitative==qualitative)
    if date:       q = q.filter(func.date(SerologyResult.created_at)==date)
    if validated is not None: q = q.filter(SerologyResult.is_validated==validated)
    return q.order_by(desc(SerologyResult.created_at)).offset(skip).limit(limit).all()


@router.post('/results', response_model=SeroOut, status_code=201)
def create_result(body: SeroCreate, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    bsl2 = body.test_code.upper() in BSL2_TESTS
    reactive = body.qualitative in ('REACTIVE','POSITIVE')
    confirm_req = reactive and bsl2
    flag = 'POS' if reactive else ('NEG' if body.qualitative in ('NON_REACTIVE','NEGATIVE') else 'N')
    rec = SerologyResult(
        sero_id=_gen_id(db), entered_by_id=user.id,
        bsl_2_alert=bsl2, confirmatory_required=confirm_req,
        flag=flag, is_critical=reactive and bsl2,
        **body.model_dump(),
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


@router.post('/results/{rid}/validate', response_model=SeroOut)
def validate(rid: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    r = db.query(SerologyResult).filter(SerologyResult.id==rid).first()
    if not r: raise HTTPException(404, 'Not found')
    r.is_validated=True; r.validated_by_id=user.id
    r.validated_at=datetime.now(timezone.utc); r.status='VALIDATED'
    db.commit(); db.refresh(r); return r


@router.patch('/results/{rid}/confirmatory')
def mark_confirmatory_done(rid: int, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    r = db.query(SerologyResult).filter(SerologyResult.id==rid).first()
    if not r: raise HTTPException(404, 'Not found')
    r.confirmatory_done = True; db.commit()
    return {'status': 'confirmatory_marked_done'}
