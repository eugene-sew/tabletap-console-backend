from django.db import models
from django.contrib.auth import get_user_model
import jwt
from django.conf import settings
from datetime import datetime, timedelta

User = get_user_model()

class Tool(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    url = models.URLField()
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class ToolAccess(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    is_granted = models.BooleanField(default=False)
    granted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'tool']
    
    def __str__(self):
        return f"{self.user.username} - {self.tool.name}"

class SSOToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    token = models.TextField()
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def is_valid(self):
        return not self.is_used and self.expires_at > datetime.now()
    
    @classmethod
    def generate_token(cls, user, tool, tenant_schema):
        """Generate SSO token for tool access"""
        payload = {
            'user_id': user.id,
            'tool_id': tool.id,
            'tenant_schema': tenant_schema,
            'exp': datetime.utcnow() + timedelta(hours=1),
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        
        sso_token = cls.objects.create(
            user=user,
            tool=tool,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        return sso_token
