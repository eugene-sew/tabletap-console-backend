from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets
import string


class User(AbstractUser):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('admin', 'Admin'),
        ('manager', 'Manager'),
        ('staff', 'Staff'),
    ]
    clerk_user_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    name = models.CharField(max_length=255, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    avatar_url = models.URLField(blank=True)
    is_verified = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='owner')

    email_verification_token = models.CharField(max_length=10, null=True, blank=True)
    email_verification_token_expires = models.DateTimeField(null=True, blank=True)

    password_reset_token = models.CharField(max_length=10, null=True, blank=True)
    password_reset_token_expires = models.DateTimeField(null=True, blank=True)

    def generate_verification_code(self):
        code = ''.join(secrets.choice(string.digits) for _ in range(6))
        from django.utils import timezone
        from datetime import timedelta
        self.email_verification_token = code
        self.email_verification_token_expires = timezone.now() + timedelta(minutes=15)
        self.save(update_fields=['email_verification_token', 'email_verification_token_expires'])
        return code

    def generate_password_reset_code(self):
        code = ''.join(secrets.choice(string.digits) for _ in range(6))
        from django.utils import timezone
        from datetime import timedelta
        self.password_reset_token = code
        self.password_reset_token_expires = timezone.now() + timedelta(minutes=30)
        self.save(update_fields=['password_reset_token', 'password_reset_token_expires'])
        return code

    def get_tenant_role(self):
        from django.db import connection
        from tenants.models import Tenant
        schema_name = connection.schema_name
        if schema_name == 'public':
            return self.role
        try:
            tenant = Tenant.objects.get(schema_name=schema_name)
            if tenant.owner_id and tenant.owner_id == self.pk:
                return 'owner'
            return self.role
        except Tenant.DoesNotExist:
            return self.role

    def __str__(self):
        return self.email or self.username
