"""
utils/image_extractor.py

Extract images embedded inside PDF and DOCX files, then describe
each image using AI vision (Claude or GPT-4o) so the content is
available to BRD generation agents.

Supported sources:
  - PDF  → uses pdfplumber + PyMuPDF (fitz) to pull embedded raster images
  - DOCX → uses python-docx to pull images from the media/ zip entries
  - Direct image files (.png / .jpg / .jpeg / .webp / .gif / .bmp)

Usage:
    from utils.image_extractor import extract_and_describe_images

    descriptions = extract_and_describe_images("/path/to/file.pdf")
    # Returns a single string:  "--- Image 1 ---\n<description>\n\n--- Image 2 ---\n..."

Environment variables used (via Django settings / .env):
    AI_PROVIDER          — 'claude' | 'openai' | 'azure_openai'
    ANTHROPIC_API_KEY    — Claude API key
    OPENAI_API_KEY       — OpenAI API key
    AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT / AZURE_OPENAI_DEPLOYMENT_NAME
"""

import base64
import io
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# ── Tuning knobs ──────────────────────────────────────────────────────────────

# Skip images smaller than this (bytes) — avoids wasting tokens on icons/dividers
MIN_IMAGE_SIZE_BYTES = 5_000

# Max images to describe per file — cost/latency guard
MAX_IMAGES_PER_FILE = 50

# Vision prompt — tailored for BRD context
VISION_PROMPT = (
    "This image is extracted from a business requirements or project document. "
    "Describe everything you see in specific detail: every text, labels, diagrams, "
    "wireframes, flowcharts, data tables, screenshots, UI mockups, or architecture "
    "components. Capture all visible text verbatim. "
    "Be factual and technical. Max 300 words."
)


# ── Public API ────────────────────────────────────────────────────────────────

def extract_and_describe_images(file_path: str) -> str:
    """
    Extract all embedded images from a file and describe each with AI vision.

    Args:
        file_path: Absolute path to a .pdf, .docx, .doc, .png, .jpg, etc.

    Returns:
        A formatted string of all image descriptions, or empty string if none found.
        Each description is prefixed with "--- Image N (page/location) ---".
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        images = _extract_images_from_pdf(file_path)
    elif ext in (".docx", ".doc"):
        images = _extract_images_from_docx(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
        # Direct image file — treat it as a single image
        with open(file_path, "rb") as f:
            data = f.read()
        images = [{"data": data, "media_type": _ext_to_media_type(ext), "label": "Image"}]
    else:
        logger.debug(f"[ImageExtractor] No image extraction for ext={ext}")
        return ""

    if not images:
        logger.info(f"[ImageExtractor] No embedded images found in {file_path}")
        return ""

    logger.info(f"[ImageExtractor] Found {len(images)} image(s) in {file_path}")

    # Limit to MAX_IMAGES_PER_FILE
    images = images[:MAX_IMAGES_PER_FILE]

    descriptions = []
    for idx, img in enumerate(images, start=1):
        label = img.get("label", f"Image {idx}")
        try:
            desc = _describe_image(img["data"], img["media_type"])
            descriptions.append(f"--- {label} ---\n{desc}")
            logger.info(f"[ImageExtractor] Described {label} ({len(img['data'])} bytes)")
        except Exception as exc:
            logger.warning(f"[ImageExtractor] Vision failed for {label}: {exc}")
            descriptions.append(f"--- {label} ---\n[Vision analysis unavailable: {exc}]")

    return "\n\n".join(descriptions)


# ── PDF image extraction ──────────────────────────────────────────────────────

def _extract_images_from_pdf(file_path: str) -> list[dict]:
    """
    Extract raster images embedded inside a PDF using PyMuPDF (fitz).
    Falls back to pdfplumber page-level screenshots if PyMuPDF is not installed.
    """
    try:
        import fitz  # PyMuPDF
        return _extract_pdf_images_fitz(file_path, fitz)
    except ImportError:
        logger.warning(
            "[ImageExtractor] PyMuPDF not installed — falling back to pdfplumber page screenshots. "
            "Install with: pip install pymupdf"
        )
        return _extract_pdf_images_pdfplumber(file_path)


def _extract_pdf_images_fitz(file_path: str, fitz) -> list[dict]:
    """Use PyMuPDF to extract embedded raster images from a PDF."""
    results = []
    doc = fitz.open(file_path)

    for page_num, page in enumerate(doc, start=1):
        image_list = page.get_images(full=True)
        for img_index, img_ref in enumerate(image_list, start=1):
            xref = img_ref[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                ext = base_image["ext"]  # 'png', 'jpeg', etc.

                if len(image_bytes) < MIN_IMAGE_SIZE_BYTES:
                    continue  # skip tiny icons / decorations

                results.append({
                    "data": image_bytes,
                    "media_type": _ext_to_media_type(f".{ext}"),
                    "label": f"Image {len(results)+1} (page {page_num}, img {img_index})",
                })
            except Exception as exc:
                logger.debug(f"[ImageExtractor] Could not extract xref {xref}: {exc}")

    doc.close()
    return results


def _extract_pdf_images_pdfplumber(file_path: str) -> list[dict]:
    """
    Fallback: render each PDF page as a PNG screenshot using pdfplumber.
    Only useful when pages contain meaningful visuals (diagrams, wireframes).
    """
    try:
        import pdfplumber
    except ImportError:
        logger.warning("[ImageExtractor] pdfplumber not available either — skipping PDF images")
        return []

    results = []
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            try:
                # Render page to PIL Image
                pil_img = page.to_image(resolution=120).original
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                image_bytes = buf.getvalue()

                if len(image_bytes) < MIN_IMAGE_SIZE_BYTES:
                    continue

                results.append({
                    "data": image_bytes,
                    "media_type": "image/png",
                    "label": f"Page {page_num} Screenshot",
                })
            except Exception as exc:
                logger.debug(f"[ImageExtractor] Page {page_num} screenshot failed: {exc}")

    return results


# ── DOCX image extraction ─────────────────────────────────────────────────────

def _extract_images_from_docx(file_path: str) -> list[dict]:
    """
    Extract embedded images from a DOCX file (which is a ZIP archive).
    Images live in word/media/ inside the zip.
    """
    import zipfile

    results = []
    SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}

    try:
        with zipfile.ZipFile(file_path, "r") as z:
            media_files = [
                name for name in z.namelist()
                if name.startswith("word/media/") and
                os.path.splitext(name)[1].lower() in SUPPORTED_EXTS
            ]

            for idx, media_path in enumerate(sorted(media_files), start=1):
                image_bytes = z.read(media_path)
                if len(image_bytes) < MIN_IMAGE_SIZE_BYTES:
                    continue

                ext = os.path.splitext(media_path)[1].lower()
                results.append({
                    "data": image_bytes,
                    "media_type": _ext_to_media_type(ext),
                    "label": f"Image {idx} ({os.path.basename(media_path)})",
                })

    except Exception as exc:
        logger.warning(f"[ImageExtractor] DOCX image extraction failed: {exc}")

    return results


# ── AI Vision ─────────────────────────────────────────────────────────────────

import httpx

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
        timeout=120.0,
    )

def _describe_image(image_bytes: bytes, media_type: str) -> str:
    """
    Send an image to the configured AI vision model and return a text description.
    Tries Claude first if AI_PROVIDER=claude, otherwise GPT-4o / Azure GPT-4o.
    """
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    provider = os.getenv("AI_PROVIDER", "claude").lower()

    if provider == "claude":
        return _claude_vision(image_b64, media_type)
    elif provider == "azure_openai":
        return _openai_vision(image_b64, media_type, use_azure=True)
    else:
        return _openai_vision(image_b64, media_type, use_azure=False)


def _claude_vision(image_b64: str, media_type: str) -> str:
    """Describe image using Anthropic Claude (claude-3-5-sonnet vision)."""
    import anthropic

    http_client = _get_robust_http_client()
    client = anthropic.Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        http_client=http_client,
    )
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=600,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )
    return message.content[0].text.strip()


def _openai_vision(image_b64: str, media_type: str, use_azure: bool = False) -> str:
    """Describe image using OpenAI or Azure OpenAI GPT-4o vision."""
    http_client = _get_robust_http_client()
    if use_azure:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            http_client=http_client,
            max_retries=1,
        )
        model = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    else:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            http_client=http_client,
            max_retries=1,
        )
        model = "gpt-4o"
   
    response = client.chat.completions.create(
        model=model,
        max_completion_tokens=600,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )
    return response.choices[0].message.content.strip()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ext_to_media_type(ext: str) -> str:
    """Map a file extension to an IANA media type string."""
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }.get(ext.lower(), "image/png")
