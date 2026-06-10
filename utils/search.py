"""
Azure AI Search Utility — Static Knowledge Base RAG.

Queries the static corporate knowledge base (BRD templates, writing
guidelines, few-shot examples) via Azure AI Search hybrid search.

STATUS: Stub mode — returns empty string when Azure Search is not configured.
This is intentional for Phase 1 POC. Once the Azure AI Search service is
provisioned and the index is populated, set the AZURE_SEARCH_* env vars
and the RAG will activate automatically.

Usage:
    from utils.search import search_knowledge_base
    guidelines = search_knowledge_base(
        section_title='Functional Requirements',
        app_type='web',
    )
    # guidelines is '' when not configured, or a template string when live
"""

import logging
import os

logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────

AZURE_SEARCH_ENDPOINT = os.getenv('AZURE_SEARCH_SERVICE_ENDPOINT', '')
AZURE_SEARCH_INDEX = os.getenv('AZURE_SEARCH_INDEX_NAME', 'static-corporate-templates-index')
AZURE_SEARCH_KEY = os.getenv('AZURE_SEARCH_API_KEY', '')

# Returns up to this many template documents per section query
DEFAULT_TOP_K = 2


def search_knowledge_base(
    section_title: str,
    app_type: str = '',
    top_k: int = DEFAULT_TOP_K,
) -> str:
    """
    Retrieve corporate template guidelines relevant to a BRD section.

    Args:
        section_title: The BRD section being generated (e.g. 'Functional Requirements').
        app_type: Application type for more targeted retrieval (e.g. 'web', 'api').
        top_k: Maximum number of template documents to retrieve.

    Returns:
        str: Formatted template guidance text for prompt injection.
             Returns empty string if Azure Search is not configured (stub mode).
    """
    if not _is_configured():
        logger.debug(
            '[KnowledgeBase] Azure AI Search not configured — '
            'returning empty context (stub mode). '
            'Set AZURE_SEARCH_SERVICE_ENDPOINT, AZURE_SEARCH_INDEX_NAME, '
            'and AZURE_SEARCH_API_KEY to activate.'
        )
        return ''

    try:
        return _search(section_title, app_type, top_k)
    except Exception as e:
        logger.error(f'[KnowledgeBase] Search failed for "{section_title}": {e}')
        return ''   # Graceful fallback — never break document generation


def _is_configured() -> bool:
    """Return True only if all required Azure Search credentials are present."""
    return bool(AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_KEY)


def _search(section_title: str, app_type: str, top_k: int) -> str:
    """
    Perform a hybrid vector + keyword search against the Azure AI Search index.

    Generates an embedding for the query using Azure OpenAI, then runs
    a combined semantic + keyword search for maximum retrieval quality.
    """
    try:
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential
    except ImportError:
        logger.error('[KnowledgeBase] azure-search-documents not installed.')
        return ''

    query = f'{app_type} {section_title} BRD template style guide formatting examples'.strip()
    logger.info(f'[KnowledgeBase] Searching for: "{query}"')

    # ── Generate query embedding ───────────────────────────────────────────────
    query_vector = _get_embedding(query)

    # ── Build search client ────────────────────────────────────────────────────
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=AZURE_SEARCH_INDEX,
        credential=AzureKeyCredential(AZURE_SEARCH_KEY),
    )

    # ── Execute hybrid search ──────────────────────────────────────────────────
    search_kwargs = {
        'search_text': query,
        'select': ['template_name', 'formatting_rules', 'few_shot_example', 'section_type'],
        'top': top_k,
    }

    if query_vector:
        search_kwargs['vector_queries'] = [{
            'value': query_vector,
            'fields': 'content_vector',
            'k': top_k,
            'kind': 'vector',
        }]

    results = search_client.search(**search_kwargs)

    # ── Format results ─────────────────────────────────────────────────────────
    template_blocks = []
    for doc in results:
        block_parts = []
        if doc.get('template_name'):
            block_parts.append(f'Template: {doc["template_name"]}')
        if doc.get('formatting_rules'):
            block_parts.append(f'Formatting Rules:\n{doc["formatting_rules"]}')
        if doc.get('few_shot_example'):
            block_parts.append(f'Example:\n{doc["few_shot_example"]}')
        if block_parts:
            template_blocks.append('\n'.join(block_parts))

    if not template_blocks:
        logger.info(f'[KnowledgeBase] No results returned for "{query}"')
        return ''

    guidance = '\n\n---\n\n'.join(template_blocks)
    logger.info(f'[KnowledgeBase] Retrieved {len(template_blocks)} template(s) for "{section_title}"')
    return f'=== CORPORATE TEMPLATE GUIDANCE ===\n\n{guidance}\n\n=== END TEMPLATE GUIDANCE ==='


def _get_embedding(text: str) -> list[float] | None:
    """
    Generate a vector embedding for hybrid search using Azure OpenAI.
    Returns None if embedding generation fails (falls back to keyword-only search).
    """
    azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT', '')
    azure_key = os.getenv('AZURE_OPENAI_API_KEY', '')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01')
    embedding_deployment = os.getenv('AZURE_OPENAI_EMBEDDING_DEPLOYMENT', 'text-embedding-3-large')

    if not azure_endpoint or not azure_key:
        logger.debug('[KnowledgeBase] Azure OpenAI not configured — using keyword search only')
        return None

    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=azure_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint,
        )
        response = client.embeddings.create(input=[text], model=embedding_deployment)
        return response.data[0].embedding
    except Exception as e:
        logger.warning(f'[KnowledgeBase] Embedding generation failed ({e}) — keyword search only')
        return None
