import json

path = r'C:\Users\kisha\.gemini\antigravity\brain\e2da6936-329c-4c56-a3d4-e061e8c36e7e\.system_generated\logs\transcript.jsonl'
output_lines = []

try:
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get('type') == 'PLANNER_RESPONSE':
                    content = str(data)
                    if 'views.py' in content:
                        # try to find the tool_calls
                        tool_calls = data.get('tool_calls', [])
                        for tc in tool_calls:
                            if tc.get('function', {}).get('name') in ['write_to_file', 'replace_file_content']:
                                args = tc.get('function', {}).get('arguments', {})
                                if 'views.py' in str(args.get('TargetFile', '')):
                                    output_lines.append(tc)
            except Exception:
                pass

    print(f"Found {len(output_lines)} tool calls to views.py.")
    with open('d:/BRD_Automation/views_tool_calls.json', 'w', encoding='utf-8') as out:
        json.dump(output_lines, out, indent=2)
except Exception as e:
    print(f"Error: {e}")
