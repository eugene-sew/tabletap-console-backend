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

from tenants.views import restaurant_current

urlpatterns = [
    # Health check
    path('api/health/', tenant_health_check, name='tenant_health_check'),
    
    # Shared endpoints (available in tenant context)
    path('api/auth/', include('authentication.urls')),
    path('api/analytics/', include('analytics.urls')),
    
    # Restaurant endpoint (specific path to avoid conflicts)
    path('api/restaurants/current/', restaurant_current, name='restaurant_current'),
    
    # Tenant-specific endpoints
    path('api/staff/', include('staff.urls')),
    path('api/tools/', include('tools.urls')),
    path('api/tables/', include('restaurant_tables.urls')),
]
