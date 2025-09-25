from django.contrib import admin
from .models import Tenant, Domain

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'schema_name', 'subscription_status', 'created_on', 'is_active']
    list_filter = ['subscription_status', 'is_active', 'created_on']
    search_fields = ['name', 'contact_email', 'schema_name']

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'tenant', 'is_primary']
    list_filter = ['is_primary']
