import json

path = r'C:\Users\kisha\.gemini\antigravity\brain\e2da6936-329c-4c56-a3d4-e061e8c36e7e\.system_generated\logs\transcript.jsonl'
output_lines = []

try:
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get('type') == 'TOOL_RESPONSE':
                    content = str(data.get('content', ''))
                    if 'views.py' in content and 'class ProjectListCreateView' in content:
                        output_lines.append(content)
            except Exception:
                pass

    longest = max(output_lines, key=len) if output_lines else ""
    if longest:
        with open('d:/BRD_Automation/views_recovered.txt', 'w', encoding='utf-8') as out:
            out.write(longest)
        print(f"Found TOOL_RESPONSE of length {len(longest)}")
    else:
        print("Could not find any TOOL_RESPONSE with views.py and class ProjectListCreateView")
except Exception as e:
    print(f"Error: {e}")
