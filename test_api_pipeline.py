import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000/api/projects"

def main():
    print("==================================================")
    print(" 🚀 BRD AUTOMATION PIPELINE - API TEST SCRIPT 🚀")
    print("==================================================")

    # 1. Create a Project
    project_description = "AI-powered CRM system for real estate agents to track leads and predict sales."
    print(f"\n[1] Creating Project via API... (Input: '{project_description}')")
    
    response = requests.post(f"{BASE_URL}/", json={"raw_input": project_description})
    
    if response.status_code != 201:
        print(f"❌ Failed to create project: {response.text}")
        sys.exit(1)
        
    data = response.json()
    project_id = data['id']
    print(f"✅ Project Created! ID: {project_id}")
    
    # 2. Poll for Clarification Questions
    print("\n[2] Polling for Clarification Questions (Waiting for AI)...")
    while True:
        status_res = requests.get(f"{BASE_URL}/{project_id}/status/")
        status_data = status_res.json()
        
        if status_data['status'] == 'failed':
            print(f"❌ Pipeline Failed: {status_data.get('error_message')}")
            sys.exit(1)
            
        if status_data['status'] == 'awaiting_answers':
            print("✅ Questions are ready!")
            break
            
        time.sleep(2) # Poll every 2 seconds
        
    # Fetch the actual questions
    q_res = requests.get(f"{BASE_URL}/{project_id}/clarification-questions/")
    questions = q_res.json()['questions']
    
    answers_payload = {}
    print("\n--- AI Clarification Questions ---")
    for idx, q in enumerate(questions):
        print(f"Q: {q['question']}")
        answers_payload[q['id']] = f"Auto-generated test answer for question {idx + 1}"
        
    # 3. Submit Answers
    print("\n[3] Submitting Answers via API...")
    ans_res = requests.post(f"{BASE_URL}/{project_id}/answer-questions/", json={"answers": answers_payload})
    if ans_res.status_code == 200:
        print("✅ Answers submitted successfully. BRD generation started.")
        
    # 4. Poll for BRD
    print("\n[4] Polling for BRD Generation (Waiting for AI - approx 30s)...")
    while True:
        status_res = requests.get(f"{BASE_URL}/{project_id}/status/")
        status_data = status_res.json()
        
        if status_data['status'] == 'failed':
            print(f"❌ Pipeline Failed: {status_data.get('error_message')}")
            sys.exit(1)
            
        if status_data['status'] == 'awaiting_approval':
            print("✅ BRD Generated Successfully!")
            break
            
        time.sleep(2)
        
    # 5. Download the BRD Docx
    print("\n[5] Downloading BRD DOCX via API...")
    download_res = requests.get(f"{BASE_URL}/{project_id}/download/brd/")
    if download_res.status_code == 200:
        filename = download_res.headers.get("Content-Disposition", "").split("filename=")[-1].strip('"')
        if not filename:
            filename = f"{project_id}_BRD.docx"
            
        with open(filename, "wb") as f:
            f.write(download_res.content)
        print(f"✅ BRD Downloaded to {filename}")
        
    # 6. Approve BRD to kick off Plan, Test Cases, Effort
    print("\n[6] Approving BRD via API...")
    approve_res = requests.post(f"{BASE_URL}/{project_id}/approve-brd/")
    if approve_res.status_code == 200:
        print("✅ BRD Approved! Remaining agents started.")
        
    # 7. Poll for Completion
    print("\n[7] Polling for Remaining Documents (Waiting for AI)...")
    while True:
        status_res = requests.get(f"{BASE_URL}/{project_id}/status/")
        status_data = status_res.json()
        
        if status_data['status'] == 'failed':
            print(f"❌ Pipeline Failed: {status_data.get('error_message')}")
            sys.exit(1)
            
        if status_data['status'] == 'complete':
            print("✅ All Documents Generated Successfully!")
            break
            
        time.sleep(2)
        
    # 8. Download Remaining Documents
    print("\n[8] Downloading Remaining DOCX files via API...")
    for doc_type in ['plan', 'testcases', 'effort']:
        doc_res = requests.get(f"{BASE_URL}/{project_id}/download/{doc_type}/")
        if doc_res.status_code == 200:
            filename = doc_res.headers.get("Content-Disposition", "").split("filename=")[-1].strip('"')
            with open(filename, "wb") as f:
                f.write(doc_res.content)
            print(f"✅ Downloaded {filename}")
            
    print("\n🎉 API PIPELINE TEST COMPLETE! 🎉")

if __name__ == "__main__":
    main()
