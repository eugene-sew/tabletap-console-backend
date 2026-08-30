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
    """Owner: get all active (pending, preparing, ready) orders with detailed item breakdowns."""
    with _with_tenant(tenant_slug):
        from orders.models import Order
        from django.utils import timezone

        active = Order.objects.filter(
            status__in=['pending', 'preparing', 'ready']
        ).order_by('-created_at')[:25]

        pending_orders = []
        preparing_orders = []
        ready_orders = []
        all_orders = []

        now = timezone.now()

        for o in active:
            items = [f"{i.quantity}x {i.name}" for i in o.items.all()]
            mins = int((now - o.created_at).total_seconds() / 60)
            order_info = {
                'order_number': o.order_number,
                'status': o.status,
                'customer_name': o.customer_name or 'Guest',
                'customer_phone': o.customer_phone or '',
                'order_type': o.order_type,
                'total': float(o.total_amount),
                'items': items,
                'minutes_ago': mins,
                'created_time': o.created_at.strftime('%H:%M'),
            }
            all_orders.append(order_info)
            if o.status == 'pending':
                pending_orders.append(order_info)
            elif o.status == 'preparing':
                preparing_orders.append(order_info)
            elif o.status == 'ready':
                ready_orders.append(order_info)

        return {
            'total_active_count': len(all_orders),
            'new_unaccepted_pending_count': len(pending_orders),
            'preparing_in_kitchen_count': len(preparing_orders),
            'ready_for_pickup_count': len(ready_orders),
            'pending_orders': pending_orders,
            'preparing_orders': preparing_orders,
            'ready_orders': ready_orders,
            'orders': all_orders,
        }


def get_metrics_summary(
    tenant_slug: str,
    period: str = 'today',
    start_date: str = None,
    end_date: str = None,
) -> dict:
    """Owner: order count, revenue, breakdown, AOV, and top items across historical time ranges."""
    with _with_tenant(tenant_slug):
        from orders.models import Order, OrderItem
        from django.utils import timezone
        from django.db.models import Sum, Count, Avg
        from datetime import datetime, timedelta

        now = timezone.now()
        today = now.date()
        s_date = None
        e_date = None
        label = "Custom Range"

        if start_date:
            try:
                s_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                if end_date:
                    e_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                else:
                    e_date = s_date
                label = f"{s_date} to {e_date}"
            except ValueError:
                pass

        if not s_date:
            norm_period = (period or 'today').lower().replace(' ', '_').replace('-', '_')
            if norm_period in ('today', 'day'):
                s_date = today
                e_date = today
                label = f"Today ({today})"
            elif norm_period == 'yesterday':
                s_date = today - timedelta(days=1)
                e_date = s_date
                label = f"Yesterday ({s_date})"
            elif norm_period in ('this_week', 'week'):
                # Monday of current week
                s_date = today - timedelta(days=today.weekday())
                e_date = today
                label = f"This Week (Since {s_date})"
            elif norm_period in ('last_week', 'previous_week'):
                monday_last_week = today - timedelta(days=today.weekday() + 7)
                sunday_last_week = monday_last_week + timedelta(days=6)
                s_date = monday_last_week
                e_date = sunday_last_week
                label = f"Last Week ({monday_last_week} to {sunday_last_week})"
            elif norm_period in ('this_month', 'month'):
                s_date = today.replace(day=1)
                e_date = today
                label = f"This Month ({s_date.strftime('%B %Y')})"
            elif norm_period in ('last_month', 'previous_month'):
                first_this_month = today.replace(day=1)
                last_prev_month = first_this_month - timedelta(days=1)
                s_date = last_prev_month.replace(day=1)
                e_date = last_prev_month
                label = f"Last Month ({s_date.strftime('%B %Y')})"
            elif norm_period in ('this_year', 'year'):
                s_date = today.replace(month=1, day=1)
                e_date = today
                label = f"This Year ({today.year})"
            elif norm_period in ('all_time', 'all', 'total'):
                s_date = None
                e_date = None
                label = "All Time"
            else:
                s_date = today
                e_date = today
                label = f"Today ({today})"

        # Query orders in date range
        orders_qs = Order.objects.all()
        if s_date:
            orders_qs = orders_qs.filter(created_at__date__gte=s_date)
        if e_date:
            orders_qs = orders_qs.filter(created_at__date__lte=e_date)

        paid_orders = orders_qs.filter(payment_status='paid')

        revenue = paid_orders.aggregate(total=Sum('total_amount'))['total'] or 0
        aov = paid_orders.aggregate(avg=Avg('total_amount'))['avg'] or 0
        order_count = orders_qs.count()
        completed = orders_qs.filter(status='completed').count()
        pending = orders_qs.filter(status='pending').count()
        preparing = orders_qs.filter(status='preparing').count()
        cancelled = orders_qs.filter(status='cancelled').count()

        # Payment methods breakdown
        momo_rev = paid_orders.filter(payment_method__icontains='momo').aggregate(t=Sum('total_amount'))['t'] or 0
        cash_rev = paid_orders.filter(payment_method__icontains='cash').aggregate(t=Sum('total_amount'))['t'] or 0
        card_rev = paid_orders.filter(payment_method__icontains='card').aggregate(t=Sum('total_amount'))['t'] or 0

        # Top 3 items in this time window
        item_qs = OrderItem.objects.filter(order__in=orders_qs)
        top_items = (
            item_qs.values('name')
            .annotate(cnt=Count('id'), qty=Sum('quantity'), total_sales=Sum('price'))
            .order_by('-qty')[:3]
        )

        top_formatted = [
            f"{t['name']} ({t['qty']} sold • GHS {float(t['total_sales'] or 0):.2f})"
            for t in top_items
        ]

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
            'top_items': top_formatted,
            'top_item': top_formatted[0] if top_formatted else 'N/A',
        }


def search_historical_orders(
    tenant_slug: str,
    query: str = None,
    date: str = None,
    status: str = None,
    customer_phone: str = None,
    limit: int = 10,
) -> dict:
    """Owner: search and inspect past orders by date, customer, status, or search term."""
    with _with_tenant(tenant_slug):
        from orders.models import Order
        from django.db.models import Q
        from datetime import datetime

        orders_qs = Order.objects.all().order_by('-created_at')

        if date:
            try:
                d = datetime.strptime(date, '%Y-%m-%d').date()
                orders_qs = orders_qs.filter(created_at__date=d)
            except ValueError:
                pass

        if status:
            orders_qs = orders_qs.filter(status__iexact=status.strip())

        if customer_phone:
            clean_p = ''.join(c for c in customer_phone if c.isdigit())
            orders_qs = orders_qs.filter(customer_phone__icontains=clean_p)

        if query:
            q = query.strip()
            orders_qs = orders_qs.filter(
                Q(order_number__icontains=q) |
                Q(customer_name__icontains=q) |
                Q(items__name__icontains=q)
            ).distinct()

        results = []
        for o in orders_qs[:max(1, min(limit, 25))]:
            items = [f"{i.quantity}x {i.name}" for i in o.items.all()]
            results.append({
                'order_number': o.order_number,
                'created_at': o.created_at.strftime('%Y-%m-%d %H:%M'),
                'customer_name': o.customer_name or 'Guest',
                'customer_phone': o.customer_phone or 'N/A',
                'status': o.status,
                'payment_status': o.payment_status,
                'payment_method': o.payment_method or 'cash',
                'total_amount': float(o.total_amount),
                'items': items,
            })

        return {
            'total_matches': orders_qs.count(),
            'returned_count': len(results),
            'orders': results,
        }


def get_top_selling_items(tenant_slug: str, period: str = 'this_month', limit: int = 5) -> dict:
    """Owner: Get top-selling dishes leaderboard with quantities and revenue."""
    with _with_tenant(tenant_slug):
        from orders.models import OrderItem, Order
        from django.utils import timezone
        from django.db.models import Sum, Count
        from datetime import timedelta

        now = timezone.now()
        today = now.date()
        norm_period = (period or 'this_month').lower().replace(' ', '_')

        if norm_period == 'today':
            s_date = today
        elif norm_period == 'yesterday':
            s_date = today - timedelta(days=1)
        elif norm_period == 'this_week':
            s_date = today - timedelta(days=today.weekday())
        elif norm_period == 'last_month':
            first_this_month = today.replace(day=1)
            last_prev_month = first_this_month - timedelta(days=1)
            s_date = last_prev_month.replace(day=1)
        elif norm_period == 'all_time':
            s_date = None
        else:
            s_date = today.replace(day=1)

        qs = OrderItem.objects.all()
        if s_date:
            qs = qs.filter(order__created_at__date__gte=s_date)

        leaderboard = (
            qs.values('name')
            .annotate(
                total_qty=Sum('quantity'),
                total_revenue=Sum('price'),
                orders_count=Count('order_id', distinct=True),
            )
            .order_by('-total_qty')[:limit]
        )

        return {
            'period': period,
            'leaderboard': [
                {
                    'rank': idx + 1,
                    'name': item['name'],
                    'quantity_sold': item['total_qty'],
                    'revenue': float(item['total_revenue'] or 0),
                    'orders_count': item['orders_count'],
                }
                for idx, item in enumerate(leaderboard)
            ],
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

