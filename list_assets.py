import os
files = os.listdir(r'd:\BRD_Automation\media\brd_assets')
for f in files:
    p = os.path.join(r'd:\BRD_Automation\media\brd_assets', f)
    print(f, os.path.getsize(p))
