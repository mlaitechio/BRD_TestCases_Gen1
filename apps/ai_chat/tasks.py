"""
AI Chat Async Tasks - Background processing with worker threads for concurrent request handling
"""
from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
import logging
from uuid import UUID

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def generate_ai_response_async(self, conversation_id, user_id, user_message, history=None):
    """
    Generate AI response asynchronously using Celery workers.
    This allows multiple concurrent requests without blocking.

    Args:
        conversation_id: UUID of the conversation
        user_id: ID of the user
        user_message: The user's message
        history: Conversation history (list of dicts)

    Returns:
        Dict with response_text and tokens_used
    """
    try:
        from .models import ChatConversation, ChatMessage, ChatSessionLog
        from .services import get_ai_service

        conversation = ChatConversation.objects.get(id=UUID(conversation_id))
        user = User.objects.get(id=user_id)
        ai_service = get_ai_service()

        # Call Azure OpenAI API (non-blocking in worker process)
        response_text, tokens_used = ai_service.get_response(
            user_message,
            history or []
        )

        # Save assistant message
        assistant_msg = ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=response_text,
            tokens_used=tokens_used,
            is_streaming_complete=True
        )

        # Update conversation metadata
        conversation.message_count = conversation.messages.count()
        conversation.total_tokens_used += tokens_used
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['message_count', 'total_tokens_used', 'last_message_at'])

        # Log session event
        ChatSessionLog.objects.create(
            conversation=conversation,
            user=user,
            event_type='response_received',
            tokens_used=tokens_used
        )

        logger.info(f'[AIChat] Worker: Generated response with {tokens_used} tokens')
        return {
            'response_text': response_text,
            'tokens_used': tokens_used,
            'message_id': str(assistant_msg.id)
        }

    except Exception as exc:
        logger.error(f'[AIChat] Worker error: {exc}')
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@shared_task(bind=True, max_retries=3)
def stream_ai_response_async(self, conversation_id, user_id, user_message, history=None):
    """
    Stream AI response chunks asynchronously.
    For compatibility with streaming clients.

    Args:
        conversation_id: UUID of the conversation
        user_id: ID of the user
        user_message: The user's message
        history: Conversation history (list of dicts)

    Returns:
        Dict with full_response and tokens_used
    """
    try:
        from .models import ChatConversation, ChatMessage, ChatSessionLog
        from .services import get_ai_service

        conversation = ChatConversation.objects.get(id=UUID(conversation_id))
        user = User.objects.get(id=user_id)
        ai_service = get_ai_service()

        # Stream response from OpenAI (runs in worker, not blocking main process)
        full_response = ''
        for chunk in ai_service.stream_response(user_message, history or []):
            full_response += chunk

        # Save assistant message after streaming completes
        assistant_msg = ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=full_response,
            is_streaming_complete=True
        )

        # Update conversation metadata
        conversation.message_count = conversation.messages.count()
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['message_count', 'last_message_at'])

        # Log session event
        ChatSessionLog.objects.create(
            conversation=conversation,
            user=user,
            event_type='streaming_ended'
        )

        logger.info(f'[AIChat] Worker: Streaming completed, {len(full_response)} chars')
        return {
            'response_text': full_response,
            'message_id': str(assistant_msg.id)
        }

    except Exception as exc:
        logger.error(f'[AIChat] Worker streaming error: {exc}')
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@shared_task(bind=True, max_retries=3)
def summarize_text_async(self, text, max_length=500):
    """
    Summarize text asynchronously using worker.

    Args:
        text: Text to summarize
        max_length: Max length of summary

    Returns:
        Dict with summary and tokens_used
    """
    try:
        from .services import get_ai_service

        ai_service = get_ai_service()
        summary, tokens_used = ai_service.summarize_text(text, max_length)

        logger.info(f'[AIChat] Worker: Text summarized, {tokens_used} tokens')
        return {
            'summary': summary,
            'tokens_used': tokens_used,
            'original_length': len(text),
            'summary_length': len(summary)
        }

    except Exception as exc:
        logger.error(f'[AIChat] Worker summarization error: {exc}')
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@shared_task(bind=True, max_retries=3)
def generate_code_async(self, requirement, language='python'):
    """
    Generate code asynchronously using worker.

    Args:
        requirement: What code should do
        language: Programming language

    Returns:
        Dict with code and tokens_used
    """
    try:
        from .services import get_ai_service

        ai_service = get_ai_service()
        code, tokens_used = ai_service.generate_code(requirement, language)

        logger.info(f'[AIChat] Worker: Code generated, {tokens_used} tokens')
        return {
            'code': code,
            'language': language,
            'tokens_used': tokens_used
        }

    except Exception as exc:
        logger.error(f'[AIChat] Worker code generation error: {exc}')
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@shared_task
def save_chat_response_async(conversation_id, user_id, response_text, tokens_used):
    """
    Save AI response to database asynchronously (doesn't block API response)
    Kept for backward compatibility
    """
    try:
        from .models import ChatConversation, ChatMessage, ChatSessionLog

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
