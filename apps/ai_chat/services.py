"""
AI Chat Services - OpenAI integration with streaming support
"""

import logging
import os
from typing import Generator, Optional
from openai import AzureOpenAI, APIError

logger = logging.getLogger(__name__)


class AISearchService:
    """
    Service to handle AI chat with streaming support.
    Integrates with Azure OpenAI API for question answering.
    """

    def __init__(self):
        """Initialize Azure OpenAI client"""
        api_key = os.getenv('AZURE_OPENAI_API_KEY')
        api_base = os.getenv('AZURE_OPENAI_ENDPOINT')
        api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01')

        if not api_key or not api_base:
            raise ValueError('AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT must be set in environment')

        self.client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=api_base,
            timeout=60.0,
            max_retries=0
        )
        self.model = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5.5')

    def stream_response(
        self,
        user_message: str,
        conversation_history: list = None,
        max_tokens: int = 2000
    ) -> Generator[str, None, None]:
        """
        Stream a response from OpenAI API.

        Args:
            user_message: User's question/message
            conversation_history: List of previous messages [{'role': 'user'/'assistant', 'content': '...'}, ...]
            max_tokens: Max tokens in response

        Yields:
            Streamed response chunks
        """
        try:
            # Build messages array
            messages = []

            # Add system prompt
            messages.append({
                'role': 'system',
                'content': '''You are a helpful AI assistant.
                You can answer questions, help with code generation, document summarization, and general inquiries.
                Be concise but thorough in your responses.
                If asked to generate code, format it clearly with language specifications.
                If asked to summarize, provide key points in a structured format.'''
            })

            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)

            # Add current user message
            messages.append({
                'role': 'user',
                'content': user_message
            })

            logger.info(f'[AIChat] Streaming response for user message: {user_message[:100]}...')

            # Stream response from OpenAI
            with self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=max_tokens,
                stream=True
            ) as stream:
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

            logger.info('[AIChat] Streaming completed successfully')

        except APIError as e:
            logger.error(f'[AIChat] OpenAI API error: {e}')
            yield f'Error: {str(e)}'
        except Exception as e:
            logger.error(f'[AIChat] Unexpected error: {e}')
            yield f'Error: {str(e)}'

    def get_response(
        self,
        user_message: str,
        conversation_history: list = None,
        max_tokens: int = 2048
    ) -> tuple[str, int]:
        """
        Get complete response (non-streaming).

        Args:
            user_message: User's question/message
            conversation_history: List of previous messages
            max_tokens: Max tokens in response

        Returns:
            Tuple of (response_text, tokens_used)
        """
        try:
            messages = []

            # Add system prompt
            messages.append({
                'role': 'system',
                'content': '''You are a helpful AI assistant.
                You can answer questions, help with code generation, document summarization, and general inquiries.
                Be concise but thorough in your responses.'''
            })

            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history)

            # Add current message
            messages.append({
                'role': 'user',
                'content': user_message
            })

            logger.info(f'[AIChat] Getting response for: {user_message[:100]}...')

            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=max_tokens
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.completion_tokens

            logger.info(f'[AIChat] Response received: {tokens_used} tokens used')
            return content, tokens_used

        except APIError as e:
            logger.error(f'[AIChat] OpenAI API error: {e}')
            raise
        except Exception as e:
            logger.error(f'[AIChat] Unexpected error: {e}')
            raise

    def summarize_text(self, text: str, max_length: int = 500) -> tuple[str, int]:
        """
        Summarize provided text.

        Args:
            text: Text to summarize
            max_length: Max length of summary

        Returns:
            Tuple of (summary, tokens_used)
        """
        prompt = f'''Please summarize the following text concisely in under {max_length} characters:

{text}

Provide only the summary without additional explanation.'''

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': 'You are a helpful summarizer.'},
                    {'role': 'user', 'content': prompt}
                ],
                max_completion_tokens=500
            )

            summary = response.choices[0].message.content
            tokens_used = response.usage.completion_tokens

            logger.info(f'[AIChat] Summarization complete: {tokens_used} tokens')
            return summary, tokens_used

        except Exception as e:
            logger.error(f'[AIChat] Summarization failed: {e}')
            raise

    def generate_code(self, requirement: str, language: str = 'python') -> tuple[str, int]:
        """
        Generate code based on requirement.

        Args:
            requirement: What code should do
            language: Programming language

        Returns:
            Tuple of (code, tokens_used)
        """
        prompt = f'''Generate {language} code for the following requirement:

{requirement}

Provide only the code with no explanation. Include comments for clarity.'''

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': f'You are an expert {language} programmer.'},
                    {'role': 'user', 'content': prompt}
                ],
                max_completion_tokens=2000
            )

            code = response.choices[0].message.content
            tokens_used = response.usage.completion_tokens

            logger.info(f'[AIChat] Code generation complete: {tokens_used} tokens')
            return code, tokens_used

        except Exception as e:
            logger.error(f'[AIChat] Code generation failed: {e}')
            raise


# Singleton instance
_ai_service = None


def get_ai_service() -> AISearchService:
    """Get or create AI search service singleton"""
    global _ai_service
    if _ai_service is None:
        _ai_service = AISearchService()
    return _ai_service
