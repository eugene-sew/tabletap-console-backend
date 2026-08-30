"""
Redis-backed session management for WhatsApp conversations.

Each session is keyed on (phone_number_id, wa_id) and stores:
  - messages: list of {role, content} dicts (last 20, LIFO)
  - cart: list of {menu_item_id, name, quantity, price}
  - awaiting_confirmation: bool — order confirmation gate
  - order_type: 'pickup' | 'delivery'
  - customer_name, customer_phone, delivery_address: strings
  - is_owner: bool — whether this WA number is an owner session
  - owner_token: str | None — authenticated staff JWT

TTL: 1 hour sliding window (refreshed on every message).
"""
import json
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)

SESSION_TTL = 86400 * 30    # 30 days sliding window
MAX_MESSAGES = 50           # rolling window of conversation turns


def _key(phone_number_id: str, wa_id: str) -> str:
    return f'wa_session:{phone_number_id}:{wa_id}'


def load_session(phone_number_id: str, wa_id: str) -> dict:
    """Load session from Redis. Returns a fresh session dict if none exists."""
    key = _key(phone_number_id, wa_id)
    try:
        raw = cache.get(key)
        if raw:
            session = json.loads(raw) if isinstance(raw, str) else raw
            return session
    except Exception as e:
        logger.warning(f'[Session] Load failed for {key}: {e}')
    return _default_session()


def save_session(phone_number_id: str, wa_id: str, session: dict) -> None:
    """Persist session to Redis with sliding TTL."""
    key = _key(phone_number_id, wa_id)
    # Trim message history to MAX_MESSAGES
    messages = session.get('messages', [])
    if len(messages) > MAX_MESSAGES:
        session['messages'] = messages[-MAX_MESSAGES:]
    try:
        cache.set(key, json.dumps(session), timeout=SESSION_TTL)
    except Exception as e:
        logger.warning(f'[Session] Save failed for {key}: {e}')


def clear_session(phone_number_id: str, wa_id: str) -> None:
    """Delete a session (e.g. after order placed or user says /reset)."""
    key = _key(phone_number_id, wa_id)
    cache.delete(key)


def append_message(session: dict, role: str, content: str) -> dict:
    """
    Append a message turn to session history.
    role: 'user' | 'model'
    """
    session.setdefault('messages', [])
    session['messages'].append({'role': role, 'content': content})
    return session


def _default_session() -> dict:
    return {
        'messages': [],
        'cart': [],
        'awaiting_confirmation': False,
        'order_type': None,
        'customer_name': '',
        'customer_phone': '',
        'delivery_address': '',
        'is_owner': False,
        'owner_token': None,
    }
