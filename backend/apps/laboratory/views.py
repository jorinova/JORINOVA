"""Laboratory views — Template + REST API"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
try:
    from django_filters.rest_framework import DjangoFilterBackend
    from django_filters import rest_framework as django_filters
except ModuleNotFoundError:
    DjangoFilterBackend = object  # fallback: filter support disabled
    django_filters = None  # type: ignore

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


@login_required
def label_center(request, lab_id=None):
    """Label Print Center — generates and prints specimen tube labels."""
    from apps.core_config.models import LaboratoryDepartment
    departments = LaboratoryDepartment.objects.filter(is_active=True).order_by('order')
    return render(request, 'labels.html', {
        'page_title':  '🏷️ Label Print Center — ALIS-X',
        'departments': departments,
        'today':       timezone.now().date(),
        'auto_lab_id': lab_id or request.GET.get('lab_id', ''),
    })


# ─── Filters ──────────────────────────────────────────────────────────────────

# When django-filter isn't installed, disable FilterSet entirely.
if django_filters is not None:
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
else:
    LabRequestFilter = None



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

    @action(detail=True, methods=['post'], url_path='enter-results')
    def enter_results(self, request, pk=None):
        """Bulk result entry — save multiple test results in one call.
        Body: { results: [{requested_test_id, value, flag, comment, result_source, entry_mode, instrument_id}],
                validate_all: bool }
        """
        lab_req      = self.get_object()
        entries      = request.data.get('results', [])
        validate_all = bool(request.data.get('validate_all', False))
        saved        = []
        errors       = []
        now          = timezone.now()

        for entry in entries:
            if not entry.get('value'):
                continue
            rt_id = entry.get('requested_test_id')
            try:
                rt = lab_req.requested_tests.get(id=rt_id)
            except RequestedTest.DoesNotExist:
                errors.append(f'Test {rt_id} not found')
                continue

            result, created = LabResult.objects.update_or_create(
                requested_test=rt,
                defaults={
                    'patient':               lab_req.patient,
                    'value':                 str(entry.get('value', '')),
                    'flag':                  entry.get('flag', 'N'),
                    'technician_comment':    entry.get('comment', ''),
                    'entered_by':            request.user,
                    'entered_at':            now,
                    'is_validated':          validate_all,
                    'validated_by':          request.user if validate_all else None,
                    'validated_at':          now if validate_all else None,
                }
            )

            # Attach source tracking
            result.__dict__.update({
                '_result_source': entry.get('result_source', 'MANUAL'),
                '_entry_mode':    entry.get('entry_mode', 'SINGLE'),
                '_instrument_id': entry.get('instrument_id', ''),
            })

            # Auto-flag critical values
            try:
                v = float(result.value)
                ref = rt.test.reference_range_min, rt.test.reference_range_max
                if ref[0] and ref[1]:
                    if v > float(ref[1]) * 1.5 or v < float(ref[0]) * 0.5:
                        result.is_critical = True
                        result.flag = 'HH' if v > float(ref[1]) else 'LL'
                    elif v > float(ref[1]) or v < float(ref[0]):
                        result.is_abnormal = True
                    result.save(update_fields=['is_critical', 'is_abnormal', 'flag',
                                               'is_validated', 'validated_by', 'validated_at'])
            except (TypeError, ValueError, AttributeError):
                result.save(update_fields=['is_validated', 'validated_by', 'validated_at'])

            rt.status = 'validated' if validate_all else 'completed'
            if validate_all:
                rt.validated_at = now
                rt.validated_by = request.user
            rt.save(update_fields=['status', 'validated_at', 'validated_by'])

            # Chain-of-custody event
            from .models import SampleCustodyEvent
            sample = lab_req.samples.first()
            if sample:
                SampleCustodyEvent.objects.create(
                    sample=sample,
                    event_type='processing',
                    location=rt.test.department.name if rt.test.department_id else '',
                    performed_by=request.user,
                    timestamp=now,
                )

            saved.append(rt_id)

        # Update request status
        if lab_req.status in ('received', 'submitted'):
            lab_req.status = 'validated' if validate_all else 'processing'
            lab_req.save(update_fields=['status', 'updated_at'])
        elif validate_all:
            lab_req.status = 'validated'
            lab_req.save(update_fields=['status', 'updated_at'])

        # Audit trail
        try:
            from apps.audit.logger import AuditLogger
            AuditLogger.log(
                entity_type='LAB',
                entity_id=lab_req.lab_id,
                action='RESULT_ENTRY',
                performed_by=request.user,
                source='MANUAL',
                metadata={'saved': saved, 'validated': validate_all, 'source': entries[0].get('result_source', 'MANUAL') if entries else ''},
            )
        except Exception:
            pass

        return Response({'saved': saved, 'errors': errors, 'validated': validate_all}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """Reject a sample at reception."""
        lab_req = self.get_object()
        reason  = request.data.get('reason', '')
        detail  = request.data.get('detail', '')
        if not reason:
            return Response({'detail': 'Rejection reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
        lab_req.status = 'cancelled'
        lab_req.save(update_fields=['status', 'updated_at'])
        for sample in lab_req.samples.all():
            sample.status = SampleStatus.REJECTED
            sample.rejection_reason = reason
            sample.save(update_fields=['status', 'rejection_reason'])
            from .models import SampleRejection, SampleCustodyEvent
            SampleRejection.objects.create(
                sample=sample, reason=reason, reason_detail=detail,
                rejected_by=request.user, recollect_required=True,
            )
            SampleCustodyEvent.objects.create(
                sample=sample, event_type='rejected',
                notes=f'{reason}: {detail}', performed_by=request.user,
            )
        return Response({'status': 'rejected', 'reason': reason})

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

    @action(detail=True, methods=['post'], url_path='label-printed')
    def label_printed(self, request, pk=None):
        """Record that a label was printed — chain of custody event."""
        sample = self.get_object()
        copies = int(request.data.get('copies', 1))
        from .models import SampleCustodyEvent
        SampleCustodyEvent.objects.create(
            sample=sample,
            event_type='labeled',
            location=request.data.get('printer', 'Label Printer'),
            performed_by=request.user,
            notes=f'Label printed × {copies}',
        )
        return Response({'status': 'logged', 'copies': copies})

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
# Attached to LabRequestViewSet as @action — added below via monkey-patch pattern
# (defined here cleanly instead)

def _labels_action(self, request, pk=None):
    req = self.get_object()
    labels_data = []
    patient  = req.patient
    hospital = req.hospital

    for sample in req.samples.select_related('department'):
        test_names = list(
            req.requested_tests
            .filter(test__department=sample.department)
            .select_related('test')
            .values_list('test__short_name', flat=True)
        )
        tube_display = sample.tube_type.replace('_', ' ').title() if sample.tube_type else '—'

        # Compute patient age
        age = None
        if patient.date_of_birth:
            from dateutil.relativedelta import relativedelta
            try:
                rd   = relativedelta(timezone.now().date(), patient.date_of_birth)
                age  = rd.years
            except Exception:
                pass

        labels_data.append({
            'sample_id':      sample.id,
            'sid':            sample.sid,
            'barcode':        sample.barcode,
            'tube_type':      sample.tube_type,
            'tube_display':   tube_display,
            'label_color':    sample.label_color,
            'specimen_type':  sample.specimen_type,
            'volume_ml':      str(sample.volume_ml) if sample.volume_ml else None,
            # Patient
            'patient_name':   patient.full_name,
            'patient_pid':    patient.pid,
            'patient_lid':    patient.unique_lab_id or '',
            'patient_dob':    patient.date_of_birth.strftime('%d/%m/%Y') if patient.date_of_birth else '',
            'patient_gender': patient.gender,
            'patient_age':    age,
            # Request
            'lab_id':         req.lab_id,
            'emergency_level':req.emergency_level,
            # Sample / Lab info
            'department':     sample.department.name if sample.department_id else '—',
            'dept_abbr':      sample.department.abbreviation if sample.department_id else '—',
            'is_high_risk':   sample.is_high_risk,
            'biosafety_emoji':sample.biosafety_emoji,
            'test_names':     test_names,
            # Hospital + datetime
            'hospital_name':  hospital.name if hospital else 'NEXUS Hospital',
            'collected_at':   timezone.now().strftime('%d/%m/%Y %H:%M'),
        })

    return Response({
        'labels':       labels_data,
        'patient_name': patient.full_name,
        'patient_pid':  patient.pid,
        'patient_lid':  patient.unique_lab_id or '',
        'lab_id':       req.lab_id,
        'emergency':    req.emergency_level,
        'tube_types':   list({s.tube_type for s in req.samples.all()}),
    })


_labels_action.__name__ = 'labels'
LabRequestViewSet.labels = action(detail=True, methods=['get'], url_path='labels')(_labels_action)


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
