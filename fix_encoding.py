import sys

def fix_file(filepath):
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # Decode as utf-8, which gives the mojibake
        mojibake = content.decode('utf-8')
        
        # Encode back to utf-16le to get the original bytes
        original_bytes = mojibake.encode('utf-16le')
        
        # Decode as utf-8 (which was the original encoding)
        original_text = original_bytes.decode('utf-8')
        
        with open(filepath + '.restored', 'wb') as f:
            f.write(original_text.encode('utf-8'))
        print(f"Success for {filepath}")
    except Exception as e:
        print(f"Error for {filepath}: {e}")

fix_file('d:/BRD_Automation/apps/projects/views.py')
