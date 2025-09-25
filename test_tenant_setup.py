#!/usr/bin/env python
"""
Test script to verify the multi-tenant setup is working correctly.
"""
import os
import sys
import django
from django.conf import settings

# Add the project directory to the Python path
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabletap_console.settings')
django.setup()

from django.test import Client
from tenants.models import Tenant, Domain

def test_tenant_setup():
    """Test the multi-tenant setup"""
    print("=== Testing Multi-Tenant Setup ===")
    
    # Test 1: Check tenants exist
    print("\n1. Checking tenants...")
    tenants = Tenant.objects.all()
    for tenant in tenants:
        print(f"   - {tenant.schema_name}: {tenant.name}")
    
    # Test 2: Check domains exist
    print("\n2. Checking domains...")
    domains = Domain.objects.all()
    for domain in domains:
        print(f"   - {domain.domain} -> {domain.tenant.schema_name}")
    
    # Test 3: Test public schema API
    print("\n3. Testing public schema API...")
    client = Client()
    response = client.get('/api/health/', HTTP_HOST='localhost')
    print(f"   - Public health check: {response.status_code}")
    if response.status_code == 200:
        print(f"   - Response: {response.json()}")
    
    # Test 4: Test tenant schema API
    print("\n4. Testing tenant schema API...")
    response = client.get('/api/health/', HTTP_HOST='test.localhost')
    print(f"   - Tenant health check: {response.status_code}")
    if response.status_code == 200:
        print(f"   - Response: {response.json()}")
    
    # Test 5: Test tenant-specific endpoints
    print("\n5. Testing tenant-specific endpoints...")
    response = client.get('/api/staff/', HTTP_HOST='test.localhost')
    print(f"   - Staff API: {response.status_code}")
    
    print("\n=== Test Complete ===")

if __name__ == '__main__':
    test_tenant_setup()
