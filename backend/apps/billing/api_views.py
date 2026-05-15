"""Billing API views"""
from django.db.models import Sum, Count, Q
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
try:
    from django_filters.rest_framework import DjangoFilterBackend
except ImportError:
    DjangoFilterBackend = None

from .models import Invoice, InvoiceStatus, InsuranceProvider
from .serializers import (
    InvoiceListSerializer, InvoiceDetailSerializer,
    RecordPaymentSerializer, InsuranceProviderSerializer,
)


class InvoiceViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['status']
    search_fields      = ['invoice_number', 'patient__family_name', 'patient__other_names', 'patient__pid']
    ordering_fields    = ['created_at', 'total_amount', 'status']
    ordering           = ['-created_at']

    def get_queryset(self):
        qs = Invoice.objects.select_related(
            'patient', 'lab_request', 'insurance_provider', 'created_by'
        ).prefetch_related('line_items', 'payments')
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital:
            qs = qs.filter(hospital=hospital)
        date_from = self.request.query_params.get('date_from')
        date_to   = self.request.query_params.get('date_to')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    def get_serializer_class(self):
        if self.action in ['retrieve', 'create', 'update', 'partial_update']:
            return InvoiceDetailSerializer
        return InvoiceListSerializer

    @action(detail=True, methods=['post'], url_path='record-payment')
    def record_payment(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status in (InvoiceStatus.PAID, InvoiceStatus.WAIVED, InvoiceStatus.CANCELLED):
            return Response({'detail': f'Invoice is already {invoice.status}.'}, status=status.HTTP_400_BAD_REQUEST)
        ser = RecordPaymentSerializer(data=request.data, context={'request': request, 'invoice': invoice})
        ser.is_valid(raise_exception=True)
        payment = ser.save()
        invoice.refresh_from_db()
        return Response(InvoiceDetailSerializer(invoice, context={'request': request}).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='waive')
    def waive(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status == InvoiceStatus.PAID:
            return Response({'detail': 'Invoice already paid.'}, status=status.HTTP_400_BAD_REQUEST)
        invoice.status = InvoiceStatus.WAIVED
        invoice.notes  = request.data.get('reason', '') or invoice.notes
        invoice.save(update_fields=['status', 'notes', 'updated_at'])
        return Response(InvoiceDetailSerializer(invoice, context={'request': request}).data)


class InsuranceProviderViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = InsuranceProviderSerializer
    queryset           = InsuranceProvider.objects.filter(is_active=True).order_by('name')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def billing_summary(request):
    """Daily billing KPIs."""
    today    = timezone.now().date()
    hospital = getattr(request.user, 'hospital', None)
    qs       = Invoice.objects.all()
    if hospital:
        qs = qs.filter(hospital=hospital)

    today_qs  = qs.filter(created_at__date=today)
    agg       = today_qs.aggregate(
        total_invoices = Count('id'),
        paid_invoices  = Count('id', filter=Q(status=InvoiceStatus.PAID)),
        pending_count  = Count('id', filter=Q(status__in=[InvoiceStatus.PENDING, InvoiceStatus.PARTIAL])),
        total_revenue  = Sum('amount_paid'),
        total_due      = Sum('amount_due'),
    )
    overdue = qs.filter(
        due_date__lt=today,
        status__in=[InvoiceStatus.PENDING, InvoiceStatus.PARTIAL]
    ).count()

    return Response({
        'date':           today.isoformat(),
        'total_invoices': agg['total_invoices'] or 0,
        'paid_invoices':  agg['paid_invoices']  or 0,
        'pending_count':  agg['pending_count']  or 0,
        'overdue_count':  overdue,
        'total_revenue':  float(agg['total_revenue'] or 0),
        'total_due':      float(agg['total_due']     or 0),
    })
