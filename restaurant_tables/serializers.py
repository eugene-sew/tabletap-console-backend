from rest_framework import serializers
from .models import Table

class TableSerializer(serializers.ModelSerializer):
    qrCode = serializers.SerializerMethodField()
    
    class Meta:
        model = Table
        fields = [
            'id', 'number', 'name', 'section', 'capacity', 'status',
            'qrCode', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_qrCode(self, obj):
        """Return QR code information"""
        return {
            'url': obj.qr_code_url,
            'generatedAt': obj.qr_code_generated_at.isoformat() if obj.qr_code_generated_at else None
        }

class TableCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ['number', 'name', 'section', 'capacity']
    
    def validate_number(self, value):
        """Ensure table number is unique"""
        if Table.objects.filter(number=value).exists():
            raise serializers.ValidationError("Table with this number already exists.")
        return value

class BulkTableCreateSerializer(serializers.Serializer):
    fromTable = serializers.IntegerField(min_value=1)
    toTable = serializers.IntegerField(min_value=1)
    section = serializers.CharField(max_length=50, required=False, allow_blank=True)
    
    def validate(self, data):
        if data['fromTable'] > data['toTable']:
            raise serializers.ValidationError("fromTable must be less than or equal to toTable")
        
        # Check for existing tables in range
        existing_tables = Table.objects.filter(
            number__gte=data['fromTable'],
            number__lte=data['toTable']
        ).values_list('number', flat=True)
        
        if existing_tables:
            raise serializers.ValidationError(
                f"Tables already exist for numbers: {list(existing_tables)}"
            )
        
        return data

class QRBatchSerializer(serializers.Serializer):
    tables = TableSerializer(many=True, read_only=True)
    restaurantSlug = serializers.CharField(read_only=True)
