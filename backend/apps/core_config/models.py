"""Core configuration models — Hospital, Department, Test Catalog"""
from django.db import models


class Hospital(models.Model):
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to='hospitals/', blank=True, null=True)
    address = models.TextField()
    district = models.CharField(max_length=100)
    province = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    hospital_type = models.CharField(
        max_length=20,
        choices=[('public', 'Public'), ('private', 'Private'), ('mission', 'Mission'), ('clinic', 'Clinic')],
        default='public'
    )
    has_lab = models.BooleanField(default=True)
    has_clinic = models.BooleanField(default=True)
    has_radiology = models.BooleanField(default=False)
    has_pharmacy = models.BooleanField(default=False)
    rbc_code = models.CharField(max_length=20, blank=True, help_text="Rwanda Biomedical Centre facility code")
    minisante_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hospitals'

    def __str__(self):
        return self.name


class LaboratoryDepartment(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=10)
    color_hex = models.CharField(max_length=7, default='#0099FF')
    tube_color = models.CharField(max_length=20, blank=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='departments')
    head = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='headed_departments'
    )
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'lab_departments'
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class TestCatalog(models.Model):
    """Master list of all laboratory tests."""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=50)
    department = models.ForeignKey(LaboratoryDepartment, on_delete=models.CASCADE, related_name='tests')
    specimen_type = models.CharField(max_length=100)
    tube_type = models.CharField(
        max_length=30,
        choices=[
            ('purple_edta', 'Purple / EDTA'),
            ('red_plain', 'Red / Plain'),
            ('yellow_sst', 'Yellow / SST'),
            ('blue_citrate', 'Blue / Citrate'),
            ('green_heparin', 'Green / Heparin'),
            ('grey_fluoride', 'Grey / Fluoride'),
            ('urine_container', 'Urine Container'),
            ('stool_container', 'Stool Container'),
            ('swab', 'Swab'),
            ('other', 'Other'),
        ],
        default='red_plain'
    )
    tat_hours = models.DecimalField(max_digits=5, decimal_places=1, default=2.0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reference_range = models.TextField(blank=True)
    unit = models.CharField(max_length=50, blank=True)
    method = models.CharField(max_length=200, blank=True)
    requires_phlebotomy = models.BooleanField(default=True)
    is_panel = models.BooleanField(default=False)
    panel_tests = models.ManyToManyField('self', blank=True, symmetrical=False)
    loinc_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    order_in_department = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'test_catalog'
        ordering = ['department__order', 'order_in_department', 'name']

    def __str__(self):
        return f"{self.name} [{self.code}]"


class ReferenceRange(models.Model):
    """
    Versioned, structured reference range for any laboratory test.
    Spec: department-based, test-based, age/sex-sensitive, method-dependent.
    Old ranges are NEVER deleted — version history is permanent for medico-legal traceability.
    """

    class Sex(models.TextChoices):
        MALE   = 'M', 'Male'
        FEMALE = 'F', 'Female'
        ANY    = '',  'Any (Both)'

    test          = models.ForeignKey(TestCatalog, on_delete=models.CASCADE, related_name='reference_ranges')
    department    = models.ForeignKey(LaboratoryDepartment, on_delete=models.CASCADE, related_name='reference_ranges')

    # Numeric range
    min_value     = models.FloatField(null=True, blank=True)
    max_value     = models.FloatField(null=True, blank=True)
    critical_low  = models.FloatField(null=True, blank=True, help_text='Value below this = Critical Low (LL)')
    critical_high = models.FloatField(null=True, blank=True, help_text='Value above this = Critical High (HH)')
    unit          = models.CharField(max_length=50)

    # Qualitative ranges
    expected_value= models.CharField(max_length=100, blank=True, help_text='For qualitative tests e.g. Negative')
    negative_value= models.CharField(max_length=50, blank=True)
    positive_label= models.CharField(max_length=50, blank=True)

    # Demographics sensitivity
    sex           = models.CharField(max_length=1, choices=Sex.choices, default=Sex.ANY, blank=True)
    age_min_years = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Minimum age (years)')
    age_max_years = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Maximum age (years); null = no upper limit')

    # Method sensitivity (different analyzers may have different ranges)
    method        = models.CharField(max_length=100, blank=True, help_text='e.g. Hexokinase, Colorimetric, PCR')
    analyzer      = models.CharField(max_length=100, blank=True, help_text='e.g. Sysmex XN-1000, Cobas 6000')

    # Versioning — IMMUTABLE history
    version       = models.PositiveSmallIntegerField(default=1)
    is_active     = models.BooleanField(default=True, help_text='Only one active range per test/dept/sex/age group')
    superseded_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='supersedes')

    # Source
    source        = models.CharField(max_length=200, blank=True, help_text='e.g. WHO 2023, ISO 15189, Internal validation')
    notes         = models.TextField(blank=True)

    created_by    = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table  = 'reference_ranges'
        ordering  = ['test', 'department', 'sex', 'age_min_years', '-version']
        indexes   = [
            models.Index(fields=['test', 'department', 'is_active']),
            models.Index(fields=['test', 'sex', 'age_min_years', 'is_active']),
        ]

    def __str__(self):
        age_str = ''
        if self.age_min_years is not None:
            age_str = f' {self.age_min_years}–{self.age_max_years or "∞"}y'
        sex_str = f' ({self.sex})' if self.sex else ''
        return f"{self.test.name}{sex_str}{age_str} v{self.version}: {self.min_value}–{self.max_value} {self.unit}"

    def get_range_display(self):
        if self.min_value is not None and self.max_value is not None:
            return f"{self.min_value}–{self.max_value} {self.unit}"
        if self.expected_value:
            return self.expected_value
        return '—'

    def flag_value(self, value: float) -> str:
        """Auto-flag a numeric value against this range. Returns HH/LL/H/L/N."""
        if value is None:
            return 'N'
        if self.critical_low is not None and value <= self.critical_low:
            return 'LL'
        if self.critical_high is not None and value >= self.critical_high:
            return 'HH'
        if self.min_value is not None and value < self.min_value:
            return 'L'
        if self.max_value is not None and value > self.max_value:
            return 'H'
        return 'N'

    def save(self, *args, **kwargs):
        """Deactivate previous versions when a new range is saved as active."""
        if self.is_active and self.pk is None:
            ReferenceRange.objects.filter(
                test=self.test, department=self.department,
                sex=self.sex or '',
                age_min_years=self.age_min_years,
                age_max_years=self.age_max_years,
                is_active=True,
            ).update(is_active=False)
        super().save(*args, **kwargs)


class TestConsumable(models.Model):
    """
    Maps each laboratory test to the consumables it requires.
    Drives the billing consumable engine and inventory deduction.
    Spec: test_consumables table — test_name, item_name, quantity_required.
    """
    test              = models.ForeignKey(TestCatalog, on_delete=models.CASCADE, related_name='consumables')
    item_name         = models.CharField(max_length=200, help_text='Must match InventoryItem.name exactly')
    item_code         = models.CharField(max_length=30, blank=True, help_text='InventoryItem.code for exact match')
    quantity_required = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    unit              = models.CharField(max_length=30, blank=True)
    unit_cost         = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_mandatory      = models.BooleanField(default=True, help_text='Mandatory consumables cannot be removed from billing')
    notes             = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table        = 'test_consumables'
        unique_together = [['test', 'item_code']]
        ordering        = ['test', 'item_name']

    def __str__(self):
        return f"{self.test.name} → {self.item_name} ×{self.quantity_required}"

    @property
    def line_total(self):
        return float(self.quantity_required) * float(self.unit_cost)


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        'authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        db_table = 'system_settings'

    def __str__(self):
        return self.key

    @classmethod
    def get(cls, key, default=''):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
