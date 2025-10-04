import jwt
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.core.cache import cache

User = get_user_model()

class ClerkAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        
        try:
            # Check cache first for performance
            cache_key = f"clerk_token_{token[:20]}"
            cached_user_id = cache.get(cache_key)
            
            if cached_user_id:
                try:
                    user = User.objects.get(clerk_user_id=cached_user_id)
                    return (user, token)
                except User.DoesNotExist:
                    cache.delete(cache_key)
            
            # Verify token with Clerk's JWT verification
            # For development, we'll use a simpler approach
            # In production, you should verify the JWT signature properly
            
            # Decode without verification for development (NOT for production)
            if settings.DEBUG:
                try:
                    # This is a simplified approach for development
                    # In production, use proper JWT verification with Clerk's public keys
                    payload = jwt.decode(token, options={"verify_signature": False})
                    clerk_user_id = payload.get('sub')
                    
                    if not clerk_user_id:
                        raise AuthenticationFailed('Invalid token payload')
                    
                    # Get or create user
                    user, created = User.objects.get_or_create(
                        clerk_user_id=clerk_user_id,
                        defaults={
                            'username': clerk_user_id,
                            'email': payload.get('email', ''),
                            'first_name': payload.get('given_name', ''),
                            'last_name': payload.get('family_name', ''),
                            'is_verified': True
                        }
                    )
                    
                    # Cache for 5 minutes
                    cache.set(cache_key, clerk_user_id, 300)
                    
                    return (user, token)
                    
                except jwt.InvalidTokenError:
                    raise AuthenticationFailed('Invalid token format')
            else:
                # Production JWT verification with Clerk
                try:
                    # Get Clerk's JWKS
                    jwks_url = f"https://api.clerk.dev/v1/jwks"
                    jwks_response = requests.get(jwks_url, timeout=10)
                    jwks = jwks_response.json()
                    
                    # Verify JWT with JWKS (simplified)
                    # In a real implementation, you'd use a proper JWKS library
                    payload = jwt.decode(
                        token, 
                        key=settings.CLERK_SECRET_KEY,
                        algorithms=['RS256'],
                        options={"verify_signature": True}
                    )
                    
                    clerk_user_id = payload.get('sub')
                    if not clerk_user_id:
                        raise AuthenticationFailed('Invalid token payload')
                    
                    user, created = User.objects.get_or_create(
                        clerk_user_id=clerk_user_id,
                        defaults={
                            'username': clerk_user_id,
                            'email': payload.get('email', ''),
                            'first_name': payload.get('given_name', ''),
                            'last_name': payload.get('family_name', ''),
                            'is_verified': True
                        }
                    )
                    
                    cache.set(cache_key, clerk_user_id, 300)
                    return (user, token)
                    
                except (requests.RequestException, jwt.InvalidTokenError) as e:
                    raise AuthenticationFailed(f'Token verification failed: {str(e)}')
            
        except Exception as e:
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def authenticate_header(self, request):
        return 'Bearer'
