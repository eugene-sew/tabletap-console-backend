"""
URL configuration for tenant-specific apps.
This file contains URLs that are available within tenant schemas.
"""
from django.urls import path, include
from django.http import JsonResponse

def tenant_health_check(request):
    """Health check endpoint for tenant schemas"""
    return JsonResponse({
        'status': 'healthy',
        'message': 'TableTap Console Backend - Tenant Schema',
        'version': '1.0.0',
        'tenant': request.tenant.name if hasattr(request, 'tenant') else 'Unknown'
    })

urlpatterns = [
    path('api/health/', tenant_health_check, name='tenant_health_check'),
    path('api/staff/', include('staff.urls')),
    path('api/tools/', include('tools.urls')),
]
