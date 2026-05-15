"""Inventory serializers"""
from rest_framework import serializers
from .models import InventoryItem, StockMovement, Supplier, PurchaseOrder


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Supplier
        fields = ['id', 'name', 'contact_name', 'phone', 'email', 'is_active']


class InventoryItemListSerializer(serializers.ModelSerializer):
    department_name  = serializers.CharField(source='department.name', read_only=True, default='')
    status_display   = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    supplier_name    = serializers.CharField(source='supplier.name', read_only=True, default='')
    stock_pct        = serializers.IntegerField(read_only=True)
    days_to_expiry   = serializers.IntegerField(read_only=True)

    class Meta:
        model  = InventoryItem
        fields = [
            'id', 'code', 'name', 'brand', 'category', 'category_display',
            'department_name', 'supplier_name',
            'unit', 'current_stock', 'min_stock', 'max_stock', 'reorder_level',
            'unit_cost', 'storage_temp', 'cold_chain',
            'expiry_date', 'batch_number', 'catalog_no',
            'status', 'status_display', 'stock_pct', 'days_to_expiry',
            'is_active', 'updated_at',
        ]


class StockMovementSerializer(serializers.ModelSerializer):
    item_name        = serializers.CharField(source='item.name', read_only=True)
    item_code        = serializers.CharField(source='item.code', read_only=True)
    performed_by_name= serializers.CharField(source='performed_by.get_full_name', read_only=True, default='')
    movement_display = serializers.CharField(source='get_movement_type_display', read_only=True)

    class Meta:
        model  = StockMovement
        fields = [
            'id', 'item', 'item_name', 'item_code',
            'movement_type', 'movement_display', 'quantity', 'balance_after',
            'batch_number', 'expiry_date', 'unit_cost',
            'notes', 'performed_by', 'performed_by_name', 'performed_at',
        ]
        read_only_fields = ['id', 'balance_after', 'item_name', 'item_code', 'movement_display', 'performed_by', 'performed_by_name', 'performed_at']


class StockMovementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = StockMovement
        fields = ['item', 'movement_type', 'quantity', 'batch_number', 'expiry_date', 'unit_cost', 'department', 'notes']

    def create(self, validated_data):
        request = self.context.get('request')
        if request:
            validated_data['performed_by'] = request.user
        return StockMovement.objects.create(**validated_data)


class StockMovementListSerializer(serializers.ModelSerializer):
    item_name         = serializers.CharField(source='item.name', read_only=True)
    item_code         = serializers.CharField(source='item.code', read_only=True)
    performed_by_name = serializers.SerializerMethodField()
    department_name   = serializers.CharField(source='department.name', read_only=True, default='')
    movement_display  = serializers.CharField(source='get_movement_type_display', read_only=True)

    class Meta:
        model  = StockMovement
        fields = [
            'id', 'item', 'item_name', 'item_code',
            'movement_type', 'movement_display', 'quantity', 'balance_after',
            'batch_number', 'expiry_date', 'unit_cost',
            'department', 'department_name',
            'notes', 'performed_by', 'performed_by_name', 'performed_at',
        ]

    def get_performed_by_name(self, obj):
        return obj.performed_by.get_full_name() if obj.performed_by_id else '—'
