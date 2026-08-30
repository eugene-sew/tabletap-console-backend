"""
WhatsApp Cloud API client.

Handles all outbound messaging to Meta's Cloud API using per-tenant credentials.
"""
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = 'v21.0'
GRAPH_API_BASE = f'https://graph.facebook.com/{GRAPH_API_VERSION}'


def _headers(access_token: str) -> dict:
    return {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }


def _post(phone_number_id: str, access_token: str, payload: dict) -> dict:
    """Send a message via the Cloud API. Returns the API response JSON."""
    url = f'{GRAPH_API_BASE}/{phone_number_id}/messages'
    try:
        resp = requests.post(url, json=payload, headers=_headers(access_token), timeout=15)
        if not resp.ok:
            logger.error(
                f'[WhatsApp] Meta API error {resp.status_code}: {resp.text[:1000]}'
            )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f'[WhatsApp] Failed to send message: {e}')
        raise


def send_text(phone_number_id: str, access_token: str, to: str, body: str) -> dict:
    """Send a plain text message."""
    # WhatsApp max message length is 4096 chars. Strip null bytes that cause 400s.
    body = (body or '').replace('\x00', '').strip()
    if len(body) > 4096:
        body = body[:4090] + '...'
    if not body:
        body = '...'
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'text',
        'text': {'preview_url': False, 'body': body},
    }
    return _post(phone_number_id, access_token, payload)


def send_reply_buttons(
    phone_number_id: str,
    access_token: str,
    to: str,
    body: str,
    buttons: list[dict],
) -> dict:
    """
    Send up to 3 quick-reply buttons.
    buttons: [{'id': 'btn_yes', 'title': 'Yes, confirm ✅'}, ...]
    """
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'button',
            'body': {'text': body},
            'action': {
                'buttons': [
                    {'type': 'reply', 'reply': {'id': b['id'], 'title': b['title'][:20]}}
                    for b in buttons[:3]
                ]
            },
        },
    }
    return _post(phone_number_id, access_token, payload)


def send_list_message(
    phone_number_id: str,
    access_token: str,
    to: str,
    header: str,
    body: str,
    button_label: str,
    sections: list[dict],
) -> dict:
    """
    Send a list message (up to 10 items across sections).
    sections: [{'title': 'Section', 'rows': [{'id': 'id1', 'title': 'Item', 'description': ''}]}]
    """
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'interactive',
        'interactive': {
            'type': 'list',
            'header': {'type': 'text', 'text': header},
            'body': {'text': body},
            'action': {
                'button': button_label[:20],
                'sections': sections,
            },
        },
    }
    return _post(phone_number_id, access_token, payload)


def send_image(
    phone_number_id: str,
    access_token: str,
    to: str,
    image_url: str,
    caption: str = '',
) -> dict:
    """Send an image message with optional caption."""
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': to,
        'type': 'image',
        'image': {'link': image_url, 'caption': caption},
    }
    return _post(phone_number_id, access_token, payload)


def send_template(
    phone_number_id: str,
    access_token: str,
    to: str,
    template_name: str,
    language_code: str = 'en_US',
    components: list | None = None,
) -> dict:
    """
    Send a pre-approved Message Template (for outbound notifications outside 24h window).
    """
    payload = {
        'messaging_product': 'whatsapp',
        'to': to,
        'type': 'template',
        'template': {
            'name': template_name,
            'language': {'code': language_code},
            'components': components or [],
        },
    }
    return _post(phone_number_id, access_token, payload)


def mark_as_read(phone_number_id: str, access_token: str, message_id: str) -> dict:
    """Send a read receipt for a message."""
    payload = {
        'messaging_product': 'whatsapp',
        'status': 'read',
        'message_id': message_id,
    }
    return _post(phone_number_id, access_token, payload)
