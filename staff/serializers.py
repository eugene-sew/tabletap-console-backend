from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Role, StaffMember

User = get_user_model()

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'tenant', 'name', 'description', 'permissions']
        read_only_fields = ['tenant']

class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'display_name']

    def get_display_name(self, obj):
        full_name = f"{obj.first_name or ''} {obj.last_name or ''}".strip()
        if full_name:
            return full_name
        if obj.email:
            return obj.email
        return None

class StaffMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    role = RoleSerializer(read_only=True)
    role_id = serializers.IntegerField(write_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)
    first_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    last_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    class Meta:
        model = StaffMember
        fields = [
            'id', 'tenant', 'user', 'role', 'user_id', 'role_id', 'email', 
            'first_name', 'last_name', 'is_active',
            'hired_date', 'employee_id', 'department', 'salary'
        ]
        read_only_fields = ['tenant']

    def create(self, validated_data):
        validated_data.pop('email', None)
        validated_data.pop('first_name', None)
        validated_data.pop('last_name', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        first_name = validated_data.pop('first_name', None)
        last_name = validated_data.pop('last_name', None)
        validated_data.pop('email', None)

        if first_name is not None or last_name is not None:
            user = instance.user
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            user.save(update_fields=['first_name', 'last_name'])

        return super().update(instance, validated_data)
