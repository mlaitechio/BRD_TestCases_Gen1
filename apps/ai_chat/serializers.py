"""
AI Chat Serializers - Convert models to JSON
"""

from rest_framework import serializers
from .models import ChatConversation, ChatMessage, ChatSessionLog


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serialize individual chat messages"""

    file_url = serializers.SerializerMethodField()
    created_at_display = serializers.DateTimeField(source='created_at', format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            'id', 'role', 'content', 'tokens_used', 'file', 'file_url', 'file_type',
            'file_size_bytes', 'is_streaming_complete', 'error_message', 'created_at',
            'created_at_display', 'updated_at'
        ]
        read_only_fields = ['id', 'tokens_used', 'file_size_bytes', 'created_at', 'updated_at']

    def get_file_url(self, obj):
        """Generate file URL if file exists"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class ChatConversationListSerializer(serializers.ModelSerializer):
    """Serialize conversation for list view"""

    latest_message = serializers.SerializerMethodField()
    created_at_display = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'is_active', 'message_count', 'total_tokens_used',
            'latest_message', 'created_at', 'created_at_display', 'updated_at'
        ]

    def get_latest_message(self, obj):
        """Get preview of latest message"""
        latest = obj.messages.last()
        if latest:
            preview = latest.content[:100] + '...' if len(latest.content) > 100 else latest.content
            return {
                'role': latest.role,
                'preview': preview,
                'created_at': latest.created_at
            }
        return None


class ChatConversationDetailSerializer(serializers.ModelSerializer):
    """Serialize conversation with full message history"""

    messages = ChatMessageSerializer(many=True, read_only=True)
    created_at_display = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'is_active', 'model_used', 'message_count', 'total_tokens_used',
            'messages', 'created_at', 'created_at_display', 'updated_at'
        ]
        read_only_fields = ['id', 'message_count', 'total_tokens_used', 'created_at', 'updated_at']


class ChatMessageCreateSerializer(serializers.ModelSerializer):
    """Serialize message creation (user sending message)"""

    class Meta:
        model = ChatMessage
        fields = ['content', 'file', 'file_type']

    def validate_content(self, value):
        """Validate message content is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError('Message content cannot be empty')
        return value.strip()


class ChatSessionLogSerializer(serializers.ModelSerializer):
    """Serialize session logs for auditing"""

    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = ChatSessionLog
        fields = [
            'id', 'event_type', 'event_type_display', 'details', 'error_message',
            'response_time_ms', 'tokens_used', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
