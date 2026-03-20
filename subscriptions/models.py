from django.db import models
from tenants.models import Tenant
import requests

class ExchangeRateSettings(models.Model):
    """Admin-configurable exchange rates as fallback"""
    usd_to_ghs = models.DecimalField(max_digits=10, decimal_places=2, default=12.68)
    usd_to_ngn = models.DecimalField(max_digits=10, decimal_places=2, default=1484.90)
    
    use_api = models.BooleanField(default=True, help_text="Use live API rates when available")
    api_key = models.CharField(max_length=100, default='28f53f97e95df6d8f7ab87ec', help_text="ExchangeRate-API key")
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Exchange Rate Settings"
        verbose_name_plural = "Exchange Rate Settings"
    
    def __str__(self):
        return f"Exchange Rates (Updated: {self.updated_at.strftime('%Y-%m-%d %H:%M')})"
    
    @classmethod
    def get_settings(cls):
        """Get or create exchange rate settings"""
        settings, created = cls.objects.get_or_create(id=1)
        return settings

class Plan(models.Model):
    PLAN_TYPES = [
        ('free', 'Free'),
        ('starter', 'Starter'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    description = models.TextField()
    
    # Base price in USD
    price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Features included
    includes_digital_menu = models.BooleanField(default=False)
    includes_pos = models.BooleanField(default=False)
    includes_cms = models.BooleanField(default=False)
    
    # Menu features
    allows_menu_images = models.BooleanField(default=False)
    
    # Limits and features
    max_menu_items = models.IntegerField(default=50)
    has_basic_analytics = models.BooleanField(default=False)
    has_advanced_analytics = models.BooleanField(default=False)
    has_multi_location = models.BooleanField(default=False)
    has_custom_integrations = models.BooleanField(default=False)
    
    # Support level
    support_level = models.CharField(
        max_length=20,
        choices=[
            ('email', 'Email Support'),
            ('priority', 'Priority Support'),
            ('phone_24_7', '24/7 Phone Support'),
        ],
        default='email'
    )
    
    # Admin settings
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['sort_order']
    
    def __str__(self):
        return f"{self.name} - ${self.price_usd}/month"
    
    def get_price_in_currency(self, currency='USD'):
        """Convert USD price to other currencies using exchange rate API"""
        if currency == 'USD':
            return self.price_usd
        
        settings = ExchangeRateSettings.get_settings()
        
        if settings.use_api:
            try:
                # Using exchangerate-api.com with API key
                response = requests.get(
                    f'https://v6.exchangerate-api.com/v6/{settings.api_key}/latest/USD',
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    if data['result'] == 'success':
                        rates = data['conversion_rates']
                        if currency in rates:
                            converted_price = float(self.price_usd) * rates[currency]
                            return round(converted_price, 2)
            except:
                pass
        
        # Use admin-configured fallback rates
        fallback_rates = {
            'GHS': float(settings.usd_to_ghs),
            'NGN': float(settings.usd_to_ngn),
        }
        
        if currency in fallback_rates:
            converted_price = float(self.price_usd) * fallback_rates[currency]
            return round(converted_price, 2)
        
        return self.price_usd
    
    @property
    def features_list(self):
        """Return list of included features"""
        features = []
        
        if self.includes_digital_menu:
            if self.max_menu_items == -1:
                features.append("Digital Menu (Unlimited items)")
            else:
                features.append(f"Digital Menu (Up to {self.max_menu_items} items)")
        
        if self.includes_pos:
            features.append("POS System")
        
        if self.includes_cms:
            features.append("Content Management System")
        
        if self.has_basic_analytics:
            features.append("Basic Analytics")
        
        if self.has_advanced_analytics:
            features.append("Advanced Analytics")
        
        if self.has_multi_location:
            features.append("Multi-location Support")
        
        if self.has_custom_integrations:
            features.append("Custom Integrations")
        
        # Support level
        support_map = {
            'email': 'Email Support',
            'priority': 'Priority Support',
            'phone_24_7': '24/7 Phone Support'
        }
        features.append(support_map.get(self.support_level, 'Email Support'))
        
        return features

class Subscription(models.Model):
    STATUS_CHOICES = [
        ('trialing', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('unpaid', 'Unpaid'),
    ]
    
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    
    # Paystack integration
    paystack_subscription_code = models.CharField(max_length=100, blank=True)
    paystack_customer_code = models.CharField(max_length=100, blank=True)
    
    # Billing periods
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    trial_end = models.DateTimeField(null=True, blank=True)
    
    # Cancellation
    cancel_at_period_end = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name} ({self.status})"
    
    @property
    def is_active(self):
        return self.status in ['trialing', 'active']
    
    @property
    def days_until_renewal(self):
        from django.utils import timezone
        if self.current_period_end:
            delta = self.current_period_end - timezone.now()
            return max(0, delta.days)
        return 0

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='GHS')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Paystack integration
    paystack_reference = models.CharField(max_length=100, unique=True)
    paystack_access_code = models.CharField(max_length=100, blank=True)
    
    # Payment details
    payment_method = models.CharField(max_length=50, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.subscription.tenant.name} - {self.amount} {self.currency} ({self.status})"
