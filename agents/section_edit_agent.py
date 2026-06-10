"""
BRD Section Edit Agent

Rewrites a single section of the BRD based on natural language instructions.
Used by the AI-Assisted Edit feature in the document workspace.

The agent receives:
  - The section key (e.g. 'executive_summary')
  - The current section content (already in the BRD)
  - The user's editing instructions
  - Project context for grounding

It returns the new section content in the same format as the original
(string for text sections, list for list sections, dict for structured sections).
"""

import json
import logging
from agents.base import generate

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior business analyst and technical writer.

Your task is to rewrite a specific section of a Business Requirements Document (BRD) 
based on editing instructions from the user.

Rules:
- Return ONLY the new content for this section — nothing else
- Maintain the exact same data type and structure as the original section
  (if original was a string, return a string; if a list, return a JSON array; if a dict, return a JSON object)
- Apply the user's instructions precisely
- Keep the professional BRD tone and style
- Return ONLY valid JSON — no markdown fences, no preamble, no explanation
- The returned JSON should be exactly the value for this section key
"""


def edit_brd_section(
    section_key: str,
    current_content,
    edit_instructions: str,
    project_context: str = '',
) -> object:
    """
    Rewrite a specific BRD section based on editing instructions.

    Args:
        section_key: The JSON field key of the section to edit (e.g. 'executive_summary').
        current_content: The current value of this section (str, list, or dict).
        edit_instructions: Natural language instructions from the user.
        project_context: Optional project description for grounding.

    Returns:
        The new section content in the same structure as current_content.

    Raises:
        ValueError: If the AI response cannot be parsed into the expected format.
        RuntimeError: If the AI API call fails.
    """
    # Determine expected output type
    content_type = type(current_content).__name__
    current_json = json.dumps(current_content, indent=2) if not isinstance(current_content, str) else current_content

    context_block = ''
    if project_context:
        context_block = f'\nProject Context (for grounding):\n{project_context[:1500]}\n'

    user_prompt = f"""Section to Edit: "{section_key}"
Expected output type: {content_type} (return the same type)

Current Content:
{current_json}

User Instructions:
{edit_instructions}
{context_block}
Return the complete new content for this section only, as valid JSON (matching the original type)."""

    logger.info(f'[SectionEdit] Editing section "{section_key}" — instructions: {edit_instructions[:100]}...')

    raw_response = generate(SYSTEM_PROMPT, user_prompt)

    # Parse the response — must match the original type
    return _parse_section_response(raw_response, current_content, section_key)


def _parse_section_response(raw: str, original, section_key: str):
    """
    Parse the AI response into the same type as the original section content.
    Falls back to returning the raw string if parsing fails.
    """
    import re

    cleaned = raw.strip()
    # Strip markdown fences
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    # If original was a plain string, return as-is (no JSON parsing needed)
    if isinstance(original, str):
        return cleaned

    # Otherwise parse as JSON
    try:
        parsed = json.loads(cleaned)
        # Validate type matches
        if isinstance(original, list) and not isinstance(parsed, list):
            logger.warning(f'[SectionEdit] Expected list for "{section_key}", got {type(parsed).__name__}')
        elif isinstance(original, dict) and not isinstance(parsed, dict):
            logger.warning(f'[SectionEdit] Expected dict for "{section_key}", got {type(parsed).__name__}')
        return parsed
    except json.JSONDecodeError:
        # Try to find JSON structure in the response
        if isinstance(original, list):
            match = re.search(r'\[.*\]', cleaned, re.DOTALL)
        else:
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)

        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

    logger.warning(
        f'[SectionEdit] Could not parse AI response as JSON for section "{section_key}". '
        f'Returning raw text.'
    )
    raise ValueError(
        f'AI response for section "{section_key}" could not be parsed.\n'
        f'Raw response (first 500 chars): {raw[:500]}'
    )
