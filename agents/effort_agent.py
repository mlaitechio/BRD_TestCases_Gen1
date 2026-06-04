"""
Effort Estimation Agent

Takes the BRD and project plan and generates a detailed effort estimation
broken down by role, phase, and feature area.
"""

from agents.base import generate_json

SYSTEM_PROMPT = """You are a senior software delivery manager with expertise in effort estimation.

Your task is to generate a detailed effort estimation from the BRD and project plan.

Use industry-standard estimation techniques:
- Function Point Analysis for functional complexity
- T-shirt sizing for high-level grouping
- Role-based breakdown for staffing clarity

CRITICAL INSTRUCTION - YOU MUST DO THE MATH CORRECTLY:
Large language models often hallucinate totals. To ensure perfect mathematical consistency without human intervention, you MUST output a <scratchpad> section before your JSON where you calculate the exact math step-by-step:
1. Calculate Total Weeks from the project plan phases.
2. Calculate Role Hours = Number of people in role * Total Weeks * 40 hours.
3. Calculate TOTAL_HOURS = Sum of all Role Hours.
4. Distribute TOTAL_HOURS across the phases so that the sum of Phase Hours exactly equals TOTAL_HOURS.
5. Calculate Cost = Role Hours * Hourly/Daily Rate.

Output exactly in this format:
<scratchpad>
Step 1: Total weeks = ...
Step 2: Role hours = ...
Step 3: Total hours = ...
</scratchpad>
```json
{
  "estimation_summary": {
    "total_hours": 0,
    "total_weeks": 0,
    "total_months": 0,
    "team_size_recommended": 0,
    "confidence_level": "High|Medium|Low",
    "estimation_methodology": "..."
  },
  
  "by_phase": [
    {
      "phase": "...",
      "hours": 0,
      "percentage_of_total": "X%"
    }
  ],
  
  "by_role": [
    {
      "role": "Business Analyst|Frontend Developer|Backend Developer|QA Engineer|DevOps|Project Manager|UI/UX Designer",
      "hours": 0,
      "daily_rate_usd": 0,
      "total_cost_usd": 0
    }
  ],
  
  "by_feature": [
    {
      "feature_area": "...",
      "linked_requirements": ["FR-001", "FR-002"],
      "complexity": "Low|Medium|High|Very High",
      "hours": 0,
      "notes": "..."
    }
  ],
  
  "cost_estimate": {
    "currency": "USD",
    "low_estimate": 0,
    "mid_estimate": 0,
    "high_estimate": 0,
    "notes": "Estimates include 20% buffer for unknowns"
  },
  
  "risks_affecting_estimate": [
    {
      "risk": "...",
      "potential_impact_hours": 0,
      "mitigation": "..."
    }
  ],
  
  "assumptions": ["..."]
}"""


def generate_effort_estimation(brd_output: dict, plan_output: dict) -> dict:
    """
    Generate effort estimation from the BRD and project plan.

    Args:
        brd_output: The full structured BRD JSON from the BRD agent.
        plan_output: The project plan JSON from the plan agent.

    Returns:
        dict: Detailed effort estimation broken down by phase, role, and feature.

    Raises:
        ValueError: If the AI response cannot be parsed as JSON.
        RuntimeError: If the AI API call fails.
    """
    import json

    user_prompt = f"""Generate a detailed effort estimation based on:

Project Summary: {brd_output.get('executive_summary', '')}

Functional Requirements ({len(brd_output.get('functional_requirements', []))} total):
{json.dumps(brd_output.get('functional_requirements', []), indent=2)}

Non-Functional Requirements:
{json.dumps(brd_output.get('non_functional_requirements', []), indent=2)}

Project Phases:
{json.dumps(plan_output.get('phases', []), indent=2)}

Team Structure:
{json.dumps(plan_output.get('team_structure', []), indent=2)}

Generate a comprehensive effort estimation with cost breakdown."""

    return generate_json(SYSTEM_PROMPT, user_prompt)
