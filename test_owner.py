from django_tenants.utils import schema_context
from staff.models import Role, StaffMember
from tenants.models import Tenant
from authentication.models import User

with schema_context('test'):
    roles = Role.objects.all()
    print("Roles in test:")
    for r in roles:
        print(f" - {r.name}: {r.permissions}")
    
    tenant = Tenant.objects.get(schema_name='test')
    print(f"\nTenant: {tenant.name}")
    
    owner_role = Role.objects.filter(tenant=tenant, name='Owner').first()
    print(f"Owner role found: {owner_role}")
    
    users = User.objects.all()
    print("\nUsers:")
    for u in users:
        print(f" - {u.email} (role: {u.role})")
        
    staff = StaffMember.objects.all()
    print("\nStaffMembers in test:")
    for s in staff:
        print(f" - {s.user.email} -> {s.role.name if s.role else None}")

