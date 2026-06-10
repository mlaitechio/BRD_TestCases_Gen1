import json

path = r'C:\Users\kisha\.gemini\antigravity\brain\e2da6936-329c-4c56-a3d4-e061e8c36e7e\.system_generated\logs\transcript.jsonl'
output_lines = []

try:
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if 'views.py' in line:
                output_lines.append(line)

    with open('d:/BRD_Automation/views_transcript_all.jsonl', 'w', encoding='utf-8') as out:
        for item in output_lines:
            out.write(item)
    print(f"Extracted {len(output_lines)} lines with views.py.")
except Exception as e:
    print(f"Error: {e}")
