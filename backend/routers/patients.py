"""Patients router — PID/LID dual identity, registration, search."""
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.patient import Patient
from models.core_config import Hospital

router = APIRouter(prefix='/patients', tags=['Patients'])


class PatientOut(BaseModel):
    id:            int
    pid:           str
    unique_lab_id: Optional[str]
    family_name:   str
    other_names:   Optional[str]
    date_of_birth: Optional[date]
    gender:        Optional[str]
    blood_group:   Optional[str]
    phone:         Optional[str]
    email:         Optional[str]
    national_id:   Optional[str]
    insurance_no:  Optional[str]
    insurance_provider: Optional[str]
    full_name:     str
    age:           Optional[int]
    is_active:     bool
    model_config = {'from_attributes': True}


class PatientCreate(BaseModel):
    family_name:   str
    other_names:   Optional[str] = None
    date_of_birth: Optional[date] = None
    gender:        Optional[str]  = None
    blood_group:   Optional[str]  = None
    phone:         Optional[str]  = None
    email:         Optional[str]  = None
    address:       Optional[str]  = None
    national_id:   Optional[str]  = None
    insurance_no:  Optional[str]  = None
    insurance_provider: Optional[str] = None


def _gen_pid(db: Session) -> str:
    from datetime import date as d
    year  = d.today().year
    count = db.query(Patient).filter(
        Patient.pid.like(f'PID-{year}-%')
    ).count()
    return f'PID-{year}-{str(count+1).zfill(6)}'


def _gen_lid(db: Session) -> str:
    count = db.query(Patient).filter(Patient.unique_lab_id != None).count()
    return f'RW-{str(count+1).zfill(7)}'


@router.get('/', response_model=list[PatientOut])
def list_patients(
    search: Optional[str] = Query(None),
    dob:    Optional[date] = Query(None),
    skip:   int = 0, limit: int = 50,
    db:     Session = Depends(get_db),
    _user:  User    = Depends(get_current_user),
):
    q = db.query(Patient).filter(Patient.is_active == True)
    if search:
        like = f'%{search}%'
        q = q.filter(or_(
            Patient.family_name.ilike(like),
            Patient.other_names.ilike(like),
            Patient.pid.ilike(like),
            Patient.unique_lab_id.ilike(like),
            Patient.phone.ilike(like),
            Patient.national_id.ilike(like),
        ))
    if dob:
        q = q.filter(Patient.date_of_birth == dob)
    return q.offset(skip).limit(limit).all()


@router.get('/{patient_id}', response_model=PatientOut)
def get_patient(
    patient_id: int, db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, 'Patient not found')
    return p


@router.get('/by-pid/{pid}', response_model=PatientOut)
def get_by_pid(pid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    p = db.query(Patient).filter(Patient.pid == pid).first()
    if not p:
        raise HTTPException(404, 'Patient not found')
    return p


@router.get('/by-lid/{lid}', response_model=PatientOut)
def get_by_lid(lid: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    p = db.query(Patient).filter(Patient.unique_lab_id == lid).first()
    if not p:
        raise HTTPException(404, 'Patient not found')
    return p


@router.post('/check-duplicate')
def check_duplicate(
    body: PatientCreate,
    db:   Session = Depends(get_db),
    _:    User    = Depends(get_current_user),
):
    """Duplicate detection before registration."""
    matches = []
    if body.national_id:
        p = db.query(Patient).filter(Patient.national_id == body.national_id).first()
        if p:
            matches.append({'patient': PatientOut.model_validate(p), 'match_field': 'national_id'})
    if body.phone:
        for p in db.query(Patient).filter(Patient.phone == body.phone).all():
            if not any(m['patient'].id == p.id for m in matches):
                matches.append({'patient': PatientOut.model_validate(p), 'match_field': 'phone'})
    if body.family_name and body.date_of_birth:
        for p in db.query(Patient).filter(
            Patient.family_name.ilike(body.family_name),
            Patient.date_of_birth == body.date_of_birth,
        ).all():
            if not any(m['patient'].id == p.id for m in matches):
                matches.append({'patient': PatientOut.model_validate(p), 'match_field': 'name+dob'})
    return {'duplicates_found': len(matches), 'matches': matches}


@router.post('/', response_model=PatientOut, status_code=201)
def create_patient(
    body:  PatientCreate,
    db:    Session = Depends(get_db),
    _user: User    = Depends(get_current_user),
):
    pid = _gen_pid(db)
    lid = _gen_lid(db)
    p   = Patient(
        pid=pid, unique_lab_id=lid,
        family_name=body.family_name, other_names=body.other_names,
        date_of_birth=body.date_of_birth, gender=body.gender,
        blood_group=body.blood_group, phone=body.phone,
        email=body.email, address=body.address,
        national_id=body.national_id, insurance_no=body.insurance_no,
        insurance_provider=body.insurance_provider,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put('/{patient_id}', response_model=PatientOut)
def update_patient(
    patient_id: int, body: PatientCreate,
    db:    Session = Depends(get_db),
    _user: User    = Depends(get_current_user),
):
    p = db.query(Patient).filter(Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, 'Patient not found')
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.get('/stats/summary')
def patient_stats(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from datetime import date as d
    return {
        'total':      db.query(Patient).count(),
        'active':     db.query(Patient).filter(Patient.is_active == True).count(),
        'with_lid':   db.query(Patient).filter(Patient.unique_lab_id != None).count(),
        'today':      db.query(Patient).filter(
            Patient.created_at >= d.today().strftime('%Y-%m-%d')
        ).count(),
    }
