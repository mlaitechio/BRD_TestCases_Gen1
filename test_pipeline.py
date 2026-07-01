"""
BRD Automation Platform — Full Pipeline Test Script
====================================================
Tests every API endpoint in sequence, simulating a complete user journey:

  1.  Create project
  2.  Poll until clarification questions are ready
  3.  Submit answers
  4.  Poll until BRD is ready
  5.  Test chat Q&A (non-modifying)
  6.  Test BRD chat-edit (full-document AI update)
  7.  Test section-wise edit (single section)
  8.  Save BRD version snapshot
  9.  Approve BRD
  10. Poll until all agents complete
  11. Fetch Plan, TestCases, Effort outputs
  12. Upload URL asset (source connector)
  13. Toggle asset OFF/ON
  14. Test BRD version restore
  15. List all projects
  16. Download DOCX check (header only)

Run:
    pip install requests
    python test_pipeline.py

    # To test against a different server:
    BASE_URL=http://your-server.com python test_pipeline.py
"""

import os
import sys
import time
import json
import requests

# ─── Config ───────────────────────────────────────────────────────────────────

BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
API = f'http://127.0.0.1:8000/api/projects'
POLL_INTERVAL = 3       # seconds between status polls
MAX_POLL_WAIT = 300     # 5 minutes max per stage


# ─── ANSI Colours ─────────────────────────────────────────────────────────────

GREEN  = '\033[92m'
RED    = '\033[91m'
YELLOW = '\033[93m'
BLUE   = '\033[94m'
BOLD   = '\033[1m'
RESET  = '\033[0m'

def ok(msg):    print(f'  {GREEN}✓{RESET} {msg}')
def fail(msg):  print(f'  {RED}✗ FAILED: {msg}{RESET}'); sys.exit(1)
def info(msg):  print(f'  {BLUE}→{RESET} {msg}')
def warn(msg):  print(f'  {YELLOW}⚠{RESET} {msg}')
def header(msg): print(f'\n{BOLD}{BLUE}{'─'*60}{RESET}\n{BOLD} {msg}{RESET}\n{BOLD}{BLUE}{'─'*60}{RESET}')


# ─── HTTP Helpers ─────────────────────────────────────────────────────────────

def get(path, **kw):
    url = f'{API}{path}'
    r = requests.get(url, timeout=30, **kw)
    return r

def post(path, json_body=None, data=None, files=None, **kw):
    url = f'{API}{path}'
    r = requests.post(url, json=json_body, data=data, files=files, timeout=60, **kw)
    return r

def patch(path, json_body=None, **kw):
    url = f'{API}{path}'
    r = requests.patch(url, json=json_body, timeout=60, **kw)
    return r

def put(path, json_body=None, **kw):
    url = f'{API}{path}'
    r = requests.put(url, json=json_body, timeout=30, **kw)
    return r

def delete(path, **kw):
    url = f'{API}{path}'
    r = requests.delete(url, timeout=30, **kw)
    return r

def assert_status(r, expected, label):
    if r.status_code != expected:
        print(f'\n  Response body: {r.text[:500]}')
        fail(f'{label} — expected HTTP {expected}, got {r.status_code}')

def poll_status(project_id, target_status, stage_label):
    """Poll /status/ until project reaches target_status or timeout."""
    info(f'Polling status until: {target_status} (max {MAX_POLL_WAIT}s)...')
    elapsed = 0
    while elapsed < MAX_POLL_WAIT:
        r = get(f'/{project_id}/status/')
        if r.status_code != 200:
            fail(f'Status poll failed: HTTP {r.status_code}')
        data = r.json()
        current = data.get('status', '')
        outputs = data.get('outputs', {})
        info(f'  Status: {current} | Outputs: {outputs} ({elapsed}s elapsed)')
        if current == target_status:
            ok(f'{stage_label} — status reached: {target_status}')
            return data
        if current == 'failed':
            fail(f'{stage_label} — project status is "failed": {data.get("error_message")}')
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    fail(f'{stage_label} — timed out after {MAX_POLL_WAIT}s waiting for "{target_status}"')


# ─── Test Steps ───────────────────────────────────────────────────────────────

def step_01_create_project():
    header('STEP 1 — Create Project')
    payload = {
        'name': 'Customer Portal Redesign [API Test]',
        'line_of_business': 'Retail Banking',
        'application_type': 'web',
        'department': 'Digital Products',
        'raw_input': (
            'We need to build a customer-facing web portal for our retail banking clients. '
            'The portal should allow customers to view account balances, transfer funds between '
            'accounts, download monthly statements as PDF, and manage their profile and contact '
            'details. The system must integrate with our existing Temenos T24 core banking APIs. '
            'We have approximately 500,000 active customers and expect peak loads of 10,000 '
            'concurrent users. GDPR compliance is mandatory. The project budget is £800,000 '
            'and must deliver by Q4 2026.'
        ),
    }
    r = post('/', json_body=payload)
    assert_status(r, 201, 'Create project')
    data = r.json()

    pid = data.get('id')
    if not pid:
        fail('No project ID returned')

    ok(f'Project created — ID: {pid}')
    info(f'Initial status: {data.get("status")}')
    return pid


def step_02_poll_clarification(pid):
    header('STEP 2 — Poll Until Clarification Questions Ready')
    poll_status(pid, 'awaiting_answers', 'Clarification agent')


def step_03_get_questions(pid):
    header('STEP 3 — Get Clarification Questions')
    r = get(f'/{pid}/clarification-questions/')
    assert_status(r, 200, 'Get clarification questions')
    data = r.json()
    questions = data.get('questions', [])
    if not questions:
        fail('No questions returned')
    ok(f'Received {len(questions)} clarification question(s):')
    for q in questions:
        info(f'  [{q.get("id")}] {q.get("question")}')
    return questions


def step_04_submit_answers(pid, questions):
    header('STEP 4 — Submit Answers → Triggers BRD Generation')
    answers = {}
    sample_answers = [
        'Retail banking customers only — consumer-facing web application with mobile-responsive design',
        'Yes — GDPR compliance is mandatory, PCI-DSS for payment card data, Open Banking standards for APIs',
        'Must integrate with existing Temenos T24 core banking system using REST APIs',
        'Self-service portal — no agent assistance. Customers manage everything independently',
        'Phase 1: account viewing and statements. Phase 2: transfers. Out of scope: loan applications',
    ]
    for i, q in enumerate(questions):
        answers[q['id']] = sample_answers[i] if i < len(sample_answers) else 'Standard implementation as per best practices'

    info(f'Submitting {len(answers)} answers...')
    r = post(f'/{pid}/answer-questions/', json_body={'answers': answers})
    assert_status(r, 200, 'Submit answers')
    ok('Answers submitted — BRD generation triggered')


def step_05_poll_brd(pid):
    header('STEP 5 — Poll Until BRD Ready')
    poll_status(pid, 'awaiting_approval', 'BRD agent')


def step_06_get_brd(pid):
    header('STEP 6 — Fetch BRD JSON')
    r = get(f'/{pid}/brd/')
    assert_status(r, 200, 'Get BRD')
    data = r.json()

    if data.get('status') != 'complete':
        fail(f'BRD status is {data.get("status")} — expected "complete"')

    brd = data.get('structured_output', {})
    if not brd:
        fail('BRD structured_output is empty')

    ok(f'BRD retrieved — {len(brd)} sections:')
    for key in brd.keys():
        info(f'  • {key}')

    # Validate all 11 required sections are present
    required = [
        'executive_summary', 'project_scope', 'business_objectives', 'stakeholders',
        'project_plan', 'effort_estimation', 'functional_requirements',
        'non_functional_requirements', 'constraints_and_assumptions',
        'success_criteria', 'glossary',
    ]
    missing = [s for s in required if s not in brd]
    if missing:
        warn(f'Missing sections: {missing}')
    else:
        ok('All 11 required BRD sections present')

    fr_count = len(brd.get('functional_requirements', []))
    ok(f'Functional requirements: {fr_count}')
    return brd


def step_07_ai_chat(pid):
    header('STEP 7 — AI Chat (Q&A — does not modify BRD)')
    r = post(f'/{pid}/chat/', json_body={
        'message': 'Can you summarise the top 3 functional requirements from this BRD?',
        'history': [],
    })
    assert_status(r, 200, 'AI chat')
    data = r.json()
    if data.get('role') != 'assistant':
        fail(f'Expected role "assistant", got: {data.get("role")}')
    content = data.get('content', '')
    if not content:
        fail('Empty AI chat response')
    ok(f'AI chat response received ({len(content)} chars):')
    info(f'  "{content[:200]}..."')
    return content


def step_08_chat_edit_full_brd(pid):
    header('STEP 8 — Chat Edit (Auto-Update Entire BRD — Async)')
    instruction = 'Add GDPR data privacy and compliance considerations to all relevant sections of the BRD'
    info(f'Instruction: "{instruction}"')

    # ── POST → fires Celery task, returns 202 immediately ─────────────────────
    r = post(f'/{pid}/brd/chat-edit/', json_body={
        'instruction': instruction,
        'auto_save_version': True,
    })
    assert_status(r, 202, 'BRD chat-edit (fire task)')
    data = r.json()

    task_id = data.get('task_id')
    poll_url = data.get('poll_url', '')
    if not task_id:
        fail('No task_id returned from chat-edit')

    ok(f'Chat-edit task queued — task_id: {task_id}')
    info(f'Poll URL: {poll_url}')

    # ── Poll until complete (same pattern as BRD/Plan generation) ─────────────
    info(f'Polling for result (max {MAX_POLL_WAIT}s, every {POLL_INTERVAL}s)...')
    elapsed = 0
    while elapsed < MAX_POLL_WAIT:
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        r = get(f'/{pid}/brd/chat-edit/{task_id}/')
        if r.status_code not in (200, 500):
            fail(f'Unexpected status poll HTTP {r.status_code}: {r.text[:200]}')

        result = r.json()
        task_status = result.get('status', 'processing')
        celery_state = result.get('celery_state', '')
        info(f'  [{elapsed}s] status={task_status} celery={celery_state}')

        if task_status == 'failed':
            fail(f'Chat-edit task failed: {result.get("error")}')

        if task_status == 'complete':
            sections_updated = result.get('sections_updated_count', 0)
            changes = result.get('changes_summary', [])
            unchanged = result.get('unchanged_sections', [])
            reasoning = result.get('router_reasoning', '')

            ok(f'Chat-edit complete — {sections_updated} section(s) updated')
            info(f'Router reasoning: {reasoning}')
            info('Updated sections:')
            for c in changes:
                info(f'  • {c.get("section_key")} — {c.get("status")}')
            info(f'Unchanged sections: {unchanged}')

            if 'updated_brd' not in result:
                fail('updated_brd not in completed result')
            ok('updated_brd present — frontend can replace BRD state directly')
            return

    fail(f'Chat-edit timed out after {MAX_POLL_WAIT}s')



def step_09_section_edit(pid):
    header('STEP 9 — Section-Wise Edit (Single Section Only)')
    r = patch(f'/{pid}/brd/edit-section/', json_body={
        'section_key': 'executive_summary',
        'instructions': 'Make it more concise — 2 paragraphs max. Focus on business value and ROI.',
    })
    assert_status(r, 200, 'Section edit')
    data = r.json()

    if data.get('section_key') != 'executive_summary':
        fail(f'Wrong section_key in response: {data.get("section_key")}')

    new_content = data.get('updated_content', '')
    if not new_content:
        fail('updated_content is empty')

    ok(f'Section "executive_summary" updated ({len(new_content)} chars)')
    info(f'  Preview: "{str(new_content)[:150]}..."')


def step_10_save_version(pid):
    header('STEP 10 — Save BRD Version Snapshot')
    r = post(f'/{pid}/brd/save-version/', json_body={
        'notes': 'Post-GDPR update — after chat-edit and section revision',
    })
    assert_status(r, 201, 'Save BRD version')
    data = r.json()
    version_number = data.get('version_number')
    ok(f'BRD version {version_number} saved — notes: "{data.get("notes")}"')
    return version_number


def step_11_list_versions(pid):
    header('STEP 11 — List BRD Versions')
    r = get(f'/{pid}/brd/versions/')
    assert_status(r, 200, 'List versions')
    data = r.json()
    count = data.get('count', 0)
    versions = data.get('versions', [])
    ok(f'{count} version(s) saved:')
    for v in versions:
        info(f'  v{v.get("version_number")} — "{v.get("notes")}" ({v.get("created_at")})')


def step_12_approve_brd(pid):
    header('STEP 12 — Approve BRD → Triggers Plan + TestCases + Effort')
    r = post(f'/{pid}/approve-brd/')
    assert_status(r, 200, 'Approve BRD')
    data = r.json()
    ok(f'BRD approved — status: {data.get("status")}')
    info('Plan, Test Cases, and Effort Estimation agents now running...')


def step_13_poll_complete(pid):
    header('STEP 13 — Poll Until All Agents Complete')
    poll_status(pid, 'complete', 'All remaining agents')


def step_14_fetch_outputs(pid):
    header('STEP 14 — Fetch Plan, TestCases, Effort Outputs')

    for output_type, label in [('plan', 'Project Plan'), ('testcases', 'Test Cases'), ('effort', 'Effort Estimation')]:
        r = get(f'/{pid}/{output_type}/')
        assert_status(r, 200, f'Get {label}')
        data = r.json()
        if data.get('status') != 'complete':
            fail(f'{label} status is {data.get("status")}')
        output = data.get('structured_output', {})
        if not output:
            fail(f'{label} structured_output is empty')
        ok(f'{label} — {len(output)} top-level keys: {list(output.keys())[:5]}')


def step_15_upload_url_asset(pid):
    header('STEP 15 — Upload URL Asset (Source Connector)')
    r = post(f'/{pid}/assets/', json_body={
        'connector_type': 'url',
        'title': 'Open Banking API Standards',
        'url': 'https://httpbin.org/json',   # Safe test URL — always returns 200
    })
    assert_status(r, 201, 'Upload URL asset')
    data = r.json()
    asset_id = data.get('id')
    ok(f'Asset created — ID: {asset_id}, extraction_status: {data.get("extraction_status")}')
    info('Note: extraction runs asynchronously via Celery — poll asset list to check "complete"')
    return asset_id


def step_16_list_assets(pid):
    header('STEP 16 — List Project Assets')
    r = get(f'/{pid}/assets/')
    assert_status(r, 200, 'List assets')
    data = r.json()
    count = data.get('count', 0)
    ok(f'{count} asset(s) found:')
    for asset in data.get('assets', []):
        info(f'  • [{asset.get("connector_type")}] {asset.get("title")} — {asset.get("extraction_status")} (active={asset.get("is_active")})')


def step_17_toggle_asset(pid, asset_id):
    header('STEP 17 — Toggle Asset OFF then ON')

    # Toggle OFF
    r = patch(f'/{pid}/assets/{asset_id}/toggle/', json_body={'is_active': False})
    assert_status(r, 200, 'Toggle asset OFF')
    data = r.json()
    if data.get('is_active') is not False:
        fail('Asset was not toggled OFF')
    ok(f'Asset toggled OFF — is_active: {data.get("is_active")}')

    # Toggle ON
    r = patch(f'/{pid}/assets/{asset_id}/toggle/', json_body={'is_active': True})
    assert_status(r, 200, 'Toggle asset ON')
    data = r.json()
    if data.get('is_active') is not True:
        fail('Asset was not toggled ON')
    ok(f'Asset toggled ON — is_active: {data.get("is_active")}')


def step_18_toc(pid):
    header('STEP 18 — GET and PUT Table of Contents')

    # GET
    r = get(f'/{pid}/toc/')
    assert_status(r, 200, 'Get TOC')
    sections = r.json().get('sections', [])
    ok(f'TOC retrieved — {len(sections)} sections')

    # PUT (reorder: move glossary to top, hide effort_estimation)
    reordered = []
    for i, s in enumerate(sections):
        reordered.append({
            'key': s['key'],
            'label': s['label'],
            'order': i + 1,
            'is_enabled': s['key'] != 'effort_estimation',  # hide effort
            'is_custom': s.get('is_custom', False),
        })

    r = put(f'/{pid}/toc/', json_body={'sections': reordered})
    assert_status(r, 200, 'Save TOC')
    ok(f'TOC saved — effort_estimation hidden, {len(reordered)} sections configured')


def step_19_restore_version(pid, version_number):
    header(f'STEP 19 — Restore BRD to Version {version_number}')
    r = post(f'/{pid}/brd/restore/{version_number}/')
    assert_status(r, 200, 'Restore BRD version')
    data = r.json()
    ok(f'BRD restored to v{data.get("restored_version")} — status: {data.get("status")}')


def step_20_download_check(pid):
    header('STEP 20 — Check DOCX Download Headers')
    for output_type in ['brd', 'plan', 'testcases', 'effort']:
        # Use HEAD/GET to check response — don't stream full binary
        r = get(f'/{pid}/download/{output_type}/', stream=True)
        if r.status_code == 200:
            content_type = r.headers.get('Content-Type', '')
            content_disp = r.headers.get('Content-Disposition', '')
            if 'openxmlformats' in content_type or 'octet-stream' in content_type:
                ok(f'Download [{output_type}] — Content-Type: {content_type[:60]}')
            else:
                warn(f'Download [{output_type}] — unexpected Content-Type: {content_type}')
            info(f'  Content-Disposition: {content_disp}')
        elif r.status_code == 425:
            warn(f'Download [{output_type}] — not ready yet (HTTP 425)')
        else:
            warn(f'Download [{output_type}] — HTTP {r.status_code}: {r.text[:100]}')
        r.close()


def step_21_list_projects():
    header('STEP 21 — List All Projects')
    r = get('/')
    assert_status(r, 200, 'List projects')
    projects = r.json()
    ok(f'{len(projects)} project(s) in the system:')
    for p in projects[:5]:
        info(f'  • {p.get("name")} — {p.get("status")} (id: {str(p.get("id"))[:8]}...)')


# ─── Error Case Tests ─────────────────────────────────────────────────────────

def step_22_error_cases(pid):
    header('STEP 22 — Error Case Validation')

    # Bad action in wrong state
    r = post(f'/{pid}/approve-brd/')
    if r.status_code == 400:
        ok('Approve BRD in wrong state → correctly returns 400')
    else:
        warn(f'Expected 400, got {r.status_code}: {r.text[:100]}')

    # chat-edit with short instruction — should return 400 (validation)
    r = post(f'/{pid}/brd/chat-edit/', json_body={'instruction': 'short'})
    if r.status_code == 400:
        ok('chat-edit with short instruction → correctly returns 400 validation error')
    else:
        warn(f'Expected 400, got {r.status_code}: {r.text[:100]}')


    # Invalid section key
    r = patch(f'/{pid}/brd/edit-section/', json_body={
        'section_key': 'nonexistent_section',
        'instructions': 'test',
    })
    if r.status_code == 400:
        ok('edit-section with invalid key → correctly returns 400')
    else:
        warn(f'Expected 400, got {r.status_code}: {r.text[:100]}')

    # 404 for unknown project
    r = get('/00000000-0000-0000-0000-000000000000/brd/')
    if r.status_code == 404:
        ok('Unknown project ID → correctly returns 404')
    else:
        warn(f'Expected 404, got {r.status_code}')


# ─── Main Runner ──────────────────────────────────────────────────────────────

def main():
    print(f'\n{BOLD}{"="*60}{RESET}')
    print(f'{BOLD}  BRD Automation Platform — Pipeline Test{RESET}')
    print(f'{BOLD}  Target: {BASE_URL}{RESET}')
    print(f'{BOLD}{"="*60}{RESET}')

    # Verify server is running
    try:
        r = get('/')
        print(f'\n  Server status: {GREEN}ONLINE{RESET} (HTTP {r.status_code})')
    except requests.exceptions.ConnectionError:
        print(f'\n  {RED}ERROR: Cannot connect to {BASE_URL}{RESET}')
        print(f'  Make sure Django is running:')
        print(f'    venv\\Scripts\\python.exe manage.py runserver')
        print(f'    venv\\Scripts\\celery.exe -A brd_system worker --loglevel=info')
        sys.exit(1)

    start_time = time.time()
    project_id = None
    saved_version_number = None
    asset_id = None

    try:
        # ── Pipeline ──────────────────────────────────────────────────────────
        project_id = step_01_create_project()
        step_02_poll_clarification(project_id)
        questions = step_03_get_questions(project_id)
        step_04_submit_answers(project_id, questions)
        step_05_poll_brd(project_id)
        step_06_get_brd(project_id)
        step_07_ai_chat(project_id)
        step_08_chat_edit_full_brd(project_id)
        step_09_section_edit(project_id)
        saved_version_number = step_10_save_version(project_id)
        step_11_list_versions(project_id)
        step_12_approve_brd(project_id)
        step_13_poll_complete(project_id)
        step_14_fetch_outputs(project_id)
        asset_id = step_15_upload_url_asset(project_id)
        step_16_list_assets(project_id)
        step_17_toggle_asset(project_id, asset_id)
        step_18_toc(project_id)
        step_22_error_cases(project_id)   # run BEFORE restore so project is 'complete'
        if saved_version_number:
            step_19_restore_version(project_id, saved_version_number)
        step_20_download_check(project_id)
        step_21_list_projects()


        # ── Summary ───────────────────────────────────────────────────────────
        elapsed = time.time() - start_time
        print(f'\n{BOLD}{"="*60}{RESET}')
        print(f'{BOLD}{GREEN}  ALL TESTS PASSED{RESET}')
        print(f'{BOLD}  Project ID: {project_id}{RESET}')
        print(f'{BOLD}  Total time: {elapsed:.1f}s{RESET}')
        print(f'{BOLD}{"="*60}{RESET}\n')

    except SystemExit:
        elapsed = time.time() - start_time
        print(f'\n{BOLD}{"="*60}{RESET}')
        print(f'{BOLD}{RED}  TEST FAILED after {elapsed:.1f}s{RESET}')
        if project_id:
            print(f'{BOLD}  Failed project ID: {project_id}{RESET}')
            print(f'{BOLD}  Check: {BASE_URL}/admin/projects/project/{project_id}/change/{RESET}')
        print(f'{BOLD}{"="*60}{RESET}\n')
        sys.exit(1)


if __name__ == '__main__':
    main()
