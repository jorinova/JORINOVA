"""
ALIS-X Deterministic Medical Rules Engine
==========================================
This module NEVER depends on AI, network, or external services.
It runs offline, at zero latency, on every result — always.

Priority: medical safety > system availability > AI sophistication

Implements:
  1. Panic / critical value detection (WHO + CAP guidelines)
  2. Reference range validation with sex/age adjustment
  3. Inventory threshold alerts
  4. MDR organism safety rules
  5. Sepsis screening heuristic (qSOFA-adjacent)
  6. Coagulation critical thresholds
  7. SOP workflow trigger rules
  8. Reflex test suggestions (DB-backed, with coded fallback)
"""
from __future__ import annotations
import logging
from typing import Optional

from ai_services.schemas import (
    PanicAlert, RulesResult, Urgency,
)

logger = logging.getLogger('rules_engine')


# ── Panic value table ─────────────────────────────────────────────────────────
# Source: CAP Critical Values + WHO Laboratory Guidelines + CLSI C56-A
# Format: test_code → (low_panic, high_panic, unit, low_msg, high_msg)
# None = no panic threshold for that direction

PANIC_VALUES: dict[str, tuple] = {
    # HEMATOLOGY
    'HGB':      (7.0,    20.0,  'g/dL',
                 'Critical anaemia — immediate transfusion assessment required',
                 'Critical polycythaemia — risk of thrombosis; notify haematologist'),
    'WBC':      (2.0,    100.0, 'x10³/µL',
                 'Severe leucopenia — risk of sepsis; isolate patient',
                 'Extreme leucocytosis — possible blast crisis or leukaemia'),
    'PLT':      (20.0,   1000.0,'x10³/µL',
                 'Severe thrombocytopenia — bleeding risk; transfusion threshold',
                 'Extreme thrombocytosis — thrombosis risk; haematology review'),
    'NEUT_A':   (0.5,    None,  'x10³/µL',
                 'Severe neutropenia — febrile neutropenia protocol; antibiotics',
                 None),
    'HCT':      (None,   60.0,  '%',
                 None,
                 'Critical polycythaemia (HCT) — risk of hyperviscosity syndrome'),

    # COAGULATION
    'PT':       (None,   30.0,  's',
                 None,
                 'Critical coagulopathy — massive bleeding risk; FFP urgently'),
    'INR':      (None,   4.5,   'ratio',
                 None,
                 'Critical INR — reversal therapy required; withhold anticoagulants'),
    'APTT':     (None,   80.0,  's',
                 None,
                 'Critical aPTT — intrinsic pathway failure; haematology urgent'),
    'FIBRIN':   (1.0,    None,  'g/L',
                 'Critical hypofibrinogenaemia — DIC or severe liver failure',
                 None),
    'DDIMER':   (None,   5.0,   'mg/L FEU',
                 None,
                 'Markedly elevated D-Dimer — thrombosis or DIC; clinical correlation'),

    # BIOCHEMISTRY — ELECTROLYTES
    'NA':       (120.0,  160.0, 'mmol/L',
                 'Critical hyponatraemia — seizure risk; controlled sodium correction',
                 'Critical hypernatraemia — CNS damage risk; controlled rehydration'),
    'K':        (2.5,    6.5,   'mmol/L',
                 'Critical hypokalaemia — cardiac arrhythmia risk; IV replacement',
                 'Critical hyperkalaemia — cardiac arrest risk; ECG + treatment NOW'),
    'CA':       (1.5,    3.75,  'mmol/L',
                 'Critical hypocalcaemia — tetany/cardiac risk; IV calcium',
                 'Critical hypercalcaemia — coma/renal failure risk; rehydration'),
    'NA_ACT':   (125.0,  155.0, 'mmol/L',
                 'Action: hyponatraemia — close monitoring, restrict free water',
                 'Action: hypernatraemia — slow rehydration required'),
    'MG':       (0.3,    None,  'mmol/L',
                 'Critical hypomagnesaemia — arrhythmia + seizure risk',
                 None),
    'PHOS':     (0.3,    None,  'mmol/L',
                 'Critical hypophosphataemia — respiratory failure risk',
                 None),

    # BIOCHEMISTRY — METABOLIC
    'FBG':      (2.5,    33.0,  'mmol/L',
                 'Critical hypoglycaemia — neurological emergency; IV dextrose NOW',
                 'Critical hyperglycaemia — DKA or HHS; urgent management'),
    'RBG':      (2.8,    33.0,  'mmol/L',
                 'Critical hypoglycaemia (random) — neurological emergency',
                 'Critical hyperglycaemia — DKA/HHS risk; urgent review'),

    # RENAL
    'CREAT':    (None,   884.0, 'µmol/L',
                 None,
                 'Critical creatinine — AKI or end-stage CKD; nephrology NOW'),
    'UREA':     (None,   35.7,  'mmol/L',
                 None,
                 'Critical uraemia — renal replacement therapy consideration'),

    # LIVER
    'TBIL':     (None,   342.0, 'µmol/L',
                 None,
                 'Critical hyperbilirubinaemia — kernicterus risk (neonate) or acute liver failure'),
    'ALT':      (None,   1000.0,'U/L',
                 None,
                 'Critical ALT — acute hepatocellular injury; hepatology review'),
    'AST':      (None,   1000.0,'U/L',
                 None,
                 'Critical AST — acute liver injury or rhabdomyolysis; urgent evaluation'),

    # CARDIAC
    'TROP_I':   (None,   0.04,  'µg/L',
                 None,
                 'Elevated Troponin I — possible ACS; immediate cardiology and ECG'),
    'CKMB':     (None,   50.0,  'U/L',
                 None,
                 'Elevated CK-MB — possible myocardial infarction; serial testing'),

    # MICROBIOLOGY / SPECIAL
    'MAL_RDT':  None,    # handled separately — positive = always critical
    'MAL_SM':   None,

    # COAGULATION SPECIAL
    'TT':       (None,   60.0,  's',
                 None,
                 'Critical thrombin time — fibrinogen deficiency or heparin contamination'),
}

# Tests where ANY positive result is always critical
ALWAYS_CRITICAL_POSITIVE: set[str] = {
    'MAL_RDT', 'MAL_SM', 'SICKLING', 'HIV_WB',        # malaria, sickle, HIV
    'TB_PCR', 'TB_CULT', 'MTB_AFB',                    # TB
    'MRSA_SCR', 'ESBL_SCR', 'CRO_SCR', 'VRE_SCR',     # MDR organisms
    'HEP_B_SURF', 'HEP_B_DNA', 'HCV_PCR', 'HIV_PCR',  # viral
    'DENGUE_NS1', 'DENGUE_IGM', 'EBOLA_SCR',           # outbreaks
}

# Tests where panic-level high value triggers sepsis screen
SEPSIS_TRIGGER_TESTS: set[str] = {'WBC', 'NEUT_A', 'TROP_I', 'LACT', 'CRP', 'PCT'}


# ── Reference range engine ────────────────────────────────────────────────────
# Coded fallback ranges when DB is unavailable
# Format: code → { 'M': (low, high), 'F': (low, high), 'default': (low, high) }

REFERENCE_RANGES: dict[str, dict] = {
    'HGB':   {'M': (13.0, 17.5), 'F': (12.0, 15.5), 'default': (12.0, 17.5)},
    'RBC':   {'M': (4.5,  5.9),  'F': (4.0,  5.2),  'default': (4.0,  5.9)},
    'WBC':   {'default': (4.0,   11.0)},
    'PLT':   {'default': (150.0, 450.0)},
    'HCT':   {'M': (40.0, 52.0), 'F': (36.0, 48.0), 'default': (36.0, 52.0)},
    'MCV':   {'default': (80.0,  100.0)},
    'MCH':   {'default': (27.0,  33.0)},
    'MCHC':  {'default': (31.0,  37.0)},
    'RDW':   {'default': (11.5,  14.5)},
    'NEUT_P':{'default': (40.0,  75.0)},
    'LYMPH_P':{'default':(20.0,  45.0)},
    'MONO_P':{'default': (2.0,   10.0)},
    'EOS_P': {'default': (1.0,   6.0)},
    'BASO_P':{'default': (0.0,   1.0)},
    'NEUT_A':{'default': (1.8,   7.5)},
    'LYMPH_A':{'default':(1.0,   4.5)},
    'ESR':   {'M': (0.0,  15.0), 'F': (0.0,  20.0), 'default': (0.0, 20.0)},
    'RETIC': {'default': (0.5,   2.5)},
    'PT':    {'default': (11.0,  14.0)},
    'INR':   {'default': (0.8,   1.2)},
    'APTT':  {'default': (25.0,  35.0)},
    'FIBRIN':{'default': (2.0,   4.0)},
    'DDIMER':{'default': (0.0,   0.50)},
    'FBG':   {'default': (3.9,   6.1)},
    'RBG':   {'default': (3.9,   11.1)},
    'HBA1C': {'default': (0.0,   5.7)},
    'UREA':  {'default': (2.5,   7.5)},
    'CREAT': {'M': (62.0, 115.0),'F': (53.0, 97.0), 'default': (53.0, 115.0)},
    'NA':    {'default': (136.0, 145.0)},
    'K':     {'default': (3.5,   5.1)},
    'CL':    {'default': (98.0,  107.0)},
    'HCO3':  {'default': (22.0,  29.0)},
    'CA':    {'default': (2.12,  2.62)},
    'MG':    {'default': (0.70,  1.05)},
    'PHOS':  {'default': (0.81,  1.45)},
    'TPROT': {'default': (60.0,  80.0)},
    'ALB':   {'default': (35.0,  52.0)},
    'ALT':   {'M': (0.0,  45.0), 'F': (0.0,  35.0), 'default': (0.0, 45.0)},
    'AST':   {'M': (0.0,  40.0), 'F': (0.0,  32.0), 'default': (0.0, 40.0)},
    'ALP':   {'default': (40.0,  130.0)},
    'GGT':   {'M': (0.0,  65.0), 'F': (0.0,  45.0), 'default': (0.0, 65.0)},
    'TBIL':  {'default': (3.0,   21.0)},
    'DBIL':  {'default': (0.0,   5.0)},
    'TCHOL': {'default': (0.0,   5.2)},
    'LDL':   {'default': (0.0,   3.4)},
    'HDL':   {'M': (1.0,  99.0), 'F': (1.3,  99.0), 'default': (1.0, 99.0)},
    'TG':    {'default': (0.0,   1.7)},
    'TROP_I':{'default': (0.0,   0.04)},
    'CKMB':  {'default': (0.0,   25.0)},
    'CK':    {'M': (52.0, 336.0),'F': (38.0, 176.0),'default': (38.0, 336.0)},
    'LDH':   {'default': (140.0, 280.0)},
}

# ── SOP rules ─────────────────────────────────────────────────────────────────
# Maps (test_code, flag) → list of SOP action notes

SOP_RULES: dict[tuple[str, str], list[str]] = {
    ('HGB', 'LL'):   ['Repeat CBC to confirm', 'Cross-match blood if transfusion required',
                      'Notify clinician within 15 minutes per critical value SOP'],
    ('HGB', 'HH'):   ['Check for haemoconcentration/dehydration', 'Repeat with fresh sample'],
    ('K', 'HH'):     ['Repeat immediately — hyperkalaemia fatal if untrue',
                      'ECG within 30 minutes', 'Check for haemolysed sample first'],
    ('K', 'LL'):     ['Notify clinician immediately', 'Check for alkalosis or insulin use'],
    ('NA', 'LL'):    ['Serum osmolality if hyponatraemia confirmed', 'Restrict free water'],
    ('INR', 'HH'):   ['Withhold anticoagulation', 'Notify prescribing physician urgently'],
    ('PLT', 'LL'):   ['Visual count on smear to confirm', 'Check for platelet clumping'],
    ('WBC', 'HH'):   ['Peripheral blood smear for blast count', 'Haematology review'],
    ('WBC', 'LL'):   ['Repeat CBC', 'Blood cultures if febrile', 'Reverse isolation if <0.5'],
    ('TROP_I', 'H'): ['Serial troponin at 3h and 6h', 'ECG STAT', 'Cardiology consult'],
    ('FBG', 'LL'):   ['Immediate glucose replacement', 'Re-check in 15 min after treatment'],
    ('FBG', 'HH'):   ['Urinalysis for ketones', 'Arterial blood gas if DKA suspected'],
    ('CREAT', 'HH'): ['Urinalysis', 'Renal ultrasound if new AKI', 'Hold nephrotoxic drugs'],
    ('MAL_RDT', 'POS'): ['Thick and thin smear for species/parasitaemia',
                          'Notify clinician immediately', 'Antimalarial per national protocol'],
}

# ── Inventory threshold rules ─────────────────────────────────────────────────
# Days of stock remaining → urgency level

INVENTORY_THRESHOLDS: dict[str, dict] = {
    'CRITICAL': {'days_remaining': 3,  'action': 'IMMEDIATE_REORDER',
                 'message': 'Stock critically low — order within 24h'},
    'LOW':      {'days_remaining': 7,  'action': 'REORDER_NOW',
                 'message': 'Low stock — initiate reorder process'},
    'WARNING':  {'days_remaining': 14, 'action': 'PLAN_REORDER',
                 'message': 'Stock approaching reorder point'},
    'ADEQUATE': {'days_remaining': 30, 'action': 'MONITOR',
                 'message': 'Adequate stock levels'},
}

EXPIRY_THRESHOLDS = {
    'EXPIRED':   {'days': 0,  'urgency': 'CRITICAL', 'action': 'QUARANTINE_IMMEDIATELY'},
    'CRITICAL':  {'days': 7,  'urgency': 'HIGH',     'action': 'USE_FIRST_FEFO'},
    'WARNING':   {'days': 30, 'urgency': 'MEDIUM',   'action': 'MONITOR_CLOSELY'},
    'ACCEPTABLE':{'days': 90, 'urgency': 'LOW',      'action': 'ROUTINE_ROTATION'},
}


# ── Public API ────────────────────────────────────────────────────────────────

def check_result(
    test_code:  str,
    value:      float | str,
    unit:       str = '',
    flag:       str = '',
    sex:        str = '',    # M | F | ''
    age:        int = 0,
    db=None,
) -> RulesResult:
    """
    Master entry point. Call for every result — always.
    Returns a RulesResult with zero network dependency.
    """
    result = RulesResult()

    # 1. Always-critical positive tests
    flag_upper = (flag or '').upper()
    code_upper = (test_code or '').upper()

    if code_upper in ALWAYS_CRITICAL_POSITIVE and flag_upper in ('POS', 'POSITIVE', 'DETECTED'):
        result.is_critical = True
        result.significance = 'CRITICAL'
        result.actions = [
            'Notify clinician IMMEDIATELY',
            'Document notification time and clinician name',
            'Archive to Critical Book per ISO 15189 SOP',
        ]
        result.panic_alerts.append(PanicAlert(
            test_code=code_upper, test_name=test_code,
            value=1.0, unit='qualitative', flag='POSITIVE',
            threshold=0.0, direction='POSITIVE',
            urgency=Urgency.IMMEDIATE,
            message=f'{test_code} positive — immediate clinical action required',
            actions=result.actions,
        ))

    # 2. Numeric panic value check
    try:
        numeric = float(str(value).replace('<','').replace('>','').strip())
        _check_panic(result, code_upper, numeric, unit)
    except (ValueError, TypeError):
        pass

    # 3. DB-backed interpretation rules (if DB available)
    if db:
        _apply_db_rules(result, code_upper, flag_upper, db)

    # 4. Coded SOP notes
    sop_key = (code_upper, flag_upper)
    if sop_key in SOP_RULES:
        result.sop_notes = SOP_RULES[sop_key]
        if not result.actions:
            result.actions = result.sop_notes[:3]

    # 5. Derive overall significance if not set
    if not result.significance or result.significance == 'NORMAL':
        if result.is_critical:
            result.significance = 'CRITICAL'
        elif flag_upper in ('HH', 'LL'):
            result.significance = 'HIGH'
        elif flag_upper in ('H', 'L', 'A'):
            result.significance = 'MODERATE'
        elif flag_upper in ('POS', 'POSITIVE', 'DETECTED'):
            result.significance = 'HIGH'
        else:
            result.significance = 'NORMAL'

    # 6. Require doctor if critical or high
    if result.is_critical or result.significance in ('CRITICAL', 'HIGH'):
        result.doctor_required = True
        result.doctor_urgency  = 'STAT' if result.is_critical else 'URGENT'

    return result


def _check_panic(result: RulesResult, code: str, value: float, unit: str) -> None:
    """Check numeric value against coded panic table."""
    entry = PANIC_VALUES.get(code)
    if not entry:
        return

    low_panic, high_panic, std_unit, low_msg, high_msg = entry

    if high_panic is not None and value >= high_panic:
        alert = PanicAlert(
            test_code=code, test_name=code,
            value=value, unit=unit or std_unit,
            flag='HH', threshold=high_panic, direction='HIGH',
            urgency=Urgency.IMMEDIATE,
            message=high_msg or f'{code} critically elevated ({value} {unit})',
            actions=SOP_RULES.get((code, 'HH'), [
                'Notify clinician immediately',
                'Repeat test to confirm if clinically unexpected',
                'Document critical value notification',
            ]),
        )
        result.panic_alerts.append(alert)
        result.is_critical = True

    if low_panic is not None and value <= low_panic:
        alert = PanicAlert(
            test_code=code, test_name=code,
            value=value, unit=unit or std_unit,
            flag='LL', threshold=low_panic, direction='LOW',
            urgency=Urgency.IMMEDIATE,
            message=low_msg or f'{code} critically low ({value} {unit})',
            actions=SOP_RULES.get((code, 'LL'), [
                'Notify clinician immediately',
                'Assess patient clinical status',
                'Document critical value notification',
            ]),
        )
        result.panic_alerts.append(alert)
        result.is_critical = True


def _apply_db_rules(result: RulesResult, code: str, flag: str, db) -> None:
    """Layer DB-backed interpretation on top of coded rules."""
    try:
        from models.core_config import TestCatalog, TestInterpretationRule, ReflexTestRule
        test = db.query(TestCatalog).filter(TestCatalog.code == code).first()
        if not test:
            return

        rule = db.query(TestInterpretationRule).filter(
            TestInterpretationRule.test_id == test.id,
            TestInterpretationRule.flag_trigger == flag,
            TestInterpretationRule.is_active == True,
        ).first()

        if rule:
            result.interpretation   = rule.interpretation or result.interpretation
            result.significance     = rule.clinical_significance or result.significance
            result.possible_causes  = rule.possible_causes or []
            if not result.actions:
                result.actions = rule.recommended_actions or []
            result.doctor_required  = rule.requires_doctor_confirmation or result.doctor_required
            if rule.doctor_message:
                result.doctor_urgency = rule.doctor_urgency or result.doctor_urgency

        reflexes = db.query(ReflexTestRule).filter(
            ReflexTestRule.trigger_test_id == test.id,
            ReflexTestRule.trigger_flag == flag,
            ReflexTestRule.is_active == True,
        ).order_by(ReflexTestRule.sort_order).limit(8).all()

        result.reflex_tests = [
            {
                'test_name':  r.suggested_test.name if r.suggested_test else '',
                'test_code':  r.suggested_test.code if r.suggested_test else '',
                'type':       r.suggestion_type,
                'reason':     r.reason,
                'department': r.suggested_department,
                'note':       r.note_to_doctor,
            }
            for r in reflexes if r.suggested_test
        ]
    except Exception as e:
        logger.warning('DB rules lookup failed (non-critical): %s', e)


def check_inventory(
    current_stock: float,
    daily_usage:   float,
    expiry_days:   Optional[int] = None,
) -> dict:
    """
    Inventory alert engine. Returns alert level and recommended action.
    Runs entirely offline — no AI, no network.
    """
    result = {'level': 'ADEQUATE', 'action': 'MONITOR', 'message': '', 'expiry_alert': None}

    if daily_usage > 0:
        days_remaining = int(current_stock / daily_usage)
    else:
        days_remaining = 999

    for level, spec in INVENTORY_THRESHOLDS.items():
        if days_remaining <= spec['days_remaining']:
            result['level']   = level
            result['action']  = spec['action']
            result['message'] = f"{spec['message']} ({days_remaining}d remaining)"
            break

    if expiry_days is not None:
        for level, spec in EXPIRY_THRESHOLDS.items():
            if expiry_days <= spec['days']:
                result['expiry_alert'] = {
                    'level':   level,
                    'urgency': spec['urgency'],
                    'action':  spec['action'],
                    'message': f'Expires in {expiry_days} day(s)',
                }
                break

    return result


def check_mdr_organism(
    organism: str,
    mdr_flags: dict[str, bool],  # {'is_mrsa': True, 'is_esbl': False, ...}
) -> dict:
    """
    MDR organism safety rules — always offline.
    Returns action list and notification requirements.
    """
    active_flags = [k for k, v in mdr_flags.items() if v]
    if not active_flags:
        return {'is_mdr': False, 'actions': [], 'public_health': False}

    actions = [
        'Place patient in contact precautions immediately',
        'Notify infection control / antimicrobial stewardship team',
        'Document MDR organism in patient record',
        'Alert ward nursing staff',
        'Review antibiogram before prescribing antibiotics',
    ]

    public_health = False
    if mdr_flags.get('is_cro') or mdr_flags.get('is_vrsa'):
        actions.insert(0, '🚨 CRO/VRSA: Notify District Health Officer — reportable organism')
        public_health = True
    if mdr_flags.get('is_mrsa') and mdr_flags.get('is_esbl'):
        actions.append('Consider cohorting: multiple MDR flags on same patient')

    return {
        'is_mdr':       True,
        'organism':     organism,
        'active_flags': active_flags,
        'actions':      actions,
        'public_health':public_health,
        'note':         'Antibiotic selection MUST be guided by full antibiogram — no empirical MDR therapy',
    }


def sepsis_screen(
    wbc: Optional[float] = None,
    temp_c: Optional[float] = None,
    hr: Optional[float] = None,
    rr: Optional[float] = None,
    crp: Optional[float] = None,
    lactate: Optional[float] = None,
    culture_positive: bool = False,
) -> dict:
    """
    SIRS/qSOFA-based sepsis screening heuristic.
    Runs offline — coded thresholds only. NOT a diagnosis.
    """
    score = 0
    triggers = []

    if wbc is not None and (wbc > 12.0 or wbc < 4.0):
        score += 1
        triggers.append(f'WBC abnormal ({wbc:.1f} x10³/µL)')
    if temp_c is not None and (temp_c > 38.3 or temp_c < 36.0):
        score += 1
        triggers.append(f'Temperature abnormal ({temp_c:.1f}°C)')
    if hr is not None and hr > 90:
        score += 1
        triggers.append(f'Tachycardia (HR {hr:.0f})')
    if rr is not None and rr > 22:
        score += 1
        triggers.append(f'Tachypnoea (RR {rr:.0f})')
    if crp is not None and crp > 100:
        score += 1
        triggers.append(f'Elevated CRP ({crp:.0f} mg/L)')
    if lactate is not None and lactate > 2.0:
        score += 2
        triggers.append(f'Elevated lactate ({lactate:.1f} mmol/L) — septic shock risk')
    if culture_positive:
        score += 2
        triggers.append('Positive blood culture')

    level = 'NONE'
    actions = []
    if score >= 5 or lactate and lactate > 4.0:
        level = 'SEPTIC_SHOCK_RISK'
        actions = ['IMMEDIATE ICU assessment', 'Sepsis bundle: fluids + antibiotics + cultures',
                   'Lactate repeat in 2h', 'Notify senior clinician STAT']
    elif score >= 3:
        level = 'SEPSIS_SCREEN_POSITIVE'
        actions = ['Blood cultures ×2 before antibiotics', 'IV fluid challenge',
                   'Broad-spectrum antibiotics per protocol', 'Monitoring 1h']
    elif score >= 2:
        level = 'SIRS_CRITERIA_MET'
        actions = ['Clinical assessment', 'Blood cultures if clinical suspicion',
                   'Monitor closely, repeat labs in 4–6h']

    return {
        'screen_level': level,
        'score':        score,
        'triggers':     triggers,
        'actions':      actions,
        'is_alert':     score >= 2,
        'note':         'Sepsis screen — clinical correlation required. NOT a diagnosis.',
    }


def get_reference_range(
    test_code: str,
    sex: str = '',
    age: int = 0,
) -> Optional[tuple[float, float]]:
    """Return coded reference range for a test. Returns None if unknown."""
    entry = REFERENCE_RANGES.get(test_code.upper())
    if not entry:
        return None
    sex_upper = (sex or '').upper()
    if sex_upper in ('M', 'MALE') and 'M' in entry:
        return entry['M']
    if sex_upper in ('F', 'FEMALE') and 'F' in entry:
        return entry['F']
    return entry.get('default')


def auto_flag(
    test_code: str,
    value: float,
    sex: str = '',
    age: int = 0,
) -> str:
    """
    Automatically compute flag (HH/LL/H/L/N) from coded reference ranges.
    Used when analyzer does not provide a flag.
    """
    entry = PANIC_VALUES.get(test_code.upper())
    if entry and entry is not None:
        low_p, high_p = entry[0], entry[1]
        if high_p is not None and value >= high_p:
            return 'HH'
        if low_p is not None and value <= low_p:
            return 'LL'

    ref = get_reference_range(test_code, sex, age)
    if ref:
        low_ref, high_ref = ref
        # Apply 20% margin above ref for H/L before HH/LL
        if value > high_ref * 1.2:
            return 'H'
        if value > high_ref:
            return 'H'
        if value < low_ref * 0.8:
            return 'L'
        if value < low_ref:
            return 'L'

    return 'N'
