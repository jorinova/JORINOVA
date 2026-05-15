from django.contrib import admin
from .models import ToxicologyRequest, DrugScreenResult, TDMResult, PoisoningCase


@admin.register(ToxicologyRequest)
class ToxicologyRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'test_type', 'status', 'is_medicolegal', 'created_at')
    list_filter  = ('test_type', 'status', 'is_medicolegal')


@admin.register(DrugScreenResult)
class DrugScreenResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'panel_type', 'status', 'coc_required', 'requires_confirmation', 'created_at')
    list_filter  = ('status', 'panel_type', 'coc_required')


@admin.register(TDMResult)
class TDMResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'drug_name', 'measured_level', 'unit', 'interp_status', 'toxicity_risk', 'created_at')
    list_filter  = ('drug_name', 'interp_status', 'toxicity_risk')


@admin.register(PoisoningCase)
class PoisoningCaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'substance', 'severity', 'lethal_threshold_exceeded', 'is_medicolegal', 'created_at')
    list_filter  = ('substance', 'severity', 'is_medicolegal')
