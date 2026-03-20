from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RoleViewSet, StaffMemberViewSet

router = DefaultRouter()
router.register(r'roles', RoleViewSet)
router.register(r'members', StaffMemberViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
