"""
Clarification Agent

Reads the project description and generates 3-5 targeted clarifying questions
that a business analyst would ask before writing a BRD.

Returns a structured JSON list of questions all at once.
The frontend renders them as a form; the user submits all answers together.
"""

from agents.base import generate_json

SYSTEM_PROMPT = """You are a senior business analyst with 15 years of experience writing 
Business Requirements Documents (BRDs) for enterprise software projects.

Your task is to read a project description and generate exactly 3 to 5 targeted clarifying 
questions that you would ask a stakeholder BEFORE writing the BRD.

Focus on questions that uncover:
- The primary users and their pain points
- Must-have vs nice-to-have features
- Integration or compliance requirements not mentioned
- Business success metrics
- Scope boundaries (what is explicitly OUT of scope)

IMPORTANT: Return ONLY valid JSON. No markdown, no preamble, no explanation.

Required JSON format:
{
  "questions": [
    {
      "id": "Q1",
      "question": "...",
      "why_asking": "Brief reason why this answer is needed to write the BRD"
    },
    ...
  ]
}"""


def generate_clarification_questions(project_description: str) -> dict:
    """
    Generate 3-5 clarifying questions for the given project description.

    Args:
        project_description: The raw text describing the project.

    Returns:
        dict with key 'questions' containing a list of question objects.

    Raises:
        ValueError: If the AI response cannot be parsed.
        RuntimeError: If the AI API call fails.
    """
    user_prompt = f"""Project Description:
{project_description}

Generate 3-5 clarifying questions for this project."""

    return generate_json(SYSTEM_PROMPT, user_prompt)
