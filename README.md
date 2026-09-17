# Brahmastra-AI

Brahmastra-AI is a JARVIS-style personal assistant composed of a React/Vite frontend, a Node/Express API gateway, and a Python/FastAPI AI and tool service.

## Architecture

```text
React Frontend -> Node/Express -> Python/FastAPI -> Provider or Tool Registry
      ^                ^                 |
      |                |                 v
      +--------- TTS/STT responses   MongoDB memory
```

Node is the canonical conversation persistence owner. It stores user-scoped conversations and messages in MongoDB using `role`, `content`, and timestamps. Each request sends the same `conversationId` to Python as `conversation_id`, plus at most the latest 20 persisted messages as `context`. Python performs orchestration, provider calls, and tool execution but does not persist a competing conversation history.

## Prerequisites

- Node.js 20+
- Python 3.11+
- MongoDB
- Provider credentials as required by the selected Python provider
- Groq credentials for backend Whisper STT

## Setup

Copy each `.env.example` to `.env` and provide local values. Never commit `.env` files or credentials.

### Python-AI

```powershell
cd Python-AI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

The service listens on port `8000` by default and exposes `POST /ai/chat`.

### Backend

```powershell
cd Backend
npm install
npm run dev
```

The gateway listens on port `5000` by default. It calls Python using `PYTHON_AI_URL` and optionally authenticates the service request with `PYTHON_AI_API_KEY`.

### Frontend

```powershell
cd Frontend
npm install
npm run dev
```

The frontend uses `VITE_API_URL` for the Node gateway URL.

## Current Features

- Voice recording through browser `MediaRecorder`
- Groq Whisper speech-to-text through Node
- Text chat through the React chat panel
- Python AI orchestration with configurable Gemini, Groq, OpenAI, OpenRouter, and Ollama providers
- Registered calculator, current-time, echo, file-info, ping, and system-info tools
- Node MongoDB conversation and visualizer-settings persistence
- OpenAI TTS with Google Translate TTS fallback

The bundled Vosk model is retained in `Frontend/public/models`, but it is not currently wired into the runtime speech pipeline.

## Tests

```powershell
cd Frontend; npm run lint; npm run build
cd Backend; npm test
cd Python-AI; python -m pytest tests -q
```

## Limitations

Authentication is currently service-key based between Node and Python when `PYTHON_AI_API_KEY` is configured; end-user login and user-specific authorization still need to be added. Desktop/browser automation, vision, proactive assistance, and local Vosk recognition are not implemented. Tool execution must remain behind trusted service authentication in production.
