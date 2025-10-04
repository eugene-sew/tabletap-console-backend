from django.db import models
from django_tenants.models import TenantMixin, DomainMixin
import uuid
from django.utils.text import slugify

class Tenant(TenantMixin):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True)
    created_on = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Restaurant specific info
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    website = models.URLField(blank=True)
    logo = models.URLField(blank=True)
    
    # Settings
    settings = models.JSONField(default=dict, blank=True)
    
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
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            original_slug = self.slug
            counter = 1
            while Tenant.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def get_default_settings(self):
        return {
            'currency': self.currency,
            'timezone': self.timezone,
            'tableCount': 0,
        }
    
    def __str__(self):
        return self.name

class Domain(DomainMixin):
    pass
