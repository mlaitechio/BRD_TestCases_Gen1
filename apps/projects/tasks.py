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

        logger.info(f'[BRD] Starting for project {project_id}')
        result = generate_brd(
            project_description=full_description,
            clarification_answers=answers,
            revision_notes=project.revision_notes,
            context_summary=asset_context,
        )

        agent_output.status = 'complete'
        agent_output.structured_output = result
        agent_output.raw_output = str(result)
        agent_output.save()

        project.status = 'awaiting_approval'
        project.revision_notes = None
        project.save(update_fields=['status', 'revision_notes', 'updated_at'])

        logger.info(f'[BRD] Complete for project {project_id}')

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
        
        logger.info(f'[Plan] Starting for project {project_id}')
        plan_record, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='plan',
            defaults={'status': 'running'}
        )
        plan_data = generate_project_plan(brd_data, context_summary=asset_context, application_type=project.application_type)
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
    Generate Test Cases manually.
    """
    from apps.projects.models import Project, AgentOutput
    from agents.testcase_agent import generate_test_cases
    from utils.context_builder import build_context_for_project

    try:
        project = Project.objects.get(id=project_id)
        
        if project.is_standalone:
            # Standalone mode
            brd_data = {
                'executive_summary': project.extracted_text or 'Refer to project context.',
                'functional_requirements': [{'id': 'REQ-ALL', 'description': 'Refer to project context for all functional requirements.'}],
                'project_scope': 'Refer to project context.'
            }
        else:
            brd_record = AgentOutput.objects.get(project=project, agent_type='brd')
            brd_data = brd_record.structured_output

        asset_context = build_context_for_project(project)
        
        logger.info(f'[TestCase] Starting for project {project_id}')
        tc_record, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='test_cases',
            defaults={'status': 'running'}
        )
        tc_data = generate_test_cases(brd_data, context_summary=asset_context, application_type=project.application_type)
        tc_record.status = 'complete'
        tc_record.structured_output = tc_data
        tc_record.raw_output = str(tc_data)
        tc_record.save()
        logger.info(f'[TestCase] Complete for project {project_id}')

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
