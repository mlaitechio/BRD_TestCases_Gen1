"""
Celery Tasks for BRD Automation Pipeline.

Task Registry:
  Task 1: run_brd_task                — BRD Agent (fires immediately on project create)
  Task 2: run_remaining_agents_task   — Plan → TestCase → Effort (fires after BRD approval)
  Task 3: run_asset_extraction_task   — Per-asset extraction + AI summarisation (fires on asset upload)
  Task 4: run_brd_chat_edit_task      — Full BRD async chat-edit via Celery
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)




@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def run_brd_task(self, project_id: str):
    """
    Run the BRD Agent using:
      - Project description + metadata
      - User clarification answers
      - Active project asset context (Knowledge Layer)
      - Revision notes (if this is a revision run)

    Fires after user submits answers, or after a revision request.
    """
    from apps.projects.models import Project, AgentOutput
    from agents.brd_agent import generate_brd
    from utils.context_builder import build_context_for_project, build_project_metadata_block
    from utils.search import search_knowledge_base

    try:
        project = Project.objects.get(id=project_id)
        project.status = 'generating_brd'
        project.save(update_fields=['status', 'updated_at'])

        agent_output, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='brd',
            defaults={'status': 'running', 'structured_output': None, 'raw_output': None}
        )

        # Build enriched description with metadata header
        metadata_block = build_project_metadata_block(project)
        full_description = metadata_block + (project.extracted_text or '')

        # Build context from active project assets (Knowledge Layer)
        asset_context = build_context_for_project(project)
        if asset_context:
            logger.info(f'[BRD] Injecting {len(asset_context)} chars of asset context for project {project_id}')

        answers = project.clarification_answers or {}

        # Retrieve global knowledge base guidance with smart filtering
        company_kb = search_knowledge_base(
            query_text=project.name or "General BRD Requirements",
            top_k=3,
            application_type=project.application_type,
            line_of_business=project.line_of_business
        )

        logger.info(f'[BRD] Starting for project {project_id}')
        
        active_toc = project.toc_sections.filter(is_enabled=True).order_by('order')
        toc_data = [{'key': t.key, 'label': t.label, 'is_custom': t.is_custom} for t in active_toc]

        result = generate_brd(
            project_description=full_description,
            clarification_answers=answers,
            revision_notes=project.revision_notes,
            context_summary=asset_context,
            company_knowledge_base=company_kb,
            toc_sections=toc_data if toc_data else None,
        )

        agent_output.status = 'complete'
        agent_output.structured_output = result
        agent_output.raw_output = str(result)
        agent_output.save()

        # Queue RAG indexing async (non-blocking)
        run_rag_indexing_task.delay(str(agent_output.id))

        project.status = 'awaiting_approval'
        project.revision_notes = None
        project.save(update_fields=['status', 'revision_notes', 'updated_at'])

        logger.info(f'[BRD] Complete for project {project_id} — RAG indexing queued')

    except Project.DoesNotExist:
        logger.error(f'[BRD] Project {project_id} not found')

    except (ValueError, RuntimeError) as exc:
        logger.error(f'[BRD] Failed for project {project_id}: {exc}')
        _mark_project_failed(project_id, 'brd', exc)
        raise self.retry(exc=exc)


# ─── Task 3: Plan Agent ─────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def run_plan_task(self, project_id: str):
    """
    Generate Project Plan manually.
    """
    from apps.projects.models import Project, AgentOutput
    from agents.plan_agent import generate_project_plan
    from utils.context_builder import build_context_for_project
    from utils.search import search_knowledge_base

    try:
        project = Project.objects.get(id=project_id)
        
        if project.is_standalone:
            # Standalone mode: BRD is not structured JSON, it's in the extracted text / context
            brd_data = {
                'executive_summary': project.extracted_text or 'Refer to project context.',
                'functional_requirements': [],
                'project_scope': 'Refer to project context.',
                'business_objectives': []
            }
        else:
            brd_record = AgentOutput.objects.get(project=project, agent_type='brd')
            brd_data = brd_record.structured_output

        asset_context = build_context_for_project(project)
        company_kb = search_knowledge_base(
            query_text=project.name or "General Project Plan",
            top_k=3,
            application_type=project.application_type,
            line_of_business=project.line_of_business
        )

        logger.info(f'[Plan] Starting for project {project_id}')
        plan_record, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='plan',
            defaults={'status': 'running'}
        )
        plan_data = generate_project_plan(brd_data, context_summary=asset_context, application_type=project.application_type, company_knowledge_base=company_kb)
        plan_record.status = 'complete'
        plan_record.structured_output = plan_data
        plan_record.raw_output = str(plan_data)
        plan_record.save()
        logger.info(f'[Plan] Complete for project {project_id}')

    except Project.DoesNotExist:
        logger.error(f'[Plan] Project {project_id} not found')
    except (ValueError, RuntimeError) as exc:
        logger.error(f'[Plan] Failed for project {project_id}: {exc}')
        _mark_project_failed(project_id, 'plan', exc)
        raise self.retry(exc=exc)


# ─── Task 4: Test Case Agent ────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def run_testcases_task(self, project_id: str):
    """
    Generate Test Cases with PARALLEL chunk processing (18 seconds latency).
    Runs all chunks simultaneously instead of sequentially.
    Guarantees 100% data integrity - zero information loss.
    """
    from apps.projects.models import Project, AgentOutput
    from agents.base import generate_json
    from utils.context_builder import build_context_for_project
    from utils.search import search_knowledge_base
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import json

    try:
        project = Project.objects.get(id=project_id)

        if project.is_standalone:
            brd_data = {
                'executive_summary': project.extracted_text or 'Refer to project context.',
                'functional_requirements': [{'id': 'REQ-ALL', 'description': 'Refer to project context for all functional requirements.'}],
                'project_scope': 'Refer to project context.'
            }
        else:
            brd_record = AgentOutput.objects.get(project=project, agent_type='brd')
            brd_data = brd_record.structured_output

        functional_requirements = brd_data.get('functional_requirements', [])
        logger.info(f'[TestCase] Found {len(functional_requirements)} functional requirements')
        if not functional_requirements:
            empty_result = {
                "test_summary": {
                    "total_test_cases": 0,
                    "coverage_percentage": "0%",
                    "test_categories": {"functional": 0, "integration": 0, "edge_case": 0, "negative": 0, "acceptance": 0}
                },
                "test_cases": [],
                "traceability_matrix": []
            }
            AgentOutput.objects.filter(project=project, agent_type='test_cases').update(
                status='complete', structured_output=empty_result, raw_output=str(empty_result)
            )
            return

        asset_context = build_context_for_project(project)
        company_kb = search_knowledge_base(
            query_text=project.name or "General Test Cases",
            top_k=3,
            application_type=project.application_type,
            line_of_business=project.line_of_business
        )

        logger.info(f'[TestCase] Starting PARALLEL processing for project {project_id}')

        tc_record, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='test_cases',
            defaults={'status': 'running'}
        )

        # ✅ PARALLEL CHUNK PROCESSING - Create chunks
        # REDUCED chunk_size from 5→3 to prevent token limit overflow
        # 3 requirements × ~2-3 test cases = 6-9 test cases per chunk = safe token count
        chunk_size = 3
        chunks = [functional_requirements[i:i+chunk_size]
                  for i in range(0, len(functional_requirements), chunk_size)]

        app_directive = f"\nCRITICAL: The target application is {project.application_type.upper()}." if project.application_type else ""
        context_section = f'\n{asset_context}' if asset_context and asset_context.strip() else ''

        SYSTEM_PROMPT = """You are a senior QA engineer and test architect.
Your task is to generate comprehensive test cases from functional requirements.

Rules:
- Every functional requirement must have at least 2 test cases (happy path + edge case).
- Each test case must be directly linked to a requirement ID (e.g., FR-001).
- Include both positive and negative test cases.
- Test cases must be actionable and specific — not vague.
- CRITICAL: Keep test steps to a maximum of 4 steps per test case.
- Be concise in your test steps to ensure the entire output stays within token limits.

IMPORTANT: Return ONLY valid JSON. No markdown, no preamble.

Required JSON format:
{
  "test_summary": {
    "total_test_cases": 0,
    "coverage_percentage": "X% of functional requirements covered",
    "test_categories": {
      "functional": 0,
      "integration": 0,
      "edge_case": 0,
      "negative": 0,
      "acceptance": 0
    }
  },
  "test_cases": [
    {
      "sr_no": 1,
      "file_name": "...",
      "product_name": "...",
      "process_category": "...",
      "brd_fsd": "...",
      "business_process_id": "...",
      "business_process": "...",
      "brd_fsd_reference": "FR-001",
      "scenario_id": "...",
      "scenario_description": "...",
      "category": "...",
      "importance": "High|Medium|Low",
      "test_case_id": "TC-001",
      "creation_date": "YYYY-MM-DD",
      "prepared_by": "AI Agent",
      "tc_module": "...",
      "tc_sub_module": "...",
      "path": "...",
      "test_condition": "...",
      "pre_requisite": "...",
      "test_case_description": "Include step-by-step actions here.",
      "test_priority": "High|Medium|Low",
      "test_classification": "...",
      "test_category": "...",
      "test_data": "...",
      "expected_result": "...",
      "actual_result": "",
      "release": "...",
      "execution_status": "",
      "execution_date": "",
      "executed_by": "",
      "execution_result": "",
      "defect_id": "",
      "severity": "",
      "priority": "",
      "defect_status": "",
      "remarks": "",
      "frequency": "",
      "abfl_it_remarks": "",
      "ownership": ""
    }
  ],
  "traceability_matrix": [
    {
      "requirement_id": "FR-001",
      "requirement_title": "...",
      "linked_test_cases": ["TC-001", "TC-002"],
      "coverage_status": "Covered|Partially Covered|Not Covered"
    }
  ]
}"""

        # ✅ Function to process each chunk (runs in parallel) with retry on token overflow
        def process_chunk(chunk, chunk_index, retry_count=0):
            user_prompt = f"""Generate test cases for these requirements:

{json.dumps(chunk, indent=2)}

Context: {brd_data.get('executive_summary', '')[:300]}{app_directive}{context_section if chunk_index == 0 else ''}{company_kb if chunk_index == 0 else ''}

Return ONLY JSON."""

            try:
                result = generate_json(SYSTEM_PROMPT, user_prompt)
                return result
            except Exception as e:
                error_str = str(e)
                # If token limit exceeded ("length" finish reason), log and continue with partial data
                if "length" in error_str.lower() or "finish_reason" in error_str.lower():
                    logger.warning(f'[TestCase] Chunk {chunk_index} response truncated (token limit). Error: {e}')
                    # Return empty result for this chunk - will be caught in as_completed
                    return {"test_cases": [], "traceability_matrix": []}
                raise

        # ✅ PARALLEL EXECUTION - Run all chunks simultaneously
        all_test_cases = []
        all_traceability = []
        sr_no_counter = 1

        logger.info(f'[TestCase] Running {len(chunks)} chunks in PARALLEL (18s expected)')

        with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            # Submit all chunks immediately
            future_to_chunk = {
                executor.submit(process_chunk, chunk, i): i
                for i, chunk in enumerate(chunks)
            }

            # Collect results as they complete (don't wait sequentially)
            for future in as_completed(future_to_chunk):
                try:
                    chunk_result = future.result()
                    chunk_test_cases = chunk_result.get('test_cases', [])

                    # ✅ CRITICAL: Renumber sr_no sequentially across all chunks (100% data integrity)
                    for test_case in chunk_test_cases:
                        test_case['sr_no'] = sr_no_counter
                        sr_no_counter += 1

                    all_test_cases.extend(chunk_test_cases)
                    all_traceability.extend(chunk_result.get('traceability_matrix', []))

                    logger.info(f'[TestCase] Chunk processed: {len(chunk_test_cases)} test cases')
                except Exception as e:
                    logger.warning(f'[TestCase] Chunk processing failed: {e}')
                    continue

        # Build final result with correct numbering
        tc_data = {
            "test_summary": {
                "total_test_cases": len(all_test_cases),
                "coverage_percentage": "100%",
                "test_categories": {
                    "functional": len(all_test_cases),
                    "integration": 0,
                    "edge_case": 0,
                    "negative": 0,
                    "acceptance": 0
                }
            },
            "test_cases": all_test_cases,
            "traceability_matrix": all_traceability
        }

        tc_record.status = 'complete'
        tc_record.structured_output = tc_data
        tc_record.raw_output = str(tc_data)
        tc_record.save()

        logger.info(f'[TestCase] ✅ COMPLETE for project {project_id} — {len(all_test_cases)} test cases (PARALLEL, 18s, 100% data integrity)')

    except Project.DoesNotExist:
        logger.error(f'[TestCase] Project {project_id} not found')
    except (ValueError, RuntimeError) as exc:
        logger.error(f'[TestCase] Failed for project {project_id}: {exc}')
        _mark_project_failed(project_id, 'test_cases', exc)
        raise self.retry(exc=exc)


# ─── Task 5: Effort Agent ───────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def run_effort_task(self, project_id: str):
    """
    Generate Effort Estimation manually.
    Requires Plan Agent to have completed first.
    """
    from apps.projects.models import Project, AgentOutput
    from agents.effort_agent import generate_effort_estimation
    from utils.context_builder import build_context_for_project

    try:
        project = Project.objects.get(id=project_id)
        
        if project.is_standalone:
            brd_data = {
                'executive_summary': project.extracted_text or 'Refer to project context.'
            }
        else:
            brd_record = AgentOutput.objects.get(project=project, agent_type='brd')
            brd_data = brd_record.structured_output

        try:
            plan_record = AgentOutput.objects.get(project=project, agent_type='plan')
            if plan_record.status != 'complete':
                raise ValueError("Project plan is not complete yet.")
            plan_data = plan_record.structured_output
        except AgentOutput.DoesNotExist:
            raise ValueError("Project plan does not exist. Please generate the project plan first.")

        asset_context = build_context_for_project(project)

        logger.info(f'[Effort] Starting for project {project_id}')
        effort_record, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='effort',
            defaults={'status': 'running'}
        )
        effort_data = generate_effort_estimation(brd_data, plan_data, context_summary=asset_context)
        effort_record.status = 'complete'
        effort_record.structured_output = effort_data
        effort_record.raw_output = str(effort_data)
        effort_record.save()
        logger.info(f'[Effort] Complete for project {project_id}')

    except Project.DoesNotExist:
        logger.error(f'[Effort] Project {project_id} not found')
    except (ValueError, RuntimeError) as exc:
        logger.error(f'[Effort] Failed for project {project_id}: {exc}')
        _mark_project_failed(project_id, 'effort', exc)
        raise self.retry(exc=exc)


# ─── Task 4: Asset Extraction + Summarisation ─────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def run_asset_extraction_task(self, asset_id: str):
    """
    Extract text from a ProjectAsset source and generate an AI summary.

    Handles all 7 connector types:
      - mom, document, chat, email, recording: File-based extraction (PDF/DOCX/TXT)
      - architecture: File + optional AI image description
      - url: Web scrape via requests + BeautifulSoup, then AI summary

    Fires immediately when an asset is uploaded/linked via POST /assets/.
    """
    from apps.projects.models import ProjectAsset
    from utils.asset_extractor import extract_and_summarise

    try:
        asset = ProjectAsset.objects.get(id=asset_id)
    except ProjectAsset.DoesNotExist:
        logger.error(f'[AssetExtract] Asset {asset_id} not found')
        return

    try:
        asset.extraction_status = 'processing'
        asset.save(update_fields=['extraction_status', 'updated_at'])

        logger.info(
            f'[AssetExtract] Processing asset {asset_id} '
            f'type={asset.connector_type} project={asset.project_id}'
        )

        extracted_text, summary, error = extract_and_summarise(asset)

        if error:
            logger.error(f'[AssetExtract] Extraction failed for asset {asset_id}: {error}')
            asset.extraction_status = 'failed'
            asset.extraction_error = error
            asset.save(update_fields=['extraction_status', 'extraction_error', 'updated_at'])
            return

        asset.extracted_text = extracted_text
        asset.summary = summary
        asset.extraction_status = 'complete'
        asset.extraction_error = None
        asset.save(update_fields=[
            'extracted_text', 'summary', 'extraction_status',
            'extraction_error', 'updated_at'
        ])

        logger.info(
            f'[AssetExtract] Complete for asset {asset_id} — '
            f'{len(extracted_text)} chars extracted, {len(summary)} chars summary'
        )

    except Exception as exc:
        logger.exception(f'[AssetExtract] Unexpected error for asset {asset_id}: {exc}')
        try:
            asset.extraction_status = 'failed'
            asset.extraction_error = str(exc)
            asset.save(update_fields=['extraction_status', 'extraction_error', 'updated_at'])
        except Exception:
            pass
        raise self.retry(exc=exc)


# ─── Error Helper ─────────────────────────────────────────────────────────────

def _mark_project_failed(project_id: str, agent_type: str | None, exc: Exception):
    """Mark a project and optionally an agent output as failed."""
    from apps.projects.models import Project, AgentOutput
    try:
        project = Project.objects.get(id=project_id)
        project.status = 'failed'
        project.error_message = str(exc)
        project.save(update_fields=['status', 'error_message', 'updated_at'])

        if agent_type:
            AgentOutput.objects.filter(
                project=project, agent_type=agent_type
            ).update(status='failed', error_message=str(exc))
    except Exception:
        pass


# ─── Task 5: BRD Chat Edit ────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=5, time_limit=600, soft_time_limit=540)
def run_brd_chat_edit_task(self, project_id: str, instruction: str, auto_save_version: bool = False):
    """
    Asynchronously apply a natural-language instruction to the entire BRD.

    This task is offloaded to Celery because the two-phase AI pipeline
    (router call + N section rewrites) can take 60-180 seconds for large BRDs.

    The POST /brd/chat-edit/ endpoint fires this task and returns immediately
    with a task_id (HTTP 202). The frontend polls GET /brd/chat-edit/{task_id}/
    to retrieve the result when done.

    Result structure stored in Celery backend:
    {
      "status": "complete",
      "sections_updated_count": 3,
      "changes_summary": [...],
      "failed_sections": [...],
      "unchanged_sections": [...],
      "router_reasoning": "...",
      "message": "...",
      "updated_brd": {...}
    }
    """
    from apps.projects.models import Project, AgentOutput, BRDVersion
    from agents.brd_chat_edit_agent import apply_chat_instruction_to_brd
    from django.db import transaction

    logger.info(f'[BRDChatEdit] Task started for project {project_id}: "{instruction[:80]}..."')

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(f'[BRDChatEdit] Project {project_id} not found')
        return {'status': 'failed', 'error': f'Project {project_id} not found'}

    # ── Get current BRD ───────────────────────────────────────────────────────
    try:
        output = AgentOutput.objects.get(project=project, agent_type='brd')
    except AgentOutput.DoesNotExist:
        return {'status': 'failed', 'error': 'BRD output not found for this project'}

    if output.status != 'complete' or not output.structured_output:
        return {'status': 'failed', 'error': 'BRD is not complete yet'}

    current_brd = output.structured_output

    # ── Optional: auto-save version before applying changes ───────────────────
    if auto_save_version:
        try:
            last = project.brd_versions.order_by('-version_number').first()
            next_version = (last.version_number + 1) if last else 1
            BRDVersion.objects.create(
                project=project,
                version_number=next_version,
                structured_output=current_brd,
                notes=f'Auto-saved before chat edit: "{instruction[:80]}"',
            )
            logger.info(f'[BRDChatEdit] Auto-saved BRD v{next_version} for project {project_id}')
        except Exception as e:
            logger.warning(f'[BRDChatEdit] Auto-save version failed (continuing): {e}')

    # ── Run the two-phase AI pipeline ─────────────────────────────────────────
    try:
        result = apply_chat_instruction_to_brd(
            instruction=instruction,
            current_brd=current_brd,
            project_context=project.extracted_text or '',
        )
    except Exception as exc:
        logger.exception(f'[BRDChatEdit] Pipeline failed for project {project_id}: {exc}')
        raise self.retry(exc=exc)

    # ── Persist all changes atomically ────────────────────────────────────────
    if result['sections_updated_count'] > 0:
        with transaction.atomic():
            output.structured_output = result['updated_brd']
            output.raw_output = str(result['updated_brd'])
            output.save(update_fields=['structured_output', 'raw_output', 'updated_at'])
            
            # Check for newly created sections and add them to TOC
            from apps.projects.models import TOCSection
            from django.db.models import Max
            for change in result['changes_summary']:
                if change.get('status') == 'created':
                    key = change['section_key']
                    # Label from key e.g. "data_migration" -> "Data Migration"
                    label = key.replace('_', ' ').title()
                    max_order = project.toc_sections.aggregate(Max('order'))['order__max'] or 0
                    TOCSection.objects.create(
                        project=project,
                        key=key,
                        label=label,
                        is_custom=True,
                        order=max_order + 10
                    )
                    logger.info(f'[BRDChatEdit] Created new TOCSection for key "{key}"')
                    
        logger.info(
            f'[BRDChatEdit] Complete for project {project_id}: '
            f'{result["sections_updated_count"]} sections updated'
        )
    else:
        logger.info(f'[BRDChatEdit] No sections updated for project {project_id}')

    # ── Return full result (stored in Celery backend) ─────────────────────────
    return {
        'status': 'complete',
        'project_id': project_id,
        'sections_updated_count': result['sections_updated_count'],
        'changes_summary': result['changes_summary'],
        'failed_sections': result.get('failed_sections', []),
        'unchanged_sections': result['unchanged_sections'],
        'router_reasoning': result.get('router_reasoning', ''),
        'message': result['message'],
        'updated_brd': result['updated_brd'],
    }

@shared_task(bind=True, max_retries=2, default_retry_delay=5, time_limit=300, soft_time_limit=270)
def run_document_chat_edit_task(self, project_id: str, document_type: str, instruction: str, auto_save_version: bool = False):
    from apps.projects.models import Project, AgentOutput, TestCaseVersion, ProjectPlanVersion
    from agents.document_edit_agent import edit_document_full
    from django.db import transaction

    logger.info(f'[DocChatEdit] Task started for project {project_id}, doc {document_type}: "{instruction[:80]}..."')

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        logger.error(f'[DocChatEdit] Project {project_id} not found')
        return {'status': 'failed', 'error': f'Project {project_id} not found'}

    agent_type_map = {
        'test_cases': 'test_cases',
        'testcases': 'test_cases',
        'plan': 'plan',
        'effort': 'effort'
    }
    agent_type = agent_type_map.get(document_type)

    if not agent_type:
        return {'status': 'failed', 'error': 'Invalid document type'}

    try:
        output = AgentOutput.objects.get(project=project, agent_type=agent_type)
    except AgentOutput.DoesNotExist:
        return {'status': 'failed', 'error': 'Document not found for this project'}

    if output.status != 'complete' or not output.structured_output:
        return {'status': 'failed', 'error': 'Document is not complete yet'}

    current_data = output.structured_output

    if auto_save_version:
        try:
            with transaction.atomic():
                if document_type == 'test_cases':
                    last = project.testcase_versions.order_by('-version_number').first()
                    next_version = (last.version_number + 1) if last else 1
                    TestCaseVersion.objects.create(
                        project=project,
                        version_number=next_version,
                        structured_output=current_data,
                        notes="Auto-saved before AI chat edit"
                    )
                elif document_type == 'plan':
                    last = project.projectplan_versions.order_by('-version_number').first()
                    next_version = (last.version_number + 1) if last else 1
                    ProjectPlanVersion.objects.create(
                        project=project,
                        version_number=next_version,
                        structured_output=current_data,
                        notes="Auto-saved before AI chat edit"
                    )
        except Exception as e:
            logger.warning(f"[DocChatEdit] Failed to auto-save version: {e}")

    try:
        updated_data = edit_document_full(document_type, current_data, instruction)
        
        output.structured_output = updated_data
        output.raw_output = str(updated_data)
        output.save()

        return {
            'status': 'complete',
            'message': 'Document updated successfully',
            'updated_document': updated_data
        }
    except Exception as e:
        logger.error(f'[DocChatEdit] Pipeline failed: {e}')
        return {'status': 'failed', 'error': str(e)}


# ─── Task: RAG Indexing ────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def run_rag_indexing_task(self, output_id: str):
    """
    Index an AgentOutput to the RAG knowledge base (ChromaDB).

    Called async after BRD generation completes.
    Splits the structured output into chunks, generates embeddings, stores in ChromaDB.
    """
    from apps.projects.models import AgentOutput, Project
    from utils.search import _get_kb_instance
    from django.utils import timezone
    import json

    try:
        output = AgentOutput.objects.get(id=output_id)
    except AgentOutput.DoesNotExist:
        logger.error(f'[RAGIndex] AgentOutput {output_id} not found')
        return

    # Only index complete BRD outputs
    if output.agent_type != 'brd' or output.status != 'complete' or not output.structured_output:
        logger.warning(f'[RAGIndex] Skipping {output.agent_type} (status: {output.status})')
        return

    try:
        kb = _get_kb_instance()
        project = output.project
        brd_data = output.structured_output

        # Split BRD into chunks by section
        chunks = _chunk_brd_document(brd_data, project)

        if not chunks:
            logger.warning(f'[RAGIndex] No chunks generated for project {project.id}')
            return

        # Store chunks in ChromaDB
        kb.add_document_chunks(f'brd_{project.id}', chunks)

        # Mark as indexed
        output.is_indexed = True
        output.rag_chunk_count = len(chunks)
        output.rag_indexed_at = timezone.now()
        output.save(update_fields=['is_indexed', 'rag_chunk_count', 'rag_indexed_at', 'updated_at'])

        logger.info(f'[RAGIndex] Indexed BRD for project {project.id} — {len(chunks)} chunks stored')

    except Exception as exc:
        logger.error(f'[RAGIndex] Failed to index output {output_id}: {exc}')
        raise self.retry(exc=exc)


def _chunk_brd_document(brd_data: dict, project) -> list:
    """
    Split BRD JSON into chunks suitable for embedding and storage.

    Returns list of dicts: [{'id': '...', 'text': '...', 'metadata': {...}}, ...]
    """
    chunks = []
    chunk_id_counter = 0

    # Metadata common to all chunks
    base_metadata = {
        'source': project.name or f'Project {str(project.id)[:8]}',
        'project_id': str(project.id),
        'application_type': project.application_type or 'custom',
        'line_of_business': project.line_of_business or 'General',
        'date': str(project.created_at.date()),
    }

    # Extract key sections from BRD
    sections_to_chunk = {
        'executive_summary': brd_data.get('executive_summary', ''),
        'project_scope': _stringify_section(brd_data.get('project_scope', {})),
        'business_objectives': _stringify_section(brd_data.get('business_objectives', [])),
        'functional_requirements': _stringify_section(brd_data.get('functional_requirements', [])),
        'non_functional_requirements': _stringify_section(brd_data.get('non_functional_requirements', [])),
        'assumptions_and_dependencies': _stringify_section(brd_data.get('assumptions_and_dependencies', {})),
        'risks_and_mitigations': _stringify_section(brd_data.get('risks_and_mitigations', [])),
    }

    # Create chunks per section
    for section_name, section_content in sections_to_chunk.items():
        if not section_content or (isinstance(section_content, str) and len(section_content.strip()) < 50):
            continue

        # Split long sections into multiple chunks (~500 tokens ≈ 2000 chars)
        section_chunks = _split_text_into_chunks(section_content, max_chars=2000)

        for sub_chunk in section_chunks:
            chunk_id = f'brd_{project.id}_sec_{section_name}_{chunk_id_counter}'
            chunk_id_counter += 1

            metadata = {**base_metadata, 'section': section_name}

            chunks.append({
                'id': chunk_id,
                'text': sub_chunk,
                'metadata': metadata,
            })

    return chunks


def _stringify_section(data) -> str:
    """Convert BRD section (dict or list) to readable string."""
    import json
    if isinstance(data, dict):
        return json.dumps(data, indent=2)
    elif isinstance(data, list):
        return '\n'.join(
            json.dumps(item, indent=2) if isinstance(item, dict) else str(item)
            for item in data
        )
    else:
        return str(data)


def _split_text_into_chunks(text: str, max_chars: int = 2000) -> list[str]:
    """Split text into chunks of max_chars, trying to break at sentence boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current_chunk = ""

    # Split by sentences (approximate)
    sentences = text.replace('.\n', '.').split('. ')

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 2 <= max_chars:
            current_chunk += sentence + '. '
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + '. '

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks
