from django.contrib import admin
from .models import Plan, Subscription, Payment, ExchangeRateSettings

@admin.register(ExchangeRateSettings)
class ExchangeRateSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        # Only allow one instance
        return not ExchangeRateSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Don't allow deletion
        return False
    
    fieldsets = (
        ('API Settings', {
            'fields': ('use_api', 'api_key'),
            'description': 'Configure live exchange rate API'
        }),
        ('Fallback Rates', {
            'fields': ('usd_to_ghs', 'usd_to_ngn'),
            'description': 'Manual rates used when API is disabled or unavailable'
        }),
        ('Last Updated', {
            'fields': ('updated_at',),
            'classes': ['collapse']
        }),
    )
    
    readonly_fields = ['updated_at']

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'plan_type', 'price_usd', 'is_active', 'is_featured']
    list_filter = ['plan_type', 'is_active', 'is_featured']
    search_fields = ['name', 'description']
    ordering = ['sort_order']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'plan_type', 'description')
        }),
        ('Pricing', {
            'fields': ('price_usd',),
            'description': 'Base price in USD. Other currencies are auto-converted.'
        }),
        ('TableTap Products', {
            'fields': ('includes_digital_menu', 'includes_pos', 'includes_cms')
        }),
        ('Features & Limits', {
            'fields': (
                'max_menu_items', 'has_basic_analytics', 'has_advanced_analytics',
                'has_multi_location', 'has_custom_integrations', 'support_level'
            )
        }),
        ('Admin Settings', {
            'fields': ('is_active', 'is_featured', 'sort_order')
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return ['created_at', 'updated_at']
        return []

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'plan', 'status', 'current_period_start', 'current_period_end', 'created_at']
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['tenant__name', 'tenant__contact_email']
    readonly_fields = ['created_at', 'updated_at', 'paystack_subscription_code', 'paystack_customer_code']
    
    fieldsets = (
        ('Subscription Details', {
            'fields': ('tenant', 'plan', 'status')
        }),
        ('Billing Period', {
            'fields': ('current_period_start', 'current_period_end', 'trial_end')
        }),
        ('Cancellation', {
            'fields': ('cancel_at_period_end', 'cancelled_at')
        }),
        ('Paystack Integration', {
            'fields': ('paystack_subscription_code', 'paystack_customer_code'),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['subscription', 'amount', 'currency', 'status', 'paid_at', 'created_at']
    list_filter = ['status', 'currency', 'created_at']
    search_fields = ['subscription__tenant__name', 'paystack_reference']
    readonly_fields = ['created_at', 'updated_at', 'paystack_reference', 'paystack_access_code']
    
    fieldsets = (
        ('Payment Details', {
            'fields': ('subscription', 'amount', 'currency', 'status')
        }),
        ('Payment Info', {
            'fields': ('payment_method', 'paid_at')
        }),
        ('Paystack Integration', {
            'fields': ('paystack_reference', 'paystack_access_code'),
            'classes': ['collapse']
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ['collapse']
        }),
    )
