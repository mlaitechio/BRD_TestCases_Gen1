"""Extract logo from BRD EY Journey file - it contains the new ABHFL logo with HOME LOANS branding."""
from docx import Document
import os

doc = Document(r'd:\BRD_Automation\BRDs\BRD EY Journey 22.01.2026.docx')
os.makedirs(r'd:\BRD_Automation\media\brd_assets', exist_ok=True)

print("=== IMAGES IN EY BRD ===")
for i, rel in enumerate(doc.part.rels.values()):
    if 'image' in rel.reltype:
        try:
            img_part = rel.target_part
            ct = img_part.content_type
            ext = ct.split('/')[-1]
            if ext in ('jpeg', 'jpg'):
                ext = 'jpg'
            elif ext == 'png':
                ext = 'png'
            size = len(img_part.blob)
            print(f"  [{i}] {ct} | {size} bytes | target: {rel.target_ref}")
            out_path = rf'd:\BRD_Automation\media\brd_assets\ey_image_{i}.{ext}'
            with open(out_path, 'wb') as f:
                f.write(img_part.blob)
            print(f"       -> saved: {out_path}")
        except Exception as e:
            print(f"  [{i}] FAILED: {e}")

# Also check header images
print("\n=== HEADER IMAGES ===")
for section in doc.sections:
    if section.header:
        for rel in section.header.part.rels.values():
            if 'image' in rel.reltype:
                try:
                    img_part = rel.target_part
                    ct = img_part.content_type
                    ext = 'jpg' if 'jpeg' in ct else 'png'
                    size = len(img_part.blob)
                    print(f"  Header image: {size} bytes | {rel.target_ref}")
                    out_path = rf'd:\BRD_Automation\media\brd_assets\ey_header_{rel.target_ref.split("/")[-1]}'
                    with open(out_path, 'wb') as f:
                        f.write(img_part.blob)
                    print(f"  -> saved: {out_path}")
                except Exception as e:
                    print(f"  FAILED: {e}")
