from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantViewSet, restaurant_current

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path('restaurants/current/', restaurant_current, name='restaurant_current'),
    path('', include(router.urls)),
]
