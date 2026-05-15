"""Quality Management models — IQC, EQA, SOP, NCR/CAPA, ISO 15189 checklist"""
from django.db import models
from django.utils import timezone


class IQCResult(models.Model):
    """Internal Quality Control run — one data point on a Levey-Jennings chart."""

    class Level(models.TextChoices):
        LOW    = 'low',    'Low Control'
        NORMAL = 'normal', 'Normal Control'
        HIGH   = 'high',   'High Control'

    class WestgardStatus(models.TextChoices):
        PASS    = 'pass',    '✅ Pass'
        WARNING = 'warning', '⚠️ 1:2S Warning'
        REJECT  = 'reject',  '❌ Reject'

    analyte        = models.CharField(max_length=60)
    control_level  = models.CharField(max_length=10, choices=Level.choices)
    run_number     = models.PositiveIntegerField()
    run_date       = models.DateField(default=timezone.now)

    measured_value = models.DecimalField(max_digits=10, decimal_places=3)
    target_mean    = models.DecimalField(max_digits=10, decimal_places=3)
    target_sd      = models.DecimalField(max_digits=8,  decimal_places=4)
    unit           = models.CharField(max_length=20, blank=True)

    z_score        = models.DecimalField(max_digits=6,  decimal_places=3, null=True, blank=True)
    cv_percent     = models.DecimalField(max_digits=6,  decimal_places=2, null=True, blank=True)
    bias_percent   = models.DecimalField(max_digits=6,  decimal_places=2, null=True, blank=True)

    westgard_status = models.CharField(max_length=10, choices=WestgardStatus.choices, default=WestgardStatus.PASS)
    westgard_rule   = models.CharField(max_length=20, blank=True, help_text='e.g. 1:3S, 2:2S, 10x')

    analyzer       = models.ForeignKey(
        'iot_analyzers.AnalyzerDevice', on_delete=models.SET_NULL, null=True, blank=True)
    shift          = models.CharField(max_length=20, blank=True)
    performed_by   = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='iqc_runs')
    reviewed_by    = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='iqc_reviewed')

    action_taken   = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['analyte', 'run_number']
        indexes  = [models.Index(fields=['analyte', 'control_level', 'run_date'])]

    def __str__(self):
        return f"IQC {self.analyte} L{self.control_level} R{self.run_number} = {self.measured_value} [{self.westgard_status}]"

    def save(self, *args, **kwargs):
        if self.target_sd:
            self.z_score = (self.measured_value - self.target_mean) / self.target_sd
        super().save(*args, **kwargs)


class EQAProgram(models.Model):
    """External Quality Assurance program registration."""

    class Cycle(models.TextChoices):
        MONTHLY    = 'monthly',    'Monthly'
        QUARTERLY  = 'quarterly',  'Quarterly'
        BIANNUAL   = 'biannual',   'Biannual'
        ANNUAL     = 'annual',     'Annual'

    name           = models.CharField(max_length=150)
    provider       = models.CharField(max_length=100)
    analytes       = models.TextField(help_text='Comma-separated analyte names')
    cycle          = models.CharField(max_length=15, choices=Cycle.choices)
    contact_email  = models.EmailField(blank=True)
    is_active      = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.provider})"


class EQASubmission(models.Model):
    """A single EQA submission/result for a cycle."""

    class Result(models.TextChoices):
        PASS = 'pass', '✅ Pass'
        FAIL = 'fail', '❌ Fail'
        PENDING = 'pending', 'Pending'

    program        = models.ForeignKey(EQAProgram, on_delete=models.CASCADE, related_name='submissions')
    cycle_label    = models.CharField(max_length=30, help_text='e.g. Q2 2026')
    submission_date= models.DateField(null=True, blank=True)
    deadline       = models.DateField()
    z_score        = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    result         = models.CharField(max_length=10, choices=Result.choices, default=Result.PENDING)
    analyte_results= models.JSONField(default=dict, blank=True)
    submitted_by   = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering  = ['-deadline']
        unique_together = [['program', 'cycle_label']]

    def __str__(self):
        return f"{self.program.name} — {self.cycle_label} ({self.result})"


class SOPDocument(models.Model):
    """Standard Operating Procedure document."""

    class SOPStatus(models.TextChoices):
        CURRENT  = 'current',  '✅ Current'
        REVIEW   = 'review',   '⚠️ Review Due'
        OVERDUE  = 'overdue',  '❌ Overdue'
        RETIRED  = 'retired',  '🗃️ Retired'
        DRAFT    = 'draft',    '📝 Draft'

    code           = models.CharField(max_length=30, unique=True)
    title          = models.CharField(max_length=200)
    department     = models.ForeignKey(
        'core_config.LaboratoryDepartment', on_delete=models.SET_NULL, null=True, blank=True)
    version        = models.CharField(max_length=10, default='1.0')
    effective_date = models.DateField()
    review_date    = models.DateField()
    status         = models.CharField(max_length=10, choices=SOPStatus.choices, default=SOPStatus.DRAFT)
    document_file  = models.FileField(upload_to='sops/', null=True, blank=True)
    content        = models.TextField(blank=True)
    approved_by    = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='sops_approved')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} v{self.version} — {self.title}"

    def update_status(self):
        today = timezone.now().date()
        if self.review_date < today:
            self.status = self.SOPStatus.OVERDUE
        elif (self.review_date - today).days <= 60:
            self.status = self.SOPStatus.REVIEW
        else:
            self.status = self.SOPStatus.CURRENT
        self.save(update_fields=['status'])


class SOPSignoff(models.Model):
    """Staff acknowledgement/signoff on a SOP."""

    sop        = models.ForeignKey(SOPDocument, on_delete=models.CASCADE, related_name='signoffs')
    user       = models.ForeignKey('authentication.NexusUser', on_delete=models.CASCADE)
    signed_at  = models.DateTimeField(default=timezone.now)
    notes      = models.TextField(blank=True)

    class Meta:
        unique_together = [['sop', 'user']]
        ordering        = ['-signed_at']

    def __str__(self):
        return f"{self.user} signed {self.sop.code}"


class NonConformity(models.Model):
    """Non-conformity report (NCR)."""

    class NCRType(models.TextChoices):
        PRE_ANALYTICAL  = 'pre_analytical',  'Pre-analytical'
        ANALYTICAL      = 'analytical',      'Analytical'
        POST_ANALYTICAL = 'post_analytical', 'Post-analytical'
        EQUIPMENT       = 'equipment',       'Equipment'
        ADMINISTRATIVE  = 'administrative',  'Administrative'
        PATIENT_SAFETY  = 'patient_safety',  'Patient Safety'
        DOCUMENTATION   = 'documentation',   'Documentation'

    class Severity(models.TextChoices):
        MINOR    = 'minor',    'Minor'
        MODERATE = 'moderate', 'Moderate'
        MAJOR    = 'major',    'Major'
        CRITICAL = 'critical', 'Critical'

    class NCRStatus(models.TextChoices):
        OPEN        = 'open',        'Open'
        IN_PROGRESS = 'in_progress', 'In Progress'
        CLOSED      = 'closed',      'Closed'
        OVERDUE     = 'overdue',     'Overdue'

    ncr_number      = models.CharField(max_length=20, unique=True)
    ncr_type        = models.CharField(max_length=25, choices=NCRType.choices)
    severity        = models.CharField(max_length=10, choices=Severity.choices)
    description     = models.TextField()
    immediate_action= models.TextField(blank=True)
    root_cause      = models.TextField(blank=True)
    detected_at     = models.DateTimeField(default=timezone.now)
    reported_by     = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, related_name='ncrs_reported')
    owner           = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='ncrs_owned')
    due_date        = models.DateField(null=True, blank=True)
    closed_date     = models.DateField(null=True, blank=True)
    status          = models.CharField(max_length=15, choices=NCRStatus.choices, default=NCRStatus.OPEN)
    lab_request     = models.ForeignKey(
        'laboratory.LabRequest', on_delete=models.SET_NULL, null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering  = ['-created_at']
        verbose_name_plural = 'Non-conformities'

    def __str__(self):
        return f"{self.ncr_number} — {self.get_severity_display()} {self.get_ncr_type_display()}"

    def save(self, *args, **kwargs):
        if not self.ncr_number:
            last = NonConformity.objects.order_by('id').last()
            seq  = (last.id + 1) if last else 1
            self.ncr_number = f"NCR-{seq:04d}"
        super().save(*args, **kwargs)


class CAPA(models.Model):
    """Corrective and Preventive Action linked to a NonConformity."""

    class CAPAStatus(models.TextChoices):
        DRAFT       = 'draft',       'Draft'
        IN_PROGRESS = 'in_progress', 'In Progress'
        VERIFICATION= 'verification','Under Verification'
        CLOSED      = 'closed',      'Closed — Effective'
        INEFFECTIVE = 'ineffective', 'Closed — Ineffective'

    capa_number     = models.CharField(max_length=20, unique=True)
    ncr             = models.ForeignKey(NonConformity, on_delete=models.CASCADE, related_name='capas')
    title           = models.CharField(max_length=200)
    root_cause_analysis = models.TextField(blank=True)
    steps           = models.JSONField(default=list, blank=True,
        help_text='[{step, description, owner, due_date, completed}]')
    effectiveness_check = models.TextField(blank=True)
    status          = models.CharField(max_length=15, choices=CAPAStatus.choices, default=CAPAStatus.DRAFT)
    owner           = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    due_date        = models.DateField(null=True, blank=True)
    closed_date     = models.DateField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'CAPA'
        verbose_name_plural = 'CAPAs'

    def __str__(self):
        return f"{self.capa_number} — {self.title}"

    @property
    def steps_done(self):
        return sum(1 for s in self.steps if s.get('completed'))

    @property
    def steps_total(self):
        return len(self.steps)

    def save(self, *args, **kwargs):
        if not self.capa_number:
            last = CAPA.objects.order_by('id').last()
            seq  = (last.id + 1) if last else 1
            self.capa_number = f"CAPA-{seq:04d}"
        super().save(*args, **kwargs)


class ISOClause(models.Model):
    """ISO 15189:2022 compliance clause tracking."""

    class ComplianceStatus(models.TextChoices):
        COMPLIANT     = 'compliant',     '✅ Compliant'
        PARTIAL       = 'partial',       '⚠️ Partial'
        NON_COMPLIANT = 'non_compliant', '❌ Non-Compliant'
        NA            = 'na',            '— N/A'

    clause_code    = models.CharField(max_length=10, unique=True)
    title          = models.CharField(max_length=200)
    description    = models.TextField(blank=True)
    status         = models.CharField(max_length=15, choices=ComplianceStatus.choices, default=ComplianceStatus.NON_COMPLIANT)
    evidence       = models.TextField(blank=True)
    evidence_files = models.JSONField(default=list, blank=True)
    responsible    = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    last_reviewed  = models.DateField(null=True, blank=True)
    notes          = models.TextField(blank=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['clause_code']

    def __str__(self):
        return f"ISO {self.clause_code} — {self.title} [{self.status}]"
