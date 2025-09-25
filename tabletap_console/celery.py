import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabletap_console.settings')

app = Celery('tabletap_console')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
