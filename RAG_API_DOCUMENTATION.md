# Global RAG Knowledge Base - API Documentation

## Overview
The Global RAG API provides endpoints to upload, manage, and search documents in the knowledge base.

Username: admin
Email: admin@test.com
Password: admin123
Password (again): admin123
Superuser created successfully.


http://localhost:8000/chatgpt/admin/




========================================
RAG API ENDPOINTS
========================================

POST   /api/rag/documents/                    - Upload document
GET    /api/rag/documents/                    - List all documents
GET    /api/rag/documents/{id}/               - Get document details
DELETE /api/rag/documents/{id}/               - Delete document
GET    /api/rag/documents/{id}/status/        - Check indexing status
POST   /api/rag/documents/{id}/reindex/       - Reindex document
POST   /api/rag/search/                       - Search knowledge base
GET    /api/rag/stats/                        - Get RAG statistics

Base URL: http://localhost:8000/api/rag/

Documentation: See above for request/response formats andgo through this for clear understanding
========================================


---

## Base URL
```
Development:  http://localhost:8000/api/rag/
Production:   https://your-domain.com/api/rag/
```
testing without ui - http://localhost:8000/chatgpt/admin/

---

## Authentication
Currently **NO authentication required** for development.

For production, add JWT token in header:
```
Authorization: Bearer <jwt_token>
```

---

## File Validation Rules

### Allowed File Types
```
✅ PDF    (.pdf)
✅ DOCX   (.docx)
✅ TXT    (.txt)
✅ XLSX   (.xlsx)
✅ XLS    (.xls)
✅ CSV    (.csv)
❌ Others (will be rejected)
```

### File Size Limits
```
Max file size:  100 MB
Min file size:  1 KB
```

### Title Validation
```
Required:       Yes
Max length:     255 characters
Min length:     1 character
```

### Error: Invalid File Type
```json
{
  "file": ["Only PDF, DOCX, TXT, XLSX, XLS, and CSV files allowed. Got: .doc"]
}
```

### Error: File Too Large
```json
{
  "file": ["File size exceeds 100MB limit"]
}
```

---

## API Endpoints

### 1. Upload Document
**POST** `/api/rag/documents/`

#### Request Format
```
Content-Type: multipart/form-data

Parameters:
- title (string, required)        - Document title (1-255 chars)
- description (string, optional)  - Document description
- file (file, required)          - PDF/DOCX/TXT file
- category (string, optional)    - e.g., "Salesforce", "ServiceNow", "General"
- tags (string, optional)        - Comma-separated tags
- created_by (string, optional)  - Username or email
```

#### Success Response (201 Created)
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Sales Process Documentation",
  "description": "Complete sales workflow",
  "source": "admin",
  "status": "pending",
  "file_type": "pdf",
  "file_size_bytes": 2500000,
  "chunk_count": 0,
  "category": "Salesforce",
  "tags": "sales,workflow,2026",
  "created_by": "admin@company.com",
  "created_at": "2026-07-06T15:30:00Z",
  "indexed_at": null,
  "error_message": ""
}
```

#### Error Responses

**400 Bad Request** - Missing required field
```json
{
  "title": ["This field is required."],
  "file": ["This field is required."]
}
```

**400 Bad Request** - Invalid file type
```json
{
  "file": ["Only PDF, DOCX, and TXT files allowed. Got: .exe"]
}
```

**400 Bad Request** - File too large
```json
{
  "file": ["File size exceeds 50MB limit"]
}
```

**500 Internal Server Error** - Server error
```json
{
  "error": "An unexpected error occurred during upload"
}
```

---

### 2. List All Documents
**GET** `/api/rag/documents/`

#### Response (200 OK)
```json
{
  "count": 3,
  "documents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Sales Process",
      "source": "admin",
      "source_display": "Admin Upload",
      "status": "indexed",
      "status_display": "Indexed",
      "file_type": "pdf",
      "file_size_bytes": 2500000,
      "chunk_count": 12,
      "category": "Salesforce",
      "tags": "sales,workflow",
      "created_at": "2026-07-06T15:30:00Z",
      "indexed_at": "2026-07-06T15:35:00Z"
    }
  ]
}
```

---

### 3. Get Document Status
**GET** `/api/rag/documents/{id}/status/`

#### URL Parameters
```
id (string, required) - Document UUID
```

#### Response (200 OK)
```json
{
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Sales Process",
  "status": "indexed",
  "status_display": "Indexed",
  "chunk_count": 12,
  "indexed_at": "2026-07-06T15:35:00Z",
  "error_message": "",
  "recent_logs": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "operation": "index",
      "operation_display": "Index",
      "status": "success",
      "status_display": "Success",
      "chunks_created": 12,
      "error_message": "",
      "duration_seconds": 15.5,
      "created_at": "2026-07-06T15:35:00Z"
    }
  ]
}
```

#### Status Values
```
pending        - Waiting to be indexed
indexing       - Currently being processed
indexed        - Successfully indexed ✅
failed         - Indexing failed ❌
```

#### Error Response (404 Not Found)
```json
{
  "error": "Document 550e8400... not found"
}
```

---

### 4. Search Knowledge Base
**POST** `/api/rag/search/`

#### Request Body
```json
{
  "query": "Salesforce integration workflow",
  "top_k": 5,
  "category": "Salesforce"
}
```

#### Parameters
```
query (string, required)        - Search query text
top_k (integer, optional)       - Max results (default: 5, max: 20)
category (string, optional)     - Filter by category
```

#### Response (200 OK)
```json
{
  "query": "Salesforce integration workflow",
  "total_results": 2,
  "results": [
    {
      "rank": 1,
      "content": "The Salesforce integration workflow includes the following steps: 1. Data mapping 2. Field validation 3. Record creation 4. Error handling...",
      "similarity_score": 0.92,
      "category": "Salesforce",
      "document_id": "550e8400-e29b-41d4-a716-446655440000",
      "chunk_index": 3
    },
    {
      "rank": 2,
      "content": "Integration best practices: Always validate data before sync...",
      "similarity_score": 0.78,
      "category": "Salesforce",
      "document_id": "550e8400-e29b-41d4-a716-446655440001",
      "chunk_index": 1
    }
  ]
}
```

#### Error Response (400 Bad Request)
```json
{
  "error": "Query parameter is required"
}
```

#### No Results (200 OK - Empty)
```json
{
  "query": "xyz123abc",
  "total_results": 0,
  "results": []
}
```

---

### 5. Get Statistics
**GET** `/api/rag/stats/`

#### Response (200 OK)
```json
{
  "total_documents": 5,
  "indexed_documents": 4,
  "pending_documents": 1,
  "failed_documents": 0,
  "total_chunks": 48,
  "by_source": {
    "admin": 3,
    "insight_attachment": 2
  }
}
```

---

### 6. Delete Document
**DELETE** `/api/rag/documents/{id}/`

#### Response (204 No Content)
```
(empty body - just status code 204)
```

#### Error Response (404 Not Found)
```json
{
  "error": "Document 550e8400... not found"
}
```

---

### 7. Reindex Document
**POST** `/api/rag/documents/{id}/reindex/`

#### Response (200 OK)
```json
{
  "message": "Document reindexing started",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "indexing"
}
```

---

## Status Polling Strategy

### Recommended Polling Flow

```
1. Upload Document
   ↓ Get document ID from response
   ↓
2. Start Polling /status/ endpoint
   Poll every 2-3 seconds
   ↓
3. Check Status
   - "pending"   → Wait, poll again
   - "indexing"  → Wait, poll again
   - "indexed"   → SUCCESS! ✅ Stop polling
   - "failed"    → ERROR! ❌ Show error message
   ↓
4. Timeout
   If still "pending" after 5 minutes → Show timeout error
```

### Polling Parameters
```
Initial delay:    500ms (optional - let backend start)
Poll interval:    2-3 seconds (good balance)
Max wait time:    5 minutes
Timeout message:  "Document indexing is taking longer than expected"
```

### JavaScript Example
```javascript
async function pollStatus(docId, maxWaitMs = 5 * 60 * 1000) {
  const startTime = Date.now();
  
  while (Date.now() - startTime < maxWaitMs) {
    const response = await fetch(`/api/rag/documents/${docId}/status/`);
    const data = await response.json();
    
    if (data.status === 'indexed') {
      return { success: true, chunks: data.chunk_count };
    }
    
    if (data.status === 'failed') {
      return { success: false, error: data.error_message };
    }
    
    // Wait 2 seconds before polling again
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
  
  return { success: false, error: 'Indexing timeout' };
}
```

---

## Frontend Integration Examples

### React Component Example

```jsx
import React, { useState } from 'react';

export function RAGDocumentUpload() {
  const [title, setTitle] = useState('');
  const [file, setFile] = useState(null);
  const [category, setCategory] = useState('General');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // Step 1: Upload document
      const formData = new FormData();
      formData.append('title', title);
      formData.append('file', file);
      formData.append('category', category);
      formData.append('created_by', 'user@company.com');

      const uploadResponse = await fetch('/api/rag/documents/', {
        method: 'POST',
        body: formData,
      });

      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json();
        throw new Error(JSON.stringify(errorData));
      }

      const docData = await uploadResponse.json();
      const docId = docData.id;

      setStatus(`Document uploaded. Document ID: ${docId}`);

      // Step 2: Poll for indexing status
      const result = await pollIndexing(docId);

      if (result.success) {
        setStatus(`✅ Successfully indexed! ${result.chunks} chunks created.`);
        // Reset form
        setTitle('');
        setFile(null);
        setCategory('General');
      } else {
        setError(`❌ Indexing failed: ${result.error}`);
      }
    } catch (err) {
      setError(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const pollIndexing = async (docId) => {
    const maxWaitMs = 5 * 60 * 1000;
    const startTime = Date.now();

    while (Date.now() - startTime < maxWaitMs) {
      const statusResponse = await fetch(`/api/rag/documents/${docId}/status/`);
      const statusData = await statusResponse.json();

      setStatus(`Status: ${statusData.status_display}`);

      if (statusData.status === 'indexed') {
        return { success: true, chunks: statusData.chunk_count };
      }

      if (statusData.status === 'failed') {
        return { success: false, error: statusData.error_message };
      }

      // Wait 2 seconds before polling again
      await new Promise(resolve => setTimeout(resolve, 2000));
    }

    return { success: false, error: 'Timeout' };
  };

  return (
    <div className="rag-upload-form">
      <h2>Upload to Knowledge Base</h2>

      {error && <div className="error">{error}</div>}
      {status && <div className="status">{status}</div>}

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Document Title *</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label>Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            disabled={loading}
          >
            <option>General</option>
            <option>Salesforce</option>
            <option>ServiceNow</option>
            <option>SAP</option>
          </select>
        </div>

        <div className="form-group">
          <label>File (PDF, DOCX, TXT, XLSX, XLS, CSV - Max 100MB) *</label>
          <input
            type="file"
            onChange={(e) => setFile(e.target.files[0])}
            accept=".pdf,.docx,.txt,.xlsx,.xls,.csv"
            required
            disabled={loading}
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading ? 'Uploading...' : 'Upload Document'}
        </button>
      </form>
    </div>
  );
}
```

### Vue Component Example

```vue
<template>
  <div class="rag-upload-form">
    <h2>Upload to Knowledge Base</h2>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="status" class="status">{{ status }}</div>

    <form @submit.prevent="handleSubmit">
      <div class="form-group">
        <label>Document Title *</label>
        <input
          v-model="title"
          type="text"
          required
          :disabled="loading"
        />
      </div>

      <div class="form-group">
        <label>Category</label>
        <select v-model="category" :disabled="loading">
          <option>General</option>
          <option>Salesforce</option>
          <option>ServiceNow</option>
        </select>
      </div>

      <div class="form-group">
        <label>File (PDF, DOCX, TXT, XLSX, XLS, CSV - Max 100MB) *</label>
        <input
          type="file"
          @change="(e) => file = e.target.files[0]"
          accept=".pdf,.docx,.txt,.xlsx,.xls,.csv"
          required
          :disabled="loading"
        />
      </div>

      <button type="submit" :disabled="loading">
        {{ loading ? 'Uploading...' : 'Upload Document' }}
      </button>
    </form>
  </div>
</template>

<script>
export default {
  data() {
    return {
      title: '',
      file: null,
      category: 'General',
      loading: false,
      status: '',
      error: '',
    };
  },
  methods: {
    async handleSubmit() {
      this.loading = true;
      this.error = '';

      try {
        // Upload document
        const formData = new FormData();
        formData.append('title', this.title);
        formData.append('file', this.file);
        formData.append('category', this.category);
        formData.append('created_by', 'user@company.com');

        const uploadResponse = await fetch('/api/rag/documents/', {
          method: 'POST',
          body: formData,
        });

        if (!uploadResponse.ok) {
          throw new Error('Upload failed');
        }

        const docData = await uploadResponse.json();
        const docId = docData.id;

        this.status = `Document uploaded. ID: ${docId}`;

        // Poll for status
        const result = await this.pollIndexing(docId);

        if (result.success) {
          this.status = `✅ Successfully indexed! ${result.chunks} chunks.`;
          this.title = '';
          this.file = null;
          this.category = 'General';
        } else {
          this.error = `❌ Indexing failed: ${result.error}`;
        }
      } catch (err) {
        this.error = `Error: ${err.message}`;
      } finally {
        this.loading = false;
      }
    },

    async pollIndexing(docId) {
      const maxWaitMs = 5 * 60 * 1000;
      const startTime = Date.now();

      while (Date.now() - startTime < maxWaitMs) {
        const statusResponse = await fetch(`/api/rag/documents/${docId}/status/`);
        const statusData = await statusResponse.json();

        this.status = `Status: ${statusData.status_display}`;

        if (statusData.status === 'indexed') {
          return { success: true, chunks: statusData.chunk_count };
        }

        if (statusData.status === 'failed') {
          return { success: false, error: statusData.error_message };
        }

        await new Promise(resolve => setTimeout(resolve, 2000));
      }

      return { success: false, error: 'Timeout' };
    },
  },
};
</script>
```

---

## Error Handling Checklist

```
✅ Validate file type before upload
✅ Validate file size before upload
✅ Show upload progress
✅ Handle network errors gracefully
✅ Handle timeout errors
✅ Display error messages to user
✅ Show indexing status updates
✅ Retry failed uploads (optional)
✅ Show success notification
✅ Reset form after successful upload
```

---

## HTTP Status Codes

```
200 OK              - Successful GET/POST request
201 Created         - Document successfully uploaded
204 No Content      - Successful DELETE request
400 Bad Request     - Invalid input/validation error
404 Not Found       - Document not found
500 Server Error    - Internal server error
```

---

## Testing Checklist for UI Developer

```
☐ Upload small PDF (< 1MB)
☐ Upload larger PDF (> 10MB)
☐ Upload DOCX file
☐ Upload TXT file
☐ Try uploading unsupported file (.exe, .zip)
☐ Try uploading without title
☐ Try uploading without file
☐ Check polling updates status correctly
☐ Verify error messages display
☐ Test on slow network (use browser DevTools)
☐ Test search returns results
☐ Test list documents endpoint
☐ Test delete document endpoint
```

---

## Notes

- Indexing typically takes 10-30 seconds depending on file size
- Search requires at least 1 indexed document
- All timestamps are in UTC
- Document IDs are UUIDs (globally unique)
- Max concurrent uploads: No limit (backend handles queuing)

---

**Questions?** Contact backend team! 🚀
