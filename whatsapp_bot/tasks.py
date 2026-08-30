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

        # Helper to normalize digits for phone comparison
        def _clean_phone(p: str) -> str:
            return ''.join(c for c in (p or '') if c.isdigit())

        clean_sender_wa_id = _clean_phone(wa_id)

        # 1. Check if sender matches tenant owner's designated WhatsApp number
        try:
            account = getattr(tenant, 'whatsapp_account', None)
            if account and account.owner_phone_number:
                if _clean_phone(account.owner_phone_number) == clean_sender_wa_id:
                    is_owner = True
        except Exception:
            pass

        # 2. Check active BotOwnerSession
        if not is_owner:
            try:
                BotOwnerSession.objects.get(
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

        save_session(phone_number_id, wa_id, session)

        # ── Send reply ───────────────────────────────────────────────────────
        wa_client.send_text(phone_number_id, access_token, wa_id, reply)
        logger.info(f'[WhatsApp] Reply sent to {wa_id} for tenant {tenant.slug}')

    except Exception as e:
        logger.error(f'[WhatsApp] Task error: {e}', exc_info=True)


# ---------------------------------------------------------------------------
# Proactive Background Tasks (Celery Beat)
# ---------------------------------------------------------------------------

@shared_task(name='whatsapp_bot.tasks.check_delayed_orders_task')
def check_delayed_orders_task():
    """
    Scans all active tenants for orders in 'pending' or 'preparing' for > 30 minutes.
    Sends a proactive alert to the restaurant owner's WhatsApp number.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django_tenants.utils import tenant_context
    from .models import TenantWhatsAppAccount
    from orders.models import Order

    logger.info('[WhatsApp Alerts] Checking for delayed orders (> 30 mins)...')
    now = timezone.now()
    threshold = now - timedelta(minutes=30)

    # Find all accounts that have proactive alerts enabled and an owner phone configured
    accounts = TenantWhatsAppAccount.objects.select_related('tenant').filter(
        is_active=True,
        enable_delayed_order_alerts=True,
    ).exclude(owner_phone_number='')

    for account in accounts:
        tenant = account.tenant
        owner_phone = account.owner_phone_number.strip()
        if not owner_phone:
            continue

        with tenant_context(tenant):
            delayed_orders = Order.objects.filter(
                status__in=['pending', 'preparing'],
                created_at__lte=threshold,
            ).order_by('created_at')

            for order in delayed_orders:
                alert_key = f'wa_delayed_alert:{tenant.slug}:{order.order_number}'
                if cache.get(alert_key):
                    continue  # Already alerted within cooldown window

                elapsed_mins = int((now - order.created_at).total_seconds() / 60)
                items_summary = ', '.join(
                    f"{item.quantity}x {item.name}" for item in order.items.all()[:4]
                ) or 'Items'

                alert_text = (
                    f"⚠️ *Delayed Order Alert (>30 mins)*\n\n"
                    f"📦 Order *#{order.order_number}* has been in *{order.status.upper()}* for *{elapsed_mins} minutes*!\n"
                    f"• *Customer*: {order.customer_name or 'Guest'} ({order.customer_phone or 'No phone'})\n"
                    f"• *Total*: {tenant.currency or 'GHS'} {order.total_amount:.2f}\n"
                    f"• *Items*: {items_summary}\n\n"
                    f"Reply *\"Mark {order.order_number} as ready\"* or check kitchen POS."
                )

                try:
                    logger.info(f"[WhatsApp Alert] Sending delayed alert for order {order.order_number} to {owner_phone}")
                    wa_client.send_text(
                        account.phone_number_id,
                        account.access_token,
                        owner_phone,
                        alert_text,
                    )
                    # Cache for 45 minutes to avoid spamming the owner
                    cache.set(alert_key, '1', timeout=60 * 45)
                except Exception as e:
                    logger.error(f"[WhatsApp Alert] Failed to send alert to {owner_phone}: {e}")


@shared_task(name='whatsapp_bot.tasks.send_daily_closing_report_task')
def send_daily_closing_report_task():
    """
    Sends an executive evening closing revenue summary to the owner's WhatsApp number.
    """
    from .models import TenantWhatsAppAccount
    from .tools import get_metrics_summary

    logger.info('[WhatsApp Reports] Sending daily closing reports to owners...')
    accounts = TenantWhatsAppAccount.objects.select_related('tenant').filter(
        is_active=True,
        enable_daily_reports=True,
    ).exclude(owner_phone_number='')

    for account in accounts:
        tenant = account.tenant
        owner_phone = account.owner_phone_number.strip()
        if not owner_phone:
            continue

        try:
            metrics = get_metrics_summary(tenant.slug, period='today')
            currency = tenant.currency or 'GHS'
            report = (
                f"📊 *Daily Closing Report — {tenant.name}*\n\n"
                f"💰 *Total Revenue*: {currency} {metrics['revenue']:.2f}\n"
                f"📦 *Total Orders*: {metrics['order_count']} ({metrics['completed']} completed, {metrics['cancelled']} cancelled)\n"
                f"🎯 *Average Order Value*: {currency} {metrics['average_order_value']:.2f}\n"
                f"🏆 *Top Seller*: {metrics['top_item']}\n\n"
                f"💳 *Payment Breakdown*:\n"
                f"• MoMo: {currency} {metrics['payments']['momo']:.2f}\n"
                f"• Cash: {currency} {metrics['payments']['cash']:.2f}\n"
                f"• Card: {currency} {metrics['payments']['card']:.2f}\n\n"
                f"Great job today! Have a restful night. 🌙"
            )

            wa_client.send_text(
                account.phone_number_id,
                account.access_token,
                owner_phone,
                report,
            )
            logger.info(f"[WhatsApp Report] Sent closing report for {tenant.slug} to {owner_phone}")
        except Exception as e:
            logger.error(f"[WhatsApp Report] Failed to send closing report for {tenant.slug}: {e}")

