from rest_framework import serializers
from .models import Tenant, Domain

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = [
            'id', 'schema_name', 'name', 'description', 'created_on',
            'is_active', 'subscription_status', 'trial_end_date',
            'contact_email', 'contact_phone', 'business_type',
            'currency', 'timezone', 'clerk_organization_id'
        ]
        read_only_fields = ['id', 'created_on', 'schema_name']

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ['domain', 'tenant', 'is_primary']
