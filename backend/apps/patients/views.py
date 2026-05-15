"""Patient Hub views — template + REST API
Implements: PID/LID dual-identity, duplicate detection, LID journey, inter-hospital access
"""
import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Patient, Guardian, InsuranceProfile, District
from .serializers import (
    PatientListSerializer, PatientDetailSerializer, PatientCreateSerializer,
    GuardianSerializer, InsuranceProfileSerializer,
)


@login_required
def patient_hub(request):
    hospital = getattr(request.user, 'hospital', None)
    from apps.core_config.models import Hospital
    hospitals = Hospital.objects.filter(is_active=True) if not hospital else []
    return render(request, 'patient_hub.html', {
        'page_title': '🧬 Patient Hub — ALIS-X',
        'active_module': 'patients',
        'hospitals': hospitals,
        'hospital': hospital,
        'districts': District.choices,
    })


class PatientViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_class(self):
        if self.action == 'create':
            return PatientCreateSerializer
        if self.action in ['retrieve', 'update', 'partial_update']:
            return PatientDetailSerializer
        return PatientListSerializer

    @action(detail=False, methods=['get'])
    def search(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 2:
            return Response([])
        qs = self.get_queryset().filter(
            Q(pid__icontains=q) |
            Q(unique_lab_id__icontains=q) |
            Q(family_name__icontains=q) |
            Q(other_names__icontains=q) |
            Q(person_id__icontains=q) |
            Q(phone__icontains=q) |
            Q(record_number__icontains=q)
        )[:20]
        return Response(
            PatientListSerializer(qs, many=True, context={'request': request}).data
        )

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        patient = self.get_object()
        try:
            from apps.laboratory.models import LabRequest
            recent = LabRequest.objects.filter(patient=patient).prefetch_related(
                'requested_tests__test'
            ).order_by('-request_date')[:5]
            recent_labs = [
                {
                    'id': lr.id,
                    'lab_id': lr.lab_id,
                    'date': lr.request_date.strftime('%d %b %Y %H:%M'),
                    'status': lr.status,
                    'emergency_level': lr.emergency_level,
                    'tests': [rt.test.name for rt in lr.requested_tests.all()],
                }
                for lr in recent
            ]
        except Exception:
            recent_labs = []

        active_ins = patient.insurances.filter(is_active=True).first()
        primary_g = patient.guardians.filter(is_primary=True).first()

        data = PatientDetailSerializer(patient, context={'request': request}).data
        data['recent_lab_requests'] = recent_labs
        data['active_insurance'] = InsuranceProfileSerializer(active_ins).data if active_ins else None
        data['primary_guardian'] = GuardianSerializer(primary_g).data if primary_g else None
        return Response(data)

    @action(detail=True, methods=['get', 'post'])
    def guardians(self, request, pk=None):
        patient = self.get_object()
        if request.method == 'POST':
            ser = GuardianSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save(patient=patient)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(GuardianSerializer(patient.guardians.all(), many=True).data)

    @action(detail=True, methods=['get', 'post'])
    def insurances(self, request, pk=None):
        patient = self.get_object()
        if request.method == 'POST':
            ser = InsuranceProfileSerializer(data=request.data)
            ser.is_valid(raise_exception=True)
            ser.save(patient=patient)
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(InsuranceProfileSerializer(patient.insurances.all(), many=True).data)

    # Keep old name for compatibility
    @action(detail=True, methods=['get', 'post'], url_path='insurance')
    def insurance(self, request, pk=None):
        return self.insurances(request, pk)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Dashboard stats for the empty state."""
        hospital = getattr(request.user, 'hospital', None)
        qs = Patient.objects.all()
        if hospital:
            qs = qs.filter(hospital=hospital)
        today = timezone.now().date()
        return Response({
            'total':      qs.count(),
            'today':      qs.filter(created_at__date=today).count(),
            'active_lids': qs.exclude(unique_lab_id='').count(),
        })

    @action(detail=True, methods=['get'], url_path='lid-journey')
    def lid_journey(self, request, pk=None):
        """Return chronological LID-linked lab encounter timeline for a patient."""
        patient = self.get_object()
        entries = []
        try:
            from apps.laboratory.models import LabRequest
            requests = LabRequest.objects.filter(
                patient=patient
            ).select_related('hospital').prefetch_related(
                'requested_tests__test__department'
            ).order_by('-request_date')

            for req in requests:
                test_names = list(req.requested_tests.values_list('test__name', flat=True)[:6])
                dept_name = ''
                first_test = req.requested_tests.select_related('test__department').first()
                if first_test and first_test.test.department:
                    dept_name = first_test.test.department.name

                hospital = getattr(req, 'hospital', None) or getattr(request.user, 'hospital', None)
                user_hosp = getattr(request.user, 'hospital', None)
                is_local = (hospital is None) or (user_hosp is None) or (hospital.id == user_hosp.id)

                entries.append({
                    'date':     req.request_date.isoformat(),
                    'lab_id':   req.lab_id,
                    'hospital': hospital.name if hospital else 'This Hospital',
                    'is_local': is_local,
                    'is_locked': False,
                    'tests':    test_names or ['—'],
                    'status':   req.status,
                    'dept':     dept_name,
                })
        except Exception:
            pass

        return Response({'lid': patient.unique_lab_id, 'entries': entries})

    @action(detail=False, methods=['post'], url_path='lid-access-request')
    def lid_access_request(self, request):
        """Log an inter-hospital LID access request."""
        data = request.data
        lid          = data.get('lid', '')
        access_level = int(data.get('access_level', 2))
        justification= data.get('justification', '').strip()
        source_hosp  = data.get('source_hospital', '')

        if not justification:
            return Response({'error': 'Clinical justification is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Log to audit trail
        try:
            from apps.audit.logger import AuditLogger
            AuditLogger.log(
                entity_type='PATIENT',
                entity_id=lid,
                action='LID_ACCESS_REQUEST',
                performed_by=request.user,
                source='MANUAL',
                metadata={
                    'access_level': access_level,
                    'justification': justification,
                    'source_hospital': source_hosp,
                },
            )
        except Exception:
            pass

        return Response({
            'status': 'submitted',
            'lid': lid,
            'access_level': access_level,
            'message': 'Access request logged and pending institutional authorization.',
        }, status=status.HTTP_201_CREATED)

    def get_queryset(self):
        """Enhanced search: q, dob, phone, person_id, lid prefix."""
        qs = Patient.objects.select_related('hospital', 'registered_by').prefetch_related(
            'guardians', 'insurances'
        )
        user    = self.request.user
        hospital = getattr(user, 'hospital', None)
        if hospital and self.action != 'lid_access_request':
            qs = qs.filter(hospital=hospital)

        params = self.request.query_params
        q      = params.get('q', '').strip()
        if q:
            # Support RW- LID prefix search
            qs = qs.filter(
                Q(pid__icontains=q) |
                Q(unique_lab_id__icontains=q) |
                Q(family_name__icontains=q) |
                Q(other_names__icontains=q) |
                Q(person_id__icontains=q) |
                Q(phone__icontains=q) |
                Q(record_number__icontains=q)
            )
        if params.get('dob'):
            qs = qs.filter(date_of_birth=params['dob'])
        if params.get('phone'):
            qs = qs.filter(phone__icontains=params['phone'])
        if params.get('person_id'):
            qs = qs.filter(person_id=params['person_id'])

        return qs.order_by('-created_at')
