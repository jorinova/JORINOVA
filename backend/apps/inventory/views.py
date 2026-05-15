from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone


@login_required
def index(request):
    from apps.core_config.models import LaboratoryDepartment
    departments = LaboratoryDepartment.objects.filter(is_active=True).order_by('order')
    return render(request, 'inventory.html', {
        'page_title':  '🗂️ Inventory Intelligence — ALIS-X',
        'departments': departments,
        'today':       timezone.now().date(),
    })
