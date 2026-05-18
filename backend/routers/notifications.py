"""Notifications router — in-app alerts, SMS queue, critical value notifications."""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.notifications import Notification, SMSQueue

router = APIRouter(prefix='/notifications', tags=['Notifications'])


class NotifOut(BaseModel):
    id: int; notif_type: str; title: str; body: str; priority: str
    entity_type: Optional[str]; entity_id: Optional[int]
    patient_pid: Optional[str]; action_url: Optional[str]
    is_read: bool; acknowledged: bool; created_at: Optional[datetime]
    model_config = {'from_attributes': True}


@router.get('/my', response_model=list[NotifOut])
def my_notifications(
    unread_only: bool=False, priority: Optional[str]=None,
    skip: int=0, limit: int=50,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    q = db.query(Notification).filter(Notification.recipient_id==user.id)
    if unread_only: q=q.filter(Notification.is_read==False)
    if priority:    q=q.filter(Notification.priority==priority)
    return q.order_by(desc(Notification.created_at)).offset(skip).limit(limit).all()


@router.get('/unread-count')
def unread_count(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.recipient_id==user.id, Notification.is_read==False).count()
    critical = db.query(Notification).filter(Notification.recipient_id==user.id, Notification.is_read==False, Notification.priority=='CRITICAL').count()
    return {'unread': n, 'critical_unread': critical}


@router.post('/mark-read/{notif_id}')
def mark_read(notif_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id==notif_id, Notification.recipient_id==user.id).first()
    if n: n.is_read=True; n.read_at=datetime.now(timezone.utc); db.commit()
    return {'status': 'read'}


@router.post('/mark-all-read')
def mark_all_read(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    db.query(Notification).filter(Notification.recipient_id==user.id, Notification.is_read==False).update({'is_read':True,'read_at':datetime.now(timezone.utc)})
    db.commit()
    return {'status': 'all_read'}


@router.post('/acknowledge/{notif_id}')
def acknowledge(notif_id: int, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    n = db.query(Notification).filter(Notification.id==notif_id, Notification.recipient_id==user.id).first()
    if n: n.acknowledged=True; n.ack_at=datetime.now(timezone.utc); n.is_read=True; db.commit()
    return {'status': 'acknowledged'}


@router.post('/send', status_code=201)
def send_notification(
    recipient_id: int, notif_type: str, title: str, body: str,
    priority: str='NORMAL', entity_type: Optional[str]=None,
    entity_id: Optional[int]=None, patient_pid: Optional[str]=None,
    action_url: Optional[str]=None,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    """Create an in-app notification for a user."""
    n = Notification(
        recipient_id=recipient_id, sender_id=user.id,
        notif_type=notif_type, title=title, body=body, priority=priority,
        entity_type=entity_type, entity_id=entity_id,
        patient_pid=patient_pid, action_url=action_url,
    )
    db.add(n); db.commit(); db.refresh(n)
    return {'id': n.id, 'status': 'sent'}


@router.post('/critical-result')
async def notify_critical_result(
    recipient_id: int, patient_pid: str, test_name: str,
    result_value: str, flag: str, lab_request_id: int,
    background_tasks: BackgroundTasks,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    """Send critical result notification to clinician (in-app + SMS queue)."""
    title = f'🚨 CRITICAL: {test_name}'
    body = f'Patient {patient_pid} — {test_name}: {result_value} [{flag}]. Immediate clinical action required.'
    n = Notification(
        recipient_id=recipient_id, sender_id=user.id,
        notif_type='CRITICAL_RESULT', title=title, body=body, priority='CRITICAL',
        entity_type='LAB', entity_id=lab_request_id, patient_pid=patient_pid,
        action_url=f'/doctor-portal/?pid={patient_pid}',
    )
    db.add(n)
    # Queue SMS
    sms = SMSQueue(
        phone_number='LOOKUP', message=body,
        sms_type='CRITICAL_VALUE', patient_pid=patient_pid,
    )
    db.add(sms)
    db.commit()
    return {'notification_id': n.id, 'sms_queued': True}


# ── SMS queue (admin) ──────────────────────────────────────────────
@router.get('/sms-queue')
def sms_queue(status: Optional[str]=None, skip: int=0, limit: int=50,
              db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    if user.role not in ('super_admin','lab_manager','it_admin'):
        return []
    q = db.query(SMSQueue)
    if status: q=q.filter(SMSQueue.status==status)
    return q.order_by(desc(SMSQueue.created_at)).offset(skip).limit(limit).all()
