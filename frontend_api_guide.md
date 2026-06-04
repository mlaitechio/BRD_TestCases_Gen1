# BRD Automation - Frontend API Integration Guide

This guide outlines the step-by-step API integration for the frontend developer to build the AI BRD Generation UI.

**Base URL**: `http://localhost:8000/api/projects`

---

## The 5-Step Pipeline Flow

### Step 1: Create Project & Start Clarification
**Endpoint**: `POST /`
**Payload**: 
```json
{
  "raw_input": "User's typed project description..."
}
```
*(Note: Can also use `multipart/form-data` with `uploaded_file` if uploading a document)*
**Response**: `201 Created`
```json
{
  "id": "uuid-here",
  "status": "new",
  "message": "Project created. Generating clarification questions..."
}
```
**Frontend Action**: Save the `id` to state, and begin polling the `/status/` endpoint (Step 2).

### Step 2: Poll Status & Get Questions
**Endpoint**: `GET /{id}/status/`
Poll this endpoint every 2-3 seconds.
Watch for `status === 'awaiting_answers'`.

When the status changes to `awaiting_answers`, fetch the questions:
**Endpoint**: `GET /{id}/clarification-questions/`
**Response**:
```json
{
  "questions": [
    {
      "id": "Q1",
      "question": "What is the primary target audience?",
      "why_asking": "Needed to determine UX requirements"
    }
  ]
}
```
**Frontend Action**: Render the questions to the user and collect their text inputs.

### Step 3: Submit Answers & Start BRD Generation
**Endpoint**: `POST /{id}/answer-questions/`
**Payload**:
```json
{
  "answers": {
    "Q1": "User's answer here",
    "Q2": "Another answer here"
  }
}
```
**Frontend Action**: After successful 200 OK, resume polling `/status/`. Watch for `status === 'awaiting_approval'`.

### Step 4: Show BRD & Approve
When status is `awaiting_approval`, the BRD is ready. 
You can fetch the JSON data to display in the UI:
**Endpoint**: `GET /{id}/brd/`

You can also let the user download the DOCX file immediately!
**Endpoint**: `GET /{id}/download/brd/` *(Triggers file download)*

If the user clicks "Approve BRD":
**Endpoint**: `POST /{id}/approve-brd/`
**Frontend Action**: Resume polling `/status/`. Watch for `status === 'complete'`.

### Step 5: Download Remaining Documents
When status is `complete`, the remaining AI agents are done. You can provide download buttons for the final documents:
**Endpoints**:
- `GET /{id}/download/plan/`
- `GET /{id}/download/testcases/`
- `GET /{id}/download/effort/`

*(Note: Files are downloaded as `application/vnd.openxmlformats-officedocument.wordprocessingml.document` and automatically named using a short, readable project title).*

---

### Alternative: Requesting a Revision
If the user reviews the BRD in Step 4 and wants to reject it and request changes:
**Endpoint**: `POST /{id}/revise-brd/`
**Payload**:
```json
{
  "revision_notes": "Please add more focus on security compliance."
}
```
**Frontend Action**: Resume polling `/status/`. It will go back to `generating_brd` and eventually return to `awaiting_approval`.
