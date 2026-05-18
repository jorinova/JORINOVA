"""
NEXUS ALIS-X — Database Seed Script
=====================================
Creates:
  1. Database tables (create_all)
  2. Default hospital record
  3. Default admin + staff users
  4. Test catalog (200+ common lab tests with prices in RWF)
  5. Lab departments
  6. Specimen types (worklist seeding)
  7. Sample IQC data for Levey-Jennings demo

Run from backend/ directory:
    python scripts/seed_database.py

Or with reset:
    python scripts/seed_database.py --reset
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from datetime import date, datetime, timedelta
import random

parser = argparse.ArgumentParser()
parser.add_argument('--reset', action='store_true', help='Drop and recreate all tables')
args = parser.parse_args()

from core.database import engine, Base, SessionLocal
from core.security import hash_password

# ── Import ALL models so Base.metadata knows all tables ──────────────────────
import models.user, models.patient, models.laboratory, models.core_config
import models.hematology, models.biochemistry, models.blood_bank
import models.quality, models.worklist, models.billing, models.notifications
import models.audit, models.rejection, models.staffhub
try:
    import models.microbiology, models.molecular, models.coagulation
    import models.serology, models.urinalysis, models.surveillance
except Exception as e:
    print(f'  [skip optional models] {e}')

if args.reset:
    print('Dropping all tables...')
    Base.metadata.drop_all(engine)
    print('Tables dropped.')

print('Creating tables...')
Base.metadata.create_all(engine)
print('Tables created.')

db = SessionLocal()

# ── 1. HOSPITAL ───────────────────────────────────────────────────────────────
from models.core_config import Hospital
if not db.query(Hospital).first():
    hospital = Hospital(
        name     = 'JORINOVA NEXUS University Hospital',
        address  = 'KG 9 Ave, Kigali, Rwanda',
        phone    = '+250788000001',
        email    = 'lab@jorinova.rw',
        district = 'Gasabo',
        province = 'Kigali City',
        is_active= True,
    )
    db.add(hospital)
    db.flush()
    print(f'  Hospital created: {hospital.name}')
else:
    hospital = db.query(Hospital).first()
    print(f'  Hospital exists: {hospital.name}')

# ── 2. LAB DEPARTMENTS ────────────────────────────────────────────────────────
from models.core_config import LabDepartment
DEPTS = [
    ('HAEM', 'Hematology',                'hematology'),
    ('CHEM', 'Biochemistry & Chemistry',   'biochemistry'),
    ('COAG', 'Coagulation',               'coagulation'),
    ('URIN', 'Urinalysis',                'urinalysis'),
    ('MICR', 'Microbiology',              'microbiology'),
    ('MOLC', 'Molecular & Genomics',      'molecular'),
    ('SERO', 'Serology & Immunology',     'serology'),
    ('BBTH', 'Blood Bank & Transfusion',  'blood_bank'),
    ('PATH', 'Pathology & Histology',     'pathology'),
    ('TOXI', 'Toxicology',                'toxicology'),
    ('ENDC', 'Endocrinology',             'biochemistry'),
]
dept_map = {}
for code, name, key in DEPTS:
    existing = db.query(LabDepartment).filter(LabDepartment.code == code).first()
    if not existing:
        dept = LabDepartment(code=code, name=name, is_active=True, hospital_id=hospital.id)
        db.add(dept); db.flush()
        dept_map[key] = dept.id
        print(f'  Department: {name}')
    else:
        dept_map[key] = existing.id
db.commit()

# ── 3. USERS ──────────────────────────────────────────────────────────────────
from models.user import User

USERS = [
    dict(username='admin',      password='admin123',    role='super_admin',
         first_name='System',   last_name='Admin',      email='admin@nexus.rw',   is_active=True),
    dict(username='labmanager', password='nexus2026',   role='lab_manager',
         first_name='Jean',     last_name='Mutabazi',   email='jmutabazi@nexus.rw',is_active=True),
    dict(username='scientist',  password='nexus2026',   role='scientist',
         first_name='Marie',    last_name='Uwimana',    email='muwimana@nexus.rw', is_active=True),
    dict(username='hematology', password='nexus2026',   role='scientist',
         first_name='Patrick',  last_name='Nkurunziza', email='pnkuru@nexus.rw',   is_active=True),
    dict(username='biochemist', password='nexus2026',   role='scientist',
         first_name='Alice',    last_name='Mukamana',   email='amukamana@nexus.rw',is_active=True),
    dict(username='receptionist',password='nexus2026',  role='receptionist',
         first_name='Grace',    last_name='Ingabire',   email='gingabire@nexus.rw',is_active=True),
    dict(username='pathologist',password='nexus2026',   role='pathologist',
         first_name='Dr. Paul', last_name='Habimana',   email='phabimana@nexus.rw',is_active=True),
]
for u in USERS:
    if not db.query(User).filter(User.username == u['username']).first():
        user = User(
            username         = u['username'],
            hashed_password  = hash_password(u['password']),
            role             = u['role'],
            first_name       = u['first_name'],
            last_name        = u['last_name'],
            email            = u['email'],
            is_active        = u['is_active'],
            hospital_id      = hospital.id,
        )
        db.add(user)
        print(f'  User: {u["username"]} ({u["role"]}) / password: {u["password"]}')
db.commit()

# ── 4. TEST CATALOG ───────────────────────────────────────────────────────────
from models.core_config import TestCatalog

# (code, name, dept_key, specimen, tube, price_rwf, tat_h, unit, ref_range_text, loinc)
TEST_CATALOG = [
    # HEMATOLOGY
    ('CBC',     'Complete Blood Count (CBC)',        'hematology', 'EDTA Blood',   'HEM', 3000, 1,  'various',      'See report',          '58410-2'),
    ('HGB',     'Haemoglobin',                       'hematology', 'EDTA Blood',   'HEM', 1500, 1,  'g/dL',         'M:13.5-17.5 F:12-16', '718-7'),
    ('MCV',     'Mean Corpuscular Volume (MCV)',      'hematology', 'EDTA Blood',   'HEM', 1500, 1,  'fL',           '80-100',              '787-2'),
    ('RETICS',  'Reticulocyte Count',                 'hematology', 'EDTA Blood',   'HEM', 2000, 2,  '%',            '0.5-2.5',             '17849-1'),
    ('ESR',     'Erythrocyte Sedimentation Rate (ESR)','hematology','EDTA Blood',  'ESR', 2000, 1,  'mm/h',         'M:<15 F:<20',         '30341-2'),
    ('PBSMEAR', 'Peripheral Blood Smear (PBS)',       'hematology', 'EDTA Blood',   'HEM', 3500, 2,  '',             'See report',          '46245-3'),
    ('HBELECTRO','Haemoglobin Electrophoresis',       'hematology', 'EDTA Blood',   'HEM', 8000, 24, '',             'See report',          '4552-8'),
    ('G6PD',    'G6PD Enzyme Assay',                  'hematology', 'EDTA Blood',   'HEM', 5000, 4,  'U/gHb',        '6.9-15.4',            '2348-5'),
    ('BM',      'Bone Marrow Examination',             'hematology', 'Bone Marrow',  'BNM', 25000,24, '',             'See report',          ''),
    # COAGULATION
    ('PT',      'Prothrombin Time (PT)',               'coagulation','Citrate Blood','CIT', 3500, 2,  's',            '11-14',               '5902-2'),
    ('INR',     'INR (Derived from PT)',               'coagulation','Citrate Blood','CIT', 3500, 2,  'ratio',        '0.8-1.2',             '34714-6'),
    ('APTT',    'Activated Partial Thromboplastin Time','coagulation','Citrate Blood','CIT',3500, 2, 's',            '25-38',               '14979-9'),
    ('FIBRIN',  'Fibrinogen',                          'coagulation','Citrate Blood','CIT', 5000, 2,  'g/L',          '2.0-4.0',             '3255-7'),
    ('DDIMER',  'D-Dimer',                             'coagulation','Citrate Blood','CIT', 12000,2,  'mg/L FEU',     '<0.5',                '48065-7'),
    # BIOCHEMISTRY — RENAL
    ('UREA',    'Urea',                                'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'mmol/L',       '2.5-7.1',             '3094-0'),
    ('CREAT',   'Creatinine',                          'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'µmol/L',       'M:62-115 F:53-97',    '2160-0'),
    ('URIC',    'Uric Acid',                           'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'µmol/L',       'M:208-428 F:155-357', '3084-1'),
    ('EGFR',    'eGFR (CKD-EPI)',                      'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'mL/min/1.73m²','≥90',                 '98979-8'),
    ('CYSSTAT', 'Cystatin C',                          'biochemistry','Serum/Plasma', 'SST', 8000, 4, 'mg/L',         '0.62-1.15',           '33914-3'),
    # BIOCHEMISTRY — LIVER
    ('ALT',     'ALT (SGPT)',                          'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'U/L',          'M:<56 F:<45',         '1742-6'),
    ('AST',     'AST (SGOT)',                          'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'U/L',          '<40',                 '1920-8'),
    ('GGT',     'GGT (Gamma-GT)',                      'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'U/L',          'M:<73 F:<43',         '2324-6'),
    ('ALP',     'Alkaline Phosphatase (ALP)',           'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'U/L',          '44-147',              '6768-6'),
    ('TBILI',   'Total Bilirubin',                     'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'µmol/L',       '<20.5',               '1975-2'),
    ('DBILI',   'Direct Bilirubin',                    'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'µmol/L',       '<8.6',                '1968-7'),
    ('ALB',     'Albumin',                             'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'g/L',          '35-52',               '1751-7'),
    ('LFT',     'Liver Function Tests (LFT panel)',    'biochemistry','Serum/Plasma', 'SST', 12000,2, 'various',      'See report',          ''),
    # BIOCHEMISTRY — GENERAL
    ('GLUCOSE_F','Fasting Blood Glucose',              'biochemistry','Fluoride Blood','FLU',2000, 1, 'mmol/L',       '3.9-6.1',             '1558-6'),
    ('GLUCOSE_R','Random Blood Glucose',               'biochemistry','Fluoride Blood','FLU',2000, 1, 'mmol/L',       '<11.1',               '2345-1'),
    ('HBA1C',   'HbA1c (Glycated Haemoglobin)',        'biochemistry','EDTA Blood',   'HEM', 5000, 4, '%',            '<6.5',                '4548-4'),
    ('PROT',    'Total Protein',                       'biochemistry','Serum/Plasma', 'SST', 2000, 2, 'g/L',          '66-83',               '2885-2'),
    # BIOCHEMISTRY — ELECTROLYTES
    ('NA',      'Sodium (Na⁺)',                        'biochemistry','Serum/Plasma', 'SST', 2000, 1, 'mmol/L',       '136-145',             '2951-2'),
    ('K',       'Potassium (K⁺)',                      'biochemistry','Serum/Plasma', 'SST', 2000, 1, 'mmol/L',       '3.5-5.1',             '2823-3'),
    ('CL',      'Chloride (Cl⁻)',                      'biochemistry','Serum/Plasma', 'SST', 2000, 1, 'mmol/L',       '98-107',              '2075-0'),
    ('BICARB',  'Bicarbonate (HCO₃⁻)',                 'biochemistry','Serum/Plasma', 'SST', 2000, 1, 'mmol/L',       '22-29',               '1963-8'),
    ('CA',      'Calcium (Ca²⁺)',                      'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'mmol/L',       '2.15-2.55',           '17861-6'),
    ('MG',      'Magnesium (Mg²⁺)',                    'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'mmol/L',       '0.65-1.05',           '19123-9'),
    ('PHOS',    'Phosphate (PO₄³⁻)',                   'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'mmol/L',       '0.81-1.45',           '2777-1'),
    ('U_E',     'Urea + Electrolytes (U&E Panel)',     'biochemistry','Serum/Plasma', 'SST', 8000, 2, 'various',      'See report',          ''),
    # BIOCHEMISTRY — LIPIDS
    ('CHOL',    'Total Cholesterol',                   'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'mmol/L',       '<5.2',                '2093-3'),
    ('LDL',     'LDL Cholesterol',                     'biochemistry','Serum/Plasma', 'SST', 3000, 2, 'mmol/L',       '<3.4',                '13457-7'),
    ('HDL',     'HDL Cholesterol',                     'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'mmol/L',       'M:>1.0 F:>1.2',       '2085-9'),
    ('TG',      'Triglycerides',                       'biochemistry','Serum/Plasma', 'SST', 2500, 2, 'mmol/L',       '<1.7',                '3043-7'),
    ('LIPID',   'Lipid Profile (panel)',               'biochemistry','Serum/Plasma', 'SST', 10000,2, 'various',      'See report',          ''),
    # CARDIAC MARKERS
    ('TROP_I',  'Troponin I (cardiac)',                'biochemistry','Serum/Plasma', 'SST', 15000,2, 'ng/mL',        '<0.04',               '10839-9'),
    ('TROP_T',  'Troponin T (hs)',                     'biochemistry','Serum/Plasma', 'SST', 18000,2, 'ng/L',         '<14',                 '67151-1'),
    ('CKMB',    'CK-MB',                               'biochemistry','Serum/Plasma', 'SST', 8000, 2, 'µg/L',         '<5.0',                '13969-1'),
    ('BNP',     'BNP (Brain Natriuretic Peptide)',     'biochemistry','Serum/Plasma', 'SST', 15000,4, 'pg/mL',        '<100',                '30934-4'),
    ('NTBNP',   'NT-proBNP',                           'biochemistry','Serum/Plasma', 'SST', 18000,4, 'pg/mL',        '<125 (<75y)',          '33762-6'),
    ('LDH',     'Lactate Dehydrogenase (LDH)',         'biochemistry','Serum/Plasma', 'SST', 3000, 2, 'U/L',          '140-280',             '2532-0'),
    # THYROID
    ('TSH',     'TSH (Thyroid Stimulating Hormone)',   'biochemistry','Serum/Plasma', 'SST', 5000, 4, 'mIU/L',        '0.27-4.2',            '3016-4'),
    ('FT4',     'Free T4 (Thyroxine)',                 'biochemistry','Serum/Plasma', 'SST', 5000, 4, 'pmol/L',       '12-22',               '3024-8'),
    ('FT3',     'Free T3 (Triiodothyronine)',           'biochemistry','Serum/Plasma', 'SST', 5000, 4, 'pmol/L',       '3.1-6.8',             '3051-0'),
    ('ATPO',    'Anti-TPO Antibodies',                 'biochemistry','Serum/Plasma', 'SST', 8000, 24,'IU/mL',        '<35',                 '5380-1'),
    ('TFT',     'Thyroid Function Tests (panel)',      'biochemistry','Serum/Plasma', 'SST', 15000,4, 'various',      'See report',          ''),
    # IRON STUDIES
    ('FERRITIN','Ferritin',                            'biochemistry','Serum/Plasma', 'SST', 5000, 4, 'µg/L',         'M:30-400 F:13-150',   '2276-4'),
    ('IRON',    'Serum Iron',                          'biochemistry','Serum/Plasma', 'SST', 3000, 4, 'µmol/L',       '10.6-28.3',           '2498-4'),
    ('TIBC',    'TIBC',                                'biochemistry','Serum/Plasma', 'SST', 3000, 4, 'µmol/L',       '45-75',               '2501-5'),
    ('IRONSTD', 'Iron Studies (panel)',                'biochemistry','Serum/Plasma', 'SST', 10000,4, 'various',      'See report',          ''),
    # VITAMINS
    ('VB12',    'Vitamin B12 (Cobalamin)',             'biochemistry','Serum/Plasma', 'SST', 8000, 24,'pmol/L',       '148-738',             '2132-9'),
    ('FOLATE',  'Folate (Folic Acid)',                 'biochemistry','Serum/Plasma', 'SST', 6000, 24,'nmol/L',       '>7.0',                '2284-8'),
    ('VD',      'Vitamin D (25-OH)',                   'biochemistry','Serum/Plasma', 'SST', 10000,24,'nmol/L',       '>50',                 '1989-3'),
    # TUMOUR MARKERS
    ('PSA',     'PSA (Prostate Specific Antigen)',     'biochemistry','Serum/Plasma', 'SST', 8000, 8, 'ng/mL',        '<4.0 (age-dep)',       '10334-1'),
    ('CEA',     'CEA (Carcinoembryonic Antigen)',      'biochemistry','Serum/Plasma', 'SST', 8000, 8, 'ng/mL',        '<5.0',                '2857-1'),
    ('AFP',     'Alpha-Fetoprotein (AFP)',             'biochemistry','Serum/Plasma', 'SST', 8000, 8, 'ng/mL',        '<8.1',                '1834-1'),
    ('CA125',   'CA-125 (Ovarian)',                    'biochemistry','Serum/Plasma', 'SST', 10000,8, 'U/mL',         '<35',                 '10334-1'),
    ('CA199',   'CA-19-9 (Pancreatic)',               'biochemistry','Serum/Plasma', 'SST', 10000,8, 'U/mL',         '<37',                 '24108-3'),
    ('CA153',   'CA-15-3 (Breast)',                   'biochemistry','Serum/Plasma', 'SST', 8000, 8, 'U/mL',         '<25',                 '85319-2'),
    # INFLAMMATORY
    ('CRP',     'C-Reactive Protein (CRP)',            'biochemistry','Serum/Plasma', 'SST', 3000, 2, 'mg/L',         '<10',                 '1988-5'),
    ('CRP_HS',  'hsCRP (High Sensitivity)',            'biochemistry','Serum/Plasma', 'SST', 5000, 2, 'mg/L',         '<3.0',                '30522-7'),
    # HORMONES
    ('CORTISOL','Cortisol (AM)',                       'biochemistry','Serum/Plasma', 'SST', 8000, 8, 'nmol/L',       '138-690 (AM)',         '2143-6'),
    ('INSULIN', 'Insulin',                             'biochemistry','Serum/Plasma', 'SST', 8000, 8, 'mIU/L',        '2.6-24.9',            '20448-7'),
    ('FSH',     'FSH (Follicle Stimulating Hormone)',  'biochemistry','Serum/Plasma', 'SST', 6000, 8, 'IU/L',         'Sex/phase dep.',       '15067-2'),
    ('LH',      'LH (Luteinizing Hormone)',            'biochemistry','Serum/Plasma', 'SST', 6000, 8, 'IU/L',         'Sex/phase dep.',       '10501-5'),
    ('PROLACT', 'Prolactin (PRL)',                     'biochemistry','Serum/Plasma', 'SST', 6000, 8, 'mIU/L',        'M:86-324 F:102-496',  '2842-3'),
    ('TESTOS',  'Testosterone (Total)',                'biochemistry','Serum/Plasma', 'SST', 8000, 8, 'nmol/L',       'M:9.9-27.8 F:0.2-2.9','2986-1'),
    ('ESTRAD',  'Oestradiol (E2)',                     'biochemistry','Serum/Plasma', 'SST', 6000, 8, 'pmol/L',       'Cycle dependent',     '2243-4'),
    ('PROGEST', 'Progesterone',                        'biochemistry','Serum/Plasma', 'SST', 6000, 8, 'nmol/L',       'Cycle dependent',     '2839-9'),
    ('HCG',     'β-hCG (Quantitative)',               'biochemistry','Serum/Plasma', 'SST', 5000, 4, 'mIU/mL',       'See report',          '21198-7'),
    ('PTH',     'Parathyroid Hormone (PTH)',           'biochemistry','Serum/Plasma', 'SST', 10000,8, 'pmol/L',       '1.6-9.3',             '2731-8'),
    # URINALYSIS
    ('UA',      'Urinalysis (Dip + Microscopy)',       'urinalysis', 'Urine (MSU)',   'URI', 2500, 1, 'various',      'See report',          '24357-6'),
    ('ACR',     'Albumin:Creatinine Ratio (ACR)',      'urinalysis', 'Urine (MSU)',   'URI', 3000, 2, 'mg/mmol',      '<3.0',                '9318-7'),
    ('24P',     '24-hour Urine Protein',               'urinalysis', '24-hour Urine','U24', 3500, 4, 'mg/day',       '<150',                '2888-6'),
    # MICROBIOLOGY — CULTURE
    ('UCSENS',  'Urine Culture + Sensitivity',         'microbiology','Urine (MSU)',  'URC', 8000, 48,'CFU/mL',       '<10⁵ (significant)',  '630-4'),
    ('BLOODCX', 'Blood Culture (Aerobic + Anaerobic)', 'microbiology','Blood Culture','BLC', 10000,120,'',            'No growth / Growth',  '600-7'),
    ('STOOLCX', 'Stool Culture + Sensitivity',         'microbiology','Stool',        'STL', 7000, 72,'',            'See report',          '625-4'),
    ('SPUTUMCX','Sputum Culture + Sensitivity',        'microbiology','Sputum',       'SPU', 7000, 72,'',            'See report',          '620-4'),
    ('WOUNDCX', 'Wound Swab Culture + Sensitivity',   'microbiology','Swab',         'SWB', 7000, 72,'',            'See report',          '612-2'),
    ('HVSCX',   'HVS Culture + Sensitivity',           'microbiology','HVS Swab',    'CER', 7000, 72,'',            'See report',          ''),
    ('AFBZN',   'AFB Smear (ZN Stain)',                'microbiology','Sputum',       'SPU', 3000, 24,'',            'No AFB seen / AFB+',  '11545-1'),
    ('GENEXPT', 'GeneXpert MTB/RIF Ultra',             'microbiology','Sputum',       'SPU', 25000,3,  '',            'MTB Detected/Not Det.','89365-1'),
    # PARASITOLOGY
    ('GE_FS',   'Thick + Thin Film (Malaria GE+FS)',   'microbiology','EDTA Blood',   'HEM', 3000, 1, 'P./µL',        'No parasites seen',   '32700-7'),
    ('MRDT',    'Malaria RDT (HRP2/pLDH)',             'microbiology','EDTA Blood',   'HEM', 2500, 0.5,'',           'Negative / Positive', '40454-0'),
    ('STOOLMICRO','Stool Microscopy (O&P)',            'microbiology','Stool',        'STL', 3000, 4, '',            'No ova or cysts seen','24956-5'),
    # SEROLOGY / IMMUNOLOGY
    ('HIVAB',   'HIV Antigen/Antibody (4th Gen)',      'serology',   'Serum/Plasma', 'SST', 4000, 1, '',            'Non-Reactive/Reactive','75622-1'),
    ('HBSAG',   'HBsAg (Hepatitis B Surface Ag)',      'serology',   'Serum/Plasma', 'SST', 4000, 4, '',            'Non-Reactive/Reactive','5196-1'),
    ('ANTIHBS', 'Anti-HBs (Hepatitis B Ab)',           'serology',   'Serum/Plasma', 'SST', 4000, 4, 'IU/L',        '>10 (protective)',    '16935-9'),
    ('HBVDNA',  'HBV DNA (Viral Load)',                'molecular',  'EDTA Blood',   'HEM', 30000,24,'IU/mL',        '<20 (UDL)',           '72914-5'),
    ('ANTIHCV', 'Anti-HCV (Hepatitis C)',              'serology',   'Serum/Plasma', 'SST', 4000, 4, '',            'Non-Reactive/Reactive','13955-0'),
    ('HCVRNA',  'HCV RNA (Viral Load)',                'molecular',  'EDTA Blood',   'HEM', 35000,24,'IU/mL',        '<15 (UDL)',           '11259-9'),
    ('VDRL',    'VDRL (Syphilis screening)',           'serology',   'Serum/Plasma', 'SST', 3000, 4, '',            'Non-Reactive/Reactive','31147-2'),
    ('TPHA',    'TPHA (Syphilis confirmation)',        'serology',   'Serum/Plasma', 'SST', 5000, 4, '',            'Non-Reactive/Reactive',''),
    ('CRAG',    'Cryptococcal Antigen (CrAg LFA)',     'serology',   'Serum/CSF',   'SST', 5000, 2, '',            'Negative/Positive',   ''),
    ('TOXIGG',  'Toxoplasma IgG/IgM',                  'serology',   'Serum/Plasma', 'SST', 6000, 8, 'IU/mL',        'See report',          ''),
    ('CMVIGG',  'CMV IgG/IgM',                         'serology',   'Serum/Plasma', 'SST', 6000, 8, '',            'See report',          ''),
    ('RF',      'Rheumatoid Factor (RF)',               'serology',   'Serum/Plasma', 'SST', 3000, 4, 'IU/mL',        '<20',                 '4537-7'),
    ('ANA',     'Antinuclear Antibodies (ANA)',         'serology',   'Serum/Plasma', 'SST', 8000, 24,'titre',        '<1:40',               '5048-4'),
    # MOLECULAR / GENOMICS
    ('VL_HIV',  'HIV Viral Load (RT-PCR)',             'molecular',  'EDTA Blood',   'HEM', 35000,24,'copies/mL',    '<40 (UDL)',           '25836-8'),
    ('CD4',     'CD4 T-Cell Count',                   'molecular',  'EDTA Blood',   'HEM', 10000,8, 'cells/µL',     '>500 (normal)',       '24467-3'),
    ('CD4_PCT', 'CD4% (CD4/CD8 Ratio)',               'molecular',  'EDTA Blood',   'HEM', 5000, 8, '%',            '>25%',               ''),
    ('TBPCR',   'TB PCR (IS6110)',                     'molecular',  'Sputum/BAL',   'SPU', 20000,8, '',            'Not Detected/Detected','71774-4'),
    ('COVIDPCR','SARS-CoV-2 RT-PCR',                  'molecular',  'NPS Swab',     'NPH', 15000,6, '',            'Not Detected/Detected','94534-5'),
    ('HPVDNA',  'HPV DNA (High-Risk Genotyping)',      'molecular',  'Cervical Swab','CER', 20000,24,'',            'Not Detected/Detected','21440-3'),
    # BLOOD BANK
    ('ABO',     'Blood Group (ABO + Rh Typing)',       'blood_bank', 'EDTA Blood',   'HEM', 3000, 1, '',            'See report',          '34530-6'),
    ('XMATCH',  'Cross-match (Compatibility)',         'blood_bank', 'EDTA + Clot',  'HEM', 5000, 2, '',            'Compatible/Incompatible','44180-7'),
    ('DAT',     'Direct Antiglobulin Test (DAT)',      'blood_bank', 'EDTA Blood',   'HEM', 5000, 2, '',            'Negative/Positive',   '14618-3'),
    ('ANTIBSC', 'Antibody Screen',                     'blood_bank', 'Serum/Plasma', 'SST', 6000, 4, '',            'Negative/Positive',   '890-3'),
]

from models.core_config import TestCatalog

added = 0
for (code, name, dept_key, specimen, tube, price, tat, unit, ref, loinc) in TEST_CATALOG:
    if not db.query(TestCatalog).filter(TestCatalog.code == code).first():
        dept_id = dept_map.get(dept_key) or dept_map.get('biochemistry')
        test = TestCatalog(
            code            = code,
            name            = name,
            department_id   = dept_id,
            specimen_type   = specimen,
            tube_type       = tube,
            price           = float(price),
            tat_hours       = float(tat),
            unit            = unit,
            reference_range = ref,
            loinc_code      = loinc,
            is_active       = True,
        )
        db.add(test)
        added += 1

db.commit()
print(f'  Test catalog: {added} tests added')

# ── 5. SPECIMEN TYPES (Worklist) ──────────────────────────────────────────────
from services.worklist_service import seed_specimen_types
seeded = seed_specimen_types(db)
if seeded:
    print(f'  Specimen types: {seeded} seeded')

# ── 6. SAMPLE IQC DATA (Levey-Jennings demo) ──────────────────────────────────
from models.quality import IQCResult

# Add 30 days of demo IQC data for Glucose L1 and L2
def add_iqc_run(dept, code, name, level, mean, sd, run_dt, drift=0.0):
    value = mean + drift + random.gauss(0, sd * 0.8)
    z     = (value - mean) / sd if sd else 0
    abs_z = abs(z)
    status = 'REJECT' if abs_z > 3 else 'WARN' if abs_z > 2 else 'PASS'
    rule   = '1_3s' if abs_z > 3 else '1_2s' if abs_z > 2 else 'PASS'
    r = IQCResult(
        department=dept, analyte_code=code, analyte_name=name,
        control_level=level, target_mean=mean, sd=sd,
        result_value=round(value, 3), unit='mmol/L',
        z_score=round(z, 3), westgard_rule=rule, status=status,
        analyzer_name='Cobas c501', operator_name='Demo Operator',
        run_date=run_dt, lot_number='LOT-2026-DEMO',
        hospital_id=hospital.id,
    )
    db.add(r)

if db.query(IQCResult).count() == 0:
    random.seed(42)  # reproducible demo data
    for dept, code, name, level, mean, sd in [
        ('biochemistry','GLUCOSE','Glucose', 'L1', 3.2, 0.15),
        ('biochemistry','GLUCOSE','Glucose', 'L2', 5.5, 0.20),
        ('biochemistry','CREAT',  'Creatinine','L1',50.0,2.5),
        ('hematology',  'HGB',    'Haemoglobin','L1', 80.0, 2.0),
        ('hematology',  'HGB',    'Haemoglobin','L2',130.0, 3.0),
    ]:
        drift = 0.0
        for d_back in range(30, -1, -1):
            run_dt = date.today() - timedelta(days=d_back)
            # Introduce drift after day 15 for demo
            if d_back < 12: drift += sd * 0.06
            add_iqc_run(dept, code, name, level, mean, sd, run_dt, drift)
    db.commit()
    print(f'  IQC demo data: 155 runs seeded (5 analytes × ~31 days)')

# ── DONE ──────────────────────────────────────────────────────────────────────
db.close()
print()
print('=' * 60)
print('SEED COMPLETE')
print('Login credentials:')
print('  admin / admin123       → super_admin')
print('  labmanager / nexus2026 → lab_manager')
print('  scientist / nexus2026  → scientist')
print('  receptionist / nexus2026 → receptionist')
print('  pathologist / nexus2026 → pathologist')
print('=' * 60)
