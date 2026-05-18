"""Head of Department Escalation Router."""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.escalation import EscalationRecord, EscalationStatus

router = APIRouter(prefix='/escalation', tags=['Escalation'])

HOD_ROLES = {'lab_manager', 'head_of_department', 'pathologist', 'super_admin'}


class ReviewBody(BaseModel):
    decision:     str    # approved | rejected
    review_note:  str = ''


@router.get('/')
async def list_escalations(
    status:  Optional[str] = None,
    skip:    int = 0,
    limit:   int = 50,
    user:    User = Depends(get_current_user),
    db:      Session = Depends(get_db),
) -> list:
    """
    List escalations.
    HoD roles see all pending escalations.
    Regular users see only their own.
    """
    q = db.query(EscalationRecord)
    if user.role not in HOD_ROLES:
        q = q.filter(EscalationRecord.user_id == user.id)
    if status:
        q = q.filter(EscalationRecord.status == status)
    records = q.order_by(EscalationRecord.created_at.desc()).offset(skip).limit(limit).all()
    return [_serialize(r) for r in records]


@router.get('/pending-count')
async def pending_count(
    user: User = Depends(get_current_user),
    db:   Session = Depends(get_db),
) -> dict:
    """Quick count of pending escalations for HoD notification badge."""
    if user.role not in HOD_ROLES:
        return {'count': 0, 'authorized': False}
    n = db.query(EscalationRecord).filter(EscalationRecord.status == 'pending').count()
    return {'count': n, 'authorized': True}


@router.get('/{record_id}')
async def get_escalation(
    record_id: int,
    user:      User = Depends(get_current_user),
    db:        Session = Depends(get_db),
) -> dict:
    r = db.query(EscalationRecord).filter(EscalationRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, 'Escalation record not found')
    if user.role not in HOD_ROLES and r.user_id != user.id:
        raise HTTPException(403, 'Access denied')
    return _serialize(r)


@router.post('/{record_id}/review')
async def review_escalation(
    record_id: int,
    body:      ReviewBody,
    user:      User = Depends(get_current_user),
    db:        Session = Depends(get_db),
) -> dict:
    """
    Head of Department approves or rejects an escalation.
    Only HoD roles can review escalations.
    """
    if user.role not in HOD_ROLES:
        raise HTTPException(403, 'Only Head of Department can review escalations')

    r = db.query(EscalationRecord).filter(EscalationRecord.id == record_id).first()
    if not r:
        raise HTTPException(404, 'Escalation record not found')
    if r.status != 'pending':
        raise HTTPException(400, f'Escalation already reviewed: {r.status}')

    if body.decision not in ('approved', 'rejected'):
        raise HTTPException(400, 'Decision must be approved or rejected')

    r.status           = body.decision
    r.reviewed_by_id   = user.id
    r.reviewed_by_name = f'{user.first_name} {user.last_name}'.strip() or user.username
    r.review_note      = body.review_note
    r.reviewed_at      = datetime.now(timezone.utc)
    db.commit()
    db.refresh(r)

    return {
        'status':   r.status,
        'message':  f'Escalation {body.decision} by {r.reviewed_by_name}',
        'record':   _serialize(r),
    }


def _serialize(r: EscalationRecord) -> dict:
    return {
        'id':              r.id,
        'user_name':       r.user_name,
        'user_role':       r.user_role,
        'command_text':    r.command_text,
        'danger_category': r.danger_category,
        'reason':          r.reason,
        'status':          r.status,
        'reviewed_by':     r.reviewed_by_name,
        'review_note':     r.review_note,
        'reviewed_at':     r.reviewed_at.isoformat() if r.reviewed_at else None,
        'created_at':      r.created_at.isoformat() if r.created_at else None,
        'action_executed': r.action_executed,
    }
