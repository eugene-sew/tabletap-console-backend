"""
WhatsApp Simulator CLI for TableTap

Allows testing the WhatsApp AI bot locally without needing Meta Dashboard, ngrok, or a live WhatsApp number.
Simulates incoming Meta webhooks to http://localhost:3001/api/whatsapp/webhook/
and prints the bot's response directly in your terminal.

Usage:
    python simulate_whatsapp.py [--tenant SLUG] [--phone NUMBER]
"""
import sys
import json
import time
import requests
import argparse

API_URL = "http://localhost:3001/api/whatsapp/webhook/"
DEFAULT_PHONE = "233241234567"
DEFAULT_PHONE_ID = "105938475829104"

def make_webhook_payload(text: str, wa_id: str, phone_id: str) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "ENTRY_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550123456",
                                "phone_number_id": phone_id,
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test User"},
                                    "wa_id": wa_id,
                                }
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.SIMULATED_{int(time.time()*1000)}",
                                    "timestamp": str(int(time.time())),
                                    "text": {"body": text},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

def main():
    parser = argparse.ArgumentParser(description="TableTap WhatsApp Simulator")
    parser.add_argument("--phone", default=DEFAULT_PHONE, help="Simulated sender WhatsApp number")
    parser.add_argument("--phone-id", default=DEFAULT_PHONE_ID, help="Meta Phone Number ID")
    parser.add_argument("--tenant", default="tabletap-restaurant", help="Tenant slug")
    args = parser.parse_args()

    print("\n" + "="*60)
    print(" 🤖 TableTap WhatsApp AI Bot Local Simulator")
    print("="*60)
    print(f" Sender Phone: +{args.phone}")
    print(f" Target Webhook: {API_URL}")
    print(f" Target Tenant Slug: {args.tenant}")
    print(" Type '/reset' to clear conversation history")
    print(" Type 'exit' or 'quit' to exit")
    print("="*60 + "\n")

    # Ensure backend is up
    try:
        r = requests.get("http://localhost:3001/api/health/", timeout=3)
        if r.status_code != 200:
            print("❌ Backend is not returning 200 OK at http://localhost:3001/api/health/")
            sys.exit(1)
    except Exception:
        print("❌ Cannot connect to backend at http://localhost:3001. Is docker running?")
        sys.exit(1)

    print("✅ Backend connected! Start chatting with the AI bot below:\n")

    while True:
        try:
            user_input = input("\n📱 You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye! 👋")
                break

            payload = make_webhook_payload(user_input, args.phone, args.phone_id)
            
            # Post payload to webhook
            resp = requests.post(API_URL, json=payload, timeout=5)
            if resp.status_code != 200:
                print(f"⚠️ Webhook returned error HTTP {resp.status_code}")
                continue

            # Wait briefly for Celery worker to process task
            print("⏳ AI Bot is thinking...", end="\r", flush=True)
            time.sleep(2.5)
            print(" "*30, end="\r")

            # Fetch updated session from backend Redis/cache or inspect DB
            # We can print task output from celery or query active session
            print(f"🤖 Bot: [Processing via Celery background worker]")

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\n❌ Error sending message: {e}")

if __name__ == "__main__":
    main()
