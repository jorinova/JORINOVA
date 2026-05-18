"""
ALIS-X Sample Rejection Rules Engine
======================================
Deterministic rejection criteria per CLSI EP23-A, ISO 15189:2022, and WHO guidelines.
The AI knows these rules so it can:
  1. Suggest rejection reasons to technicians during reception
  2. Understand WHY a sample was rejected for pattern analysis
  3. Flag recurring rejection sources for QC improvement
  4. Educate staff on proper collection procedures via voice assistant

Rules are:
  - ALWAYS offline (no AI dependency)
  - Linked to specific tests/departments where applicable
  - Carry corrective action instructions
  - Categorised by rejection type and severity
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RejectionCategory(str, Enum):
    PRE_ANALYTICAL  = 'pre_analytical'    # collection/transport issues
    ANALYTICAL      = 'analytical'        # testing-phase issues
    SPECIMEN_QUALITY= 'specimen_quality'  # visible quality problems
    IDENTIFICATION  = 'identification'    # labeling/ID issues
    TUBE_CONTAINER  = 'tube_container'    # wrong container
    VOLUME          = 'volume'            # quantity issues
    TIMING          = 'timing'            # time-related issues
    SAFETY          = 'safety'            # biosafety/contamination


class RejectionSeverity(str, Enum):
    CRITICAL  = 'critical'    # must reject — cannot process
    HIGH      = 'high'        # should reject — result unreliable
    MODERATE  = 'moderate'    # can process with note
    LOW       = 'low'         # advisory only


@dataclass
class RejectionRule:
    code:            str                      # unique rejection code
    name:            str                      # short display name
    description:     str                      # full description for staff
    category:        RejectionCategory
    severity:        RejectionSeverity
    affected_tests:  list[str]               = field(default_factory=list)  # [] = all tests
    affected_depts:  list[str]               = field(default_factory=list)  # [] = all depts
    corrective_action: str                   = ''    # what to do about it
    recollect:       bool                    = True  # requires new specimen?
    ai_context:      str                     = ''    # explanation for AI assistant
    tat_impact:      str                     = ''    # impact on TAT

    def to_dict(self) -> dict:
        return {
            'code':             self.code,
            'name':             self.name,
            'description':      self.description,
            'category':         self.category,
            'severity':         self.severity,
            'affected_tests':   self.affected_tests,
            'affected_depts':   self.affected_depts,
            'corrective_action':self.corrective_action,
            'recollect':        self.recollect,
            'tat_impact':       self.tat_impact,
        }


# ── Rejection rule catalogue ──────────────────────────────────────────────────

REJECTION_RULES: dict[str, RejectionRule] = {

    # ── IDENTIFICATION ──────────────────────────────────────────────────────

    'ID-001': RejectionRule(
        code='ID-001', name='Unlabelled Specimen',
        description='Specimen received with no patient label or identification.',
        category=RejectionCategory.IDENTIFICATION,
        severity=RejectionSeverity.CRITICAL,
        corrective_action=(
            'Do NOT process. Contact requesting unit immediately. '
            'Collect new specimen with proper patient identification. '
            'Two-patient identifiers required: full name + PID or date of birth.'
        ),
        recollect=True,
        ai_context='Unlabelled specimens are the most common cause of patient misidentification — a WHO Never Event.',
    ),

    'ID-002': RejectionRule(
        code='ID-002', name='Mislabelled Specimen',
        description='Patient name on label does not match request form or system.',
        category=RejectionCategory.IDENTIFICATION,
        severity=RejectionSeverity.CRITICAL,
        corrective_action=(
            'Do NOT process. Clarify patient identity with collecting unit. '
            'Never correct the label — collect a new specimen with verified labelling.'
        ),
        recollect=True,
        ai_context='Mislabelled specimens can cause diagnostic errors and are subject to medico-legal action.',
    ),

    'ID-003': RejectionRule(
        code='ID-003', name='Illegible Label',
        description='Patient name, DOB or ID on label is unreadable (smudged, faded, torn).',
        category=RejectionCategory.IDENTIFICATION,
        severity=RejectionSeverity.HIGH,
        corrective_action=(
            'Attempt to verify against electronic system. '
            'If unverifiable, contact ward and request re-labelling or new collection.'
        ),
        recollect=False,
        ai_context='Barcoded labels prevent illegibility — reinforce scanning workflow.',
    ),

    # ── SPECIMEN QUALITY ─────────────────────────────────────────────────────

    'SQ-001': RejectionRule(
        code='SQ-001', name='Gross Haemolysis',
        description='Specimen is visibly red/pink due to red blood cell rupture (haemolysis).',
        category=RejectionCategory.SPECIMEN_QUALITY,
        severity=RejectionSeverity.CRITICAL,
        affected_tests=['K', 'LDH', 'AST', 'ALT', 'TROP_I', 'CKMB', 'HGB', 'RBC', 'PLT',
                        'PT', 'INR', 'APTT', 'FIBRIN'],
        corrective_action=(
            'Reject for potassium, LDH, haematology, coagulation tests. '
            'Falsely elevated K+, LDH, and interference with optical measurements. '
            'Collect fresh specimen — tourniquet time <1 min, avoid vigorous mixing.'
        ),
        recollect=True,
        ai_context='Haemolysis releases intracellular K+ causing falsely elevated potassium — can trigger dangerous treatment decisions.',
        tat_impact='New collection required — adds 1–4 hours',
    ),

    'SQ-002': RejectionRule(
        code='SQ-002', name='Lipaemia / Turbidity',
        description='Specimen appears milky/turbid due to high triglycerides or lipids.',
        category=RejectionCategory.SPECIMEN_QUALITY,
        severity=RejectionSeverity.HIGH,
        affected_tests=['TCHOL', 'HDL', 'LDL', 'TG', 'ALB', 'TPROT', 'TBIL', 'ALT', 'AST', 'NA', 'CL'],
        corrective_action=(
            'Note: lipaemia interferes with photometric assays. '
            'For triglyceride: expected — report with flag. '
            'For electrolytes: request fasting sample if non-urgent. '
            'Ultracentrifugation possible if available.'
        ),
        recollect=False,
        ai_context='Lipaemia causes pseudohyponatraemia and interferes with colorimetric chemistry assays.',
        tat_impact='May proceed with flagged result or await fasting sample',
    ),

    'SQ-003': RejectionRule(
        code='SQ-003', name='Icterus (Severe Jaundice)',
        description='Specimen is dark yellow/orange due to very high bilirubin.',
        category=RejectionCategory.SPECIMEN_QUALITY,
        severity=RejectionSeverity.MODERATE,
        affected_tests=['TBIL', 'DBIL', 'TPROT', 'ALB', 'NA', 'K', 'CRP'],
        corrective_action=(
            'Icterus interferes with colorimetric assays — report with flag. '
            'Bilirubin itself may be interpretable. '
            'Use bichromatic method if available.'
        ),
        recollect=False,
        ai_context='High bilirubin absorbs at similar wavelengths to many assay chromogens, causing false readings.',
    ),

    'SQ-004': RejectionRule(
        code='SQ-004', name='Clotted Anticoagulated Sample',
        description='Sample collected in EDTA or citrate tube shows clot formation.',
        category=RejectionCategory.SPECIMEN_QUALITY,
        severity=RejectionSeverity.CRITICAL,
        affected_tests=['HGB', 'RBC', 'WBC', 'PLT', 'MCV', 'PT', 'INR', 'APTT', 'FIBRIN',
                        'DDIMER', 'HCT', 'RETIC'],
        affected_depts=['HEM', 'COAG'],
        corrective_action=(
            'Reject entirely. Clots consume platelets, coagulation factors, and affect cell counts. '
            'Cause: insufficient mixing (8–10 gentle inversions required) or delayed processing. '
            'Collect new specimen with immediate correct mixing.'
        ),
        recollect=True,
        ai_context='Clotted EDTA causes artefactual thrombocytopenia — falsely low platelet count is a patient safety risk.',
        tat_impact='New collection required',
    ),

    'SQ-005': RejectionRule(
        code='SQ-005', name='Grossly Contaminated / Turbid CSF',
        description='CSF sample appears turbid, contaminated, or clearly bloody without clinical explanation.',
        category=RejectionCategory.SPECIMEN_QUALITY,
        severity=RejectionSeverity.HIGH,
        affected_depts=['MICRO', 'BIOCHEM'],
        corrective_action=(
            'Proceed with caution. Inform clinician immediately — turbid CSF may indicate meningitis. '
            'Traumatic tap must be differentiated from true xanthochromia. '
            'Do not reject if meningitis is suspected — request urgent cell count + protein + glucose + culture.'
        ),
        recollect=False,
        ai_context='Turbid CSF with high WBC suggests bacterial meningitis — a medical emergency. Never hold this specimen.',
    ),

    # ── VOLUME ───────────────────────────────────────────────────────────────

    'VOL-001': RejectionRule(
        code='VOL-001', name='Quantity Not Sufficient (QNS)',
        description='Sample volume is too small to complete all requested tests.',
        category=RejectionCategory.VOLUME,
        severity=RejectionSeverity.HIGH,
        corrective_action=(
            'Prioritise tests with clinician — most critical first. '
            'For blood counts: minimum 1 mL EDTA. '
            'For coagulation: minimum volume to maintain 9:1 blood:citrate ratio. '
            'Collect additional sample if accessible.'
        ),
        recollect=False,
        ai_context='Underfilling citrate tubes alters blood-to-anticoagulant ratio, directly affecting PT/INR accuracy.',
        tat_impact='Partial testing — some tests may not be performed',
    ),

    'VOL-002': RejectionRule(
        code='VOL-002', name='Underfilled Citrate Tube',
        description='Citrate tube (blue top) is less than 90% full — incorrect blood:anticoagulant ratio.',
        category=RejectionCategory.VOLUME,
        severity=RejectionSeverity.CRITICAL,
        affected_tests=['PT', 'INR', 'APTT', 'FIBRIN', 'DDIMER', 'TT'],
        affected_depts=['COAG'],
        corrective_action=(
            'Reject coagulation tests. An underfilled citrate tube has excess anticoagulant, '
            'falsely prolonging PT and aPTT — could cause dangerous anticoagulant under-dosing. '
            'Recollect to exactly the fill line.'
        ),
        recollect=True,
        ai_context='Underfilling citrate tubes is the most common pre-analytical error in coagulation — results are always invalid.',
        tat_impact='New collection required — urgent if patient on anticoagulation',
    ),

    # ── TUBE / CONTAINER ──────────────────────────────────────────────────────

    'TUB-001': RejectionRule(
        code='TUB-001', name='Wrong Tube Type',
        description='Sample collected in incorrect container for the test requested.',
        category=RejectionCategory.TUBE_CONTAINER,
        severity=RejectionSeverity.HIGH,
        corrective_action=(
            'Check required tube colour for each test. '
            'Common errors: glucose in SST (serum — falsely low due to glycolysis), '
            'electrolytes in EDTA (K+ contamination from EDTA). '
            'Recollect in correct tube.'
        ),
        recollect=True,
        ai_context='EDTA contains K-EDTA — a potassium salt — which contaminates serum and causes falsely high potassium.',
    ),

    'TUB-002': RejectionRule(
        code='TUB-002', name='Expired Collection Tube',
        description='Tube expiry date has passed — vacuum may be inadequate, anticoagulant degraded.',
        category=RejectionCategory.TUBE_CONTAINER,
        severity=RejectionSeverity.CRITICAL,
        corrective_action=(
            'Reject expired tubes. An expired EDTA tube may have degraded K2EDTA — unreliable cell counts. '
            'An expired citrate tube may not fill correctly. '
            'Remove expired stock from circulation immediately.'
        ),
        recollect=True,
        ai_context='Expired tube additives are unreliable — patient safety risk in coagulation and haematology.',
    ),

    'TUB-003': RejectionRule(
        code='TUB-003', name='Broken / Leaking Tube',
        description='Collection tube is cracked, leaking, or the stopper is missing or compromised.',
        category=RejectionCategory.SAFETY,
        severity=RejectionSeverity.CRITICAL,
        corrective_action=(
            'BIOSAFETY: Handle with PPE — gloves + eye protection. '
            'Do NOT process. Discard in biohazard container. '
            'Notify sender and request new collection. '
            'Decontaminate any surface exposed to specimen.'
        ),
        recollect=True,
        ai_context='Leaking tubes are a Category B biological substance hazard — biosafety protocol must be followed.',
    ),

    # ── TIMING ───────────────────────────────────────────────────────────────

    'TMG-001': RejectionRule(
        code='TMG-001', name='Collection Time Not Recorded',
        description='Sample has no documented collection time — TAT cannot be calculated, timed tests invalid.',
        category=RejectionCategory.TIMING,
        severity=RejectionSeverity.MODERATE,
        affected_tests=['LACT', 'PT', 'APTT', 'HBA1C'],
        corrective_action=(
            'Request collection time from ward. '
            'For timed tests (cortisol, GTT, creatinine clearance): cannot proceed without collection time. '
            'For routine tests: proceed with note.'
        ),
        recollect=False,
        ai_context='Collection time is essential for timed specimens (cortisol peak/trough, GTT), and for calculating TAT compliance.',
    ),

    'TMG-002': RejectionRule(
        code='TMG-002', name='Delayed Transport — Exceeded Stability',
        description='Specimen arrived outside the acceptable stability window for one or more tests.',
        category=RejectionCategory.TIMING,
        severity=RejectionSeverity.HIGH,
        corrective_action=(
            'Critical stability limits:\n'
            '  Glucose (grey top) — 2h at RT\n'
            '  Blood gas — 15min on ice, 30min at RT\n'
            '  Ammonia — 15min on ice\n'
            '  Coagulation — 4h at RT\n'
            '  Urinalysis — 2h at RT\n'
            'Reject time-sensitive tests. Collect new specimen where possible.'
        ),
        recollect=False,
        ai_context='Glucose continues to be consumed by cells in whole blood — delay causes falsely low glucose, potentially missing hypoglycaemia.',
        tat_impact='Time-sensitive tests must be rejected',
    ),

    'TMG-003': RejectionRule(
        code='TMG-003', name='Stored at Wrong Temperature',
        description='Specimen was stored at incorrect temperature (e.g., frozen when it should not be).',
        category=RejectionCategory.TIMING,
        severity=RejectionSeverity.HIGH,
        corrective_action=(
            'Freezing-thawing causes cell lysis — destroys cells, alters proteins, denatures enzymes. '
            'Do not process haematology after freeze-thaw. '
            'For coagulation: freeze is acceptable for plasma aliquots — but not whole blood. '
            'Document and recollect.'
        ),
        recollect=True,
        ai_context='Freeze-thaw cycles destroy cell membranes — platelet counts and coagulation studies from frozen whole blood are invalid.',
    ),

    # ── SAFETY ───────────────────────────────────────────────────────────────

    'SAF-001': RejectionRule(
        code='SAF-001', name='No Biohazard Label on High-Risk Sample',
        description='Sample from known high-risk patient (HIV, HBV, TB) lacks biohazard marking.',
        category=RejectionCategory.SAFETY,
        severity=RejectionSeverity.HIGH,
        corrective_action=(
            'Apply biohazard label before processing. '
            'Ensure all staff handling are aware and use enhanced PPE. '
            'Verify high-risk status in patient record.'
        ),
        recollect=False,
        ai_context='High-risk sample labelling is required by biosafety Level 2+ protocols and protects all laboratory staff.',
    ),

    # ── PRE-ANALYTICAL ────────────────────────────────────────────────────────

    'PRE-001': RejectionRule(
        code='PRE-001', name='Air Bubbles in Coagulation Sample',
        description='Air bubbles present in citrate tube — affects plasma CO2/bicarbonate and coagulation factors.',
        category=RejectionCategory.PRE_ANALYTICAL,
        affected_tests=['PT', 'INR', 'APTT'],
        severity=RejectionSeverity.HIGH,
        corrective_action=(
            'Reject coagulation tests from aerated specimens. '
            'Air causes CO2 loss → pH rise → factor changes. '
            'Instruct collector to fill tube to fill line without shaking or introducing air.'
        ),
        recollect=True,
        ai_context='Air in citrate tubes artificially shortens PT by altering pH — can mask clotting disorders.',
    ),

    'PRE-002': RejectionRule(
        code='PRE-002', name='Catheter Sample — Contamination Risk',
        description='Sample collected from IV line or central catheter without adequate discard.',
        category=RejectionCategory.PRE_ANALYTICAL,
        severity=RejectionSeverity.HIGH,
        corrective_action=(
            'IV catheter samples have infusion fluid contamination. '
            'Discard the first 5–10 mL before collection (CLSI GP41). '
            'Glucose from dextrose infusion causes falsely elevated results. '
            'Prefer peripheral venepuncture for glucose and electrolytes.'
        ),
        recollect=True,
        ai_context='Glucose and electrolytes collected from dextrose lines can show extreme values — risk of incorrect insulin therapy.',
    ),
}

# ── Tube colour guidance ───────────────────────────────────────────────────────
# For use in rejection book and AI explanations

TUBE_GUIDE = {
    'purple_edta':   {'name':'Purple EDTA', 'tests':['CBC','DIFF','ESR','HbA1c','Blood group'],
                      'mix':8, 'note':'8 gentle inversions immediately after collection'},
    'blue_citrate':  {'name':'Blue Citrate', 'tests':['PT','INR','aPTT','D-Dimer','Fibrinogen'],
                      'mix':3, 'note':'3–4 gentle inversions; fill to mark exactly (9:1 ratio)'},
    'grey_fluoride': {'name':'Grey Fluoride', 'tests':['Glucose','Lactate'],
                      'mix':8, 'note':'8 inversions; prevents glycolysis — deliver within 2h'},
    'yellow_sst':    {'name':'Yellow SST/Gold', 'tests':['Biochemistry','Hormones','Serology'],
                      'mix':5, 'note':'5 inversions; allow 30 min clotting before centrifuge'},
    'green_heparin': {'name':'Green Lithium Heparin', 'tests':['Stat chemistry','ionised Ca','Blood gas'],
                      'mix':8, 'note':'8 inversions; process within 30 min for stat'},
    'red_plain':     {'name':'Red (no additive)', 'tests':['Serology','Drug levels','Special'],
                      'mix':0, 'note':'Do not mix — allow to clot fully'},
    'pink_edta':     {'name':'Pink EDTA', 'tests':['Blood bank','Crossmatch','Blood group'],
                      'mix':8, 'note':'Same as purple but dedicated for transfusion medicine'},
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_rule(code: str) -> dict | None:
    r = REJECTION_RULES.get(code)
    return r.to_dict() if r else None

def get_all_rules() -> list[dict]:
    return [r.to_dict() for r in REJECTION_RULES.values()]

def get_by_category(category: str) -> list[dict]:
    return [r.to_dict() for r in REJECTION_RULES.values() if r.category == category]

def get_by_severity(severity: str) -> list[dict]:
    return [r.to_dict() for r in REJECTION_RULES.values() if r.severity == severity]

def suggest_for_test(test_code: str) -> list[dict]:
    """Return rejection rules that are relevant for a specific test code."""
    relevant = []
    for r in REJECTION_RULES.values():
        if not r.affected_tests or test_code in r.affected_tests:
            relevant.append(r.to_dict())
    return relevant

def suggest_for_observation(
    is_haemolysed: bool = False,
    is_lipaemic:   bool = False,
    is_clotted:    bool = False,
    is_qns:        bool = False,
    wrong_tube:    bool = False,
    no_label:      bool = False,
    expired_tube:  bool = False,
    leaking:       bool = False,
    delayed:       bool = False,
) -> list[dict]:
    """Return applicable rejection rules based on observed specimen characteristics."""
    codes = []
    if no_label:      codes.append('ID-001')
    if leaking:       codes.append('TUB-003')
    if expired_tube:  codes.append('TUB-002')
    if is_haemolysed: codes.append('SQ-001')
    if is_lipaemic:   codes.append('SQ-002')
    if is_clotted:    codes.append('SQ-004')
    if is_qns:        codes.append('VOL-001')
    if wrong_tube:    codes.append('TUB-001')
    if delayed:       codes.append('TMG-002')
    return [REJECTION_RULES[c].to_dict() for c in codes if c in REJECTION_RULES]

def get_tube_guide() -> dict:
    return TUBE_GUIDE

def ai_summary() -> str:
    """Return a summary of rejection rules for AI system prompt injection."""
    lines = ['Sample rejection rules in ALIS-X (CLSI EP23 / ISO 15189):']
    for code, rule in REJECTION_RULES.items():
        lines.append(f'  {code} ({rule.severity}): {rule.name} — {rule.corrective_action[:100]}')
    return '\n'.join(lines)
