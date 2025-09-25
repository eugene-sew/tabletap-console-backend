from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, dashboard_summary, track_event

router = DefaultRouter()
router.register(r'events', EventViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', dashboard_summary, name='dashboard_summary'),
    path('track/', track_event, name='track_event'),
]
