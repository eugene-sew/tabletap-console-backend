from rest_framework import serializers
from .models import Plan, Subscription, Payment

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'description', 'price_ghs', 'price_ngn', 'price_usd',
            'includes_pos', 'includes_menu', 'includes_cms',
            'max_staff', 'max_tables', 'max_menu_items', 'is_active'
        ]

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'tenant', 'plan', 'status', 'paystack_subscription_code',
            'current_period_start', 'current_period_end', 'created_at'
        ]

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'subscription', 'amount', 'currency', 'status',
            'paystack_reference', 'created_at'
        ]
