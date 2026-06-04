"""
BRD Automation API Views.

All endpoints the frontend will call.

Endpoint Summary:
  POST   /api/projects/                               Create project
  GET    /api/projects/:id/status/                   Poll project status
  GET    /api/projects/:id/clarification-questions/  Get AI questions
  POST   /api/projects/:id/answer-questions/         Submit answers → fires BRD
  GET    /api/projects/:id/brd/                      Get BRD JSON
  POST   /api/projects/:id/approve-brd/              Approve → fires remaining agents
  POST   /api/projects/:id/revise-brd/               Request revision with notes
  GET    /api/projects/:id/plan/                     Get Project Plan JSON
  GET    /api/projects/:id/testcases/                Get Test Cases JSON
  GET    /api/projects/:id/effort/                   Get Effort Estimation JSON
  GET    /api/projects/:id/download/:type/           Download DOCX
"""

import logging
from django.http import FileResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Project, AgentOutput
from .serializers import (
    ProjectCreateSerializer,
    ProjectStatusSerializer,
    ClarificationQuestionsSerializer,
    AnswerQuestionsSerializer,
    RevisionSerializer,
    AgentOutputSerializer,
)
from utils.file_extractor import extract_text_from_file

logger = logging.getLogger(__name__)


# ─── Helper ──────────────────────────────────────────────────────────────────

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
        output = AgentOutput.objects.get(project=project, agent_type=agent_type)
        return output, None
    except AgentOutput.DoesNotExist:
        return None, Response(
            {'error': f'{agent_type} output not available yet. Check /status/ first.'},
            status=status.HTTP_404_NOT_FOUND
        )


# ─── Views ───────────────────────────────────────────────────────────────────

class ProjectCreateView(APIView):
    """
    POST /api/projects/

    Create a new BRD project. Accepts either:
      - raw_input (text/json): {"raw_input": "Build a customer portal..."}
      - uploaded_file (multipart): file field + optional raw_input

    Automatically extracts text from the file if provided.
    Fires the clarification task immediately after creation.
    Returns the project ID for all subsequent polling.
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        from .tasks import run_clarification_task

        serializer = ProjectCreateSerializer(data=request.data)
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
                    {
                        'error': (
                            'Could not extract text from your uploaded file. '
                            'Please paste your project description as text instead.'
                        )
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )

        # Combine file text + any raw_input (file takes priority, raw_input appended)
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

        # ── Fire clarification task ──────────────────────────────────────────
        run_clarification_task.delay(str(project.id))
        logger.info(f'Created project {project.id}, fired clarification task')

        return Response(
            {
                'id': str(project.id),
                'status': project.status,
                'message': 'Project created. Generating clarification questions...',
            },
            status=status.HTTP_201_CREATED
        )


class ProjectStatusView(APIView):
    """
    GET /api/projects/:id/status/

    Returns current project status and per-agent output statuses.
    Frontend should poll this every 2 seconds.

    Response shape:
    {
      "id": "uuid",
      "status": "awaiting_answers",
      "brd_approved": false,
      "outputs": {
        "clarification": "complete",
        "brd": "pending",
        "plan": "pending",
        "test_cases": "pending",
        "effort": "pending"
      },
      "error_message": null,
      "created_at": "...",
      "updated_at": "..."
    }
    """

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        serializer = ProjectStatusSerializer(project)
        return Response(serializer.data)


class ClarificationQuestionsView(APIView):
    """
    GET /api/projects/:id/clarification-questions/

    Returns the 3-5 clarification questions generated by the AI.
    Only available once status is 'awaiting_answers'.
    """

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        if project.status == 'clarifying':
            return Response(
                {'status': project.status, 'message': 'Clarification questions are being generated. Please wait.'},
                status=status.HTTP_202_ACCEPTED
            )

        if not project.clarification_questions:
            return Response(
                {'error': 'Clarification questions not yet available. Check status first.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({
            'id': str(project.id),
            'status': project.status,
            'questions': project.clarification_questions,
        })


class AnswerQuestionsView(APIView):
    """
    POST /api/projects/:id/answer-questions/

    Submit user answers to the clarification questions.
    Fires the BRD generation task.

    Request body:
    {
      "answers": {
        "Q1": "Our primary users are B2B sales teams...",
        "Q2": "Must integrate with Salesforce CRM...",
        ...
      }
    }
    """

    def post(self, request, pk):
        from .tasks import run_brd_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        if project.status not in ('awaiting_answers',):
            return Response(
                {'error': f'Cannot submit answers in current status: {project.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AnswerQuestionsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        project.clarification_answers = serializer.validated_data['answers']
        project.save(update_fields=['clarification_answers', 'updated_at'])

        # Fire BRD generation task
        run_brd_task.delay(str(project.id))
        logger.info(f'Answers saved for project {project.id}, fired BRD task')

        return Response({
            'id': str(project.id),
            'status': 'generating_brd',
            'message': 'Answers saved. Generating BRD...',
        })


class BRDOutputView(APIView):
    """
    GET /api/projects/:id/brd/

    Returns the full structured BRD JSON once generation is complete.
    """

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        output, error = _get_agent_output(project, 'brd')
        if error:
            return error

        serializer = AgentOutputSerializer(output)
        return Response(serializer.data)


class ApproveBRDView(APIView):
    """
    POST /api/projects/:id/approve-brd/

    Approve the generated BRD. Fires the remaining agents
    (Plan → Test Cases → Effort) as a single Celery task.
    """

    def post(self, request, pk):
        from .tasks import run_remaining_agents_task

        project, error = _get_project_or_404(pk)
        if error:
            return error

        if project.status != 'awaiting_approval':
            return Response(
                {'error': f'BRD can only be approved when status is awaiting_approval. Current: {project.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        project.brd_approved = True
        project.save(update_fields=['brd_approved', 'updated_at'])

        run_remaining_agents_task.delay(str(project.id))
        logger.info(f'BRD approved for project {project.id}, fired remaining agents task')

        return Response({
            'id': str(project.id),
            'status': 'approved',
            'message': 'BRD approved. Generating project plan, test cases, and effort estimation...',
        })


class ReviseBRDView(APIView):
    """
    POST /api/projects/:id/revise-brd/

    Request a BRD revision with specific notes.
    Resets BRD output and re-fires BRD generation.

    Request body:
    {
      "revision_notes": "Please add more detail on the payment integration requirements..."
    }
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

        # Clear existing BRD output
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


class PlanOutputView(APIView):
    """GET /api/projects/:id/plan/ — Returns Project Plan JSON."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        output, error = _get_agent_output(project, 'plan')
        if error:
            return error

        serializer = AgentOutputSerializer(output)
        return Response(serializer.data)


class TestCasesOutputView(APIView):
    """GET /api/projects/:id/testcases/ — Returns Test Cases JSON."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        output, error = _get_agent_output(project, 'test_cases')
        if error:
            return error

        serializer = AgentOutputSerializer(output)
        return Response(serializer.data)


class EffortOutputView(APIView):
    """GET /api/projects/:id/effort/ — Returns Effort Estimation JSON."""

    def get(self, request, pk):
        project, error = _get_project_or_404(pk)
        if error:
            return error

        output, error = _get_agent_output(project, 'effort')
        if error:
            return error

        serializer = AgentOutputSerializer(output)
        return Response(serializer.data)


class DownloadOutputView(APIView):
    """
    GET /api/projects/:id/download/:type/

    Generate and return a DOCX file for any output type.
    :type values: brd | plan | testcases | effort

    Returns file as a streaming attachment download.
    """

    OUTPUT_TYPE_MAP = {
        'brd': ('brd', 'BRD'),
        'plan': ('plan', 'ProjectPlan'),
        'testcases': ('test_cases', 'TestCases'),
        'effort': ('effort', 'EffortEstimation'),
    }

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
            clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', project.extracted_text)
            short_name = '_'.join(clean_text.split()[:4]).capitalize()
            if not short_name:
                short_name = f"Project_{str(project.id)[:4]}"

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
