from django.urls import path
from .views import (
    register,
    verify_email,
    login,
    token_refresh,
    password_reset_request,
    password_reset_confirm,
    user_profile,
    user_tenant,
    provision_tenant,
    link_staff_account,
    test_auth,
    log_auth_event,
)

urlpatterns = [
    path('register/', register, name='auth_register'),
    path('verify-email/', verify_email, name='auth_verify_email'),
    path('login/', login, name='auth_login'),
    path('token/refresh/', token_refresh, name='auth_token_refresh'),
    path('password-reset/', password_reset_request, name='auth_password_reset_request'),
    path('password-reset/confirm/', password_reset_confirm, name='auth_password_reset_confirm'),
    path('profile/', user_profile, name='user_profile'),
    path('tenant/', user_tenant, name='user_tenant'),
    path('provision/', provision_tenant, name='provision_tenant'),
    path('link-staff/', link_staff_account, name='link_staff_account'),
    path('test/', test_auth, name='test_auth'),
    path('log-event/', log_auth_event, name='log_auth_event'),
]
