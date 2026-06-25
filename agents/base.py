"""
AI Provider Abstraction Layer.

Reads AI_PROVIDER from .env:
  - AI_PROVIDER=claude          → Anthropic claude-sonnet
  - AI_PROVIDER=openai          → OpenAI gpt-4o
  - AI_PROVIDER=azure_openai    → Azure OpenAI (enterprise / production)

All agents import only from this module. Switch AI providers by changing
one environment variable — no code changes required.
"""

import os
import json
import re
import ssl
import warnings
from dotenv import load_dotenv

# ==============================================================================
# GLOBAL SSL VERIFICATION DISABLE (Bypass Enterprise Proxy & IP Mismatch)
# ==============================================================================
try:
    if hasattr(ssl, '_create_unverified_context'):
        ssl._create_default_https_context = ssl._create_unverified_context
    def _custom_unverified_context(*args, **kwargs):
        ctx = ssl._create_unverified_context(*args, **kwargs)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    ssl.create_default_context = _custom_unverified_context
except Exception:
    pass

os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
warnings.filterwarnings('ignore')
# ==============================================================================

load_dotenv()

AI_PROVIDER = os.getenv('AI_PROVIDER', 'claude').lower()

# ── Claude config ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
CLAUDE_MODEL = 'claude-sonnet-4-5'
CLAUDE_MAX_TOKENS = 8192

# ── OpenAI config ──────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = 'gpt-4o'
OPENAI_MAX_TOKENS = 8192

# ── Azure OpenAI config ────────────────────────────────────────────────────────
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '')
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY', '')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01')
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-4o')
AZURE_OPENAI_MAX_TOKENS = 8192


# ─── Public API ───────────────────────────────────────────────────────────────

def generate(system_prompt: str, user_prompt: str, model_override: str = None) -> str:
    """
    Send a prompt to the configured AI provider and return the raw text response.

    Args:
        system_prompt: Instructions / persona for the AI.
        user_prompt: The actual task / content to process.
        model_override: Optional specific model or deployment name to use for this call (e.g., a cheaper model).

    Returns:
        str: Raw text response from the AI model.

    Raises:
        RuntimeError: If the AI call fails or returns an empty response.
    """
    if AI_PROVIDER == 'claude':
        return _call_claude(system_prompt, user_prompt, model_override)
    elif AI_PROVIDER == 'openai':
        return _call_openai(system_prompt, user_prompt, model_override)
    elif AI_PROVIDER == 'azure_openai':
        return _call_azure_openai(system_prompt, user_prompt, model_override)
    else:
        raise RuntimeError(
            f"Unknown AI_PROVIDER: '{AI_PROVIDER}'. "
            "Set to 'claude', 'openai', or 'azure_openai' in .env"
        )


def generate_json(system_prompt: str, user_prompt: str, model_override: str = None) -> dict:
    """
    Call the AI and parse the response as JSON.

    Handles common issues:
    - Strips ```json ... ``` fences Claude or OpenAI sometimes wrap output in
    - Tries to find the JSON object if there is surrounding text
    - Falls back gracefully with error context

    Args:
        system_prompt: Instructions / persona for the AI.
        user_prompt: The actual task / content to process.
        model_override: Optional specific model or deployment name to use for this call.

    Returns:
        dict: Parsed JSON response.

    Raises:
        ValueError: If the response cannot be parsed as valid JSON.
    """
    raw = generate(system_prompt, user_prompt, model_override)
    return _parse_json(raw)


# ─── JSON Parser ──────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> dict:
    """Clean and parse a JSON string from AI output."""
    if not raw or not raw.strip():
        raise ValueError("AI response was completely empty. This usually happens if the BRD has no content or the AI model blocked the response (e.g. content filters).")

    # Strip markdown code fences
    cleaned = raw.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e1:
        error1 = e1

    # Try to extract the first JSON object from the response
    match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e2:
            error2 = e2
    else:
        error2 = 'No JSON object found.'

    raise ValueError(
        f'AI response could not be parsed as JSON.\n'
        f'Error 1 (direct): {error1}\n'
        f'Error 2 (extracted): {error2}\n'
        f'Raw response (first 300 chars): {raw[:300]}\n'
        f'Raw response (last 300 chars): {raw[-300:]}'
    )


# ─── Provider Implementations ─────────────────────────────────────────────────

import os
import httpx

def _get_robust_http_client() -> httpx.Client:
    """
    Returns an invincible httpx client configured to bypass enterprise proxies,
    firewalls, WAF drops, and HTTP/2 protocol disconnects.
    """
    proxy_url = os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY', os.getenv('https_proxy', os.getenv('http_proxy', ''))))
    if proxy_url and not proxy_url.startswith(('http://', 'https://')):
        proxy_url = f'http://{proxy_url}'

    return httpx.Client(
        verify=False,
        http2=False,
        http1=True,
        proxy=proxy_url if proxy_url else None,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'},
        timeout=60.0,
    )


def _call_claude(system_prompt: str, user_prompt: str, model_override: str = None) -> str:
    """Call Anthropic Claude API."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError('anthropic package not installed. Run: pip install anthropic')

    if not ANTHROPIC_API_KEY:
        raise RuntimeError('ANTHROPIC_API_KEY is not set in .env')

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, http_client=_get_robust_http_client())

    try:
        message = client.messages.create(
            model=model_override or CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}]
        )
        return message.content[0].text
    except anthropic.APITimeoutError as e:
        raise RuntimeError(f'Claude API timeout: {e}')
    except anthropic.APIStatusError as e:
        raise RuntimeError(f'Claude API error {e.status_code}: {e.message}')
    except Exception as e:
        raise RuntimeError(f'Claude API call failed: {e}')


def _call_openai(system_prompt: str, user_prompt: str, model_override: str = None) -> str:
    """Call OpenAI API."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError('openai package not installed. Run: pip install openai')

    if not OPENAI_API_KEY:
        raise RuntimeError('OPENAI_API_KEY is not set in .env')

    client = OpenAI(api_key=OPENAI_API_KEY, http_client=_get_robust_http_client())

    try:
        response = client.chat.completions.create(
            model=model_override or OPENAI_MODEL,
            max_completion_tokens=OPENAI_MAX_TOKENS,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f'OpenAI API call failed: {e}')


def _call_azure_openai(system_prompt: str, user_prompt: str, model_override: str = None) -> str:
    """Call Azure OpenAI Service (enterprise production provider)."""
    try:
        from openai import AzureOpenAI
    except ImportError:
        raise RuntimeError('openai package not installed. Run: pip install openai')

    if not AZURE_OPENAI_API_KEY:
        raise RuntimeError('AZURE_OPENAI_API_KEY is not set in .env')
    if not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError('AZURE_OPENAI_ENDPOINT is not set in .env')

    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        http_client=_get_robust_http_client(),
    )

    try:
        response = client.chat.completions.create(
            model=model_override or AZURE_OPENAI_DEPLOYMENT_NAME,   # Deployment name in Azure OpenAI Studio
            max_completion_tokens=AZURE_OPENAI_MAX_TOKENS,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ]
        )
        
        choice = response.choices[0]
        content = choice.message.content
        if not content or not content.strip():
            finish_reason = getattr(choice, 'finish_reason', 'unknown')
            raise RuntimeError(f'Azure OpenAI returned empty content. Finish reason: {finish_reason}')
            
        return content
    except Exception as e:
        raise RuntimeError(f'Azure OpenAI API call failed: {e}')
