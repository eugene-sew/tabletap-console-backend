from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_tenants.utils import get_tenant_model
from .models import Tool, ToolAccess, SSOToken
from .serializers import ToolSerializer, ToolAccessSerializer, SSOTokenSerializer

Tenant = get_tenant_model()

class ToolViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tool.objects.filter(is_active=True)
    serializer_class = ToolSerializer

class ToolAccessViewSet(viewsets.ModelViewSet):
    queryset = ToolAccess.objects.all()
    serializer_class = ToolAccessSerializer
    
    def get_queryset(self):
        return ToolAccess.objects.filter(user=self.request.user)

@api_view(['POST'])
def generate_sso_token(request):
    """Generate SSO token for tool access"""
    tool_id = request.data.get('tool_id')
    
    tool = get_object_or_404(Tool, id=tool_id)
    
    # Check if user has access to this tool
    try:
        access = ToolAccess.objects.get(user=request.user, tool=tool)
        if not access.is_granted:
            return Response({'error': 'Access denied'}, status=403)
    except ToolAccess.DoesNotExist:
        return Response({'error': 'Access not configured'}, status=403)
    
    # Get tenant schema from connection
    from django.db import connection
    tenant_schema = connection.schema_name
    
    # Generate token
    sso_token = SSOToken.generate_token(request.user, tool, tenant_schema)
    
    serializer = SSOTokenSerializer(sso_token)
    return Response(serializer.data)

@api_view(['POST'])
def verify_sso_token(request):
    """Verify SSO token from tools"""
    token = request.data.get('token')
    
    try:
        sso_token = SSOToken.objects.get(token=token)
        
        if not sso_token.is_valid():
            return Response({'error': 'Token expired or invalid'}, status=400)
        
        # Mark token as used
        sso_token.is_used = True
        sso_token.save()
        
        return Response({
            'valid': True,
            'user_id': sso_token.user.id,
            'tool_id': sso_token.tool.id,
            'tenant_schema': 'extracted_from_token'  # Extract from JWT payload
        })
        
    except SSOToken.DoesNotExist:
        return Response({'error': 'Invalid token'}, status=400)
