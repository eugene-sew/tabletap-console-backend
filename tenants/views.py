from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta
import uuid
from .models import Tenant, Domain
from .serializers import TenantSerializer, DomainSerializer, RestaurantSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new tenant with automatic schema generation"""
        data = request.data.copy()
        
        # Generate unique schema name
        schema_name = f"tenant_{uuid.uuid4().hex[:8]}"
        data['schema_name'] = schema_name
        
        # Set trial period (7 days)
        data['trial_end_date'] = timezone.now() + timedelta(days=7)
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        tenant = serializer.save()
        
        # Create default domain
        domain_name = f"{schema_name}.localhost"
        Domain.objects.create(
            domain=domain_name,
            tenant=tenant,
            is_primary=True
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def activate_subscription(self, request, pk=None):
        """Activate tenant subscription"""
        tenant = self.get_object()
        tenant.subscription_status = 'active'
        tenant.save()
        return Response({'status': 'subscription activated'})
    
    @action(detail=True, methods=['post'])
    def deactivate_subscription(self, request, pk=None):
        """Deactivate tenant subscription"""
        tenant = self.get_object()
        tenant.subscription_status = 'inactive'
        tenant.save()
        return Response({'status': 'subscription deactivated'})


@swagger_auto_schema(
    method='get',
    operation_description="Get current restaurant/tenant information",
    responses={
        200: RestaurantSerializer,
        404: 'Restaurant not found'
    }
)
@swagger_auto_schema(
    method='put',
    operation_description="Update current restaurant/tenant information",
    request_body=RestaurantSerializer,
    responses={
        200: RestaurantSerializer,
        400: 'Validation errors'
    }
)
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def restaurant_current(request):
    """Get or update current restaurant information"""
    try:
        # Get current tenant from request
        tenant = request.tenant
        
        if request.method == 'GET':
            serializer = RestaurantSerializer(tenant)
            return Response({
                'success': True,
                'data': serializer.data,
                'meta': {
                    'timestamp': timezone.now().isoformat(),
                    'version': '1.0.0'
                }
            })
        
        elif request.method == 'PUT':
            serializer = RestaurantSerializer(tenant, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    'success': True,
                    'data': serializer.data,
                    'message': 'Restaurant information updated successfully',
                    'meta': {
                        'timestamp': timezone.now().isoformat(),
                        'version': '1.0.0'
                    }
                })
            else:
                return Response({
                    'success': False,
                    'errors': serializer.errors,
                    'message': 'Validation failed',
                    'meta': {
                        'timestamp': timezone.now().isoformat(),
                        'version': '1.0.0'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
                
    except AttributeError:
        return Response({
            'success': False,
            'message': 'No restaurant found for current user',
            'meta': {
                'timestamp': timezone.now().isoformat(),
                'version': '1.0.0'
            }
        }, status=status.HTTP_404_NOT_FOUND)
