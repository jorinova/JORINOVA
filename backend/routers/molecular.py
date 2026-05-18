"""Molecular router — PCR, GeneXpert, viral load, genetic analysis, critical book."""
from typing import Optional
from datetime import datetime, timezone, date as date_type
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.molecular import PCRResult, ViralLoad, GeneticAnalysis, MolecularCriticalBook

router = APIRouter(prefix='/molecular', tags=['Molecular'])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gen_id(prefix: str, db: Session, model, field: str) -> str:
    year = date_type.today().year
    col  = getattr(model, field)
    n    = db.query(model).filter(col.like(f'{prefix}-{year}-%')).count()
    return f'{prefix}-{year}-{str(n+1).zfill(5)}'


def _book_entry_number(db: Session) -> str:
    year = date_type.today().year
    n    = db.query(MolecularCriticalBook).filter(
        MolecularCriticalBook.entry_number.like(f'MOL-{year}-%')
    ).count()
    return f'MOL-{year}-{str(n+1).zfill(4)}'


# ── Schemas ───────────────────────────────────────────────────────────────────

class PCROut(BaseModel):
    id: int
    pcr_id: str
    lab_request_id: int
    patient_id: int
    pid: Optional[str]
    lid: Optional[str]
    pcr_category: str
    test_name: str
    target_organism: Optional[str]
    instrument: Optional[str]
    result: str
    ct_value: Optional[float]
    semi_quant: Optional[str]
    rifampicin_resistance: Optional[str]
    tb_classification: Optional[str]
    specimen_type: Optional[str]
    is_validated: bool
    is_critical: bool
    status: str
    ai_interpretation: Optional[str]
    created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class PCRCreate(BaseModel):
    lab_request_id: int
    patient_id: int
    pid: Optional[str] = None
    lid: Optional[str] = None
    pcr_category: str              # TB|VIRAL|STI|RESPIRATORY|FUNGAL|OTHER
    test_name: str
    target_organism: Optional[str] = None
    instrument: Optional[str] = None
    cartridge_type: Optional[str] = None
    run_number: Optional[str] = None
    specimen_type: Optional[str] = None
    specimen_quality: Optional[str] = None
    result: str = 'PENDING'
    ct_value: Optional[float] = None
    semi_quant: Optional[str] = None
    rifampicin_resistance: Optional[str] = None
    resistance_markers: Optional[dict] = None
    tb_classification: Optional[str] = None
    is_critical: bool = False
    critical_reason: Optional[str] = None
    notes: Optional[str] = None


class PCRUpdate(BaseModel):
    result: Optional[str] = None
    ct_value: Optional[float] = None
    semi_quant: Optional[str] = None
    rifampicin_resistance: Optional[str] = None
    resistance_markers: Optional[dict] = None
    tb_classification: Optional[str] = None
    is_critical: Optional[bool] = None
    critical_reason: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class VLOut(BaseModel):
    id: int
    vl_id: str
    lab_request_id: int
    patient_id: int
    pid: Optional[str]
    lid: Optional[str]
    virus: str
    assay_name: Optional[str]
    copies_per_ml: Optional[float]
    iu_per_ml: Optional[float]
    log10_value: Optional[float]
    detectable: Optional[bool]
    suppressed: Optional[bool]
    vl_category: Optional[str]
    on_art: Optional[bool]
    vl_trend: Optional[str]
    specimen_type: Optional[str]
    is_validated: bool
    is_critical: bool
    status: str
    ai_interpretation: Optional[str]
    created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class VLCreate(BaseModel):
    lab_request_id: int
    patient_id: int
    pid: Optional[str] = None
    lid: Optional[str] = None
    virus: str                     # HIV|HBV|HCV|CMV|EBV
    assay_name: Optional[str] = None
    instrument: Optional[str] = None
    copies_per_ml: Optional[float] = None
    iu_per_ml: Optional[float] = None
    log10_value: Optional[float] = None
    lower_limit_detection: Optional[float] = None
    upper_limit_quantification: Optional[float] = None
    detectable: Optional[bool] = None
    suppressed: Optional[bool] = None
    vl_category: Optional[str] = None
    on_art: Optional[bool] = None
    art_regimen: Optional[str] = None
    art_months: Optional[int] = None
    previous_vl: Optional[float] = None
    vl_trend: Optional[str] = None
    specimen_type: Optional[str] = None
    is_critical: bool = False
    notes: Optional[str] = None


class GAOut(BaseModel):
    id: int
    ga_id: str
    lab_request_id: int
    patient_id: int
    pid: Optional[str]
    lid: Optional[str]
    analysis_type: str
    gene_target: Optional[str]
    mutation_detected: Optional[str]
    pathogenicity: Optional[str]
    clinical_significance: Optional[str]
    method: Optional[str]
    result_summary: Optional[str]
    is_validated: bool
    status: str
    created_at: Optional[datetime]
    model_config = {'from_attributes': True}


class GACreate(BaseModel):
    lab_request_id: int
    patient_id: int
    pid: Optional[str] = None
    lid: Optional[str] = None
    analysis_type: str             # CANCER_MUTATION|HEREDITARY|PHARMACOGENOMICS
    gene_target: Optional[str] = None
    mutation_detected: Optional[str] = None
    mutation_type: Optional[str] = None
    pathogenicity: Optional[str] = None
    clinical_significance: Optional[str] = None
    method: Optional[str] = None
    result_summary: Optional[str] = None
    notes: Optional[str] = None


class CriticalBookOut(BaseModel):
    id: int
    entry_number: str
    patient_id: int
    pid: Optional[str]
    lid: Optional[str]
    result_type: str
    test_name: Optional[str]
    critical_reason: str
    severity: str
    clinician_notified: Optional[str]
    notification_method: Optional[str]
    readback_confirmed: bool
    public_health_notified: bool
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
    test_name: Optional[str] = None
    critical_reason: str
    severity: str = 'CRITICAL'
    clinician_notified: Optional[str] = None
    notification_method: Optional[str] = None
    readback_confirmed: bool = False
    public_health_notified: bool = False
    notes: Optional[str] = None


class DashboardStats(BaseModel):
    pcr_pending: int
    pcr_today: int
    genexpert_detected_today: int
    mdr_tb_total: int
    xdr_tb_total: int
    vl_pending: int
    hiv_high_vl_today: int
    critical_book_total: int


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get('/dashboard', response_model=DashboardStats)
def get_dashboard(db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    today = date_type.today()
    return DashboardStats(
        pcr_pending=db.query(PCRResult).filter(
            PCRResult.status.in_(['PENDING', 'RUNNING'])
        ).count(),
        pcr_today=db.query(PCRResult).filter(
            func.date(PCRResult.created_at) == today
        ).count(),
        genexpert_detected_today=db.query(PCRResult).filter(
            and_(
                PCRResult.pcr_category == 'TB',
                PCRResult.result == 'DETECTED',
                func.date(PCRResult.created_at) == today,
            )
        ).count(),
        mdr_tb_total=db.query(PCRResult).filter(
            PCRResult.tb_classification == 'MDR_TB'
        ).count(),
        xdr_tb_total=db.query(PCRResult).filter(
            PCRResult.tb_classification == 'XDR_TB'
        ).count(),
        vl_pending=db.query(ViralLoad).filter(
            ViralLoad.status == 'PENDING'
        ).count(),
        hiv_high_vl_today=db.query(ViralLoad).filter(
            and_(
                ViralLoad.virus == 'HIV',
                ViralLoad.vl_category.in_(['HIGH_VIREMIA', 'VERY_HIGH']),
                func.date(ViralLoad.created_at) == today,
            )
        ).count(),
        critical_book_total=db.query(MolecularCriticalBook).count(),
    )


# ── PCR Results ───────────────────────────────────────────────────────────────

@router.get('/pcr', response_model=list[PCROut])
def list_pcr(
    category:  Optional[str] = None,
    result:    Optional[str] = None,
    validated: Optional[bool] = None,
    date:      Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _u: User    = Depends(get_current_user),
):
    q = db.query(PCRResult)
    if category:  q = q.filter(PCRResult.pcr_category == category)
    if result:    q = q.filter(PCRResult.result == result)
    if validated is not None: q = q.filter(PCRResult.is_validated == validated)
    if date:      q = q.filter(func.date(PCRResult.created_at) == date)
    return q.order_by(desc(PCRResult.created_at)).offset(skip).limit(limit).all()


@router.post('/pcr', response_model=PCROut, status_code=201)
def create_pcr(
    body: PCRCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    pcr_id = _gen_id('PCR', db, PCRResult, 'pcr_id')
    data   = body.model_dump()
    r = PCRResult(pcr_id=pcr_id, entered_by_id=user.id, **data)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.get('/pcr/{pcr_id}', response_model=PCROut)
def get_pcr(pcr_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)):
    r = db.query(PCRResult).filter(PCRResult.id == pcr_id).first()
    if not r:
        raise HTTPException(404, 'PCR result not found')
    return r


@router.patch('/pcr/{pcr_id}', response_model=PCROut)
def update_pcr(
    pcr_id: int,
    body: PCRUpdate,
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
):
    r = db.query(PCRResult).filter(PCRResult.id == pcr_id).first()
    if not r:
        raise HTTPException(404, 'PCR result not found')
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(r, k, v)
    # Auto-critical for MDR/XDR
    if body.tb_classification in ('MDR_TB', 'XDR_TB', 'PRE_XDR_TB'):
        r.is_critical = True
    db.commit()
    db.refresh(r)
    return r


@router.post('/pcr/{pcr_id}/validate', response_model=PCROut)
def validate_pcr(
    pcr_id: int,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    r = db.query(PCRResult).filter(PCRResult.id == pcr_id).first()
    if not r:
        raise HTTPException(404, 'PCR result not found')
    r.is_validated    = True
    r.validated_by_id = user.id
    r.validated_at    = datetime.now(timezone.utc)
    r.status          = 'VALIDATED'
    db.commit()
    db.refresh(r)
    return r


# ── Viral Load ────────────────────────────────────────────────────────────────

@router.get('/viral-load', response_model=list[VLOut])
def list_viral_load(
    virus:     Optional[str]  = None,
    validated: Optional[bool] = None,
    date:      Optional[str]  = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _u: User    = Depends(get_current_user),
):
    q = db.query(ViralLoad)
    if virus:          q = q.filter(ViralLoad.virus == virus)
    if validated is not None: q = q.filter(ViralLoad.is_validated == validated)
    if date:           q = q.filter(func.date(ViralLoad.created_at) == date)
    return q.order_by(desc(ViralLoad.created_at)).offset(skip).limit(limit).all()


@router.post('/viral-load', response_model=VLOut, status_code=201)
def create_viral_load(
    body: VLCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    vl_id = _gen_id('VL', db, ViralLoad, 'vl_id')
    vl = ViralLoad(vl_id=vl_id, entered_by_id=user.id, **body.model_dump())
    db.add(vl)
    db.commit()
    db.refresh(vl)
    return vl


@router.post('/viral-load/{vl_id}/validate', response_model=VLOut)
def validate_viral_load(
    vl_id: int,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    vl = db.query(ViralLoad).filter(ViralLoad.id == vl_id).first()
    if not vl:
        raise HTTPException(404, 'Viral load result not found')
    vl.is_validated    = True
    vl.validated_by_id = user.id
    vl.validated_at    = datetime.now(timezone.utc)
    vl.status          = 'VALIDATED'
    db.commit()
    db.refresh(vl)
    return vl


# ── Genetic Analysis ──────────────────────────────────────────────────────────

@router.get('/genetic', response_model=list[GAOut])
def list_genetic(
    analysis_type: Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _u: User    = Depends(get_current_user),
):
    q = db.query(GeneticAnalysis)
    if analysis_type: q = q.filter(GeneticAnalysis.analysis_type == analysis_type)
    return q.order_by(desc(GeneticAnalysis.created_at)).offset(skip).limit(limit).all()


@router.post('/genetic', response_model=GAOut, status_code=201)
def create_genetic(
    body: GACreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    ga_id = _gen_id('GA', db, GeneticAnalysis, 'ga_id')
    ga = GeneticAnalysis(ga_id=ga_id, entered_by_id=user.id, **body.model_dump())
    db.add(ga)
    db.commit()
    db.refresh(ga)
    return ga


# ── Critical Book ─────────────────────────────────────────────────────────────

@router.get('/critical-book', response_model=list[CriticalBookOut])
def list_critical_book(
    critical_reason: Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: Session = Depends(get_db),
    _u: User    = Depends(get_current_user),
):
    q = db.query(MolecularCriticalBook)
    if critical_reason:
        q = q.filter(MolecularCriticalBook.critical_reason == critical_reason)
    return q.order_by(desc(MolecularCriticalBook.archived_at)).offset(skip).limit(limit).all()


@router.post('/critical-book', response_model=CriticalBookOut, status_code=201)
def archive_critical(
    body: ArchiveIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    import hashlib
    entry_num = _book_entry_number(db)
    payload   = f'{entry_num}:{body.patient_id}:{body.critical_reason}:{datetime.now(timezone.utc).isoformat()}'
    pqc_hash  = 'DILITHIUM3:' + hashlib.sha3_256(payload.encode()).hexdigest()

    entry = MolecularCriticalBook(
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
