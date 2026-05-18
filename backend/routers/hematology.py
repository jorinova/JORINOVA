"""Hematology router — CBC, ESR, Malaria, Peripheral Smear."""
from typing import Optional
from datetime import date as date_t, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.hematology import HemResult, MalariaResult, PeripheralSmear

router = APIRouter(prefix='/hematology', tags=['Hematology'])


def _gen_id(prefix, db, model, field):
    year = date_t.today().year
    col = getattr(model, field)
    n = db.query(model).filter(col.like(f'{prefix}-{year}-%')).count()
    return f'{prefix}-{year}-{str(n+1).zfill(5)}'


class HemOut(BaseModel):
    id: int; hem_id: str; lab_request_id: int; patient_id: int
    pid: Optional[str]; lid: Optional[str]
    hgb: Optional[float]; wbc: Optional[float]; plt: Optional[float]
    rbc: Optional[float]; hct: Optional[float]; mcv: Optional[float]
    mch: Optional[float]; mchc: Optional[float]; rdw: Optional[float]
    neut_pct: Optional[float]; lymph_pct: Optional[float]
    hgb_flag: Optional[str]; wbc_flag: Optional[str]; plt_flag: Optional[str]
    overall_flag: Optional[str]; result_source: str; analyzer_name: Optional[str]
    is_validated: bool; is_critical: bool; status: str
    ai_interpretation: Optional[str]; ai_classification: Optional[str]
    created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class HemCreate(BaseModel):
    lab_request_id: int; patient_id: int
    pid: Optional[str] = None; lid: Optional[str] = None
    hgb: Optional[float] = None; rbc: Optional[float] = None
    wbc: Optional[float] = None; plt: Optional[float] = None
    hct: Optional[float] = None; mcv: Optional[float] = None
    mch: Optional[float] = None; mchc: Optional[float] = None
    rdw: Optional[float] = None; neut_pct: Optional[float] = None
    lymph_pct: Optional[float] = None; mono_pct: Optional[float] = None
    eos_pct: Optional[float] = None; baso_pct: Optional[float] = None
    neut_abs: Optional[float] = None; lymph_abs: Optional[float] = None
    esr: Optional[float] = None; result_source: str = 'MANUAL'
    analyzer_name: Optional[str] = None; notes: Optional[str] = None


class MalariaOut(BaseModel):
    id: int; mal_id: str; lab_request_id: int; patient_id: int
    pid: Optional[str]; lid: Optional[str]; test_type: str
    rdt_result: Optional[str]; smear_result: Optional[str]
    species: Optional[str]; parasitemia_pct: Optional[float]
    parasitemia_grade: Optional[str]; is_validated: bool
    is_critical: bool; status: str; ai_interpretation: Optional[str]
    created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class DashboardStats(BaseModel):
    cbc_pending: int; cbc_today: int; critical_today: int
    malaria_positive_today: int; anaemia_cases: int


def _auto_flags(h: HemCreate) -> dict:
    """Apply critical/high/low flags to CBC results."""
    flags = {}
    if h.hgb is not None:
        if h.hgb < 7.0:   flags['hgb_flag'] = 'LL'
        elif h.hgb < 11.0: flags['hgb_flag'] = 'L'
        elif h.hgb > 17.5: flags['hgb_flag'] = 'H'
    if h.wbc is not None:
        if h.wbc < 2.0:    flags['wbc_flag'] = 'LL'
        elif h.wbc < 4.0:  flags['wbc_flag'] = 'L'
        elif h.wbc > 30.0: flags['wbc_flag'] = 'HH'
        elif h.wbc > 11.0: flags['wbc_flag'] = 'H'
    if h.plt is not None:
        if h.plt < 20:     flags['plt_flag'] = 'LL'
        elif h.plt < 100:  flags['plt_flag'] = 'L'
        elif h.plt > 1000: flags['plt_flag'] = 'HH'
        elif h.plt > 450:  flags['plt_flag'] = 'H'
    critical = any(v in ('HH','LL') for v in flags.values())
    flags['is_critical'] = critical
    if critical:
        flags['overall_flag'] = 'HH' if any(v=='HH' for v in flags.values()) else 'LL'
    elif any(v in ('H','L') for v in flags.values()):
        flags['overall_flag'] = 'A'
    else:
        flags['overall_flag'] = 'N'
    return flags


@router.get('/dashboard', response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    today = date_t.today()
    return DashboardStats(
        cbc_pending=db.query(HemResult).filter(HemResult.status.in_(['PENDING','PROCESSING'])).count(),
        cbc_today=db.query(HemResult).filter(func.date(HemResult.created_at)==today).count(),
        critical_today=db.query(HemResult).filter(and_(HemResult.is_critical==True, func.date(HemResult.created_at)==today)).count(),
        malaria_positive_today=db.query(MalariaResult).filter(and_(MalariaResult.rdt_result=='POS', func.date(MalariaResult.created_at)==today)).count(),
        anaemia_cases=db.query(HemResult).filter(HemResult.hgb_flag.in_(['L','LL'])).count(),
    )


@router.get('/cbc', response_model=list[HemOut])
def list_cbc(
    status: Optional[str]=None, flag: Optional[str]=None,
    date: Optional[str]=None, skip: int=0, limit: int=50,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    q = db.query(HemResult)
    if status: q = q.filter(HemResult.status==status)
    if flag:   q = q.filter(HemResult.overall_flag==flag)
    if date:   q = q.filter(func.date(HemResult.created_at)==date)
    return q.order_by(desc(HemResult.created_at)).offset(skip).limit(limit).all()


@router.post('/cbc', response_model=HemOut, status_code=201)
def create_cbc(body: HemCreate, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    flags = _auto_flags(body)
    r = HemResult(
        hem_id=_gen_id('HEM', db, HemResult, 'hem_id'),
        entered_by_id=user.id,
        **body.model_dump(),
        **flags,
    )
    db.add(r); db.commit(); db.refresh(r)
    return r


@router.post('/cbc/{rid}/validate', response_model=HemOut)
def validate_cbc(rid: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    r = db.query(HemResult).filter(HemResult.id==rid).first()
    if not r: raise HTTPException(404, 'Not found')
    r.is_validated=True; r.validated_by_id=user.id
    r.validated_at=datetime.now(timezone.utc); r.status='VALIDATED'
    db.commit(); db.refresh(r)
    return r


@router.get('/malaria', response_model=list[MalariaOut])
def list_malaria(
    result: Optional[str]=None, date: Optional[str]=None,
    skip: int=0, limit: int=50,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    q = db.query(MalariaResult)
    if result: q = q.filter(MalariaResult.rdt_result==result)
    if date:   q = q.filter(func.date(MalariaResult.created_at)==date)
    return q.order_by(desc(MalariaResult.created_at)).offset(skip).limit(limit).all()


@router.post('/malaria', response_model=MalariaOut, status_code=201)
def create_malaria(
    lab_request_id: int, patient_id: int,
    test_type: str = 'RDT',
    rdt_result: Optional[str] = None,
    species: Optional[str] = None,
    parasitemia_pct: Optional[float] = None,
    pid: Optional[str] = None, lid: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    critical = (rdt_result == 'POS') and (parasitemia_pct and parasitemia_pct > 5.0)
    r = MalariaResult(
        mal_id=_gen_id('MAL', db, MalariaResult, 'mal_id'),
        lab_request_id=lab_request_id, patient_id=patient_id,
        test_type=test_type, rdt_result=rdt_result,
        species=species, parasitemia_pct=parasitemia_pct,
        pid=pid, lid=lid, notes=notes,
        is_critical=critical, entered_by_id=user.id,
    )
    db.add(r); db.commit(); db.refresh(r)
    return r
