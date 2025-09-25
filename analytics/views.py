from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from .models import Event, DashboardMetric
from .serializers import EventSerializer, DashboardMetricSerializer

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

@api_view(['GET'])
def dashboard_summary(request):
    """Get dashboard summary metrics"""
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
