"""
AI Chat Agent

Provides an interactive AI assistant for the project workspace. Users can:
  - Ask questions about the BRD, Test Cases, Plan, or Effort
  - Request explanations of specific sections or nodes
  - Get suggestions for improving the document
  - Ask the AI to propose edits (which can then be applied via the frontend)

The agent maintains conversation history for context continuity within a session.
"""

from agents.base import generate

def generate_chat_response(
    document_type: str,
    project_description: str,
    document_data: dict | None,
    chat_history: list[dict],
    user_message: str,
) -> dict:
    """
    Generate an AI assistant response in the context of the requested project document.

    Args:
        document_type: The type of document ('brd', 'test_cases', 'plan', 'effort').
        project_description: The extracted project description text.
        document_data: The full document structured JSON (if available). Can be None.
        chat_history: List of previous turns: [{"role": "user"|"assistant", "content": "..."}]
        user_message: The current user message to respond to.

    Returns:
        dict: Parsed JSON with "content" and "proposed_edits".

    Raises:
        RuntimeError: If the AI API call fails.
    """
    import json
    import logging
    logger = logging.getLogger(__name__)

    doc_names = {
        'brd': 'Business Requirements Document (BRD)',
        'test_cases': 'Test Cases',
        'plan': 'Project Plan',
        'effort': 'Effort Estimation'
    }
    doc_name = doc_names.get(document_type, 'Document')

    system_prompt = f"""You are an expert business analyst and project manager AI assistant embedded in a 
{doc_name} workspace.

Your role is to:
1. Answer questions about the project's {doc_name}, requirements, and scope.
2. Explain individual sections or nodes, their purpose, and details.
3. Suggest improvements to the document structure or content.
4. Help the user think through edge cases, missing elements, or stakeholder concerns.
5. Draft proposed content changes when the user asks (the user can then apply them).

Behaviour rules:
- Always base your answers on the {doc_name} context provided — do not hallucinate.
- Be concise but thorough — answer the actual question directly.
- Use professional language.
- If the user asks you to edit or improve a specific section/node, provide the suggested new content in `proposed_edits`.
- For BRD, the `section_key` should be the key of the section (e.g. `executive_summary`).
- For Test Cases, Plan, or Effort, if the frontend can patch it, use an appropriate key (e.g., test case ID, phase name, or general identifier). Otherwise, use a descriptive key.
- If something is ambiguous in the {doc_name}, flag it proactively.

You MUST respond in valid JSON format matching this schema:
{{
  "content": "Your conversational response to the user",
  "proposed_edits": [
    {{
      "section_key": "exact_section_key_here",
      "updated_content": "The full revised text/data for this section or node (can be a string or JSON object depending on the original data structure)"
    }}
  ]
}}
If there are no edits to propose, return an empty list for `proposed_edits`.
"""

    # ── Build context block ────────────────────────────────────────────────────
    context_parts = []

    if project_description:
        context_parts.append(f'PROJECT DESCRIPTION:\n{project_description[:2000]}')

    if document_data:
        # Summarise document for context — avoid sending entire JSON if it's too large
        if document_type == 'brd':
            summary = {
                'executive_summary': document_data.get('executive_summary', ''),
                'project_scope': document_data.get('project_scope', {}),
                'functional_requirements': document_data.get('functional_requirements', []),
                'non_functional_requirements': document_data.get('non_functional_requirements', []),
                'business_objectives': document_data.get('business_objectives', []),
            }
        else:
            # For Test Cases, Plan, Effort, we usually send the whole JSON as they are smaller
            # We'll just truncate the string representation if it gets excessively large
            summary = document_data
            
        summary_str = json.dumps(summary, indent=2)
        if len(summary_str) > 8000:
            summary_str = summary_str[:8000] + "\n...[TRUNCATED]"
            
        context_parts.append(
            f'CURRENT {doc_name.upper()} CONTENT:\n{summary_str}'
        )
    else:
        context_parts.append(f'NOTE: The {doc_name} has not been generated yet for this project.')

    context_block = '\n\n---\n\n'.join(context_parts)

    # ── Build conversation history block ───────────────────────────────────────
    history_text = ''
    if chat_history:
        history_lines = []
        # Include only last 10 turns to avoid token overflow
        for turn in chat_history[-10:]:
            role = turn.get('role', 'user').capitalize()
            content = turn.get('content', '')
            history_lines.append(f'{role}: {content}')
        history_text = '\n\n'.join(history_lines)

    # ── Assemble full user prompt ──────────────────────────────────────────────
    user_prompt = f"""{context_block}

---

CONVERSATION HISTORY:
{history_text or '(No previous messages)'}

---

USER MESSAGE:
{user_message}

Please provide a helpful, accurate, and concise response based on the project context above."""

    try:
        raw_response = generate(system_prompt, user_prompt)
        # Extract JSON if it's wrapped in markdown
        if '```json' in raw_response:
            json_str = raw_response.split('```json')[1].split('```')[0].strip()
        elif '```' in raw_response:
            json_str = raw_response.split('```')[1].split('```')[0].strip()
        else:
            json_str = raw_response.strip()
            
        parsed = json.loads(json_str)
        return parsed
    except json.JSONDecodeError as e:
        logger.error(f'Failed to parse JSON from chat agent: {e}\nRaw: {raw_response}')
        # Fallback
        return {
            "content": raw_response,
            "proposed_edits": []
        }
    except Exception as e:
        logger.error(f'Error generating chat response: {e}')
        raise RuntimeError(str(e))
