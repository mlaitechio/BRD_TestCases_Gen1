import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

def _create_styles():
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    h1_style = styles['Heading1']
    h2_style = styles['Heading2']
    normal_style = styles['Normal']
    
    bullet_style = ParagraphStyle(
        name='Bullet',
        parent=normal_style,
        leftIndent=20,
        bulletIndent=10,
    )
    return title_style, h1_style, h2_style, normal_style, bullet_style

def _create_table(data, headers):
    table_data = [headers] + data
    # Convert all to Paragraphs to handle wrapping
    styles = getSampleStyleSheet()
    normal_style = styles['Normal']
    wrapped_data = []
    for row in table_data:
        wrapped_row = [Paragraph(str(cell) if cell is not None else '', normal_style) for cell in row]
        wrapped_data.append(wrapped_row)

    t = Table(wrapped_data)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return t

def export_brd_to_pdf(structured_output: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    title_style, h1_style, h2_style, normal_style, bullet_style = _create_styles()
    
    story.append(Paragraph('Business Requirements Document', title_style))
    story.append(Spacer(1, 12))
    
    # 1. Executive Summary
    story.append(Paragraph('1. Executive Summary', h1_style))
    story.append(Paragraph(structured_output.get('executive_summary', ''), normal_style))
    story.append(Spacer(1, 12))
    
    # 2. Project Scope
    story.append(Paragraph('2. Project Scope', h1_style))
    scope = structured_output.get('project_scope', {})
    story.append(Paragraph('In Scope', h2_style))
    for item in scope.get('in_scope', []):
        story.append(Paragraph(f'• {item}', bullet_style))
    story.append(Paragraph('Out of Scope', h2_style))
    for item in scope.get('out_of_scope', []):
        story.append(Paragraph(f'• {item}', bullet_style))
    story.append(Spacer(1, 12))
    
    # 3. Business Objectives
    story.append(Paragraph('3. Business Objectives', h1_style))
    for obj in structured_output.get('business_objectives', []):
        story.append(Paragraph(f"{obj.get('id', '')} - {obj.get('objective', '')}", h2_style))
        story.append(Paragraph(f"Metric: {obj.get('metric', '')}", normal_style))
        story.append(Paragraph(f"Target: {obj.get('target', '')}", normal_style))
    story.append(Spacer(1, 12))
    
    # 4. Stakeholders
    story.append(Paragraph('4. Stakeholder List', h1_style))
    stakeholders = structured_output.get('stakeholders', [])
    if stakeholders:
        headers = ['Role', 'Responsibilities', 'Interest', 'Influence']
        data = [[s.get('role', ''), s.get('responsibilities', ''), s.get('interest_level', ''), s.get('influence_level', '')] for s in stakeholders]
        story.append(_create_table(data, headers))
    story.append(Spacer(1, 12))
    
    # 5. Project Plan
    story.append(Paragraph('5. Project Plan', h1_style))
    plan = structured_output.get('project_plan', {})
    for phase in plan.get('phases', []):
        story.append(Paragraph(f"{phase.get('phase', '')} ({phase.get('duration', '')})", h2_style))
        story.append(Paragraph('Deliverables:', normal_style))
        for d in phase.get('deliverables', []):
            story.append(Paragraph(f'• {d}', bullet_style))
        story.append(Paragraph('Milestones:', normal_style))
        for m in phase.get('milestones', []):
            story.append(Paragraph(f'• {m}', bullet_style))
    story.append(Spacer(1, 12))
    
    # 6. Effort Estimation
    story.append(Paragraph('6. Effort Estimation', h1_style))
    effort = structured_output.get('effort_estimation', {})
    story.append(Paragraph(f"Total Estimated Hours: {effort.get('total_estimated_hours', 'TBD')}", normal_style))
    story.append(Paragraph(effort.get('summary', ''), normal_style))
    breakdown = effort.get('breakdown', [])
    if breakdown:
        headers = ['Component', 'Hours', 'Complexity']
        data = [[b.get('component', ''), b.get('hours', ''), b.get('complexity', '')] for b in breakdown]
        story.append(_create_table(data, headers))
    story.append(Spacer(1, 12))
    
    # 7. Functional Requirements
    story.append(Paragraph('7. Functional Requirements', h1_style))
    for req in structured_output.get('functional_requirements', []):
        story.append(Paragraph(f"{req.get('id', '')} - {req.get('title', '')}", h2_style))
        story.append(Paragraph(f"Priority: {req.get('priority', '')}", normal_style))
        story.append(Paragraph(req.get('description', ''), normal_style))
        story.append(Paragraph('Acceptance Criteria:', normal_style))
        for ac in req.get('acceptance_criteria', []):
            story.append(Paragraph(f'• {ac}', bullet_style))
        compliance = req.get('compliance_notes', '')
        if compliance and compliance != 'N/A':
            story.append(Paragraph(f"Compliance: {compliance}", normal_style))
    story.append(Spacer(1, 12))
    
    # 8. Non-Functional Requirements
    story.append(Paragraph('8. Non-Functional Requirements', h1_style))
    nfr_list = structured_output.get('non_functional_requirements', [])
    if nfr_list:
        headers = ['ID', 'Category', 'Requirement', 'Metric', 'Priority']
        data = [[n.get('id', ''), n.get('category', ''), n.get('requirement', ''), n.get('metric', ''), n.get('priority', '')] for n in nfr_list]
        story.append(_create_table(data, headers))
    story.append(Spacer(1, 12))
    
    # 9. Constraints and Assumptions
    story.append(Paragraph('9. Constraints and Assumptions', h1_style))
    ca = structured_output.get('constraints_and_assumptions', {})
    story.append(Paragraph('Constraints', h2_style))
    for con in ca.get('constraints', []):
        story.append(Paragraph(f"{con.get('id', '')} - {con.get('description', '')}", h2_style))
        story.append(Paragraph(f"Impact: {con.get('impact', '')}", normal_style))
    story.append(Paragraph('Assumptions', h2_style))
    for ass in ca.get('assumptions', []):
        story.append(Paragraph(f"{ass.get('id', '')} - {ass.get('description', '')}", h2_style))
        story.append(Paragraph(f"Risk if Wrong: {ass.get('risk_if_wrong', '')}", normal_style))
    story.append(Spacer(1, 12))
    
    # 10. Success Criteria
    story.append(Paragraph('10. Success Criteria', h1_style))
    for sc in structured_output.get('success_criteria', []):
        story.append(Paragraph(f"{sc.get('id', '')} - {sc.get('criterion', '')}", h2_style))
        story.append(Paragraph(f"Measurement: {sc.get('measurement_method', '')}", normal_style))
        story.append(Paragraph(f"Target: {sc.get('target', '')}", normal_style))
    story.append(Spacer(1, 12))
    
    # 11. Glossary
    story.append(Paragraph('11. Glossary', h1_style))
    glossary = structured_output.get('glossary', [])
    if glossary:
        headers = ['Term', 'Definition']
        data = [[g.get('term', ''), g.get('definition', '')] for g in glossary]
        story.append(_create_table(data, headers))
    
    doc.build(story)
    return buffer.getvalue()

def export_plan_to_pdf(structured_output: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    title_style, h1_style, h2_style, normal_style, bullet_style = _create_styles()
    
    story.append(Paragraph('Project Plan', title_style))
    story.append(Spacer(1, 12))
    
    story.append(Paragraph(structured_output.get('project_summary', ''), normal_style))
    story.append(Paragraph(f"Methodology: {structured_output.get('methodology', '')}", normal_style))
    story.append(Paragraph(f"Total Duration: {structured_output.get('total_duration', '')}", normal_style))
    story.append(Spacer(1, 12))
    
    # Team Structure
    story.append(Paragraph('Team Structure', h1_style))
    team = structured_output.get('team_structure', [])
    if team:
        headers = ['Role', 'Count', 'Responsibilities']
        data = [[t.get('role', ''), t.get('count', ''), t.get('responsibilities', '')] for t in team]
        story.append(_create_table(data, headers))
    story.append(Spacer(1, 12))
    
    # Phases
    story.append(Paragraph('Project Phases', h1_style))
    for phase in structured_output.get('phases', []):
        story.append(Paragraph(f"Phase {phase.get('phase_number', '')} - {phase.get('phase_name', '')}", h2_style))
        story.append(Paragraph(f"Duration: {phase.get('duration', '')} | Weeks {phase.get('start_week', '')}-{phase.get('end_week', '')}", normal_style))
        
        story.append(Paragraph('Objectives:', normal_style))
        for obj in phase.get('objectives', []):
            story.append(Paragraph(f'• {obj}', bullet_style))
            
        story.append(Paragraph('Tasks:', normal_style))
        tasks = phase.get('tasks', [])
        if tasks:
            headers = ['Task ID', 'Task Name', 'Role', 'Days', 'Linked Requirements']
            data = [[t.get('task_id', ''), t.get('task_name', ''), t.get('assignee_role', ''), t.get('duration_days', ''), ', '.join(t.get('linked_requirements', []))] for t in tasks]
            story.append(_create_table(data, headers))
            
        story.append(Paragraph('Deliverables:', normal_style))
        for d in phase.get('deliverables', []):
            story.append(Paragraph(f'• {d}', bullet_style))
    story.append(Spacer(1, 12))
    
    # Risk Register
    story.append(Paragraph('Risk Register', h1_style))
    risks = structured_output.get('risk_register', [])
    if risks:
        headers = ['ID', 'Risk', 'Probability', 'Impact', 'Mitigation', 'Owner']
        data = [[r.get('risk_id', ''), r.get('description', ''), r.get('probability', ''), r.get('impact', ''), r.get('mitigation', ''), r.get('owner', '')] for r in risks]
        story.append(_create_table(data, headers))
    story.append(Spacer(1, 12))
    
    # Definition of Done
    story.append(Paragraph('Definition of Done', h1_style))
    for item in structured_output.get('definition_of_done', []):
        story.append(Paragraph(f'• {item}', bullet_style))
        
    doc.build(story)
    return buffer.getvalue()
