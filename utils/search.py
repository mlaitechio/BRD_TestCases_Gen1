"""
Knowledge Base RAG Utility.

Queries the global corporate knowledge base (past BRDs, templates, guidelines)
via local ChromaDB and OpenAI embeddings.

Usage:
    from utils.search import search_knowledge_base
    guidelines = search_knowledge_base(
        query_text='web application project requiring strict authentication',
        top_k=3,
    )
"""

import logging
import os
import httpx
import chromadb
from chromadb.config import Component
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from overrides import override

# ==============================================================================
# COMPLETELY DISABLE CHROMA DB TELEMETRY & POSTHOG TO PREVENT CELERY FORK DEADLOCK
# ==============================================================================
os.environ['ANONYMIZED_TELEMETRY'] = 'False'
os.environ['POSTHOG_DISABLED'] = '1'

class DummyTelemetry(Component):
    def __init__(self, system):
        super().__init__(system)
    @override
    def start(self) -> None:
        self._running = True
    @override
    def stop(self) -> None:
        self._running = False
    def capture(self, *args, **kwargs): pass

try:
    import chromadb.telemetry.product.posthog
    chromadb.telemetry.product.posthog.Posthog = DummyTelemetry
except Exception:
    pass

try:
    import posthoganalytics
    posthoganalytics.Posthog = DummyTelemetry
except Exception:
    pass

logger = logging.getLogger(__name__)

def _get_robust_http_client() -> httpx.Client:
    proxy_url = os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY', os.getenv('https_proxy', os.getenv('http_proxy', ''))))
    if proxy_url and not proxy_url.startswith(('http://', 'https://')):
        proxy_url = f'http://{proxy_url}'
    return httpx.Client(
        verify=False,
        http2=False,
        http1=True,
        proxy=proxy_url if proxy_url else None,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0'},
        timeout=600.0,
    )

class RobustAzureOpenAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str, api_base: str, api_version: str, deployment_id: str, http_client):
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
        return "openai"

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.embeddings.create(
            model=self.deployment_id,
            input=input
        )
        return [data.embedding for data in response.data]

class RobustOpenAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, api_key: str, model_name: str, http_client):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key,
            http_client=http_client,
            max_retries=1,
        )
        self.model_name = model_name

    def name(self) -> str:
        return "openai"

    def __call__(self, input: Documents) -> Embeddings:
        response = self.client.embeddings.create(
            model=self.model_name,
            input=input
        )
        return [data.embedding for data in response.data]

class GlobalKnowledgeBase:
    def __init__(self):
        os.environ['ANONYMIZED_TELEMETRY'] = 'False'
        os.environ['POSTHOG_DISABLED'] = '1'
        self.persist_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            'chroma_db'
        )
        
        # Force remove stale lock files
        try:
            lock_file = os.path.join(self.persist_directory, "chroma.sqlite3.lock")
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except Exception:
            pass

        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=chromadb.config.Settings(
                anonymized_telemetry=False,
                chroma_telemetry_impl="utils.search.DummyTelemetry",
            )
        )
        
        # Configure embedding function based on AI provider
        ai_provider = os.getenv('AI_PROVIDER', 'claude').lower()
        http_client = _get_robust_http_client()
        
        if ai_provider == 'azure_openai':
            api_key = os.getenv('AZURE_OPENAI_API_KEY')
            api_base = os.getenv('AZURE_OPENAI_ENDPOINT')
            api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01')
            # Typically Azure needs a separate deployment for embeddings
            deployment_id = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME', os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'text-embedding-ada-002'))
            
            if api_key and api_base:
                self.embedding_fn = RobustAzureOpenAIEmbeddingFunction(
                    api_key=api_key,
                    api_base=api_base,
                    api_version=api_version,
                    deployment_id=deployment_id,
                    http_client=http_client,
                )
            else:
                self.embedding_fn = None
                logger.warning("[GlobalKnowledgeBase] Azure credentials missing. Embeddings will not work.")
        else:
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                self.embedding_fn = RobustOpenAIEmbeddingFunction(
                    api_key=openai_key,
                    model_name="text-embedding-3-small",
                    http_client=http_client,
                )
            else:
                self.embedding_fn = None
                logger.warning("[GlobalKnowledgeBase] OPENAI_API_KEY not set. Embeddings will not work.")

        self.collection_name = "global_company_kb"
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn
        )

    def add_document_chunks(self, document_id: str, chunks: list[dict]):
        """
        chunks should be a list of dicts: {'id': '...', 'text': '...', 'metadata': {...}}
        """
        if not chunks:
            return
            
        ids = [chunk['id'] for chunk in chunks]
        documents = [chunk['text'] for chunk in chunks]
        metadatas = [chunk['metadata'] for chunk in chunks]
        
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"[GlobalKnowledgeBase] Added {len(chunks)} chunks for document {document_id}.")

    def search_similar(self, query_text: str, top_k: int = 5, application_type: str = None, line_of_business: str = None) -> str:
        """
        Search the ChromaDB collection for chunks similar to the query text.

        Args:
            query_text: The search query
            top_k: Number of results to return
            application_type: Filter by app type (e.g., 'salesforce', 'servicenow')
            line_of_business: Filter by business unit

        Returns:
            Formatted context block with retrieved chunks
        """
        if not self.embedding_fn:
            logger.error("[GlobalKnowledgeBase] Cannot search without an embedding provider.")
            return ""

        try:
            # Build metadata filter if provided
            where_filter = None
            if application_type or line_of_business:
                filters = []
                if application_type:
                    filters.append({"application_type": {"$eq": application_type}})
                if line_of_business:
                    filters.append({"line_of_business": {"$eq": line_of_business}})

                # Combine filters with OR
                if len(filters) > 1:
                    where_filter = {"$or": filters}
                else:
                    where_filter = filters[0] if filters else None

            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k,
                where=where_filter
            )

            if not results['documents'] or not results['documents'][0]:
                return ""

            retrieved_chunks = results['documents'][0]
            metadatas = results['metadatas'][0]

            context_blocks = []
            for doc, meta in zip(retrieved_chunks, metadatas):
                source = meta.get('source', 'Unknown')
                section = meta.get('section', 'General')
                app_type = meta.get('application_type', '')
                date = meta.get('date', '')
                context_blocks.append(f"--- Previous BRD ({source} - {app_type}) [{section}] ({date}) ---\n{doc}")

            return "\n\n".join(context_blocks)
        except Exception as e:
            logger.error(f"[GlobalKnowledgeBase] Search failed: {e}")
            return ""

# Lazy singleton instance to prevent Celery fork() deadlocks
_kb_instance = None

def _get_kb_instance():
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = GlobalKnowledgeBase()
    return _kb_instance

def search_knowledge_base(query_text: str, top_k: int = 5, application_type: str = None, line_of_business: str = None) -> str:
    """
    Retrieve corporate knowledge base guidelines and past similar BRD chunks.

    Args:
        query_text: Search query
        top_k: Number of results
        application_type: Filter by app type (optional)
        line_of_business: Filter by business unit (optional)

    Returns:
        Formatted context block for prompt injection
    """
    kb = _get_kb_instance()
    guidance = kb.search_similar(query_text, top_k, application_type, line_of_business)
    if not guidance:
        return ""

    return f'=== COMPANY KNOWLEDGE BASE ===\n\n{guidance}\n\n=== END COMPANY KNOWLEDGE BASE ===\n'
