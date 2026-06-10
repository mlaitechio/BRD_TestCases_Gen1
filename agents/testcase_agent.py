"""
Test Case Agent

Generates structured test cases directly linked to functional requirements from the BRD.
Maintains full traceability between requirements and test cases.
"""

from agents.base import generate_json

SYSTEM_PROMPT = """You are a senior QA engineer and test architect.

Your task is to generate comprehensive test cases from the functional requirements in a BRD.

Rules:
- Every functional requirement must have at least 2 test cases (happy path + edge case).
- Each test case must be directly linked to a requirement ID (e.g., FR-001).
- Include both positive and negative test cases.
- Test cases must be actionable and specific — not vague.
- Include acceptance test cases that mirror the acceptance criteria in the BRD.
- CRITICAL: ONLY generate test cases for a MAXIMUM of the top 3 functional requirements. Do NOT generate more than 6 test cases total.
- CRITICAL: Keep test steps to an absolute maximum of 4 steps per test case.
- Be concise in your test steps to ensure the entire output stays under 8000 tokens.

IMPORTANT: Return ONLY valid JSON. No markdown, no preamble.

Required JSON format:
{
  "test_summary": {
    "total_test_cases": 0,
    "coverage_percentage": "X% of functional requirements covered",
    "test_categories": {
      "functional": 0,
      "integration": 0,
      "edge_case": 0,
      "negative": 0,
      "acceptance": 0
    }
  },
  
  "test_cases": [
    {
      "test_id": "TC-001",
      "linked_requirement": "FR-001",
      "title": "...",
      "type": "Functional|Integration|Edge Case|Negative|Acceptance",
      "priority": "High|Medium|Low",
      "preconditions": ["..."],
      "test_steps": [
        {
          "step": 1,
          "action": "...",
          "expected_result": "..."
        }
      ],
      "expected_outcome": "...",
      "pass_criteria": "..."
    }
  ],
  
  "traceability_matrix": [
    {
      "requirement_id": "FR-001",
      "requirement_title": "...",
      "linked_test_cases": ["TC-001", "TC-002"],
      "coverage_status": "Covered|Partially Covered|Not Covered"
    }
  ]
}"""


def generate_test_cases(brd_output: dict, context_summary: str | None = None, application_type: str | None = None) -> dict:
    """
    Generate test cases from BRD functional requirements.

    Args:
        brd_output: The full structured BRD JSON from the BRD agent.
        context_summary: Optional active project asset context for prompt injection.
        application_type: Optional application type (e.g. salesforce, jira) to guide test categories.

    Returns:
        dict: Test cases with full traceability matrix.

    Raises:
        ValueError: If the AI response cannot be parsed as JSON.
        RuntimeError: If the AI API call fails.
    """
    import json

    functional_requirements = brd_output.get('functional_requirements', [])

    context_section = f'\n\n{context_summary}' if context_summary and context_summary.strip() else ''
    
    app_directive = ""
    if application_type:
        app_directive = f"\n\nCRITICAL: The target application is {application_type.upper()}. Ensure test categories and specific test scenarios include relevant application-specific testing (e.g., Salesforce Profile & Permission Testing, Jira Screen Configuration Testing)."

    user_prompt = f"""Generate comprehensive test cases for these functional requirements:

{json.dumps(functional_requirements, indent=2)}

Project Context: {brd_output.get('executive_summary', '')}{context_section}{app_directive}

Generate test cases with full traceability to requirement IDs."""

    return generate_json(SYSTEM_PROMPT, user_prompt)
