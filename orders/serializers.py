from rest_framework import serializers
from .models import Order, OrderItem, OrderReview

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'menu_item_id', 'name', 'quantity', 'price', 'notes']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer_name', 'table_number', 'order_type', 
            'delivery_fee', 'tax_amount', 'customer_phone', 'delivery_address', 
            'delivery_notes', 'status', 'total_amount', 'payment_status', 
            'payment_method', 'processed_by_name', 'items', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        # Get tenant from context
        tenant = self.context.get('request').tenant if self.context.get('request') else None
        order = Order.objects.create(tenant=tenant, **validated_data)
        for item_data in items_data:
            OrderItem.objects.create(order=order, **item_data)
        return order

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderReview
        fields = ['id', 'order', 'rating', 'comment', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        # Get tenant from order if not provided in context
        order = validated_data.get('order')
        tenant = order.tenant if order else None
        return OrderReview.objects.create(tenant=tenant, **validated_data)
