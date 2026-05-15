from django.contrib import admin
from .models import PathologyCase, SpecimenBlock, MicroscopySlide, SlideAIAnalysis, IHCPanel, HistopathologyReport


@admin.register(PathologyCase)
class PathologyCaseAdmin(admin.ModelAdmin):
    list_display  = ('case_number', 'patient', 'case_type', 'specimen_site', 'priority', 'status', 'created_at')
    list_filter   = ('case_type', 'priority', 'status')
    search_fields = ('case_number', 'patient__first_name', 'patient__last_name', 'specimen_site')
    date_hierarchy = 'created_at'


@admin.register(HistopathologyReport)
class HistopathologyReportAdmin(admin.ModelAdmin):
    list_display  = ('case', 'report_status', 'is_malignant', 'tumor_grade', 'signed_by', 'signed_at')
    list_filter   = ('report_status', 'is_malignant', 'tumor_grade')


@admin.register(IHCPanel)
class IHCPanelAdmin(admin.ModelAdmin):
    list_display  = ('case', 'marker', 'result', 'intensity', 'percentage')
    list_filter   = ('result', 'marker')
    search_fields = ('marker', 'case__case_number')


admin.site.register(SpecimenBlock)
admin.site.register(MicroscopySlide)
admin.site.register(SlideAIAnalysis)
