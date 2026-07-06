"""
RAG Django Admin Configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from .models import RAGDocument, RAGIndexingLog


@admin.register(RAGDocument)
class RAGDocumentAdmin(admin.ModelAdmin):
    """Admin interface for RAG Documents"""

    list_display = [
        'title', 'source_badge', 'status_badge', 'file_type',
        'chunk_count', 'category', 'indexed_at', 'created_at'
    ]

    def save_model(self, request, obj, form, change):
        """Auto-set file_size_bytes and trigger indexing"""
        if obj.file and not obj.file_size_bytes:
            obj.file_size_bytes = obj.file.size
        if obj.file and not obj.file_type:
            ext = obj.file.name.split('.')[-1].lower()
            # Map extensions to file_type field
            ext_map = {
                'pdf': 'pdf',
                'docx': 'docx',
                'txt': 'txt',
                'xlsx': 'xlsx',
                'xls': 'xls',
                'csv': 'csv'
            }
            obj.file_type = ext_map.get(ext, 'txt')
        super().save_model(request, obj, form, change)

        # Trigger async indexing
        if obj.status == 'pending':
            from apps.rag.tasks import run_rag_document_indexing_task
            run_rag_document_indexing_task.delay(str(obj.id))
    list_filter = ['status', 'source', 'file_type', 'category', 'created_at']
    search_fields = ['title', 'description', 'category', 'tags']
    readonly_fields = [
        'id', 'file_size_bytes', 'chunk_count', 'indexed_at',
        'created_at', 'updated_at', 'error_message'
    ]

    fieldsets = (
        ('Document Info', {
            'fields': ('id', 'title', 'description', 'file', 'file_type', 'file_size_bytes')
        }),
        ('Metadata', {
            'fields': ('source', 'category', 'tags', 'created_by')
        }),
        ('Indexing Status', {
            'fields': ('status', 'chunk_count', 'indexed_at', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def source_badge(self, obj):
        """Display source as colored badge"""
        colors = {
            'admin': '#2196F3',
            'insight_attachment': '#4CAF50',
        }
        color = colors.get(obj.source, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_source_display()
        )
    source_badge.short_description = 'Source'

    def status_badge(self, obj):
        """Display status as colored badge"""
        colors = {
            'pending': '#FFC107',
            'indexing': '#2196F3',
            'indexed': '#4CAF50',
            'failed': '#F44336',
        }
        color = colors.get(obj.status, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(RAGIndexingLog)
class RAGIndexingLogAdmin(admin.ModelAdmin):
    """Admin interface for RAG Indexing Logs"""

    list_display = [
        'document_title', 'operation', 'status_badge', 'chunks_created',
        'duration_seconds', 'created_at'
    ]
    list_filter = ['operation', 'status', 'created_at']
    search_fields = ['document__title', 'error_message']
    readonly_fields = [
        'id', 'document', 'operation', 'status', 'chunks_created',
        'error_message', 'duration_seconds', 'created_at'
    ]

    fieldsets = (
        ('Operation', {
            'fields': ('id', 'document', 'operation', 'status')
        }),
        ('Details', {
            'fields': ('chunks_created', 'duration_seconds', 'error_message')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def document_title(self, obj):
        """Display document title"""
        return obj.document.title
    document_title.short_description = 'Document'

    def status_badge(self, obj):
        """Display status as colored badge"""
        color = '#4CAF50' if obj.status == 'success' else '#F44336'
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
