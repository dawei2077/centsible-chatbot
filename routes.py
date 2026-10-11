from fastapi import APIRouter, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import logging
from parser import process_media
from sanitizer import sanitize_text
from advisor import analyze_finances
from sender import send_imessage, send_tapback
import database

router = APIRouter()
logger = logging.getLogger(__name__)

class WebhookPayload(BaseModel):
    phone_number: str
    text: Optional[str] = None
    media_url: Optional[str] = None
    media_base64: Optional[str] = None
    media_mime_type: Optional[str] = None
    message_id: Optional[str] = None

async def process_message_task(payload: WebhookPayload):
    try:
        # 1. Strictly ignore completely empty events (e.g. read receipts or reaction events)
        has_text = bool(payload.text and payload.text.strip())
        has_media = bool((payload.media_url and payload.media_url.strip()) or (payload.media_base64 and payload.media_base64.strip()))
        if not has_text and not has_media:
            logger.info(f"Ignored event with no text or media from {payload.phone_number}.")
            return

        # 2. Prevent infinite loops if Photon echoes ANY of our own outbound messages back
        if payload.text:
            text_strip = payload.text.strip()
            text_lower = text_strip.lower()
            if (
                text_lower.startswith("error")
                or "error contacting" in text_lower
                or "welcome to centsible" in text_lower
                or "🚨 unprompted alert 🚨" in text_lower
                or "opted out of the 8 am" in text_lower
                or "opted back in" in text_lower
                or text_strip.startswith("**")
            ):
                logger.info(f"Ignored echo of bot message from {payload.phone_number}.")
                return

        if payload.message_id:
            # Send an initial reaction (e.g., "!" or processing indicator)
            send_tapback(payload.phone_number, payload.message_id, "!")
            
        # 3. Check for opt-out/opt-in commands
        if payload.text:
            text_upper = payload.text.strip().upper()
            if text_upper in ["STOP", "OPTOUT", "OPT OUT", "UNSUBSCRIBE"]:
                database.opt_out_user(payload.phone_number)
                send_imessage(payload.phone_number, "You have opted out of notifications. You can still message me anytime for 50/30/20 advice or to look up deals! Text 'START' to opt back in.")
                return
            elif text_upper in ["START", "OPTIN", "OPT IN", "SUBSCRIBE"]:
                database.opt_in_user(payload.phone_number)
                send_imessage(payload.phone_number, "Welcome back! 🎉 You're re-subscribed. Text me anytime with purchases, receipts, or asking for deals!")
                return

        # 4. Check for direct name introduction (e.g., "I'm Leo", "My name is Sarah", or just "Leo")
        import re
        if payload.text and not database.get_user_name(payload.phone_number):
            raw_input = payload.text.strip().rstrip('.!')
            name_re = re.match(r'^(?:hi|hello|hey|yo)?\s*(?:i\'?m|i am|my name is|this is|call me|it\'?s)\s+([A-Za-z]{2,20})$', raw_input, re.IGNORECASE)
            if name_re:
                detected_name = name_re.group(1).capitalize()
                database.set_user_name(payload.phone_number, detected_name)
                logger.info(f"Learned user name via pattern match: {detected_name} for {payload.phone_number}")
            elif re.match(r'^[A-Z][a-z]{1,19}$', raw_input):
                database.set_user_name(payload.phone_number, raw_input)
                logger.info(f"Learned user name from single word: {raw_input} for {payload.phone_number}")

        # 5. Extract image bytes and media text
        image_bytes = None
        mime_type = payload.media_mime_type or "image/jpeg"

        if payload.media_base64:
            import base64
            try:
                image_bytes = base64.b64decode(payload.media_base64)
            except Exception as e:
                logger.error(f"Error decoding base64 image: {e}")

        if not image_bytes and payload.media_url:
            import os
            if os.path.exists(payload.media_url):
                try:
                    with open(payload.media_url, "rb") as f:
                        image_bytes = f.read()
                except Exception as e:
                    logger.error(f"Error reading local media file: {e}")

        # If it's a PDF document, extract text using parser.py
        extracted_text = ""
        if payload.media_url and payload.media_url.lower().endswith(".pdf"):
            extracted_text = process_media(payload.media_url)

        # Combine media text and message text
        full_text = f"Message: {payload.text or ''}\nDocument: {extracted_text}".strip()
        sanitized_text = sanitize_text(full_text)
        
        # Save user message to memory immediately
        database.save_message(payload.phone_number, "user", sanitized_text or "[Uploaded Image/Receipt]")

        # Check if user sent high-risk credentials or excessive personal info
        from sanitizer import detect_sensitive_info
        detected_sensitive = detect_sensitive_info(full_text)
        if detected_sensitive:
            logger.warning(f"Detected sensitive credentials from {payload.phone_number}: {detected_sensitive}")

        # Check if message contains or refers to a bank statement or financial document
        is_statement = bool(
            (payload.media_url and payload.media_url.lower().endswith(".pdf"))
            or (payload.text and any(w in payload.text.lower() for w in ["statement", "bank statement", "checking account", "savings account", "transaction history", "paystub", "pay stub"]))
            or (extracted_text and any(w in extracted_text.lower() for w in ["statement", "beginning balance", "ending balance", "account summary", "deposit", "withdrawal"]))
        )

        # 6. Analyze with LLM (Multimodal with Gemini Vision)
        analysis_result = analyze_finances(
            phone_number=payload.phone_number,
            sanitized_data=sanitized_text,
            user_question=payload.text,
            image_bytes=image_bytes,
            mime_type=mime_type,
            detected_sensitive=detected_sensitive,
            is_statement_or_doc=is_statement
        )

        # 7. Check if Gemini extracted/tagged a name: [NAME: <Name>]
        name_tag_match = re.search(r'\[NAME:\s*([A-Za-z\- \'\.]{2,30})\]', analysis_result, re.IGNORECASE)
        if name_tag_match:
            extracted_name = name_tag_match.group(1).strip()
            if extracted_name.lower() not in ["unknown", "none", "null", "user", "theirname"]:
                database.set_user_name(payload.phone_number, extracted_name)
                logger.info(f"Learned user name from LLM tag: {extracted_name} for {payload.phone_number}")
            analysis_result = re.sub(r'\[NAME:\s*[A-Za-z\- \'\.]{2,30}\]', '', analysis_result).strip()

        # Save AI response to memory
        database.save_message(payload.phone_number, "advisor", analysis_result)

        # 8. Send response
        send_imessage(payload.phone_number, analysis_result)
        
    except Exception as e:
        logger.error(f"Error processing message from {payload.phone_number}: {e}")

@router.post("/imessage-webhook")
async def imessage_webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """
    Receives incoming JSON payloads from the iMessage bridge.
    Processing is sent to a background task to immediately return 200 OK.
    """
    background_tasks.add_task(process_message_task, payload)
    return {"status": "success"}

class TextFirstPayload(BaseModel):
    phone_number: str
    name: Optional[str] = None
    message: Optional[str] = None

@router.post("/text-first")
async def text_first(payload: TextFirstPayload):
    """
    Initiate an outbound first text to a user before they send a message.
    """
    phone = payload.phone_number.strip()
    if payload.name:
        database.set_user_name(phone, payload.name.strip())

    user_name = database.get_user_name(phone)
    if payload.message and payload.message.strip():
        text_to_send = payload.message.strip()
    elif user_name:
        text_to_send = f"Hey {user_name}! 👋 I'm Centsible, your personal AI financial advisor. Text me anytime with receipts, purchases, or budgeting questions to keep your savings on track!"
    else:
        text_to_send = "Hey there! 👋 I'm Centsible, your personal AI financial advisor. I'm here to help you budget with the 50/30/20 rule, track expenses, and crush your savings goals. What should I call you?"

    # Save to SQLite memory
    database.save_message(phone, "advisor", text_to_send)

    # Dispatch to iMessage proxy
    send_imessage(phone, text_to_send)

    return {
        "status": "success",
        "phone_number": phone,
        "name": user_name,
        "message_sent": text_to_send
    }

@router.get("/text-first")
async def text_first_get(phone: str, name: Optional[str] = None, message: Optional[str] = None):
    """
    Browser-friendly GET endpoint to trigger texting first.
    Example: http://127.0.0.1:8000/text-first?phone=+16784622289&name=Leo
    """
    payload = TextFirstPayload(phone_number=phone, name=name, message=message)
    return await text_first(payload)


