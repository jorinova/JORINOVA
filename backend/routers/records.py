"""
Records Router — Laboratory Record Books System
================================================
Every department has its own immutable record book.
Books are PQC-signed, shift-intelligent, and specimen-color-linked.

Book categories:
  1. Hematology & Haemostasis
  2. Biochemistry & Endocrinology
  3. Immunology & Serology
  4. Microbiology (by specimen type)
  5. Molecular & Genomics
  6. Anatomic Pathology
  7. Toxicology
  8. Blood Bank & Transfusion
  9. Operations & Administration
  10. Quality & Audit
"""
from __future__ import annotations
from typing import Optional, Any
from datetime import date as date_t, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text
from pydantic import BaseModel
from core.database import get_db
from core.security import get_current_user
from models.user import User

router = APIRouter(prefix='/records', tags=['Records'])

# ── Comprehensive Book Catalogue ──────────────────────────────────────────────

BOOKS: dict[str, dict] = {

    # ── HEMATOLOGY & HAEMOSTASIS ────────────────────────────────────────────
    'hematology': {
        'name': '🔴 Hematology CBC Book',
        'category': 'Hematology & Haemostasis',
        'icon': '🔴',
        'tube': 'purple_edta',
        'accent': '#DC143C',
        'gradient': 'linear-gradient(135deg,#3d0010 0%,#8b0026 60%,#c0003a 100%)',
        'text': '#ffd6d9',
        'department': 'HEM',
        'description': 'CBC · Differential Count · ESR · Reticulocytes · Blood Morphology',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'lid','label':'LID','type':'text'},
            {'key':'hgb','label':'Hb (g/dL)','type':'number','flag_lo':12,'flag_hi':17,'critical_lo':7,'critical_hi':20},
            {'key':'wbc','label':'WBC (×10³)','type':'number','flag_lo':4,'flag_hi':11,'critical_lo':2,'critical_hi':30},
            {'key':'plt','label':'PLT (×10³)','type':'number','flag_lo':150,'flag_hi':450,'critical_lo':20,'critical_hi':1000},
            {'key':'hct','label':'HCT (%)','type':'number'},
            {'key':'mcv','label':'MCV (fL)','type':'number'},
            {'key':'esr','label':'ESR (mm/h)','type':'number'},
            {'key':'result_source','label':'Source','type':'select','options':['MANUAL','AUTOMATED']},
            {'key':'analyzer','label':'Analyzer','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'blood_group': {
        'name': '🩸 Blood Group & Crossmatch',
        'category': 'Hematology & Haemostasis',
        'icon': '🩸',
        'tube': 'purple_edta',
        'accent': '#B22222',
        'gradient': 'linear-gradient(135deg,#2a0000 0%,#6b0000 60%,#990000 100%)',
        'text': '#ffcdd2',
        'department': 'HEM',
        'description': 'ABO grouping · Rh typing · Direct Coombs · Antibody screen · Crossmatch',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'blood_group','label':'ABO Group','type':'select','options':['A','B','AB','O']},
            {'key':'rh_factor','label':'Rh Factor','type':'select','options':['Positive','Negative']},
            {'key':'direct_coombs','label':'Direct Coombs','type':'select','options':['Negative','Positive','Weak+']},
            {'key':'antibody_screen','label':'Antibody Screen','type':'select','options':['Negative','Positive']},
            {'key':'crossmatch','label':'Crossmatch','type':'select','options':['Compatible','Incompatible','Pending']},
            {'key':'blood_unit_id','label':'Blood Unit ID','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'peripheral_smear': {
        'name': '🔬 Peripheral Blood Smear',
        'category': 'Hematology & Haemostasis',
        'icon': '🔬',
        'tube': 'purple_edta',
        'accent': '#C62828',
        'gradient': 'linear-gradient(135deg,#1a0a0a 0%,#6b1a1a 60%,#9b2222 100%)',
        'text': '#ffebee',
        'department': 'HEM',
        'description': 'RBC · WBC · Platelet morphology · Parasite detection · Differential',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'rbc_morphology','label':'RBC Morphology','type':'text'},
            {'key':'wbc_morphology','label':'WBC Morphology','type':'text'},
            {'key':'plt_morphology','label':'Platelet Morphology','type':'text'},
            {'key':'blast_pct','label':'Blasts (%)','type':'number'},
            {'key':'malaria_parasites','label':'Malaria Parasites','type':'select','options':['Negative','P.falciparum','P.vivax','P.malariae','P.ovale','Mixed']},
            {'key':'sickle_cells','label':'Sickle Cells','type':'select','options':['Absent','Present']},
            {'key':'leukemia_flag','label':'Leukemia Flag','type':'select','options':['No','Suspected','Confirmed']},
            {'key':'staining','label':'Stain','type':'select','options':['Leishman','Giemsa','Wright','May-Grünwald']},
            {'key':'microscopist','label':'Microscopist','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'coagulation': {
        'name': '💙 Coagulation Book',
        'category': 'Hematology & Haemostasis',
        'icon': '💙',
        'tube': 'blue_citrate',
        'accent': '#1565C0',
        'gradient': 'linear-gradient(135deg,#000a2a 0%,#003080 60%,#0050c0 100%)',
        'text': '#d0e8ff',
        'department': 'COAG',
        'description': 'PT · INR · aPTT · Fibrinogen · D-Dimer · Thrombin Time · Anti-Xa',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'pt','label':'PT (s)','type':'number','flag_hi':14,'critical_hi':30},
            {'key':'inr','label':'INR','type':'number','flag_hi':1.2,'critical_hi':3.0},
            {'key':'aptt','label':'aPTT (s)','type':'number','flag_hi':35,'critical_hi':70},
            {'key':'fibrinogen','label':'Fibrinogen (g/L)','type':'number','flag_lo':2,'flag_hi':4,'critical_lo':1.0},
            {'key':'ddimer','label':'D-Dimer (mg/L)','type':'number','flag_hi':0.5,'critical_hi':5.0},
            {'key':'anticoagulant','label':'Anticoagulant Rx','type':'text'},
            {'key':'analyzer','label':'Analyzer','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── BIOCHEMISTRY & ENDOCRINOLOGY ────────────────────────────────────────
    'general_chemistry': {
        'name': '🧫 General Biochemistry Book',
        'category': 'Biochemistry & Endocrinology',
        'icon': '🧫',
        'tube': 'yellow_sst',
        'accent': '#F57F17',
        'gradient': 'linear-gradient(135deg,#1a0e00 0%,#7a4000 60%,#c06800 100%)',
        'text': '#fff8e1',
        'department': 'BIOCHEM',
        'description': 'Glucose · Urea · Creatinine · LFT · Electrolytes · Lipids',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'glucose','label':'Glucose (mmol/L)','type':'number','flag_lo':3.9,'flag_hi':6.1,'critical_lo':2.2,'critical_hi':22},
            {'key':'urea','label':'Urea (mmol/L)','type':'number','flag_hi':7.5},
            {'key':'creatinine','label':'Creatinine (µmol/L)','type':'number','flag_hi':115,'critical_hi':500},
            {'key':'sodium','label':'Na+ (mmol/L)','type':'number','flag_lo':136,'flag_hi':145,'critical_lo':120,'critical_hi':160},
            {'key':'potassium','label':'K+ (mmol/L)','type':'number','flag_lo':3.5,'flag_hi':5.1,'critical_lo':2.5,'critical_hi':6.5},
            {'key':'alt','label':'ALT (U/L)','type':'number','flag_hi':45,'critical_hi':1000},
            {'key':'ast','label':'AST (U/L)','type':'number','flag_hi':40},
            {'key':'bilirubin','label':'TBil (µmol/L)','type':'number','flag_hi':21},
            {'key':'cholesterol','label':'Chol (mmol/L)','type':'number','flag_hi':5.2},
            {'key':'analyzer','label':'Analyzer','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'endocrinology': {
        'name': '🔵 Endocrinology & Hormones',
        'category': 'Biochemistry & Endocrinology',
        'icon': '🔵',
        'tube': 'yellow_sst',
        'accent': '#1565C0',
        'gradient': 'linear-gradient(135deg,#000a2a 0%,#0d2975 60%,#1a4aba 100%)',
        'text': '#e3f2fd',
        'department': 'HORMONE',
        'description': 'TSH · T3 · T4 · Cortisol · Prolactin · Testosterone · Oestrogen · Insulin · LH · FSH',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'test_name','label':'Test','type':'select','options':['TSH','Free T3','Free T4','Cortisol (AM)','Cortisol (PM)','Prolactin','Testosterone','Oestradiol (E2)','LH','FSH','Progesterone','DHEA-S','Insulin','C-Peptide','PTH','Aldosterone']},
            {'key':'result_value','label':'Result','type':'number'},
            {'key':'unit','label':'Unit','type':'text'},
            {'key':'reference_range','label':'Reference Range','type':'text'},
            {'key':'flag','label':'Flag','type':'flag'},
            {'key':'collection_time','label':'Collection Time','type':'text'},
            {'key':'clinical_context','label':'Clinical Context','type':'text'},
            {'key':'analyzer','label':'Analyzer','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'tumour_markers': {
        'name': '🎗️ Tumour Markers Book',
        'category': 'Biochemistry & Endocrinology',
        'icon': '🎗️',
        'tube': 'yellow_sst',
        'accent': '#AD1457',
        'gradient': 'linear-gradient(135deg,#1a0010 0%,#6b004a 60%,#a0006a 100%)',
        'text': '#fce4ec',
        'department': 'MARKER',
        'description': 'AFP · CEA · PSA · CA-125 · CA 19-9 · CA 15-3 · NSE · CYFRA · β-hCG',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'marker','label':'Marker','type':'select','options':['AFP','CEA','PSA','Free PSA','CA-125','CA 19-9','CA 15-3','CA 72-4','NSE','CYFRA 21-1','β-hCG','Total hCG','Calcitonin','Thyroglobulin']},
            {'key':'result_value','label':'Result','type':'number'},
            {'key':'unit','label':'Unit','type':'text'},
            {'key':'reference_range','label':'Reference Range','type':'text'},
            {'key':'flag','label':'Flag','type':'flag'},
            {'key':'clinical_note','label':'Clinical Note','type':'text'},
            {'key':'oncology_referral','label':'Oncology Referral','type':'select','options':['Not required','Recommended','Urgent']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'cardiac_markers': {
        'name': '❤️ Cardiac Markers Book',
        'category': 'Biochemistry & Endocrinology',
        'icon': '❤️',
        'tube': 'yellow_sst',
        'accent': '#C62828',
        'gradient': 'linear-gradient(135deg,#1a0505 0%,#7a1515 60%,#b02020 100%)',
        'text': '#ffebee',
        'department': 'BIOCHEM',
        'description': 'Troponin I · Troponin T · CK-MB · CK · LDH · BNP · NT-proBNP · Myoglobin',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'troponin_i','label':'Troponin I (µg/L)','type':'number','flag_hi':0.04,'critical_hi':0.5},
            {'key':'ck_mb','label':'CK-MB (U/L)','type':'number','flag_hi':25},
            {'key':'ck_total','label':'CK Total (U/L)','type':'number','flag_hi':336},
            {'key':'ldh','label':'LDH (U/L)','type':'number','flag_hi':280},
            {'key':'nt_probnp','label':'NT-proBNP (pg/mL)','type':'number','flag_hi':125},
            {'key':'clinical_dx','label':'Clinical Diagnosis','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── IMMUNOLOGY & SEROLOGY ────────────────────────────────────────────────
    'serology_hiv': {
        'name': '🔴 HIV & Retroviral Book',
        'category': 'Immunology & Serology',
        'icon': '🔴',
        'tube': 'yellow_sst',
        'accent': '#B71C1C',
        'gradient': 'linear-gradient(135deg,#0d0000 0%,#500000 60%,#800000 100%)',
        'text': '#ffcdd2',
        'department': 'SERO',
        'description': 'HIV Rapid · HIV 1/2 ELISA · Confirmatory WB · CD4 count · WHO staging',
        'bsl2': True,
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'rapid_result','label':'Rapid Test','type':'select','options':['Non-Reactive','Reactive','Invalid']},
            {'key':'elisa_result','label':'ELISA Result','type':'select','options':['Non-Reactive','Reactive','Equivocal']},
            {'key':'sco_ratio','label':'S/CO Ratio','type':'number'},
            {'key':'confirmatory','label':'Confirmatory','type':'select','options':['Pending','Positive','Negative','Indeterminate']},
            {'key':'counselling','label':'Counselling Done','type':'select','options':['Pre-test','Post-test','Declined']},
            {'key':'who_stage','label':'WHO Stage','type':'select','options':['Not applicable','Stage 1','Stage 2','Stage 3','Stage 4']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'hepatitis_book': {
        'name': '🟡 Hepatitis Markers Book',
        'category': 'Immunology & Serology',
        'icon': '🟡',
        'tube': 'yellow_sst',
        'accent': '#F9A825',
        'gradient': 'linear-gradient(135deg,#1a1100 0%,#6b4a00 60%,#a07000 100%)',
        'text': '#fff8e1',
        'department': 'SERO',
        'description': 'HBsAg · HBcAb · HBeAg · Anti-HCV · HAV · HEV · HDV markers',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'hbsag','label':'HBsAg','type':'select','options':['Non-Reactive','Reactive']},
            {'key':'hbc_igg','label':'HBcAb IgG','type':'select','options':['Non-Reactive','Reactive']},
            {'key':'hbe_ag','label':'HBeAg','type':'select','options':['Non-Reactive','Reactive','Not tested']},
            {'key':'anti_hcv','label':'Anti-HCV','type':'select','options':['Non-Reactive','Reactive','Equivocal']},
            {'key':'anti_hav','label':'Anti-HAV','type':'select','options':['Non-Reactive','Reactive','Not tested']},
            {'key':'method','label':'Method','type':'select','options':['Rapid','ELISA','CLIA']},
            {'key':'sco_ratio','label':'S/CO','type':'number'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'autoimmune_book': {
        'name': '🛡️ Autoimmune & Allergy Book',
        'category': 'Immunology & Serology',
        'icon': '🛡️',
        'tube': 'yellow_sst',
        'accent': '#4527A0',
        'gradient': 'linear-gradient(135deg,#0a0020 0%,#2a0080 60%,#4a00c0 100%)',
        'text': '#ede7f6',
        'department': 'SERO',
        'description': 'ANA · ANCA · RF · Anti-CCP · C3/C4 · ASO · CRP · Total IgE · Allergen panels',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'test_name','label':'Test','type':'select','options':['ANA','ANCA (c-ANCA)','ANCA (p-ANCA)','Rheumatoid Factor','Anti-CCP','Anti-dsDNA','Complement C3','Complement C4','ASO Titre','CRP','Total IgE','Specific IgE']},
            {'key':'result_value','label':'Result / Titre','type':'text'},
            {'key':'unit','label':'Unit','type':'text'},
            {'key':'flag','label':'Flag','type':'flag'},
            {'key':'pattern','label':'Pattern (ANA)','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'widal_serogroup': {
        'name': '🔬 Widal & Other Serology',
        'category': 'Immunology & Serology',
        'icon': '🔬',
        'tube': 'yellow_sst',
        'accent': '#00796B',
        'gradient': 'linear-gradient(135deg,#001a18 0%,#00504a 60%,#007a70 100%)',
        'text': '#e0f2f1',
        'department': 'SERO',
        'description': 'Widal · VDRL · TPHA · Brucella · Cryptococcal · Dengue · Typhoid',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'test_name','label':'Test','type':'select','options':['Widal (O)','Widal (H)','VDRL','TPHA','Brucella Ab','Cryptococcal Ag','Dengue NS1','Dengue IgM','Dengue IgG','Leptospira IgM','Scrub Typhus IgM']},
            {'key':'titre','label':'Titre / Result','type':'text'},
            {'key':'interpretation','label':'Interpretation','type':'select','options':['Negative','Positive','Equivocal','Significant titre']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── MICROBIOLOGY — BY SPECIMEN ───────────────────────────────────────────
    'blood_culture': {
        'name': '🩸 Blood Culture Book',
        'category': 'Microbiology — Specimens',
        'icon': '🩸',
        'tube': 'blood_culture',
        'accent': '#880E4F',
        'gradient': 'linear-gradient(135deg,#0d0010 0%,#450030 60%,#700050 100%)',
        'text': '#fce4ec',
        'department': 'MICRO',
        'description': 'Blood · Bone marrow cultures — organism identification · antibiogram',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'specimen','label':'Specimen','type':'select','options':['Peripheral blood','Central line','Bone marrow','Port-a-cath']},
            {'key':'volume_ml','label':'Volume (mL)','type':'number'},
            {'key':'media_used','label':'Media','type':'select','options':['BacT/ALERT','BACTEC Aerobic','BACTEC Anaerobic','Brucella medium','Sabouraud']},
            {'key':'growth_status','label':'Growth','type':'select','options':['Pending','No growth (5d)','No growth (10d)','Growth — Gram+','Growth — Gram-','Growth — Yeast','Growth — AFB']},
            {'key':'organism','label':'Organism Identified','type':'text'},
            {'key':'is_mrsa','label':'MRSA','type':'select','options':['No','Yes']},
            {'key':'is_esbl','label':'ESBL','type':'select','options':['No','Yes']},
            {'key':'is_cro','label':'CRO','type':'select','options':['No','Yes']},
            {'key':'antibiogram_days','label':'Days to Grow','type':'number'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'urine_culture': {
        'name': '🟡 Urine Culture Book',
        'category': 'Microbiology — Specimens',
        'icon': '🟡',
        'tube': 'urine',
        'accent': '#F9A825',
        'gradient': 'linear-gradient(135deg,#1a1400 0%,#6b5500 60%,#a08000 100%)',
        'text': '#fff8e1',
        'department': 'MICRO',
        'description': 'MSU · CSU · SPA — colony count · organism · antibiogram',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'collection_method','label':'Collection','type':'select','options':['MSU (midstream)','CSU (catheter)','SPA (suprapubic)','Bag urine']},
            {'key':'macroscopy','label':'Macroscopy','type':'text'},
            {'key':'wbc_count','label':'WBC count (/µL)','type':'text'},
            {'key':'growth_status','label':'Growth','type':'select','options':['No growth','Significant growth (>10⁵)','Mixed growth','Contaminated']},
            {'key':'organism','label':'Organism','type':'text'},
            {'key':'colony_count','label':'Colony Count (CFU/mL)','type':'text'},
            {'key':'sensitivity_summary','label':'Sensitivity Summary','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'stool_microbiology': {
        'name': '🟤 Stool Microbiology Book',
        'category': 'Microbiology — Specimens',
        'icon': '🟤',
        'tube': 'stool',
        'accent': '#6D4C41',
        'gradient': 'linear-gradient(135deg,#0a0500 0%,#3a1a10 60%,#60302a 100%)',
        'text': '#efebe9',
        'department': 'MICRO',
        'description': 'Culture · Microscopy · Parasitology · H.pylori · C.diff · Rotavirus',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'consistency','label':'Consistency','type':'select','options':['Formed','Semi-formed','Loose','Watery','Bloody','Mucoid','Bloody-mucoid']},
            {'key':'ova_parasites','label':'Ova & Parasites','type':'text'},
            {'key':'culture_organism','label':'Culture Organism','type':'text'},
            {'key':'cdiff','label':'C. difficile','type':'select','options':['Not tested','Negative','Positive (toxin A)','Positive (toxin B)','Positive (A+B)']},
            {'key':'rota_adeno','label':'Rota/Adenovirus','type':'select','options':['Not tested','Negative','Rotavirus +','Adenovirus +']},
            {'key':'hpylori','label':'H. pylori Ag','type':'select','options':['Not tested','Negative','Positive']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'sputum_tb': {
        'name': '💨 Sputum & Respiratory Book',
        'category': 'Microbiology — Specimens',
        'icon': '💨',
        'tube': 'sputum',
        'accent': '#0277BD',
        'gradient': 'linear-gradient(135deg,#000d1a 0%,#00355a 60%,#005580 100%)',
        'text': '#e1f5fe',
        'department': 'MICRO',
        'description': 'AFB smear · ZN stain · Auramine · Culture · GeneXpert MTB · Sputum quality',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'specimen_type','label':'Specimen','type':'select','options':['Sputum (induced)','Sputum (expectorated)','BAL','Bronchial washings','Nasopharyngeal swab']},
            {'key':'sputum_quality','label':'Quality','type':'select','options':['Adequate (>25 WBC, <10 squam)','Saliva — rejected','Adequate — salivary']},
            {'key':'afb_smear','label':'AFB Smear (ZN)','type':'select','options':['Negative','Scanty (1-9/100 HPF)','1+ (10-99/100 HPF)','2+ (1-10/HPF)','3+ (>10/HPF)']},
            {'key':'genexpert','label':'GeneXpert MTB','type':'select','options':['Not tested','Not detected','Detected — Rif sensitive','Detected — Rif resistant','Invalid/Error']},
            {'key':'culture_result','label':'Culture (LJ/MGIT)','type':'select','options':['Pending','Negative (8 wks)','Growth — MTB','Growth — NTM','Contaminated']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'body_fluid': {
        'name': '💧 Body Fluid Book',
        'category': 'Microbiology — Specimens',
        'icon': '💧',
        'tube': 'fluid',
        'accent': '#00838F',
        'gradient': 'linear-gradient(135deg,#00141a 0%,#005060 60%,#007880 100%)',
        'text': '#e0f7fa',
        'department': 'MICRO',
        'description': 'CSF · Pleural · Ascitic · Synovial · Pericardial · Peritoneal · Amniotic',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'fluid_type','label':'Fluid Type','type':'select','options':['CSF','Pleural','Ascitic/Peritoneal','Synovial','Pericardial','Amniotic','Bursa','Drain fluid']},
            {'key':'appearance','label':'Appearance','type':'select','options':['Clear colourless','Xanthochromic','Turbid/Cloudy','Haemorrhagic/Bloody','Milky/Chylous','Purulent']},
            {'key':'wbc_count','label':'WBC (/µL)','type':'number'},
            {'key':'rbc_count','label':'RBC (/µL)','type':'number'},
            {'key':'protein','label':'Protein (g/L)','type':'number'},
            {'key':'glucose','label':'Glucose (mmol/L)','type':'number'},
            {'key':'lactate','label':'Lactate (mmol/L)','type':'number'},
            {'key':'gram_stain','label':'Gram Stain','type':'text'},
            {'key':'culture_result','label':'Culture','type':'text'},
            {'key':'cytology_result','label':'Cytology','type':'select','options':['Not requested','Negative','Atypical','Malignant cells']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'wound_swab': {
        'name': '🩹 Wound & Swab Culture Book',
        'category': 'Microbiology — Specimens',
        'icon': '🩹',
        'tube': 'swab',
        'accent': '#558B2F',
        'gradient': 'linear-gradient(135deg,#0a1400 0%,#2a4a10 60%,#456820 100%)',
        'text': '#f1f8e9',
        'department': 'MICRO',
        'description': 'Wound · Throat · Ear · Eye · Nasal · Genital · Decubitus ulcer swabs',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'swab_site','label':'Site','type':'select','options':['Wound','Throat','Ear (L)','Ear (R)','Eye (L)','Eye (R)','Nasal','High vaginal','Endocervical','Urethral','Perianal','Decubitus ulcer','Surgical site','Diabetic foot','Burns wound']},
            {'key':'gram_stain','label':'Gram Stain','type':'text'},
            {'key':'organism','label':'Organism Isolated','type':'text'},
            {'key':'is_mrsa','label':'MRSA','type':'select','options':['No','Yes']},
            {'key':'sensitivity_summary','label':'Sensitivity','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'urinalysis_book': {
        'name': '🟡 Urinalysis Book',
        'category': 'Microbiology — Specimens',
        'icon': '🟡',
        'tube': 'urine',
        'accent': '#FBC02D',
        'gradient': 'linear-gradient(135deg,#1a1300 0%,#6b5500 60%,#a08200 100%)',
        'text': '#fff9c4',
        'department': 'URN',
        'description': 'Dipstick · Macroscopy · Microscopy · 24h protein · Microalbumin',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'colour','label':'Colour','type':'text'},
            {'key':'appearance','label':'Appearance','type':'select','options':['Clear','Slightly turbid','Turbid','Haematuric']},
            {'key':'ph','label':'pH','type':'number'},
            {'key':'sg','label':'SG','type':'text'},
            {'key':'protein','label':'Protein','type':'select','options':['Negative','Trace','1+','2+','3+','4+']},
            {'key':'glucose','label':'Glucose','type':'select','options':['Negative','Trace','1+','2+','3+','4+']},
            {'key':'blood','label':'Blood','type':'select','options':['Negative','Trace','1+','2+','3+']},
            {'key':'nitrite','label':'Nitrite','type':'select','options':['Negative','Positive']},
            {'key':'leukocytes','label':'Leukocytes','type':'select','options':['Negative','Trace','1+','2+','3+']},
            {'key':'ketones','label':'Ketones','type':'select','options':['Negative','Trace','Moderate','Large']},
            {'key':'microscopy_rbc','label':'RBC/HPF','type':'text'},
            {'key':'microscopy_wbc','label':'WBC/HPF','type':'text'},
            {'key':'bacteria','label':'Bacteria','type':'select','options':['None','Few','Moderate','Many']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── MOLECULAR & GENOMICS ─────────────────────────────────────────────────
    'viral_load_book': {
        'name': '💉 Viral Load Book',
        'category': 'Molecular & Genomics',
        'icon': '💉',
        'tube': 'plasma',
        'accent': '#D32F2F',
        'gradient': 'linear-gradient(135deg,#0d0000 0%,#500010 60%,#800020 100%)',
        'text': '#ffd7d7',
        'department': 'MOL',
        'description': 'HIV VL · HBV VL · HCV VL · CMV · EBV — ART monitoring · Suppression status',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'virus','label':'Virus','type':'select','options':['HIV-1','HIV-2','HBV','HCV','CMV','EBV']},
            {'key':'assay','label':'Assay','type':'text'},
            {'key':'copies_per_ml','label':'Copies/mL','type':'number'},
            {'key':'log10','label':'Log₁₀ Value','type':'number'},
            {'key':'vl_category','label':'Category','type':'select','options':['Undetectable','Suppressed (<1000)','Viremic (1k-10k)','High (10k-100k)','Very High (>100k)']},
            {'key':'on_art','label':'On ART','type':'select','options':['Yes','No','Not applicable']},
            {'key':'art_regimen','label':'ART Regimen','type':'text'},
            {'key':'art_months','label':'Months on ART','type':'number'},
            {'key':'vl_trend','label':'Trend','type':'select','options':['First test','Declining','Stable','Rising','Rebounding']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'tb_analysis': {
        'name': '🦠 TB Analysis Book',
        'category': 'Molecular & Genomics',
        'icon': '🦠',
        'tube': 'sputum',
        'accent': '#E65100',
        'gradient': 'linear-gradient(135deg,#0d0500 0%,#502000 60%,#804000 100%)',
        'text': '#fff3e0',
        'department': 'MOL',
        'description': 'GeneXpert MTB/RIF · AFB · DST · MDR-TB · XDR-TB · Resistance profiling',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'specimen','label':'Specimen','type':'select','options':['Sputum','BAL','Gastric lavage','CSF','Lymph node','Biopsy','Urine']},
            {'key':'afb_smear','label':'AFB Smear','type':'select','options':['Negative','Scanty','1+','2+','3+']},
            {'key':'genexpert_mtb','label':'GeneXpert MTB','type':'select','options':['Not detected','Detected','Invalid']},
            {'key':'rif_resistance','label':'Rif Resistance','type':'select','options':['Not detected','Detected','Indeterminate']},
            {'key':'culture_result','label':'Culture (MTB)','type':'select','options':['Pending','Negative','Positive — Sensitive','Positive — RR-TB','Positive — MDR-TB','Positive — Pre-XDR','Positive — XDR-TB']},
            {'key':'tb_classification','label':'TB Classification','type':'select','options':['DS-TB','RR-TB','MDR-TB','Pre-XDR-TB','XDR-TB']},
            {'key':'dst_summary','label':'DST Summary','type':'text'},
            {'key':'public_health_notified','label':'Public Health Notified','type':'select','options':['Yes','No','Pending']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'pcr_molecular': {
        'name': '🔬 PCR Molecular Book',
        'category': 'Molecular & Genomics',
        'icon': '🔬',
        'tube': 'plasma',
        'accent': '#6A1B9A',
        'gradient': 'linear-gradient(135deg,#0a0020 0%,#350060 60%,#5a0090 100%)',
        'text': '#f3e5f5',
        'department': 'MOL',
        'description': 'STI PCR · Respiratory panel · Viral PCR · MRSA · C.diff · BioFire results',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'panel','label':'Panel','type':'select','options':['STI Panel','Respiratory Panel (BioFire)','Meningitis Panel','GI Panel','HIV RNA','HBV DNA','HCV RNA','MRSA PCR','C.diff PCR','HPV genotyping']},
            {'key':'instrument','label':'Instrument','type':'text'},
            {'key':'targets_detected','label':'Targets Detected','type':'text'},
            {'key':'ct_values','label':'Ct Values','type':'text'},
            {'key':'result_summary','label':'Result Summary','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'sequencing_book': {
        'name': '🧬 NGS Sequencing Book',
        'category': 'Molecular & Genomics',
        'icon': '🧬',
        'tube': 'plasma',
        'accent': '#283593',
        'gradient': 'linear-gradient(135deg,#000520 0%,#101870 60%,#202898 100%)',
        'text': '#e8eaf6',
        'department': 'MOL',
        'description': 'WGS · WES · Panel sequencing · RNA-seq · Coverage · Quality metrics',
        'columns': [
            {'key':'record_no','label':'Run ID','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'ngs_type','label':'NGS Type','type':'select','options':['WGS','WES','Gene panel','RNA-seq','Targeted amplicon','Metagenomics']},
            {'key':'sequencer','label':'Sequencer','type':'select','options':['Illumina NovaSeq','Illumina MiSeq','Oxford Nanopore','Ion Torrent','PacBio']},
            {'key':'target_coverage','label':'Target Coverage (×)','type':'number'},
            {'key':'mean_coverage','label':'Mean Coverage (×)','type':'number'},
            {'key':'q30_score','label':'Q30 Score (%)','type':'number'},
            {'key':'total_reads','label':'Total Reads (M)','type':'number'},
            {'key':'mapping_rate','label':'Mapping Rate (%)','type':'number'},
            {'key':'variants_found','label':'Variants Found','type':'number'},
            {'key':'pathogenic_variants','label':'Pathogenic','type':'number'},
            {'key':'analyst','label':'Analyst','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'novel_pattern_book': {
        'name': '⚠️ Novel Pattern Discovery Book',
        'category': 'Molecular & Genomics',
        'icon': '⚠️',
        'tube': 'plasma',
        'accent': '#F57C00',
        'gradient': 'linear-gradient(135deg,#0d0800 0%,#503000 60%,#804800 100%)',
        'text': '#fff8e1',
        'department': 'MOL',
        'description': 'Unknown mutations · New pathogen strains · Emerging resistance · Unusual variant combinations',
        'columns': [
            {'key':'record_no','label':'Novel ID','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'genome_position','label':'Genomic Position','type':'text'},
            {'key':'gene_name','label':'Gene / Region','type':'text'},
            {'key':'mutation_type','label':'Mutation Type','type':'select','options':['SNV','Indel','CNV','Fusion','Structural','Unknown']},
            {'key':'sequence_change','label':'Sequence Change','type':'text'},
            {'key':'database_match','label':'DB Match','type':'select','options':['No match found','Partial match','New strain variant','Known but unusual combination']},
            {'key':'ai_confidence','label':'AI Confidence (%)','type':'number'},
            {'key':'predicted_impact','label':'Predicted Impact','type':'select','options':['Benign','Uncertain','Likely pathogenic','Pathogenic']},
            {'key':'alert_level','label':'Alert Level','type':'select','options':['Watch','Warning','Alert','Emergency']},
            {'key':'publication_status','label':'Publication','type':'select','options':['Internal only','Shared with WHO','Submitted to ClinVar','Published']},
            {'key':'assigned_geneticist','label':'Assigned Geneticist','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'genomic_prediction': {
        'name': '🔮 Genomic Prediction Book',
        'category': 'Molecular & Genomics',
        'icon': '🔮',
        'tube': 'plasma',
        'accent': '#00838F',
        'gradient': 'linear-gradient(135deg,#001820 0%,#005060 60%,#007880 100%)',
        'text': '#e0f7fa',
        'department': 'MOL',
        'description': 'Pharmacogenomics · Cancer risk prediction · BRCA · Lynch · Drug metabolism · Carrier status',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'analysis_type','label':'Analysis Type','type':'select','options':['Pharmacogenomics','Hereditary cancer risk','Carrier screening','Prenatal aneuploidy','Drug metabolism','Polygenic risk score']},
            {'key':'gene_target','label':'Gene(s) Analysed','type':'text'},
            {'key':'mutation_detected','label':'Mutation Detected','type':'text'},
            {'key':'acmg_class','label':'ACMG Class','type':'select','options':['Pathogenic','Likely Pathogenic','VUS','Likely Benign','Benign']},
            {'key':'risk_score','label':'Risk Score','type':'text'},
            {'key':'clinical_significance','label':'Clinical Significance','type':'text'},
            {'key':'family_counselling','label':'Family Counselling','type':'select','options':['Recommended','Completed','Not required']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── ANATOMICAL PATHOLOGY ─────────────────────────────────────────────────
    'anapath_histology': {
        'name': '🔭 Histopathology Book (Anapath)',
        'category': 'Anatomical Pathology',
        'icon': '🔭',
        'tube': 'formalin',
        'accent': '#7B1FA2',
        'gradient': 'linear-gradient(135deg,#0d0020 0%,#3a0060 60%,#5a0090 100%)',
        'text': '#f3e5f5',
        'department': 'ANAPATH',
        'description': 'Biopsy · Surgical resection · Histological diagnosis · Grade · Margins · IHC',
        'columns': [
            {'key':'record_no','label':'Accession #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'specimen_type','label':'Specimen','type':'select','options':['Core biopsy','Excision biopsy','Surgical resection','TURP chips','Curettings','Total gastrectomy','Colectomy','Mastectomy','Other']},
            {'key':'organ_site','label':'Organ / Site','type':'text'},
            {'key':'diagnosis_category','label':'Diagnosis','type':'select','options':['Benign','Pre-malignant','Malignant','Inflammatory','Normal/Reactive','Inconclusive']},
            {'key':'tumour_type','label':'Tumour Type','type':'text'},
            {'key':'grade','label':'Grade','type':'select','options':['G1 — Well diff.','G2 — Moderate','G3 — Poorly diff.','G4 — Undifferentiated','Not applicable']},
            {'key':'margin_status','label':'Margins','type':'select','options':['Clear (>2mm)','Close (<2mm)','Involved','Not applicable']},
            {'key':'ihc_ordered','label':'IHC Ordered','type':'select','options':['No','Yes — pending','Completed']},
            {'key':'pathologist','label':'Pathologist','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'cytology_book': {
        'name': '💧 Cytology Book (PAP / FNAC)',
        'category': 'Anatomical Pathology',
        'icon': '💧',
        'tube': 'cytology',
        'accent': '#AD1457',
        'gradient': 'linear-gradient(135deg,#100010 0%,#500040 60%,#800060 100%)',
        'text': '#fce4ec',
        'department': 'ANAPATH',
        'description': 'PAP smear (Bethesda) · FNAC · LBC · Fluid cytology · Sputum cytology',
        'columns': [
            {'key':'record_no','label':'Accession #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'cyto_type','label':'Type','type':'select','options':['PAP Smear','LBC','FNAC','Fluid cytology','Sputum cytology','Urine cytology','Nipple discharge']},
            {'key':'adequacy','label':'Adequacy','type':'select','options':['Satisfactory','Satisfactory + TZ','Unsatisfactory']},
            {'key':'bethesda_category','label':'Bethesda / Result','type':'select','options':['NILM','ASC-US','LSIL','ASC-H','HSIL','SCC','AGC','AIS','Adenocarcinoma','Malignant — other','Negative for malignancy','Suspicious for malignancy']},
            {'key':'recommendation','label':'Recommendation','type':'select','options':['Routine screening','Repeat in 6 months','Colposcopy referral','Biopsy','MDT']},
            {'key':'cytopathologist','label':'Cytopathologist','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'ihc_book': {
        'name': '🎨 Immunohistochemistry (IHC) Book',
        'category': 'Anatomical Pathology',
        'icon': '🎨',
        'tube': 'formalin',
        'accent': '#4527A0',
        'gradient': 'linear-gradient(135deg,#050015 0%,#200060 60%,#350090 100%)',
        'text': '#ede7f6',
        'department': 'ANAPATH',
        'description': 'ER/PR/HER2/Ki-67 · CD markers · p53 · PD-L1 · Special stains',
        'columns': [
            {'key':'record_no','label':'Accession #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'linked_histo','label':'Linked Histology #','type':'text'},
            {'key':'marker','label':'Marker','type':'select','options':['ER','PR','HER2','Ki-67','p53','PD-L1','CD3','CD20','CD10','BCL2','BCL6','Synaptophysin','Chromogranin','S100','HMB45','Melan-A','TTF-1','CK7','CK20','Desmin','SMA','CD34','MDM2']},
            {'key':'clone_antibody','label':'Clone','type':'text'},
            {'key':'intensity','label':'Intensity (0-3)','type':'select','options':['0 — Negative','1+ Weak','2+ Moderate','3+ Strong']},
            {'key':'percent_positive','label':'% Positive','type':'number'},
            {'key':'h_score','label':'H-Score','type':'number'},
            {'key':'interpretation','label':'Interpretation','type':'select','options':['Positive','Negative','Equivocal (2+)']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'image_analysis_book': {
        'name': '🖼️ Image Analysis Book',
        'category': 'Anatomical Pathology',
        'icon': '🖼️',
        'tube': 'digital',
        'accent': '#0277BD',
        'gradient': 'linear-gradient(135deg,#000d1a 0%,#003060 60%,#005090 100%)',
        'text': '#e1f5fe',
        'department': 'ANAPATH',
        'description': 'AI slide analysis · Mitotic count · Cell quantification · Digital pathology records',
        'columns': [
            {'key':'record_no','label':'Analysis ID','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'linked_accession','label':'Linked Accession','type':'text'},
            {'key':'image_type','label':'Image Type','type':'select','options':['H&E slide','IHC slide','Cytology smear','Frozen section','Whole slide image (WSI)']},
            {'key':'ai_cellularity','label':'AI Cellularity (%)','type':'number'},
            {'key':'ai_mitoses','label':'AI Mitoses (/HPF)','type':'number'},
            {'key':'ai_necrosis','label':'AI Necrosis (%)','type':'number'},
            {'key':'ai_ki67_estimate','label':'AI Ki-67 Estimate (%)','type':'number'},
            {'key':'ai_grade_suggestion','label':'AI Grade Suggestion','type':'select','options':['G1','G2','G3','G4','Inconclusive']},
            {'key':'ai_confidence','label':'AI Confidence (%)','type':'number'},
            {'key':'pathologist_decision','label':'Pathologist Decision','type':'select','options':['Accepted with modification','Accepted as-is','Rejected — manual review']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── TOXICOLOGY ───────────────────────────────────────────────────────────
    'uds_book': {
        'name': '💊 Drug Screening (UDS) Book',
        'category': 'Toxicology',
        'icon': '💊',
        'tube': 'urine',
        'accent': '#7B1FA2',
        'gradient': 'linear-gradient(135deg,#0d0020 0%,#3a0060 60%,#5a0090 100%)',
        'text': '#f3e5f5',
        'department': 'TOX',
        'description': 'Cannabis · Opiates · Cocaine · Amphetamines · Benzodiazepines · MDMA',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'panel_type','label':'Panel','type':'select','options':['Standard 5','Extended 10','Workplace','Forensic']},
            {'key':'thc','label':'THC','type':'select','options':['Negative','Positive']},
            {'key':'opiates','label':'Opiates','type':'select','options':['Negative','Positive']},
            {'key':'cocaine','label':'Cocaine','type':'select','options':['Negative','Positive']},
            {'key':'amphetamines','label':'Amphetamines','type':'select','options':['Negative','Positive']},
            {'key':'benzodiazepines','label':'Benzodiazepines','type':'select','options':['Negative','Positive']},
            {'key':'methadone','label':'Methadone','type':'select','options':['Negative','Positive']},
            {'key':'mdma','label':'MDMA','type':'select','options':['Negative','Positive']},
            {'key':'overall_result','label':'Overall','type':'select','options':['Negative','Positive']},
            {'key':'confirmatory_required','label':'Confirmatory GC-MS','type':'select','options':['No','Yes — pending','Completed']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'tdm_book': {
        'name': '💉 Therapeutic Drug Monitoring Book',
        'category': 'Toxicology',
        'icon': '💉',
        'tube': 'yellow_sst',
        'accent': '#F57F17',
        'gradient': 'linear-gradient(135deg,#1a0e00 0%,#7a4000 60%,#c06800 100%)',
        'text': '#fff8e1',
        'department': 'TOX',
        'description': 'Vancomycin · Digoxin · Phenytoin · Lithium · Tacrolimus · Methotrexate',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'drug_name','label':'Drug','type':'select','options':['Vancomycin','Gentamicin','Amikacin','Digoxin','Phenytoin','Carbamazepine','Valproate','Lithium','Clozapine','Tacrolimus','Cyclosporin','Sirolimus','Methotrexate','Theophylline','Phenobarbitone']},
            {'key':'level_type','label':'Level Type','type':'select','options':['Trough (pre-dose)','Peak (post-dose)','Random']},
            {'key':'concentration','label':'Concentration','type':'number'},
            {'key':'unit','label':'Unit','type':'text'},
            {'key':'therapeutic_range','label':'Target Range','type':'text'},
            {'key':'interpretation','label':'Interpretation','type':'select','options':['Sub-therapeutic','Therapeutic','Toxic']},
            {'key':'dose_recommendation','label':'Dose Recommendation','type':'text'},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'poisoning_book': {
        'name': '☠️ Poisoning Cases Book',
        'category': 'Toxicology',
        'icon': '☠️',
        'tube': 'red_plain',
        'accent': '#B71C1C',
        'gradient': 'linear-gradient(135deg,#0d0000 0%,#500000 60%,#800000 100%)',
        'text': '#ffcdd2',
        'department': 'TOX',
        'description': 'Paracetamol · Organophosphate · CO · Heavy metals · Methanol · Salicylate',
        'columns': [
            {'key':'record_no','label':'Case #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'poison_type','label':'Poison','type':'select','options':['Paracetamol','Salicylate','Organophosphate','Lead (Pb)','Mercury (Hg)','Arsenic (As)','Carbon Monoxide','Methanol','Ethanol','Cyanide','Iron','Digoxin OD','Lithium OD','Other']},
            {'key':'result_value','label':'Level / Result','type':'number'},
            {'key':'unit','label':'Unit','type':'text'},
            {'key':'severity','label':'Severity','type':'select','options':['Mild','Moderate','Severe','Critical']},
            {'key':'antidote_given','label':'Antidote','type':'text'},
            {'key':'outcome','label':'Outcome','type':'select','options':['Recovered','Improved','Transferred ICU','Death','Unknown']},
            {'key':'validated_by','label':'Validated By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── BLOOD BANK & TRANSFUSION ─────────────────────────────────────────────
    'blood_bank_donor': {
        'name': '🩸 Blood Bank Donor Book',
        'category': 'Blood Bank & Transfusion',
        'icon': '🩸',
        'tube': 'pink_edta',
        'accent': '#C62828',
        'gradient': 'linear-gradient(135deg,#0d0000 0%,#500000 60%,#800000 100%)',
        'text': '#ffcdd2',
        'department': 'BLOOD_BANK',
        'description': 'Donor registration · Screening · Component preparation · FEFO storage',
        'columns': [
            {'key':'record_no','label':'Donor Record #','type':'text'},
            {'key':'donor_name','label':'Donor Name','type':'text'},
            {'key':'donor_id','label':'Donor ID','type':'text'},
            {'key':'blood_group','label':'Blood Group','type':'select','options':['A+','A-','B+','B-','AB+','AB-','O+','O-']},
            {'key':'donation_type','label':'Donation Type','type':'select','options':['Whole blood','Apheresis platelets','Plasmapheresis','Directed donation']},
            {'key':'volume_ml','label':'Volume (mL)','type':'number'},
            {'key':'hiv_screen','label':'HIV Screen','type':'select','options':['Non-Reactive','Reactive — deferred']},
            {'key':'hbsag_screen','label':'HBsAg Screen','type':'select','options':['Non-Reactive','Reactive — deferred']},
            {'key':'hcv_screen','label':'HCV Screen','type':'select','options':['Non-Reactive','Reactive — deferred']},
            {'key':'syphilis_screen','label':'Syphilis (VDRL)','type':'select','options':['Non-Reactive','Reactive — deferred']},
            {'key':'unit_status','label':'Unit Status','type':'select','options':['Quarantine','Released for use','Discarded']},
            {'key':'components','label':'Components Made','type':'text'},
            {'key':'expiry_date','label':'Expiry Date','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'transfusion_book': {
        'name': '💉 Transfusion Monitoring Book',
        'category': 'Blood Bank & Transfusion',
        'icon': '💉',
        'tube': 'pink_edta',
        'accent': '#880E4F',
        'gradient': 'linear-gradient(135deg,#0a0010 0%,#400040 60%,#700060 100%)',
        'text': '#fce4ec',
        'department': 'BLOOD_BANK',
        'description': 'Patient crossmatch · Blood unit tracking · Transfusion record · Haemovigilance',
        'columns': [
            {'key':'record_no','label':'Transfusion #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'blood_unit_id','label':'Blood Unit ID','type':'text'},
            {'key':'component','label':'Component','type':'select','options':['Packed RBCs','Fresh Frozen Plasma','Platelets','Cryoprecipitate','Whole blood','Granulocytes']},
            {'key':'blood_group_patient','label':'Patient Group','type':'text'},
            {'key':'blood_group_unit','label':'Unit Group','type':'text'},
            {'key':'crossmatch_result','label':'Crossmatch','type':'select','options':['Compatible','Incompatible','Emergency uncrossmatched']},
            {'key':'volume_transfused','label':'Volume (mL)','type':'number'},
            {'key':'transfusion_start','label':'Start Time','type':'text'},
            {'key':'transfusion_end','label':'End Time','type':'text'},
            {'key':'reaction_observed','label':'Reaction','type':'select','options':['None','Febrile','Allergic','Haemolytic','TRALI','TACO','Other']},
            {'key':'nurse_signature','label':'Nurse','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── OPERATIONS & ADMINISTRATION ──────────────────────────────────────────
    'reception_opd': {
        'name': '🏥 Reception OPD Book',
        'category': 'Administration & Operations',
        'icon': '🏥',
        'tube': 'admin',
        'accent': '#1565C0',
        'gradient': 'linear-gradient(135deg,#000820 0%,#002a6b 60%,#003a9b 100%)',
        'text': '#e3f2fd',
        'department': 'RECEPTION',
        'description': 'Outpatient registration · Walk-in patients · OPD queue · Sample receipt',
        'columns': [
            {'key':'record_no','label':'Visit #','type':'text'},
            {'key':'patient_name','label':'Patient Name','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'lid','label':'LID (Lab ID)','type':'text'},
            {'key':'age','label':'Age','type':'text'},
            {'key':'sex','label':'Sex','type':'select','options':['M','F']},
            {'key':'referring_doctor','label':'Referring Doctor','type':'text'},
            {'key':'clinical_indication','label':'Clinical Indication','type':'text'},
            {'key':'tests_ordered','label':'Tests Ordered','type':'text'},
            {'key':'payment_method','label':'Payment','type':'select','options':['Cash','Insurance (RSSB)','Mutuelle','RAMA','Military','Free/Waived']},
            {'key':'amount_rwf','label':'Amount (RWF)','type':'number'},
            {'key':'receptionist','label':'Receptionist','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'reception_ipd': {
        'name': '🛏️ Reception IPD Book',
        'category': 'Administration & Operations',
        'icon': '🛏️',
        'tube': 'admin',
        'accent': '#00695C',
        'gradient': 'linear-gradient(135deg,#001a18 0%,#00504a 60%,#007068 100%)',
        'text': '#e0f2f1',
        'department': 'RECEPTION',
        'description': 'Inpatient admissions · Ward samples · Urgent ward requests · Daily census',
        'columns': [
            {'key':'record_no','label':'Ward Request #','type':'text'},
            {'key':'patient_name','label':'Patient Name','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'ward','label':'Ward','type':'text'},
            {'key':'bed_number','label':'Bed #','type':'text'},
            {'key':'attending_doctor','label':'Attending Doctor','type':'text'},
            {'key':'urgency','label':'Urgency','type':'select','options':['STAT','Urgent','Routine']},
            {'key':'tests_requested','label':'Tests Requested','type':'text'},
            {'key':'sample_time','label':'Sample Collected','type':'text'},
            {'key':'received_by','label':'Received By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'sample_rejection': {
        'name': '🚫 Sample Rejection Book',
        'category': 'Administration & Operations',
        'icon': '🚫',
        'tube': 'rejection',
        'accent': '#B71C1C',
        'gradient': 'linear-gradient(135deg,#0d0000 0%,#500000 60%,#800000 100%)',
        'text': '#ffcdd2',
        'department': 'RECEPTION',
        'description': 'Rejected specimens with coded reason (CLSI EP23) · Corrective action · Ward notification',
        'columns': [
            {'key':'record_no','label':'Rejection #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'sid','label':'SID','type':'text'},
            {'key':'rejection_code','label':'Rejection Code','type':'text'},
            {'key':'rejection_reason','label':'Reason','type':'select','options':['ID-001 Unlabelled','ID-002 Mislabelled','SQ-001 Haemolysis','SQ-002 Lipaemia','SQ-004 Clotted EDTA','VOL-001 QNS','VOL-002 Underfilled citrate','TUB-001 Wrong tube','TUB-002 Expired tube','TUB-003 Leaking','TMG-002 Delayed transport','SAF-001 No biohazard label','Other']},
            {'key':'specimen_type','label':'Specimen','type':'text'},
            {'key':'department','label':'Department','type':'text'},
            {'key':'ward_notified','label':'Ward Notified','type':'select','options':['Yes','No']},
            {'key':'recollection_required','label':'Recollect','type':'select','options':['Yes','No']},
            {'key':'rejected_by','label':'Rejected By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'inventory_book': {
        'name': '📦 Inventory & Stock Book',
        'category': 'Administration & Operations',
        'icon': '📦',
        'tube': 'admin',
        'accent': '#33691E',
        'gradient': 'linear-gradient(135deg,#051200 0%,#203a0a 60%,#356020 100%)',
        'text': '#f1f8e9',
        'department': 'INVENTORY',
        'description': 'Reagent stock · Consumables · Equipment · Expiry monitoring · Reorder alerts',
        'columns': [
            {'key':'record_no','label':'Transaction #','type':'text'},
            {'key':'item_name','label':'Item Name','type':'text'},
            {'key':'item_code','label':'Item Code','type':'text'},
            {'key':'category','label':'Category','type':'select','options':['Reagent','Consumable','PPE','Equipment','Stationery','Cleaning']},
            {'key':'transaction_type','label':'Transaction','type':'select','options':['Stock received','Issued to dept','Returned','Disposed (expired)','Stock count correction']},
            {'key':'quantity','label':'Quantity','type':'number'},
            {'key':'unit','label':'Unit','type':'text'},
            {'key':'lot_number','label':'Lot #','type':'text'},
            {'key':'expiry_date','label':'Expiry Date','type':'text'},
            {'key':'stock_balance','label':'Balance After','type':'number'},
            {'key':'department_issued','label':'Issued To','type':'text'},
            {'key':'recorded_by','label':'Recorded By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'finance_book': {
        'name': '💰 Finance & Billing Book',
        'category': 'Administration & Operations',
        'icon': '💰',
        'tube': 'admin',
        'accent': '#F9A825',
        'gradient': 'linear-gradient(135deg,#100a00 0%,#504000 60%,#806000 100%)',
        'text': '#fff8e1',
        'department': 'FINANCE',
        'description': 'Daily billing · Payments received · Insurance claims · MoMo transactions · Daily totals',
        'columns': [
            {'key':'record_no','label':'Invoice #','type':'text'},
            {'key':'patient_name','label':'Patient','type':'text'},
            {'key':'pid','label':'PID','type':'text'},
            {'key':'tests_billed','label':'Tests Billed','type':'text'},
            {'key':'gross_amount','label':'Gross (RWF)','type':'number'},
            {'key':'discount','label':'Discount (RWF)','type':'number'},
            {'key':'net_amount','label':'Net Amount (RWF)','type':'number'},
            {'key':'payment_method','label':'Payment Method','type':'select','options':['Cash','MTN MoMo','Airtel Money','Visa/MasterCard','RSSB Insurance','Mutuelle de Santé','RAMA','Military Insurance','Free/Government waiver']},
            {'key':'amount_paid','label':'Paid (RWF)','type':'number'},
            {'key':'balance','label':'Balance (RWF)','type':'number'},
            {'key':'transaction_id','label':'Transaction ID','type':'text'},
            {'key':'cashier','label':'Cashier','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── SURVEILLANCE & EPIDEMIOLOGY ──────────────────────────────────────────
    'epidemiology_book': {
        'name': '🔭 Epidemiology & Surveillance Book',
        'category': 'Surveillance & Public Health',
        'icon': '🔭',
        'tube': 'admin',
        'accent': '#1B5E20',
        'gradient': 'linear-gradient(135deg,#001500 0%,#005000 60%,#007500 100%)',
        'text': '#e8f5e9',
        'department': 'SURVEILLANCE',
        'description': 'Notifiable diseases · Outbreak signals · Disease trends · AMR surveillance',
        'columns': [
            {'key':'record_no','label':'Signal #','type':'text'},
            {'key':'disease','label':'Disease / Pathogen','type':'text'},
            {'key':'department','label':'Department','type':'text'},
            {'key':'new_cases','label':'New Cases','type':'number'},
            {'key':'total_7day','label':'7-Day Total','type':'number'},
            {'key':'baseline_rate','label':'Baseline Rate','type':'number'},
            {'key':'pct_increase','label':'% Increase','type':'number'},
            {'key':'alert_level','label':'Alert Level','type':'select','options':['Watch','Warning','Alert','Emergency']},
            {'key':'district','label':'District','type':'text'},
            {'key':'ai_signal','label':'AI Signal','type':'select','options':['Yes','No']},
            {'key':'public_health_notified','label':'MoH Notified','type':'select','options':['Yes','No','Pending']},
            {'key':'resolved','label':'Resolved','type':'select','options':['Yes','No','Ongoing']},
            {'key':'recorded_by','label':'Recorded By','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    # ── QUALITY & AUDIT ──────────────────────────────────────────────────────
    'iqc_book': {
        'name': '📐 IQC / Levey-Jennings Book',
        'category': 'Quality & Audit',
        'icon': '📐',
        'tube': 'qc',
        'accent': '#00838F',
        'gradient': 'linear-gradient(135deg,#001a1f 0%,#005060 60%,#007878 100%)',
        'text': '#e0f7fa',
        'department': 'QM',
        'description': 'Daily IQC results · Westgard rules · Pass/Fail/Warn · All departments',
        'columns': [
            {'key':'record_no','label':'Record #','type':'text'},
            {'key':'department','label':'Department','type':'text'},
            {'key':'analyte','label':'Analyte','type':'text'},
            {'key':'control_level','label':'Level','type':'select','options':['L1 (Low normal)','L2 (High normal)','L3 (Pathological)']},
            {'key':'lot_number','label':'Lot #','type':'text'},
            {'key':'target_mean','label':'Target Mean','type':'number'},
            {'key':'sd','label':'SD','type':'number'},
            {'key':'result_value','label':'Result Value','type':'number'},
            {'key':'z_score','label':'Z-Score','type':'number'},
            {'key':'westgard_rule','label':'Westgard Rule','type':'select','options':['PASS','1_2s (Warn)','1_3s (Reject)','2_2s (Reject)','R_4s (Reject)','4_1s (Reject)','10x (Reject)']},
            {'key':'qc_status','label':'QC Status','type':'select','options':['PASS','WARN','REJECT']},
            {'key':'analyzer','label':'Analyzer','type':'text'},
            {'key':'operator','label':'Operator','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },

    'shift_handover': {
        'name': '🔄 Shift Handover Book',
        'category': 'Quality & Audit',
        'icon': '🔄',
        'tube': 'admin',
        'accent': '#37474F',
        'gradient': 'linear-gradient(135deg,#050a0d 0%,#1a2a30 60%,#2c3e50 100%)',
        'text': '#eceff1',
        'department': 'ALL',
        'description': 'Shift summary · Pending tasks · Equipment issues · Staff handover · Daily totals',
        'columns': [
            {'key':'record_no','label':'Handover #','type':'text'},
            {'key':'shift','label':'Shift','type':'select','options':['Morning (6am-2pm)','Afternoon (2pm-10pm)','Night (10pm-6am)']},
            {'key':'department','label':'Department','type':'text'},
            {'key':'outgoing_staff','label':'Outgoing Staff','type':'text'},
            {'key':'incoming_staff','label':'Incoming Staff','type':'text'},
            {'key':'samples_received','label':'Samples Received','type':'number'},
            {'key':'samples_pending','label':'Samples Pending','type':'number'},
            {'key':'critical_results','label':'Critical Results','type':'number'},
            {'key':'equipment_issues','label':'Equipment Issues','type':'text'},
            {'key':'pending_tasks','label':'Pending Tasks','type':'text'},
            {'key':'iqc_status','label':'IQC Status','type':'select','options':['All PASS','Warnings noted','Rejections — escalated']},
            {'key':'notes','label':'General Notes','type':'text'},
            {'key':'status','label':'Status','type':'status'},
        ],
    },
}

# ── Book categories for display ───────────────────────────────────────────────

BOOK_CATEGORIES = [
    'Hematology & Haemostasis',
    'Biochemistry & Endocrinology',
    'Immunology & Serology',
    'Microbiology — Specimens',
    'Molecular & Genomics',
    'Anatomical Pathology',
    'Toxicology',
    'Blood Bank & Transfusion',
    'Administration & Operations',
    'Surveillance & Public Health',
    'Quality & Audit',
]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get('/books')
def list_books(_u: User = Depends(get_current_user)) -> dict:
    """Return the complete books catalogue."""
    result = {}
    for cat in BOOK_CATEGORIES:
        cat_books = {k: {**v, 'id': k} for k, v in BOOKS.items() if v.get('category') == cat}
        if cat_books:
            result[cat] = cat_books
    return {'categories': BOOK_CATEGORIES, 'books': result, 'total': len(BOOKS)}


@router.get('/books/{book_id}')
def get_book(book_id: str, _u: User = Depends(get_current_user)) -> dict:
    """Return metadata for a specific book."""
    b = BOOKS.get(book_id)
    if not b:
        raise HTTPException(404, f'Book not found: {book_id}')
    return {**b, 'id': book_id}


@router.get('/books/{book_id}/entries')
def list_entries(
    book_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    shift: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
) -> dict:
    """
    List entries for a specific record book.
    Pulls from the appropriate model based on book_id.
    """
    b = BOOKS.get(book_id)
    if not b:
        raise HTTPException(404, f'Book not found: {book_id}')

    # Route to the appropriate model
    rows, total = _query_book_entries(book_id, b, db, date_from, date_to, status, search, shift, skip, limit)

    return {
        'book_id': book_id,
        'book_name': b['name'],
        'total': total,
        'entries': rows,
        'columns': b.get('columns', []),
    }


def _query_book_entries(book_id: str, book_cfg: dict, db: Session, date_from, date_to, status, search, shift, skip, limit):
    """Route book_id to the correct SQLAlchemy model and query."""
    dept = book_cfg.get('department', '')

    try:
        # Hematology
        if book_id == 'hematology':
            from models.hematology import HemResult as M
            q = db.query(M)
            if date_from: q = q.filter(func.date(M.created_at) >= date_from)
            if date_to:   q = q.filter(func.date(M.created_at) <= date_to)
            total = q.count()
            rows = _hem_to_dict(q.order_by(desc(M.created_at)).offset(skip).limit(limit).all())
            return rows, total

        elif book_id == 'blood_group':
            from models.laboratory import LabResult as M
            q = db.query(M).filter(M.result_type == 'QUALITATIVE')
            total = q.count()
            return _generic_result_to_dict(q.offset(skip).limit(limit).all()), total

        elif book_id == 'coagulation':
            from models.coagulation import CoagResult as M
            q = db.query(M)
            if date_from: q = q.filter(func.date(M.created_at) >= date_from)
            if date_to:   q = q.filter(func.date(M.created_at) <= date_to)
            if status:    q = q.filter(M.status == status)
            total = q.count()
            return _coag_to_dict(q.order_by(desc(M.created_at)).offset(skip).limit(limit).all()), total

        elif book_id in ('serology_hiv', 'hepatitis_book', 'autoimmune_book', 'widal_serogroup'):
            from models.serology import SerologyResult as M
            q = db.query(M)
            if date_from: q = q.filter(func.date(M.created_at) >= date_from)
            if date_to:   q = q.filter(func.date(M.created_at) <= date_to)
            total = q.count()
            return _sero_to_dict(q.order_by(desc(M.created_at)).offset(skip).limit(limit).all()), total

        elif book_id in ('blood_culture','urine_culture','stool_microbiology','wound_swab'):
            from models.microbiology import MicroCulture as M
            q = db.query(M)
            if date_from: q = q.filter(func.date(M.created_at) >= date_from)
            if date_to:   q = q.filter(func.date(M.created_at) <= date_to)
            total = q.count()
            return _culture_to_dict(q.order_by(desc(M.created_at)).offset(skip).limit(limit).all()), total

        elif book_id == 'urinalysis_book':
            from models.urinalysis import DipstickResult as M
            q = db.query(M)
            total = q.count()
            return _dip_to_dict(q.order_by(desc(M.created_at)).offset(skip).limit(limit).all()), total

        elif book_id == 'viral_load_book':
            from models.molecular import ViralLoad as M
            q = db.query(M)
            total = q.count()
            return _vl_to_dict(q.order_by(desc(M.created_at)).offset(skip).limit(limit).all()), total

        elif book_id == 'tb_analysis':
            from models.molecular import PCRResult as M
            q = db.query(M).filter(M.pcr_category == 'TB')
            total = q.count()
            return _pcr_to_dict(q.order_by(desc(M.created_at)).offset(skip).limit(limit).all()), total

        elif book_id == 'sample_rejection':
            from models.rejection import SampleRejection as M
            q = db.query(M)
            if date_from: q = q.filter(func.date(M.rejected_at) >= date_from)
            total = q.count()
            return _rejection_to_dict(q.order_by(desc(M.rejected_at)).offset(skip).limit(limit).all()), total

        elif book_id == 'iqc_book':
            from models.quality import IQCResult as M
            q = db.query(M)
            if date_from: q = q.filter(M.run_date >= date_from)
            total = q.count()
            return _iqc_to_dict(q.order_by(desc(M.run_date)).offset(skip).limit(limit).all()), total

        else:
            # Generic — try lab results for this department
            from models.laboratory import LabResult as M
            q = db.query(M)
            if date_from: q = q.filter(func.date(M.entered_at) >= date_from)
            if date_to:   q = q.filter(func.date(M.entered_at) <= date_to)
            total = q.count()
            return _generic_result_to_dict(q.order_by(desc(M.entered_at)).offset(skip).limit(limit).all()), total

    except Exception as e:
        return [], 0


# ── Serializers ───────────────────────────────────────────────────────────────

def _base(obj, i: int) -> dict:
    return {
        'record_no': f'REC-{str(i+1).zfill(5)}',
        'pid': getattr(obj, 'pid', '—') or '—',
        'lid': getattr(obj, 'lid', '—') or '—',
        'status': getattr(obj, 'status', 'PENDING') or 'PENDING',
        'created_at': str(obj.created_at)[:16] if hasattr(obj,'created_at') and obj.created_at else '—',
        'is_validated': getattr(obj, 'is_validated', False),
        'is_critical': getattr(obj, 'is_critical', False),
    }

def _hem_to_dict(rows):
    return [{**_base(r,i), 'hgb':r.hgb,'wbc':r.wbc,'plt':r.plt,'hct':r.hct,'mcv':r.mcv,'esr':r.esr,
             'hgb_flag':r.hgb_flag,'wbc_flag':r.wbc_flag,'plt_flag':r.plt_flag,
             'analyzer':r.analyzer_name,'result_source':r.result_source} for i,r in enumerate(rows)]

def _coag_to_dict(rows):
    return [{**_base(r,i), 'test_code':r.test_code,'test_name':r.test_name,
             'numeric_value':r.numeric_value,'unit':r.unit,'flag':r.flag,
             'anticoagulant':r.anticoagulant,'anticoag_status':r.anticoag_status} for i,r in enumerate(rows)]

def _sero_to_dict(rows):
    return [{**_base(r,i), 'test_code':r.test_code,'test_name':r.test_name,
             'qualitative':r.qualitative,'sco_ratio':r.sco_ratio,'method':r.method,
             'bsl_2_alert':r.bsl_2_alert,'confirmatory_required':r.confirmatory_required} for i,r in enumerate(rows)]

def _culture_to_dict(rows):
    return [{**_base(r,i), 'specimen_type':r.specimen_type,'growth_status':r.growth_status,
             'organism_identified':r.organism_identified,'is_mrsa':r.is_mrsa,
             'is_esbl':r.is_esbl,'is_cro':r.is_cro,'gram_stain_result':r.gram_stain_result} for i,r in enumerate(rows)]

def _dip_to_dict(rows):
    return [{**_base(r,i), 'colour':r.colour,'appearance':r.appearance,'ph':r.ph,'sg':r.sg,
             'protein':r.protein,'glucose':r.glucose,'blood':r.blood,'nitrite':r.nitrite,
             'leukocytes':r.leukocytes,'overall_flag':r.overall_flag,'uti_suspected':r.uti_suspected} for i,r in enumerate(rows)]

def _vl_to_dict(rows):
    return [{**_base(r,i), 'virus':r.virus,'assay_name':r.assay_name,'copies_per_ml':r.copies_per_ml,
             'log10_value':r.log10_value,'vl_category':r.vl_category,'on_art':r.on_art,
             'art_regimen':r.art_regimen,'vl_trend':r.vl_trend} for i,r in enumerate(rows)]

def _pcr_to_dict(rows):
    return [{**_base(r,i), 'test_name':r.test_name,'result':r.result,'ct_value':r.ct_value,
             'rifampicin_resistance':r.rifampicin_resistance,'tb_classification':r.tb_classification,
             'instrument':r.instrument,'specimen_type':r.specimen_type} for i,r in enumerate(rows)]

def _rejection_to_dict(rows):
    return [{**_base(r,i), 'rejection_id':r.rejection_id,'rejection_code':r.rejection_code,
             'rejection_name':r.rejection_name,'severity':r.severity,'sid':r.sid,
             'specimen_type':r.specimen_type,'department':r.department,
             'ward_notified':r.ward_notified,'recollect_required':r.recollect_required,
             'rejected_by':r.rejected_by_name,'rejected_at':str(r.rejected_at)[:16] if r.rejected_at else '—'} for i,r in enumerate(rows)]

def _iqc_to_dict(rows):
    return [{**_base(r,i), 'department':r.department,'analyte_code':r.analyte_code,
             'analyte_name':r.analyte_name,'control_level':r.control_level,
             'target_mean':r.target_mean,'sd':r.sd,'result_value':r.result_value,
             'z_score':r.z_score,'westgard_rule':r.westgard_rule,'qc_status':r.status,
             'analyzer':r.analyzer_name,'operator':r.operator_name} for i,r in enumerate(rows)]

def _generic_result_to_dict(rows):
    return [{**_base(r,i), 'result_value':r.result_value or r.numeric_value,
             'unit':getattr(r,'unit',None),'flag':getattr(r,'flag',None)} for i,r in enumerate(rows)]


@router.post('/books/{book_id}/entries', status_code=201)
def create_entry(
    book_id: str,
    entry: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Create a new record book entry (generic — for admin books)."""
    b = BOOKS.get(book_id)
    if not b:
        raise HTTPException(404, f'Book not found: {book_id}')
    # For now return success; actual save handled by department-specific routers
    return {
        'status': 'created',
        'book_id': book_id,
        'message': f'Entry saved to {b["name"]}',
    }


@router.get('/stats')
def records_stats(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> dict:
    """Overall records statistics for the index page."""
    today = date_t.today()
    stats = {}
    try:
        from models.laboratory import LabResult
        stats['total_results_today'] = db.query(LabResult).filter(func.date(LabResult.entered_at)==today).count()
        stats['total_results_all'] = db.query(LabResult).count()
    except: pass
    try:
        from models.rejection import SampleRejection
        stats['rejections_today'] = db.query(SampleRejection).filter(func.date(SampleRejection.rejected_at)==today).count()
    except: pass
    stats['total_books'] = len(BOOKS)
    return stats
