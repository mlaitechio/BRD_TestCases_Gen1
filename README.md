# BRD Automation — Quick Start Guide

## Prerequisites

- Python 3.12 (already installed)
- Docker (for Redis) OR Windows Redis binary

---

## Step 1 — Add your API Keys

Edit `.env` and add your real API keys:

```
AI_PROVIDER=claude        # or openai
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

---

## Step 2 — Start Redis (Terminal 1)

Using Docker:
```bash
docker run -p 6379:6379 redis:alpine
```

OR download Windows Redis from: https://github.com/tporadowski/redis/releases
Then run:
```bash
redis-server
```

---

## Step 3 — Start Celery Worker (Terminal 2)

```bash
celery -A brd_system worker --loglevel=info --pool=solo
```

> **Windows Note**: Always use `--pool=solo` on Windows — the default `prefork` pool doesn't work on Windows.

---

## Step 4 — Start Django Server (Terminal 3)

```bash
python manage.py runserver
```

The API is now live at: http://localhost:8000

---

## API Quick Reference

| Step | Endpoint | Method |
|---|---|---|
| 1. Create project | `POST /api/projects/` | POST |
| 2. Poll status | `GET /api/projects/{id}/status/` | GET |
| 3. Get questions | `GET /api/projects/{id}/clarification-questions/` | GET |
| 4. Submit answers | `POST /api/projects/{id}/answer-questions/` | POST |
| 5. Poll until awaiting_approval | `GET /api/projects/{id}/status/` | GET |
| 6. Get BRD | `GET /api/projects/{id}/brd/` | GET |
| 7. Approve BRD | `POST /api/projects/{id}/approve-brd/` | POST |
| 8. Poll until complete | `GET /api/projects/{id}/status/` | GET |
| 9. Get Plan | `GET /api/projects/{id}/plan/` | GET |
| 10. Get Test Cases | `GET /api/projects/{id}/testcases/` | GET |
| 11. Get Effort | `GET /api/projects/{id}/effort/` | GET |
| 12. Download DOCX | `GET /api/projects/{id}/download/brd/` | GET |

---

## End-to-End Test (curl)

```bash
# 1. Create project
curl -X POST http://localhost:8000/api/projects/ \
  -H "Content-Type: application/json" \
  -d "{\"raw_input\": \"Build a customer portal for B2B clients to track orders and raise support tickets. Must integrate with Salesforce CRM.\"}"

# Save the returned "id" as PROJECT_ID

# 2. Poll until awaiting_answers
curl http://localhost:8000/api/projects/{PROJECT_ID}/status/

# 3. Get clarification questions
curl http://localhost:8000/api/projects/{PROJECT_ID}/clarification-questions/

# 4. Submit answers
curl -X POST http://localhost:8000/api/projects/{PROJECT_ID}/answer-questions/ \
  -H "Content-Type: application/json" \
  -d "{\"answers\": {\"Q1\": \"B2B enterprise clients\", \"Q2\": \"Salesforce and SAP\", \"Q3\": \"GDPR compliance required\"}}"

# 5. Poll until awaiting_approval
curl http://localhost:8000/api/projects/{PROJECT_ID}/status/

# 6. Approve BRD
curl -X POST http://localhost:8000/api/projects/{PROJECT_ID}/approve-brd/

# 7. Poll until complete
curl http://localhost:8000/api/projects/{PROJECT_ID}/status/

# 8. Download BRD as DOCX
curl -o BRD.docx http://localhost:8000/api/projects/{PROJECT_ID}/download/brd/
```

---

## Switch AI Provider

To use OpenAI instead of Claude, edit `.env`:
```
AI_PROVIDER=openai
```

No code changes needed.

---

## Admin UI

Access the Django admin at: http://localhost:8000/admin/

Create a superuser first:
```bash
python manage.py createsuperuser
```
