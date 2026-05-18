"""
JORINOVA NEXUS ALIS-X — Voice AI Assistant Knowledge Base
==========================================================
Production voice guidance system for touch-free lab operation.

Covers:
  - System navigation commands (all pages/modules)
  - Step-by-step workflow guidance (EN / FR / RW)
  - Medical terminology explanations
  - Lab procedure guidance (reception, worklist, result entry, validation)
  - ISO 15189 quality requirements
  - AI interpretation of spoken commands

Languages:
  en — English (default)
  fr — French (Rwanda official)
  rw — Kinyarwanda (national language, common in labs)

Voice: Female, calm, professional — like a knowledgeable colleague guiding you.

IMPORTANT: All patient data queries go through the secure API (not spoken directly).
"""
from __future__ import annotations
import logging
import re
from typing import Optional

log = logging.getLogger('voice_assistant')

# ── Navigation map: voice command → URL + spoken confirmation ─────────────────

NAVIGATION_MAP = {
    # English commands
    'dashboard':        ('/dashboard/', 'Opening the main dashboard.'),
    'home':             ('/dashboard/', 'Going to dashboard.'),
    'reception':        ('/reception/', 'Opening sample reception.'),
    'worklist':         ('/worklist/',  'Opening worklist preparation.'),
    'hematology':       ('/hematology/','Opening hematology department.'),
    'haematology':      ('/hematology/','Opening haematology department.'),
    'biochemistry':     ('/biochemistry/','Opening biochemistry.'),
    'chemistry':        ('/biochemistry/','Opening chemistry department.'),
    'microbiology':     ('/microbiology/','Opening microbiology.'),
    'micro':            ('/microbiology/','Opening microbiology.'),
    'molecular':        ('/molecular/','Opening molecular diagnostics.'),
    'urinalysis':       ('/urinalysis/','Opening urinalysis department.'),
    'urine':            ('/urinalysis/','Opening urinalysis.'),
    'coagulation':      ('/coagulation/','Opening coagulation department.'),
    'blood bank':       ('/blood-bank/','Opening blood bank.'),
    'transfusion':      ('/blood-bank/','Opening blood bank and transfusion.'),
    'serology':         ('/serology/','Opening serology and immunology.'),
    'immunology':       ('/serology/','Opening immunology department.'),
    'pathology':        ('/pathology/','Opening pathology department.'),
    'toxicology':       ('/toxicology/','Opening toxicology department.'),
    'quality':          ('/quality/','Opening quality management.'),
    'quality control':  ('/quality/','Opening quality control.'),
    'levey jennings':   ('/quality/levey-jennings','Opening Levey-Jennings QC chart.'),
    'levey-jennings':   ('/quality/levey-jennings','Opening Levey-Jennings chart.'),
    'records':          ('/records/','Opening laboratory records.'),
    'patients':         ('/patients/','Opening patient registry.'),
    'patients hub':     ('/patients/hub/','Opening patients hub.'),
    'surveillance':     ('/surveillance/','Opening epidemic surveillance.'),
    'inventory':        ('/inventory/','Opening inventory management.'),
    'billing':          ('/billing/','Opening billing system.'),
    'reports':          ('/reports/','Opening reports module.'),
    'audit':            ('/audit-trail/','Opening audit trail.'),
    'staffhub':         ('/staffhub/','Opening staff hub.'),
    'staff':            ('/staffhub/','Opening staff management.'),
    'admin':            ('/admin/','Opening administration panel.'),
    'settings':         ('/core-config/','Opening system settings.'),
    'genomics':         ('/genomics/','Opening genomics module.'),
    'ai':               ('/ai-nexus/','Opening A I intelligence hub.'),
    'microbiology ai':  ('/micro-ai/','Opening microbiology AI module.'),
    'security':         ('/security/','Opening security module.'),
    'interoperability': ('/interoperability/','Opening interoperability module.'),
    'notifications':    ('/notifications/','Opening notifications.'),
    # French commands
    'accueil':          ('/dashboard/','Ouverture du tableau de bord.'),
    'réception':        ('/reception/','Ouverture de la réception des échantillons.'),
    'hématologie':      ('/hematology/','Ouverture du département d\'hématologie.'),
    'biochimie':        ('/biochemistry/','Ouverture de la biochimie.'),
    'microbiologie':    ('/microbiology/','Ouverture de la microbiologie.'),
    'moléculaire':      ('/molecular/','Ouverture de la biologie moléculaire.'),
    'banque du sang':   ('/blood-bank/','Ouverture de la banque du sang.'),
    'qualité':          ('/quality/','Ouverture du contrôle qualité.'),
    'patients':         ('/patients/','Ouverture du registre des patients.'),
    'facturation':      ('/billing/','Ouverture de la facturation.'),
    'dossiers':         ('/records/','Ouverture des dossiers de laboratoire.'),
    # Kinyarwanda commands
    'amagara':          ('/hematology/','Fungura igice cy\'amaraso.'),
    'inkingo':          ('/blood-bank/','Fungura banki y\'amaraso.'),
    'ubuvuzi':          ('/dashboard/','Fungura imbonerahamwe.'),
}

# ── Step-by-step workflow guides ──────────────────────────────────────────────

WORKFLOW_GUIDES = {
    'receive_sample': {
        'en': [
            "Step 1: Open Reception from the sidebar or say 'Open Reception'.",
            "Step 2: Search for the patient by name or PID in the patient search box.",
            "Step 3: Select the correct patient from the results.",
            "Step 4: Enter the requesting doctor's name and ward.",
            "Step 5: Search and select the ordered tests from the test catalog.",
            "Step 6: Set the priority — routine, urgent, or STAT.",
            "Step 7: Click Submit Request to create the lab request.",
            "Step 8: Go to the new request and click Prepare Worklist.",
            "Step 9: Confirm the tube assignments for each specimen type.",
            "Step 10: Click Confirm and Generate Worklist. The system will assign SIDs, rack numbers, and open billing.",
            "Step 11: Confirm the billing items and payment method.",
            "Step 12: Print specimen labels for all tubes. Labels show: patient name, SID, barcode, department, and tests.",
            "The sample reception is complete. Samples are now in the department worklists.",
        ],
        'fr': [
            "Étape 1: Ouvrez la réception depuis le menu ou dites 'Réception'.",
            "Étape 2: Cherchez le patient par nom ou PID.",
            "Étape 3: Sélectionnez le bon patient dans les résultats.",
            "Étape 4: Entrez le nom du médecin prescripteur et le service.",
            "Étape 5: Sélectionnez les analyses demandées dans le catalogue.",
            "Étape 6: Définissez la priorité: routine, urgent, ou STAT.",
            "Étape 7: Cliquez Soumettre la demande.",
            "Étape 8: Allez à la nouvelle demande et cliquez Préparer le Worklist.",
            "Étape 9: Confirmez les tubes pour chaque type d'échantillon.",
            "Étape 10: Cliquez Confirmer et Générer le Worklist. Le système assigne les SID et ouvre la facturation.",
            "Étape 11: Confirmez les éléments de facturation et le mode de paiement.",
            "Étape 12: Imprimez les étiquettes pour tous les tubes.",
            "La réception de l'échantillon est terminée.",
        ],
        'rw': [
            "Intambwe ya 1: Fungura reception ukoresheje menu.",
            "Intambwe ya 2: Shakisha umurwayi ukoresheje izina cg PID.",
            "Intambwe ya 3: Hitamo umurwayi ukwiye.",
            "Intambwe ya 4: Shyiramo izina rya muganga na ward.",
            "Intambwe ya 5: Hitamo ibizamini bisabwe mu katalogue.",
            "Intambwe ya 6: Hitamo intambwe: routine, urgent, cg STAT.",
            "Intambwe ya 7: Kanda Submit Request.",
            "Intambwe ya 8: Jya kuri request mushya ukande Prepare Worklist.",
            "Intambwe ya 9: Emeza tubes za buri igice cy'ingano.",
            "Intambwe ya 10: Kanda Confirm na Generate Worklist. Sistema izaha SID, numero y'icyunamo, itangura gufatira.",
            "Intambwe ya 11: Emeza ibintu byo gufatira n'uburyo bwo kwishyura.",
            "Intambwe ya 12: Sohora etiquette za tubes zose.",
            "Reception y'ingano irarangiye.",
        ],
    },
    'enter_result': {
        'en': [
            "Step 1: Go to the relevant department worklist — for example, open Biochemistry.",
            "Step 2: Find the patient sample in the worklist by SID or rack number.",
            "Step 3: Click the sample to open the result entry form.",
            "Step 4: Enter the numeric value from the analyzer into the result field.",
            "Step 5: Verify the unit is correct — for example, millimoles per liter.",
            "Step 6: The system will automatically flag the result as High, Low, or Critical based on reference ranges.",
            "Step 7: Review the AI interpretation note shown below the result.",
            "Step 8: If the result is critical — like potassium above 6.5 — you must notify the clinician immediately and document it.",
            "Step 9: Click Validate to mark the result as reviewed and validated.",
            "Step 10: If you are a pathologist or lab manager, click Authorize to release the result.",
            "Results are now available to the doctor via the doctor portal.",
        ],
        'fr': [
            "Étape 1: Ouvrez le worklist du département concerné.",
            "Étape 2: Trouvez l'échantillon par SID ou numéro de rack.",
            "Étape 3: Cliquez pour ouvrir le formulaire de saisie des résultats.",
            "Étape 4: Entrez la valeur numérique de l'analyseur.",
            "Étape 5: Vérifiez l'unité de mesure.",
            "Étape 6: Le système flaggera automatiquement les valeurs anormales.",
            "Étape 7: Consultez l'interprétation AI affichée sous le résultat.",
            "Étape 8: Si c'est une valeur critique, notifiez immédiatement le clinicien.",
            "Étape 9: Cliquez Valider pour confirmer le résultat.",
            "Étape 10: Le pathologiste autorise et libère le résultat.",
        ],
        'rw': [
            "Intambwe ya 1: Fungura worklist y'icyiciro gishinzwe.",
            "Intambwe ya 2: Shakisha ingano ya SID cg numero y'icyunamo.",
            "Intambwe ya 3: Kanda inzu yo gushyiramo ibisubizo.",
            "Intambwe ya 4: Shyiramo inomero ivuye ku analyzer.",
            "Intambwe ya 5: Reba ko unit ari yo.",
            "Intambwe ya 6: Sistema izatera ibendera ibisubizo bidasanzwe.",
            "Intambwe ya 7: Soma inshamake y'AI iri munsi y'ibisubizo.",
            "Intambwe ya 8: Niba ari agaciro gasumba urugero — nko potassium irenze 6.5 — menyesha muganga vuba.",
            "Intambwe ya 9: Kanda Validate kugirango wemeze ibisubizo.",
            "Intambwe ya 10: Pathologiste cg manager yemeza agasohorora ibisubizo.",
        ],
    },
    'validate_result': {
        'en': [
            "To validate a result, follow these steps.",
            "Step 1: Open the department worklist or search for the patient.",
            "Step 2: Find the result to validate — it should be in PENDING status.",
            "Step 3: Review the result value, unit, and reference range carefully.",
            "Step 4: Check the AI interpretation — does it match your clinical assessment?",
            "Step 5: If a critical value is present — like sodium below 120 or above 160 — you must document clinician notification before validating.",
            "Step 6: Click the Validate button. You will be asked to confirm.",
            "Step 7: The result status changes from PENDING to VALIDATED.",
            "Step 8: If you are authorizing — as a pathologist or lab manager — click Authorize to release to the doctor.",
            "Remember: Never release a result you are not confident about. When in doubt, repeat the test.",
        ],
        'fr': [
            "Pour valider un résultat, suivez ces étapes.",
            "Étape 1: Ouvrez le worklist ou cherchez le patient.",
            "Étape 2: Trouvez le résultat en statut PENDING.",
            "Étape 3: Vérifiez soigneusement la valeur, l'unité et l'intervalle de référence.",
            "Étape 4: Vérifiez l'interprétation AI.",
            "Étape 5: En cas de valeur critique, documentez la notification au clinicien.",
            "Étape 6: Cliquez Valider et confirmez.",
            "Étape 7: Le statut passe de PENDING à VALIDATED.",
            "Étape 8: Le pathologiste autorise et libère vers le médecin.",
        ],
        'rw': [
            "Kugirango uemeze ibisubizo, kurikiza intambwe zikurikira.",
            "Intambwe ya 1: Fungura worklist cg shakisha umurwayi.",
            "Intambwe ya 2: Shakisha ibisubizo byari mu ntambwe ya PENDING.",
            "Intambwe ya 3: Reba neza igaciro, unit, n'urugero rw'aho bisanzwe.",
            "Intambwe ya 4: Reba inshamake y'AI.",
            "Intambwe ya 5: Niba hari agaciro gateye akaga, andika ko umuganga yamenyeshejwe.",
            "Intambwe ya 6: Kanda Validate ukemeze.",
            "Intambwe ya 7: Indangagaciro ihinduka VALIDATED.",
            "Intambwe ya 8: Pathologiste yemeza asohorora ku muganga.",
        ],
    },
    'reject_sample': {
        'en': [
            "To reject a sample, follow these steps.",
            "Step 1: Find the sample in the worklist by SID or patient name.",
            "Step 2: Click the reject button — the red X icon next to the sample.",
            "Step 3: Select the rejection reason from the list. Common reasons include: hemolysis, clotted sample, insufficient volume — called QNS — wrong tube type, unlabelled specimen, or exceeded time limit.",
            "Step 4: If needed, add additional notes in the text field.",
            "Step 5: Click Reject and Create Replacement. The system will automatically assign a new SID — for example, if the original was HEM-01, the replacement becomes HEM-02.",
            "Step 6: The same lab request barcode and billing are kept. This protects the patient from being charged twice.",
            "Step 7: Collect a new sample and print a new label with the replacement SID.",
            "Step 8: The rejection is logged in the sample rejection book for ISO 15189 audit purposes.",
        ],
        'fr': [
            "Pour rejeter un échantillon, suivez ces étapes.",
            "Étape 1: Trouvez l'échantillon dans le worklist.",
            "Étape 2: Cliquez le bouton rejeter — l'icône X rouge.",
            "Étape 3: Sélectionnez la raison du rejet: hémolyse, caillot, QNS, mauvais tube, non-étiqueté, délai dépassé.",
            "Étape 4: Ajoutez des notes si nécessaire.",
            "Étape 5: Cliquez Rejeter et Créer un Remplacement. Un nouveau SID est attribué automatiquement.",
            "Étape 6: Le même code-barre et la facturation sont conservés pour protéger le patient.",
            "Étape 7: Prélevez un nouvel échantillon et imprimez une nouvelle étiquette.",
            "Étape 8: Le rejet est enregistré dans le registre pour l'audit ISO 15189.",
        ],
        'rw': [
            "Kugirango uhakanye ingano, kurikiza intambwe zikurikira.",
            "Intambwe ya 1: Shakisha ingano mu worklist.",
            "Intambwe ya 2: Kanda buto yo guhakana — ikimenyetso X gitukura.",
            "Intambwe ya 3: Hitamo impamvu yo guhakana: amaraso yarangiye, ingano ni macye, tube itari yo, nta ntsinagamutwe.",
            "Intambwe ya 4: Ongeraho inyandiko nshya nimba bikenewe.",
            "Intambwe ya 5: Kanda Reject na Create Replacement. Sistema izaha SID nshya — nka HEM-01 iba HEM-02.",
            "Intambwe ya 6: Code-barre n'impushya bihora bimwe kugirango umurwayi atishyurwe kabiri.",
            "Intambwe ya 7: Fata ingano nshya usohore etiquette nshya.",
            "Intambwe ya 8: Guhakana kwandikwa mu gitabo cy'ISO 15189.",
        ],
    },
    'levey_jennings': {
        'en': [
            "The Levey-Jennings chart is used to monitor internal quality control over time.",
            "Step 1: Open Quality from the menu, then click Levey-Jennings Chart.",
            "Step 2: Select the department — for example, Biochemistry.",
            "Step 3: Select the analyte — for example, Glucose.",
            "Step 4: Select the control level — Level 1 is low, Level 2 is normal, Level 3 is high.",
            "Step 5: Choose the time period — 7, 14, 30, 60, or 90 days.",
            "Step 6: Click Plot Chart. The system will display the chart with six reference lines: the mean, plus and minus 1 SD, plus and minus 2 SD, and plus and minus 3 SD.",
            "Step 7: Read the run decision at the top — ACCEPT means all Westgard rules passed.",
            "WARN means a 1-2s warning was triggered — check carefully before releasing patient results.",
            "REJECT means a rejection rule was violated — do NOT release patient results.",
            "Step 8: If rejected, check the Violations panel below the chart to see which Westgard rule was broken and the recommended corrective action.",
            "Step 9: Add a new QC run by clicking Add QC Run to enter today's control value.",
            "Step 10: Download the chart as PNG for your QC records using the Export PNG button.",
        ],
        'fr': [
            "Le graphique Levey-Jennings surveille le contrôle qualité interne dans le temps.",
            "Étape 1: Ouvrez Qualité puis cliquez sur Graphique Levey-Jennings.",
            "Étape 2: Sélectionnez le département.",
            "Étape 3: Sélectionnez l'analyte.",
            "Étape 4: Sélectionnez le niveau de contrôle.",
            "Étape 5: Choisissez la période.",
            "Étape 6: Cliquez Tracer le Graphique.",
            "Étape 7: Lisez la décision: ACCEPT, WARN ou REJECT.",
            "Étape 8: En cas de REJECT, consultez le panneau des violations.",
            "Étape 9: Ajoutez une nouvelle valeur QC avec Ajouter une Mesure QC.",
            "Étape 10: Exportez en PNG pour vos archives qualité.",
        ],
        'rw': [
            "Grafike ya Levey-Jennings ikurikirana inyakuri z'ubwiza bw'ibikorwa by'imbere.",
            "Kanda Quality mu menu, ubukurikire ubukurikire ukande Levey-Jennings Chart.",
            "Hitamo icyiciro, analyte, urwego rw'uburinzi, n'igihe.",
            "Kanda Plot Chart kugirango usohore grafike.",
            "Soma icyemezo cy'uruzinduko: ACCEPT bivuze byose byanyuze, WARN bivuze bisabwa kugenzura, REJECT bivuze ntuzosohore ibisubizo by'abarwayi.",
        ],
    },
    'blood_bank': {
        'en': [
            "Here is how to use the Blood Bank module.",
            "Step 1: Open Blood Bank from the sidebar.",
            "Step 2: To view current stock, click Blood Group Stock. You will see available units per ABO and Rh group.",
            "Step 3: To register a donor, click Donors then Register New Donor. Enter the donor's details and blood group.",
            "Step 4: After donation, collect the blood bag and set its status to Quarantine until screening tests are complete.",
            "Step 5: When all screening tests — HIV, Hepatitis B, Hepatitis C, Syphilis — are negative, change status to Available.",
            "Step 6: For a blood request from a ward, click Blood Requests then New Request. Enter patient details, required blood group, component — PRBC, FFP, Platelets — and clinical indication.",
            "Step 7: To perform crossmatch, find the patient and compatible bag. Record the crossmatch result — compatible or incompatible.",
            "Step 8: Click Issue Blood to issue a compatible bag to the patient. The system will warn you if there is a blood group mismatch.",
            "Step 9: During transfusion, monitor the patient every 15 minutes. Report any adverse reactions immediately using Haemovigilance.",
            "Step 10: After transfusion is complete, record it in the system and update bag status to Transfused.",
        ],
    },
}

# ── System help answers ───────────────────────────────────────────────────────

SYSTEM_HELP = {
    'what can you do': {
        'en': (
            "I am NEXUS, your voice AI assistant for ALIS-X. "
            "I can navigate to any module in the system, guide you through workflows step by step, "
            "explain lab procedures, answer questions about test interpretation, "
            "and help you understand quality control rules. "
            "Just say the name of a module like 'Open Hematology' or ask me 'How do I receive a sample?'"
        ),
        'fr': (
            "Je suis NEXUS, votre assistant vocal pour ALIS-X. "
            "Je peux naviguer vers n'importe quel module, vous guider étape par étape, "
            "expliquer les procédures de laboratoire et répondre aux questions. "
            "Dites simplement le nom d'un module ou posez une question."
        ),
        'rw': (
            "Ndi NEXUS, umufasha wawe w'ijwi kuri ALIS-X. "
            "Nshobora gufungura umuryango uwo ari wo wose, nkujyane intambwe ku ntambwe mu mirimo, "
            "nsobanure amabwiriza y'ubushakashatsi bw'amaraso, kandi nsubize ibibazo. "
            "Vuga izina ry'icyiciro nka 'Fungura Hematology' cg ubaze ikibazo."
        ),
    },
    'sid': {
        'en': "SID stands for Specimen ID. It is a unique identifier assigned to each tube or specimen type collected for a lab request. Format: 3-letter specimen code dash 2-digit number. For example: HEM-01 for the first EDTA tube, SER-01 for the first serum tube. If a sample is rejected and a replacement is needed, the number increments to HEM-02. The SID resets to 01 for each new lab request or each new day.",
        'rw': "SID ni Specimen ID, ni nimero ipanga ingano buri bwoko bwangana mu isaba ry'ibizamini. Imiterere: inyuguti 3 z'ubwoko bw'ingano ukurikije inomero 2. Urugero: HEM-01 ni tube ya mbere y'EDTA, SER-01 ni serum ya mbere. Niba ingano yahakanywe, inomero ikuze itandukana — HEM-02. SID itsinda kuri 01 igihe request nshya cyangwa umunsi mushya.",
    },
    'westgard rules': {
        'en': (
            "Westgard rules are 6 statistical rules used in quality control to decide if an analytical run should be accepted or rejected. "
            "The 1-2s rule: a warning when one QC result exceeds plus or minus 2 standard deviations. "
            "The 1-3s rule: reject the run when one result exceeds plus or minus 3 standard deviations. "
            "The 2-2s rule: reject when two consecutive results exceed the same plus or minus 2 SD limit. "
            "The R-4s rule: reject when the range between two consecutive results exceeds 4 standard deviations. "
            "The 4-1s rule: reject when four consecutive results are on the same side of the mean beyond plus or minus 1 SD. "
            "The 10-x rule: reject when ten consecutive results fall on the same side of the mean. "
            "If any rejection rule is violated, do NOT release patient results until the issue is resolved."
        ),
    },
    'iso 15189': {
        'en': (
            "ISO 15189 is the international standard for medical laboratory quality and competence. "
            "It covers: pre-analytical quality — proper sample collection and handling; "
            "analytical quality — accurate testing with validated methods and quality control; "
            "and post-analytical quality — correct interpretation, reporting, and record keeping. "
            "Key requirements include: documented SOPs for all procedures, internal QC with Levey-Jennings charts, "
            "external QA participation, critical value notification, sample rejection documentation, "
            "and regular staff competency assessments."
        ),
    },
    'critical value': {
        'en': (
            "A critical value is a result so far outside the normal range that it may be life-threatening and requires immediate clinical action. "
            "Common critical values include: Potassium below 2.8 or above 6.5 millimoles per liter, "
            "Sodium below 120 or above 160, Glucose below 2.2 or above 22 millimoles per liter, "
            "Haemoglobin below 7 grams per deciliter, and Troponin elevated in the context of chest pain. "
            "When you see a critical value in NEXUS — shown with HH or LL flag — you must: "
            "immediately notify the responsible clinician by phone, document the call in the system, "
            "and record that the clinician confirmed understanding by reading back the value. "
            "This is required by ISO 15189."
        ),
    },
    'malaria gefs': {
        'en': (
            "GE stands for Goutte Épaisse in French, meaning thick blood smear. "
            "FS stands for Frottis Sanguin, meaning thin blood smear. "
            "Together, GE and FS are the gold standard for malaria diagnosis. "
            "The thick smear concentrates parasites for detection and species identification. "
            "The thin smear allows precise species identification and parasitemia counting. "
            "Stain with Giemsa or Field's stain. "
            "Plasmodium falciparum shows ring forms with a double chromatin dot, banana-shaped gametocytes, and no Schüffner dots. "
            "Plasmodium vivax shows enlarged red blood cells with Schüffner dots and amoeboid trophozoites. "
            "Report parasitemia as a percentage of infected red blood cells."
        ),
    },
    'mentzer index': {
        'en': (
            "The Mentzer Index is used to differentiate iron deficiency anaemia from thalassaemia when both present with microcytic hypochromic anaemia. "
            "It is calculated as MCV divided by RBC count. "
            "A value less than 13 suggests thalassaemia — because in thalassaemia, the RBC count is relatively high despite low MCV. "
            "A value greater than 13 suggests iron deficiency anaemia — because iron deficiency causes a greater reduction in red cell number. "
            "Confirm with ferritin levels and haemoglobin electrophoresis."
        ),
    },
}

# ── Command intent parser ─────────────────────────────────────────────────────

NAVIGATION_TRIGGERS = [
    'open', 'go to', 'navigate to', 'show me', 'take me to',
    'fungura', 'jya', 'ouvre', 'ouvrir', 'aller à',
]

WORKFLOW_TRIGGERS = {
    'receive_sample':    ['receive sample', 'receive', 'reception', 'take sample', 'collect sample',
                          'gukira ingano', 'reception y\'ingano', 'réceptionner'],
    'enter_result':      ['enter result', 'enter results', 'input result', 'add result',
                          'shyiramo ibisubizo', 'saisir résultat', 'saisie'],
    'validate_result':   ['validate', 'validation', 'validate result', 'emeza', 'valider'],
    'reject_sample':     ['reject', 'rejection', 'guhakana', 'rejeter', 'refuser'],
    'levey_jennings':    ['levey jennings', 'levey-jennings', 'qc chart', 'quality chart', 'control chart'],
    'blood_bank':        ['blood bank', 'transfusion', 'blood', 'banki y\'amaraso', 'banque du sang'],
}

HELP_TRIGGERS = {
    'what can you do':   ['what can you do', 'help', 'capabilities', 'functions', 'irya ushobora', 'aide'],
    'sid':               ['what is sid', 'explain sid', 'specimen id', 'ibisobanuro bya sid'],
    'westgard rules':    ['westgard', 'qc rules', 'quality rules', 'amabwiriza ya westgard'],
    'iso 15189':         ['iso 15189', 'quality standard', 'iso standard', 'uburenganzira bw\'ubwiza'],
    'critical value':    ['critical value', 'critical result', 'agaciro gasumba', 'valeur critique', 'critical'],
    'malaria gefs':      ['malaria', 'thick smear', 'thin smear', 'ge fs', 'gefs', 'malaria test'],
    'mentzer index':     ['mentzer', 'iron deficiency', 'thalassaemia', 'thalassemia', 'microcytic'],
}


def parse_command(text: str, lang: str = 'en') -> dict:
    """
    Parse a voice command and return the action to take.
    Returns: {type, action, target, response_text, navigate_to, guide_topic, lang}
    """
    text_lower = text.lower().strip()
    detected_lang = _detect_lang(text_lower) or lang

    # 1. Navigation commands
    for trigger in NAVIGATION_TRIGGERS:
        if trigger in text_lower:
            remainder = text_lower.replace(trigger, '').strip()
            for key, (url, confirm) in NAVIGATION_MAP.items():
                if key in remainder:
                    return {
                        'type': 'navigate',
                        'navigate_to': url,
                        'response_text': confirm,
                        'lang': detected_lang,
                    }

    # Direct module name (without trigger)
    for key, (url, confirm) in NAVIGATION_MAP.items():
        if key == text_lower or text_lower.endswith(key):
            return {
                'type': 'navigate',
                'navigate_to': url,
                'response_text': confirm,
                'lang': detected_lang,
            }

    # 2. Workflow guides
    for topic, triggers in WORKFLOW_TRIGGERS.items():
        if any(t in text_lower for t in triggers):
            guide = WORKFLOW_GUIDES.get(topic, {})
            steps = guide.get(detected_lang, guide.get('en', []))
            return {
                'type': 'guide',
                'guide_topic': topic,
                'steps': steps,
                'response_text': steps[0] if steps else 'Starting guidance.',
                'all_steps': steps,
                'lang': detected_lang,
            }

    # 3. Help / knowledge base
    for topic, triggers in HELP_TRIGGERS.items():
        if any(t in text_lower for t in triggers):
            answer = SYSTEM_HELP.get(topic, {})
            text_answer = answer.get(detected_lang, answer.get('en', ''))
            if isinstance(answer, str):
                text_answer = answer
            return {
                'type': 'answer',
                'topic': topic,
                'response_text': text_answer or 'I do not have information on that topic yet.',
                'lang': detected_lang,
            }

    # 4. Repeat last (accessibility)
    if any(t in text_lower for t in ['repeat', 'again', 'powtórz', 'ongera', 'répéter']):
        return {'type': 'repeat', 'lang': detected_lang}

    # 5. Stop/cancel
    if any(t in text_lower for t in ['stop', 'cancel', 'silence', 'tace', 'hagarara', 'arrête']):
        return {'type': 'stop', 'response_text': '', 'lang': detected_lang}

    # 6. Unknown — forward to AI
    return {
        'type': 'ai_query',
        'query': text,
        'lang': detected_lang,
        'response_text': _fallback_response(text_lower, detected_lang),
    }


def _detect_lang(text: str) -> Optional[str]:
    """Detect language from command text."""
    rw_words = ['fungura', 'kanda', 'jya', 'guhakana', 'ingano', 'ibisubizo', 'emeza', 'shakisha']
    fr_words  = ['ouvre', 'aller', 'valider', 'rejeter', 'saisir', 'étape', 'résultat']
    if any(w in text for w in rw_words): return 'rw'
    if any(w in text for w in fr_words): return 'fr'
    return None


def _fallback_response(text: str, lang: str) -> str:
    fallbacks = {
        'en': f"I heard: {text}. I can help you navigate the system, guide you through workflows, or answer lab questions. Try saying: 'Open Hematology', 'How do I receive a sample?', or 'What is a critical value?'",
        'fr': f"J'ai entendu: {text}. Je peux vous aider à naviguer, guider les flux de travail, ou répondre aux questions. Essayez: 'Ouvrir Hématologie' ou 'Comment recevoir un échantillon?'",
        'rw': f"Numvise: {text}. Nshobora gufasha gufungura ibice, kukujyana intambwe ku ntambwe, cg gusubiza ibibazo. Gerageza kuvuga: 'Fungura Hematology' cg 'Nshobora gute gukiria ingano?'",
    }
    return fallbacks.get(lang, fallbacks['en'])


def get_greeting(lang: str = 'en') -> str:
    """Return wake-word activation greeting."""
    greetings = {
        'en': "NEXUS is listening. How can I help you?",
        'fr': "NEXUS vous écoute. Comment puis-je vous aider?",
        'rw': "NEXUS ikumva. Ngire iki nakugiriye?",
    }
    return greetings.get(lang, greetings['en'])


def get_idle_prompt(lang: str = 'en') -> str:
    """Prompt shown when system is idle — reminds staff voice is available."""
    prompts = {
        'en': "Say 'NEXUS' to activate voice control.",
        'fr': "Dites 'NEXUS' pour activer le contrôle vocal.",
        'rw': "Vuga 'NEXUS' kugirango utangire uburinzi bw'ijwi.",
    }
    return prompts.get(lang, prompts['en'])
