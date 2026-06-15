"""
Project Plan Agent

Takes the approved BRD and generates a detailed project plan with phases,
tasks, timelines, resource allocation, and risk register.
"""

from agents.base import generate_json

SYSTEM_PROMPT = """You are a senior project manager with expertise in software delivery.

Your task is to take an approved BRD and generate a detailed project plan in JSON format.

The plan must be realistic, phased, and directly traceable to the BRD requirements.
Adhere strictly to any planning guidelines, project structures, or past templates provided in the <COMPANY_KNOWLEDGE_BASE> block (if provided).

IMPORTANT: Return ONLY valid JSON. No markdown, no preamble.
CRITICAL LIMITS:
- MAXIMUM 4 phases.
- MAXIMUM 5 tasks per phase. Do NOT generate massive task lists.
- MAXIMUM 3 risks in the risk register.
- Be concise in your text descriptions to ensure the entire JSON stays well under 8000 tokens.

Required JSON format:
{
  "project_summary": "Brief overview of the project plan",
  
  "methodology": "Agile|Waterfall|Hybrid",
  
  "total_duration": "X months",
  
  "team_structure": [
    {
      "role": "...",
      "count": 1,
      "responsibilities": "..."
    }
  ],
  
  "phases": [
    {
      "phase_number": 1,
      "phase_name": "...",
      "duration": "X weeks",
      "start_week": 1,
      "end_week": 2,
      "objectives": ["..."],
      "tasks": [
        {
          "task_id": "T-001",
          "task_name": "...",
          "assignee_role": "...",
          "duration_days": 5,
          "dependencies": ["T-000"],
          "linked_requirements": ["FR-001", "FR-002"]
        }
      ],
      "deliverables": ["..."],
      "milestones": ["..."]
    }
  ],
  
  "risk_register": [
    {
      "risk_id": "R-001",
      "description": "...",
      "probability": "High|Medium|Low",
      "impact": "High|Medium|Low",
      "mitigation": "...",
      "owner": "..."
    }
  ],
  
  "communication_plan": {
    "meetings": [
      {
        "meeting_type": "...",
        "frequency": "...",
        "attendees": ["..."],
        "purpose": "..."
      }
    ],
    "reporting": "..."
  },
  
  "definition_of_done": ["criterion 1", "criterion 2"]
}"""


def generate_project_plan(brd_output: dict, context_summary: str | None = None, application_type: str | None = None, company_knowledge_base: str | None = None) -> dict:
    """
    Generate a detailed project plan from an approved BRD.

    Args:
        brd_output: The full structured BRD JSON from the BRD agent.
        context_summary: Optional active project asset context for prompt injection.
        application_type: Optional application type (e.g. salesforce, jira) to guide plan milestones.
        company_knowledge_base: Extracted knowledge base RAG context.

    Returns:
        dict: Project plan with phases, tasks, risks, and team structure.

    Raises:
        ValueError: If the AI response cannot be parsed as JSON.
        RuntimeError: If the AI API call fails.
    """
    import json

    context_section = f"\n\n{context_summary}" if context_summary and context_summary.strip() else ''
    
    app_directive = ""
    if application_type:
        app_directive = f"\n\nCRITICAL: The target application is {application_type.upper()}. Ensure project phases and milestones reflect specific activities for this application (e.g., Salesforce Org Audit & Data Model Design, or Jira Workflow Scheme Design & Screen Configuration)."

    knowledge_base_section = ''
    if company_knowledge_base and company_knowledge_base.strip():
        knowledge_base_section = f'\n\n{company_knowledge_base}'

    user_prompt = f"""Based on this approved BRD, generate a detailed project plan:

BRD Summary: {brd_output.get('executive_summary', '')}

Functional Requirements Count: {len(brd_output.get('functional_requirements', []))}

Key Requirements:
{json.dumps(brd_output.get('functional_requirements', [])[:10], indent=2)}

Project Scope:
{json.dumps(brd_output.get('project_scope', {}), indent=2)}

Business Objectives:
{json.dumps(brd_output.get('business_objectives', []), indent=2)}

Generate a comprehensive project plan.{context_section}{app_directive}{knowledge_base_section}"""

    return generate_json(SYSTEM_PROMPT, user_prompt)
