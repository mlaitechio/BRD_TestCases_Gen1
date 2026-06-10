import json

path = 'd:/BRD_Automation/views_transcript_all.jsonl'

longest_code = ""
try:
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            # Recursively search for long strings containing 'import rest_framework' or similar
            def find_strings(obj):
                global longest_code
                if isinstance(obj, str):
                    if 'class ProjectListCreateView' in obj and len(obj) > len(longest_code):
                        longest_code = obj
                elif isinstance(obj, dict):
                    for k, v in obj.items():
                        find_strings(v)
                elif isinstance(obj, list):
                    for item in obj:
                        find_strings(item)
            
            find_strings(data)

    if longest_code:
        with open('d:/BRD_Automation/views_recovered.txt', 'w', encoding='utf-8') as out:
            out.write(longest_code)
        print(f"Found code of length {len(longest_code)}")
    else:
        print("Could not find full code.")
except Exception as e:
    print(f"Error: {e}")
