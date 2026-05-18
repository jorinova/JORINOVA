"""Sample Rejection API Router."""
from datetime import date as date_type, datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ai_services.rejection_rules import (
    get_all_rules, get_rule, get_by_category, suggest_for_test,
    suggest_for_observation, get_tube_guide, REJECTION_RULES,
)
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.rejection import SampleRejection

router = APIRouter(prefix='/rejection', tags=['Sample Rejection'])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RejectIn(BaseModel):
    rejection_code:    str
    sid:               Optional[str] = None
    pid:               Optional[str] = None
    lid:               Optional[str] = None
    lab_request_id:    Optional[int] = None
    patient_id:        Optional[int] = None
    specimen_type:     Optional[str] = None
    tube_type:         Optional[str] = None
    collection_site:   Optional[str] = None
    collected_by:      Optional[str] = None
    rejection_note:    Optional[str] = None
    ward_notified:     bool = False
    requester_name:    Optional[str] = None
    department:        Optional[str] = None


class SuggestIn(BaseModel):
    is_haemolysed: bool = False
    is_lipaemic:   bool = False
    is_clotted:    bool = False
    is_qns:        bool = False
    wrong_tube:    bool = False
    no_label:      bool = False
    expired_tube:  bool = False
    leaking:       bool = False
    delayed:       bool = False


class ResolveIn(BaseModel):
    recollection_done: bool = False
    recollection_sid:  Optional[str] = None
    resolved:          bool = True


# ── Rules endpoints ───────────────────────────────────────────────────────────

@router.get('/rules')
def list_rules(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    _u:       User = Depends(get_current_user),
) -> list:
    """Return all coded rejection rules (offline, AI-accessible)."""
    rules = get_all_rules()
    if category: rules = [r for r in rules if r['category'] == category]
    if severity: rules = [r for r in rules if r['severity'] == severity]
    return rules


@router.get('/rules/{code}')
def get_rejection_rule(code: str, _u: User = Depends(get_current_user)) -> dict:
    """Get a specific rejection rule by code (e.g. SQ-001)."""
    r = get_rule(code.upper())
    if not r:
        raise HTTPException(404, f'Rejection rule not found: {code}')
    return r


@router.get('/rules/test/{test_code}')
def rules_for_test(test_code: str, _u: User = Depends(get_current_user)) -> list:
    """Get rejection rules applicable to a specific test code."""
    return suggest_for_test(test_code.upper())


@router.post('/rules/suggest')
def suggest_rules(body: SuggestIn, _u: User = Depends(get_current_user)) -> list:
    """
    Suggest rejection rules based on observed specimen characteristics.
    The AI and technician use this to pick the correct rejection reason.
    """
    return suggest_for_observation(**body.model_dump())


@router.get('/tube-guide')
def tube_guide(_u: User = Depends(get_current_user)) -> dict:
    """Return tube type guidance (colour, tests, mixing instructions)."""
    return get_tube_guide()


# ── Rejection book endpoints ──────────────────────────────────────────────────

@router.post('/', status_code=201)
def create_rejection(
    body: RejectIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Record a sample rejection in the immutable rejection book.
    The rejection rule must exist in the coded catalogue.
    """
    rule = REJECTION_RULES.get(body.rejection_code.upper())
    if not rule:
        raise HTTPException(400, f'Unknown rejection code: {body.rejection_code}. '
                            f'Call GET /rejection/rules for the list.')

    # Generate rejection ID
    year = date_type.today().year
    n    = db.query(SampleRejection).filter(
        SampleRejection.rejection_id.like(f'REJ-{year}-%')
    ).count()
    rej_id = f'REJ-{year}-{str(n+1).zfill(5)}'

    record = SampleRejection(
        rejection_id      = rej_id,
        rejection_code    = rule.code,
        rejection_name    = rule.name,
        rejection_category= rule.category,
        severity          = rule.severity,
        corrective_action = rule.corrective_action,
        recollect_required= rule.recollect,
        rejected_by_id    = user.id,
        rejected_by_name  = f'{user.first_name} {user.last_name}'.strip() or user.username,
        rejected_at       = datetime.now(timezone.utc),
        **{k: v for k, v in body.model_dump().items()
           if k not in ('rejection_code',) and hasattr(SampleRejection, k)},
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        'rejection_id':   record.rejection_id,
        'code':           rule.code,
        'name':           rule.name,
        'severity':       rule.severity,
        'corrective_action': rule.corrective_action,
        'recollect_required': rule.recollect,
        'ai_context':     rule.ai_context,
    }


@router.get('/')
def list_rejections(
    date_from:  Optional[str] = None,
    date_to:    Optional[str] = None,
    category:   Optional[str] = None,
    severity:   Optional[str] = None,
    department: Optional[str] = None,
    resolved:   Optional[bool] = None,
    skip:       int = 0,
    limit:      int = 50,
    db:         Session = Depends(get_db),
    _u:         User    = Depends(get_current_user),
) -> list:
    """List rejection book entries with filtering."""
    q = db.query(SampleRejection)
    if date_from:  q = q.filter(func.date(SampleRejection.rejected_at) >= date_from)
    if date_to:    q = q.filter(func.date(SampleRejection.rejected_at) <= date_to)
    if category:   q = q.filter(SampleRejection.rejection_category == category)
    if severity:   q = q.filter(SampleRejection.severity == severity)
    if department: q = q.filter(SampleRejection.department == department)
    if resolved is not None: q = q.filter(SampleRejection.resolved == resolved)
    records = q.order_by(desc(SampleRejection.rejected_at)).offset(skip).limit(limit).all()
    return [_serialize(r) for r in records]


@router.get('/stats/summary')
def rejection_stats(
    days: int = 30,
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
) -> dict:
    """QA summary statistics for rejection book."""
    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=days)
    total = db.query(SampleRejection).filter(SampleRejection.rejected_at >= since).count()
    by_code = (db.query(SampleRejection.rejection_code,
                        SampleRejection.rejection_name,
                        func.count(SampleRejection.id).label('count'))
               .filter(SampleRejection.rejected_at >= since)
               .group_by(SampleRejection.rejection_code, SampleRejection.rejection_name)
               .order_by(desc('count')).limit(10).all())
    by_dept = (db.query(SampleRejection.department, func.count(SampleRejection.id))
               .filter(SampleRejection.rejected_at >= since)
               .group_by(SampleRejection.department)
               .order_by(desc('count')).all())
    return {
        'total':      total,
        'period_days':days,
        'top_reasons':[{'code':r.rejection_code,'name':r.rejection_name,'count':r.count} for r in by_code],
        'by_dept':    [{'dept':d,'count':c} for d, c in by_dept if d],
    }


@router.get('/{rejection_id}')
def get_rejection(
    rejection_id: str,
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
) -> dict:
    r = db.query(SampleRejection).filter(
        (SampleRejection.rejection_id == rejection_id) |
        (SampleRejection.id == int(rejection_id) if rejection_id.isdigit() else False)
    ).first()
    if not r:
        raise HTTPException(404, f'Rejection record not found: {rejection_id}')
    return _serialize(r)


@router.patch('/{rejection_id}/resolve')
def resolve_rejection(
    rejection_id: str,
    body: ResolveIn,
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
) -> dict:
    """Mark a rejection as resolved (recollected or waived)."""
    r = db.query(SampleRejection).filter(SampleRejection.rejection_id == rejection_id).first()
    if not r:
        raise HTTPException(404, 'Rejection record not found')
    r.recollection_done = body.recollection_done
    r.recollection_sid  = body.recollection_sid
    r.resolved          = body.resolved
    db.commit()
    return {'status': 'resolved', 'rejection_id': rejection_id}


def _serialize(r: SampleRejection) -> dict:
    return {
        'id':               r.id,
        'rejection_id':     r.rejection_id,
        'rejection_code':   r.rejection_code,
        'rejection_name':   r.rejection_name,
        'category':         r.rejection_category,
        'severity':         r.severity,
        'sid':              r.sid,
        'pid':              r.pid,
        'lid':              r.lid,
        'specimen_type':    r.specimen_type,
        'tube_type':        r.tube_type,
        'collected_by':     r.collected_by,
        'rejected_by':      r.rejected_by_name,
        'rejection_note':   r.rejection_note,
        'corrective_action':r.corrective_action,
        'recollect_required': r.recollect_required,
        'ward_notified':    r.ward_notified,
        'department':       r.department,
        'resolved':         r.resolved,
        'recollection_done':r.recollection_done,
        'recollection_sid': r.recollection_sid,
        'rejected_at':      r.rejected_at.isoformat() if r.rejected_at else None,
    }
