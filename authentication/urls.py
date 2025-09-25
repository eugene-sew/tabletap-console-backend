from django.urls import path
from .views import clerk_webhook, user_profile

urlpatterns = [
    path('webhook/clerk/', clerk_webhook, name='clerk_webhook'),
    path('profile/', user_profile, name='user_profile'),
]
