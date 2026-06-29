# 💊 Pharmacy WhatsApp AI Agent (MedBot)

An AI-powered WhatsApp pharmacy assistant built with **FastAPI**, **GLM 5.2** (via Ollama Cloud), and **Meta WhatsApp Cloud API**. MedBot handles medicine inquiries, order placement, order tracking, prescription uploads, and bidirectional voice messaging — all through WhatsApp.

## ✨ Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Medicine Stock Check** | Query 12 mock medicines — availability, price, Rx requirement, manufacturer |
| 2 | **Order Placement** | Create orders with auto-generated ID (RX-XXXXX), persisted to SQLite |
| 3 | **Order Tracking** | Track by order ID — checks SQLite DB first, falls back to mock data |
| 4 | **Prescription Upload** | Download prescription photos via Meta Media API → save to `prescriptions/` |
| 5 | **Voice Messaging** | Incoming: Whisper STT → text → LLM. Outgoing: edge-tts → OGG/Opus → audio message |
| 6 | **Conversation Memory** | SQLite per phone number, 2hr TTL auto-wipe, last 15 messages as context |
| 7 | **LLM Tool Calling** | GLM 5.2 with 3 tool schemas → autonomous function execution |
| 8 | **Session Restart** | "restart" command clears session memory on demand |
| 9 | **Webhook Verification** | Meta hub.challenge handshake |
| 10 | **Health Check** | `/health` endpoint + Docker healthcheck |
| 11 | **Order Persistence** | SQLite `orders.db` — survives server restarts |
| 12 | **Docker Support** | Dockerfile + docker-compose.yml ready |

## 🏗️ Architecture

```
WhatsApp User
    ↕ (Webhook)
FastAPI Server (port 8000)
    ├── Message Handler → GLM 5.2 (Ollama Cloud)
    │                       ├── Tool: check_medicine_stock
    │                       ├── Tool: create_pharmacy_order
    │                       ├── Tool: check_order_status
    │                       └── Tool: upload_prescription
    ├── Audio Handler → faster-whisper (STT) / edge-tts (TTS)
    ├── Memory → SQLite (per phone, 2hr TTL)
    └── Order Store → SQLite (persistent)
```

## 📁 Project Structure

```
pharmacy-whatsapp-agent/
├── app/
│   ├── main.py           # FastAPI app + webhook + LLM cycle (389 lines)
│   ├── whatsapp.py       # WhatsApp Cloud API sender (157 lines)
│   ├── audio.py          # STT (Whisper) + TTS (edge-tts) + ffmpeg (223 lines)
│   └── memory.py         # SQLite chat history + TTL (115 lines)
├── tools/
│   ├── pharmacy_tools.py # 4 business logic tools (299 lines)
│   ├── mock_data.py      # 12 medicines + 3 mock orders (150 lines)
│   └── schema.py         # OpenAI-compatible tool schemas (79 lines)
├── prompts/
│   └── system_prompt.txt # MedBot persona + rules
├── tests/
│   └── test_agent.py     # 12 test cases (140 lines)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- A Meta WhatsApp Business account with Cloud API access
- An Ollama Cloud account (or local Ollama) for GLM 5.2

### Setup

```bash
# Clone the repo
git clone https://github.com/kamatanuj/pharmacy-whatsapp-agent.git
cd pharmacy-whatsapp-agent

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the server
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker-compose up -d
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `META_ACCESS_TOKEN` | Meta WhatsApp Cloud API access token |
| `META_PHONE_NUMBER_ID` | WhatsApp phone number ID |
| `META_VERIFY_TOKEN` | Webhook verification token (any string) |
| `OLLAMA_CLOUD_API_KEY` | Ollama Cloud API key |
| `OLLAMA_CLOUD_BASE_URL` | Ollama Cloud base URL (default: `https://ollama.com/v1`) |
| `LLM_MODEL` | LLM model name (default: `glm-5.2:cloud`) |
| `PHARMACY_DB_URL` | Pharmacy database API URL |
| `DB_API_KEY` | Pharmacy database API key |
| `HOST` | Server host (default: `0.0.0.0`) |
| `PORT` | Server port (default: `8000`) |

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/webhook` | Meta webhook verification |
| `POST` | `/webhook` | Incoming WhatsApp messages |

## 🧪 Tests

```bash
python3 -m pytest tests/test_agent.py -v
```

## 📄 License

MIT