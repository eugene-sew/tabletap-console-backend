from rest_framework import serializers
from .models import Tool, ToolAccess, SSOToken

class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = ['id', 'name', 'description', 'url', 'is_active']

class ToolAccessSerializer(serializers.ModelSerializer):
    tool = ToolSerializer(read_only=True)
    
    class Meta:
        model = ToolAccess
        fields = ['id', 'user', 'tool', 'is_granted', 'granted_at']

class SSOTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = SSOToken
        fields = ['token', 'expires_at', 'created_at']
