"""Billing & Finance models — Invoices, Payments, Insurance Claims"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.conf import settings
from apps.patients.models import Patient
from apps.laboratory.models import LabRequest


class InvoiceStatus(models.TextChoices):
    DRAFT     = 'draft',    'Draft'
    PENDING   = 'pending',  'Pending'
    PARTIAL   = 'partial',  'Partial'
    PAID      = 'paid',     'Paid'
    OVERDUE   = 'overdue',  'Overdue'
    WAIVED    = 'waived',   'Waived'
    CANCELLED = 'cancelled','Cancelled'


class PaymentMethod(models.TextChoices):
    CASH         = 'cash',         'Cash'
    MOMO_MTN     = 'momo_mtn',     'MTN Mobile Money'
    MOMO_AIRTEL  = 'momo_airtel',  'Airtel Money'
    BANK_TRANSFER= 'bank_transfer','Bank Transfer'
    INSURANCE    = 'insurance',    'Insurance'
    RSSB         = 'rssb',         'RSSB'
    WAIVED       = 'waived',       'Waived / Free'


class InsuranceProvider(models.Model):
    name        = models.CharField(max_length=120)
    code        = models.CharField(max_length=20, unique=True)
    is_active   = models.BooleanField(default=True)
    coverage_pct= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    contact     = models.CharField(max_length=120, blank=True)
    notes       = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=30, unique=True, editable=False)
    patient        = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name='invoices')
    lab_request    = models.OneToOneField(LabRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice')
    hospital       = models.ForeignKey('core_config.Hospital', on_delete=models.PROTECT, null=True, blank=True)

    status         = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.PENDING)
    subtotal       = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_amount= models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_amount   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    amount_paid    = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    amount_due     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    insurance_provider = models.ForeignKey(InsuranceProvider, on_delete=models.SET_NULL, null=True, blank=True)
    insurance_claim_no = models.CharField(max_length=60, blank=True)
    insurance_coverage = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    notes          = models.TextField(blank=True)
    created_by     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_invoices')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)
    due_date       = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['status']),
            models.Index(fields=['patient', 'created_at']),
        ]

    def __str__(self):
        return f'INV-{self.invoice_number} — {self.patient.full_name}'

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            today = timezone.now().date()
            last  = Invoice.objects.filter(created_at__date=today).count() + 1
            self.invoice_number = f"{today.strftime('%Y%m%d')}-{str(last).zfill(4)}"
        self.amount_due = self.total_amount - self.amount_paid - self.insurance_coverage
        if self.amount_due <= 0:
            self.status = InvoiceStatus.PAID
        elif self.amount_paid > 0:
            self.status = InvoiceStatus.PARTIAL
        super().save(*args, **kwargs)


class InvoiceLineItem(models.Model):
    invoice     = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='line_items')
    description = models.CharField(max_length=200)
    test        = models.ForeignKey('core_config.TestCatalog', on_delete=models.SET_NULL, null=True, blank=True)
    quantity    = models.PositiveSmallIntegerField(default=1)
    unit_price  = models.DecimalField(max_digits=10, decimal_places=2)
    discount_pct= models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))
    line_total  = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        discount = self.unit_price * (self.discount_pct / 100)
        self.line_total = (self.unit_price - discount) * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.description} × {self.quantity}'


class Payment(models.Model):
    invoice       = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount        = models.DecimalField(max_digits=12, decimal_places=2)
    method        = models.CharField(max_length=20, choices=PaymentMethod.choices)
    reference_no  = models.CharField(max_length=80, blank=True)
    received_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    received_at   = models.DateTimeField(default=timezone.now)
    notes         = models.TextField(blank=True)

    class Meta:
        ordering = ['-received_at']

    def __str__(self):
        return f'{self.invoice.invoice_number} — {self.method} {self.amount}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        inv = self.invoice
        inv.amount_paid = sum(p.amount for p in inv.payments.all())
        inv.save(update_fields=['amount_paid', 'amount_due', 'status', 'updated_at'])
