from rest_framework import serializers
from .models import Plan, Subscription, Payment

class PlanSerializer(serializers.ModelSerializer):
    features_list = serializers.ReadOnlyField()
    price_ghs = serializers.SerializerMethodField()
    price_ngn = serializers.SerializerMethodField()
    
    class Meta:
        model = Plan
        fields = [
            'id', 'name', 'plan_type', 'description', 
            'price_usd', 'price_ghs', 'price_ngn',
            'includes_digital_menu', 'includes_pos', 'includes_cms',
            'allows_menu_images', 'max_menu_items', 'has_basic_analytics', 'has_advanced_analytics',
            'has_multi_location', 'has_custom_integrations', 'support_level',
            'is_featured', 'features_list'
        ]
    
    def get_price_ghs(self, obj):
        return obj.get_price_in_currency('GHS')
    
    def get_price_ngn(self, obj):
        return obj.get_price_in_currency('NGN')

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    plan_id = serializers.IntegerField(write_only=True)
    is_active = serializers.ReadOnlyField()
    days_until_renewal = serializers.ReadOnlyField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan', 'plan_id', 'status', 'is_active',
            'current_period_start', 'current_period_end', 'trial_end',
            'cancel_at_period_end', 'cancelled_at', 'days_until_renewal',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            'id', 'amount', 'currency', 'status', 'payment_method',
            'paid_at', 'created_at'
        ]
        read_only_fields = ['created_at']

class CreateSubscriptionSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    currency = serializers.ChoiceField(choices=['USD', 'GHS', 'NGN'], default='USD')
    
    def validate_plan_id(self, value):
        try:
            plan = Plan.objects.get(id=value, is_active=True)
            return value
        except Plan.DoesNotExist:
            raise serializers.ValidationError("Invalid or inactive plan selected.")

class PaystackPaymentSerializer(serializers.Serializer):
    subscription_id = serializers.IntegerField()
    currency = serializers.ChoiceField(choices=['USD', 'GHS', 'NGN'], default='USD')
    callback_url = serializers.URLField(required=False)
