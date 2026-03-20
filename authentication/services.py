import uuid
from datetime import timedelta
from django.utils import timezone
from django_tenants.utils import tenant_context
from tenants.models import Tenant, Domain
from django.contrib.auth import get_user_model

User = get_user_model()

ROLE_DEFINITIONS = [
    {
        'name': 'Owner',
        'description': 'Full administrative access to everything',
        'permissions': {'*': True},
    },
    {
        'name': 'Manager',
        'description': 'Full access except Subscriptions, Settings, and Support',
        'permissions': {
            'dashboard': True,
            'menu': True,
            'orders': True,
            'tables': True,
            'team': True,
            'feedback': True,
        },
    },
    {
        'name': 'Waiter',
        'description': 'Access to POS and Order processing only',
        'permissions': {
            'orders': True,
        },
    },
]


def provision_tenant_for_user(user, restaurant_name=None):
    """
    Ensure a user has a tenant and primary domain.
    Returns (tenant, created)
    """
    first_name = user.first_name
    last_name = user.last_name
    email = user.email
    clerk_user_id = user.clerk_user_id

    if not clerk_user_id:
        return None, False

    if not restaurant_name:
        if first_name or last_name:
            restaurant_name = f"{first_name} {last_name}".strip()
        elif email:
            restaurant_name = f"{email.split('@')[0]}'s Restaurant"
        else:
            restaurant_name = f"Restaurant {clerk_user_id[-4:]}"

    tenant, tenant_created = Tenant.objects.get_or_create(
        clerk_organization_id=clerk_user_id,
        defaults={
            'schema_name': f"tenant_{uuid.uuid4().hex[:8]}",
            'name': restaurant_name,
            'contact_email': email or f"{clerk_user_id}@tabletap.space",
            'subscription_status': 'trial',
            'trial_end_date': timezone.now() + timedelta(days=7),
        }
    )

    if tenant_created:
        Domain.objects.create(
            tenant=tenant,
            domain=f"{tenant.slug}.tabletap.space",
            is_primary=True
        )

    with tenant_context(tenant):
        from staff.models import Role, StaffMember

        owner_role = None
        for role_def in ROLE_DEFINITIONS:
            role, _ = Role.objects.get_or_create(
                name=role_def['name'],
                defaults={
                    'description': role_def['description'],
                    'permissions': role_def['permissions'],
                }
            )
            if role_def['name'] == 'Owner':
                owner_role = role

        StaffMember.objects.get_or_create(
            user=user,
            tenant=tenant,
            defaults={'role': owner_role, 'is_active': True}
        )

    return tenant, tenant_created
