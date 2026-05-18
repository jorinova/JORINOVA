"""Dashboard router — real-time system-wide statistics."""
from datetime import date as date_t, timedelta
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.laboratory import LabRequest, LabResult
from models.patient import Patient

router = APIRouter(prefix='/dashboard', tags=['Dashboard'])


@router.get('/stats')
def system_stats(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    """Complete system stats for the main dashboard."""
    today = date_t.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    # Lab requests
    req_today = db.query(LabRequest).filter(func.date(LabRequest.request_date)==today).count()
    req_week  = db.query(LabRequest).filter(func.date(LabRequest.request_date)>=week_ago).count()
    pending   = db.query(LabRequest).filter(LabRequest.status.in_(['pending','received','processing'])).count()
    stat_today= db.query(LabRequest).filter(func.date(LabRequest.request_date)==today, LabRequest.emergency_level=='stat').count()
    validated_today = db.query(LabRequest).filter(func.date(LabRequest.request_date)==today, LabRequest.status=='validated').count()

    # Results
    results_today = db.query(LabResult).filter(func.date(LabResult.entered_at)==today).count()
    critical_today= db.query(LabResult).filter(func.date(LabResult.entered_at)==today, LabResult.flag.in_(['HH','LL'])).count()

    # Patients
    patients_total = db.query(Patient).filter(Patient.is_active==True).count()
    patients_today = db.query(Patient).filter(func.date(Patient.created_at)==today).count()

    return {
        'lab_requests': {
            'today': req_today,
            'week': req_week,
            'pending': pending,
            'stat_today': stat_today,
            'validated_today': validated_today,
        },
        'results': {
            'entered_today': results_today,
            'critical_today': critical_today,
        },
        'patients': {
            'total_active': patients_total,
            'registered_today': patients_today,
        },
        'system': {
            'status': 'operational',
            'current_date': str(today),
            'user_role': user.role,
        }
    }


@router.get('/tat-summary')
def tat_summary(date: Optional[str]=None, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    """TAT compliance summary for the shift bar."""
    target_date = date_t.fromisoformat(date) if date else date_t.today()
    # Simplified TAT analysis
    total = db.query(LabRequest).filter(func.date(LabRequest.request_date)==target_date).count()
    completed = db.query(LabRequest).filter(func.date(LabRequest.request_date)==target_date, LabRequest.status.in_(['validated','released'])).count()
    return {
        'date': str(target_date),
        'total_requests': total,
        'completed': completed,
        'pending': total - completed,
        'completion_rate': round((completed/total*100) if total else 0, 1),
    }


@router.get('/activity-feed')
def activity_feed(limit: int=20, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    """Recent lab activity for the dashboard feed."""
    from models.laboratory import LabRequest
    recent = db.query(LabRequest).order_by(LabRequest.request_date.desc()).limit(limit).all()
    return [
        {
            'id': r.id,
            'lab_id': r.lab_id,
            'pid': r.pid,
            'status': r.status,
            'emergency_level': r.emergency_level,
            'department': 'LAB',
            'timestamp': r.request_date.isoformat() if r.request_date else None,
        }
        for r in recent
    ]
