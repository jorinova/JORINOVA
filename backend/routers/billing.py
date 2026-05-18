"""
Billing Router — JORINOVA NEXUS ALIS-X
========================================
Inline reception billing endpoints.

  POST /billing/quick                    — Create billing record inline from reception modal
  GET  /billing/autobill/{lab_request_id}— Suggest billing items from ordered tests + prices
  GET  /billing/search-items             — Quick typeahead for "Other" billing items
  GET  /billing/record/{lab_request_id}  — Fetch billing record for a request
  PUT  /billing/record/{id}/status       — Update payment status
"""
from __future__ import annotations
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.user import User

log = logging.getLogger('billing_router')
router = APIRouter(tags=['Billing'])


# ══════════════════════════════════════════════════════════════════════════════
#  Pydantic schemas
# ══════════════════════════════════════════════════════════════════════════════

class BillingItemIn(BaseModel):
    item_code:      str   = ''
    item_name:      str
    unit_price:     float
    quantity:       int   = 1
    test_id:        Optional[int] = None
    is_auto_billed: bool  = True
    is_waived:      bool  = False
    waiver_reason:  Optional[str] = None

    @field_validator('quantity')
    @classmethod
    def qty_positive(cls, v):
        if v < 1:
            raise ValueError('quantity must be >= 1')
        return v

    @field_validator('unit_price')
    @classmethod
    def price_non_negative(cls, v):
        if v < 0:
            raise ValueError('unit_price must be >= 0')
        return v


class QuickBillRequest(BaseModel):
    lab_request_id: int
    items:          list[BillingItemIn]
    payment_method: Optional[str] = None   # CASH|INSURANCE|RSSB|MOMO|CREDIT
    insurance_name: Optional[str] = None
    insurance_id:   Optional[str] = None
    momo_ref:       Optional[str] = None
    notes:          Optional[str] = None
    auto_confirm:   bool          = True   # If True → status=CONFIRMED immediately


class StatusUpdate(BaseModel):
    status:         str            # CONFIRMED | PAID | CANCELLED
    payment_method: Optional[str] = None
    paid_amount:    Optional[float] = None
    momo_ref:       Optional[str] = None
    notes:          Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
#  Helper: serialisers
# ══════════════════════════════════════════════════════════════════════════════

def _item_dict(item) -> dict:
    return {
        'id':              item.id,
        'item_code':       item.item_code,
        'item_name':       item.item_name,
        'description':     item.description,
        'quantity':        item.quantity,
        'unit_price':      item.unit_price,
        'total_price':     item.total_price,
        'is_auto_billed':  item.is_auto_billed,
        'is_waived':       item.is_waived,
        'waiver_reason':   item.waiver_reason,
        'test_id':         item.test_id,
    }


def _record_dict(rec) -> dict:
    patient = rec.patient
    patient_name = '—'
    if patient:
        patient_name = (getattr(patient, 'full_name', None)
                        or f'{getattr(patient, "family_name", "")} '
                           f'{getattr(patient, "other_names", "") or ""}'.strip())
    return {
        'id':               rec.id,
        'lab_request_id':   rec.lab_request_id,
        'patient_id':       rec.patient_id,
        'patient_name':     patient_name,
        'status':           rec.status,
        'subtotal_amount':  rec.subtotal_amount,
        'discount_amount':  rec.discount_amount,
        'total_amount':     rec.total_amount,
        'paid_amount':      rec.paid_amount,
        'currency':         rec.currency,
        'payment_method':   rec.payment_method,
        'insurance_name':   rec.insurance_name,
        'insurance_id':     rec.insurance_id,
        'momo_ref':         rec.momo_ref,
        'notes':            rec.notes,
        'created_at':       str(rec.created_at),
        'updated_at':       str(rec.updated_at),
        'items':            [_item_dict(i) for i in rec.items],
    }


def _recalc_totals(record, items_data: list[BillingItemIn]) -> float:
    """Recalculate and return total_amount from item list."""
    subtotal = sum(
        it.unit_price * it.quantity
        for it in items_data
        if not it.is_waived
    )
    record.subtotal_amount = round(subtotal, 2)
    record.total_amount    = round(subtotal - record.discount_amount, 2)
    return record.total_amount


# ══════════════════════════════════════════════════════════════════════════════
#  POST /billing/quick
# ══════════════════════════════════════════════════════════════════════════════

@router.post('/billing/quick')
def create_quick_billing(
    body: QuickBillRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Create (or replace) a billing record from the reception inline modal.
    If a DRAFT record already exists for this lab_request, it is replaced.
    """
    from models.billing import BillingRecord, BillingItem
    from models.laboratory import LabRequest

    req = db.query(LabRequest).filter(LabRequest.id == body.lab_request_id).first()
    if not req:
        raise HTTPException(404, 'Lab request not found')

    # If a DRAFT already exists for this request, replace it
    existing = (db.query(BillingRecord)
                .filter(BillingRecord.lab_request_id == body.lab_request_id,
                        BillingRecord.status == 'DRAFT')
                .first())
    if existing:
        # Delete old items
        for old_item in existing.items:
            db.delete(old_item)
        db.flush()
        record = existing
    else:
        record = BillingRecord(
            lab_request_id  = body.lab_request_id,
            patient_id      = req.patient_id,
            created_by_id   = user.id,
            currency        = 'RWF',
            discount_amount = 0.0,
        )
        db.add(record)
        db.flush()  # get record.id

    # Set payment info
    record.payment_method = body.payment_method
    record.insurance_name = body.insurance_name
    record.insurance_id   = body.insurance_id
    record.momo_ref       = body.momo_ref
    record.notes          = body.notes

    # Create line items
    for it in body.items:
        line_total = round(it.unit_price * it.quantity, 2)
        item = BillingItem(
            billing_record_id = record.id,
            test_id           = it.test_id,
            lab_request_id    = body.lab_request_id,
            item_code         = it.item_code or '',
            item_name         = it.item_name,
            quantity          = it.quantity,
            unit_price        = round(it.unit_price, 2),
            total_price       = line_total,
            is_auto_billed    = it.is_auto_billed,
            is_waived         = it.is_waived,
            waiver_reason     = it.waiver_reason,
        )
        db.add(item)

    # Totals
    _recalc_totals(record, body.items)

    # Status
    if body.auto_confirm:
        record.status          = 'CONFIRMED'
        record.confirmed_by_id = user.id
    else:
        record.status = 'DRAFT'

    db.commit()
    db.refresh(record)

    log.info(
        'Billing record #%d %s for lab_request=%d total=%.0f RWF (user=%s)',
        record.id, record.status, body.lab_request_id, record.total_amount, user.username,
    )

    return _record_dict(record)


# ══════════════════════════════════════════════════════════════════════════════
#  GET /billing/autobill/{lab_request_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/billing/autobill/{lab_request_id}')
def get_autobill_items(
    lab_request_id: int,
    db:             Session = Depends(get_db),
    user:           User    = Depends(get_current_user),
) -> dict:
    """
    Return auto-suggested billing items from ordered tests in a lab request.
    Uses TestCatalog.price for each test.  Returns both the suggested items
    and a subtotal so the frontend can pre-fill the billing modal.
    """
    from sqlalchemy import text

    # 1. Try to get tests via ordered_tests → test_catalog join
    suggested = []
    try:
        rows = db.execute(text("""
            SELECT tc.id, tc.code, tc.name, tc.price, tc.specimen_type,
                   d.name as dept_name
            FROM ordered_tests ot
            JOIN test_catalog tc ON tc.id = ot.test_id
            LEFT JOIN lab_departments d ON d.id = tc.department_id
            WHERE ot.lab_request_id = :rid
            ORDER BY tc.name
        """), {'rid': lab_request_id}).fetchall()
        suggested = rows
    except Exception:
        pass

    # 2. Fallback: look for results that reference test_catalog
    if not suggested:
        try:
            rows = db.execute(text("""
                SELECT tc.id, tc.code, tc.name, tc.price, tc.specimen_type,
                       d.name as dept_name
                FROM lab_results lr
                JOIN test_catalog tc ON tc.id = lr.test_id
                LEFT JOIN lab_departments d ON d.id = tc.department_id
                WHERE lr.lab_request_id = :rid
                GROUP BY tc.id, tc.code, tc.name, tc.price, tc.specimen_type, d.name
                ORDER BY tc.name
            """), {'rid': lab_request_id}).fetchall()
            suggested = rows
        except Exception:
            pass

    items = []
    subtotal = 0.0
    for row in suggested:
        test_id, code, name, price, specimen, dept = row
        price = float(price or 0.0)
        items.append({
            'test_id':       test_id,
            'item_code':     code or '',
            'item_name':     name,
            'unit_price':    price,
            'quantity':      1,
            'total_price':   price,
            'is_auto_billed': True,
            'is_waived':     False,
            'specimen_type': specimen or '',
            'department':    dept or '',
        })
        subtotal += price

    return {
        'lab_request_id': lab_request_id,
        'items':          items,
        'subtotal':       round(subtotal, 2),
        'currency':       'RWF',
        'count':          len(items),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GET /billing/search-items
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/billing/search-items')
def search_billing_items(
    q:    str     = Query('', min_length=1, description='Search string'),
    limit:int     = Query(20, ge=1, le=100),
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> list:
    """
    Typeahead search for billing items.
    Searches test_catalog by name or code.  Returns items with prices.
    Used by the "Other" add-on field in the billing modal.
    """
    from models.core_config import TestCatalog, LaboratoryDepartment
    from sqlalchemy import or_

    results = (
        db.query(TestCatalog)
        .filter(
            TestCatalog.is_active == True,
            or_(
                TestCatalog.name.ilike(f'%{q}%'),
                TestCatalog.code.ilike(f'%{q}%'),
                TestCatalog.short_name.ilike(f'%{q}%'),
            )
        )
        .order_by(TestCatalog.name)
        .limit(limit)
        .all()
    )

    return [
        {
            'test_id':    t.id,
            'item_code':  t.code,
            'item_name':  t.name,
            'unit_price': float(t.price or 0),
            'quantity':   1,
            'specimen':   t.specimen_type or '',
            'department': t.department.name if t.department else '',
        }
        for t in results
    ]


# ══════════════════════════════════════════════════════════════════════════════
#  GET /billing/record/{lab_request_id}
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/billing/record/{lab_request_id}')
def get_billing_record(
    lab_request_id: int,
    db:             Session = Depends(get_db),
    user:           User    = Depends(get_current_user),
) -> dict:
    """Retrieve the billing record for a lab request (any non-cancelled status)."""
    from models.billing import BillingRecord

    record = (
        db.query(BillingRecord)
        .filter(
            BillingRecord.lab_request_id == lab_request_id,
            BillingRecord.status != 'CANCELLED',
        )
        .order_by(BillingRecord.id.desc())
        .first()
    )
    if not record:
        raise HTTPException(404, 'No billing record found for this lab request')

    return _record_dict(record)


# ══════════════════════════════════════════════════════════════════════════════
#  PUT /billing/record/{id}/status
# ══════════════════════════════════════════════════════════════════════════════

@router.put('/billing/record/{billing_id}/status')
def update_billing_status(
    billing_id: int,
    body:       StatusUpdate,
    db:         Session = Depends(get_db),
    user:       User    = Depends(get_current_user),
) -> dict:
    """
    Update payment status of a billing record.
    Allowed transitions:
      DRAFT → CONFIRMED | CANCELLED
      CONFIRMED → PAID | CANCELLED
      PAID → (terminal)
    """
    from models.billing import BillingRecord

    _VALID = {
        'DRAFT':     {'CONFIRMED', 'CANCELLED'},
        'CONFIRMED': {'PAID', 'CANCELLED'},
        'PAID':      set(),
        'CANCELLED': set(),
    }

    record = db.query(BillingRecord).filter(BillingRecord.id == billing_id).first()
    if not record:
        raise HTTPException(404, 'Billing record not found')

    new_status = body.status.upper()
    allowed    = _VALID.get(record.status, set())
    if new_status not in allowed:
        raise HTTPException(400,
            f'Cannot transition billing from {record.status} → {new_status}. '
            f'Allowed: {sorted(allowed) or "none"}')

    record.status = new_status

    if body.payment_method:
        record.payment_method = body.payment_method
    if body.paid_amount is not None:
        record.paid_amount = body.paid_amount
    if body.momo_ref:
        record.momo_ref = body.momo_ref
    if body.notes:
        record.notes = body.notes

    if new_status == 'CONFIRMED':
        record.confirmed_by_id = user.id

    db.commit()
    db.refresh(record)

    return _record_dict(record)


# ══════════════════════════════════════════════════════════════════════════════
#  GET /billing/summary/today   — Quick dashboard stat
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/billing/summary/today')
def billing_today_summary(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """Today's billing totals by status."""
    from models.billing import BillingRecord
    from sqlalchemy import func, cast, Date
    from datetime import date

    today = date.today()
    rows = (
        db.query(BillingRecord.status, func.count(BillingRecord.id),
                 func.coalesce(func.sum(BillingRecord.total_amount), 0))
        .filter(func.date(BillingRecord.created_at) == today)
        .group_by(BillingRecord.status)
        .all()
    )
    by_status = {r[0]: {'count': r[1], 'amount': float(r[2])} for r in rows}

    return {
        'date':      str(today),
        'currency':  'RWF',
        'by_status': by_status,
        'total_confirmed': by_status.get('CONFIRMED', {}).get('amount', 0)
                         + by_status.get('PAID', {}).get('amount', 0),
        'total_paid':      by_status.get('PAID', {}).get('amount', 0),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  GET /billing/lab-request/{id}  — Lab request + patient detail for worklist-prep page
# ══════════════════════════════════════════════════════════════════════════════

@router.get('/billing/lab-request/{lab_request_id}')
def get_lab_request_detail(
    lab_request_id: int,
    db:             Session = Depends(get_db),
    user:           User    = Depends(get_current_user),
) -> dict:
    """
    Fetch a LabRequest with patient data for the worklist preparation page.
    Used by frontend when it needs the full context before worklist is created.
    """
    from models.laboratory import LabRequest
    from models.patient    import Patient

    req = db.query(LabRequest).filter(LabRequest.id == lab_request_id).first()
    if not req:
        raise HTTPException(404, 'Lab request not found')

    patient = req.patient
    patient_data = None
    if patient:
        full_name = (getattr(patient, 'full_name', None)
                     or f'{getattr(patient, "family_name", "")} '
                        f'{getattr(patient, "other_names", "") or ""}'.strip())
        patient_data = {
            'id':           patient.id,
            'pid':          patient.pid,
            'full_name':    full_name,
            'family_name':  getattr(patient, 'family_name', None),
            'other_names':  getattr(patient, 'other_names', None),
            'gender':       getattr(patient, 'gender', None),
            'age':          getattr(patient, 'age', None),
            'date_of_birth':str(patient.date_of_birth) if getattr(patient, 'date_of_birth', None) else None,
            'phone':        getattr(patient, 'phone', None),
        }

    return {
        'id':              req.id,
        'lab_id':          req.lab_id,
        'patient_id':      req.patient_id,
        'doctor_name':     req.doctor_name,
        'ward':            req.ward,
        'diagnosis':       req.diagnosis,
        'status':          req.status,
        'emergency_level': req.emergency_level,
        'is_high_risk':    req.is_high_risk,
        'request_date':    req.request_date.isoformat() if req.request_date else None,
        'notes':           req.notes,
        'patient':         patient_data,
    }
