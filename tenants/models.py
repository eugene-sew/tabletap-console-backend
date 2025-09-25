from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Subscription info
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('trial', 'Trial'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('cancelled', 'Cancelled'),
        ],
        default='trial'
    )
    trial_end_date = models.DateTimeField(null=True, blank=True)
    
    # Contact info
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Business info
    business_type = models.CharField(max_length=50, blank=True)
    currency = models.CharField(max_length=3, default='USD')
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Clerk integration
    clerk_organization_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    
    auto_create_schema = True
    
    def __str__(self):
        return self.name

class Domain(DomainMixin):
    pass
