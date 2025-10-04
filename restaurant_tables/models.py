from django.db import models
from django.utils import timezone
import qrcode
from io import BytesIO
import base64

class Table(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    
    number = models.IntegerField()
    name = models.CharField(max_length=100, blank=True)  # Optional nickname
    section = models.CharField(max_length=50, blank=True)
    capacity = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # QR Code info
    qr_code_url = models.URLField(blank=True)
    qr_code_generated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['number']
        ordering = ['number']
    
    def generate_qr_code_url(self, restaurant_slug):
        """Generate QR code URL for this table"""
        # Format: menu.tabletap.space/{slug}/{table}
        self.qr_code_url = f"https://menu.tabletap.space/{restaurant_slug}/{self.number}"
        self.qr_code_generated_at = timezone.now()
        return self.qr_code_url
    
    def get_qr_code_image(self):
        """Generate QR code image as base64 string"""
        if not self.qr_code_url:
            return None
            
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(self.qr_code_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    def __str__(self):
        return f"Table {self.number}" + (f" ({self.name})" if self.name else "")
