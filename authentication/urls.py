from django.urls import path
from .views import clerk_webhook, user_profile, user_tenant, test_auth

urlpatterns = [
    path('webhook/clerk/', clerk_webhook, name='clerk_webhook'),
    path('profile/', user_profile, name='user_profile'),
    path('tenant/', user_tenant, name='user_tenant'),
    path('test/', test_auth, name='test_auth'),
]
