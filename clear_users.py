import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabletap_console.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
print(f'Deleted {User.objects.all().delete()} users')

