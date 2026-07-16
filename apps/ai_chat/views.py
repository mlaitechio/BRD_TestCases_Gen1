"""
AI Chat API Views - Endpoints for chat, conversation management, and streaming
"""

import logging
from django.http import StreamingHttpResponse, JsonResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ChatConversation, ChatMessage, ChatSessionLog, ChatSession
from .serializers import (
    ChatConversationListSerializer,
    ChatConversationDetailSerializer,
    ChatMessageCreateSerializer,
    ChatMessageSerializer,
)
from .services import get_ai_service

logger = logging.getLogger(__name__)


class ChatConversationListCreateView(APIView):
    """
    GET  /api/chat/conversations/?sessionid=xxx  - List all conversations for session
    POST /api/chat/conversations/                - Create new conversation
    """

    def _get_session(self, sessionid):
        """Get session from sessionid"""
        try:
            return ChatSession.objects.get(sessionid=sessionid)
        except ChatSession.DoesNotExist:
            return None

    def get(self, request):
        """List user's conversations for a session"""
        from django.contrib.auth.models import User

        sessionid = request.query_params.get('sessionid') or request.data.get('sessionid')

        if not sessionid:
            return Response({'error': 'sessionid is required'}, status=status.HTTP_400_BAD_REQUEST)

        session = self._get_session(sessionid)
        if not session:
            return Response({'error': 'Invalid session'}, status=status.HTTP_404_NOT_FOUND)

        conversations = ChatConversation.objects.filter(session=session, is_active=True)
        serializer = ChatConversationListSerializer(conversations, many=True)
        return Response({
            'count': conversations.count(),
            'sessionid': sessionid,
            'conversations': serializer.data
        })

    def post(self, request):
        """Create new conversation for a session"""
        sessionid = request.data.get('sessionid')
        title = request.data.get('title', 'New Conversation')

        if not sessionid:
            return Response({'error': 'sessionid is required'}, status=status.HTTP_400_BAD_REQUEST)

        session = self._get_session(sessionid)
        if not session:
            return Response({'error': 'Invalid session'}, status=status.HTTP_404_NOT_FOUND)

        conversation = ChatConversation.objects.create(
            session=session,
            user=session.user,
            title=title
        )

        logger.info(f'[AIChat] Created conversation {conversation.id} for session {sessionid}')

        serializer = ChatConversationDetailSerializer(conversation, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChatConversationDetailView(APIView):
    """
    GET    /api/chat/conversations/{id}/?sessionid=xxx  - Get conversation with history
    DELETE /api/chat/conversations/{id}/?sessionid=xxx  - Archive/delete conversation
    """

    def _get_session(self, sessionid):
        """Get session from sessionid"""
        try:
            return ChatSession.objects.get(sessionid=sessionid)
        except ChatSession.DoesNotExist:
            return None

    def get_conversation(self, conversation_id, session):
        """Get conversation and check ownership"""
        try:
            return ChatConversation.objects.get(id=conversation_id, session=session)
        except ChatConversation.DoesNotExist:
            return None

    def get(self, request, conversation_id):
        """Get conversation details with message history"""
        sessionid = request.query_params.get('sessionid')
        if not sessionid:
            return Response({'error': 'sessionid is required'}, status=status.HTTP_400_BAD_REQUEST)

        session = self._get_session(sessionid)
        if not session:
            return Response({'error': 'Invalid session'}, status=status.HTTP_404_NOT_FOUND)

        conversation = self.get_conversation(conversation_id, session)
        if not conversation:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ChatConversationDetailSerializer(conversation, context={'request': request})
        return Response(serializer.data)

    def delete(self, request, conversation_id):
        """Archive conversation (soft delete)"""
        sessionid = request.query_params.get('sessionid')
        if not sessionid:
            return Response({'error': 'sessionid is required'}, status=status.HTTP_400_BAD_REQUEST)

        session = self._get_session(sessionid)
        if not session:
            return Response({'error': 'Invalid session'}, status=status.HTTP_404_NOT_FOUND)

        conversation = self.get_conversation(conversation_id, session)
        if not conversation:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)

        conversation.is_active = False
        conversation.save()

        logger.info(f'[AIChat] Archived conversation {conversation_id}')
        return Response({'deleted': True, 'id': conversation_id})


class ChatMessageSendView(APIView):
    """
    POST /api/chat/conversations/{id}/messages/?sessionid=xxx  - Send message and get response
    """

    def _get_session(self, sessionid):
        """Get session from sessionid"""
        try:
            return ChatSession.objects.get(sessionid=sessionid)
        except ChatSession.DoesNotExist:
            return None

    def post(self, request, conversation_id):
        """
        Send message to conversation and get AI response.
        Supports streaming via query param ?stream=true
        Requires sessionid parameter
        """
        sessionid = request.query_params.get('sessionid')
        if not sessionid:
            return Response({'error': 'sessionid is required'}, status=status.HTTP_400_BAD_REQUEST)

        session = self._get_session(sessionid)
        if not session:
            return Response({'error': 'Invalid session'}, status=status.HTTP_404_NOT_FOUND)

        try:
            conversation = ChatConversation.objects.get(id=conversation_id, session=session)
        except ChatConversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)

        # Parse request
        serializer = ChatMessageCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_message = serializer.validated_data['content']

        # Save user message
        file_obj = serializer.validated_data.get('file')
        file_type = serializer.validated_data.get('file_type', '')

        user_msg = ChatMessage.objects.create(
            conversation=conversation,
            role='user',
            content=user_message
        )

        # Add file if provided
        if file_obj:
            user_msg.file = file_obj
            user_msg.file_type = file_type or ''
            user_msg.save()

        logger.info(f'[AIChat] User message: {user_message[:100]}...')

        # Build conversation history for context
        history = [
            {'role': m.role, 'content': m.content}
            for m in conversation.messages.exclude(id=user_msg.id).order_by('-created_at')[:10]
        ]
        history.reverse()  # Reverse to chronological order

        # Check if streaming requested
        stream = request.query_params.get('stream', 'false').lower() == 'true'

        if stream:
            return self._stream_response(conversation, user_msg, user_message, history, request)
        else:
            return self._get_full_response(conversation, user_msg, user_message, history, request)

    def _stream_response(self, conversation, user_msg, user_message, history, request):
        """Stream response from OpenAI"""
        ai_service = get_ai_service()

        def response_generator():
            """Generator for streaming response"""
            full_response = ''
            try:
                for chunk in ai_service.stream_response(user_message, history):
                    full_response += chunk
                    # Send chunk to client as JSON
                    yield f'data: {{"content": "{chunk.replace(chr(34), chr(92) + chr(34))}"}}\n\n'

                # Save assistant message after streaming completes
                ChatMessage.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=full_response,
                    is_streaming_complete=True
                )

                # Update conversation
                conversation.message_count = conversation.messages.count()
                conversation.last_message_at = timezone.now()
                conversation.save(update_fields=['message_count', 'last_message_at'])

                # Log session
                ChatSessionLog.objects.create(
                    conversation=conversation,
                    user=conversation.user,
                    event_type='streaming_ended',
                    tokens_used=0
                )

                logger.info('[AIChat] Streaming completed')
                yield 'data: {"done": true}\n\n'

            except Exception as e:
                logger.error(f'[AIChat] Streaming error: {e}')
                yield f'data: {{"error": "{str(e)}"}}\n\n'

        return StreamingHttpResponse(
            response_generator(),
            content_type='text/event-stream'
        )

    def _get_full_response(self, conversation, user_msg, user_message, history, request):
        """Get full response at once (non-streaming)"""
        try:
            ai_service = get_ai_service()
            response_text, tokens_used = ai_service.get_response(user_message, history)

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

            # Log session
            ChatSessionLog.objects.create(
                conversation=conversation,
                user=conversation.user,
                event_type='response_received',
                tokens_used=tokens_used
            )

            serializer = ChatMessageSerializer(assistant_msg, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f'[AIChat] Error getting response: {e}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['POST'])
# @permission_classes([IsAuthenticated])  # Disabled for testing - allow all users
def summarize_text_view(request):
    """
    POST /api/chat/summarize/  - Summarize text

    Request body: {"text": "...long text...", "max_length": 500}
    """
    text = request.data.get('text', '')
    max_length = request.data.get('max_length', 500)

    if not text:
        return Response({'error': 'Text is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ai_service = get_ai_service()
        summary, tokens_used = ai_service.summarize_text(text, max_length)

        logger.info(f'[AIChat] Summarization: {tokens_used} tokens')
        return Response({
            'summary': summary,
            'tokens_used': tokens_used,
            'original_length': len(text),
            'summary_length': len(summary)
        })

    except Exception as e:
        logger.error(f'[AIChat] Summarization error: {e}')
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
# @permission_classes([IsAuthenticated])  # Disabled for testing - allow all users
def generate_code_view(request):
    """
    POST /api/chat/generate-code/  - Generate code

    Request body: {"requirement": "...", "language": "python"}
    """
    requirement = request.data.get('requirement', '')
    language = request.data.get('language', 'python')

    if not requirement:
        return Response({'error': 'Requirement is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ai_service = get_ai_service()
        code, tokens_used = ai_service.generate_code(requirement, language)

        logger.info(f'[AIChat] Code generation: {tokens_used} tokens')
        return Response({
            'code': code,
            'language': language,
            'tokens_used': tokens_used
        })

    except Exception as e:
        logger.error(f'[AIChat] Code generation error: {e}')
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def init_session_view(request):
    """
    POST /api/chat/init/  - Initialize a new chat session

    Returns: {"sessionid": "xxx"}
    """
    import uuid
    from django.contrib.auth.models import User

    try:
        # Get authenticated user or use default
        user = request.user if request.user.is_authenticated else User.objects.first()
        if not user:
            return Response({'error': 'User not found'}, status=status.HTTP_400_BAD_REQUEST)

        # Create new session with unique sessionid
        sessionid = str(uuid.uuid4())[:8]  # Short unique id
        session = ChatSession.objects.create(
            sessionid=sessionid,
            user=user,
            is_active=True
        )

        # Auto-create first conversation
        conversation = ChatConversation.objects.create(
            session=session,
            user=user,
            title='New Chat'
        )

        logger.info(f'[AIChat] New session created: {sessionid} for user {user.username}')
        return Response({
            'sessionid': sessionid,
            'conversation_id': str(conversation.id)
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f'[AIChat] Session init error: {e}')
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def send_message_simple_view(request):
    """
    POST /api/chat/send/  - Send message and get AI response

    Request body: {"sessionid": "xxx", "message": "your query"}
    Returns: {"response": "AI answer", "sessionid": "xxx"}
    """
    sessionid = request.data.get('sessionid')
    message = request.data.get('message', '')

    if not sessionid or not message:
        return Response(
            {'error': 'sessionid and message are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        session = ChatSession.objects.get(sessionid=sessionid)
    except ChatSession.DoesNotExist:
        return Response({'error': 'Invalid sessionid'}, status=status.HTTP_404_NOT_FOUND)

    try:
        conversation = ChatConversation.objects.filter(session=session, is_active=True).first()
        if not conversation:
            conversation = ChatConversation.objects.create(
                session=session,
                user=session.user,
                title='Chat'
            )

        user_msg = ChatMessage.objects.create(
            conversation=conversation,
            role='user',
            content=message
        )

        logger.info(f'[AIChat] User message: {message[:100]}...')

        history = [
            {'role': m.role, 'content': m.content}
            for m in conversation.messages.exclude(id=user_msg.id).order_by('-created_at')[:3]
        ]
        history.reverse()

        ai_service = get_ai_service()
        response_text, tokens_used = ai_service.get_response(message, history)

        ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=response_text,
            tokens_used=tokens_used,
            is_streaming_complete=True
        )

        conversation.message_count = conversation.messages.count()
        conversation.total_tokens_used += tokens_used
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['message_count', 'total_tokens_used', 'last_message_at'])

        logger.info(f'[AIChat] Response sent: {tokens_used} tokens')
        return Response({
            'response': response_text,
            'sessionid': sessionid,
            'tokens_used': tokens_used
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f'[AIChat] Send message error: {e}')
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
