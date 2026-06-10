"""
Database Models for IT Automation SDLC Platform.

Models:
  - Project         Core project record — tracks status through pipeline
  - AgentOutput     AI agent results (one per agent type per project)
  - ProjectAsset    Source connector uploads (7 types) with ON/OFF toggle
  - BRDVersion      Immutable BRD snapshots — version history
  - TOCSection      Custom table of contents configuration per project
"""

import uuid
from django.db import models


class Project(models.Model):
    """Represents a single SDLC project with its full lifecycle state."""

    STATUS_CHOICES = [
        ('new', 'New'),
        ('clarifying', 'Generating Clarification Questions'),
        ('awaiting_answers', 'Awaiting User Answers'),
        ('generating_brd', 'Generating BRD'),
        ('awaiting_approval', 'Awaiting BRD Approval'),
        ('approved', 'BRD Approved — Running Remaining Agents'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]

    APPLICATION_TYPE_CHOICES = [
        ('salesforce', 'Salesforce'),
        ('servicenow', 'ServiceNow'),
        ('sap', 'SAP'),
        ('custom', 'Custom Application'),
    ]

    # ── Identifiers ────────────────────────────────────────────────────────────
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Project Metadata (from Create Project form) ────────────────────────────
    name = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='Short project name e.g. "Customer Portal Redesign"'
    )
    line_of_business = models.CharField(
        max_length=150, blank=True, null=True,
        help_text='Line of business / business unit e.g. "Retail Banking"'
    )
    application_type = models.CharField(
        max_length=50, choices=APPLICATION_TYPE_CHOICES, blank=True, null=True,
        help_text='Category of system being built'
    )
    department = models.CharField(
        max_length=150, blank=True, null=True,
        help_text='Requesting department e.g. "Finance" or "IT Operations"'
    )

    # ── Input Content ──────────────────────────────────────────────────────────
    is_standalone = models.BooleanField(
        default=False,
        help_text='If True, indicates the project is created directly from an external BRD to generate downstream artifacts.'
    )
    raw_input = models.TextField(
        blank=True, null=True,
        help_text='Free text project description from user'
    )
    uploaded_file = models.FileField(
        upload_to='uploads/', blank=True, null=True,
        help_text='Primary project description file (PDF/DOCX/TXT)'
    )
    extracted_text = models.TextField(
        blank=True, null=True,
        help_text='Text extracted from raw_input or uploaded_file'
    )

    # ── Clarification Q&A ──────────────────────────────────────────────────────
    clarification_questions = models.JSONField(
        blank=True, null=True,
        help_text='List of 3-5 clarifying questions from AI'
    )
    clarification_answers = models.JSONField(
        blank=True, null=True,
        help_text='User answers to clarification questions'
    )

    # ── Pipeline State ─────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=50, choices=STATUS_CHOICES, default='new',
        db_index=True
    )
    brd_approved = models.BooleanField(default=False)
    revision_notes = models.TextField(
        blank=True, null=True,
        help_text='User notes when requesting a BRD revision'
    )
    error_message = models.TextField(blank=True, null=True)

    # ── Timestamps ─────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

    def __str__(self) -> str:
        label = self.name or f'Project {str(self.id)[:8]}'
        return f'{label} [{self.status}]'

    def get_active_assets_context(self) -> str:
        """Return combined text of all ON (is_active=True) project assets."""
        active = self.assets.filter(is_active=True).exclude(summary='').exclude(summary=None)
        if not active.exists():
            return ''
        parts = []
        for asset in active:
            connector_label = dict(ProjectAsset.CONNECTOR_TYPE_CHOICES).get(asset.connector_type, asset.connector_type)
            parts.append(f'[{connector_label}] {asset.title or "Untitled"}:\n{asset.summary}')
        return '\n\n---\n\n'.join(parts)


class AgentOutput(models.Model):
    """Stores the output of each AI agent for a given project."""

    AGENT_TYPE_CHOICES = [
        ('clarification', 'Clarification Agent'),
        ('brd', 'BRD Agent'),
        ('plan', 'Project Plan Agent'),
        ('test_cases', 'Test Case Agent'),
        ('effort', 'Effort Estimation Agent'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='outputs')
    agent_type = models.CharField(max_length=20, choices=AGENT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    raw_output = models.TextField(
        blank=True, null=True,
        help_text='Raw AI response — fallback if JSON parsing fails'
    )
    structured_output = models.JSONField(
        blank=True, null=True,
        help_text='Parsed JSON output — what the frontend reads'
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        unique_together = [('project', 'agent_type')]
        verbose_name = 'Agent Output'
        verbose_name_plural = 'Agent Outputs'

    def __str__(self) -> str:
        return f'{self.agent_type} output for {self.project} [{self.status}]'


class ProjectAsset(models.Model):
    """
    Represents a single context source item attached to a project.

    Covers all 7 source connector types. Each asset is independently
    extracted, summarised by AI, and can be toggled ON/OFF without deletion.
    Active assets are automatically injected into agent prompts.
    """

    CONNECTOR_TYPE_CHOICES = [
        ('mom', 'Minutes of Meeting'),
        ('url', 'Reference URL'),
        ('architecture', 'Architecture / Design Diagram'),
        ('document', 'Reference Document'),
        ('chat', 'Chat Export'),
        ('email', 'Email Thread'),
        ('recording', 'Call Recording Transcript'),
    ]

    EXTRACTION_STATUS_CHOICES = [
        ('pending', 'Pending Extraction'),
        ('processing', 'Extracting & Summarising'),
        ('complete', 'Ready'),
        ('failed', 'Extraction Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assets')
    connector_type = models.CharField(max_length=30, choices=CONNECTOR_TYPE_CHOICES)

    # ── Source ─────────────────────────────────────────────────────────────────
    title = models.CharField(
        max_length=255, blank=True, null=True,
        help_text='User-provided label for this asset'
    )
    file = models.FileField(
        upload_to='assets/', blank=True, null=True,
        help_text='Uploaded file (MOM, PDF, DOCX, TXT, image for architecture)'
    )
    url = models.URLField(
        max_length=2048, blank=True, null=True,
        help_text='URL to scrape (used for url connector type)'
    )

    # ── Extracted Content ──────────────────────────────────────────────────────
    extracted_text = models.TextField(
        blank=True, null=True,
        help_text='Full text extracted from the source'
    )
    summary = models.TextField(
        blank=True, null=True,
        help_text='AI-generated concise summary injected into agent prompts'
    )
    extraction_status = models.CharField(
        max_length=20, choices=EXTRACTION_STATUS_CHOICES, default='pending'
    )
    extraction_error = models.TextField(blank=True, null=True)

    # ── Context Toggle ─────────────────────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        help_text='When True, this asset is injected into AI prompts'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Project Asset'
        verbose_name_plural = 'Project Assets'

    def __str__(self) -> str:
        return f'[{self.connector_type}] {self.title or self.url or "Untitled"} → {self.project}'


class BRDVersion(models.Model):
    """
    Immutable snapshot of a BRD at a point in time.

    Created when user clicks "Save Document". Each save increments the
    version number. Users can restore any historical version.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='brd_versions')
    version_number = models.PositiveIntegerField(
        help_text='Monotonically increasing version counter (1, 2, 3, ...)'
    )
    structured_output = models.JSONField(
        help_text='Full BRD JSON at the time of this snapshot'
    )
    notes = models.TextField(
        blank=True,
        help_text='Optional user notes about this version'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = [('project', 'version_number')]
        verbose_name = 'BRD Version'
        verbose_name_plural = 'BRD Versions'

    def __str__(self) -> str:
        return f'BRD v{self.version_number} — {self.project}'


class TestCaseVersion(models.Model):
    """Immutable snapshot of Test Cases at a point in time."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='testcase_versions')
    version_number = models.PositiveIntegerField()
    structured_output = models.JSONField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = [('project', 'version_number')]

    def __str__(self) -> str:
        return f'TestCases v{self.version_number} — {self.project}'


class ProjectPlanVersion(models.Model):
    """Immutable snapshot of a Project Plan at a point in time."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='plan_versions')
    version_number = models.PositiveIntegerField()
    structured_output = models.JSONField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = [('project', 'version_number')]

    def __str__(self) -> str:
        return f'Plan v{self.version_number} — {self.project}'


class TOCSection(models.Model):
    """
    Defines the Table of Contents structure for a project's BRD.

    The default TOC is seeded from the 11 standard BRD sections. Users
    can reorder, hide/show sections, or add fully custom sections.
    """

    # Base required sections for all application types
    BASE_SECTIONS = [
        ('executive_summary', 'Executive Summary', True),
        ('project_scope', 'Project Scope', True),
        ('current_state_analysis', 'Current State Analysis', False),
        ('functional_requirements', 'Functional Requirements', True),
        ('non_functional_requirements', 'Non-Functional Requirements', True),
        ('integration_requirements', 'Integration Requirements', False),
        ('assumptions_and_dependencies', 'Assumptions & Dependencies', True),
        ('risks_and_mitigations', 'Risks & Mitigations', True),
        ('stakeholders', 'Stakeholder Register', True),
        ('project_plan', 'Project Plan', False),
        ('effort_estimation', 'Effort Estimation', False),
        ('sign_off_matrix', 'Sign-off Matrix', True),
    ]

    # Application specific optional sections
    APP_SPECIFIC_SECTIONS = {
        'salesforce': [
            ('object_data_model', 'Object & Data Model', False),
            ('profiles_permissions', 'Profiles & Permissions', False),
            ('automation_logic', 'Automation Logic', False),
        ],
        'jira': [
            ('workflow_scheme_design', 'Workflow Scheme Design', False),
            ('issue_type_hierarchy', 'Issue Type Hierarchy', False),
            ('screen_configuration', 'Screen Configuration', False),
        ],
        'servicenow': [
            ('table_dictionary_design', 'Table & Dictionary Design', False),
            ('catalog_items', 'Catalog Items', False),
            ('client_scripts_ui_policies', 'Client Scripts & UI Policies', False),
        ],
        'sap': [
            ('business_process_master_list', 'Business Process Master List', False),
            ('rICEF_inventory', 'RICEF Inventory', False),
            ('configuration_rationale', 'Configuration Rationale', False),
        ],
        'custom': [
            ('database_schema', 'Database Schema', False),
            ('api_contracts', 'API Contracts', False),
            ('ui_ux_design', 'UI/UX Design', False),
        ]
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='toc_sections')
    key = models.CharField(
        max_length=100,
        help_text='JSON field key for standard sections, or slug for custom sections'
    )
    label = models.CharField(
        max_length=255,
        help_text='Human-readable section title displayed in the document'
    )
    order = models.PositiveIntegerField(
        help_text='Display order — lower numbers appear first'
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text='When False, this section is hidden from the BRD output'
    )
    is_required = models.BooleanField(
        default=False,
        help_text='When True, the user cannot delete or disable this section'
    )
    is_custom = models.BooleanField(
        default=False,
        help_text='True for user-added sections not in the standard list'
    )

    class Meta:
        ordering = ['order']
        unique_together = [('project', 'key')]
        verbose_name = 'TOC Section'
        verbose_name_plural = 'TOC Sections'

    def __str__(self) -> str:
        status = '✓' if self.is_enabled else '✗'
        req = ' [Required]' if self.is_required else ''
        return f'{status} [{self.order}] {self.label}{req} ({self.project})'

    @classmethod
    def seed_default_toc(cls, project: 'Project') -> None:
        """Create the TOC sections tailored to the project's application type."""
        sections_to_create = list(cls.BASE_SECTIONS)
        
        # Append application specific sections if applicable
        if project.application_type and project.application_type in cls.APP_SPECIFIC_SECTIONS:
            sections_to_create.extend(cls.APP_SPECIFIC_SECTIONS[project.application_type])
            
        sections = [
            cls(
                project=project,
                key=key,
                label=label,
                order=idx + 1,
                is_enabled=True,
                is_required=is_req,
                is_custom=False,
            )
            for idx, (key, label, is_req) in enumerate(sections_to_create)
        ]
        cls.objects.bulk_create(sections, ignore_conflicts=True)
