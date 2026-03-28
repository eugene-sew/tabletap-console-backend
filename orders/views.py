from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q
from .models import Order, OrderReview
from .serializers import OrderSerializer, ReviewSerializer
from .pusher_client import get_pusher_client


def _get_actor_name(request):
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'pk', None):
        return ''
    full = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    return full or getattr(user, 'username', '') or getattr(user, 'email', '') or ''


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = super().get_queryset()

        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)

        order_type_param = self.request.query_params.get('order_type')
        if order_type_param:
            queryset = queryset.filter(order_type=order_type_param)

        start_date = self.request.query_params.get('start_date')
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)

        search_query = self.request.query_params.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(customer_name__icontains=search_query) |
                Q(order_number__icontains=search_query) |
                Q(table_number__icontains=search_query) |
                Q(items__name__icontains=search_query)
            ).distinct()

        ordering = self.request.query_params.get('ordering', '-created_at')
        queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer):
        order = serializer.save()
        self._trigger_pusher('new-order', order)
        try:
            from analytics.audit import log_action
            actor = _get_actor_name(self.request)
            log_action(
                self.request,
                action='order.created',
                entity_type='order',
                entity_id=order.id,
                entity_label=f"Order #{order.order_number}",
                metadata={
                    'order_number': order.order_number,
                    'customer': order.customer_name,
                    'total': float(order.total_amount),
                    'order_type': order.order_type,
                    'source': actor or 'Customer (QR/Online)',
                },
            )
        except Exception:
            pass

    def update(self, request, *args, **kwargs):
        resp = super().update(request, *args, **kwargs)
        if resp.status_code == status.HTTP_200_OK:
            order = self.get_object()
            self._trigger_pusher('order-updated', order)
        return resp

    @action(detail=True, methods=['patch'])
    def status(self, request, pk=None):
        order = self.get_object()
        new_status = request.data.get('status')
        if new_status:
            old_status = order.status
            order.status = new_status
            order.save()
            self._trigger_pusher('order-updated', order)
            try:
                from analytics.audit import log_action
                STATUS_LABELS = {
                    'pending': 'New', 'preparing': 'Accepted',
                    'ready': 'Completed', 'completed': 'Closed', 'cancelled': 'Cancelled',
                }
                log_action(
                    request,
                    action='order.status_changed',
                    entity_type='order',
                    entity_id=order.id,
                    entity_label=f"Order #{order.order_number}",
                    metadata={
                        'order_number': order.order_number,
                        'customer': order.customer_name,
                        'from_status': STATUS_LABELS.get(old_status, old_status),
                        'to_status': STATUS_LABELS.get(new_status, new_status),
                    },
                )
            except Exception:
                pass
            return Response(OrderSerializer(order).data)
        return Response({'error': 'Status not provided'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def pay(self, request, pk=None):
        order = self.get_object()
        payment_method = request.data.get('payment_method', 'cash')
        actor_name = _get_actor_name(request)

        order.payment_status = 'paid'
        order.payment_method = payment_method
        order.processed_by_name = actor_name
        if order.status in ('pending', 'confirmed', 'preparing', 'ready'):
            order.status = 'completed'
        order.save()
        self._trigger_pusher('order-updated', order)

        try:
            from analytics.audit import log_action
            METHOD_LABELS = {
                'cash': 'Cash', 'mobile_money': 'Mobile Money',
                'mobile-money': 'Mobile Money', 'card': 'Card', 'other': 'Other',
            }
            log_action(
                request,
                action='order.payment_confirmed',
                entity_type='order',
                entity_id=order.id,
                entity_label=f"Order #{order.order_number}",
                metadata={
                    'order_number': order.order_number,
                    'customer': order.customer_name,
                    'amount': float(order.total_amount),
                    'payment_method': METHOD_LABELS.get(payment_method, payment_method),
                    'processed_by': actor_name or 'Unknown',
                },
            )
        except Exception:
            pass

        return Response(OrderSerializer(order).data)

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        label = f"Order #{order.order_number}"
        resp = super().destroy(request, *args, **kwargs)
        if resp.status_code == status.HTTP_204_NO_CONTENT:
            try:
                from analytics.audit import log_action
                log_action(
                    request,
                    action='order.cancelled',
                    entity_type='order',
                    entity_id=order.id,
                    entity_label=label,
                    metadata={'order_number': order.order_number, 'customer': order.customer_name},
                )
            except Exception:
                pass
        return resp

    def _trigger_pusher(self, event: str, order: Order):
        try:
            client = get_pusher_client()
            if not client:
                return

            tenant_slug = order.tenant.slug if order.tenant else 'public'
            tenant_channel = f"orders-{tenant_slug}"
            order_channel = f"order-{order.id}"

            data = OrderSerializer(order).data
            data['total_amount'] = float(data['total_amount'] or 0)
            if 'created_at' in data and data['created_at']:
                data['created_at'] = str(data['created_at'])
            for item in data.get('items', []):
                item['price'] = float(item['price'] or 0)

            client.trigger(tenant_channel, event, data)
            client.trigger(order_channel, event, data)
            print(f"[Pusher] Triggered '{event}' on '{tenant_channel}' and '{order_channel}'")
        except Exception as e:
            print(f"[Pusher] Error triggering event: {str(e)}")


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = OrderReview.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return super().get_queryset()
