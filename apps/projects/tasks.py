"""
Celery Tasks for BRD Automation Pipeline.

Two-task pattern (safest for MVP):
  Task 1: run_clarification_task  — runs Clarification Agent
  Task 2: run_brd_task            — runs BRD Agent (after user answers)
  Task 3: run_remaining_agents_task — runs Plan → TestCase → Effort (after BRD approval)
"""

import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def run_clarification_task(self, project_id: str):
    """
    Task 1: Run the Clarification Agent to generate 3-5 questions.
    Fires immediately after project creation.
    """
    # Import here to avoid circular imports
    from apps.projects.models import Project, AgentOutput
    from agents.clarification_agent import generate_clarification_questions

    try:
        project = Project.objects.get(id=project_id)
        project.status = 'clarifying'
        project.save(update_fields=['status', 'updated_at'])

        # Create or update AgentOutput record
        agent_output, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='clarification',
            defaults={'status': 'running'}
        )

        logger.info(f'[Clarification] Starting for project {project_id}')
        result = generate_clarification_questions(project.extracted_text)

        # Save the structured output
        agent_output.status = 'complete'
        agent_output.structured_output = result
        agent_output.raw_output = str(result)
        agent_output.save()

        # Store questions on the project for quick access
        project.clarification_questions = result.get('questions', [])
        project.status = 'awaiting_answers'
        project.save(update_fields=['clarification_questions', 'status', 'updated_at'])

        logger.info(f'[Clarification] Complete for project {project_id}')

    except Project.DoesNotExist:
        logger.error(f'[Clarification] Project {project_id} not found')

    except (ValueError, RuntimeError) as exc:
        logger.error(f'[Clarification] Failed for project {project_id}: {exc}')
        try:
            project = Project.objects.get(id=project_id)
            project.status = 'failed'
            project.error_message = str(exc)
            project.save(update_fields=['status', 'error_message', 'updated_at'])

            AgentOutput.objects.filter(
                project=project, agent_type='clarification'
            ).update(status='failed', error_message=str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def run_brd_task(self, project_id: str):
    """
    Task 2: Run the BRD Agent using project description + clarification answers.
    Fires after user submits answers to clarification questions.
    Also used when user requests a revision.
    """
    from apps.projects.models import Project, AgentOutput
    from agents.brd_agent import generate_brd

    try:
        project = Project.objects.get(id=project_id)
        project.status = 'generating_brd'
        project.save(update_fields=['status', 'updated_at'])

        agent_output, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='brd',
            defaults={'status': 'running', 'structured_output': None, 'raw_output': None}
        )

        # Build answers dict: {Q1: answer, Q2: answer, ...}
        answers = {}
        if project.clarification_answers:
            answers = project.clarification_answers

        logger.info(f'[BRD] Starting for project {project_id}')
        result = generate_brd(
            project_description=project.extracted_text,
            clarification_answers=answers,
            revision_notes=project.revision_notes
        )

        agent_output.status = 'complete'
        agent_output.structured_output = result
        agent_output.raw_output = str(result)
        agent_output.save()

        project.status = 'awaiting_approval'
        project.revision_notes = None  # Clear revision notes after re-generation
        project.save(update_fields=['status', 'revision_notes', 'updated_at'])

        logger.info(f'[BRD] Complete for project {project_id}')

    except Project.DoesNotExist:
        logger.error(f'[BRD] Project {project_id} not found')

    except (ValueError, RuntimeError) as exc:
        logger.error(f'[BRD] Failed for project {project_id}: {exc}')
        try:
            project = Project.objects.get(id=project_id)
            project.status = 'failed'
            project.error_message = str(exc)
            project.save(update_fields=['status', 'error_message', 'updated_at'])

            AgentOutput.objects.filter(
                project=project, agent_type='brd'
            ).update(status='failed', error_message=str(exc))
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def run_remaining_agents_task(self, project_id: str):
    """
    Task 3: Run Plan → Test Case → Effort agents sequentially.
    Fires after the BRD is approved by the user.
    """
    from apps.projects.models import Project, AgentOutput
    from agents.plan_agent import generate_project_plan
    from agents.testcase_agent import generate_test_cases
    from agents.effort_agent import generate_effort_estimation

    try:
        project = Project.objects.get(id=project_id)
        project.status = 'approved'
        project.save(update_fields=['status', 'updated_at'])

        # Fetch the approved BRD output
        brd_record = AgentOutput.objects.get(project=project, agent_type='brd')
        brd_data = brd_record.structured_output

        # ── Plan Agent ──────────────────────────────────────────────────────
        logger.info(f'[Plan] Starting for project {project_id}')
        plan_record, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='plan',
            defaults={'status': 'running'}
        )
        plan_data = generate_project_plan(brd_data)
        plan_record.status = 'complete'
        plan_record.structured_output = plan_data
        plan_record.raw_output = str(plan_data)
        plan_record.save()
        logger.info(f'[Plan] Complete for project {project_id}')

        # ── Test Case Agent ──────────────────────────────────────────────────
        logger.info(f'[TestCase] Starting for project {project_id}')
        tc_record, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='test_cases',
            defaults={'status': 'running'}
        )
        tc_data = generate_test_cases(brd_data)
        tc_record.status = 'complete'
        tc_record.structured_output = tc_data
        tc_record.raw_output = str(tc_data)
        tc_record.save()
        logger.info(f'[TestCase] Complete for project {project_id}')

        # ── Effort Agent ─────────────────────────────────────────────────────
        logger.info(f'[Effort] Starting for project {project_id}')
        effort_record, _ = AgentOutput.objects.update_or_create(
            project=project,
            agent_type='effort',
            defaults={'status': 'running'}
        )
        effort_data = generate_effort_estimation(brd_data, plan_data)
        effort_record.status = 'complete'
        effort_record.structured_output = effort_data
        effort_record.raw_output = str(effort_data)
        effort_record.save()
        logger.info(f'[Effort] Complete for project {project_id}')

        # ── All Done ─────────────────────────────────────────────────────────
        project.status = 'complete'
        project.save(update_fields=['status', 'updated_at'])
        logger.info(f'[Pipeline] All agents complete for project {project_id}')

    except Project.DoesNotExist:
        logger.error(f'[Remaining] Project {project_id} not found')

    except (ValueError, RuntimeError) as exc:
        logger.error(f'[Remaining] Failed for project {project_id}: {exc}')
        try:
            project = Project.objects.get(id=project_id)
            project.status = 'failed'
            project.error_message = str(exc)
            project.save(update_fields=['status', 'error_message', 'updated_at'])
        except Exception:
            pass
        raise self.retry(exc=exc)
