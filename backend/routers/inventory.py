"""
Inventory & Reagent Management Router — JORINOVA NEXUS ALIS-X
==============================================================
Manages laboratory reagents, consumables, equipment, and stock levels.
Includes automated low-stock SMS alerts and smart reorder suggestions.
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

log = logging.getLogger('inventory_router')
router = APIRouter(tags=['Inventory & Reagents'])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class ItemCreate(BaseModel):
    item_code:       str
    name:            str
    category:        str = 'reagent'   # reagent|consumable|equipment|ppe
    unit:            str = 'units'
    department:      str = 'general'
    current_stock:   float = 0
    reorder_level:   float = 10
    max_stock:       float = 100
    unit_price:      float = 0
    currency:        str   = 'RWF'
    supplier:        Optional[str] = None
    lot_number:      Optional[str] = None
    expiry_date:     Optional[str] = None   # YYYY-MM-DD
    storage_temp:    Optional[str] = None   # e.g. "2-8°C"
    notes:           Optional[str] = None

class StockMovement(BaseModel):
    item_id:     int
    movement:    str    # IN | OUT | ADJUSTMENT | EXPIRED | DAMAGED
    quantity:    float
    reason:      Optional[str] = None
    lot_number:  Optional[str] = None
    expiry_date: Optional[str] = None

class ReorderRequest(BaseModel):
    item_id:    int
    quantity:   float
    supplier:   Optional[str] = None
    notes:      Optional[str] = None


# ── In-memory demo store (replace with DB model when inventory model added) ────

_DEMO_ITEMS = [
    {'id':1,'item_code':'EDTA-TUBE-4ML','name':'EDTA 4mL Lavender Tubes','category':'consumable',
     'unit':'box/100','department':'hematology','current_stock':12,'reorder_level':5,'max_stock':50,
     'unit_price':8500,'currency':'RWF','supplier':'Becton Dickinson','expiry_date':'2027-03-01','storage_temp':'RT'},
    {'id':2,'item_code':'SST-TUBE-5ML','name':'SST Gold Top 5mL Tubes','category':'consumable',
     'unit':'box/100','department':'biochemistry','current_stock':8,'reorder_level':10,'max_stock':50,
     'unit_price':12000,'currency':'RWF','supplier':'Becton Dickinson','expiry_date':'2027-06-01','storage_temp':'RT'},
    {'id':3,'item_code':'CHEM-GLUCOSE','name':'Glucose Reagent (Cobas)','category':'reagent',
     'unit':'cassette','department':'biochemistry','current_stock':4,'reorder_level':3,'max_stock':20,
     'unit_price':45000,'currency':'RWF','supplier':'Roche Diagnostics','expiry_date':'2026-08-15','storage_temp':'2-8°C'},
    {'id':4,'item_code':'MALARIA-RDT','name':'Malaria RDT (HRP2/pLDH)','category':'reagent',
     'unit':'box/25','department':'microbiology','current_stock':15,'reorder_level':5,'max_stock':100,
     'unit_price':18000,'currency':'RWF','supplier':'SD Bioline','expiry_date':'2026-12-01','storage_temp':'2-30°C'},
    {'id':5,'item_code':'HIV-COMBO','name':'HIV Ag/Ab Combo Test (4th Gen)','category':'reagent',
     'unit':'box/25','department':'serology','current_stock':22,'reorder_level':10,'max_stock':100,
     'unit_price':25000,'currency':'RWF','supplier':'Abbott','expiry_date':'2027-01-01','storage_temp':'2-30°C'},
    {'id':6,'item_code':'BACTEC-AEROB','name':'BACTEC Aerobic Blood Culture Bottles','category':'reagent',
     'unit':'bottle','department':'microbiology','current_stock':30,'reorder_level':20,'max_stock':200,
     'unit_price':4500,'currency':'RWF','supplier':'BD Biosciences','expiry_date':'2026-10-01','storage_temp':'RT'},
    {'id':7,'item_code':'GENEXPERT-CRTG','name':'GeneXpert MTB/RIF Ultra Cartridges','category':'reagent',
     'unit':'cartridge','department':'molecular','current_stock':2,'reorder_level':5,'max_stock':50,
     'unit_price':25000,'currency':'RWF','supplier':'Cepheid','expiry_date':'2026-09-01','storage_temp':'2-28°C'},
    {'id':8,'item_code':'LATEX-GLOVE-M','name':'Latex Gloves Medium','category':'ppe',
     'unit':'box/100','department':'general','current_stock':25,'reorder_level':10,'max_stock':100,
     'unit_price':3500,'currency':'RWF','supplier':'Medline','expiry_date':None,'storage_temp':'RT'},
]
_NEXT_ID = len(_DEMO_ITEMS) + 1


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get('/inventory/items')
def list_items(
    department: Optional[str] = Query(None),
    category:   Optional[str] = Query(None),
    low_stock:  bool          = Query(False, description='Only items below reorder level'),
    expiring:   int           = Query(0, description='Items expiring within N days (0=all)'),
    q:          Optional[str] = Query(None),
    db:         Session       = Depends(get_db),
    user:       User          = Depends(get_current_user),
) -> list:
    items = list(_DEMO_ITEMS)
    if department: items = [i for i in items if i['department'] == department]
    if category:   items = [i for i in items if i['category']   == category]
    if low_stock:  items = [i for i in items if i['current_stock'] <= i['reorder_level']]
    if q:
        ql = q.lower()
        items = [i for i in items if ql in i['name'].lower() or ql in i['item_code'].lower()]
    if expiring > 0:
        cutoff = (date.today() + timedelta(days=expiring)).isoformat()
        items = [i for i in items if i['expiry_date'] and i['expiry_date'] <= cutoff]
    return [_item_with_status(i) for i in items]


@router.get('/inventory/items/{item_id}')
def get_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    item = next((i for i in _DEMO_ITEMS if i['id'] == item_id), None)
    if not item: raise HTTPException(404, 'Item not found')
    return _item_with_status(item)


@router.post('/inventory/items', status_code=201)
def create_item(
    body: ItemCreate,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    global _NEXT_ID
    if user.role not in {'super_admin','it_admin','lab_manager','storekeeper'}:
        raise HTTPException(403, 'Lab manager access required')
    item = {**body.dict(), 'id': _NEXT_ID}
    _DEMO_ITEMS.append(item)
    _NEXT_ID += 1
    return _item_with_status(item)


@router.post('/inventory/stock-movement')
def record_movement(
    body: StockMovement,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    item = next((i for i in _DEMO_ITEMS if i['id'] == body.item_id), None)
    if not item: raise HTTPException(404, 'Item not found')

    before = item['current_stock']
    if body.movement == 'IN':
        item['current_stock'] = before + body.quantity
    elif body.movement in ('OUT', 'EXPIRED', 'DAMAGED'):
        if body.quantity > before:
            raise HTTPException(400, f'Insufficient stock: {before} available')
        item['current_stock'] = before - body.quantity
    elif body.movement == 'ADJUSTMENT':
        item['current_stock'] = body.quantity
    else:
        raise HTTPException(400, f'Unknown movement type: {body.movement}')

    after = item['current_stock']

    # Low stock SMS alert
    if after <= item['reorder_level'] and before > item['reorder_level']:
        _trigger_low_stock_alert(item, user, db)

    return {
        'item_id':    item['id'],
        'item_name':  item['name'],
        'movement':   body.movement,
        'quantity':   body.quantity,
        'before':     before,
        'after':      after,
        'is_low':     after <= item['reorder_level'],
    }


@router.get('/inventory/stats')
def inventory_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    total    = len(_DEMO_ITEMS)
    low      = sum(1 for i in _DEMO_ITEMS if i['current_stock'] <= i['reorder_level'])
    out      = sum(1 for i in _DEMO_ITEMS if i['current_stock'] == 0)
    cutoff   = (date.today() + timedelta(days=30)).isoformat()
    expiring = sum(1 for i in _DEMO_ITEMS if i.get('expiry_date') and i['expiry_date'] <= cutoff)
    total_val= sum(i['current_stock'] * i.get('unit_price', 0) for i in _DEMO_ITEMS)

    return {
        'total_items':       total,
        'low_stock':         low,
        'out_of_stock':      out,
        'expiring_30_days':  expiring,
        'total_value_rwf':   round(total_val, 0),
        'categories':        _count_by('category'),
        'departments':       _count_by('department'),
    }


@router.get('/inventory/expiring')
def expiring_items(
    days: int = Query(30, ge=1, le=365),
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> list:
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    items  = [i for i in _DEMO_ITEMS if i.get('expiry_date') and i['expiry_date'] <= cutoff]
    return [_item_with_status(i) for i in sorted(items, key=lambda x: x['expiry_date'])]


@router.post('/inventory/reorder')
def create_reorder(
    body: ReorderRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    item = next((i for i in _DEMO_ITEMS if i['id'] == body.item_id), None)
    if not item: raise HTTPException(404, 'Item not found')
    return {
        'reorder_created': True,
        'item':            item['name'],
        'quantity':        body.quantity,
        'supplier':        body.supplier or item.get('supplier','—'),
        'estimated_cost':  body.quantity * item.get('unit_price', 0),
        'currency':        item.get('currency','RWF'),
        'created_by':      user.username,
        'created_at':      datetime.now(timezone.utc).isoformat(),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _item_with_status(item: dict) -> dict:
    stock      = item.get('current_stock', 0)
    reorder    = item.get('reorder_level', 0)
    expiry     = item.get('expiry_date')
    days_exp   = None
    if expiry:
        days_exp = (date.fromisoformat(expiry) - date.today()).days

    stock_status = 'ok'
    if stock == 0:          stock_status = 'out'
    elif stock <= reorder:  stock_status = 'low'

    expiry_status = 'ok'
    if days_exp is not None:
        if days_exp < 0:    expiry_status = 'expired'
        elif days_exp <= 7: expiry_status = 'critical'
        elif days_exp <= 30:expiry_status = 'warning'

    return {**item, 'stock_status': stock_status, 'expiry_status': expiry_status,
            'days_to_expiry': days_exp}


def _count_by(field: str) -> dict:
    counts = {}
    for i in _DEMO_ITEMS:
        v = i.get(field, 'other')
        counts[v] = counts.get(v, 0) + 1
    return counts


def _trigger_low_stock_alert(item, user, db):
    try:
        from services.sms_service import notify_low_stock
        import asyncio
        from models.core_config import Hospital
        hospital = db.query(Hospital).first()
        mgr_phone = getattr(user, 'phone', '') or ''
        if mgr_phone and hospital:
            asyncio.create_task(notify_low_stock(
                manager_phone  = mgr_phone,
                item_name      = item['name'],
                remaining      = item['current_stock'],
                unit           = item['unit'],
                reorder_level  = item['reorder_level'],
                hospital_name  = hospital.name,
                db             = db,
            ))
            log.info('Low stock SMS sent for %s to %s', item['name'], mgr_phone)
    except Exception as e:
        log.warning('Low stock SMS failed: %s', e)
