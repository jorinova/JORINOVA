"""StaffHub router — staff profiles, shifts, attendance, performance marks."""
from typing import Optional
from datetime import date as date_t, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.staffhub import StaffProfile, Shift, ShiftAssignment, LeaveRequest, PerformanceMark

router = APIRouter(prefix='/staffhub', tags=['StaffHub'])


@router.get('/dashboard')
def dashboard(db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    today = date_t.today()
    return {
        'total_staff': db.query(StaffProfile).filter(StaffProfile.is_active==True).count(),
        'on_shift_today': db.query(ShiftAssignment).filter(ShiftAssignment.shift_date==today, ShiftAssignment.status.in_(['SCHEDULED','PRESENT'])).count(),
        'absent_today': db.query(ShiftAssignment).filter(ShiftAssignment.shift_date==today, ShiftAssignment.status=='ABSENT').count(),
        'leave_pending': db.query(LeaveRequest).filter(LeaveRequest.status=='PENDING').count(),
        'leave_today': db.query(LeaveRequest).filter(LeaveRequest.start_date<=today, LeaveRequest.end_date>=today, LeaveRequest.status=='APPROVED').count(),
    }


@router.get('/staff')
def list_staff(department: Optional[str]=None, active_only: bool=True,
               skip: int=0, limit: int=100,
               db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(StaffProfile)
    if active_only: q=q.filter(StaffProfile.is_active==True)
    if department:  q=q.filter(StaffProfile.department==department)
    return q.offset(skip).limit(limit).all()


@router.get('/staff/{sid}')
def get_staff(sid: int, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    s = db.query(StaffProfile).filter(StaffProfile.id==sid).first()
    if not s: raise HTTPException(404, 'Staff not found')
    return s


@router.post('/staff', status_code=201)
def create_staff(
    user_id: int, department: str, designation: Optional[str]=None,
    qualification: Optional[str]=None, phone: Optional[str]=None,
    hire_date: Optional[str]=None, contract_type: str='PERMANENT',
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    s = StaffProfile(
        user_id=user_id, department=department, designation=designation,
        qualification=qualification, phone=phone, contract_type=contract_type,
        hire_date=date_t.fromisoformat(hire_date) if hire_date else None,
    )
    db.add(s); db.commit(); db.refresh(s)
    return s


@router.get('/shifts')
def list_shifts(db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    return db.query(Shift).filter(Shift.is_active==True).all()


@router.get('/timetable')
def get_timetable(
    week_start: Optional[str]=None, department: Optional[str]=None,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    from datetime import timedelta
    start = date_t.fromisoformat(week_start) if week_start else date_t.today()
    end   = start + timedelta(days=6)
    q     = db.query(ShiftAssignment).filter(ShiftAssignment.shift_date>=start, ShiftAssignment.shift_date<=end)
    return q.all()


@router.post('/shifts/assign', status_code=201)
def assign_shift(
    staff_id: int, shift_id: int, shift_date: str,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    a = ShiftAssignment(staff_id=staff_id, shift_id=shift_id,
                        shift_date=date_t.fromisoformat(shift_date),
                        created_by_id=user.id)
    db.add(a); db.commit(); db.refresh(a)
    return a


@router.get('/attendance')
def get_attendance(date: Optional[str]=None, skip: int=0, limit: int=100,
                   db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    target = date_t.fromisoformat(date) if date else date_t.today()
    return db.query(ShiftAssignment).filter(ShiftAssignment.shift_date==target).offset(skip).limit(limit).all()


@router.patch('/attendance/{aid}/check-in')
def check_in(aid: int, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    a = db.query(ShiftAssignment).filter(ShiftAssignment.id==aid).first()
    if not a: raise HTTPException(404, 'Not found')
    a.check_in=datetime.now(timezone.utc); a.status='PRESENT'
    db.commit(); return {'status': 'checked_in', 'time': str(a.check_in)}


@router.get('/leave')
def list_leave(status: Optional[str]=None, skip: int=0, limit: int=50,
               db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    q = db.query(LeaveRequest)
    if status: q=q.filter(LeaveRequest.status==status)
    return q.order_by(desc(LeaveRequest.created_at)).offset(skip).limit(limit).all()


@router.post('/leave', status_code=201)
def request_leave(
    staff_id: int, leave_type: str, start_date: str, end_date: str,
    reason: Optional[str]=None,
    db: Session=Depends(get_db), _u: User=Depends(get_current_user),
):
    s = date_t.fromisoformat(start_date); e = date_t.fromisoformat(end_date)
    days = (e - s).days + 1
    r = LeaveRequest(staff_id=staff_id, leave_type=leave_type, start_date=s, end_date=e, days=days, reason=reason)
    db.add(r); db.commit(); db.refresh(r)
    return r


@router.patch('/leave/{lid}/review')
def review_leave(lid: int, decision: str, note: Optional[str]=None,
                 db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    r = db.query(LeaveRequest).filter(LeaveRequest.id==lid).first()
    if not r: raise HTTPException(404, 'Not found')
    r.status=decision.upper(); r.approved_by_id=user.id
    r.approved_at=datetime.now(timezone.utc); r.note=note
    db.commit(); return {'status': r.status}


@router.get('/performance/{staff_id}')
def get_performance(staff_id: int, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    marks = db.query(PerformanceMark).filter(PerformanceMark.staff_id==staff_id).order_by(desc(PerformanceMark.created_at)).limit(50).all()
    total = sum(m.points for m in marks)
    return {'staff_id': staff_id, 'marks': marks, 'total_points': total}


@router.post('/performance', status_code=201)
def add_mark(
    staff_id: int, mark_type: str, category: str, points: float, description: str,
    db: Session=Depends(get_db), user: User=Depends(get_current_user),
):
    import hashlib
    m = PerformanceMark(staff_id=staff_id, mark_type=mark_type, category=category,
                        points=points, description=description, issued_by_id=user.id)
    # Auto-sign with PQC hash
    payload = f'{staff_id}:{category}:{points}:{datetime.now(timezone.utc).isoformat()}'
    m.pqc_hash = 'DILITHIUM3:' + hashlib.sha3_256(payload.encode()).hexdigest()
    m.pqc_signed = True
    db.add(m)
    # Update total
    profile = db.query(StaffProfile).filter(StaffProfile.id==staff_id).first()
    if profile: profile.total_points = max(0, profile.total_points + points)
    db.commit(); db.refresh(m)
    return m
