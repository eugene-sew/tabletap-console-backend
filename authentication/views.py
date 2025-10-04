from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from tenants.models import Tenant
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import uuid
from datetime import timedelta
from django.utils import timezone

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
        
        # Create user
        user, created = User.objects.get_or_create(
            clerk_user_id=clerk_user_id,
            defaults={
                'username': clerk_user_id,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'is_verified': True
            }
        )
        
        if created:
            # Create tenant for new user
            schema_name = f"tenant_{uuid.uuid4().hex[:8]}"
            tenant = Tenant.objects.create(
                schema_name=schema_name,
                name=f"{first_name} {last_name}".strip() or email.split('@')[0],
                contact_email=email,
                subscription_status='trial',
                trial_end_date=timezone.now() + timedelta(days=7),
                clerk_organization_id=clerk_user_id
            )
            
            return Response({
                'status': 'success',
                'tenant_id': tenant.id,
                'schema_name': schema_name
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
    """Get user's tenant information"""
    try:
        tenant = Tenant.objects.get(clerk_organization_id=request.user.clerk_user_id)
        return Response({
            'tenant_id': tenant.id,
            'schema_name': tenant.schema_name,
            'name': tenant.name,
            'subscription_status': tenant.subscription_status,
            'trial_end_date': tenant.trial_end_date,
            'is_active': tenant.is_active,
        })
    except Tenant.DoesNotExist:
        return Response({'error': 'No tenant found for user'}, status=404)

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
def test_auth(request):
    """Test endpoint to verify authentication is working"""
    return Response({
        'message': 'Authentication successful!',
        'user': request.user.email,
        'tenant': getattr(request, 'tenant', {}).name if hasattr(request, 'tenant') else 'No tenant context',
        'data_received': request.data
    })
