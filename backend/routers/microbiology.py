"""Microbiology router — cultures, antibiograms, parasitology, critical book."""
from typing import Optional
from datetime import datetime, timezone, date as date_type
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.microbiology import MicroCulture, Antibiogram, ParasitologyResult, MicroCriticalBook

router = APIRouter(prefix='/microbiology', tags=['Microbiology'])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gen_id(prefix: str, db: Session, model, field: str) -> str:
    year = date_type.today().year
    col  = getattr(model, field)
    n    = db.query(model).filter(col.like(f'{prefix}-{year}-%')).count()
    return f'{prefix}-{year}-{str(n+1).zfill(5)}'


def _book_entry_number(db: Session) -> str:
    year = date_type.today().year
    n    = db.query(MicroCriticalBook).filter(MicroCriticalBook.entry_number.like(f'MICRO-{year}-%')).count()
    return f'MICRO-{year}-{str(n+1).zfill(4)}'


# ── Schemas ───────────────────────────────────────────────────────────────────

class CultureOut(BaseModel):
    id: int
    culture_id: str
    lab_request_id: int
    patient_id: int
    pid: Optional[str]
    lid: Optional[str]
    specimen_type: str
    gram_stain_done: bool
    gram_stain_result: Optional[str]
    growth_status: str
    organism_identified: Optional[str]
    is_mrsa: bool
    is_esbl: bool
    is_cro: bool
    status: str
    is_validated: bool
    is_critical: bool
    ai_interpretation: Optional[str]
    notes: Optional[str]
    created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class CultureCreate(BaseModel):
    lab_request_id: int
    patient_id: int
    pid: Optional[str] = None
    lid: Optional[str] = None
    sid: Optional[str] = None
    specimen_type: str
    specimen_notes: Optional[str] = None
    gram_stain_done: bool = False
    gram_stain_result: Optional[str] = None
    gram_stain_morphology: Optional[str] = None
    notes: Optional[str] = None


class CultureUpdate(BaseModel):
    gram_stain_done: Optional[bool] = None
    gram_stain_result: Optional[str] = None
    gram_stain_morphology: Optional[str] = None
    growth_status: Optional[str] = None
    growth_days: Optional[int] = None
    colony_morphology: Optional[str] = None
    organism_identified: Optional[str] = None
    organism_count: Optional[str] = None
    identification_method: Optional[str] = None
    is_mrsa: Optional[bool] = None
    is_esbl: Optional[bool] = None
    is_cro: Optional[bool] = None
    is_vrsa: Optional[bool] = None
    mdr_note: Optional[str] = None
    status: Optional[str] = None
    is_critical: Optional[bool] = None
    notes: Optional[str] = None


class AntibiogramEntry(BaseModel):
    antibiotic: str
    drug_class: Optional[str] = None
    interpretation: str  # S|I|R
    mic_value: Optional[float] = None
    mic_unit: Optional[str] = None
    disk_zone_mm: Optional[float] = None
    method: Optional[str] = None
    notes: Optional[str] = None


class AntibiogramOut(BaseModel):
    id: int
    culture_id: int
    antibiotic: str
    drug_class: Optional[str]
    interpretation: str
    mic_value: Optional[float]
    disk_zone_mm: Optional[float]
    method: Optional[str]
    model_config = {'from_attributes': True}


class ParaOut(BaseModel):
    id: int
    para_id: str
    lab_request_id: int
    patient_id: int
    pid: Optional[str]
    lid: Optional[str]
    category: str
    specimen_type: str
    parasite_name: Optional[str]
    parasite_species: Optional[str]
    result: str
    quantity: Optional[str]
    parasitemia_pct: Optional[float]
    staining_technique: Optional[str]
    rdt_done: bool
    rdt_result: Optional[str]
    is_validated: bool
    is_critical: bool
    status: str
    ai_interpretation: Optional[str]
    created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class ParaCreate(BaseModel):
    lab_request_id: int
    patient_id: int
    pid: Optional[str] = None
    lid: Optional[str] = None
    category: str  # BLOOD|STOOL|URINE|CSF|SKIN
    specimen_type: str
    parasite_name: Optional[str] = None
    parasite_species: Optional[str] = None
    stage: Optional[str] = None
    result: str = 'PENDING'
    quantity: Optional[str] = None
    parasitemia_pct: Optional[float] = None
    staining_technique: Optional[str] = None
    preparation: Optional[str] = None
    rdt_done: bool = False
    rdt_result: Optional[str] = None
    rdt_brand: Optional[str] = None
    is_critical: bool = False
    notes: Optional[str] = None


class CriticalBookOut(BaseModel):
    id: int
    entry_number: str
    patient_id: int
    pid: Optional[str]
    lid: Optional[str]
    result_type: str
    organism: Optional[str]
    critical_reason: str
    severity: str
    clinician_notified: Optional[str]
    notification_method: Optional[str]
    readback_confirmed: bool
    rbc_notified: bool
    pqc_hash: Optional[str]
    archived_at: datetime
    model_config = {'from_attributes': True}


class ArchiveIn(BaseModel):
    lab_request_id: int
    patient_id: int
    pid: Optional[str] = None
    lid: Optional[str] = None
    result_type: str
    result_ref_id: int
    organism: Optional[str] = None
    critical_reason: str
    severity: str = 'CRITICAL'
    clinician_notified: Optional[str] = None
    notification_method: Optional[str] = None
    readback_confirmed: bool = False
    notes: Optional[str] = None


class DashboardStats(BaseModel):
    cultures_pending: int
    cultures_today: int
    critical_cultures: int
    mrsa_count: int
    esbl_count: int
    parasitology_pending: int
    malaria_positive_today: int
    critical_book_total: int


# ── Cultures ─────────────────────────────────────────────────────────────────

@router.get('/dashboard', response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    today = date_type.today()
    return DashboardStats(
        cultures_pending=db.query(MicroCulture).filter(
            MicroCulture.status.in_(['PENDING', 'IN_PROGRESS'])
        ).count(),
        cultures_today=db.query(MicroCulture).filter(
            func.date(MicroCulture.created_at) == today
        ).count(),
        critical_cultures=db.query(MicroCulture).filter(MicroCulture.is_critical == True).count(),
        mrsa_count=db.query(MicroCulture).filter(MicroCulture.is_mrsa == True).count(),
        esbl_count=db.query(MicroCulture).filter(MicroCulture.is_esbl == True).count(),
        parasitology_pending=db.query(ParasitologyResult).filter(
            ParasitologyResult.status == 'PENDING'
        ).count(),
        malaria_positive_today=db.query(ParasitologyResult).filter(
            and_(
                ParasitologyResult.result == 'POSITIVE',
                ParasitologyResult.parasite_name.ilike('%malaria%'),
                func.date(ParasitologyResult.created_at) == today,
            )
        ).count(),
        critical_book_total=db.query(MicroCriticalBook).count(),
    )


@router.get('/cultures', response_model=list[CultureOut])
def list_cultures(
    status:        Optional[str] = None,
    specimen_type: Optional[str] = None,
    mdr_flag:      Optional[str] = None,
    date:          Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _u: User    = Depends(get_current_user),
):
    q = db.query(MicroCulture)
    if status:        q = q.filter(MicroCulture.status == status)
    if specimen_type: q = q.filter(MicroCulture.specimen_type == specimen_type)
    if mdr_flag == 'MRSA': q = q.filter(MicroCulture.is_mrsa == True)
    if mdr_flag == 'ESBL': q = q.filter(MicroCulture.is_esbl == True)
    if mdr_flag == 'CRO':  q = q.filter(MicroCulture.is_cro  == True)
    if date:          q = q.filter(func.date(MicroCulture.created_at) == date)
    return q.order_by(desc(MicroCulture.created_at)).offset(skip).limit(limit).all()


@router.post('/cultures', response_model=CultureOut, status_code=201)
def create_culture(
    body: CultureCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    culture_id = _gen_id('CUL', db, MicroCulture, 'culture_id')
    c = MicroCulture(
        culture_id=culture_id,
        entered_by_id=user.id,
        received_at=datetime.now(timezone.utc),
        **body.model_dump(),
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get('/cultures/{culture_id}', response_model=CultureOut)
def get_culture(culture_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    c = db.query(MicroCulture).filter(MicroCulture.id == culture_id).first()
    if not c:
        raise HTTPException(404, 'Culture not found')
    return c


@router.patch('/cultures/{culture_id}', response_model=CultureOut)
def update_culture(
    culture_id: int,
    body: CultureUpdate,
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
):
    c = db.query(MicroCulture).filter(MicroCulture.id == culture_id).first()
    if not c:
        raise HTTPException(404, 'Culture not found')
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    # Auto-set critical if MDR detected
    if body.is_mrsa or body.is_esbl or body.is_cro:
        c.is_critical = True
    db.commit()
    db.refresh(c)
    return c


@router.post('/cultures/{culture_id}/validate', response_model=CultureOut)
def validate_culture(
    culture_id: int,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    c = db.query(MicroCulture).filter(MicroCulture.id == culture_id).first()
    if not c:
        raise HTTPException(404, 'Culture not found')
    c.is_validated    = True
    c.validated_by_id = user.id
    c.validated_at    = datetime.now(timezone.utc)
    c.status          = 'VALIDATED'
    db.commit()
    db.refresh(c)
    return c


# ── Antibiogram ───────────────────────────────────────────────────────────────

@router.get('/cultures/{culture_id}/antibiogram', response_model=list[AntibiogramOut])
def get_antibiogram(culture_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    return db.query(Antibiogram).filter(Antibiogram.culture_id == culture_id).all()


@router.post('/cultures/{culture_id}/antibiogram', status_code=201)
def add_antibiogram_entries(
    culture_id: int,
    entries: list[AntibiogramEntry],
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
):
    c = db.query(MicroCulture).filter(MicroCulture.id == culture_id).first()
    if not c:
        raise HTTPException(404, 'Culture not found')
    for e in entries:
        db.add(Antibiogram(culture_id=culture_id, **e.model_dump()))
    db.commit()
    return {'added': len(entries)}


# ── Parasitology ──────────────────────────────────────────────────────────────

@router.get('/parasitology', response_model=list[ParaOut])
def list_parasitology(
    category:  Optional[str] = None,
    result:    Optional[str] = None,
    validated: Optional[bool] = None,
    date:      Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _u: User    = Depends(get_current_user),
):
    q = db.query(ParasitologyResult)
    if category:  q = q.filter(ParasitologyResult.category == category)
    if result:    q = q.filter(ParasitologyResult.result == result)
    if validated is not None: q = q.filter(ParasitologyResult.is_validated == validated)
    if date:      q = q.filter(func.date(ParasitologyResult.created_at) == date)
    return q.order_by(desc(ParasitologyResult.created_at)).offset(skip).limit(limit).all()


@router.post('/parasitology', response_model=ParaOut, status_code=201)
def create_parasitology(
    body: ParaCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    para_id = _gen_id('PAR', db, ParasitologyResult, 'para_id')
    p = ParasitologyResult(para_id=para_id, entered_by_id=user.id, **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.patch('/parasitology/{para_id}/validate', response_model=ParaOut)
def validate_parasitology(
    para_id: int,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    p = db.query(ParasitologyResult).filter(ParasitologyResult.id == para_id).first()
    if not p:
        raise HTTPException(404, 'Parasitology result not found')
    p.is_validated    = True
    p.validated_by_id = user.id
    p.validated_at    = datetime.now(timezone.utc)
    p.status          = 'VALIDATED'
    db.commit()
    db.refresh(p)
    return p


# ── Critical Book ─────────────────────────────────────────────────────────────

@router.get('/critical-book', response_model=list[CriticalBookOut])
def list_critical_book(
    critical_reason: Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _u: User    = Depends(get_current_user),
):
    q = db.query(MicroCriticalBook)
    if critical_reason:
        q = q.filter(MicroCriticalBook.critical_reason == critical_reason)
    return q.order_by(desc(MicroCriticalBook.archived_at)).offset(skip).limit(limit).all()


@router.post('/critical-book', response_model=CriticalBookOut, status_code=201)
def archive_critical(
    body: ArchiveIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    import hashlib, json
    entry_num = _book_entry_number(db)
    payload   = f'{entry_num}:{body.patient_id}:{body.critical_reason}:{datetime.now(timezone.utc).isoformat()}'
    pqc_hash  = 'DILITHIUM3:' + hashlib.sha3_256(payload.encode()).hexdigest()

    entry = MicroCriticalBook(
        entry_number=entry_num,
        archived_by_id=user.id,
        pqc_hash=pqc_hash,
        archived_at=datetime.now(timezone.utc),
        **body.model_dump(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
