from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
import uuid
from .models import Tenant, Domain
from .serializers import TenantSerializer, DomainSerializer

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
