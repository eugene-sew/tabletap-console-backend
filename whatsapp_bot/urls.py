from django.urls import path
from . import views

urlpatterns = [
    # Meta webhook (public — no auth, HMAC-verified)
    path('webhook/', views.webhook, name='whatsapp_webhook'),

    # Owner magic link verification (public — token-gated)
    path('owner-verify/', views.owner_auth_verify, name='whatsapp_owner_verify'),

    # Console settings API (authenticated)
    path('status/', views.connect_status, name='whatsapp_status'),
    path('settings/', views.bot_settings, name='whatsapp_settings'),
    path('connect/', views.manual_connect, name='whatsapp_manual_connect'),
    path('disconnect/', views.disconnect, name='whatsapp_disconnect'),
    path('owner-access/', views.request_owner_bot_access, name='whatsapp_owner_access'),

    # Console Inbox API (authenticated)
    path('inbox/', views.inbox_conversations, name='whatsapp_inbox_conversations'),
    path('inbox/<str:wa_id>/', views.inbox_conversation_detail, name='whatsapp_inbox_detail'),
    path('inbox/<str:wa_id>/send/', views.inbox_send_message, name='whatsapp_inbox_send'),
]

