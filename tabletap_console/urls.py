from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(request):
    """Simple health check endpoint"""
    tenant_info = {}
    if hasattr(request, 'tenant'):
        tenant_info = {
            'tenant_name': request.tenant.name,
            'schema_name': request.tenant.schema_name,
        }
    
    return JsonResponse({
        'status': 'healthy',
        'message': 'TableTap Console Backend is running',
        'version': '1.0.0',
        **tenant_info
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health_check'),
    path('api/auth/', include('authentication.urls')),
    path('api/tenants/', include('tenants.urls')),
    path('api/staff/', include('staff.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),
    path('api/tools/', include('tools.urls')),
    path('api/analytics/', include('analytics.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
