def log_action(request_or_user, action, entity_type, entity_id='', entity_label='', metadata=None):
    """
    Create an AuditLog entry scoped to the current tenant.

    Can be called with a DRF request object (extracts user + tenant automatically)
    or with a plain User object (falls back to the active DB schema).
    """
    from .models import AuditLog
    from django.db import connection

    if hasattr(request_or_user, 'user'):
        user = request_or_user.user
        tenant = getattr(request_or_user, 'tenant', None)
    else:
        user = request_or_user
        tenant = None

    actor_name = ''
    actor_email = ''
    if user and hasattr(user, 'pk') and user.pk:
        full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        actor_name = full_name or getattr(user, 'username', '') or ''
        actor_email = getattr(user, 'email', '') or ''

    # Resolve tenant schema: prefer request.tenant, fall back to active connection schema
    if tenant and hasattr(tenant, 'schema_name'):
        tenant_schema = tenant.schema_name
    else:
        tenant_schema = getattr(connection, 'schema_name', 'public')

    try:
        AuditLog.objects.create(
            actor_name=actor_name,
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            entity_label=entity_label,
            tenant_schema=tenant_schema,
            metadata=metadata or {},
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"[AuditLog] Failed to create entry: {exc}")
