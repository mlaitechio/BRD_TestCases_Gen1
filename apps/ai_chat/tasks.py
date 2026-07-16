"""
AI Chat Async Tasks - Background processing
"""
from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def save_chat_response_async(conversation_id, user_id, response_text, tokens_used):
    """
    Save AI response to database asynchronously (doesn't block API response)
    """
    try:
        from .models import ChatConversation, ChatMessage, ChatSessionLog
        from uuid import UUID

        conversation = ChatConversation.objects.get(id=UUID(conversation_id))
        user = User.objects.get(id=user_id)

        # Save assistant message
        assistant_msg = ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=response_text,
            tokens_used=tokens_used,
            is_streaming_complete=True
        )

        # Update conversation
        conversation.message_count = conversation.messages.count()
        conversation.total_tokens_used += tokens_used
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['message_count', 'total_tokens_used', 'last_message_at'])

        # Log event
        ChatSessionLog.objects.create(
            conversation=conversation,
            user=user,
            event_type='response_received',
            tokens_used=tokens_used
        )

        logger.info(f'[AIChat] Background: Response saved, {tokens_used} tokens')

    except Exception as e:
        logger.error(f'[AIChat] Background save error: {e}')
