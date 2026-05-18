"""JORINOVA NEXUS ALIS-X — Medical Knowledge Base"""
from __future__ import annotations

MEDICAL_ABBREVIATIONS = {
    # Lab / Specimen
    'GE':'Goutte Épaisse (Thick Blood Smear — malaria)',
    'FS':'Frottis Sanguin (Thin Blood Smear — malaria)',
    'SID':'Specimen ID (unique tube identifier)',
    'CID':'Culture ID (microbiology plate identifier)',
    'QNS':'Quantity Not Sufficient (rejection reason)',
    'TAT':'Turnaround Time',
    'LIS':'Laboratory Information System',
    'IQC':'Internal Quality Control',
    'EQA':'External Quality Assurance',
    'SOP':'Standard Operating Procedure',
    'NCR':'Non-Conformity Report',
    'CAPA':'Corrective and Preventive Action',
    'AFB':'Acid-Fast Bacilli',
    'ZN':'Ziehl-Neelsen (AFB stain)',
    'PCR':'Polymerase Chain Reaction',
    'NAAT':'Nucleic Acid Amplification Test',
    'NGS':'Next Generation Sequencing',
    'MIC':'Minimum Inhibitory Concentration',
    'AST':'Antibiotic Susceptibility Testing',
    'CLSI':'Clinical and Laboratory Standards Institute (USA)',
    'EUCAST':'European Committee on Antimicrobial Susceptibility Testing',
    'ISBT':'International Society of Blood Transfusion',
    # Diseases / Infections
    'TB':'Tuberculosis',
    'MTB':'Mycobacterium tuberculosis',
    'MDR':'Multi-Drug Resistant (TB)',
    'XDR':'Extensively Drug Resistant (TB)',
    'RIF':'Rifampicin',
    'HIV':'Human Immunodeficiency Virus',
    'AIDS':'Acquired Immunodeficiency Syndrome',
    'ARV':'Antiretroviral',
    'VL':'Viral Load (HIV RT-PCR)',
    'PMTCT':'Prevention of Mother-to-Child Transmission',
    'PTME':'Prévention de la Transmission Mère-Enfant',
    'HBV':'Hepatitis B Virus',
    'HCV':'Hepatitis C Virus',
    'HAV':'Hepatitis A Virus',
    'HEV':'Hepatitis E Virus',
    'HPV':'Human Papillomavirus',
    'CMV':'Cytomegalovirus',
    'EBV':'Epstein-Barr Virus',
    'VZV':'Varicella-Zoster Virus (chickenpox/shingles)',
    'HSV':'Herpes Simplex Virus',
    'RSV':'Respiratory Syncytial Virus',
    'SARS':'Severe Acute Respiratory Syndrome',
    'COVID':'COVID-19 (SARS-CoV-2)',
    'MRSA':'Methicillin-Resistant Staphylococcus aureus',
    'VRE':'Vancomycin-Resistant Enterococcus',
    'ESBL':'Extended Spectrum Beta-Lactamase',
    'CPE':'Carbapenemase-Producing Enterobacteriaceae',
    'GAS':'Group A Streptococcus (S.pyogenes)',
    'GBS':'Group B Streptococcus (S.agalactiae)',
    'STI':'Sexually Transmitted Infection',
    'GC':'Gonorrhoea (Neisseria gonorrhoeae)',
    'CT':'Chlamydia trachomatis',
    'GUD':'Genital Ulcer Disease',
    # Haematology
    'CBC':'Complete Blood Count',
    'FBC':'Full Blood Count',
    'WBC':'White Blood Cells (Leukocytes)',
    'RBC':'Red Blood Cells (Erythrocytes)',
    'HGB':'Haemoglobin',
    'HCT':'Haematocrit (Packed Cell Volume)',
    'MCV':'Mean Corpuscular Volume',
    'MCH':'Mean Corpuscular Haemoglobin',
    'MCHC':'Mean Corpuscular Haemoglobin Concentration',
    'RDW':'Red Cell Distribution Width',
    'PLT':'Platelets (Thrombocytes)',
    'MPV':'Mean Platelet Volume',
    'ESR':'Erythrocyte Sedimentation Rate',
    'PBS':'Peripheral Blood Smear',
    'IDA':'Iron Deficiency Anaemia',
    'B12':'Vitamin B12 (Cobalamin)',
    'DIC':'Disseminated Intravascular Coagulation',
    'TTP':'Thrombotic Thrombocytopenic Purpura',
    'HUS':'Haemolytic Uraemic Syndrome',
    # Coagulation
    'PT':'Prothrombin Time',
    'INR':'International Normalized Ratio',
    'APTT':'Activated Partial Thromboplastin Time',
    'TT':'Thrombin Time',
    'DDIMER':'D-Dimer (fibrin degradation product)',
    'FDP':'Fibrin Degradation Products',
    'vWF':'von Willebrand Factor',
    # Biochemistry
    'LFT':'Liver Function Tests',
    'RFT':'Renal Function Tests',
    'TFT':'Thyroid Function Tests',
    'FBS':'Fasting Blood Sugar',
    'RBS':'Random Blood Sugar',
    'OGTT':'Oral Glucose Tolerance Test',
    'HbA1c':'Glycated Haemoglobin (diabetes monitoring)',
    'ALT':'Alanine Aminotransferase (SGPT) — liver',
    'AST':'Aspartate Aminotransferase (SGOT) — liver/heart',
    'GGT':'Gamma-Glutamyl Transferase — liver/biliary',
    'ALP':'Alkaline Phosphatase',
    'LDH':'Lactate Dehydrogenase',
    'CK':'Creatine Kinase',
    'CKMB':'CK Myocardial Band — cardiac marker',
    'BNP':'Brain Natriuretic Peptide — heart failure',
    'NTBNP':'NT-proBNP — heart failure',
    'TROP':'Troponin (I or T) — myocardial infarction',
    'CRP':'C-Reactive Protein — inflammation',
    'PCT':'Procalcitonin — bacterial sepsis',
    'ABG':'Arterial Blood Gas',
    'TIBC':'Total Iron Binding Capacity',
    'PSA':'Prostate Specific Antigen',
    'CEA':'Carcinoembryonic Antigen',
    'AFP':'Alpha-Fetoprotein',
    'CA125':'Cancer Antigen 125 (ovarian)',
    'CA199':'Cancer Antigen 19-9 (pancreatic)',
    'CA153':'Cancer Antigen 15-3 (breast)',
    'HCG':'Human Chorionic Gonadotropin',
    # Hormones
    'TSH':'Thyroid Stimulating Hormone',
    'FT4':'Free Thyroxine',
    'FT3':'Free Triiodothyronine',
    'PTH':'Parathyroid Hormone',
    'FSH':'Follicle Stimulating Hormone',
    'LH':'Luteinizing Hormone',
    'PRL':'Prolactin',
    'DHEAS':'Dehydroepiandrosterone Sulphate',
    'ALDO':'Aldosterone',
    'CORT':'Cortisol',
    # Serology
    'HBsAg':'Hepatitis B surface Antigen',
    'AntiHBs':'Anti-Hepatitis B surface Antibody',
    'HBeAg':'Hepatitis B e Antigen',
    'AntiHCV':'Anti-Hepatitis C Antibody',
    'VDRL':'Venereal Disease Research Lab (syphilis screening)',
    'RPR':'Rapid Plasma Reagin (syphilis)',
    'TPHA':'Treponema pallidum Haemagglutination (syphilis conf)',
    'RF':'Rheumatoid Factor',
    'ANA':'Antinuclear Antibody',
    'ANCA':'Antineutrophil Cytoplasmic Antibody',
    'CrAg':'Cryptococcal Antigen',
    'CD4':'CD4 T-lymphocyte count',
    # Wards / Departments
    'OPD':'Outpatient Department',
    'IPD':'Inpatient Department',
    'ICU':'Intensive Care Unit',
    'SICU':'Surgical ICU',
    'NICU':'Neonatal ICU',
    'PICU':'Paediatric ICU',
    'HDU':'High Dependency Unit',
    'OT':'Operating Theatre',
    'A&E':'Accident & Emergency',
    'ER':'Emergency Room',
    'ANC':'Antenatal Care',
    'PNC':'Postnatal Care',
    'MCH':'Maternal and Child Health',
    'CPN':'Consultation Prénatale',
    'GYN':'Gynaecology',
    'PED':'Paediatrics',
    'ONCO':'Oncology',
    'CARD':'Cardiology',
    'NEURO':'Neurology',
    'NEPH':'Nephrology',
    'PULM':'Pulmonology / Chest',
    'GASTRO':'Gastroenterology',
    'RHEUM':'Rheumatology',
    'ENDO':'Endocrinology',
    'ORTHO':'Orthopaedics',
    'BURNS':'Burns Unit',
    'REHAB':'Rehabilitation',
    'DERM':'Dermatology',
    'OPHTH':'Ophthalmology',
    'ENT':'Ear Nose Throat',
    'PSYCH':'Psychiatry',
    'ID':'Infectious Disease',
    'RENAL':'Renal / Dialysis Unit',
    'VL':'Viral Load',
}

TUBE_TYPES = {
    'EDTA_LAVENDER': {
        'cap_color':'lavender/purple','additive':'K2 or K3 EDTA',
        'mechanism':'chelates calcium preventing coagulation',
        'tests':['CBC','HbA1c','Blood Group & Screen','CD4','Viral Load HIV','Reticulocytes','ESR','Hb Electrophoresis','Blood Film','G6PD','Malaria GE/FS','Coomb Direct'],
        'inversions':8,'volume_ml':3.0,
        'notes':'Mix gently 8 times. Do NOT use for coagulation or calcium.',
        'rejection':['clotted','insufficient volume','hemolysis','wrong tube for PT/INR'],
    },
    'CITRATE_BLUE': {
        'cap_color':'light blue','additive':'3.2% Sodium Citrate',
        'mechanism':'chelates calcium reversibly (anticoagulant for coagulation)',
        'tests':['PT','INR','APTT','Fibrinogen','D-Dimer','Factor assays','vWF'],
        'inversions':3,'volume_ml':2.7,'ratio':'9:1 blood:citrate',
        'notes':'CRITICAL: Fill to the line exactly. Underfilled = reject. Mix 3-4 times immediately.',
        'rejection':['underfilled (ratio error)','clotted','hemolysis','delayed processing >4h'],
    },
    'SST_GOLD': {
        'cap_color':'gold or tiger-top','additive':'clot activator + serum separator gel',
        'mechanism':'silica particles activate clotting; gel separates serum after centrifuge',
        'tests':['All biochemistry (glucose/urea/creatinine/electrolytes/LFTs/lipids)','All hormones (TSH/FT4/FSH/LH/Prolactin/Cortisol)','All tumor markers','Serology (HIV/HBsAg/HCV/VDRL)','Vitamin D/B12/Folate','CRP','Iron studies'],
        'inversions':5,'volume_ml':5.0,
        'notes':'Wait 30min after collection before centrifuging (clot must form). Do NOT shake.',
        'rejection':['insufficient clot time','hemolysis','lipemia (interfering)','icterus severe','wrong tube for CBC or coagulation'],
    },
    'PLAIN_RED': {
        'cap_color':'red','additive':'clot activator only (no gel)',
        'mechanism':'glass/silica activates clotting',
        'tests':['Blood banking/crossmatch','Some serology','Drug levels','Trace elements (if royal blue unavailable)'],
        'inversions':5,'volume_ml':5.0,
        'notes':'Allow full clot (30-60 min). Centrifuge. Serum only (no gel separator).',
    },
    'HEPARIN_GREEN': {
        'cap_color':'green','additive':'Lithium Heparin',
        'mechanism':'inhibits thrombin and Xa — anticoagulant for plasma',
        'tests':['Arterial Blood Gas (special heparinised syringe)','Plasma biochemistry (rapid results needed)','Chromosomes/cytogenetics','Plasma ammonia'],
        'inversions':8,'volume_ml':4.0,
        'notes':'Cannot use for lithium levels (additive interference). Plasma is yellow-green.',
    },
    'FLUORIDE_GREY': {
        'cap_color':'grey','additive':'Sodium Fluoride + Potassium Oxalate',
        'mechanism':'fluoride inhibits glycolysis, preserving glucose; oxalate chelates calcium',
        'tests':['Fasting glucose','Random glucose','Lactate','Alcohol level'],
        'inversions':8,'volume_ml':2.0,
        'notes':'Inhibits glycolysis — prevents glucose from falling in transit. Plasma is used.',
    },
    'ROYAL_BLUE': {
        'cap_color':'royal blue','additive':'EDTA or plain (trace element-free)',
        'mechanism':'EDTA or no additive, ultra-clean (no metal contamination)',
        'tests':['Zinc','Copper','Lead','Selenium','Manganese','Mercury','ESR Westergren'],
        'inversions':8,'volume_ml':6.0,
        'notes':'Trace element-free tube — prevents contamination from standard tube metals.',
    },
    'ACD_YELLOW': {
        'cap_color':'yellow','additive':'Acid Citrate Dextrose (ACD-A or ACD-B)',
        'mechanism':'low pH + dextrose preserves RBCs and platelets',
        'tests':['Blood banking (HLA typing)','Paternity testing','DNA analysis','Stem cell processing'],
        'inversions':8,'volume_ml':8.5,
    },
    'BLOOD_CULTURE_AEROBIC': {
        'cap_color':'orange cap / blue label','additive':'growth media + resins',
        'mechanism':'nutrient broth supports aerobic organism growth',
        'tests':['Blood culture (aerobic organisms: most bacteria, yeast)'],
        'volume_ml':10.0,
        'notes':'Inoculate BEFORE other tubes. Clean top with alcohol swab. Volume critical (8-10mL per bottle).',
        'rejection':['<5mL blood inoculated','antibiotic already started (note)','contaminated during collection'],
    },
    'BLOOD_CULTURE_ANAEROBIC': {
        'cap_color':'purple cap / orange label','additive':'growth media (pre-reduced)',
        'mechanism':'oxygen-free environment for anaerobic organisms',
        'tests':['Blood culture (anaerobes: Bacteroides, Clostridium, Peptostreptococcus)'],
        'volume_ml':10.0,
    },
}

TEST_TO_TUBE = {
    # Haematology
    'CBC':'EDTA_LAVENDER','FBC':'EDTA_LAVENDER','HGB':'EDTA_LAVENDER',
    'HbA1c':'EDTA_LAVENDER','RETICS':'EDTA_LAVENDER','ESR':'ROYAL_BLUE',
    'BLOOD_GROUP':'EDTA_LAVENDER','CROSSMATCH':'EDTA_LAVENDER + PLAIN_RED',
    'CD4':'EDTA_LAVENDER','VL_HIV':'EDTA_LAVENDER',
    'MALARIA_GE_FS':'EDTA_LAVENDER','MALARIA_RDT':'EDTA_LAVENDER',
    'HB_ELECTROPHORESIS':'EDTA_LAVENDER','G6PD':'EDTA_LAVENDER',
    'BLOOD_FILM':'EDTA_LAVENDER','DAT':'EDTA_LAVENDER',
    # Coagulation
    'PT':'CITRATE_BLUE','INR':'CITRATE_BLUE','APTT':'CITRATE_BLUE',
    'FIBRINOGEN':'CITRATE_BLUE','D_DIMER':'CITRATE_BLUE','FACTOR_ASSAYS':'CITRATE_BLUE',
    # Biochemistry (SST gold)
    'GLUCOSE_F':'FLUORIDE_GREY','GLUCOSE_R':'FLUORIDE_GREY','LACTATE':'FLUORIDE_GREY',
    'UREA':'SST_GOLD','CREATININE':'SST_GOLD','EGFR':'SST_GOLD',
    'SODIUM':'SST_GOLD','POTASSIUM':'SST_GOLD','CHLORIDE':'SST_GOLD',
    'BICARBONATE':'SST_GOLD','CALCIUM':'SST_GOLD','MAGNESIUM':'SST_GOLD','PHOSPHATE':'SST_GOLD',
    'ALT':'SST_GOLD','AST':'SST_GOLD','GGT':'SST_GOLD','ALP':'SST_GOLD',
    'BILIRUBIN_T':'SST_GOLD','BILIRUBIN_D':'SST_GOLD',
    'ALBUMIN':'SST_GOLD','TOTAL_PROTEIN':'SST_GOLD',
    'CHOLESTEROL':'SST_GOLD','LDL':'SST_GOLD','HDL':'SST_GOLD','TG':'SST_GOLD',
    'TROPONIN':'SST_GOLD','TROP_I':'SST_GOLD','TROP_T':'SST_GOLD',
    'BNP':'SST_GOLD','NT_BNP':'SST_GOLD','CK_MB':'SST_GOLD','LDH':'SST_GOLD',
    'TSH':'SST_GOLD','FT4':'SST_GOLD','FT3':'SST_GOLD','PTH':'SST_GOLD',
    'FSH':'SST_GOLD','LH':'SST_GOLD','PROLACTIN':'SST_GOLD',
    'TESTOSTERONE':'SST_GOLD','OESTRADIOL':'SST_GOLD','PROGESTERONE':'SST_GOLD',
    'HCG':'SST_GOLD','CORTISOL':'SST_GOLD','INSULIN':'SST_GOLD',
    'PSA':'SST_GOLD','CEA':'SST_GOLD','AFP':'SST_GOLD','CA125':'SST_GOLD','CA199':'SST_GOLD',
    'CRP':'SST_GOLD','FERRITIN':'SST_GOLD','IRON':'SST_GOLD','TIBC':'SST_GOLD',
    'VIT_B12':'SST_GOLD','FOLATE':'SST_GOLD','VIT_D':'SST_GOLD','VIT_A':'SST_GOLD',
    'HIV_AB':'SST_GOLD','HBSAG':'SST_GOLD','ANTI_HCV':'SST_GOLD','VDRL':'SST_GOLD',
    'TPHA':'SST_GOLD','RF':'SST_GOLD','ANA':'SST_GOLD','CRAG':'SST_GOLD',
    # Blood culture
    'BLOOD_CULTURE':'BLOOD_CULTURE_AEROBIC + BLOOD_CULTURE_ANAEROBIC',
    # Special
    'TRACE_ELEMENTS':'ROYAL_BLUE','LEAD':'ROYAL_BLUE','ZINC':'ROYAL_BLUE',
    'AMMONIA':'HEPARIN_GREEN','ABG':'HEPARIN_GREEN (arterial)',
    'HLA_TYPING':'ACD_YELLOW','DNA_ANALYSIS':'ACD_YELLOW',
}

REJECTION_REASONS = {
    'HEMOLYSIS_MILD':   {'clsi':'EP23','severity':'warn','affects':['K+','LDH','AST'],'action':'Note on report; may affect K+ by 0.5 mmol/L. Repeat if clinical concern.'},
    'HEMOLYSIS_MOD':    {'clsi':'EP23','severity':'reject','affects':['K+','LDH','AST','Troponin','Bilirubin','Iron'],'action':'Reject. Recollect. Inform phlebotomist. Document in rejection book.'},
    'HEMOLYSIS_SEVERE': {'clsi':'EP23','severity':'reject','affects':['all above + potassium falsely very high'],'action':'Reject immediately. New venepuncture required.'},
    'CLOTTED_EDTA':     {'clsi':'EP23','severity':'reject','affects':['CBC — platelet clumps, WBC inaccurate','Coagulation invalid'],'action':'Reject. Recollect with immediate mixing (8 inversions).'},
    'CLOTTED_CITRATE':  {'clsi':'EP23','severity':'reject','affects':['PT','APTT','all coagulation'],'action':'Reject. Recollect citrate and mix immediately 3-4 times.'},
    'QNS_CITRATE':      {'clsi':'EP23','severity':'reject','affects':['All coagulation — ratio error dilutes citrate'],'action':'Reject if <90% full. Critical: 9:1 ratio must be maintained.'},
    'QNS_GENERAL':      {'clsi':'EP23','severity':'reject','affects':['All ordered tests'],'action':'Reject. Recollect sufficient volume. Prioritise critical tests.'},
    'WRONG_TUBE':       {'clsi':'EP23','severity':'reject','affects':['Depends on tube — EDTA in gold affects Na+/K+'],'action':'Reject. Educate phlebotomist. Note additive carry-over risk.'},
    'UNLABELLED':       {'clsi':'EP23','severity':'reject','affects':['Patient safety — cannot verify identity'],'action':'CRITICAL REJECT. Cannot process. Return to ward for recollection with proper ID.'},
    'MISLABELLED':      {'clsi':'EP23','severity':'reject','affects':['Patient safety — wrong patient result'],'action':'CRITICAL REJECT. Do NOT process. Investigate immediately. ISO 15189 §6.4.'},
    'EXPIRED_TUBE':     {'clsi':'EP23','severity':'reject','affects':['Additive degraded — results unreliable'],'action':'Reject. Remove expired stock. Check lot dates. Recollect.'},
    'ICTERUS_MODERATE': {'clsi':'EP23','severity':'warn','affects':['Photometric assays — bilirubin >200 µmol/L interferes'],'action':'Note interference. Verify dilution method available.'},
    'LIPEMIA':          {'clsi':'EP23','severity':'warn','affects':['Photometric assays (cholesterol/triglycerides/protein)'],'action':'Ultracentrifuge or dilution. Note on report. Fasting sample preferred.'},
    'TEMP_EXCEEDED':    {'clsi':'EP23','severity':'reject','affects':['Protein denaturation, bacterial growth in blood culture'],'action':'Reject. Note storage/transport failure. Recollect.'},
    'TIME_EXCEEDED':    {'clsi':'EP23','severity':'reject','affects':['Glucose falls 0.6 mmol/L/h at RT; potassium rises; CBCs change'],'action':'Check analyte-specific stability. Reject unstable analytes. Document TAT failure.'},
    'INADEQUATE_SPUTUM':{'clsi':'EP23','severity':'reject','affects':['Sputum culture — saliva only, no PMN'],'action':'Reject if <25 PMN/lpf. Collect deep cough specimen. Physiotherapy if needed.'},
    'OLD_CSF':          {'clsi':'EP23','severity':'reject','affects':['Cell count (cells lyse rapidly)','Culture (organisms die)'],'action':'STAT processing mandatory for CSF. Never delay > 30 min.'},
    'LEAKED_CONTAINER': {'clsi':'EP23','severity':'reject','affects':['Biohazard + sample loss'],'action':'Reject. Biohazard disposal. Recollect. Report to safety officer.'},
}

CULTURE_MEDIA = {
    'BLOOD_AGAR': {
        'type':'general (enriched)','base':'Trypticase Soy','supplement':'5% sheep blood',
        'use':'All specimens — general isolation','temp':'35°C','atm':'aerobic/5% CO2',
        'colonies':{'S.aureus':'golden-yellow, beta-haemolysis','S.pneumoniae':'alpha-haemolysis, draughtsman','GAS':'beta-haemolysis, small','E.coli':'large grey, no haemolysis'},
        'selectivity':'non-selective (grows all organisms)',
    },
    'CHOCOLATE_AGAR': {
        'type':'enriched (heated blood)','supplement':'heated (lysed) blood',
        'use':'Haemophilus influenzae (needs X+V factors), Neisseria gonorrhoeae/meningitidis',
        'temp':'35°C','atm':'5-10% CO2',
        'notes':'Heated blood releases hemin (X factor) and NAD (V factor)',
    },
    'MACCONKEY': {
        'type':'selective-differential','inhibitor':'bile salts + crystal violet (Gram+)',
        'use':'Gram-negative rod isolation','indicator':'neutral red (pH)',
        'colonies':{'E.coli':'PINK/RED (lactose fermenter)','Klebsiella':'PINK/mucoid','Salmonella':'COLORLESS (non-fermenter)','Shigella':'COLORLESS','Pseudomonas':'COLORLESS, flat'},
        'selectivity':'inhibits Gram-positive organisms',
    },
    'CLED': {
        'type':'selective-differential (cystine-lactose-electrolyte-deficient)',
        'use':'Urine culture — counts CFU/mL, differentiates organisms',
        'colonies':{'E.coli':'YELLOW (lactose+)','Klebsiella':'YELLOW mucoid','Proteus':'translucent blue (no swarming on CLED!)','Enterococcus':'YELLOW small'},
        'notes':'Prevents Proteus swarming unlike BAP',
    },
    'MANNITOL_SALT': {
        'type':'selective-differential','inhibitor':'7.5% NaCl (halophilic)',
        'use':'Staphylococcus isolation and differentiation',
        'colonies':{'S.aureus':'YELLOW (mannitol fermentation)','S.epidermidis':'PINK/RED (non-fermenter)'},
    },
    'SABOURAUD_DEXTROSE': {
        'type':'selective (fungal)','pH':'5.6 (acidic — inhibits bacteria)',
        'use':'Fungi: Candida, Aspergillus, Dermatophytes',
        'temp':'25-30°C (room temp)','incubation':'7-21 days',
        'colonies':{'Candida albicans':'white/cream pasty','Aspergillus':'grey-green with powdery top','Dermatophytes':'fluffy/cottony'},
    },
    'LOWENSTEIN_JENSEN': {
        'type':'selective (mycobacterial)','base':'egg + glycerol + malachite green',
        'use':'Mycobacterium tuberculosis culture (solid)','temp':'37°C','incubation':'6-8 weeks',
        'colonies':{'MTB':'rough, crumbly, cream/buff coloured (after 3-8 weeks)','NTM':'faster growing, pigmented'},
    },
    'MGIT': {
        'type':'liquid broth (BACTEC MGIT 960)','use':'Rapid TB culture + DST',
        'time':'7-42 days (vs 6-8 weeks on LJ)','fluorescent':'O2-sensitive fluorochrome',
        'notes':'WHO recommended first-line TB culture method. Auto-signals positivity.',
    },
    'TCBS': {
        'type':'selective-differential (thiosulfate-citrate-bile-sucrose)',
        'use':'Vibrio species','inhibitor':'bile salts inhibit most organisms',
        'colonies':{'V.cholerae':'YELLOW (sucrose+)','V.parahaemolyticus':'BLUE-GREEN (sucrose-)'},
    },
    'XLD': {
        'type':'selective-differential (xylose-lysine-deoxycholate)',
        'use':'Salmonella/Shigella from stool',
        'colonies':{'Salmonella':'PINK/RED with BLACK centre (H2S)','Shigella':'PINK/RED, no black','E.coli':'YELLOW (xylose+)'},
    },
    'MUELLER_HINTON': {
        'type':'non-selective (AST standard)','use':'Antibiotic susceptibility disk diffusion (Kirby-Bauer)',
        'temp':'35°C','atm':'aerobic','notes':'WHO/CLSI standard for disk diffusion. Standardised depth 4mm.',
    },
    'THAYER_MARTIN': {
        'type':'selective (modified chocolate agar)','inhibitors':'VCN (vancomycin, colistin, nystatin)',
        'use':'Neisseria gonorrhoeae isolation from genital specimens','temp':'35°C','atm':'5% CO2',
    },
    'CAMPY_AGAR': {
        'type':'selective (Campylobacter)','temp':'42°C (selective!)','atm':'microaerophilic (5% O2)',
        'use':'Campylobacter from stool','incubation':'48-72h',
        'colonies':{'Campylobacter':'grey/flat, spreading, oxidase+'},
    },
    'CHROMAGAR': {
        'type':'chromogenic (colour-producing)','use':'Candida species ID, MRSA screening, VRE',
        'colonies':{'C.albicans':'GREEN','C.tropicalis':'BLUE/METALLIC','C.krusei':'PINK FUZZY','MRSA':'MAUVE/PINK on MRSA chromagar'},
    },
}

STAINING_METHODS = {
    'GRAM': {
        'use':'Classify bacteria as Gram+ or Gram-, assess morphology',
        'steps':['Crystal violet (primary)','Gram iodine (mordant)','Acetone-alcohol decoloriser','Safranin (counterstain)'],
        'gram_pos':{'color':'PURPLE/VIOLET','examples':['Staphylococcus cocci clusters','Streptococcus cocci chains','Pneumococcus lancet diplococci','Bacillus/Clostridium rods']},
        'gram_neg':{'color':'PINK/RED','examples':['E.coli short rods','Klebsiella plump rods','Pseudomonas slim rods','Neisseria diplococci (kidney-bean)','H.influenzae coccobacilli']},
        'clinical':'First step in all culture positives. Guides empirical antibiotic choice within 1-2 hours.',
    },
    'ZN_AFB': {
        'use':'Detect acid-fast organisms (Mycobacterium, Nocardia, Cryptosporidium)',
        'steps':['Carbol fuchsin (hot)','Acid-alcohol decolorise','Methylene blue counterstain'],
        'positive':'BRIGHT RED rods on BLUE background',
        'grading':{'0':'No AFB seen (Neg)','1-9/100 fields':'Scanty (report number)','1+':'1-9 per field','2+':'10-99 per field','3+':'>99 per field'},
        'clinical':'Diagnosis of TB, leprosy, Nocardia infection. Sensitivity 50-80% in pulmonary TB.',
        'note':'Modified ZN (cold method) for Cryptosporidium, Cyclospora — PINK oocysts 4-6µm',
    },
    'GIEMSA': {
        'use':'Blood parasites (malaria, trypanosomes, Leishmania, Babesia), blood cell morphology',
        'fixative':'Methanol','stain':'Giemsa diluted in buffer pH 7.2',
        'results':{'malaria':'Ring forms, trophozoites, schizonts, gametocytes — species specific','Leishmania':'LD bodies (amastigotes) 2-4µm in macrophages','Trypanosoma':'trypomastigotes with undulating membrane','Babesia':'intraerythrocytic, often 4-cell maltese cross'},
        'clinical':'Gold standard for malaria speciation and parasitemia quantification.',
    },
    'FIELDS': {
        'use':'Rapid malaria detection in field/high-volume settings',
        'stains':'Field A (polychrome methylene blue) + Field B (eosin)',
        'time':'30-60 seconds',
        'results':'Same as Giemsa — rings/trophozoites/gametocytes in RBCs',
        'clinical':'Used in Rwanda for GE and FS. Faster than Giemsa for routine malaria.',
    },
    'INDIA_INK': {
        'use':'Visualise Cryptococcus capsule in CSF',
        'principle':'negative stain — black background, capsule appears as CLEAR HALO around yeast',
        'positive':'CLEAR/WHITE HALO around budding yeast (5-15µm) on BLACK background',
        'clinical':'Diagnose Cryptococcal meningitis. Sensitivity 70-90% in HIV patients.',
        'note':'Follow with CrAg LFA (sensitivity 99%) for confirmation.',
    },
    'KOH': {
        'use':'Detect fungal elements in skin, nail, hair, sputum, vaginal discharge',
        'concentration':'10-20% KOH','time':'5-30 min',
        'results':{'positive':'Hyphae, pseudohyphae, spores — refractile on microscopy','C.albicans':'budding yeast + pseudohyphae','Dermatophyte':'septate hyphae + arthrospores'},
        'clinical':'Rapid point-of-care fungal diagnosis. Calcofluor white (fluorescent) more sensitive.',
    },
    'HE': {
        'use':'Routine histology — all tissue biopsies',
        'stains':'Haematoxylin (nuclei blue/purple) + Eosin (cytoplasm pink)',
        'use_cases':['Histopathology all organs','Cancer diagnosis and grading','Inflammatory infiltrates'],
        'clinical':'Universal stain — starting point for all histological diagnosis.',
    },
    'PAS': {
        'use':'Detect glycogen, mucin, fungi (Pneumocystis, Candida), basement membranes',
        'results':'Positive=MAGENTA/PINK, Negative=blue/green counterstain',
        'use_cases':['Fungal detection (Pneumocystis jirovecii in BAL)','Renal PAS (basement membrane thickening in DM)','Mucin staining'],
    },
    'GMS': {
        'use':'Fungal detection — silver methenamine (Grocott) stain',
        'results':'Fungi BLACK on green/grey background',
        'sensitivity':'Higher than PAS for fungi','use_cases':['Pneumocystis jirovecii','Histoplasma','Aspergillus','Cryptococcus'],
    },
    'ALBERT': {
        'use':'Corynebacterium diphtheriae — detect metachromatic granules',
        'results':'Granules DARK BLUE/BLACK; rest of cell GREEN',
        'clinical':'Diagnose diphtheria when pseudomembrane present.',
    },
    'NEW_METHYLENE_BLUE': {
        'use':'Reticulocyte count, Heinz bodies, blood parasites (quick)',
        'results':'Reticulocytes show blue RNA network','clinical':'Haemolytic anaemia, G6PD — Heinz bodies (denatured Hb)',
    },
}

PARASITES = {
    'P_FALCIPARUM': {
        'name':'Plasmodium falciparum','disease':'Malaria (most severe)',
        'vector':'Anopheles female mosquito (night biting)',
        'infective_stage':'Sporozoite (salivary gland)','diagnostic_stage':'Ring forms, gametocytes in blood',
        'specimen':'EDTA blood (GE + FS)','stain':'Giemsa or Fields',
        'morphology':{'rings':'Small, delicate, double chromatin dot, "appliqué/accolé" forms (at RBC margin)','gametocytes':'BANANA-shaped (only P.falciparum)','schizont':'Rarely seen in peripheral blood (sequestered)'},
        'rbc_changes':'NO Schüffner dots, no RBC enlargement, >5% parasitemia possible',
        'complications':['Cerebral malaria (seizure, coma)','Severe anaemia (Hgb <7)','Renal failure (blackwater fever)','ARDS','Hypoglycaemia','DIC'],
        'lab':['Anaemia (normocytic)','Thrombocytopenia','Leukopenia','Elevated LDH/bilirubin','Hypoglycaemia'],
        'treatment_principle':'Artemisinin-based combination therapy (ACT). Severe: IV Artesunate.',
        'mentzer_note':'Malaria causes normocytic anaemia — Mentzer index not applicable.',
    },
    'P_VIVAX': {
        'name':'Plasmodium vivax','disease':'Relapsing Malaria',
        'infective_stage':'Sporozoite','diagnostic_stage':'Trophozoites, schizonts, gametocytes',
        'morphology':{'trophozoite':'Amoeboid (irregular shape), enlarged RBC with SCHÜFFNER DOTS','merozoites':'16/schizont'},
        'rbc_changes':'ENLARGED RBC, SCHÜFFNER DOTS present',
        'special':'Hypnozoites in liver — cause relapse weeks-months later',
        'complications':['Splenomegaly','Anaemia','Rare splenic rupture'],
        'treatment_principle':'Chloroquine (if sensitive) + Primaquine (kills hypnozoites). Check G6PD before primaquine!',
    },
    'P_MALARIAE': {
        'name':'Plasmodium malariae','disease':'Quartan malaria (72h cycle)',
        'morphology':{'trophozoite':'BAND FORM (crosses width of RBC)','schizont':'ROSETTE pattern (merozoites around central pigment)'},
        'rbc_changes':'NO Schüffner dots, NO enlargement. Low parasitemia.',
        'complications':['Quartan nephropathy (immune complex GN)'],
    },
    'P_OVALE': {
        'name':'Plasmodium ovale','disease':'Ovale malaria (benign relapsing)',
        'morphology':{'trophozoite':'Compact, oval/fimbriated RBC','rbc':'OVAL RBC SHAPE, SCHÜFFNER DOTS'},
        'treatment_principle':'Chloroquine + Primaquine (has hypnozoites like vivax)',
    },
    'TRYPANOSOMA_BRUCEI': {
        'name':'Trypanosoma brucei','disease':'African Sleeping Sickness',
        'subspecies':{'gambiense':'West Africa, chronic (months-years), Glossina palpalis (riverine)','rhodesiense':'East Africa, acute (weeks), Glossina morsitans (savanna)'},
        'vector':'Tsetse fly (Glossina spp.) — daytime biting',
        'infective_stage':'Metacyclic trypomastigote (fly saliva)',
        'diagnostic_stage':'Trypomastigotes in blood/lymph/CSF',
        'morphology':'Long (15-30µm), kinetoplast at posterior, undulating membrane, free flagellum',
        'stages':{'stage1':'Blood/lymph (haemolymphatic)','stage2':'CNS involvement (encephalitic)'},
        'signs':['Chancre at bite site','Winterbottom sign (posterior cervical lymphadenopathy — gambiense)','Fever','Daytime somnolence','Coma'],
        'lab':['Trypomastigotes in thick blood film or lymph node aspirate','Anaemia','Elevated IgM'],
    },
    'T_CRUZI': {
        'name':'Trypanosoma cruzi','disease':'Chagas disease (American trypanosomiasis)',
        'vector':'Triatoma (kissing/assassin bug) — feces contaminate bite wound',
        'geographic':'Latin America','infective_stage':'Metacyclic trypomastigote',
        'diagnostic_stage':{'acute':'Trypomastigotes in blood (C-shaped)','chronic':'Amastigotes in heart/muscle tissue'},
        'signs':['Romana sign (unilateral painless periorbital oedema)','Chagoma (skin nodule at bite)','Cardiomegaly','Megaoesophagus/megacolon'],
        'complications':['Cardiomyopathy','Arrhythmia','Sudden cardiac death','Achalasia'],
    },
    'LEISHMANIA_DONOVANI': {
        'name':'Leishmania donovani complex','disease':'Visceral leishmaniasis (Kala-azar)',
        'vector':'Phlebotomus sandfly (Old World) / Lutzomyia (New World)',
        'infective_stage':'Promastigote (metacyclic, in sandfly saliva)',
        'diagnostic_stage':'Amastigotes (LD bodies) in macrophages of RES (spleen, bone marrow, liver)',
        'specimen':'Bone marrow aspirate (safest), splenic aspirate (most sensitive but risky), lymph node',
        'stain':'Giemsa — LD bodies 2-4µm oval, visible nucleus + kinetoplast',
        'signs':['Prolonged fever','Massive splenomegaly','Hepatomegaly','Weight loss','Darkening of skin (kala-azar = black sickness)'],
        'lab':['Pancytopenia','Hypergammaglobulinaemia (IgG)','Hypoalbuminaemia','Elevated ESR'],
        'serology':['DAT (direct agglutination test)','rK39 rapid test'],
        'treatment_principle':'Liposomal Amphotericin B or Miltefosine',
    },
    'E_HISTOLYTICA': {
        'name':'Entamoeba histolytica','disease':'Amoebiasis (amoebic dysentery/liver abscess)',
        'infective_stage':'Quadrinucleate cyst (4 nuclei) — faecal-oral',
        'diagnostic_stage':{'stool':'Trophozoite WITH INGESTED RBCs = PATHOGENIC (E.histolytica)','cyst':'Quadrinucleate cyst'},
        'non_pathogenic':'E.coli (8 nuclei in mature cyst), E.dispar (morphologically identical to histolytica)',
        'specimen':'Fresh stool (within 30min), preserved stool',
        'stain':'Saline wet mount (motility) + Lugol iodine (cyst nuclear detail)',
        'complications':{'intestinal':['Colonic flask-shaped ulcers','Perforation','Amoeboma'],'extraintestinal':['Liver abscess (chocolate sauce/anchovy paste pus)','Lung abscess','Brain abscess']},
        'serology':'Serology positive in invasive disease (antibody to Gal/GalNAc lectin)',
        'treatment_principle':'Metronidazole (invasive) + Diloxanide furoate (luminal cysts)',
    },
    'GIARDIA': {
        'name':'Giardia lamblia (intestinalis/duodenalis)','disease':'Giardiasis',
        'infective_stage':'Cyst (4 nuclei, oval, 8-12µm) — faecal-oral',
        'diagnostic_stage':'Trophozoite (pear-shaped, 2 nuclei, 4 pairs of flagella, ventral disc) + cysts in stool',
        'motility':'Falling leaf motility of trophozoite',
        'specimen':'Stool (3 samples on alternate days for best sensitivity)',
        'symptoms':['Fatty diarrhoea/steatorrhoea','Malabsorption','Bloating','Weight loss','No blood/mucus (non-invasive)'],
        'lab':['Stool microscopy — trophozoites/cysts','Stool antigen EIA (most sensitive)','Duodenal aspirate if stool negative'],
        'treatment_principle':'Metronidazole or Tinidazole',
    },
    'CRYPTOSPORIDIUM': {
        'name':'Cryptosporidium parvum/hominis','disease':'Cryptosporidiosis',
        'infective_stage':'Sporulated oocyst (4 sporozoites)','diagnostic_stage':'Oocysts in stool',
        'size':'4-6 µm','stain':'MODIFIED ZN (cold ZN) — PINK oocysts on BLUE background',
        'symptoms':['Watery diarrhoea (profuse in immunocompromised)','Self-limiting in immunocompetent (7-14 days)','Life-threatening in HIV/AIDS (<200 CD4)'],
        'diagnosis':['Modified ZN stain','Stool antigen EIA','PCR (most sensitive)'],
        'treatment':'Nitazoxanide (limited). Immunocompromised: ART to restore CD4.',
    },
    'SCHISTOSOMA': {
        'S_mansoni':{'eggs':'Lateral spine','snail':'Biomphalaria','disease':'Intestinal + portal hypertension','geographic':'Africa, Middle East, Americas'},
        'S_haematobium':{'eggs':'Terminal spine','snail':'Bulinus','disease':'Urinary schistosomiasis (haematuria)','geographic':'Africa, Middle East'},
        'S_japonicum':{'eggs':'Small lateral spine','snail':'Oncomelania','disease':'Intestinal','geographic':'Asia'},
        'lifecycle':'Miracidium→snail→cercaria→penetrate human skin→schistosomula→portal system→adult worms→eggs in tissues',
        'diagnosis_haematobium':'Terminal urine (noon collection) — eggs with terminal spine','diagnosis_mansoni':'Stool — eggs with lateral spine','serology':'Available',
        'complications_haematobium':['Haematuria','Bladder fibrosis','Bladder cancer (SCC)','Hydronephrosis'],
        'complications_mansoni':['Portal hypertension','Oesophageal varices','Hepatosplenomegaly'],
    },
    'ASCARIS': {
        'name':'Ascaris lumbricoides','disease':'Ascariasis',
        'infective':'Embryonated egg (soil-transmitted)','diagnostic':'Eggs in stool, worms in stool/vomit',
        'lifecycle':'Egg→larva in soil→swallowed→duodenum→liver→lung (Löffler syndrome)→pharynx→swallowed→intestine→adult',
        'complications':['Intestinal obstruction (heavy worm load)','Biliary/pancreatic duct obstruction','Löffler syndrome (pulmonary eosinophilia)'],
        'lab':['Eosinophilia (larval migration phase)','Stool microscopy — large ova','Worms in stool/vomit'],
    },
    'HOOKWORM': {
        'name':'Ancylostoma duodenale / Necator americanus','disease':'Hookworm infection',
        'infective':'Filariform (L3) larvae — skin penetration (walking barefoot)',
        'diagnostic':'Eggs in stool (oval, thin shell)','larva':'Rhabditiform L1 larvae in fresh stool',
        'complications':['Iron Deficiency Anaemia (blood-sucking)','Hypoalbuminaemia','Malnutrition','Cutaneous larva migrans (creeping eruption)'],
        'lab':['Microcytic hypochromic anaemia','Low ferritin','Eosinophilia','Stool microscopy — eggs'],
    },
    'TOXOPLASMA': {
        'name':'Toxoplasma gondii','disease':'Toxoplasmosis',
        'definitive_host':'Cat (sexual cycle — oocysts in faeces)','intermediate_host':'Humans, all warm-blooded animals',
        'infective':'Oocyst (from cat faeces) OR tissue cyst (undercooked meat)',
        'forms':{'tachyzoite':'Active (acute infection — rapidly multiplying)','bradyzoite':'Dormant in tissue cysts (chronic)'},
        'congenital':['Intracranial calcifications','Hydrocephalus','Chorioretinitis (classical triad)','Microcephaly','Stillbirth'],
        'immunocompromised':'Encephalitis (toxoplasma reactivation in HIV — CD4 <100)',
        'diagnosis':{'serology':'IgM (acute), IgG (past/chronic)','PCR':'amniotic fluid, CSF','imaging':'Ring-enhancing lesions brain (toxo vs lymphoma)'},
        'treatment_principle':'Pyrimethamine + Sulfadiazine + Folinic acid',
    },
    'W_BANCROFTI': {
        'name':'Wuchereria bancrofti','disease':'Lymphatic filariasis (elephantiasis)',
        'vector':'Culex mosquito (night biting — nocturnal periodicity)',
        'infective':'L3 larvae (mosquito salivary gland)','diagnostic':'Microfilariae in blood',
        'periodicity':'NOCTURNAL — blood sample at midnight',
        'morphology':'Sheathed microfilaria, NO nuclei in tail tip',
        'complications':['Lymphoedema','Elephantiasis (limbs/scrotum)','Hydrocele','Tropical pulmonary eosinophilia'],
        'diagnosis':['Thick blood film at midnight','Knott concentration method','Antigen card test (day sample)'],
    },
    'T_SOLIUM': {
        'name':'Taenia solium','disease':'Taeniasis (intestinal) + Cysticercosis (larval)',
        'infective':'Cysticercus in undercooked pork (taeniasis) OR ingested eggs (cysticercosis)',
        'diagnostic':'Proglottids/eggs in stool (taeniasis)','uterine_branches':'<13 (vs saginata >13)',
        'cysticercosis':'Larval cysts in: brain (neurocysticercosis — seizures), muscle, eye, skin',
        'treatment_principle':'Praziquantel or Niclosamide. Neurocysticercosis: Albendazole + corticosteroids',
    },
}

DISEASE_LAB_CORRELATIONS = {
    'MALARIA': {
        'key_tests':['GE+FS (thick+thin film)','Malaria RDT (HRP2/pLDH)','CBC'],
        'expected':{'GE_FS':'parasites visible (specify species+parasitemia%)','RDT':'positive HRP2/pLDH','Hgb':'low (normocytic)','Platelets':'low (thrombocytopenia)','WBC':'low-normal','LDH':'elevated','Bilirubin':'elevated (haemolysis)'},
        'notes':'GE+FS gold standard. RDT fast but misses low parasitemia. Culture not needed.',
    },
    'TYPHOID': {
        'key_tests':['Blood culture (week 1-2)','Stool/urine culture (week 2-3)','CBC','LFT'],
        'expected':{'blood_cx':'Salmonella typhi/paratyphi','WBC':'LEUKOPENIA (classic)','Eosinophils':'absent (eosinopenia)','LFT':'mild elevation','platelets':'may fall'},
        'notes':'Widal test unreliable in endemic areas. Blood culture week 1 most sensitive.',
    },
    'HIV_AIDS': {
        'key_tests':['HIV Ag/Ab combo (4th gen screening)','CD4 count','Viral Load','CBC'],
        'expected':{'HIV_screen':'reactive (confirm with 2nd test or Western Blot)','CD4':'<200=AIDS-defining','VL':'detectable/quantified','WBC':'low','lymphocytes':'depleted'},
        'who_staging':{'1':'Asymptomatic/mild','2':'Moderate','3':'Advanced','4':'Severe (AIDS)'},
    },
    'TB': {
        'key_tests':['GeneXpert MTB/RIF Ultra','ZN smear ×3','Culture (LJ/MGIT)','CBC','LFT (before ARV)'],
        'expected':{'GeneXpert':'MTB detected + RIF sensitivity','ZN':'AFB seen (scanty to 3+)','culture':'MTB grows (6-8 weeks on LJ, 1-6 weeks MGIT)','CBC':'normocytic anaemia','ESR':'very elevated'},
        'notes':'GeneXpert sensitivity 89% for smear-positive. Must do LFT before starting INH/RIF.',
    },
    'DIABETES': {
        'key_tests':['FBS','OGTT (2h)','HbA1c','Urinalysis (albumin)','Lipid profile','Renal function'],
        'diagnostic_criteria':{'FBS':'≥7.0 mmol/L (×2 tests)','OGTT_2h':'≥11.1 mmol/L','HbA1c':'≥6.5%','RBS':'≥11.1 + symptoms'},
        'monitoring':{'HbA1c':'every 3-6 months','renal':'annual eGFR + ACR','lipids':'annual'},
    },
    'IDA': {
        'name':'Iron Deficiency Anaemia',
        'key_tests':['CBC','Ferritin','Iron','TIBC','Blood film'],
        'expected':{'Hgb':'low','MCV':'low (<80 fL)','MCH':'low','MCHC':'low','RDW':'HIGH (anisocytosis)','Ferritin':'<10 µg/L (depleted stores)','Iron':'low','TIBC':'HIGH (compensatory)','transferrin_sat':'<15%','film':'microcytic hypochromic, target cells, pencil cells'},
        'mentzer':'MCV/RBC >13 = IDA (vs <13 = thalassaemia)',
    },
    'THALASSAEMIA': {
        'key_tests':['CBC','Hb Electrophoresis','Mentzer Index','Blood film'],
        'expected':{'Hgb':'low','MCV':'very low (<70 fL)','RBC':'NORMAL or HIGH (despite low Hgb)','Mentzer':'<13','Ferritin':'normal or high (not depleted)','film':'hypochromic, target cells, basophilic stippling','Hb_electrophoresis':'HbA2 >3.5% (beta-thal minor), HbF elevated'},
    },
    'SEPSIS': {
        'key_tests':['Blood culture ×2','CBC','CRP','PCT','Lactate','Renal/hepatic function'],
        'expected':{'WBC':'elevated or severely low','neutrophils':'band forms (left shift)','CRP':'very high >100','PCT':'>2 = bacterial sepsis','Lactate':'>2 mmol/L (tissue hypoperfusion)','blood_cx':'organism identified in 40-60%'},
        'notes':'Source cultures before antibiotics (blood, urine, wound). SOFA score for severity.',
    },
    'DKA': {
        'name':'Diabetic Ketoacidosis',
        'key_tests':['Blood glucose','Blood ketones','ABG','U&E','CBC'],
        'expected':{'glucose':'>14 mmol/L','ketones':'>3 mmol/L or large urine ketones','pH':'<7.3','bicarbonate':'<15 mmol/L','anion_gap':'>12','K+':'may be elevated initially (shifts out of cells) but total body depleted'},
    },
    'RENAL_FAILURE': {
        'key_tests':['Creatinine','Urea','eGFR','Electrolytes','Urinalysis','Urinary protein'],
        'ckd_stages':{'G1':'eGFR≥90','G2':'60-89','G3a':'45-59','G3b':'30-44','G4':'15-29','G5':'<15 (renal replacement)'},
        'expected':{'creatinine':'elevated','urea':'elevated','eGFR':'reduced','K+':'elevated (hyperkalaemia)','Bicarb':'low (metabolic acidosis)','Hgb':'low (EPO deficiency)','Phosphate':'elevated','Calcium':'low'},
    },
    'LIVER_FAILURE': {
        'key_tests':['LFTs','PT/INR','Albumin','Bilirubin','Ammonia','CBC'],
        'expected':{'ALT_AST':'very high (hepatocellular)','ALP_GGT':'high (cholestatic)','Albumin':'LOW (<25 = severe)','PT_INR':'prolonged','Bilirubin':'HIGH','Ammonia':'elevated (encephalopathy)','platelets':'low (portal hypertension)'},
    },
}

CRITICAL_VALUES = {
    'GLUCOSE':   {'low_critical':2.2,'high_critical':22.2,'unit':'mmol/L','action':'IV dextrose if <2.2; insulin if >22.2'},
    'POTASSIUM': {'low_critical':2.8,'high_critical':6.5,'unit':'mmol/L','action':'ECG monitoring; IV KCl if <2.8; urgent treatment if >6.5'},
    'SODIUM':    {'low_critical':120,'high_critical':160,'unit':'mmol/L','action':'Seizure risk <120; slow correction; neurological monitoring'},
    'CALCIUM':   {'low_critical':1.75,'high_critical':3.5,'unit':'mmol/L','action':'IV calcium gluconate if <1.75; IV fluids + bisphosphonate if >3.5'},
    'HAEMOGLOBIN':{'low_critical':7.0,'high_critical':None,'unit':'g/dL','action':'Consider transfusion if symptomatic'},
    'PLATELETS': {'low_critical':20,'high_critical':None,'unit':'×10⁹/L','action':'Platelet transfusion if <10-20 or bleeding'},
    'TROPONIN':  {'low_critical':None,'high_critical':0.04,'unit':'ng/mL','action':'ECG, urgent cardiology consult — ACS until proved otherwise'},
    'CREATININE':{'low_critical':None,'high_critical':884,'unit':'µmol/L','action':'Urgent nephrology — consider dialysis'},
    'BICARBONATE':{'low_critical':10,'high_critical':40,'unit':'mmol/L','action':'ABG, treat underlying cause — DKA vs COPD'},
    'INR':       {'low_critical':None,'high_critical':5.0,'unit':'ratio','action':'Hold anticoagulant; Vitamin K or FFP if bleeding'},
}

AGE_GENDER_RANGES = {
    'HAEMOGLOBIN': {
        'adult_male':   (13.5, 17.5, 'g/dL'),
        'adult_female': (12.0, 16.0, 'g/dL'),
        'children_6m_6y':(11.0,14.0,'g/dL'),
        'children_6_12': (11.5,15.5,'g/dL'),
        'neonates':      (14.0,24.0,'g/dL'),
        'pregnancy':     (11.0,14.0,'g/dL'),
    },
    'FERRITIN': {
        'adult_male':   (30, 400, 'µg/L'),
        'adult_female': (13, 150, 'µg/L'),
        'children':     (7,  140, 'µg/L'),
        'note':'Ferritin is an acute-phase protein — elevated in infection/inflammation even with true IDA',
    },
    'CREATININE': {
        'adult_male':   (62, 115, 'µmol/L'),
        'adult_female': (53, 97,  'µmol/L'),
        'children_0_2': (20, 55,  'µmol/L'),
        'children_2_12':(25, 75,  'µmol/L'),
        'elderly':      'may appear normal despite reduced GFR — use eGFR',
    },
    'ALP': {
        'adult':    (44, 147, 'U/L'),
        'children': (100, 400, 'U/L'),
        'note':'ALP physiologically elevated in children (bone growth) and pregnancy (placenta)',
    },
    'PSA': {
        'male_40_49':(0, 2.5,'ng/mL'),
        'male_50_59':(0, 3.5,'ng/mL'),
        'male_60_69':(0, 4.5,'ng/mL'),
        'male_70_up':(0, 6.5,'ng/mL'),
        'note':'PSA is male-specific. Free:Total PSA ratio helps in grey zone 4-10 ng/mL.',
    },
    'TSH': {
        'adult':   (0.27, 4.2, 'mIU/L'),
        'pregnant_T1':(0.1,2.5,'mIU/L'),
        'pregnant_T2':(0.2,3.0,'mIU/L'),
        'pregnant_T3':(0.3,3.5,'mIU/L'),
        'neonates':(1.0,39.0,'mIU/L'),
        'note':'Hypothyroid in pregnancy causes fetal brain damage — screen all pregnant women',
    },
}

WARD_ABBREVIATIONS = {
    'OPD':'Outpatient / Consultations Externes','IPD':'Inpatient / Hospitalisation',
    'ICU':'Unité de Soins Intensifs / Réanimation','NICU':'Neonatologie',
    'PICU':'Pédiatrie Intensive','HDU':'High Dependency / Semi-intensif',
    'OT':'Bloc Opératoire','ER':'Urgences / Emergency Room',
    'ANC':'Soins Prénataux / CPN','PNC':'Soins Postnataux','MCH':'Santé Mère-Enfant',
    'GYN':'Gynécologie','PED':'Pédiatrie','MED':'Médecine Interne',
    'SURG':'Chirurgie Générale','ORTHO':'Orthopédie','CARD':'Cardiologie',
    'NEURO':'Neurologie','NEPH':'Néfrologie','PULM':'Pneumologie / Chest',
    'GASTRO':'Gastroentérologie','ONCO':'Oncologie','HAEM':'Hématologie Clinique',
    'DERM':'Dermatologie','OPHTH':'Ophtalmologie','ENT':'ORL',
    'PSYCH':'Psychiatrie','RHEUM':'Rhumatologie','ENDO':'Endocrinologie',
    'ID':'Maladies Infectieuses','REHAB':'Rééducation','BURNS':'Brûlologie',
    'VL':'Viral Load (result type)','GE':'Goutte Épaisse (malaria test)',
    'FS':'Frottis Sanguin (malaria test)','GYN_SWAB':'HVS / Prélèvement Vaginal',
}

# ── Helper functions ───────────────────────────────────────────────────────────

def lookup(term: str) -> str:
    """Look up any medical abbreviation or term."""
    t = term.strip().upper()
    if t in MEDICAL_ABBREVIATIONS:
        return MEDICAL_ABBREVIATIONS[t]
    t2 = term.strip().lower()
    for k, v in MEDICAL_ABBREVIATIONS.items():
        if t2 in v.lower() or t2 in k.lower():
            return f'{k}: {v}'
    return f'Term "{term}" not found in knowledge base.'


def get_tube_for_test(test_name: str) -> str:
    """Return the recommended tube for a test."""
    t = test_name.strip().upper().replace(' ','_')
    if t in TEST_TO_TUBE:
        return TEST_TO_TUBE[t]
    for k, v in TEST_TO_TUBE.items():
        if t in k or k in t:
            return v
    return 'SST_GOLD'   # default to gold/SST for unknown tests


def get_critical_values(test_code: str) -> dict:
    """Return critical value thresholds for a test."""
    return CRITICAL_VALUES.get(test_code.upper(), {})


def search(query: str) -> list:
    """Search across all knowledge base sections."""
    q = query.lower()
    results = []
    for abbr, full in MEDICAL_ABBREVIATIONS.items():
        if q in abbr.lower() or q in full.lower():
            results.append({'type':'abbreviation','code':abbr,'meaning':full})
    for disease, data in DISEASE_LAB_CORRELATIONS.items():
        if q in disease.lower() or q in str(data).lower():
            results.append({'type':'disease','name':disease,'data':data})
    return results[:10]


def get_rejection_guidance(reason_code: str) -> dict:
    """Get CLSI rejection guidance for a specific rejection reason."""
    return REJECTION_REASONS.get(reason_code.upper(), {
        'severity':'reject','action':'Reject sample. Recollect. Document reason.',
        'clsi':'EP23'
    })
