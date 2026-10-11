import requests
import logging

logger = logging.getLogger(__name__)

# We route messages to the local TypeScript Proxy on port 8001
PROXY_URL = "http://127.0.0.1:8001/send-imessage"

def send_imessage(phone_number: str, message_text: str):
    """
    Sends a text message using the local TypeScript Photon Proxy.
    """
    try:
        response = requests.post(
            PROXY_URL,
            json={
                "phone_number": phone_number,
                "text": message_text
            },
            timeout=10
        )
        if response.status_code == 200:
            logger.info(f"Successfully sent message to {phone_number}")
        else:
            logger.error(f"Failed to send message: {response.text}")
    except Exception as e:
        logger.error(f"Error contacting proxy: {e}")

def send_tapback(phone_number: str, message_id: str, tapback_type: str = "!"):
    """
    Mock tapback for Photon (Photon doesn't natively support tapbacks yet, so we just log it)
    """
    logger.info(f"Mock Tapback: Sent '{tapback_type}' to message {message_id} from {phone_number}")
