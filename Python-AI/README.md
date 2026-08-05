# BRAHMASTRA AI

Enterprise-grade AI Assistant built using:

- FastAPI
- Python
- React
- Node.js
- MongoDB

---

## Features

- REST API
- AI Tool Registry
- Modular Architecture
- Logging
- Middleware
- Authentication Ready
- Production Ready
- Future Desktop Agent
- Browser Automation
- Memory System
- Vision System

---

## Installation

Create virtual environment

```bash
python -m venv .venv
```

Activate

Windows

```powershell
.venv\Scripts\activate
```

Linux

```bash
source .venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run

```bash
uvicorn app:app --reload
```

Swagger

```
http://localhost:8000/docs
```

Redoc

```
http://localhost:8000/redoc
```

---

## Project Structure

```
Python-AI
│
├── agents
├── core
├── middleware
├── routers
├── schemas
├── services
├── storage
├── tools
├── utils
├── app.py
```