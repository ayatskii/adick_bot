#!/usr/bin/env python3
"""
Script to fix syntax errors in whitelist_config.py
This script ensures all entries in ADMIN_USER_IDS have proper commas.
"""
import re
import sys
from pathlib import Path

def fix_config_file(file_path: Path):
    """Fix syntax errors in the config file"""
    print(f"Reading config file: {file_path}")
    
    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        return False
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find ADMIN_USER_IDS section
    pattern = r'(ADMIN_USER_IDS\s*=\s*\[)(.*?)(\])'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print("Error: Could not find ADMIN_USER_IDS section")
        return False
    
    list_content = match.group(2)
    print(f"Current list content:\n{repr(list_content[:200])}")
    
    # Fix the list content
    lines = list_content.rstrip().split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip empty lines and comments
        if not stripped or stripped.startswith('#'):
            fixed_lines.append(line)
            continue
        
        # Check if this is a number (user ID)
        if re.match(r'^\s*\d+\s*$', line):
            # Ensure it has a comma
            if not line.rstrip().endswith(','):
                fixed_lines.append(line.rstrip() + ',')
            else:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    # Reconstruct the list
    fixed_content = '\n'.join(fixed_lines)
    if fixed_content and not fixed_content.endswith('\n'):
        fixed_content += '\n'
    
    # Replace in original content
    replacement = match.group(1) + fixed_content + match.group(3)
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write back
    print(f"Writing fixed content to: {file_path}")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Config file fixed successfully!")
    return True

if __name__ == '__main__':
    # Try Docker volume location first
    docker_path = Path('/app/config/whitelist_config.py')
    project_path = Path('whitelist_config.py')
    
    if docker_path.exists():
        print("Found config in Docker volume location")
        fix_config_file(docker_path)
    elif project_path.exists():
        print("Found config in project root")
        fix_config_file(project_path)
    else:
        print("Error: Could not find whitelist_config.py")
        print(f"  Tried: {docker_path}")
        print(f"  Tried: {project_path.absolute()}")
        sys.exit(1)

