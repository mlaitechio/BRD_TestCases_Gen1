"""
Relevance Evaluation Agent

Evaluates whether an uploaded document is relevant for the corporate Knowledge Base
to be used for BRD generation and Test Case generation.
"""

import os
from agents.base import generate_json

SYSTEM_PROMPT = """You are a Data Quality AI for a corporate Knowledge Base.

Your job is to determine if a document is relevant to be stored in a vector database 
used by an AI to generate Business Requirement Documents (BRDs) and Test Cases.

Relevant documents include:
- Existing BRDs or Functional Specification Documents (FSDs)
- UI/UX Guidelines or design standards
- API Documentation and technical specifications
- Coding, Testing, and Quality Assurance standards
- Test cases, test scenarios, or traceability matrices
- Project plans or executive summaries detailing software features

Irrelevant documents include:
- HR policies, lunch menus, casual chat logs
- Financial data, highly technical server crash logs, or completely unrelated files
- Raw code files without descriptive context (unless they are explicitly documentation)

Review the following document snippet (which may be truncated).

Return a JSON object with:
- "is_relevant": true or false
- "reason": A brief 1-sentence explanation of why it is relevant or not.

Required JSON format:
{
  "is_relevant": true,
  "reason": "..."
}
"""

def evaluate_document_relevance(document_text: str) -> dict:
    """
    Evaluate if a document is relevant for the Knowledge Base.

    Args:
        document_text: The first few thousand characters of the document.

    Returns:
        dict: containing "is_relevant" (bool) and "reason" (str)
    """
    user_prompt = f"Document Snippet:\n\n{document_text}"
    
    # Use a cheaper model (e.g. gpt-4o-mini) for simple summary-level tasks if configured
    cheap_model = os.getenv('CHEAP_MODEL_DEPLOYMENT_NAME')
    return generate_json(SYSTEM_PROMPT, user_prompt, model_override=cheap_model)
