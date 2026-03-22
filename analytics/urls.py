from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EventViewSet, dashboard_summary, dashboard_metrics, dashboard_activities,
    track_event, audit_logs,
    chart_revenue_trend, chart_hourly_orders, chart_top_items, chart_order_types,
    system_search,
)

router = DefaultRouter()
router.register(r'events', EventViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', dashboard_summary, name='dashboard_summary'),
    path('dashboard/metrics/', dashboard_metrics, name='dashboard_metrics'),
    path('dashboard/activities/', dashboard_activities, name='dashboard_activities'),
    path('track/', track_event, name='track_event'),
    path('audit/', audit_logs, name='audit_logs'),
    # Chart endpoints
    path('charts/revenue-trend/', chart_revenue_trend, name='chart_revenue_trend'),
    path('charts/hourly-orders/', chart_hourly_orders, name='chart_hourly_orders'),
    path('charts/top-items/', chart_top_items, name='chart_top_items'),
    path('charts/order-types/', chart_order_types, name='chart_order_types'),
    path('search/', system_search, name='system_search'),
]
