"""Toxicology models — Drug Screening, TDM, Poisoning Assessment"""
from django.db import models
from django.utils import timezone


class ToxicologyRequest(models.Model):
    """Bridge to LabRequest for toxicology work."""

    class TestType(models.TextChoices):
        UDS      = 'uds',      'Urine Drug Screen'
        TDM      = 'tdm',      'Therapeutic Drug Monitoring'
        POISONING= 'poisoning','Poisoning Assessment'
        FORENSIC = 'forensic', 'Forensic Toxicology'

    class Status(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        RESULTED  = 'resulted',  'Resulted'
        VALIDATED = 'validated', 'Validated'

    lab_request = models.OneToOneField(
        'laboratory.LabRequest', on_delete=models.CASCADE, related_name='toxicology')
    patient     = models.ForeignKey(
        'patients.Patient', on_delete=models.PROTECT, related_name='toxicology_requests')
    test_type   = models.CharField(max_length=15, choices=TestType.choices)
    status      = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    is_medicolegal = models.BooleanField(default=False)
    chain_of_custody_id = models.CharField(max_length=50, blank=True)
    notes       = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"TOX-{self.pk} {self.get_test_type_display()} — {self.patient}"


class DrugScreenResult(models.Model):
    """Urine Drug Screen panel result."""

    class PanelType(models.TextChoices):
        PANEL_5  = '5',  '5-Panel Standard'
        PANEL_10 = '10', '10-Panel Extended'
        PANEL_12 = '12', '12-Panel Comprehensive'

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        VALIDATED = 'validated', 'Validated'
        CONFIRMED = 'confirmed', 'GC-MS Confirmed'

    request    = models.OneToOneField(ToxicologyRequest, on_delete=models.CASCADE, related_name='drug_screen')
    panel_type = models.CharField(max_length=5, choices=PanelType.choices, default=PanelType.PANEL_5)

    # Each drug entry: {name, result: positive/negative, cutoff_ng_ml, measured_ng_ml, method}
    drug_results = models.JSONField(default=dict, blank=True)

    screening_method   = models.CharField(max_length=50, default='Immunoassay',
        choices=[('immunoassay','Immunoassay (IA)'),('gcms','GC-MS'),('lcms','LC-MS/MS'),('rdt','Rapid Dipstrip')])
    coc_required       = models.BooleanField(default=False)
    specimen_temp_ok   = models.BooleanField(default=True, help_text='Specimen temperature within acceptable range')
    creatinine_ok      = models.BooleanField(default=True, help_text='Specimen creatinine acceptable')
    specific_gravity_ok= models.BooleanField(default=True)

    ai_interpretation  = models.JSONField(default=dict, blank=True)
    positive_drugs     = models.JSONField(default=list, blank=True)
    requires_confirmation = models.BooleanField(default=False)

    status        = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    validated_by  = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    validated_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        pos = len(self.positive_drugs)
        return f"UDS #{self.pk} {self.panel_type}-Panel — {pos} positive"


# ── TDM ────────────────────────────────────────────────────────────────────────

TDM_RANGES = {
    'digoxin':       {'lo': 0.8,  'hi': 2.0,  'unit': 'ng/mL',   'trough_only': True},
    'phenytoin':     {'lo': 10.0, 'hi': 20.0, 'unit': 'µg/mL',   'trough_only': True},
    'carbamazepine': {'lo': 4.0,  'hi': 12.0, 'unit': 'µg/mL',   'trough_only': True},
    'valproate':     {'lo': 50.0, 'hi': 100.0,'unit': 'µg/mL',   'trough_only': True},
    'lithium':       {'lo': 0.6,  'hi': 1.2,  'unit': 'mmol/L',  'trough_only': True},
    'gentamicin':    {'lo': 5.0,  'hi': 10.0, 'unit': 'µg/mL',   'trough_only': False},
    'vancomycin':    {'lo': 15.0, 'hi': 20.0, 'unit': 'µg/mL',   'trough_only': False},
    'methotrexate':  {'lo': 0.0,  'hi': 0.1,  'unit': 'µmol/L',  'trough_only': False},
    'tacrolimus':    {'lo': 5.0,  'hi': 15.0, 'unit': 'ng/mL',   'trough_only': True},
    'cyclosporine':  {'lo': 100,  'hi': 300,  'unit': 'ng/mL',   'trough_only': True},
    'theophylline':  {'lo': 5.0,  'hi': 15.0, 'unit': 'µg/mL',   'trough_only': False},
    'amikacin':      {'lo': 20.0, 'hi': 35.0, 'unit': 'µg/mL',   'trough_only': False},
}


class TDMResult(models.Model):
    """Therapeutic Drug Monitoring result with AI range interpretation."""

    class SampleTiming(models.TextChoices):
        TROUGH = 'trough', 'Trough (pre-dose)'
        PEAK   = 'peak',   'Peak (post-dose)'
        RANDOM = 'random', 'Random'

    class InterpretStatus(models.TextChoices):
        SUB_THERAPEUTIC = 'sub',   'Sub-therapeutic'
        THERAPEUTIC     = 'thera', 'Therapeutic'
        SUPRA           = 'supra', 'Supra-therapeutic (Toxic)'

    class Status(models.TextChoices):
        DRAFT     = 'draft',     'Draft'
        VALIDATED = 'validated', 'Validated'

    request         = models.OneToOneField(ToxicologyRequest, on_delete=models.CASCADE, related_name='tdm')
    drug_name       = models.CharField(max_length=60)
    measured_level  = models.DecimalField(max_digits=8, decimal_places=3)
    unit            = models.CharField(max_length=20)
    sample_timing   = models.CharField(max_length=10, choices=SampleTiming.choices)
    patient_weight  = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text='kg')
    patient_age     = models.PositiveSmallIntegerField(null=True, blank=True)
    indication      = models.CharField(max_length=200, blank=True)
    dose_regimen    = models.CharField(max_length=100, blank=True)

    therapeutic_range_lo = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    therapeutic_range_hi = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    interp_status   = models.CharField(max_length=10, choices=InterpretStatus.choices, blank=True)

    ai_interpretation    = models.JSONField(default=dict, blank=True)
    dose_recommendation  = models.TextField(blank=True)
    toxicity_risk        = models.BooleanField(default=False)

    status        = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    validated_by  = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    validated_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"TDM #{self.pk} {self.drug_name} {self.measured_level}{self.unit} [{self.interp_status}]"

    def set_range_from_drug(self):
        if self.drug_name.lower() in TDM_RANGES:
            r = TDM_RANGES[self.drug_name.lower()]
            self.therapeutic_range_lo = r['lo']
            self.therapeutic_range_hi = r['hi']
            self.unit = r['unit']

    def classify(self):
        if self.therapeutic_range_lo and self.therapeutic_range_hi:
            v = float(self.measured_level)
            if v < float(self.therapeutic_range_lo):
                self.interp_status = self.InterpretStatus.SUB_THERAPEUTIC
            elif v > float(self.therapeutic_range_hi):
                self.interp_status = self.InterpretStatus.SUPRA
                self.toxicity_risk = True
            else:
                self.interp_status = self.InterpretStatus.THERAPEUTIC


class PoisoningCase(models.Model):
    """Acute poisoning / toxic substance assessment."""

    class Severity(models.TextChoices):
        MILD     = 'mild',     'Mild'
        MODERATE = 'moderate', 'Moderate'
        SEVERE   = 'severe',   'Severe'
        LETHAL   = 'lethal',   'Potentially Lethal'

    class Substance(models.TextChoices):
        ORGANOPHOSPHATE = 'organophosphate', 'Organophosphates / Pesticides'
        PARACETAMOL     = 'paracetamol',     'Paracetamol / Acetaminophen'
        SALICYLATE      = 'salicylate',      'Salicylates (Aspirin)'
        ALCOHOL         = 'alcohol',         'Ethanol (Alcohol)'
        METHANOL        = 'methanol',        'Methanol / Ethylene Glycol'
        HEAVY_METAL     = 'heavy_metal',     'Heavy Metals (Pb, As, Hg)'
        CO              = 'co',              'Carbon Monoxide'
        CYANIDE         = 'cyanide',         'Cyanide'
        BENZODIAZEPINE  = 'benzodiazepine',  'Benzodiazepines'
        OPIOID          = 'opioid',          'Opioids / Morphine'
        RODENTICIDE     = 'rodenticide',     'Rodenticide (Warfarin-type)'
        OTHER           = 'other',           'Other'

    request             = models.OneToOneField(ToxicologyRequest, on_delete=models.CASCADE, related_name='poisoning')
    substance           = models.CharField(max_length=30, choices=Substance.choices)
    substance_other     = models.CharField(max_length=100, blank=True)
    concentration       = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    concentration_unit  = models.CharField(max_length=20, blank=True)
    sample_type         = models.CharField(max_length=30, choices=[
        ('blood','Blood'),('urine','Urine'),('gastric','Gastric Content'),('hair','Hair'),
    ], default='blood')
    time_since_exposure = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text='Hours')
    is_medicolegal      = models.BooleanField(default=False)

    severity            = models.CharField(max_length=15, choices=Severity.choices, blank=True)
    lethal_threshold_exceeded = models.BooleanField(default=False)
    ai_assessment       = models.JSONField(default=dict, blank=True)
    management_guidance = models.TextField(blank=True)
    antidote            = models.CharField(max_length=200, blank=True)
    antidote_dose       = models.CharField(max_length=200, blank=True)
    referral_needed     = models.BooleanField(default=False)
    referral_facility   = models.CharField(max_length=100, blank=True)

    validated_by   = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    validated_at   = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"POI #{self.pk} {self.get_substance_display()} [{self.severity}]"
