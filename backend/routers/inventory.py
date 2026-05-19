"""
Inventory & Reagent Management Router — JORINOVA NEXUS ALIS-X
Real SQLAlchemy database — replaces in-memory demo store.
"""
from __future__ import annotations
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.inventory import InventoryItem, StockMovement as StockMovementModel
from models.user import User

log = logging.getLogger('inventory_router')
router = APIRouter(tags=['Inventory & Reagents'])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    item_code:    str
    name:         str
    category:     str = 'reagent'
    unit:         str = 'units'
    quantity:     float = 0
    min_stock:    float = 10
    unit_cost:    float = 0
    lot_number:   Optional[str] = None
    expiry_date:  Optional[date] = None
    location:     Optional[str] = None
    notes:        Optional[str] = None


class ItemUpdate(BaseModel):
    name:         Optional[str]   = None
    quantity:     Optional[float] = None
    min_stock:    Optional[float] = None
    unit_cost:    Optional[float] = None
    lot_number:   Optional[str]   = None
    expiry_date:  Optional[date]  = None
    location:     Optional[str]   = None
    notes:        Optional[str]   = None
    is_active:    Optional[bool]  = None


class MovementIn(BaseModel):
    item_id:   int
    movement:  str       # IN | OUT | ADJUSTMENT | EXPIRED | DAMAGED | CONSUMED
    quantity:  float
    reason:    Optional[str] = None


class ReorderRequest(BaseModel):
    item_id:  int
    quantity: float
    supplier: Optional[str] = None
    notes:    Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _item_out(item: InventoryItem) -> dict:
    d   = item.days_to_expiry
    ss  = 'ok'
    if item.quantity == 0:          ss = 'out'
    elif item.is_low_stock:         ss = 'low'
    es  = 'ok'
    if d is not None:
        if d < 0:    es = 'expired'
        elif d <= 7: es = 'critical'
        elif d <= 30:es = 'warning'
    return {
        'id':           item.id,
        'item_code':    item.item_code,
        'name':         item.name,
        'category':     item.category,
        'unit':         item.unit,
        'current_stock':item.quantity,
        'quantity':     item.quantity,
        'min_stock':    item.min_stock,
        'reorder_level':item.min_stock,
        'unit_cost':    item.unit_cost,
        'unit_price':   item.unit_cost,
        'lot_number':   item.lot_number,
        'expiry_date':  item.expiry_date.isoformat() if item.expiry_date else None,
        'location':     item.location,
        'notes':        item.notes,
        'is_active':    item.is_active,
        'stock_status': ss,
        'expiry_status':es,
        'days_to_expiry':d,
        'created_at':   item.created_at.isoformat() if item.created_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get('/inventory/items')
def list_items(
    category:   Optional[str] = Query(None),
    low_stock:  bool          = Query(False),
    expiring:   int           = Query(0, ge=0, le=365),
    q:          Optional[str] = Query(None),
    skip:       int           = Query(0, ge=0),
    limit:      int           = Query(100, le=500),
    db:         Session       = Depends(get_db),
    user:       User          = Depends(get_current_user),
) -> list:
    qs = db.query(InventoryItem).filter(InventoryItem.is_active == True)
    if category:
        qs = qs.filter(InventoryItem.category == category)
    if low_stock:
        qs = qs.filter(InventoryItem.quantity <= InventoryItem.min_stock)
    if expiring > 0:
        cutoff = date.today() + timedelta(days=expiring)
        qs = qs.filter(InventoryItem.expiry_date <= cutoff, InventoryItem.expiry_date.isnot(None))
    if q:
        qs = qs.filter(or_(
            InventoryItem.name.ilike(f'%{q}%'),
            InventoryItem.item_code.ilike(f'%{q}%'),
        ))
    items = qs.order_by(InventoryItem.category, InventoryItem.name).offset(skip).limit(limit).all()
    return [_item_out(i) for i in items]


@router.get('/inventory/items/{item_id}')
def get_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, 'Item not found')
    return _item_out(item)


@router.post('/inventory/items', status_code=201)
def create_item(body: ItemCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    if user.role not in {'super_admin', 'it_admin', 'lab_manager', 'storekeeper'}:
        raise HTTPException(403, 'Lab manager access required')
    if db.query(InventoryItem).filter(InventoryItem.item_code == body.item_code).first():
        raise HTTPException(400, f'Item code {body.item_code!r} already exists')
    item = InventoryItem(
        item_code=body.item_code, name=body.name, category=body.category,
        unit=body.unit, quantity=body.quantity, min_stock=body.min_stock,
        unit_cost=body.unit_cost, lot_number=body.lot_number,
        expiry_date=body.expiry_date, location=body.location, notes=body.notes,
        hospital_id=getattr(user, 'hospital_id', None),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_out(item)


@router.patch('/inventory/items/{item_id}')
def update_item(
    item_id: int, body: ItemUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
) -> dict:
    item = db.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(404, 'Item not found')
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(item, field, val)
    db.commit()
    db.refresh(item)
    return _item_out(item)


@router.post('/inventory/stock-movement')
def record_movement(
    body: MovementIn,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    item = db.get(InventoryItem, body.item_id)
    if not item:
        raise HTTPException(404, 'Item not found')
    before = item.quantity
    if body.movement == 'IN':
        item.quantity = before + body.quantity
    elif body.movement in ('OUT', 'EXPIRED', 'DAMAGED', 'CONSUMED'):
        if body.quantity > before:
            raise HTTPException(400, f'Insufficient stock: {before} available')
        item.quantity = before - body.quantity
    elif body.movement == 'ADJUSTMENT':
        item.quantity = body.quantity
    else:
        raise HTTPException(400, f'Unknown movement: {body.movement}')
    after = item.quantity
    mov = StockMovementModel(
        item_id=item.id, movement_type=body.movement,
        quantity=body.quantity, quantity_before=before, quantity_after=after,
        reason=body.reason, performed_by_id=user.id,
        hospital_id=getattr(user, 'hospital_id', None),
    )
    db.add(mov)
    db.commit()
    # Low-stock alert
    if after <= item.min_stock and before > item.min_stock:
        _trigger_low_stock_alert(item, user, db)
    return {
        'item_id':   item.id, 'item_name': item.name,
        'movement':  body.movement, 'quantity': body.quantity,
        'before':    before, 'after': after, 'is_low': after <= item.min_stock,
    }


@router.get('/inventory/stats')
def inventory_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    total     = db.query(func.count(InventoryItem.id)).filter(InventoryItem.is_active == True).scalar()
    low       = db.query(func.count(InventoryItem.id)).filter(
                    InventoryItem.is_active == True,
                    InventoryItem.quantity <= InventoryItem.min_stock,
                ).scalar()
    out       = db.query(func.count(InventoryItem.id)).filter(
                    InventoryItem.is_active == True, InventoryItem.quantity == 0,
                ).scalar()
    cutoff    = date.today() + timedelta(days=30)
    expiring  = db.query(func.count(InventoryItem.id)).filter(
                    InventoryItem.is_active == True,
                    InventoryItem.expiry_date.isnot(None),
                    InventoryItem.expiry_date <= cutoff,
                ).scalar()
    total_val = db.query(
                    func.sum(InventoryItem.quantity * InventoryItem.unit_cost)
                ).filter(InventoryItem.is_active == True).scalar() or 0

    from sqlalchemy import distinct
    cats = db.query(InventoryItem.category, func.count(InventoryItem.id)).filter(
               InventoryItem.is_active == True
           ).group_by(InventoryItem.category).all()

    return {
        'total_items':      total or 0,
        'low_stock':        low   or 0,
        'out_of_stock':     out   or 0,
        'expiring_30_days': expiring or 0,
        'total_value_rwf':  round(float(total_val), 0),
        'categories':       {c: n for c, n in cats},
    }


@router.get('/inventory/expiring')
def expiring_items(
    days: int     = Query(30, ge=1, le=365),
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> list:
    cutoff = date.today() + timedelta(days=days)
    items  = db.query(InventoryItem).filter(
        InventoryItem.is_active == True,
        InventoryItem.expiry_date.isnot(None),
        InventoryItem.expiry_date <= cutoff,
    ).order_by(InventoryItem.expiry_date).all()
    return [_item_out(i) for i in items]


@router.get('/inventory/movements')
def list_movements(
    item_id: Optional[int] = Query(None),
    limit:   int           = Query(50, le=200),
    db:      Session       = Depends(get_db),
    user:    User          = Depends(get_current_user),
) -> list:
    qs = db.query(StockMovementModel)
    if item_id:
        qs = qs.filter(StockMovementModel.item_id == item_id)
    movements = qs.order_by(StockMovementModel.created_at.desc()).limit(limit).all()
    return [{
        'id':         m.id, 'item_id': m.item_id,
        'movement':   m.movement_type,
        'quantity':   m.quantity, 'before': m.quantity_before, 'after': m.quantity_after,
        'reason':     m.reason,
        'created_at': m.created_at.isoformat() if m.created_at else None,
    } for m in movements]


@router.post('/inventory/reorder')
def create_reorder(
    body: ReorderRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    item = db.get(InventoryItem, body.item_id)
    if not item:
        raise HTTPException(404, 'Item not found')
    return {
        'reorder_created': True,
        'item':            item.name,
        'quantity':        body.quantity,
        'supplier':        body.supplier or '—',
        'estimated_cost':  body.quantity * item.unit_cost,
        'currency':        'RWF',
        'created_by':      user.username,
        'created_at':      datetime.now(timezone.utc).isoformat(),
    }


def _trigger_low_stock_alert(item, user, db):
    try:
        from services.sms_service import notify_low_stock
        import asyncio
        from models.core_config import Hospital
        hospital  = db.query(Hospital).first()
        mgr_phone = getattr(user, 'phone', '') or ''
        if mgr_phone and hospital:
            asyncio.create_task(notify_low_stock(
                manager_phone=mgr_phone, item_name=item.name,
                remaining=item.quantity, unit=item.unit,
                reorder_level=item.min_stock, hospital_name=hospital.name, db=db,
            ))
    except Exception as e:
        log.warning('Low stock SMS failed: %s', e)
