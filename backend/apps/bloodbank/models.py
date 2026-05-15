"""
Blood Bank Models — JORINOVA NEXUS ALIS-X
Storage: Fridge/Freezer → Chambers → Numbered Slots
Tracking: FIFO / FEFO, AI Exchange, Haemovigilance
ISO 15189 compliant
"""
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator


# ─── Blood Group & Rh ─────────────────────────────────────────────────────────

class BloodGroup(models.TextChoices):
    A_POS  = 'A+',  'A+'
    A_NEG  = 'A-',  'A-'
    B_POS  = 'B+',  'B+'
    B_NEG  = 'B-',  'B-'
    AB_POS = 'AB+', 'AB+'
    AB_NEG = 'AB-', 'AB-'
    O_POS  = 'O+',  'O+'
    O_NEG  = 'O-',  'O-'


class BloodComponent(models.TextChoices):
    WHOLE_BLOOD   = 'WB',   'Whole Blood'
    PACKED_RBC    = 'PRBC', 'Packed Red Blood Cells'
    FRESH_FROZEN  = 'FFP',  'Fresh Frozen Plasma'
    PLATELETS     = 'PLT',  'Platelets'
    CRYOPRECIPITATE='CRYO', 'Cryoprecipitate'
    ALBUMIN       = 'ALB',  'Albumin'
    GRANULOCYTES  = 'GRAN', 'Granulocytes'


class BagStatus(models.TextChoices):
    QUARANTINE   = 'quarantine',  '🔒 Quarantine'
    AVAILABLE    = 'available',   '✅ Available'
    RESERVED     = 'reserved',    '📌 Reserved'
    ISSUED       = 'issued',      '🏥 Issued'
    TRANSFUSED   = 'transfused',  '💉 Transfused'
    DISCARDED    = 'discarded',   '❌ Discarded'
    EXPIRED      = 'expired',     '⏰ Expired'
    IN_TRANSIT   = 'in_transit',  '🚁 In Transit'
    EXCHANGED    = 'exchanged',   '🔄 Exchanged'


# ─── Storage Infrastructure ───────────────────────────────────────────────────

class StorageUnitType(models.TextChoices):
    FRIDGE  = 'fridge',  '❄️ Blood Refrigerator'
    FREEZER = 'freezer', '🧊 Plasma Freezer'
    PLATELET= 'platelet','🔴 Platelet Agitator'
    CRYOGENIC='cryo',    '🌡️ Cryogenic Storage'


class StorageUnit(models.Model):
    """Physical fridge or freezer unit."""
    unit_code     = models.CharField(max_length=20, unique=True)
    name          = models.CharField(max_length=100)
    unit_type     = models.CharField(max_length=20, choices=StorageUnitType.choices, default=StorageUnitType.FRIDGE)
    hospital      = models.ForeignKey('core_config.Hospital', on_delete=models.CASCADE, null=True, blank=True)
    department    = models.ForeignKey('core_config.LaboratoryDepartment', on_delete=models.SET_NULL, null=True, blank=True)

    model_name    = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=80, blank=True)
    location      = models.CharField(max_length=100, blank=True, help_text='Room/section where unit is located')

    # Temperature specs
    min_temp      = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('2.0'))
    max_temp      = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('6.0'))
    current_temp  = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    last_temp_reading = models.DateTimeField(null=True, blank=True)
    temp_alert_active = models.BooleanField(default=False)

    total_chambers= models.PositiveSmallIntegerField(default=1)
    is_active     = models.BooleanField(default=True)
    notes         = models.TextField(blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['unit_type', 'unit_code']

    def __str__(self):
        return f'{self.unit_code} — {self.name} ({self.unit_type})'

    @property
    def temp_status(self):
        if self.current_temp is None:
            return 'unknown'
        if self.min_temp <= self.current_temp <= self.max_temp:
            return 'normal'
        return 'alert'

    @property
    def capacity_used(self):
        return sum(c.slots_used for c in self.chambers.all())

    @property
    def capacity_total(self):
        return sum(c.total_slots for c in self.chambers.all())


class StorageChamber(models.Model):
    """A numbered chamber inside a storage unit (e.g., Fridge 1 → Chamber A, B, C)."""
    unit          = models.ForeignKey(StorageUnit, on_delete=models.CASCADE, related_name='chambers')
    chamber_number= models.CharField(max_length=10, help_text='e.g. A, B, 1, 2')
    label         = models.CharField(max_length=60, blank=True, help_text='e.g. Group O+, AB-')
    total_slots   = models.PositiveSmallIntegerField(default=20)
    purpose       = models.CharField(max_length=100, blank=True, help_text='e.g. O+/O- only, Platelets')
    is_active     = models.BooleanField(default=True)

    class Meta:
        ordering = ['unit', 'chamber_number']
        unique_together = ['unit', 'chamber_number']

    def __str__(self):
        return f'{self.unit.unit_code} / Chamber {self.chamber_number}'

    @property
    def slots_used(self):
        return self.blood_bags.filter(status__in=[BagStatus.AVAILABLE, BagStatus.RESERVED]).count()

    @property
    def slots_free(self):
        return max(0, self.total_slots - self.slots_used)

    @property
    def occupancy_pct(self):
        if self.total_slots == 0:
            return 0
        return int((self.slots_used / self.total_slots) * 100)


# ─── Donors ───────────────────────────────────────────────────────────────────

class Donor(models.Model):
    donor_id      = models.CharField(max_length=20, unique=True, editable=False)
    family_name   = models.CharField(max_length=80)
    other_names   = models.CharField(max_length=100)
    blood_group   = models.CharField(max_length=4, choices=BloodGroup.choices)
    date_of_birth = models.DateField()
    gender        = models.CharField(max_length=1, choices=[('M','Male'),('F','Female')])
    phone         = models.CharField(max_length=20)
    national_id   = models.CharField(max_length=30, unique=True, blank=True)
    email         = models.EmailField(blank=True)
    address       = models.TextField(blank=True)
    hospital      = models.ForeignKey('core_config.Hospital', on_delete=models.SET_NULL, null=True, blank=True)

    is_eligible   = models.BooleanField(default=True)
    deferral_reason= models.TextField(blank=True)
    deferral_until= models.DateField(null=True, blank=True)
    total_donations= models.PositiveSmallIntegerField(default=0)
    last_donation  = models.DateField(null=True, blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['family_name', 'other_names']

    def __str__(self):
        return f'{self.donor_id} — {self.family_name} {self.other_names} ({self.blood_group})'

    @property
    def full_name(self):
        return f'{self.family_name} {self.other_names}'

    def save(self, *args, **kwargs):
        if not self.donor_id:
            today = timezone.now().date()
            last  = Donor.objects.filter(created_at__date=today).count() + 1
            self.donor_id = f"DNR-{today.strftime('%Y%m%d')}-{str(last).zfill(4)}"
        super().save(*args, **kwargs)


# ─── Donations & Blood Bags ───────────────────────────────────────────────────

class DonationEvent(models.Model):
    class DonationType(models.TextChoices):
        VOLUNTARY  = 'voluntary', 'Voluntary'
        DIRECTED   = 'directed',  'Directed (Family)'
        AUTOLOGOUS = 'auto',      'Autologous'
        APHERESIS  = 'apheresis', 'Apheresis'

    donation_id   = models.CharField(max_length=20, unique=True, editable=False)
    donor         = models.ForeignKey(Donor, on_delete=models.PROTECT, related_name='donations')
    hospital      = models.ForeignKey('core_config.Hospital', on_delete=models.SET_NULL, null=True, blank=True)
    donation_type = models.CharField(max_length=15, choices=DonationType.choices, default=DonationType.VOLUNTARY)
    donation_date = models.DateField(default=timezone.now)
    collected_by  = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, related_name='donations_collected')
    volume_ml     = models.PositiveSmallIntegerField(default=450)

    # Screening results
    hiv_screen    = models.BooleanField(default=False, help_text='True = reactive/positive = DISCARD')
    hbsag_screen  = models.BooleanField(default=False)
    hcv_screen    = models.BooleanField(default=False)
    syphilis_screen= models.BooleanField(default=False)
    malaria_screen= models.BooleanField(default=False)
    screening_done= models.BooleanField(default=False)
    screening_passed= models.BooleanField(default=False)

    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-donation_date']

    def __str__(self):
        return f'{self.donation_id} — {self.donor.full_name} ({self.donation_date})'

    def save(self, *args, **kwargs):
        if not self.donation_id:
            last = DonationEvent.objects.filter(donation_date=timezone.now().date()).count() + 1
            self.donation_id = f"DON-{timezone.now().strftime('%Y%m%d')}-{str(last).zfill(3)}"
        if self.screening_done:
            self.screening_passed = not any([
                self.hiv_screen, self.hbsag_screen, self.hcv_screen,
                self.syphilis_screen, self.malaria_screen,
            ])
        super().save(*args, **kwargs)


class BloodBag(models.Model):
    """Individual blood bag — tracked by location in fridge/freezer."""
    bag_number    = models.CharField(max_length=25, unique=True, editable=False)
    donation      = models.ForeignKey(DonationEvent, on_delete=models.PROTECT, related_name='blood_bags', null=True, blank=True)
    component     = models.CharField(max_length=6, choices=BloodComponent.choices, default=BloodComponent.WHOLE_BLOOD)
    blood_group   = models.CharField(max_length=4, choices=BloodGroup.choices)
    volume_ml     = models.PositiveSmallIntegerField(default=450)
    hospital      = models.ForeignKey('core_config.Hospital', on_delete=models.SET_NULL, null=True, blank=True)

    # Storage location (Fridge → Chamber → Slot #)
    storage_unit  = models.ForeignKey(StorageUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='blood_bags')
    chamber       = models.ForeignKey(StorageChamber, on_delete=models.SET_NULL, null=True, blank=True, related_name='blood_bags')
    slot_number   = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Physical slot number in the chamber')

    status        = models.CharField(max_length=20, choices=BagStatus.choices, default=BagStatus.QUARANTINE)

    # Dates (FIFO / FEFO)
    collection_date = models.DateField(default=timezone.now)
    processing_date = models.DateField(null=True, blank=True)
    expiry_date   = models.DateField()
    stored_at     = models.DateTimeField(default=timezone.now)

    is_irradiated = models.BooleanField(default=False)
    is_leukoreduced= models.BooleanField(default=False)
    is_cmv_neg    = models.BooleanField(default=False)

    # Cross-match / issue info
    reserved_for_patient = models.ForeignKey('patients.Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='reserved_bags')
    issued_to_patient    = models.ForeignKey('patients.Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_bags')
    issued_at     = models.DateTimeField(null=True, blank=True)
    issued_by     = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='issued_bags')

    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['expiry_date', 'collection_date']   # natural FEFO / FIFO
        indexes  = [
            models.Index(fields=['blood_group', 'component', 'status']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['storage_unit', 'chamber', 'slot_number']),
        ]

    def __str__(self):
        return f'{self.bag_number} | {self.blood_group} {self.component} | Expires {self.expiry_date}'

    @property
    def days_to_expiry(self):
        return (self.expiry_date - timezone.now().date()).days

    @property
    def expiry_status(self):
        d = self.days_to_expiry
        if d < 0:   return 'expired'
        if d <= 3:  return 'critical'
        if d <= 7:  return 'warning'
        return 'ok'

    @property
    def location_label(self):
        if self.storage_unit and self.chamber and self.slot_number:
            return f'{self.storage_unit.unit_code} / Ch.{self.chamber.chamber_number} / Slot {self.slot_number}'
        return 'Unassigned'

    def save(self, *args, **kwargs):
        if not self.bag_number:
            last = BloodBag.objects.filter(collection_date=timezone.now().date()).count() + 1
            self.bag_number = f"BB-{timezone.now().strftime('%Y%m%d')}-{str(last).zfill(4)}"
        # Auto-expire
        if self.expiry_date < timezone.now().date() and self.status == BagStatus.AVAILABLE:
            self.status = BagStatus.EXPIRED
        super().save(*args, **kwargs)


# ─── Cross-Matching ───────────────────────────────────────────────────────────

class CrossmatchRecord(models.Model):
    class CrossmatchResult(models.TextChoices):
        COMPATIBLE   = 'compatible',   '✅ Compatible'
        INCOMPATIBLE = 'incompatible', '❌ Incompatible'
        WEAK_POS     = 'weak_pos',     '⚠️ Weak Positive — Review'
        PENDING      = 'pending',      '⏳ Pending'

    blood_bag     = models.ForeignKey(BloodBag, on_delete=models.CASCADE, related_name='crossmatches')
    patient       = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='crossmatches')
    lab_request   = models.ForeignKey('laboratory.LabRequest', on_delete=models.SET_NULL, null=True, blank=True)
    performed_by  = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True)
    performed_at  = models.DateTimeField(default=timezone.now)

    result        = models.CharField(max_length=20, choices=CrossmatchResult.choices, default=CrossmatchResult.PENDING)
    method        = models.CharField(max_length=60, default='Indirect Antiglobulin Test (IAT)')
    ai_flag       = models.BooleanField(default=False, help_text='AI detected potential incompatibility')
    ai_note       = models.TextField(blank=True)
    technician_note= models.TextField(blank=True)
    validated_by  = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_crossmatches')
    validated_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-performed_at']

    def __str__(self):
        return f'{self.blood_bag.bag_number} × {self.patient.full_name} — {self.result}'


# ─── Haemovigilance ───────────────────────────────────────────────────────────

class HaemovigilanceReport(models.Model):
    class ReactionType(models.TextChoices):
        FEBR_NHTR    = 'fnhtr',    'Febrile Non-Haemolytic Transfusion Reaction'
        ALLERGIC     = 'allergic', 'Allergic / Urticarial'
        ABO_HAEMO    = 'abo_haemo','Acute Haemolytic — ABO Incompatibility'
        DELAYED_HAEMO= 'del_haemo','Delayed Haemolytic'
        TACO         = 'taco',     'TACO — Transfusion-Associated Circulatory Overload'
        TRALI        = 'trali',    'TRALI — Lung Injury'
        SEPTIC       = 'septic',   'Septic Transfusion Reaction'
        GVHD         = 'gvhd',     'Transfusion-Associated GvHD'
        NEAR_MISS    = 'near_miss','Near Miss'
        WRONG_BLOOD  = 'wrong_blood','Wrong Blood in Tube'
        OTHER        = 'other',    'Other'

    class Severity(models.TextChoices):
        MILD     = 'mild',     'Mild'
        MODERATE = 'moderate', 'Moderate'
        SEVERE   = 'severe',   'Severe'
        FATAL    = 'fatal',    'Fatal'
        NEAR_MISS= 'near_miss','Near Miss / No Harm'

    report_id     = models.CharField(max_length=20, unique=True, editable=False)
    blood_bag     = models.ForeignKey(BloodBag, on_delete=models.PROTECT, related_name='haemovigilance_reports', null=True, blank=True)
    patient       = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='haemovigilance_reports')
    hospital      = models.ForeignKey('core_config.Hospital', on_delete=models.SET_NULL, null=True, blank=True)

    reaction_type = models.CharField(max_length=20, choices=ReactionType.choices)
    severity      = models.CharField(max_length=10, choices=Severity.choices)
    onset_time    = models.DateTimeField()
    transfusion_stopped = models.BooleanField(default=True)
    volume_transfused_ml= models.PositiveSmallIntegerField(default=0)

    symptoms      = models.TextField(help_text='Documented symptoms at time of reaction')
    clinical_management= models.TextField(blank=True)
    outcome       = models.TextField(blank=True)
    root_cause    = models.TextField(blank=True)
    preventive_action= models.TextField(blank=True)

    reported_by   = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, related_name='hv_reports')
    reported_at   = models.DateTimeField(auto_now_add=True)
    reviewed_by   = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='hv_reviews')
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    is_notified_to_rbc = models.BooleanField(default=False, help_text='Notified to Rwanda Biomedical Centre')

    class Meta:
        ordering = ['-reported_at']

    def __str__(self):
        return f'HV-{self.report_id} | {self.reaction_type} | {self.severity}'

    def save(self, *args, **kwargs):
        if not self.report_id:
            last = HaemovigilanceReport.objects.filter(reported_at__date=timezone.now().date()).count() + 1
            self.report_id = f"HV-{timezone.now().strftime('%Y%m%d')}-{str(last).zfill(3)}"
        super().save(*args, **kwargs)


# ─── Inter-Hospital Exchange (RBC / Zipline) ──────────────────────────────────

class ExchangePartner(models.TextChoices):
    RBC     = 'rbc',     'Rwanda Biomedical Centre (RBC)'
    ZIPLINE = 'zipline', 'Zipline Rwanda'
    DIRECT  = 'direct',  'Direct Hospital Transfer'


class InterHospitalExchange(models.Model):
    class ExchangeType(models.TextChoices):
        SEND     = 'send',    '🚁 Send to Partner'
        RECEIVE  = 'receive', '📦 Receive from Partner'
        EXCHANGE = 'exchange','🔄 Bilateral Exchange'

    class ExchangeStatus(models.TextChoices):
        AI_SUGGESTED   = 'ai_suggested',   '🤖 AI Suggested'
        PENDING_APPROVAL='pending',        '⏳ Pending RBC/Zipline Approval'
        APPROVED       = 'approved',       '✅ Approved'
        IN_TRANSIT     = 'in_transit',     '🚁 In Transit'
        COMPLETED      = 'completed',      '✔️ Completed'
        REJECTED       = 'rejected',       '❌ Rejected'
        CANCELLED      = 'cancelled',      '🚫 Cancelled'

    exchange_id    = models.CharField(max_length=25, unique=True, editable=False)
    exchange_type  = models.CharField(max_length=15, choices=ExchangeType.choices)
    partner        = models.CharField(max_length=15, choices=ExchangePartner.choices)
    status         = models.CharField(max_length=20, choices=ExchangeStatus.choices, default=ExchangeStatus.AI_SUGGESTED)

    source_hospital= models.ForeignKey('core_config.Hospital', on_delete=models.PROTECT, related_name='outgoing_exchanges')
    dest_hospital_name = models.CharField(max_length=150, blank=True)
    blood_bags     = models.ManyToManyField(BloodBag, related_name='exchanges', blank=True)

    blood_group    = models.CharField(max_length=4, choices=BloodGroup.choices)
    component      = models.CharField(max_length=6, choices=BloodComponent.choices, default=BloodComponent.PACKED_RBC)
    quantity       = models.PositiveSmallIntegerField(default=1)

    # AI reasoning
    ai_reason      = models.TextField(blank=True, help_text='AI justification for this exchange suggestion')
    ai_urgency     = models.CharField(max_length=20, default='normal',
                                       choices=[('critical','Critical'),('high','High'),('normal','Normal'),('low','Low')])
    days_to_expiry_avg = models.PositiveSmallIntegerField(null=True, blank=True)

    # Approval (one-click by RBC/Zipline)
    approval_code  = models.CharField(max_length=30, blank=True, editable=False)
    approved_by_name= models.CharField(max_length=100, blank=True)
    approved_at    = models.DateTimeField(null=True, blank=True)

    # Transport
    transport_method= models.CharField(max_length=40, default='Zipline Drone',
                                        choices=[('drone','Zipline Drone'),('courier','Road Courier'),('ambulance','Ambulance')])
    sis_score      = models.SmallIntegerField(null=True, blank=True, help_text='BioTrack Sample Integrity Score')
    tracking_code  = models.CharField(max_length=60, blank=True)
    dispatched_at  = models.DateTimeField(null=True, blank=True)
    received_at    = models.DateTimeField(null=True, blank=True)

    requested_by   = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, related_name='exchange_requests')
    created_at     = models.DateTimeField(auto_now_add=True)
    notes          = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.exchange_id} | {self.blood_group} {self.component} × {self.quantity} → {self.dest_hospital_name}'

    def save(self, *args, **kwargs):
        if not self.exchange_id:
            last = InterHospitalExchange.objects.filter(created_at__date=timezone.now().date()).count() + 1
            self.exchange_id = f"EXC-{timezone.now().strftime('%Y%m%d')}-{str(last).zfill(3)}"
        if not self.approval_code:
            import secrets
            self.approval_code = secrets.token_urlsafe(12)
        super().save(*args, **kwargs)

    def approve(self, approved_by_name='RBC'):
        """One-click approval triggers status change and auto-dispatch."""
        self.status          = self.ExchangeStatus.APPROVED
        self.approved_by_name= approved_by_name
        self.approved_at     = timezone.now()
        # Mark bags as in-transit
        self.blood_bags.filter(status=BagStatus.AVAILABLE).update(status=BagStatus.IN_TRANSIT)
        self.save(update_fields=['status', 'approved_by_name', 'approved_at'])

    def complete(self):
        """Called when bags received at destination — auto-updates inventory."""
        self.status      = self.ExchangeStatus.COMPLETED
        self.received_at = timezone.now()
        self.blood_bags.filter(status=BagStatus.IN_TRANSIT).update(status=BagStatus.EXCHANGED)
        self.save(update_fields=['status', 'received_at'])


# ─── Blood Request (internal ward/theatre) ───────────────────────────────────

class BloodRequest(models.Model):
    class Urgency(models.TextChoices):
        EMERGENCY = 'emergency', '🚨 Emergency (STAT)'
        URGENT    = 'urgent',    '⚡ Urgent (2h)'
        ROUTINE   = 'routine',   '📋 Routine'

    class RequestStatus(models.TextChoices):
        PENDING    = 'pending',    'Pending'
        CROSSMATCH = 'crossmatch', 'Cross-matching'
        READY      = 'ready',      'Ready for Issue'
        ISSUED     = 'issued',     'Issued'
        TRANSFUSED = 'transfused', 'Transfused'
        CANCELLED  = 'cancelled',  'Cancelled'

    request_id    = models.CharField(max_length=20, unique=True, editable=False)
    patient       = models.ForeignKey('patients.Patient', on_delete=models.PROTECT, related_name='blood_requests')
    hospital      = models.ForeignKey('core_config.Hospital', on_delete=models.SET_NULL, null=True, blank=True)
    lab_request   = models.ForeignKey('laboratory.LabRequest', on_delete=models.SET_NULL, null=True, blank=True)

    blood_group   = models.CharField(max_length=4, choices=BloodGroup.choices)
    component     = models.CharField(max_length=6, choices=BloodComponent.choices, default=BloodComponent.PACKED_RBC)
    units_requested= models.PositiveSmallIntegerField(default=1)
    urgency       = models.CharField(max_length=15, choices=Urgency.choices, default=Urgency.ROUTINE)
    clinical_indication= models.TextField()
    pre_transfusion_hb= models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    status        = models.CharField(max_length=15, choices=RequestStatus.choices, default=RequestStatus.PENDING)
    assigned_bags = models.ManyToManyField(BloodBag, related_name='blood_requests', blank=True)
    requested_by  = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, related_name='blood_requests')
    processed_by  = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_requests')

    ward          = models.CharField(max_length=60, blank=True)
    doctor_name   = models.CharField(max_length=100, blank=True)
    notes         = models.TextField(blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    needed_by     = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['urgency', '-created_at']

    def __str__(self):
        return f'{self.request_id} | {self.blood_group} {self.component} × {self.units_requested} | {self.urgency}'

    def save(self, *args, **kwargs):
        if not self.request_id:
            last = BloodRequest.objects.filter(created_at__date=timezone.now().date()).count() + 1
            self.request_id = f"BRQ-{timezone.now().strftime('%Y%m%d')}-{str(last).zfill(3)}"
        super().save(*args, **kwargs)


# ─── Temperature Log (Fridge/Freezer monitoring) ─────────────────────────────

class TemperatureLog(models.Model):
    storage_unit  = models.ForeignKey(StorageUnit, on_delete=models.CASCADE, related_name='temp_logs')
    temperature   = models.DecimalField(max_digits=5, decimal_places=1)
    humidity_pct  = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    is_alert      = models.BooleanField(default=False)
    alert_message = models.CharField(max_length=200, blank=True)
    source        = models.CharField(max_length=30, default='sensor',
                                      choices=[('sensor','IoT Sensor'),('manual','Manual Entry'),('api','External API')])
    recorded_by   = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    recorded_at   = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-recorded_at']
        indexes  = [models.Index(fields=['storage_unit', 'recorded_at'])]

    def __str__(self):
        return f'{self.storage_unit.unit_code} @ {self.temperature}°C — {self.recorded_at}'
