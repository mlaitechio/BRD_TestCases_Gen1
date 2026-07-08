"""
AI Chat Models - Store conversations and messages
"""

import os
import uuid
from django.db import models
from django.contrib.auth.models import User


def get_default_model():
    """Get default model from environment variable"""
    return os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5.5')


class ChatConversation(models.Model):
    """
    Stores individual chat conversations.
    Each conversation is a separate thread with its own message history.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # User & Metadata
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_conversations')
    title = models.CharField(max_length=255, blank=True, help_text='Conversation title (auto-generated or user-set)')

    # Status & Settings
    is_active = models.BooleanField(default=True, help_text='Whether conversation is archived or active')
    model_used = models.CharField(
        max_length=100,
        default=get_default_model,
        help_text='Azure OpenAI model used (gpt-5.5, gpt-4o, etc)'
    )

    # Tracking
    total_tokens_used = models.PositiveIntegerField(default=0, help_text='Total tokens used in this conversation')
    message_count = models.PositiveIntegerField(default=0, help_text='Number of messages in conversation')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_message_at', '-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f'{self.title or "Untitled"} ({self.user.username})'


class ChatMessage(models.Model):
    """
    Stores individual messages within a conversation.
    Each message includes role (user/assistant), content, and metadata.
    """

    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    # Message Content
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, help_text='Who sent the message')
    content = models.TextField(help_text='Message content/text')

    # Token Tracking
    tokens_used = models.PositiveIntegerField(default=0, help_text='Tokens used for this message')

    # File Attachments
    file = models.FileField(
        upload_to='ai_chat/attachments/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text='Optional file attachment'
    )
    file_type = models.CharField(
        max_length=20,
        blank=True,
        help_text='File type: pdf, txt, code, image, etc'
    )
    file_size_bytes = models.PositiveIntegerField(null=True, blank=True)

    # Metadata
    is_streaming_complete = models.BooleanField(default=True, help_text='Whether streaming response completed')
    error_message = models.TextField(blank=True, help_text='Error message if request failed')

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['role']),
        ]

    def save(self, *args, **kwargs):
        """Auto-populate file metadata"""
        if self.file:
            self.file_size_bytes = self.file.size
        super().save(*args, **kwargs)

    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f'[{self.role}] {preview}'


class ChatSessionLog(models.Model):
    """
    Audit log for chat sessions - tracks usage patterns and errors.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Session Info
    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='session_logs'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_session_logs')

    # Event Tracking
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('message_sent', 'Message Sent'),
            ('response_received', 'Response Received'),
            ('streaming_started', 'Streaming Started'),
            ('streaming_ended', 'Streaming Ended'),
            ('file_uploaded', 'File Uploaded'),
            ('error_occurred', 'Error Occurred'),
        ]
    )
    details = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    # Metrics
    response_time_ms = models.PositiveIntegerField(null=True, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['event_type']),
        ]

    def __str__(self):
        return f'{self.event_type} - {self.user.username} ({self.created_at})'
