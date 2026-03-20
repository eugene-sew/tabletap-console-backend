from django.urls import path
from .views import clerk_webhook, user_profile, user_tenant, provision_tenant, test_auth, link_staff_account, log_auth_event

urlpatterns = [
    path('webhook/clerk/', clerk_webhook, name='clerk_webhook'),
    path('profile/', user_profile, name='user_profile'),
    path('tenant/', user_tenant, name='user_tenant'),
    path('provision/', provision_tenant, name='provision_tenant'),
    path('link-staff/', link_staff_account, name='link_staff_account'),
    path('test/', test_auth, name='test_auth'),
    path('log-event/', log_auth_event, name='log_auth_event'),
]
