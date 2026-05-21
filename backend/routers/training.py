"""
Training / AI Demo router
=========================
Serves the static scenarios catalog AND on-demand AI-generated scenarios that
anchor on real (anonymised) pilot data.

Endpoints:
  /scenarios                          static catalog list
  /scenarios/{id}                     static catalog detail
  /public/scenarios{,/{id}}           same, no auth (kiosk mode)
  /features                           feature catalog the generator can target
  /generate                           POST → generate a scenario via LLM
  /scenarios/generated/{id}           fetch a previously-generated scenario
  /data-source/lab-request            fetch one real (anonymised) LabRequest
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ai_services import training_generator as tg
from ai_services import training_scenarios as ts
from core.database import get_db
from core.security import get_current_user
from models.user import User

router = APIRouter(prefix='/training', tags=['Training / AI Demo'])


@router.get('/scenarios')
def list_scenarios(_u: User = Depends(get_current_user)) -> dict:
    """List all scenarios (summary). Filter on the client by role."""
    return {'scenarios': ts.list_scenarios()}


@router.get('/scenarios/{scenario_id}')
def get_scenario(scenario_id: str, _u: User = Depends(get_current_user)) -> dict:
    """Return the full scenario including step bodies."""
    s = ts.get_scenario(scenario_id)
    if not s:
        raise HTTPException(404, f'Scenario "{scenario_id}" not found')
    return s


# Public (no-auth) endpoints for kiosk / showcase use ──────────────────────────

@router.get('/public/scenarios')
def list_scenarios_public() -> dict:
    """No-auth list — intended for demo kiosks. Returns the same summary."""
    return {'scenarios': ts.list_scenarios()}


@router.get('/public/scenarios/{scenario_id}')
def get_scenario_public(scenario_id: str) -> dict:
    """No-auth fetch — intended for demo kiosks. Also serves generated scenarios."""
    if scenario_id.startswith('gen_'):
        cached = tg.cache_get(scenario_id)
        if cached:
            return cached
        raise HTTPException(404, f'Generated scenario "{scenario_id}" expired or unknown')
    s = ts.get_scenario(scenario_id)
    if not s:
        raise HTTPException(404, f'Scenario "{scenario_id}" not found')
    return s


# ── AI-generated scenarios ────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    feature_id:       str                                            = Field(..., description='Key from /training/features')
    role:             str                                            = 'lab_technician'
    language:         Literal['en', 'fr', 'rw']                      = 'en'
    anchor_record_id: Optional[int]                                  = None
    provider:         Literal['cloud', 'local', 'auto', 'stub']      = 'auto'


@router.get('/features')
def list_features(_u: User = Depends(get_current_user)) -> dict:
    """List the feature catalog the AI generator can target."""
    return {
        'features': [
            {
                'id':           fid,
                'title':        cfg['title'],
                'description':  cfg['description'],
                'scene':        cfg['scene'],
                'innovations':  cfg.get('innovations', []),
                'targets':      cfg.get('targets', []),
            }
            for fid, cfg in tg.FEATURE_CATALOG.items()
        ]
    }


@router.post('/generate')
async def generate(
    body: GenerateRequest,
    db:   Session = Depends(get_db),
    user: User    = Depends(get_current_user),
) -> dict:
    """
    Generate a training scenario via LLM, optionally anchored to a real
    pilot record. Cached in memory by scenario id (short TTL).
    """
    try:
        scenario = await tg.generate_scenario(
            db,
            feature_id       = body.feature_id,
            role             = body.role or user.role,
            language         = body.language,
            anchor_record_id = body.anchor_record_id,
            provider         = body.provider,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f'Generation failed: {e}')

    tg.cache_put(scenario)
    return scenario


@router.get('/scenarios/generated/{scenario_id}')
def get_generated(
    scenario_id: str,
    _u:          User = Depends(get_current_user),
) -> dict:
    """Fetch a previously-generated scenario from in-memory cache."""
    cached = tg.cache_get(scenario_id)
    if not cached:
        raise HTTPException(404, f'Generated scenario "{scenario_id}" expired or unknown')
    return cached


# ── Live data sources (anonymised) ────────────────────────────────────────────

@router.get('/data-source/lab-request')
def data_source_lab_request(
    db:           Session = Depends(get_db),
    _u:           User    = Depends(get_current_user),
    feature_id:   str = Query('critical_cbc'),
    anchor_id:    Optional[int] = None,
) -> dict:
    """
    Return one real LabRequest (anonymised) matching the feature's data_source
    filter — useful for scenes to bind to live data when running standalone.
    """
    data = tg.fetch_anchor(db, feature_id, anchor_id)
    if not data:
        raise HTTPException(404, 'No matching record in pilot data')
    return data
