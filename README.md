# Mini Agent Platform

A multi-tenant backend API for managing and running AI Agents.

## Setup

1. **Create Virtual Environment:**
```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
```

2. **Install Dependencies:**
```bash
    pip install fastapi uvicorn sqlalchemy pytest httpx
```


## Authentication
This API is multi-tenant. You must include the x-api-key header in every request.

**Available Keys:**

sk-key-123 (Tenant 1)

sk-key-456 (Tenant 2)

sk-key-admin (Admin Tenant)

## Features
Agents & Tools: Full Create/Read/Update/Delete support.

Run Agent: Simulates an LLM response based on the agent's persona.

History: Tracks execution logs with pagination.

Throttling: Limits tenants to 5 requests per minute.

## Usage

**Running the App:**
```bash
uvicorn main:app --reload
```
The API documentation (Swagger UI) will be available at: http://127.0.0.1:8000/docs

**Running Tests**
```bash
pytest
```