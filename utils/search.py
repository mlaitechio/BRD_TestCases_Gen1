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
from chromadb.utils import embedding_functions

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
        timeout=60.0,
    )

class GlobalKnowledgeBase:
    def __init__(self):
        self.persist_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            'chroma_db'
        )
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
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
                self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                    api_key=api_key,
                    api_base=api_base,
                    api_type="azure",
                    api_version=api_version,
                    deployment_id=deployment_id,
                    model_name=deployment_id,
                    http_client=http_client,
                )
            else:
                self.embedding_fn = None
                logger.warning("[GlobalKnowledgeBase] Azure credentials missing. Embeddings will not work.")
        else:
            openai_key = os.getenv('OPENAI_API_KEY')
            if openai_key:
                self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                    api_key=openai_key,
                    model_name="text-embedding-3-large",
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

    def search_similar(self, query_text: str, top_k: int = 5) -> str:
        """
        Search the ChromaDB collection for chunks similar to the query text.
        """
        if not self.embedding_fn:
            logger.error("[GlobalKnowledgeBase] Cannot search without an embedding provider.")
            return ""

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=top_k
            )
            
            if not results['documents'] or not results['documents'][0]:
                return ""
                
            retrieved_chunks = results['documents'][0]
            metadatas = results['metadatas'][0]
            
            context_blocks = []
            for doc, meta in zip(retrieved_chunks, metadatas):
                source = meta.get('source', 'Unknown')
                section = meta.get('section', 'General')
                context_blocks.append(f"--- Previous BRD ({source}) - {section} ---\n{doc}")
                
            return "\n\n".join(context_blocks)
        except Exception as e:
            logger.error(f"[GlobalKnowledgeBase] Search failed: {e}")
            return ""

# Singleton instance
kb_instance = GlobalKnowledgeBase()

def search_knowledge_base(query_text: str, top_k: int = 5) -> str:
    """
    Retrieve corporate knowledge base guidelines and past similar BRD chunks.
    """
    guidance = kb_instance.search_similar(query_text, top_k)
    if not guidance:
        return ""
    
    return f'=== COMPANY KNOWLEDGE BASE ===\n\n{guidance}\n\n=== END COMPANY KNOWLEDGE BASE ===\n'
