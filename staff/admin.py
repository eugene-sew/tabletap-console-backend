from django.contrib import admin
from .models import Role, StaffMember

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description']
    search_fields = ['name']

@admin.register(StaffMember)
class StaffMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'is_active', 'hired_date']
    list_filter = ['role', 'is_active', 'hired_date']
    search_fields = ['user__username', 'user__email', 'employee_id']
