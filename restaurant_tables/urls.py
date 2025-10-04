from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TableViewSet, bulk_generate_tables, qr_batch

router = DefaultRouter()
router.register(r'', TableViewSet)

urlpatterns = [
    path('bulk-generate/', bulk_generate_tables, name='bulk_generate_tables'),
    path('qr-batch/', qr_batch, name='qr_batch'),
    path('', include(router.urls)),
]
