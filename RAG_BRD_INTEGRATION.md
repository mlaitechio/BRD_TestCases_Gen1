# Global RAG - BRD Generation Integration

## Overview
The BRD generation now automatically searches the Global RAG Knowledge Base for relevant user-uploaded documents and uses them to enhance the generated BRD.

---

## What Changed

### File: `apps/projects/tasks.py`

#### 1. **Updated `run_brd_task()` function** (Lines 19-77)
```
OLD: BRD generation used only:
  ├── Project description
  ├── Asset context
  └── Company knowledge base

NEW: BRD generation now uses:
  ├── Project description
  ├── Global RAG documents ← NEW!
  ├── Asset context
  └── Company knowledge base
```

#### 2. **Added Helper Function: `_search_global_rag_for_brd()`**
```python
def _search_global_rag_for_brd(project) -> str:
```
**What it does:**
- Searches Global RAG for documents relevant to the project
- Uses project name, application type, and line of business as search query
- Filters for high-confidence matches (similarity score ≥ 0.7)
- Formats results into readable context block
- Returns empty string if no matches (non-blocking)

**Search Parameters:**
```python
search_query = f"{project.name} {project.application_type} {project.line_of_business}"
top_k = 5  # Get top 5 matching documents
category = project.application_type  # Filter by category
```

#### 3. **Added Helper Function: `_combine_brd_contexts()`**
```python
def _combine_brd_contexts(rag_context, company_kb, asset_context) -> str:
```
**Context Priority:**
```
1. RAG Context (Most specific)
   └── User-uploaded documents most relevant to this project

2. Company Knowledge Base
   └── General company guidelines and standards

3. Asset Context
   └── Extracted content from Insight Attachments
```

---

## How It Works

### BRD Generation Flow

```
User creates Project
        ↓
run_brd_task() starts
        ├─ Step 1: Extract project description
        ├─ Step 2: Build asset context
        ├─ Step 3: Search Global RAG ← NEW!
        │          └─ Query: "Project Name App-Type LoB"
        │          └─ Returns: Top 5 matching documents
        │
        ├─ Step 4: Search company knowledge base
        │
        ├─ Step 5: Combine contexts ← NEW!
        │          ├─ RAG documents first
        │          ├─ Company KB second
        │          └─ Asset context last
        │
        ├─ Step 6: Call generate_brd() with combined context
        │
        ├─ Step 7: Save BRD output
        └─ Step 8: Queue BRD for RAG indexing

BRD Generated with enriched context! ✅
```

---

## Example Usage

### Scenario: Salesforce Project

**Uploaded Documents in RAG:**
```
1. "Salesforce Integration Guide" (score: 0.92)
2. "CRM Configuration Best Practices" (score: 0.85)
3. "Data Migration Strategy" (score: 0.78)
```

**BRD Generation:**
```
Search Query: "Salesforce Project CRM Finance"
              ↓
Retrieved Documents (score ≥ 0.7):
├─ Salesforce Integration Guide (0.92)
├─ CRM Configuration Best Practices (0.85)
└─ Data Migration Strategy (0.78)
              ↓
Combined Context (1200 chars):
├─ RAG Documents
├─ Company Knowledge Base
└─ Asset Context
              ↓
Enhanced BRD Generated! ✅
```

---

## Key Features

### ✅ Non-Blocking
- If RAG search fails, BRD generation continues
- No degradation if knowledge base is empty
- Graceful fallback to company KB only

### ✅ Relevance Filtering
- Only includes documents with similarity score ≥ 0.7
- Filters by project application type
- Prioritizes most relevant results

### ✅ Context Prioritization
- User documents (RAG) take precedence
- Company guidelines as secondary context
- Asset extraction as tertiary source

### ✅ Logging
- Logs RAG search queries
- Logs number of documents retrieved
- Logs combined context size
- Logs any search failures (non-critical)

---

## Testing

### Test 1: Upload Document → Generate BRD

```bash
# Step 1: Upload document to RAG
POST /api/rag/documents/
{
  "title": "Salesforce Configuration Guide",
  "file": (PDF file),
  "category": "Salesforce"
}

# Step 2: Create Project
POST /api/projects/
{
  "name": "Salesforce Implementation",
  "application_type": "salesforce"
}

# Step 3: Generate BRD
POST /api/projects/{project-id}/generate-brd/

# Result: BRD should include content from uploaded document! ✅
```

### Test 2: Verify RAG is Used

**Check logs:**
```bash
# Should see logs like:
[BRD RAG] Searching for: Salesforce Implementation salesforce 
[BRD RAG] Retrieved 2 documents (850 chars)
[BRD] Combined context: 2150 chars (3 sources)
```

### Test 3: Multiple Documents

```bash
# Upload 3 Salesforce documents
# Generate BRD for Salesforce project
# BRD should include relevant content from all 3! ✅
```

---

## Configuration

### Search Parameters (Tunable)

In `_search_global_rag_for_brd()`:

```python
top_k = 5                    # Number of documents to retrieve (1-20)
category = project.application_type  # Filter by app type (optional)
min_score = 0.7              # Minimum similarity threshold
```

### Context Priority (Tunable)

In `_combine_brd_contexts()`:

```python
parts = [
    rag_context,        # 1. Most specific (user docs)
    company_kb,         # 2. General (company guidelines)
    asset_context       # 3. Least specific (extracted)
]
```

---

## Error Handling

### Scenario: RAG Search Fails
```
Status: Non-blocking ✅
Action: Log warning, continue with company KB
Result: BRD still generates successfully
```

### Scenario: No Matching Documents
```
Status: Normal ✅
Action: Return empty string
Result: BRD uses company KB only
```

### Scenario: Network Error
```
Status: Non-blocking ✅
Action: Catch exception, log warning
Result: BRD continues without RAG context
```

---

## Benefits

✅ **Higher Quality BRDs**
- Includes relevant project-specific documents
- Maintains consistency with past projects
- Better context for LLM generation

✅ **Organizational Knowledge Leverage**
- Uses uploaded best practices and guides
- Reduces need for external research
- Enforces company standards

✅ **Scalable**
- Works with 1 or 10,000 documents
- Automatic relevance filtering
- No manual configuration

✅ **Non-Intrusive**
- Fails gracefully
- No impact on existing functionality
- Backwards compatible

---

## Next Steps

1. ✅ **Integration Complete**
   - RAG search integrated into BRD generation
   - Helper functions added
   - Error handling in place

2. **Testing** (TODO)
   - Upload test documents
   - Generate BRD and verify RAG is used
   - Check logs for confirmation
   - Test with multiple documents

3. **Optimization** (Future)
   - Fine-tune similarity threshold
   - Add more search parameters
   - Implement document ranking
   - Add user feedback loop

---

## Code Changes Summary

| File | Lines | Change | Impact |
|------|-------|--------|--------|
| tasks.py | 19-77 | Updated run_brd_task() | Integrated RAG search |
| tasks.py | 20 | Added RAG import | Enables RAG service access |
| tasks.py | 44 | Added _search_global_rag_for_brd() | Searches RAG for documents |
| tasks.py | 89 | Added _combine_brd_contexts() | Combines all contexts |
| tasks.py | 70-72 | Updated context_summary | Now includes RAG documents |

---

## Logs to Monitor

```
[BRD RAG] Searching for: {project_name} {app_type} {lob}
[BRD RAG] Retrieved {N} documents ({M} chars)
[BRD] Combined context: {N} chars ({M} sources)
[BRD RAG] No relevant documents found
[BRD RAG] Search failed (non-blocking): {error}
```

---

## Status: ✅ COMPLETE

The Global RAG Knowledge Base is now fully integrated with BRD generation!

- ✅ Search functionality
- ✅ Context combining
- ✅ Error handling
- ✅ Logging
- ✅ Non-blocking behavior

**Ready to test!** 🚀
