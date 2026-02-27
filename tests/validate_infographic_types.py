"""Validate individual style type prompt files in directives/style_types/."""
import json, sys, os

REQUIRED_FIELDS = ['id', 'prompt', 'layout', 'visual_hierarchy', 'focal_point', 'white_space', 'balance']
BASE_DIR = 'directives/style_types'

# Expected structure: { style_key: [list of type keys] }
EXPECTED = {
    'infographic': ['glassmorphic_venn', 'minimalist_framework', 'comparison', 'bento_grid', 'whiteboard_style'],
    'ugc': ['lifestyle_post', 'relatable_meme', 'visual_hook', 'informative_ugc']
}

errors = []
total_prompts = 0

for style_key, expected_types in EXPECTED.items():
    style_dir = os.path.join(BASE_DIR, style_key)
    if not os.path.isdir(style_dir):
        errors.append(f"MISSING DIR: '{style_dir}'")
        continue

    for type_key in expected_types:
        fpath = os.path.join(style_dir, type_key + '.json')
        prefix = f"{style_key}/{type_key}"
        if not os.path.exists(fpath):
            errors.append(f"MISSING FILE: '{fpath}'")
            continue
        with open(fpath, 'r', encoding='utf-8') as f:
            type_data = json.load(f)
        if 'label' not in type_data:
            errors.append(f"{prefix}: missing 'label'")
        if 'prompts' not in type_data:
            errors.append(f"{prefix}: missing 'prompts'")
            continue
        prompts = type_data['prompts']
        if len(prompts) < 1:
            errors.append(f"{prefix}: no prompts found")
        total_prompts += len(prompts)
        for i, p in enumerate(prompts):
            pid = p.get('id', '?')
            for field in REQUIRED_FIELDS:
                if field not in p or not p[field]:
                    errors.append(f"{prefix}/{pid}: missing or empty '{field}'")
            if '{{' not in p.get('prompt', ''):
                errors.append(f"{prefix}/{pid}: no placeholder tokens found")

if errors:
    print("ERRORS FOUND:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    total_types = sum(len(v) for v in EXPECTED.values())
    print(f"ALL VALID: {total_types} type files across {len(EXPECTED)} styles, {total_prompts} prompts total")
    for style_key, expected_types in EXPECTED.items():
        print(f"\n  [{style_key.upper()}]")
        for tk in expected_types:
            fpath = os.path.join(BASE_DIR, style_key, tk + '.json')
            td = json.load(open(fpath, 'r', encoding='utf-8'))
            ids = [p['id'] for p in td['prompts']]
            print(f"    {tk} ({td['label']}): {ids}")
    sys.exit(0)
