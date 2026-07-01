# Frontend UI Flow & API Guidelines

This guide provides step-by-step instructions for the frontend team to build the UI screens, specifically highlighting which APIs to call, when to call them, what data to send, and what response to expect. It groups all required APIs logically by screen.

---

## 1. Dashboard & Project Creation (1st Screen)

### A. Project List Dashboard
**Overview:** The main landing page showing existing projects.
*   **API to Call:** `GET /api/projects/`
*   **Why:** To fetch the latest list of projects to populate the data table (Name, LOB, Department, Application, Created On).
*   **Expected Response:** A JSON array of project objects.
    ```json
    [
      {
        "id": "uuid",
        "name": "Project Name",
        "line_of_business": "Retail",
        "application_type": "salesforce",
        "department": "Digital",
        "status": "complete",
        "created_at": "..."
      }
    ]
    ```

### B. Create Project Modal
**Overview:** Triggered by a "+ Project" button to create a new project.
*   **API to Call:** `POST /api/projects/`
*   **Why:** To save the new project details. Note: This *only creates* the project; it does not start the BRD generation.
*   **Request Body (application/json):**
    ```json
    {
      "name": "Project Name",
      "line_of_business": "Retail",
      "application_type": "salesforce",  // Choices: salesforce, servicenow, sap, custom
      "department": "Digital",
      "raw_input": "High level project requirement..."
    }
    ```
*   **Expected Response (201 Created):**
    ```json
    { "id": "uuid", "status": "new", "message": "Project created successfully." }
    ```
*   **Action:** Upon success, navigate the user directly to the new Project Workspace using the returned `id`.

---

## 2. Project Workspace & Sidebar (2nd Screen)

**Overview:** The main editor workspace while setting up a project. The left sidebar is used for managing knowledge sources and triggering the BRD generation.

### A. Load Project Details
*   **API to Call:** `GET /api/projects/{id}/`
*   **Why:** To load the core details, current status, and output statuses for the workspace header.

### B. Insight Attachments
**Overview:** Manages documents specifically uploaded for the *current* project.

1.  **List Existing Files:**
    *   **API:** `GET /api/projects/{id}/assets/`
    *   **Response:** Array of assets `{"count": 1, "assets": [{"id": "uuid", "title": "spec.pdf", "is_active": true, "extraction_status": "complete"}]}`

2.  **Upload New File:**
    *   **API:** `POST /api/projects/{id}/assets/`
    *   **Request Body (multipart/form-data):** `connector_type="document"`, `file=[binary]`

3.  **Toggle File ON/OFF:**
    *   **API:** `PATCH /api/projects/{id}/assets/{asset_id}/toggle/`
    *   **Request Body:** `{"is_active": false}`

4.  **Delete File:**
    *   **API:** `DELETE /api/projects/{id}/assets/{asset_id}/`

### C. Table of Contents Configuration
**Overview:** A modal or slide-out where users configure the structure of the BRD.

1.  **Load TOC Settings:**
    *   **API:** `GET /api/projects/{id}/toc/`
    *   **Response:** `{"sections": [{"key": "executive_summary", "label": "Executive Summary", "order": 1, "is_enabled": true}]}`

2.  **Save TOC Settings:**
    *   **API:** `PUT /api/projects/{id}/toc/`
    *   **Request Body:** Send the *full, reordered array* back to the server.

### D. "Generate BRD" Button
**Overview:** Button located at the bottom of the sidebar to manually start the AI BRD generation.

1.  **Trigger Generation:**
    *   **API:** `POST /api/projects/{id}/generate-brd/`
    *   **Why:** Because project creation no longer starts the AI automatically.
    *   **Response (200 OK):** `{ "id": "uuid", "status": "generating_brd" }`

2.  **Poll for Status:**
    *   **API:** `GET /api/projects/{id}/status/`
    *   **Action:** Poll every 2-3 seconds until `status === "awaiting_approval"`. Once ready, navigate to or show the BRD Viewer screen.

---

## 3. BRD Viewer & AI Editor (3rd Screen)

**Overview:** The screen where the user reads the generated BRD, uses AI to edit it, manages versions, and finally approves or sends it back for revision.

### A. Load the Generated BRD
*   **API to Call:** `GET /api/projects/{id}/brd/`
*   **Why:** To fetch the structured JSON containing the entire generated BRD.
*   **Expected Response:** 
    ```json
    {
      "id": "uuid",
      "status": "complete",
      "structured_output": {
        "executive_summary": "...",
        "project_scope": { "in_scope": [], "out_of_scope": [] },
        "functional_requirements": [ {"id": "FR-001", "title": "..."} ]
      }
    }
    ```

### B. AI Chat Editing (Main BRD Chatbox)
**Overview:** A chat interface where the user tells the AI to rewrite or update the document globally.
*   **API to Call:** `POST /api/projects/{id}/brd/chat-edit/`
*   **Why:** The AI determines which sections to update and rewrites them based on the instruction.
*   **Request Body:**
    ```json
    {
      "instruction": "Add GDPR compliance requirements to all relevant sections",
      "auto_save_version": true
    }
    ```
*   **Expected Response:** Returns `updated_brd` object. Replace your local state with this new BRD immediately without needing to re-fetch.

### C. Specific Section Editing (Inline Edit)
**Overview:** Clicking a specific section in the UI (e.g. Executive Summary) and giving a targeted instruction.
*   **API to Call:** `PATCH /api/projects/{id}/brd/edit-section/`
*   **Request Body:**
    ```json
    {
      "section_key": "executive_summary",
      "instructions": "Make it more concise."
    }
    ```
*   **Expected Response:** Returns `updated_content`. Patch your local UI state for just that section.

### D. Q&A Assistant Chat (Non-Editing)
**Overview:** A side panel asking questions about the document without actually modifying it.
*   **API to Call:** `POST /api/projects/{id}/chat/`
*   **Request Body:** `{"message": "Why is FR-003 a 'Should Have'?", "history": [...]}`
*   **Response:** AI assistant text response. 

### E. Version History
**Overview:** Sidebar or modal to see past snapshots of the BRD.
1.  **List Versions:** `GET /api/projects/{id}/brd/versions/`
2.  **Save Snapshot:** `POST /api/projects/{id}/brd/save-version/` (Body: `{"notes": "Version 1"}`)
3.  **Restore Version:** `POST /api/projects/{id}/brd/restore/{version_number}/`

### F. Approval & Revision Workflow
**Overview:** The action buttons at the top/bottom of the BRD viewer.

1.  **Approve BRD:**
    *   **API:** `POST /api/projects/{id}/approve-brd/`
    *   **Why:** Marks the BRD as approved so that execution documents (Plan, Test Cases) can be manually generated. Note: This no longer generates them automatically.
    *   **Action:** Change UI status to `approved`. Enable the buttons in Screen 4 to generate the deliverables.

2.  **Request Revision:**
    *   **API:** `POST /api/projects/{id}/revise-brd/`
    *   **Request Body:** `{"revision_notes": "Missed mobile requirements."}`
    *   **Action:** Changes status back to `generating_brd`. Begin polling `/status/` again.

---

## 4. Final Deliverables (4th Screen)

**Overview:** Shown after the BRD is approved (`status === "approved"`). Users must manually trigger the generation of the supplementary documents. Note: Effort Estimation requires the Project Plan to be generated first.

### A. Generate Documents
Provide buttons to generate each deliverable. When clicked, show a loading state.

1.  **Generate Project Plan:**
    *   **API:** `POST /api/projects/{id}/generate-plan/`
    *   **Response:** `{ "id": "uuid", "message": "Project Plan generation started..." }`
2.  **Generate Test Cases:**
    *   **API:** `POST /api/projects/{id}/generate-testcases/`
    *   **Response:** `{ "id": "uuid", "message": "Test Cases generation started..." }`
3.  **Generate Effort Estimation:**
    *   **API:** `POST /api/projects/{id}/generate-effort/`
    *   **Constraint:** *Do not allow this to be clicked until the Project Plan has been generated.*
    *   **Response:** `{ "id": "uuid", "message": "Effort Estimation generation started..." }`

### B. Load Completed Documents
Once generated, fetch the documents to display them in tabs alongside the finalized BRD.

*   **API to Call (Project Plan):** `GET /api/projects/{id}/plan/`
*   **API to Call (Test Cases):** `GET /api/projects/{id}/testcases/`
*   **API to Call (Effort Estimation):** `GET /api/projects/{id}/effort/`
