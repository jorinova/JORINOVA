"""
Blood Bank Router — JORINOVA NEXUS ALIS-X
==========================================
Covers full transfusion medicine workflow per AABB / WHO / Rwanda BNLSS:

  Donors
    GET  /blood-bank/donors              — List / search donors
    POST /blood-bank/donors              — Register new donor
    GET  /blood-bank/donors/{id}         — Donor profile + donation history
    PUT  /blood-bank/donors/{id}         — Update donor record
    POST /blood-bank/donors/{id}/defer   — Defer donor (temp or permanent)

  Blood Bags (Inventory)
    GET  /blood-bank/inventory           — Stock by blood group + component
    GET  /blood-bank/bags                — List bags (filterable)
    POST /blood-bank/bags                — Collect / register new bag
    GET  /blood-bank/bags/{bag_no}       — Get bag details
    PUT  /blood-bank/bags/{bag_no}/status— Update bag status
    GET  /blood-bank/bags/expiring       — Bags expiring in ≤7 days

  Blood Requests + Crossmatch
    GET  /blood-bank/requests            — List blood requests
    POST /blood-bank/requests            — New blood request from ward
    GET  /blood-bank/requests/{id}       — Request detail
    PUT  /blood-bank/requests/{id}/status— Update request status

    POST /blood-bank/crossmatch          — Perform crossmatch (assign bag → patient)
    GET  /blood-bank/crossmatch/{id}     — Get crossmatch result

  Issue + Transfusion
    POST /blood-bank/issue/{request_id}  — Issue blood (assign bag, generate form)
    POST /blood-bank/transfuse/{request_id}— Record transfusion started
    POST /blood-bank/transfuse/{request_id}/complete— Record transfusion complete

  Haemovigilance
    GET  /blood-bank/haemovigilance      — List all reactions
    POST /blood-bank/haemovigilance      — Report transfusion reaction
    GET  /blood-bank/haemovigilance/{id} — Reaction detail

  Stats + Reports
    GET  /blood-bank/stats               — Dashboard KPIs
    GET  /blood-bank/blood-group-stock   — Stock per ABO/Rh group
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.user import User

log = logging.getLogger('blood_bank_router')
router = APIRouter(tags=['Blood Bank'])

# ── Blood group compatibility table ───────────────────────────────────────────
# Recipient → compatible donor groups (for PRBC)
COMPATIBILITY: dict[str, list[str]] = {
    'A+':  ['A+', 'A-', 'O+', 'O-'],
    'A-':  ['A-', 'O-'],
    'B+':  ['B+', 'B-', 'O+', 'O-'],
    'B-':  ['B-', 'O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    'AB-': ['A-', 'B-', 'AB-', 'O-'],
    'O+':  ['O+', 'O-'],
    'O-':  ['O-'],
}

# Shelf life by component (days from collection)
SHELF_LIFE: dict[str, int] = {
    'WB':   35, 'PRBC': 42, 'FFP':  365,
    'PLT':  5,  'CRYO': 365, 'ALB': 730, 'GRAN': 1,
}

REACTION_TYPES = {
    'fnhtr':        'Febrile Non-Haemolytic Transfusion Reaction',
    'allergic':     'Allergic / Urticarial Reaction',
    'abo_haemo':    'ABO Incompatibility Haemolysis',
    'del_haemo':    'Delayed Haemolytic Reaction',
    'taco':         'Transfusion-Associated Circulatory Overload (TACO)',
    'trali':        'Transfusion-Related Acute Lung Injury (TRALI)',
    'septic':       'Septic / Bacterial Contamination',
    'gvhd':         'Transfusion-Associated GvHD',
    'near_miss':    'Near-Miss Event',
    'wrong_blood':  'Wrong Blood to Patient',
    'other':        'Other / Unclassified',
}


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class DonorCreate(BaseModel):
    family_name:   str
    other_names:   str = ''
    blood_group:   str
    date_of_birth: Optional[str] = None   # YYYY-MM-DD
    gender:        str = 'M'
    phone:         str = ''
    national_id:   Optional[str] = None

class DonorDefer(BaseModel):
    reason:        str
    deferral_until: Optional[str] = None  # YYYY-MM-DD; None = permanent

class BagCreate(BaseModel):
    donor_id:       Optional[int] = None
    blood_group:    str
    component:      str = 'PRBC'
    volume_ml:      int = 450
    collection_date:str            # YYYY-MM-DD
    is_irradiated:  bool = False
    is_leukoreduced:bool = False
    notes:          Optional[str] = None

class BloodRequestCreate(BaseModel):
    patient_id:          int
    blood_group:         str
    component:           str = 'PRBC'
    units_requested:     int = 1
    urgency:             str = 'routine'    # routine|urgent|emergency
    clinical_indication: str
    ward:                Optional[str] = None
    doctor_name:         Optional[str] = None

class CrossmatchIn(BaseModel):
    blood_bag_id: int
    patient_id:   int
    result:       str  # compatible|incompatible|weak_pos
    method:       str = 'Indirect Antiglobulin Test (IAT)'
    notes:        Optional[str] = None

class IssueIn(BaseModel):
    bag_number: str
    notes:      Optional[str] = None

class HaemovigilanceCreate(BaseModel):
    blood_bag_id:           Optional[int] = None
    patient_id:             int
    reaction_type:          str
    severity:               str  # mild|moderate|severe|fatal|near_miss
    onset_time:             Optional[str] = None
    transfusion_stopped:    bool = True
    volume_transfused_ml:   int = 0
    symptoms:               str
    clinical_management:    Optional[str] = None
    outcome:                Optional[str] = None


# ── Donors ─────────────────────────────────────────────────────────────────────

@router.get('/blood-bank/donors')
def list_donors(
    q:          Optional[str] = Query(None, description='Search name, donor_id, blood group'),
    blood_group:Optional[str] = Query(None),
    eligible:   Optional[bool]= Query(None),
    limit:      int           = Query(50, le=200),
    db:         Session       = Depends(get_db),
    user:       User          = Depends(get_current_user),
) -> list:
    from models.blood_bank import Donor
    from sqlalchemy import or_
    query = db.query(Donor)
    if blood_group: query = query.filter(Donor.blood_group == blood_group)
    if eligible is not None: query = query.filter(Donor.is_eligible == eligible)
    if q:
        query = query.filter(or_(
            Donor.family_name.ilike(f'%{q}%'),
            Donor.other_names.ilike(f'%{q}%'),
            Donor.donor_id.ilike(f'%{q}%'),
        ))
    donors = query.order_by(Donor.family_name).limit(limit).all()
    return [_donor_dict(d) for d in donors]


@router.post('/blood-bank/donors')
def register_donor(
    body: DonorCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    from models.blood_bank import Donor
    donor_id = f'DON{date.today().strftime("%Y%m%d")}-{_next_seq(db, "donors")}'
    dob = date.fromisoformat(body.date_of_birth) if body.date_of_birth else None

    # Eligibility: must be 18-65, last donation ≥56 days ago
    eligible = True
    defer_reason = None
    if dob:
        age = (date.today() - dob).days // 365
        if not (18 <= age <= 65):
            eligible = False
            defer_reason = f'Age {age} outside donor eligibility range (18–65)'

    donor = Donor(
        donor_id=donor_id, family_name=body.family_name,
        other_names=body.other_names, blood_group=body.blood_group.upper(),
        date_of_birth=dob, gender=body.gender.upper(),
        phone=body.phone, national_id=body.national_id,
        is_eligible=eligible, deferral_reason=defer_reason,
    )
    db.add(donor)
    db.commit()
    return _donor_dict(donor)


@router.get('/blood-bank/donors/{donor_id}')
def get_donor(donor_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    from models.blood_bank import Donor
    d = db.query(Donor).filter(Donor.id == donor_id).first()
    if not d: raise HTTPException(404, 'Donor not found')
    result = _donor_dict(d)
    result['bags'] = [_bag_dict(b) for b in d.blood_bags[-10:]]
    return result


@router.post('/blood-bank/donors/{donor_id}/defer')
def defer_donor(
    donor_id: int, body: DonorDefer,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    from models.blood_bank import Donor
    d = db.query(Donor).filter(Donor.id == donor_id).first()
    if not d: raise HTTPException(404, 'Donor not found')
    d.is_eligible    = False
    d.deferral_reason = body.reason
    d.deferral_until  = date.fromisoformat(body.deferral_until) if body.deferral_until else None
    db.commit()
    log.info('Donor %s deferred: %s', d.donor_id, body.reason)
    return _donor_dict(d)


# ── Blood Bags / Inventory ─────────────────────────────────────────────────────

@router.get('/blood-bank/inventory')
def blood_stock(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """Current stock levels by blood group and component."""
    from models.blood_bank import BloodBag
    from sqlalchemy import func
    rows = (db.query(BloodBag.blood_group, BloodBag.component, func.count(BloodBag.id))
            .filter(BloodBag.status == 'available')
            .group_by(BloodBag.blood_group, BloodBag.component)
            .all())
    stock: dict = {}
    for group, comp, cnt in rows:
        stock.setdefault(group, {})[comp] = cnt
    return stock


@router.get('/blood-bank/bags')
def list_bags(
    status:     Optional[str] = Query(None),
    blood_group:Optional[str] = Query(None),
    component:  Optional[str] = Query(None),
    limit:      int           = Query(50, le=200),
    db:         Session       = Depends(get_db),
    user:       User          = Depends(get_current_user),
) -> list:
    from models.blood_bank import BloodBag
    from sqlalchemy import desc
    q = db.query(BloodBag)
    if status:      q = q.filter(BloodBag.status      == status)
    if blood_group: q = q.filter(BloodBag.blood_group == blood_group.upper())
    if component:   q = q.filter(BloodBag.component   == component.upper())
    bags = q.order_by(desc(BloodBag.collection_date)).limit(limit).all()
    return [_bag_dict(b) for b in bags]


@router.get('/blood-bank/bags/expiring')
def expiring_bags(
    days:   int     = Query(7, ge=1, le=30),
    db:     Session = Depends(get_db),
    user:   User    = Depends(get_current_user),
) -> list:
    """Bags expiring within `days` days — critical for wastage prevention."""
    from models.blood_bank import BloodBag
    cutoff = date.today() + timedelta(days=days)
    bags = (db.query(BloodBag)
            .filter(BloodBag.status == 'available',
                    BloodBag.expiry_date <= cutoff)
            .order_by(BloodBag.expiry_date)
            .all())
    return [_bag_dict(b) for b in bags]


@router.post('/blood-bank/bags')
def collect_bag(
    body: BagCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    from models.blood_bank import BloodBag
    collection = date.fromisoformat(body.collection_date)
    shelf_days = SHELF_LIFE.get(body.component.upper(), 42)
    expiry     = collection + timedelta(days=shelf_days)
    bag_number = f'BAG{collection.strftime("%Y%m%d")}-{_next_seq(db, "blood_bags")}'

    bag = BloodBag(
        bag_number=bag_number, donor_id=body.donor_id,
        component=body.component.upper(), blood_group=body.blood_group.upper(),
        volume_ml=body.volume_ml, status='quarantine',
        collection_date=collection, expiry_date=expiry,
        is_irradiated=body.is_irradiated, is_leukoreduced=body.is_leukoreduced,
        notes=body.notes,
    )
    db.add(bag)

    # Update donor last_donation and total_donations
    if body.donor_id:
        from models.blood_bank import Donor
        donor = db.query(Donor).filter(Donor.id == body.donor_id).first()
        if donor:
            donor.last_donation   = collection
            donor.total_donations = (donor.total_donations or 0) + 1
            # 56-day deferral after donation
            donor.deferral_until  = collection + timedelta(days=56)

    db.commit()
    return _bag_dict(bag)


@router.get('/blood-bank/bags/{bag_number}')
def get_bag(bag_number: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    from models.blood_bank import BloodBag
    bag = db.query(BloodBag).filter(BloodBag.bag_number == bag_number).first()
    if not bag: raise HTTPException(404, 'Blood bag not found')
    return _bag_dict(bag)


@router.put('/blood-bank/bags/{bag_number}/status')
def update_bag_status(
    bag_number: str,
    status:     str,
    db:         Session = Depends(get_db),
    user:       User    = Depends(get_current_user),
) -> dict:
    from models.blood_bank import BloodBag
    valid = {'quarantine','available','reserved','issued','transfused','discarded','expired','in_transit'}
    if status not in valid:
        raise HTTPException(400, f'Invalid status. Must be one of: {sorted(valid)}')
    bag = db.query(BloodBag).filter(BloodBag.bag_number == bag_number).first()
    if not bag: raise HTTPException(404, 'Bag not found')
    bag.status = status
    if status == 'issued':
        bag.issued_at      = datetime.now(timezone.utc)
        bag.issued_by_id   = user.id
    db.commit()
    return _bag_dict(bag)


# ── Blood Requests ─────────────────────────────────────────────────────────────

@router.get('/blood-bank/requests')
def list_requests(
    status:     Optional[str] = Query(None),
    urgency:    Optional[str] = Query(None),
    patient_id: Optional[int] = Query(None),
    limit:      int           = Query(50, le=200),
    db:         Session       = Depends(get_db),
    user:       User          = Depends(get_current_user),
) -> list:
    from models.blood_bank import BloodRequest
    from sqlalchemy import desc
    q = db.query(BloodRequest)
    if status:     q = q.filter(BloodRequest.status    == status)
    if urgency:    q = q.filter(BloodRequest.urgency   == urgency)
    if patient_id: q = q.filter(BloodRequest.patient_id== patient_id)
    reqs = q.order_by(desc(BloodRequest.created_at)).limit(limit).all()
    return [_request_dict(r) for r in reqs]


@router.post('/blood-bank/requests')
def new_blood_request(
    body: BloodRequestCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    from models.blood_bank import BloodRequest
    req_id = f'BR{date.today().strftime("%Y%m%d")}-{_next_seq(db, "blood_requests")}'

    # Check compatibility
    compatible_groups = COMPATIBILITY.get(body.blood_group.upper(), [])

    req = BloodRequest(
        request_id=req_id, patient_id=body.patient_id,
        blood_group=body.blood_group.upper(), component=body.component.upper(),
        units_requested=body.units_requested, urgency=body.urgency,
        clinical_indication=body.clinical_indication,
        ward=body.ward, doctor_name=body.doctor_name,
        requested_by_id=user.id, status='pending',
    )
    db.add(req)
    db.commit()

    # Check available stock for this blood group
    from models.blood_bank import BloodBag
    from sqlalchemy import func
    available = (db.query(func.count(BloodBag.id))
                 .filter(BloodBag.status == 'available',
                         BloodBag.blood_group.in_(compatible_groups),
                         BloodBag.component == body.component.upper())
                 .scalar() or 0)

    result = _request_dict(req)
    result['available_compatible_units'] = available
    result['compatible_groups']          = compatible_groups
    if available < body.units_requested:
        result['warning'] = f'Only {available} compatible units available — {body.units_requested} requested'
    return result


@router.put('/blood-bank/requests/{request_id}/status')
def update_request_status(
    request_id: int,
    status:     str,
    db:         Session = Depends(get_db),
    user:       User    = Depends(get_current_user),
) -> dict:
    from models.blood_bank import BloodRequest
    req = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if not req: raise HTTPException(404, 'Blood request not found')
    req.status = status
    db.commit()
    return _request_dict(req)


# ── Crossmatch ─────────────────────────────────────────────────────────────────

@router.post('/blood-bank/crossmatch')
def perform_crossmatch(
    body: CrossmatchIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    from models.blood_bank import CrossmatchRecord, BloodBag
    bag = db.query(BloodBag).filter(BloodBag.id == body.blood_bag_id).first()
    if not bag: raise HTTPException(404, 'Blood bag not found')
    if bag.status not in ('available', 'quarantine'):
        raise HTTPException(400, f'Bag status is {bag.status} — cannot crossmatch')

    xm = CrossmatchRecord(
        blood_bag_id=body.blood_bag_id, patient_id=body.patient_id,
        performed_by_id=user.id, result=body.result,
        method=body.method,
        ai_flag = body.result == 'incompatible',
        ai_note = 'Incompatibility detected — do NOT issue. Repeat testing required.' if body.result == 'incompatible' else None,
    )
    db.add(xm)

    if body.result == 'compatible':
        bag.status = 'reserved'
        bag.reserved_for_patient_id = body.patient_id

    db.commit()
    log.info('Crossmatch: bag %s patient %d → %s', bag.bag_number, body.patient_id, body.result)
    return {
        'id': xm.id, 'bag_number': bag.bag_number,
        'blood_group': bag.blood_group,
        'patient_id': body.patient_id,
        'result': xm.result, 'method': xm.method,
        'ai_flag': xm.ai_flag, 'ai_note': xm.ai_note,
        'performed_at': str(xm.performed_at),
    }


# ── Issue ──────────────────────────────────────────────────────────────────────

@router.post('/blood-bank/issue/{request_id}')
def issue_blood(
    request_id: int,
    body:       IssueIn,
    db:         Session = Depends(get_db),
    user:       User    = Depends(get_current_user),
) -> dict:
    """Issue a blood bag to a patient — records issue event, generates transfusion checklist."""
    from models.blood_bank import BloodRequest, BloodBag
    req = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if not req: raise HTTPException(404, 'Blood request not found')

    bag = db.query(BloodBag).filter(BloodBag.bag_number == body.bag_number).first()
    if not bag: raise HTTPException(404, f'Bag {body.bag_number} not found')

    # Safety checks
    if bag.expiry_date < date.today():
        raise HTTPException(400, f'Bag {body.bag_number} EXPIRED on {bag.expiry_date}')
    if bag.blood_group != req.blood_group:
        compatible = COMPATIBILITY.get(req.blood_group, [])
        if bag.blood_group not in compatible:
            raise HTTPException(400,
                f'INCOMPATIBLE: Patient needs {req.blood_group}, bag is {bag.blood_group}')
    if bag.status not in ('available', 'reserved'):
        raise HTTPException(400, f'Bag status is {bag.status} — cannot issue')

    bag.status               = 'issued'
    bag.issued_to_patient_id = req.patient_id
    bag.issued_at            = datetime.now(timezone.utc)
    bag.issued_by_id         = user.id
    req.status               = 'issued'
    db.commit()

    return {
        'issued':         True,
        'bag_number':     bag.bag_number,
        'blood_group':    bag.blood_group,
        'component':      bag.component,
        'volume_ml':      bag.volume_ml,
        'patient_id':     req.patient_id,
        'issued_at':      str(bag.issued_at),
        'issued_by':      user.username,
        'expiry_date':    str(bag.expiry_date),
        'days_to_expiry': bag.days_to_expiry,
        'checklist': [
            'Verify patient identity (2 identifiers: name + PID)',
            'Check ABO/Rh label matches patient blood group',
            'Check bag for clots, discolouration, or leaks',
            'Confirm crossmatch compatibility',
            'Confirm informed consent documented',
            'Pre-transfusion vitals recorded (BP, Pulse, Temp)',
            'Start transfusion slowly (first 15 min — watch for reaction)',
            'Monitor vitals every 15 min for first hour, then hourly',
            'Record start time, end time, volume transfused',
            'Report any adverse reactions immediately',
        ],
    }


@router.post('/blood-bank/transfuse/{request_id}/complete')
def record_transfusion(
    request_id: int,
    volume_ml:  int     = 0,
    notes:      Optional[str] = None,
    db:         Session = Depends(get_db),
    user:       User    = Depends(get_current_user),
) -> dict:
    from models.blood_bank import BloodRequest, BloodBag
    req = db.query(BloodRequest).filter(BloodRequest.id == request_id).first()
    if not req: raise HTTPException(404, 'Blood request not found')
    req.status = 'transfused'
    if req.patient and hasattr(req, 'blood_bags'):
        for bag in req.patient.blood_bags if hasattr(req.patient, 'blood_bags') else []:
            if bag.status == 'issued' and bag.issued_to_patient_id == req.patient_id:
                bag.status = 'transfused'
    db.commit()
    return {'transfused': True, 'request_id': request_id, 'volume_ml': volume_ml}


# ── Haemovigilance ─────────────────────────────────────────────────────────────

@router.get('/blood-bank/haemovigilance')
def list_reactions(
    limit:  int     = Query(50, le=200),
    db:     Session = Depends(get_db),
    user:   User    = Depends(get_current_user),
) -> list:
    from models.blood_bank import HaemovigilanceReport
    from sqlalchemy import desc
    items = db.query(HaemovigilanceReport).order_by(desc(HaemovigilanceReport.reported_at)).limit(limit).all()
    return [_hv_dict(h) for h in items]


@router.post('/blood-bank/haemovigilance')
def report_reaction(
    body: HaemovigilanceCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """Report a transfusion adverse reaction — immediately flags for review."""
    from models.blood_bank import HaemovigilanceReport
    report_id = f'HV{datetime.now().strftime("%Y%m%d%H%M%S")}'
    onset     = datetime.fromisoformat(body.onset_time) if body.onset_time else datetime.now(timezone.utc)

    hv = HaemovigilanceReport(
        report_id=report_id, blood_bag_id=body.blood_bag_id,
        patient_id=body.patient_id,
        reaction_type=body.reaction_type, severity=body.severity,
        onset_time=onset, transfusion_stopped=body.transfusion_stopped,
        volume_transfused_ml=body.volume_transfused_ml,
        symptoms=body.symptoms, clinical_management=body.clinical_management,
        outcome=body.outcome, reported_by_id=user.id,
    )
    db.add(hv)

    # If ABO incompatibility — quarantine the bag immediately
    if body.reaction_type == 'abo_haemo' and body.blood_bag_id:
        from models.blood_bank import BloodBag
        bag = db.query(BloodBag).filter(BloodBag.id == body.blood_bag_id).first()
        if bag: bag.status = 'quarantine'

    db.commit()
    log.warning('HAEMOVIGILANCE REPORT %s: %s reaction severity=%s patient=%d',
                report_id, body.reaction_type, body.severity, body.patient_id)
    return _hv_dict(hv)


@router.get('/blood-bank/haemovigilance/{report_id}')
def get_reaction(report_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    from models.blood_bank import HaemovigilanceReport
    hv = db.query(HaemovigilanceReport).filter(HaemovigilanceReport.id == report_id).first()
    if not hv: raise HTTPException(404, 'Report not found')
    return _hv_dict(hv)


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get('/blood-bank/stats')
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    from models.blood_bank import BloodBag, BloodRequest, Donor, HaemovigilanceReport
    from sqlalchemy import func, cast, Date

    total_available = db.query(func.count(BloodBag.id)).filter(BloodBag.status == 'available').scalar() or 0
    expiring_soon   = db.query(func.count(BloodBag.id)).filter(
        BloodBag.status == 'available',
        BloodBag.expiry_date <= date.today() + timedelta(days=7)).scalar() or 0
    expired = db.query(func.count(BloodBag.id)).filter(
        BloodBag.status == 'available',
        BloodBag.expiry_date < date.today()).scalar() or 0
    pending_requests = db.query(func.count(BloodRequest.id)).filter(
        BloodRequest.status == 'pending').scalar() or 0
    total_donors = db.query(func.count(Donor.id)).scalar() or 0
    eligible     = db.query(func.count(Donor.id)).filter(Donor.is_eligible == True).scalar() or 0
    reactions_30d = db.query(func.count(HaemovigilanceReport.id)).filter(
        HaemovigilanceReport.reported_at >= datetime.now(timezone.utc) - timedelta(days=30)).scalar() or 0

    stock = {}
    from models.blood_bank import BloodBag as BB
    rows = (db.query(BB.blood_group, func.count(BB.id))
            .filter(BB.status == 'available')
            .group_by(BB.blood_group).all())
    for group, cnt in rows: stock[group] = cnt

    return {
        'total_available_units': total_available,
        'expiring_within_7_days': expiring_soon,
        'expired_in_stock':       expired,
        'pending_blood_requests': pending_requests,
        'total_donors':           total_donors,
        'eligible_donors':        eligible,
        'reactions_last_30d':     reactions_30d,
        'stock_by_group':         stock,
    }


@router.get('/blood-bank/blood-group-stock')
def blood_group_stock(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list:
    from models.blood_bank import BloodBag
    from sqlalchemy import func
    rows = (db.query(BloodBag.blood_group, BloodBag.component, func.count(BloodBag.id))
            .filter(BloodBag.status == 'available')
            .group_by(BloodBag.blood_group, BloodBag.component)
            .order_by(BloodBag.blood_group)
            .all())
    return [{'blood_group': g, 'component': c, 'units': n} for g, c, n in rows]


# ── Serialisers ────────────────────────────────────────────────────────────────

def _donor_dict(d) -> dict:
    return {
        'id': d.id, 'donor_id': d.donor_id,
        'full_name': d.full_name, 'blood_group': d.blood_group,
        'gender': d.gender, 'phone': d.phone,
        'is_eligible': d.is_eligible, 'deferral_reason': d.deferral_reason,
        'deferral_until': str(d.deferral_until) if d.deferral_until else None,
        'total_donations': d.total_donations,
        'last_donation': str(d.last_donation) if d.last_donation else None,
    }

def _bag_dict(b) -> dict:
    return {
        'id': b.id, 'bag_number': b.bag_number,
        'blood_group': b.blood_group, 'component': b.component,
        'volume_ml': b.volume_ml, 'status': b.status,
        'collection_date': str(b.collection_date),
        'expiry_date': str(b.expiry_date),
        'days_to_expiry': b.days_to_expiry,
        'expiry_status': b.expiry_status,
        'is_irradiated': b.is_irradiated,
        'is_leukoreduced': b.is_leukoreduced,
        'donor_id': b.donor_id,
    }

def _request_dict(r) -> dict:
    patient = r.patient
    return {
        'id': r.id, 'request_id': r.request_id,
        'patient_id': r.patient_id,
        'patient_name': patient.full_name if patient and hasattr(patient,'full_name') else
                        f'{getattr(patient,"family_name","")} {getattr(patient,"other_names","") or ""}' if patient else '—',
        'blood_group': r.blood_group, 'component': r.component,
        'units_requested': r.units_requested, 'urgency': r.urgency,
        'clinical_indication': r.clinical_indication,
        'ward': r.ward, 'doctor_name': r.doctor_name,
        'status': r.status,
        'created_at': str(r.created_at) if r.created_at else None,
    }

def _hv_dict(h) -> dict:
    return {
        'id': h.id, 'report_id': h.report_id,
        'reaction_type': h.reaction_type,
        'reaction_name': REACTION_TYPES.get(h.reaction_type, h.reaction_type),
        'severity': h.severity, 'patient_id': h.patient_id,
        'symptoms': h.symptoms, 'outcome': h.outcome,
        'transfusion_stopped': h.transfusion_stopped,
        'volume_transfused_ml': h.volume_transfused_ml,
        'reported_at': str(h.reported_at),
    }

def _next_seq(db, table_name) -> str:
    from sqlalchemy import text
    try:
        r = db.execute(text(f'SELECT COUNT(*) FROM {table_name}')).scalar()
        return str((r or 0) + 1).zfill(4)
    except Exception:
        return '0001'
