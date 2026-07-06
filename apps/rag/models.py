"""
RAG Document Models - Track documents in the Global Knowledge Base
"""

import uuid
from django.db import models


class RAGDocument(models.Model):
    """
    Tracks documents indexed into the Global RAG Knowledge Base.

    Supports both:
    - Admin-uploaded documents (via API)
    - User-uploaded Insight Attachments
    """

    SOURCE_CHOICES = [
        ('admin', 'Admin Upload'),
        ('insight_attachment', 'Insight Attachment'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Indexing'),
        ('indexing', 'Indexing in Progress'),
        ('indexed', 'Indexed'),
        ('failed', 'Indexing Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Document metadata
    title = models.CharField(max_length=255, help_text='Document title/name')
    description = models.TextField(blank=True, help_text='Document description')
    source = models.CharField(
        max_length=50,
        choices=SOURCE_CHOICES,
        default='admin',
        help_text='Whether doc is from admin or user upload'
    )

    # File handling
    file = models.FileField(
        upload_to='rag_documents/%Y/%m/%d/',
        help_text='Uploaded document file'
    )
    file_type = models.CharField(
        max_length=10,
        choices=[
            ('pdf', 'PDF'),
            ('docx', 'DOCX'),
            ('txt', 'Text'),
            ('xlsx', 'Excel'),
            ('xls', 'Excel 97-2003'),
            ('csv', 'CSV'),
        ],
        help_text='File type/extension'
    )
    file_size_bytes = models.PositiveIntegerField(help_text='File size in bytes')

    # RAG Indexing metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text='Indexing status'
    )
    chunk_count = models.PositiveIntegerField(
        default=0,
        help_text='Number of chunks created during indexing'
    )
    indexed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the document was indexed'
    )
    error_message = models.TextField(
        blank=True,
        help_text='Error message if indexing failed'
    )

    # Metadata for search filtering
    category = models.CharField(
        max_length=100,
        blank=True,
        help_text='Document category (e.g., Salesforce, ServiceNow, General)'
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text='Comma-separated tags for filtering'
    )

    # Tracking
    created_by = models.CharField(
        max_length=255,
        blank=True,
        help_text='Username or email of uploader'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'RAG Document'
        verbose_name_plural = 'RAG Documents'
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['source']),
        ]

    def save(self, *args, **kwargs):
        """Auto-populate file_size_bytes when file is uploaded"""
        if self.file:
            self.file_size_bytes = self.file.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} ({self.get_status_display()})'


class RAGIndexingLog(models.Model):
    """
    Audit log for RAG indexing operations.
    Tracks all indexing attempts, successes, and failures.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        RAGDocument,
        on_delete=models.CASCADE,
        related_name='indexing_logs'
    )

    operation = models.CharField(
        max_length=50,
        choices=[
            ('index', 'Index'),
            ('reindex', 'Re-index'),
            ('delete', 'Delete'),
        ]
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('success', 'Success'),
            ('failed', 'Failed'),
        ]
    )

    chunks_created = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'RAG Indexing Log'
        verbose_name_plural = 'RAG Indexing Logs'

    def __str__(self):
        return f'{self.document.title} - {self.get_operation_display()} - {self.get_status_display()}'
