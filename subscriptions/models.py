from django.db import models
from tenants.models import Tenant

class Plan(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price_ghs = models.DecimalField(max_digits=10, decimal_places=2)
    price_ngn = models.DecimalField(max_digits=10, decimal_places=2)
    price_usd = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Features included
    includes_pos = models.BooleanField(default=False)
    includes_menu = models.BooleanField(default=False)
    includes_cms = models.BooleanField(default=False)
    
    # Limits
    max_staff = models.IntegerField(default=5)
    max_tables = models.IntegerField(default=10)
    max_menu_items = models.IntegerField(default=100)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    def get_price(self, currency='USD'):
        currency_map = {
            'GHS': self.price_ghs,
            'NGN': self.price_ngn,
            'USD': self.price_usd,
        }
        return currency_map.get(currency, self.price_usd)

class Subscription(models.Model):
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('cancelled', 'Cancelled'),
            ('past_due', 'Past Due'),
            ('trialing', 'Trialing'),
        ],
        default='trialing'
    )
    
    # Paystack integration
    paystack_subscription_code = models.CharField(max_length=100, blank=True)
    paystack_customer_code = models.CharField(max_length=100, blank=True)
    
    current_period_start = models.DateTimeField()
    current_period_end = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name}"

class Payment(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('success', 'Success'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    
    # Paystack reference
    paystack_reference = models.CharField(max_length=100, unique=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.subscription.tenant.name} - {self.amount} {self.currency}"
