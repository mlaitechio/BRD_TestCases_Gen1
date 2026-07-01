import sys
import os
sys.path.insert(0, r'd:\BRD_Automation')
from utils.docx_exporter import export_brd_to_docx

sample = {
    "project_name": "Individual and Non Individual verification in SFDC",
    "version": "1.3",
    "document_date": "December 2025",
    "executive_summary": "Sample summary."
}

buf = export_brd_to_docx(sample)
out_path = r'd:\BRD_Automation\test_output\ABHFL_BRD_Cover_Test.docx'
os.makedirs(r'd:\BRD_Automation\test_output', exist_ok=True)
with open(out_path, 'wb') as f:
    f.write(buf.read())
print(f"SUCCESS: Written to {out_path}")
