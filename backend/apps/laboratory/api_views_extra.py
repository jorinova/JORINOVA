"""
Laboratory extra API views — Critical Documents, Reference Ranges, Critical Book
"""
from django.db import models
from django.utils import timezone
from rest_framework import viewsets, status, serializers, filters
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from .models import CriticalDocument, CriticalResultBook, LabRequest
from apps.core_config.models import ReferenceRange


# ─── Serializers ──────────────────────────────────────────────────────────────

class CriticalDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    validated_by_name= serializers.SerializerMethodField()

    class Meta:
        model  = CriticalDocument
        fields = '__all__'
        read_only_fields = ['pid', 'lid', 'pqc_hash', 'created_at']

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() if obj.uploaded_by_id else '—'

    def get_validated_by_name(self, obj):
        return obj.validated_by.get_full_name() if obj.validated_by_id else '—'


class CriticalResultBookSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CriticalResultBook
        fields = '__all__'
        read_only_fields = ['entry_number', 'pqc_hash', 'created_at']


class ReferenceRangeSerializer(serializers.ModelSerializer):
    test_name  = serializers.CharField(source='test.name', read_only=True)
    dept_name  = serializers.CharField(source='department.name', read_only=True)
    range_display = serializers.SerializerMethodField()
    flag_result   = serializers.SerializerMethodField()

    class Meta:
        model  = ReferenceRange
        fields = '__all__'

    def get_range_display(self, obj):
        return obj.get_range_display()

    def get_flag_result(self, obj):
        val = self.context.get('value')
        if val is not None:
            try: return obj.flag_value(float(val))
            except (TypeError, ValueError): pass
        return None


# ─── ViewSets ─────────────────────────────────────────────────────────────────

class CriticalDocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]
    serializer_class   = CriticalDocumentSerializer
    filter_backends    = [filters.OrderingFilter]
    ordering           = ['-created_at']

    def get_queryset(self):
        qs = CriticalDocument.objects.select_related('patient', 'uploaded_by', 'validated_by', 'department')
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital:
            qs = qs.filter(patient__hospital=hospital)
        params = self.request.query_params
        if params.get('pid'):   qs = qs.filter(pid=params['pid'])
        if params.get('lid'):   qs = qs.filter(lid=params['lid'])
        if params.get('status'):qs = qs.filter(status=params['status'])
        return qs

    def perform_create(self, serializer):
        lab_req_id = self.request.data.get('lab_request_id')
        lab_req    = None
        patient    = None
        if lab_req_id:
            try:
                lab_req = LabRequest.objects.select_related('patient').get(id=lab_req_id)
                patient = lab_req.patient
            except LabRequest.DoesNotExist:
                pass

        doc = serializer.save(
            uploaded_by=self.request.user,
            patient=patient,
            lab_request=lab_req,
            test_name=self.request.data.get('test_name', ''),
            status=CriticalDocument.Status.PENDING,
        )

        # Auto-populate pid/lid
        if patient:
            CriticalDocument.objects.filter(pk=doc.pk).update(
                pid=patient.pid or '',
                lid=patient.unique_lab_id or '',
            )

        # Log to audit trail
        try:
            from apps.audit.logger import AuditLogger
            AuditLogger.log(
                entity_type='LAB',
                entity_id=lab_req.lab_id if lab_req else '',
                action='CRITICAL_DOCUMENT_UPLOADED',
                performed_by=self.request.user,
                source='MANUAL',
                metadata={
                    'document_type': doc.document_type,
                    'test_name':     doc.test_name,
                    'reason':        doc.reason,
                },
            )
        except Exception:
            pass

    @action(detail=True, methods=['post'], url_path='validate')
    def validate_doc(self, request, pk=None):
        doc = self.get_object()
        doc.validated_by = request.user
        doc.validated_at = timezone.now()
        doc.status = CriticalDocument.Status.VALIDATED
        doc.save(update_fields=['validated_by', 'validated_at', 'status'])

        # Update result's critical_doc_uploaded flag
        try:
            doc.result.critical_doc_uploaded = True
            doc.result.save(update_fields=['critical_doc_uploaded'])
        except Exception:
            pass

        return Response({'status': 'validated', 'doc_id': doc.pk})


class CriticalResultBookViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only — append-only, immutable critical result book."""
    permission_classes = [IsAuthenticated]
    serializer_class   = CriticalResultBookSerializer
    filter_backends    = [filters.OrderingFilter]
    ordering           = ['-created_at']

    def get_queryset(self):
        qs = CriticalResultBook.objects.select_related('patient', 'department')
        params = self.request.query_params
        if params.get('pid'):   qs = qs.filter(pid=params['pid'])
        if params.get('lid'):   qs = qs.filter(lid=params['lid'])
        if params.get('flag'):  qs = qs.filter(flag=params['flag'])
        return qs


class ReferenceRangeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = ReferenceRangeSerializer
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['test__name', 'test__code', 'method']
    ordering           = ['test', 'department', 'sex', 'age_min_years']

    def get_queryset(self):
        qs     = ReferenceRange.objects.select_related('test', 'department', 'created_by')
        params = self.request.query_params
        if params.get('test'):       qs = qs.filter(test_id=params['test'])
        if params.get('department'): qs = qs.filter(department_id=params['department'])
        if params.get('active_only', 'true') == 'true': qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def range_for_test(request, test_id: int):
    """
    Return the active reference range for a test, optionally filtered by patient sex/age.
    Used by the result entry UI to auto-populate reference range and auto-flag.
    """
    sex     = request.query_params.get('sex', '')
    age     = request.query_params.get('age')
    method  = request.query_params.get('method', '')
    value   = request.query_params.get('value')  # optional: return flag too

    qs = ReferenceRange.objects.filter(test_id=test_id, is_active=True)

    # Prefer sex-specific, then fall back to any
    sex_qs = qs.filter(sex=sex) if sex else qs.filter(sex='')
    if not sex_qs.exists():
        sex_qs = qs

    # Prefer age-specific
    if age:
        try:
            age_int = int(age)
            age_qs  = sex_qs.filter(age_min_years__lte=age_int).filter(
                models.Q(age_max_years__gte=age_int) | models.Q(age_max_years__isnull=True)
            )
            if age_qs.exists():
                sex_qs = age_qs
        except (ValueError, TypeError):
            pass

    rr = sex_qs.order_by('-version').first()
    if not rr:
        return Response({'detail': 'No reference range found'}, status=status.HTTP_404_NOT_FOUND)

    data = ReferenceRangeSerializer(rr, context={'value': value}).data
    if value:
        try:
            data['auto_flag'] = rr.flag_value(float(value))
        except (TypeError, ValueError):
            data['auto_flag'] = 'N'

    return Response(data)
