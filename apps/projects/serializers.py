from rest_framework import serializers
from .models import Project, AgentOutput


class ProjectCreateSerializer(serializers.ModelSerializer):
    """Used when creating a new project — accepts text input or file upload."""

    class Meta:
        model = Project
        fields = ['id', 'raw_input', 'uploaded_file']
        read_only_fields = ['id']


class ProjectStatusSerializer(serializers.ModelSerializer):
    """Polling response — returns project status and per-agent output statuses."""

    outputs = serializers.SerializerMethodField()

    def get_outputs(self, obj):
        result = {}
        for output in obj.outputs.all():
            result[output.agent_type] = output.status
        return result

    class Meta:
        model = Project
        fields = ['id', 'status', 'brd_approved', 'outputs', 'error_message', 'created_at', 'updated_at']


class ClarificationQuestionsSerializer(serializers.ModelSerializer):
    """Returns the AI-generated clarification questions."""

    class Meta:
        model = Project
        fields = ['id', 'clarification_questions', 'status']


class AnswerQuestionsSerializer(serializers.Serializer):
    """Accepts user answers to clarification questions."""
    answers = serializers.DictField(
        child=serializers.CharField(),
        help_text='Dict mapping question IDs to user answers. Example: {"Q1": "answer", "Q2": "answer"}'
    )


class RevisionSerializer(serializers.Serializer):
    """Accepts revision notes when user requests a BRD revision."""
    revision_notes = serializers.CharField(
        help_text='Specific feedback or changes requested for the BRD revision'
    )


class AgentOutputSerializer(serializers.ModelSerializer):
    """Returns the structured JSON output of any agent."""

    class Meta:
        model = AgentOutput
        fields = ['id', 'agent_type', 'status', 'structured_output', 'error_message', 'updated_at']
