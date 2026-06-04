import os
import sys
import django
import time
from pathlib import Path

def setup_django():
    # Setup django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'brd_system.settings')
    django.setup()

def get_multiline_input(prompt):
    print(f"\n{prompt}")
    print("(Type your input, then press Enter twice to submit)")
    print("-" * 50)
    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)

def main():
    print("=" * 70)
    print(" 🚀 BRD AUTOMATION PIPELINE - INTERACTIVE CLI 🚀")
    print("=" * 70)
    print("NOTE: Make sure your .env has ANTHROPIC_API_KEY or OPENAI_API_KEY set.")
    
    setup_django()
    
    from apps.projects.models import Project
    from apps.projects.tasks import run_clarification_task, run_brd_task, run_remaining_agents_task
    from utils.docx_exporter import export_brd_to_docx, export_plan_to_docx, export_testcases_to_docx, export_effort_to_docx
    
    # 1. Project Description
    project_description = get_multiline_input("Please describe your software project:")
    
    if not project_description.strip():
        print("❌ Project description cannot be empty. Exiting.")
        sys.exit(1)
        
    print("\n[1/5] Creating project and starting Clarification Agent...")
    project = Project.objects.create(
        extracted_text=project_description,
        status='new'
    )
    
    start_time = time.time()
    # Run synchronously
    try:
        run_clarification_task(str(project.id))
    except Exception as e:
        print(f"❌ Clarification agent failed: {e}")
        sys.exit(1)
        
    project.refresh_from_db()
    
    questions = project.clarification_questions
    if not questions:
        print("❌ No clarification questions were generated. Check your API keys and logs.")
        sys.exit(1)
        
    print(f"✅ Generated {len(questions)} clarification questions in {time.time() - start_time:.1f}s.\n")
    
    # 2. Answer Questions
    answers = {}
    print("=" * 70)
    print(" 📝 CLARIFICATION QUESTIONS ")
    print("=" * 70)
    for q in questions:
        print(f"\n[{q['id']}] {q['question']}")
        print(f"💡 Why: {q['why_asking']}")
        answer = input("\nYour Answer: ")
        answers[q['id']] = answer
        
    project.clarification_answers = answers
    project.save(update_fields=['clarification_answers'])
    
    # 3. Generate BRD
    print("\n[2/5] Generating Business Requirements Document (BRD)...")
    print("      (This may take 30-60 seconds depending on project size)")
    start_time = time.time()
    
    try:
        run_brd_task(str(project.id))
    except Exception as e:
        print(f"❌ BRD agent failed: {e}")
        sys.exit(1)
        
    project.refresh_from_db()
    brd_output = project.outputs.get(agent_type='brd').structured_output
    
    print(f"✅ BRD generated in {time.time() - start_time:.1f}s.")
    
    # Export BRD immediately
    output_dir = Path("cli_outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Generate a readable short name from the project description (first 4 words)
    import re
    clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', project.extracted_text)
    short_name = '_'.join(clean_text.split()[:4]).capitalize()
    if not short_name:
        short_name = f"Project_{str(project.id)[:4]}"
    
    brd_buffer = export_brd_to_docx(brd_output)
    brd_filepath = output_dir / f"{short_name}_BRD.docx"
    with open(brd_filepath, 'wb') as f:
        f.write(brd_buffer.getvalue())
    print(f"\n  💾 BRD Saved for review: {brd_filepath}")
    
    print("=" * 70)
    print(" 📄 BRD SUMMARY ")
    print("=" * 70)
    
    frs = brd_output.get('functional_requirements', [])
    nfrs = brd_output.get('non_functional_requirements', [])
    print(f"Found {len(frs)} Functional Requirements and {len(nfrs)} Non-Functional Requirements.")
    print("\nTop Functional Requirements:")
    for fr in frs[:3]:
        print(f"  - [{fr.get('id')}] {fr.get('title')} ({fr.get('priority')})")
        
    print("\n")
    approve = input("Do you approve this BRD to generate Plan, Test Cases, and Effort? (y/n): ")
    if approve.lower() not in ['y', 'yes']:
        print("Pipeline paused. You can implement revision flows in the API.")
        sys.exit(0)
        
    project.brd_approved = True
    project.save(update_fields=['brd_approved'])
    
    # 4. Run remaining agents sequentially and save immediately
    print("\n[3/5] Generating Project Plan...")
    from agents.plan_agent import generate_project_plan
    try:
        plan_data = generate_project_plan(brd_output)
        plan_buffer = export_plan_to_docx(plan_data)
        plan_filepath = output_dir / f"{short_name}_ProjectPlan.docx"
        with open(plan_filepath, 'wb') as f:
            f.write(plan_buffer.getvalue())
        print(f"  ✅ Plan Generated! 💾 Saved: {plan_filepath}")
    except Exception as e:
        print(f"❌ Plan agent failed: {e}")

    print("\n[4/5] Generating Test Cases...")
    from agents.testcase_agent import generate_test_cases
    try:
        tc_data = generate_test_cases(brd_output)
        tc_buffer = export_testcases_to_docx(tc_data)
        tc_filepath = output_dir / f"{short_name}_TestCases.docx"
        with open(tc_filepath, 'wb') as f:
            f.write(tc_buffer.getvalue())
        print(f"  ✅ Test Cases Generated! 💾 Saved: {tc_filepath}")
    except Exception as e:
        print(f"❌ Test cases agent failed: {e}")

    print("\n[5/5] Generating Effort Estimation...")
    from agents.effort_agent import generate_effort_estimation
    try:
        # We need plan data for effort estimation. If it failed, we pass empty dict.
        plan_data_for_effort = plan_data if 'plan_data' in locals() else {}
        effort_data = generate_effort_estimation(brd_output, plan_data_for_effort)
        effort_buffer = export_effort_to_docx(effort_data)
        effort_filepath = output_dir / f"{short_name}_EffortEstimation.docx"
        with open(effort_filepath, 'wb') as f:
            f.write(effort_buffer.getvalue())
        print(f"  ✅ Effort Estimation Generated! 💾 Saved: {effort_filepath}")
    except Exception as e:
        print(f"❌ Effort agent failed: {e}")
        
    print("\n🚀 Pipeline Complete! 🎉")
    print(f"Project ID: {project.id}")
    print("=" * 70)

if __name__ == "__main__":
    main()
