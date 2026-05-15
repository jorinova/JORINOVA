from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import LabRequestViewSet, SampleViewSet, LabResultViewSet, TestCatalogViewSet, DepartmentViewSet
from . import api_views_extra

router = DefaultRouter()
router.register('requests',           LabRequestViewSet,          basename='lab-request')
router.register('samples',            SampleViewSet,              basename='sample')
router.register('results',            LabResultViewSet,           basename='lab-result')
router.register('tests',              TestCatalogViewSet,         basename='test-catalog')
router.register('departments',        DepartmentViewSet,          basename='lab-department')
router.register('critical-documents', api_views_extra.CriticalDocumentViewSet, basename='critical-document')
router.register('reference-ranges',   api_views_extra.ReferenceRangeViewSet,   basename='reference-range')
router.register('critical-book',      api_views_extra.CriticalResultBookViewSet,basename='critical-book')

urlpatterns = router.urls + [
    path('reference-ranges/for-test/<int:test_id>/', api_views_extra.range_for_test, name='range-for-test'),
]
