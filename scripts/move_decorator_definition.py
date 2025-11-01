"""
Moves the @analytics_function decorator definition to the top of analytics_service.py
to resolve "analytics_function is not defined" lint errors.
"""

from pathlib import Path
import re

# Path to analytics_service.py
SERVICE_FILE = Path(__file__).parent.parent / "microservices" / "blueprints" / "analytics_service.py"

def move_decorator_to_top():
    """Move the decorator definition to after imports."""
    
    print(f"Reading {SERVICE_FILE}...")
    with open(SERVICE_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the decorator definition block (registry dict + function)
    decorator_start = None
    decorator_end = None
    
    for i, line in enumerate(lines):
        if line.strip() == '_analytics_registry_meta = {}':
            decorator_start = i
        if decorator_start is not None and line.strip() == 'return decorator':
            decorator_end = i + 1  # Include the 'return decorator' line
            break
    
    if decorator_start is None or decorator_end is None:
        print("❌ Could not find decorator definition block")
        return False
    
    print(f"Found decorator definition at lines {decorator_start+1}-{decorator_end+1}")
    
    # Extract the decorator block (including comments above it)
    # Look for the comment block above _analytics_registry_meta
    comment_start = decorator_start
    for i in range(decorator_start - 1, -1, -1):
        if lines[i].strip().startswith('#'):
            comment_start = i
        elif lines[i].strip() == '':
            continue
        else:
            break
    
    decorator_block = lines[comment_start:decorator_end]
    
    # Find where to insert: after _save_analytics_meta() function
    insert_position = None
    for i, line in enumerate(lines):
        if 'def _save_analytics_meta():' in line:
            # Find the end of this function
            for j in range(i + 1, len(lines)):
                if lines[j].strip() and not lines[j].startswith(' ') and not lines[j].startswith('\t'):
                    insert_position = j
                    break
                elif j < len(lines) - 1 and lines[j].strip() and lines[j + 1].strip() == '':
                    # End of function before blank line
                    insert_position = j + 1
                    break
            break
    
    if insert_position is None:
        print("❌ Could not find insertion point after _save_analytics_meta")
        return False
    
    print(f"Will insert decorator at line {insert_position+1}")
    
    # Remove decorator from old location
    new_lines = lines[:comment_start] + lines[decorator_end:]
    
    # Insert decorator at new location (adjust for removed lines)
    if insert_position > decorator_end:
        adjusted_insert = insert_position - (decorator_end - comment_start)
    else:
        adjusted_insert = insert_position
    
    # Add blank lines around decorator for readability
    new_lines = (new_lines[:adjusted_insert] + 
                 ['\n'] + 
                 decorator_block + 
                 ['\n'] + 
                 new_lines[adjusted_insert:])
    
    # Write back
    print(f"Writing modified file...")
    with open(SERVICE_FILE, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("✅ Successfully moved decorator definition to top of file")
    print("   This should resolve all 'analytics_function is not defined' lint errors")
    return True

if __name__ == "__main__":
    print("="*60)
    print("Moving @analytics_function decorator to top of file")
    print("="*60)
    print()
    
    success = move_decorator_to_top()
    
    if success:
        print("\n✅ Done! Decorator is now defined before all functions that use it.")
        print("   Lint errors should be resolved.")
    else:
        print("\n❌ Failed to move decorator. Manual intervention may be required.")
