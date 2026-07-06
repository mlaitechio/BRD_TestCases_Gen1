"""
RAG Django App Configuration
"""

from django.apps import AppConfig


class RagConfig(AppConfig):
    """Configuration for RAG app"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.rag'
    verbose_name = 'Global RAG Knowledge Base'
