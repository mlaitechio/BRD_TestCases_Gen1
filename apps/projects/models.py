import uuid
from django.db import models


class Project(models.Model):
    """Represents a single BRD generation request from a user."""

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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    raw_input = models.TextField(blank=True, null=True, help_text='Free text project description from user')
    uploaded_file = models.FileField(upload_to='uploads/', blank=True, null=True, help_text='Uploaded PDF/DOCX/TXT file')
    extracted_text = models.TextField(blank=True, null=True, help_text='Text extracted from raw_input or uploaded_file')
    clarification_questions = models.JSONField(blank=True, null=True, help_text='List of 3-5 clarifying questions from AI')
    clarification_answers = models.JSONField(blank=True, null=True, help_text='User answers to clarification questions')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='new')
    brd_approved = models.BooleanField(default=False)
    revision_notes = models.TextField(blank=True, null=True, help_text='User notes when requesting a BRD revision')
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Project {self.id} [{self.status}]'


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
    raw_output = models.TextField(blank=True, null=True, help_text='Raw AI response — fallback if JSON parsing fails')
    structured_output = models.JSONField(blank=True, null=True, help_text='Parsed JSON output — what the frontend reads')
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        unique_together = [('project', 'agent_type')]

    def __str__(self):
        return f'{self.agent_type} output for Project {self.project_id} [{self.status}]'
