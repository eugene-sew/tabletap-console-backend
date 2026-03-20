from rest_framework import serializers
from .models import Event, DashboardMetric

class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ['id', 'event_type', 'user', 'data', 'ip_address', 'created_at']

class DashboardMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardMetric
        fields = ['id', 'name', 'value', 'metric_type', 'date']
