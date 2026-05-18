"""Epidemic Surveillance router — outbreak signals, disease tracking, AI alerts."""
from typing import Optional
from datetime import date as date_t, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.surveillance import SurveillanceSignal, DiseaseTracking

router = APIRouter(prefix='/surveillance', tags=['Surveillance'])


def _gen_sig_id(db):
    year = date_t.today().year
    n = db.query(SurveillanceSignal).filter(SurveillanceSignal.signal_id.like(f'SIG-{year}-%')).count()
    return f'SIG-{year}-{str(n+1).zfill(5)}'


@router.get('/dashboard')
def dashboard(db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    today = date_t.today()
    return {
        'active_signals': db.query(SurveillanceSignal).filter(SurveillanceSignal.resolved==False).count(),
        'emergency_alerts': db.query(SurveillanceSignal).filter(SurveillanceSignal.alert_level=='EMERGENCY', SurveillanceSignal.resolved==False).count(),
        'diseases_tracked': db.query(func.count(DiseaseTracking.disease.distinct())).scalar() or 0,
        'cases_today': db.query(func.sum(DiseaseTracking.new_cases)).filter(DiseaseTracking.track_date==today).scalar() or 0,
        'malaria_7d': db.query(func.sum(DiseaseTracking.new_cases)).filter(DiseaseTracking.disease.ilike('%malaria%'), DiseaseTracking.track_date>=(today-timedelta(days=7))).scalar() or 0,
        'tb_7d': db.query(func.sum(DiseaseTracking.new_cases)).filter(DiseaseTracking.disease.ilike('%tb%'), DiseaseTracking.track_date>=(today-timedelta(days=7))).scalar() or 0,
    }


@router.get('/signals')
def list_signals(
    alert_level: Optional[str]=None, disease: Optional[str]=None,
    resolved: Optional[bool]=None, skip: int=0, limit: int=50,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    q = db.query(SurveillanceSignal)
    if alert_level: q=q.filter(SurveillanceSignal.alert_level==alert_level)
    if disease:     q=q.filter(SurveillanceSignal.disease.ilike(f'%{disease}%'))
    if resolved is not None: q=q.filter(SurveillanceSignal.resolved==resolved)
    return q.order_by(desc(SurveillanceSignal.signal_date)).offset(skip).limit(limit).all()


@router.post('/signals', status_code=201)
def create_signal(
    department: str, alert_level: str, case_count_7d: int,
    baseline_rate: Optional[float]=None, disease: Optional[str]=None,
    test_code: Optional[str]=None, suspected_pathogen: Optional[str]=None,
    recommended_action: Optional[str]=None, ai_confidence: Optional[str]=None,
    district: Optional[str]=None, notes: Optional[str]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    pct = ((case_count_7d/baseline_rate-1)*100) if baseline_rate and baseline_rate>0 else None
    s = SurveillanceSignal(
        signal_id=_gen_sig_id(db), signal_date=date_t.today(),
        department=department, alert_level=alert_level,
        case_count_7d=case_count_7d, baseline_rate=baseline_rate,
        pct_increase=pct, disease=disease, test_code=test_code,
        suspected_pathogen=suspected_pathogen, recommended_action=recommended_action,
        ai_confidence=ai_confidence, district=district, notes=notes,
    )
    db.add(s); db.commit(); db.refresh(s)
    return s


@router.post('/signals/{sid}/resolve')
def resolve_signal(sid: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    from datetime import datetime, timezone
    s = db.query(SurveillanceSignal).filter(SurveillanceSignal.id==sid).first()
    if not s: raise HTTPException(404, 'Signal not found')
    s.resolved=True; s.resolved_at=datetime.now(timezone.utc)
    db.commit(); return {'status': 'resolved'}


@router.get('/disease-tracking')
def disease_tracking(
    disease: Optional[str]=None, days: int=30,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    since = date_t.today() - timedelta(days=days)
    q = db.query(DiseaseTracking).filter(DiseaseTracking.track_date>=since)
    if disease: q=q.filter(DiseaseTracking.disease.ilike(f'%{disease}%'))
    return q.order_by(DiseaseTracking.track_date.desc()).limit(500).all()


@router.post('/disease-tracking', status_code=201)
def record_cases(
    disease: str, department: str, new_cases: int,
    track_date: Optional[str]=None, district: Optional[str]=None,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    td = date_t.fromisoformat(track_date) if track_date else date_t.today()
    existing = db.query(DiseaseTracking).filter(DiseaseTracking.disease==disease, DiseaseTracking.track_date==td).first()
    if existing:
        existing.new_cases+=new_cases; existing.total_cases+=new_cases
        db.commit(); return existing
    total = db.query(func.sum(DiseaseTracking.new_cases)).filter(DiseaseTracking.disease==disease).scalar() or 0
    rec = DiseaseTracking(disease=disease, department=department, new_cases=new_cases,
                          total_cases=total+new_cases, track_date=td, district=district)
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


@router.get('/amr-report')
def amr_report(db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    """Antimicrobial resistance summary from microbiology."""
    from models.microbiology import MicroCulture
    total = db.query(MicroCulture).count()
    mrsa  = db.query(MicroCulture).filter(MicroCulture.is_mrsa==True).count()
    esbl  = db.query(MicroCulture).filter(MicroCulture.is_esbl==True).count()
    cro   = db.query(MicroCulture).filter(MicroCulture.is_cro==True).count()
    return {
        'total_cultures': total,
        'mrsa': mrsa, 'esbl': esbl, 'cro': cro,
        'mrsa_rate': round((mrsa/total*100) if total else 0, 1),
        'esbl_rate': round((esbl/total*100) if total else 0, 1),
    }
