from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from tenants.models import Tenant
import uuid
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

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

@api_view(['GET'])
def user_profile(request):
    """Get current user profile"""
    if not request.user.is_authenticated:
        return Response({'error': 'Not authenticated'}, status=401)
    
    return Response({
        'id': request.user.id,
        'username': request.user.username,
        'email': request.user.email,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'clerk_user_id': request.user.clerk_user_id,
    })
