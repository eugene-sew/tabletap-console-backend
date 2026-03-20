from rest_framework import serializers
from .models import Category, MenuItem

class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='category.name')

    class Meta:
        model = MenuItem
        fields = [
            'id', 'tenant', 'category', 'category_name', 'name', 'description', 
            'price', 'imageUrl', 'isAvailable', 'created_at', 'updated_at'
        ]
        read_only_fields = ['tenant']

class CategorySerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'tenant', 'name', 'priority', 'items', 'created_at', 'updated_at']
        read_only_fields = ['tenant']
