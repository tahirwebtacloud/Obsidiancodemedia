import os

for filename in ['01-01-PLAN.md', '01-03-PLAN.md']:
    path = f".planning/phases/01-the-security-dmz/{filename}"
    with open(path, 'r') as f:
        content = f.read()
    
    if filename == '01-03-PLAN.md':
        content = content.replace('<task type="checkpoint:human-verify" gate="blocking">', '<task type="checkpoint:human-verify" gate="blocking">\n  <name>Task 4: Checkpoint</name>\n  <action>Pause for human check</action>')
    
    with open(path, 'w') as f:
        f.write(content)
