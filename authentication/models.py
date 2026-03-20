from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q

class User(AbstractUser):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
    ]
    clerk_user_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    avatar_url = models.URLField(blank=True)
    is_verified = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='owner')
    
    def get_tenant_role(self):
        """Get user's role in current tenant context"""
        from django.db import connection
        from tenants.models import Tenant
        
        # Get current tenant from schema
        schema_name = connection.schema_name
        if schema_name == 'public':
            return self.role
            
        try:
            tenant = Tenant.objects.get(schema_name=schema_name)
            # Check if user is tenant owner (created the tenant)
            if hasattr(tenant, 'clerk_organization_id') and tenant.clerk_organization_id:
                # If the tenant's exact owner ID matches this user's ID
                return 'owner' if self.clerk_user_id == tenant.clerk_organization_id else self.role
            return self.role
        except Tenant.DoesNotExist:
            return self.role
    
    def __str__(self):
        return self.email or self.username
