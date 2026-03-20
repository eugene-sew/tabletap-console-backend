def log_action(request_or_user, action, entity_type, entity_id='', entity_label='', metadata=None):
    """
    Create an AuditLog entry.

    Can be called with a DRF request object (extracts user automatically) or
    with a plain User object.
    """
    from .models import AuditLog

    if hasattr(request_or_user, 'user'):
        user = request_or_user.user
    else:
        user = request_or_user

    actor_name = ''
    actor_email = ''
    if user and hasattr(user, 'pk') and user.pk:
        full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        actor_name = full_name or getattr(user, 'username', '') or ''
        actor_email = getattr(user, 'email', '') or ''

    try:
        AuditLog.objects.create(
            actor_name=actor_name,
            actor_email=actor_email,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            entity_label=entity_label,
            metadata=metadata or {},
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"[AuditLog] Failed to create entry: {exc}")
