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
            # Check cache first for performance (silently skip if Redis is unavailable)
            cache_key = f"clerk_token_{token[:20]}"
            cached_user_id = None
            try:
                cached_user_id = cache.get(cache_key)
            except Exception:
                pass

            if cached_user_id:
                try:
                    user = User.objects.get(clerk_user_id=cached_user_id)
                    return (user, token)
                except User.DoesNotExist:
                    try:
                        cache.delete(cache_key)
                    except Exception:
                        pass
            
            payload = None
            clerk_user_id = None
            
            if settings.DEBUG:
                try:
                    # Try decoding as JWT first
                    payload = jwt.decode(token, options={"verify_signature": False})
                    clerk_user_id = payload.get('sub')
                except (jwt.InvalidTokenError, jwt.exceptions.DecodeError):
                    # If not a valid JWT, check if it's our mock-token
                    if token in ["console-token", "mock-token", "test-token"]:
                        clerk_user_id = "user_2ovMsw88i79sWd96YVlkVpBqR6D" # A default dev ID
                        payload = {
                            'sub': clerk_user_id,
                            'email': 'user@tabletap.com',
                            'given_name': 'Console',
                            'family_name': 'User'
                        }
                    else:
                        raise AuthenticationFailed('Invalid token format')
            else:
                # Production JWT verification with Clerk JWKS
                try:
                    import json as _json

                    # Fetch JWKS — cache for 1 hour to avoid hammering Clerk on every request
                    jwks_cache_key = "clerk_jwks"
                    jwks = None
                    try:
                        jwks = cache.get(jwks_cache_key)
                    except Exception:
                        pass

                    if jwks is None:
                        jwks_url = "https://api.clerk.dev/v1/jwks"
                        jwks_headers = {}
                        clerk_secret = getattr(settings, 'CLERK_SECRET_KEY', '')
                        if clerk_secret:
                            jwks_headers['Authorization'] = f'Bearer {clerk_secret}'
                        jwks_response = requests.get(jwks_url, headers=jwks_headers, timeout=10)
                        jwks_response.raise_for_status()
                        jwks = jwks_response.json()
                        try:
                            cache.set(jwks_cache_key, jwks, 3600)
                        except Exception:
                            pass

                    # Match the key from the token's kid header
                    unverified_header = jwt.get_unverified_header(token)
                    kid = unverified_header.get('kid')

                    public_key = None
                    for key_data in jwks.get('keys', []):
                        if key_data.get('kid') == kid:
                            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(
                                _json.dumps(key_data)
                            )
                            break

                    if public_key is None:
                        # kid not found — JWKS may be stale, bust cache and retry once
                        try:
                            cache.delete(jwks_cache_key)
                        except Exception:
                            pass
                        raise AuthenticationFailed('Public key not found in JWKS — please retry')

                    payload = jwt.decode(
                        token,
                        public_key,
                        algorithms=['RS256'],
                        options={"verify_aud": False},
                    )
                    clerk_user_id = payload.get('sub')
                except AuthenticationFailed:
                    raise
                except (requests.RequestException, jwt.InvalidTokenError) as e:
                    raise AuthenticationFailed(f'Token verification failed: {str(e)}')
                except Exception as e:
                    raise AuthenticationFailed(f'Token verification error: {str(e)}')

            if not clerk_user_id:
                raise AuthenticationFailed('Invalid token payload')
            
            # User resolution logic
            email = payload.get('email', '')
            
            # Fetching user profile from Clerk API if email is missing from JWT
            if not email and settings.CLERK_SECRET_KEY:
                try:
                    headers = {"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"}
                    clerk_user_res = requests.get(f"https://api.clerk.dev/v1/users/{clerk_user_id}", headers=headers, timeout=5)
                    if clerk_user_res.status_code == 200:
                        clerk_user_data = clerk_user_res.json()
                        primary_email_id = clerk_user_data.get('primary_email_address_id')
                        for em in clerk_user_data.get('email_addresses', []):
                            if em.get('id') == primary_email_id:
                                email = em.get('email_address', '')
                                break
                except requests.RequestException:
                    pass

            # Ensure email is None if empty string to avoid unique constraint violation
            email = email if email else None
            
            if email:
                try:
                    # Link placeholder users (ONLY if email is provided).
                    # Preserve existing role — staff invitees should NOT become 'owner'.
                    existing = User.objects.get(email=email)
                    if not existing.clerk_user_id:
                        existing.clerk_user_id = clerk_user_id
                        existing.username = clerk_user_id
                        existing.is_active = True
                        existing.save(update_fields=['clerk_user_id', 'username', 'is_active'])
                except User.DoesNotExist:
                    pass

            # update_or_create the user — intentionally does NOT include 'role'
            # so existing staff roles are preserved.  New signups get 'owner' below.
            jwt_first = payload.get('given_name', '') or ''
            jwt_last  = payload.get('family_name', '') or ''

            defaults = {
                'username': clerk_user_id,
                'email': email,
                'is_verified': True,
            }
            # Only overwrite names when the JWT actually provides them, so that
            # names set via the edit modal are not wiped on the next login.
            if jwt_first:
                defaults['first_name'] = jwt_first
            if jwt_last:
                defaults['last_name'] = jwt_last

            user, created = User.objects.update_or_create(
                clerk_user_id=clerk_user_id,
                defaults=defaults,
            )
            if created:
                user.role = 'owner'
                user.save(update_fields=['role'])
            
            # Cache for 5 minutes (silently skip if Redis is unavailable)
            try:
                cache.set(cache_key, clerk_user_id, 300)
            except Exception:
                pass
            return (user, token)
            
        except AuthenticationFailed:
            raise
        except Exception as e:
            print(f"[AUTH DEBUG] Unexpected error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def authenticate_header(self, request):
        return 'Bearer'
