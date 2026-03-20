from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import connection
from tenants.models import Tenant
from .models import Order
from .pusher_client import get_pusher_client
from .serializers import OrderSerializer

@shared_task
def check_stale_orders():
    """
    Checks for orders that have been in 'pending' or 'preparing' status 
    for more than 30 minutes and notifies the restaurant owner.
    """
    now = timezone.now()
    stale_limit = now - timedelta(minutes=30)
    
    # Iterate through all tenants except public
    tenants = Tenant.objects.exclude(schema_name='public')
    
    for tenant in tenants:
        # Switch connection to the tenant's schema
        connection.set_tenant(tenant)
        
        stale_orders = Order.objects.filter(
            status__in=['pending', 'preparing'],
            created_at__lt=stale_limit,
            is_stale_notified=False
        )
        
        if stale_orders.exists():
            client = get_pusher_client()
            tenant_slug = tenant.slug
            channel = f"orders-{tenant_slug}"
            
            for order in stale_orders:
                print(f"[Celery] Found stale order: {order.order_number} for tenant: {tenant.name}")
                
                # Trigger Pusher event
                if client:
                    data = OrderSerializer(order).data
                    # Ensure decimal/datetime are serializable
                    data['total_amount'] = float(data['total_amount'] or 0)
                    data['created_at'] = str(data['created_at'])
                    
                    client.trigger(channel, 'stale-order', data)
                
                # Mark as notified
                order.is_stale_notified = True
                order.save()
    
    return f"Checked {tenants.count()} tenants for stale orders."
