"""
FastAPI Main Application — Pharmacy WhatsApp AI Agent
Webhook handler + LLM cycle (GLM 5.2 via Ollama Cloud)
"""

import os
import json
import logging
import requests
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Import modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.memory import init_db, get_chat_history, save_to_history, clear_session_memory
from app.whatsapp import send_whatsapp_message, send_whatsapp_audio, upload_whatsapp_media, mark_message_read
from app.audio import transcribe_audio, generate_speech, convert_mp3_to_ogg, download_whatsapp_media
from tools.pharmacy_tools import AVAILABLE_TOOLS
from tools.schema import TOOLS_SCHEMA

# --- Config ---
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "healthfirst_whatsapp_verify_2026")
OLLAMA_CLOUD_API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")

# LLM config — switch between local Ollama and Ollama Cloud via env vars
# Local mode (free, dev):  LLM_MODEL=ornith:9b, LLM_API_URL=http://localhost:11434/v1/chat/completions
# Cloud mode (production): LLM_MODEL=glm-5.2:cloud, LLM_API_URL=https://ollama.com/v1/chat/completions
LLM_MODEL = os.getenv("LLM_MODEL", "glm-5.2:cloud")
LLM_API_URL = os.getenv("LLM_API_URL", "https://ollama.com/v1/chat/completions")
LLM_IS_LOCAL = "localhost" in LLM_API_URL or "127.0.0.1" in LLM_API_URL

# Initialize SQLite
init_db()

# Create FastAPI app
app = FastAPI(title="Pharmacy WhatsApp AI Agent", version="1.0.0")


# ========== LLM Cycle ==========

def run_llm_cycle(phone_number: str, user_message: str) -> str:
    """
    Core LLM loop:
    1. Fetch chat history from SQLite (last 15 messages)
    2. Append new user message
    3. Load system prompt
    4. Call GLM 5.2 via Ollama Cloud with tools
    5. If tool_calls: execute, append result, second call (no tools)
    6. Save user msg + bot reply to SQLite
    7. Return final conversational text
    """
    # 1. Fetch history
    history = get_chat_history(phone_number, limit=15)

    # 2. Load system prompt
    prompt_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "prompts", "system_prompt.txt"
    )
    with open(prompt_path, "r") as f:
        system_prompt = f.read().strip()

    # 3. Build messages array
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    # 4. First LLM call (with tools)
    logger.info(f"LLM cycle for {phone_number}: {user_message[:80]}")
    response = _call_llm(messages, tools=TOOLS_SCHEMA)

    if "error" in response:
        logger.error(f"LLM error: {response['error']}")
        return "I'm sorry, I'm having trouble processing your request right now. Please try again in a moment. 🙏"

    msg = response.get("choices", [{}])[0].get("message", {})
    tool_calls = msg.get("tool_calls")
    content = msg.get("content", "")

    # 5. Handle tool calls (max 2 calls per tool per cycle to prevent loops)
    if tool_calls:
        # Append assistant message with tool_calls to messages
        messages.append(msg)

        # Track how many times each tool has been called in this cycle
        tool_call_counts = {}

        for tc in tool_calls:
            func_name = tc["function"]["name"]
            func_args = json.loads(tc["function"]["arguments"])

            # Inject phone_number for order creation
            if func_name == "create_pharmacy_order":
                func_args["phone_number"] = phone_number

            # --- Retry cap: max 2 calls per tool per cycle ---
            tool_call_counts[func_name] = tool_call_counts.get(func_name, 0) + 1
            if tool_call_counts[func_name] > 2:
                logger.warning(f"Tool {func_name} called {tool_call_counts[func_name]} times — capping at 2, returning fallback")
                result = {
                    "order_id": func_args.get("order_id", "N/A"),
                    "status": "Not Found",
                    "estimated_delivery": "N/A",
                    "_retry_exceeded": True,
                    "message": f"Order {func_args.get('order_id', '')} could not be found after multiple attempts. Please check the order ID and try again.",
                }
            else:
                logger.info(f"Tool call #{tool_call_counts[func_name]}: {func_name}({func_args})")

                # Execute tool
                if func_name in AVAILABLE_TOOLS:
                    result = AVAILABLE_TOOLS[func_name](**func_args)
                else:
                    result = {"error": f"Unknown tool: {func_name}"}

            logger.info(f"Tool result: {result}")

            # Append tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": json.dumps(result, ensure_ascii=False),
            })

        # Second LLM call (no tools, get conversational response)
        response2 = _call_llm(messages, tools=None)
        if "error" not in response2:
            content = response2.get("choices", [{}])[0].get("message", {}).get("content", "")
        else:
            logger.error(f"Second LLM call error: {response2['error']}")
            content = "I've processed your request, but I'm having trouble generating a response. Please try again."

    # 6. Save to history
    save_to_history(phone_number, "user", user_message)
    if content:
        save_to_history(phone_number, "assistant", content)

    # 7. Return final text
    return content if content else "I understand. How can I help you further?"


def _call_llm(messages: list, tools: list = None) -> dict:
    """Call LLM via Ollama API (local or cloud)."""
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": 1000,
        "temperature": 0.7,
    }
    if tools:
        payload["tools"] = tools

    # Build headers — local Ollama doesn't need auth
    headers = {"Content-Type": "application/json"}
    if not LLM_IS_LOCAL and OLLAMA_CLOUD_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_CLOUD_API_KEY}"

    # Local Ollama is slower (CPU), give it more time
    timeout = 180 if LLM_IS_LOCAL else 90

    try:
        resp = requests.post(
            LLM_API_URL,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# ========== Webhook Handlers ==========

@app.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    """
    Meta webhook verification endpoint.
    Meta sends GET with hub.challenge — we must return it.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    logger.info(f"Webhook verification: mode={mode}, token={token}")

    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        logger.info("Webhook verified successfully!")
        return Response(content=challenge, media_type="text/plain", status_code=200)
    else:
        logger.warning(f"Webhook verification failed: mode={mode}, token={token}")
        return Response(content="Forbidden", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request) -> JSONResponse:
    """
    Main message handler — receives WhatsApp messages (text + image).
    """
    try:
        body = await request.json()
        logger.info(f"Webhook received: {json.dumps(body, indent=2)[:500]}")

        # Meta webhook structure
        # body["entry"][0]["changes"][0]["value"]["messages"][0]
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        messages = value.get("messages", [])
        if not messages:
            # Could be a status update — acknowledge
            return JSONResponse(content={"status": "ok"}, status_code=200)

        msg = messages[0]
        sender_phone = msg.get("from", "")
        msg_type = msg.get("type", "")
        msg_id = msg.get("id", "")

        # Mark message as read
        if msg_id:
            mark_message_read(msg_id)

        # --- Handle Image (prescription) ---
        if msg_type == "image":
            image_info = msg.get("image", {})
            media_id = image_info.get("id", "")

            logger.info(f"Image received from {sender_phone}, media_id={media_id}")

            # Download prescription image
            from tools.pharmacy_tools import download_prescription_image
            result = download_prescription_image(media_id)

            if result.get("success"):
                send_whatsapp_message(
                    sender_phone,
                    "✅ Prescription received! Our pharmacist will review it shortly. "
                    "We'll notify you once it's verified.",
                )
            else:
                send_whatsapp_message(
                    sender_phone,
                    "⚠️ We received your prescription image but had trouble processing it. "
                    "Please try sending it again, or call us directly.",
                )

            return JSONResponse(content={"status": "ok"}, status_code=200)

        # --- Handle Audio (voice message) ---
        if msg_type == "audio":
            audio_info = msg.get("audio", {})
            media_id = audio_info.get("id", "")
            # Note: WhatsApp voice messages are audio/ogg with Opus codec

            logger.info(f"Voice message from {sender_phone}, media_id={media_id}")

            # Download the audio file from WhatsApp
            audio_path = download_whatsapp_media(media_id, META_ACCESS_TOKEN)

            if not audio_path:
                send_whatsapp_message(
                    sender_phone,
                    "⚠️ I couldn't download your voice message. Please try sending it again, or type your message.",
                )
                return JSONResponse(content={"status": "ok"}, status_code=200)

            try:
                # Transcribe audio to text
                transcribed_text = transcribe_audio(audio_path)

                # Clean up downloaded file
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

                if not transcribed_text:
                    send_whatsapp_message(
                        sender_phone,
                        "⚠️ I couldn't understand your voice message. Could you please type your message instead?",
                    )
                    return JSONResponse(content={"status": "ok"}, status_code=200)

                logger.info(f"Transcribed voice from {sender_phone}: {transcribed_text[:100]}")

                # Run LLM cycle with transcribed text
                reply = run_llm_cycle(sender_phone, transcribed_text)

                # Send text reply
                send_whatsapp_message(sender_phone, reply)

                # Also send voice reply (TTS)
                try:
                    mp3_path = generate_speech(reply, language="en")
                    if mp3_path:
                        ogg_path = convert_mp3_to_ogg(mp3_path)
                        if ogg_path:
                            wa_media_id = upload_whatsapp_media(ogg_path, mime_type="audio/ogg")
                            if wa_media_id:
                                send_whatsapp_audio(sender_phone, wa_media_id)
                            # Clean up temp files
                            for p in [mp3_path, ogg_path]:
                                try:
                                    os.remove(p)
                                except Exception:
                                    pass
                except Exception as e:
                    logger.error(f"TTS/voice reply error: {e}")

            except Exception as e:
                logger.error(f"Audio processing error: {e}", exc_info=True)
                send_whatsapp_message(
                    sender_phone,
                    "I had trouble processing your voice message. Please try typing instead. 🙏",
                )

            return JSONResponse(content={"status": "ok"}, status_code=200)

        # --- Handle Text ---
        if msg_type == "text":
            text_body = msg.get("text", {}).get("body", "").strip()
            logger.info(f"Text from {sender_phone}: {text_body[:100]}")

            # Restart command
            if text_body.lower() == "restart":
                clear_session_memory(sender_phone)
                send_whatsapp_message(
                    sender_phone,
                    "🔄 Session reset. How can I help you today?",
                )
                return JSONResponse(content={"status": "ok"}, status_code=200)

            # Run LLM cycle
            try:
                reply = run_llm_cycle(sender_phone, text_body)
                send_whatsapp_message(sender_phone, reply)

                # Also send voice reply (TTS)
                try:
                    mp3_path = generate_speech(reply, language="en")
                    if mp3_path:
                        ogg_path = convert_mp3_to_ogg(mp3_path)
                        if ogg_path:
                            wa_media_id = upload_whatsapp_media(ogg_path, mime_type="audio/ogg")
                            if wa_media_id:
                                send_whatsapp_audio(sender_phone, wa_media_id)
                            # Clean up temp files
                            for p in [mp3_path, ogg_path]:
                                try:
                                    os.remove(p)
                                except Exception:
                                    pass
                except Exception as e:
                    logger.error(f"TTS/voice reply error: {e}")

            except Exception as e:
                logger.error(f"LLM cycle error: {e}", exc_info=True)
                send_whatsapp_message(
                    sender_phone,
                    "I'm sorry, I'm having trouble right now. Please try again in a moment. 🙏",
                )

            return JSONResponse(content={"status": "ok"}, status_code=200)

        # --- Other message types ---
        logger.info(f"Unsupported message type: {msg_type}")
        send_whatsapp_message(
            sender_phone,
            "I currently support text messages and prescription photo uploads. "
            "How can I help you?",
        )
        return JSONResponse(content={"status": "ok"}, status_code=200)

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Pharmacy WhatsApp AI Agent",
        "model": LLM_MODEL,
        "mode": "local" if LLM_IS_LOCAL else "cloud",
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Pharmacy WhatsApp AI Agent",
        "endpoints": ["/webhook (GET+POST)", "/health (GET)"],
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("app.main:app", host=host, port=port, reload=True)