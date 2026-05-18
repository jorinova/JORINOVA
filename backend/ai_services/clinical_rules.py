"""
JORINOVA NEXUS ALIS-X — Clinical Interpretation Rules Engine
=============================================================
CRITICAL PATIENT SAFETY SYSTEM — Every rule here directly affects
clinical decisions. Rules are based on:
  - CLSI EP28-A3c: Defining, Establishing, and Verifying Reference Intervals
  - WHO Laboratory Quality Standards
  - BCSH (British Committee for Standards in Haematology)
  - ESH/EHA Haematology Guidelines
  - WHO/IUIS Immunology Guidelines
  - CLSI C28-A3c: Reference Intervals
  - IFCC Biochemistry Standards
  - ECMM/ISHAM Mycology Guidelines

⚠️  ANY MODIFICATION MUST BE REVIEWED BY A QUALIFIED PATHOLOGIST
⚠️  THESE RULES ARE DECISION SUPPORT ONLY — NOT FINAL DIAGNOSIS
⚠️  CRITICAL VALUES REQUIRE IMMEDIATE CLINICIAN NOTIFICATION

All reference ranges are for ADULTS unless otherwise specified.
Sex-specific and paediatric ranges are flagged.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Significance(str, Enum):
    CRITICAL  = 'CRITICAL'    # Life-threatening — notify clinician NOW
    HIGH      = 'HIGH'        # Urgent clinical action needed
    MODERATE  = 'MODERATE'    # Warrants investigation
    LOW       = 'LOW'         # Mildly abnormal — monitor
    NORMAL    = 'NORMAL'      # Within reference range


@dataclass
class InterpretationResult:
    """Structured clinical interpretation output."""
    test_code:       str
    test_name:       str
    value:           float | str | None
    unit:            str
    flag:            str              # N|L|H|LL|HH|POS|NEG|A
    significance:    Significance
    interpretation:  str              # Main clinical statement
    possible_causes: list[str]        = field(default_factory=list)
    recommended_actions: list[str]    = field(default_factory=list)
    reflex_tests:    list[str]        = field(default_factory=list)
    is_critical:     bool             = False
    critical_message:str              = ''
    differential_dx: list[dict]       = field(default_factory=list)
    indices:         dict             = field(default_factory=dict)
    panel_pattern:   str              = ''     # Named syndrome/pattern


# ══ HAEMATOLOGY RULES ════════════════════════════════════════════

class HaematologyRules:
    """
    Complete blood count interpretation including:
    - CBC with full differential (Sysmex XN / ADVIA format)
    - Anemia classification (IDA, Thalassemia, B12/Folate, Haemolytic...)
    - WBC differential interpretation
    - Platelet interpretation
    - Critical value alerts
    """

    # ── Reference ranges (Adults, sea level) ──────────────────────
    REF = {
        # Parameter: (lo_M, hi_M, lo_F, hi_F, crit_lo, crit_hi, unit)
        'HGB':   (13.0, 17.5, 12.0, 15.5, 7.0,  None, 'g/dL'),
        'RBC':   (4.5,  5.9,  4.0,  5.2,  None, None, '×10¹²/L'),
        'WBC':   (4.0,  11.0, 4.0,  11.0, 2.0,  30.0, '×10³/µL'),
        'PLT':   (150,  450,  150,  450,  20,   1000, '×10³/µL'),
        'HCT':   (40.0, 52.0, 36.0, 48.0, None, None, '%'),
        'MCV':   (80.0, 100,  80.0, 100,  None, None, 'fL'),
        'MCH':   (27.0, 33.0, 27.0, 33.0, None, None, 'pg'),
        'MCHC':  (31.5, 35.5, 31.5, 35.5, None, None, 'g/dL'),
        'RDW_CV':(11.5, 14.5, 11.5, 14.5, None, None, '%'),
        'RDW_SD':(37.0, 54.0, 37.0, 54.0, None, None, 'fL'),
        'MPV':   (7.5,  12.5, 7.5,  12.5, None, None, 'fL'),
        'PDW':   (9.0,  17.0, 9.0,  17.0, None, None, '%'),
        'PCT':   (0.15, 0.40, 0.15, 0.40, None, None, '%'),
        'ESR':   (None, 15,   None, 20,   None, None, 'mm/h'),  # <15 M, <20 F
        'RETIC': (0.5,  2.5,  0.5,  2.5,  None, None, '%'),
        # WBC Differential — Absolute counts (×10³/µL)
        'NEU_A': (1.8,  7.5,  1.8,  7.5,  0.5,  None, '×10³/µL'),
        'LYM_A': (1.0,  4.5,  1.0,  4.5,  None, None, '×10³/µL'),
        'MON_A': (0.2,  1.0,  0.2,  1.0,  None, None, '×10³/µL'),
        'EOS_A': (0.0,  0.5,  0.0,  0.5,  None, None, '×10³/µL'),
        'BAS_A': (0.0,  0.1,  0.0,  0.1,  None, None, '×10³/µL'),
        # WBC Differential — Percentages
        'NEU_P': (40.0, 75.0, 40.0, 75.0, None, None, '%'),
        'LYM_P': (20.0, 45.0, 20.0, 45.0, None, None, '%'),
        'MON_P': (2.0,  10.0, 2.0,  10.0, None, None, '%'),
        'EOS_P': (1.0,  6.0,  1.0,  6.0,  None, None, '%'),
        'BAS_P': (0.0,  1.0,  0.0,  1.0,  None, None, '%'),
    }

    # ── Anemia classification ──────────────────────────────────────
    @staticmethod
    def classify_anemia(hgb: float, mcv: float, mch: float, mchc: float,
                        rdw: float, rbc: float, sex: str = 'M',
                        retic: Optional[float] = None,
                        serum_iron: Optional[float] = None,
                        ferritin: Optional[float] = None,
                        tibc: Optional[float] = None,
                        b12: Optional[float] = None,
                        folate: Optional[float] = None,
                        ldh: Optional[float] = None,
                        bilirubin: Optional[float] = None) -> dict:
        """
        Classify anaemia by MCV pattern with differential diagnosis.
        Based on BCSH Guidelines for the Investigation of Anaemia (2018).

        Mentzer Index = MCV / RBC
          < 13  → Thalassemia trait (more likely)
          > 13  → Iron Deficiency Anaemia (more likely)

        England-Fraser Index = (MCV² × MCH) / (HGB × 100)
          Used to differentiate IDA from Thalassemia

        Returns structured differential diagnosis.
        """
        hgb_lo = 13.0 if sex.upper() == 'M' else 12.0
        is_anaemic = hgb < hgb_lo

        result = {
            'is_anaemic': is_anaemic,
            'severity': None,
            'morphology': None,
            'type': None,
            'differential': [],
            'indices': {},
            'recommended_workup': [],
            'interpretation': '',
            'critical': hgb < 7.0,
        }

        if not is_anaemic:
            result['interpretation'] = 'Haemoglobin within reference range. No anaemia detected.'
            return result

        # Severity
        if hgb >= 10.0:    result['severity'] = 'Mild anaemia'
        elif hgb >= 8.0:   result['severity'] = 'Moderate anaemia'
        elif hgb >= 6.0:   result['severity'] = 'Severe anaemia'
        else:              result['severity'] = 'Very severe anaemia — life-threatening'

        # Mentzer Index
        mentzer = round(mcv / rbc, 1) if rbc > 0 else None
        result['indices']['mentzer'] = mentzer
        mentzer_interp = 'Thalassemia trait favoured (< 13)' if (mentzer and mentzer < 13) else 'IDA favoured (> 13)'

        # England-Fraser Index
        ef_index = round((mcv**2 * mch) / (hgb * 100), 2) if hgb > 0 else None
        result['indices']['england_fraser'] = ef_index

        # MCV-based classification
        if mcv < 80:
            # ── MICROCYTIC ANAEMIA ─────────────────────────────────
            result['morphology'] = 'Microcytic'
            if mchc < 31.5:
                result['morphology'] += ' hypochromic'

            # Pattern analysis
            dx_list = []

            # 1. Iron Deficiency Anaemia (IDA)
            ida_score = 0
            ida_features = []
            if rdw > 14.5:  ida_score += 2; ida_features.append('Elevated RDW (anisocytosis — typical of IDA)')
            if mentzer and mentzer > 13: ida_score += 2; ida_features.append(f'Mentzer index {mentzer} > 13 (favours IDA)')
            if rbc < 3.8:   ida_score += 1; ida_features.append('Low RBC count (expected in IDA)')
            if ferritin is not None and ferritin < 12: ida_score += 3; ida_features.append(f'Low ferritin {ferritin} µg/L (diagnostic of depleted iron stores)')
            if serum_iron is not None and serum_iron < 9: ida_score += 2; ida_features.append(f'Low serum iron {serum_iron} µmol/L')
            if tibc is not None and tibc > 70: ida_score += 2; ida_features.append(f'Elevated TIBC {tibc} µmol/L (iron deficiency pattern)')

            dx_list.append({
                'diagnosis': 'Iron Deficiency Anaemia (IDA)',
                'likelihood': 'High' if ida_score >= 4 else ('Moderate' if ida_score >= 2 else 'Possible'),
                'score': ida_score,
                'features': ida_features,
                'key_differences': [
                    'RDW elevated (cells of unequal size)',
                    'Serum ferritin LOW (iron stores depleted)',
                    'Serum iron LOW, TIBC HIGH',
                    'Mentzer index > 13',
                    'Blood film: pencil cells, hypochromic microcytes, anisocytosis, poikilocytosis',
                ],
                'confirmatory': ['Serum ferritin', 'Serum iron + TIBC', 'Blood film', 'Reticulocyte count'],
                'treatment': 'Oral ferrous sulphate 200mg TDS × 3 months after Hb normalises',
            })

            # 2. Thalassaemia Trait (α or β)
            thal_score = 0
            thal_features = []
            if rdw <= 14.5: thal_score += 2; thal_features.append('Normal/low RDW (uniform small cells — typical of thalassaemia)')
            if mentzer and mentzer < 13: thal_score += 2; thal_features.append(f'Mentzer index {mentzer} < 13 (favours thalassaemia)')
            if rbc > 5.0:   thal_score += 2; thal_features.append(f'High/normal RBC count {rbc} ×10¹²/L despite low Hb (paradox of thalassaemia)')
            if ferritin is not None and ferritin >= 12: thal_score += 2; thal_features.append(f'Normal ferritin {ferritin} µg/L (iron stores intact)')

            dx_list.append({
                'diagnosis': 'Thalassaemia Trait (α or β)',
                'likelihood': 'High' if thal_score >= 4 else ('Moderate' if thal_score >= 2 else 'Possible'),
                'score': thal_score,
                'features': thal_features,
                'key_differences': [
                    'RDW NORMAL or only mildly elevated (uniform microcytosis)',
                    'RBC count ELEVATED or high-normal (>5.0 ×10¹²/L) despite low Hb',
                    'Mentzer index < 13',
                    'Ferritin NORMAL (iron stores intact)',
                    'Blood film: target cells, basophilic stippling (β-thal), microcytes',
                    'GENETIC: β-thalassaemia confirmed by HPLC (elevated HbA2 >3.5%)',
                    'α-thalassaemia: HPLC may be normal — requires DNA analysis',
                ],
                'confirmatory': ['Haemoglobin electrophoresis / HPLC (HbA2, HbF)', 'Family history', 'DNA analysis for α-thalassaemia', 'Blood film'],
                'treatment': 'Genetic counselling (autosomal recessive). No iron supplementation unless iron deficiency coexists.',
            })

            # CRITICAL NOTE: IDA vs Thalassaemia
            result['differential'] = sorted(dx_list, key=lambda x: x['score'], reverse=True)
            result['type'] = 'Microcytic hypochromic anaemia'

            best_dx = result['differential'][0]
            second_dx = result['differential'][1] if len(result['differential']) > 1 else None

            result['interpretation'] = (
                f"{result['severity']} with microcytic hypochromic morphology (MCV {mcv} fL, MCH {mch} pg). "
                f"Most likely: {best_dx['diagnosis']} (score {best_dx['score']}). "
                f"Mentzer index: {mentzer} → {mentzer_interp}. "
                f"⚠️ Iron deficiency and thalassaemia trait CAN COEXIST — confirmatory tests required."
            )

            if not ferritin and not serum_iron:
                result['recommended_workup'] = [
                    'Serum ferritin (GOLD STANDARD for iron deficiency)',
                    'Serum iron + TIBC (transferrin saturation)',
                    'Haemoglobin electrophoresis / HPLC (HbA2, HbF levels)',
                    'Reticulocyte count + reticulocyte haemoglobin content (CHr/Ret-He)',
                    'Peripheral blood film',
                    'Family history and genetic screening if thalassaemia suspected',
                ]
            else:
                result['recommended_workup'] = [
                    'Haemoglobin electrophoresis / HPLC if ferritin normal',
                    'Peripheral blood film',
                    'Reticulocyte count',
                ]

        elif mcv > 100:
            # ── MACROCYTIC ANAEMIA ─────────────────────────────────
            result['morphology'] = 'Macrocytic'
            result['type'] = 'Macrocytic anaemia'
            dx_list = []

            # Megaloblastic causes
            if b12 is not None and b12 < 200:
                dx_list.append({
                    'diagnosis': 'Vitamin B12 Deficiency',
                    'likelihood': 'High' if b12 < 100 else 'Moderate',
                    'features': [f'Low B12 {b12} pg/mL', 'Associated with neurological symptoms (subacute combined degeneration)', 'Glossitis, angular cheilitis'],
                    'key_differences': ['B12 < 200 pg/mL diagnostic', 'May have neurological symptoms', 'Intrinsic factor antibodies (pernicious anaemia)', 'MMA elevated', 'Homocysteine elevated'],
                    'confirmatory': ['Serum B12', 'Intrinsic factor antibody', 'MMA', 'Gastric parietal cell antibody'],
                    'treatment': 'IM hydroxocobalamin 1mg on alternate days × 2 weeks, then monthly',
                })

            if folate is not None and folate < 3.0:
                dx_list.append({
                    'diagnosis': 'Folate Deficiency',
                    'likelihood': 'High' if folate < 1.5 else 'Moderate',
                    'features': [f'Low folate {folate} µg/L', 'No neurological symptoms (unlike B12)', 'Common in pregnancy, malnutrition, anticonvulsants'],
                    'key_differences': ['Folate < 3.0 µg/L', 'NO neurological symptoms', 'Homocysteine elevated (but NOT MMA)', 'Common causes: poor diet, malabsorption, drugs'],
                    'confirmatory': ['Serum folate', 'RBC folate (more reliable)', 'Homocysteine'],
                    'treatment': 'Folic acid 5mg daily × 4 months',
                })

            if not dx_list:
                dx_list.append({
                    'diagnosis': 'Macrocytic anaemia — cause undetermined',
                    'likelihood': 'Investigate',
                    'features': ['MCV > 100 fL without known deficiency'],
                    'key_differences': ['Non-megaloblastic: liver disease, hypothyroidism, reticulocytosis, alcohol', 'Megaloblastic: B12 or folate deficiency'],
                    'confirmatory': ['Serum B12', 'Serum/RBC folate', 'LFT', 'TFT (TSH)', 'Blood film — hypersegmented neutrophils suggest megaloblastosis'],
                    'treatment': 'Treat underlying cause',
                })

            result['differential'] = dx_list
            result['recommended_workup'] = [
                'Serum vitamin B12',
                'Serum folate (and RBC folate)',
                'Peripheral blood film (hypersegmented neutrophils)',
                'LFT (liver disease)',
                'TFT — TSH (hypothyroidism)',
                'Reticulocyte count',
                'Blood alcohol level if indicated',
            ]
            result['interpretation'] = (
                f"{result['severity']} with macrocytic morphology (MCV {mcv} fL). "
                f"Megaloblastic causes (B12/folate deficiency) must be excluded urgently. "
                f"Non-megaloblastic causes: liver disease, hypothyroidism, alcohol, reticulocytosis."
            )

        else:
            # ── NORMOCYTIC ANAEMIA ─────────────────────────────────
            result['morphology'] = 'Normocytic normochromic'
            result['type'] = 'Normocytic anaemia'
            dx_list = []

            # Haemolytic workup
            haemolytic_signs = []
            if ldh is not None and ldh > 280:    haemolytic_signs.append(f'Elevated LDH {ldh} U/L')
            if bilirubin is not None and bilirubin > 20: haemolytic_signs.append(f'Elevated bilirubin {bilirubin} µmol/L')
            if retic is not None and retic > 2.5: haemolytic_signs.append(f'Elevated reticulocytes {retic}% (active haemopoiesis)')

            if haemolytic_signs:
                dx_list.append({
                    'diagnosis': 'Haemolytic Anaemia',
                    'likelihood': 'High' if len(haemolytic_signs) >= 2 else 'Moderate',
                    'features': haemolytic_signs,
                    'key_differences': ['Elevated LDH + unconjugated bilirubin', 'Reticulocytosis (bone marrow compensating)', 'Direct Coombs test (autoimmune)', 'Blood film: spherocytes, schistocytes, polychromasia'],
                    'confirmatory': ['Direct Coombs test (DAT)', 'Peripheral blood film', 'LDH', 'Unconjugated bilirubin', 'Haptoglobin (low in haemolysis)', 'G6PD assay'],
                    'treatment': 'Depends on cause — autoimmune: steroids; G6PD: avoid triggers',
                })

            dx_list.extend([
                {
                    'diagnosis': 'Anaemia of Chronic Disease / Inflammation',
                    'likelihood': 'Moderate',
                    'features': ['Normal MCV with low Hb', 'Often in chronic infection, autoimmune disease, malignancy, CKD'],
                    'key_differences': ['Normal or elevated ferritin', 'Low serum iron', 'Low TIBC', 'Elevated CRP/ESR'],
                    'confirmatory': ['CRP, ESR', 'Ferritin', 'Serum iron + TIBC', 'Clinical history'],
                    'treatment': 'Treat underlying disease; erythropoietin in CKD if indicated',
                },
                {
                    'diagnosis': 'Acute Blood Loss',
                    'likelihood': 'Moderate',
                    'features': ['Rapid Hb drop', 'May have reticulocytosis after 3-5 days'],
                    'key_differences': ['Clinical history crucial', 'Reticulocytes elevated 3-5 days after haemorrhage'],
                    'confirmatory': ['Clinical history', 'Reticulocyte count', 'Blood film'],
                    'treatment': 'Treat source of bleeding; transfuse if Hb < 7 g/dL (or < 8 in cardiac disease)',
                },
            ])

            result['differential'] = dx_list
            result['recommended_workup'] = [
                'Serum ferritin, serum iron, TIBC',
                'Serum B12 and folate',
                'Reticulocyte count',
                'Direct Coombs test',
                'LDH, unconjugated bilirubin, haptoglobin',
                'CRP, ESR',
                'Renal function (eGFR)',
                'Blood film',
                'Clinical history (bleeding, chronic disease, drugs)',
            ]
            result['interpretation'] = (
                f"{result['severity']} with normocytic normochromic morphology (MCV {mcv} fL). "
                f"Differential includes: anaemia of chronic disease, acute blood loss, haemolytic anaemia, bone marrow failure. "
                f"Further workup required."
            )

        return result

    @staticmethod
    def interpret_wbc(wbc: float, neu_a: float, lym_a: float,
                      mon_a: float, eos_a: float, bas_a: float,
                      neu_p: float, lym_p: float) -> list[dict]:
        """
        WBC differential interpretation.
        Based on BCSH Guidelines for WBC Morphology Review.
        """
        findings = []

        # ── Total WBC ────────────────────────────────────────────
        if wbc > 30.0:
            findings.append({
                'parameter': 'WBC (Total)',
                'finding': 'CRITICAL leukocytosis',
                'value': f'{wbc} ×10³/µL',
                'significance': 'CRITICAL',
                'interpretation': f'WBC {wbc} ×10³/µL — extreme leukocytosis. Leukaemoid reaction, CML, or acute leukaemia must be excluded. Immediate blood film and haematology review.',
                'actions': ['STAT blood film', 'Haematology specialist referral', 'Bone marrow aspirate if blast cells detected'],
            })
        elif wbc > 11.0:
            cause = 'neutrophilia' if neu_p > 75 else ('lymphocytosis' if lym_p > 45 else 'leukocytosis')
            findings.append({
                'parameter': 'WBC (Total)',
                'finding': f'Leukocytosis ({cause})',
                'value': f'{wbc} ×10³/µL',
                'significance': 'MODERATE',
                'interpretation': f'WBC elevated at {wbc} ×10³/µL with predominant {cause}.',
                'actions': ['Review differential', 'Clinical correlation (infection, inflammation, drugs)', 'Blood film if WBC > 20'],
            })
        elif wbc < 2.0:
            findings.append({
                'parameter': 'WBC (Total)',
                'finding': 'CRITICAL leukopenia',
                'value': f'{wbc} ×10³/µL',
                'significance': 'CRITICAL',
                'interpretation': f'WBC {wbc} ×10³/µL — critical leukopenia. Risk of life-threatening infection. Bone marrow failure, drug toxicity, or viral suppression must be excluded.',
                'actions': ['Immediate isolation (reverse barrier nursing if < 1.0)', 'Bone marrow aspirate/trephine', 'Drug history review', 'Viral serology (EBV, CMV, HIV)', 'Antibiotic prophylaxis consideration'],
            })
        elif wbc < 4.0:
            findings.append({
                'parameter': 'WBC (Total)',
                'finding': 'Leukopenia',
                'value': f'{wbc} ×10³/µL',
                'significance': 'MODERATE',
                'interpretation': f'WBC {wbc} ×10³/µL — mild leukopenia. Consider viral infection, autoimmune disease, drugs.',
                'actions': ['Blood film', 'Full history including drug history', 'Viral serology if indicated'],
            })

        # ── Neutrophils ───────────────────────────────────────────
        if neu_a < 0.5:
            findings.append({
                'parameter': 'Neutrophils (Absolute)',
                'finding': 'CRITICAL agranulocytosis',
                'value': f'NEU# {neu_a} ×10³/µL',
                'significance': 'CRITICAL',
                'interpretation': f'Absolute neutrophil count (ANC) {neu_a} ×10³/µL — agranulocytosis (< 0.5). EXTREME risk of overwhelming bacterial infection and sepsis. Medical emergency.',
                'actions': ['IMMEDIATE physician notification', 'Strict reverse isolation', 'Review ALL drugs (especially carbimazole, clozapine, metamizole, chemotherapy)', 'GCSF consideration', 'Broad-spectrum antibiotics if febrile'],
            })
        elif neu_a < 1.5:
            findings.append({
                'parameter': 'Neutrophils (Absolute)',
                'finding': 'Neutropenia (ANC < 1.5)',
                'value': f'NEU# {neu_a} ×10³/µL',
                'significance': 'HIGH',
                'interpretation': f'ANC {neu_a} — neutropenia. Increased infection risk. Common causes: drugs, viral infection, autoimmune, bone marrow suppression.',
                'actions': ['Drug history', 'Viral serology (EBV, CMV)', 'ANA + anti-neutrophil antibodies', 'Repeat in 1 week'],
            })
        elif neu_a > 7.5:
            findings.append({
                'parameter': 'Neutrophils (Absolute)',
                'finding': 'Neutrophilia',
                'value': f'NEU# {neu_a} ×10³/µL',
                'significance': 'MODERATE' if neu_a < 15 else 'HIGH',
                'interpretation': f'Neutrophilia {neu_a} ×10³/µL. Most commonly: bacterial infection, inflammation, stress, corticosteroids, smoking. If > 20: exclude leukaemoid reaction or CML.',
                'actions': ['Clinical correlation', 'CRP, ESR', 'Blood film (toxic granulation, Döhle bodies, left shift)'],
            })

        # ── Lymphocytes ───────────────────────────────────────────
        if lym_a > 5.0:
            findings.append({
                'parameter': 'Lymphocytes (Absolute)',
                'finding': 'Lymphocytosis',
                'value': f'LYM# {lym_a} ×10³/µL',
                'significance': 'HIGH' if lym_a > 10 else 'MODERATE',
                'interpretation': f'Absolute lymphocytosis {lym_a} ×10³/µL. Differential: viral infection (EBV/CMV = reactive lymphocytes), pertussis, CLL. If persistent > 5.0: immunophenotyping required.',
                'actions': ['Blood film (atypical/reactive lymphocytes)', 'EBV/CMV serology', 'HIV test', 'Immunophenotyping if persistent or > 10 ×10³/µL'],
            })

        # ── Eosinophils ───────────────────────────────────────────
        if eos_a > 0.5:
            severity = 'Hypereosinophilia (> 1.5)' if eos_a > 1.5 else 'Eosinophilia'
            findings.append({
                'parameter': 'Eosinophils (Absolute)',
                'finding': severity,
                'value': f'EOS# {eos_a} ×10³/µL',
                'significance': 'HIGH' if eos_a > 1.5 else 'MODERATE',
                'interpretation': f'Eosinophilia {eos_a} ×10³/µL. Main causes: parasitic infection (helminths), drug allergy, atopic disease (asthma, eczema), Löffler syndrome. Hypereosinophilia (> 1.5): exclude hypereosinophilic syndrome — cardiac/organ damage risk.',
                'actions': [
                    'Stool ova and parasites × 3',
                    'Strongyloides serology',
                    'Drug history review',
                    'IgE total and specific allergen testing',
                    'If EOS > 1.5: troponin, echocardiogram (cardiac involvement)',
                    'Immunophenotyping if hypereosinophilia',
                ],
            })

        # ── Monocytes ─────────────────────────────────────────────
        if mon_a > 1.0:
            findings.append({
                'parameter': 'Monocytes (Absolute)',
                'finding': 'Monocytosis',
                'value': f'MON# {mon_a} ×10³/µL',
                'significance': 'MODERATE',
                'interpretation': f'Monocytosis {mon_a} ×10³/µL. Causes: chronic infection (TB, brucella, infective endocarditis), CMML, inflammatory bowel disease. Persistent monocytosis > 1.0 warrants bone marrow evaluation.',
                'actions': ['TB workup if indicated', 'Bone marrow aspirate if persistent', 'CMML screening'],
            })

        # ── Basophils ─────────────────────────────────────────────
        if bas_a > 0.1:
            findings.append({
                'parameter': 'Basophils (Absolute)',
                'finding': 'Basophilia',
                'value': f'BAS# {bas_a} ×10³/µL',
                'significance': 'MODERATE',
                'interpretation': f'Basophilia {bas_a} ×10³/µL. Basophilia > 0.1 in absence of allergy/inflammation is a classic feature of CML and myeloproliferative neoplasms. BCR-ABL1 testing indicated if persistent.',
                'actions': ['Blood film', 'BCR-ABL1 PCR (exclude CML)', 'JAK2 V617F (if splenomegaly)', 'Bone marrow assessment'],
            })

        return findings

    @staticmethod
    def interpret_platelets(plt: float, mpv: Optional[float] = None) -> dict:
        """Platelet count and MPV interpretation."""
        if plt < 20:
            return {
                'significance': 'CRITICAL',
                'interpretation': f'Platelet count {plt} ×10³/µL — CRITICAL thrombocytopenia. Life-threatening haemorrhage risk. Immediate haematology review. Spontaneous bleeding can occur.',
                'actions': ['URGENT haematology referral', 'Hold invasive procedures', 'Platelet transfusion threshold discussion with haematologist', 'Review drugs (heparin — exclude HIT)', 'Blood film', 'Coagulation screen'],
                'is_critical': True,
            }
        elif plt < 50:
            return {
                'significance': 'HIGH',
                'interpretation': f'Platelet count {plt} ×10³/µL — severe thrombocytopenia. Significant bleeding risk especially with trauma or procedure.',
                'actions': ['Blood film', 'Coagulation screen (DIC exclusion)', 'Drug history (especially heparin, quinine, sulphonamides)', 'ADAMTS13 if TTP suspected', 'LDH, bilirubin (haemolytic-uraemic syndrome/TTP)'],
                'is_critical': False,
            }
        elif plt < 100:
            return {
                'significance': 'MODERATE',
                'interpretation': f'Platelet count {plt} ×10³/µL — moderate thrombocytopenia. Causes: ITP, liver disease, hypersplenism, bone marrow infiltration, drug-induced.',
                'actions': ['Blood film', 'Drug history', 'LFT', 'Coagulation screen', 'H. pylori testing (in ITP)'],
                'is_critical': False,
            }
        elif plt > 1000:
            return {
                'significance': 'CRITICAL',
                'interpretation': f'Platelet count {plt} ×10³/µL — extreme thrombocytosis. Paradoxically, platelet counts > 1000 ×10³/µL carry THROMBOSIS AND HAEMORRHAGE risk. Exclude essential thrombocythaemia (ET), reactive thrombocytosis.',
                'actions': ['JAK2 V617F / CALR / MPL mutations', 'Blood film', 'Aspirin consideration', 'Haematology referral', 'Bone marrow biopsy'],
                'is_critical': True,
            }
        elif plt > 450:
            return {
                'significance': 'MODERATE',
                'interpretation': f'Platelet count {plt} ×10³/µL — thrombocytosis. Most commonly reactive (infection, iron deficiency, post-splenectomy, inflammation). If persistent > 600: exclude myeloproliferative neoplasm.',
                'actions': ['CRP, ESR (reactive cause)', 'Iron studies (IDA-associated thrombocytosis)', 'Blood film', 'JAK2 if persists'],
                'is_critical': False,
            }
        return {'significance': 'NORMAL', 'interpretation': f'Platelet count {plt} ×10³/µL — within reference range.', 'actions': [], 'is_critical': False}


# ══ COAGULATION RULES ════════════════════════════════════════════

class CoagulationRules:
    """
    Coagulation interpretation based on:
    - BCSH Guidelines on Investigation and Management of Coagulopathies
    - ISTH SSC Guidelines
    """

    CRITICAL = {
        'PT':    ('>30s',   'Severe coagulopathy — haemorrhage risk'),
        'INR':   ('>3.0',   'Supratherapeutic anticoagulation — bleeding risk'),
        'APTT':  ('>70s',   'Severe coagulopathy — factor VIII/IX deficiency or lupus anticoagulant'),
        'FIBRIN':('<1.0',   'Critical hypofibrinogenaemia — DIC or severe liver disease'),
        'DDIMER':('>5.0',   'Marked elevation — high probability PE/DVT or DIC'),
    }

    @staticmethod
    def interpret_pt_inr(pt: float, inr: float,
                         anticoagulant: Optional[str] = None,
                         indication: Optional[str] = None) -> dict:
        """
        Prothrombin time / INR interpretation.
        Warfarin target ranges (BCSH 2011):
          AF / VTE:          INR 2.0–3.0
          Mechanical valve:  INR 2.5–3.5
          APS:               INR 2.0–3.0 (or 3.0–4.0 high-risk)
        """
        is_critical = inr > 3.0
        is_therapeutic_warfarin = anticoagulant and 'warfarin' in anticoagulant.lower()

        if is_therapeutic_warfarin:
            target = '2.5–3.5' if indication and 'valve' in indication.lower() else '2.0–3.0'
            if inr > 5.0:
                return {
                    'significance': 'CRITICAL',
                    'interpretation': f'INR {inr} — CRITICALLY elevated on warfarin. Major haemorrhage risk. Do not wait. Reverse immediately.',
                    'actions': ['HOLD warfarin', 'Vitamin K 5–10mg IV', 'Prothrombin complex concentrate if bleeding', '4-factor PCC preferred over FFP', 'Reassess in 6 hours', 'Haematology/anticoagulation clinic review'],
                    'is_critical': True,
                }
            elif inr > 3.0:
                return {
                    'significance': 'HIGH',
                    'interpretation': f'INR {inr} — supratherapeutic for target {target}. Increased bleeding risk.',
                    'actions': ['Hold or reduce warfarin dose', 'Low-dose vitamin K 1–2mg oral if bleeding risk high', 'Recheck INR in 48h', 'Check for interacting drugs/foods (grapefruit, antibiotics)'],
                    'is_critical': False,
                }
            elif 2.0 <= inr <= (3.5 if 'valve' in str(indication).lower() else 3.0):
                return {
                    'significance': 'NORMAL',
                    'interpretation': f'INR {inr} — within therapeutic range ({target}) for {indication or "anticoagulation indication"}.',
                    'actions': ['Continue current dose', 'Next INR check per protocol'],
                    'is_critical': False,
                }
            else:
                return {
                    'significance': 'MODERATE',
                    'interpretation': f'INR {inr} — sub-therapeutic (target {target}). Thromboembolic risk.',
                    'actions': ['Increase warfarin dose', 'Consider bridging if high-risk indication', 'Reassess compliance and diet'],
                    'is_critical': False,
                }

        # Non-anticoagulated patient
        if inr > 3.0 or pt > 30:
            return {
                'significance': 'CRITICAL',
                'interpretation': f'PT {pt}s / INR {inr} — critically prolonged. Severe extrinsic/common pathway defect. Causes: severe liver disease, DIC, vitamin K deficiency, factor VII deficiency, supratherapeutic anticoagulation.',
                'actions': ['aPTT + fibrinogen + D-dimer (DIC screen)', 'LFT + albumin (liver disease)', 'Vitamin K 10mg IV', 'Mixing study (if factor deficiency suspected)', 'Haematology urgent referral'],
                'is_critical': True,
            }
        elif inr > 1.5:
            return {
                'significance': 'MODERATE',
                'interpretation': f'PT {pt}s / INR {inr} — prolonged in non-anticoagulated patient. Investigate.',
                'actions': ['LFT', 'Vitamin K levels', 'aPTT', 'Mixing study'],
                'is_critical': False,
            }
        return {
            'significance': 'NORMAL',
            'interpretation': f'PT {pt}s / INR {inr} — within reference range.',
            'actions': [],
            'is_critical': False,
        }

    @staticmethod
    def interpret_aptt(aptt: float, ratio: Optional[float] = None,
                       on_heparin: bool = False) -> dict:
        """aPTT interpretation — intrinsic pathway and heparin monitoring."""
        if on_heparin:
            therapeutic = 1.5 <= (ratio or aptt / 30) <= 2.5
            if aptt > 100 or (ratio and ratio > 3.0):
                return {'significance': 'CRITICAL', 'interpretation': f'aPTT {aptt}s — excessively prolonged on heparin. Haemorrhage risk. HOLD heparin. Check anti-Xa if LMWH.', 'actions': ['HOLD UFH infusion', 'Protamine sulphate if active bleeding', 'Recheck aPTT 4h after dose adjustment'], 'is_critical': True}
            return {'significance': 'NORMAL' if therapeutic else 'MODERATE', 'interpretation': f'aPTT {aptt}s on heparin — {"therapeutic" if therapeutic else "sub/supratherapeutic — adjust dose"}.', 'actions': ['Adjust UFH per local protocol', 'Check anti-Xa level if result discordant'], 'is_critical': False}

        if aptt > 70:
            return {
                'significance': 'CRITICAL',
                'interpretation': f'aPTT {aptt}s — critically prolonged. Severe intrinsic/common pathway defect. Haemorrhage risk. Causes: haemophilia A (FVIII) or B (FIX), lupus anticoagulant (paradoxical thrombosis), DIC, heparin contamination.',
                'actions': ['Mixing study (incubated — distinguish factor deficiency from inhibitor)', 'FVIII, FIX, FXI assays', 'Lupus anticoagulant (dRVVT, silica clotting time)', 'Check for heparin contamination (Thrombin time — TT prolonged by heparin)', 'Haematology referral'],
                'is_critical': True,
            }
        elif aptt > 45:
            return {
                'significance': 'MODERATE',
                'interpretation': f'aPTT {aptt}s — prolonged. Mixing study required to differentiate factor deficiency from inhibitor.',
                'actions': ['Mixing study', 'Lupus anticoagulant screen', 'Factor assays if mixing study corrects'],
                'is_critical': False,
            }
        return {'significance': 'NORMAL', 'interpretation': f'aPTT {aptt}s — within reference range.', 'actions': [], 'is_critical': False}

    @staticmethod
    def interpret_ddimer(ddimer: float, pretest_prob: str = 'unknown') -> dict:
        """D-Dimer interpretation for VTE and DIC."""
        if ddimer > 5.0:
            return {
                'significance': 'CRITICAL',
                'interpretation': f'D-Dimer {ddimer} mg/L FEU — markedly elevated. HIGH probability of: (1) Active VTE (DVT/PE) — imaging URGENTLY required, (2) DIC — check fibrinogen, PT, aPTT, FBC, (3) Sepsis, malignancy, liver disease, pregnancy.',
                'actions': ['CTPA or V/Q scan (PE exclusion)', 'Bilateral leg doppler (DVT)', 'Fibrinogen + PT + aPTT (DIC screen)', 'Clinical assessment for alternative causes', 'Age-adjusted D-Dimer cut-off: 10 × age (µg/L) for patients > 50'],
                'is_critical': True,
            }
        elif ddimer > 0.5:
            msg = ''
            if pretest_prob == 'low':
                msg = 'In LOW pre-test probability patients, elevated D-Dimer does NOT confirm VTE (low specificity). Consider alternative causes.'
            return {
                'significance': 'HIGH' if ddimer > 2.0 else 'MODERATE',
                'interpretation': f'D-Dimer {ddimer} mg/L FEU — elevated. {msg} Causes: VTE, infection, inflammation, malignancy, recent surgery, pregnancy. D-Dimer is sensitive but NOT specific for VTE.',
                'actions': ['Clinical pre-test probability assessment (Wells/YEARS score)', 'CT-PA if high probability', 'Consider age-adjusted cut-off', 'Do NOT use D-Dimer alone to diagnose VTE'],
                'is_critical': False,
            }
        return {
            'significance': 'NORMAL',
            'interpretation': f'D-Dimer {ddimer} mg/L FEU — within normal range. In LOW pre-test probability patients, a normal D-Dimer effectively excludes VTE (sensitivity 95-97%).',
            'actions': [],
            'is_critical': False,
        }


# ══ BIOCHEMISTRY RULES ═══════════════════════════════════════════

class BiochemistryRules:
    """
    Clinical biochemistry interpretation.
    Based on IFCC, AACC, and local clinical guidelines.
    """

    CRITICAL = {
        'glucose_lo': (2.2, 'CRITICAL hypoglycaemia — immediate 50% dextrose IV'),
        'glucose_hi': (22.0,'CRITICAL hyperglycaemia — DKA/HHS risk'),
        'sodium_lo':  (120, 'CRITICAL hyponatraemia — cerebral oedema risk, seizures'),
        'sodium_hi':  (160, 'CRITICAL hypernatraemia — brain shrinkage, vascular rupture'),
        'potassium_lo':(2.5,'CRITICAL hypokalaemia — fatal arrhythmia risk'),
        'potassium_hi':(6.5,'CRITICAL hyperkalaemia — cardiac arrest risk'),
        'calcium_lo': (1.75,'CRITICAL hypocalcaemia — tetany, laryngospasm, seizures'),
        'calcium_hi': (3.5, 'CRITICAL hypercalcaemia — cardiac arrest, renal failure'),
        'creatinine': (500, 'CRITICAL — severe renal failure, dialysis likely required'),
        'troponin_i': (0.5, 'CRITICAL — significant myocardial injury / NSTEMI/STEMI'),
    }

    @staticmethod
    def interpret_electrolytes(na: float, k: float,
                               cl: Optional[float] = None,
                               co2: Optional[float] = None) -> list[dict]:
        """Serum electrolytes interpretation with clinical correlation."""
        findings = []

        # Sodium
        if na < 120:
            findings.append({
                'parameter': 'Sodium', 'value': f'{na} mmol/L', 'significance': 'CRITICAL',
                'interpretation': f'CRITICAL hyponatraemia {na} mmol/L. Risk of: cerebral oedema, seizures, herniation. CORRECTION MUST BE SLOW (max 10 mmol/L/24h) — too rapid causes osmotic demyelination syndrome (ODS).',
                'actions': ['Immediate ICU/HDU review', 'Fluid restriction if euvolaemic/hypervolaemic', 'Hypertonic saline 3% if symptomatic (seizures)', 'Urine sodium + osmolality (SIADH exclusion)', 'Endocrine review (hypothyroidism, Addisons)'],
                'is_critical': True,
            })
        elif na < 130:
            findings.append({'parameter': 'Sodium', 'value': f'{na} mmol/L', 'significance': 'HIGH',
                'interpretation': f'Significant hyponatraemia {na} mmol/L. Correct slowly (< 10 mmol/L/24h). Assess volume status. Common causes: SIADH, diuretics, vomiting, hypothyroidism.',
                'actions': ['Urine Na + osmolality', 'TFT', 'Cortisol', 'Volume assessment', 'Drug review (diuretics, SSRIs, carbamazepine)'],
                'is_critical': False})
        elif na > 160:
            findings.append({'parameter': 'Sodium', 'value': f'{na} mmol/L', 'significance': 'CRITICAL',
                'interpretation': f'CRITICAL hypernatraemia {na} mmol/L. Severe dehydration. Brain shrinkage — cerebral vein rupture risk. Correct slowly (max 10 mmol/L/24h). Causes: diabetes insipidus, inadequate water intake, excess sodium.',
                'actions': ['Fluid balance assessment', 'Water deficit calculation: deficit (L) = 0.6 × IBW × (Na/140 − 1)', 'Urine osmolality (if DI suspected)', 'Endocrine review (DI)'],
                'is_critical': True})
        elif na > 150:
            findings.append({'parameter': 'Sodium', 'value': f'{na} mmol/L', 'significance': 'HIGH',
                'interpretation': f'Hypernatraemia {na} mmol/L. Dehydration, diabetes insipidus, or excess sodium intake. Correct gradually with hypotonic fluids.',
                'actions': ['Water replacement (oral if alert, IV hypotonic if not)', 'Urine osmolality', 'Fluid balance review'],
                'is_critical': False})

        # Potassium
        if k < 2.5:
            findings.append({'parameter': 'Potassium', 'value': f'{k} mmol/L', 'significance': 'CRITICAL',
                'interpretation': f'CRITICAL hypokalaemia {k} mmol/L. Fatal ventricular arrhythmia risk (torsades de pointes, VF). Correct IV urgently with cardiac monitoring.',
                'actions': ['Cardiac monitoring (ECG — U waves, T-wave flattening, QT prolongation)', 'IV KCl via central line (max 20 mmol/h peripherally)', 'Replace magnesium simultaneously (hypoMg → hypokalaemia)', 'Identify cause (diuretics, vomiting, diarrhoea, hyperaldosteronism)', 'Recheck K after each replacement'],
                'is_critical': True})
        elif k < 3.0:
            findings.append({'parameter': 'Potassium', 'value': f'{k} mmol/L', 'significance': 'HIGH',
                'interpretation': f'Significant hypokalaemia {k} mmol/L. Arrhythmia risk — correct urgently especially if on digoxin or QT-prolonging drugs.',
                'actions': ['ECG', 'IV or oral KCl depending on severity', 'Magnesium replacement', 'Review diuretics'],
                'is_critical': False})
        elif k > 6.5:
            findings.append({'parameter': 'Potassium', 'value': f'{k} mmol/L', 'significance': 'CRITICAL',
                'interpretation': f'CRITICAL hyperkalaemia {k} mmol/L. CARDIAC ARREST RISK. Peaked T-waves → PR prolongation → wide QRS → VF/asystole. Act immediately.',
                'actions': ['IMMEDIATE ECG', 'IV calcium gluconate 10% 10mL over 10 min (stabilise membrane)', 'Insulin 10 units + 50mL 50% dextrose IV', 'Salbutamol 10-20mg nebulised', 'Calcium resonium / Patiromer (eliminate K)', 'Emergency dialysis if resistant', 'Recheck K in 1h'],
                'is_critical': True})
        elif k > 5.5:
            findings.append({'parameter': 'Potassium', 'value': f'{k} mmol/L', 'significance': 'HIGH',
                'interpretation': f'Hyperkalaemia {k} mmol/L. Exclude haemolysis (pseudohyperkalaemia). If true: renal failure, ACEi/ARBs, Addisons, acidosis.',
                'actions': ['ECG', 'Repeat K on fresh non-haemolysed sample', 'Renal function', 'Stop K-retaining drugs', 'Dietary advice'],
                'is_critical': False})

        return findings

    @staticmethod
    def interpret_troponin(troponin_i: float, delta: Optional[float] = None,
                           hours_from_symptoms: int = 0) -> dict:
        """
        High-sensitivity Troponin I interpretation.
        Based on ESC 0h/1h/2h algorithm (2020).
        Universal MI Definition (ESC 2018).
        """
        # URL 99th percentile for hs-TnI varies by assay — using Abbott Architect (26 ng/L)
        # For general rules: any above 0.04 µg/L (40 ng/L) flagged as significant
        if troponin_i > 0.5:
            return {
                'significance': 'CRITICAL',
                'interpretation': f'Troponin I {troponin_i} µg/L — CRITICALLY elevated. Significant myocardial injury. Type 1 MI (plaque rupture), Type 2 MI (demand ischaemia), or myocarditis. Immediate cardiology referral.',
                'actions': ['Immediate ECG (12-lead)', 'Cardiology referral STAT', 'Aspirin 300mg loading (if Type 1 MI)', 'CTCA or invasive coronary angiography', 'Serial troponin at 1h/3h (delta)', 'GRACE score risk stratification'],
                'is_critical': True,
            }
        elif troponin_i > 0.04:
            delta_msg = ''
            if delta is not None:
                if delta > 0.05 or delta > (0.2 * troponin_i):
                    delta_msg = f' Serial rise of {delta:.3f} µg/L — dynamic rise/fall = HIGH probability acute MI.'
                else:
                    delta_msg = f' Serial change of {delta:.3f} µg/L — stable (rule-out if clinically low probability).'
            return {
                'significance': 'HIGH',
                'interpretation': f'Troponin I {troponin_i} µg/L — elevated above 99th percentile.{delta_msg} May represent acute MI or non-ischaemic myocardial injury (PE, myocarditis, sepsis, renal failure, heart failure).',
                'actions': ['ECG', 'Serial troponin at 1h and 3h (ESC 0h/1h algorithm)', 'Echocardiography', 'Clinical context assessment', 'Cardiology review if rising or positive symptoms'],
                'is_critical': troponin_i > 0.1,
            }
        return {
            'significance': 'NORMAL',
            'interpretation': f'Troponin I {troponin_i} µg/L — within normal range. A single normal troponin does NOT exclude ACS if < 3h from symptoms. Serial measurement required.',
            'actions': ['Repeat troponin at 1h and 3h if < 3h from symptom onset', 'Clinical and ECG review'],
            'is_critical': False,
        }


# ══ MICROBIOLOGY RULES ═══════════════════════════════════════════

class MicrobiologyRules:
    """
    Microbiology interpretation — organism significance and antibiogram guidance.
    Based on EUCAST breakpoints, CLSI M100, and local epidemiology.
    """

    # Critical organisms requiring immediate notification
    CRITICAL_ORGANISMS = [
        ('MRSA', 'Methicillin-resistant Staphylococcus aureus — Contact precautions, decolonisation protocol'),
        ('ESBL', 'ESBL-producing organism — Carbapenem required for serious infection'),
        ('CRE',  'Carbapenem-resistant Enterobacteriaceae — Last-resort antibiotics (colistin, ceftazidime-avibactam)'),
        ('CRO',  'Carbapenem-resistant organism — Infection control alert, cohorting'),
        ('VRSA', 'Vancomycin-resistant Staphylococcus aureus — Extremely rare, strict isolation, public health notification'),
        ('VRE',  'Vancomycin-resistant Enterococcus — Contact precautions'),
        ('CDI',  'Clostridioides difficile — Enteric precautions, metronidazole/vancomycin/fidaxomicin'),
        ('MTB',  'Mycobacterium tuberculosis — Airborne precautions, public health notification MANDATORY'),
        ('MDR_TB','MDR-TB (RIF + INH resistant) — Specialist TB unit referral, public health emergency'),
        ('XDR_TB','XDR-TB — Extreme public health emergency, specialist management only'),
        ('NTM',  'Non-tuberculous Mycobacterium — Clinical significance context-dependent'),
    ]

    @staticmethod
    def interpret_culture_result(organism: str, specimen: str,
                                 is_mrsa: bool = False, is_esbl: bool = False,
                                 is_cro: bool = False) -> dict:
        """Culture result clinical significance."""
        findings = []
        is_critical = any([is_mrsa, is_esbl, is_cro])

        if is_mrsa:
            findings.append('⚠️ MRSA: Vancomycin or teicoplanin required. Contact precautions. Screen contacts. Decolonisation with mupirocin nasal ointment + chlorhexidine body wash.')
        if is_esbl:
            findings.append('⚠️ ESBL producer: Treat serious infections with carbapenem (meropenem/ertapenem). Avoid cephalosporins, penicillins, fluoroquinolones (high failure rates despite in-vitro sensitivity).')
        if is_cro:
            findings.append('⚠️ Carbapenem-Resistant Organism (CRO): EMERGENCY — contact infection control. Last-resort options: ceftazidime-avibactam, ceftolozane-tazobactam, colistin. Public health notification required.')

        return {
            'organism': organism,
            'specimen': specimen,
            'is_critical': is_critical,
            'significance': 'CRITICAL' if is_critical else 'HIGH' if organism else 'NEGATIVE',
            'interpretation': f'{"⚠️ " if is_critical else ""}Growth of {organism} from {specimen}.',
            'clinical_notes': findings,
            'infection_control_actions': [
                'Isolate patient in single room' if is_critical else '',
                'Contact precautions (gown + gloves)' if is_mrsa or is_cro else '',
                'Airborne precautions' if 'MTB' in organism.upper() else '',
                'Notify infection control team' if is_critical else '',
                'Screen contacts' if is_mrsa else '',
            ],
        }

    @staticmethod
    def interpret_tb_result(genexpert_result: str, rif_resistance: str,
                            afb_smear: str = 'Not done') -> dict:
        """GeneXpert MTB/RIF result interpretation — WHO 2021 guidelines."""
        if genexpert_result == 'NOT_DETECTED':
            return {
                'significance': 'NORMAL',
                'interpretation': 'GeneXpert MTB: NOT DETECTED. Mycobacterium tuberculosis DNA not detected. Does not exclude TB if pre-test probability is high (clinical + radiological assessment).',
                'actions': ['Clinical review', 'Consider culture (more sensitive for paucibacillary TB)', 'Repeat if high clinical suspicion'],
                'is_critical': False,
                'public_health': False,
            }

        if genexpert_result == 'DETECTED' and rif_resistance == 'NOT_DETECTED':
            return {
                'significance': 'HIGH',
                'interpretation': 'GeneXpert MTB: DETECTED — Rifampicin SENSITIVE. Drug-sensitive TB (DS-TB). Standard RHEZ regimen (2HRZE/4HR). Airborne isolation. PUBLIC HEALTH NOTIFICATION MANDATORY.',
                'actions': ['Start RHEZ immediately (Rifampicin, Isoniazid, Ethambutol, Pyrazinamide)', 'Airborne isolation (negative pressure room)', 'Contact tracing — ALL contacts within 4 weeks', 'Public health notification to MoH', 'HIV test', 'Baseline LFT', 'Eye test (ethambutol — colour vision)'],
                'is_critical': True,
                'public_health': True,
            }

        if genexpert_result == 'DETECTED' and rif_resistance == 'DETECTED':
            return {
                'significance': 'CRITICAL',
                'interpretation': '⚠️ GeneXpert MTB: DETECTED — Rifampicin RESISTANT. RR-TB = MDR-TB until proven otherwise. EMERGENCY — specialist TB unit referral mandatory. Standard TB regimen MUST NOT be used.',
                'actions': ['URGENT specialist TB unit referral (same day)', 'Full drug susceptibility testing (DST) — Xpert MTB/XDR or culture DST', 'Second-line regimen per WHO 2022 guidelines (BPaLM: bedaquiline, pretomanid, linezolid, moxifloxacin)', 'Airborne isolation', 'Contact tracing', 'PUBLIC HEALTH EMERGENCY — notify MoH, WHO if XDR-TB', 'HIV test', 'Nutritional support'],
                'is_critical': True,
                'public_health': True,
                'tb_classification': 'RR-TB / MDR-TB',
            }

        return {
            'significance': 'MODERATE',
            'interpretation': f'GeneXpert result: {genexpert_result}. Rifampicin resistance: {rif_resistance}. Clinical review required.',
            'actions': ['Clinical review', 'Culture and DST'],
            'is_critical': False,
            'public_health': False,
        }


# ══ SEROLOGY / IMMUNOLOGY RULES ══════════════════════════════════

class SerologyRules:
    """HIV, Hepatitis, Autoimmune interpretation."""

    @staticmethod
    def interpret_hiv(rapid_result: str, elisa_result: Optional[str] = None,
                      sco_ratio: Optional[float] = None,
                      cd4: Optional[float] = None) -> dict:
        """HIV testing interpretation — WHO HIV testing algorithm."""

        if rapid_result in ('NON_REACTIVE', 'NEGATIVE'):
            return {
                'significance': 'NORMAL',
                'interpretation': 'HIV rapid test NON-REACTIVE. In low-prevalence populations with no recent high-risk exposure (< 6 weeks), this is highly reassuring. In high-risk settings or recent exposure: repeat at 6 weeks (window period for 4th generation tests).',
                'actions': ['Repeat if within window period (< 6 weeks exposure)', 'Counsel on risk reduction', 'PrEP consideration if ongoing high risk'],
                'is_critical': False,
            }

        if rapid_result == 'REACTIVE':
            cd4_msg = f' CD4 count {cd4} cells/µL — {"< 200 (AIDS-defining)" if cd4 and cd4 < 200 else ""}.' if cd4 else ''
            return {
                'significance': 'CRITICAL',
                'interpretation': f'HIV REACTIVE.{cd4_msg} Confirmatory testing and ART initiation workup required. Pre- and post-test counselling is MANDATORY. Confidentiality must be maintained.',
                'actions': [
                    'WHO HIV testing algorithm — confirmatory with different rapid test or ELISA',
                    'Pre- and post-test counselling (MANDATORY)',
                    'CD4 count + HIV viral load',
                    'WHO staging assessment',
                    'ART initiation within same day where possible (Test and Treat)',
                    'Screen for OIs: TB (GeneXpert), cryptococcal antigen (if CD4 < 100)',
                    'Partner notification (counselled)',
                    'PMTCT if pregnant',
                    'Ensure confidentiality — this is CONFIDENTIAL INFORMATION',
                ],
                'is_critical': True,
                'bsl2_handling': True,
                'counselling_required': True,
            }

        return {
            'significance': 'MODERATE',
            'interpretation': f'HIV result: {rapid_result}. Requires follow-up.',
            'actions': ['Repeat testing', 'Counselling'],
            'is_critical': False,
        }


# ══ MAIN INTERPRETATION DISPATCHER ═══════════════════════════════

def interpret_result(
    test_code: str,
    value: float | str | None,
    unit: str = '',
    sex: str = 'M',
    age: int = 40,
    patient_context: Optional[dict] = None,
) -> InterpretationResult:
    """
    Main dispatcher — routes to correct rules engine based on test code.
    Returns structured InterpretationResult.
    Patient context: {'hgb', 'mcv', 'mch', 'mchc', 'rdw', 'rbc', 'retic',
                      'ferritin', 'serum_iron', 'tibc', 'b12', 'folate',
                      'ldh', 'bilirubin', 'anticoagulant', 'indication'}
    """
    ctx = patient_context or {}
    code = test_code.upper().strip()

    # ── Haematology ───────────────────────────────────────────────
    if code == 'HGB':
        v = float(value)
        ref = HaematologyRules.REF['HGB']
        lo, hi = (ref[0], ref[1]) if sex.upper()=='M' else (ref[2], ref[3])
        crit_lo = ref[4]
        # Anemia classification if below reference
        if v < lo and all(k in ctx for k in ['mcv','mch','mchc','rdw','rbc']):
            anem = HaematologyRules.classify_anemia(
                hgb=v, mcv=ctx['mcv'], mch=ctx['mch'], mchc=ctx['mchc'],
                rdw=ctx['rdw'], rbc=ctx['rbc'], sex=sex,
                retic=ctx.get('retic'), ferritin=ctx.get('ferritin'),
                serum_iron=ctx.get('serum_iron'), tibc=ctx.get('tibc'),
                b12=ctx.get('b12'), folate=ctx.get('folate'),
                ldh=ctx.get('ldh'), bilirubin=ctx.get('bilirubin'),
            )
            flag = 'LL' if v < 7.0 else 'L'
            return InterpretationResult(
                test_code=code, test_name='Haemoglobin', value=v, unit=unit, flag=flag,
                significance=Significance.CRITICAL if v < 7.0 else Significance.HIGH if v < 10 else Significance.MODERATE,
                interpretation=anem['interpretation'],
                possible_causes=[dx['diagnosis'] for dx in anem['differential'][:3]],
                recommended_actions=anem.get('recommended_workup', []),
                is_critical=anem['critical'],
                critical_message='CRITICAL ANAEMIA — Hb < 7 g/dL. Transfusion threshold reached.' if v < 7.0 else '',
                differential_dx=anem['differential'],
                indices=anem['indices'],
                panel_pattern=anem.get('type',''),
            )
        flag = 'N' if lo <= v <= hi else ('LL' if v < crit_lo else 'L' if v < lo else 'H' if v > hi else 'N')
        return InterpretationResult(test_code=code, test_name='Haemoglobin', value=v, unit=unit, flag=flag,
            significance=Significance.NORMAL if flag=='N' else Significance.CRITICAL if 'LL' in flag else Significance.MODERATE,
            interpretation=f'Haemoglobin {v} {unit} — {"within normal range" if flag=="N" else ("elevated — polycythaemia?" if flag=="H" else "low")}.',
            is_critical=flag=='LL',)

    # PLT
    if code == 'PLT':
        v = float(value)
        r = HaematologyRules.interpret_platelets(v, ctx.get('mpv'))
        flag = 'LL' if v < 20 else ('L' if v < 150 else ('HH' if v > 1000 else ('H' if v > 450 else 'N')))
        return InterpretationResult(test_code=code, test_name='Platelet Count', value=v, unit=unit, flag=flag,
            significance=Significance[r['significance']], interpretation=r['interpretation'],
            recommended_actions=r['actions'], is_critical=r['is_critical'],
            critical_message=r['interpretation'] if r['is_critical'] else '')

    # INR
    if code == 'INR':
        v = float(value)
        pt_v = float(ctx.get('pt', v * 12))
        r = CoagulationRules.interpret_pt_inr(pt_v, v, ctx.get('anticoagulant'), ctx.get('indication'))
        flag = 'HH' if v > 3.0 else ('H' if v > 1.2 else ('L' if v < 0.8 else 'N'))
        return InterpretationResult(test_code=code, test_name='INR', value=v, unit=unit, flag=flag,
            significance=Significance[r['significance']], interpretation=r['interpretation'],
            recommended_actions=r['actions'], is_critical=r['is_critical'])

    # D-Dimer
    if code in ('DDIMER','D_DIMER'):
        v = float(value)
        r = CoagulationRules.interpret_ddimer(v, ctx.get('pretest_prob','unknown'))
        flag = 'HH' if v > 5.0 else ('H' if v > 0.5 else 'N')
        return InterpretationResult(test_code=code, test_name='D-Dimer', value=v, unit=unit, flag=flag,
            significance=Significance[r['significance']], interpretation=r['interpretation'],
            recommended_actions=r['actions'], is_critical=r['is_critical'])

    # Troponin
    if code in ('TROP_I','TROPONIN_I'):
        v = float(value)
        r = BiochemistryRules.interpret_troponin(v, ctx.get('delta'), ctx.get('hours_from_symptoms',0))
        flag = 'HH' if v > 0.5 else ('H' if v > 0.04 else 'N')
        return InterpretationResult(test_code=code, test_name='Troponin I', value=v, unit=unit, flag=flag,
            significance=Significance[r['significance']], interpretation=r['interpretation'],
            recommended_actions=r['actions'], is_critical=r['is_critical'])

    # Generic flag for anything else with reference range in HaematologyRules.REF
    if code in HaematologyRules.REF:
        v = float(value)
        ref = HaematologyRules.REF[code]
        lo_m, hi_m, lo_f, hi_f, crit_lo, crit_hi, u = ref
        lo = lo_m if sex.upper()=='M' else lo_f
        hi = hi_m if sex.upper()=='M' else hi_f
        if v < (crit_lo or -999):  flag = 'LL'
        elif v > (crit_hi or 999): flag = 'HH'
        elif lo and v < lo:        flag = 'L'
        elif hi and v > hi:        flag = 'H'
        else:                      flag = 'N'
        crit = flag in ('HH','LL')
        sig = Significance.CRITICAL if crit else (Significance.NORMAL if flag=='N' else Significance.MODERATE)
        interp = f'{code} {v} {u} — {"within reference range" if flag=="N" else ("critically elevated" if flag=="HH" else ("elevated" if flag=="H" else ("critically low" if flag=="LL" else "low")))}.'
        return InterpretationResult(test_code=code, test_name=code, value=v, unit=unit, flag=flag,
            significance=sig, interpretation=interp, is_critical=crit,
            critical_message=f'CRITICAL: {code} {v} {u}' if crit else '')

    # Fallback
    return InterpretationResult(test_code=code, test_name=code, value=value, unit=unit, flag='N',
        significance=Significance.NORMAL, interpretation=f'{code}: {value} {unit}. No specific rule defined.')


def get_ai_summary_prompt(results: list[dict]) -> str:
    """Build a prompt for the AI to provide panel interpretation."""
    lines = ['Patient laboratory panel results for clinical interpretation:']
    for r in results:
        flag_txt = {'HH':'🚨CRITICAL HIGH','LL':'🚨CRITICAL LOW','H':'⬆HIGH','L':'⬇LOW','N':'✓Normal','POS':'🔴POSITIVE','NEG':'✅NEGATIVE'}.get(r.get('flag','N'), '')
        lines.append(f'  {r.get("test_name","?")} ({r.get("test_code","?")}): {r.get("value","?")} {r.get("unit","")} {flag_txt}')
    lines.append('\nProvide: (1) syndrome/pattern identification, (2) most likely diagnosis, (3) urgent actions, (4) reflex investigations. Be concise and evidence-based. This is REAL patient data.')
    return '\n'.join(lines)
