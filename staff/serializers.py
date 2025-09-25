from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Role, StaffMember

User = get_user_model()

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'permissions']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class StaffMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    role_id = serializers.IntegerField(write_only=True)
    user_id = serializers.IntegerField(write_only=True)
    
    class Meta:
        model = StaffMember
        fields = [
            'id', 'user', 'role', 'user_id', 'role_id', 'is_active',
            'hired_date', 'employee_id', 'department', 'salary'
        ]
