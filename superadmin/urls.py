from django.urls import path
from . import views

urlpatterns = [
    path('overview/',                    views.overview,            name='superadmin-overview'),
    path('tenants/',                     views.tenant_list,         name='superadmin-tenant-list'),
    path('tenants/<int:tenant_id>/',     views.tenant_detail,       name='superadmin-tenant-detail'),
    path('tenants/<int:tenant_id>/toggle/', views.tenant_toggle,    name='superadmin-tenant-toggle'),
    path('users/',                       views.user_list,           name='superadmin-user-list'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='superadmin-user-toggle-active'),
    path('users/<int:user_id>/toggle-staff/',  views.user_toggle_staff,  name='superadmin-user-toggle-staff'),
]
