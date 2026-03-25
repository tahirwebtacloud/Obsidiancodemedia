import sys

def fix_file(path):
    with open(path, 'r') as f:
        content = f.read()
    
    # Very simple hack: if there's a checkpoint task, make sure it has name, action, verify, done, files
    if '<task type="checkpoint' in content:
        if '<files>' not in content.split('<task type="checkpoint')[1]:
            content = content.replace('<what-built>', '<files>N/A</files>\n  <verify>Human visual check</verify>\n  <done>Human approved</done>\n  <what-built>')
    
    with open(path, 'w') as f:
        f.write(content)

fix_file('.planning/phases/01-the-security-dmz/01-01-PLAN.md')
fix_file('.planning/phases/01-the-security-dmz/01-03-PLAN.md')
