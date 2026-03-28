from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.conf import settings
from django.utils import timezone
from tenants.models import Tenant
import uuid

User = get_user_model()


def _jwt_tokens_for_user(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """Register a new user. Sends a 6-digit email verification code."""
    email = (request.data.get('email') or '').strip().lower()
    password = request.data.get('password', '')
    first_name = (request.data.get('firstName') or '').strip()
    last_name = (request.data.get('lastName') or '').strip()

    if not email or not password:
        return Response({'error': 'Email and password are required.'}, status=400)

    if User.objects.filter(email=email).exists():
        existing = User.objects.get(email=email)
        if existing.is_verified:
            return Response({'error': 'An account with this email already exists.'}, status=400)
        # Update placeholder account with the submitted credentials before resending
        existing.set_password(password)
        if first_name:
            existing.first_name = first_name
        if last_name:
            existing.last_name = last_name
        existing.is_active = True
        existing.save(update_fields=['password', 'first_name', 'last_name', 'is_active'])
        code = existing.generate_verification_code()
        _send_verification_email(existing, code)
        return Response({'status': 'pending_verification', 'userId': existing.pk})

    username = email.split('@')[0] + '_' + uuid.uuid4().hex[:6]
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        is_verified=False,
        is_active=True,
        role='owner',
    )

    code = user.generate_verification_code()
    _send_verification_email(user, code)

    return Response({'status': 'pending_verification', 'userId': user.pk})


def _send_verification_email(user, code):
    from .services import send_email_via_resend
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #f97316;">Verify your TableTap account</h2>
      <p>Hi {user.first_name or 'there'},</p>
      <p>Your verification code is:</p>
      <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #f97316;
                  background: #fff7ed; padding: 16px 24px; border-radius: 8px; display: inline-block;">
        {code}
      </div>
      <p style="color: #6b7280; margin-top: 16px;">This code expires in 15 minutes.</p>
    </div>
    """
    send_email_via_resend(user.email, 'Verify your TableTap account', html)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """Verify email with the 6-digit code. Returns JWT tokens on success."""
    user_id = request.data.get('userId')
    code = (request.data.get('code') or '').strip()

    if not user_id or not code:
        return Response({'error': 'userId and code are required.'}, status=400)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Invalid request.'}, status=400)

    if user.email_verification_token != code:
        return Response({'error': 'Invalid verification code.'}, status=400)

    if user.email_verification_token_expires and timezone.now() > user.email_verification_token_expires:
        return Response({'error': 'Verification code has expired. Please request a new one.'}, status=400)

    user.is_verified = True
    user.is_active = True
    user.email_verification_token = None
    user.email_verification_token_expires = None
    user.save(update_fields=['is_verified', 'is_active', 'email_verification_token', 'email_verification_token_expires'])

    tokens = _jwt_tokens_for_user(user)
    return Response({
        'status': 'verified',
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'user': {
            'id': user.pk,
            'email': user.email,
            'firstName': user.first_name,
            'lastName': user.last_name,
        },
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Authenticate with email and password. Returns JWT tokens."""
    from django.contrib.auth import authenticate as django_authenticate
    email = (request.data.get('email') or '').strip().lower()
    password = request.data.get('password', '')

    if not email or not password:
        return Response({'error': 'Email and password are required.'}, status=400)

    try:
        user_obj = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'Invalid email or password.'}, status=401)

    user = django_authenticate(request, username=user_obj.username, password=password)
    if user is None:
        return Response({'error': 'Invalid email or password.'}, status=401)

    if not user.is_verified:
        code = user.generate_verification_code()
        _send_verification_email(user, code)
        return Response({
            'status': 'pending_verification',
            'userId': user.pk,
            'message': 'Please verify your email before signing in.',
        }, status=403)

    tokens = _jwt_tokens_for_user(user)
    return Response({
        'access': tokens['access'],
        'refresh': tokens['refresh'],
        'user': {
            'id': user.pk,
            'email': user.email,
            'firstName': user.first_name,
            'lastName': user.last_name,
        },
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh(request):
    """Refresh the access token using a refresh token."""
    from rest_framework_simplejwt.tokens import RefreshToken
    from rest_framework_simplejwt.exceptions import TokenError
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response({'error': 'Refresh token is required.'}, status=400)
    try:
        token = RefreshToken(refresh_token)
        return Response({'access': str(token.access_token)})
    except TokenError as e:
        return Response({'error': str(e)}, status=401)


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """Send a 6-digit password reset code to the user's email."""
    email = (request.data.get('email') or '').strip().lower()
    if not email:
        return Response({'error': 'Email is required.'}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'status': 'sent'})

    code = user.generate_password_reset_code()
    from .services import send_email_via_resend
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <h2 style="color: #f97316;">Reset your TableTap password</h2>
      <p>Hi {user.first_name or 'there'},</p>
      <p>Your password reset code is:</p>
      <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #f97316;
                  background: #fff7ed; padding: 16px 24px; border-radius: 8px; display: inline-block;">
        {code}
      </div>
      <p style="color: #6b7280; margin-top: 16px;">This code expires in 30 minutes.</p>
    </div>
    """
    send_email_via_resend(user.email, 'Reset your TableTap password', html)
    return Response({'status': 'sent', 'userId': user.pk})


@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """Verify the reset code and set a new password. Returns JWT tokens."""
    user_id = request.data.get('userId')
    code = (request.data.get('code') or '').strip()
    new_password = request.data.get('newPassword', '')

    if not user_id or not code or not new_password:
        return Response({'error': 'userId, code, and newPassword are required.'}, status=400)
    if len(new_password) < 8:
        return Response({'error': 'Password must be at least 8 characters.'}, status=400)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return Response({'error': 'Invalid request.'}, status=400)

    if user.password_reset_token != code:
        return Response({'error': 'Invalid or expired reset code.'}, status=400)

    if user.password_reset_token_expires and timezone.now() > user.password_reset_token_expires:
        return Response({'error': 'Reset code has expired. Please request a new one.'}, status=400)

    user.set_password(new_password)
    user.password_reset_token = None
    user.password_reset_token_expires = None
    user.is_verified = True
    user.save(update_fields=['password', 'password_reset_token', 'password_reset_token_expires', 'is_verified'])

    tokens = _jwt_tokens_for_user(user)
    return Response({
        'status': 'reset',
        'access': tokens['access'],
        'refresh': tokens['refresh'],
    })


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get or update current user profile"""
    if request.method == 'GET':
        restaurant_id = getattr(request.tenant, 'id', None) if hasattr(request, 'tenant') else None
        return Response({
            'success': True,
            'data': {
                'firstName': request.user.first_name,
                'lastName': request.user.last_name,
                'email': request.user.email,
                'role': request.user.get_tenant_role(),
                'restaurantId': str(restaurant_id) if restaurant_id else None,
            },
            'meta': {
                'timestamp': timezone.now().isoformat(),
                'version': '1.0.0'
            }
        })

    user = request.user
    data = request.data
    if 'firstName' in data:
        user.first_name = data['firstName']
    if 'lastName' in data:
        user.last_name = data['lastName']
    if 'email' in data:
        user.email = data['email']

    try:
        user.save()
        return Response({
            'success': True,
            'data': {
                'firstName': user.first_name,
                'lastName': user.last_name,
                'email': user.email,
                'role': user.get_tenant_role(),
                'restaurantId': str(getattr(request.tenant, 'id', None)) if hasattr(request, 'tenant') else None,
            },
            'message': 'Profile updated successfully',
            'meta': {
                'timestamp': timezone.now().isoformat(),
                'version': '1.0.0'
            }
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': 'Failed to update profile',
            'errors': [str(e)],
            'meta': {'timestamp': timezone.now().isoformat(), 'version': '1.0.0'}
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_tenant(request):
    """Get user's tenant information, discovering or provisioning one if needed."""
    from django.db import connection as _conn
    _conn.set_schema_to_public()
    tenant = None

    try:
        from django_tenants.utils import tenant_context as _tc
        from staff.models import StaffMember as _SM

        # Path 1: invited staff — find their StaffMember record
        for candidate in Tenant.objects.exclude(schema_name='public'):
            with _tc(candidate):
                if _SM.objects.filter(user=request.user).exists():
                    tenant = candidate
                    break

        # Path 2: owner — look up by owner FK
        if tenant is None:
            tenant = Tenant.objects.filter(owner=request.user).first()

        # Path 2b (backward compat): fall back to clerk_organization_id
        if tenant is None and request.user.clerk_user_id:
            tenant = Tenant.objects.filter(
                clerk_organization_id=request.user.clerk_user_id
            ).first()

    except Exception as e:
        return Response({
            'error': 'Tenant discovery failed',
            'detail': str(e),
        }, status=500)

    if tenant is None:
        return Response({
            'error': 'No restaurant found',
            'message': 'Your account is not linked to a restaurant yet.',
        }, status=404)

    return Response({
        'tenant_id': tenant.id,
        'schema_name': tenant.schema_name,
        'slug': tenant.slug or tenant.schema_name,
        'name': tenant.name,
        'subscription_status': tenant.subscription_status,
        'trial_end_date': str(tenant.trial_end_date) if tenant.trial_end_date else None,
        'is_active': tenant.is_active,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def provision_tenant(request):
    """
    Explicitly provision a tenant for the authenticated user.
    Idempotent — safe to call even if the tenant already exists.
    """
    from django.db import connection
    connection.set_schema_to_public()

    from django_tenants.utils import tenant_context as _tc
    from staff.models import StaffMember as _SM

    for candidate in Tenant.objects.exclude(schema_name='public'):
        with _tc(candidate):
            if _SM.objects.filter(user=request.user).exists():
                return Response({
                    'tenant_id': candidate.id,
                    'schema_name': candidate.schema_name,
                    'slug': candidate.slug or candidate.schema_name,
                    'name': candidate.name,
                    'subscription_status': candidate.subscription_status,
                    'is_active': candidate.is_active,
                    'created': False,
                })

    restaurant_name = request.data.get('restaurantName') or request.data.get('restaurant_name')

    from .services import provision_tenant_for_user
    tenant, created = provision_tenant_for_user(request.user, restaurant_name)

    if not tenant:
        return Response({'error': 'Failed to provision tenant'}, status=500)

    return Response({
        'tenant_id': tenant.id,
        'schema_name': tenant.schema_name,
        'slug': tenant.slug or tenant.schema_name,
        'name': tenant.name,
        'subscription_status': tenant.subscription_status,
        'is_active': tenant.is_active,
        'created': created,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def link_staff_account(request):
    """
    Called after an invited staff member completes signup.
    Links the new account to the correct placeholder user and returns their tenant slug.
    """
    from django.core import signing
    from django.db import connection as _conn
    _conn.set_schema_to_public()

    token = request.data.get('token', '').strip()
    if not token:
        return Response({'error': 'No invite token provided'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        data = signing.loads(token, salt='staff_invitation', max_age=7 * 24 * 3600)
        placeholder_id = data['user_id']
    except signing.SignatureExpired:
        return Response({'error': 'Invitation link has expired. Please ask your manager to resend the invite.'}, status=400)
    except (signing.BadSignature, KeyError):
        return Response({'error': 'Invalid invitation token.'}, status=400)

    try:
        placeholder = User.objects.get(id=placeholder_id)
    except User.DoesNotExist:
        return Response({'error': 'Invitation no longer valid.'}, status=400)

    new_user = request.user

    if placeholder.id == new_user.id:
        pass
    elif not placeholder.has_usable_password():
        # Placeholder was created by staff invite system (no password yet) — merge
        from django.db import connection as _raw_conn
        with _raw_conn.cursor() as cur:
            cur.execute(
                "UPDATE authentication_user SET username = %s WHERE id = %s",
                [f'_pending_delete_{new_user.id}', new_user.id],
            )

        placeholder.is_active = True
        update_fields = ['is_active']
        if new_user.first_name and not placeholder.first_name:
            placeholder.first_name = new_user.first_name
            update_fields.append('first_name')
        if new_user.last_name and not placeholder.last_name:
            placeholder.last_name = new_user.last_name
            update_fields.append('last_name')
        if new_user.email and not placeholder.email:
            placeholder.email = new_user.email
            update_fields.append('email')

        # Copy the password hash from the new account to the placeholder
        placeholder.password = new_user.password
        update_fields.append('password')
        placeholder.is_verified = True
        update_fields.append('is_verified')

        placeholder.save(update_fields=update_fields)

        if new_user.id != placeholder.id:
            try:
                with _raw_conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM authentication_user WHERE id = %s",
                        [new_user.id],
                    )
            except Exception as del_err:
                print(f"[LINK STAFF] Could not delete duplicate user {new_user.id}: {del_err}")

    from django_tenants.utils import tenant_context as _tc
    from staff.models import StaffMember as _SM

    for candidate in Tenant.objects.exclude(schema_name='public'):
        with _tc(candidate):
            if _SM.objects.filter(user=placeholder).exists():
                # Issue fresh JWT tokens for the placeholder (now the real account)
                tokens = _jwt_tokens_for_user(placeholder)
                return Response({
                    'success': True,
                    'slug': candidate.slug or candidate.schema_name,
                    'tenant_name': candidate.name,
                    'access': tokens['access'],
                    'refresh': tokens['refresh'],
                })

    return Response({'error': 'No restaurant found for this invitation.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_auth(request):
    """Test endpoint to verify authentication is working"""
    return Response({
        'message': 'Authentication successful!',
        'user': request.user.email,
        'tenant': getattr(request.tenant, 'name', 'No tenant') if hasattr(request, 'tenant') and request.tenant else 'No tenant',
        'data_received': request.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_auth_event(request):
    """Log a login or logout event to the audit log."""
    from analytics.audit import log_action
    event = request.data.get('event', '')
    if event not in ('login', 'logout'):
        return Response({'error': 'Invalid event.'}, status=400)

    action = 'user_login' if event == 'login' else 'user_logout'
    user = request.user
    label = getattr(user, 'email', '') or str(user.pk)
    log_action(request, action=action, entity_type='user', entity_id=str(user.pk), entity_label=label)
    return Response({'status': 'logged'})
