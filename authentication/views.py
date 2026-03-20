from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.conf import settings
from tenants.models import Tenant
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import uuid
from datetime import timedelta
from django.utils import timezone
import django_tenants

User = get_user_model()

@swagger_auto_schema(
    method='post',
    operation_description="Handle Clerk webhooks for user events",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'type': openapi.Schema(type=openapi.TYPE_STRING, description='Event type'),
            'data': openapi.Schema(type=openapi.TYPE_OBJECT, description='User data'),
        }
    ),
    responses={200: 'Webhook processed successfully'}
)
@api_view(['POST'])
@permission_classes([AllowAny])
def clerk_webhook(request):
    """Handle Clerk webhooks for user events"""
    event_type = request.data.get('type')
    user_data = request.data.get('data', {})
    
    if event_type == 'user.created':
        # Create new tenant when user signs up
        clerk_user_id = user_data.get('id')
        email = user_data.get('email_addresses', [{}])[0].get('email_address')
        first_name = user_data.get('first_name', '')
        last_name = user_data.get('last_name', '')
        
        # Sanitize email (treat empty string as None)
        email = email if email else None
        
        # Check if user already exists by email (ONLY if email is provided)
        user = User.objects.filter(email=email).first() if email else None
        
        if user:
            # Link the Clerk account but preserve existing role —
            # invited staff must not be silently upgraded to 'owner'.
            user.clerk_user_id = clerk_user_id
            user.username = clerk_user_id
            user.first_name = first_name
            user.last_name = last_name
            user.is_verified = True
            user.is_active = True
            user.save(update_fields=[
                'clerk_user_id', 'username', 'first_name', 'last_name',
                'is_verified', 'is_active',
            ])
            user_created = False
        else:
            # Create brand new user
            user, user_created = User.objects.update_or_create(
                clerk_user_id=clerk_user_id,
                defaults={
                    'username': clerk_user_id,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_verified': True,
                    'role': 'owner' 
                }
            )
        
        # Get restaurant name from metadata
        restaurant_name = user_data.get('unsafe_metadata', {}).get('restaurantName')
        
        # Provision tenant using shared service
        from .services import provision_tenant_for_user
        tenant, tenant_created = provision_tenant_for_user(user, restaurant_name)
        
        return Response({
            'status': 'success',
            'tenant_id': tenant.id,
            'schema_name': tenant.schema_name,
            'user_created': user_created,
            'tenant_created': tenant_created
        })
    
    return Response({'status': 'processed'})

@swagger_auto_schema(
    method='get',
    operation_description="Get current user profile",
    responses={
        200: openapi.Response(
            description="User profile",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'firstName': openapi.Schema(type=openapi.TYPE_STRING),
                            'lastName': openapi.Schema(type=openapi.TYPE_STRING),
                            'email': openapi.Schema(type=openapi.TYPE_STRING),
                            'role': openapi.Schema(type=openapi.TYPE_STRING),
                            'restaurantId': openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    )
                }
            )
        )
    }
)
@swagger_auto_schema(
    method='put',
    operation_description="Update current user profile",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'firstName': openapi.Schema(type=openapi.TYPE_STRING),
            'lastName': openapi.Schema(type=openapi.TYPE_STRING),
            'email': openapi.Schema(type=openapi.TYPE_STRING),
        }
    ),
    responses={
        200: 'Profile updated successfully',
        400: 'Validation errors'
    }
)
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """Get or update current user profile"""
    if request.method == 'GET':
        # Get restaurant ID from current tenant
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
    
    elif request.method == 'PUT':
        user = request.user
        data = request.data
        
        # Update allowed fields
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
                'meta': {
                    'timestamp': timezone.now().isoformat(),
                    'version': '1.0.0'
                }
            }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_description="Get user's tenant information",
    responses={
        200: openapi.Response(
            description="Tenant information",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'tenant_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                    'schema_name': openapi.Schema(type=openapi.TYPE_STRING),
                    'name': openapi.Schema(type=openapi.TYPE_STRING),
                    'subscription_status': openapi.Schema(type=openapi.TYPE_STRING),
                    'trial_end_date': openapi.Schema(type=openapi.TYPE_STRING),
                    'is_active': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                }
            )
        ),
        404: 'No tenant found for user'
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_tenant(request):
    """Get user's tenant information, provisioning one via JIT if it doesn't exist yet."""
    # Always operate from the public schema — tenant records live there, and
    # creating a new tenant from a non-public schema raises an error.
    from django.db import connection as _conn
    _conn.set_schema_to_public()
    tenant = None

    try:
        from django_tenants.utils import tenant_context as _tc
        from staff.models import StaffMember as _SM

        # Path 1 (highest priority): invited staff — search for a StaffMember record
        # across all tenant schemas. This must run BEFORE the owner lookup so that
        # a staff member's Clerk ID is never mistakenly matched to a spurious tenant
        # that may have been provisioned with their Clerk ID as clerk_organization_id.
        for candidate in Tenant.objects.exclude(schema_name='public'):
            with _tc(candidate):
                if _SM.objects.filter(user=request.user).exists():
                    tenant = candidate
                    print(f"[TENANT] Staff member {request.user.email} found in tenant '{candidate.name}'")
                    break

        # Path 2: owner — tenant is indexed by their Clerk user ID (only if not
        # already found as a staff member above)
        if tenant is None:
            tenant = Tenant.objects.filter(
                clerk_organization_id=request.user.clerk_user_id
            ).first()

    except Exception as e:
        return Response({
            'error': 'Tenant discovery failed',
            'detail': str(e),
            'message': 'An unexpected error occurred. Please contact support.'
        }, status=500)

    if tenant is None:
        # Path 3: truly new owner signup — JIT provision a fresh tenant.
        # Guard: only provision if the user has a restaurant name from Clerk metadata,
        # preventing spurious tenants being created for staff who aren't linked yet.
        restaurant_name = None
        if settings.CLERK_SECRET_KEY:
            try:
                import requests as req
                headers = {"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"}
                clerk_resp = req.get(
                    f"https://api.clerk.dev/v1/users/{request.user.clerk_user_id}",
                    headers=headers,
                    timeout=5
                )
                if clerk_resp.status_code == 200:
                    clerk_data = clerk_resp.json()
                    restaurant_name = (
                        clerk_data.get('unsafe_metadata', {}).get('restaurantName') or
                        clerk_data.get('public_metadata', {}).get('restaurantName')
                    )
            except Exception as fetch_err:
                print(f"[TENANT JIT] Could not fetch Clerk user data: {fetch_err}")

        if not restaurant_name:
            # No restaurant name means this is NOT a new owner — it's a staff member
            # whose link hasn't been set up yet. Return a clear error instead of
            # creating a spurious tenant.
            return Response({
                'error': 'No restaurant found',
                'message': 'Your account is not linked to a restaurant yet. Please ask your manager to resend the invitation, or sign up via the Console.',
            }, status=404)

        from .services import provision_tenant_for_user
        tenant, _ = provision_tenant_for_user(request.user, restaurant_name)

        if not tenant:
            return Response({
                'error': 'Tenant provisioning failed',
                'message': 'We could not create a restaurant for your account. Please contact support.'
            }, status=500)

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
    Called by the frontend immediately after a new user signs up,
    passing the restaurant name collected during registration.
    Idempotent — safe to call even if the tenant already exists.
    Staff members are detected first and routed to their existing tenant.
    """
    from django.db import connection
    connection.set_schema_to_public()

    # --- Staff path: find their existing tenant instead of creating a new one ---
    from django_tenants.utils import tenant_context as _tc
    from staff.models import StaffMember as _SM

    for candidate in Tenant.objects.exclude(schema_name='public'):
        with _tc(candidate):
            if _SM.objects.filter(user=request.user).exists():
                print(f"[PROVISION] {request.user.email} is staff in '{candidate.name}' — skipping new tenant creation.")
                return Response({
                    'tenant_id': candidate.id,
                    'schema_name': candidate.schema_name,
                    'slug': candidate.slug or candidate.schema_name,
                    'name': candidate.name,
                    'subscription_status': candidate.subscription_status,
                    'is_active': candidate.is_active,
                    'created': False,
                })

    # --- Owner path: provision or return existing tenant ---
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

@swagger_auto_schema(
    method='post',
    operation_description="Test endpoint to verify authentication is working",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'test': openapi.Schema(type=openapi.TYPE_STRING, description='Test data'),
        }
    ),
    responses={
        200: openapi.Response(
            description="Authentication test result",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'message': openapi.Schema(type=openapi.TYPE_STRING),
                    'user': openapi.Schema(type=openapi.TYPE_STRING),
                    'tenant': openapi.Schema(type=openapi.TYPE_STRING),
                    'data_received': openapi.Schema(type=openapi.TYPE_OBJECT),
                }
            )
        )
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def link_staff_account(request):
    """
    Called by the frontend after an invited staff member completes Clerk signup.
    Receives a signed invite token (generated at invite time) and links the new
    Clerk account to the correct placeholder user + returns their tenant slug.
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
        return Response({'error': 'Invitation link has expired. Please ask your manager to resend the invite.'}, status=status.HTTP_400_BAD_REQUEST)
    except (signing.BadSignature, KeyError):
        return Response({'error': 'Invalid invitation token.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        placeholder = User.objects.get(id=placeholder_id)
    except User.DoesNotExist:
        return Response({'error': 'Invitation no longer valid.'}, status=status.HTTP_400_BAD_REQUEST)

    new_user = request.user

    if placeholder.id == new_user.id:
        pass
    elif not placeholder.clerk_user_id:
        clerk_id = new_user.clerk_user_id

        # 1. Clear unique fields from new_user first — avoids IntegrityError when
        #    we later set the same clerk_user_id on the placeholder.
        from django.db import connection as _raw_conn
        with _raw_conn.cursor() as cur:
            cur.execute(
                "UPDATE authentication_user SET clerk_user_id = NULL, username = %s WHERE id = %s",
                [f'_pending_delete_{new_user.id}', new_user.id],
            )

        # 2. Now safely assign the real Clerk ID to the placeholder, and copy
        #    display information (name, email) from the newly created Clerk account.
        placeholder.clerk_user_id = clerk_id
        placeholder.username = clerk_id
        placeholder.is_active = True
        update_fields = ['clerk_user_id', 'username', 'is_active']
        if new_user.first_name and not placeholder.first_name:
            placeholder.first_name = new_user.first_name
            update_fields.append('first_name')
        if new_user.last_name and not placeholder.last_name:
            placeholder.last_name = new_user.last_name
            update_fields.append('last_name')
        if new_user.email and not placeholder.email:
            placeholder.email = new_user.email
            update_fields.append('email')
        placeholder.save(update_fields=update_fields)

        # 3. Delete the now-orphaned duplicate via raw SQL so that Django ORM
        #    cascade logic (which tries tenant-schema tables) is bypassed entirely.
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
                print(f"[LINK STAFF] {placeholder.email} linked to tenant '{candidate.name}'")
                return Response({
                    'success': True,
                    'slug': candidate.slug or candidate.schema_name,
                    'tenant_name': candidate.name,
                })

    return Response({'error': 'No restaurant found for this invitation.'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_auth(request):
    """Test endpoint to verify authentication is working"""
    return Response({
        'message': 'Authentication successful!',
        'user': request.user.email,
        'tenant': getattr(request.tenant, 'name', 'No tenant name') if hasattr(request, 'tenant') and request.tenant else 'No tenant context',
        'data_received': request.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_auth_event(request):
    """Log a login or logout event to the audit log."""
    from analytics.audit import log_action
    event = request.data.get('event', '')
    if event not in ('login', 'logout'):
        return Response({'error': 'Invalid event. Must be "login" or "logout".'}, status=400)

    action = 'user_login' if event == 'login' else 'user_logout'
    user = request.user
    label = getattr(user, 'email', '') or getattr(user, 'username', '') or str(user.pk)
    log_action(request, action=action, entity_type='user', entity_id=str(user.pk), entity_label=label)
    return Response({'status': 'logged'})
