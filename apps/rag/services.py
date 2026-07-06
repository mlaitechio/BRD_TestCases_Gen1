"""
RAG Services - Core RAG indexing and search functionality
"""

import logging
import os
import httpx
import chromadb
from typing import List, Dict, Optional
from datetime import datetime

from .models import RAGDocument, RAGIndexingLog
from .utils import extract_text_from_document, chunk_document, format_rag_context

logger = logging.getLogger(__name__)

# Disable ChromaDB telemetry
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['POSTHOG_DISABLED'] = '1'


def _get_robust_http_client() -> httpx.Client:
    """Create robust HTTP client with proxy support"""
    proxy_url = os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY', os.getenv('https_proxy', os.getenv('http_proxy', ''))))
    if proxy_url and not proxy_url.startswith(('http://', 'https://')):
        proxy_url = f'http://{proxy_url}'
    return httpx.Client(
        verify=False,
        http2=False,
        http1=True,
        proxy=proxy_url if proxy_url else None,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        timeout=600.0,
    )


class RAGService:
    """Core RAG service for indexing and searching documents"""

    def __init__(self):
        """Initialize ChromaDB client with persistent storage"""
        self.persist_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'rag', 'chroma_db'
        )

        # Create directory if not exists
        os.makedirs(self.persist_directory, exist_ok=True)

        # Remove stale lock files
        try:
            lock_file = os.path.join(self.persist_directory, "chroma.sqlite3.lock")
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception:
            pass

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=chromadb.config.Settings(
                anonymized_telemetry=False,
            )
        )

        # Configure embedding function
        self._setup_embedding_function()

        # Get or create collection
        self.collection_name = 'global_rag_kb'
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn
        )

        logger.info(f'[RAG] Initialized with ChromaDB at {self.persist_directory}')

    def _setup_embedding_function(self):
        """Setup embedding function based on AI provider"""
        from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
        from overrides import override

        ai_provider = os.getenv('AI_PROVIDER', 'azure_openai').lower()
        http_client = _get_robust_http_client()

        if ai_provider == 'azure_openai':
            class AzureEmbedding(EmbeddingFunction):
                def __init__(self, api_key, api_base, api_version, deployment_id, http_client):
                    from openai import AzureOpenAI
                    self.client = AzureOpenAI(
                        api_key=api_key,
                        api_version=api_version,
                        azure_endpoint=api_base,
                        http_client=http_client,
                        max_retries=1,
                    )
                    self.deployment_id = deployment_id

                def name(self) -> str:
                    return "azure_openai"

                @override
                def __call__(self, input: Documents) -> Embeddings:
                    response = self.client.embeddings.create(
                        model=self.deployment_id,
                        input=input
                    )
                    return [data.embedding for data in response.data]

            self.embedding_fn = AzureEmbedding(
                api_key=os.getenv('AZURE_OPENAI_API_KEY'),
                api_base=os.getenv('AZURE_OPENAI_ENDPOINT'),
                api_version=os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01'),
                deployment_id=os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', 'text-embedding-ada-002'),
                http_client=http_client
            )
        else:
            class OpenAIEmbedding(EmbeddingFunction):
                def __init__(self, api_key, http_client):
                    from openai import OpenAI
                    self.client = OpenAI(api_key=api_key, http_client=http_client, max_retries=1)

                def name(self) -> str:
                    return "openai"

                @override
                def __call__(self, input: Documents) -> Embeddings:
                    response = self.client.embeddings.create(
                        model="text-embedding-3-small",
                        input=input
                    )
                    return [data.embedding for data in response.data]

            self.embedding_fn = OpenAIEmbedding(
                api_key=os.getenv('OPENAI_API_KEY'),
                http_client=http_client
            )

    def index_document(self, document_id: str, file_path: str, file_type: str, category: str = 'General') -> int:
        """
        Index a document to RAG.

        Args:
            document_id: RAGDocument UUID
            file_path: Path to document file
            file_type: File type (pdf, docx, txt)
            category: Document category

        Returns:
            Number of chunks indexed
        """
        try:
            # Extract text
            text = extract_text_from_document(file_path, file_type)
            if not text:
                raise ValueError('Failed to extract text from document')

            # Chunk document
            chunks = chunk_document(text, document_id, category)
            if not chunks:
                raise ValueError('No chunks generated from document')

            # Add to ChromaDB
            ids = [chunk['id'] for chunk in chunks]
            documents = [chunk['text'] for chunk in chunks]
            metadatas = [chunk['metadata'] for chunk in chunks]

            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f'[RAG] Indexed {len(chunks)} chunks for document {document_id}')
            return len(chunks)

        except Exception as e:
            logger.error(f'[RAG] Indexing failed for {document_id}: {e}')
            raise

    def search(self, query_text: str, top_k: int = 5, category: str = None) -> List[Dict]:
        """
        Search RAG knowledge base.

        Args:
            query_text: Search query
            top_k: Number of results
            category: Filter by category (optional)

        Returns:
            List of search results
        """
        try:
            # Build filter if category provided
            where_filter = None
            if category:
                where_filter = {'category': {'$eq': category}}

            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where_filter
            )

            if not results['documents'] or not results['documents'][0]:
                return []

            search_results = []
            for idx, (doc, meta, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
                # Convert distance to similarity (0-1 range)
                similarity = 1 - (distance / 2)

                search_results.append({
                    'rank': idx + 1,
                    'content': doc,
                    'similarity_score': similarity,
                    'category': meta.get('category', 'General'),
                    'document_id': meta.get('document_id', 'unknown'),
                    'chunk_index': meta.get('chunk_index', 0),
                })

            logger.info(f'[RAG] Found {len(search_results)} results for query')
            return search_results

        except Exception as e:
            logger.error(f'[RAG] Search failed: {e}')
            return []

    def delete_document_chunks(self, document_id: str) -> int:
        """
        Delete all chunks for a document from RAG.

        Args:
            document_id: Document UUID

        Returns:
            Number of chunks deleted
        """
        try:
            # Get all chunk IDs for this document
            results = self.collection.get(
                where={'document_id': {'$eq': str(document_id)}}
            )

            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f'[RAG] Deleted {len(results["ids"])} chunks for document {document_id}')
                return len(results['ids'])

            return 0

        except Exception as e:
            logger.error(f'[RAG] Deletion failed for {document_id}: {e}')
            raise


# Singleton instance
_rag_service = None


def get_rag_service() -> RAGService:
    """Get RAG service singleton"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


def index_rag_document_sync(document_id: str, file_path: str, file_type: str, category: str = 'General'):
    """
    Synchronous document indexing.

    Args:
        document_id: RAGDocument UUID
        file_path: Path to document file
        file_type: File type
        category: Document category
    """
    try:
        doc = RAGDocument.objects.get(id=document_id)
        doc.status = 'indexing'
        doc.save(update_fields=['status'])

        rag = get_rag_service()
        chunk_count = rag.index_document(document_id, file_path, file_type, category)

        doc.status = 'indexed'
        doc.chunk_count = chunk_count
        doc.indexed_at = datetime.now()
        doc.error_message = ''
        doc.save(update_fields=['status', 'chunk_count', 'indexed_at', 'error_message'])

        RAGIndexingLog.objects.create(
            document=doc,
            operation='index',
            status='success',
            chunks_created=chunk_count
        )

        logger.info(f'[RAG] Document {document_id} indexed successfully')

    except RAGDocument.DoesNotExist:
        logger.error(f'[RAG] Document {document_id} not found')
    except Exception as e:
        logger.error(f'[RAG] Indexing failed for {document_id}: {e}')

        try:
            doc = RAGDocument.objects.get(id=document_id)
            doc.status = 'failed'
            doc.error_message = str(e)
            doc.save(update_fields=['status', 'error_message'])

            RAGIndexingLog.objects.create(
                document=doc,
                operation='index',
                status='failed',
                error_message=str(e)
            )
        except:
            pass
