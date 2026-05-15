from django.contrib import admin
from .models import HematologyRequest, CBCResult, CoagulationResult, InflammationResult, SmearResult


@admin.register(CBCResult)
class CBCResultAdmin(admin.ModelAdmin):
    list_display  = ('id', 'get_patient', 'hgb', 'plt', 'wbc', 'primary_finding', 'severity', 'status', 'created_at')
    list_filter   = ('status', 'severity', 'leukemia_flag')
    search_fields = ('request__patient__first_name', 'request__patient__last_name', 'primary_finding')
    readonly_fields = ('created_at', 'updated_at', 'ai_interpretation', 'critical_values', 'reflex_suggestions')
    date_hierarchy = 'created_at'

    def get_patient(self, obj):
        return str(obj.request.patient) if obj.request_id else '—'
    get_patient.short_description = 'Patient'


@admin.register(CoagulationResult)
class CoagulationResultAdmin(admin.ModelAdmin):
    list_display  = ('id', 'inr', 'aptt', 'primary_finding', 'severity', 'status', 'created_at')
    list_filter   = ('status', 'severity')


@admin.register(InflammationResult)
class InflammationResultAdmin(admin.ModelAdmin):
    list_display  = ('id', 'crp', 'pct', 'primary_finding', 'severity', 'sepsis_alert', 'created_at')
    list_filter   = ('status', 'sepsis_alert')


@admin.register(SmearResult)
class SmearResultAdmin(admin.ModelAdmin):
    list_display  = ('id', 'stain_type', 'impression', 'ai_confidence', 'status', 'created_at')
    list_filter   = ('status', 'stain_type')


admin.site.register(HematologyRequest)
