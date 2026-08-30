from django.contrib import admin
from .models import TenantWhatsAppAccount, BotOwnerSession


@admin.register(TenantWhatsAppAccount)
class TenantWhatsAppAccountAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'phone_number', 'phone_number_id', 'is_active', 'connected_at')
    list_filter = ('is_active',)
    search_fields = ('tenant__name', 'phone_number', 'phone_number_id')
    readonly_fields = ('connected_at', 'updated_at')


@admin.register(BotOwnerSession)
class BotOwnerSessionAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'wa_id', 'is_authenticated', 'last_seen')
    list_filter = ('is_authenticated',)
    search_fields = ('tenant__name', 'wa_id')
    readonly_fields = ('created_at', 'last_seen')
