# BRD Automation Platform — Frontend Integration Guide

> Written from the actual Django source code (models, serializers, views, URLs).  
> Every field name, constraint, and response key is exactly what the server sends/expects.

---

## Global Setup

| Setting | Value |
|---|---|
| Base URL | `http://localhost:8000/api/projects` |
| Content-Type (JSON requests) | `application/json` |
| Content-Type (file uploads) | `multipart/form-data` |
| Auth | None for now — placeholder ready for Cyberk auth |
| Default timeout | 30 seconds |
| AI endpoint timeout | 120 seconds (BRD edit, section edit, chat) |
| Download requests | No timeout — use browser redirect, not fetch |

All error responses follow this exact shape:
```
{ "error": "Human-readable message here" }
```
Always show the `error` value directly to the user.

---

## Project Status Machine

The `status` field on a project drives the entire UI. Every screen, button, and action depends on it.

| Status | Meaning | What to show |
|---|---|---|
| `new` | Project just created | Ready for asset upload & TOC configuration |
| `generating_brd` | AI is writing the BRD | Spinner — "Generating your BRD..." |
| `awaiting_approval` | BRD is ready for review | Full BRD + Approve + Revise + Chat Edit buttons |
| `approved` | BRD approved, plan/tests/effort running | Spinner — "Generating project documents..." |
| `complete` | All outputs done | All tabs enabled + all download buttons |
| `failed` | Something went wrong | Error panel showing `error_message` from status endpoint |

> **Manual Generation.** BRD generation does NOT start automatically on project creation.
> The project remains in status `new` until the user manually triggers BRD generation.
> Once triggered (via `POST /api/projects/{id}/generate-brd/`), the status changes to `generating_brd`.

---

## Polling Rules

Polling = calling an endpoint repeatedly until something changes.

**When to poll `/status/`:**
- After triggering manual BRD generation → poll until `awaiting_approval`
- After approving BRD → poll until `complete`
- After requesting a revision → poll until `awaiting_approval` again

**When to poll `/brd/chat-edit/{task_id}/`:**
- After starting a chat edit → poll until `status` is `complete` or `failed`

**Rules:**
- Interval: every **3 seconds** — never faster
- Always stop the moment the target status is reached
- Always stop if `status === "failed"`
- Hard timeout: 5 minutes — show a timeout error and a "Refresh" button
- Cancel the interval when the user leaves the page (component unmount)

---

## Endpoints

---

### 1. List All Projects

```
GET /api/projects/
```

**No request body.**

**Response — 200 OK:**
```json
[
  {
    "id": "8b6e1d3d-48b9-47c3-a543-80cb09c3eabc",
    "name": "Customer Portal",
    "line_of_business": "Retail Banking",
    "application_type": "web",
    "department": "Digital Products",
    "status": "complete",
    "brd_approved": true,
    "created_at": "2026-06-01T10:00:00Z",
    "updated_at": "2026-06-01T11:00:00Z"
  }
]
```

**What to do:** Render each project as a card. Use `status` as a colour-coded badge. Click navigates to `/projects/:id`.

---

### 2. Create Project

```
POST /api/projects/
```

> Use `multipart/form-data` if uploading a file. Use `application/json` if description is plain text only.

**Request body fields:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `name` | string | ✅ | Max 255 characters |
| `line_of_business` | string | ✅ | Max 150 characters. e.g. `"Retail Banking"` |
| `application_type` | string | ✅ | Must be one of: `salesforce` `servicenow` `sap` `custom` |
| `department` | string | ✅ | Max 150 characters. e.g. `"Finance"` |
| `raw_input` | string | One of these two is required | Free-text project description |
| `uploaded_file` | file | One of these two is required | PDF, DOCX, or TXT. Max 10 MB |

> Either `raw_input` or `uploaded_file` must be provided. Both can be sent together — they get merged.  
> If you send a file that cannot be parsed, the server deletes the project and returns 422.

**Response — 201 Created:**
```json
{
  "id": "8b6e1d3d-48b9-47c3-a543-80cb09c3eabc",
  "status": "new",
  "message": "Project created successfully."
}
```

**Error — 400 Bad Request (validation failed):**
```json
{
  "name": ["This field is required."],
  "application_type": ["\"xyz\" is not a valid choice."]
}
```
> Validation errors use field names as keys, not the generic `error` key.

**Error — 422 (file cannot be read):**
```json
{
  "error": "Could not extract text from your uploaded file. Please paste your project description as text instead."
}
```

**What to do:** Save the `id`. Navigate to the project workspace (Screen 2). Allow the user to upload insight attachments and configure the TOC first.

---

### 2.5 Generate BRD (Manual)

```
POST /api/projects/{id}/generate-brd/
```

Call this endpoint when the user clicks the "Generate BRD" button after configuring assets and Table of Contents.

**No request body.**

**Response — 200 OK:**
```json
{
  "id": "8b6e1d3d-48b9-47c3-a543-80cb09c3eabc",
  "status": "generating_brd",
  "message": "BRD generation started..."
}
```

**What to do:** Start polling `/status/` every 3 seconds until `status === "awaiting_approval"`.

---

### 3. Get Project Detail

```
GET /api/projects/{id}/
```

**No request body.**

**Response — 200 OK:**
```json
{
  "id": "8b6e1d3d-48b9-47c3-a543-80cb09c3eabc",
  "name": "Customer Portal",
  "line_of_business": "Retail Banking",
  "application_type": "web",
  "department": "Digital Products",
  "status": "awaiting_approval",
  "brd_approved": false,
  "revision_notes": null,
  "error_message": null,
  "outputs": {
    "brd": "complete",
    "plan": "pending",
    "test_cases": "pending",
    "effort": "pending"
  },
  "created_at": "2026-06-01T10:00:00Z",
  "updated_at": "2026-06-01T10:30:00Z"
}
```

**What to do:** Use this on initial page load to restore the current project state.

---

### 4. Poll Project Status ← **Poll this endpoint**

```
GET /api/projects/{id}/status/
```

**No request body.**

**Response — 200 OK:**
```json
{
  "id": "8b6e1d3d-48b9-47c3-a543-80cb09c3eabc",
  "name": "Customer Portal",
  "status": "generating_brd",
  "brd_approved": false,
  "outputs": {
    "brd": "running",
    "plan": "pending",
    "test_cases": "pending",
    "effort": "pending"
  },
  "error_message": null,
  "created_at": "2026-06-01T10:00:00Z",
  "updated_at": "2026-06-01T10:15:00Z"
}
```

> `outputs` is a dictionary — agent type → its own status (`pending` / `running` / `complete` / `failed`).  
> `error_message` is non-null only when `status === "failed"`. Always display it when present.

**Polling targets:**

| After this action | Poll until project `status` is |
|---|---|
| Project created | `awaiting_approval` |
| BRD revision submitted | `awaiting_approval` |
| Manual Generation (Plan/Test/Effort) | Poll until output status is `complete` |

---

### 5. Get BRD

```
GET /api/projects/{id}/brd/
```

**No request body.**  
**Call when:** `status === "awaiting_approval"`, `status === "approved"`, or `status === "complete"`.

**Response — 200 OK:**
```json
{
  "id": "uuid",
  "agent_type": "brd",
  "status": "complete",
  "error_message": null,
  "updated_at": "2026-06-01T10:30:00Z",
  "structured_output": {
    "executive_summary": "This project delivers...",

    "project_scope": {
      "in_scope": ["User account management", "Fund transfers"],
      "out_of_scope": ["Loan origination"]
    },

    "business_objectives": [
      {
        "id": "BO-001",
        "objective": "Reduce call centre volume by 30%",
        "metric": "Monthly call volume",
        "target": "30% reduction within 6 months of launch"
      }
    ],

    "stakeholders": [
      {
        "role": "Product Owner",
        "responsibilities": "Define and prioritise requirements",
        "interest_level": "High",
        "influence_level": "High"
      }
    ],

    "project_plan": {
      "phases": [
        {
          "phase": "Discovery",
          "duration": "4 weeks",
          "deliverables": ["Requirements document", "Wireframes"],
          "milestones": ["Stakeholder sign-off on scope"]
        }
      ]
    },

    "effort_estimation": {
      "total_estimated_hours": 1200,
      "summary": "Based on complexity analysis...",
      "breakdown": [
        {
          "component": "Authentication Module",
          "hours": 120,
          "complexity": "Medium"
        }
      ]
    },

    "functional_requirements": [
      {
        "id": "FR-001",
        "title": "Account Balance View",
        "description": "Users can view real-time account balances",
        "priority": "Must Have",
        "acceptance_criteria": ["Balance updates within 5 seconds of transaction"],
        "compliance_notes": "Mask account numbers to last 4 digits — PCI-DSS"
      }
    ],

    "non_functional_requirements": [
      {
        "id": "NFR-001",
        "category": "Performance",
        "requirement": "All pages load under 2 seconds",
        "metric": "95th percentile page load time",
        "priority": "Must Have"
      }
    ],

    "constraints_and_assumptions": {
      "constraints": [
        {
          "id": "CON-001",
          "description": "Must integrate with existing Temenos T24 core banking APIs",
          "impact": "API design is constrained by T24 interface contracts"
        }
      ],
      "assumptions": [
        {
          "id": "ASS-001",
          "description": "T24 APIs are stable and fully documented",
          "risk_if_wrong": "Significant rework of integration layer required"
        }
      ]
    },

    "success_criteria": [
      {
        "id": "SC-001",
        "criterion": "Zero critical security vulnerabilities at launch",
        "measurement_method": "Third-party penetration test report",
        "target": "0 critical, fewer than 5 high severity findings"
      }
    ],

    "glossary": [
      {
        "term": "T24",
        "definition": "Temenos core banking platform used by the organisation"
      }
    ]
  }
}
```

> `structured_output` will be `null` if BRD is still generating. Show a loading state in that case.  
> There are exactly **11 sections** — always render all of them.

**Error — 404 (BRD not generated yet):**
```json
{ "error": "brd output not available yet. Check /status/ first." }
```

---

### 6. Approve BRD

```
POST /api/projects/{id}/approve-brd/
```

**No request body.**  
**Only call when:** `status === "awaiting_approval"`. The server enforces this.

**Response — 200 OK:**
```json
{
  "id": "8b6e1d3d-48b9-47c3-a543-80cb09c3eabc",
  "status": "approved",
  "message": "BRD approved successfully."
}
```

**Error — 400 (wrong status):**
```json
{ "error": "BRD can only be approved when status is awaiting_approval. Current: complete" }
```

**What to do:** Change UI state to approved and enable the manual generation buttons for Plan, Test Cases, and Effort.

---

### 6.1 Generate Deliverables (Manual Triggers)

Once the BRD is approved, you can manually trigger generation of the supplementary documents.

**Generate Plan:**
```
POST /api/projects/{id}/generate-plan/
```
**Generate Test Cases:**
```
POST /api/projects/{id}/generate-testcases/
```
**Generate Effort Estimation:**
```
POST /api/projects/{id}/generate-effort/
```
*(Note: Effort Estimation requires the Project Plan to be completed first).*

**Responses — 200 OK:**
```json
{
  "id": "8b6e1d3d-48b9-47c3-a543-80cb09c3eabc",
  "message": "Project Plan generation started..."
}
```

---

### 7. Revise BRD

```
POST /api/projects/{id}/revise-brd/
```

**Only call when:** `status === "awaiting_approval"`.

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `revision_notes` | string | ✅ | Cannot be empty — describe what to change |

```json
{
  "revision_notes": "Please strengthen the security requirements section and add specific GDPR data handling requirements throughout."
}
```

**Response — 200 OK:**
```json
{
  "id": "8b6e1d3d-48b9-47c3-a543-80cb09c3eabc",
  "status": "generating_brd",
  "message": "Revision notes saved. Re-generating BRD..."
}
```

**Error — 400 (wrong status):**
```json
{ "error": "BRD can only be revised when status is awaiting_approval. Current: complete" }
```

**Error — 400 (empty notes):**
```json
{ "revision_notes": ["This field may not be blank."] }
```

**What to do:** Clear the displayed BRD. Start polling `/status/` until `awaiting_approval` again.

---

### 8. Get BRD (Outputs also share this structure)

> The Plan, Test Cases, and Effort outputs use the same serializer as BRD.  
> See endpoints 20, 21, 22 for their specific URLs.

---

### 9. Chat Edit BRD — Start (Async)

```
POST /api/projects/{id}/brd/chat-edit/
```

**Only call when:** BRD `agent_type=brd` has `status === "complete"`.  
**This is a 2-step flow:** POST → get `task_id` → poll the status URL.

**Request body:**

| Field | Type | Required | Constraints |
|---|---|---|---|
| `instruction` | string | ✅ | Min 10 characters |
| `auto_save_version` | boolean | ❌ | Default: `false`. If `true`, saves a version snapshot before editing |

```json
{
  "instruction": "Add GDPR data privacy and compliance considerations to all relevant sections of the BRD",
  "auto_save_version": true
}
```

**Response — 202 Accepted** (not 200 — the work happens in the background):
```json
{
  "task_id": "a3f2c1d8-9b4e-4f2a-8c1d-7e9f2a3b4c5d",
  "status": "processing",
  "message": "Chat edit in progress. Poll the status URL every 3-5 seconds.",
  "poll_url": "/api/projects/8b6e1d3d-.../brd/chat-edit/a3f2c1d8-.../"
}
```

**Error — 400 (instruction too short):**
```json
{ "instruction": ["Ensure this value has at least 10 characters (it has 6)."] }
```

**Error — 400 (BRD not ready):**
```json
{ "error": "BRD is not complete yet. Generate and approve the BRD first." }
```

**What to do:** Save `task_id`. Start polling endpoint 10 every 4 seconds.

---

### 10. Chat Edit BRD — Poll Result ← **Poll this endpoint**

```
GET /api/projects/{id}/brd/chat-edit/{task_id}/
```

**No request body.**

**Response while running:**
```json
{
  "task_id": "a3f2c1d8-...",
  "status": "processing",
  "celery_state": "STARTED",
  "message": "Chat edit is still running. Poll again in 3-5 seconds."
}
```

**Response when complete:**
```json
{
  "task_id": "a3f2c1d8-...",
  "status": "complete",
  "sections_updated_count": 3,
  "changes_summary": [
    {
      "section_key": "functional_requirements",
      "instruction_applied": "Add GDPR considerations",
      "status": "updated"
    },
    {
      "section_key": "non_functional_requirements",
      "instruction_applied": "Add GDPR considerations",
      "status": "updated"
    },
    {
      "section_key": "constraints_and_assumptions",
      "instruction_applied": "Add GDPR considerations",
      "status": "updated"
    }
  ],
  "failed_sections": [],
  "unchanged_sections": ["executive_summary", "glossary", "stakeholders"],
  "router_reasoning": "Instruction relates to compliance which affects NFRs and constraints primarily",
  "message": "Updated 3 section(s): functional_requirements, non_functional_requirements, constraints_and_assumptions",
  "updated_brd": {
    "executive_summary": "...",
    "functional_requirements": [...],
    "...": "..."
  }
}
```

**Response when failed:**
```json
{
  "task_id": "a3f2c1d8-...",
  "status": "failed",
  "error": "AI service error: context length exceeded"
}
```

**What to do per status:**

| `status` value | Action |
|---|---|
| `processing` | Wait 4 seconds, poll again |
| `complete` | Replace the full BRD in state with `updated_brd`. Show `changes_summary`. Stop polling. |
| `complete` with `sections_updated_count === 0` | Tell user "No sections were changed — try a more specific instruction" |
| `failed` | Show `error` value. Show a Retry button. Stop polling. |
| Still `processing` after 5 minutes | Show timeout error. Stop polling. |

> **Do not refetch `/brd/`** after a chat edit. Use `updated_brd` from this response directly.

---

### 11. Section-Wise Edit

```
PATCH /api/projects/{id}/brd/edit-section/
```

**Only call when:** BRD has `status === "complete"`.  
**This is synchronous** — takes 5–20 seconds, no polling needed.

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `section_key` | string | ✅ | Must match an existing key in the BRD `structured_output` |
| `instructions` | string | ✅ | What to change in this section |

**Valid `section_key` values:**

| Key | Section |
|---|---|
| `executive_summary` | Executive Summary |
| `project_scope` | Project Scope |
| `business_objectives` | Business Objectives |
| `stakeholders` | Stakeholders |
| `project_plan` | Project Plan |
| `effort_estimation` | Effort Estimation |
| `functional_requirements` | Functional Requirements |
| `non_functional_requirements` | Non-Functional Requirements |
| `constraints_and_assumptions` | Constraints & Assumptions |
| `success_criteria` | Success Criteria |
| `glossary` | Glossary |

```json
{
  "section_key": "executive_summary",
  "instructions": "Make it shorter — maximum 2 paragraphs. Focus on business value and expected ROI."
}
```

**Response — 200 OK:**
```json
{
  "section_key": "executive_summary",
  "updated_content": "This project delivers a modern customer banking portal...",
  "message": "Section \"executive_summary\" updated successfully."
}
```

**Error — 400 (invalid key):**
```json
{ "error": "Section key \"invalid_key\" not found in current BRD." }
```

**Error — 400 (BRD not ready):**
```json
{ "error": "BRD is not complete yet." }
```

**Error — 500 (AI failed):**
```json
{ "error": "AI section edit failed: [reason]" }
```

**What to do:** Update only `structured_output[section_key]` in state with `updated_content`. Do not refetch the full BRD. Show a loading spinner on that section card only.

---

### 12. Save BRD Version

```
POST /api/projects/{id}/brd/save-version/
```

**Only call when:** BRD has `status === "complete"`.

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `notes` | string | ❌ | Optional label for this snapshot. Defaults to empty string. |

```json
{
  "notes": "Baseline before GDPR update — approved by stakeholders on 5 June"
}
```

or send an empty body `{}` for a version with no notes.

**Response — 201 Created:**
```json
{
  "id": "uuid",
  "version_number": 3,
  "structured_output": { "...": "full BRD snapshot..." },
  "notes": "Baseline before GDPR update",
  "created_at": "2026-06-05T12:00:00Z"
}
```

**Error — 400 (BRD not complete):**
```json
{ "error": "BRD is not complete yet. Cannot save a version." }
```

---

### 13. List BRD Versions

```
GET /api/projects/{id}/brd/versions/
```

**No request body.**

**Response — 200 OK:**
```json
{
  "count": 3,
  "versions": [
    {
      "id": "uuid",
      "version_number": 3,
      "notes": "After GDPR update",
      "created_at": "2026-06-05T14:00:00Z"
    },
    {
      "id": "uuid",
      "version_number": 2,
      "notes": "Baseline before GDPR update",
      "created_at": "2026-06-05T12:00:00Z"
    },
    {
      "id": "uuid",
      "version_number": 1,
      "notes": "",
      "created_at": "2026-06-01T10:30:00Z"
    }
  ]
}
```

> Note: this list response does **not** include `structured_output` to keep it lightweight.  
> Versions are sorted newest first (highest `version_number` first).

---

### 14. Restore BRD Version

```
POST /api/projects/{id}/brd/restore/{version_number}/
```

**`version_number` is an integer in the URL — not a UUID.**  
**No request body.**

**Response — 200 OK:**
```json
{
  "id": "8b6e1d3d-...",
  "restored_version": 2,
  "status": "awaiting_approval",
  "message": "BRD successfully restored to version 2."
}
```

**Error — 404 (version not found):**
```json
{ "error": "Version 99 does not exist for this project." }
```

**What to do:**
1. Show a confirmation dialog **before** calling this — it overwrites the live BRD permanently.
2. After success, call `GET /brd/` to fetch and display the restored BRD.
3. Project status resets to `awaiting_approval` — update your UI state accordingly.

---

### 15. Get Table of Contents

```
GET /api/projects/{id}/toc/
```

**No request body.**

**Response — 200 OK:**
```json
{
  "sections": [
    {
      "id": "uuid",
      "key": "executive_summary",
      "label": "Executive Summary",
      "order": 1,
      "is_enabled": true,
      "is_custom": false
    },
    {
      "id": "uuid",
      "key": "project_scope",
      "label": "Project Scope",
      "order": 2,
      "is_enabled": true,
      "is_custom": false
    }
  ]
}
```

> All 11 standard sections are returned. `order` starts from 1.  
> If no TOC exists yet, the server auto-seeds the default 11 sections.

---

### 16. Save Table of Contents

```
PUT /api/projects/{id}/toc/
```

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `sections` | array | ✅ | Full list of all sections — cannot be empty |

Each item in `sections`:

| Field | Type | Required | Notes |
|---|---|---|---|
| `key` | string | ✅ | Section key (e.g. `executive_summary`) |
| `label` | string | ✅ | Display name |
| `order` | integer | ✅ | Position (1, 2, 3...) |
| `is_enabled` | boolean | ✅ | `true` = visible in BRD output |
| `is_custom` | boolean | ✅ | `false` for standard sections |

```json
{
  "sections": [
    { "key": "executive_summary", "label": "Executive Summary", "order": 1, "is_enabled": true, "is_custom": false },
    { "key": "functional_requirements", "label": "Functional Requirements", "order": 2, "is_enabled": true, "is_custom": false },
    { "key": "effort_estimation", "label": "Effort Estimation", "order": 3, "is_enabled": false, "is_custom": false }
  ]
}
```

> You must include **all sections** in the array — not just changed ones.  
> The server deletes all existing TOC records and recreates from the array you send.

**Response — 200 OK:**
```json
{
  "sections": [ "...updated sections array..." ],
  "message": "Table of Contents updated successfully."
}
```

**Error — 400 (empty array):**
```json
{ "error": "sections list cannot be empty." }
```

---

### 17. List Assets

```
GET /api/projects/{id}/assets/
```

**No request body.**

**Response — 200 OK:**
```json
{
  "count": 2,
  "assets": [
    {
      "id": "uuid",
      "connector_type": "mom",
      "connector_type_display": "Minutes of Meeting",
      "title": "Kickoff Meeting Notes",
      "file": "http://localhost:8000/media/assets/kickoff.pdf",
      "url": null,
      "summary": "This meeting covered the project scope and agreed on...",
      "extraction_status": "complete",
      "extraction_status_display": "Ready",
      "extraction_error": null,
      "is_active": true,
      "created_at": "2026-06-01T09:00:00Z",
      "updated_at": "2026-06-01T09:05:00Z"
    }
  ]
}
```

**`extraction_status` values and what to display:**

| Value | Display |
|---|---|
| `pending` | Grey badge — "Queued" |
| `processing` | Spinner — "Processing..." |
| `complete` | Green badge — "Ready" |
| `failed` | Red badge — "Failed". Show `extraction_error` on hover |

---

### 18. Upload File Asset

```
POST /api/projects/{id}/assets/
Content-Type: multipart/form-data
```

**Form fields:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `connector_type` | string | ✅ | See table below — determines file validation |
| `title` | string | ✅ | Max 255 characters — user-provided label |
| `file` | file | ✅ | Max 10 MB |

**`connector_type` values and accepted file extensions:**

| Value | Display Name | Accepted files |
|---|---|---|
| `mom` | Minutes of Meeting | `.pdf` `.docx` `.txt` |
| `architecture` | Architecture / Design Diagram | `.pdf` `.docx` `.png` `.jpg` |
| `document` | Reference Document | `.pdf` `.docx` `.txt` |
| `chat` | Chat Export | `.txt` `.docx` |
| `email` | Email Thread | `.txt` `.docx` |
| `recording` | Call Recording Transcript | `.txt` `.docx` |

> Validate file type and size on the frontend before sending — the server validates again but it's better UX to catch it early.

**Response — 201 Created:**
```json
{
  "id": "uuid",
  "connector_type": "mom",
  "connector_type_display": "Minutes of Meeting",
  "title": "Kickoff Meeting Notes",
  "file": "http://localhost:8000/media/assets/kickoff.pdf",
  "url": null,
  "summary": null,
  "extraction_status": "pending",
  "extraction_status_display": "Pending Extraction",
  "extraction_error": null,
  "is_active": true,
  "created_at": "2026-06-05T10:00:00Z",
  "updated_at": "2026-06-05T10:00:00Z"
}
```

**What to do:** Add to asset list. Poll `GET /assets/` every 3s until `extraction_status === "complete"`.

---

### 19. Link URL Asset

```
POST /api/projects/{id}/assets/
Content-Type: application/json
```

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `connector_type` | string | ✅ | Must be `"url"` |
| `title` | string | ✅ | Max 255 characters |
| `url` | string | ✅ | Full URL including `https://` — max 2048 chars |

```json
{
  "connector_type": "url",
  "title": "Open Banking API Standards Documentation",
  "url": "https://openbanking.org.uk/standards"
}
```

**Error — 400 (url connector without url field):**
```json
{ "url": "A URL is required for the \"url\" connector type." }
```

**Response — 201 Created:** Same shape as file upload response, with `url` set and `file` as `null`.

---

### 20. Toggle Asset Active/Inactive

```
PATCH /api/projects/{id}/assets/{asset_id}/toggle/
```

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `is_active` | boolean | ✅ | `true` = include in AI context · `false` = exclude |

```json
{ "is_active": false }
```

**Response — 200 OK:**
```json
{
  "id": "uuid",
  "is_active": false,
  "message": "Asset context toggled OFF."
}
```

**What to do:** Update only that asset's `is_active` value in local state.

---

### 21. Delete Asset

```
DELETE /api/projects/{id}/assets/{asset_id}/
```

**No request body.**

**Response — 204 No Content** (empty body)

**What to do:** Always show a confirmation dialog first — deletion is permanent and also deletes the file from disk. Remove from local state on success (204).

---

### 22. AI Chat Assistant

```
POST /api/projects/{id}/chat/
```

> This is a **Q&A assistant only** — it answers questions about the BRD. It does **not** change the BRD.

**Request body:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `message` | string | ✅ | The user's question |
| `history` | array | ❌ | Previous turns. Defaults to `[]` if omitted |

Each item in `history`:

| Field | Type | Values |
|---|---|---|
| `role` | string | `"user"` or `"assistant"` |
| `content` | string | The message text |

```json
{
  "message": "Can you summarise the top 3 functional requirements?",
  "history": [
    { "role": "user", "content": "What compliance standards are mentioned in the BRD?" },
    { "role": "assistant", "content": "The BRD references GDPR and PCI-DSS primarily..." }
  ]
}
```

**Response — 200 OK:**
```json
{
  "role": "assistant",
  "content": "The top 3 functional requirements are: FR-001 Account Balance View, FR-002 Fund Transfer, FR-003 Statement Download."
}
```

**Error — 500 (AI failure):**
```json
{ "error": "AI chat failed: [reason]" }
```

**Rules:**
- The server is **stateless** — history is not stored server-side
- You must send the full accumulated history with every request
- Store history in frontend component state
- Append both `{ role: "user", content: message }` and the response to your history array after each successful call
- This call takes 5–20 seconds — show a typing indicator while waiting

---

### 23. Get Project Plan

```
GET /api/projects/{id}/plan/
```

**No request body.**  
**Only call when:** `status === "complete"` or `outputs.plan === "complete"`.

**Response — 200 OK:**
```json
{
  "id": "uuid",
  "agent_type": "plan",
  "status": "complete",
  "error_message": null,
  "updated_at": "2026-06-01T11:00:00Z",
  "structured_output": { "...": "plan data..." }
}
```

**Error — 404 (not generated yet):**
```json
{ "error": "plan output not available yet. Check /status/ first." }
```

---

### 24. Get Test Cases

```
GET /api/projects/{id}/testcases/
```

**No request body.**  
**Only call when:** `outputs.test_cases === "complete"`.

**Response — 200 OK:** Same shape as plan output, `agent_type: "test_cases"`.

---

### 25. Get Effort Estimation

```
GET /api/projects/{id}/effort/
```

**No request body.**  
**Only call when:** `outputs.effort === "complete"`.

**Response — 200 OK:** Same shape as plan output, `agent_type: "effort"`.

---

### 26. Download DOCX

```
GET /api/projects/{id}/download/{output_type}/
```

**`output_type` values:**

| Value | Document |
|---|---|
| `brd` | Business Requirements Document |
| `plan` | Project Plan |
| `testcases` | Test Cases |
| `effort` | Effort Estimation |

**No request body.**

**Response — 200 OK:**
- Content-Type: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Content-Disposition: `attachment; filename="CustomerPortal_BRD.docx"`
- Body: binary DOCX file stream

**Error — 400 (invalid output_type):**
```json
{ "error": "Invalid output_type: xyz. Choose from: brd, plan, testcases, effort" }
```

**Error — 425 Too Early (output not ready):**
```json
{ "error": "brd is not ready yet. Status: running" }
```

**Error — 500 (generation failed):**
```json
{ "error": "DOCX generation failed: [reason]" }
```

**Rules:**
- **Do not use fetch/axios** for downloads — point the browser directly to the URL: `window.open(url)` or an `<a href="..." download>` tag
- Only show download buttons when the output's status is `complete`
- If you get 425, hide the button — do not show an error toast

---

## HTTP Status Code Reference

| Code | When it happens | What to show |
|---|---|---|
| `200` | Success | Use the response data |
| `201` | Resource created | Use the response data |
| `202` | Async task started | Save `task_id`, start polling |
| `204` | Deleted successfully | Remove from state (no response body) |
| `400` | Validation error or wrong state | Show the `error` or field-level error |
| `404` | Project/asset/output not found | "Not found" message |
| `422` | File could not be parsed | Show the `error` message |
| `425` | Output not ready yet | Hide or disable the related button |
| `500` | AI or server error | "Something went wrong — try again" + Retry button |
| Network error | No connection | "Connection failed — check your network" |

---

## Button & Feature Visibility Rules

| Feature | Show when |
|---|---|
| Approve BRD button | `project.status === "awaiting_approval"` |
| Revise BRD button | `project.status === "awaiting_approval"` |
| Chat Edit (full BRD) | BRD output `status === "complete"` |
| Section Edit buttons | BRD output `status === "complete"` |
| AI Chat panel | BRD output `status === "complete"` (optional: allow earlier) |
| Save Version button | BRD output `status === "complete"` |
| Plan tab | `outputs.plan === "complete"` |
| Test Cases tab | `outputs.test_cases === "complete"` |
| Effort tab | `outputs.effort === "complete"` |
| Download BRD | BRD `status === "complete"` |
| Download Plan | `outputs.plan === "complete"` |
| Download Test Cases | `outputs.test_cases === "complete"` |
| Download Effort | `outputs.effort === "complete"` |

---

## Common Mistakes to Avoid

| Mistake | Correct approach |
|---|---|
| Polling faster than 3 seconds | Minimum 3s interval — 4s is safer |
| Not stopping the poll on component unmount | Always clear the interval in cleanup |
| Calling `/approve-brd/` when status is not `awaiting_approval` | Guard with a status check before calling |
| Refetching full BRD after chat edit | Use `updated_brd` from the poll response directly |
| Refetching full BRD after section edit | Use `updated_content` from the response for that one key |
| Using fetch/axios for DOCX downloads | Use `window.open()` or an `<a>` tag |
| Showing download buttons before output is `complete` | Check `outputs.<type>` before rendering the button |
| Sending chat history on the server | History is frontend-only — store in state, send each time |
| Not confirming before BRD version restore | Always show a confirmation dialog — it overwrites live BRD |
| Using 30s timeout on AI calls | Use 120s minimum for BRD edit, section edit, chat endpoints |

---

## Complete Endpoint Reference

```
GET    /api/projects/                                    List all projects
POST   /api/projects/                                    Create project → BRD fires immediately

GET    /api/projects/{id}/                               Full project detail
GET    /api/projects/{id}/status/                        Poll project status ← poll this

GET    /api/projects/{id}/brd/                           Get BRD JSON
POST   /api/projects/{id}/approve-brd/                   Approve BRD
POST   /api/projects/{id}/revise-brd/                    Request BRD revision

GET    /api/projects/{id}/brd/versions/                  List BRD version history
POST   /api/projects/{id}/brd/save-version/              Save current BRD as snapshot
POST   /api/projects/{id}/brd/restore/{version_number}/  Restore BRD to a version (integer in URL)

PATCH  /api/projects/{id}/brd/edit-section/              AI edit one section (sync)
POST   /api/projects/{id}/brd/chat-edit/                 Start full BRD chat edit → 202 + task_id
GET    /api/projects/{id}/brd/chat-edit/{task_id}/       Poll chat edit result ← poll this

GET    /api/projects/{id}/toc/                           Get TOC config
PUT    /api/projects/{id}/toc/                           Save TOC config (full replace)

GET    /api/projects/{id}/assets/                        List assets
POST   /api/projects/{id}/assets/                        Upload file or link URL
PATCH  /api/projects/{id}/assets/{asset_id}/toggle/      Toggle active/inactive
DELETE /api/projects/{id}/assets/{asset_id}/             Delete asset

POST   /api/projects/{id}/chat/                          AI Q&A chat (does not edit BRD)

GET    /api/projects/{id}/plan/                          Get Project Plan JSON
GET    /api/projects/{id}/testcases/                     Get Test Cases JSON
GET    /api/projects/{id}/effort/                        Get Effort Estimation JSON

GET    /api/projects/{id}/download/brd/                  Download BRD as DOCX
GET    /api/projects/{id}/download/plan/                 Download Plan as DOCX
GET    /api/projects/{id}/download/testcases/            Download Test Cases as DOCX
GET    /api/projects/{id}/download/effort/               Download Effort as DOCX
```
