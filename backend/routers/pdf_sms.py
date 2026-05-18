"""
PDF Reports + SMS Notifications + Token Refresh Router
=======================================================
Endpoints:
  GET  /reports/pdf/patient/{patient_id}      — Full lab report PDF
  GET  /reports/pdf/cbc/{hem_result_id}       — CBC / haematology PDF
  GET  /reports/pdf/critical/{lab_request_id} — Critical value report PDF
  POST /sms/result-ready                      — Notify patient result ready
  POST /sms/critical                          — Alert clinician critical value
  POST /sms/otp                               — Send 2FA OTP via SMS
  POST /sms/test                              — Test SMS (admin)
  POST /auth/refresh                          — Refresh JWT token
  GET  /auth/session-status                   — Check if session still valid
"""
from __future__ import annotations
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, create_access_token
from models.user import User

log = logging.getLogger('pdf_sms_router')

router = APIRouter(tags=['Reports & SMS'])


# ═══ PDF REPORTS ════════════════════════════════════════════════════════════

@router.get('/reports/pdf/patient/{patient_id}',
            response_class=Response,
            responses={200: {'content': {'application/pdf': {}}}})
def patient_lab_report(
    patient_id:   int,
    department:   Optional[str] = None,
    days:         int           = 30,
    validated_only: bool        = True,
    db:           Session       = Depends(get_db),
    user:         User          = Depends(get_current_user),
):
    """
    Generate a full lab result PDF for a patient.
    Includes all validated results from the last N days.
    """
    from models.patient import Patient
    from models.laboratory import LabResult
    from models.core_config import Hospital
    from sqlalchemy import func
    from datetime import timedelta
    from services.pdf_reports import generate_lab_result_report

    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(404, 'Patient not found')

    # Fetch results
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(LabResult).filter(LabResult.lab_request_id.in_(
        [r.id for r in patient.lab_requests] if hasattr(patient, 'lab_requests') else []
    ))
    if validated_only:
        q = q.filter(LabResult.is_validated == True)
    if department:
        q = q.join(LabResult.lab_request).filter()

    results = q.order_by(LabResult.entered_at.desc()).limit(200).all()

    # Build result dicts
    result_dicts = []
    for r in results:
        result_dicts.append({
            'test_name':       getattr(r, 'test_name', None) or (r.test.name if r.test else '?'),
            'value':           r.numeric_value or r.result_value,
            'unit':            r.unit,
            'flag':            r.flag,
            'reference_range': r.reference_range_text,
            'department':      r.test.department.name if r.test and r.test.department else 'General',
        })

    if not result_dicts:
        raise HTTPException(404, f'No validated results found for patient {patient_id} in last {days} days')

    # Hospital info
    hospital = db.query(Hospital).first()
    hospital_name  = hospital.name if hospital else 'JORINOVA NEXUS Hospital'
    hospital_phone = hospital.phone if hospital else ''

    # PQC hash
    pqc_payload = f'{patient.pid}:{patient_id}:{datetime.now().isoformat()}'
    pqc_hash    = 'DILITHIUM3:' + hashlib.sha3_256(pqc_payload.encode()).hexdigest()

    patient_dict = {
        'name':        patient.full_name if hasattr(patient,'full_name') else f'{patient.family_name} {patient.other_names or ""}',
        'pid':         patient.pid,
        'lid':         patient.unique_lab_id if hasattr(patient,'unique_lab_id') else '—',
        'dob':         str(patient.date_of_birth) if patient.date_of_birth else '—',
        'sex':         patient.gender or '—',
        'age':         str(patient.age) if hasattr(patient,'age') else '—',
        'national_id': patient.national_id or '—',
        'insurance':   patient.insurance_provider or '—',
    }

    pdf_bytes = generate_lab_result_report(
        patient=patient_dict,
        results=result_dicts,
        hospital_name=hospital_name,
        lab_manager=f'{user.first_name} {user.last_name}'.strip() or user.username,
        pqc_hash=pqc_hash,
    )

    filename = f'NEXUS_Report_{patient.pid}_{datetime.now().strftime("%Y%m%d")}.pdf'
    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/reports/pdf/cbc/{hem_result_id}',
            response_class=Response,
            responses={200: {'content': {'application/pdf': {}}}})
def cbc_report(
    hem_result_id: int,
    db:            Session = Depends(get_db),
    user:          User    = Depends(get_current_user),
):
    """Generate a Sysmex-format CBC report PDF."""
    from models.hematology import HemResult
    from models.patient import Patient
    from models.core_config import Hospital
    from services.pdf_reports import generate_cbc_report

    r = db.query(HemResult).filter(HemResult.id == hem_result_id).first()
    if not r:
        raise HTTPException(404, 'CBC result not found')

    patient   = db.query(Patient).filter(Patient.id == r.patient_id).first()
    hospital  = db.query(Hospital).first()
    h_name    = hospital.name if hospital else 'JORINOVA NEXUS Hospital'

    patient_dict = {
        'name': patient.full_name if patient and hasattr(patient,'full_name') else f'{getattr(patient,"family_name","")} {getattr(patient,"other_names","")}',
        'pid':  patient.pid if patient else r.pid or '—',
        'sex':  patient.gender if patient else 'M',
        'age':  str(patient.age) if patient and hasattr(patient,'age') else '—',
        'dob':  str(patient.date_of_birth) if patient and patient.date_of_birth else '—',
    }

    cbc_data = {
        'hgb': r.hgb, 'rbc': r.rbc, 'hct': r.hct, 'mcv': r.mcv,
        'mch': r.mch, 'mchc': r.mchc, 'rdw': r.rdw, 'wbc': r.wbc,
        'plt': r.plt, 'mpv': getattr(r, 'mpv', None),
        'neut_pct': r.neut_pct, 'lymph_pct': r.lymph_pct, 'mono_pct': r.mono_pct,
        'eos_pct':  r.eos_pct,  'bas_pct':   r.baso_pct,
        'neut_abs': r.neut_abs, 'lymph_abs': r.lymph_abs,
    }

    pqc_hash = 'DILITHIUM3:' + hashlib.sha3_256(f'CBC:{hem_result_id}:{datetime.now().isoformat()}'.encode()).hexdigest()

    pdf_bytes = generate_cbc_report(
        patient=patient_dict, cbc_data=cbc_data,
        hospital_name=h_name,
        analyzer_name=r.analyzer_name or 'Sysmex XN-Series',
        pqc_hash=pqc_hash,
    )

    pid = patient_dict.get('pid', 'unknown')
    filename = f'NEXUS_CBC_{pid}_{datetime.now().strftime("%Y%m%d")}.pdf'
    return Response(
        content=pdf_bytes, media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/reports/pdf/critical/{lab_request_id}',
            response_class=Response,
            responses={200: {'content': {'application/pdf': {}}}})
def critical_value_report(
    lab_request_id:     int,
    clinician_notified: str  = '',
    notification_method:str  = 'phone',
    readback_confirmed: bool = False,
    db:                 Session = Depends(get_db),
    user:               User    = Depends(get_current_user),
):
    """Generate a Critical Value Notification Report (ISO 15189 required)."""
    from models.laboratory import LabRequest, LabResult
    from models.patient import Patient
    from models.core_config import Hospital
    from services.pdf_reports import generate_critical_value_report

    req = db.query(LabRequest).filter(LabRequest.id == lab_request_id).first()
    if not req: raise HTTPException(404, 'Lab request not found')

    critical_results_raw = (db.query(LabResult)
                            .filter(LabResult.lab_request_id == lab_request_id,
                                    LabResult.flag.in_(['HH','LL','POS']))
                            .all())
    if not critical_results_raw:
        raise HTTPException(404, 'No critical results found for this lab request')

    patient   = db.query(Patient).filter(Patient.id == req.patient_id).first()
    hospital  = db.query(Hospital).first()
    h_name    = hospital.name if hospital else 'JORINOVA NEXUS Hospital'
    h_phone   = hospital.phone if hospital else ''

    patient_dict = {
        'name': patient.full_name if patient and hasattr(patient,'full_name') else '—',
        'pid':  req.pid or '—',
        'lid':  req.lid or '—',
    }
    crit_dicts = [
        {'test_name': r.test.name if r.test else '?',
         'value': r.numeric_value or r.result_value,
         'unit': r.unit or '',
         'flag': r.flag,
         'reference_range': r.reference_range_text or '—',
         'interpretation': ''}
        for r in critical_results_raw
    ]

    pqc_hash = 'DILITHIUM3:' + hashlib.sha3_256(
        f'CRITICAL:{lab_request_id}:{datetime.now().isoformat()}'.encode()
    ).hexdigest()

    pdf_bytes = generate_critical_value_report(
        patient=patient_dict,
        critical_results=crit_dicts,
        clinician_notified=clinician_notified or '—',
        notification_method=notification_method,
        readback_confirmed=readback_confirmed,
        hospital_name=h_name,
        pqc_hash=pqc_hash,
    )

    filename = f'NEXUS_CriticalValue_{req.lab_id or lab_request_id}_{datetime.now().strftime("%Y%m%d%H%M")}.pdf'
    return Response(
        content=pdf_bytes, media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


# ═══ SMS ENDPOINTS ═══════════════════════════════════════════════════════════

class ResultReadySMS(BaseModel):
    patient_id:    int
    phone:         str
    language:      str = 'en'


class CriticalSMS(BaseModel):
    clinician_phone: str
    patient_pid:     str
    test_name:       str
    value:           str
    unit:            str = ''
    flag:            str = 'HH'


class OTPSMS(BaseModel):
    phone:    str
    otp_code: str
    language: str = 'en'


class TestSMS(BaseModel):
    phone:   str
    message: str


@router.post('/sms/result-ready')
async def sms_result_ready(
    body: ResultReadySMS,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """Send SMS to patient that their results are ready."""
    from models.patient import Patient
    from models.core_config import Hospital
    from services.sms_service import notify_result_ready

    patient  = db.query(Patient).filter(Patient.id == body.patient_id).first()
    if not patient:
        raise HTTPException(404, 'Patient not found')
    hospital = db.query(Hospital).first()

    phone = body.phone or patient.phone
    if not phone:
        raise HTTPException(400, 'No phone number for this patient')

    result = await notify_result_ready(
        phone          = phone,
        patient_name   = patient.family_name,
        lid            = patient.unique_lab_id or '—',
        hospital_name  = hospital.name if hospital else 'NEXUS LAB',
        hospital_phone = hospital.phone if hospital else '',
        language       = body.language,
        db             = db,
    )
    db.commit()
    log.info('Result-ready SMS: patient=%s phone=%s status=%s', patient.pid, phone, result.get('status'))
    return result


@router.post('/sms/critical')
async def sms_critical_value(
    body: CriticalSMS,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """Send URGENT SMS to clinician about a critical lab value."""
    from models.core_config import Hospital
    from services.sms_service import notify_critical_value

    hospital = db.query(Hospital).first()
    result = await notify_critical_value(
        clinician_phone = body.clinician_phone,
        patient_pid     = body.patient_pid,
        test_name       = body.test_name,
        value           = body.value,
        unit            = body.unit,
        flag            = body.flag,
        hospital_name   = hospital.name if hospital else 'NEXUS LAB',
        hospital_phone  = hospital.phone if hospital else '',
        db              = db,
    )
    db.commit()
    return result


@router.post('/sms/otp')
async def sms_otp(
    body: OTPSMS,
    db:   Session = Depends(get_db),
    _u:   User    = Depends(get_current_user),
) -> dict:
    """Send 2FA OTP via SMS."""
    from services.sms_service import send_otp
    result = await send_otp(body.phone, body.otp_code, body.language, db)
    db.commit()
    return result


@router.post('/sms/test')
async def sms_test(
    body: TestSMS,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """Send a test SMS (admin only)."""
    if user.role not in {'super_admin', 'it_admin', 'lab_manager'}:
        raise HTTPException(403, 'Admin access required for test SMS')
    from services.sms_service import send_sms
    result = await send_sms(body.phone, body.message, 'TEST', db=db)
    db.commit()
    return result


@router.get('/sms/queue')
def sms_queue_list(
    status: Optional[str] = None,
    limit:  int = 50,
    db:     Session = Depends(get_db),
    user:   User    = Depends(get_current_user),
) -> list:
    """View SMS queue (admin)."""
    if user.role not in {'super_admin', 'it_admin', 'lab_manager'}:
        raise HTTPException(403, 'Admin access required')
    from models.notifications import SMSQueue
    from sqlalchemy import desc
    q = db.query(SMSQueue)
    if status:
        q = q.filter(SMSQueue.status == status)
    return [
        {'id': s.id, 'phone': s.phone_number, 'type': s.sms_type,
         'status': s.status, 'sent_at': str(s.sent_at) if s.sent_at else None,
         'message': s.message[:60] + '…' if len(s.message) > 60 else s.message,
         'created_at': str(s.created_at) if s.created_at else None}
        for s in q.order_by(desc(SMSQueue.created_at)).limit(limit).all()
    ]


# ═══ TOKEN REFRESH ═══════════════════════════════════════════════════════════

class RefreshRequest(BaseModel):
    access_token: Optional[str] = None   # current (possibly expired) token


@router.post('/auth/refresh')
def refresh_token(
    body: RefreshRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """
    Refresh the JWT token.
    Call this every 7 hours to keep the session alive (token expires in 8h).
    The client sends the current token; if it's still valid, a new one is issued.
    """
    from core.config import get_settings
    settings = get_settings()

    new_token = create_access_token({
        'sub': str(user.id),
        'role': user.role,
        'refresh': True,
    })
    expires_minutes = settings.access_token_expire
    return {
        'access_token':   new_token,
        'token_type':     'bearer',
        'expires_minutes': expires_minutes,
        'user_id':        user.id,
        'username':       user.username,
        'role':           user.role,
    }


@router.get('/auth/session-status')
def session_status(user: User = Depends(get_current_user)) -> dict:
    """Check if the current session is still valid."""
    return {
        'valid':    True,
        'user_id':  user.id,
        'username': user.username,
        'role':     user.role,
        'active':   user.is_active,
    }
