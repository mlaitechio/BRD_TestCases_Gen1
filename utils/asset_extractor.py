"""
Asset Extractor Utility — Knowledge Layer Source Connectors.

Handles text extraction and AI-powered summarisation for all 7
ProjectAsset connector types:

  1. mom        — Minutes of Meeting (PDF / DOCX / TXT)
  2. url        — Reference URL (fetched via requests + BeautifulSoup, summarised by LLM)
  3. architecture — Architecture / Design Diagram (image → describe, or DOCX/PDF text)
  4. document   — Reference Document (PDF / DOCX / TXT)
  5. chat       — Chat Export (TXT / DOCX)
  6. email      — Email Thread (TXT / DOCX / EML)
  7. recording  — Call Recording Transcript (TXT / DOCX)

After extraction, the full text is summarised by the configured AI provider
into a short, dense summary optimised for context injection.

Usage:
    from utils.asset_extractor import extract_and_summarise
    extracted_text, summary, error = extract_and_summarise(asset)
"""

import logging
import os
import re

from utils.image_extractor import extract_and_describe_images

logger = logging.getLogger(__name__)


# Maximum characters to send to the LLM for summarisation
MAX_TEXT_FOR_SUMMARY = 12000

# System prompt for the summarisation LLM call
SUMMARY_SYSTEM_PROMPT = """You are a technical analyst assistant. 
Summarise the following document into a dense, factual paragraph (max 400 words) 
capturing: key decisions, requirements, technical details, people involved, 
dates, and action items. Focus on information useful for writing a Business 
Requirements Document. Be concise and factual. Do not include meta-commentary."""


def extract_and_summarise(asset) -> tuple[str, str, str | None]:
    """
    Extract text from an asset and generate an AI summary.

    Args:
        asset: A ProjectAsset model instance with connector_type, file, url set.

    Returns:
        tuple: (extracted_text: str, summary: str, error: str | None)
               error is None on success, error message string on failure.
    """
    connector_type = asset.connector_type
    logger.info(f'[AssetExtractor] Processing asset {asset.id} type={connector_type}')

    try:
        if connector_type == 'url':
            extracted_text = _extract_from_url(asset.url)
            image_descriptions = ''  # URLs: no local file to scan
        else:
            if not asset.file:
                return '', '', f'No file uploaded for asset type "{connector_type}"'
            file_path = asset.file.path
            extracted_text = _extract_from_file(file_path, connector_type)

            # ── Image extraction ────────────────────────────────────────────
            # Extract and describe any images embedded in PDF/DOCX files,
            # or describe the file itself if it IS an image.
            image_descriptions = ''
            try:
                image_descriptions = extract_and_describe_images(file_path)
                if image_descriptions:
                    logger.info(
                        f'[AssetExtractor] Image analysis added for asset {asset.id} '
                        f'({len(image_descriptions)} chars)'
                    )
            except Exception as img_exc:
                logger.warning(
                    f'[AssetExtractor] Image extraction skipped for asset {asset.id}: {img_exc}'
                )

        if not extracted_text or not extracted_text.strip():
            # If there's no text but there ARE image descriptions, use those
            if image_descriptions:
                extracted_text = ''
            else:
                return '', '', 'Could not extract any text from the source.'

        # Merge text + image descriptions before summarisation
        combined_text = extracted_text.strip()
        if image_descriptions:
            combined_text += (
                '\n\n'
                '=== EMBEDDED IMAGE ANALYSIS ===\n'
                '(Images extracted from the document and described by AI vision)\n\n'
                + image_descriptions
            )

        summary = _summarise(combined_text, connector_type, asset.title)
        return combined_text, summary, None

    except Exception as e:
        logger.exception(f'[AssetExtractor] Failed for asset {asset.id}: {e}')
        return '', '', str(e)


# ─── URL Extractor ────────────────────────────────────────────────────────────

def _extract_from_url(url: str) -> str:
    """
    Fetch a URL and extract readable text using requests + BeautifulSoup.
    Falls back to raw text if HTML parsing fails.
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError(
            'requests and beautifulsoup4 are required. Run: pip install requests beautifulsoup4'
        )

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }

    logger.info(f'[AssetExtractor] Fetching URL: {url}')
    response = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
    response.raise_for_status()

    content_type = response.headers.get('Content-Type', '')

    # If it's a PDF served at a URL, extract via pdfplumber
    if 'application/pdf' in content_type:
        import io
        return _extract_pdf_from_bytes(io.BytesIO(response.content))

    # HTML parsing — extract meaningful text
    soup = BeautifulSoup(response.text, 'lxml')

    # Remove boilerplate elements
    for tag in soup(['script', 'style', 'nav', 'header', 'footer',
                      'aside', 'form', 'button', 'iframe', 'noscript']):
        tag.decompose()

    # Extract main content preferring semantic elements
    main_content = (
        soup.find('main') or
        soup.find('article') or
        soup.find(id=re.compile(r'content|main|body', re.I)) or
        soup.find(class_=re.compile(r'content|main|article', re.I)) or
        soup.find('body') or
        soup
    )

    # Get text with clean whitespace
    text = main_content.get_text(separator='\n', strip=True)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)

    logger.info(f'[AssetExtractor] URL extracted {len(text)} chars from {url}')
    return text.strip()


def _extract_pdf_from_bytes(file_obj) -> str:
    """Extract text from a PDF bytes object using pdfplumber."""
    try:
        import pdfplumber
        with pdfplumber.open(file_obj) as pdf:
            pages = [page.extract_text() or '' for page in pdf.pages]
        return '\n\n'.join(filter(None, pages))
    except Exception as e:
        raise RuntimeError(f'PDF extraction from bytes failed: {e}')


# ─── File Extractor ───────────────────────────────────────────────────────────

def _extract_from_file(file_path: str, connector_type: str) -> str:
    """
    Dispatch to the appropriate extractor based on file extension.
    All non-URL connector types (mom, architecture, document, chat, email, recording)
    go through this function.
    """
    ext = os.path.splitext(file_path)[1].lower()
    logger.info(f'[AssetExtractor] Extracting file {file_path} (ext={ext})')

    if ext == '.pdf':
        return _extract_pdf(file_path)
    elif ext in ('.docx', '.doc'):
        return _extract_docx(file_path)
    elif ext in ('.txt', '.md', '.csv', '.eml'):
        return _extract_text_file(file_path)
    elif ext in ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'):
        # All connector types: describe image using AI vision
        # (previously only 'architecture' was handled this way)
        return _describe_image_with_ai(file_path)
    elif ext in ('.mp3', '.wav', '.m4a', '.ogg'):
        return f'[Audio file transcription stub: {os.path.basename(file_path)}]'
    else:
        # Fallback — try reading as plain text
        return _extract_text_file(file_path)


def _extract_pdf(file_path: str) -> str:
    """Extract text from PDF using pdfplumber with PyPDF2 fallback."""
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            pages = [page.extract_text() or '' for page in pdf.pages]
        text = '\n\n'.join(filter(None, pages))
        if text.strip():
            return text
    except Exception as e:
        logger.warning(f'[AssetExtractor] pdfplumber failed ({e}), trying PyPDF2')

    try:
        import PyPDF2
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            pages = [page.extract_text() or '' for page in reader.pages]
        return '\n\n'.join(filter(None, pages))
    except Exception as e:
        raise RuntimeError(f'PDF extraction failed: {e}')


def _extract_docx(file_path: str) -> str:
    """Extract text from DOCX/DOC file using python-docx."""
    try:
        from docx import Document
        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return '\n\n'.join(paragraphs)
    except Exception as e:
        raise RuntimeError(f'DOCX extraction failed: {e}')


def _extract_text_file(file_path: str) -> str:
    """Read a plain text file with UTF-8 / latin-1 fallback."""
    for encoding in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1252'):
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue
    raise RuntimeError(f'Could not decode text file: {file_path}')


def _describe_image_with_ai(file_path: str) -> str:
    """
    Use the LLM (vision capable) to describe an architecture diagram image.
    Falls back to a generic placeholder if the provider does not support vision.
    """
    try:
        import base64
        with open(file_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')

        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        media_type = {
            'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'png': 'image/png', 'gif': 'image/gif',
            'webp': 'image/webp',
        }.get(ext, 'image/png')

        # Use Anthropic vision if Claude is configured
        ai_provider = os.getenv('AI_PROVIDER', 'claude').lower()
        if ai_provider == 'claude':
            return _claude_describe_image(image_data, media_type)
        else:
            # For OpenAI/Azure OpenAI — use GPT-4o vision
            return _openai_describe_image(image_data, media_type, ai_provider)

    except Exception as e:
        logger.warning(f'[AssetExtractor] Image description failed ({e}), using placeholder')
        return f'[Architecture diagram uploaded: {os.path.basename(file_path)}. Manual review required.]'


def _claude_describe_image(image_data: str, media_type: str) -> str:
    """Describe image via Anthropic Claude (supports vision natively)."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY', ''))
    message = client.messages.create(
        model='claude-3-5-sonnet-20241022',
        max_tokens=1024,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': image_data,
                    },
                },
                {
                    'type': 'text',
                    'text': (
                        'This is an architecture or design diagram for a software project. '
                        'Describe all components, their connections, data flows, technologies, '
                        'and any labels visible. Be specific and technical. Max 300 words.'
                    ),
                },
            ],
        }]
    )
    return message.content[0].text


def _openai_describe_image(image_data: str, media_type: str, provider: str) -> str:
    """Describe image via OpenAI or Azure OpenAI (GPT-4o vision)."""
    if provider == 'azure_openai':
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=os.getenv('AZURE_OPENAI_API_KEY', ''),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT', ''),
        )
        model = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4o')
    else:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY', ''))
        model = 'gpt-4o'

    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[{
            'role': 'user',
            'content': [
                {
                    'type': 'image_url',
                    'image_url': {'url': f'data:{media_type};base64,{image_data}'},
                },
                {
                    'type': 'text',
                    'text': (
                        'This is an architecture or design diagram for a software project. '
                        'Describe all components, their connections, data flows, technologies, '
                        'and any labels visible. Be specific and technical. Max 300 words.'
                    ),
                },
            ],
        }]
    )
    return response.choices[0].message.content


# ─── AI Summariser ────────────────────────────────────────────────────────────

def _summarise(text: str, connector_type: str, title: str | None) -> str:
    """
    Generate a dense AI summary of the extracted text for context injection.

    Args:
        text: Full extracted text from the source.
        connector_type: One of the 7 connector type strings.
        title: Optional user-provided title for the asset.

    Returns:
        str: Concise summary for prompt injection (max ~400 words / ~2000 chars).
    """
    from agents.base import generate  # Import here to avoid circular deps at module load

    # Truncate text to avoid exceeding LLM input limits
    truncated_text = text[:MAX_TEXT_FOR_SUMMARY]
    if len(text) > MAX_TEXT_FOR_SUMMARY:
        truncated_text += f'\n\n[... text truncated at {MAX_TEXT_FOR_SUMMARY} chars ...]'

    connector_label = {
        'mom': 'Minutes of Meeting',
        'url': 'Reference URL / Web Page',
        'architecture': 'Architecture Diagram',
        'document': 'Reference Document',
        'chat': 'Chat Export',
        'email': 'Email Thread',
        'recording': 'Call Recording Transcript',
    }.get(connector_type, connector_type.title())

    doc_label = f'{connector_label}: "{title}"' if title else connector_label

    user_prompt = f"""Document Type: {doc_label}

Content:
{truncated_text}

Provide a dense, factual summary (max 400 words) capturing all key requirements, 
decisions, technical details, and action items relevant to BRD generation."""

    try:
        summary = generate(SUMMARY_SYSTEM_PROMPT, user_prompt)
        return summary.strip()
    except Exception as e:
        logger.error(f'[AssetExtractor] Summarisation failed: {e}')
        # Return truncated raw text as fallback so the asset is still usable
        return text[:1000].strip() + '...' if len(text) > 1000 else text.strip()
