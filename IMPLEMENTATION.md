# Pharmacy WhatsApp AI Agent — Implementation Document

**Project:** HealthFirst Medical Shop — MedBot  
**Version:** 1.0.0  
**Date:** June 29, 2026  
**Status:** ✅ Live and Working  

---

## 1. Overview

MedBot is an AI-powered WhatsApp assistant for **HealthFirst Medical Shop**. Customers can check medicine availability, get pricing, place delivery orders, track order status, and send voice messages — all through WhatsApp. The bot is powered by **GLM 5.2** (via Ollama Cloud) with function-calling (tool use) for structured pharmacy operations.

### Key Stats

| Metric | Value |
|---|---|
| Total source files | 13 (excl. tests, config, Docker) |
| Total lines of code | ~1,600 |
| Test cases | 12 (all passing) |
| LLM | GLM 5.2 via Ollama Cloud |
| STT | faster-whisper (local, CPU) |
| TTS | edge-tts (local) |
| Database | SQLite (chat history + orders) |
| Webhook | Meta WhatsApp Cloud API v21.0 |
| Public URL | ngrok tunnel (port 8000) |

---

## 2. Features Implemented

### 2.1 Medicine Stock Check
- **What:** Customer asks "Do you have Paracetamol?" — bot checks inventory and responds with availability, stock level, price, manufacturer, and whether a prescription is required.
- **Tool:** `check_medicine_stock(medicine_name)`
- **Mock inventory:** 12 medicines (OTC, Schedule H, supplements)

### 2.2 Order Placement
- **What:** Customer specifies medicines + quantities + delivery address — bot creates a pending order with a unique order ID (RX-XXXXX format).
- **Tool:** `create_pharmacy_order(customer_name, phone_number, delivery_address, items)`
- **Persistence:** Orders saved to SQLite (`data/orders.db`) — survive server restarts.
- **Phone auto-injection:** Sender's WhatsApp number is auto-injected (not exposed in schema).

### 2.3 Order Tracking
- **What:** Customer asks "Where is my order RX-10001?" — bot checks status (Pending, Confirmed, Out for Delivery, Delivered).
- **Tool:** `check_order_status(order_id)`
- **Lookup priority:** SQLite DB → in-memory mock data → "Not Found"

### 2.4 Prescription Image Upload
- **What:** Customer sends a photo of their prescription — bot downloads it via Meta Media API and saves to `prescriptions/` directory for pharmacist review.
- **Tool:** `download_prescription_image(media_id)`
- **Auto-reply:** Bot confirms receipt and says pharmacist will review shortly.

### 2.5 Voice Messaging (Bidirectional)
- **Incoming:** Customer sends a voice note → bot downloads OGG/Opus audio from Meta API → transcribes via faster-whisper (STT) → processes text through LLM cycle → replies.
- **Outgoing:** Bot generates text reply → converts to speech via edge-tts (Indian English voice: en-IN-NeerjaNeural) → converts MP3 to OGG/Opus via ffmpeg → uploads to Meta → sends as audio message.
- **Both text and voice:** Every reply is sent as BOTH a text message AND an audio message.
- **Language support:** Auto-detect for STT; Hindi + English voices available.

### 2.6 Conversation Memory
- **What:** Chat history stored in SQLite per phone number with 2-hour TTL auto-wipe.
- **Capacity:** Last 15 messages included as context for each LLM call.
- **Reset:** Customer can type "restart" to clear their session.
- **Storage:** `data/chat.db` (SQLite)

### 2.7 LLM Tool Calling (Function Calling)
- **What:** GLM 5.2 receives OpenAI-compatible tool schemas and can call pharmacy functions autonomously.
- **Flow:** First LLM call (with tools) → if tool_calls: execute → append results → second LLM call (no tools) → natural language response.
- **Schemas:** 3 tools defined in `tools/schema.py` (check_medicine_stock, create_pharmacy_order, check_order_status).

### 2.8 Webhook Verification
- **Meta webhook verification:** GET `/webhook` with hub.challenge handshake.
- **Message handling:** POST `/webhook` processes all incoming messages.

### 2.9 Health Check
- **Endpoint:** GET `/health` returns JSON status.
- **Docker healthcheck:** Configured in docker-compose.yml (30s interval).

### 2.10 Session Management
- **"restart" command:** Clears all chat history for the sender's phone number.
- **TTL auto-wipe:** Messages older than 2 hours automatically deleted on each history fetch.

---

## 3. Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
│  WhatsApp    │────▶│  Meta Cloud  │────▶│  ngrok Tunnel    │
│  Customer    │◀────│  API v21.0   │◀────│  (port 8000)     │
└─────────────┘     └──────────────┘     └────────┬─────────┘
                                                   │
                                          ┌────────▼─────────┐
                                          │  FastAPI Webhook  │
                                          │  app/main.py      │
                                          └────────┬─────────┘
                                                   │
                           ┌───────────────────────┼───────────────────┐
                           │                       │                   │
                  ┌────────▼────────┐   ┌─────────▼─────────┐  ┌───────▼───────┐
                  │  LLM Cycle       │   │  Audio Module     │  │  WhatsApp     │
                  │  (GLM 5.2 Cloud) │   │  app/audio.py     │  │  Sender       │
                  │  + Tool Calling  │   │  STT + TTS        │  │  app/whatsapp │
                  └────────┬────────┘   └───────────────────┘  └───────────────┘
                           │
                  ┌────────▼────────┐
                  │  Pharmacy Tools │
                  │  tools/          │
                  │  - Stock check   │
                  │  - Order create  │
                  │  - Order track   │
                  │  - Rx image dl   │
                  └────────┬────────┘
                           │
                  ┌────────▼────────┐
                  │  Mock Data       │
                  │  + SQLite DB     │
                  │  data/           │
                  │  - chat.db       │
                  │  - orders.db     │
                  └─────────────────┘
```

### Message Processing Flow

```
Customer sends message (text / audio / image)
        │
        ▼
   Webhook receives POST /webhook
        │
        ├─→ Image?  → Download prescription → Confirm receipt
        │
        ├─→ Audio?  → Download OGG → STT (Whisper) → Text
        │                  → LLM cycle → Text reply + TTS → Voice reply
        │
        └─→ Text?   → LLM cycle → Text reply + TTS → Voice reply
                           │
                           ▼
                    LLM Cycle (run_llm_cycle):
                    1. Fetch last 15 messages from SQLite
                    2. Build messages: [system_prompt, ...history, user_msg]
                    3. Call GLM 5.2 (with tool schemas)
                    4. If tool_calls: execute each → append results
                    5. Second GLM 5.2 call (no tools) → natural response
                    6. Save user + assistant messages to SQLite
                    7. Return text
```

---

## 4. File List

### Project Root: `/root/pharmacy-whatsapp-agent/`

| # | File | Lines | Description |
|---|---|---|---|
| 1 | `.env` | 16 | Environment variables (API keys, tokens, phone number ID) |
| 2 | `.gitignore` | 7 | Git ignore rules (.env, __pycache__, DB files, prescriptions) |
| 3 | `requirements.txt` | 3 | Python dependencies (fastapi, uvicorn, requests, python-dotenv) |
| 4 | `Dockerfile` | 18 | Docker image definition (python:3.11-slim) |
| 5 | `docker-compose.yml` | 17 | Docker Compose service config (port 8000, healthcheck, volumes) |
| 6 | `IMPLEMENTATION.md` | — | This document |

### Application: `app/`

| # | File | Lines | Description |
|---|---|---|---|
| 7 | `app/__init__.py` | 0 | Python package marker |
| 8 | `app/main.py` | 389 | **Core application.** FastAPI webhook handler, LLM cycle (GLM 5.2 + tool calling), message routing for text/audio/image types, voice reply generation. |
| 9 | `app/whatsapp.py` | 157 | WhatsApp Cloud API client. Functions: send text message, send image, upload media, send audio message, mark message read. |
| 10 | `app/audio.py` | 223 | Audio processing module. STT via faster-whisper, TTS via edge-tts, MP3→OGG/Opus conversion via ffmpeg, WhatsApp media download helper. |
| 11 | `app/memory.py` | 115 | SQLite chat history management. Functions: init_db, get_chat_history (with 2hr TTL), save_to_history, clear_session_memory, cleanup_all_expired. |

### Tools: `tools/`

| # | File | Lines | Description |
|---|---|---|---|
| 12 | `tools/__init__.py` | 0 | Python package marker |
| 13 | `tools/pharmacy_tools.py` | 299 | **Business logic.** 4 tools: check_medicine_stock, create_pharmacy_order (with SQLite persistence), check_order_status (DB + mock fallback), download_prescription_image. Order persistence via SQLite. |
| 14 | `tools/mock_data.py` | 150 | Mock pharmacy inventory (12 medicines), 3 pre-existing orders, order counter. |
| 15 | `tools/schema.py` | 79 | OpenAI/GLM-compatible function tool schemas (3 tools: stock check, order create, order status). |

### Prompts: `prompts/`

| # | File | Lines | Description |
|---|---|---|---|
| 16 | `prompts/system_prompt.txt` | 17 | MedBot persona, rules (ask for Rx for Schedule H, no clinical advice, conversational tone, "restart" command). |

### Tests: `tests/`

| # | File | Lines | Description |
|---|---|---|---|
| 17 | `tests/test_agent.py` | 140 | 12 test cases: stock check (in stock, Rx required, out of stock, unknown), order creation, order tracking (existing, nonexistent), memory (restart clear, history limit), schema validation (all tools, phone_number hidden), tool registry. |

### Data (runtime, git-ignored)

| File | Description |
|---|---|
| `data/chat.db` | SQLite — chat history (per phone number, 2hr TTL) |
| `data/orders.db` | SQLite — persistent orders (survives restarts) |
| `prescriptions/*.jpg` | Downloaded prescription images |

---

## 5. Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **LLM** | GLM 5.2 (Ollama Cloud) | OpenAI-compatible API at `https://ollama.com/v1`, model `glm-5.2:cloud` |
| **STT** | faster-whisper v1.2.1 | Local, CPU, int8 quantization, base model, VAD filter |
| **TTS** | edge-tts | Microsoft Edge Neural TTS, voice: en-IN-NeerjaNeural |
| **Audio Conversion** | ffmpeg v6.1.1 | MP3 → OGG/Opus (64kbps, voip application) |
| **Web Framework** | FastAPI 0.115.6 | Async webhook handler |
| **Server** | uvicorn 0.34.0 | ASGI server on port 8000 |
| **Database** | SQLite | Two DBs: chat history + orders |
| **Messaging** | Meta WhatsApp Cloud API v21.0 | Send/receive text, audio, image |
| **Tunnel** | ngrok v3.39.7 | Public HTTPS → localhost:8000 |
| **Python** | 3.11.15 | |
| **Containerization** | Docker + docker-compose | python:3.11-slim base |

---

## 6. LLM Tool-Calling Details

### Tools Available to GLM 5.2

| Tool | Parameters | Returns |
|---|---|---|
| `check_medicine_stock` | `medicine_name` (string) | name, available, stock, price_per_strip, requires_prescription, category, manufacturer |
| `create_pharmacy_order` | `customer_name`, `delivery_address`, `items[]` (phone_number auto-injected) | status, order_id, message |
| `check_order_status` | `order_id` (string) | order_id, status, estimated_delivery |

### Tool Calling Flow

1. GLM 5.2 receives `tools` parameter with schemas
2. If user query requires action, GLM returns `tool_calls` array
3. Each tool call executed; result appended as `role: "tool"` message
4. Second GLM call (no tools) produces natural language response

---

## 7. Voice Messaging Implementation

### Incoming Voice Message

```
WhatsApp → webhook (type=audio)
    → download_whatsapp_media(media_id) → OGG file on disk
    → transcribe_audio(path) via faster-whisper → text
    → run_llm_cycle(phone, text) → reply text
    → send_whatsapp_message(phone, reply) → text reply
    → generate_speech(reply) via edge-tts → MP3
    → convert_mp3_to_ogg(mp3) via ffmpeg → OGG/Opus
    → upload_whatsapp_media(ogg) → media_id
    → send_whatsapp_audio(phone, media_id) → voice reply
```

### Outgoing Voice Reply (also for text messages)

Every text reply also generates a voice reply:
1. `generate_speech(text)` — edge-tts with en-IN-NeerjaNeural voice
2. `convert_mp3_to_ogg(mp3_path)` — ffmpeg to OGG/Opus (WhatsApp format)
3. `upload_whatsapp_media(ogg_path)` — upload to Meta, get media_id
4. `send_whatsapp_audio(phone, media_id)` — send as audio message

### Audio Format

| Direction | Format | Codec |
|---|---|---|
| Incoming (WhatsApp) | OGG | Opus |
| STT input | OGG/Opus → ffmpeg decode | — |
| TTS output (edge-tts) | MP3 | — |
| Outgoing (WhatsApp) | OGG | Opus (64kbps, voip) |

---

## 8. Mock Data

### Medicine Inventory (12 items)

| Medicine | Manufacturer | Price (₹/strip) | Stock | Category | Rx Required |
|---|---|---|---|---|---|
| Paracetamol | Cipla | 40 | 500 | OTC | No |
| Amoxicillin | Sun Pharma | 120 | 45 | Schedule H | Yes |
| Lipitor | Pfizer | 350 | 0 (Out of stock) | Schedule H | Yes |
| Crocin | GSK | 35 | 300 | OTC | No |
| Aspirin | USV | 25 | 200 | OTC | No |
| Metformin | USV | 55 | 150 | Schedule H | Yes |
| Omeprazole | Dr. Reddy's | 90 | 80 | OTC | No |
| Azithromycin | Cipla | 180 | 60 | Schedule H | Yes |
| Vitamin D3 | D-Blue | 65 | 400 | Supplement | No |
| Cough Syrup | Cipla | 75 | 120 | OTC | No |
| Insulin | Lupin | 450 | 30 | Schedule H | Yes |
| Pantoprazole | Sun Pharma | 70 | 100 | OTC | No |

### Pre-existing Orders (mock)

| Order ID | Customer | Medicine | Qty | Status | ETA |
|---|---|---|---|---|---|
| RX-10001 | Raj Patel | Paracetamol | 2 | Out for Delivery | 45 min |
| RX-10002 | Priya Sharma | Metformin | 3 | Confirmed | 2 hours |
| RX-10003 | Amit Singh | Azithromycin | 1 | Pending | 3 hours |

---

## 9. API Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Root — service info + endpoint list |
| GET | `/health` | Health check — returns JSON status |
| GET | `/webhook` | Meta webhook verification (hub.challenge handshake) |
| POST | `/webhook` | Main message handler — receives WhatsApp messages |

---

## 10. Environment Variables

| Variable | Description |
|---|---|
| `META_ACCESS_TOKEN` | Meta WhatsApp Cloud API access token |
| `META_PHONE_NUMBER_ID` | WhatsApp phone number ID (YOUR_PHONE_NUMBER_ID) |
| `META_VERIFY_TOKEN` | Webhook verification token (YOUR_VERIFY_TOKEN) |
| `OLLAMA_CLOUD_API_KEY` | Ollama Cloud API key for GLM 5.2 |
| `PORT` | Server port (default: 8000) |
| `HOST` | Server host (default: 0.0.0.0) |
| `PHARMACY_DB_URL` | Future: real pharmacy DB API URL |
| `DB_API_KEY` | Future: pharmacy DB API key |

---

## 11. Testing

### Test Suite: `tests/test_agent.py`

```bash
cd /root/pharmacy-whatsapp-agent
python -m pytest tests/test_agent.py -v
```

### Test Cases (12 total)

| # | Test | Description |
|---|---|---|
| 1 | `test_1_paracetamol_in_stock` | Paracetamol available, no Rx, 500 stock |
| 2 | `test_6_amoxicillin_rx_required` | Amoxicillin available, Rx required |
| 3 | `test_7_lipitor_out_of_stock` | Lipitor out of stock |
| 4 | `test_unknown_medicine` | Unknown medicine returns not available |
| 5 | `test_2_create_order` | Create order for Paracetamol x2 |
| 6 | `test_3_existing_order` | Track RX-10001 → Out for Delivery |
| 7 | `test_nonexistent_order` | Non-existent order → Not Found |
| 8 | `test_5_restart_clears_memory` | "restart" clears chat history |
| 9 | `test_history_limit` | History returns max 15 messages |
| 10 | `test_schema_has_required_tools` | Schema has all 3 tools |
| 11 | `test_phone_number_not_in_schema` | phone_number not exposed in schema |
| 12 | `test_all_tools_registered` | All tools in AVAILABLE_TOOLS registry |

---

## 12. Deployment

### Current (Running)

```
ngrok tunnel → localhost:8000 → uvicorn (FastAPI)
```

- **ngrok:** `https://bevilled-malik-decennially.ngrok-free.dev`
- **Webhook URL:** `https://bevilled-malik-decennially.ngrok-free.dev/webhook`
- **Phone number:** +91 98201 63055

### Docker (Available)

```bash
docker-compose up -d
# Health: http://localhost:8000/health
```

### Startup

```bash
cd /root/pharmacy-whatsapp-agent
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 13. Future Enhancements

| Feature | Status |
|---|---|
| Real pharmacy DB integration (replace mock data) | Placeholder code ready (commented out) |
| Prescription OCR (text extraction from images) | Not started |
| Hindi voice support (hi-IN-SwaraNeural) | Voice mapping ready in audio.py |
| Order status updates (webhook from pharmacy system) | Not started |
| Multiple pharmacy branches | Not started |
| Payment integration (UPI, Razorpay) | Not started |
| Medicine reminders (scheduled messages) | Not started |
| Auto-convert audio for all responses | ✅ Implemented |
| Order persistence across restarts | ✅ Implemented (SQLite) |

---

## 14. Known Limitations

1. **Mock data only** — No real pharmacy database connected. All inventory and orders are simulated.
2. **No OCR** — Prescription images are downloaded but not analyzed; pharmacist must manually review.
3. **Single language STT auto-detect** — Whisper auto-detects language but may misidentify short clips.
4. **TTS voice is Indian English female** — No male voice or multi-voice rotation.
5. **2-hour TTL on chat history** — Conversations older than 2 hours are automatically wiped.
6. **ngrok free tier** — URL changes on restart; needs Meta webhook reconfiguration.
7. **No rate limiting** — Webhook accepts all requests (Meta handles rate limits on their side).
8. **GLM 5.2 does not support vision** — Cannot analyze prescription images via LLM.

---

*Document generated on June 29, 2026*
*Project: HealthFirst Medical Shop — MedBot*
*Developed for D-Insights (www.d-insights.global)*