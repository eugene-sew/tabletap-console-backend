"""
Celery tasks for async WhatsApp message processing.

The webhook view enqueues process_whatsapp_message immediately and returns 200 OK.
This task does all the heavy lifting: session load, agent call, reply send.
"""
import logging
from celery import shared_task
from django.core.cache import cache

from . import client as wa_client
from .session import load_session, save_session, clear_session
from .agent import run_customer_agent, run_owner_agent

logger = logging.getLogger(__name__)

IDEMPOTENCY_TTL = 86400  # 24 hours — enough to cover Meta's retry window


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    name='whatsapp_bot.tasks.process_whatsapp_message',
)
def process_whatsapp_message(self, payload: dict, phone_number_id: str):
    """
    Process an incoming WhatsApp message event.

    Steps:
    1. Extract message data
    2. Idempotency check (skip duplicate deliveries)
    3. Load tenant + credentials from phone_number_id
    4. Load Redis session
    5. Determine customer vs owner persona
    6. Run Gemini agent
    7. Send WhatsApp reply
    8. Persist updated session
    """
    try:
        # Extract message fields from Meta webhook payload
        entry = payload.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        messages = value.get('messages', [])

        if not messages:
            return  # Status update or other non-message event

        msg = messages[0]
        message_id = msg.get('id', '')
        wa_id = msg.get('from', '')  # Sender's WhatsApp number
        msg_type = msg.get('type', 'text')

        contacts = value.get('contacts', [])
        contact_name = ''
        if contacts:
            contact_profile = contacts[0].get('profile', {})
            contact_name = contact_profile.get('name', '')
            if not wa_id:
                wa_id = contacts[0].get('wa_id', '')

        # ── Guard: skip if no sender wa_id (status updates, system events) ────
        if not wa_id:
            logger.info(f'[WhatsApp] Skipping message with no sender wa_id (message_id={message_id})')
            return

        # ── Idempotency: skip if already processed ──────────────────────────
        idempotency_key = f'wa_processed:{message_id}'
        if cache.get(idempotency_key):
            logger.info(f'[WhatsApp] Duplicate message {message_id} — skipping')
            return
        cache.set(idempotency_key, '1', timeout=IDEMPOTENCY_TTL)

        # ── Extract text ─────────────────────────────────────────────────────
        if msg_type == 'text':
            text = msg.get('text', {}).get('body', '').strip()
        elif msg_type == 'interactive':
            # Reply button or list selection
            interactive = msg.get('interactive', {})
            if interactive.get('type') == 'button_reply':
                text = interactive['button_reply'].get('title', '')
            elif interactive.get('type') == 'list_reply':
                text = interactive['list_reply'].get('title', '')
            else:
                text = ''
        else:
            # Voice notes, images, etc — not yet supported
            text = ''

        if not text:
            logger.info(f'[WhatsApp] Non-text message from {wa_id} — ignoring')
            return

        # ── Resolve tenant from phone_number_id ──────────────────────────────
        from .models import TenantWhatsAppAccount, BotOwnerSession
        from tenants.models import Tenant

        try:
            wa_account = TenantWhatsAppAccount.objects.select_related('tenant').get(
                phone_number_id=phone_number_id,
                is_active=True,
            )
            tenant = wa_account.tenant
            access_token = wa_account.access_token
        except TenantWhatsAppAccount.DoesNotExist:
            # Fall back to settings-level default (for single-number testing)
            from django.conf import settings as dj_settings
            default_phone_id = getattr(dj_settings, 'META_PHONE_NUMBER_ID', '')
            default_token = getattr(dj_settings, 'META_ACCESS_TOKEN', '')
            default_slug = getattr(dj_settings, 'META_DEFAULT_TENANT_SLUG', '')

            if phone_number_id != default_phone_id or not default_slug:
                logger.warning(f'[WhatsApp] No tenant found for phone_number_id={phone_number_id}')
                return

            try:
                tenant = Tenant.objects.get(slug=default_slug)
                access_token = default_token
            except Tenant.DoesNotExist:
                logger.error(f'[WhatsApp] Default tenant slug {default_slug!r} not found')
                return

        # ── Send read receipt ────────────────────────────────────────────────
        try:
            wa_client.mark_as_read(phone_number_id, access_token, message_id)
        except Exception:
            pass

        # ── Load session ─────────────────────────────────────────────────────
        session = load_session(phone_number_id, wa_id)
        if contact_name and not session.get('customer_name'):
            session['customer_name'] = contact_name
        if not session.get('customer_phone'):
            session['customer_phone'] = wa_id

        # ── Reset command ────────────────────────────────────────────────────
        if text.lower().strip() in ['/reset', 'reset', 'start over', 'restart']:
            clear_session(phone_number_id, wa_id)
            wa_client.send_text(
                phone_number_id, access_token, wa_id,
                f'Starting fresh! 👋 Welcome to *{tenant.name}*. How can I help you today?'
            )
            return

        # ── Determine persona: customer vs owner ─────────────────────────────
        is_owner = False
        try:
            owner_session = BotOwnerSession.objects.get(
                tenant=tenant,
                wa_id=wa_id,
                is_authenticated=True,
            )
            is_owner = True
        except BotOwnerSession.DoesNotExist:
            pass

        session['is_owner'] = is_owner

        # ── Run agent ────────────────────────────────────────────────────────
        logger.info(f'[WhatsApp] [{tenant.slug}] {"Owner" if is_owner else "Customer"} message from {wa_id}: {text[:80]}')

        if is_owner:
            reply, session = run_owner_agent(text, session, tenant)
        else:
            reply, session = run_customer_agent(text, session, tenant)

        # ── Send reply ───────────────────────────────────────────────────────
        wa_client.send_text(phone_number_id, access_token, wa_id, reply)

        # ── Persist session ──────────────────────────────────────────────────
        save_session(phone_number_id, wa_id, session)

        logger.info(f'[WhatsApp] Reply sent to {wa_id} for tenant {tenant.slug}')

    except Exception as exc:
        logger.error(f'[WhatsApp] Task error: {exc}', exc_info=True)
        raise
