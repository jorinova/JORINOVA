"""Urinalysis router — dipstick, microscopy, culture referrals, special tests."""
from typing import Optional
from datetime import date as date_t, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.urinalysis import DipstickResult, UrineМicroscopy

router = APIRouter(prefix='/urinalysis', tags=['Urinalysis'])


def _gen_dip_id(db):
    year = date_t.today().year
    n = db.query(DipstickResult).filter(DipstickResult.dip_id.like(f'DIP-{year}-%')).count()
    return f'DIP-{year}-{str(n+1).zfill(5)}'


def _gen_micro_id(db):
    year = date_t.today().year
    n = db.query(UrineМicroscopy).filter(UrineМicroscopy.micro_id.like(f'UMC-{year}-%')).count()
    return f'UMC-{year}-{str(n+1).zfill(5)}'


class DipOut(BaseModel):
    id: int; dip_id: str; lab_request_id: int; patient_id: int
    pid: Optional[str]; lid: Optional[str]; colour: Optional[str]
    appearance: Optional[str]; ph: Optional[float]; sg: Optional[float]
    blood: Optional[str]; protein: Optional[str]; glucose: Optional[str]
    ketones: Optional[str]; bilirubin: Optional[str]; nitrite: Optional[str]
    leukocytes: Optional[str]; uti_suspected: bool; overall_flag: Optional[str]
    microscopy_required: bool; culture_referred: bool
    is_validated: bool; status: str; created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class DipCreate(BaseModel):
    lab_request_id: int; patient_id: int
    pid: Optional[str]=None; lid: Optional[str]=None
    colour: Optional[str]=None; appearance: Optional[str]=None
    ph: Optional[float]=None; sg: Optional[float]=None
    blood: Optional[str]=None; protein: Optional[str]=None
    glucose: Optional[str]=None; ketones: Optional[str]=None
    bilirubin: Optional[str]=None; urobilinogen: Optional[str]=None
    nitrite: Optional[str]=None; leukocytes: Optional[str]=None
    result_source: str='MANUAL'; analyzer_name: Optional[str]=None
    microscopy_required: bool=False; culture_referred: bool=False
    notes: Optional[str]=None


@router.get('/dashboard')
def dashboard(db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    today = date_t.today()
    return {
        'total_today': db.query(DipstickResult).filter(func.date(DipstickResult.created_at)==today).count(),
        'abnormal_today': db.query(DipstickResult).filter(DipstickResult.overall_flag=='ABNORMAL', func.date(DipstickResult.created_at)==today).count(),
        'uti_suspected': db.query(DipstickResult).filter(DipstickResult.uti_suspected==True).count(),
        'culture_referred': db.query(DipstickResult).filter(DipstickResult.culture_referred==True).count(),
        'pending': db.query(DipstickResult).filter(DipstickResult.status=='PENDING').count(),
    }


@router.get('/dipstick', response_model=list[DipOut])
def list_dipstick(
    flag: Optional[str]=None, date: Optional[str]=None,
    uti_only: bool=False, skip: int=0, limit: int=50,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    q = db.query(DipstickResult)
    if flag:     q = q.filter(DipstickResult.overall_flag==flag)
    if date:     q = q.filter(func.date(DipstickResult.created_at)==date)
    if uti_only: q = q.filter(DipstickResult.uti_suspected==True)
    return q.order_by(desc(DipstickResult.created_at)).offset(skip).limit(limit).all()


@router.post('/dipstick', response_model=DipOut, status_code=201)
def create_dipstick(body: DipCreate, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    abnormal_params = ['blood','protein','glucose','ketones','bilirubin','nitrite','leukocytes']
    is_abnormal = any(getattr(body, p) not in (None,'NEG','NORMAL') for p in abnormal_params)
    uti = body.nitrite=='POS' and body.leukocytes not in (None,'NEG')
    rec = DipstickResult(
        dip_id=_gen_dip_id(db), entered_by_id=user.id,
        overall_flag='ABNORMAL' if is_abnormal else 'NORMAL',
        uti_suspected=uti, **body.model_dump(),
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


@router.post('/dipstick/{did}/validate')
def validate_dipstick(did: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    r = db.query(DipstickResult).filter(DipstickResult.id==did).first()
    if not r: raise HTTPException(404, 'Not found')
    r.is_validated=True; r.validated_by_id=user.id; r.status='VALIDATED'
    r.validated_at=datetime.now(timezone.utc)
    db.commit(); return {'status': 'validated'}


@router.get('/microscopy')
def list_microscopy(date: Optional[str]=None, skip: int=0, limit: int=50,
                    db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(UrineМicroscopy)
    if date: q = q.filter(func.date(UrineМicroscopy.created_at)==date)
    return q.order_by(desc(UrineМicroscopy.created_at)).offset(skip).limit(limit).all()


@router.post('/microscopy', status_code=201)
def create_microscopy(
    lab_request_id: int, patient_id: int,
    pid: Optional[str]=None, lid: Optional[str]=None,
    rbc_hpf: Optional[str]=None, wbc_hpf: Optional[str]=None,
    bacteria: Optional[str]=None, cast_type: Optional[str]=None,
    yeast: Optional[str]=None, culture_referred: bool=False,
    culture_reason: Optional[str]=None,
    dipstick_id: Optional[int]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    rec = UrineМicroscopy(
        micro_id=_gen_micro_id(db), lab_request_id=lab_request_id,
        patient_id=patient_id, pid=pid, lid=lid,
        rbc_hpf=rbc_hpf, wbc_hpf=wbc_hpf, bacteria=bacteria,
        path_casts=cast_type, yeast=yeast,
        culture_referred=culture_referred, culture_reason=culture_reason,
        dipstick_id=dipstick_id, entered_by_id=user.id,
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return {'id': rec.id, 'micro_id': rec.micro_id, 'culture_referred': culture_referred}
