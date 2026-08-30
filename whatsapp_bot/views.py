"""
WhatsApp Bot API views.

- webhook: Meta webhook verification (GET) + message processing (POST)
- connect_status: Console → get bot connection state for a tenant
- bot_settings: Console → update bot config (name, greeting, toggle)
- embedded_signup_callback: OAuth callback for per-tenant WABA linking
- owner_auth_verify: Owner magic link verification
"""
import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import TenantWhatsAppAccount, BotOwnerSession
from .tasks import process_whatsapp_message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_tenant_from_request(request):
    tenant = getattr(request, 'tenant', None)
    if tenant and getattr(tenant, 'slug', '') not in ('', 'public'):
        return tenant
    from tenants.models import Tenant
    if hasattr(request, 'user') and request.user and hasattr(request.user, 'owned_tenants'):
        t = request.user.owned_tenants.first()
        if t:
            return t
    return Tenant.objects.exclude(slug='public').first()


# ---------------------------------------------------------------------------
# Meta webhook
# ---------------------------------------------------------------------------

@csrf_exempt
def webhook(request):
    """
    GET  — Meta webhook verification challenge
    POST — Incoming WhatsApp event (enqueue immediately, return 200)
    """
    if request.method == 'GET':
        verify_token = getattr(settings, 'META_VERIFY_TOKEN', '')
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == verify_token:
            logger.info('[WhatsApp] Webhook verified successfully')
            return HttpResponse(challenge, content_type='text/plain')

        logger.warning('[WhatsApp] Webhook verification failed')
        return HttpResponse('Forbidden', status=403)

    elif request.method == 'POST':
        # Verify X-Hub-Signature-256 if not DEBUG
        app_secret = getattr(settings, 'META_APP_SECRET', '')
        if app_secret and not settings.DEBUG:
            sig_header = request.headers.get('X-Hub-Signature-256', '')
            expected = 'sha256=' + hmac.new(
                app_secret.encode(),
                request.body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(sig_header, expected):
                logger.warning('[WhatsApp] Invalid webhook signature')
                return HttpResponse('Forbidden', status=403)

        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponse('Bad Request', status=400)

        # Extract phone_number_id from payload
        try:
            phone_number_id = (
                payload['entry'][0]['changes'][0]['value']['metadata']['phone_number_id']
            )
        except (KeyError, IndexError):
            # Could be a status update or other event — ack and ignore
            return HttpResponse('OK', status=200)

        # Enqueue async — return 200 immediately
        process_whatsapp_message.delay(payload, phone_number_id)
        return HttpResponse('OK', status=200)

    return HttpResponse('Method Not Allowed', status=405)


# ---------------------------------------------------------------------------
# Console API — bot settings
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def connect_status(request):
    """Return WhatsApp bot connection status for the current tenant."""
    tenant = _get_tenant_from_request(request)
    if not tenant:
        return Response({'connected': False})

    try:
        account = TenantWhatsAppAccount.objects.get(tenant=tenant)
        return Response({
            'connected': True,
            'is_active': account.is_active,
            'phone_number': account.phone_number,
            'bot_display_name': account.bot_display_name,
            'greeting_message': account.greeting_message,
            'owner_phone_number': account.owner_phone_number,
            'enable_delayed_order_alerts': account.enable_delayed_order_alerts,
            'enable_daily_reports': account.enable_daily_reports,
            'connected_at': account.connected_at.isoformat(),
        })
    except TenantWhatsAppAccount.DoesNotExist:
        return Response({'connected': False})


@api_view(['PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def bot_settings(request):
    """Update bot configuration: toggle, persona name, greeting, owner phone, proactive alerts."""
    tenant = _get_tenant_from_request(request)
    if not tenant:
        return Response({'error': 'No tenant context'}, status=400)

    try:
        account = TenantWhatsAppAccount.objects.get(tenant=tenant)
    except TenantWhatsAppAccount.DoesNotExist:
        return Response({'error': 'WhatsApp not connected'}, status=404)

    data = request.data
    if 'is_active' in data:
        account.is_active = bool(data['is_active'])
    if 'bot_display_name' in data:
        account.bot_display_name = data['bot_display_name'][:100]
    if 'greeting_message' in data:
        account.greeting_message = data['greeting_message']
    if 'owner_phone_number' in data:
        account.owner_phone_number = str(data['owner_phone_number']).strip()
    if 'enable_delayed_order_alerts' in data:
        account.enable_delayed_order_alerts = bool(data['enable_delayed_order_alerts'])
    if 'enable_daily_reports' in data:
        account.enable_daily_reports = bool(data['enable_daily_reports'])

    account.save()
    return Response({
        'success': True,
        'is_active': account.is_active,
        'bot_display_name': account.bot_display_name,
        'greeting_message': account.greeting_message,
        'owner_phone_number': account.owner_phone_number,
        'enable_delayed_order_alerts': account.enable_delayed_order_alerts,
        'enable_daily_reports': account.enable_daily_reports,
    })


@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated])
def disconnect(request):
    """Disconnect WhatsApp — removes stored credentials."""
    tenant = _get_tenant_from_request(request)
    if not tenant:
        return Response({'error': 'No tenant context'}, status=400)

    deleted, _ = TenantWhatsAppAccount.objects.filter(tenant=tenant).delete()
    return Response({'success': True, 'deleted': deleted})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def manual_connect(request):
    """
    Direct connection using a phone_number_id + access_token.
    For testing without Embedded Signup; also useful for restaurants
    that configure their own WABA manually.
    """
    tenant = _get_tenant_from_request(request)
    if not tenant:
        return Response({'error': 'No tenant context'}, status=400)

    phone_number_id = request.data.get('phone_number_id', '').strip()
    access_token = request.data.get('access_token', '').strip()
    waba_id = request.data.get('waba_id', '').strip()
    phone_number = request.data.get('phone_number', '').strip()

    if not phone_number_id or not access_token:
        return Response({'error': 'phone_number_id and access_token are required'}, status=400)

    account, created = TenantWhatsAppAccount.objects.update_or_create(
        tenant=tenant,
        defaults={
            'phone_number_id': phone_number_id,
            'access_token': access_token,
            'waba_id': waba_id,
            'phone_number': phone_number,
            'is_active': True,
        }
    )
    return Response({
        'success': True,
        'created': created,
        'phone_number_id': account.phone_number_id,
        'phone_number': account.phone_number,
    }, status=201 if created else 200)


# ---------------------------------------------------------------------------
# Owner authentication
# ---------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def request_owner_bot_access(request):
    """
    Console: owner requests bot access for their WhatsApp number.
    Sends a magic link to the owner's email or directly confirms.
    """
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return Response({'error': 'No tenant context'}, status=400)

    wa_number = request.data.get('wa_number', '').strip().replace('+', '').replace(' ', '')
    if not wa_number:
        return Response({'error': 'wa_number is required'}, status=400)

    session_obj, _ = BotOwnerSession.objects.get_or_create(
        tenant=tenant,
        wa_id=wa_number,
        defaults={'staff_user_id': request.user.pk},
    )
    token = session_obj.generate_magic_token()

    # Send magic link via WhatsApp (if account is connected)
    try:
        account = TenantWhatsAppAccount.objects.get(tenant=tenant, is_active=True)
        verify_url = f"{getattr(settings, 'FRONTEND_URL', '')}/api/whatsapp/owner-verify/?token={token}"
        from . import client as wa_client
        wa_client.send_text(
            account.phone_number_id,
            account.access_token,
            wa_number,
            f'👋 Hi! To activate owner access for *{tenant.name}* bot, click this link:\n\n{verify_url}\n\nThis link expires in 15 minutes.'
        )
    except Exception as e:
        logger.warning(f'[WhatsApp] Could not send magic link: {e}')

    return Response({'success': True, 'message': 'Magic link sent to your WhatsApp'})




@csrf_exempt
def owner_auth_verify(request):
    """Verify a magic token and mark the owner session as authenticated."""
    token = request.GET.get('token', '')
    if not token:
        return JsonResponse({'error': 'Token required'}, status=400)

    from django.utils import timezone
    try:
        session = BotOwnerSession.objects.get(
            magic_token=token,
            magic_token_expires__gt=timezone.now(),
        )
        session.is_authenticated = True
        session.magic_token = ''
        session.save(update_fields=['is_authenticated', 'magic_token'])
        return JsonResponse({'success': True, 'message': 'Owner bot access activated! Send any message to start.'})
    except BotOwnerSession.DoesNotExist:
        return JsonResponse({'error': 'Invalid or expired token'}, status=400)


# ---------------------------------------------------------------------------
# Console Inbox API — Owner reads & replies to WhatsApp conversations
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def inbox_conversations(request):
    """
    Return a list of all active WhatsApp conversations for the authenticated tenant.
    Each entry: { wa_id, customer_name, customer_phone, last_message, last_message_at, message_count }
    Reads from Redis session keys: wa_session:{phone_number_id}:*
    """
    from django.core.cache import cache
    import json

    tenant = _get_tenant_from_request(request)
    if not tenant:
        return Response({'error': 'Tenant not found'}, status=404)

    # Get the phone_number_id for this tenant
    try:
        wa_account = TenantWhatsAppAccount.objects.get(tenant=tenant, is_active=True)
        phone_number_id = wa_account.phone_number_id
    except TenantWhatsAppAccount.DoesNotExist:
        phone_number_id = getattr(settings, 'META_PHONE_NUMBER_ID', '')

    if not phone_number_id:
        return Response({'conversations': []})

    # Scan Redis raw keys to discover wa_session conversations for this phone_number_id.
    # Django cache prefixes keys with ':1:' (version), so raw keys look like: :1:wa_session:{id}:{wa_id}
    # We scan with a wildcard to find all keys, then extract the logical key and use cache.get().
    try:
        from django.core.cache import caches, cache
        redis_client = caches['default'].client.get_client()
        pattern = f'*wa_session:{phone_number_id}:*'
        raw_keys = list(redis_client.scan_iter(pattern))
    except Exception as scan_err:
        logger.warning(f'[Inbox] Redis scan failed: {scan_err}')
        raw_keys = []

    from django_tenants.utils import schema_context
    from orders.models import Order

    conversations = []
    seen_wa_ids = set()

    for raw_key in raw_keys:
        try:
            raw_key_str = raw_key.decode() if isinstance(raw_key, bytes) else raw_key

            # Extract the logical Django cache key by finding the wa_session marker
            wa_session_marker = f'wa_session:{phone_number_id}:'
            marker_idx = raw_key_str.find(wa_session_marker)
            if marker_idx == -1:
                continue

            wa_id = raw_key_str[marker_idx + len(wa_session_marker):]
            if not wa_id or wa_id in seen_wa_ids:
                continue

            logical_key = f'wa_session:{phone_number_id}:{wa_id}'

            # Use Django's cache.get() which handles deserialization (pickle/json)
            session = cache.get(logical_key)
            if not session:
                continue
            if isinstance(session, str):
                import json as _json
                session = _json.loads(session)

            messages = session.get('messages', [])
            if not messages:
                continue

            seen_wa_ids.add(wa_id)
            customer_name = session.get('customer_name') or ''
            customer_phone = session.get('customer_phone') or wa_id

            # Lookup recent orders for this customer from the database
            latest_order_info = None
            try:
                with schema_context(tenant.schema_name):
                    clean_phone = wa_id[-9:] if len(wa_id) >= 9 else wa_id
                    matched_order = Order.objects.filter(customer_phone__icontains=clean_phone).first()
                    if matched_order:
                        if not customer_name or customer_name == wa_id:
                            customer_name = matched_order.customer_name or customer_name
                        latest_order_info = {
                            'order_number': matched_order.order_number,
                            'status': matched_order.status,
                            'total_amount': float(matched_order.total_amount),
                            'created_at': matched_order.created_at.isoformat(),
                        }
            except Exception as order_err:
                logger.warning(f'[Inbox] Failed to fetch order info for {wa_id}: {order_err}')

            last_msg = messages[-1] if messages else {}
            conversations.append({
                'wa_id': wa_id,
                'customer_name': customer_name or wa_id,
                'customer_phone': customer_phone,
                'last_message': last_msg.get('content', '')[:120],
                'last_message_role': last_msg.get('role', 'user'),
                'message_count': len(messages),
                'is_owner': session.get('is_owner', False),
                'latest_order': latest_order_info,
            })
        except Exception as e:
            logger.warning(f'[Inbox] Failed to parse session: {e}')
            continue

    # Also add past customer orders that might not have an active Redis session
    try:
        with schema_context(tenant.schema_name):
            recent_orders = Order.objects.exclude(customer_phone='').order_by('-created_at')[:20]
            for ord_obj in recent_orders:
                c_phone = ord_obj.customer_phone.strip()
                # Clean phone into a pseudo wa_id if valid
                digits = ''.join(filter(str.isdigit, c_phone))
                if len(digits) >= 9:
                    c_wa_id = f'233{digits[-9:]}'
                    if c_wa_id not in seen_wa_ids:
                        seen_wa_ids.add(c_wa_id)
                        conversations.append({
                            'wa_id': c_wa_id,
                            'customer_name': ord_obj.customer_name or c_phone,
                            'customer_phone': c_phone,
                            'last_message': f'Order #{ord_obj.order_number} ({ord_obj.status}) - GHS {float(ord_obj.total_amount):.2f}',
                            'last_message_role': 'model',
                            'message_count': 1,
                            'is_owner': False,
                            'latest_order': {
                                'order_number': ord_obj.order_number,
                                'status': ord_obj.status,
                                'total_amount': float(ord_obj.total_amount),
                                'created_at': ord_obj.created_at.isoformat(),
                            }
                        })
    except Exception as e:
        logger.warning(f'[Inbox] Failed to load DB order conversations: {e}')

    # Sort: conversations with most messages / latest activity first
    conversations.sort(key=lambda c: c['message_count'], reverse=True)
    return Response({'conversations': conversations, 'phone_number_id': phone_number_id})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def inbox_conversation_detail(request, wa_id):
    """
    Return the full message history and order history for a specific WhatsApp conversation.
    """
    import json as _json
    from django.core.cache import cache
    from django_tenants.utils import schema_context
    from orders.models import Order

    tenant = _get_tenant_from_request(request)
    if not tenant:
        return Response({'error': 'Tenant not found'}, status=404)

    try:
        wa_account = TenantWhatsAppAccount.objects.get(tenant=tenant, is_active=True)
        phone_number_id = wa_account.phone_number_id
    except TenantWhatsAppAccount.DoesNotExist:
        phone_number_id = getattr(settings, 'META_PHONE_NUMBER_ID', '')

    # Use cache.get() with the logical key - Django handles pickle deserialization
    logical_key = f'wa_session:{phone_number_id}:{wa_id}'
    session = cache.get(logical_key)

    messages = []
    customer_name = wa_id
    customer_phone = wa_id
    is_owner = False

    if session:
        if isinstance(session, str):
            session = _json.loads(session)
        messages = session.get('messages', [])
        customer_name = session.get('customer_name') or wa_id
        customer_phone = session.get('customer_phone') or wa_id
        is_owner = session.get('is_owner', False)

    # Fetch all orders associated with this customer
    recent_orders = []
    try:
        with schema_context(tenant.schema_name):
            clean_phone = wa_id[-9:] if len(wa_id) >= 9 else wa_id
            db_orders = Order.objects.filter(customer_phone__icontains=clean_phone).prefetch_related('items').order_by('-created_at')[:10]
            for o in db_orders:
                if (not customer_name or customer_name == wa_id) and o.customer_name:
                    customer_name = o.customer_name
                recent_orders.append({
                    'id': o.id,
                    'order_number': o.order_number,
                    'status': o.status,
                    'order_type': o.order_type,
                    'total_amount': float(o.total_amount),
                    'payment_status': o.payment_status,
                    'payment_method': o.payment_method,
                    'created_at': o.created_at.isoformat(),
                    'items': [
                        {
                            'id': it.id,
                            'name': it.name,
                            'quantity': it.quantity,
                            'price': float(it.price),
                        }
                        for it in o.items.all()
                    ]
                })
    except Exception as e:
        logger.warning(f'[Inbox] Failed to load orders for {wa_id}: {e}')

    return Response({
        'wa_id': wa_id,
        'messages': messages,
        'customer_name': customer_name,
        'customer_phone': customer_phone,
        'is_owner': is_owner,
        'recent_orders': recent_orders,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def inbox_send_message(request, wa_id):
    """
    Send a manual message from the console to a specific WhatsApp customer.
    Bypasses the AI agent — this is a direct human reply.
    Body: { "message": "Hello, your order is ready!" }
    """
    import json
    from django.core.cache import cache
    from . import client as wa_client
    from .session import load_session, save_session, append_message

    message_text = request.data.get('message', '').strip()
    if not message_text:
        return Response({'error': 'Message text is required'}, status=400)

    tenant = _get_tenant_from_request(request)
    if not tenant:
        return Response({'error': 'Tenant not found'}, status=404)

    try:
        wa_account = TenantWhatsAppAccount.objects.get(tenant=tenant, is_active=True)
        phone_number_id = wa_account.phone_number_id
        access_token = wa_account.access_token
    except TenantWhatsAppAccount.DoesNotExist:
        phone_number_id = getattr(settings, 'META_PHONE_NUMBER_ID', '')
        access_token = getattr(settings, 'META_ACCESS_TOKEN', '')

    if not phone_number_id or not access_token:
        return Response({'error': 'WhatsApp account not configured'}, status=503)

    try:
        wa_client.send_text(phone_number_id, access_token, wa_id, message_text)
    except Exception as e:
        logger.error(f'[Inbox] Failed to send manual message to {wa_id}: {e}')
        return Response({'error': str(e)}, status=502)

    # Append to Redis session so it appears in the conversation thread
    session = load_session(phone_number_id, wa_id)
    append_message(session, 'owner', message_text)
    save_session(phone_number_id, wa_id, session)

    logger.info(f'[Inbox] Manual message sent to {wa_id} by {request.user}')
    return Response({'success': True, 'message': message_text})

