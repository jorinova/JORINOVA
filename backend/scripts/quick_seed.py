"""Quick seed — hospital, users, test catalog, IQC demo data."""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date, timedelta

import models.user, models.patient, models.laboratory, models.core_config
import models.hematology, models.biochemistry, models.blood_bank
import models.quality, models.worklist, models.billing, models.notifications

from core.database import SessionLocal, Base, engine
from core.security import hash_password, verify_password
from models.user import User
from models.core_config import Hospital, LaboratoryDepartment, TestCatalog
from models.quality import IQCResult
from services.worklist_service import seed_specimen_types

# Create all tables
Base.metadata.create_all(engine)
db = SessionLocal()

# Hospital
if not db.query(Hospital).first():
    h = Hospital(name='JORINOVA NEXUS University Hospital',
                 address='KG 9 Ave, Kigali, Rwanda',
                 phone='+250788000001', email='lab@jorinova.rw',
                 district='Gasabo', province='Kigali City', is_active=True)
    db.add(h); db.flush()
    print(f'Hospital: {h.name}')
else:
    h = db.query(Hospital).first()
    print(f'Hospital exists: {h.name}')

# Lab departments
dept_map = {}
for i, (code, name, key, abbr, color) in enumerate([
    ('HAEM','Hematology',           'hematology',  'HEM', '#dc2626'),
    ('CHEM','Biochemistry',         'biochemistry','BIO', '#2563eb'),
    ('COAG','Coagulation',          'coagulation', 'COA', '#7c3aed'),
    ('URIN','Urinalysis',           'urinalysis',  'URI', '#f59e0b'),
    ('MICR','Microbiology',         'microbiology','MIC', '#16a34a'),
    ('MOLC','Molecular & Genomics', 'molecular',   'MOL', '#0891b2'),
    ('SERO','Serology & Immunology','serology',    'SER', '#0284c7'),
    ('BBTH','Blood Bank',           'blood_bank',  'BBK', '#be185d'),
    ('PATH','Pathology',            'pathology',   'PAT', '#78716c'),
    ('TOXI','Toxicology',           'toxicology',  'TOX', '#b45309'),
]):
    existing = db.query(LaboratoryDepartment).filter(LaboratoryDepartment.code==code).first()
    if not existing:
        dept = LaboratoryDepartment(code=code, name=name, abbreviation=abbr,
                                    color_hex=color, order=i, is_active=True)
        db.add(dept); db.flush()
        dept_map[key] = dept.id
        print(f'  Dept: {name}')
    else:
        dept_map[key] = existing.id
db.commit()

# Users
USERS = [
    ('admin',        'admin123',  'super_admin',   'System',  'Administrator','admin@nexus.rw'),
    ('labmanager',   'nexus2026', 'lab_manager',   'Jean',    'Mutabazi',    'jm@nexus.rw'),
    ('scientist',    'nexus2026', 'scientist',     'Marie',   'Uwimana',     'mu@nexus.rw'),
    ('hematologist', 'nexus2026', 'scientist',     'Patrick', 'Nkurunziza',  'pn@nexus.rw'),
    ('biochemist',   'nexus2026', 'scientist',     'Alice',   'Mukamana',    'am@nexus.rw'),
    ('receptionist', 'nexus2026', 'receptionist',  'Grace',   'Ingabire',    'gi@nexus.rw'),
    ('pathologist',  'nexus2026', 'pathologist',   'Paul',    'Habimana',    'ph@nexus.rw'),
]
for username, password, role, fn, ln, email in USERS:
    if not db.query(User).filter(User.username==username).first():
        user = User(username=username, hashed_password=hash_password(password),
                    role=role, first_name=fn, last_name=ln, email=email,
                    is_active=True, hospital_id=h.id)
        db.add(user)
        print(f'  User: {username} / {password} ({role})')
db.commit()
print(f'Users: {db.query(User).count()} total')

# Test Catalog
TESTS = [
    # HEMATOLOGY
    ('CBC',     'Complete Blood Count',        'hematology',  'EDTA Blood',   'HEM', 3000, 1,    'various',   'See report',   '58410-2'),
    ('HGB',     'Haemoglobin',                 'hematology',  'EDTA Blood',   'HEM', 1500, 1,    'g/dL',      'M:13.5-17.5',  '718-7'),
    ('ESR',     'Erythrocyte Sedimentation Rate','hematology', 'EDTA Blood',  'HEM', 2000, 1,    'mm/h',      'M<15 F<20',    '30341-2'),
    ('RETICS',  'Reticulocyte Count',           'hematology',  'EDTA Blood',   'HEM', 2000, 2,    '%',         '0.5-2.5',      '17849-1'),
    ('HBELECTRO','Hgb Electrophoresis',         'hematology',  'EDTA Blood',   'HEM', 8000, 24,   '',          'See report',   '4552-8'),
    # COAGULATION
    ('PT',      'Prothrombin Time',             'coagulation', 'Citrate Blood','CIT', 3500, 2,    's',         '11-14',        '5902-2'),
    ('INR',     'INR',                          'coagulation', 'Citrate Blood','CIT', 3500, 2,    'ratio',     '0.8-1.2',      '34714-6'),
    ('APTT',    'APTT',                         'coagulation', 'Citrate Blood','CIT', 3500, 2,    's',         '25-38',        '14979-9'),
    ('DDIMER',  'D-Dimer',                      'coagulation', 'Citrate Blood','CIT', 12000,2,    'mg/L FEU',  '<0.5',         '48065-7'),
    # BIOCHEMISTRY
    ('GLUCOSE_F','Fasting Glucose',             'biochemistry','Fluoride Blood','FLU',2000, 1,    'mmol/L',    '3.9-6.1',      '1558-6'),
    ('GLUCOSE_R','Random Glucose',              'biochemistry','Fluoride Blood','FLU',2000, 1,    'mmol/L',    '<11.1',        '2345-1'),
    ('HBA1C',   'HbA1c',                        'biochemistry','EDTA Blood',   'HEM', 5000, 4,    '%',         '<6.5',         '4548-4'),
    ('UREA',    'Urea',                         'biochemistry','Serum',        'SST', 2500, 2,    'mmol/L',    '2.5-7.1',      '3094-0'),
    ('CREAT',   'Creatinine',                   'biochemistry','Serum',        'SST', 2500, 2,    'µmol/L',    '62-115',       '2160-0'),
    ('NA',      'Sodium',                       'biochemistry','Serum',        'SST', 2000, 1,    'mmol/L',    '136-145',      '2951-2'),
    ('K',       'Potassium',                    'biochemistry','Serum',        'SST', 2000, 1,    'mmol/L',    '3.5-5.1',      '2823-3'),
    ('CA',      'Calcium',                      'biochemistry','Serum',        'SST', 2500, 2,    'mmol/L',    '2.15-2.55',    '17861-6'),
    ('ALT',     'ALT (SGPT)',                   'biochemistry','Serum',        'SST', 2500, 2,    'U/L',       '<56',          '1742-6'),
    ('AST',     'AST (SGOT)',                   'biochemistry','Serum',        'SST', 2500, 2,    'U/L',       '<40',          '1920-8'),
    ('GGT',     'GGT',                          'biochemistry','Serum',        'SST', 2500, 2,    'U/L',       'M<73 F<43',    '2324-6'),
    ('ALP',     'Alkaline Phosphatase',         'biochemistry','Serum',        'SST', 2500, 2,    'U/L',       '44-147',       '6768-6'),
    ('TBILI',   'Total Bilirubin',              'biochemistry','Serum',        'SST', 2500, 2,    'µmol/L',    '<20.5',        '1975-2'),
    ('ALB',     'Albumin',                      'biochemistry','Serum',        'SST', 2500, 2,    'g/L',       '35-52',        '1751-7'),
    ('CHOL',    'Total Cholesterol',            'biochemistry','Serum',        'SST', 2500, 2,    'mmol/L',    '<5.2',         '2093-3'),
    ('LDL',     'LDL Cholesterol',              'biochemistry','Serum',        'SST', 3000, 2,    'mmol/L',    '<3.4',         '13457-7'),
    ('HDL',     'HDL Cholesterol',              'biochemistry','Serum',        'SST', 2500, 2,    'mmol/L',    '>1.0',         '2085-9'),
    ('TG',      'Triglycerides',               'biochemistry','Serum',        'SST', 2500, 2,    'mmol/L',    '<1.7',         '3043-7'),
    ('CRP',     'C-Reactive Protein',           'biochemistry','Serum',        'SST', 3000, 2,    'mg/L',      '<10',          '1988-5'),
    ('FERRITIN','Ferritin',                     'biochemistry','Serum',        'SST', 5000, 4,    'µg/L',      'M:30-400',     '2276-4'),
    ('VB12',    'Vitamin B12',                  'biochemistry','Serum',        'SST', 8000, 24,   'pmol/L',    '148-738',      '2132-9'),
    ('VD',      'Vitamin D (25-OH)',             'biochemistry','Serum',        'SST', 10000,24,   'nmol/L',    '>50',          '1989-3'),
    ('TSH',     'TSH',                          'biochemistry','Serum',        'SST', 5000, 4,    'mIU/L',     '0.27-4.2',     '3016-4'),
    ('FT4',     'Free T4',                      'biochemistry','Serum',        'SST', 5000, 4,    'pmol/L',    '12-22',        '3024-8'),
    ('FT3',     'Free T3',                      'biochemistry','Serum',        'SST', 5000, 4,    'pmol/L',    '3.1-6.8',      '3051-0'),
    ('TROP_I',  'Troponin I',                   'biochemistry','Serum',        'SST', 15000,2,    'ng/mL',     '<0.04',        '10839-9'),
    ('BNP',     'BNP',                          'biochemistry','Serum',        'SST', 15000,4,    'pg/mL',     '<100',         '30934-4'),
    ('PSA',     'PSA',                          'biochemistry','Serum',        'SST', 8000, 8,    'ng/mL',     '<4.0',         '10334-1'),
    ('CEA',     'CEA',                          'biochemistry','Serum',        'SST', 8000, 8,    'ng/mL',     '<5.0',         '2857-1'),
    ('AFP',     'Alpha-Fetoprotein',            'biochemistry','Serum',        'SST', 8000, 8,    'ng/mL',     '<8.1',         '1834-1'),
    ('CA125',   'CA-125',                       'biochemistry','Serum',        'SST', 10000,8,    'U/mL',      '<35',          '10334-1'),
    ('INSULIN', 'Insulin',                      'biochemistry','Serum',        'SST', 8000, 8,    'mIU/L',     '2.6-24.9',     '20448-7'),
    ('CORTISOL','Cortisol AM',                  'biochemistry','Serum',        'SST', 8000, 8,    'nmol/L',    '138-690',      '2143-6'),
    ('FSH',     'FSH',                          'biochemistry','Serum',        'SST', 6000, 8,    'IU/L',      'Sex dep.',      '15067-2'),
    ('LH',      'LH',                           'biochemistry','Serum',        'SST', 6000, 8,    'IU/L',      'Sex dep.',      '10501-5'),
    ('PROLACT', 'Prolactin',                    'biochemistry','Serum',        'SST', 6000, 8,    'mIU/L',     'M:86-324',     '2842-3'),
    ('TESTOS',  'Testosterone',                 'biochemistry','Serum',        'SST', 8000, 8,    'nmol/L',    'M:9.9-27.8',   '2986-1'),
    ('HCG',     'beta-hCG (quantitative)',      'biochemistry','Serum',        'SST', 5000, 4,    'mIU/mL',    'See report',   '21198-7'),
    ('LFT',     'Liver Function Tests Panel',   'biochemistry','Serum',        'SST', 12000,2,    'various',   'See report',   ''),
    ('RFT',     'Renal Function Tests Panel',   'biochemistry','Serum',        'SST', 8000, 2,    'various',   'See report',   ''),
    ('LIPID',   'Lipid Profile Panel',          'biochemistry','Serum',        'SST', 10000,2,    'various',   'See report',   ''),
    # URINALYSIS
    ('UA',      'Urinalysis (Dip+Microscopy)',  'urinalysis',  'Urine MSU',    'URI', 2500, 1,    'various',   'See report',   '24357-6'),
    ('ACR',     'Albumin:Creatinine Ratio',     'urinalysis',  'Urine MSU',    'URI', 3000, 2,    'mg/mmol',   '<3.0',         '9318-7'),
    # MICROBIOLOGY
    ('GE_FS',   'Malaria Thick+Thin Film',      'microbiology','EDTA Blood',   'HEM', 3000, 1,    'P./µL',     'No parasites', '32700-7'),
    ('MRDT',    'Malaria RDT (HRP2/pLDH)',      'microbiology','EDTA Blood',   'HEM', 2500, 0.5,  '',          'Negative',     '40454-0'),
    ('STOOLMICRO','Stool Microscopy O&P',       'microbiology','Stool',        'STL', 3000, 4,    '',          'No ova/cysts', '24956-5'),
    ('UCSENS',  'Urine Culture+Sensitivity',    'microbiology','Urine MSU',    'URC', 8000, 48,   'CFU/mL',    '<10^5',        '630-4'),
    ('BLOODCX', 'Blood Culture (Aerobic+Anaer)','microbiology','Blood Culture','BLC', 10000,120,   '',          'No growth',    '600-7'),
    ('STOOLCX', 'Stool Culture+Sensitivity',    'microbiology','Stool',        'STL', 7000, 72,   '',          'See report',   '625-4'),
    ('SPUTUMCX','Sputum Culture+Sensitivity',   'microbiology','Sputum',       'SPU', 7000, 72,   '',          'See report',   '620-4'),
    ('WOUNDCX', 'Wound Swab Culture+Sensitivity','microbiology','Swab',        'SWB', 7000, 72,   '',          'See report',   '612-2'),
    ('AFBZN',   'AFB Smear ZN Stain',           'microbiology','Sputum',       'SPU', 3000, 24,   '',          'No AFB',       '11545-1'),
    ('GENEXPT', 'GeneXpert MTB/RIF Ultra',      'microbiology','Sputum',       'SPU', 25000,3,    '',          'Not Detected', '89365-1'),
    ('CRAG',    'CrAg Lateral Flow Assay',      'microbiology','Serum/CSF',    'SST', 5000, 2,    '',          'Negative',     ''),
    # SEROLOGY
    ('HIVAB',   'HIV Ag/Ab (4th Gen)',           'serology',    'Serum',        'SST', 4000, 1,    '',          'Non-Reactive', '75622-1'),
    ('HBSAG',   'HBsAg',                        'serology',    'Serum',        'SST', 4000, 4,    '',          'Non-Reactive', '5196-1'),
    ('ANTIHBS', 'Anti-HBs',                     'serology',    'Serum',        'SST', 4000, 4,    'IU/L',      '>10=immune',   '16935-9'),
    ('ANTIHCV', 'Anti-HCV',                     'serology',    'Serum',        'SST', 4000, 4,    '',          'Non-Reactive', '13955-0'),
    ('VDRL',    'VDRL (Syphilis)',               'serology',    'Serum',        'SST', 3000, 4,    '',          'Non-Reactive', '31147-2'),
    ('TPHA',    'TPHA (Syphilis conf.)',          'serology',    'Serum',        'SST', 5000, 4,    '',          'Non-Reactive', ''),
    ('RF',      'Rheumatoid Factor',             'serology',    'Serum',        'SST', 3000, 4,    'IU/mL',     '<20',          '4537-7'),
    ('ANA',     'Antinuclear Antibodies',        'serology',    'Serum',        'SST', 8000, 24,   'titre',      '<1:40',        '5048-4'),
    # MOLECULAR
    ('VL_HIV',  'HIV Viral Load (RT-PCR)',       'molecular',   'EDTA Blood',   'HEM', 35000,24,   'copies/mL', '<40 UDL',     '25836-8'),
    ('CD4',     'CD4 T-Cell Count',             'molecular',   'EDTA Blood',   'HEM', 10000,8,    'cells/µL',  '>500',         '24467-3'),
    ('COVIDPCR','SARS-CoV-2 RT-PCR',            'molecular',   'NPS Swab',     'NPH', 15000,6,    '',          'Not Detected', '94534-5'),
    ('TBPCR',   'TB PCR (IS6110)',               'molecular',   'Sputum',       'SPU', 20000,8,    '',          'Not Detected', '71774-4'),
    # BLOOD BANK
    ('ABO',     'Blood Group ABO+Rh',           'blood_bank',  'EDTA Blood',   'HEM', 3000, 1,    '',          'See report',   '34530-6'),
    ('XMATCH',  'Crossmatch (Compatibility)',    'blood_bank',  'EDTA+Serum',   'HEM', 5000, 2,    '',          'Compatible',   '44180-7'),
    ('DAT',     'Direct Antiglobulin Test',      'blood_bank',  'EDTA Blood',   'HEM', 5000, 2,    '',          'Negative',     '14618-3'),
]

added = 0
for code, name, dept_key, spec, tube, price, tat, unit, ref, loinc in TESTS:
    if not db.query(TestCatalog).filter(TestCatalog.code==code).first():
        d_id = dept_map.get(dept_key, dept_map.get('biochemistry'))
        tc = TestCatalog(code=code, name=name, department_id=d_id,
                         specimen_type=spec, tube_type=tube,
                         price=float(price), tat_hours=float(tat),
                         unit=unit, reference_range=ref,
                         loinc_code=loinc, is_active=True)
        db.add(tc)
        added += 1
db.commit()
print(f'Test catalog: {added} tests added, {db.query(TestCatalog).count()} total')

# Specimen types
seeded = seed_specimen_types(db)
print(f'Specimen types: {seeded} seeded')

# IQC demo data (30 days per analyte for Levey-Jennings)
if db.query(IQCResult).count() == 0:
    random.seed(42)
    iqc_count = 0
    for dept, code, name, level, mean, sd, unit in [
        ('biochemistry','GLUCOSE','Glucose','L1',3.2,0.15,'mmol/L'),
        ('biochemistry','GLUCOSE','Glucose','L2',5.5,0.20,'mmol/L'),
        ('biochemistry','CREAT','Creatinine','L1',50.0,2.5,'µmol/L'),
        ('biochemistry','CREAT','Creatinine','L2',120.0,5.0,'µmol/L'),
        ('hematology','HGB','Haemoglobin','L1',80.0,2.0,'g/L'),
        ('hematology','HGB','Haemoglobin','L2',130.0,3.0,'g/L'),
    ]:
        drift = 0.0
        for d_back in range(30,-1,-1):
            run_dt = date.today() - timedelta(days=d_back)
            if d_back < 10: drift += sd * 0.07
            value = mean + drift + random.gauss(0, sd*0.8)
            z = (value-mean)/sd
            abs_z = abs(z)
            status = 'REJECT' if abs_z>3 else 'WARN' if abs_z>2 else 'PASS'
            rule = '1_3s' if abs_z>3 else '1_2s' if abs_z>2 else 'PASS'
            r = IQCResult(department=dept, analyte_code=code, analyte_name=name,
                          control_level=level, target_mean=mean, sd=sd,
                          result_value=round(value,3), unit=unit,
                          z_score=round(z,3), westgard_rule=rule, status=status,
                          analyzer_name='Demo Analyzer', operator_name='Demo Op',
                          run_date=run_dt, lot_number='LOT-DEMO-001')
            db.add(r); iqc_count += 1
    db.commit()
    print(f'IQC demo data: {iqc_count} runs')

# Final verification
print()
print('=' * 55)
print('SEED COMPLETE')
print(f'  Users:    {db.query(User).count()}')
print(f'  Tests:    {db.query(TestCatalog).count()}')
print(f'  IQC:      {db.query(IQCResult).count()} runs')
print()
print('Login credentials:')
print('  admin / admin123        → super_admin')
print('  labmanager / nexus2026  → lab_manager')
print('  scientist / nexus2026   → scientist')
print('  receptionist / nexus2026→ receptionist')
print('  pathologist / nexus2026 → pathologist')
print('=' * 55)

admin = db.query(User).filter(User.username=='admin').first()
if admin:
    ok = verify_password('admin123', admin.hashed_password)
    print(f'Admin login test: {"PASS admin/admin123" if ok else "FAIL"}')

db.close()
