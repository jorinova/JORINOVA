from django.contrib import admin
from .models import Hospital, LaboratoryDepartment, TestCatalog, ReferenceRange, TestConsumable, SystemSetting


@admin.register(ReferenceRange)
class ReferenceRangeAdmin(admin.ModelAdmin):
    list_display  = ('test', 'department', 'sex', 'age_min_years', 'age_max_years', 'min_value', 'max_value', 'unit', 'method', 'version', 'is_active')
    list_filter   = ('department', 'is_active', 'sex')
    search_fields = ('test__name', 'test__code', 'method')
    readonly_fields = ('created_at', 'updated_at', 'version')


@admin.register(TestConsumable)
class TestConsumableAdmin(admin.ModelAdmin):
    list_display  = ('test', 'item_name', 'item_code', 'quantity_required', 'unit', 'unit_cost', 'is_mandatory')
    list_filter   = ('is_mandatory', 'test__department')
    search_fields = ('test__name', 'item_name', 'item_code')


class TestConsumableInline(admin.TabularInline):
    model  = TestConsumable
    extra  = 2
    fields = ['item_name', 'item_code', 'quantity_required', 'unit', 'unit_cost', 'is_mandatory']


@admin.register(TestCatalog)
class TestCatalogAdmin(admin.ModelAdmin):
    list_display  = ('code', 'name', 'department', 'specimen_type', 'tube_type', 'tat_hours', 'price', 'is_active')
    list_filter   = ('department', 'tube_type', 'is_active', 'is_panel')
    search_fields = ('code', 'name', 'short_name', 'loinc_code')
    inlines       = [TestConsumableInline]


@admin.register(Hospital)
class HospitalAdmin(admin.ModelAdmin):
    list_display  = ('name', 'short_name', 'hospital_type', 'district', 'is_active')
    list_filter   = ('hospital_type', 'is_active')
    search_fields = ('name', 'rbc_code', 'minisante_code')


@admin.register(LaboratoryDepartment)
class LaboratoryDepartmentAdmin(admin.ModelAdmin):
    list_display  = ('name', 'abbreviation', 'code', 'hospital', 'order', 'is_active')
    list_filter   = ('hospital', 'is_active')
    search_fields = ('name', 'code', 'abbreviation')


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display  = ('key', 'value', 'updated_at')
    search_fields = ('key',)
