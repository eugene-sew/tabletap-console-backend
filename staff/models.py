from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=dict)
    
    def __str__(self):
        return self.name

class StaffMember(models.Model):
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
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role.name}"
