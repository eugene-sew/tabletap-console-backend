#!/usr/bin/env python3
"""
Simple integration test script to verify backend-frontend compatibility
"""
import requests
import json

def test_backend_health():
    """Test if backend is running and healthy"""
    try:
        response = requests.get('http://localhost:3001/api/health/')
        if response.status_code == 200:
            data = response.json()
            print("✅ Backend health check passed")
            print(f"   Status: {data.get('status')}")
            print(f"   Message: {data.get('message')}")
            return True
        else:
            print(f"❌ Backend health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend - is it running on port 3001?")
        return False
    except Exception as e:
        print(f"❌ Backend health check error: {e}")
        return False

def test_cors_headers():
    """Test CORS headers for frontend compatibility"""
    try:
        response = requests.options('http://localhost:3001/api/health/', 
                                  headers={'Origin': 'http://localhost:3000'})
        
        cors_headers = {
            'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
            'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
            'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
        }
        
        if cors_headers['Access-Control-Allow-Origin']:
            print("✅ CORS headers configured")
            for header, value in cors_headers.items():
                if value:
                    print(f"   {header}: {value}")
            return True
        else:
            print("❌ CORS headers not configured properly")
            return False
            
    except Exception as e:
        print(f"❌ CORS test error: {e}")
        return False

def test_api_endpoints():
    """Test key API endpoints"""
    endpoints = [
        '/api/tenants/',
        '/api/subscriptions/plans/',
        '/api/tools/available/',
        '/api/analytics/dashboard/',
    ]
    
    results = []
    for endpoint in endpoints:
        try:
            response = requests.get(f'http://localhost:3001{endpoint}')
            # We expect 401 (unauthorized) since we're not sending auth tokens
            if response.status_code in [200, 401, 403]:
                print(f"✅ {endpoint} - endpoint accessible")
                results.append(True)
            else:
                print(f"❌ {endpoint} - unexpected status: {response.status_code}")
                results.append(False)
        except Exception as e:
            print(f"❌ {endpoint} - error: {e}")
            results.append(False)
    
    return all(results)

def main():
    print("🧪 Testing TableTap Backend-Frontend Integration\n")
    
    tests = [
        ("Backend Health", test_backend_health),
        ("CORS Configuration", test_cors_headers),
        ("API Endpoints", test_api_endpoints),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Testing {test_name}...")
        result = test_func()
        results.append(result)
    
    print(f"\n📊 Test Results: {sum(results)}/{len(results)} passed")
    
    if all(results):
        print("\n🎉 All integration tests passed! Backend is ready for frontend.")
        print("\n📝 Next steps:")
        print("   1. Start the backend: docker-compose up")
        print("   2. Start the frontend: npm run dev")
        print("   3. Visit http://localhost:3000")
    else:
        print("\n⚠️  Some tests failed. Please check the backend configuration.")

if __name__ == "__main__":
    main()
