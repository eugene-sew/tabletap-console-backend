import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabletap_console.settings')
django.setup()

from tenants.models import Tenant, Domain

def check_and_fix():
    print("--- Current Tenants ---")
    tenants = Tenant.objects.all()
    for t in tenants:
        print(f"Schema: {t.schema_name}, Name: {t.name}")
    
    print("\n--- Current Domains ---")
    domains = Domain.objects.all()
    for d in domains:
        print(f"Domain: {d.domain}, Tenant: {d.tenant.schema_name}")

    # Ensure public tenant exists
    public_tenant, created = Tenant.objects.get_or_create(
        schema_name='public',
        defaults={'name': 'Public', 'contact_email': 'admin@example.com'}
    )
    if created:
        print("\nCreated public tenant.")

    # Ensure localhost is mapped to public
    domain, created = Domain.objects.get_or_create(
        domain='localhost',
        defaults={'tenant': public_tenant, 'is_primary': True}
    )
    if created:
        print(f"Created domain mapping: localhost -> {public_tenant.schema_name}")
    else:
        print(f"Domain 'localhost' already exists for tenant: {domain.tenant.schema_name}")

    # Ensure 127.0.0.1 is mapped to public for good measure
    Domain.objects.get_or_create(
        domain='127.0.0.1',
        defaults={'tenant': public_tenant, 'is_primary': False}
    )

    # Ensure test tenant exists
    test_tenant, created = Tenant.objects.get_or_create(
        schema_name='test',
        defaults={'name': 'Test Restaurant', 'contact_email': 'test@example.com'}
    )
    if created:
        print("\nCreated test tenant.")

    # Ensure test.localhost is mapped to test
    Domain.objects.get_or_create(
        domain='test.localhost',
        defaults={'tenant': test_tenant, 'is_primary': True}
    )
    print("Mapped test.localhost -> test")

if __name__ == "__main__":
    check_and_fix()
