from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from .models import Event, DashboardMetric
from .serializers import EventSerializer, DashboardMetricSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import random

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    
    def get_queryset(self):
        queryset = Event.objects.all().order_by('-created_at')
        
        # Filter by event type
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset

@swagger_auto_schema(
    method='get',
    operation_description="Get dashboard metrics",
    manual_parameters=[
        openapi.Parameter('period', openapi.IN_QUERY, description="Period: today, week, month", type=openapi.TYPE_STRING)
    ],
    responses={
        200: openapi.Response(
            description="Dashboard metrics",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'totalRevenue': openapi.Schema(type=openapi.TYPE_NUMBER),
                            'activeCustomers': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'todayOrders': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'currency': openapi.Schema(type=openapi.TYPE_STRING),
                            'period': openapi.Schema(type=openapi.TYPE_STRING),
                        }
                    )
                }
            )
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_metrics(request):
    """Get dashboard metrics for frontend"""
    period = request.query_params.get('period', 'today')
    today = timezone.now().date()
    
    # Calculate date range based on period
    if period == 'today':
        start_date = today
    elif period == 'week':
        start_date = today - timedelta(days=7)
    elif period == 'month':
        start_date = today - timedelta(days=30)
    else:
        start_date = today
    
    # Get tenant currency
    currency = getattr(request.tenant, 'currency', 'USD') if hasattr(request, 'tenant') else 'USD'
    
    # Calculate metrics (using mock data for now - replace with real data from POS/Menu services)
    order_events = Event.objects.filter(
        event_type='order',
        created_at__date__gte=start_date
    )
    
    # Mock calculations - replace with real data
    total_revenue = sum([
        float(event.data.get('amount', random.uniform(10, 100))) 
        for event in order_events
    ])
    
    active_customers = Event.objects.filter(
        event_type='customer',
        created_at__date__gte=start_date
    ).values('user').distinct().count()
    
    today_orders = Event.objects.filter(
        event_type='order',
        created_at__date=today
    ).count()
    
    return Response({
        'success': True,
        'data': {
            'totalRevenue': round(total_revenue, 2),
            'activeCustomers': active_customers,
            'todayOrders': today_orders,
            'currency': currency,
            'period': period,
        },
        'meta': {
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0'
        }
    })

@swagger_auto_schema(
    method='get',
    operation_description="Get dashboard activities",
    manual_parameters=[
        openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
        openapi.Parameter('limit', openapi.IN_QUERY, description="Items per page", type=openapi.TYPE_INTEGER)
    ],
    responses={
        200: openapi.Response(
            description="Dashboard activities",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                    'data': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'activities': openapi.Schema(
                                type=openapi.TYPE_ARRAY,
                                items=openapi.Schema(
                                    type=openapi.TYPE_OBJECT,
                                    properties={
                                        'id': openapi.Schema(type=openapi.TYPE_STRING),
                                        'type': openapi.Schema(type=openapi.TYPE_STRING),
                                        'title': openapi.Schema(type=openapi.TYPE_STRING),
                                        'description': openapi.Schema(type=openapi.TYPE_STRING),
                                        'timestamp': openapi.Schema(type=openapi.TYPE_STRING),
                                        'metadata': openapi.Schema(type=openapi.TYPE_OBJECT),
                                    }
                                )
                            ),
                            'pagination': openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'page': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'limit': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'total': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'totalPages': openapi.Schema(type=openapi.TYPE_INTEGER),
                                }
                            )
                        }
                    )
                }
            )
        )
    }
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_activities(request):
    """Get dashboard activities with pagination"""
    # Pagination
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 20))
    offset = (page - 1) * limit
    
    # Get recent events
    events = Event.objects.all().order_by('-created_at')
    total = events.count()
    events_page = events[offset:offset + limit]
    
    # Format activities
    activities = []
    for event in events_page:
        activities.append({
            'id': str(event.id),
            'type': event.event_type,
            'title': event.get_title(),
            'description': event.get_description(),
            'timestamp': event.created_at.isoformat(),
            'metadata': event.data
        })
    
    total_pages = (total + limit - 1) // limit
    
    return Response({
        'success': True,
        'data': {
            'activities': activities,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'totalPages': total_pages,
            }
        },
        'meta': {
            'timestamp': timezone.now().isoformat(),
            'version': '1.0.0'
        }
    })

@api_view(['GET'])
def dashboard_summary(request):
    """Get dashboard summary metrics (legacy endpoint)"""
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    # Event counts
    today_events = Event.objects.filter(created_at__date=today).count()
    week_events = Event.objects.filter(created_at__date__gte=week_ago).count()
    month_events = Event.objects.filter(created_at__date__gte=month_ago).count()
    
    # Event breakdown by type
    event_breakdown = Event.objects.filter(
        created_at__date__gte=week_ago
    ).values('event_type').annotate(count=Count('id'))
    
    # Recent metrics
    recent_metrics = DashboardMetric.objects.filter(
        date__gte=week_ago
    ).order_by('-date')[:10]
    
    return Response({
        'summary': {
            'today_events': today_events,
            'week_events': week_events,
            'month_events': month_events,
        },
        'event_breakdown': list(event_breakdown),
        'recent_metrics': DashboardMetricSerializer(recent_metrics, many=True).data
    })

@api_view(['POST'])
def track_event(request):
    """Track an event from external tools"""
    serializer = EventSerializer(data=request.data)
    if serializer.is_valid():
        # Add IP and user agent from request
        event = serializer.save(
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
