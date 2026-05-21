"""
Smart sample routing service for ALIS-X worklist preparation.

This module is the production implementation for the /api/routing/ endpoints.
It wraps worklist_service.route_request_to_worklist() and adds barcode/QR
scan handling plus manual/auto routing confirmation.

P0 fix: replaces the empty stub that caused ImportError at import time.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from models.worklist import WorklistEntry, SpecimenTypeConfig
from services.worklist_service import (
    route_request_to_worklist,
    seed_specimen_types,
    get_specimen_config,
    get_current_shift,
)
from models.laboratory import LabRequest

log = logging.getLogger('routing_service')


# ── Public API ─────────────────────────────────────────────────────────────────

class RoutingService:
    """Facade over worklist_service used by the /api/routing/ router."""

    @staticmethod
    def process_sample_scan(db: Session, sample_id: str) -> dict[str, Any]:
        """
        Look up a barcode / SID and return its routing state.

        Accepts:
          • LabRequest.lab_id  (e.g.  LR-2026-0001)
          • WorklistEntry.sid  (e.g.  HEM-01)
          • WorklistEntry.barcode

        Returns enriched dict for the frontend scanner UI.
        Raises ValueError if nothing matches.
        """
        # Try LabRequest first
        req = (
            db.query(LabRequest)
            .filter(LabRequest.lab_id == sample_id)
            .first()
        )
        if req:
            return {
                'kind':       'lab_request',
                'lab_id':     req.lab_id,
                'patient_id': req.patient_id,
                'pid':        req.pid,
                'status':     req.status,
                'ward':       req.ward,
                'priority':   req.emergency_level,
                'received':   req.received_at is not None,
            }

        # Try WorklistEntry by SID or barcode
        entry = (
            db.query(WorklistEntry)
            .filter(
                (WorklistEntry.sid == sample_id)
                | (WorklistEntry.barcode == sample_id)
            )
            .first()
        )
        if entry:
            # 24h geometry: floor=(rack//24), column=(rack%24), slot=(column+1)
            from services.worklist_service import rack_to_geometry
            geo = rack_to_geometry(entry.rack_number or 0)
            spec = (
                db.query(SpecimenTypeConfig)
                .filter(SpecimenTypeConfig.acronym == entry.specimen_acronym)
                .first()
            )
            return {
                'kind':          'worklist_entry',
                'sid':           entry.sid,
                'lab_request':   entry.lab_request_id,
                'patient_id':    entry.patient_id,
                'route_id':      entry.rack_number or 0,
                'rack_number':   entry.rack_number,
                'rack_position': geo['slot'],       # 1..24 (tube label position)
                'rack_floor':    geo['floor'],
                'department':    entry.department,
                'specimen':      entry.specimen_name,
                'tube_color':    entry.tube_color,
                'cid':           entry.cid,
                'status':        entry.status,
                'priority':      entry.priority,
                'is_replacement': entry.is_rejection_replacement,
                'received_at':   entry.received_at.isoformat() if entry.received_at else None,
                'specimen_volume_ml': spec.volume_ml if spec else None,
            }

        raise ValueError(f'No sample found with identifier: {sample_id!r}')

    @staticmethod
    def confirm_routing(
        db: Session,
        sample_id: str,
        mode: str,
        user: Any,   # User model — avoid circular import at module level
    ) -> dict[str, Any]:
        """
        Confirm or cancel routing for a scanned sample.

        mode = 'all'     → full auto-route (default)
        mode = 'manual'  → mark received but skip auto-route
        mode = 'cancel'  → undo / roll back routing
        """
        # Find the underlying record
        req = (
            db.query(LabRequest)
            .filter(LabRequest.lab_id == sample_id)
            .first()
        )
        if not req:
            raise ValueError(f'LabRequest {sample_id!r} not found.')

        shift = get_current_shift(db)

        if mode in ('all', 'auto', 'auto-route'):
            entries = route_request_to_worklist(
                db=db,
                lab_request_id=req.id,
                received_by_id=user.id,
                shift_name=shift,
            )
            db.commit()
            return {
                'mode':    'auto',
                'entries': [
                    {
                        'sid':   e.sid,
                        'dept':  e.department,
                        'rack':  e.rack_number,
                        'cid':   e.cid,
                        'color': e.tube_color,
                    }
                    for e in entries
                ],
                'message': f'{len(entries)} worklist entries created.',
            }

        if mode == 'manual':
            req.status = 'received'
            req.received_at = __import__('datetime').datetime.utcnow()
            req.received_by_id = user.id
            db.commit()
            return {
                'mode':    'manual',
                'entries': [],
                'message': f'LabRequest {sample_id} marked as received (manual).',
            }

        if mode == 'cancel':
            return {
                'mode':    'cancel',
                'entries': [],
                'message': f'Routing cancelled for {sample_id}.',
            }

        raise ValueError(f'Unknown routing mode: {mode!r}')
