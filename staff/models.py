from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Role(models.Model):
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='staff_roles', null=True, blank=True)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=dict)
    
    def __str__(self):
        return self.name

class StaffMember(models.Model):
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.CASCADE, related_name='staff_members', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    hired_date = models.DateTimeField(auto_now_add=True)
    
    # Additional staff info
    employee_id = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=50, blank=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        unique_together = ['user']
    
    def save(self, *args, **kwargs):
        if not self.employee_id and self.tenant:
            prefix = self.tenant.name[:2].upper() if self.tenant.name else "XX"
            count = StaffMember.objects.filter(tenant=self.tenant).count()
            self.employee_id = f"TT-{prefix}-{count:04d}"
            
            while StaffMember.objects.filter(tenant=self.tenant, employee_id=self.employee_id).exists():
                count += 1
                self.employee_id = f"TT-{prefix}-{count:04d}"
                
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role.name}"
