import json

path = r'C:\Users\kisha\.gemini\antigravity\brain\e2da6936-329c-4c56-a3d4-e061e8c36e7e\.system_generated\logs\transcript.jsonl'
output_lines = []

try:
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                # Look for view_file output for views.py
                if data.get('type') == 'TOOL_RESPONSE' and 'views.py' in str(data):
                    content = data.get('content', '')
                    if 'File Path: `file:///d:/BRD_Automation/apps/projects/views.py`' in content:
                        output_lines.append(content)
            except Exception:
                pass

    with open('d:/BRD_Automation/views_transcript_extract.txt', 'w', encoding='utf-8') as out:
        for item in output_lines:
            out.write("==== TOOL RESPONSE ====\n")
            out.write(item)
            out.write("\n")
    print(f"Extracted {len(output_lines)} instances of view_file for views.py.")
except Exception as e:
    print(f"Error: {e}")
