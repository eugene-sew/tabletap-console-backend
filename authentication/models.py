from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    clerk_user_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    avatar_url = models.URLField(blank=True)
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return self.email or self.username
