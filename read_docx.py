import zipfile
import xml.etree.ElementTree as ET
import sys

sys.stdout.reconfigure(encoding='utf-8')

with zipfile.ZipFile('Antigravity_Backend_Plan.docx', 'r') as z:
    with z.open('word/document.xml') as f:
        root = ET.parse(f).getroot()
        ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        texts = []
        for p in root.iter(f'{{{ns}}}p'):
            runs = p.findall(f'.//{{{ns}}}t')
            line = ''.join(r.text or '' for r in runs)
            if line.strip():
                texts.append(line)
        print('\n'.join(texts))
