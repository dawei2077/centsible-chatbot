import sys
import argparse
import database
from sender import send_imessage

def text_first(phone_number: str, name: str = None, message: str = None):
    """
    Sends an outbound text to initiate a conversation with a new user.
    """
    clean_phone = phone_number.strip()
    if not clean_phone.startswith("+"):
        # Default to +1 if 10-digit US number
        digits = "".join(filter(str.isdigit, clean_phone))
        if len(digits) == 10:
            clean_phone = "+1" + digits
        elif len(digits) == 11 and digits.startswith("1"):
            clean_phone = "+" + digits

    if name and name.strip():
        clean_name = name.strip()
        database.set_user_name(clean_phone, clean_name)
    else:
        clean_name = database.get_user_name(clean_phone)

    if message and message.strip():
        text_to_send = message.strip()
    elif clean_name:
        text_to_send = (
            f"Hey {clean_name}! 👋 I'm Centsible, your personal AI financial advisor. "
            "Text me anytime with receipts, purchases, or budgeting questions to keep your savings on track!"
        )
    else:
        text_to_send = (
            "Hey there! 👋 I'm Centsible, your personal AI financial advisor. "
            "I'm here to help you budget with the 50/30/20 rule, track expenses, and crush your savings goals. "
            "What should I call you?"
        )

    print("=" * 60)
    print("🚀 INITIATING OUTBOUND FIRST iMESSAGE")
    print("=" * 60)
    print(f"📱 Recipient: {clean_phone}")
    print(f"👤 Name:      {clean_name or '(Unknown - bot will ask)'}")
    print(f"💬 Message:   {text_to_send}")
    print("=" * 60)

    # Save to SQLite memory
    database.save_message(clean_phone, "advisor", text_to_send)

    # Dispatch via Photon proxy
    print("Sending message via Photon proxy...")
    send_imessage(clean_phone, text_to_send)
    print("✅ Outbound first message sent!")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Send an outbound first text from Centsible AI to any phone number.")
    parser.add_argument("phone", nargs="?", help="Recipient phone number (e.g. +16784622289)")
    parser.add_argument("name", nargs="?", help="Recipient name (optional)")
    parser.add_argument("message", nargs="?", help="Custom first message (optional)")
    args = parser.parse_args()

    phone = args.phone
    name = args.name
    message = args.message

    if not phone:
        print("\n=== Centsible: Text-First Tool ===")
        phone = input("Enter recipient phone number (e.g. +16784622289): ").strip()
        if not phone:
            print("❌ Phone number is required.")
            sys.exit(1)
        name_input = input("Enter recipient's name (optional, press Enter to skip): ").strip()
        name = name_input if name_input else None
        msg_input = input("Enter custom message (optional, press Enter for friendly default): ").strip()
        message = msg_input if msg_input else None

    text_first(phone, name, message)

if __name__ == "__main__":
    main()
