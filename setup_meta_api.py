"""
Automated Meta Graph API Setup Script for TableTap

Performs all Meta WhatsApp API setup programmatically using your Meta Access Token.
Zero manual clicking in the Meta Developer Dashboard required!

What this script does:
1. Verifies your Meta Access Token
2. Fetches your WhatsApp Business Account (WABA) ID & Phone Number ID
3. Automatically writes META_PHONE_NUMBER_ID & META_ACCESS_TOKEN into your backend .env
4. Configures your Meta Webhook URL & verify token via Graph API

Usage:
    python setup_meta_api.py --token "YOUR_META_ACCESS_TOKEN" [--webhook-url "HTTPS_WEBHOOK_URL"]
"""
import os
import sys
import re
import requests
import argparse

GRAPH_BASE = "https://graph.facebook.com/v21.0"
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

def update_env_file(key: str, value: str):
    """Update or add a key=value pair in .env"""
    if not os.path.exists(ENV_PATH):
        print(f"⚠️ .env file not found at {ENV_PATH}")
        return

    with open(ENV_PATH, "r") as f:
        content = f.read()

    pattern = re.compile(rf"^{key}=.*$", re.MULTILINE)
    new_line = f"{key}={value}"

    if pattern.search(content):
        content = pattern.sub(new_line, content)
    else:
        content += f"\n{new_line}\n"

    with open(ENV_PATH, "w") as f:
        f.write(content)

    print(f"  ✓ Updated .env: {key}={value[:15]}...")

def main():
    parser = argparse.ArgumentParser(description="Automated Meta WhatsApp Setup")
    parser.add_argument("--token", required=True, help="Meta Access Token (System User or Developer Token)")
    parser.add_argument("--app-id", help="Meta App ID (optional)")
    parser.add_argument("--webhook-url", help="Public HTTPS Webhook URL (e.g. https://xxxx.orb.local/api/whatsapp/webhook/)")
    parser.add_argument("--verify-token", default="tabletap_wa_verify_2026", help="Webhook verify token")
    args = parser.parse_args()

    print("\n" + "="*60)
    print(" 🚀 TableTap Meta WhatsApp Automated API Setup")
    print("="*60 + "\n")

    token = args.token.strip()

    # 1. Verify Token & Get Debug Info
    print("1️⃣  Verifying Meta Access Token...")
    try:
        r = requests.get(f"{GRAPH_BASE}/me", params={"access_token": token}, timeout=10)
        if r.status_code != 200:
            print(f"❌ Invalid Access Token: {r.json().get('error', {}).get('message', 'Unknown error')}")
            sys.exit(1)
        user_data = r.json()
        print(f"  ✓ Token valid! Name/ID: {user_data.get('name', 'N/A')} ({user_data.get('id', '')})")
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)

    # 2. Fetch WhatsApp Business Accounts
    print("\n2️⃣  Fetching WhatsApp Business Accounts & Phone Numbers...")
    phone_number_id = None
    waba_id = None

    try:
        r = requests.get(
            f"{GRAPH_BASE}/me/whatsapp_business_accounts",
            params={"access_token": token, "fields": "id,name,phone_numbers{id,display_phone_number}"},
            timeout=10,
        )
        data = r.json()
        accounts = data.get("data", [])
        if not accounts:
            print("⚠️ No WhatsApp Business Accounts associated with this token.")
        else:
            waba_id = accounts[0].get("id")
            phones = accounts[0].get("phone_numbers", {}).get("data", [])
            if phones:
                phone_number_id = phones[0].get("id")
                phone_display = phones[0].get("display_phone_number")
                print(f"  ✓ Found WABA ID: {waba_id}")
                print(f"  ✓ Found Phone Number ID: {phone_number_id} ({phone_display})")
    except Exception as e:
        print(f"⚠️ Could not fetch WABA data automatically: {e}")

    # Save credentials to .env
    print("\n3️⃣  Saving Credentials to backend .env...")
    update_env_file("META_ACCESS_TOKEN", token)
    if phone_number_id:
        update_env_file("META_PHONE_NUMBER_ID", phone_number_id)
    if args.verify_token:
        update_env_file("META_VERIFY_TOKEN", args.verify_token)

    # 4. Subscribe App to Webhooks (if app_id & webhook_url provided)
    if args.app_id and args.webhook_url:
        print("\n4️⃣  Subscribing App to WhatsApp Webhooks via API...")
        try:
            r = requests.post(
                f"{GRAPH_BASE}/{args.app_id}/subscriptions",
                data={
                    "object": "whatsapp_business_account",
                    "callback_url": args.webhook_url,
                    "verify_token": args.verify_token,
                    "fields": "messages",
                    "access_token": token,
                },
                timeout=10,
            )
            if r.status_code == 200 and r.json().get("success"):
                print("  ✓ Webhook successfully subscribed in Meta!")
            else:
                print(f"  ⚠️ Webhook subscription response: {r.text}")
        except Exception as e:
            print(f"  ⚠️ Webhook subscription failed: {e}")

    print("\n" + "="*60)
    print(" ✅ Setup Complete! Your .env file has been updated.")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
