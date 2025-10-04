from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantViewSet, restaurant_current

router = DefaultRouter()
router.register(r'', TenantViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('restaurants/current/', restaurant_current, name='restaurant_current'),
]
