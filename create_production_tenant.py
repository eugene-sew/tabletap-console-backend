#!/usr/bin/env python
"""
Create production tenant for your deployed domain
Run this on your server after deployment
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabletap_console.settings')
django.setup()

from tenants.models import Tenant, Domain

def create_production_tenant():
    # Replace with your actual production domain
    PRODUCTION_DOMAIN = input("Enter your production domain (e.g., api.yourdomain.com): ").strip()
    
    if not PRODUCTION_DOMAIN:
        print("Domain is required!")
        return
    
    # Create public tenant
    public_tenant, created = Tenant.objects.get_or_create(
        schema_name='public',
        defaults={
            'name': 'TableTap Public',
            'contact_email': 'admin@tabletap.com'
        }
    )
    
    if created:
        print(f"Created public tenant: {public_tenant.name}")
    else:
        print(f"Public tenant already exists: {public_tenant.name}")
    
    # Create domain mapping
    domain, created = Domain.objects.get_or_create(
        domain=PRODUCTION_DOMAIN,
        defaults={
            'tenant': public_tenant,
            'is_primary': True
        }
    )
    
    if created:
        print(f"Created domain mapping: {domain.domain} -> {domain.tenant.schema_name}")
    else:
        print(f"Domain mapping already exists: {domain.domain} -> {domain.tenant.schema_name}")
    
    print(f"\n✅ Your API should now work at: https://{PRODUCTION_DOMAIN}/api/health/")

if __name__ == '__main__':
    create_production_tenant()
