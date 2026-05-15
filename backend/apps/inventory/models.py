"""Inventory & Supply Chain models — Reagents, Consumables, Equipment"""
from decimal import Decimal
from django.db import models
from django.utils import timezone


class ItemCategory(models.TextChoices):
    REAGENT       = 'reagent',      'Reagent'
    CONSUMABLE    = 'consumable',   'Consumable'
    EQUIPMENT     = 'equipment',    'Equipment'
    CONTROL       = 'qc_control',   'QC Control'
    STAIN         = 'stain',        'Stain / Dye'
    CULTURE_MEDIA = 'culture_media','Culture Media'
    PPE           = 'ppe',          'PPE'
    OTHER         = 'other',        'Other'


class StockStatus(models.TextChoices):
    IN_STOCK       = 'in_stock',      'In Stock'
    LOW_STOCK      = 'low_stock',     'Low Stock'
    OUT_OF_STOCK   = 'out_of_stock',  'Out of Stock'
    EXPIRED        = 'expired',       'Expired'
    EXPIRING_SOON  = 'expiring_soon', 'Expiring Soon'
    DISCONTINUED   = 'discontinued',  'Discontinued'


class MovementType(models.TextChoices):
    RESTOCK  = 'restock',  'Restock / Received'
    ISSUE    = 'issue',    'Issued / Used'
    ADJUST   = 'adjust',   'Adjustment'
    EXPIRED  = 'expired',  'Expired Disposal'
    RETURN   = 'return',   'Return to Supplier'
    TRANSFER = 'transfer', 'Department Transfer'


class Supplier(models.Model):
    name         = models.CharField(max_length=150)
    contact_name = models.CharField(max_length=100, blank=True)
    phone        = models.CharField(max_length=30, blank=True)
    email        = models.EmailField(blank=True)
    address      = models.TextField(blank=True)
    is_active    = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    code          = models.CharField(max_length=30, unique=True)
    name          = models.CharField(max_length=200)
    brand         = models.CharField(max_length=100, blank=True)
    category      = models.CharField(max_length=20, choices=ItemCategory.choices, default=ItemCategory.REAGENT)
    department    = models.ForeignKey('core_config.LaboratoryDepartment', on_delete=models.SET_NULL, null=True, blank=True)
    hospital      = models.ForeignKey('core_config.Hospital', on_delete=models.SET_NULL, null=True, blank=True)
    supplier      = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)

    unit          = models.CharField(max_length=30, default='unit')
    current_stock = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    min_stock     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('10.00'))
    max_stock     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100.00'))
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('20.00'))

    unit_cost     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    storage_temp  = models.CharField(max_length=40, blank=True, help_text='e.g. 2–8°C, -20°C, Room temp')
    cold_chain    = models.BooleanField(default=False)

    expiry_date   = models.DateField(null=True, blank=True)
    batch_number  = models.CharField(max_length=60, blank=True)
    catalog_no    = models.CharField(max_length=60, blank=True)

    status        = models.CharField(max_length=20, choices=StockStatus.choices, default=StockStatus.IN_STOCK)
    is_active     = models.BooleanField(default=True)

    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name']
        indexes  = [
            models.Index(fields=['status']),
            models.Index(fields=['category', 'department']),
            models.Index(fields=['expiry_date']),
        ]

    def __str__(self):
        return f'{self.code} — {self.name}'

    def save(self, *args, **kwargs):
        self._update_status()
        super().save(*args, **kwargs)

    def _update_status(self):
        today = timezone.now().date()
        if self.expiry_date and self.expiry_date < today:
            self.status = StockStatus.EXPIRED
        elif self.expiry_date and (self.expiry_date - today).days <= 30:
            self.status = StockStatus.EXPIRING_SOON
        elif self.current_stock <= 0:
            self.status = StockStatus.OUT_OF_STOCK
        elif self.current_stock <= self.min_stock:
            self.status = StockStatus.LOW_STOCK
        else:
            self.status = StockStatus.IN_STOCK

    @property
    def stock_pct(self):
        if self.max_stock <= 0:
            return 0
        return min(int((self.current_stock / self.max_stock) * 100), 100)

    @property
    def days_to_expiry(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.now().date()).days


class StockMovement(models.Model):
    item          = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity      = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    batch_number  = models.CharField(max_length=60, blank=True)
    expiry_date   = models.DateField(null=True, blank=True)
    supplier      = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    unit_cost     = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    department    = models.ForeignKey('core_config.LaboratoryDepartment', on_delete=models.SET_NULL, null=True, blank=True)
    notes         = models.TextField(blank=True)
    performed_by  = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True)
    performed_at  = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-performed_at']

    def __str__(self):
        sign = '+' if self.movement_type in ('restock', 'return') else '-'
        return f'{self.item.code} {sign}{self.quantity} ({self.movement_type})'

    def save(self, *args, **kwargs):
        item = self.item
        if self.movement_type in (MovementType.RESTOCK, MovementType.RETURN):
            item.current_stock += self.quantity
        elif self.movement_type in (MovementType.ISSUE, MovementType.EXPIRED):
            item.current_stock = max(Decimal('0'), item.current_stock - self.quantity)
        elif self.movement_type == MovementType.ADJUST:
            item.current_stock = self.quantity
        self.balance_after = item.current_stock
        if self.batch_number:
            item.batch_number = self.batch_number
        if self.expiry_date:
            item.expiry_date = self.expiry_date
        if self.unit_cost:
            item.unit_cost = self.unit_cost
        item.save()
        super().save(*args, **kwargs)


class PurchaseOrder(models.Model):
    class POStatus(models.TextChoices):
        DRAFT     = 'draft',    'Draft'
        SUBMITTED = 'submitted','Submitted'
        APPROVED  = 'approved', 'Approved'
        RECEIVED  = 'received', 'Received'
        CANCELLED = 'cancelled','Cancelled'

    po_number    = models.CharField(max_length=30, unique=True, editable=False)
    supplier     = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    hospital     = models.ForeignKey('core_config.Hospital', on_delete=models.SET_NULL, null=True, blank=True)
    status       = models.CharField(max_length=20, choices=POStatus.choices, default=POStatus.DRAFT)
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    notes        = models.TextField(blank=True)
    requested_by = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, related_name='po_requests')
    approved_by  = models.ForeignKey('authentication.NexusUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='po_approvals')
    expected_date= models.DateField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'PO-{self.po_number} — {self.supplier.name}'

    def save(self, *args, **kwargs):
        if not self.po_number:
            today = timezone.now().date()
            last  = PurchaseOrder.objects.filter(created_at__date=today).count() + 1
            self.po_number = f"PO-{today.strftime('%Y%m%d')}-{str(last).zfill(3)}"
        super().save(*args, **kwargs)
