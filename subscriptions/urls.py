from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'plans', views.PlanViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('subscription/', views.get_user_subscription, name='get_user_subscription'),
    path('subscription/create/', views.create_subscription, name='create_subscription'),
    path('payment/initialize/', views.initialize_payment, name='initialize_payment'),
    path('payment/history/', views.get_payment_history, name='payment_history'),
    path('webhook/paystack/', views.paystack_webhook, name='paystack_webhook'),
]
