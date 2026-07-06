"""
RAG API Views - Document upload, management, and search endpoints
"""

import logging
from django.db import transaction, models
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import RAGDocument, RAGIndexingLog
from .serializers import (
    RAGDocumentListSerializer,
    RAGDocumentDetailSerializer,
    RAGDocumentUploadSerializer,
    RAGIndexingLogSerializer,
    RAGSearchResultSerializer,
)
from .services import get_rag_service, index_rag_document_sync

logger = logging.getLogger(__name__)


class RAGDocumentListCreateView(APIView):
    """
    GET  /api/rag/documents/          - List all indexed documents
    POST /api/rag/documents/          - Upload new document for indexing
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        """List all RAG documents"""
        documents = RAGDocument.objects.all()
        serializer = RAGDocumentListSerializer(documents, many=True)
        return Response({
            'count': documents.count(),
            'documents': serializer.data
        })

    def post(self, request):
        """Upload new document"""
        serializer = RAGDocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        document = serializer.save()

        logger.info(f'[RAG API] Document uploaded: {document.id} - {document.title}')

        # Trigger async indexing
        from .tasks import run_rag_document_indexing_task
        run_rag_document_indexing_task.delay(str(document.id))

        return Response(
            RAGDocumentDetailSerializer(document, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class RAGDocumentDetailView(APIView):
    """
    GET    /api/rag/documents/{id}/   - Get document details
    DELETE /api/rag/documents/{id}/   - Delete document and its chunks
    """

    def get(self, request, doc_id):
        """Get document details"""
        try:
            document = RAGDocument.objects.get(id=doc_id)
            serializer = RAGDocumentDetailSerializer(document, context={'request': request})
            return Response(serializer.data)
        except RAGDocument.DoesNotExist:
            return Response(
                {'error': f'Document {doc_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def delete(self, request, doc_id):
        """Delete document and its RAG chunks"""
        try:
            document = RAGDocument.objects.get(id=doc_id)
        except RAGDocument.DoesNotExist:
            return Response(
                {'error': f'Document {doc_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            # Delete chunks from RAG
            try:
                rag = get_rag_service()
                deleted_chunks = rag.delete_document_chunks(str(document.id))

                RAGIndexingLog.objects.create(
                    document=document,
                    operation='delete',
                    status='success',
                    chunks_created=deleted_chunks
                )
            except Exception as e:
                logger.warning(f'[RAG API] Failed to delete RAG chunks: {e}')

            # Delete file
            if document.file:
                document.file.delete()

            # Delete document record
            document.delete()

        logger.info(f'[RAG API] Document {doc_id} deleted')
        return Response(
            {'message': f'Document {doc_id} deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


class RAGSearchView(APIView):
    """
    POST /api/rag/search/    - Search Global RAG Knowledge Base

    Request body:
    {
      "query": "search query text",
      "top_k": 5,
      "category": "Salesforce" (optional)
    }
    """

    def post(self, request):
        """Search RAG knowledge base"""
        query = request.data.get('query', '').strip()
        top_k = int(request.data.get('top_k', 5))
        category = request.data.get('category')

        if not query:
            return Response(
                {'error': 'Query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            rag = get_rag_service()
            results = rag.search(query, top_k=top_k, category=category)

            return Response({
                'query': query,
                'total_results': len(results),
                'results': results
            })

        except Exception as e:
            logger.error(f'[RAG API] Search failed: {e}')
            return Response(
                {'error': f'Search failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RAGReindexDocumentView(APIView):
    """
    POST /api/rag/documents/{id}/reindex/    - Manually trigger reindexing
    """

    def post(self, request, doc_id):
        """Manually trigger document reindexing"""
        try:
            document = RAGDocument.objects.get(id=doc_id)
        except RAGDocument.DoesNotExist:
            return Response(
                {'error': f'Document {doc_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not document.file:
            return Response(
                {'error': 'Document file not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info(f'[RAG API] Reindexing document {doc_id}')

        # Trigger async reindexing
        from .tasks import run_rag_document_indexing_task
        run_rag_document_indexing_task.delay(str(document.id))

        return Response({
            'message': f'Document {doc_id} reindexing started',
            'document_id': str(document.id),
            'status': 'indexing'
        })


class RAGIndexingStatusView(APIView):
    """
    GET /api/rag/documents/{id}/status/    - Check indexing status and logs
    """

    def get(self, request, doc_id):
        """Get document indexing status and logs"""
        try:
            document = RAGDocument.objects.get(id=doc_id)
        except RAGDocument.DoesNotExist:
            return Response(
                {'error': f'Document {doc_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        logs = document.indexing_logs.all()[:5]  # Last 5 logs
        log_serializer = RAGIndexingLogSerializer(logs, many=True)

        return Response({
            'document_id': str(document.id),
            'title': document.title,
            'status': document.status,
            'status_display': document.get_status_display(),
            'chunk_count': document.chunk_count,
            'indexed_at': document.indexed_at,
            'error_message': document.error_message,
            'recent_logs': log_serializer.data
        })


class RAGStatsView(APIView):
    """
    GET /api/rag/stats/    - Global RAG statistics
    """

    def get(self, request):
        """Get RAG statistics"""
        total_docs = RAGDocument.objects.count()
        indexed_docs = RAGDocument.objects.filter(status='indexed').count()
        pending_docs = RAGDocument.objects.filter(status='pending').count()
        failed_docs = RAGDocument.objects.filter(status='failed').count()

        total_chunks = RAGDocument.objects.filter(status='indexed').aggregate(
            total=models.Sum('chunk_count')
        )['total'] or 0

        admin_docs = RAGDocument.objects.filter(source='admin').count()
        insight_docs = RAGDocument.objects.filter(source='insight_attachment').count()

        return Response({
            'total_documents': total_docs,
            'indexed_documents': indexed_docs,
            'pending_documents': pending_docs,
            'failed_documents': failed_docs,
            'total_chunks': total_chunks,
            'by_source': {
                'admin': admin_docs,
                'insight_attachment': insight_docs
            }
        })
