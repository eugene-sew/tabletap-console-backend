from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from .models import Table
from .serializers import (
    TableSerializer, TableCreateSerializer, 
    BulkTableCreateSerializer, QRBatchSerializer
)
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TableCreateSerializer
        return TableSerializer
    
    def perform_create(self, serializer):
        """Create table and generate QR code"""
        table = serializer.save()
        
        # Get restaurant slug from current tenant
        restaurant_slug = getattr(self.request.tenant, 'slug', 'default') if hasattr(self.request, 'tenant') else 'default'
        
        # Generate QR code URL
        table.generate_qr_code_url(restaurant_slug)
        table.save()
    
    def perform_update(self, serializer):
        """Update table and regenerate QR code if needed"""
        table = serializer.save()
        
        # Regenerate QR code if table number changed
        if 'number' in serializer.validated_data:
            restaurant_slug = getattr(self.request.tenant, 'slug', 'default') if hasattr(self.request, 'tenant') else 'default'
            table.generate_qr_code_url(restaurant_slug)
            table.save()

@swagger_auto_schema(
    method='post',
    operation_description="Bulk create tables",
    request_body=BulkTableCreateSerializer,
    responses={
        201: openapi.Response(
            description="Tables created successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'created': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'tables': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(type=openapi.TYPE_OBJECT)
                            )
                        }
                    )
                }
            )
        ),
        400: 'Validation errors'
    }
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_generate_tables(request):
    """Bulk generate tables"""
    serializer = BulkTableCreateSerializer(data=request.data)
    
    if serializer.is_valid():
        data = serializer.validated_data
        from_table = data['fromTable']
        to_table = data['toTable']
        section = data.get('section', '')
        
        # Get restaurant slug
        restaurant_slug = getattr(request.tenant, 'slug', 'default') if hasattr(request, 'tenant') else 'default'
        
        created_tables = []
        
        with transaction.atomic():
            for table_num in range(from_table, to_table + 1):
                table = Table.objects.create(
                    number=table_num,
                    section=section,
                    status='active'
                )
                
                # Generate QR code
                table.generate_qr_code_url(restaurant_slug)
                table.save()
                
                created_tables.append(table)
        
        # Serialize created tables
        table_serializer = TableSerializer(created_tables, many=True)
        
        return Response({
            'success': True,
            'data': {
                'created': len(created_tables),
                'tables': table_serializer.data
            },
            'message': f'Successfully created {len(created_tables)} tables',
            'meta': {
                'timestamp': timezone.now().isoformat(),
                'version': '1.0.0'
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors,
        'message': 'Validation failed',
        'meta': {
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0'
        }
    }, status=status.HTTP_400_BAD_REQUEST)

@swagger_auto_schema(
    method='get',
    operation_description="Get QR codes for all tables",
    responses={
        200: openapi.Response(
            description="QR batch data",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'tables': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(type=openapi.TYPE_OBJECT)
                            ),
                            'restaurantSlug': openapi.Schema(type=openapi.TYPE_STRING)
                        }
                    )
                }
            )
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def qr_batch(request):
    """Get QR codes for all tables"""
    tables = Table.objects.filter(status='active').order_by('number')
    restaurant_slug = getattr(request.tenant, 'slug', 'default') if hasattr(request, 'tenant') else 'default'
    
    # Ensure all tables have QR codes
    for table in tables:
        if not table.qr_code_url:
            table.generate_qr_code_url(restaurant_slug)
            table.save()
    
    serializer = TableSerializer(tables, many=True)
    
    return Response({
        'success': True,
        'data': {
            'tables': serializer.data,
            'restaurantSlug': restaurant_slug
        },
        'meta': {
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0'
        }
    })
