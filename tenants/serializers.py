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
    remaining_slug_changes = serializers.SerializerMethodField()
    
    class Meta:
        model = Tenant
        fields = [
            'id', 'name', 'slug', 'slug_change_count', 'remaining_slug_changes',
            'description', 'address', 'phone', 
            'email', 'website', 'logo', 'currency', 'settings'
        ]
        read_only_fields = ['id', 'slug_change_count', 'remaining_slug_changes']

    def get_remaining_slug_changes(self, obj) -> int:
        return max(0, 2 - (obj.slug_change_count or 0))

    def validate_slug(self, value):
        """Ensure slug is URL-safe, unique, and respect the 2-change limit"""
        import re
        clean_slug = (value or '').strip().lower()
        if not re.match(r'^[a-z0-9-]+$', clean_slug):
            raise serializers.ValidationError("Slug must contain only lowercase letters, numbers, and hyphens.")
        
        # Check uniqueness, excluding the current instance
        instance = getattr(self, 'instance', None)
        if Tenant.objects.filter(slug=clean_slug).exclude(id=getattr(instance, 'id', None)).exists():
            raise serializers.ValidationError("This slug is already taken.")

        # Check the 2-change limit if the slug is being modified
        if instance and instance.slug and instance.slug != clean_slug:
            if (instance.slug_change_count or 0) >= 2:
                raise serializers.ValidationError(
                    "You have reached the maximum limit of 2 URL/slug changes. Please contact support if you need further assistance."
                )
            
        return clean_slug

    def update(self, instance, validated_data):
        new_slug = validated_data.get('slug')
        old_slug = instance.slug

        if new_slug and old_slug and new_slug != old_slug:
            instance.slug_change_count = (instance.slug_change_count or 0) + 1
            # Sync with Hostinger DNS API
            from .hostinger_client import hostinger_dns
            try:
                hostinger_dns.sync_tenant_subdomain(new_slug, old_slug)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"[Hostinger DNS] Sync error on update: {e}")

        return super().update(instance, validated_data)
    
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
