#!/bin/bash
# Verify all models in registry exist and are valid files

python3 -c "
import json
import os

config_path = 'src/models/config.json'
if not os.path.exists(config_path):
    print(f'Error: config.json not found at {config_path}')
    exit(1)

with open(config_path) as f:
    config = json.load(f)

print('Checking models...')
print()
all_ok = True

for name, model in config['models'].items():
    path = model['model_path']
    if os.path.exists(path):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        print(f'✓ {name}')
        print(f'  Path: {path}')
        print(f'  Size: {size_mb:.0f} MB')
        print(f'  Context: {model[\"max_context_len\"]} tokens')
        print(f'  Description: {model.get(\"description\", \"N/A\")}')
        print()
    else:
        print(f'✗ {name}')
        print(f'  Path: {path}')
        print(f'  Status: NOT FOUND')
        print()
        all_ok = False

if all_ok:
    print('All models found!')
else:
    print('Some models are missing. Please download them.')
    exit(1)
"
