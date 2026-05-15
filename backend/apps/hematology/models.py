"""Hematology models — CBC, Coagulation, Peripheral Smear, Inflammation"""
from django.db import models
from django.utils import timezone


class HematologyRequest(models.Model):
    """Bridge between a LabRequest and hematology-specific results."""

    class Status(models.TextChoices):
        PENDING    = 'pending',    'Pending'
        PROCESSING = 'processing', 'Processing'
        RESULTED   = 'resulted',   'Resulted'
        VALIDATED  = 'validated',  'Validated'
        AUTHORIZED = 'authorized', 'Authorized'
        REJECTED   = 'rejected',   'Rejected'

    lab_request    = models.OneToOneField(
        'laboratory.LabRequest', on_delete=models.CASCADE, related_name='hematology')
    patient        = models.ForeignKey(
        'patients.Patient', on_delete=models.PROTECT, related_name='hematology_requests')
    status         = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    sample_received_at = models.DateTimeField(null=True, blank=True)
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"HEMA-{self.pk} → {self.patient}"


class CBCResult(models.Model):
    """Complete Blood Count result entry with AI interpretation."""

    class Severity(models.TextChoices):
        NORMAL   = 'normal',   'Normal'
        MILD     = 'mild',     'Mild'
        MODERATE = 'moderate', 'Moderate'
        SEVERE   = 'severe',   'Severe'
        CRITICAL = 'critical', 'Critical'

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        RESULTED  = 'resulted',  'Resulted'
        VALIDATED = 'validated', 'Validated'
        AUTHORIZED= 'authorized','Authorized'

    request        = models.OneToOneField(HematologyRequest, on_delete=models.CASCADE, related_name='cbc')
    analyzer       = models.CharField(max_length=100, blank=True)

    # ── Red Cell Indices ─────────────────────────────────────────────────────
    wbc            = models.DecimalField(max_digits=6,  decimal_places=2, null=True, blank=True, help_text='×10³/µL')
    rbc            = models.DecimalField(max_digits=5,  decimal_places=2, null=True, blank=True, help_text='×10⁶/µL')
    hgb            = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='g/dL')
    hct            = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='%')
    mcv            = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='fL')
    mch            = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='pg')
    mchc           = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='g/dL')
    rdw            = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='%')

    # ── WBC Differential ─────────────────────────────────────────────────────
    neut_pct       = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='%')
    lymph_pct      = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='%')
    mono_pct       = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='%')
    eo_pct         = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='%')
    baso_pct       = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='%')
    blast_pct      = models.DecimalField(max_digits=4,  decimal_places=1, null=True, blank=True, help_text='% — flag if >0')

    # ── Absolute Counts ────────────────────────────────────────────────────
    neut_abs       = models.DecimalField(max_digits=5,  decimal_places=2, null=True, blank=True, help_text='×10³/µL ANC')
    lymph_abs      = models.DecimalField(max_digits=5,  decimal_places=2, null=True, blank=True)
    mono_abs       = models.DecimalField(max_digits=5,  decimal_places=2, null=True, blank=True)

    # ── Platelets ─────────────────────────────────────────────────────────
    plt            = models.DecimalField(max_digits=6,  decimal_places=0, null=True, blank=True, help_text='×10³/µL')
    mpv            = models.DecimalField(max_digits=5,  decimal_places=1, null=True, blank=True, help_text='fL')

    # ── AI Interpretation ─────────────────────────────────────────────────
    primary_finding    = models.CharField(max_length=200, blank=True)
    severity           = models.CharField(max_length=15, choices=Severity.choices, default=Severity.NORMAL)
    ai_interpretation  = models.JSONField(default=dict, blank=True)
    critical_values    = models.JSONField(default=list, blank=True)
    leukemia_flag      = models.BooleanField(default=False)
    reflex_suggestions = models.JSONField(default=list, blank=True)

    # ── Validation ────────────────────────────────────────────────────────
    status             = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    validated_by       = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='cbc_validated')
    validated_at       = models.DateTimeField(null=True, blank=True)
    authorized_by      = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='cbc_authorized')
    authorized_at      = models.DateTimeField(null=True, blank=True)
    correction_reason  = models.TextField(blank=True)

    created_at         = models.DateTimeField(auto_now_add=True)
    updated_at         = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"CBC #{self.pk} HGB:{self.hgb} PLT:{self.plt}"

    @property
    def is_critical(self):
        return bool(self.critical_values) or self.leukemia_flag


class CoagulationResult(models.Model):
    """Coagulation profile — PT/INR, APTT, Fibrinogen, D-Dimer."""

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        VALIDATED = 'validated', 'Validated'

    request        = models.OneToOneField(HematologyRequest, on_delete=models.CASCADE, related_name='coagulation')

    pt             = models.DecimalField(max_digits=6,  decimal_places=1, null=True, blank=True, help_text='sec')
    inr            = models.DecimalField(max_digits=5,  decimal_places=2, null=True, blank=True)
    aptt           = models.DecimalField(max_digits=6,  decimal_places=1, null=True, blank=True, help_text='sec')
    fibrinogen     = models.DecimalField(max_digits=5,  decimal_places=2, null=True, blank=True, help_text='g/L')
    d_dimer        = models.DecimalField(max_digits=6,  decimal_places=3, null=True, blank=True, help_text='µg/mL')
    tt             = models.DecimalField(max_digits=6,  decimal_places=1, null=True, blank=True, help_text='sec')

    anticoagulant_therapy = models.CharField(max_length=50, blank=True)

    ai_interpretation = models.JSONField(default=dict, blank=True)
    primary_finding   = models.CharField(max_length=200, blank=True)
    severity          = models.CharField(max_length=15, default='normal')

    status            = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    validated_by      = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    validated_at      = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Coag #{self.pk} INR:{self.inr}"


class InflammationResult(models.Model):
    """Inflammatory markers — ESR, CRP, PCT, Ferritin, LDH, IL-6."""

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        VALIDATED = 'validated', 'Validated'

    request    = models.OneToOneField(HematologyRequest, on_delete=models.CASCADE, related_name='inflammation')

    esr        = models.DecimalField(max_digits=5,  decimal_places=0, null=True, blank=True, help_text='mm/hr')
    crp        = models.DecimalField(max_digits=7,  decimal_places=2, null=True, blank=True, help_text='mg/L')
    pct        = models.DecimalField(max_digits=6,  decimal_places=3, null=True, blank=True, help_text='µg/L')
    ferritin   = models.DecimalField(max_digits=8,  decimal_places=1, null=True, blank=True, help_text='µg/L')
    ldh        = models.DecimalField(max_digits=7,  decimal_places=0, null=True, blank=True, help_text='U/L')
    il6        = models.DecimalField(max_digits=7,  decimal_places=2, null=True, blank=True, help_text='pg/mL')

    patient_gender = models.CharField(max_length=1, choices=[('M','Male'),('F','Female')], default='M')
    patient_age    = models.PositiveSmallIntegerField(null=True, blank=True)

    ai_interpretation  = models.JSONField(default=dict, blank=True)
    primary_finding    = models.CharField(max_length=200, blank=True)
    severity           = models.CharField(max_length=15, default='normal')
    sepsis_alert       = models.BooleanField(default=False)

    status         = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    validated_by   = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    validated_at   = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Inflammation #{self.pk} CRP:{self.crp} PCT:{self.pct}"


class SmearResult(models.Model):
    """Peripheral blood smear analysis result."""

    class Status(models.TextChoices):
        DRAFT      = 'draft',      'Draft'
        AI_PENDING = 'ai_pending', 'AI Processing'
        RESULTED   = 'resulted',   'Resulted'
        VALIDATED  = 'validated',  'Validated'

    request        = models.OneToOneField(HematologyRequest, on_delete=models.CASCADE, related_name='smear')
    stain_type     = models.CharField(max_length=50, choices=[
        ('leishman','Leishman'), ('giemsa','Giemsa'), ('wright','Wright'),
        ('mgg','May-Grünwald Giemsa'), ('hne','H&E'),
    ], default='leishman')
    film_type      = models.CharField(max_length=20, choices=[
        ('thin','Thin Film (differential)'), ('thick','Thick Film (parasite)'),
    ], default='thin')
    magnification  = models.CharField(max_length=20, default='100x')
    smear_image    = models.ImageField(upload_to='smear_images/', null=True, blank=True)

    # ── Morphology findings ────────────────────────────────────────────────
    red_cell_morphology = models.JSONField(default=list, blank=True,
        help_text='[{name, pct, color}] — morphology distribution')
    wbc_differential    = models.JSONField(default=dict, blank=True,
        help_text='{neutrophils, lymphocytes, monocytes, eosinophils, basophils, blast}')
    platelet_estimate   = models.CharField(max_length=30, blank=True)
    parasite_detected   = models.CharField(max_length=100, blank=True)
    parasite_stage      = models.CharField(max_length=100, blank=True)

    # ── AI ────────────────────────────────────────────────────────────────
    impression          = models.TextField(blank=True)
    ai_confidence       = models.PositiveSmallIntegerField(default=0, help_text='0–100%')
    ai_raw              = models.JSONField(default=dict, blank=True)

    # ── Validation ────────────────────────────────────────────────────────
    status         = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    reviewed_by    = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='smears_reviewed')
    reviewed_at    = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Smear #{self.pk} — {self.impression[:60]}"
