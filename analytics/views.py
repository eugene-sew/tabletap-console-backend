from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from .models import Event, DashboardMetric, AuditLog
from .serializers import EventSerializer, DashboardMetricSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import random
from orders.models import Order
from django.contrib.auth import get_user_model
User = get_user_model()

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
    today = timezone.now()
    
    # Calculate date range based on period
    if period == 'today':
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_date = today - timedelta(days=7)
    elif period == 'month':
        start_date = today - timedelta(days=30)
    else:
        start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get tenant currency (handling cases where tenant/currency might be missing)
    currency = 'GHS' # Default for this project context
    if hasattr(request, 'tenant') and hasattr(request.tenant, 'currency'):
        currency = request.tenant.currency
    
    # Get physical orders for the period (excluding cancelled)
    orders = Order.objects.filter(
        created_at__gte=start_date
    ).exclude(status='cancelled')
    
    if hasattr(request, 'tenant'):
        orders = orders.filter(tenant=request.tenant)
    
    # Calculate metrics
    total_revenue = orders.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    order_count = orders.count()
    avg_order_value = total_revenue / order_count if order_count > 0 else 0
    
    # Orders specifically for today
    today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    today_orders = Order.objects.filter(
        created_at__gte=today_start
    ).exclude(status='cancelled')
    
    if hasattr(request, 'tenant'):
        today_orders = today_orders.filter(tenant=request.tenant)
    
    today_orders_count = today_orders.count()
    
    # Top Fulfillment Type
    top_fulfillment = orders.values('order_type').annotate(
        count=Count('id')
    ).order_by('-count').first()
    
    top_fulfillment_label = "Dine-in" # Default
    if top_fulfillment:
        type_map = dict(Order.ORDER_TYPE_CHOICES)
        top_fulfillment_label = type_map.get(top_fulfillment['order_type'], top_fulfillment['order_type'])

    return Response({
        'success': True,
        'data': {
            'totalRevenue': float(round(total_revenue, 2)),
            'avgOrderValue': float(round(avg_order_value, 2)),
            'todayOrders': today_orders_count,
            'topFulfillment': top_fulfillment_label,
            'currency': currency,
            'period': period,
        },
        'meta': {
            'timestamp': timezone.now().isoformat(),
            'version': '1.1.0'
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
    """Get dashboard activities with pagination, synthesizing from Orders if Events are sparse"""
    page = int(request.query_params.get('page', 1))
    limit = int(request.query_params.get('limit', 5))
    offset = (page - 1) * limit
    
    # Get recent events
    events_queryset = Event.objects.all().order_by('-created_at')
    
    # Get recent orders
    orders_queryset = Order.objects.all().order_by('-created_at')
    
    if hasattr(request, 'tenant') and request.tenant:
        # Filter orders by tenant
        orders_queryset = orders_queryset.filter(tenant=request.tenant)
        # For events, we filter if they have a user associated with this tenant 
        # (Assuming User model is not shared or has tenant info)
        if hasattr(User, 'tenant'):
            events_queryset = events_queryset.filter(user__tenant=request.tenant)

    # Fetch with limits
    events = events_queryset[:limit*2]
    orders = orders_queryset[:limit*2]

    # Format into unified activity structure
    combined_activities = []
    
    for event in events:
        combined_activities.append({
            'id': f"event-{event.id}",
            'type': event.event_type,
            'title': event.get_title(),
            'description': event.get_description(),
            'timestamp': event.created_at,
            'metadata': event.data
        })
        
    for order in orders:
        combined_activities.append({
            'id': f"order-{order.id}",
            'type': 'order',
            'title': f"New Order #{order.order_number}",
            'description': f"Order for {order.customer_name or 'Walk-in'} - {order.table_number or 'No Table'}",
            'timestamp': order.created_at,
            'metadata': {
                'order_id': order.id,
                'total': float(order.total_amount),
                'status': order.status
            }
        })
    
    # Sort combined list by timestamp
    combined_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Paginate manually
    total = len(combined_activities)
    activities_page = combined_activities[offset:offset + limit]
    
    # Fix timestamps for JSON serialization
    for act in activities_page:
        if not isinstance(act['timestamp'], str):
            act['timestamp'] = act['timestamp'].isoformat()
            
    total_pages = (total + limit - 1) // limit if limit > 0 else 1
    
    return Response({
        'success': True,
        'data': {
            'data': activities_page,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'totalPages': total_pages,
            }
        },
        'meta': {
            'timestamp': timezone.now().isoformat(),
            'version': '1.1.0'
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


class AuditLogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_logs(request):
    """
    Return a paginated, filterable list of audit log entries for the current tenant.
    Filters: entity_type, action, actor_email, start_date, end_date, search
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({'success': False, 'error': 'Tenant context required'}, status=400)

    qs = AuditLog.objects.filter(tenant_schema=tenant.schema_name)

    entity_type = request.query_params.get('entity_type')
    if entity_type:
        qs = qs.filter(entity_type=entity_type)

    action_filter = request.query_params.get('action')
    if action_filter:
        qs = qs.filter(action=action_filter)

    actor_email = request.query_params.get('actor_email')
    if actor_email:
        qs = qs.filter(actor_email=actor_email)

    start_date = request.query_params.get('start_date')
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)

    end_date = request.query_params.get('end_date')
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)

    search = request.query_params.get('search', '').strip()
    if search:
        from django.db.models import Q as _Q
        qs = qs.filter(
            _Q(actor_name__icontains=search) |
            _Q(actor_email__icontains=search) |
            _Q(entity_label__icontains=search) |
            _Q(action__icontains=search)
        )

    paginator = AuditLogPagination()
    page = paginator.paginate_queryset(qs, request)

    data = [
        {
            'id': log.id,
            'actor_name': log.actor_name or 'System',
            'actor_email': log.actor_email,
            'action': log.action,
            'action_label': log.get_action_display(),
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'entity_label': log.entity_label,
            'metadata': log.metadata,
            'created_at': log.created_at.isoformat(),
        }
        for log in page
    ]

    return paginator.get_paginated_response(data)
