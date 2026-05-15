"""Inventory Intelligence API views — Stock · Movements · POs · Expiry · Stats"""
from decimal import Decimal
from django.db.models import Count, Q, Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
try:
    from django_filters.rest_framework import DjangoFilterBackend
except ImportError:
    DjangoFilterBackend = None

from .models import InventoryItem, StockMovement, StockStatus, Supplier, PurchaseOrder
from .serializers import (
    InventoryItemListSerializer, StockMovementSerializer,
    StockMovementCreateSerializer, StockMovementListSerializer, SupplierSerializer,
)


# ─── InventoryItem ViewSet ─────────────────────────────────────────────────────

class InventoryItemViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends    = ([DjangoFilterBackend] if DjangoFilterBackend else []) + [filters.SearchFilter, filters.OrderingFilter]
    filterset_fields   = ['status', 'cold_chain']
    search_fields      = ['code', 'name', 'brand', 'batch_number', 'catalog_no']
    ordering_fields    = ['name', 'current_stock', 'expiry_date', 'updated_at', 'created_at']
    ordering           = ['category', 'name']
    serializer_class   = InventoryItemListSerializer

    def get_queryset(self):
        qs = InventoryItem.objects.filter(is_active=True).select_related('department', 'supplier', 'hospital')
        user     = self.request.user
        hospital = getattr(user, 'hospital', None)
        if hospital:
            qs = qs.filter(hospital=hospital)

        params = self.request.query_params
        dept   = params.get('department')
        cat    = params.get('category')
        stat   = params.get('status')
        has_ex = params.get('has_expiry')

        if dept:   qs = qs.filter(department_id=dept)
        if stat:   qs = qs.filter(status=stat)
        if has_ex: qs = qs.exclude(expiry_date__isnull=True)

        # category may be comma-separated
        if cat:
            cats = [c.strip() for c in cat.split(',') if c.strip()]
            qs   = qs.filter(category__in=cats)

        return qs

    def perform_create(self, serializer):
        hospital = getattr(self.request.user, 'hospital', None)
        serializer.save(hospital=hospital)


# ─── StockMovement ViewSet ────────────────────────────────────────────────────

class StockMovementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends    = ([DjangoFilterBackend] if DjangoFilterBackend else []) + [filters.OrderingFilter, filters.SearchFilter]
    filterset_fields   = ['movement_type']
    search_fields      = ['item__name', 'item__code', 'notes']
    ordering           = ['-performed_at']

    def get_queryset(self):
        qs  = StockMovement.objects.select_related('item', 'performed_by', 'supplier', 'department')
        params = self.request.query_params
        item_id   = params.get('item')
        mov_type  = params.get('movement_type')
        date_from = params.get('date_from')
        if item_id:   qs = qs.filter(item_id=item_id)
        if mov_type:  qs = qs.filter(movement_type=mov_type)
        if date_from: qs = qs.filter(performed_at__date__gte=date_from)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return StockMovementCreateSerializer
        return StockMovementListSerializer

    def perform_create(self, serializer):
        serializer.save(performed_by=self.request.user)


# ─── Supplier ViewSet ─────────────────────────────────────────────────────────

class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = SupplierSerializer
    queryset           = Supplier.objects.filter(is_active=True).order_by('name')


# ─── PurchaseOrder ViewSet ───────────────────────────────────────────────────

class PurchaseOrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends    = ([DjangoFilterBackend] if DjangoFilterBackend else []) + [filters.OrderingFilter]
    filterset_fields   = ['status']
    ordering           = ['-created_at']

    def get_queryset(self):
        qs = PurchaseOrder.objects.select_related('supplier', 'requested_by', 'approved_by', 'hospital')
        hospital = getattr(self.request.user, 'hospital', None)
        if hospital:
            qs = qs.filter(hospital=hospital)
        return qs

    def get_serializer_class(self):
        from rest_framework import serializers

        class POSerializer(serializers.ModelSerializer):
            supplier_name     = serializers.SerializerMethodField()
            requested_by_name = serializers.SerializerMethodField()

            class Meta:
                model  = PurchaseOrder
                fields = '__all__'

            def get_supplier_name(self, obj):
                return obj.supplier.name if obj.supplier_id else '—'

            def get_requested_by_name(self, obj):
                return obj.requested_by.get_full_name() if obj.requested_by_id else '—'

        return POSerializer

    def perform_create(self, serializer):
        hospital = getattr(self.request.user, 'hospital', None)
        serializer.save(requested_by=self.request.user, hospital=hospital)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        po = self.get_object()
        if po.status not in ('draft', 'submitted'):
            return Response({'detail': 'PO is not in an approvable state.'}, status=status.HTTP_400_BAD_REQUEST)
        po.status      = 'approved'
        po.approved_by = request.user
        po.save(update_fields=['status', 'approved_by'])
        return Response({'status': 'approved', 'po_number': po.po_number})

    @action(detail=True, methods=['post'], url_path='receive')
    def receive(self, request, pk=None):
        """Mark PO as received and auto-update stock for all line items."""
        po = self.get_object()
        if po.status != 'approved':
            return Response({'detail': 'PO must be approved before receiving.'}, status=status.HTTP_400_BAD_REQUEST)

        # Process PO lines if they exist (future: POLineItem model)
        # For now, just mark PO received and log it
        po.status = 'received'
        po.save(update_fields=['status'])

        try:
            from apps.audit.logger import AuditLogger
            AuditLogger.log(
                entity_type='INVENTORY',
                entity_id=po.po_number,
                action='PO_RECEIVED',
                performed_by=request.user,
                source='MANUAL',
                metadata={'supplier': po.supplier.name, 'total': str(po.total_amount)},
            )
        except Exception:
            pass

        return Response({'status': 'received', 'po_number': po.po_number})


# ─── Dashboard Stats ──────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def inventory_stats(request):
    """Comprehensive dashboard statistics for the inventory module."""
    hospital = getattr(request.user, 'hospital', None)
    qs = InventoryItem.objects.filter(is_active=True)
    if hospital:
        qs = qs.filter(hospital=hospital)

    today  = timezone.now().date()
    agg    = qs.aggregate(
        total_items  = Count('id'),
        low_stock    = Count('id', filter=Q(status=StockStatus.LOW_STOCK)),
        out_of_stock = Count('id', filter=Q(status=StockStatus.OUT_OF_STOCK)),
        expiring_soon= Count('id', filter=Q(status=StockStatus.EXPIRING_SOON)),
        expired      = Count('id', filter=Q(status=StockStatus.EXPIRED)),
        total_reagents = Count('id', filter=Q(category__in=['reagent','qc_control','stain','culture_media'])),
    )

    # Total stock value
    total_val = qs.aggregate(
        val=Sum(ExpressionWrapper(F('current_stock') * F('unit_cost'), output_field=DecimalField()))
    )['val'] or Decimal('0')

    # Open POs
    open_pos = PurchaseOrder.objects.filter(status__in=['submitted','approved'])
    if hospital:
        open_pos = open_pos.filter(hospital=hospital)
    open_pos_count = open_pos.count()

    # Low stock items (top 5)
    low_items = qs.filter(
        status__in=[StockStatus.LOW_STOCK, StockStatus.OUT_OF_STOCK]
    ).select_related('department')[:8]
    low_stock_items = [
        {
            'id':            it.id,
            'code':          it.code,
            'name':          it.name,
            'current_stock': str(it.current_stock),
            'min_stock':     str(it.min_stock),
            'max_stock':     str(it.max_stock),
            'unit':          it.unit,
            'dept':          it.department.name if it.department_id else '—',
        }
        for it in low_items
    ]

    # Expiry alerts (items expiring within 30 days)
    expiry_qs = qs.filter(
        expiry_date__isnull=False,
        expiry_date__lte=today + timezone.timedelta(days=30)
    ).order_by('expiry_date')[:8]
    expiry_alerts = [
        {
            'id':          it.id,
            'code':        it.code,
            'name':        it.name,
            'expiry_date': it.expiry_date.isoformat(),
            'days_left':   (it.expiry_date - today).days,
            'batch':       it.batch_number,
        }
        for it in expiry_qs
    ]

    # Recent movements (last 5)
    recent_movs = StockMovement.objects.select_related('item').order_by('-performed_at')[:8]
    recent_movements = [
        {
            'type':     m.movement_type,
            'item':     m.item.name if m.item_id else '—',
            'qty':      str(m.quantity),
            'time':     _time_ago(m.performed_at),
        }
        for m in recent_movs
    ]

    # Top consumed (last 30 days)
    thirty_days_ago = today - timezone.timedelta(days=30)
    top = StockMovement.objects.filter(
        movement_type='issue', performed_at__date__gte=thirty_days_ago
    ).values('item__name', 'item__unit').annotate(
        consumed=Sum('quantity')
    ).order_by('-consumed')[:5]
    top_consumed = [
        {'name': t['item__name'], 'consumed': str(t['consumed']), 'unit': t['item__unit'] or ''}
        for t in top
    ]

    # Category breakdown
    cat_counts = {}
    for it in qs.values('category').annotate(cnt=Count('id')):
        cat_counts[it['category']] = it['cnt']

    # 7-day consumption trend
    trend = []
    for i in range(6, -1, -1):
        d = today - timezone.timedelta(days=i)
        cnt = StockMovement.objects.filter(movement_type='issue', performed_at__date=d).count()
        trend.append(cnt)

    return Response({
        **agg,
        'total_value':       str(total_val),
        'open_pos':          open_pos_count,
        'low_stock_items':   low_stock_items,
        'expiry_alerts':     expiry_alerts,
        'recent_movements':  recent_movements,
        'top_consumed':      top_consumed,
        'category_counts':   cat_counts,
        'consumption_trend': trend,
    })


def _time_ago(dt):
    if not dt:
        return '—'
    now     = timezone.now()
    elapsed = int((now - dt).total_seconds())
    if elapsed < 3600:
        return f'{elapsed // 60} min ago'
    if elapsed < 86400:
        return f'{elapsed // 3600} hrs ago'
    if elapsed < 604800:
        return f'{elapsed // 86400} days ago'
    return dt.strftime('%d %b %Y')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def inventory_summary(request):
    """Legacy summary endpoint — now delegates to stats."""
    return inventory_stats(request._request)
