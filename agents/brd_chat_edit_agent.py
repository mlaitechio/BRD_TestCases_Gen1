"""
BRD Chat Edit Agent

Two-phase AI pipeline that lets a user update the ENTIRE BRD through a
single natural-language instruction typed in the chat box.

Phase 1 — Section Router
  A lightweight AI call reads the instruction + BRD section map and returns
  a JSON list of which sections to update and why.

Phase 2 — Parallel Section Rewrite
  For each identified section, calls the existing edit_brd_section() function
  from section_edit_agent.py to produce the new content.

The caller receives:
  - updated_brd: full BRD dict with changes applied
  - changes_summary: list of {section, change_description} applied
  - unchanged_sections: sections the AI decided did not need updating

Usage:
    from agents.brd_chat_edit_agent import apply_chat_instruction_to_brd

    result = apply_chat_instruction_to_brd(
        instruction="Add GDPR compliance requirements to all relevant sections",
        current_brd=brd_dict,
        project_context=project.extracted_text,
    )
    updated_brd = result['updated_brd']
    changes     = result['changes_summary']
"""

import json
import logging
from agents.base import generate_json, generate
from agents.section_edit_agent import edit_brd_section

logger = logging.getLogger(__name__)

# ─── Section Router System Prompt ─────────────────────────────────────────────

ROUTER_SYSTEM_PROMPT = """You are a senior business analyst.

You will receive:
1. A user instruction describing changes they want made to a BRD
2. A map of the current BRD sections (key → brief excerpt)

Your task is to decide WHICH sections need to be updated to fulfil the instruction.

Rules:
- Only include sections that are genuinely relevant to the instruction
- Do NOT include sections just to be thorough — only include ones that need real changes
- For each section, write a specific rewrite instruction for that section
- Return ONLY valid JSON — no markdown, no explanation

Required JSON format:
{
  "sections_to_update": [
    {
      "section_key": "executive_summary",
      "rewrite_instruction": "Specific instruction for what to change in this section"
    }
  ],
  "unchanged_sections": ["project_scope", "glossary"],
  "reasoning": "One sentence explaining your selection"
}"""


# ─── Public API ────────────────────────────────────────────────────────────────

def apply_chat_instruction_to_brd(
    instruction: str,
    current_brd: dict,
    project_context: str = '',
) -> dict:
    """
    Apply a natural-language instruction to the entire BRD.

    Phase 1: Identify which sections need updating (lightweight router call).
    Phase 2: Rewrite each identified section using section_edit_agent.

    Args:
        instruction: The user's natural language change request.
                     E.g. "Add GDPR compliance notes throughout"
        current_brd: The full BRD structured JSON (all sections).
        project_context: Optional project description for grounding.

    Returns:
        dict with keys:
          - updated_brd (dict): Full BRD with all changes applied
          - changes_summary (list): [{section_key, original_instruction, status}]
          - unchanged_sections (list): Section keys not modified
          - sections_updated_count (int): Number of sections that changed

    Raises:
        RuntimeError: If the AI API call fails.
        ValueError: If no sections were identified or the response cannot be parsed.
    """
    logger.info(f'[BRDChatEdit] Applying instruction: "{instruction[:100]}..."')

    # ── Phase 1: Route — identify affected sections ────────────────────────────
    router_result = _identify_sections(instruction, current_brd)
    sections_to_update = router_result.get('sections_to_update', [])
    unchanged_sections = router_result.get('unchanged_sections', [])

    logger.info(
        f'[BRDChatEdit] Router identified {len(sections_to_update)} sections to update: '
        f'{[s["section_key"] for s in sections_to_update]}'
    )

    if not sections_to_update:
        logger.info('[BRDChatEdit] No sections identified — instruction may not apply to this BRD')
        return {
            'updated_brd': current_brd,
            'changes_summary': [],
            'unchanged_sections': list(current_brd.keys()),
            'sections_updated_count': 0,
            'router_reasoning': router_result.get('reasoning', ''),
            'message': (
                'The AI determined no sections need updating for this instruction. '
                'Try being more specific, or use the section-level edit for targeted changes.'
            ),
        }

    # ── Phase 2: Rewrite each identified section ───────────────────────────────
    updated_brd = dict(current_brd)  # Shallow copy — we'll replace individual keys
    changes_summary = []
    failed_sections = []

    for item in sections_to_update:
        section_key = item.get('section_key', '')
        rewrite_instruction = item.get('rewrite_instruction', instruction)

        # Skip if the section doesn't exist in the current BRD
        if section_key not in current_brd:
            logger.warning(f'[BRDChatEdit] Section "{section_key}" not found in BRD — skipping')
            failed_sections.append({
                'section_key': section_key,
                'status': 'skipped',
                'reason': 'Section key not found in current BRD',
            })
            continue

        logger.info(f'[BRDChatEdit] Rewriting section: "{section_key}"')

        try:
            new_content = edit_brd_section(
                section_key=section_key,
                current_content=current_brd[section_key],
                edit_instructions=rewrite_instruction,
                project_context=project_context,
            )
            updated_brd[section_key] = new_content
            changes_summary.append({
                'section_key': section_key,
                'instruction_applied': rewrite_instruction,
                'status': 'updated',
            })
            logger.info(f'[BRDChatEdit] Section "{section_key}" updated successfully')

        except (ValueError, RuntimeError) as e:
            logger.error(f'[BRDChatEdit] Failed to rewrite section "{section_key}": {e}')
            failed_sections.append({
                'section_key': section_key,
                'status': 'failed',
                'reason': str(e),
            })

    # ── Return consolidated result ─────────────────────────────────────────────
    return {
        'updated_brd': updated_brd,
        'changes_summary': changes_summary,
        'failed_sections': failed_sections,
        'unchanged_sections': unchanged_sections,
        'sections_updated_count': len(changes_summary),
        'router_reasoning': router_result.get('reasoning', ''),
        'message': _build_summary_message(changes_summary, failed_sections, unchanged_sections),
    }


# ─── Phase 1: Section Router ──────────────────────────────────────────────────

def _identify_sections(instruction: str, current_brd: dict) -> dict:
    """
    Use a lightweight AI call to determine which BRD sections need updating.

    Returns the router JSON with sections_to_update, unchanged_sections, reasoning.
    """
    # Build a compact section map — key + first 150 chars of content
    section_map = {}
    for key, value in current_brd.items():
        if isinstance(value, str):
            section_map[key] = value[:150] + ('...' if len(value) > 150 else '')
        elif isinstance(value, list):
            count = len(value)
            preview = json.dumps(value[:2], ensure_ascii=False)[:150]
            section_map[key] = f'[{count} items] {preview}...'
        elif isinstance(value, dict):
            preview = json.dumps(value, ensure_ascii=False)[:150]
            section_map[key] = f'{{dict}} {preview}...'
        else:
            section_map[key] = str(value)[:150]

    user_prompt = f"""User Instruction:
"{instruction}"

Current BRD Section Map (key: excerpt):
{json.dumps(section_map, indent=2)}

Identify which sections need updating to fulfil this instruction.
Return the JSON with sections_to_update, unchanged_sections, and reasoning."""

    try:
        return generate_json(ROUTER_SYSTEM_PROMPT, user_prompt)
    except (ValueError, RuntimeError) as e:
        logger.error(f'[BRDChatEdit] Router phase failed: {e}')
        # Fallback: return all sections for updating if router fails
        return {
            'sections_to_update': [
                {'section_key': k, 'rewrite_instruction': instruction}
                for k in current_brd.keys()
            ],
            'unchanged_sections': [],
            'reasoning': 'Router failed — applying instruction to all sections as fallback',
        }


# ─── Summary Message Builder ──────────────────────────────────────────────────

def _build_summary_message(
    changes: list,
    failed: list,
    unchanged: list,
) -> str:
    """Build a human-readable summary of what the operation did."""
    parts = []
    if changes:
        section_names = ', '.join(f'"{c["section_key"].replace("_", " ").title()}"' for c in changes)
        parts.append(f'Updated {len(changes)} section(s): {section_names}.')
    if failed:
        parts.append(f'{len(failed)} section(s) could not be updated.')
    if not changes and not failed:
        parts.append('No sections were updated — the instruction may not apply to this BRD.')
    return ' '.join(parts)
