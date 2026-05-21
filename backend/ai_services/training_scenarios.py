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
