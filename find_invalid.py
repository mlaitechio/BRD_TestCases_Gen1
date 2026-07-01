c = open('d:/BRD_Automation/apps/projects/views.py', 'rb').read()
try:
    c.decode('utf-8')
except UnicodeDecodeError as e:
    print(f"Error at position {e.start}: byte {c[e.start]:hex}")
    # Print surrounding context
    start = max(0, e.start - 50)
    end = min(len(c), e.start + 50)
    print("Surrounding text:", c[start:end])
