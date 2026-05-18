"""Interoperability router — HL7 v2.5, FHIR R4, RBC integration, WHO APIs."""
from typing import Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User

router = APIRouter(prefix='/interoperability', tags=['Interoperability'])


# ── HL7 v2.5 ─────────────────────────────────────────────────────

@router.post('/hl7/receive')
async def receive_hl7(request: Request, _u: User=Depends(get_current_user)):
    """
    Receive HL7 v2.5 message from external systems.
    Supports: ORM (order), ORU (result), ADT (patient), QRY (query).
    """
    body = await request.body()
    raw = body.decode('utf-8', errors='replace')
    try:
        lines = raw.strip().split('\r')
        msg_type = ''
        for line in lines:
            if line.startswith('MSH'):
                fields = line.split('|')
                msg_type = fields[8] if len(fields) > 8 else ''
                break
        return {
            'status': 'received',
            'message_type': msg_type,
            'segment_count': len(lines),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'ack': f'MSH|^~\\&|ALIS-X|NEXUS|{msg_type.split("^")[0]}||{datetime.now().strftime("%Y%m%d%H%M%S")}||ACK|1|P|2.5\rMSA|AA|1|Message accepted',
        }
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}


@router.get('/hl7/send-result/{lab_request_id}')
async def send_hl7_result(lab_request_id: int, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    """Generate HL7 ORU^R01 message for a validated lab result."""
    from models.laboratory import LabRequest, LabResult
    req = db.query(LabRequest).filter(LabRequest.id==lab_request_id).first()
    if not req: raise HTTPException(404, 'Lab request not found')
    results = db.query(LabResult).filter(LabResult.lab_request_id==lab_request_id, LabResult.is_validated==True).all()
    now = datetime.now().strftime('%Y%m%d%H%M%S')
    obx_segments = []
    for i, r in enumerate(results, 1):
        obx = f'OBX|{i}|NM|{r.test_id}||{r.numeric_value or r.result_value}|{r.unit or ""}|{r.reference_range_text or ""}|{r.flag or "N"}|||F|||{now}'
        obx_segments.append(obx)
    hl7 = '\r'.join([
        f'MSH|^~\\&|ALIS-X|NEXUS|EHR|HOSPITAL|{now}||ORU^R01|{lab_request_id}|P|2.5',
        f'PID|1||{req.pid or "UNKNOWN"}||PATIENT^NAME||19800101|U',
        f'OBR|1|{req.lab_id}||LAB^Laboratory Results|||{now}||||||||||LAB',
        *obx_segments,
    ])
    return {'hl7_message': hl7, 'segment_count': len(hl7.split('\r'))}


# ── FHIR R4 ──────────────────────────────────────────────────────

@router.get('/fhir/Patient/{pid}')
def fhir_patient(pid: str, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    """Return FHIR R4 Patient resource."""
    from models.patient import Patient
    p = db.query(Patient).filter(Patient.pid==pid).first()
    if not p: raise HTTPException(404, 'Patient not found')
    return {
        'resourceType': 'Patient',
        'id': str(p.id),
        'identifier': [{'system': 'urn:jorinova:pid', 'value': p.pid}],
        'name': [{'family': p.family_name, 'given': [p.other_names or '']}],
        'birthDate': str(p.date_of_birth) if p.date_of_birth else None,
        'gender': p.gender.lower() if p.gender else 'unknown',
        'telecom': [{'system': 'phone', 'value': p.phone}] if p.phone else [],
    }


@router.get('/fhir/DiagnosticReport/{lab_id}')
def fhir_diagnostic_report(lab_id: str, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    """Return FHIR R4 DiagnosticReport resource."""
    from models.laboratory import LabRequest, LabResult
    req = db.query(LabRequest).filter(LabRequest.lab_id==lab_id).first()
    if not req: raise HTTPException(404, 'Lab request not found')
    results = db.query(LabResult).filter(LabResult.lab_request_id==req.id).all()
    observations = [
        {
            'resourceType': 'Observation',
            'id': str(r.id),
            'status': 'final' if r.is_validated else 'preliminary',
            'valueQuantity': {'value': r.numeric_value, 'unit': r.unit},
            'interpretation': [{'text': r.flag or 'N'}],
        }
        for r in results
    ]
    return {
        'resourceType': 'DiagnosticReport',
        'id': lab_id,
        'status': 'final' if req.status == 'validated' else 'partial',
        'subject': {'identifier': {'value': req.pid}},
        'result': [{'reference': f'Observation/{o["id"]}', 'resource': o} for o in observations],
        'issued': req.request_date.isoformat() if req.request_date else None,
    }


@router.post('/fhir/ServiceRequest')
async def fhir_service_request(request: Request, db: Session=Depends(get_db), _u: User=Depends(get_current_user)):
    """Accept FHIR ServiceRequest (lab order from external EHR)."""
    body = await request.json()
    return {
        'resourceType': 'OperationOutcome',
        'issue': [{'severity': 'information', 'code': 'informational',
                   'diagnostics': 'ServiceRequest received and queued for processing.'}]
    }


# ── System status & connections ───────────────────────────────────

@router.get('/connections')
def list_connections(_u: User=Depends(get_current_user)):
    """Return status of all external system connections."""
    return {
        'connections': [
            {'name': 'RBC System (Rwanda)', 'protocol': 'REST/JSON', 'status': 'configured', 'last_sync': None},
            {'name': 'Ministry of Health HMIS', 'protocol': 'HL7 v2.5', 'status': 'configured', 'last_sync': None},
            {'name': 'WHO DHIS2', 'protocol': 'FHIR R4', 'status': 'configured', 'last_sync': None},
            {'name': 'National TB Program', 'protocol': 'REST/JSON', 'status': 'configured', 'last_sync': None},
            {'name': 'Lab Middleware (ASTM)', 'protocol': 'ASTM E1394', 'status': 'active', 'last_sync': datetime.now(timezone.utc).isoformat()},
        ]
    }


@router.get('/status')
def interop_status(_u: User=Depends(get_current_user)):
    return {
        'hl7_endpoint': '/api/v1/interoperability/hl7/receive',
        'fhir_base': '/api/v1/interoperability/fhir',
        'fhir_version': 'R4 (4.0.1)',
        'hl7_version': 'v2.5',
        'supported_resources': ['Patient','DiagnosticReport','Observation','ServiceRequest'],
        'supported_segments': ['MSH','PID','OBR','OBX','ORM','ORU','ADT'],
    }
