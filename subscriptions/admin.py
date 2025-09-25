from django.contrib import admin
from .models import Plan, Subscription, Payment

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price_usd', 'includes_pos', 'includes_menu', 'includes_cms', 'is_active']
    list_filter = ['includes_pos', 'includes_menu', 'includes_cms', 'is_active']

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'status', 'current_period_start', 'current_period_end']
    list_filter = ['status', 'plan']
    search_fields = ['tenant__name']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['paystack_reference']
