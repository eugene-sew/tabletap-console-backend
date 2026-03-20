from rest_framework import serializers
from .models import Tenant, Domain

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            'id', 'schema_name', 'name', 'slug', 'description', 'created_on',
            'is_active', 'subscription_status', 'trial_end_date',
            'contact_email', 'contact_phone', 'business_type',
            'currency', 'timezone', 'clerk_organization_id',
            'address', 'phone', 'website', 'logo', 'settings'
        ]
        read_only_fields = ['id', 'created_on', 'schema_name', 'slug']

class RestaurantSerializer(serializers.ModelSerializer):
    """Serializer for restaurant-specific frontend needs"""
    email = serializers.CharField(source='contact_email')
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'description', 'address', 'phone', 
            'email', 'website', 'logo', 'currency', 'settings'
        ]
        read_only_fields = ['id']

    def validate_slug(self, value):
        """Ensure slug is URL-safe and unique"""
        import re
        if not re.match(r'^[a-z0-9-]+$', value):
            raise serializers.ValidationError("Slug must contain only lowercase letters, numbers, and hyphens.")
        
        # Check uniqueness, excluding the current instance
        instance = getattr(self, 'instance', None)
        if Tenant.objects.filter(slug=value).exclude(id=getattr(instance, 'id', None)).exists():
            raise serializers.ValidationError("This slug is already taken.")
            
        return value
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ensure settings has default structure
        if not data.get('settings'):
            data['settings'] = instance.get_default_settings()
        return data

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['domain', 'tenant', 'is_primary']
