"""
Gemini 2.5 Flash AI agent for WhatsApp conversations.

Two personas:
  - Customer agent: menu browsing, cart, order placement, tracking
  - Owner agent: metrics, live orders, status management

Uses native Gemini function calling (no LangGraph).
"""
import json
import logging
from django.conf import settings
from django.utils import timezone

import google.generativeai as genai

from . import tools as T
from .session import append_message

import re

logger = logging.getLogger(__name__)


def _format_for_whatsapp(text: str) -> str:
    """Format markdown text for clean WhatsApp display (convert **bold** and ## headers)."""
    if not text:
        return text
    # Convert markdown headers (# Header) to WhatsApp bold (*Header*)
    text = re.sub(r'^#{1,6}\s*(.+)$', r'*\1*', text, flags=re.MULTILINE)
    # Convert double asterisks (**bold**) to single asterisks (*bold*)
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    # Convert double underscores (__italic__) to single underscores (_italic_)
    text = re.sub(r'__(.*?)__', r'_\1_', text)
    return text


# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

def _get_gemini():
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('GEMINI_API_KEY is not configured')
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name='gemini-3.5-flash-lite',
        generation_config={'temperature': 0.4, 'max_output_tokens': 1024},
    )


# ---------------------------------------------------------------------------
# Tool schemas (Gemini function declarations)
# ---------------------------------------------------------------------------

CUSTOMER_TOOL_DECLARATIONS = [
    {
        'name': 'get_menu',
        'description': (
            'Fetch the restaurant menu. Use when the customer asks what food is available, '
            'wants to see the menu, or asks about specific categories or dishes. '
            'Returns categories with items and prices.'
        ),
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'category_filter': {
                    'type': 'STRING',
                    'description': 'Optional category name to filter results. Leave empty for full menu.',
                }
            },
        },
    },
    {
        'name': 'get_item_details',
        'description': 'Search for a specific menu item by name. Use when customer asks about a specific dish.',
        'parameters': {
            'type': 'OBJECT',
            'required': ['item_name'],
            'properties': {
                'item_name': {'type': 'STRING', 'description': 'Name of the dish to look up'},
            },
        },
    },
    {
        'name': 'get_payment_info',
        'description': 'Get payment methods and MoMo details. Use when customer asks how to pay.',
        'parameters': {'type': 'OBJECT', 'properties': {}},
    },
    {
        'name': 'track_order',
        'description': (
            'Get the current status of an order. Use when the customer mentions an order number '
            'or asks where their food is or when it will be ready.'
        ),
        'parameters': {
            'type': 'OBJECT',
            'required': ['order_number'],
            'properties': {
                'order_number': {'type': 'STRING', 'description': 'The order number (e.g. WA-AB12CD)'},
            },
        },
    },
    {
        'name': 'confirm_order',
        'description': (
            'Called ONLY after you have shown the customer a full order summary AND they have replied '
            'with YES, Confirm, or an equivalent affirmation. '
            'NEVER call this without explicit customer confirmation. '
            'Pass the items ordered.'
        ),
        'parameters': {
            'type': 'OBJECT',
            'required': ['order_type', 'customer_name', 'customer_phone'],
            'properties': {
                'order_type': {
                    'type': 'STRING',
                    'enum': ['pickup', 'delivery', 'dine_in'],
                    'description': 'How the customer wants their order',
                },
                'customer_name': {'type': 'STRING'},
                'customer_phone': {'type': 'STRING'},
                'delivery_address': {'type': 'STRING', 'description': 'Required for delivery orders'},
                'delivery_notes': {'type': 'STRING'},
                'items': {
                    'type': 'ARRAY',
                    'description': 'List of items in the order: [{"name": "Item Name", "quantity": 1, "price": 45.0}]',
                    'items': {
                        'type': 'OBJECT',
                        'properties': {
                            'name': {'type': 'STRING'},
                            'quantity': {'type': 'NUMBER'},
                            'price': {'type': 'NUMBER'},
                        },
                    },
                },
            },
        },
    },
]

OWNER_TOOL_DECLARATIONS = [
    {
        'name': 'get_metrics_summary',
        'description': "Get sales metrics, revenue, order counts, payment method breakdown, AOV, and top-selling items across any historical period (today, yesterday, this_week, last_week, this_month, last_month, this_year, all_time, or custom start_date/end_date).",
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'period': {
                    'type': 'STRING',
                    'enum': ['today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month', 'this_year', 'all_time'],
                    'description': "Time window for metrics. E.g. 'yesterday', 'last_week', 'last_month', 'all_time'. Defaults to 'today'.",
                },
                'start_date': {
                    'type': 'STRING',
                    'description': 'Optional start date in YYYY-MM-DD format for custom historical ranges.',
                },
                'end_date': {
                    'type': 'STRING',
                    'description': 'Optional end date in YYYY-MM-DD format for custom historical ranges.',
                },
            },
        },
    },
    {
        'name': 'search_historical_orders',
        'description': 'Search, filter, and inspect past orders by date, customer name, phone number, order number, or status.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'query': {'type': 'STRING', 'description': 'Search keyword (order #, customer name, or dish name)'},
                'date': {'type': 'STRING', 'description': 'Specific date to look up in YYYY-MM-DD format'},
                'status': {'type': 'STRING', 'description': 'Filter by status: completed, cancelled, pending, preparing, ready'},
                'customer_phone': {'type': 'STRING', 'description': 'Customer phone number to search for past orders'},
                'limit': {'type': 'INTEGER', 'description': 'Maximum number of orders to return (default 10)'},
            },
        },
    },
    {
        'name': 'get_top_selling_items',
        'description': 'Get a ranked leaderboard of top-selling dishes with quantities and revenue over any historical timeframe.',
        'parameters': {
            'type': 'OBJECT',
            'properties': {
                'period': {
                    'type': 'STRING',
                    'enum': ['today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month', 'all_time'],
                    'description': "Timeframe for the top-seller leaderboard. Defaults to 'this_month'.",
                },
                'limit': {'type': 'INTEGER', 'description': 'Number of items to rank (default 5)'},
            },
        },
    },
    {
        'name': 'get_live_orders',
        'description': 'Get all active (pending/preparing/ready) orders right now with wait times.',
        'parameters': {'type': 'OBJECT', 'properties': {}},
    },
    {
        'name': 'update_order_status',
        'description': 'Change the status of an order (e.g. mark as ready, completed, cancelled).',
        'parameters': {
            'type': 'OBJECT',
            'required': ['order_number', 'new_status'],
            'properties': {
                'order_number': {'type': 'STRING'},
                'new_status': {
                    'type': 'STRING',
                    'enum': ['pending', 'preparing', 'ready', 'completed', 'cancelled'],
                },
            },
        },
    },
    {
        'name': 'get_menu',
        'description': 'View the full current restaurant menu with categories, items, prices, and availability.',
        'parameters': {'type': 'OBJECT', 'properties': {}},
    },
    {
        'name': 'add_menu_item',
        'description': 'Add a new item to the restaurant menu. If the category does not exist, it is automatically created.',
        'parameters': {
            'type': 'OBJECT',
            'required': ['name', 'price', 'category_name'],
            'properties': {
                'name': {'type': 'STRING', 'description': 'Name of the new menu item'},
                'price': {'type': 'NUMBER', 'description': 'Price in local currency (e.g. 65.00)'},
                'category_name': {'type': 'STRING', 'description': 'Category to place item under (e.g. Mains, Drinks, Grills). Created automatically if new.'},
                'description': {'type': 'STRING', 'description': 'Optional description of the dish'},
                'is_available': {'type': 'BOOLEAN', 'description': 'True if available now, False if 86ed'},
            },
        },
    },
    {
        'name': 'update_menu_item',
        'description': 'Update price, name, description, category, or availability of an existing menu item.',
        'parameters': {
            'type': 'OBJECT',
            'required': ['item_name'],
            'properties': {
                'item_name': {'type': 'STRING', 'description': 'Name of the item to find and update'},
                'new_price': {'type': 'NUMBER', 'description': 'New price in local currency'},
                'new_name': {'type': 'STRING', 'description': 'New name for the item if renaming'},
                'description': {'type': 'STRING', 'description': 'New description for the dish'},
                'category_name': {'type': 'STRING', 'description': 'New category for the item (created automatically if new)'},
                'available': {'type': 'BOOLEAN', 'description': 'True = available, False = paused (86ed)'},
            },
        },
    },
    {
        'name': 'delete_menu_item',
        'description': 'Permanently delete a menu item from the restaurant menu.',
        'parameters': {
            'type': 'OBJECT',
            'required': ['item_name'],
            'properties': {
                'item_name': {'type': 'STRING', 'description': 'Name of the item to delete'},
            },
        },
    },
    {
        'name': 'toggle_item_availability',
        'description': 'Pause or resume a menu item. Use when owner says "pause the jollof", "86 the chicken", or "bring back tilapia".',
        'parameters': {
            'type': 'OBJECT',
            'required': ['item_name', 'available'],
            'properties': {
                'item_name': {'type': 'STRING'},
                'available': {'type': 'BOOLEAN', 'description': 'True = available, False = paused'},
            },
        },
    },
]


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

def _customer_system_prompt(tenant) -> str:
    settings_data = tenant.settings or {}
    currency = tenant.currency or 'GHS'
    return f"""You are the WhatsApp ordering assistant for *{tenant.name}*.
Your job is to help customers browse the menu and place food orders.

Restaurant: {tenant.name}
Location: {tenant.address or 'See our social media for directions'}
Currency: {currency}
Current time: {timezone.now().strftime('%H:%M, %A %d %B %Y')}

RULES — follow these strictly:
1. Be friendly, warm, and concise. Use emojis naturally but don't overdo it.
2. Always use the get_menu tool to fetch real menu data — never invent items or prices.
3. To add items to the cart: keep track in your responses, do not call any tool.
4. Before placing an order, ALWAYS show the customer a full summary (items, quantities, prices, total) and ask them to reply YES to confirm.
5. NEVER call confirm_order unless the customer has explicitly said YES, Confirm, or equivalent.
6. If asked about anything unrelated to food/orders, politely redirect.
7. Always show prices in {currency}.
8. Payment methods available: {', '.join(settings_data.get('paymentMethods', ['cash']))}.
9. If customer says /reset or start over, acknowledge and start fresh.
10. Keep responses under 300 words — WhatsApp is a chat, not an essay."""


def _owner_system_prompt(tenant) -> str:
    currency = tenant.currency or 'GHS'
    return f"""You are the intelligent WhatsApp Copilot & Business Assistant for the owner/manager of *{tenant.name}*.

Restaurant: {tenant.name}
Currency: {currency}
Current time: {timezone.now().strftime('%H:%M, %A %d %B %Y')}

YOU HAVE FULL ACCESS TO LIVE AND HISTORICAL RESTAURANT DATA VIA YOUR TOOLS:
1. **Historical & Current Financial Analytics**:
   - You HAVE direct access to past records, archive data, and historical sales.
   - For historical queries (*"yesterday"*, *"last week"*, *"last month"*, *"all time"*, or specific dates), ALWAYS call `get_metrics_summary` with `period` or `start_date`/`end_date`.
   - For top-seller leaderboards, ALWAYS call `get_top_selling_items(period=...)`.
   - NEVER tell the owner you lack historical archives or past sales data.
2. **Order Lookups & History**:
   - Look up past orders by customer, date, or order number with `search_historical_orders`.
3. **Live Orders & Kitchen Status**:
   - When asked about *"new orders"*, *"unaccepted orders"*, *"pending orders"*, or *"kitchen status"*, ALWAYS call `get_live_orders`.
   - Group and report orders by status: 🟡 Pending (needs acceptance), 🔵 Preparing (in kitchen), 🟢 Ready (for pickup).
4. **Menu Management**:
   - Add new items with `add_menu_item` (categories are created automatically if new).
   - Update prices, descriptions, names, or categories with `update_menu_item`.
   - 86/pause items with `toggle_item_availability`.
   - View menu with `get_menu`.
5. **Order Control**:
   - Change order statuses with `update_order_status` (e.g. mark ready, completed, cancelled).

RULES:
- Be fast, professional, and clear. Format numbers with emojis (💰, 📦, 🍳, ⏳, 🏆).
- Confirm every menu addition or price change with the exact details updated.
- Always use tools to fetch actual numbers — never guess or refuse valid requests."""


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

def _dispatch_customer_tool(name: str, args: dict, tenant_slug: str, session: dict) -> tuple[str, dict]:
    """Execute a customer tool call and return (result_str, updated_session)."""
    if name == 'get_menu':
        result = T.get_menu(tenant_slug, args.get('category_filter', ''))
    elif name == 'get_item_details':
        result = T.get_item_details(tenant_slug, args.get('item_name', ''))
    elif name == 'get_payment_info':
        result = T.get_payment_info(tenant_slug)
    elif name == 'track_order':
        result = T.track_order(tenant_slug, args.get('order_number', ''))
    elif name == 'confirm_order':
        cart = args.get('items') or session.get('cart', [])
        if not cart:
            # Fallback: get items from menu if not in cart or args
            menu_res = T.get_menu(tenant_slug)
            all_items = []
            for cat in menu_res.get('categories', []):
                all_items.extend(cat.get('items', []))
            if all_items:
                cart = [{
                    'menu_item_id': str(all_items[0]['id']),
                    'name': all_items[0]['name'],
                    'quantity': 1,
                    'price': float(all_items[0]['price']),
                }]

        result = T.place_order(
            tenant_slug=tenant_slug,
            items=cart,
            order_type=args.get('order_type', 'pickup'),
            customer_name=args.get('customer_name', session.get('customer_name', 'Guest')),
            customer_phone=args.get('customer_phone', session.get('customer_phone', '')),
            delivery_address=args.get('delivery_address', session.get('delivery_address', '')),
            delivery_notes=args.get('delivery_notes', ''),
        )
        if result.get('success'):
            session['cart'] = []
            session['awaiting_confirmation'] = False
    else:
        result = {'error': f'Unknown tool: {name}'}

    return json.dumps(result, default=str), session


def _dispatch_owner_tool(name: str, args: dict, tenant_slug: str) -> str:
    if name == 'get_metrics_summary':
        result = T.get_metrics_summary(
            tenant_slug=tenant_slug,
            period=args.get('period', 'today'),
            start_date=args.get('start_date'),
            end_date=args.get('end_date'),
        )
    elif name == 'search_historical_orders':
        result = T.search_historical_orders(
            tenant_slug=tenant_slug,
            query=args.get('query'),
            date=args.get('date'),
            status=args.get('status'),
            customer_phone=args.get('customer_phone'),
            limit=args.get('limit', 10),
        )
    elif name == 'get_top_selling_items':
        result = T.get_top_selling_items(
            tenant_slug=tenant_slug,
            period=args.get('period', 'this_month'),
            limit=args.get('limit', 5),
        )
    elif name == 'get_live_orders':
        result = T.get_live_orders(tenant_slug)
    elif name == 'update_order_status':
        result = T.update_order_status_tool(
            tenant_slug, args.get('order_number', ''), args.get('new_status', '')
        )
    elif name == 'get_menu':
        result = T.get_menu(tenant_slug)
    elif name == 'add_menu_item':
        result = T.add_menu_item_tool(
            tenant_slug=tenant_slug,
            name=args.get('name', ''),
            price=float(args.get('price', 0)),
            category_name=args.get('category_name', 'General'),
            description=args.get('description', ''),
            is_available=args.get('is_available', True),
        )
    elif name == 'update_menu_item':
        result = T.update_menu_item_tool(
            tenant_slug=tenant_slug,
            item_name=args.get('item_name', ''),
            new_price=float(args.get('new_price')) if args.get('new_price') is not None else None,
            new_name=args.get('new_name'),
            description=args.get('description'),
            category_name=args.get('category_name'),
            available=args.get('available'),
        )
    elif name == 'delete_menu_item':
        result = T.delete_menu_item_tool(tenant_slug, args.get('item_name', ''))
    elif name == 'toggle_item_availability':
        result = T.toggle_item_availability_tool(
            tenant_slug, args.get('item_name', ''), args.get('available', True)
        )
    else:
        result = {'error': f'Unknown tool: {name}'}
    return json.dumps(result, default=str)


# ---------------------------------------------------------------------------
# Message pre-processing — cart intent detection
# ---------------------------------------------------------------------------

def _detect_confirmation(text: str) -> bool:
    """True if the customer's message is an explicit confirmation."""
    affirmations = ['yes', 'confirm', 'yep', 'yup', 'sure', 'ok', 'okay', 'proceed',
                    'go ahead', 'place order', 'order now', '✅', 'yeah', 'correct']
    t = text.lower().strip()
    return any(t == a or t.startswith(a) for a in affirmations)


# ---------------------------------------------------------------------------
# Public agent entry points
# ---------------------------------------------------------------------------

def run_customer_agent(message: str, session: dict, tenant) -> tuple[str, dict]:
    """
    Run one turn of the customer agent.
    Returns (reply_text, updated_session).
    """
    tenant_slug = tenant.slug
    model = _get_gemini()

    # If awaiting confirmation and user says yes → mark confirmed
    if session.get('awaiting_confirmation') and _detect_confirmation(message):
        # Let the LLM know to call confirm_order
        pass
    elif session.get('awaiting_confirmation') and not _detect_confirmation(message):
        # User said something else — cancel pending confirmation
        session['awaiting_confirmation'] = False

    # Build conversation history for Gemini.
    # Gemini only accepts 'user' and 'model' roles.
    # Console 'owner' replies are treated as 'model' (the restaurant's voice).
    history = []
    for msg in session.get('messages', []):
        gemini_role = 'model' if msg['role'] in ('model', 'owner') else 'user'
        history.append({
            'role': gemini_role,
            'parts': [msg['content']],
        })

    # Build cart context string for the system prompt
    cart = session.get('cart', [])
    cart_context = ''
    if cart:
        cart_lines = '\n'.join(
            f"  - {item['name']} x{item['quantity']} @ {item['price']}" for item in cart
        )
        cart_context = f'\n\nCurrent cart:\n{cart_lines}'

    system = _customer_system_prompt(tenant) + cart_context
    if session.get('awaiting_confirmation'):
        system += '\n\nIMPORTANT: Customer is ready to confirm. If they say YES, call the confirm_order tool immediately.'

    tools = CUSTOMER_TOOL_DECLARATIONS

    try:
        chat = model.start_chat(history=history)
        # Include system instruction inline on first or every turn
        response = chat.send_message(
            [system + '\n\nCustomer message: ' + message] if not history else message,
            tools=tools,
        )

        # Handle function calls (tool use loop — max 3 rounds)
        reply = ''
        for _ in range(3):
            part = response.candidates[0].content.parts[0]
            if hasattr(part, 'function_call') and part.function_call.name:
                fc = part.function_call
                args = dict(fc.args)
                logger.info(f'[Agent] Customer tool call: {fc.name}({args})')
                tool_result, session = _dispatch_customer_tool(fc.name, args, tenant_slug, session)
                response = chat.send_message(
                    genai.protos.Content(
                        parts=[genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=fc.name,
                                response={'result': tool_result},
                            )
                        )],
                        role='user',
                    )
                )
            else:
                reply = part.text
                break

        if not reply:
            reply = response.candidates[0].content.parts[0].text

    except Exception as e:
        logger.error(f'[Agent] Gemini error: {e}')
        reply = 'Sorry, I\'m having a moment 🤔 Please try again in a second.'

    reply = _format_for_whatsapp(reply)
    # Update session
    append_message(session, 'user', message)
    append_message(session, 'model', reply)

    # Detect if this reply is an order summary (set awaiting_confirmation)
    summary_keywords = ['total:', 'total amount', 'confirm your order', 'reply yes', 'type yes']
    if any(kw in reply.lower() for kw in summary_keywords):
        session['awaiting_confirmation'] = True

    return reply, session


def run_owner_agent(message: str, session: dict, tenant) -> tuple[str, dict]:
    """
    Run one turn of the owner agent.
    Returns (reply_text, updated_session).
    """
    tenant_slug = tenant.slug
    model = _get_gemini()

    history = []
    for msg in session.get('messages', []):
        gemini_role = 'model' if msg['role'] in ('model', 'owner') else 'user'
        history.append({
            'role': gemini_role,
            'parts': [msg['content']],
        })

    tools = OWNER_TOOL_DECLARATIONS

    try:
        chat = model.start_chat(history=history)
        system = _owner_system_prompt(tenant)
        prompt_with_system = f"{system}\n\nOwner message: {message}"
        response = chat.send_message(prompt_with_system, tools=tools)

        reply = ''
        for _ in range(3):
            part = response.candidates[0].content.parts[0]
            if hasattr(part, 'function_call') and part.function_call.name:
                fc = part.function_call
                args = dict(fc.args)
                logger.info(f'[Agent] Owner tool call: {fc.name}({args})')
                tool_result = _dispatch_owner_tool(fc.name, args, tenant_slug)
                response = chat.send_message(
                    genai.protos.Content(
                        parts=[genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=fc.name,
                                response={'result': tool_result},
                            )
                        )],
                        role='user',
                    )
                )
            else:
                reply = part.text
                break

        if not reply:
            reply = response.candidates[0].content.parts[0].text

    except Exception as e:
        logger.error(f'[Agent] Owner Gemini error: {e}')
        reply = 'Having trouble connecting right now. Try again in a moment.'

    reply = _format_for_whatsapp(reply)
    append_message(session, 'user', message)
    append_message(session, 'model', reply)
    return reply, session
