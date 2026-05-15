from django.contrib import admin
from .models import IQCResult, EQAProgram, EQASubmission, SOPDocument, SOPSignoff, NonConformity, CAPA, ISOClause


@admin.register(IQCResult)
class IQCResultAdmin(admin.ModelAdmin):
    list_display  = ('analyte', 'control_level', 'run_number', 'run_date', 'measured_value', 'z_score', 'westgard_status')
    list_filter   = ('westgard_status', 'control_level', 'analyte')
    date_hierarchy = 'run_date'


@admin.register(SOPDocument)
class SOPDocumentAdmin(admin.ModelAdmin):
    list_display  = ('code', 'title', 'department', 'version', 'review_date', 'status')
    list_filter   = ('status', 'department')
    search_fields = ('code', 'title')


@admin.register(NonConformity)
class NonConformityAdmin(admin.ModelAdmin):
    list_display  = ('ncr_number', 'ncr_type', 'severity', 'status', 'owner', 'due_date')
    list_filter   = ('status', 'severity', 'ncr_type')
    search_fields = ('ncr_number', 'description')


@admin.register(CAPA)
class CAPAAdmin(admin.ModelAdmin):
    list_display  = ('capa_number', 'ncr', 'title', 'status', 'due_date')
    list_filter   = ('status',)


@admin.register(ISOClause)
class ISOClauseAdmin(admin.ModelAdmin):
    list_display  = ('clause_code', 'title', 'status', 'last_reviewed')
    list_filter   = ('status',)


admin.site.register(EQAProgram)
admin.site.register(EQASubmission)
admin.site.register(SOPSignoff)
