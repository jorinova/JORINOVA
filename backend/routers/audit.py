"""Audit Trail router — immutable system-wide activity log."""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.audit import AuditLog

router = APIRouter(prefix='/audit', tags=['Audit'])


def log_action(db: Session, entity_type: str, action: str,
               entity_id: Optional[str]=None, user: Optional[User]=None,
               patient_pid: Optional[str]=None, patient_lid: Optional[str]=None,
               sample_sid: Optional[str]=None, source: str='MANUAL',
               department: Optional[str]=None, metadata: Optional[dict]=None):
    """Write an audit log entry. Call this from any router."""
    import json
    entry = AuditLog(
        entity_type=entity_type, entity_id=entity_id, action=action,
        performed_by_id=user.id if user else None,
        performed_by=f'{user.first_name} {user.last_name}'.strip() if user else None,
        user_role=user.role if user else None,
        source=source, department=department,
        patient_pid=patient_pid, patient_lid=patient_lid,
        sample_sid=sample_sid,
        metadata_json=json.dumps(metadata) if metadata else None,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(entry)
    # Intentionally no commit here — let the calling transaction commit


@router.get('/logs')
def list_logs(
    entity_type: Optional[str]=None, action: Optional[str]=None,
    user_id: Optional[int]=None, patient_pid: Optional[str]=None,
    date_from: Optional[str]=None, date_to: Optional[str]=None,
    skip: int=0, limit: int=100,
    db: Session=Depends(get_db), current_user: User=Depends(get_current_user),
):
    if current_user.role not in ('super_admin','it_admin','security_officer','lab_manager'):
        return []
    q = db.query(AuditLog)
    if entity_type: q=q.filter(AuditLog.entity_type==entity_type)
    if action:      q=q.filter(AuditLog.action==action)
    if user_id:     q=q.filter(AuditLog.performed_by_id==user_id)
    if patient_pid: q=q.filter(AuditLog.patient_pid==patient_pid)
    if date_from:   q=q.filter(AuditLog.timestamp>=date_from)
    if date_to:     q=q.filter(AuditLog.timestamp<=date_to)
    return q.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()


@router.get('/logs/patient/{pid}')
def patient_audit(pid: str, skip: int=0, limit: int=50,
                  db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    return db.query(AuditLog).filter(AuditLog.patient_pid==pid).order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit).all()


@router.get('/logs/stats')
def audit_stats(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ('super_admin','it_admin','security_officer'): return {}
    from datetime import date
    today = date.today()
    return {
        'total_logs': db.query(AuditLog).count(),
        'today': db.query(AuditLog).filter(AuditLog.timestamp>=str(today)).count(),
        'by_entity': {
            'PATIENT': db.query(AuditLog).filter(AuditLog.entity_type=='PATIENT').count(),
            'LAB': db.query(AuditLog).filter(AuditLog.entity_type=='LAB').count(),
            'RESULT': db.query(AuditLog).filter(AuditLog.entity_type=='RESULT').count(),
            'SECURITY': db.query(AuditLog).filter(AuditLog.entity_type=='SECURITY').count(),
        }
    }
