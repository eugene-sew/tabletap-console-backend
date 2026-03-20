from tenants.models import Tenant, Domain

def fix_domains():
    # Public domains
    public_tenant = Tenant.objects.get(schema_name='public')
    for d in ['localhost', '127.0.0.1']:
        Domain.objects.get_or_create(domain=d, tenant=public_tenant, is_primary=True)

    # Blueplate Pub (test)
    test_tenant = Tenant.objects.get(schema_name='test')
    for d in ['test.localhost', 'test-restaurant.localhost']:
        obj, created = Domain.objects.get_or_create(domain=d, tenant=test_tenant)
        if created:
            print(f"Created domain {d} for {test_tenant.schema_name}")

    # Mama Esi Restaurant (test_restaurant)
    test_res_tenant = Tenant.objects.get(schema_name='test_restaurant')
    for d in ['mama-esi.localhost', 'mama-esi-restaurant.localhost']:
        obj, created = Domain.objects.get_or_create(domain=d, tenant=test_res_tenant)
        if created:
            print(f"Created domain {d} for {test_res_tenant.schema_name}")

if __name__ == "__main__":
    fix_domains()
