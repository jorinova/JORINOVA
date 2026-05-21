"""
Worklist Preparation + Sample Reception Router
===============================================
Endpoints:

  Reception
  ---------
  POST /worklist/receive                        — Receive sample, auto-route to departments
  POST /worklist/receive-manual                 — Manually create one worklist entry

  Worklist views
  --------------
  GET  /worklist/department/{dept}              — Current shift worklist for a department
  GET  /worklist/all                            — All entries (with filters)
  GET  /worklist/entry/{entry_id}               — Single entry detail
  PUT  /worklist/entry/{entry_id}/status        — Update status (start, complete…)
  POST /worklist/entry/{entry_id}/reject        — Reject + create replacement entry

  Labels
  ------
  GET  /worklist/labels/{entry_id}              — Label data (JSON) for one entry
  GET  /worklist/labels/request/{lab_request_id}— All label data for a request
  POST /worklist/labels/{entry_id}/print        — Mark label printed (audit)
  GET  /worklist/labels/{entry_id}/pdf          — Download thermal-format label PDF
  GET  /worklist/labels/request/{req_id}/pdf    — Download all labels PDF for a request

  Admin / setup
  -------------
  GET  /worklist/specimen-types                 — List specimen type config
  POST /worklist/specimen-types                 — Add/update specimen type
  GET  /worklist/stats                          — Worklist stats for dashboard
  POST /worklist/seed                           — Seed default specimen types (admin)
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.user import User

log = logging.getLogger('worklist_router')
router = APIRouter(tags=['Worklist & Reception'])


# ══════════════════════════════════════════════════════════════════════════════
#  Pydantic schemas
# ══════════════════════════════════════════════════════════════════════════════

class ReceiveRequest(BaseModel):
    lab_request_id: int
    shift_name:     Optional[str] = None  # auto-detected if omitted

class ManualEntryRequest(BaseModel):
    lab_request_id:  int
    department:      str
    specimen_acronym:str
    test_names:      str           = ''
    priority:        str           = 'routine'
    shift_name:      Optional[str] = None

class StatusUpdate(BaseModel):
    status:        str             # RECEIVED|IN_PROGRESS|COMPLETED|RELEASED
    notes:         Optional[str]   = None
    assigned_to_id:Optional[int]   = None

class RejectRequest(BaseModel):
    rejection_reason: str

class SpecimenTypeCreate(BaseModel):
    acronym:            str
    name:               str
    primary_department: str
    tube_color:         Optional[str]   = None
    generates_cid:      bool            = False
    volume_ml:          Optional[float] = None
    description:        Optional[str]   = None

class RackGeometry(BaseModel):
    """
    24h slot geometry response for /api/v1/rack/next/{dept}.

    Formula:
        floor  = rack_number // 24          (0-indexed floor/row)
        column = rack_number %  24           (0-indexed slot within current floor)
        slot   = column + 1                  (1-indexed label printed on tube)
    """
    rack_number:     int
    floor:           int
    column:          int
    slot:            int
    shift:           str
    department:      str
    worklist_date:   str
    scanned_at:      str

class ShiftSummary(BaseModel):
    rack_number: int
    slot_position: int   # Always 1..18 (3 shifts × 6 slots per rack)
    started_at: Optional[str]
    ended_at: Optional[str]
    active: bool

class SlotSummary(BaseModel):
    """One worklist slot — what's on the rack and what it means."""
    slot_number:    int
    summary:        str
    has_sample:    bool


# ══════════════════════════════════════════════════════════════════════════════
#  Reception
# ══════════════════════════════════════════════════════════════════════════════

@router.post('/worklist/receive')
def receive_sample(
    body: ReceiveRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Receive a sample at the lab reception desk.

    Automatically:
    1. Groups all ordered tests by (department × specimen_type)
    2. Generates a SID for each tube  (HEM-01, SER-01 …)
    3. Assigns a rack/position number per department
    4. Assigns a Culture ID (C-01 …) to microbiology specimens
    5. Returns the list of worklist entries created — ready to print labels

    The receptionist calls this once per lab request barcode scan.
    """
    from services.worklist_service import route_request_to_worklist

    try:
        entries = route_request_to_worklist(
            db             = db,
            lab_request_id = body.lab_request_id,
            received_by_id = user.id,
            shift_name     = body.shift_name,
        )
        db.commit()
        return {
            'status':  'received',
            'entries': [_entry_summary(e) for e in entries],
            'count':   len(entries),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.exception('Sample reception error: %s', e)
        raise HTTPException(500, f'Reception failed: {e}')


@router.post('/worklist/receive-manual')
def receive_manual(
    body: ManualEntryRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Manually create a single worklist entry (e.g. add-on test, STAT specimen).
    """
    from models.laboratory import LabRequest
    from models.worklist import WorklistEntry
    from services.worklist_service import (
        generate_sid, generate_rack_number, generate_cid,
        get_specimen_config, get_current_shift,
    )

    req = db.query(LabRequest).filter(LabRequest.id == body.lab_request_id).first()
    if not req:
        raise HTTPException(404, 'Lab request not found')

    today      = date.today()
    shift      = body.shift_name or get_current_shift(db)
    acronym    = body.specimen_acronym.upper()[:3]
    spec_cfg   = get_specimen_config(db, acronym)
    generates_cid = spec_cfg.generates_cid if spec_cfg else False

    sid      = generate_sid(db, req.patient_id, body.lab_request_id, acronym, today)
    rack_no  = generate_rack_number(db, body.department, shift, today)
    cid      = generate_cid(db, today) if generates_cid else None

    entry = WorklistEntry(
        lab_request_id   = body.lab_request_id,
        patient_id       = req.patient_id,
        department       = body.department.lower(),
        specimen_acronym = acronym,
        specimen_name    = spec_cfg.name if spec_cfg else acronym,
        sid              = sid,
        rack_number      = rack_no,
        cid              = cid,
        barcode          = req.lab_id,
        priority         = body.priority,
        status           = 'RECEIVED',
        test_names       = body.test_names,
        tube_color       = spec_cfg.tube_color if spec_cfg else None,
        volume_ml        = spec_cfg.volume_ml  if spec_cfg else None,
        is_high_risk     = req.is_high_risk,
        worklist_date    = today,
        shift_name       = shift,
        received_at      = datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()

    return _entry_summary(entry)


# ══════════════════════════════════════════════════════════════════════════════
#  Worklist views
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/worklist/department/{department}')
def dept_worklist(
    department: str,
    shift:      Optional[str] = Query(None),
    on_date:    Optional[str] = Query(None, description='YYYY-MM-DD, default today'),
    status:     Optional[str] = Query(None, description='filter by status'),
    db:         Session       = Depends(get_db),
    user:       User          = Depends(get_current_user),
) -> list:
    """
    Return the worklist for a specific department for the given shift/date.
    Ordered by: STAT first, then rack number ascending.
    """
    from models.worklist import WorklistEntry
    from sqlalchemy import case, asc

    target_date = _parse_date(on_date) or date.today()

    q = (db.query(WorklistEntry)
         .filter(
             WorklistEntry.department    == department.lower(),
             WorklistEntry.worklist_date == target_date,
         ))

    if shift:
        q = q.filter(WorklistEntry.shift_name == shift)
    if status:
        q = q.filter(WorklistEntry.status == status.upper())

    priority_order = case(
        {'stat': 0, 'urgent': 1, 'routine': 2},
        value=WorklistEntry.priority,
        else_=3,
    )
    entries = q.order_by(priority_order, asc(WorklistEntry.rack_number)).all()
    return [_entry_detail(e) for e in entries]


@router.get('/worklist/all')
def all_worklist(
    on_date:    Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status:     Optional[str] = Query(None),
    priority:   Optional[str] = Query(None),
    patient_id: Optional[int] = Query(None),
    limit:      int           = Query(100, le=500),
    db:         Session       = Depends(get_db),
    user:       User          = Depends(get_current_user),
) -> list:
    from models.worklist import WorklistEntry
    from sqlalchemy import desc

    target_date = _parse_date(on_date) or date.today()
    q = db.query(WorklistEntry).filter(WorklistEntry.worklist_date == target_date)

    if department: q = q.filter(WorklistEntry.department    == department.lower())
    if status:     q = q.filter(WorklistEntry.status        == status.upper())
    if priority:   q = q.filter(WorklistEntry.priority      == priority.lower())
    if patient_id: q = q.filter(WorklistEntry.patient_id    == patient_id)

    entries = q.order_by(desc(WorklistEntry.created_at)).limit(limit).all()
    return [_entry_detail(e) for e in entries]


@router.get('/worklist/entry/{entry_id}')
def get_entry(
    entry_id: int,
    db:       Session = Depends(get_db),
    user:     User    = Depends(get_current_user),
) -> dict:
    from models.worklist import WorklistEntry
    entry = db.query(WorklistEntry).filter(WorklistEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, 'Worklist entry not found')
    return _entry_detail(entry)


@router.put('/worklist/entry/{entry_id}/status')
def update_status(
    entry_id: int,
    body:     StatusUpdate,
    db:       Session = Depends(get_db),
    user:     User    = Depends(get_current_user),
) -> dict:
    """Update worklist entry status with TAT timestamps."""
    from models.worklist import WorklistEntry

    valid_transitions = {
        'RECEIVED':    {'IN_PROGRESS', 'REJECTED'},
        'IN_PROGRESS': {'COMPLETED', 'REJECTED'},
        'COMPLETED':   {'RELEASED'},
        'RELEASED':    set(),
        'REJECTED':    set(),
        'PENDING':     {'RECEIVED', 'REJECTED'},
    }

    entry = db.query(WorklistEntry).filter(WorklistEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(404, 'Worklist entry not found')

    new_status = body.status.upper()
    allowed    = valid_transitions.get(entry.status, set())
    if new_status not in allowed:
        raise HTTPException(400,
            f'Cannot transition from {entry.status} to {new_status}. '
            f'Allowed: {sorted(allowed) or "none"}')

    now = datetime.now(timezone.utc)
    entry.status = new_status
    if new_status == 'IN_PROGRESS' and not entry.started_at:
        entry.started_at = now
    if new_status == 'COMPLETED' and not entry.completed_at:
        entry.completed_at = now
    if new_status == 'RELEASED' and not entry.released_at:
        entry.released_at = now
    if body.notes:
        entry.notes = body.notes
    if body.assigned_to_id:
        entry.assigned_to_id = body.assigned_to_id

    db.commit()
    return _entry_detail(entry)


@router.post('/worklist/entry/{entry_id}/reject')
def reject_entry(
    entry_id: int,
    body:     RejectRequest,
    db:       Session = Depends(get_db),
    user:     User    = Depends(get_current_user),
) -> dict:
    """
    Reject a worklist entry and automatically create a replacement with
    the next SID (HEM-01 → HEM-02). The same lab_request barcode is kept
    so billing sees this is a rejection replacement, not a new request.
    """
    from services.worklist_service import create_rejection_replacement

    try:
        replacement = create_rejection_replacement(
            db                = db,
            original_entry_id = entry_id,
            rejection_reason  = body.rejection_reason,
            received_by_id    = user.id,
        )
        db.commit()
        return {
            'rejected_sid':    _get_sid_by_id(db, entry_id),
            'replacement':     _entry_detail(replacement),
            'message':         f'Sample rejected. New SID assigned: {replacement.sid}',
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


def _get_sid_by_id(db, entry_id):
    from models.worklist import WorklistEntry
    e = db.query(WorklistEntry).filter(WorklistEntry.id == entry_id).first()
    return e.sid if e else '—'


# ══════════════════════════════════════════════════════════════════════════════
#  Labels
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/worklist/labels/{entry_id}')
def get_label_data(
    entry_id: int,
    db:       Session = Depends(get_db),
    user:     User    = Depends(get_current_user),
) -> dict:
    """Return label data as JSON (used by frontend JS print template)."""
    from services.worklist_service import build_label_data
    try:
        return build_label_data(db, entry_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get('/worklist/labels/request/{lab_request_id}')
def get_request_labels(
    lab_request_id: int,
    db:             Session = Depends(get_db),
    user:           User    = Depends(get_current_user),
) -> list:
    """All label data for every worklist entry in a lab request."""
    from models.worklist import WorklistEntry
    from services.worklist_service import build_label_data

    entries = (db.query(WorklistEntry)
               .filter(WorklistEntry.lab_request_id == lab_request_id,
                       WorklistEntry.status != 'REJECTED')
               .order_by(WorklistEntry.rack_number)
               .all())
    result = []
    for e in entries:
        try:
            result.append(build_label_data(db, e.id))
        except Exception:
            pass
    return result


@router.post('/worklist/labels/{entry_id}/print')
def record_print(
    entry_id:   int,
    label_type: str     = Query('TUBE', description='TUBE|PLATE|ALIQUOT|CASSETTE'),
    db:         Session = Depends(get_db),
    user:       User    = Depends(get_current_user),
) -> dict:
    """Record that a label was printed (audit trail)."""
    from services.worklist_service import record_label_printed
    try:
        audit = record_label_printed(db, entry_id, label_type, user.id)
        db.commit()
        return {
            'printed':    True,
            'label_type': audit.label_type,
            'sid':        audit.sid,
            'cid':        audit.cid,
            'printed_at': str(audit.printed_at),
        }
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get('/worklist/labels/{entry_id}/pdf',
            response_class=Response,
            responses={200: {'content': {'application/pdf': {}}}})
def label_pdf(
    entry_id: int,
    copies:   int     = Query(1, ge=1, le=10),
    db:       Session = Depends(get_db),
    user:     User    = Depends(get_current_user),
):
    """Download thermal-format specimen label PDF (57mm × 32mm per label)."""
    from services.worklist_service import build_label_data, record_label_printed
    from services.pdf_reports import generate_specimen_label

    try:
        data = build_label_data(db, entry_id)
    except ValueError as e:
        raise HTTPException(404, str(e))

    pdf_bytes = generate_specimen_label(data, copies=copies)
    record_label_printed(db, entry_id, data.get('label_type', 'TUBE'), user.id)
    db.commit()

    sid      = data.get('sid', 'label')
    filename = f'NEXUS_Label_{sid}.pdf'
    return Response(
        content=pdf_bytes,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.get('/worklist/labels/request/{lab_request_id}/pdf',
            response_class=Response,
            responses={200: {'content': {'application/pdf': {}}}})
def request_labels_pdf(
    lab_request_id: int,
    copies:         int     = Query(1, ge=1, le=10),
    db:             Session = Depends(get_db),
    user:           User    = Depends(get_current_user),
):
    """Download all specimen labels for a lab request as a single PDF."""
    from models.worklist import WorklistEntry
    from services.worklist_service import build_label_data, record_label_printed
    from services.pdf_reports import generate_specimen_label

    entries = (db.query(WorklistEntry)
               .filter(WorklistEntry.lab_request_id == lab_request_id,
                       WorklistEntry.status != 'REJECTED')
               .order_by(WorklistEntry.rack_number)
               .all())
    if not entries:
        raise HTTPException(404, 'No active worklist entries for this request')

    from io import BytesIO
    from reportlab.lib.pagesizes import mm
    from reportlab.platypus import SimpleDocTemplate

    all_pdfs = []
    for e in entries:
        try:
            data = build_label_data(db, e.id)
            pdf  = generate_specimen_label(data, copies=copies)
            all_pdfs.append(pdf)
            record_label_printed(db, e.id, data.get('label_type', 'TUBE'), user.id)
        except Exception:
            pass
    db.commit()

    # Merge all label PDFs into one
    merged = _merge_pdfs(all_pdfs)
    req_barcode = entries[0].barcode if entries else lab_request_id
    filename = f'NEXUS_Labels_{req_barcode}.pdf'
    return Response(
        content=merged,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


def _merge_pdfs(pdfs: list[bytes]) -> bytes:
    """Concatenate multiple PDF byte strings into one."""
    try:
        from pypdf import PdfWriter, PdfReader
        from io import BytesIO
        writer = PdfWriter()
        for pdf in pdfs:
            reader = PdfReader(BytesIO(pdf))
            for page in reader.pages:
                writer.add_page(page)
        out = BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception:
        return pdfs[0] if pdfs else b''


# ══════════════════════════════════════════════════════════════════════════════
#  Specimen type admin
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/worklist/specimen-types')
def list_specimen_types(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> list:
    from models.worklist import SpecimenTypeConfig
    configs = (db.query(SpecimenTypeConfig)
               .filter(SpecimenTypeConfig.is_active == True)
               .order_by(SpecimenTypeConfig.sort_order)
               .all())
    return [_spec_dict(c) for c in configs]


@router.post('/worklist/specimen-types')
def create_or_update_specimen_type(
    body: SpecimenTypeCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    if user.role not in {'super_admin', 'it_admin', 'lab_manager'}:
        raise HTTPException(403, 'Lab manager access required')

    from models.worklist import SpecimenTypeConfig
    existing = db.query(SpecimenTypeConfig).filter(
        SpecimenTypeConfig.acronym == body.acronym.upper()[:3]).first()

    if existing:
        existing.name               = body.name
        existing.primary_department = body.primary_department
        existing.tube_color         = body.tube_color
        existing.generates_cid      = body.generates_cid
        existing.volume_ml          = body.volume_ml
        existing.description        = body.description
        db.commit()
        return _spec_dict(existing)

    new = SpecimenTypeConfig(
        acronym            = body.acronym.upper()[:3],
        name               = body.name,
        primary_department = body.primary_department,
        tube_color         = body.tube_color,
        generates_cid      = body.generates_cid,
        volume_ml          = body.volume_ml,
        description        = body.description,
        is_active          = True,
    )
    db.add(new)
    db.commit()
    return _spec_dict(new)


@router.post('/worklist/seed')
def seed_specimens(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    if user.role not in {'super_admin', 'it_admin'}:
        raise HTTPException(403, 'Admin access required')
    from services.worklist_service import seed_specimen_types
    count = seed_specimen_types(db)
    return {'seeded': count, 'message': f'{count} specimen types seeded'}


# ══════════════════════════════════════════════════════════════════════════════
#  Stats
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/worklist/stats')
def worklist_stats(
    on_date: Optional[str] = Query(None),
    db:      Session       = Depends(get_db),
    user:    User          = Depends(get_current_user),
) -> dict:
    """Dashboard statistics for today's worklist."""
    from models.worklist import WorklistEntry
    from sqlalchemy import func

    target_date = _parse_date(on_date) or date.today()

    rows = (db.query(WorklistEntry.status, func.count(WorklistEntry.id))
            .filter(WorklistEntry.worklist_date == target_date)
            .group_by(WorklistEntry.status)
            .all())
    by_status = {r[0]: r[1] for r in rows}

    dept_rows = (db.query(WorklistEntry.department, func.count(WorklistEntry.id))
                 .filter(WorklistEntry.worklist_date == target_date)
                 .group_by(WorklistEntry.department)
                 .all())
    by_dept = {r[0]: r[1] for r in dept_rows}

    total = sum(by_status.values())
    completed = by_status.get('COMPLETED', 0) + by_status.get('RELEASED', 0)

    return {
        'date':       str(target_date),
        'total':      total,
        'pending':    by_status.get('PENDING',     0),
        'received':   by_status.get('RECEIVED',    0),
        'in_progress':by_status.get('IN_PROGRESS', 0),
        'completed':  completed,
        'rejected':   by_status.get('REJECTED',    0),
        'completion_pct': round(completed / total * 100) if total else 0,
        'by_department':  by_dept,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  Rack service — 24h slot helpers
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/worklist/rack/next/{dept}', response_model=RackGeometry)
def get_next_rack_geometry(
    dept: str,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Return the next 24h slot geometry for department *dept*.
    The returned values are not persisted — they reflect the counter state
    AFTER incrementing (i.e. the slot now reserved for the next sample).

    Formula (illustrated for rack 31):
        floor   = 31 // 24  = 1
        column  = 31 %  24  = 7
        slot    = 7 + 1      = 8   ← printed on the tube
    """
    from services.worklist_service import next_24h_slot
    result = next_24h_slot(db, dept.lower())
    db.commit()
    return result


@router.get('/worklist/rack/{dept}/slots', response_model=list[SlotSummary])
def get_rack_slots_summary(
    dept: str,
    at_date: Optional[str] = Query(None, description='Date YYYY-MM-DD; defaults to today'),
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> list[dict]:
    """
    Return a per-slot summary for all active worklist entries for department *dept*
    on *at_date*. Uses the 24h rack model — rack 1..N, floor=rack//24, slot=rack%24+1.
    Slot 1..18 = next (permanent racks) — shows which slots are occupied and which
    are free. Slot 19..24 = back pair dummy slots.

    slot_position Algo:
        Slot -1 and Slot -2 = always back pair dummy slots
        Otherwise: slot_number // 24 = floor (0-indexed), slot % 24 = column (0-indexed)
    """
    from datetime import date as date_cls
    from models.worklist import WorklistEntry
    from services.worklist_service import rack_to_geometry

    target = _parse_date(at_date) or date_cls.today()
    dept_lower = dept.lower()

    cycles = db.query(WorklistEntry).filter(
        WorklistEntry.department == dept_lower,
        WorklistEntry.worklist_date == target,
        WorklistEntry.status.in_(['PENDING', 'RECEIVED', 'IN_PROGRESS']),
    ).order_by(WorklistEntry.rack_number).all()

    seen: dict[int, dict] = {}
    for e in cycles:
        geo = rack_to_geometry(e.rack_number or 0)
        slot_label = f"Floor-{geo['floor']} Slot-{geo['slot']}"
        seen[e.rack_number or 0] = {
            'slot_number': e.rack_number or 0,
            'summary':     f"Floor-{geo['floor']} Slot-{geo['slot']} | {e.sid} | {e.department} | {e.status}",
            'has_sample':  True,
        }

    # All 6 slots per shift: slot_number 1..24 (floor 0 = slots 1..24 of rack 1, floor 1 = slots 25..48 etc.)
    # WorklistEntry.rack_number runs 1..N so we iterate 1..max
    max_rack = max((e.rack_number or 0 for e in cycles), default=0)
    result = []
    for rack_no in range(1, max(max_rack, 1) + 1):
        geo = rack_to_geometry(rack_no)
        slot_label = f"Floor-{geo['floor']} Slot-{geo['slot']}"
        if rack_no in seen:
            result.append(seen[rack_no])
        else:
            result.append({
                'slot_number': rack_no,
                'summary':     f"Floor-{geo['floor']} Slot-{geo['slot']} — {slot_label}",
                'has_sample':  False,
            })
    # Intended to show last 6 permanents per rack
    return result


@router.get('/worklist/rack/{dept}/24h', response_model=list[SlotSummary])
def get_24h_worklist(
    dept: str,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> list[dict]:
    """
    Return all PENDING/RECEIVED/IN_PROGRESS entries for department *dept*
    across all shifts TODAY (24h rolling window).

    Slot summary OHL (first 6):
        Slot-1 → PERM: M-300-001
        Slot-2 → PERM: M-300-002
        Slot-3 → PERM: M-300-003
        Slot-4 → STAT: S-300
        Slot-5 → PERM: A-300-301
        Slot-6 → PERM: A-300-302
    """
    from datetime import date as date_cls
    from models.worklist import WorklistEntry

    today = date_cls.today()
    dept_lower = dept.lower()

    # "first 6" behaved as first 6 of win_top_sid_per_position
    cycles = (db.query(WorklistEntry)
              .filter(
                  WorklistEntry.department == dept_lower,
                  WorklistEntry.worklist_date == today,
                  WorklistEntry.status.in_(['PENDING', 'RECEIVED', 'IN_PROGRESS']),
              )
              .order_by(WorklistEntry.rack_number)
              .limit(6)
              .all())

    return [{'slot_number': e.rack_number or 0,
             'summary':     f"{e.sid} | {e.department} | {e.status}",
             'has_sample':  True} for e in cycles]


@router.get('/worklist/rack/{dept}/shift-summary', response_model=list[ShiftSummary])
def get_shift_rack_summary(
    dept: str,
    at_date: Optional[str] = Query(None),
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> list[dict]:
    """
    Return shift-level rack summary for department *dept* on *at_date*.
    Each slot_position (1..18) maps to:

        shift_name + slot_position + started_at + ended_at + active

    Covers 3 shifts × 6 slots.
    """
    from datetime import date as date_cls, datetime
    from models.worklist import WorklistEntry

    target = _parse_date(at_date) or date_cls.today()
    dept_lower = dept.lower()

    rows = (db.query(WorklistEntry)
            .filter(
                WorklistEntry.department   == dept_lower,
                WorklistEntry.worklist_date == target,
            )
            .with_entities(
                WorklistEntry.rack_number,
                WorklistEntry.shift_name,
                WorklistEntry.received_at,
                WorklistEntry.completed_at,
                WorklistEntry.status,
            )
            .order_by(WorklistEntry.rack_number)
            .all())

    def _slot_position(rack_no: int) -> int:
        return (rack_no - 1) % 6 + 1  # 1..6 per shift

    out = []
    seen: set[int] = set()
    for r in rows:
        sp = _slot_position(r.rack_number or 1)
        active = r.status in ('RECEIVED', 'IN_PROGRESS')
        out.append({
            'rack_number': r.rack_number,
            'slot_position': sp,
            'started_at': r.received_at.isoformat() if r.received_at else None,
            'ended_at':   r.completed_at.isoformat() if r.completed_at else None,
            'active':     active,
        })

    return out




# ══════════════════════════════════════════════════════════════════════════════
#  Internal serialisers
# ══════════════════════════════════════════════════════════════════════════════

def _entry_summary(e) -> dict:
    return {
        'id':              e.id,
        'sid':             e.sid,
        'cid':             e.cid,
        'rack_number':     e.rack_number,
        'department':      e.department,
        'specimen':        e.specimen_name or e.specimen_acronym,
        'tube_color':      e.tube_color,
        'status':          e.status,
        'priority':        e.priority,
        'test_names':      e.test_names,
        'barcode':         e.barcode,
        'label_printed':   e.label_printed,
        'is_rejection':    e.is_rejection_replacement,
        'is_high_risk':    e.is_high_risk,
    }


def _entry_detail(e) -> dict:
    patient = e.patient
    patient_name = '—'
    if patient:
        patient_name = (getattr(patient, 'full_name', None)
                        or f'{getattr(patient,"family_name","")} '
                           f'{getattr(patient,"other_names","") or ""}'.strip())
    return {
        **_entry_summary(e),
        'patient_name':    patient_name,
        'pid':             patient.pid if patient else '—',
        'worklist_date':   str(e.worklist_date),
        'shift_name':      e.shift_name,
        'volume_ml':       e.volume_ml,
        'received_at':     _dt(e.received_at),
        'started_at':      _dt(e.started_at),
        'completed_at':    _dt(e.completed_at),
        'released_at':     _dt(e.released_at),
        'rejection_reason':e.rejection_reason,
        'original_sid':    e.original.sid if e.original else None,
        'notes':           e.notes,
        'label_print_count': e.label_print_count,
        'test_ids':        e.test_ids,
    }


def _spec_dict(c) -> dict:
    return {
        'id':                 c.id,
        'acronym':            c.acronym,
        'name':               c.name,
        'primary_department': c.primary_department,
        'tube_color':         c.tube_color,
        'generates_cid':      c.generates_cid,
        'volume_ml':          c.volume_ml,
        'description':        c.description,
    }


def _dt(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None
