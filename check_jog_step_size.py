#!/usr/bin/env python3
"""
Quick check to see what step size is being used for jogging
"""

import re

def check_jog_step_size():
    """Check what values are being passed to jog() method"""
    
    with open("main_app.py", "r") as f:
        content = f.read()
    
    print("Searching for jog() method calls...")
    
    # Find all jog method calls
    jog_calls = re.findall(r'\.jog\([^)]+\)', content)
    
    if jog_calls:
        print("Found jog() calls:")
        for call in jog_calls[:10]:  # Show first 10
            print(f"  {call}")
    else:
        print("No direct jog() calls found")
    
    # Look for UI button/key handlers that might call jog
    print("\nSearching for button/key handlers...")
    
    ui_patterns = [
        r'command.*=.*lambda.*jog',
        r'bind.*lambda.*jog',
        r'def.*jog.*button',
        r'def.*on.*key'
    ]
    
    for pattern in ui_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            print(f"Found UI handlers: {matches}")
    
    # Look for step size or distance variables
    print("\nSearching for step size variables...")
    
    step_patterns = [
        r'(step_size|jog_distance|jog_step|move_distance)\s*=\s*([\d.]+)',
        r'STEP_SIZE.*=.*[\d.]+',
        r'JOG.*=.*[\d.]+'
    ]
    
    for pattern in step_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            print(f"Found step variables: {matches}")
    
    # Look for any hardcoded numbers that might be step sizes
    print("\nSearching for potential step size numbers...")
    
    # Find lines containing jog and numbers
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'jog' in line.lower() and re.search(r'\b[01]\.\d+\b', line):
            print(f"Line {i+1}: {line.strip()}")
    
    print("\nDone checking jog step sizes.")

def find_arrow_key_handlers():
    """Find arrow key event handlers"""
    
    with open("main_app.py", "r") as f:
        content = f.read()
    
    print("\nSearching for arrow key handlers...")
    
    arrow_patterns = [
        r'<.*[Aa]rrow.*>',
        r'bind.*[Aa]rrow',
        r'[Ll]eft.*[Rr]ight.*[Uu]p.*[Dd]own',
        r'KeyPress.*Arrow',
        r'on.*key.*press'
    ]
    
    for pattern in arrow_patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            # Get surrounding context
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 50)
            context = content[start:end].replace('\n', ' ')
            print(f"Found arrow key reference: ...{context}...")

if __name__ == "__main__":
    print("Checking Jog Step Size Configuration")
    print("=====================================")
    
    check_jog_step_size()
    find_arrow_key_handlers()