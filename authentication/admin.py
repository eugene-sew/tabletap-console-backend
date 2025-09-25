from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_verified', 'is_staff']
    list_filter = ['is_verified', 'is_staff', 'is_superuser']
    search_fields = ['username', 'email', 'clerk_user_id']
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Clerk Integration', {'fields': ('clerk_user_id', 'phone_number', 'avatar_url', 'is_verified')}),
    )
