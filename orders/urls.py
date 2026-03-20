from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, ReviewViewSet

router = DefaultRouter()
router.register(r'', OrderViewSet)

review_router = DefaultRouter()
review_router.register(r'', ReviewViewSet, basename='review')

urlpatterns = [
    # reviews/ MUST come before '' to avoid {pk}/ wildcard swallowing it
    path('reviews/', include(review_router.urls)),
    path('', include(router.urls)),
]
