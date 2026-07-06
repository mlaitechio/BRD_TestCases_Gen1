"""
RAG Celery Tasks - Async document indexing
"""

import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def run_rag_document_indexing_task(self, document_id: str):
    """
    Async task to index a document to Global RAG.

    Called after document upload or on manual reindex request.

    Args:
        document_id: RAGDocument UUID
    """
    from apps.rag.models import RAGDocument
    from apps.rag.services import index_rag_document_sync

    try:
        document = RAGDocument.objects.get(id=document_id)

        if not document.file:
            logger.error(f'[RAG Task] Document {document_id} has no file')
            return

        logger.info(f'[RAG Task] Starting indexing for document {document_id}')

        # Index the document
        index_rag_document_sync(
            document_id=document_id,
            file_path=document.file.path,
            file_type=document.file_type,
            category=document.category or 'General'
        )

        logger.info(f'[RAG Task] Indexing complete for document {document_id}')

    except RAGDocument.DoesNotExist:
        logger.error(f'[RAG Task] Document {document_id} not found')

    except Exception as exc:
        logger.error(f'[RAG Task] Indexing failed for {document_id}: {exc}')
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def run_rag_batch_indexing_task(self, document_ids: list):
    """
    Batch indexing task for multiple documents.

    Args:
        document_ids: List of RAGDocument UUIDs
    """
    from apps.rag.models import RAGDocument

    logger.info(f'[RAG Task] Starting batch indexing for {len(document_ids)} documents')

    success_count = 0
    fail_count = 0

    for doc_id in document_ids:
        try:
            run_rag_document_indexing_task.delay(str(doc_id))
            success_count += 1
        except Exception as e:
            logger.error(f'[RAG Task] Failed to queue indexing for {doc_id}: {e}')
            fail_count += 1

    logger.info(
        f'[RAG Task] Batch indexing queued - Success: {success_count}, Failed: {fail_count}'
    )
