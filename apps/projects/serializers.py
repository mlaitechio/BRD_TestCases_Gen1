"""
DRF Serializers for all models.

Covers Project lifecycle, AgentOutput, ProjectAsset,
BRDVersion, and TOCSection.
"""

from rest_framework import serializers
from .models import Project, AgentOutput, ProjectAsset, BRDVersion, TOCSection, TestCaseVersion, ProjectPlanVersion


# ─── Project Serializers ───────────────────────────────────────────────────────

class ProjectCreateSerializer(serializers.ModelSerializer):
    """Used when creating a new project — accepts metadata + text input or file upload."""

    application_type = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'line_of_business', 'application_type',
            'department', 'raw_input', 'uploaded_file',
        ]
        read_only_fields = ['id']

    def validate_application_type(self, value):
        if not value:
            return value

        choices = {key: label for key, label in Project.APPLICATION_TYPE_CHOICES}
        labels_to_keys = {label.lower(): key for key, label in Project.APPLICATION_TYPE_CHOICES}
        normalized_value = value.strip()

        if normalized_value in choices:
            return normalized_value

        lookup_key = labels_to_keys.get(normalized_value.lower())
        if lookup_key:
            return lookup_key

        raise serializers.ValidationError(
            f'"{value}" is not a valid choice.'
        )


class ProjectListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing all projects on the dashboard."""

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'line_of_business', 'application_type',
            'department', 'status', 'brd_approved', 'created_at', 'updated_at',
        ]


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
        fields = [
            'id', 'name', 'status', 'brd_approved',
            'outputs', 'error_message', 'created_at', 'updated_at',
        ]


class ProjectDetailSerializer(serializers.ModelSerializer):
    """Full project details including metadata."""

    outputs = serializers.SerializerMethodField()

    def get_outputs(self, obj):
        result = {}
        for output in obj.outputs.all():
            result[output.agent_type] = output.status
        return result

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'line_of_business', 'application_type', 'department',
            'status', 'brd_approved', 'revision_notes', 'error_message',
            'outputs', 'created_at', 'updated_at',
        ]


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


# ─── Agent Output ──────────────────────────────────────────────────────────────

class AgentOutputSerializer(serializers.ModelSerializer):
    """Returns the structured JSON output of any agent."""

    class Meta:
        model = AgentOutput
        fields = ['id', 'agent_type', 'status', 'structured_output', 'error_message', 'updated_at']


# ─── Project Assets (Source Connectors) ───────────────────────────────────────

class ProjectAssetSerializer(serializers.ModelSerializer):
    """Full asset detail including extraction status and summary."""

    connector_type_display = serializers.CharField(
        source='get_connector_type_display', read_only=True
    )
    extraction_status_display = serializers.CharField(
        source='get_extraction_status_display', read_only=True
    )

    class Meta:
        model = ProjectAsset
        fields = [
            'id', 'connector_type', 'connector_type_display', 'title',
            'file', 'url', 'summary', 'extraction_status',
            'extraction_status_display', 'extraction_error',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'summary', 'extraction_status', 'extraction_status_display',
            'extraction_error', 'created_at', 'updated_at',
        ]


class ProjectAssetCreateSerializer(serializers.ModelSerializer):
    """Used when uploading/linking a new asset via a source connector."""

    text_content = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ProjectAsset
        fields = ['id', 'connector_type', 'title', 'file', 'url', 'text_content']
        read_only_fields = ['id']
        extra_kwargs = {
            'connector_type': {'required': False},
            'title': {'required': False},
        }

    def to_internal_value(self, data):
        """Map frontend connector_type labels to valid choices BEFORE validation."""
        if 'connector_type' in data:
            connector_type_map = {
                'mails': 'email',
                'emails': 'email',
                'documents': 'document',
                'chats': 'chat',
            }
            data['connector_type'] = connector_type_map.get(data['connector_type'], data['connector_type'])

        return super().to_internal_value(data)

    def validate(self, data):
        from django.core.files.base import ContentFile

        connector_type = data.get('connector_type', 'document')
        file = data.get('file')
        url = data.get('url')
        title = data.get('title')
        text_content = data.get('text_content', '')

        # Map frontend labels to valid connector types
        connector_type_map = {
            'mails': 'email',
            'emails': 'email',
            'document': 'document',
            'documents': 'document',
            'chats': 'chat',
        }

        if connector_type in connector_type_map:
            connector_type = connector_type_map[connector_type]
            data['connector_type'] = connector_type

        # Auto-set connector type to 'document' if not provided
        if not connector_type:
            data['connector_type'] = 'document'
            connector_type = 'document'

        # Auto-set title from filename if not provided
        if not title and file:
            data['title'] = file.name
            title = file.name

        # Handle pasted text content (create virtual file for chat type)
        if connector_type == 'chat' and text_content and not file:
            filename = title or 'pasted_chat.txt'
            file = ContentFile(text_content.encode('utf-8'), name=filename)
            data['file'] = file

        if connector_type == 'url':
            if not url:
                raise serializers.ValidationError(
                    {'url': 'A URL is required for the "url" connector type.'}
                )
        else:
            if not file:
                raise serializers.ValidationError(
                    {'file': f'A file upload is required for the "{connector_type}" connector type.'}
                )
        return data


class AssetToggleSerializer(serializers.Serializer):
    """Toggle a single asset's is_active flag."""
    is_active = serializers.BooleanField()


# ─── BRD Versions ─────────────────────────────────────────────────────────────

class BRDVersionListSerializer(serializers.ModelSerializer):
    """Lightweight list — does not include full structured_output JSON."""

    class Meta:
        model = BRDVersion
        fields = ['id', 'version_number', 'notes', 'created_at']


class BRDVersionDetailSerializer(serializers.ModelSerializer):
    """Full version detail including the complete BRD JSON snapshot."""

    class Meta:
        model = BRDVersion
        fields = ['id', 'version_number', 'structured_output', 'notes', 'created_at']


class SaveVersionSerializer(serializers.Serializer):
    """Used when user clicks 'Save Document' for test cases or project plan."""
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class TestCaseVersionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCaseVersion
        fields = ['id', 'version_number', 'notes', 'created_at']

class TestCaseVersionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCaseVersion
        fields = ['id', 'version_number', 'structured_output', 'notes', 'created_at']


class ProjectPlanVersionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlanVersion
        fields = ['id', 'version_number', 'notes', 'created_at']

class ProjectPlanVersionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlanVersion
        fields = ['id', 'version_number', 'structured_output', 'notes', 'created_at']


# ─── TOC Sections ─────────────────────────────────────────────────────────────

class TOCSectionSerializer(serializers.ModelSerializer):
    """Full TOC section — used for both GET and PUT."""

    class Meta:
        model = TOCSection
        fields = ['id', 'key', 'label', 'order', 'is_enabled', 'is_required', 'is_custom']
        read_only_fields = ['id', 'is_required']


class TOCSaveSerializer(serializers.Serializer):
    """
    Used for PUT /toc/ — accepts the full array of TOC sections in desired order.
    The frontend sends the entire section list; we replace the project's TOC entirely.
    """
    sections = serializers.ListField(
        child=serializers.DictField(),
        help_text='Full ordered list of TOC sections'
    )


# ─── AI Chat ──────────────────────────────────────────────────────────────────

class ChatMessageSerializer(serializers.Serializer):
    """Used for POST /chat/ — user sends a message, gets AI response."""
    document_type = serializers.ChoiceField(
        choices=['brd', 'test_cases', 'plan', 'effort'],
        default='brd',
        help_text='Which document context to chat about'
    )
    message = serializers.CharField(
        help_text='User message to the AI assistant'
    )
    history = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        default=list,
        help_text='Previous conversation turns: [{"role": "user"|"assistant", "content": "..."}]'
    )


# ─── AI Section Edit ──────────────────────────────────────────────────────────

class SectionEditSerializer(serializers.Serializer):
    """Used for PATCH /brd/edit-section/ — AI rewrites a specific BRD section."""
    section_key = serializers.CharField(
        help_text='JSON field key of the BRD section to edit e.g. "executive_summary"'
    )
    instructions = serializers.CharField(
        help_text='Natural language instructions for how to change this section'
    )


# ─── BRD Chat Edit (Full-Document Update from Chat) ───────────────────────────

class DocumentChatEditSerializer(serializers.Serializer):
    """
    Used for POST /brd/chat-edit/

    User types a single instruction in the chat box; the AI identifies
    which sections are affected and rewrites them — entire BRD updates automatically.

    Example:
      {"instruction": "Add GDPR compliance requirements to all relevant sections"}
      {"instruction": "Make the executive summary shorter and more business-focused"}
      {"instruction": "Add mobile app support requirements throughout the document"}
    """
    instruction = serializers.CharField(
        help_text='Natural language instruction for updating the document.'
    )
    auto_save_version = serializers.BooleanField(
        default=False,
        required=False,
        help_text='If true, automatically saves a BRD version snapshot before applying changes.'
    )
