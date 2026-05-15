"""Laboratory views — Template + REST API"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import rest_framework as django_filters

from .models import LabRequest, RequestedTest, Sample, LabResult, SampleStatus
from apps.core_config.models import TestCatalog, LaboratoryDepartment
from .serializers import (
    LabRequestListSerializer, LabRequestDetailSerializer, LabRequestCreateSerializer,
    SampleSerializer, ResultEntrySerializer, TestCatalogBriefSerializer,
)


# ─── Template views ────────────────────────────────────────────────────────────

@login_required
def index(request):
    from apps.core_config.models import LaboratoryDepartment
    departments = LaboratoryDepartment.objects.filter(is_active=True).order_by('order')
    return render(request, 'lab_index.html', {
        'page_title':  'Laboratory — ALIS-X',
        'departments': departments,
        'today':       timezone.now().date(),
    })


@login_required
def serology_index(request):
    from apps.core_config.models import LaboratoryDepartment
    departments = LaboratoryDepartment.objects.filter(is_active=True).order_by('order')
    return render(request, 'serology.html', {
        'page_title':  '🔬 Serology — ALIS-X',
        'departments': departments,
        'today':       timezone.now().date(),
    })


@login_required
def dept_index(request, dept='hematology'):
    from apps.core_config.models import LaboratoryDepartment
    departments = LaboratoryDepartment.objects.filter(is_active=True).order_by('order')
    return render(request, 'lab_index.html', {
        'page_title':  f'Laboratory — {dept.title()} — ALIS-X',
        'departments': departments,
        'active_dept': dept,
        'today':       timezone.now().date(),
    })


@login_required
def new_request(request):
    from apps.core_config.models import LaboratoryDepartment
    departments = LaboratoryDepartment.objects.filter(is_active=True).order_by('order')
    return render(request, 'reception.html', {
        'page_title':  '📡 New Lab Request — ALIS-X',
        'departments': departments,
        'today':       timezone.now().date(),
    })


# ─── Filters ──────────────────────────────────────────────────────────────────

class LabRequestFilter(django_filters.FilterSet):
    department  = django_filters.NumberFilter(field_name='requested_tests__test__department', distinct=True)
    patient     = django_filters.NumberFilter(field_name='patient')
    date_from   = django_filters.DateFilter(field_name='request_date__date', lookup_expr='gte')
    date_to     = django_filters.DateFilter(field_name='request_date__date', lookup_expr='lte')
    is_critical = django_filters.BooleanFilter(field_name='requested_tests__result__is_critical')
    lab_id      = django_filters.CharFilter(field_name='lab_id', lookup_expr='icontains')

    class Meta:
        model  = LabRequest
        fields = ['status', 'emergency_level', 'is_high_risk']


# ─── ViewSets ─────────────────────────────────────────────────────────────────

class LabRequestViewSet(viewsets.ModelViewSet):
    permission_classes   = [IsAuthenticated]
    filter_backends      = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class      = LabRequestFilter
    search_fields        = ['lab_id', 'patient__family_name', 'patient__other_names',
                            'patient__pid', 'doctor_name']
    ordering_fields      = ['request_date', 'emergency_level', 'status']
    ordering             = ['-request_date']

    def get_queryset(self):
        qs = LabRequest.objects.select_related(
            'patient', 'hospital', 'requested_by', 'received_by'
        ).prefetch_related(
            'requested_tests__test__department',
            'requested_tests__result',
            'samples__department',
        )
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital:
            qs = qs.filter(hospital=hospital)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return LabRequestCreateSerializer
        if self.action in ['retrieve', 'update', 'partial_update']:
            return LabRequestDetailSerializer
        return LabRequestListSerializer

    @action(detail=True, methods=['post'], url_path='receive')
    def receive(self, request, pk=None):
        req = self.get_object()
        if req.status not in ('submitted', 'draft'):
            return Response({'detail': 'Request already received.'}, status=status.HTTP_400_BAD_REQUEST)
        req.status       = 'received'
        req.received_by  = request.user
        req.received_at  = timezone.now()
        req.save(update_fields=['status', 'received_by', 'received_at'])
        for sample in req.samples.filter(status=SampleStatus.PENDING):
            sample.status        = SampleStatus.RECEIVED
            sample.received_time = timezone.now()
            sample.received_by   = request.user
            if not sample.tat_start:
                sample.tat_start = timezone.now()
                from datetime import timedelta
                max_tat = max(
                    (float(rt.test.tat_hours) for rt in req.requested_tests.select_related('test').all()),
                    default=2.0
                )
                sample.tat_deadline = timezone.now() + timedelta(hours=max_tat)
            sample.save(update_fields=['status','received_time','received_by','tat_start','tat_deadline'])
        return Response(LabRequestDetailSerializer(req, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='validate')
    def validate_request(self, request, pk=None):
        req = self.get_object()
        if req.status not in ('processing', 'received'):
            return Response({'detail': 'Request is not in a validatable state.'}, status=status.HTTP_400_BAD_REQUEST)
        pending = req.requested_tests.filter(status__in=['pending', 'started'])
        if pending.exists():
            return Response({'detail': f'{pending.count()} test(s) still pending results.'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        req.requested_tests.filter(status='completed').update(
            status='validated', validated_at=now, validated_by=request.user
        )
        LabResult.objects.filter(
            requested_test__request=req, is_validated=False
        ).update(is_validated=True, validated_by=request.user, validated_at=now)
        req.status = 'validated'
        req.save(update_fields=['status', 'updated_at'])
        return Response(LabRequestDetailSerializer(req, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='enter-result/(?P<rt_id>[0-9]+)')
    def enter_result(self, request, pk=None, rt_id=None):
        lab_req = self.get_object()
        try:
            rt = lab_req.requested_tests.get(id=rt_id)
        except RequestedTest.DoesNotExist:
            return Response({'detail': 'Test not found in this request.'}, status=status.HTTP_404_NOT_FOUND)
        ser = ResultEntrySerializer(
            data=request.data,
            context={'request': request, 'requested_test': rt}
        )
        ser.is_valid(raise_exception=True)
        result = ser.save()
        if lab_req.status in ('received',):
            lab_req.status = 'processing'
            lab_req.save(update_fields=['status'])
        from .serializers import LabResultSerializer
        return Response(LabResultSerializer(result).data, status=status.HTTP_201_CREATED)


class SampleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names  = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = Sample.objects.select_related(
            'patient', 'department', 'lab_request', 'collected_by', 'received_by'
        )
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital:
            qs = qs.filter(lab_request__hospital=hospital)
        return qs

    def get_serializer_class(self):
        return SampleSerializer

    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        sample = self.get_object()
        new_status = request.data.get('status')
        allowed_transitions = {
            SampleStatus.PENDING:     [SampleStatus.COLLECTED, SampleStatus.REJECTED],
            SampleStatus.COLLECTED:   [SampleStatus.IN_TRANSIT, SampleStatus.RECEIVED, SampleStatus.REJECTED],
            SampleStatus.IN_TRANSIT:  [SampleStatus.RECEIVED, SampleStatus.REJECTED],
            SampleStatus.RECEIVED:    [SampleStatus.PROCESSING, SampleStatus.REJECTED],
            SampleStatus.PROCESSING:  [SampleStatus.COMPLETED],
            SampleStatus.COMPLETED:   [SampleStatus.STORED],
        }
        allowed = allowed_transitions.get(sample.status, [])
        if new_status not in allowed:
            return Response(
                {'detail': f'Cannot transition from {sample.status} to {new_status}.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        sample.status = new_status
        if new_status == SampleStatus.RECEIVED and not sample.received_time:
            sample.received_time = timezone.now()
            sample.received_by   = request.user
        if new_status == SampleStatus.REJECTED:
            sample.rejection_reason = request.data.get('rejection_reason', '')
        sample.save()
        return Response(SampleSerializer(sample).data)


class LabResultViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = ResultEntrySerializer
    ordering           = ['-entered_at']

    def get_queryset(self):
        qs = LabResult.objects.select_related(
            'requested_test__test', 'patient', 'entered_by', 'validated_by'
        )
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital:
            qs = qs.filter(patient__hospital=hospital)
        return qs

    @action(detail=True, methods=['post'], url_path='notify')
    def send_notification(self, request, pk=None):
        result = self.get_object()
        patient = result.patient
        sent = []
        try:
            from apps.notifications.tasks import send_result_sms, send_result_email
            if patient.phone and not result.sms_sent:
                send_result_sms.delay(result.id)
                sent.append('sms')
            if patient.email and not result.email_sent:
                send_result_email.delay(result.id)
                sent.append('email')
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'sent': sent, 'detail': f'Notification queued: {", ".join(sent) or "none"}'})


# ─── Label generation ─────────────────────────────────────────────────────────

@action(detail=True, methods=['get'], url_path='labels')
def labels(self, request, pk=None):
    req = self.get_object()
    labels_data = []
    for sample in req.samples.select_related('department'):
        test_names = list(
            req.requested_tests
            .filter(test__department=sample.department)
            .values_list('test__short_name', flat=True)
        )
        labels_data.append({
            'sid':            sample.sid,
            'barcode':        sample.barcode,
            'tube_type':      sample.tube_type,
            'tube_display':   sample.tube_type.replace('_', ' ').title(),
            'label_color':    sample.label_color,
            'patient_name':   req.patient.full_name,
            'patient_pid':    req.patient.pid,
            'patient_dob':    req.patient.date_of_birth.strftime('%d/%m/%Y') if req.patient.date_of_birth else '',
            'patient_gender': req.patient.gender,
            'patient_age':    req.patient.age,
            'lab_id':         req.lab_id,
            'department':     sample.department.name,
            'dept_abbr':      sample.department.abbreviation,
            'is_high_risk':   sample.is_high_risk,
            'test_names':     test_names,
            'collected_at':   timezone.now().strftime('%d/%m/%Y %H:%M'),
            'hospital_name':  req.hospital.name,
        })
    return Response({
        'labels':       labels_data,
        'patient_name': req.patient.full_name,
        'lab_id':       req.lab_id,
        'emergency':    req.emergency_level,
    })


LabRequestViewSet.labels = labels


# ─── Test Catalog ViewSet ──────────────────────────────────────────────────────
class TestCatalogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = TestCatalogBriefSerializer
    filter_backends    = [filters.SearchFilter, DjangoFilterBackend]
    search_fields      = ['name', 'short_name', 'code']

    def get_queryset(self):
        qs = TestCatalog.objects.filter(is_active=True).select_related('department')
        dept_id = self.request.query_params.get('department')
        if dept_id:
            qs = qs.filter(department_id=dept_id)
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital:
            qs = qs.filter(department__hospital=hospital)
        return qs.order_by('department__order', 'order_in_department', 'name')


# ─── Department ViewSet ────────────────────────────────────────────────────────
class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = LaboratoryDepartment.objects.filter(is_active=True)
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital:
            qs = qs.filter(hospital=hospital)
        return qs.order_by('order', 'name')

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        data = [{
            'id':           d.id,
            'code':         d.code,
            'name':         d.name,
            'abbreviation': d.abbreviation,
            'color_hex':    d.color_hex,
            'tube_color':   d.tube_color,
        } for d in qs]
        return Response(data)

    def retrieve(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
