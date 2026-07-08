# AI Chat & Search API Documentation

## Overview
The AI Chat API provides real-time conversational AI capabilities using Azure OpenAI (gpt-5.5). This API supports:
- ✅ Multi-turn conversations with context memory
- ✅ Code generation in multiple languages
- ✅ Text summarization
- ✅ Streaming responses (real-time word-by-word)
- ✅ Conversation history persistence
- ✅ Token usage tracking
- ✅ Session audit logging
- ✅ Anonymous & authenticated users

**Authentication:** NOT REQUIRED (open for all users and admins)

**Base URL:** `http://localhost:8000/chatgpt/api/chat/`

---

## API Endpoints

### 1. Create Conversation
**Create a new chat conversation**

```
POST /api/chat/conversations/
```

**Request Body:**
```json
{
  "title": "My Conversation"  // optional, auto-generated if not provided
}
```

**Response (201 Created):**
```json
{
  "id": "6c1696f4-0de1-46f7-b351-f9ab6a1ece03",
  "title": "My Conversation",
  "user": "test_user",
  "is_active": true,
  "model_used": "gpt-5.5",
  "total_tokens_used": 0,
  "message_count": 0,
  "created_at": "2026-07-08T06:42:00Z",
  "last_message_at": null,
  "messages": []
}
```

**Example (PowerShell):**
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/"
$body = @{ title = "My First Chat" } | ConvertTo-Json
Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Body $body
```

---

### 2. List Conversations
**Get all conversations for current user**

```
GET /api/chat/conversations/
```

**Response (200 OK):**
```json
{
  "count": 2,
  "conversations": [
    {
      "id": "6c1696f4-0de1-46f7-b351-f9ab6a1ece03",
      "title": "My Conversation",
      "message_count": 4,
      "last_message_at": "2026-07-08T06:43:05Z",
      "latest_message_preview": "Can you give me a Python example of a simple AI?"
    },
    {
      "id": "abc123def456...",
      "title": "Another Chat",
      "message_count": 2,
      "last_message_at": "2026-07-08T05:30:00Z",
      "latest_message_preview": "What is machine learning?"
    }
  ]
}
```

**Example (PowerShell):**
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/"
Invoke-RestMethod -Uri $uri -Method GET
```

---

### 3. Get Conversation Details
**Retrieve full conversation with all message history**

```
GET /api/chat/conversations/{conversation_id}/
```

**URL Parameters:**
- `conversation_id` (UUID) - ID from create conversation response

**Response (200 OK):**
```json
{
  "id": "6c1696f4-0de1-46f7-b351-f9ab6a1ece03",
  "title": "My Conversation",
  "user": "test_user",
  "is_active": true,
  "model_used": "gpt-5.5",
  "total_tokens_used": 410,
  "message_count": 4,
  "created_at": "2026-07-08T06:42:00Z",
  "last_message_at": "2026-07-08T06:43:05Z",
  "messages": [
    {
      "id": "msg-id-1",
      "role": "user",
      "content": "What is artificial intelligence?",
      "tokens_used": 0,
      "created_at": "2026-07-08T06:42:15Z"
    },
    {
      "id": "msg-id-2",
      "role": "assistant",
      "content": "Artificial intelligence (AI) is...",
      "tokens_used": 141,
      "created_at": "2026-07-08T06:42:20Z"
    },
    {
      "id": "msg-id-3",
      "role": "user",
      "content": "Can you give me a Python example of a simple AI?",
      "tokens_used": 0,
      "created_at": "2026-07-08T06:43:00Z"
    },
    {
      "id": "msg-id-4",
      "role": "assistant",
      "content": "Sure – here's a very simple 'AI' in Python: a tiny rule-based chatbot...",
      "tokens_used": 269,
      "created_at": "2026-07-08T06:43:05Z"
    }
  ]
}
```

**Example (PowerShell):**
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/6c1696f4-0de1-46f7-b351-f9ab6a1ece03/"
Invoke-RestMethod -Uri $uri -Method GET
```

---

### 4. Send Message & Get Response
**Send a message to conversation and receive AI response**

```
POST /api/chat/conversations/{conversation_id}/messages/
```

**URL Parameters:**
- `conversation_id` (UUID) - Conversation ID
- `?stream=true` (optional query param) - Enable streaming responses

**Request Body:**
```json
{
  "content": "What is artificial intelligence?",
  "file": null  // optional file upload
}
```

**Response (201 Created):**
```json
{
  "id": "6b9ad7dc-a491-4665-afe5-307cc667402b",
  "role": "assistant",
  "content": "Artificial intelligence (AI) is the field of computer science focused on creating systems that can perform tasks that normally require human intelligence...",
  "tokens_used": 141,
  "file": null,
  "file_url": null,
  "file_type": "",
  "file_size_bytes": null,
  "is_streaming_complete": true,
  "error_message": "",
  "created_at": "2026-07-08T06:42:15.230463Z",
  "created_at_display": "2026-07-08 06:42:15",
  "updated_at": "2026-07-08T06:42:15.230463Z"
}
```

**Example (Non-Streaming) - PowerShell:**
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/6c1696f4-0de1-46f7-b351-f9ab6a1ece03/messages/"
$body = @{ content = "What is artificial intelligence?" } | ConvertTo-Json
Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Body $body
```

**Example (Streaming) - PowerShell:**
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/6c1696f4-0de1-46f7-b351-f9ab6a1ece03/messages/?stream=true"
$body = @{ content = "What is artificial intelligence?" } | ConvertTo-Json
Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Body $body
```

**Streaming Response Format (Server-Sent Events):**
```
data: {"content": "Artificial"}
data: {"content": " intelligence"}
data: {"content": " (AI)"}
...
data: {"done": true}
```

---

### 5. Archive Conversation
**Soft delete conversation (mark as inactive)**

```
DELETE /api/chat/conversations/{conversation_id}/
```

**URL Parameters:**
- `conversation_id` (UUID) - Conversation ID

**Response (200 OK):**
```json
{
  "deleted": true,
  "id": "6c1696f4-0de1-46f7-b351-f9ab6a1ece03"
}
```

**Example (PowerShell):**
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/6c1696f4-0de1-46f7-b351-f9ab6a1ece03/"
Invoke-RestMethod -Uri $uri -Method DELETE
```

---

### 6. Generate Code
**Generate code for a specific requirement**

```
POST /api/chat/generate-code/
```

**Request Body:**
```json
{
  "requirement": "Create a Python function to check if a number is prime",
  "language": "python"  // python, javascript, java, cpp, csharp, etc.
}
```

**Response (200 OK):**
```json
{
  "code": "def is_prime(n):\n    # Check if number is less than 2\n    if n < 2:\n        return False\n    \n    # Check for factors from 2 to sqrt(n)\n    for i in range(2, int(n ** 0.5) + 1):\n        if n % i == 0:\n            return False\n    \n    return True\n\n# Test cases\nprint(is_prime(2))    # True\nprint(is_prime(17))   # True\nprint(is_prime(20))   # False",
  "language": "python",
  "tokens_used": 156
}
```

**Example (PowerShell):**
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/generate-code/"
$body = @{ 
  requirement = "Create a Python function to check if a number is prime"
  language = "python" 
} | ConvertTo-Json
Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Body $body
```

---

### 7. Summarize Text
**Summarize any text to a specified length**

```
POST /api/chat/summarize/
```

**Request Body:**
```json
{
  "text": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed. It focuses on developing algorithms that can access data and learn from it independently.",
  "max_length": 100  // max characters for summary
}
```

**Response (200 OK):**
```json
{
  "summary": "Machine learning lets AI systems learn from data without explicit programming.",
  "tokens_used": 32,
  "original_length": 256,
  "summary_length": 78
}
```

**Example (PowerShell):**
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/summarize/"
$body = @{ 
  text = "Machine learning is a subset of artificial intelligence..."
  max_length = 100 
} | ConvertTo-Json
Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Body $body
```

---

## Response Status Codes

| Code | Meaning | Example |
|------|---------|---------|
| `200` | OK | Successful GET request |
| `201` | Created | Successful POST (message sent, conversation created) |
| `400` | Bad Request | Missing required fields |
| `404` | Not Found | Conversation ID doesn't exist |
| `500` | Server Error | Azure OpenAI API error, database error |

---

## Error Handling

**Error Response Format:**
```json
{
  "error": "Error message here",
  "detail": "Additional details if available"
}
```

**Example Errors:**

Missing required field:
```json
{
  "error": "Content is required"
}
```

Conversation not found:
```json
{
  "error": "Conversation not found"
}
```

OpenAI API error:
```json
{
  "error": "Azure OpenAI API error: [specific error]"
}
```

---

## Data Types & Models

### ChatConversation
```json
{
  "id": "UUID",
  "title": "String",
  "user": "String (username)",
  "is_active": "Boolean",
  "model_used": "String (gpt-5.5, gpt-4o, etc)",
  "total_tokens_used": "Integer",
  "message_count": "Integer",
  "created_at": "ISO 8601 DateTime",
  "updated_at": "ISO 8601 DateTime",
  "last_message_at": "ISO 8601 DateTime or null"
}
```

### ChatMessage
```json
{
  "id": "UUID",
  "role": "String (user, assistant, system)",
  "content": "String (message text)",
  "tokens_used": "Integer",
  "file": "File object or null",
  "file_url": "String or null",
  "file_type": "String (pdf, txt, code, image, etc)",
  "file_size_bytes": "Integer or null",
  "is_streaming_complete": "Boolean",
  "error_message": "String or empty",
  "created_at": "ISO 8601 DateTime",
  "updated_at": "ISO 8601 DateTime"
}
```

---

## Features & Capabilities

### ✅ Multi-turn Conversations
Each message includes conversation history automatically. The AI remembers previous messages in the conversation and can reference them.

**Example:**
```
User: What is Python?
AI: Python is a programming language...

User: Show me an example
AI: Here's an example: [Python code]
// AI knows you're asking about Python from the previous message
```

### ✅ Token Tracking
Every response includes `tokens_used` field showing how many tokens were consumed by that specific message.

### ✅ Streaming Responses
Enable real-time responses with `?stream=true` query parameter for Server-Sent Events (SSE) format data.

### ✅ Session Audit Logging
All activities are logged with:
- Event type (message_sent, response_received, etc)
- Timestamps
- Tokens used
- Errors (if any)

### ✅ File Support
Messages can include file attachments (pdf, txt, code, images, etc) - currently validated in models, integration with file processing pending.

### ✅ Anonymous Access
No authentication required - works for both logged-in users and anonymous visitors.

---

## Usage Examples

### Example 1: Simple Q&A Flow
```powershell
# 1. Create conversation
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/"
$conv = Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Body (@{title="QA Chat"} | ConvertTo-Json)
$convId = $conv.id

# 2. Send message
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/$convId/messages/"
$resp = Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Body (@{content="What is AI?"} | ConvertTo-Json)
Write-Host $resp.content
Write-Host "Tokens used: $($resp.tokens_used)"

# 3. Get full conversation
$uri = "http://localhost:8000/chatgpt/api/chat/conversations/$convId/"
$full = Invoke-RestMethod -Uri $uri -Method GET
Write-Host "Total messages: $($full.message_count)"
Write-Host "Total tokens: $($full.total_tokens_used)"
```

### Example 2: Code Generation Workflow
```powershell
$uri = "http://localhost:8000/chatgpt/api/chat/generate-code/"
$body = @{
  requirement = "Create a REST API endpoint for user authentication"
  language = "python"
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri $uri -Method POST -ContentType "application/json" -Body $body
Write-Host $result.code
```

### Example 3: Multi-turn Conversation with Context
```powershell
# First message
$body1 = @{content="Explain quantum computing"} | ConvertTo-Json
$msg1 = Invoke-RestMethod -Uri "$uri/messages/" -Method POST -ContentType "application/json" -Body $body1

# Second message - AI remembers quantum computing from first message
$body2 = @{content="How does it differ from classical computing?"} | ConvertTo-Json
$msg2 = Invoke-RestMethod -Uri "$uri/messages/" -Method POST -ContentType "application/json" -Body $body2
# Response will reference quantum computing without you mentioning it again
```

---

## Access Control

**Current Configuration:**
- ✅ Available for: **All Users** (authenticated & anonymous)
- ✅ Available for: **Admins**
- ✅ Authentication: **NOT REQUIRED**

Anonymous users are automatically assigned to `test_user` account for tracking purposes.

---

## Rate Limiting & Quotas

Currently: **No rate limiting**

Future considerations:
- Per-user token limits
- Request rate limiting
- Conversation limits

---

## Technology Stack

- **Backend Framework:** Django REST Framework
- **AI Model:** Azure OpenAI (gpt-5.5)
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **API Version:** 2024-06-01

---

## Support & Debugging

### Enable Debug Logging
Check Django terminal for detailed logs:
```
[AIChat] Streaming response for user message: ...
[AIChat] Response received: X tokens used
[AIChat] Streaming completed successfully
```

### Common Issues

**Issue:** "Conversation not found"
- Ensure conversation ID is correct
- Verify conversation belongs to current user

**Issue:** "JSON parse error"
- Check request body is valid JSON
- Verify all required fields are present

**Issue:** "Azure OpenAI API error"
- Check AZURE_OPENAI_* environment variables
- Verify API key and endpoint are correct
- Check rate limits not exceeded

---

## Next Steps for Frontend Team

1. ✅ Use endpoints to create chat UI
2. ✅ Implement conversation list view
3. ✅ Build message display with streaming support
4. ✅ Add code syntax highlighting for code generation responses
5. ✅ Implement file upload UI
6. ✅ Add token usage display
7. ✅ Create conversation archive functionality

---

**API Status:** ✅ TESTED & WORKING
**Last Updated:** 2026-07-08
**Model Version:** gpt-5.5
