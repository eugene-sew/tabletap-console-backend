from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, SubscriptionViewSet, subscribe_to_plan, paystack_webhook

router = DefaultRouter()
router.register(r'plans', PlanViewSet)
router.register(r'subscriptions', SubscriptionViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('subscribe/', subscribe_to_plan, name='subscribe_to_plan'),
    path('webhook/paystack/', paystack_webhook, name='paystack_webhook'),
]
