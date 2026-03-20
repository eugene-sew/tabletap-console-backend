from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ToolViewSet, ToolAccessViewSet, generate_sso_token, verify_sso_token

router = DefaultRouter()
router.register(r'available', ToolViewSet)
router.register(r'access', ToolAccessViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('sso/generate/', generate_sso_token, name='generate_sso_token'),
    path('sso/verify/', verify_sso_token, name='verify_sso_token'),
]
