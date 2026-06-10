"""
BRD Automation API Views — Full Endpoint Suite.

Endpoint Summary:
  ── Project Lifecycle ──────────────────────────────────────────────────────
  GET    /api/projects/                               List all projects
  POST   /api/projects/                               Create project → fires BRD immediately
  GET    /api/projects/:id/                           Get project detail
  GET    /api/projects/:id/status/                    Poll project status
  POST   /api/projects/:id/approve-brd/               Approve → fires remaining agents
  POST   /api/projects/:id/revise-brd/                Request revision with notes

  ── Document Outputs ───────────────────────────────────────────────────────
  GET    /api/projects/:id/brd/                       Get BRD JSON
  GET    /api/projects/:id/plan/                      Get Project Plan JSON
  GET    /api/projects/:id/testcases/                 Get Test Cases JSON
  GET    /api/projects/:id/effort/                    Get Effort Estimation JSON
  GET    /api/projects/:id/download/:type/            Download DOCX

  ── BRD Versioning ─────────────────────────────────────────────────────────
  GET    /api/projects/:id/brd/versions/              List all BRD versions
  POST   /api/projects/:id/brd/save-version/          Save BRD snapshot
  POST   /api/projects/:id/brd/restore/:vn/           Restore BRD to version N
  PATCH  /api/projects/:id/brd/edit-section/          AI-assisted single section rewrite
  POST   /api/projects/:id/brd/chat-edit/             Chat instruction → auto-update entire BRD

  ── Table of Contents ──────────────────────────────────────────────────────
  GET    /api/projects/:id/toc/                       Get TOC sections
  PUT    /api/projects/:id/toc/                       Save/reorder TOC

  ── Source Connectors (Knowledge Layer) ───────────────────────────────────
  GET    /api/projects/:id/assets/                    List all project assets
  POST   /api/projects/:id/assets/                    Upload/link an asset
  PATCH  /api/projects/:id/assets/:aid/toggle/        Toggle asset ON/OFF
  DELETE /api/projects/:id/assets/:aid/               Delete an asset

  ── AI Chat ────────────────────────────────────────────────────────────────
  POST   /api/projects/:id/chat/                      Send chat message, get response
"""

import logging
from django.http import FileResponse
from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Project, AgentOutput, ProjectAsset, BRDVersion, TOCSection, TestCaseVersion, ProjectPlanVersion
from .serializers import (
    ProjectCreateSerializer,
    ProjectListSerializer,
    ProjectDetailSerializer,
    ProjectStatusSerializer,
    RevisionSerializer,
    AgentOutputSerializer,
    ProjectAssetSerializer,
    ProjectAssetCreateSerializer,
    AssetToggleSerializer,
    BRDVersionListSerializer,
    BRDVersionDetailSerializer,
    SaveVersionSerializer,
    TestCaseVersionListSerializer,
    TestCaseVersionDetailSerializer,
    ProjectPlanVersionListSerializer,
    ProjectPlanVersionDetailSerializer,
    TOCSectionSerializer,
    TOCSaveSerializer,
    ChatMessageSerializer,
    SectionEditSerializer,
    DocumentChatEditSerializer,
)
from utils.file_extractor import extract_text_from_file

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_project_or_404(pk) -> tuple:
    """Return (project, None) or (None, error_response)."""
    try:
        return Project.objects.get(id=pk), None
    except Project.DoesNotExist:
        return None, Response(
            {'error': f'Project {pk} not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


def _get_agent_output(project: Project, agent_type: str) -> tuple:
    """Return (output, None) or (None, error_response)."""
    try:
        return AgentOutput.objects.get(project=project, agent_type=agent_type), None
    except AgentOutput.DoesNotExist:
        return None, Response(
            {'error': f'{agent_type} output not available yet. Check /status/ first.'},
            status=status.HTTP_404_NOT_FOUND
        )


def _get_asset_or_404(project: Project, asset_id) -> tuple:
    """Return (asset, None) or (None, error_response)."""
    try:
        return ProjectAsset.objects.get(id=asset_id, project=project), None
    except ProjectAsset.DoesNotExist:
        return None, Response(
            {'error': f'Asset {asset_id} not found for this project.'},
            status=status.HTTP_404_NOT_FOUND
        )


# ─── Project List & Create ────────────────────────────────────────────────────

class ProjectListCreateView(APIView):
    """
    GET  /api/projects/   — List all projects (most recent first)
    POST /api/projects/   — Create a new project and fire BRD agent directly
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        projects = Project.objects.all()
        serializer = ProjectListSerializer(projects, many=True)
        return Response(serializer.data)

    def post(self, request):
        from .tasks import run_brd_task

        serializer = ProjectCreateSerializer(data=request.data)
        print(request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        project = serializer.save()

        # ── Extract text from input ──────────────────────────────────────────
        extracted_text = ''

        if project.uploaded_file:
            file_path = project.uploaded_file.path
            extracted_text = extract_text_from_file(file_path) or ''
            if not extracted_text:
                project.delete()
                return Response(
                    {'error': (
                        'Could not extract text from your uploaded file. '
                        'Please paste your project description as text instead.'
                    )},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )

        if project.raw_input:
            extracted_text = (extracted_text + '\n\n' + project.raw_input).strip()

        if not extracted_text:
            project.delete()
            return Response(
                {'error': 'Please provide either a project description (raw_input) or upload a file.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        project.extracted_text = extracted_text
        project.status = 'new'
        project.save(update_fields=['extracted_text', 'status'])

        # Seed default TOC for this project
        TOCSection.seed_default_toc(project)

        logger.info(f'Created project {project.id}')

        return Response(
            {
                'id': str(project.id),
                'status': project.status,
                'message': 'Project created successfully.',
            },
            status=status.HTTP_201_CREATED
        )


# ─── Project Detail & Status ──────────────────────────────────────────────────

class ProjectDetailView(APIView):
    """GET /api/projects/:id/ — Full project detail including metadata."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        serializer = ProjectDetailSerializer(project)
        return Response(serializer.data)


class ProjectStatusView(APIView):
    """
    GET /api/projects/:id/status/
    Returns current project + per-agent output statuses. Poll every 2-3 seconds.
    """
    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        serializer = ProjectStatusSerializer(project)
        return Response(serializer.data)


# ─── BRD Output, Approval & Revision ─────────────────────────────────────────

class BRDOutputView(APIView):
    """GET /api/projects/:id/brd/ — Returns the full structured BRD JSON."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        output, error = _get_agent_output(project, 'brd')
        if error:
            return error
        serializer = AgentOutputSerializer(output)
        return Response(serializer.data)


class GenerateBRDView(APIView):
    """
    POST /api/projects/:id/generate-brd/
    Manually trigger the BRD generation process (after configuring TOC/assets).
    """
    def post(self, request, pk):
        from .tasks import run_brd_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        run_brd_task.delay(str(project.id))
        logger.info(f'Manually triggered BRD generation for project {project.id}')

        return Response({
            'id': str(project.id),
            'status': 'generating_brd',
            'message': 'BRD generation started...',
        })


class ApproveBRDView(APIView):
    """
    POST /api/projects/:id/approve-brd/
    Approve BRD.
    """
    def post(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        if project.status != 'awaiting_approval':
            return Response(
                {'error': f'BRD can only be approved when status is awaiting_approval. Current: {project.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        project.brd_approved = True
        project.status = 'approved'
        project.save(update_fields=['brd_approved', 'status', 'updated_at'])

        logger.info(f'BRD approved for project {project.id}')

        return Response({
            'id': str(project.id),
            'status': 'approved',
            'message': 'BRD approved successfully.',
        })


class GeneratePlanView(APIView):
    """
    POST /api/projects/:id/generate-plan/
    Manually trigger the Project Plan generation process.
    """
    def post(self, request, pk):
        from .tasks import run_plan_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        if not project.brd_approved:
            return Response(
                {'error': 'BRD must be approved before generating a plan.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        run_plan_task.delay(str(project.id))
        logger.info(f'Manually triggered Plan generation for project {project.id}')

        return Response({
            'id': str(project.id),
            'message': 'Project Plan generation started...',
        })


class GenerateTestCasesView(APIView):
    """
    POST /api/projects/:id/generate-testcases/
    Manually trigger the Test Cases generation process.
    """
    def post(self, request, pk):
        from .tasks import run_testcases_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        if not project.brd_approved:
            return Response(
                {'error': 'BRD must be approved before generating test cases.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        run_testcases_task.delay(str(project.id))
        logger.info(f'Manually triggered Test Cases generation for project {project.id}')

        return Response({
            'id': str(project.id),
            'message': 'Test Cases generation started...',
        })


class GenerateEffortView(APIView):
    """
    POST /api/projects/:id/generate-effort/
    Manually trigger the Effort Estimation process.
    """
    def post(self, request, pk):
        from .tasks import run_effort_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        if not project.brd_approved:
            return Response(
                {'error': 'BRD must be approved before generating effort estimation.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        run_effort_task.delay(str(project.id))
        logger.info(f'Manually triggered Effort generation for project {project.id}')

        return Response({
            'id': str(project.id),
            'message': 'Effort Estimation generation started...',
        })



class ReviseBRDView(APIView):
    """
    POST /api/projects/:id/revise-brd/
    Request revision with notes → resets BRD output and re-fires BRD agent.
    """
    def post(self, request, pk):
        from .tasks import run_brd_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        if project.status not in ('awaiting_approval',):
            return Response(
                {'error': f'BRD can only be revised when status is awaiting_approval. Current: {project.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = RevisionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        project.revision_notes = serializer.validated_data['revision_notes']
        project.brd_approved = False
        project.save(update_fields=['revision_notes', 'brd_approved', 'updated_at'])

        AgentOutput.objects.filter(project=project, agent_type='brd').update(
            status='pending', structured_output=None, raw_output=None
        )

        run_brd_task.delay(str(project.id))
        logger.info(f'BRD revision requested for project {project.id}')

        return Response({
            'id': str(project.id),
            'status': 'generating_brd',
            'message': 'Revision notes saved. Re-generating BRD...',
        })


# ─── BRD Versioning ───────────────────────────────────────────────────────────

class BRDVersionListView(APIView):
    """GET /api/projects/:id/brd/versions/ — List all saved BRD version snapshots."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        versions = project.brd_versions.all()
        serializer = BRDVersionListSerializer(versions, many=True)
        return Response({'count': versions.count(), 'versions': serializer.data})


class SaveBRDVersionView(APIView):
    """
    POST /api/projects/:id/brd/save-version/
    Save the current live BRD as an immutable version snapshot.
    Increments version_number automatically.
    """
    def post(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        output, error = _get_agent_output(project, 'brd')
        if error:
            return error

        if output.status != 'complete' or not output.structured_output:
            return Response(
                {'error': 'BRD is not complete yet. Cannot save a version.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SaveVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Determine next version number
        last = project.brd_versions.order_by('-version_number').first()
        next_version = (last.version_number + 1) if last else 1

        version = BRDVersion.objects.create(
            project=project,
            version_number=next_version,
            structured_output=output.structured_output,
            notes=serializer.validated_data.get('notes', ''),
        )

        logger.info(f'BRD v{next_version} saved for project {project.id}')
        return Response(
            BRDVersionDetailSerializer(version).data,
            status=status.HTTP_201_CREATED
        )


class RestoreBRDVersionView(APIView):
    """
    POST /api/projects/:id/brd/restore/:vn/
    Restore the live BRD to a specific historical version snapshot.
    The current BRD output is overwritten with the version's data.
    """
    def post(self, request, pk, vn):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        try:
            version = BRDVersion.objects.get(project=project, version_number=vn)
        except BRDVersion.DoesNotExist:
            return Response(
                {'error': f'Version {vn} does not exist for this project.'},
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            AgentOutput.objects.update_or_create(
                project=project,
                agent_type='brd',
                defaults={
                    'status': 'complete',
                    'structured_output': version.structured_output,
                    'raw_output': str(version.structured_output),
                }
            )
            project.status = 'awaiting_approval'
            project.brd_approved = False
            project.save(update_fields=['status', 'brd_approved', 'updated_at'])

        logger.info(f'BRD restored to v{vn} for project {project.id}')
        return Response({
            'id': str(project.id),
            'restored_version': vn,
            'status': project.status,
            'message': f'BRD successfully restored to version {vn}.',
        })


# ─── TestCase Versioning ──────────────────────────────────────────────────────

class TestCaseVersionListView(APIView):
    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error: return error
        versions = project.testcase_versions.all()
        serializer = TestCaseVersionListSerializer(versions, many=True)
        return Response({'count': versions.count(), 'versions': serializer.data})

class SaveTestCaseVersionView(APIView):
    def post(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error: return error
        output, error = _get_agent_output(project, 'test_cases')
        if error: return error
        if output.status != 'complete' or not output.structured_output:
            return Response({'error': 'Test Cases not complete.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SaveVersionSerializer(data=request.data)
        if not serializer.is_valid(): return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        last = project.testcase_versions.order_by('-version_number').first()
        next_version = (last.version_number + 1) if last else 1
        version = TestCaseVersion.objects.create(
            project=project, version_number=next_version,
            structured_output=output.structured_output, notes=serializer.validated_data.get('notes', '')
        )
        return Response(TestCaseVersionDetailSerializer(version).data, status=status.HTTP_201_CREATED)

class RestoreTestCaseVersionView(APIView):
    def post(self, request, pk, vn):
        project, error = _get_project_or_404(pk)
        if error: return error
        try:
            version = TestCaseVersion.objects.get(project=project, version_number=vn)
        except TestCaseVersion.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            AgentOutput.objects.update_or_create(
                project=project, agent_type='test_cases',
                defaults={'status': 'complete', 'structured_output': version.structured_output, 'raw_output': str(version.structured_output)}
            )
        return Response({'message': f'Restored to v{vn}'})


# ─── ProjectPlan Versioning ───────────────────────────────────────────────────

class ProjectPlanVersionListView(APIView):
    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error: return error
        versions = project.plan_versions.all()
        serializer = ProjectPlanVersionListSerializer(versions, many=True)
        return Response({'count': versions.count(), 'versions': serializer.data})

class SaveProjectPlanVersionView(APIView):
    def post(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error: return error
        output, error = _get_agent_output(project, 'plan')
        if error: return error
        if output.status != 'complete' or not output.structured_output:
            return Response({'error': 'Project Plan not complete.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = SaveVersionSerializer(data=request.data)
        if not serializer.is_valid(): return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        last = project.plan_versions.order_by('-version_number').first()
        next_version = (last.version_number + 1) if last else 1
        version = ProjectPlanVersion.objects.create(
            project=project, version_number=next_version,
            structured_output=output.structured_output, notes=serializer.validated_data.get('notes', '')
        )
        return Response(ProjectPlanVersionDetailSerializer(version).data, status=status.HTTP_201_CREATED)

class RestoreProjectPlanVersionView(APIView):
    def post(self, request, pk, vn):
        project, error = _get_project_or_404(pk)
        if error: return error
        try:
            version = ProjectPlanVersion.objects.get(project=project, version_number=vn)
        except ProjectPlanVersion.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            AgentOutput.objects.update_or_create(
                project=project, agent_type='plan',
                defaults={'status': 'complete', 'structured_output': version.structured_output, 'raw_output': str(version.structured_output)}
            )
        return Response({'message': f'Restored to v{vn}'})


# ─── AI-Assisted BRD Section Edit ────────────────────────────────────────────

class BRDSectionEditView(APIView):
    """
    PATCH /api/projects/:id/brd/edit-section/
    Ask the AI to rewrite a specific section of the BRD.
    The live BRD JSON is updated in-place for the specified section.

    Request body:
    {
      "section_key": "executive_summary",
      "instructions": "Make it more concise and add a note about GDPR compliance"
    }
    """
    def patch(self, request, pk):
        from agents.section_edit_agent import edit_brd_section

        project, error = _get_project_or_404(pk)
        if error:
            return error

        output, error = _get_agent_output(project, 'brd')
        if error:
            return error

        if output.status != 'complete' or not output.structured_output:
            return Response(
                {'error': 'BRD is not complete yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SectionEditSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        section_key = serializer.validated_data['section_key']
        instructions = serializer.validated_data['instructions']

        current_output = output.structured_output
        if section_key not in current_output:
            return Response(
                {'error': f'Section key "{section_key}" not found in current BRD.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_section_content = edit_brd_section(
                section_key=section_key,
                current_content=current_output[section_key],
                edit_instructions=instructions,
                project_context=project.extracted_text or '',
            )
        except (ValueError, RuntimeError) as e:
            logger.error(f'Section edit failed for project {project.id}: {e}')
            return Response(
                {'error': f'AI section edit failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Update the BRD output in-place for the specific section
        current_output[section_key] = new_section_content
        output.structured_output = current_output
        output.save(update_fields=['structured_output', 'updated_at'])

        logger.info(f'Section "{section_key}" edited for project {project.id}')
        return Response({
            'section_key': section_key,
            'updated_content': new_section_content,
            'message': f'Section "{section_key}" updated successfully.',
        })


# ─── BRD Chat Edit (Full-Document Update — Async via Celery) ─────────────────

class BRDChatEditView(APIView):
    """
    POST /api/projects/:id/brd/chat-edit/

    Fires a Celery task that runs the two-phase AI pipeline in the background:
      Phase 1 — Router LLM call: identifies which sections need updating
      Phase 2 — N section rewrite calls: rewrites each affected section

    Returns HTTP 202 immediately with a task_id.
    Poll GET /brd/chat-edit/{task_id}/ to retrieve the result.

    Request body:
    {
      "instruction": "Add GDPR compliance requirements to all relevant sections",
      "auto_save_version": false
    }

    Response 202 Accepted:
    {
      "task_id": "abc123-...",
      "status": "processing",
      "message": "Chat edit in progress. Poll /brd/chat-edit/{task_id}/ for results.",
      "poll_url": "/api/projects/{id}/brd/chat-edit/abc123-.../"
    }
    """

    def post(self, request, pk):
        from apps.projects.tasks import run_brd_chat_edit_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        output, error = _get_agent_output(project, 'brd')
        if error:
            return error

        if output.status != 'complete' or not output.structured_output:
            return Response(
                {'error': 'BRD is not complete yet. Generate and approve the BRD first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DocumentChatEditSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        instruction = serializer.validated_data['instruction']
        auto_save_version = serializer.validated_data.get('auto_save_version', False)

        # Fire Celery task — returns immediately, no timeout risk
        task = run_brd_chat_edit_task.delay(
            project_id=str(project.id),
            instruction=instruction,
            auto_save_version=auto_save_version,
        )

        logger.info(
            f'BRD chat-edit task queued for project {project.id} '
            f'— task_id: {task.id}'
        )

        return Response(
            {
                'task_id': task.id,
                'status': 'processing',
                'message': 'Chat edit in progress. Poll the status URL every 3-5 seconds.',
                'poll_url': f'/api/projects/{project.id}/brd/chat-edit/{task.id}/',
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BRDChatEditStatusView(APIView):
    """
    GET /api/projects/:id/brd/chat-edit/{task_id}/

    Poll this endpoint after POST /brd/chat-edit/ returns a task_id.
    Returns the task result when the Celery task completes.

    Possible response statuses:
      - "processing"  → task still running, poll again in 3-5s
      - "complete"    → task finished, updated_brd contains the new BRD
      - "failed"      → task failed, check error field

    Response (processing):
    {
      "task_id": "abc123-...",
      "status": "processing",
      "message": "Chat edit is still running..."
    }

    Response (complete):
    {
      "task_id": "abc123-...",
      "status": "complete",
      "sections_updated_count": 3,
      "changes_summary": [...],
      "failed_sections": [],
      "unchanged_sections": [...],
      "router_reasoning": "...",
      "message": "Updated 3 section(s)...",
      "updated_brd": { ...full BRD... }
    }
    """

    def get(self, request, pk, task_id):
        from celery.result import AsyncResult

        # Validate the project exists
        project, error = _get_project_or_404(pk)
        if error:
            return error

        result = AsyncResult(task_id)
        state = result.state  # PENDING, STARTED, SUCCESS, FAILURE, RETRY

        if state in ('PENDING', 'STARTED', 'RETRY'):
            return Response({
                'task_id': task_id,
                'status': 'processing',
                'celery_state': state,
                'message': 'Chat edit is still running. Poll again in 3-5 seconds.',
            })

        if state == 'SUCCESS':
            task_result = result.result or {}
            if isinstance(task_result, dict) and task_result.get('status') == 'failed':
                return Response(
                    {
                        'task_id': task_id,
                        'status': 'failed',
                        'error': task_result.get('error', 'Unknown error'),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            return Response({
                'task_id': task_id,
                **task_result,
            })

        if state == 'FAILURE':
            error_info = str(result.result) if result.result else 'Task failed'
            return Response(
                {
                    'task_id': task_id,
                    'status': 'failed',
                    'error': error_info,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Unknown state
        return Response({
            'task_id': task_id,
            'status': 'processing',
            'celery_state': state,
            'message': 'Unknown state — continue polling.',
        })


# ─── TOC Management ───────────────────────────────────────────────────────────

class TOCView(APIView):
    """
    GET /api/projects/:id/toc/ — Return ordered TOC section list
    PUT /api/projects/:id/toc/ — Save a new TOC configuration (full replace)
    """

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        sections = project.toc_sections.all()

        # Auto-seed default TOC if none exist yet
        if not sections.exists():
            TOCSection.seed_default_toc(project)
            sections = project.toc_sections.all()

        serializer = TOCSectionSerializer(sections, many=True)
        return Response({'sections': serializer.data})

    def put(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        serializer = TOCSaveSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        incoming_sections = serializer.validated_data['sections']

        if not incoming_sections:
            return Response(
                {'error': 'sections list cannot be empty.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Preserve is_required from existing sections
            existing_sections = {sec.key: sec for sec in project.toc_sections.all()}
            
            project.toc_sections.all().delete()
            new_sections = []
            for idx, sec in enumerate(incoming_sections):
                key = sec.get('key', f'custom_{idx}')
                is_req = existing_sections[key].is_required if key in existing_sections else False
                
                # Force is_enabled=True if the section is required
                is_enabled = sec.get('is_enabled', True)
                if is_req:
                    is_enabled = True
                    
                new_sections.append(TOCSection(
                    project=project,
                    key=key,
                    label=sec.get('label', f'Section {idx + 1}'),
                    order=sec.get('order', idx + 1),
                    is_enabled=is_enabled,
                    is_required=is_req,
                    is_custom=sec.get('is_custom', False),
                ))
            TOCSection.objects.bulk_create(new_sections)

        updated = project.toc_sections.all()
        logger.info(f'TOC updated for project {project.id} — {len(new_sections)} sections')
        return Response({
            'sections': TOCSectionSerializer(updated, many=True).data,
            'message': 'Table of Contents updated successfully.',
        })


# ─── Source Connectors (Project Assets) ───────────────────────────────────────

class ProjectAssetSearchView(APIView):
    """
    POST /api/projects/:id/assets/search/
    Performs a web search and adds the result as a 'url' project asset.
    Body: {"query": "Some search query"}
    """
    def post(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error: return error
        
        query = request.data.get('query')
        if not query:
            return Response({'error': 'Search query is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
        # TODO: Integrate with actual web search API (e.g. Tavily/Bing)
        # For now, we mock the search result
        mock_result_url = f"https://example.com/search?q={query.replace(' ', '+')}"
        mock_extracted_text = f"Simulated search results for: {query}. This contains valuable context."
        
        asset = ProjectAsset.objects.create(
            project=project,
            connector_type='url',
            title=f"Web Search: {query}",
            url=mock_result_url,
            extracted_text=mock_extracted_text,
            summary=f"Search results for {query}",
            extraction_status='completed'
        )
        
        logger.info(f'Web search asset created for project {project.id} with query "{query}"')
        return Response(ProjectAssetSerializer(asset).data, status=status.HTTP_201_CREATED)

class ProjectAssetListCreateView(APIView):
    """
    GET  /api/projects/:id/assets/ — List all assets for a project
    POST /api/projects/:id/assets/ — Upload/link a new source connector asset
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        assets = project.assets.all()
        serializer = ProjectAssetSerializer(assets, many=True, context={'request': request})
        return Response({'count': assets.count(), 'assets': serializer.data})

    def post(self, request, pk):
        from .tasks import run_asset_extraction_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        serializer = ProjectAssetCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        asset = serializer.save(project=project, extraction_status='pending')

        # Fire async extraction + summarisation task
        run_asset_extraction_task.delay(str(asset.id))
        logger.info(f'Asset {asset.id} created for project {project.id}, fired extraction task')

        return Response(
            ProjectAssetSerializer(asset, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ProjectAssetToggleView(APIView):
    """
    PATCH /api/projects/:id/assets/:aid/toggle/
    Toggle an asset's is_active flag (ON/OFF context injection).

    Request body: {"is_active": true | false}
    """
    def patch(self, request, pk, aid):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        asset, error = _get_asset_or_404(project, aid)
        if error:
            return error

        serializer = AssetToggleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        asset.is_active = serializer.validated_data['is_active']
        asset.save(update_fields=['is_active', 'updated_at'])

        state = 'ON' if asset.is_active else 'OFF'
        logger.info(f'Asset {asset.id} toggled {state} for project {project.id}')
        return Response({
            'id': str(asset.id),
            'is_active': asset.is_active,
            'message': f'Asset context toggled {state}.',
        })


class ProjectAssetDeleteView(APIView):
    """
    DELETE /api/projects/:id/assets/:aid/
    Permanently delete a project asset and its uploaded file.
    """
    def delete(self, request, pk, aid):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        asset, error = _get_asset_or_404(project, aid)
        if error:
            return error

        # Delete physical file if present
        if asset.file:
            try:
                import os as _os
                if _os.path.exists(asset.file.path):
                    _os.remove(asset.file.path)
            except Exception as e:
                logger.warning(f'Could not delete file for asset {asset.id}: {e}')

        asset.delete()
        logger.info(f'Asset {aid} deleted from project {project.id}')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── AI Chat ──────────────────────────────────────────────────────────────────

class AIChatView(APIView):
    """
    POST /api/projects/:id/chat/
    Send a user message to the AI assistant in the context of a specific document (BRD, Test Cases, Plan, Effort).
    The AI can answer questions, suggest improvements, and explain sections.

    Request body:
    {
      "message": "Can you explain the functional requirement FR-003?",
      "history": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
      ]
    }
    """
    def post(self, request, pk):
        from agents.chat_agent import generate_chat_response

        project, error = _get_project_or_404(pk)
        if error:
            return error

        serializer = ChatMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        document_type = serializer.validated_data.get('document_type', 'brd')
        user_message = serializer.validated_data['message']
        history = serializer.validated_data.get('history', [])

        # Map document_type to agent_type internally
        agent_type_map = {
            'test_cases': 'test_cases',
            'testcases': 'test_cases',
            'plan': 'plan',
            'effort': 'effort',
            'brd': 'brd'
        }
        agent_type = agent_type_map.get(document_type, 'brd')

        # Gather specific document data if available
        document_data = None
        try:
            doc_output = AgentOutput.objects.get(project=project, agent_type=agent_type)
            if doc_output.status == 'complete':
                document_data = doc_output.structured_output
        except AgentOutput.DoesNotExist:
            pass

        try:
            response_data = generate_chat_response(
                project_description=project.extracted_text or '',
                brd_data=document_data,  # Passed as context to the AI
                chat_history=history,
                user_message=user_message,
            )
        except (ValueError, RuntimeError) as e:
            logger.error(f'AI chat failed for project {project.id}: {e}')
            return Response(
                {'error': f'AI chat failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            'role': 'assistant',
            'content': response_data.get('content', ''),
            'proposed_edits': response_data.get('proposed_edits', []),
        })


# ─── Other Agent Outputs ──────────────────────────────────────────────────────

class PlanOutputView(APIView):
    """GET /api/projects/:id/plan/ — Returns Project Plan JSON."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        output, error = _get_agent_output(project, 'plan')
        if error:
            return error
        return Response(AgentOutputSerializer(output).data)


class TestCasesOutputView(APIView):
    """GET /api/projects/:id/testcases/ — Returns Test Cases JSON."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        output, error = _get_agent_output(project, 'test_cases')
        if error:
            return error
        return Response(AgentOutputSerializer(output).data)


class EffortOutputView(APIView):
    """GET /api/projects/:id/effort/ — Returns Effort Estimation JSON."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error
        output, error = _get_agent_output(project, 'effort')
        if error:
            return error
        return Response(AgentOutputSerializer(output).data)


# ─── DOCX Downloads ───────────────────────────────────────────────────────────

class DownloadOutputView(APIView):
    """
    GET /api/projects/:id/download/:type/
    Generate and stream a DOCX file for any output type.
    :type values: brd | plan | testcases | effort
    """

    OUTPUT_TYPE_MAP = {
        'brd': ('brd', 'BRD'),
        'plan': ('plan', 'ProjectPlan'),
        'testcases': ('test_cases', 'TestCases'),
        'effort': ('effort', 'EffortEstimation'),
    }

    def perform_content_negotiation(self, request, force=False):
        from rest_framework.renderers import JSONRenderer
        # Force JSON renderer for any error Responses to bypass 406 Not Acceptable
        # when the client sends a strict DOCX Accept header.
        # Successful execution returns a FileResponse which bypasses DRF rendering entirely.
        return (JSONRenderer(), JSONRenderer().media_type)

    def get(self, request, pk, output_type: str):
        from utils.docx_exporter import (
            export_brd_to_docx,
            export_plan_to_docx,
            export_testcases_to_docx,
            export_effort_to_docx,
        )

        EXPORTERS = {
            'brd': export_brd_to_docx,
            'plan': export_plan_to_docx,
            'testcases': export_testcases_to_docx,
            'effort': export_effort_to_docx,
        }

        if output_type not in self.OUTPUT_TYPE_MAP:
            return Response(
                {'error': f'Invalid output_type: {output_type}. Choose from: brd, plan, testcases, effort'},
                status=status.HTTP_400_BAD_REQUEST
            )

        project, error = _get_project_or_404(pk)
        if error:
            return error

        agent_type, filename_prefix = self.OUTPUT_TYPE_MAP[output_type]
        output, error = _get_agent_output(project, agent_type)
        if error:
            return error

        if output.status != 'complete' or not output.structured_output:
            return Response(
                {'error': f'{output_type} is not ready yet. Status: {output.status}'},
                status=status.HTTP_425_TOO_EARLY
            )

        try:
            exporter = EXPORTERS[output_type]
            buffer = exporter(output.structured_output)

            import re
            source_text = project.name or project.extracted_text or ''
            clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', source_text)
            short_name = '_'.join(clean_text.split()[:4]).capitalize()
            if not short_name:
                short_name = f'Project_{str(project.id)[:8]}'

            filename = f'{short_name}_{filename_prefix}.docx'
            return FileResponse(
                buffer,
                as_attachment=True,
                filename=filename,
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        except Exception as e:
            logger.error(f'DOCX export failed for project {project.id} type {output_type}: {e}')
            return Response(
                {'error': f'DOCX generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# --- Document Chat Edit (Full-Document Update for Plan/TestCases/Effort) ----

class DocumentChatEditView(APIView):
    """
    POST /api/projects/:id/<document_type>/chat-edit/
    Fires a Celery task that rewrites the document based on instruction.
    Returns HTTP 202 immediately with a task_id.
    """
    def post(self, request, pk, document_type):
        from apps.projects.tasks import run_document_chat_edit_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        agent_type_map = {
            'testcases': 'test_cases',
            'test_cases': 'test_cases',
            'plan': 'plan',
            'effort': 'effort'
        }
        agent_type = agent_type_map.get(document_type)
        if not agent_type:
            return Response({'error': 'Invalid document type in URL'}, status=status.HTTP_400_BAD_REQUEST)

        output, error = _get_agent_output(project, agent_type)
        if error:
            return error

        if output.status != 'complete' or not output.structured_output:
            return Response(
                {'error': f'{document_type} is not complete yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DocumentChatEditSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        instruction = serializer.validated_data['instruction']
        auto_save_version = serializer.validated_data.get('auto_save_version', False)

        task = run_document_chat_edit_task.delay(
            project_id=str(project.id),
            document_type=document_type,
            instruction=instruction,
            auto_save_version=auto_save_version,
        )

        logger.info(f'{document_type} chat-edit task queued for project {project.id} � task_id: {task.id}')

        return Response(
            {
                'task_id': task.id,
                'status': 'processing',
                'message': 'Chat edit in progress. Poll the status URL every 3-5 seconds.',
                'poll_url': f'/api/projects/{project.id}/{document_type}/chat-edit/{task.id}/',
            },
            status=status.HTTP_202_ACCEPTED,
        )

class DocumentChatEditStatusView(APIView):
    """
    GET /api/projects/:id/<document_type>/chat-edit/{task_id}/
    Polls the Celery task status.
    """
    def get(self, request, pk, document_type, task_id):
        from celery.result import AsyncResult
        
        project, error = _get_project_or_404(pk)
        if error:
            return error

        result = AsyncResult(task_id)

        if result.state == 'PENDING':
            return Response({'status': 'processing'})
        elif result.state == 'SUCCESS':
            task_result = result.result
            if isinstance(task_result, dict) and task_result.get('status') == 'failed':
                return Response(task_result, status=status.HTTP_400_BAD_REQUEST)
            return Response(task_result, status=status.HTTP_200_OK)
        elif result.state == 'FAILURE':
            return Response(
                {'status': 'failed', 'error': str(result.info)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        else:
            return Response({'status': result.state.lower()})


class ChatAPIView(APIView):
    def post(self, request):
        return Response({'message': 'ChatGPT API connected!'})
    def get(self, request):
        return Response({'message': 'ChatGPT API connected!'})
