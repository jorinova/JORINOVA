from django.contrib import admin
from .models import (
    LabRequest, RequestedTest, Sample, LabResult,
    CriticalDocument, CriticalResultBook,
    SampleCustodyEvent, SampleRejection, ResultCorrection,
    AnalyzerImport, ResultNotification, LabRecordBookEntry,
)


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display  = ('id', 'get_patient', 'get_test', 'value', 'unit', 'flag', 'result_source', 'is_critical', 'is_validated', 'entered_at')
    list_filter   = ('flag', 'is_critical', 'is_validated', 'result_source', 'result_type')
    search_fields = ('pid', 'lid', 'patient__family_name', 'requested_test__test__name')
    readonly_fields = ('pid', 'lid', 'sid', 'entered_at', 'pqc_hash' if hasattr(LabResult, 'pqc_hash') else 'entered_at')
    date_hierarchy = 'entered_at'

    def get_patient(self, obj):
        return str(obj.patient) if obj.patient_id else '—'
    get_patient.short_description = 'Patient'

    def get_test(self, obj):
        return obj.requested_test.test.name if obj.requested_test_id else '—'
    get_test.short_description = 'Test'


@admin.register(CriticalDocument)
class CriticalDocumentAdmin(admin.ModelAdmin):
    list_display  = ('entry_number_display', 'pid', 'lid', 'test_name', 'document_type', 'status', 'uploaded_by', 'created_at')
    list_filter   = ('document_type', 'status', 'department')
    search_fields = ('pid', 'lid', 'test_name', 'reason')
    date_hierarchy = 'created_at'
    readonly_fields = ('pid', 'lid', 'pqc_hash', 'created_at')

    def entry_number_display(self, obj):
        return f"CritDoc #{obj.pk}"
    entry_number_display.short_description = '#'


@admin.register(CriticalResultBook)
class CriticalResultBookAdmin(admin.ModelAdmin):
    list_display  = ('entry_number', 'pid', 'lid', 'test_name', 'result_value', 'flag', 'validated_by', 'clinician_notified', 'read_back_confirmed', 'created_at')
    list_filter   = ('flag', 'clinician_notified', 'read_back_confirmed', 'department')
    search_fields = ('entry_number', 'pid', 'lid', 'test_name')
    date_hierarchy = 'created_at'
    readonly_fields = ('entry_number', 'pqc_hash', 'created_at')


@admin.register(LabRequest)
class LabRequestAdmin(admin.ModelAdmin):
    list_display  = ('lab_id', 'patient', 'status', 'emergency_level', 'is_high_risk', 'received_at', 'request_date')
    list_filter   = ('status', 'emergency_level', 'is_high_risk')
    search_fields = ('lab_id', 'patient__family_name', 'patient__pid')
    date_hierarchy = 'request_date'


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display  = ('sid', 'barcode', 'patient', 'department', 'tube_type', 'status', 'is_high_risk', 'tat_start')
    list_filter   = ('status', 'tube_type', 'is_high_risk', 'department')
    search_fields = ('sid', 'barcode', 'patient__family_name', 'patient__pid')


@admin.register(SampleRejection)
class SampleRejectionAdmin(admin.ModelAdmin):
    list_display  = ('sample', 'reason', 'rejected_by', 'rejected_at', 'ai_suggested', 'recollect_required')
    list_filter   = ('reason', 'ai_suggested', 'recollect_required')
    date_hierarchy = 'rejected_at'


admin.site.register(RequestedTest)
admin.site.register(SampleCustodyEvent)
admin.site.register(ResultCorrection)
admin.site.register(AnalyzerImport)
admin.site.register(ResultNotification)
admin.site.register(LabRecordBookEntry)
