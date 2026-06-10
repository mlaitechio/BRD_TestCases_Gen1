# BRD Automation - Frontend API Integration Guide

This guide outlines the step-by-step API integration for the frontend developer to build the AI BRD Generation UI.

**Base URL**: `http://localhost:8000/api/projects`

---

## The 4-Step Pipeline Flow

### Step 1: Create Project
**Endpoint**: `POST /`
**Payload**: 
```json
{
  "name": "Customer Portal",
  "line_of_business": "Retail Banking",
  "application_type": "salesforce",
  "department": "Digital Products",
  "raw_input": "User's typed project description..."
}
```
*(Note: Can also use `multipart/form-data` with `uploaded_file` if uploading a document)*
**application_type choices**: `salesforce`, `servicenow`, `sap`, `custom`

**Response**: `201 Created`
```json
{
  "id": "uuid-here",
  "status": "new",
  "message": "Project created successfully."
}
```
**Frontend Action**: Save the `id` to state, and redirect user to the workspace.

---

### Step 2: Configure Workspace (Optional)
While in the workspace, the user can:
1. **Upload Assets**: `POST /{id}/assets/` (mom, architecture, document, etc.)
2. **Toggle Assets**: `PATCH /{id}/assets/{asset_id}/toggle/`
3. **Configure TOC**: `PUT /{id}/toc/` (reorder/rename sections)

---

### Step 3: Trigger BRD Generation
When the user clicks the "Generate BRD" button:
**Endpoint**: `POST /{id}/generate-brd/`
**Response**: `200 OK`
```json
{
  "id": "uuid-here",
  "status": "generating_brd",
  "message": "BRD generation started..."
}
```
**Frontend Action**: Show loading spinner and start polling `/status/` (Step 4).

---

### Step 4: Poll Status & Show BRD
**Endpoint**: `GET /{id}/status/`
Poll this endpoint every 3 seconds. Watch for `status === 'awaiting_approval'`.

When ready, fetch the full BRD JSON:
**Endpoint**: `GET /{id}/brd/`

If the user clicks "Approve BRD":
**Endpoint**: `POST /{id}/approve-brd/`
**Frontend Action**: Change status to `approved`. The user can now manually trigger generation of the Plan, Test Cases, and Effort.

If the user requests a revision:
**Endpoint**: `POST /{id}/revise-brd/`
**Payload**:
```json
{
  "revision_notes": "Please add focus on security..."
}
```
**Frontend Action**: Poll `/status/` until it goes back to `awaiting_approval`.

---

### Step 5: Manually Generate Deliverables
Once the BRD is approved (`status === 'approved'`), the user can click buttons to trigger the generation of the remaining execution documents.

1. **Generate Project Plan**:
   **Endpoint**: `POST /{id}/generate-plan/`
2. **Generate Test Cases**:
   **Endpoint**: `POST /{id}/generate-testcases/`
3. **Generate Effort Estimation**:
   **Endpoint**: `POST /{id}/generate-effort/` (Note: Plan must be generated first).

**Frontend Action**: When these are clicked, they will return a message starting the task. You can poll the status endpoint or provide a local loading state.

---

### Step 6: View & Download Documents
When the documents are generated, you can fetch them via:
- `GET /{id}/plan/`
- `GET /{id}/testcases/`
- `GET /{id}/effort/`

Provide download buttons for DOCX formats:
- `GET /{id}/download/brd/`
- `GET /{id}/download/plan/`
- `GET /{id}/download/testcases/`
- `GET /{id}/download/effort/`
