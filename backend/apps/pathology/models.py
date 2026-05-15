"""Anatomical Pathology models — Histopathology, Cytology, IHC, AI Vision"""
from django.db import models
from django.utils import timezone


class PathologyCase(models.Model):
    """Master record for a pathology case (biopsy, cytology, FNA, autopsy)."""

    class CaseType(models.TextChoices):
        BIOPSY      = 'biopsy',      'Biopsy (Histology)'
        CYTOLOGY    = 'cytology',    'Cytology (Pap / Non-Gyn)'
        FNA         = 'fna',         'Fine-Needle Aspiration (FNA)'
        RESECTION   = 'resection',   'Surgical Resection'
        FROZEN      = 'frozen',      'Frozen Section'
        AUTOPSY     = 'autopsy',     'Autopsy / Post-mortem'
        BONE_MARROW = 'bone_marrow', 'Bone Marrow Trephine'
        FLOWCYTO    = 'flowcyto',    'Flow Cytometry'

    class Priority(models.TextChoices):
        ROUTINE  = 'routine',  'Routine'
        URGENT   = 'urgent',   'Urgent (48h)'
        STAT     = 'stat',     'STAT — Intraoperative'

    class Status(models.TextChoices):
        REGISTERED   = 'registered',   'Registered'
        GROSSING     = 'grossing',      'Grossing'
        PROCESSING   = 'processing',    'Tissue Processing'
        EMBEDDING    = 'embedding',     'Embedding'
        SECTIONING   = 'sectioning',    'Sectioning'
        STAINING     = 'staining',      'Staining'
        MICROSCOPY   = 'microscopy',    'Microscopy'
        AI_REVIEW    = 'ai_review',     'AI Vision Review'
        REPORTING    = 'reporting',     'Reporting'
        VALIDATED    = 'validated',     'Validated'
        AUTHORIZED   = 'authorized',    'Authorized / Signed Out'
        AMENDED      = 'amended',       'Amended'

    case_number    = models.CharField(max_length=30, unique=True)
    patient        = models.ForeignKey(
        'patients.Patient', on_delete=models.PROTECT, related_name='pathology_cases')
    lab_request    = models.ForeignKey(
        'laboratory.LabRequest', on_delete=models.SET_NULL, null=True, blank=True)
    case_type      = models.CharField(max_length=15, choices=CaseType.choices)
    priority       = models.CharField(max_length=10, choices=Priority.choices, default=Priority.ROUTINE)
    status         = models.CharField(max_length=15, choices=Status.choices, default=Status.REGISTERED)

    # ── Specimen details ──────────────────────────────────────────────────────
    specimen_site       = models.CharField(max_length=200)
    specimen_laterality = models.CharField(max_length=10, blank=True,
        choices=[('left','Left'),('right','Right'),('bilateral','Bilateral'),('midline','Midline')])
    specimen_count      = models.PositiveSmallIntegerField(default=1)
    fixative            = models.CharField(max_length=50, default='Formalin 10%',
        choices=[('formalin','Formalin 10%'),('bouin','Bouin\'s'),('alcohol','Alcohol'),
                 ('fresh','Fresh (frozen)'),('glutaraldehyde','Glutaraldehyde')])
    collection_date     = models.DateField(null=True, blank=True)
    received_date       = models.DateField(default=timezone.now)

    # ── Clinical context ──────────────────────────────────────────────────────
    clinical_information = models.TextField(blank=True)
    requesting_clinician = models.CharField(max_length=100, blank=True)
    provisional_diagnosis= models.CharField(max_length=200, blank=True)
    procedure_type       = models.CharField(max_length=100, blank=True, help_text='e.g. TURBT, core needle biopsy')

    # ── IHC / Special stains ──────────────────────────────────────────────────
    ihc_requested       = models.BooleanField(default=False)
    special_stains_requested = models.BooleanField(default=False)

    # ── Tracking ──────────────────────────────────────────────────────────────
    assigned_pathologist = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pathology_cases')
    notes               = models.TextField(blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.case_number} — {self.get_case_type_display()} ({self.specimen_site})"

    def save(self, *args, **kwargs):
        if not self.case_number:
            year  = timezone.now().year
            last  = PathologyCase.objects.filter(case_number__startswith=f'PATH-{year}').order_by('id').last()
            seq   = (int(last.case_number.split('-')[-1]) + 1) if last else 1
            self.case_number = f"PATH-{year}-{seq:05d}"
        super().save(*args, **kwargs)


class SpecimenBlock(models.Model):
    """Individual tissue block cut from a specimen."""

    case       = models.ForeignKey(PathologyCase, on_delete=models.CASCADE, related_name='blocks')
    block_code = models.CharField(max_length=10)
    description= models.CharField(max_length=200, blank=True)
    cassette_color = models.CharField(max_length=20, blank=True)
    processed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [['case', 'block_code']]
        ordering        = ['block_code']

    def __str__(self):
        return f"{self.case.case_number} Block {self.block_code}"


class MicroscopySlide(models.Model):
    """H&E or special stain slide cut from a block."""

    class StainType(models.TextChoices):
        HE       = 'he',       'H&E'
        PAS      = 'pas',      'PAS'
        MASSON   = 'masson',   'Masson Trichrome'
        GIEMSA   = 'giemsa',   'Giemsa'
        ZIEHL    = 'ziehl',    'Ziehl-Neelsen (AFB)'
        GMS      = 'gms',      'GMS (fungal)'
        PRUSSIAN = 'prussian', 'Prussian Blue (iron)'
        GRAM     = 'gram',     'Gram stain'
        CONGO    = 'congo',    'Congo Red (amyloid)'
        OTHER    = 'other',    'Other'

    block      = models.ForeignKey(SpecimenBlock, on_delete=models.CASCADE, related_name='slides')
    slide_code = models.CharField(max_length=15)
    stain_type = models.CharField(max_length=15, choices=StainType.choices, default=StainType.HE)
    cut_at     = models.DateTimeField(null=True, blank=True)
    slide_image= models.ImageField(upload_to='pathology/slides/', null=True, blank=True)
    wsi_url    = models.URLField(blank=True, help_text='Whole-slide image URL (digital pathology)')
    notes      = models.TextField(blank=True)

    class Meta:
        ordering = ['slide_code']

    def __str__(self):
        return f"{self.block} — Slide {self.slide_code} ({self.get_stain_type_display()})"


class SlideAIAnalysis(models.Model):
    """AI vision analysis result for a slide image."""

    class AIModel(models.TextChoices):
        NEXUS_VISION  = 'nexus_vision',  'NEXUS AI Vision'
        PATHAI        = 'pathai',        'PathAI'
        PAIGE         = 'paige',         'Paige.AI'
        MANUAL        = 'manual',        'Manual (No AI)'

    slide          = models.OneToOneField(MicroscopySlide, on_delete=models.CASCADE, related_name='ai_analysis')
    ai_model       = models.CharField(max_length=20, choices=AIModel.choices, default=AIModel.NEXUS_VISION)
    ai_version     = models.CharField(max_length=20, blank=True)
    confidence     = models.PositiveSmallIntegerField(default=0, help_text='0–100%')

    # Detection findings
    cancer_probability   = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='0–100%')
    detected_patterns    = models.JSONField(default=list, blank=True,
        help_text='[{pattern, confidence, region_coords}]')
    cell_classification  = models.JSONField(default=dict, blank=True,
        help_text='{malignant_pct, benign_pct, necrosis_pct, ...}')
    ki67_index           = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text='Proliferation index %')
    mitotic_count        = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Per 10 HPF')

    ai_impression        = models.TextField(blank=True)
    ai_raw_output        = models.JSONField(default=dict, blank=True)
    reviewed_at          = models.DateTimeField(null=True, blank=True)
    analysed_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-analysed_at']

    def __str__(self):
        return f"AI Analysis — {self.slide} ({self.confidence}% conf)"


class IHCPanel(models.Model):
    """Immunohistochemistry panel result."""

    case   = models.ForeignKey(PathologyCase, on_delete=models.CASCADE, related_name='ihc_panels')
    marker = models.CharField(max_length=60, help_text='e.g. ER, PR, HER2, Ki-67, CD20')
    clone  = models.CharField(max_length=50, blank=True)
    result = models.CharField(max_length=20, choices=[
        ('positive','Positive'),('negative','Negative'),
        ('equivocal','Equivocal (2+)'),('not_done','Not Done'),
    ])
    intensity       = models.CharField(max_length=20, blank=True,
        choices=[('weak','Weak (1+)'),('moderate','Moderate (2+)'),('strong','Strong (3+)')])
    percentage      = models.PositiveSmallIntegerField(null=True, blank=True, help_text='% positive cells')
    h_score         = models.PositiveSmallIntegerField(null=True, blank=True, help_text='H-score 0–300')
    allred_score    = models.PositiveSmallIntegerField(null=True, blank=True)
    notes           = models.TextField(blank=True)
    performed_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['marker']

    def __str__(self):
        return f"{self.case.case_number} {self.marker}: {self.result}"


class HistopathologyReport(models.Model):
    """Final pathology report for a case."""

    class ReportStatus(models.TextChoices):
        DRAFT      = 'draft',      'Draft'
        PRELIMINARY= 'preliminary','Preliminary'
        FINAL      = 'final',      'Final'
        AMENDED    = 'amended',    'Amended'
        ADDENDUM   = 'addendum',   'Addendum'

    class TumorGrade(models.TextChoices):
        G1  = 'G1',  'Grade 1 — Well differentiated'
        G2  = 'G2',  'Grade 2 — Moderately differentiated'
        G3  = 'G3',  'Grade 3 — Poorly differentiated'
        G4  = 'G4',  'Grade 4 — Undifferentiated'
        GX  = 'GX',  'GX — Grade cannot be assessed'
        NA  = 'NA',  'Not applicable'

    case            = models.OneToOneField(PathologyCase, on_delete=models.CASCADE, related_name='report')
    report_status   = models.CharField(max_length=15, choices=ReportStatus.choices, default=ReportStatus.DRAFT)

    # ── Gross description ────────────────────────────────────────────────────
    gross_description   = models.TextField(blank=True)
    specimen_weight_g   = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    specimen_size_cm    = models.CharField(max_length=50, blank=True, help_text='e.g. 3.5 × 2.1 × 1.8 cm')

    # ── Microscopic description ───────────────────────────────────────────
    microscopic_description = models.TextField(blank=True)

    # ── Diagnosis ──────────────────────────────────────────────────────────
    diagnosis           = models.TextField()
    icd10_code          = models.CharField(max_length=15, blank=True)
    icd_o_morphology    = models.CharField(max_length=20, blank=True, help_text='ICD-O morphology code e.g. 8140/3')
    snomed_concept      = models.CharField(max_length=50, blank=True)
    is_malignant        = models.BooleanField(null=True, blank=True)

    # ── Tumour staging ─────────────────────────────────────────────────────
    tumor_grade         = models.CharField(max_length=5, choices=TumorGrade.choices, default=TumorGrade.NA)
    pT                  = models.CharField(max_length=10, blank=True, help_text='Pathological T stage')
    pN                  = models.CharField(max_length=10, blank=True)
    pM                  = models.CharField(max_length=10, blank=True)
    tnm_stage           = models.CharField(max_length=15, blank=True)
    lymphovascular_invasion = models.CharField(max_length=20, blank=True,
        choices=[('present','Present'),('absent','Absent'),('indeterminate','Indeterminate')])
    perineural_invasion = models.CharField(max_length=20, blank=True,
        choices=[('present','Present'),('absent','Absent'),('indeterminate','Indeterminate')])
    resection_margins   = models.CharField(max_length=30, blank=True,
        choices=[('clear','Clear — Margins free'),('close','Close (<1mm)'),('involved','Margins involved')])

    # ── AI assistance ─────────────────────────────────────────────────────
    ai_assisted         = models.BooleanField(default=False)
    ai_suggestions      = models.JSONField(default=dict, blank=True)

    # ── Comments & Signing ────────────────────────────────────────────────
    comments            = models.TextField(blank=True)
    signed_by           = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_signed')
    signed_at           = models.DateTimeField(null=True, blank=True)
    counter_signed_by   = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='reports_countersigned')
    amendment_reason    = models.TextField(blank=True)

    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report {self.case.case_number} — {self.report_status}"
