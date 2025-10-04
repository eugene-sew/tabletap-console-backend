from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, dashboard_summary, dashboard_metrics, dashboard_activities, track_event

router = DefaultRouter()
router.register(r'events', EventViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', dashboard_summary, name='dashboard_summary'),  # Legacy
    path('dashboard/metrics/', dashboard_metrics, name='dashboard_metrics'),
    path('dashboard/activities/', dashboard_activities, name='dashboard_activities'),
    path('track/', track_event, name='track_event'),
]
