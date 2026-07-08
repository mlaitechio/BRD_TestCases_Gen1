"""
AI Chat Admin Interface
"""

from django.contrib import admin
from .models import ChatConversation, ChatMessage, ChatSessionLog


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    """Admin interface for chat conversations"""

    list_display = ['title', 'user', 'message_count', 'total_tokens_used', 'is_active', 'updated_at']
    list_filter = ['is_active', 'created_at', 'user']
    search_fields = ['title', 'user__username']
    readonly_fields = ['id', 'message_count', 'total_tokens_used', 'created_at', 'updated_at']

    fieldsets = (
        ('Conversation Info', {
            'fields': ('id', 'user', 'title', 'model_used')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Metrics', {
            'fields': ('message_count', 'total_tokens_used')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_message_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin interface for chat messages"""

    list_display = ['conversation', 'role', 'content_preview', 'tokens_used', 'created_at']
    list_filter = ['role', 'created_at', 'conversation__user']
    search_fields = ['conversation__title', 'content']
    readonly_fields = ['id', 'tokens_used', 'file_size_bytes', 'created_at', 'updated_at']

    fieldsets = (
        ('Message Info', {
            'fields': ('id', 'conversation', 'role', 'content')
        }),
        ('File Attachment', {
            'fields': ('file', 'file_type', 'file_size_bytes'),
            'classes': ('collapse',)
        }),
        ('Metrics', {
            'fields': ('tokens_used',)
        }),
        ('Status', {
            'fields': ('is_streaming_complete', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def content_preview(self, obj):
        """Show preview of message content"""
        preview = obj.content[:100] + '...' if len(obj.content) > 100 else obj.content
        return preview
    content_preview.short_description = 'Content'


@admin.register(ChatSessionLog)
class ChatSessionLogAdmin(admin.ModelAdmin):
    """Admin interface for session logs"""

    list_display = ['conversation', 'event_type', 'response_time_ms', 'tokens_used', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['conversation__title', 'error_message']
    readonly_fields = ['id', 'created_at']

    fieldsets = (
        ('Session Info', {
            'fields': ('id', 'conversation', 'user', 'event_type')
        }),
        ('Details', {
            'fields': ('details', 'error_message')
        }),
        ('Metrics', {
            'fields': ('response_time_ms', 'tokens_used')
        }),
        ('Timestamp', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
