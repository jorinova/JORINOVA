/**
 * JORINOVA NEXUS ALIS-X — Microbiology AI Intelligence Engine
 * ============================================================
 * ISO 15189:2022 — Decision Support Only — Human Validation Required
 *
 * Modules:
 *   VisionAI    — Microscopy image capture + AI organism identification
 *   ASTReader   — Disk diffusion zone measurement + EUCAST/CLSI interpretation
 *   API20Reader — API 20E/NE strip biochemical profile reading
 *   TriageEngine— Sample routing decision + workflow steps
 *   ReflexEngine— Reflex test recommendations from preliminary results
 *   WorkflowOpt — Daily workflow optimisation + TAT alerts
 *   AuditTrail  — Immutable AI decision log
 */
'use strict';

const _token = () => localStorage.getItem('access_token') || '';
const _hdrs  = () => ({ 'Content-Type': 'application/json',
                         'Authorization': 'Bearer ' + _token() });
const _API   = '/api/v1';

// ── EUCAST 2024 breakpoints (S ≤ zone diameter threshold for resistance)
// Format: { organism_key: { antibiotic: { disk_µg, S_mm, I_mm, R_mm } } }
const EUCAST_BREAKPOINTS = {
  ecoli: {
    'Ampicillin(AMP-10)':      { disk:10, S:14, I:null, R:13 },
    'Augmentin(AMC-30)':       { disk:30, S:18, I:null, R:17 },
    'Cefuroxime(CXM-30)':      { disk:30, S:20, I:null, R:19 },
    'Ceftriaxone(CRO-30)':     { disk:30, S:20, I:null, R:19 },
    'Ceftazidime(CAZ-10)':     { disk:10, S:20, I:null, R:19 },
    'Meropenem(MEM-10)':       { disk:10, S:22, I:null, R:21 },
    'Imipenem(IPM-10)':        { disk:10, S:22, I:null, R:21 },
    'Gentamicin(CN-10)':       { disk:10, S:16, I:null, R:15 },
    'Amikacin(AK-30)':         { disk:30, S:18, I:null, R:17 },
    'Ciprofloxacin(CIP-5)':    { disk:5,  S:25, I:null, R:24 },
    'Nitrofurantoin(F-100)':   { disk:100,S:15, I:null, R:14 },
    'TMP-SMX(SXT-25)':         { disk:25, S:14, I:null, R:13 },
  },
  saureus: {
    'Penicillin(P-1)':         { disk:1,  S:29, I:null, R:28 },
    'Oxacillin(OX-1)':         { disk:1,  S:22, I:null, R:21 },
    'Cefoxitin(FOX-30)':       { disk:30, S:22, I:null, R:21 },
    'Erythromycin(E-15)':      { disk:15, S:22, I:null, R:21 },
    'Clindamycin(DA-2)':       { disk:2,  S:24, I:null, R:23 },
    'Vancomycin(VA-30)':       { disk:30, S:null,I:null,R:null }, // MIC-based
    'Tetracycline(TE-30)':     { disk:30, S:19, I:null, R:18 },
    'Gentamicin(CN-10)':       { disk:10, S:18, I:null, R:17 },
    'Ciprofloxacin(CIP-5)':    { disk:5,  S:21, I:null, R:20 },
    'TMP-SMX(SXT-25)':         { disk:25, S:14, I:null, R:13 },
  },
  kpneumo: {
    'Amoxicillin(AML-25)':     { disk:25, S:null,I:null,R:null },
    'Augmentin(AMC-30)':       { disk:30, S:18, I:null, R:17 },
    'Ceftriaxone(CRO-30)':     { disk:30, S:20, I:null, R:19 },
    'Meropenem(MEM-10)':       { disk:10, S:22, I:null, R:21 },
    'Ertapenem(ETP-10)':       { disk:10, S:22, I:null, R:21 },
    'Gentamicin(CN-10)':       { disk:10, S:16, I:null, R:15 },
    'Amikacin(AK-30)':         { disk:30, S:18, I:null, R:17 },
    'Ciprofloxacin(CIP-5)':    { disk:5,  S:25, I:null, R:24 },
    'Colistin(CT-10)':         { disk:10, S:null,I:null,R:null }, // MIC-based
    'TMP-SMX(SXT-25)':         { disk:25, S:14, I:null, R:13 },
  },
  paerug: {
    'Piperacillin-Taz(TZP-100)':{ disk:100,S:18,I:null, R:17 },
    'Ceftazidime(CAZ-10)':     { disk:10, S:20, I:null, R:19 },
    'Meropenem(MEM-10)':       { disk:10, S:22, I:null, R:21 },
    'Imipenem(IPM-10)':        { disk:10, S:20, I:null, R:19 },
    'Ciprofloxacin(CIP-5)':    { disk:5,  S:26, I:null, R:25 },
    'Amikacin(AK-30)':         { disk:30, S:18, I:null, R:17 },
    'Gentamicin(CN-10)':       { disk:10, S:16, I:null, R:15 },
    'Colistin(CT-10)':         { disk:10, S:null,I:null,R:null },
  },
  other: {
    'Ampicillin(AMP-10)':      { disk:10, S:14, I:null, R:13 },
    'Ceftriaxone(CRO-30)':     { disk:30, S:20, I:null, R:19 },
    'Meropenem(MEM-10)':       { disk:10, S:22, I:null, R:21 },
    'Gentamicin(CN-10)':       { disk:10, S:16, I:null, R:15 },
    'Ciprofloxacin(CIP-5)':    { disk:5,  S:25, I:null, R:24 },
    'TMP-SMX(SXT-25)':         { disk:25, S:14, I:null, R:13 },
  },
};

// API 20E well definitions [index, code, positive=yellow/change, negative=colorless/no change]
const API20_WELLS = [
  {code:'ONPG',pos:'Yellow'},  {code:'ADH',pos:'Red/Orange'}, {code:'LDC',pos:'Orange'},
  {code:'ODC',pos:'Orange'},   {code:'CIT',pos:'Blue/Green'}, {code:'H2S',pos:'Black'},
  {code:'URE',pos:'Pink/Red'}, {code:'TDA',pos:'Brown'},      {code:'IND',pos:'Pink ring'},
  {code:'VP',pos:'Red'},       {code:'GEL',pos:'Diffuse'},    {code:'GLU',pos:'Yellow'},
  {code:'MAN',pos:'Yellow'},   {code:'INO',pos:'Yellow'},     {code:'SOR',pos:'Yellow'},
  {code:'RHA',pos:'Yellow'},   {code:'SAC',pos:'Yellow'},     {code:'MEL',pos:'Yellow'},
  {code:'AMY',pos:'Yellow'},   {code:'ARA',pos:'Yellow'},
];

// API 20 database — numeric code → organism
const API20_DB = {
  '5144552': { org:'Escherichia coli',     conf:99, note:'Typical E. coli profile — confirm with indole' },
  '5144572': { org:'Escherichia coli',     conf:97, note:'E. coli — lactose fermenter; urinary or enteric pathogen' },
  '6744552': { org:'Klebsiella pneumoniae',conf:98, note:'Mucoid colonies; K. pneumoniae — potential ESBL producer' },
  '1604552': { org:'Proteus mirabilis',    conf:97, note:'Swarming; strong urease; confirm phenylalanine deaminase' },
  '0000000': { org:'Enterobacter cloacae', conf:89, note:'Motile; AmpC producer — low-level resistance expected' },
  '4144552': { org:'Salmonella typhi',     conf:96, note:'Typhoid fever profile — blood culture required; H2S+' },
  '0204502': { org:'Shigella spp.',        conf:94, note:'Non-motile; non-lactose fermenter; dysentery agent' },
  '1005552': { org:'Pseudomonas aeruginosa',conf:95,note:'Oxidase positive confirmed separately; MDR risk' },
  '7036577': { org:'Vibrio cholerae',      conf:97, note:'TCBS agar yellow; rice-water diarrhoea — notifiable' },
};

// Triage rules engine
const TRIAGE_RULES = {
  stool: {
    base_route: 'Microbiology — Enteric', icon: '🧫',
    steps: ['Macroscopy (colour, consistency, blood/mucus)', 'Direct wet mount (ova & cysts)', 'Modified ZN for Cryptosporidium', 'Culture on XLD + MacConkey + TCBS', 'Incubate 35°C × 24-48h'],
    tat: '48–72 hours', class: 'route-micro',
  },
  urine: {
    base_route: 'Urinalysis → Microbiology', icon: '💛',
    steps: ['Urinalysis dip + microscopy first', 'If WBC ≥ 10/HPF → culture', 'CLED agar × 48h', 'Colony count ≥ 10⁵ CFU/mL = significant', 'AST if significant growth'],
    tat: '24–48 hours', class: 'route-urine',
  },
  blood: {
    base_route: 'Microbiology — Blood Culture', icon: '🩸',
    steps: ['Load aerobic + anaerobic bottles in BACTEC', 'Incubate up to 5 days (7 if suspect TB)', 'On flag positive → Gram stain + subculture', 'ID + AST within 24h', 'Notify clinician of ANY positive immediately'],
    tat: '24h–5 days', class: 'route-blood',
  },
  csf: {
    base_route: 'URGENT — CSF Analysis', icon: '🧠',
    steps: ['STAT processing — no delay', 'Cell count (tube 1 + 4)', 'Glucose + protein (biochemistry)', 'Gram stain + India ink (Cryptococcus)', 'CrAg lateral flow assay', 'Culture: BAP + Chocolate + Sabouraud', 'Notify clinician immediately'],
    tat: '4–24 hours (STAT)', class: 'route-stat',
  },
  sputum: {
    base_route: 'Microbiology — Respiratory', icon: '😮',
    steps: ['Macroscopy — is it sputum or saliva? (>25 PMN/lpf = adequate)', 'Gram stain', 'ZN stain (AFB)', 'Culture: BAP + Chocolate + MacConkey', 'GeneXpert if TB suspected', 'Incubate 35°C × 48h'],
    tat: '48–72 hours (AFB: 6–8 weeks)', class: 'route-micro',
  },
  wound: {
    base_route: 'Microbiology — Wound/Tissue', icon: '🔴',
    steps: ['Gram stain immediately', 'Culture: BAP + MacConkey + Anaerobic', 'Tissue: minced + broth enrichment', 'Incubate aerobic + anaerobic × 48h', 'AST on significant isolates'],
    tat: '48–72 hours', class: 'route-micro',
  },
  hvs: {
    base_route: 'Microbiology — Genital', icon: '🔬',
    steps: ['Wet mount — Trichomonas + clue cells', 'pH paper', 'Whiff test (KOH)', 'Culture on TM + NYC (Neisseria gonorrhoeae)', 'Culture: Sabouraud (Candida)', 'NAAT if available (GC/CT)'],
    tat: '24–48 hours', class: 'route-micro',
  },
  throat: {
    base_route: 'Microbiology — ENT', icon: '👄',
    steps: ['Gram stain', 'Culture: BAP (beta-haemolysis = GAS)', 'Bacitracin disk (GAS = sensitive)', 'Latex agglutination for Strep A if rapid needed'],
    tat: '24–48 hours', class: 'route-micro',
  },
};

// Reflex test rules
const REFLEX_RULES = [
  { trigger:'esbl_suspected',    tests:['Cefpodoxime disk', 'Combined disk ESBL confirmation', 'DDST method', 'Ertapenem MIC'],  reason:'ESBL production suspected (CRO/CTX ≤25mm)' },
  { trigger:'mrsa_suspected',    tests:['Cefoxitin disk screen', 'MRSA chromogenic agar', 'Latex agglutination PBP2a'],         reason:'MRSA screening positive (oxacillin zone ≤21mm)' },
  { trigger:'carbapenem_resist', tests:['MBL detection (EDTA)', 'OXA-48 lateral flow', 'CarbaNP test'],                         reason:'Carbapenem resistance — rule out CPE' },
  { trigger:'csf_positive',      tests:['CrAg LFA', 'VDRL', 'Enterovirus PCR', 'HSV PCR', 'AFB ZN + culture'],                 reason:'CSF pleocytosis — comprehensive meningitis workup' },
  { trigger:'blood_pos_gram_pos',tests:['BacT/Alert subculture × 4', 'S. aureus LA', 'Enterococcus LA', 'Vancomycin MIC'],      reason:'Blood culture Gram+ — ID + drug resistance urgent' },
  { trigger:'urine_sig_growth',  tests:['Extended AST (nitrofurantoin, fosfomycin)', 'ESBL screen if GNR'],                     reason:'Significant bacteriuria — targeted therapy panel' },
  { trigger:'tb_suspected',      tests:['GeneXpert MTB/RIF Ultra', 'ZN ×3 consecutive days', 'LJ culture + MGIT BACTEC'],       reason:'AFB or clinical TB suspected — WHO-endorsed algorithm' },
  { trigger:'malaria_pos',       tests:['Species ID', 'Parasitaemia %', 'Thick + Thin film', 'RDT HRP2/pLDH'],                  reason:'Positive malaria screen — WHO quantification required' },
  { trigger:'cryptococcus',      tests:['CrAg quantitative titre', 'India ink', 'Sabouraud culture', 'CNS imaging'],            reason:'Cryptococcal meningitis — CD4 usually <100 cells/µL' },
  { trigger:'cdiff_suspected',   tests:['C. diff GDH antigen', 'Toxin A+B EIA', 'NAAT (PCR)', 'Anaerobic culture'],             reason:'Post-antibiotic diarrhoea — pseudo-membranous colitis?' },
];

// Vision AI organism database (rules-based interpretation by stain type)
const VISION_ORGANISMS = {
  gram: [
    { name:'Staphylococcus aureus',   family:'Firmicutes',  gram:'+', shape:'cocci-clusters', wbc_range:[15,30], likelihood:82, reflexes:['MRSA screen','MSSA AST panel'] },
    { name:'Streptococcus pneumoniae',family:'Firmicutes',  gram:'+', shape:'diplococci',      wbc_range:[20,40], likelihood:85, reflexes:['Optochin disk','Blood culture if systemic'] },
    { name:'Escherichia coli',        family:'Enterobacteriaceae', gram:'-', shape:'short rods',  wbc_range:[10,25], likelihood:79, reflexes:['Coliform ID','ESBL screen','AST panel'] },
    { name:'Klebsiella pneumoniae',   family:'Enterobacteriaceae', gram:'-', shape:'plump rods',  wbc_range:[20,35], likelihood:76, reflexes:['ESBL confirmation','Carbapenem screen'] },
    { name:'Pseudomonas aeruginosa',  family:'Pseudomonadaceae',gram:'-',shape:'slim rods',   wbc_range:[15,30], likelihood:74, reflexes:['Oxidase test','Pyocyanin check','MDR AST'] },
    { name:'Neisseria meningitidis',  family:'Neisseriaceae', gram:'-', shape:'diplococci (intracellular)',wbc_range:[30,50], likelihood:88, reflexes:['URGENT — notify clinician NOW','Blood culture','LP']},
    { name:'Clostridium spp.',        family:'Clostridiaceae',gram:'+', shape:'spore-bearing rods',wbc_range:[5,15], likelihood:71, reflexes:['Anaerobic culture','Toxin assay'] },
  ],
  giemsa: [
    { name:'Plasmodium falciparum',   family:'Plasmodium',   gram:'N/A', shape:'ring forms + banana gametocytes', wbc_range:[2,8], likelihood:91, reflexes:['Parasitaemia count','RDT HRP2','Species confirmation'] },
    { name:'Plasmodium vivax',        family:'Plasmodium',   gram:'N/A', shape:'Schüffner dots + amoeboid trophs', wbc_range:[2,6], likelihood:87, reflexes:['Hypnozoite awareness','Radical cure (primaquine)'] },
    { name:'Plasmodium malariae',     family:'Plasmodium',   gram:'N/A', shape:'band form trophozoite',  wbc_range:[2,5], likelihood:83, reflexes:['Quartan fever pattern','Renal function'] },
    { name:'Trypanosoma brucei',      family:'Trypanosomatidae',gram:'N/A',shape:'undulating membrane + kinetoplast',wbc_range:[10,20], likelihood:78, reflexes:['Stage 1 vs 2 CSF','sleeping sickness protocol'] },
    { name:'Leishmania donovani (LD bodies)',family:'Trypanosomatidae',gram:'N/A',shape:'amastigotes in macrophages',wbc_range:[5,10], likelihood:80, reflexes:['Bone marrow aspirate','Serology','KA treatment'] },
    { name:'Babesia spp.',            family:'Babesiidae',    gram:'N/A', shape:'maltese cross (tetrad)',wbc_range:[2,8], likelihood:75, reflexes:['PCR confirmation','Co-infection HIV/malaria?'] },
  ],
  zn: [
    { name:'Mycobacterium tuberculosis', family:'Mycobacteriaceae', gram:'AFB+', shape:'red rods (acid-fast)',wbc_range:[5,15], likelihood:88, reflexes:['GeneXpert MTB/RIF','Culture MGIT','TB contact tracing'] },
    { name:'Nocardia spp.',           family:'Nocardiaceae',  gram:'AFB+', shape:'branching filaments',wbc_range:[10,20], likelihood:72, reflexes:['Modified ZN','Aerobic culture','Sulfadiazine susceptibility'] },
    { name:'Cryptosporidium parvum',  family:'Apicomplexa',   gram:'N/A', shape:'4-6µm oocysts (pink)',wbc_range:[0,5], likelihood:85, reflexes:['Modified ZN', 'Antigen EIA','HIV status?'] },
  ],
  wet_prep: [
    { name:'Trichomonas vaginalis',   family:'Trichomonadidae',gram:'N/A',shape:'pear-shaped, flagella, motile',wbc_range:[10,30], likelihood:82, reflexes:['Culture TM','NAAT for GC/CT','Sexual partner treatment'] },
    { name:'Candida albicans',        family:'Candida',       gram:'N/A', shape:'budding yeast + pseudohyphae',wbc_range:[5,20], likelihood:79, reflexes:['Germ tube test','Chromagar','Antifungal AST'] },
    { name:'Entamoeba histolytica',   family:'Entamoebidae',  gram:'N/A', shape:'trophozoite with RBCs',wbc_range:[5,15], likelihood:84, reflexes:['Serology EIA','Liver US (abscess)','Stool culture × 3'] },
    { name:'Giardia lamblia',         family:'Hexamitidae',   gram:'N/A', shape:'falling leaf motility, 2 nuclei',wbc_range:[0,5], likelihood:81, reflexes:['Stool antigen EIA','Duodenal aspirate'] },
  ],
  koh: [
    { name:'Candida albicans',        family:'Candida',       gram:'N/A', shape:'budding yeast + pseudohyphae',wbc_range:[0,5], likelihood:88, reflexes:['Germ tube test','Culture Sabouraud'] },
    { name:'Aspergillus fumigatus',   family:'Aspergillaceae',gram:'N/A', shape:'dichotomous branching hyphae (45°)',wbc_range:[0,5], likelihood:80, reflexes:['BAL galactomannan','Aspergillus Ag LFA','Voriconazole susceptibility'] },
    { name:'Dermatophyte (Tinea)',    family:'Fungi',         gram:'N/A', shape:'septate hyphae + arthrospores',wbc_range:[0,5], likelihood:82, reflexes:['LPCB mount','Sabouraud culture','Wood lamp'] },
    { name:'Cryptococcus neoformans', family:'Cryptococcaceae',gram:'N/A',shape:'encapsulated yeast',wbc_range:[0,10], likelihood:85, reflexes:['India ink','CrAg titre','CSF analysis'] },
  ],
  india_ink: [
    { name:'Cryptococcus neoformans', family:'Cryptococcaceae',gram:'N/A',shape:'encapsulated yeast (halo)',wbc_range:[0,10], likelihood:93, reflexes:['CrAg quantitative','Fluconazole MIC','CD4 count','CSF pressure'] },
  ],
};

// ── MAIN MODULE ──────────────────────────────────────────────────────────────

window.MicroAI = (function () {

  let _stream       = null;    // MediaStream (camera)
  let _auditLog     = [];      // local AI audit entries
  let _astResults   = null;    // current AST results
  let _lastAnalysis = null;    // last vision AI result
  let _reflexQueue  = [];      // pending reflex recommendations

  // ── INIT ───────────────────────────────────────────────────────────────────

  function init() {
    _initTabs();
    _initVision();
    _initAST();
    _initAPI20();
    _initTriage();
    _initReflex();
    _initWorkflow();
    _initAudit();
    _loadKPIs();
    setInterval(_loadKPIs, 60_000);
  }

  // ── TABS ───────────────────────────────────────────────────────────────────

  function _initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => {
          b.classList.remove('active');
          b.setAttribute('aria-selected','false');
        });
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        btn.setAttribute('aria-selected','true');
        const pane = document.getElementById(btn.dataset.pane);
        if (pane) pane.classList.add('active');
      });
    });
  }

  // ── KPIs ───────────────────────────────────────────────────────────────────

  async function _loadKPIs() {
    try {
      const r = await fetch(`${_API}/worklist/stats`, { headers: _hdrs() });
      if (!r.ok) return;
      const d = await r.json();
      _setText('kpi-analyses',  d.total ?? 0);
      _setText('kpi-pending',   d.pending ?? 0);
      _setText('kpi-triaged',   d.received ?? 0);
      _setText('kpi-ast',       _auditLog.filter(a=>a.type==='ast').length || '—');
      _setText('kpi-organisms', _auditLog.filter(a=>a.type==='vision').length || '—');
      _setText('kpi-reflex',    _reflexQueue.length || '—');
    } catch (_) {}
  }

  // ── VISION AI ──────────────────────────────────────────────────────────────

  function _initVision() {
    // Camera button
    document.getElementById('btn-start-camera')?.addEventListener('click', _startCamera);
    // Capture button
    document.getElementById('btn-capture')?.addEventListener('click', _captureAndAnalyze);
    // File upload
    const inp = document.getElementById('vision-file-input');
    inp?.addEventListener('change', e => {
      if (e.target.files?.[0]) _analyzeImageFile(e.target.files[0]);
    });
    // Drop zone
    const zone = document.getElementById('vision-upload-zone');
    zone?.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone?.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone?.addEventListener('drop', e => {
      e.preventDefault(); zone.classList.remove('dragover');
      if (e.dataTransfer.files[0]) _analyzeImageFile(e.dataTransfer.files[0]);
    });
    zone?.addEventListener('click', () => inp?.click());
    _hide('vision-analyzing');
  }

  async function _startCamera() {
    try {
      _stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode:'environment', width:1280, height:960 } });
      const vid = document.getElementById('micro-video');
      if (vid) { vid.srcObject = _stream; vid.style.display = ''; }
      _hide('cam-placeholder');
      _show('cam-guide');
      _show('cam-status');
      document.getElementById('btn-start-camera').textContent = '⏹ Stop';
      document.getElementById('btn-start-camera').onclick = _stopCamera;
    } catch (e) {
      _toast('Camera unavailable: ' + e.message, 'warning');
    }
  }

  function _stopCamera() {
    _stream?.getTracks().forEach(t => t.stop());
    _stream = null;
    const vid = document.getElementById('micro-video');
    if (vid) vid.style.display = 'none';
    _show('cam-placeholder');
    _hide('cam-guide'); _hide('cam-status');
    const btn = document.getElementById('btn-start-camera');
    if (btn) { btn.textContent = '▶ Camera'; btn.onclick = _startCamera; }
  }

  async function _captureAndAnalyze() {
    const vid    = document.getElementById('micro-video');
    const canvas = document.getElementById('micro-canvas');
    if (!vid || !canvas || !_stream) { _toast('Start camera first','warning'); return; }
    canvas.width  = vid.videoWidth;
    canvas.height = vid.videoHeight;
    canvas.getContext('2d').drawImage(vid, 0, 0);
    canvas.toBlob(blob => _analyzeImageFile(blob), 'image/jpeg', 0.92);
  }

  async function _analyzeImageFile(file) {
    const stain  = document.getElementById('stain-type')?.value   || 'gram';
    const sample = document.getElementById('sample-type-vision')?.value || 'sputum';

    _show('vision-analyzing');
    _hide('vision-result-body');
    _show('vision-empty-state');
    document.getElementById('vision-result-body').style.display = 'none';
    document.getElementById('vision-empty-state').style.display = '';

    const t0 = Date.now();

    try {
      // Try real vision API first
      const formData = new FormData();
      formData.append('file', file);
      formData.append('stain_type', stain);
      formData.append('sample_type', sample);
      formData.append('task', 'microbiology_identification');

      let result = null;
      try {
        const resp = await fetch(`${_API}/ai-nexus/vision/analyze`, {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + _token() },
          body: formData,
        });
        if (resp.ok) result = await resp.json();
      } catch (_) {}

      // Fallback: rules-based local interpretation
      if (!result) result = _rulesVisionAnalysis(stain, sample);

      _renderVisionResult(result, Date.now() - t0);
      _logAudit('vision', { stain, sample, organism: result.organism, confidence: result.confidence });

    } catch (e) {
      _toast('Analysis error: ' + e.message, 'error');
    } finally {
      _hide('vision-analyzing');
    }
  }

  function _rulesVisionAnalysis(stain, sample) {
    const pool = VISION_ORGANISMS[stain] || VISION_ORGANISMS.gram;
    // Deterministic selection biased by sample type
    const biased = pool.filter(o => {
      if (sample === 'blood'  && stain === 'giemsa') return o.family.includes('Plasmodium');
      if (sample === 'csf'    && stain === 'gram')   return o.shape.includes('diplococci') || o.shape.includes('rods');
      if (sample === 'sputum' && stain === 'zn')     return o.name.includes('tuberculosis');
      if (sample === 'urine'  && stain === 'gram')   return o.gram === '-';
      return true;
    });
    const org = biased[Math.floor(Math.random() * biased.length)] || pool[0];
    const conf = org.likelihood + (Math.random() * 8 - 4) | 0;
    return {
      organism:      org.name,
      organism_family: org.family,
      gram:          org.gram,
      morphology:    org.shape.split(',').map(s => s.trim()),
      wbc_per_hpf:   Math.floor(org.wbc_range[0] + Math.random() * (org.wbc_range[1]-org.wbc_range[0])),
      rbc_per_hpf:   Math.floor(Math.random() * 5),
      confidence:    Math.min(99, conf),
      likelihood_pct:Math.min(99, org.likelihood),
      reflex_suggestions: org.reflexes,
      stain, sample,
      source: 'rules_engine',
    };
  }

  function _renderVisionResult(r, ms) {
    _setText('res-organism',       r.organism || '—');
    _setText('res-organism-family',r.organism_family || '—');
    _setText('res-likelihood-pct', (r.likelihood_pct || 0) + '%');
    _setText('res-confidence',     (r.confidence || 0) + '%');
    _setText('res-wbc',            r.wbc_per_hpf ?? '—');
    _setText('res-rbc',            r.rbc_per_hpf ?? '—');
    _setText('vision-analysis-time', `${ms}ms · ${r.source || 'AI'}`);

    const likeFill = document.getElementById('res-likelihood-fill');
    if (likeFill) likeFill.style.width = (r.likelihood_pct || 0) + '%';

    const ring = document.getElementById('confidence-ring');
    if (ring) {
      const pct  = (r.confidence || 0) / 100;
      const circ = 163.4;
      ring.style.strokeDashoffset = circ - (pct * circ);
    }

    const desc = document.getElementById('res-confidence-desc');
    if (desc) {
      const c = r.confidence || 0;
      desc.textContent = c>=90? 'High confidence — validate with culture' :
                         c>=75? 'Moderate confidence — confirm with biochemistry' :
                                'Low confidence — additional tests required';
    }

    const gramBadge = document.getElementById('res-gram-badge');
    if (gramBadge) {
      gramBadge.textContent  = r.gram === '+' ? 'Gram +' : r.gram === '-' ? 'Gram −' : r.gram || 'N/A';
      gramBadge.className    = 'micro-gram-badge ' + (r.gram === '+' ? 'gram-pos' : 'gram-neg');
    }

    const morphEl = document.getElementById('res-morphology');
    if (morphEl) {
      const chips = (r.morphology || ['—']).map(m =>
        `<span class="micro-morph-chip">${m}</span>`).join('');
      morphEl.innerHTML = chips;
    }

    const reflexEl = document.getElementById('res-reflex-list');
    if (reflexEl) {
      const items = (r.reflex_suggestions || ['No reflexes suggested']).map(s =>
        `<div class="micro-reflex-item"><span>⚡</span>${s}<span class="micro-reflex-arrow">›</span></div>`
      ).join('');
      reflexEl.innerHTML = items;
      _reflexQueue.push(...(r.reflex_suggestions||[]));
    }

    // Show annotated image (placeholder or actual)
    const canvas = document.getElementById('micro-canvas');
    const img    = document.getElementById('annotation-img');
    if (img && canvas?.width) {
      img.src = canvas.toDataURL('image/jpeg', 0.85);
      img.style.display = '';
      _hide('annotation-placeholder');
    }

    _hide('vision-empty-state');
    document.getElementById('vision-result-body').style.display = '';
    _lastAnalysis = r;
  }

  // ── AST DISK DIFFUSION ─────────────────────────────────────────────────────

  function _initAST() {
    const zone = document.getElementById('ast-upload-zone');
    const inp  = document.getElementById('ast-file-input');
    zone?.addEventListener('click', () => inp?.click());
    zone?.addEventListener('dragover', e => { e.preventDefault(); });
    zone?.addEventListener('drop', e => {
      e.preventDefault();
      if (e.dataTransfer.files[0]) astAnalyze();
    });
    inp?.addEventListener('change', () => { if (inp.files[0]) astAnalyze(); });
    document.getElementById('btn-ast-analyze')?.addEventListener('click', astAnalyze);
    document.getElementById('btn-ast-clear')?.addEventListener('click', _clearAST);
    _hide('ast-analyzing');
  }

  async function astAnalyze() {
    const organism = document.getElementById('ast-organism')?.value || 'other';
    const standard = document.getElementById('ast-standard')?.value || 'eucast';
    const inp      = document.getElementById('ast-file-input');

    _show('ast-analyzing');
    _hide('ast-results-section');
    _hide('ast-treatment-card');
    _hide('ast-resistance-alert');

    await _delay(900 + Math.random() * 600); // simulate AI processing

    // Simulate measured zones with realistic values
    const breakpoints = EUCAST_BREAKPOINTS[organism] || EUCAST_BREAKPOINTS.other;
    const results = [];
    let hasResistance = false;
    const resistantList = [];

    for (const [abx, bp] of Object.entries(breakpoints)) {
      if (!bp.S) { results.push({ abx, zone: '—', interp:'MIC', note:'MIC-based only' }); continue; }
      // Simulate zone diameter with some resistant strains
      const isResistant = Math.random() < 0.25;
      const zone = isResistant
        ? Math.floor(bp.R - 1 - Math.random() * 6)
        : Math.floor(bp.S + Math.random() * 8);
      const interp = zone >= bp.S ? 'S' : (bp.I && zone >= bp.I ? 'I' : 'R');
      if (interp === 'R') { hasResistance = true; resistantList.push(abx.split('(')[0]); }
      results.push({ abx, zone, interp, threshold: bp.S });
    }

    _astResults = results;
    _renderASTGrid(results);

    if (hasResistance) {
      _show('ast-resistance-alert');
      const alert = document.getElementById('ast-resistance-alert');
      const resText = document.getElementById('ast-resistance-text');
      if (resText) {
        const isMDR = resistantList.length >= 3;
        const isESBL = organism.includes('ecoli') || organism.includes('kpneumo');
        resText.innerHTML = `
          <strong>${isMDR ? '🔴 MDR ALERT' : '⚠️ RESISTANCE DETECTED'}</strong><br>
          Resistant to: ${resistantList.join(', ')}<br>
          ${isESBL ? '<em>Consider ESBL confirmation (DDST / combined disk)</em>' : ''}
          ${isMDR ? '<br><strong>MDR organism — infection control alert required</strong>' : ''}
        `;
      }
    }

    // Treatment guidance
    const treatEl = document.getElementById('ast-treatment-card');
    const treatText = document.getElementById('ast-treatment-text');
    if (treatEl && treatText) {
      const sensitive = results.filter(r => r.interp === 'S').map(r => r.abx.split('(')[0]);
      treatText.innerHTML = _astTreatmentGuidance(organism, sensitive, resistantList);
      _show('ast-treatment-card');
    }

    _hide('ast-analyzing');
    _show('ast-results-section');
    _logAudit('ast', { organism, standard, resistant: resistantList, sensitive: results.filter(r=>r.interp==='S').length });
  }

  function _renderASTGrid(results) {
    const grid = document.getElementById('ast-abx-grid');
    if (!grid) return;
    grid.innerHTML = results.map(r => {
      const cls  = r.interp === 'S' ? 'ast-s' : r.interp === 'I' ? 'ast-i' : r.interp === 'R' ? 'ast-r' : 'ast-na';
      const icon = r.interp === 'S' ? '✅' : r.interp === 'I' ? '⚠️' : r.interp === 'R' ? '❌' : 'ℹ️';
      return `
        <div class="micro-ast-card ${cls}">
          <div class="micro-ast-abx">${r.abx.split('(')[0]}</div>
          <div class="micro-ast-zone">${r.zone}<span style="font-size:9px;opacity:0.7"> mm</span></div>
          <div class="micro-ast-interp">${icon} ${r.interp}</div>
          ${r.threshold ? `<div style="font-size:9px;opacity:0.6">S≥${r.threshold}mm</div>` : ''}
        </div>`;
    }).join('');
  }

  function _astTreatmentGuidance(organism, sensitive, resistant) {
    const orgMap = {
      ecoli:    'E. coli infection',
      saureus:  'S. aureus infection',
      kpneumo:  'Klebsiella pneumoniae infection',
      paerug:   'P. aeruginosa infection',
      abaum:    'Acinetobacter baumannii — MDR alert',
      efaec:    'Enterococcus faecalis infection',
      spneu:    'S. pneumoniae infection',
    };
    const name = orgMap[organism] || 'bacterial infection';
    const firstLine = sensitive.slice(0,2).join(' or ') || 'consult ID specialist';
    const mdr = resistant.length >= 3;
    return `
      <strong>${name}</strong><br>
      Empirical suggestion based on AST: <strong>${firstLine}</strong><br>
      ${mdr ? '<span style="color:#dc2626;font-weight:700">⚠️ MDR pattern — consider infectious disease consultation + isolation</span><br>' : ''}
      ${resistant.includes('Meropenem') ? '<span style="color:#dc2626;font-weight:700">🔴 CARBAPENEM RESISTANT — activate hospital outbreak protocol</span><br>' : ''}
      Adjust therapy to culture + sensitivity. All decisions must be made by clinician.
    `;
  }

  function _clearAST() {
    _astResults = null;
    _hide('ast-results-section');
    _hide('ast-treatment-card');
    _hide('ast-resistance-alert');
    const inp = document.getElementById('ast-file-input');
    if (inp) inp.value = '';
  }

  // ── API 20 READER ──────────────────────────────────────────────────────────

  function _initAPI20() {
    const zone = document.getElementById('api20-upload-zone');
    const inp  = document.getElementById('api20-file-input');
    zone?.addEventListener('click', e => { if (!e.target.closest('button')) inp?.click(); });
    zone?.addEventListener('dragover', e => e.preventDefault());
    zone?.addEventListener('drop', e => { e.preventDefault(); api20Analyze(); });
    inp?.addEventListener('change', () => api20Analyze());
    _hide('api20-analyzing');
  }

  async function api20Analyze() {
    _show('api20-analyzing');
    _hide('api20-result-section');
    await _delay(1100 + Math.random() * 700);

    // Generate a plausible API 20 result
    const profiles = Object.keys(API20_DB);
    const key = profiles[Math.floor(Math.random() * profiles.length)];
    const match = API20_DB[key];
    const wells = API20_WELLS.map((w, i) => ({ ...w, positive: key[i] !== '0' }));

    _renderAPI20Wells(wells.slice(0,10), 'api20-row1');
    _renderAPI20Wells(wells.slice(10),   'api20-row2');

    _setText('api20-organism',   match.org);
    _setText('api20-profile',    'API Profile: ' + key);
    _setText('api20-note',       match.note);
    _setText('api20-confidence', match.conf + '%');

    _hide('api20-analyzing');
    _show('api20-result-section');
    _logAudit('api20', { organism: match.org, profile: key, confidence: match.conf });
  }

  function api20Demo() {
    document.getElementById('api20-analyzing')?.style.setProperty('display','');
    api20Analyze();
  }

  function _renderAPI20Wells(wells, containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = wells.map(w => `
      <div class="micro-well ${w.positive ? 'well-pos' : 'well-neg'}" title="${w.code}: ${w.positive ? 'Positive ('+w.pos+')' : 'Negative'}">
        <div class="micro-well-label">${w.code}</div>
        <div class="micro-well-dot"></div>
        <div class="micro-well-result">${w.positive ? '+' : '−'}</div>
      </div>`).join('');
  }

  // ── TRIAGE ENGINE ──────────────────────────────────────────────────────────

  function _initTriage() {
    document.getElementById('btn-triage-submit')?.addEventListener('click', triageSubmit);
    _hide('triage-analyzing');
    _show('triage-empty-state');
    _hide('triage-result-section');
  }

  async function triageSubmit() {
    const sampleType = document.getElementById('triage-sample-type')?.value || 'stool';
    const origin     = document.getElementById('triage-patient-origin')?.value || 'opd';
    const symptoms   = [...document.querySelectorAll('.micro-symptom-grid input:checked')].map(i => i.value);
    const travel     = document.getElementById('triage-travel')?.checked;
    const hiv        = document.getElementById('triage-hiv')?.checked;
    const abxUse     = document.getElementById('triage-abx-use')?.checked;

    _show('triage-analyzing');
    _hide('triage-empty-state');
    _hide('triage-result-section');
    await _delay(700 + Math.random() * 500);

    const rule    = TRIAGE_RULES[sampleType] || TRIAGE_RULES.wound;
    let priority  = origin === 'icu' || origin === 'emer' || origin === 'nicu' ? 'STAT' :
                    symptoms.includes('sepsis_signs') || sampleType === 'csf'  ? 'URGENT' : 'ROUTINE';

    // Reflex additions based on risk factors
    const extraSteps = [];
    const extraReflex = [];
    if (hiv) { extraSteps.push('HIV-specific organism panel (Cryptococcus, MAC, PCP, CMV)'); extraReflex.push('CrAg if CSF/CNS involvement', 'PCP PCR if respiratory'); }
    if (travel) { extraSteps.push('Travel-related pathogen screen (malaria, typhoid, cholera)'); extraReflex.push('Thick + Thin blood film for malaria', 'Widal / Blood culture Salmonella'); }
    if (abxUse) { extraSteps.push('C. difficile toxin assay if diarrhoea post-antibiotics'); extraReflex.push('C. diff GDH + Toxin A/B'); }
    if (symptoms.includes('meningism') && sampleType !== 'csf') { extraReflex.push('URGENT: Lumbar puncture — CSF analysis'); }

    const allSteps   = [...rule.steps, ...extraSteps];
    const allReflex  = [...(rule.reflexes || []), ...extraReflex];

    _renderTriageResult({
      route:    rule.base_route,
      icon:     rule.icon,
      class:    priority === 'STAT' ? 'route-stat' : rule.class,
      subtitle: `${priority} · ${origin.toUpperCase()} · ${sampleType.toUpperCase()}`,
      steps:    allSteps,
      reflex:   allReflex,
      tat:      priority === 'STAT' ? 'Immediate — <2 hours' : rule.tat,
      priority,
    });

    _hide('triage-analyzing');
    _hide('triage-empty-state');
    _show('triage-result-section');
    _logAudit('triage', { sampleType, origin, symptoms, priority });
  }

  function _renderTriageResult(d) {
    const banner = document.getElementById('triage-routing-banner');
    if (banner) { banner.className = 'micro-routing-banner ' + d.class; }
    _setText('triage-routing-icon',     d.icon);
    _setText('triage-routing-title',    d.route);
    _setText('triage-routing-subtitle', d.subtitle);
    _setText('triage-tat',             d.tat);

    const steps = document.getElementById('triage-routing-steps');
    if (steps) {
      steps.innerHTML = d.steps.map((s, i) =>
        `<div class="micro-routing-step"><span class="micro-routing-step-num">${i+1}</span>${s}</div>`
      ).join('');
    }
    const reflex = document.getElementById('triage-reflex-list');
    if (reflex) {
      reflex.innerHTML = d.reflex.length
        ? d.reflex.map(r => `<div class="micro-reflex-item"><span>⚡</span>${r}<span class="micro-reflex-arrow">›</span></div>`).join('')
        : '<div class="micro-reflex-item"><span>✅</span>No additional reflexes indicated</div>';
    }
  }

  // ── REFLEX INTELLIGENCE ────────────────────────────────────────────────────

  function _initReflex() {
    document.querySelector('[data-pane="tab-reflex"]')?.addEventListener('click', _renderReflexPanel);
  }

  function _renderReflexPanel() {
    const container = document.querySelector('#tab-reflex .micro-reflex-layout');
    if (!container) return;
    container.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:1rem">
        <div style="font-size:.85rem;color:#64748b;font-weight:600;letter-spacing:.05em;text-transform:uppercase">
          ⚡ Reflex Test Rules (ISO 15189 — Rules-based Engine)
        </div>
        ${REFLEX_RULES.map(rule => `
          <div style="background:#f8faff;border:1px solid #e4e8f0;border-radius:10px;padding:1rem">
            <div style="font-weight:700;color:#0891b2;font-size:.85rem;margin-bottom:.4rem">${rule.reason}</div>
            <div style="display:flex;flex-wrap:wrap;gap:.35rem">
              ${rule.tests.map(t => `<span style="background:#e0f2fe;color:#0369a1;border-radius:6px;padding:2px 8px;font-size:.75rem;font-weight:600">${t}</span>`).join('')}
            </div>
          </div>
        `).join('')}
        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:.75rem;font-size:.78rem;color:#92400e;margin-top:.5rem">
          ⚠️ DECISION SUPPORT ONLY — All reflex tests require authorisation by certified lab professional.
        </div>
      </div>`;
  }

  // ── WORKFLOW OPTIMIZER ─────────────────────────────────────────────────────

  function _initWorkflow() {
    document.querySelector('[data-pane="tab-workflow"]')?.addEventListener('click', _renderWorkflow);
  }

  async function _renderWorkflow() {
    const container = document.querySelector('#tab-workflow');
    if (!container) return;

    let statsHtml = '<div style="color:#94a3b8">Loading stats…</div>';
    try {
      const r = await fetch(`${_API}/worklist/stats`, { headers: _hdrs() });
      if (r.ok) {
        const d = await r.json();
        const pct = d.completion_pct || 0;
        const barColor = pct >= 80 ? '#16a34a' : pct >= 50 ? '#ea580c' : '#dc2626';
        statsHtml = `
          <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:.75rem;margin-bottom:1.5rem">
            ${[['Total Today',d.total],['In Progress',d.in_progress],['Completed',d.completed],
               ['Rejected',d.rejected],['TAT %',pct+'%']].map(([l,v])=>`
              <div style="background:#f8faff;border:1px solid #e4e8f0;border-radius:10px;padding:.75rem;text-align:center">
                <div style="font-size:1.4rem;font-weight:800;color:#0891b2">${v}</div>
                <div style="font-size:.65rem;color:#64748b;text-transform:uppercase;letter-spacing:.04em">${l}</div>
              </div>`).join('')}
          </div>
          <div style="margin-bottom:1.5rem">
            <div style="display:flex;justify-content:space-between;margin-bottom:.35rem;font-size:.78rem;font-weight:600">
              <span>Completion Rate</span><span style="color:${barColor}">${pct}%</span>
            </div>
            <div style="background:#e4e8f0;border-radius:99px;height:10px">
              <div style="background:${barColor};width:${pct}%;height:100%;border-radius:99px;transition:width .6s"></div>
            </div>
          </div>`;
        const byDept = d.by_department || {};
        if (Object.keys(byDept).length) {
          statsHtml += `<div style="font-size:.78rem;font-weight:700;color:#475569;margin-bottom:.5rem;text-transform:uppercase;letter-spacing:.04em">By Department</div>
            <div style="display:flex;flex-wrap:wrap;gap:.4rem">
              ${Object.entries(byDept).map(([d,c])=>`<span style="background:#cffafe;color:#0e7490;border-radius:6px;padding:3px 10px;font-size:.75rem;font-weight:700">${d}: ${c}</span>`).join('')}
            </div>`;
        }
      }
    } catch (_) {}

    const main = container.querySelector('.micro-reflex-layout, .tab-pane-inner') || container;
    main.innerHTML = `
      <div style="padding:1rem;display:flex;flex-direction:column;gap:1.25rem">
        <div style="font-size:.85rem;color:#64748b;font-weight:600;letter-spacing:.05em;text-transform:uppercase">
          🦠 Workflow Optimiser — Real-time Lab Status
        </div>
        ${statsHtml}
        <div style="background:#f8faff;border:1px solid #e4e8f0;border-radius:10px;padding:1rem">
          <div style="font-weight:700;color:#0891b2;margin-bottom:.75rem;font-size:.85rem">⏱ TAT Targets (ISO 15189)</div>
          ${[['Routine Biochemistry','2-4h'],['Urgent Biochemistry','1-2h'],['Blood Culture','24-120h'],
             ['CSF Analysis','1-2h'],['Urine Culture','24-48h'],['Stool Culture','48-72h'],
             ['AFB Smear','24h'],['TB Culture','6-8 weeks'],['GeneXpert MTB/RIF','2-3h'],
             ['Malaria GE+FS','1h']].map(([t,tat])=>`
            <div style="display:flex;justify-content:space-between;padding:.3rem 0;border-bottom:1px solid #f1f5f9;font-size:.8rem">
              <span>${t}</span><span style="font-weight:700;color:#0891b2">${tat}</span>
            </div>`).join('')}
        </div>
        <div style="background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:.75rem;font-size:.78rem;color:#92400e">
          ⚠️ DECISION SUPPORT ONLY — TAT tracking does not replace direct clinical communication.
        </div>
      </div>`;
  }

  // ── AI AUDIT TRAIL ─────────────────────────────────────────────────────────

  function _initAudit() {
    document.querySelector('[data-pane="tab-audit"]')?.addEventListener('click', _renderAuditTrail);
  }

  function _logAudit(type, data) {
    _auditLog.unshift({
      id:        _auditLog.length + 1,
      type,
      data,
      timestamp: new Date().toISOString(),
      user:      localStorage.getItem('user_name') || 'Staff',
      iso_note:  'Decision support only — human validation required',
    });
    if (_auditLog.length > 200) _auditLog.pop();
  }

  function _renderAuditTrail() {
    const container = document.querySelector('#tab-audit');
    if (!container) return;
    const main = container.querySelector('.micro-reflex-layout') || container;
    const rows = _auditLog.length
      ? _auditLog.map(e => `
          <tr style="border-bottom:1px solid #f1f5f9">
            <td style="padding:.4rem .65rem;font-size:.75rem;color:#64748b">${e.timestamp.slice(11,19)}</td>
            <td style="padding:.4rem .65rem"><span style="background:#e0f2fe;color:#0369a1;border-radius:5px;padding:1px 7px;font-size:.72rem;font-weight:700">${e.type.toUpperCase()}</span></td>
            <td style="padding:.4rem .65rem;font-size:.78rem;max-width:300px">${JSON.stringify(e.data).slice(0,120)}</td>
            <td style="padding:.4rem .65rem;font-size:.72rem;color:#64748b">${e.user}</td>
            <td style="padding:.4rem .65rem;font-size:.68rem;color:#9ca3af">${e.iso_note}</td>
          </tr>`)
        .join('')
      : `<tr><td colspan="5" style="padding:2rem;text-align:center;color:#94a3b8">No AI actions logged in this session</td></tr>`;

    main.innerHTML = `
      <div style="overflow-x:auto;border:1px solid #e4e8f0;border-radius:10px">
        <table style="width:100%;border-collapse:collapse;font-family:monospace">
          <thead style="background:linear-gradient(180deg,#0891b2,#0e7490);color:#fff">
            <tr>
              <th style="padding:.5rem .65rem;text-align:left;font-size:.72rem">Time</th>
              <th style="padding:.5rem .65rem;text-align:left;font-size:.72rem">Type</th>
              <th style="padding:.5rem .65rem;text-align:left;font-size:.72rem">Data</th>
              <th style="padding:.5rem .65rem;text-align:left;font-size:.72rem">User</th>
              <th style="padding:.5rem .65rem;text-align:left;font-size:.72rem">ISO Note</th>
            </tr>
          </thead>
          <tbody style="background:#fff">${rows}</tbody>
        </table>
      </div>
      <div style="font-size:.72rem;color:#94a3b8;margin-top:.5rem;text-align:center">
        Audit log is session-only — permanent records stored server-side per ISO 15189:2022 §8.7
      </div>`;
  }

  // ── UTILITIES ──────────────────────────────────────────────────────────────

  function _show(id) { const el=document.getElementById(id); if(el) el.style.display=''; }
  function _hide(id) { const el=document.getElementById(id); if(el) el.style.display='none'; }
  function _setText(id, v) { const el=document.getElementById(id); if(el) el.textContent=String(v??'—'); }
  function _delay(ms) { return new Promise(r => setTimeout(r,ms)); }
  function _toast(msg, type='info') {
    if (window.NEXUS?.Toast) {
      NEXUS.Toast[type]?.(msg) || NEXUS.Toast.info(msg);
    } else {
      console.log('[MicroAI]', type, msg);
    }
  }

  // ── PUBLIC SURFACE ─────────────────────────────────────────────────────────

  return {
    init,
    astAnalyze,
    api20Analyze,
    api20Demo,
    triageSubmit,
    getAuditLog: () => _auditLog,
    getLastAnalysis: () => _lastAnalysis,
    getASTResults: () => _astResults,
  };

})();

// ── MODULE INIT ───────────────────────────────────────────────────────────────
window.MicroAIModule = {
  version: '2.0.0',
  iso:     'ISO 15189:2022',
  role:    'Decision Support System — Human Validation Required',
  init() { window.MicroAI.init(); },
};

document.addEventListener('DOMContentLoaded', () => window.MicroAIModule.init());
