from authentication.models import User
from tenants.models import Tenant
from staff.models import StaffMember
from django_tenants.utils import tenant_context

print("=== USERS ===")
for u in User.objects.all():
    print(u.id, u.email, u.role, u.clerk_user_id)

print("\n=== TENANTS ===")
for t in Tenant.objects.all():
    print(t.id, t.schema_name, t.clerk_organization_id)
    if t.schema_name == 'public':
        continue
    with tenant_context(t):
        try:
            for s in StaffMember.objects.all():
                print(f"  STAFF: {s.id} {s.user.email} {s.role.name}")
        except Exception as e:
            print(f"  Error: {e}")
