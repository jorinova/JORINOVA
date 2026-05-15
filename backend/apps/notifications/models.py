"""Notifications models — system alerts, patient SMS/email, critical results"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class NotificationType(models.TextChoices):
    CRITICAL_RESULT  = 'critical_result',  '🚨 Critical Result'
    RESULT_READY     = 'result_ready',     '✅ Result Ready'
    TAT_BREACH       = 'tat_breach',       '⏱️ TAT Breach'
    LOW_STOCK        = 'low_stock',        '⚠️ Low Stock'
    SYSTEM_ALERT     = 'system_alert',     '🔔 System Alert'
    SHIFT_CHANGE     = 'shift_change',     '🔄 Shift Change'
    SAMPLE_REJECTED  = 'sample_rejected',  '❌ Sample Rejected'
    BIOSAFETY_ALERT  = 'biosafety_alert',  '☣️ Biosafety Alert'


class NotificationChannel(models.TextChoices):
    IN_APP = 'in_app', 'In-App'
    SMS    = 'sms',    'SMS'
    EMAIL  = 'email',  'Email'


class NotificationPriority(models.TextChoices):
    LOW      = 'low',      'Low'
    NORMAL   = 'normal',   'Normal'
    HIGH     = 'high',     'High'
    CRITICAL = 'critical', 'Critical'


class Notification(models.Model):
    recipient     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    patient       = models.ForeignKey('patients.Patient', on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications')
    hospital      = models.ForeignKey('core_config.Hospital', on_delete=models.SET_NULL, null=True, blank=True)

    notification_type = models.CharField(max_length=30, choices=NotificationType.choices, default=NotificationType.SYSTEM_ALERT)
    channel       = models.CharField(max_length=15, choices=NotificationChannel.choices, default=NotificationChannel.IN_APP)
    priority      = models.CharField(max_length=15, choices=NotificationPriority.choices, default=NotificationPriority.NORMAL)

    title         = models.CharField(max_length=200)
    message       = models.TextField()
    action_url    = models.CharField(max_length=300, blank=True)
    extra_data    = models.JSONField(default=dict, blank=True)

    is_read       = models.BooleanField(default=False)
    read_at       = models.DateTimeField(null=True, blank=True)
    is_sent       = models.BooleanField(default=False)
    sent_at       = models.DateTimeField(null=True, blank=True)
    send_error    = models.TextField(blank=True)

    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['priority', 'created_at']),
            models.Index(fields=['notification_type']),
        ]

    def __str__(self):
        return f'[{self.priority.upper()}] {self.title}'

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
