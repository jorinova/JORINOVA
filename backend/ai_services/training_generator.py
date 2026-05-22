"""
AI Training Scenario Generator
==============================
Produces a scenario JSON (steps[], scenes[], metadata) from a feature_id,
role, language, and optional anchor record drawn from real pilot data.

Output shape matches `training_scenarios.SCENARIOS[i]` so the frontend
dispatcher consumes it identically to a static scenario.

Provider selection:
  - 'cloud' : ai_services.cloud_llm  (Claude)
  - 'local' : ai_services.local_llm  (Ollama phi3:mini)
  - 'auto'  : try cloud, fall back to local on error
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from ai_services import cloud_llm, local_llm, local_llm_router
from ai_services.training_scenarios import SCENARIOS

logger = logging.getLogger('alis_x.training_generator')


# ── Feature catalog ──────────────────────────────────────────────────────────
# Maps a feature_id (what callers ask for) to a scene_id (frontend component)
# and a human-readable description that the AI uses to write narration.

FEATURE_CATALOG: dict[str, dict[str, Any]] = {
    'critical_cbc': {
        'scene':                'critical_cbc',
        'static_scenario_id':   'critical_value_validation',
        'title':                'Validate a critical CBC',
        'description':          'Review a complete blood count where the white blood cell count is elevated, recognise the leukocytosis pattern, and authorize the result under digital signature.',
        'innovations':          ['PQC digital signing', 'AI lab interpretation', 'critical-value escalation'],
        'data_source':          {'entity': 'lab_request', 'filter': {'has_critical_result': True}},
        'targets':              ['[data-train="search"]', '[data-train="lab-panel"]', '[data-train="wbc-row"]', '[data-train="approve"]'],
    },
    'specimen_intake_stat': {
        'scene':                'specimen_intake',
        'static_scenario_id':   'specimen_intake_stat',
        'title':                'STAT specimen intake',
        'description':          'Scan a STAT-priority barcode, identify the patient, flag the priority, and print aliquot labels.',
        'innovations':          ['shift-based LID labelling', 'AI specimen routing', 'STAT prioritisation'],
        'data_source':          {'entity': 'lab_request', 'filter': {'priority': 'stat'}},
        'targets':              ['[data-train="scanner"]', '[data-train="patient-card"]', '[data-train="priority-chip"]', '[data-train="print-btn"]', '[data-train="status"]'],
    },
    'lis_mapping_walkthrough': {
        'scene':                'lis_mapping_demo',
        'static_scenario_id':   'lis_mapping_walkthrough',
        'title':                'LIS auto-mapping from a request form',
        'description':          'Upload a scanned lab request form, run OCR + intelligent matching, expand panels like CBC, and confirm the worklist with one click.',
        'innovations':          ['OCR + fuzzy catalogue match', 'panel expansion (CBC -> 9 tests)', 'duplicate detection'],
        'data_source':          {'entity': 'lab_request', 'filter': {}},   # anchor on the most recent LabRequest
        'targets':              ['[data-train="dropzone"]', '[data-train="extract-btn"]', '[data-train="draft"]', '[data-train="confirm-btn"]', '[data-train="result"]'],
    },
    'blood_bank_crossmatch': {
        'scene':                'blood_bank_crossmatch',
        'static_scenario_id':   'blood_bank_crossmatch_demo',
        'title':                'Blood bank: crossmatch + chamber/slot tracking',
        'description':          'Demonstrate a compatibility crossmatch with chamber/slot inventory lookup, FIFO/FEFO routing, and the post-issue haemovigilance hook.',
        'innovations':          ['fridge/freezer -> chamber -> numbered slot tracking', 'FIFO/FEFO selection', 'AI RBC routing + Zipline exchange', 'haemovigilance auto-link'],
        'data_source':          {'entity': 'blood_bag', 'filter': {}},
        'targets':              ['[data-train="bag-card"]', '[data-train="slot-grid"]', '[data-train="crossmatch-btn"]', '[data-train="issue-btn"]', '[data-train="status"]'],
    },
    'momo_billing': {
        'scene':                'momo_billing',
        'static_scenario_id':   'momo_billing_demo',
        'title':                'MoMo payment at reception',
        'description':          'Confirm a lab request bill, accept payment over Mobile Money, capture the MoMo reference, and release the worklist downstream.',
        'innovations':          ['Rwanda MoMo integration', 'auto-generated bill from TestCatalog prices', 'split-tender (insurance + MoMo)'],
        'data_source':          {'entity': 'billing_record', 'filter': {}},
        'targets':              ['[data-train="invoice"]', '[data-train="momo-input"]', '[data-train="confirm-btn"]', '[data-train="receipt"]', '[data-train="status"]'],
    },
    'medgenome_pcr': {
        'scene':                'medgenome_pcr',
        'static_scenario_id':   'medgenome_pcr_demo',
        'title':                'MedGenome: TB GeneXpert + resistance call',
        'description':          'Review a GeneXpert MTB/RIF Ultra run, interpret the Ct value, flag rifampicin resistance, and route the molecular epidemiology signal.',
        'innovations':          ['GeneXpert + Cobas + BioFire integration', 'AI genomic interpretation', 'rifampicin resistance auto-flag', 'molecular epidemiology routing'],
        'data_source':          {'entity': 'pcr_result', 'filter': {'category': 'TB'}},
        'targets':              ['[data-train="pcr-card"]', '[data-train="ct-value"]', '[data-train="resistance"]', '[data-train="interpret-btn"]', '[data-train="route-btn"]'],
    },
    'iot_analyzer_intake': {
        'scene':                'iot_analyzer_intake',
        'static_scenario_id':   'iot_analyzer_intake_demo',
        'title':                'IoT: any analyzer, one contract',
        'description':          'Show how ANY analyzer in the lab plugs into the LIS through the vendor-neutral IoT adapter layer. HL7, ASTM, JSON, or CSV — every payload normalises to the same result shape.',
        'innovations':          ['vendor-neutral analyzer ingestion', 'HL7 + ASTM + JSON + CSV adapters', 'pluggable per-vendor variants', 'normalised ParsedResult downstream contract'],
        'data_source':          None,
        'targets':              ['[data-train="adapter-list"]', '[data-train="selected-adapter"]', '[data-train="payload-preview"]', '[data-train="ingest-btn"]', '[data-train="result-feed"]'],
    },
}


# ── Anonymisation ────────────────────────────────────────────────────────────

def _anonymise_patient(patient: dict) -> dict:
    """Strip PII for use in voice narration. Keeps age band, sex, ward."""
    out = dict(patient)
    out.pop('phone', None)
    out.pop('national_id', None)
    out.pop('email', None)
    # Replace identifiers with initials
    full = (patient.get('family_name') or '') + ' ' + (patient.get('other_names') or '')
    initials = ''.join(p[0] for p in full.split() if p)[:3].upper() or 'P'
    out['family_name'] = initials
    out['other_names'] = ''
    out['pid']  = '[redacted]'
    out['lid']  = '[redacted]'
    # Age band
    dob = patient.get('date_of_birth')
    if dob:
        try:
            from datetime import date as _date, datetime
            d = _date.fromisoformat(dob) if isinstance(dob, str) else dob
            today = datetime.now().date()
            age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
            out['age_band'] = f'{(age // 10) * 10}s'
        except Exception:
            out['age_band'] = 'unknown'
    return out


# ── Real data fetchers ───────────────────────────────────────────────────────

def fetch_anchor(db: Session, feature_id: str, anchor_record_id: int | None = None) -> dict | None:
    """Return one anonymised record matching the feature's data_source filter."""
    cfg = FEATURE_CATALOG.get(feature_id)
    if not cfg or not cfg.get('data_source'):
        return None
    ds = cfg['data_source']
    entity = ds['entity']
    filt   = ds.get('filter', {})

    if entity == 'lab_request':
        return _fetch_lab_request(db, filt, anchor_record_id)
    if entity == 'blood_bag':
        return _fetch_blood_bag(db, filt, anchor_record_id)
    if entity == 'billing_record':
        return _fetch_billing_record(db, filt, anchor_record_id)
    if entity == 'pcr_result':
        return _fetch_pcr_result(db, filt, anchor_record_id)
    return None


def _fetch_lab_request(db: Session, filt: dict, anchor_id: int | None) -> dict | None:
    """Fetch one LabRequest (anonymised) matching filter."""
    from models.laboratory import LabRequest, LabResult
    from models.patient import Patient

    q = db.query(LabRequest)
    if anchor_id:
        q = q.filter(LabRequest.id == anchor_id)
    elif filt.get('priority'):
        q = q.filter(LabRequest.emergency_level == filt['priority'])

    if filt.get('has_critical_result'):
        q = q.join(LabResult, LabResult.lab_request_id == LabRequest.id) \
             .filter(LabResult.flag.in_(['HH', 'LL', 'POS', 'H', 'L']))

    req = q.order_by(LabRequest.id.desc()).first()
    if not req:
        return None

    patient = db.query(Patient).filter(Patient.id == req.patient_id).first()
    results = db.query(LabResult).filter(LabResult.lab_request_id == req.id).limit(20).all()

    patient_d = {
        'family_name':   getattr(patient, 'family_name', ''),
        'other_names':   getattr(patient, 'other_names', ''),
        'date_of_birth': getattr(patient, 'date_of_birth', None).isoformat() if patient and patient.date_of_birth else None,
        'gender':        getattr(patient, 'gender', None),
        'pid':           getattr(patient, 'pid', None),
        'lid':           getattr(patient, 'unique_lab_id', None),
    } if patient else {}

    return {
        'lab_request': {
            'id':              req.id,
            'lab_id':          req.lab_id,
            'doctor_name':     req.doctor_name,
            'ward':            req.ward,
            'diagnosis':       req.diagnosis,
            'priority':        req.emergency_level,
        },
        'patient': _anonymise_patient(patient_d),
        'results': [
            {
                'test_id':      r.test_id,
                'value':        r.value,
                'numeric_value':r.numeric_value,
                'unit':         r.unit,
                'flag':         r.flag,
                'status':       r.status,
            } for r in results
        ],
    }


def _fetch_blood_bag(db: Session, filt: dict, anchor_id: int | None) -> dict | None:
    """Fetch one BloodBag (anonymised), preferring fresh `available` units."""
    from models.blood_bank import BloodBag, CrossmatchRecord
    from models.patient import Patient

    q = db.query(BloodBag)
    if anchor_id:
        q = q.filter(BloodBag.id == anchor_id)
    else:
        if filt.get('status'):
            q = q.filter(BloodBag.status == filt['status'])
        if filt.get('blood_group'):
            q = q.filter(BloodBag.blood_group == filt['blood_group'])
    bag = q.order_by(BloodBag.collection_date.desc()).first()
    if not bag:
        return None

    # Most-recent crossmatch (if any)
    xm = (db.query(CrossmatchRecord)
            .filter(CrossmatchRecord.blood_bag_id == bag.id)
            .order_by(CrossmatchRecord.performed_at.desc())
            .first())

    recipient = None
    if xm and xm.patient_id:
        p = db.query(Patient).filter(Patient.id == xm.patient_id).first()
        if p:
            recipient = _anonymise_patient({
                'family_name':   p.family_name,
                'other_names':   p.other_names,
                'date_of_birth': p.date_of_birth.isoformat() if p.date_of_birth else None,
                'gender':        p.gender,
                'pid':           p.pid,
                'lid':           p.unique_lab_id,
            })

    return {
        'blood_bag': {
            'id':              bag.id,
            'bag_number':      bag.bag_number,
            'component':       bag.component,
            'blood_group':     bag.blood_group,
            'volume_ml':       bag.volume_ml,
            'status':          bag.status,
            'expiry_date':     bag.expiry_date.isoformat() if bag.expiry_date else None,
            'days_to_expiry':  bag.days_to_expiry,
            'expiry_status':   bag.expiry_status,
            'is_irradiated':   bag.is_irradiated,
            'is_leukoreduced': bag.is_leukoreduced,
        },
        'crossmatch': {
            'id':             xm.id          if xm else None,
            'result':         xm.result      if xm else None,
            'method':         xm.method      if xm else None,
            'ai_flag':        xm.ai_flag     if xm else False,
            'performed_at':   xm.performed_at.isoformat() if xm and xm.performed_at else None,
        } if xm else None,
        'recipient': recipient,
    }


def _fetch_billing_record(db: Session, filt: dict, anchor_id: int | None) -> dict | None:
    """Fetch one BillingRecord with line items (PHI-free aside from initials)."""
    from models.billing import BillingRecord, BillingItem
    from models.patient import Patient

    q = db.query(BillingRecord)
    if anchor_id:
        q = q.filter(BillingRecord.id == anchor_id)
    else:
        if filt.get('payment_method'):
            q = q.filter(BillingRecord.payment_method == filt['payment_method'])
        if filt.get('status'):
            q = q.filter(BillingRecord.status == filt['status'])
    rec = q.order_by(BillingRecord.id.desc()).first()
    if not rec:
        return None

    items = db.query(BillingItem).filter(BillingItem.billing_record_id == rec.id).limit(12).all()

    patient = db.query(Patient).filter(Patient.id == rec.patient_id).first() if rec.patient_id else None
    patient_d = _anonymise_patient({
        'family_name':   patient.family_name      if patient else None,
        'other_names':   patient.other_names      if patient else None,
        'date_of_birth': patient.date_of_birth.isoformat() if patient and patient.date_of_birth else None,
        'gender':        patient.gender           if patient else None,
        'pid':           patient.pid              if patient else None,
        'lid':           patient.unique_lab_id    if patient else None,
    }) if patient else None

    return {
        'billing_record': {
            'id':              rec.id,
            'status':          rec.status,
            'currency':        rec.currency,
            'subtotal':        rec.subtotal_amount,
            'discount':        rec.discount_amount,
            'total':           rec.total_amount,
            'paid':            rec.paid_amount,
            'payment_method':  rec.payment_method,
            'momo_ref':        rec.momo_ref,
            'insurance_name':  rec.insurance_name,
        },
        'patient': patient_d,
        'items': [
            {
                'code':       i.item_code,
                'name':       i.item_name[:60] if i.item_name else '',
                'quantity':   i.quantity,
                'unit_price': i.unit_price,
                'total':      i.total_price,
            } for i in items
        ],
    }


def _fetch_pcr_result(db: Session, filt: dict, anchor_id: int | None) -> dict | None:
    """Fetch one PCRResult — useful for MedGenome / TB GeneXpert demos."""
    from models.molecular import PCRResult
    from models.patient   import Patient

    q = db.query(PCRResult)
    if anchor_id:
        q = q.filter(PCRResult.id == anchor_id)
    else:
        if filt.get('category'):
            q = q.filter(PCRResult.pcr_category == filt['category'])
        if filt.get('result'):
            q = q.filter(PCRResult.result == filt['result'])
    pcr = q.order_by(PCRResult.id.desc()).first()
    if not pcr:
        return None

    patient = db.query(Patient).filter(Patient.id == pcr.patient_id).first() if pcr.patient_id else None
    patient_d = _anonymise_patient({
        'family_name':   patient.family_name      if patient else None,
        'other_names':   patient.other_names      if patient else None,
        'date_of_birth': patient.date_of_birth.isoformat() if patient and patient.date_of_birth else None,
        'gender':        patient.gender           if patient else None,
        'pid':           patient.pid              if patient else None,
        'lid':           patient.unique_lab_id    if patient else None,
    }) if patient else None

    return {
        'pcr_result': {
            'id':             pcr.id,
            'pcr_id':         pcr.pcr_id,
            'category':       pcr.pcr_category,
            'test_name':      pcr.test_name,
            'target_organism':pcr.target_organism,
            'instrument':     pcr.instrument,
            'cartridge_type': pcr.cartridge_type,
            'result':         pcr.result,
            'ct_value':       pcr.ct_value,
            'semi_quant':     pcr.semi_quant,
            'rifampicin_resistance': pcr.rifampicin_resistance,
            'resistance_markers':    pcr.resistance_markers,
        },
        'patient': patient_d,
    }


# ── Prompt + generation ──────────────────────────────────────────────────────

LANGUAGE_LABELS = {'en': 'English', 'fr': 'French', 'rw': 'Kinyarwanda'}

# Narrator persona for all generated training voice text.
# This is prepended to every prompt sent to the LLM so the generated
# narration (the `voice` field in each step) follows a consistent style:
# patient, calm, simple, never rushed, never jargon-heavy.
NARRATOR_PERSONA = """You are the JORINOVA AI training assistant.
Style rules for every line of narration you produce:
- Use SIMPLE English or SIMPLE Kinyarwanda. Avoid difficult French or technical jargon.
- Short sentences. Step by step.
- Calm and slow. Never rushed.
- Patient and respectful. Clarity over speed.
- Greet briefly only in the first step ("Good morning" / "Mwaramutse" depending on language).
- Thank the user at least once near the start.
- Close politely on the last step ("You're welcome. Have a nice day." / "Murakoze. Mugire umunsi mwiza.").
- Never invent patient names, IDs, or numbers — use only what the ANCHOR RECORD provides, otherwise use generic terms like "the patient" or "the result".
"""

PROMPT_TEMPLATE = NARRATOR_PERSONA + """
You are generating a step-by-step training script for the JORINOVA NEXUS laboratory system.

FEATURE: {title}
DESCRIPTION: {description}
INNOVATIONS TO HIGHLIGHT: {innovations}
USER ROLE: {role}
LANGUAGE: {language_label} (narration must be in this language)
SCENE ID (do NOT change): {scene}

Available DOM targets in this scene (use ONLY these as `target` values):
{targets}

{anchor_block}

Return STRICT JSON with this exact shape (no prose, no markdown):
{{
  "title": "<short title>",
  "description": "<one sentence>",
  "duration_minutes": <integer 1-5>,
  "steps": [
    {{
      "id":      "<short_snake_case_id>",
      "scene":   "{scene}",
      "target":  "<one of the available targets, or null>",
      "voice":   "<one sentence of narration in {language_label}>",
      "action":  "dwell" | "click" | "type" | "highlight" | "flash",
      "payload": {{}} | null,
      "dwell_ms": <integer 300-1500>
    }}
  ]
}}

Rules:
- 5 to 8 steps total
- The first step is always an intro with target:null and action:"dwell"
- Narration is clinical, professional, no PHI (use initials or general descriptors only)
- Highlight CSS classes: trainPulseRed, trainPulseBlue, trainPulseGreen, trainApproved
- For "highlight" or "flash" actions, payload should be {{"cls": "trainPulseRed"}}
- For "type" actions, payload should be {{"text": "<short typed text>", "into": "<target selector>"}}
- For "click" with state change, payload should be {{"cls": "trainApproved"}}
- Do NOT invent new scene names or target selectors
- Output JSON only, no markdown fences
"""


async def generate_scenario(
    db:               Session,
    feature_id:       str,
    role:             str = 'lab_technician',
    language:         str = 'en',
    anchor_record_id: int | None = None,
    provider:         Literal['cloud', 'local', 'auto', 'stub'] = 'auto',
) -> dict[str, Any]:
    """
    Generate a scenario.

    Providers:
      - 'cloud' : Claude only. Errors propagate.
      - 'local' : Ollama only. Errors propagate.
      - 'auto'  : Try cloud → local → stub. NEVER raises on provider failure.
      - 'stub'  : Skip the LLM entirely; build from the static catalog template.
                  Always works as long as the feature_id is known.
    """
    cfg = FEATURE_CATALOG.get(feature_id)
    if not cfg:
        raise ValueError(f'Unknown feature_id "{feature_id}". Known: {list(FEATURE_CATALOG.keys())}')
    if language not in LANGUAGE_LABELS:
        raise ValueError(f'Unsupported language "{language}". Use en | fr | rw.')

    anchor = fetch_anchor(db, feature_id, anchor_record_id)

    # Explicit stub provider — skip LLM and synthesize from the static template
    if provider == 'stub':
        return _stub_scenario(feature_id, cfg, role, language, anchor, source='stub')

    anchor_block = ''
    if anchor:
        anchor_block = (
            'ANCHOR RECORD (real pilot data, already anonymised - incorporate the priority '
            'level, ward, and flag pattern into the narration):\n'
            + json.dumps(anchor, indent=2, default=str)
            + '\n'
        )

    prompt = PROMPT_TEMPLATE.format(
        title          = cfg['title'],
        description    = cfg['description'],
        innovations    = ', '.join(cfg['innovations']),
        role           = role,
        language_label = LANGUAGE_LABELS[language],
        scene          = cfg['scene'],
        targets        = '\n'.join(f'  - {t}' for t in cfg['targets']),
        anchor_block   = anchor_block,
    )

    try:
        raw = await _call_llm(prompt, provider)
        if not raw:
            raise RuntimeError('LLM returned no content')
        parsed = _strict_parse(raw)
        scenario = _to_scenario(feature_id, cfg, role, language, parsed, anchor)
        scenario['source'] = provider
        return scenario
    except Exception as e:
        if provider != 'auto':
            raise
        logger.warning('Auto generation failed (%s); falling back to stub template', str(e)[:120])
        return _stub_scenario(feature_id, cfg, role, language, anchor, source='stub-fallback')


def _stub_scenario(
    feature_id: str, cfg: dict, role: str, language: str,
    anchor: dict | None, source: str,
) -> dict[str, Any]:
    """Build a scenario from the static catalog template — no LLM call."""
    static_id = cfg.get('static_scenario_id')
    template = None
    if static_id:
        for s in SCENARIOS:
            if s['id'] == static_id:
                template = s
                break

    steps: list[dict] = []
    if template:
        steps = [
            {
                'id':       s['id'],
                'scene':    cfg['scene'],
                'target':   s.get('target'),
                'voice':    s.get('voice', ''),
                'action':   s.get('action') or 'dwell',
                'payload':  s.get('payload'),
                'dwell_ms': int(s.get('dwell_ms') or 600),
            }
            for s in template['steps']
        ]
    else:
        steps = [{
            'id':       'intro',
            'scene':    cfg['scene'],
            'target':   None,
            'voice':    f'This is a guided walkthrough of {cfg["title"]}.',
            'action':   'dwell',
            'payload':  None,
            'dwell_ms': 800,
        }]

    return {
        'id':                f'gen_{feature_id}_{uuid.uuid4().hex[:8]}',
        'title':             template['title'] if template else cfg['title'],
        'description':       template['description'] if template else cfg['description'],
        'duration_minutes':  template['duration_minutes'] if template else 2,
        'roles':             [role],
        'modules':           [feature_id],
        'scenes':            [cfg['scene']],
        'steps':             steps,
        'data_source':       cfg.get('data_source'),
        'live_data':         anchor,
        'language':          language,
        'generated':         True,
        'source':            source,
    }


async def _call_llm(prompt: str, provider: str) -> str:
    """
    Run the prompt through the chosen provider.

    Local mode routes via `local_llm_router` with task='fast' (structured JSON
    is the sweet spot for phi3:mini → mistral → tinyllama ladder). This means
    if phi3:mini is unhealthy (e.g. OOM on small hosts), the router automatically
    walks the ladder before reporting failure.

    Auto mode tries cloud → local-router → tinyllama (last-resort), then raises
    so the caller can drop to the stub fallback.
    """
    if provider == 'local':
        resp = await local_llm_router.route(
            task='fast', prompt=prompt, max_tokens=1500, temperature=0.2,
        )
        if resp.error or not resp.content:
            raise RuntimeError(f'Local LLM failed: {resp.error or "empty content"}')
        return resp.content

    if provider == 'cloud':
        resp = await cloud_llm.generate(prompt, max_tokens=1500, temperature=0.2)
        if resp.error or not resp.content:
            raise RuntimeError(f'Cloud LLM failed: {resp.error or "empty content"}')
        return resp.content

    # auto: cloud → local router → raise
    resp = await cloud_llm.generate(prompt, max_tokens=1500, temperature=0.2)
    if resp.content and not resp.error:
        return resp.content
    logger.info(
        'Cloud unavailable (%s); routing to local pool',
        (resp.error or '')[:80],
    )
    resp2 = await local_llm_router.route(
        task='fast', prompt=prompt, max_tokens=1500, temperature=0.2,
    )
    if resp2.content and not resp2.error:
        return resp2.content
    raise RuntimeError(
        f'Both providers failed (cloud={resp.error[:120] if resp.error else "?"}; '
        f'local-router={resp2.error[:120] if resp2.error else "no content"})'
    )


JSON_BLOCK_RE = re.compile(r'\{.*\}', re.S)

def _strict_parse(raw: str) -> dict:
    """Extract and parse the first JSON object in the raw LLM output."""
    raw = raw.strip()
    # Strip markdown fences if model ignored the rule
    if raw.startswith('```'):
        raw = re.sub(r'^```[a-zA-Z0-9_-]*\s*', '', raw)
        raw = re.sub(r'\s*```\s*$', '', raw)
    m = JSON_BLOCK_RE.search(raw)
    if not m:
        raise ValueError(f'No JSON object found in LLM output: {raw[:200]}')
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON from LLM: {e}; head={raw[:200]}')


def _to_scenario(
    feature_id: str, cfg: dict, role: str, language: str,
    parsed: dict, anchor: dict | None,
) -> dict[str, Any]:
    """Validate + shape into the scenario contract."""
    steps_raw = parsed.get('steps')
    if not isinstance(steps_raw, list) or not steps_raw:
        raise ValueError('Generated scenario has no steps array')

    allowed_targets = set(cfg['targets']) | {None, ''}
    allowed_actions = {'dwell', 'click', 'type', 'highlight', 'flash'}

    steps_out: list[dict] = []
    for i, s in enumerate(steps_raw):
        if not isinstance(s, dict):
            continue
        target = s.get('target')
        if target not in allowed_targets and target is not None:
            target = None    # drop invented selectors
        action = s.get('action') or 'dwell'
        if action not in allowed_actions:
            action = 'dwell'
        steps_out.append({
            'id':       (s.get('id') or f'step_{i}')[:64],
            'scene':    cfg['scene'],
            'target':   target,
            'voice':    (s.get('voice') or '')[:600],
            'action':   action,
            'payload':  s.get('payload') if isinstance(s.get('payload'), dict) else None,
            'dwell_ms': int(s.get('dwell_ms') or 600),
        })

    scenario_id = f'gen_{feature_id}_{uuid.uuid4().hex[:8]}'
    return {
        'id':                scenario_id,
        'title':             parsed.get('title') or cfg['title'],
        'description':       parsed.get('description') or cfg['description'],
        'duration_minutes':  int(parsed.get('duration_minutes') or 2),
        'roles':             [role],
        'modules':           [feature_id],
        'scenes':            [cfg['scene']],
        'steps':             steps_out,
        'data_source':       cfg.get('data_source'),
        'live_data':         anchor,      # already anonymised
        'language':          language,
        'generated':         True,
    }


# ── In-memory cache for generated scenarios ──────────────────────────────────

_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_MAX = 64

def cache_put(scenario: dict[str, Any]) -> None:
    sid = scenario['id']
    _CACHE[sid] = scenario
    # Trim oldest if too big
    while len(_CACHE) > _CACHE_MAX:
        oldest = next(iter(_CACHE))
        _CACHE.pop(oldest, None)


def cache_get(scenario_id: str) -> dict[str, Any] | None:
    return _CACHE.get(scenario_id)
