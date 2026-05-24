"""
IoT / Analyzer ingestion router

Vendor-neutral entry points for ANY analyzer in the lab. Goes through
ai_services.iot_adapters which has a registry per instrument type.

Endpoints
---------
  GET  /api/v1/iot/adapters             list registered adapters
  POST /api/v1/iot/ingest                ingest raw bytes via a chosen adapter
  GET  /api/v1/iot/public/adapters       no-auth list (kiosk / discovery)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ai_services import iot_adapters as iot
from core.security import get_current_user
from models.user import User

router = APIRouter(prefix='/iot', tags=['IoT / Analyzers'])
log = logging.getLogger('alis_x.iot.router')


@router.get('/adapters')
def adapters(_u: User = Depends(get_current_user)) -> dict:
    return {'adapters': iot.list_adapters()}


@router.get('/public/adapters')
def adapters_public() -> dict:
    """No-auth discovery — useful for kiosk / commissioning screens."""
    return {'adapters': iot.list_adapters()}


@router.post('/ingest')
async def ingest(
    req:           Request,
    adapter_id:    str = Query(..., description='Registered adapter id, see GET /iot/adapters'),
    instrument_id: str = Query(..., description='Serial / inventory id of the source instrument'),
    _u:            User = Depends(get_current_user),
) -> dict:
    """
    Generic ingest endpoint. The caller picks the adapter (e.g. 'hl7_generic',
    'sysmex_xn', 'cobas_pro', 'json_push', 'csv_dump', 'astm_generic') via query
    string; the request body must be the raw analyzer payload (HL7 / ASTM / JSON / CSV bytes).
    """
    raw = await req.body()
    if not raw:
        raise HTTPException(400, 'Empty payload')

    env = iot.IngestEnvelope(
        adapter_id    = adapter_id,
        instrument_id = instrument_id,
        raw_payload   = raw,
        content_type  = req.headers.get('content-type', 'application/octet-stream'),
        received_at   = datetime.now(timezone.utc).isoformat(),
    )
    if iot.get_adapter(adapter_id) is None:
        raise HTTPException(404, f'Unknown adapter "{adapter_id}". See /api/v1/iot/adapters.')

    parsed = iot.ingest(env)
    log.info(
        'IoT ingest adapter=%s instrument=%s bytes=%d parsed=%d',
        adapter_id, instrument_id, len(raw), len(parsed),
    )
    return {
        'adapter_id':    adapter_id,
        'instrument_id': instrument_id,
        'received_at':   env.received_at,
        'parsed_count':  len(parsed),
        'results': [
            {
                'sample_id':     r.sample_id,
                'patient_pid':   r.patient_pid,
                'test_code':     r.test_code,
                'test_name':     r.test_name,
                'value':         r.value,
                'numeric_value': r.numeric_value,
                'unit':          r.unit,
                'flag':          r.flag,
                'reference_low': r.reference_low,
                'reference_high':r.reference_high,
                'result_status': r.result_status,
                'instrument':    r.instrument,
            } for r in parsed
        ],
    }
