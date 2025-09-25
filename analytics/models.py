from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Event(models.Model):
    EVENT_TYPES = [
        ('pos_transaction', 'POS Transaction'),
        ('menu_view', 'Menu View'),
        ('cms_update', 'CMS Update'),
        ('user_login', 'User Login'),
        ('staff_action', 'Staff Action'),
    ]
    
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Event data
    data = models.JSONField(default=dict)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.created_at}"

class DashboardMetric(models.Model):
    name = models.CharField(max_length=100)
    value = models.DecimalField(max_digits=15, decimal_places=2)
    metric_type = models.CharField(max_length=50)
    date = models.DateField()
    
    class Meta:
        unique_together = ['name', 'date']
    
    def __str__(self):
        return f"{self.name}: {self.value} ({self.date})"
