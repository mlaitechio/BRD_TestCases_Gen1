"""
Document Edit Agent

Provides AI-driven full document rewrites for smaller JSON documents
like Test Cases, Project Plans, and Effort Estimations.
Unlike the BRD (which uses a router to update specific sections), 
these documents are rewritten entirely in a single pass to ensure consistency.
"""

from agents.base import generate_json

def edit_document_full(document_type: str, document_data: dict, instruction: str) -> dict:
    """
    Rewrite the entire document based on the user's natural language instruction.
    
    Args:
        document_type: 'test_cases', 'plan', or 'effort'
        document_data: The current full JSON of the document.
        instruction: The user's instruction (e.g., "Add more edge cases", "Include a UAT phase").
        
    Returns:
        dict: The completely rewritten document in its original schema format.
    """
    import json
    import logging
    logger = logging.getLogger(__name__)

    doc_names = {
        'test_cases': 'Test Cases',
        'plan': 'Project Plan',
        'effort': 'Effort Estimation'
    }
    doc_name = doc_names.get(document_type, 'Document')

    system_prompt = f"""You are an expert business analyst and project manager AI assistant.

Your task is to rewrite an entire {doc_name} document based on a user's instruction.
The provided document is in JSON format. You MUST return the entirely updated document in the EXACT same JSON schema structure as the original.
Ensure all previous information is preserved unless the instruction explicitly requires removing or changing it.

Rules:
- Apply the user's instructions thoroughly across the entire document.
- Ensure the output is ONLY valid JSON.
- Do not wrap the JSON in Markdown or include any preamble.
- Preserve the exact JSON keys and structure of the original document.
"""

    user_prompt = f"""CURRENT {doc_name.upper()} JSON:
{json.dumps(document_data, indent=2)}

---

USER INSTRUCTION:
{instruction}

---

Please provide the FULL rewritten JSON document matching the original schema structure, incorporating the instruction above."""

    try:
        updated_data = generate_json(system_prompt, user_prompt)
        return updated_data
    except Exception as e:
        logger.error(f"Error in edit_document_full for {document_type}: {e}")
        raise RuntimeError(f"Failed to edit {doc_name}: {e}")
