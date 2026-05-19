"""
JORINOVA NEXUS ALIS-X — Sync Router
=====================================
Handles offline-first data synchronisation from client devices (4G / 5G / satellite).

POST /sync/batch         — receive and apply a batch of offline operations
GET  /sync/status        — device sync status (last sync time, pending count)
GET  /sync/delta         — server-side changes since last sync (for pull)
POST /sync/ping          — ultra-lightweight connectivity probe
GET  /sync/conflicts     — conflicts requiring manual resolution
POST /sync/resolve/{id}  — resolve a conflict (keep_client | keep_server)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.sync_queue import DeviceSync, SyncOperation
from models.user import User

log = logging.getLogger('sync_router')
router = APIRouter(prefix='/sync', tags=['Sync & Offline'])


# ── Schemas ───────────────────────────────────────────────────────────────────

class OperationIn(BaseModel):
    queue_id:   str
    endpoint:   str
    method:     str
    payload:    Optional[Any] = None
    created_at: Optional[str] = None


class BatchSyncIn(BaseModel):
    device_id:   str
    client_time: Optional[str] = None
    network_type: Optional[str] = None
    operations:  list[OperationIn]


class ConflictResolve(BaseModel):
    resolution: str  # keep_client | keep_server


# ── Ping (ultra-lightweight — no DB, no auth needed) ─────────────────────────

@router.get('/ping', include_in_schema=False)
@router.post('/ping', include_in_schema=False)
async def ping():
    """Zero-overhead connectivity probe used by the network monitor."""
    return {'ok': True, 'ts': datetime.now(timezone.utc).isoformat()}


# ── Batch sync ────────────────────────────────────────────────────────────────

@router.post('/batch')
async def batch_sync(
    body:    BatchSyncIn,
    request: Request,
    db:      Session = Depends(get_db),
    user:    User    = Depends(get_current_user),
):
    """
    Apply a batch of offline operations from a client device.
    Returns per-operation results: synced | conflict | failed.
    """
    synced, conflicts, failed = [], [], []

    # Upsert device record
    dev = db.query(DeviceSync).filter(DeviceSync.device_id == body.device_id).first()
    if not dev:
        dev = DeviceSync(device_id=body.device_id, user_id=user.id,
                         user_agent=request.headers.get('user-agent','')[:200])
        db.add(dev)
    dev.last_sync_at = datetime.now(timezone.utc)
    dev.network_type  = body.network_type or 'unknown'
    db.flush()

    # Process each operation
    async with httpx.AsyncClient(base_url=str(request.base_url), timeout=10.0) as client:
        for op in body.operations:
            # Skip already-applied operations (idempotent)
            existing = db.query(SyncOperation).filter(
                SyncOperation.queue_id == op.queue_id
            ).first()
            if existing and existing.status == 'applied':
                synced.append({'queue_id': op.queue_id, 'status': 'already_applied'})
                continue

            # Record operation
            so = existing or SyncOperation(
                queue_id=op.queue_id, device_id=body.device_id, user_id=user.id,
                endpoint=op.endpoint, method=op.method.upper(), payload=op.payload,
                client_timestamp=_parse_dt(op.created_at),
            )
            so.status = 'received'
            if not existing:
                db.add(so)
            db.flush()

            # Apply the operation via internal HTTP call
            result = await _apply_operation(client, so, user)
            so.status    = result['status']
            so.result    = result.get('data')
            so.error     = result.get('error')
            so.applied_at = datetime.now(timezone.utc) if result['status'] == 'applied' else None

            if result['status'] == 'applied':
                synced.append({'queue_id': op.queue_id, 'status': 'synced'})
                dev.ops_synced = (dev.ops_synced or 0) + 1
            elif result['status'] == 'conflict':
                conflicts.append({'queue_id': op.queue_id, 'reason': result.get('error','Conflict')})
                so.conflict_detail = result.get('error')
            else:
                failed.append({'queue_id': op.queue_id, 'error': result.get('error','Unknown error')})
                dev.ops_failed = (dev.ops_failed or 0) + 1

    db.commit()
    return {
        'synced':     synced,
        'conflicts':  conflicts,
        'failed':     failed,
        'server_time': datetime.now(timezone.utc).isoformat(),
        'device_id':  body.device_id,
    }


async def _apply_operation(client: httpx.AsyncClient, op: SyncOperation, user: User) -> dict:
    """Forward the offline operation to the appropriate API endpoint."""
    try:
        # Build the request against our own API
        # We use an internal token that identifies this as a sync replay
        headers = {
            'X-Sync-Replay': 'true',
            'X-Device-Id':   op.device_id,
            'X-Original-User': str(user.id),
        }
        method  = op.method.upper()
        url     = f'/api/v1{op.endpoint}'
        payload = op.payload or {}

        resp = await client.request(
            method, url, json=payload, headers=headers,
        )

        if resp.status_code in (200, 201, 204):
            data = resp.json() if resp.content and resp.status_code != 204 else {}
            return {'status': 'applied', 'data': data}

        if resp.status_code == 409:
            return {'status': 'conflict', 'error': resp.text[:200]}

        if resp.status_code in (400, 422):
            err = resp.json().get('detail', resp.text[:200]) if resp.content else 'Validation error'
            return {'status': 'failed', 'error': str(err)[:200]}

        return {'status': 'failed', 'error': f'HTTP {resp.status_code}'}

    except Exception as e:
        log.warning('Operation apply error %s %s: %s', op.method, op.endpoint, e)
        return {'status': 'failed', 'error': str(e)[:200]}


# ── Device status ─────────────────────────────────────────────────────────────

@router.get('/status')
def sync_status(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    """Return this user's device sync state."""
    devices = db.query(DeviceSync).filter(DeviceSync.user_id == user.id).all()
    return [{
        'device_id':    d.device_id,
        'last_sync_at': d.last_sync_at.isoformat() if d.last_sync_at else None,
        'network_type': d.network_type,
        'ops_synced':   d.ops_synced,
        'ops_failed':   d.ops_failed,
    } for d in devices]


# ── Delta pull (server changes since last sync) ───────────────────────────────

@router.get('/delta')
def delta_pull(
    since:    Optional[str] = None,
    modules:  Optional[str] = None,   # comma-separated: patients,lab,inventory
    db:       Session       = Depends(get_db),
    user:     User          = Depends(get_current_user),
):
    """
    Return server-side records changed since `since` timestamp.
    Used by client to update local IndexedDB cache after coming online.
    Limited to modules the client requests (bandwidth-aware).
    """
    since_dt = _parse_dt(since) if since else None
    requested = set((modules or 'patients,lab,inventory').split(','))
    delta: dict[str, list] = {}

    # Test catalog — always include (small, essential for offline entry)
    if 'catalog' in requested or 'lab' in requested:
        from models.core_config import TestCatalog
        q = db.query(TestCatalog).filter(TestCatalog.is_active == True)
        delta['test_catalog'] = [
            {'id': t.id, 'code': t.code, 'name': t.name, 'unit': t.unit,
             'reference_range': t.reference_range, 'department': t.department_id}
            for t in q.limit(200).all()
        ]

    # Patients (limited fields — privacy)
    if 'patients' in requested:
        from models.patient import Patient
        q = db.query(Patient)
        if since_dt:
            q = q.filter(Patient.created_at >= since_dt)
        hospital_id = getattr(user, 'hospital_id', None)
        if hospital_id:
            q = q.filter(Patient.hospital_id == hospital_id)
        delta['patients'] = [
            {'id': p.id, 'pid': p.pid, 'full_name': p.full_name,
             'unique_lab_id': p.unique_lab_id, 'blood_group': getattr(p,'blood_group','')}
            for p in q.order_by(Patient.created_at.desc()).limit(100).all()
        ]

    # Reference ranges (interpretation rules — for offline AI)
    if 'rules' in requested:
        from models.core_config import TestInterpretationRule
        rules = db.query(TestInterpretationRule).filter(
            TestInterpretationRule.is_active == True
        ).limit(500).all()
        delta['interpretation_rules'] = [
            {'test_id': r.test_id, 'flag': r.flag_trigger,
             'interpretation': r.interpretation,
             'significance': r.clinical_significance,
             'causes': r.possible_causes, 'actions': r.recommended_actions,
             'doctor_required': r.requires_doctor_confirmation,
             'doctor_urgency': r.doctor_urgency}
            for r in rules
        ]

    return {
        'delta':       delta,
        'server_time': datetime.now(timezone.utc).isoformat(),
        'modules':     list(requested),
    }


# ── Conflicts ─────────────────────────────────────────────────────────────────

@router.get('/conflicts')
def list_conflicts(
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
):
    ops = db.query(SyncOperation).filter(
        SyncOperation.user_id == user.id,
        SyncOperation.status == 'conflict',
    ).order_by(SyncOperation.received_at.desc()).limit(50).all()
    return [{
        'id':             op.id,
        'queue_id':       op.queue_id,
        'endpoint':       op.endpoint,
        'method':         op.method,
        'conflict_detail':op.conflict_detail,
        'received_at':    op.received_at.isoformat(),
    } for op in ops]


@router.post('/resolve/{op_id}')
def resolve_conflict(
    op_id:   int,
    body:    ConflictResolve,
    db:      Session = Depends(get_db),
    user:    User    = Depends(get_current_user),
):
    op = db.query(SyncOperation).filter(
        SyncOperation.id == op_id, SyncOperation.user_id == user.id
    ).first()
    if not op:
        raise HTTPException(404, 'Operation not found')
    if op.status != 'conflict':
        raise HTTPException(400, 'Operation is not in conflict state')

    if body.resolution == 'keep_client':
        op.status = 'pending_reapply'
    elif body.resolution == 'keep_server':
        op.status = 'abandoned'
    else:
        raise HTTPException(400, 'Invalid resolution. Use keep_client or keep_server')

    db.commit()
    return {'resolved': True, 'resolution': body.resolution, 'op_id': op_id}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None
