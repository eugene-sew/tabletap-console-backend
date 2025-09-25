from django.contrib import admin
from .models import Event, DashboardMetric

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'user', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['user__username']
    readonly_fields = ['created_at']

@admin.register(DashboardMetric)
class DashboardMetricAdmin(admin.ModelAdmin):
    list_display = ['name', 'value', 'metric_type', 'date']
    list_filter = ['metric_type', 'date']
    search_fields = ['name']
