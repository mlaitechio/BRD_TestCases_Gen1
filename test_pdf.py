import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'brd_system.settings')
django.setup()

from utils.pdf_exporter import export_brd_to_pdf

fake_brd = {
    "executive_summary": "Test Summary",
    "project_scope": {
        "in_scope": ["Test Scope"],
        "out_of_scope": ["Not Scope"]
    }
}

try:
    buffer = export_brd_to_pdf(fake_brd)
    with open("test_out.pdf", "wb") as f:
        f.write(buffer)
    print("Success")
except Exception as e:
    print(f"Error: {e}")
