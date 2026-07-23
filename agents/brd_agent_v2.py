"""
Improved BRD Agent v2 - Multi-stage generation with better accuracy

Uses iterative refinement similar to ChatGPT/Copilot for better quality:
1. Generate detailed outline
2. Fill each section with comprehensive content
3. Add business logic and context
4. Refine and validate
"""

from agents.base import generate_json
import json

SYSTEM_PROMPT_STAGE1 = """You are a senior enterprise business analyst specializing in financial systems BRDs.

TASK: Generate a detailed outline structure for this project. Think deeply about all sections needed.

Focus on:
- What business problem does this solve?
- What are the key processes?
- What systems integrate?
- What are the compliance/regulatory needs?
- What are the success metrics?

For a Receipting/Payment Automation project, include:
1. Executive Summary (business context + problem statement)
2. Current Process & Pain Points
3. Proposed Solution & Benefits
4. Detailed Functional Requirements (minimum 8-12 FRs with acceptance criteria)
5. Non-Functional Requirements (performance, security, audit, scalability)
6. Integration Architecture (APIs, systems, data flows)
7. Business Rules & Validations
8. Error Handling & Exceptions
9. Reporting & Analytics
10. Project Phases & Timeline
11. Effort Estimation
12. Risks & Mitigation
13. Success Criteria
14. Stakeholders & Governance
15. Assumptions & Constraints

Return as JSON with brief descriptions for each section."""

SYSTEM_PROMPT_STAGE2 = """You are a senior business analyst writing a comprehensive BRD.

INSTRUCTIONS:
- Generate DETAILED, SPECIFIC requirements (not generic)
- Include real business logic from the context provided
- Add 10-12 functional requirements with actual acceptance criteria
- Make requirements SMART (Specific, Measurable, Achievable, Relevant, Time-bound)
- Include business rules, validation rules, and edge cases
- Reference actual systems and processes from the input documents
- Add metrics and targets for success
- Include compliance and regulatory requirements

CRITICAL: Extract and use specific details like:
- Actual field names and mappings
- Specific API endpoints and parameters
- Actual account numbers, business rules
- Real validation rules and error scenarios
- Actual retry logic and timing (e.g., 3-second gaps, 3-hour retries)

For Receipting Automation:
- Include loan number validation
- Include amount validation
- Include account mapping logic
- Include narration parsing rules
- Include receipt mode extraction
- Include API request/response mapping
- Include automatic and manual retry mechanisms
- Include audit logging requirements
- Include dashboard/reporting requirements

Return comprehensive JSON with ALL details."""

QUALITY_CHECKLIST = """
QUALITY VALIDATION CHECKLIST:

1. Functional Requirements:
   ✓ 10+ unique FRs with IDs (FR-001, FR-002, etc.)
   ✓ Each has title, description, priority, acceptance_criteria
   ✓ Acceptance criteria are specific and testable
   ✓ Include validation rules explicitly
   ✓ Include integration points (API, systems)

2. Business Context:
   ✓ Current state/pain points described
   ✓ Proposed solution explained
   ✓ Business benefits quantified
   ✓ Success metrics defined

3. Technical Details:
   ✓ API endpoints specified
   ✓ Field mappings included
   ✓ Integration requirements clear
   ✓ Error handling defined
   ✓ Retry logic specified

4. Completeness:
   ✓ Non-Functional Requirements (5+)
   ✓ Business Rules documented
   ✓ Assumptions & Constraints listed
   ✓ Risks & Mitigations provided
   ✓ Project phases with timelines
   ✓ Effort estimation included

5. Quality:
   ✓ No generic/template language
   ✓ Specific to the project domain
   ✓ References actual systems/APIs
   ✓ Includes real business logic
   ✓ Professional and comprehensive
"""

def generate_brd_improved(
    project_description: str,
    api_specs: str = "",
    current_process: str = "",
    business_context: str = "",
    technical_specs: str = ""
) -> dict:
    """
    Generate a comprehensive BRD using multi-stage approach.

    Args:
        project_description: Main project overview
        api_specs: API documentation and specifications
        current_process: Description of current/legacy process
        business_context: Business goals and context
        technical_specs: Technical requirements and constraints

    Returns:
        dict: Complete BRD with all sections
    """

    # Combine all context
    full_context = f"""
PROJECT DESCRIPTION:
{project_description}

CURRENT PROCESS:
{current_process}

BUSINESS CONTEXT:
{business_context}

API SPECIFICATIONS:
{api_specs}

TECHNICAL SPECIFICATIONS:
{technical_specs}
"""

    # Stage 1: Generate comprehensive outline
    outline_prompt = f"""{SYSTEM_PROMPT_STAGE1}

CONTEXT:
{full_context}

Generate a detailed section outline with descriptions. Include specific items relevant to this project.
Return as JSON with sections array."""

    # Stage 2: Generate detailed BRD
    brd_prompt = f"""{SYSTEM_PROMPT_STAGE2}

CONTEXT:
{full_context}

{QUALITY_CHECKLIST}

Generate a COMPREHENSIVE BRD with the following structure:
{{
  "executive_summary": "2-3 paragraphs about business problem, solution, and benefits",
  "current_state_analysis": "Detailed analysis of current process and pain points",
  "proposed_solution": "Description of how new system solves the problem",
  "business_objectives": [
    {{"id": "BO-001", "objective": "...", "metric": "...", "target": "..."}}
  ],
  "functional_requirements": [
    {{
      "id": "FR-001",
      "title": "...",
      "description": "...",
      "priority": "Must Have",
      "acceptance_criteria": ["criterion 1", "criterion 2", "criterion 3"],
      "business_rules": "...",
      "compliance_notes": "..."
    }}
  ],
  "non_functional_requirements": [
    {{"id": "NFR-001", "category": "Performance", "requirement": "...", "metric": "...", "priority": "Must Have"}}
  ],
  "integration_requirements": [
    {{"system": "A3S LMS", "integration_type": "API", "description": "...", "endpoints": ["..."]}}
  ],
  "business_rules_and_validations": [
    {{"rule_id": "BR-001", "rule": "...", "validation": "...", "error_handling": "..."}}
  ],
  "error_handling_and_exceptions": [
    {{"scenario": "...", "error_codes": "...", "action": "...", "retry_logic": "..."}}
  ],
  "reporting_and_analytics": [
    {{"report_name": "...", "metrics": ["..."], "frequency": "...", "users": "..."}}
  ],
  "project_phases": [
    {{"phase": "Phase 1", "duration": "X weeks", "deliverables": ["..."], "milestones": ["..."]}}
  ],
  "effort_estimation": {{"total_hours": 0, "breakdown": [{{"component": "...", "hours": 0, "complexity": "High"}}]}},
  "risks_and_mitigations": [
    {{"id": "RSK-001", "risk": "...", "probability": "High", "impact": "High", "mitigation": "..."}}
  ],
  "success_criteria": [
    {{"id": "SC-001", "criterion": "...", "measurement": "...", "target": "..."}}
  ],
  "stakeholders": [
    {{"role": "...", "responsibilities": "...", "interest": "High", "influence": "High"}}
  ],
  "assumptions_and_constraints": {{
    "assumptions": [{{"id": "ASS-001", "assumption": "...", "risk": "..."}}],
    "constraints": [{{"id": "CON-001", "constraint": "...", "impact": "..."}}]
  }},
  "glossary": [{{"term": "...", "definition": "..."}}]
}}

IMPORTANT:
- Generate MINIMUM 12 Functional Requirements (FR-001 through FR-012+)
- Each FR must have at least 3-4 acceptance criteria
- Include specific business rules and validation logic
- Reference actual API endpoints and field names
- Include retry logic, error handling, and fallback mechanisms
- Make it specific to Receipting Automation domain, NOT generic
- Include regulatory/compliance requirements if applicable
"""

    print("[Stage 1] Generating detailed outline...")
    try:
        outline_result = generate_json(
            system_prompt=SYSTEM_PROMPT_STAGE1,
            user_prompt=full_context
        )
        print("[OK] Outline generated")
    except Exception as e:
        print(f"[WARN] Outline generation partial: {e}")
        outline_result = {}

    print("[Stage 2] Generating comprehensive BRD...")
    try:
        brd_result = generate_json(
            system_prompt=SYSTEM_PROMPT_STAGE2,
            user_prompt=f"""{full_context}

{QUALITY_CHECKLIST}

Generate a COMPREHENSIVE BRD with the following structure:
{{
  "executive_summary": "2-3 paragraphs about business problem, solution, and benefits",
  "current_state_analysis": "Detailed analysis of current process and pain points",
  "proposed_solution": "Description of how new system solves the problem",
  "business_objectives": [
    {{"id": "BO-001", "objective": "...", "metric": "...", "target": "..."}}
  ],
  "functional_requirements": [
    {{
      "id": "FR-001",
      "title": "...",
      "description": "...",
      "priority": "Must Have",
      "acceptance_criteria": ["criterion 1", "criterion 2", "criterion 3"],
      "business_rules": "...",
      "compliance_notes": "..."
    }}
  ],
  "non_functional_requirements": [
    {{"id": "NFR-001", "category": "Performance", "requirement": "...", "metric": "...", "priority": "Must Have"}}
  ],
  "integration_requirements": [
    {{"system": "A3S LMS", "integration_type": "API", "description": "...", "endpoints": ["..."]}}
  ],
  "business_rules_and_validations": [
    {{"rule_id": "BR-001", "rule": "...", "validation": "...", "error_handling": "..."}}
  ],
  "error_handling_and_exceptions": [
    {{"scenario": "...", "error_codes": "...", "action": "...", "retry_logic": "..."}}
  ],
  "reporting_and_analytics": [
    {{"report_name": "...", "metrics": ["..."], "frequency": "...", "users": "..."}}
  ],
  "project_phases": [
    {{"phase": "Phase 1", "duration": "X weeks", "deliverables": ["..."], "milestones": ["..."]}}
  ],
  "effort_estimation": {{"total_hours": 0, "breakdown": [{{"component": "...", "hours": 0, "complexity": "High"}}]}},
  "risks_and_mitigations": [
    {{"id": "RSK-001", "risk": "...", "probability": "High", "impact": "High", "mitigation": "..."}}
  ],
  "success_criteria": [
    {{"id": "SC-001", "criterion": "...", "measurement": "...", "target": "..."}}
  ],
  "stakeholders": [
    {{"role": "...", "responsibilities": "...", "interest": "High", "influence": "High"}}
  ],
  "assumptions_and_constraints": {{
    "assumptions": [{{"id": "ASS-001", "assumption": "...", "risk": "..."}}],
    "constraints": [{{"id": "CON-001", "constraint": "...", "impact": "..."}}]
  }},
  "glossary": [{{"term": "...", "definition": "..."}}]
}}

IMPORTANT:
- Generate MINIMUM 12 Functional Requirements (FR-001 through FR-012+)
- Each FR must have at least 3-4 acceptance criteria
- Include specific business rules and validation logic
- Reference actual API endpoints and field names
- Include retry logic, error handling, and fallback mechanisms
- Make it specific to Receipting Automation domain, NOT generic
- Include regulatory/compliance requirements if applicable
"""
        )
        print("[OK] BRD generated")
    except Exception as e:
        print(f"[WARN] BRD generation failed: {e}")
        brd_result = {}

    # Validate quality
    print("[Validate] Checking BRD quality...")
    quality_issues = validate_brd_quality(brd_result)

    if quality_issues:
        print("[WARN] Quality issues found:")
        for issue in quality_issues:
            print(f"  - {issue}")
    else:
        print("[OK] Quality validation passed")

    return {
        "brd": brd_result,
        "quality_issues": quality_issues,
        "metadata": {
            "version": "2.0-improved",
            "generation_method": "multi-stage-iterative",
            "model": "gpt-4o"
        }
    }


def validate_brd_quality(brd: dict) -> list:
    """Validate BRD has minimum quality standards"""
    issues = []

    # Check functional requirements
    frs = brd.get("functional_requirements", [])
    if len(frs) < 10:
        issues.append(f"Only {len(frs)} functional requirements (need 10+)")

    for fr in frs:
        if not fr.get("acceptance_criteria") or len(fr.get("acceptance_criteria", [])) < 2:
            issues.append(f"FR {fr.get('id')} missing detailed acceptance criteria")

    # Check business objectives
    bos = brd.get("business_objectives", [])
    if len(bos) < 3:
        issues.append(f"Only {len(bos)} business objectives (need 3+)")

    # Check NFRs
    nfrs = brd.get("non_functional_requirements", [])
    if len(nfrs) < 5:
        issues.append(f"Only {len(nfrs)} non-functional requirements (need 5+)")

    # Check completeness
    required_sections = [
        "executive_summary",
        "functional_requirements",
        "non_functional_requirements",
        "integration_requirements",
        "effort_estimation",
        "success_criteria",
        "assumptions_and_constraints"
    ]

    for section in required_sections:
        if section not in brd or not brd[section]:
            issues.append(f"Missing or empty section: {section}")

    return issues
