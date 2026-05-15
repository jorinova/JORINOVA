"""Patient models — Demographics, Guardian, Medical history, LID"""
import random
import string
import hashlib
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta


def generate_unique_lab_id():
    """7-digit permanent unique lab ID (per-hospital)."""
    while True:
        uid = ''.join(random.choices(string.digits, k=7))
        if not Patient.objects.filter(unique_lab_id=uid).exists():
            return uid


def generate_lid():
    """
    Lifelong Patient ID (LID) — permanent cross-hospital identifier.
    Format: NXS-LID-YYYY-XXXXXXX
    Globally unique, never changes regardless of hospital visited.
    """
    year = timezone.now().strftime('%Y')
    while True:
        seq = ''.join(random.choices(string.digits, k=7))
        lid = f"NXS-LID-{year}-{seq}"
        if not Patient.objects.filter(lid=lid).exists():
            return lid


def generate_pid():
    """Patient ID: PID-YYYYMMDD-XXXX (per-facility visit ID)."""
    date_part = timezone.now().strftime('%Y%m%d')
    seq = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    pid = f"PID-{date_part}-{seq}"
    if Patient.objects.filter(pid=pid).exists():
        return generate_pid()
    return pid


class District(models.TextChoices):
    NYARUGENGE = 'Nyarugenge', 'Nyarugenge'
    GASABO = 'Gasabo', 'Gasabo'
    KICUKIRO = 'Kicukiro', 'Kicukiro'
    BURERA = 'Burera', 'Burera'
    GICUMBI = 'Gicumbi', 'Gicumbi'
    GAKENKE = 'Gakenke', 'Gakenke'
    MUSANZE = 'Musanze', 'Musanze'
    RULINDO = 'Rulindo', 'Rulindo'
    RUBAVU = 'Rubavu', 'Rubavu'
    NGORORERO = 'Ngororero', 'Ngororero'
    KARONGI = 'Karongi', 'Karongi'
    NYABIHU = 'Nyabihu', 'Nyabihu'
    RUTSIRO = 'Rutsiro', 'Rutsiro'
    NYAMASHEKE = 'Nyamasheke', 'Nyamasheke'
    RUSIZI = 'Rusizi', 'Rusizi'
    GISAGARA = 'Gisagara', 'Gisagara'
    HUYE = 'Huye', 'Huye'
    KAMONYI = 'Kamonyi', 'Kamonyi'
    MUHANGA = 'Muhanga', 'Muhanga'
    NYAMAGABE = 'Nyamagabe', 'Nyamagabe'
    NYANZA = 'Nyanza', 'Nyanza'
    NYARUGURU = 'Nyaruguru', 'Nyaruguru'
    RUHANGO = 'Ruhango', 'Ruhango'
    BUGESERA = 'Bugesera', 'Bugesera'
    GATSIBO = 'Gatsibo', 'Gatsibo'
    KAYONZA = 'Kayonza', 'Kayonza'
    KIREHE = 'Kirehe', 'Kirehe'
    NGOMA = 'Ngoma', 'Ngoma'
    NYAGATARE = 'Nyagatare', 'Nyagatare'
    RWAMAGANA = 'Rwamagana', 'Rwamagana'
    OTHER = 'Other', 'Other / Foreign'


class Patient(models.Model):
    """Central patient record — permanent identity with cross-hospital LID."""

    # ── Permanent Lifelong ID (cross-hospital, never changes) ──────────────
    lid = models.CharField(
        max_length=25, unique=True, default=generate_lid, editable=False,
        help_text='Lifelong Patient ID — permanent, cross-hospital, auto-generated'
    )
    # ── Per-hospital / per-visit identifiers ──────────────────────────────
    pid = models.CharField(max_length=30, unique=True, default=generate_pid, editable=False)
    unique_lab_id = models.CharField(max_length=7, unique=True, default=generate_unique_lab_id, editable=False)
    record_number = models.CharField(max_length=30, blank=True)
    archive_code = models.CharField(max_length=30, blank=True)

    # ── External / clinic sync IDs ─────────────────────────────────────────
    clinic_pid        = models.CharField(max_length=50, blank=True, help_text='Clinic-generated PID (synced from referring clinic)')
    external_facility = models.CharField(max_length=120, blank=True, help_text='Referring clinic / external facility name')
    national_health_id= models.CharField(max_length=50, blank=True, help_text='Ministry of Health National Health ID (Mutuelle/RSSB)')
    rssb_number       = models.CharField(max_length=30, blank=True, help_text='RSSB Insurance Number')

    family_name = models.CharField(max_length=100)
    other_names = models.CharField(max_length=200)
    date_of_birth = models.DateField()
    gender = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')]
    )
    person_id = models.CharField(max_length=30, blank=True, help_text="National ID / Passport")
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    district = models.CharField(max_length=50, choices=District.choices, blank=True)
    province = models.CharField(max_length=50, blank=True)
    nationality = models.CharField(max_length=50, default='Rwandan')
    photo = models.ImageField(upload_to='patients/photos/', blank=True, null=True)
    fingerprint_hash = models.CharField(max_length=512, blank=True)
    blood_group = models.CharField(
        max_length=10,
        choices=[
            ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
            ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'), ('unknown', 'Unknown')
        ],
        default='unknown'
    )
    allergies = models.TextField(blank=True)
    chronic_conditions = models.TextField(blank=True)
    hiv_status = models.CharField(
        max_length=20,
        choices=[('positive', 'Positive'), ('negative', 'Negative'), ('unknown', 'Unknown'), ('not_disclosed', 'Not Disclosed')],
        default='not_disclosed'
    )
    hospital = models.ForeignKey('core_config.Hospital', on_delete=models.CASCADE, related_name='patients')
    registered_by = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='registered_patients'
    )
    is_inpatient = models.BooleanField(default=False)
    ward = models.CharField(max_length=50, blank=True)
    bed_number = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'patients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['lid']),
            models.Index(fields=['pid']),
            models.Index(fields=['unique_lab_id']),
            models.Index(fields=['family_name', 'other_names']),
            models.Index(fields=['person_id']),
            models.Index(fields=['national_health_id']),
        ]

    def __str__(self):
        return f"{self.family_name} {self.other_names} [{self.pid}]"

    @property
    def full_name(self):
        return f"{self.family_name} {self.other_names}"

    @property
    def age(self):
        if self.date_of_birth:
            rd = relativedelta(timezone.now().date(), self.date_of_birth)
            if rd.years > 0:
                return f"{rd.years}y"
            elif rd.months > 0:
                return f"{rd.months}m"
            else:
                return f"{rd.days}d"
        return "N/A"

    @property
    def age_years(self):
        if self.date_of_birth:
            return relativedelta(timezone.now().date(), self.date_of_birth).years
        return 0


class Guardian(models.Model):
    """Guardian / accompanying person for a patient."""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='guardians')
    full_name = models.CharField(max_length=200)
    relationship = models.CharField(
        max_length=30,
        choices=[
            ('parent', 'Parent'), ('spouse', 'Spouse'), ('sibling', 'Sibling'),
            ('child', 'Child'), ('caretaker', 'Caretaker'), ('other', 'Other')
        ]
    )
    phone = models.CharField(max_length=20)
    national_id = models.CharField(max_length=30, blank=True)
    district = models.CharField(max_length=50, blank=True)
    is_primary = models.BooleanField(default=True)

    class Meta:
        db_table = 'guardians'

    def __str__(self):
        return f"{self.full_name} ({self.relationship} of {self.patient.full_name})"


class InsuranceProfile(models.Model):
    """Patient insurance / payment profile."""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='insurances')
    payment_type = models.CharField(
        max_length=20,
        choices=[('private', 'Private'), ('insurance', 'Insurance'), ('cg', 'Community-Based'), ('free', 'Free')]
    )
    insurance_name = models.CharField(max_length=100, blank=True)
    insurance_id = models.CharField(max_length=50, blank=True)
    policy_number = models.CharField(max_length=50, blank=True)
    coverage_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'insurance_profiles'

    def __str__(self):
        return f"{self.insurance_name or self.payment_type} — {self.patient.full_name}"


# ═══════════════════════════════════════════════════════════════
# CROSS-HOSPITAL LINKAGE — LID-based universal patient network
# ═══════════════════════════════════════════════════════════════

class PatientHospitalLink(models.Model):
    """
    Records every hospital/facility that has seen this patient under a given LID.
    Enables cross-hospital history lookup using a single LID.
    """
    patient         = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='hospital_links')
    hospital        = models.ForeignKey('core_config.Hospital', on_delete=models.CASCADE)
    local_pid       = models.CharField(max_length=50, blank=True, help_text='The PID used at this specific facility')
    local_lab_id    = models.CharField(max_length=20, blank=True)
    first_visit     = models.DateField(default=timezone.now)
    last_visit      = models.DateField(null=True, blank=True)
    visit_count     = models.PositiveIntegerField(default=1)
    is_primary_facility = models.BooleanField(default=False)
    synced_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'patient_hospital_links'
        unique_together = ['patient', 'hospital']

    def __str__(self):
        return f"{self.patient.lid} @ {self.hospital}"


class ClinicPIDSync(models.Model):
    """
    Synchronisation log for clinic-generated PIDs mapped to NXS LID.
    Clinics submit their PID; NEXUS maps it to the permanent LID.
    """
    class SyncStatus(models.TextChoices):
        PENDING   = 'pending',   'Pending'
        MATCHED   = 'matched',   'Matched to existing LID'
        CREATED   = 'created',   'New LID created'
        CONFLICT  = 'conflict',  'Conflict — manual review required'
        REJECTED  = 'rejected',  'Rejected'

    patient         = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name='clinic_syncs')
    clinic_name     = models.CharField(max_length=150)
    clinic_pid      = models.CharField(max_length=50)
    patient_name    = models.CharField(max_length=200)
    dob             = models.DateField(null=True, blank=True)
    national_id     = models.CharField(max_length=30, blank=True)
    status          = models.CharField(max_length=15, choices=SyncStatus.choices, default=SyncStatus.PENDING)
    matched_lid     = models.CharField(max_length=25, blank=True)
    confidence_pct  = models.SmallIntegerField(default=0, help_text='AI matching confidence 0-100%')
    sync_note       = models.TextField(blank=True)
    submitted_at    = models.DateTimeField(auto_now_add=True)
    resolved_at     = models.DateTimeField(null=True, blank=True)
    resolved_by     = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table   = 'clinic_pid_syncs'
        ordering   = ['-submitted_at']

    def __str__(self):
        return f"{self.clinic_name} / {self.clinic_pid} → {self.matched_lid or 'unresolved'}"
