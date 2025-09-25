from django.contrib import admin
from .models import Tool, ToolAccess, SSOToken

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ['name', 'url', 'is_active']
    list_filter = ['is_active']

@admin.register(ToolAccess)
class ToolAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'tool', 'is_granted', 'granted_at']
    list_filter = ['tool', 'is_granted']
    search_fields = ['user__username']

@admin.register(SSOToken)
class SSOTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'tool', 'expires_at', 'is_used', 'created_at']
    list_filter = ['tool', 'is_used', 'created_at']
    search_fields = ['user__username']
