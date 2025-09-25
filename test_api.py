#!/usr/bin/env python
"""
Test API endpoints with proper tenant routing
"""
import requests
import json

def test_api():
    base_url = "http://localhost:3001"
    
    print("=== Testing API Endpoints ===")
    
    # Test 1: Public schema health check
    print("\n1. Testing public schema...")
    try:
        response = requests.get(f"{base_url}/api/health/", 
                              headers={"Host": "localhost"})
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Tenant schema health check
    print("\n2. Testing tenant schema...")
    try:
        response = requests.get(f"{base_url}/api/health/", 
                              headers={"Host": "test.localhost"})
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Public tenants API
    print("\n3. Testing public tenants API...")
    try:
        response = requests.get(f"{base_url}/api/tenants/", 
                              headers={"Host": "localhost"})
        print(f"   Status: {response.status_code}")
        if response.status_code in [200, 401, 403]:
            print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Tenant staff API
    print("\n4. Testing tenant staff API...")
    try:
        response = requests.get(f"{base_url}/api/staff/members/", 
                              headers={"Host": "test.localhost"})
        print(f"   Status: {response.status_code}")
        if response.status_code in [200, 401, 403]:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_api()
