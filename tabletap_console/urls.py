from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

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

schema_view = get_schema_view(
    openapi.Info(
        title="TableTap Console API",
        default_version='v1',
        description="Multi-tenant restaurant management system API",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="admin@tabletap.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health_check'),
    path('api/auth/', include('authentication.urls')),
    path('api/tenants/', include('tenants.urls')),
    path('api/', include('tenants.urls')),  # For /api/restaurants/current/
    path('api/staff/', include('staff.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),
    path('api/tools/', include('tools.urls')),
    path('api/analytics/', include('analytics.urls')),
    
    # Swagger URLs
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
