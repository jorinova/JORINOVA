from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register('items',           api_views.InventoryItemViewSet,   basename='inventory-item')
router.register('movements',       api_views.StockMovementViewSet,   basename='stock-movement')
router.register('suppliers',       api_views.SupplierViewSet,        basename='supplier')
router.register('purchase-orders', api_views.PurchaseOrderViewSet,   basename='purchase-order')

urlpatterns = [
    path('', include(router.urls)),
    path('stats/',   api_views.inventory_stats,   name='inventory-stats'),
    path('summary/', api_views.inventory_summary, name='inventory-summary'),
]
