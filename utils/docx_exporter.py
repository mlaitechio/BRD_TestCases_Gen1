"""
DOCX Export Utility.

Generates downloadable Word documents from structured JSON agent outputs.
Four exporters — one per agent output type.

Usage in views:
    buffer = export_brd_to_docx(structured_output)
    return FileResponse(buffer, as_attachment=True, filename='BRD.docx',
                        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
"""

from io import BytesIO
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


# ─── Shared Style Helpers ────────────────────────────────────────────────────

def _add_title(doc: Document, text: str):
    """Add a styled document title."""
    para = doc.add_heading(text, 0)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _add_h1(doc: Document, text: str):
    doc.add_heading(text, 1)


def _add_h2(doc: Document, text: str):
    doc.add_heading(text, 2)


def _add_bullet(doc: Document, text: str):
    doc.add_paragraph(text, style='List Bullet')


def _add_table_from_list(doc: Document, headers: list[str], rows: list[list]):
    """Add a formatted table."""
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        run = hdr_cells[i].paragraphs[0].runs[0]
        run.bold = True

    for row_data in rows:
        row_cells = table.add_row().cells
        for i, cell_val in enumerate(row_data):
            row_cells[i].text = str(cell_val) if cell_val is not None else ''


# ─── BRD Exporter ────────────────────────────────────────────────────────────

def export_brd_to_docx(structured_output: dict) -> BytesIO:
    """Export BRD JSON to a formatted Word document."""
    doc = Document()
    _add_title(doc, 'Business Requirements Document')

    # Executive Summary
    _add_h1(doc, '1. Executive Summary')
    doc.add_paragraph(structured_output.get('executive_summary', ''))

    # Project Scope
    _add_h1(doc, '2. Project Scope')
    scope = structured_output.get('project_scope', {})
    _add_h2(doc, 'In Scope')
    for item in scope.get('in_scope', []):
        _add_bullet(doc, item)
    _add_h2(doc, 'Out of Scope')
    for item in scope.get('out_of_scope', []):
        _add_bullet(doc, item)

    # Business Objectives
    _add_h1(doc, '3. Business Objectives')
    for obj in structured_output.get('business_objectives', []):
        _add_h2(doc, f"{obj.get('id', '')} — {obj.get('objective', '')}")
        doc.add_paragraph(f"Metric: {obj.get('metric', '')}")
        doc.add_paragraph(f"Target: {obj.get('target', '')}")

    # Stakeholders
    _add_h1(doc, '4. Stakeholder List')
    stakeholders = structured_output.get('stakeholders', [])
    if stakeholders:
        _add_table_from_list(
            doc,
            ['Role', 'Responsibilities', 'Interest', 'Influence'],
            [[s.get('role', ''), s.get('responsibilities', ''),
              s.get('interest_level', ''), s.get('influence_level', '')]
             for s in stakeholders]
        )

    # Project Plan
    _add_h1(doc, '5. Project Plan')
    plan = structured_output.get('project_plan', {})
    for phase in plan.get('phases', []):
        _add_h2(doc, f"{phase.get('phase', '')} ({phase.get('duration', '')})")
        doc.add_paragraph('Deliverables:')
        for d in phase.get('deliverables', []):
            _add_bullet(doc, d)
        doc.add_paragraph('Milestones:')
        for m in phase.get('milestones', []):
            _add_bullet(doc, m)

    # Effort Estimation
    _add_h1(doc, '6. Effort Estimation')
    effort = structured_output.get('effort_estimation', {})
    doc.add_paragraph(f"Total Estimated Hours: {effort.get('total_estimated_hours', 'TBD')}")
    doc.add_paragraph(effort.get('summary', ''))
    breakdown = effort.get('breakdown', [])
    if breakdown:
        _add_table_from_list(
            doc,
            ['Component', 'Hours', 'Complexity'],
            [[b.get('component', ''), b.get('hours', ''), b.get('complexity', '')]
             for b in breakdown]
        )

    # Functional Requirements
    _add_h1(doc, '7. Functional Requirements')
    for req in structured_output.get('functional_requirements', []):
        _add_h2(doc, f"{req.get('id', '')} — {req.get('title', '')}")
        doc.add_paragraph(f"Priority: {req.get('priority', '')}")
        doc.add_paragraph(req.get('description', ''))
        doc.add_paragraph('Acceptance Criteria:')
        for ac in req.get('acceptance_criteria', []):
            _add_bullet(doc, ac)
        compliance = req.get('compliance_notes', '')
        if compliance and compliance != 'N/A':
            doc.add_paragraph(f"Compliance: {compliance}")

    # Non-Functional Requirements
    _add_h1(doc, '8. Non-Functional Requirements')
    nfr_list = structured_output.get('non_functional_requirements', [])
    if nfr_list:
        _add_table_from_list(
            doc,
            ['ID', 'Category', 'Requirement', 'Metric', 'Priority'],
            [[n.get('id', ''), n.get('category', ''), n.get('requirement', ''),
              n.get('metric', ''), n.get('priority', '')]
             for n in nfr_list]
        )

    # Constraints and Assumptions
    _add_h1(doc, '9. Constraints and Assumptions')
    ca = structured_output.get('constraints_and_assumptions', {})
    _add_h2(doc, 'Constraints')
    for con in ca.get('constraints', []):
        _add_h2(doc, f"{con.get('id', '')} — {con.get('description', '')}")
        doc.add_paragraph(f"Impact: {con.get('impact', '')}")
    _add_h2(doc, 'Assumptions')
    for ass in ca.get('assumptions', []):
        _add_h2(doc, f"{ass.get('id', '')} — {ass.get('description', '')}")
        doc.add_paragraph(f"Risk if Wrong: {ass.get('risk_if_wrong', '')}")

    # Success Criteria
    _add_h1(doc, '10. Success Criteria')
    for sc in structured_output.get('success_criteria', []):
        _add_h2(doc, f"{sc.get('id', '')} — {sc.get('criterion', '')}")
        doc.add_paragraph(f"Measurement: {sc.get('measurement_method', '')}")
        doc.add_paragraph(f"Target: {sc.get('target', '')}")

    # Glossary
    _add_h1(doc, '11. Glossary')
    glossary = structured_output.get('glossary', [])
    if glossary:
        _add_table_from_list(
            doc,
            ['Term', 'Definition'],
            [[g.get('term', ''), g.get('definition', '')] for g in glossary]
        )

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ─── Project Plan Exporter ────────────────────────────────────────────────────

def export_plan_to_docx(structured_output: dict) -> BytesIO:
    """Export Project Plan JSON to a formatted Word document."""
    doc = Document()
    _add_title(doc, 'Project Plan')

    doc.add_paragraph(structured_output.get('project_summary', ''))
    doc.add_paragraph(f"Methodology: {structured_output.get('methodology', '')}")
    doc.add_paragraph(f"Total Duration: {structured_output.get('total_duration', '')}")

    # Team Structure
    _add_h1(doc, 'Team Structure')
    _add_table_from_list(
        doc,
        ['Role', 'Count', 'Responsibilities'],
        [[t.get('role', ''), t.get('count', ''), t.get('responsibilities', '')]
         for t in structured_output.get('team_structure', [])]
    )

    # Phases
    _add_h1(doc, 'Project Phases')
    for phase in structured_output.get('phases', []):
        _add_h2(doc, f"Phase {phase.get('phase_number', '')} — {phase.get('phase_name', '')}")
        doc.add_paragraph(f"Duration: {phase.get('duration', '')} | Weeks {phase.get('start_week', '')}–{phase.get('end_week', '')}")

        doc.add_paragraph('Objectives:')
        for obj in phase.get('objectives', []):
            _add_bullet(doc, obj)

        doc.add_paragraph('Tasks:')
        tasks = phase.get('tasks', [])
        if tasks:
            _add_table_from_list(
                doc,
                ['Task ID', 'Task Name', 'Role', 'Days', 'Linked Requirements'],
                [[t.get('task_id', ''), t.get('task_name', ''), t.get('assignee_role', ''),
                  t.get('duration_days', ''), ', '.join(t.get('linked_requirements', []))]
                 for t in tasks]
            )

        doc.add_paragraph('Deliverables:')
        for d in phase.get('deliverables', []):
            _add_bullet(doc, d)

    # Risk Register
    _add_h1(doc, 'Risk Register')
    risks = structured_output.get('risk_register', [])
    if risks:
        _add_table_from_list(
            doc,
            ['ID', 'Risk', 'Probability', 'Impact', 'Mitigation', 'Owner'],
            [[r.get('risk_id', ''), r.get('description', ''), r.get('probability', ''),
              r.get('impact', ''), r.get('mitigation', ''), r.get('owner', '')]
             for r in risks]
        )

    # Definition of Done
    _add_h1(doc, 'Definition of Done')
    for item in structured_output.get('definition_of_done', []):
        _add_bullet(doc, item)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ─── Test Cases Exporter ─────────────────────────────────────────────────────

def export_testcases_to_docx(structured_output: dict) -> BytesIO:
    """Export Test Cases JSON to a formatted Word document."""
    doc = Document()
    _add_title(doc, 'Test Cases & Traceability Matrix')

    # Summary
    summary = structured_output.get('test_summary', {})
    _add_h1(doc, 'Test Summary')
    doc.add_paragraph(f"Total Test Cases: {summary.get('total_test_cases', 0)}")
    doc.add_paragraph(f"Coverage: {summary.get('coverage_percentage', '')}")
    cats = summary.get('test_categories', {})
    if cats:
        _add_table_from_list(
            doc,
            ['Category', 'Count'],
            [[k, v] for k, v in cats.items()]
        )

    # Test Cases
    _add_h1(doc, 'Test Cases')
    for tc in structured_output.get('test_cases', []):
        _add_h2(doc, f"{tc.get('test_id', '')} — {tc.get('title', '')}")
        doc.add_paragraph(f"Linked Requirement: {tc.get('linked_requirement', '')} | "
                          f"Type: {tc.get('type', '')} | Priority: {tc.get('priority', '')}")
        doc.add_paragraph('Preconditions:')
        for pre in tc.get('preconditions', []):
            _add_bullet(doc, pre)
        doc.add_paragraph('Steps:')
        for step in tc.get('test_steps', []):
            doc.add_paragraph(f"  Step {step.get('step', '')}: {step.get('action', '')}")
            doc.add_paragraph(f"  Expected: {step.get('expected_result', '')}")
        doc.add_paragraph(f"Expected Outcome: {tc.get('expected_outcome', '')}")
        doc.add_paragraph(f"Pass Criteria: {tc.get('pass_criteria', '')}")
        doc.add_paragraph('')

    # Traceability Matrix
    _add_h1(doc, 'Requirements Traceability Matrix')
    matrix = structured_output.get('traceability_matrix', [])
    if matrix:
        _add_table_from_list(
            doc,
            ['Requirement ID', 'Title', 'Linked Test Cases', 'Coverage'],
            [[m.get('requirement_id', ''), m.get('requirement_title', ''),
              ', '.join(m.get('linked_test_cases', [])), m.get('coverage_status', '')]
             for m in matrix]
        )

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer


# ─── Effort Estimation Exporter ───────────────────────────────────────────────

def export_effort_to_docx(structured_output: dict) -> BytesIO:
    """Export Effort Estimation JSON to a formatted Word document."""
    doc = Document()
    _add_title(doc, 'Effort Estimation Report')

    # Summary
    _add_h1(doc, 'Estimation Summary')
    summary = structured_output.get('estimation_summary', {})
    doc.add_paragraph(f"Total Hours: {summary.get('total_hours', 0)}")
    doc.add_paragraph(f"Total Duration: {summary.get('total_weeks', 0)} weeks / {summary.get('total_months', 0)} months")
    doc.add_paragraph(f"Recommended Team Size: {summary.get('team_size_recommended', 0)}")
    doc.add_paragraph(f"Confidence Level: {summary.get('confidence_level', '')}")
    doc.add_paragraph(f"Methodology: {summary.get('estimation_methodology', '')}")

    # By Phase
    _add_h1(doc, 'Effort by Phase')
    _add_table_from_list(
        doc,
        ['Phase', 'Hours', '% of Total'],
        [[p.get('phase', ''), p.get('hours', ''), p.get('percentage_of_total', '')]
         for p in structured_output.get('by_phase', [])]
    )

    # By Role
    _add_h1(doc, 'Effort by Role')
    _add_table_from_list(
        doc,
        ['Role', 'Hours', 'Daily Rate (USD)', 'Total Cost (USD)'],
        [[r.get('role', ''), r.get('hours', ''), r.get('daily_rate_usd', ''), r.get('total_cost_usd', '')]
         for r in structured_output.get('by_role', [])]
    )

    # By Feature
    _add_h1(doc, 'Effort by Feature')
    _add_table_from_list(
        doc,
        ['Feature Area', 'Linked Requirements', 'Complexity', 'Hours', 'Notes'],
        [[f.get('feature_area', ''), ', '.join(f.get('linked_requirements', [])),
          f.get('complexity', ''), f.get('hours', ''), f.get('notes', '')]
         for f in structured_output.get('by_feature', [])]
    )

    # Cost Estimate
    _add_h1(doc, 'Cost Estimate')
    cost = structured_output.get('cost_estimate', {})
    doc.add_paragraph(f"Currency: {cost.get('currency', 'USD')}")
    doc.add_paragraph(f"Low Estimate:  ${cost.get('low_estimate', 0):,}")
    doc.add_paragraph(f"Mid Estimate:  ${cost.get('mid_estimate', 0):,}")
    doc.add_paragraph(f"High Estimate: ${cost.get('high_estimate', 0):,}")
    doc.add_paragraph(cost.get('notes', ''))

    # Risks
    _add_h1(doc, 'Risks Affecting Estimate')
    risks = structured_output.get('risks_affecting_estimate', [])
    if risks:
        _add_table_from_list(
            doc,
            ['Risk', 'Potential Impact (hours)', 'Mitigation'],
            [[r.get('risk', ''), r.get('potential_impact_hours', ''), r.get('mitigation', '')]
             for r in risks]
        )

    # Assumptions
    _add_h1(doc, 'Assumptions')
    for assumption in structured_output.get('assumptions', []):
        _add_bullet(doc, assumption)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
