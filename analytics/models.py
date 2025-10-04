from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Event(models.Model):
    EVENT_TYPES = [
        ('order', 'Order'),
        ('customer', 'Customer'),
        ('menu', 'Menu'),
        ('system', 'System'),
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
    
    def get_title(self):
        """Generate a human-readable title for the event"""
        titles = {
            'order': 'New Order',
            'customer': 'Customer Activity',
            'menu': 'Menu Update',
            'system': 'System Event',
            'pos_transaction': 'POS Transaction',
            'menu_view': 'Menu Viewed',
            'cms_update': 'Content Updated',
            'user_login': 'User Login',
            'staff_action': 'Staff Action',
        }
        return titles.get(self.event_type, self.event_type.replace('_', ' ').title())
    
    def get_description(self):
        """Generate a description based on event data"""
        if self.event_type == 'order' and 'amount' in self.data:
            return f"Order placed for ${self.data['amount']}"
        elif self.event_type == 'menu' and 'item_name' in self.data:
            return f"Menu item '{self.data['item_name']}' updated"
        elif self.event_type == 'user_login' and self.user:
            return f"{self.user.get_full_name() or self.user.username} logged in"
        return self.data.get('description', 'Event occurred')
    
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
