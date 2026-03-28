import os
from datetime import timedelta
from decouple import config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = config('SECRET_KEY', default='your-secret-key-here')
DEBUG = config('DEBUG', default=True, cast=bool)
_raw_allowed_hosts = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,.tabletap.space,tabletap.space', cast=lambda v: [s.strip() for s in v.split(',')])
ALLOWED_HOSTS = [('.' + h[2:]) if h.startswith('*.') else h for h in _raw_allowed_hosts if h]
if DEBUG:
    ALLOWED_HOSTS += ['*']

SHARED_APPS = [
    'django_tenants',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_yasg',
    'tenants',
    'authentication',
    'subscriptions',
    'analytics',
    'superadmin',
]

TENANT_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'staff',
    'tools',
    'restaurant_tables',
    'menu',
    'orders',
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'tenants.middleware.TableTapTenantMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tabletap_console.tenant_urls'
PUBLIC_SCHEMA_URLCONF = 'tabletap_console.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tabletap_console.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django_tenants.postgresql_backend',
        'NAME': config('DB_NAME', default=os.environ.get('PGDATABASE', 'tabletap_console')),
        'USER': config('DB_USER', default=os.environ.get('PGUSER', 'postgres')),
        'PASSWORD': config('DB_PASSWORD', default=os.environ.get('PGPASSWORD', 'mysecretpassword')),
        'HOST': config('DB_HOST', default=os.environ.get('PGHOST', 'localhost')),
        'PORT': config('DB_PORT', default=os.environ.get('PGPORT', '5432')),
    }
}

DATABASE_ROUTERS = (
    'django_tenants.routers.TenantSyncRouter',
)

REDIS_URL = config('REDIS_URL', default='')

if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

CELERY_BROKER_URL = REDIS_URL or 'memory://'
CELERY_RESULT_BACKEND = REDIS_URL or 'cache+memory://'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

CELERY_BEAT_SCHEDULE = {
    'check-stale-orders-every-minute': {
        'task': 'orders.tasks.check_stale_orders',
        'schedule': 60.0,
    },
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'authentication.auth.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOW_CREDENTIALS = True
else:
    CORS_ALLOWED_ORIGINS = config(
        'CORS_ALLOWED_ORIGINS',
        default='http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,https://tabletap.space,https://console.tabletap.space,https://pos.tabletap.space',
        cast=lambda v: [s.strip() for s in v.split(',')]
    )
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https://.*\.tabletap\.space$",
    ]

from corsheaders.defaults import default_headers

CORS_ALLOW_HEADERS = list(default_headers) + [
    "x-tenant-id",
    "x-store-id",
]

RESEND_API_KEY = config('RESEND_API_KEY', default='')
RESEND_FROM_EMAIL = config('RESEND_FROM_EMAIL', default='onboarding@resend.dev')
FRONTEND_URL = config('FRONTEND_URL', default='https://tabletap.space')

CLERK_SECRET_KEY = config('CLERK_SECRET_KEY', default='')
CLERK_PUBLISHABLE_KEY = config('CLERK_PUBLISHABLE_KEY', default='')
CLERK_WEBHOOK_SECRET = config('CLERK_WEBHOOK_SECRET', default='')

PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')

AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')

if not DEBUG:
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
    'https://tabletap.space',
    'https://console.tabletap.space',
    'https://pos.tabletap.space',
    'https://*.tabletap.space',
]

AUTH_USER_MODEL = 'authentication.User'

PUSHER_APP_ID = config('PUSHER_APP_ID', default='')
PUSHER_KEY = config('PUSHER_KEY', default='')
PUSHER_SECRET = config('PUSHER_SECRET', default='')
PUSHER_CLUSTER = config('PUSHER_CLUSTER', default='eu')
