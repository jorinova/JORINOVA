"""
Training Scenarios Catalog
==========================
Static catalog of guided demos / training scenarios. Each scenario is a sequence
of steps that the frontend training runner executes (move virtual cursor, narrate,
perform a UI action, dwell).

Steps are intentionally UI-agnostic: they reference logical scene IDs and CSS
selectors that the corresponding scene component on the frontend exposes.
This file is the single source of truth — the frontend fetches it via
GET /api/v1/training/scenarios.
"""
from __future__ import annotations

from typing import Any


# Step shape:
#   id              str          — unique within the scenario
#   scene           str          — frontend scene component identifier
#   target          str | None   — CSS selector inside the scene; null = no movement
#   voice           str          — TTS narration
#   action          str | None   — click | type | highlight | flash | navigate | dwell
#   payload         dict | None  — action-specific data (text to type, css class …)
#   dwell_ms        int          — pause AFTER the action before the next step

SCENARIOS: list[dict[str, Any]] = [
    {
        'id':         'specimen_intake_stat',
        'title':      'Receive a STAT sample',
        'description': 'Walk through scanning a STAT-priority barcode, looking up the patient, and printing aliquot labels.',
        'duration_minutes': 2,
        'roles':      ['receptionist', 'lab_technician', 'lab_manager'],
        'modules':    ['reception', 'worklist'],
        'scenes':     ['specimen_intake'],
        'data_source': {
            'entity':     'lab_request',
            'feature_id': 'specimen_intake_stat',
            'filter':     {'priority': 'stat'},
        },
        'steps': [
            {
                'id':     'intro',
                'scene':  'specimen_intake',
                'target': None,
                'voice':  'Welcome. We will walk through receiving a STAT priority specimen.',
                'action': 'dwell',
                'dwell_ms': 700,
            },
            {
                'id':     'focus_scanner',
                'scene':  'specimen_intake',
                'target': '[data-train="scanner"]',
                'voice':  'First, place the cursor in the barcode scanner field.',
                'action': 'click',
                'dwell_ms': 400,
            },
            {
                'id':     'type_barcode',
                'scene':  'specimen_intake',
                'target': '[data-train="scanner"]',
                'voice':  'Now we simulate scanning the tube. Barcode S-I-D dash zero-one-zero-one.',
                'action': 'type',
                'payload': {'text': 'SID-0101', 'into': '[data-train="scanner"]'},
                'dwell_ms': 600,
            },
            {
                'id':     'highlight_patient',
                'scene':  'specimen_intake',
                'target': '[data-train="patient-card"]',
                'voice':  'The patient is now identified: Mary Uwineza, female, twenty-eight years old.',
                'action': 'highlight',
                'payload': {'cls': 'trainPulseBlue'},
                'dwell_ms': 800,
            },
            {
                'id':     'flag_priority',
                'scene':  'specimen_intake',
                'target': '[data-train="priority-chip"]',
                'voice':  'Priority is STAT. The system will route this specimen to the front of the worklist.',
                'action': 'flash',
                'payload': {'cls': 'trainPulseRed'},
                'dwell_ms': 1000,
            },
            {
                'id':     'print_labels',
                'scene':  'specimen_intake',
                'target': '[data-train="print-btn"]',
                'voice':  'Click Print to generate the aliquot labels.',
                'action': 'click',
                'payload': {'cls': 'trainPrinted'},
                'dwell_ms': 700,
            },
            {
                'id':     'done',
                'scene':  'specimen_intake',
                'target': '[data-train="status"]',
                'voice':  'Labels printed. The specimen is now in the worklist with STAT priority.',
                'action': 'highlight',
                'payload': {'cls': 'trainPulseGreen'},
                'dwell_ms': 600,
            },
        ],
    },
    {
        'id':         'critical_value_validation',
        'title':      'Validate a critical CBC',
        'description': 'A CBC came back with elevated WBC. Review the data, acknowledge the flag, and authorize the result.',
        'duration_minutes': 2,
        'roles':      ['lab_technician', 'pathologist', 'lab_manager'],
        'modules':    ['hematology', 'laboratory'],
        'scenes':     ['critical_cbc'],
        'data_source': {
            'entity':     'lab_request',
            'feature_id': 'critical_cbc',
            'filter':     {'has_critical_result': True},
        },
        'steps': [
            {
                'id':     'intro',
                'scene':  'critical_cbc',
                'target': None,
                'voice':  'Welcome. This scenario reviews a CBC with a critical White Blood Cell count.',
                'action': 'dwell',
                'dwell_ms': 700,
            },
            {
                'id':     'search_patient',
                'scene':  'critical_cbc',
                'target': '[data-train="search"]',
                'voice':  'Accessing patient records for ID One-Zero-One.',
                'action': 'type',
                'payload': {'text': 'One-Zero-One', 'into': '[data-train="search"]'},
                'dwell_ms': 500,
            },
            {
                'id':     'show_results',
                'scene':  'critical_cbc',
                'target': '[data-train="lab-panel"]',
                'voice':  'Analyzing laboratory data. Hemoglobin is normal, but White Blood Cell count is elevated at 15,000 cells per microliter. Flagging mild leukocytosis.',
                'action': 'flash',
                'payload': {'cls': 'trainPulseRed', 'target': '[data-train="wbc-row"]'},
                'dwell_ms': 1100,
            },
            {
                'id':     'approve',
                'scene':  'critical_cbc',
                'target': '[data-train="approve"]',
                'voice':  'No critical panic values exceed the threshold. Approving and signing the result under Jorinova Nexus protocols.',
                'action': 'click',
                'payload': {'cls': 'trainApproved'},
                'dwell_ms': 700,
            },
            {
                'id':     'done',
                'scene':  'critical_cbc',
                'target': '[data-train="approve"]',
                'voice':  'Authorized. Result has been digitally signed and transmitted.',
                'action': 'dwell',
                'dwell_ms': 500,
            },
        ],
    },
    {
        'id':         'lis_mapping_walkthrough',
        'title':      'Upload a lab request form (OCR)',
        'description': 'Drop a scanned request form and watch the system extract patient and tests, then confirm the worklist.',
        'duration_minutes': 2,
        'roles':      ['receptionist', 'lab_technician', 'lab_manager', 'super_admin'],
        'modules':    ['lis_mapping'],
        'scenes':     ['lis_mapping_demo'],
        'data_source': {
            'entity':     'lab_request',
            'feature_id': 'lis_mapping_walkthrough',
            'filter':     {},
        },
        'steps': [
            {
                'id':     'intro',
                'scene':  'lis_mapping_demo',
                'target': None,
                'voice':  'Welcome. We will demonstrate the LIS auto-mapping feature.',
                'action': 'dwell',
                'dwell_ms': 700,
            },
            {
                'id':     'highlight_drop',
                'scene':  'lis_mapping_demo',
                'target': '[data-train="dropzone"]',
                'voice':  'A scanned lab request is dropped into the upload area.',
                'action': 'highlight',
                'payload': {'cls': 'trainPulseBlue'},
                'dwell_ms': 700,
            },
            {
                'id':     'extract',
                'scene':  'lis_mapping_demo',
                'target': '[data-train="extract-btn"]',
                'voice':  'The Extract draft button starts the OCR and matching pipeline.',
                'action': 'click',
                'dwell_ms': 600,
            },
            {
                'id':     'reveal_draft',
                'scene':  'lis_mapping_demo',
                'target': '[data-train="draft"]',
                'voice':  'In a moment the patient, the tests, and the priority appear with confidence chips. CBC is expanded into nine individual tests.',
                'action': 'highlight',
                'payload': {'cls': 'trainRevealCard'},
                'dwell_ms': 1100,
            },
            {
                'id':     'confirm',
                'scene':  'lis_mapping_demo',
                'target': '[data-train="confirm-btn"]',
                'voice':  'After review, the user clicks Create LabRequest. The worklist is now populated.',
                'action': 'click',
                'payload': {'cls': 'trainApproved'},
                'dwell_ms': 800,
            },
            {
                'id':     'done',
                'scene':  'lis_mapping_demo',
                'target': '[data-train="result"]',
                'voice':  'LabRequest created. The end-to-end mapping is now complete.',
                'action': 'highlight',
                'payload': {'cls': 'trainPulseGreen'},
                'dwell_ms': 600,
            },
        ],
    },

    {
        'id':         'blood_bank_crossmatch_demo',
        'title':      'Blood bank: chamber/slot crossmatch',
        'description': 'Pick a bag from the slot grid, run an Indirect Antiglobulin crossmatch, and issue the unit under haemovigilance watch.',
        'duration_minutes': 3,
        'roles':      ['lab_technician', 'lab_manager', 'super_admin'],
        'modules':    ['blood_bank'],
        'scenes':     ['blood_bank_crossmatch'],
        'data_source': {
            'entity':     'blood_bag',
            'feature_id': 'blood_bank_crossmatch',
            'filter':     {},
        },
        'steps': [
            {'id': 'intro',          'scene': 'blood_bank_crossmatch', 'target': None,
             'voice': 'Welcome. We will demonstrate a blood-bank crossmatch with chamber and slot tracking.',
             'action': 'dwell', 'payload': None, 'dwell_ms': 700},
            {'id': 'show_bag',       'scene': 'blood_bank_crossmatch', 'target': '[data-train="bag-card"]',
             'voice': 'Here is the selected bag. The system shows blood group, component, volume, and expiry.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseBlue'}, 'dwell_ms': 900},
            {'id': 'show_slots',     'scene': 'blood_bank_crossmatch', 'target': '[data-train="slot-grid"]',
             'voice': 'The bag is tracked at the fridge, chamber, and numbered slot level. FIFO and FEFO rules picked this exact unit.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseBlue'}, 'dwell_ms': 1000},
            {'id': 'do_crossmatch',  'scene': 'blood_bank_crossmatch', 'target': '[data-train="crossmatch-btn"]',
             'voice': 'The technician triggers the Indirect Antiglobulin crossmatch.',
             'action': 'click', 'payload': {'cls': 'trainApproved'}, 'dwell_ms': 700},
            {'id': 'issue_unit',     'scene': 'blood_bank_crossmatch', 'target': '[data-train="issue-btn"]',
             'voice': 'Compatible result. The unit is issued and the haemovigilance watch is armed.',
             'action': 'click', 'payload': {'cls': 'trainApproved'}, 'dwell_ms': 700},
            {'id': 'done',           'scene': 'blood_bank_crossmatch', 'target': '[data-train="status"]',
             'voice': 'Transfusion clock started. Any reaction will auto-link to this bag.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseGreen'}, 'dwell_ms': 600},
        ],
    },

    {
        'id':         'momo_billing_demo',
        'title':      'MoMo payment at reception',
        'description': 'Confirm a lab bill, accept Mobile Money payment, capture the reference, and release the worklist.',
        'duration_minutes': 2,
        'roles':      ['receptionist', 'lab_manager', 'super_admin'],
        'modules':    ['billing'],
        'scenes':     ['momo_billing'],
        'data_source': {
            'entity':     'billing_record',
            'feature_id': 'momo_billing',
            'filter':     {},
        },
        'steps': [
            {'id': 'intro',         'scene': 'momo_billing', 'target': None,
             'voice': 'Welcome. We will accept a Mobile Money payment for a confirmed lab bill.',
             'action': 'dwell', 'payload': None, 'dwell_ms': 700},
            {'id': 'show_invoice',  'scene': 'momo_billing', 'target': '[data-train="invoice"]',
             'voice': 'The invoice was auto-generated from the requested tests using the test catalogue prices.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseBlue'}, 'dwell_ms': 900},
            {'id': 'type_ref',      'scene': 'momo_billing', 'target': '[data-train="momo-input"]',
             'voice': 'The receptionist enters the MoMo reference returned by the patient.',
             'action': 'type', 'payload': {'text': 'MTN-7842-3091', 'into': '[data-train="momo-input"]'}, 'dwell_ms': 600},
            {'id': 'confirm',       'scene': 'momo_billing', 'target': '[data-train="confirm-btn"]',
             'voice': 'Confirming the payment registers the receipt and matches it to the bill.',
             'action': 'click', 'payload': {'cls': 'trainApproved'}, 'dwell_ms': 700},
            {'id': 'show_receipt',  'scene': 'momo_billing', 'target': '[data-train="receipt"]',
             'voice': 'The receipt now shows the MoMo reference, the method, and the paid amount.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseGreen'}, 'dwell_ms': 800},
            {'id': 'done',          'scene': 'momo_billing', 'target': '[data-train="status"]',
             'voice': 'The bill is settled. The worklist is now released to the analyzer floor.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseGreen'}, 'dwell_ms': 600},
        ],
    },

    {
        'id':         'medgenome_pcr_demo',
        'title':      'MedGenome: TB GeneXpert interpretation',
        'description': 'Review a GeneXpert MTB/RIF Ultra run, read the Ct value, check the rifampicin resistance call, then route the signal.',
        'duration_minutes': 3,
        'roles':      ['pathologist', 'lab_technician', 'lab_manager', 'super_admin'],
        'modules':    ['molecular'],
        'scenes':     ['medgenome_pcr'],
        'data_source': {
            'entity':     'pcr_result',
            'feature_id': 'medgenome_pcr',
            'filter':     {'category': 'TB'},
        },
        'steps': [
            {'id': 'intro',          'scene': 'medgenome_pcr', 'target': None,
             'voice': 'Welcome. We will interpret a GeneXpert MTB and Rif Ultra result.',
             'action': 'dwell', 'payload': None, 'dwell_ms': 700},
            {'id': 'show_pcr',       'scene': 'medgenome_pcr', 'target': '[data-train="pcr-card"]',
             'voice': 'Here is the PCR run, with the test name, instrument, cartridge, and result.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseBlue'}, 'dwell_ms': 900},
            {'id': 'show_ct',        'scene': 'medgenome_pcr', 'target': '[data-train="ct-value"]',
             'voice': 'The Cycle threshold value places this case in a medium bacillary load band.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseBlue'}, 'dwell_ms': 900},
            {'id': 'show_rif',       'scene': 'medgenome_pcr', 'target': '[data-train="resistance"]',
             'voice': 'Rifampicin resistance is checked. Detected resistance escalates to multi-drug-resistance protocol.',
             'action': 'flash', 'payload': {'cls': 'trainPulseRed'}, 'dwell_ms': 1000},
            {'id': 'interpret',      'scene': 'medgenome_pcr', 'target': '[data-train="interpret-btn"]',
             'voice': 'AI interpretation synthesises the Ct, semi-quant band, and resistance markers into a clinical summary.',
             'action': 'click', 'payload': {'cls': 'trainApproved'}, 'dwell_ms': 700},
            {'id': 'route',          'scene': 'medgenome_pcr', 'target': '[data-train="route-btn"]',
             'voice': 'The case is routed into the molecular epidemiology surveillance signal pipeline.',
             'action': 'click', 'payload': {'cls': 'trainApproved'}, 'dwell_ms': 700},
        ],
    },

    {
        'id':         'iot_analyzer_intake_demo',
        'title':      'IoT: any analyzer, one contract',
        'description': 'Demonstrate vendor-neutral analyzer ingestion. Pick an adapter, accept the payload, and watch the result normalise.',
        'duration_minutes': 2,
        'roles':      ['lab_technician', 'lab_manager', 'super_admin'],
        'modules':    ['interoperability', 'laboratory'],
        'scenes':     ['iot_analyzer_intake'],
        'data_source': None,
        'steps': [
            {'id': 'intro',         'scene': 'iot_analyzer_intake', 'target': None,
             'voice': 'Good day. Thank you for taking time today. This demo shows how any laboratory analyzer connects to the system.',
             'action': 'dwell', 'payload': None, 'dwell_ms': 800},
            {'id': 'show_list',     'scene': 'iot_analyzer_intake', 'target': '[data-train="adapter-list"]',
             'voice': 'Here is the live list of analyzer adapters. We are not locked to one brand. Sysmex, Roche, Mindray, BioRad, Beckman, any vendor can plug in.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseBlue'}, 'dwell_ms': 1100},
            {'id': 'show_selected', 'scene': 'iot_analyzer_intake', 'target': '[data-train="selected-adapter"]',
             'voice': 'When the technician selects an adapter, the system knows the wire format and the vendor.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseBlue'}, 'dwell_ms': 900},
            {'id': 'show_payload',  'scene': 'iot_analyzer_intake', 'target': '[data-train="payload-preview"]',
             'voice': 'This is what the analyzer sends. Some send HL7, some send ASTM, some send JSON or CSV. The adapter understands them all.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseBlue'}, 'dwell_ms': 1000},
            {'id': 'do_ingest',     'scene': 'iot_analyzer_intake', 'target': '[data-train="ingest-btn"]',
             'voice': 'Ingest into the laboratory information system.',
             'action': 'click', 'payload': {'cls': 'trainApproved'}, 'dwell_ms': 700},
            {'id': 'done',          'scene': 'iot_analyzer_intake', 'target': '[data-train="result-feed"]',
             'voice': 'All payloads end up in the same shape. Sample identifier, test code, value, flag. You are welcome. Have a nice day.',
             'action': 'highlight', 'payload': {'cls': 'trainPulseGreen'}, 'dwell_ms': 800},
        ],
    },
]


def list_scenarios() -> list[dict[str, Any]]:
    """Return summary view for the picker (no step bodies)."""
    return [
        {
            'id':                s['id'],
            'title':             s['title'],
            'description':       s['description'],
            'duration_minutes':  s['duration_minutes'],
            'roles':             s['roles'],
            'modules':           s['modules'],
            'scenes':            s['scenes'],
            'step_count':        len(s['steps']),
        }
        for s in SCENARIOS
    ]


def get_scenario(scenario_id: str) -> dict[str, Any] | None:
    """Return the full scenario including steps."""
    for s in SCENARIOS:
        if s['id'] == scenario_id:
            return s
    return None
