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

    if not restaurant_name:
        if first_name or last_name:
            restaurant_name = f"{first_name} {last_name}".strip()
        elif email:
            restaurant_name = f"{email.split('@')[0]}'s Restaurant"
        else:
            restaurant_name = f"Restaurant {str(user.pk)[-4:]}"

    tenant, tenant_created = Tenant.objects.get_or_create(
        owner=user,
        defaults={
            'schema_name': f"tenant_{uuid.uuid4().hex[:8]}",
            'name': restaurant_name,
            'contact_email': email or f"user{user.pk}@tabletap.space",
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


def send_email_via_resend(to_email, subject, html_body):
    """Send an email using the Resend API."""
    from django.conf import settings
    import resend

    api_key = getattr(settings, 'RESEND_API_KEY', '')
    from_email = getattr(settings, 'RESEND_FROM_EMAIL', 'onboarding@resend.dev')

    if not api_key:
        print(f"[EMAIL] RESEND_API_KEY not set — skipping email to {to_email}")
        print(f"[EMAIL] Subject: {subject}")
        return False

    try:
        resend.api_key = api_key
        resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
        })
        return True
    except Exception as e:
        print(f"[EMAIL] Failed to send email to {to_email}: {e}")
        return False
