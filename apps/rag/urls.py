"""
RAG URL Configuration
"""

from django.urls import path
from . import views

app_name = 'rag'

urlpatterns = [
    # Document management
    path('documents/', views.RAGDocumentListCreateView.as_view(), name='document-list-create'),
    path('documents/<uuid:doc_id>/', views.RAGDocumentDetailView.as_view(), name='document-detail'),
    path('documents/<uuid:doc_id>/reindex/', views.RAGReindexDocumentView.as_view(), name='document-reindex'),
    path('documents/<uuid:doc_id>/status/', views.RAGIndexingStatusView.as_view(), name='document-status'),

    # Search
    path('search/', views.RAGSearchView.as_view(), name='search'),

    # Statistics
    path('stats/', views.RAGStatsView.as_view(), name='stats'),
]
