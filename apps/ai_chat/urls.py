"""
AI Chat URL Routing
"""

from django.urls import path
from . import views

urlpatterns = [
    # Conversations
    path('conversations/', views.ChatConversationListCreateView.as_view(), name='chat-conversation-list-create'),
    path('conversations/<uuid:conversation_id>/', views.ChatConversationDetailView.as_view(), name='chat-conversation-detail'),

    # Messages
    path('conversations/<uuid:conversation_id>/messages/', views.ChatMessageSendView.as_view(), name='chat-message-send'),

    # Utilities
    path('summarize/', views.summarize_text_view, name='chat-summarize'),
    path('generate-code/', views.generate_code_view, name='chat-generate-code'),
]
