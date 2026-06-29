"""
WhatsApp Cloud API — Message Sending
"""

import os
import requests
import logging

logger = logging.getLogger(__name__)

META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID")


def send_whatsapp_message(phone_number: str, message: str) -> dict:
    """
    Send a text message via WhatsApp Cloud API.

    Args:
        phone_number: Recipient phone number (with country code, no +)
        message: Text message body

    Returns:
        dict with success status and Meta API response
    """
    url = f"https://graph.facebook.com/v17.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info(f"Message sent to {phone_number}: {message[:50]}...")
        return {"success": True, "response": resp.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send message to {phone_number}: {e}")
        return {"success": False, "error": str(e)}


def send_whatsapp_image(phone_number: str, media_id: str) -> dict:
    """
    Send an image via WhatsApp Cloud API (for future use).
    """
    url = f"https://graph.facebook.com/v17.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "image",
        "image": {"id": media_id},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        return {"success": True, "response": resp.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send image to {phone_number}: {e}")
        return {"success": False, "error": str(e)}


def upload_whatsapp_media(file_path: str, mime_type: str = "audio/ogg") -> str:
    """
    Upload a media file to WhatsApp Cloud API.
    Returns the media ID needed for sending audio messages.
    
    Args:
        file_path: Path to the file to upload
        mime_type: MIME type of the file
    
    Returns:
        Media ID string, or None on error.
    """
    url = f"https://graph.facebook.com/v17.0/{META_PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
    }
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, mime_type)}
            data = {
                "messaging_product": "whatsapp",
                "type": mime_type.split("/")[0],  # "audio"
            }
            resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
            resp.raise_for_status()
            media_id = resp.json().get("id")
            logger.info(f"Media uploaded: {file_path} → media_id={media_id}")
            return media_id
    except Exception as e:
        logger.error(f"Media upload error: {e}")
        return None


def send_whatsapp_audio(phone_number: str, media_id: str) -> dict:
    """
    Send an audio message via WhatsApp Cloud API.
    Audio must be in OGG/Opus format.
    
    Args:
        phone_number: Recipient phone number
        media_id: Media ID from upload_whatsapp_media()
    
    Returns:
        dict with success status
    """
    url = f"https://graph.facebook.com/v17.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "audio",
        "audio": {"id": media_id},
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info(f"Audio sent to {phone_number}: media_id={media_id}")
        return {"success": True, "response": resp.json()}
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send audio to {phone_number}: {e}")
        return {"success": False, "error": str(e)}


def mark_message_read(message_id: str) -> bool:
    """Mark a message as read (blue tick)."""
    url = f"https://graph.facebook.com/v17.0/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False