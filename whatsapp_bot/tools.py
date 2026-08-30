"""
Bot tool functions — direct DB access (no HTTP round-trip).

Each function operates within the correct tenant schema by accepting
a tenant_slug and temporarily setting the DB connection to that schema.

These functions are called by the Gemini agent when it decides to use a tool.
"""
import logging
from decimal import Decimal
from django.db import connection
from django_tenants.utils import schema_context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema context helper
# ---------------------------------------------------------------------------

def _with_tenant(tenant_slug: str):
    """Context manager: switch DB connection to tenant schema by slug or schema name."""
    from tenants.models import Tenant
    connection.set_schema_to_public()
    try:
        t = Tenant.objects.filter(slug=tenant_slug).first() or Tenant.objects.filter(schema_name=tenant_slug).first()
        schema = t.schema_name if t else tenant_slug
    except Exception:
        schema = tenant_slug
    return schema_context(schema)


# ---------------------------------------------------------------------------
# Customer tools
# ---------------------------------------------------------------------------

def get_menu(tenant_slug: str, category_filter: str = '') -> dict:
    """
    Returns the restaurant's menu grouped by category.
    Only includes available items.
    """
    with _with_tenant(tenant_slug):
        from menu.models import Category, MenuItem
        categories = Category.objects.prefetch_related('items').order_by('priority', 'name')
        result = []
        for cat in categories:
            items = cat.items.filter(isAvailable=True)
            if category_filter:
                if category_filter.lower() not in cat.name.lower():
                    continue
            if not items.exists():
                continue
            result.append({
                'category': cat.name,
                'items': [
                    {
                        'id': str(item.pk),
                        'name': item.name,
                        'description': item.description,
                        'price': float(item.price),
                    }
                    for item in items
                ],
            })
        return {'menu': result, 'total_categories': len(result)}


def get_item_details(tenant_slug: str, item_name: str) -> dict:
    """Search for a menu item by name (case-insensitive partial match)."""
    with _with_tenant(tenant_slug):
        from menu.models import MenuItem
        items = MenuItem.objects.filter(
            name__icontains=item_name,
            isAvailable=True,
        )[:5]
        return {
            'items': [
                {
                    'id': str(i.pk),
                    'name': i.name,
                    'description': i.description,
                    'price': float(i.price),
                    'category': i.category.name,
                }
                for i in items
            ]
        }


def get_payment_info(tenant_slug: str) -> dict:
    """Returns the restaurant's payment methods and MoMo details."""
    from tenants.models import Tenant
    try:
        tenant = Tenant.objects.get(slug=tenant_slug)
        s = tenant.settings or {}
        return {
            'payment_methods': s.get('paymentMethods', ['cash']),
            'momo_number': s.get('momoNumber', ''),
            'momo_qr_code': s.get('momoQrCode', ''),
            'currency': tenant.currency or 'GHS',
        }
    except Tenant.DoesNotExist:
        return {'payment_methods': ['cash'], 'currency': 'GHS'}


def track_order(tenant_slug: str, order_number: str) -> dict:
    """Get the current status of an order by order number."""
    with _with_tenant(tenant_slug):
        from orders.models import Order
        try:
            order = Order.objects.get(order_number=order_number)
            STATUS_LABELS = {
                'pending': 'Received — we\'re looking at it 👀',
                'preparing': 'Being prepared in the kitchen 🍳',
                'ready': 'Ready! Come pick it up 🎉',
                'completed': 'Completed ✅',
                'cancelled': 'Cancelled',
            }
            return {
                'found': True,
                'order_number': order.order_number,
                'status': order.status,
                'status_label': STATUS_LABELS.get(order.status, order.status),
                'total_amount': float(order.total_amount),
                'order_type': order.order_type,
                'payment_status': order.payment_status,
            }
        except Order.DoesNotExist:
            return {'found': False, 'message': f'No order found with number {order_number}'}


def place_order(
    tenant_slug: str,
    items: list,
    order_type: str,
    customer_name: str,
    customer_phone: str,
    delivery_address: str = '',
    delivery_notes: str = '',
) -> dict:
    """
    Create an order in the database and fire the Pusher new-order event.
    items: [{'menu_item_id': str, 'name': str, 'quantity': int, 'price': float}]
    order_type: 'pickup' | 'delivery' | 'dine_in'
    """
    with _with_tenant(tenant_slug):
        from orders.models import Order, OrderItem
        from orders.pusher_client import get_pusher_client
        from orders.serializers import OrderSerializer
        from tenants.models import Tenant
        import uuid

        tenant = Tenant.objects.get(slug=tenant_slug)
        settings_data = tenant.settings or {}
        tax_rate = Decimal(str(settings_data.get('taxRate', 0))) / 100
        delivery_fee = Decimal(str(settings_data.get('deliveryFee', 0))) if order_type == 'delivery' else Decimal('0')

        subtotal = sum(Decimal(str(i['price'])) * Decimal(str(i['quantity'])) for i in items)
        tax_amount = (subtotal * tax_rate).quantize(Decimal('0.01'))
        total_amount = subtotal + tax_amount + delivery_fee

        # Generate short order number
        order_number = f'WA-{uuid.uuid4().hex[:6].upper()}'

        order = Order.objects.create(
            tenant=tenant,
            order_number=order_number,
            customer_name=customer_name,
            customer_phone=customer_phone,
            order_type=order_type,
            delivery_address=delivery_address,
            delivery_notes=delivery_notes,
            delivery_fee=delivery_fee,
            tax_amount=tax_amount,
            total_amount=total_amount,
            status='pending',
            payment_status='unpaid',
        )

        for item in items:
            OrderItem.objects.create(
                order=order,
                menu_item_id=item.get('menu_item_id', ''),
                name=item['name'],
                quantity=item['quantity'],
                price=Decimal(str(item['price'])),
            )

        # Fire Pusher event (reuse existing pusher trigger logic)
        try:
            client = get_pusher_client()
            if client:
                data = OrderSerializer(order).data
                data['total_amount'] = float(data['total_amount'] or 0)
                if 'created_at' in data and data['created_at']:
                    data['created_at'] = str(data['created_at'])
                for it in data.get('items', []):
                    it['price'] = float(it['price'] or 0)
                client.trigger(f'orders-{tenant_slug}', 'new-order', data)
        except Exception as e:
            logger.warning(f'[WhatsApp] Pusher trigger failed: {e}')

        return {
            'success': True,
            'order_number': order_number,
            'total_amount': float(total_amount),
            'currency': tenant.currency or 'GHS',
            'status': 'pending',
        }


# ---------------------------------------------------------------------------
# Owner tools (require authenticated staff token)
# ---------------------------------------------------------------------------

def get_live_orders(tenant_slug: str) -> dict:
    """Owner: get all active (non-completed) orders."""
    with _with_tenant(tenant_slug):
        from orders.models import Order
        active = Order.objects.filter(
            status__in=['pending', 'preparing', 'ready']
        ).order_by('-created_at')[:20]
        return {
            'count': active.count(),
            'orders': [
                {
                    'order_number': o.order_number,
                    'status': o.status,
                    'customer_name': o.customer_name or 'Guest',
                    'order_type': o.order_type,
                    'total': float(o.total_amount),
                    'items_count': o.items.count(),
                    'minutes_ago': int((
                        __import__('django.utils.timezone', fromlist=['now']).now() - o.created_at
                    ).total_seconds() / 60),
                }
                for o in active
            ],
        }


def get_metrics_summary(tenant_slug: str, period: str = 'today') -> dict:
    """Owner: order count, revenue, breakdown, AOV, and top items."""
    with _with_tenant(tenant_slug):
        from orders.models import Order, OrderItem
        from django.utils import timezone
        from django.db.models import Sum, Count, Avg
        from datetime import timedelta

        now = timezone.now()
        if period == 'week':
            start_date = (now - timedelta(days=7)).date()
            label = "Last 7 Days"
        elif period == 'month':
            start_date = (now - timedelta(days=30)).date()
            label = "Last 30 Days"
        else:
            start_date = now.date()
            label = "Today"

        period_orders = Order.objects.filter(created_at__date__gte=start_date)
        paid_orders = period_orders.filter(payment_status='paid')

        revenue = paid_orders.aggregate(total=Sum('total_amount'))['total'] or 0
        aov = paid_orders.aggregate(avg=Avg('total_amount'))['avg'] or 0
        order_count = period_orders.count()
        completed = period_orders.filter(status='completed').count()
        pending = period_orders.filter(status='pending').count()
        preparing = period_orders.filter(status='preparing').count()
        cancelled = period_orders.filter(status='cancelled').count()

        # Payment methods breakdown
        momo_rev = paid_orders.filter(payment_method__icontains='momo').aggregate(t=Sum('total_amount'))['t'] or 0
        cash_rev = paid_orders.filter(payment_method__icontains='cash').aggregate(t=Sum('total_amount'))['t'] or 0
        card_rev = paid_orders.filter(payment_method__icontains='card').aggregate(t=Sum('total_amount'))['t'] or 0

        # Top item
        top = (
            OrderItem.objects.filter(order__created_at__date__gte=start_date)
            .values('name')
            .annotate(cnt=Count('id'), qty=Sum('quantity'))
            .order_by('-qty')
            .first()
        )
        return {
            'period': label,
            'order_count': order_count,
            'completed': completed,
            'pending': pending,
            'preparing': preparing,
            'cancelled': cancelled,
            'revenue': float(revenue),
            'average_order_value': round(float(aov), 2),
            'payments': {
                'momo': float(momo_rev),
                'cash': float(cash_rev),
                'card': float(card_rev),
            },
            'top_item': f"{top['name']} ({top['qty']} sold)" if top else 'N/A',
        }


def add_menu_item_tool(
    tenant_slug: str,
    name: str,
    price: float,
    category_name: str = "General",
    description: str = "",
    is_available: bool = True,
) -> dict:
    """Owner: Add a new menu item, auto-creating the category if it doesn't exist."""
    with _with_tenant(tenant_slug):
        from menu.models import Category, MenuItem
        from tenants.models import Tenant

        tenant = Tenant.objects.get(slug=tenant_slug)
        cat_name = (category_name or "General").strip().title()

        # Find or auto-create category
        category = Category.objects.filter(name__iexact=cat_name).first()
        if not category:
            max_priority = Category.objects.all().order_by('-priority').values_list('priority', flat=True).first() or 0
            category = Category.objects.create(
                tenant=tenant,
                name=cat_name,
                priority=max_priority + 1,
            )
            cat_created = True
        else:
            cat_created = False

        # Create menu item
        item = MenuItem.objects.create(
            tenant=tenant,
            category=category,
            name=name.strip(),
            price=price,
            description=description.strip(),
            isAvailable=is_available,
        )

        # Trigger Pusher sync
        try:
            from orders.pusher_client import get_pusher_client
            client = get_pusher_client()
            if client:
                client.trigger(f'menu-{tenant_slug}', 'menu-updated', {'action': 'item-created', 'item_id': item.id})
        except Exception:
            pass

        return {
            'success': True,
            'item_id': item.id,
            'name': item.name,
            'price': float(item.price),
            'category': category.name,
            'category_auto_created': cat_created,
            'is_available': item.isAvailable,
        }


def update_menu_item_tool(
    tenant_slug: str,
    item_name: str,
    new_price: float = None,
    new_name: str = None,
    description: str = None,
    category_name: str = None,
    available: bool = None,
) -> dict:
    """Owner: update price, name, description, category, or availability of a menu item."""
    with _with_tenant(tenant_slug):
        from menu.models import MenuItem, Category
        from tenants.models import Tenant

        item = MenuItem.objects.filter(name__icontains=item_name.strip()).first()
        if not item:
            return {'success': False, 'error': f'No menu item matching "{item_name}" found.'}

        updated_fields = []
        if new_price is not None:
            item.price = new_price
            updated_fields.append(f'price = GHS {new_price:.2f}')

        if new_name:
            item.name = new_name.strip()
            updated_fields.append(f'name = "{item.name}"')

        if description is not None:
            item.description = description.strip()
            updated_fields.append('description updated')

        if available is not None:
            item.isAvailable = available
            updated_fields.append('available' if available else 'paused (86ed)')

        if category_name:
            tenant = Tenant.objects.get(slug=tenant_slug)
            cat_name = category_name.strip().title()
            category = Category.objects.filter(name__iexact=cat_name).first()
            if not category:
                max_priority = Category.objects.all().order_by('-priority').values_list('priority', flat=True).first() or 0
                category = Category.objects.create(
                    tenant=tenant,
                    name=cat_name,
                    priority=max_priority + 1,
                )
            item.category = category
            updated_fields.append(f'category = "{category.name}"')

        item.save()

        # Trigger Pusher sync
        try:
            from orders.pusher_client import get_pusher_client
            client = get_pusher_client()
            if client:
                client.trigger(f'menu-{tenant_slug}', 'menu-updated', {'action': 'item-updated', 'item_id': item.id})
        except Exception:
            pass

        return {
            'success': True,
            'name': item.name,
            'price': float(item.price),
            'category': item.category.name,
            'is_available': item.isAvailable,
            'changes': updated_fields,
        }


def delete_menu_item_tool(tenant_slug: str, item_name: str) -> dict:
    """Owner: delete a menu item by name."""
    with _with_tenant(tenant_slug):
        from menu.models import MenuItem

        item = MenuItem.objects.filter(name__icontains=item_name.strip()).first()
        if not item:
            return {'success': False, 'error': f'No menu item matching "{item_name}" found.'}

        deleted_name = item.name
        item.delete()

        # Trigger Pusher sync
        try:
            from orders.pusher_client import get_pusher_client
            client = get_pusher_client()
            if client:
                client.trigger(f'menu-{tenant_slug}', 'menu-updated', {'action': 'item-deleted'})
        except Exception:
            pass

        return {
            'success': True,
            'deleted_item': deleted_name,
        }


def update_order_status_tool(tenant_slug: str, order_number: str, new_status: str) -> dict:
    """Owner: change the status of an order."""
    valid = ['pending', 'preparing', 'ready', 'completed', 'cancelled']
    if new_status not in valid:
        return {'success': False, 'error': f'Invalid status. Choose from: {", ".join(valid)}'}
    with _with_tenant(tenant_slug):
        from orders.models import Order
        from orders.pusher_client import get_pusher_client
        from orders.serializers import OrderSerializer
        try:
            order = Order.objects.get(order_number=order_number)
            order.status = new_status
            order.save(update_fields=['status'])
            # Fire pusher
            try:
                client = get_pusher_client()
                if client:
                    data = OrderSerializer(order).data
                    client.trigger(f'orders-{tenant_slug}', 'order-updated', data)
            except Exception:
                pass
            return {'success': True, 'order_number': order_number, 'new_status': new_status}
        except Order.DoesNotExist:
            return {'success': False, 'error': f'Order {order_number} not found'}


def toggle_item_availability_tool(tenant_slug: str, item_name: str, available: bool) -> dict:
    """Owner: pause or resume a menu item by name."""
    with _with_tenant(tenant_slug):
        from menu.models import MenuItem
        items = MenuItem.objects.filter(name__icontains=item_name)
        if not items.exists():
            return {'success': False, 'error': f'No item matching "{item_name}" found'}
        updated = []
        for item in items:
            item.isAvailable = available
            item.save(update_fields=['isAvailable'])
            updated.append(item.name)

        # Trigger Pusher sync
        try:
            from orders.pusher_client import get_pusher_client
            client = get_pusher_client()
            if client:
                client.trigger(f'menu-{tenant_slug}', 'menu-updated', {'action': 'availability-toggled'})
        except Exception:
            pass

        return {
            'success': True,
            'updated_items': updated,
            'availability': 'available' if available else 'paused (86ed)',
        }

