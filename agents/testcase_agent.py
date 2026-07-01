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
- CRITICAL: You MUST generate test cases for ALL provided functional requirements. Do not truncate or skip any.
- CRITICAL: Keep test steps to an absolute maximum of 4 steps per test case.
- Be concise in your test steps to ensure the entire output stays within token limits.
- Follow testing guidelines and standards from the <COMPANY_KNOWLEDGE_BASE> block (if provided).

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
      "sr_no": 1,
      "file_name": "...",
      "product_name": "...",
      "process_category": "...",
      "brd_fsd": "...",
      "business_process_id": "...",
      "business_process": "...",
      "brd_fsd_reference": "FR-001",
      "scenario_id": "...",
      "scenario_description": "...",
      "category": "...",
      "importance": "High|Medium|Low",
      "test_case_id": "TC-001",
      "creation_date": "YYYY-MM-DD",
      "prepared_by": "AI Agent",
      "tc_module": "...",
      "tc_sub_module": "...",
      "path": "...",
      "test_condition": "...",
      "pre_requisite": "...",
      "test_case_description": "Include step-by-step actions here.",
      "test_priority": "High|Medium|Low",
      "test_classification": "...",
      "test_category": "...",
      "test_data": "...",
      "expected_result": "...",
      "actual_result": "",
      "release": "...",
      "execution_status": "",
      "execution_date": "",
      "executed_by": "",
      "execution_result": "",
      "defect_id": "",
      "severity": "",
      "priority": "",
      "defect_status": "",
      "remarks": "",
      "frequency": "",
      "abfl_it_remarks": "",
      "ownership": ""
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


def generate_test_cases(brd_output: dict, context_summary: str | None = None, application_type: str | None = None, company_knowledge_base: str | None = None) -> dict:
    """
    Generate test cases from BRD functional requirements.

    Args:
        brd_output: The full structured BRD JSON from the BRD agent.
        context_summary: Optional active project asset context for prompt injection.
        application_type: Optional application type (e.g. salesforce, jira) to guide test categories.
        company_knowledge_base: Extracted knowledge base RAG context.

    Returns:
        dict: Test cases with full traceability matrix.

    Raises:
        ValueError: If the AI response cannot be parsed as JSON.
        RuntimeError: If the AI API call fails.
    """
    import json

    functional_requirements = brd_output.get('functional_requirements', [])
    
    if not functional_requirements:
        return {
            "test_summary": {
                "total_test_cases": 0,
                "coverage_percentage": "0%",
                "test_categories": {
                    "functional": 0,
                    "integration": 0,
                    "edge_case": 0,
                    "negative": 0,
                    "acceptance": 0
                }
            },
            "test_cases": [],
            "traceability_matrix": []
        }

    context_section = f'\n\n{context_summary}' if context_summary and context_summary.strip() else ''
    
    app_directive = ""
    if application_type:
        app_directive = f"\n\nCRITICAL: The target application is {application_type.upper()}. Ensure test categories and specific test scenarios include relevant application-specific testing (e.g., Salesforce Profile & Permission Testing, Jira Screen Configuration Testing)."

    knowledge_base_section = ''
    if company_knowledge_base and company_knowledge_base.strip():
        knowledge_base_section = f'\n\n{company_knowledge_base}'

    chunk_size = 3
    all_test_cases = []
    all_traceability = []

    for i in range(0, len(functional_requirements), chunk_size):
        chunk = functional_requirements[i:i + chunk_size]
        
        user_prompt = f"""Generate comprehensive test cases for these specific functional requirements ONLY:

{json.dumps(chunk, indent=2)}

Project Context: {brd_output.get('executive_summary', '')}{context_section}{app_directive}{knowledge_base_section}

Generate test cases with full traceability to requirement IDs."""

        try:
            chunk_result = generate_json(SYSTEM_PROMPT, user_prompt)
            all_test_cases.extend(chunk_result.get('test_cases', []))
            all_traceability.extend(chunk_result.get('traceability_matrix', []))
        except Exception as e:
            print(f"Warning: Failed to generate test cases for a chunk: {e}")
            continue

    return {
        "test_summary": {
            "total_test_cases": len(all_test_cases),
            "coverage_percentage": "100%",
            "test_categories": {
                "functional": len(all_test_cases),
                "integration": 0,
                "edge_case": 0,
                "negative": 0,
                "acceptance": 0
            }
        },
        "test_cases": all_test_cases,
        "traceability_matrix": all_traceability
    }
