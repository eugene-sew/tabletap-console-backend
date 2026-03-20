#!/usr/bin/env python3
"""
Simple script to test if Django is properly configured for tunneling
"""

import os
import sys
import django
from django.conf import settings

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabletap_console.settings')
django.setup()

def test_tunnel_config():
    print("🔍 Testing Django Tunnel Configuration")
    print("=" * 50)
    
    print(f"DEBUG: {settings.DEBUG}")
    print(f"ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
    
    if hasattr(settings, 'CORS_ALLOW_ALL_ORIGINS'):
        print(f"CORS_ALLOW_ALL_ORIGINS: {settings.CORS_ALLOW_ALL_ORIGINS}")
    
    if hasattr(settings, 'CORS_ALLOWED_ORIGINS'):
        print(f"CORS_ALLOWED_ORIGINS: {settings.CORS_ALLOWED_ORIGINS}")
    
    print(f"CSRF_TRUSTED_ORIGINS: {settings.CSRF_TRUSTED_ORIGINS}")
    
    # Test specific tunnel domains
    tunnel_domains = [
        'ttc-app.loca.lt',
        'test.loca.lt', 
        'example.ngrok.io'
    ]
    
    print("\n🌐 Testing Tunnel Domain Support:")
    print("-" * 30)
    
    for domain in tunnel_domains:
        # Check if domain would be allowed
        allowed = False
        for allowed_host in settings.ALLOWED_HOSTS:
            if allowed_host == '*':
                allowed = True
                break
            elif allowed_host.startswith('*.'):
                # Wildcard domain check
                wildcard_domain = allowed_host[2:]  # Remove *.
                if domain.endswith(wildcard_domain):
                    allowed = True
                    break
            elif allowed_host == domain:
                allowed = True
                break
        
        status = "✅ ALLOWED" if allowed else "❌ BLOCKED"
        print(f"{domain}: {status}")
    
    print("\n💡 Recommendations:")
    if not any('*.loca.lt' in host for host in settings.ALLOWED_HOSTS):
        print("- Add '*.loca.lt' to ALLOWED_HOSTS")
    if settings.DEBUG and not getattr(settings, 'CORS_ALLOW_ALL_ORIGINS', False):
        print("- Enable CORS_ALLOW_ALL_ORIGINS for development")
    
    print("\n🚀 Your tunnel should work now!")

if __name__ == '__main__':
    test_tunnel_config()
