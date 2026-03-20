import re
from django.conf import settings
from django.db import connection
from django_tenants.middleware.main import TenantMainMiddleware
from django_tenants.utils import get_tenant_model, get_public_schema_name
from tenants.models import Tenant, Domain


class TableTapTenantMiddleware(TenantMainMiddleware):
    """
    Custom middleware to resolve tenants using headers or path prefixes.
    Resolution order:
    1. X-Tenant-Id header (slug or schema_name) — highest priority
    2. Hostname match against the tenants_domain table
    3. Fallback to the public schema — so auth/provision endpoints always work
    """

    def _get_public_tenant(self):
        try:
            return Tenant.objects.get(schema_name=get_public_schema_name())
        except Tenant.DoesNotExist:
            return None

    def process_request(self, request):
        connection.set_schema_to_public()

        tenant_slug = request.headers.get('X-Tenant-Id')
        host = request.get_host().split(':')[0].lower()

        # ── 1. Resolve by X-Tenant-Id header ──────────────────────────────
        if tenant_slug:
            tenant = (
                Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
                or Tenant.objects.filter(schema_name=tenant_slug, is_active=True).first()
            )
            if tenant:
                request.tenant = tenant
                connection.set_tenant(tenant)
                request.urlconf = settings.ROOT_URLCONF
                return

        # ── 2. Resolve by hostname ─────────────────────────────────────────
        domain_obj = Domain.objects.filter(domain=host).select_related('tenant').first()
        if domain_obj:
            tenant = domain_obj.tenant
            request.tenant = tenant
            connection.set_tenant(tenant)
            # Use PUBLIC_SCHEMA_URLCONF for the public schema, tenant URLs otherwise
            if tenant.schema_name == get_public_schema_name():
                request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
            else:
                request.urlconf = settings.ROOT_URLCONF
            return

        # ── 3. Fallback: use public schema ─────────────────────────────────
        # This handles dynamic Replit preview domains, localhost variants,
        # and any host not in the domain table. Auth and provision endpoints
        # are all registered in PUBLIC_SCHEMA_URLCONF so they stay reachable.
        public_tenant = self._get_public_tenant()
        if public_tenant:
            request.tenant = public_tenant
            connection.set_tenant(public_tenant)
            request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
            return

        # If even the public tenant doesn't exist yet, let django-tenants
        # handle the error (will show a clear error page).
        super().process_request(request)
