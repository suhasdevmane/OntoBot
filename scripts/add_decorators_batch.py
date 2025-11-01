"""
Batch adds @analytics_function decorators to all analytics functions in analytics_service.py.
This script will insert decorators before function definitions.
"""

import re
from pathlib import Path
from analytics_decorators import FUNCTION_DECORATORS

# Path to analytics_service.py
SERVICE_FILE = Path(__file__).parent.parent / "microservices" / "blueprints" / "analytics_service.py"

def format_decorator(func_name, config):
    """Format the decorator string for a function."""
    patterns_str = ",\n        ".join([f'r"{p}"' for p in config['patterns']])
    
    decorator = f'''@analytics_function(
    patterns=[
        {patterns_str}
    ],
    description="{config['description']}"
)
'''
    return decorator

def add_decorators():
    """Add decorators to all functions in analytics_service.py."""
    
    # Read the file
    print(f"Reading {SERVICE_FILE}...")
    with open(SERVICE_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    functions_decorated = 0
    functions_skipped = 0
    
    # Process each function in the decorator mapping
    for func_name, config in FUNCTION_DECORATORS.items():
        # Check if function already has decorator
        if f'@analytics_function\ndef {func_name}(' in content or \
           f'@analytics_function(\ndef {func_name}(' in content:
            print(f"  ⏭️  Skipping {func_name} (already has decorator)")
            functions_skipped += 1
            continue
        
        # Find the function definition
        pattern = rf'^def {func_name}\('
        match = re.search(pattern, content, re.MULTILINE)
        
        if not match:
            print(f"  ⚠️  Warning: Function {func_name} not found in file")
            continue
        
        # Get the start position of the function definition
        func_start = match.start()
        
        # Find the start of the line (to preserve indentation)
        line_start = content.rfind('\n', 0, func_start) + 1
        indent = content[line_start:func_start]
        
        # Format the decorator with proper indentation
        decorator_text = format_decorator(func_name, config)
        decorator_lines = decorator_text.split('\n')
        indented_decorator = '\n'.join(indent + line for line in decorator_lines)
        
        # Insert the decorator before the function definition
        content = content[:line_start] + indented_decorator + '\n' + content[line_start:]
        
        functions_decorated += 1
        print(f"  ✅ Added decorator to {func_name}")
    
    # Write the modified content back
    if functions_decorated > 0:
        print(f"\nWriting changes to {SERVICE_FILE}...")
        with open(SERVICE_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n{'='*60}")
        print(f"✅ Successfully decorated {functions_decorated} functions")
        print(f"⏭️  Skipped {functions_skipped} functions (already decorated)")
        print(f"📝 Total decorators in mapping: {len(FUNCTION_DECORATORS)}")
        print(f"{'='*60}")
        
        # Create backup of original
        backup_file = SERVICE_FILE.with_suffix('.py.backup')
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(original_content)
        print(f"\n💾 Backup saved to: {backup_file}")
        
    else:
        print("\n⚠️  No functions were decorated. All functions may already have decorators.")

if __name__ == "__main__":
    print("="*60)
    print("Analytics Function Decorator Batch Addition")
    print("="*60)
    print(f"\nTarget file: {SERVICE_FILE}")
    print(f"Decorators to add: {len(FUNCTION_DECORATORS)}\n")
    
    add_decorators()
    
    print("\n✅ Done! Next steps:")
    print("  1. Restart microservices: docker-compose restart microservices")
    print("  2. Verify registry: curl http://localhost:6001/analytics/functions | jq '.functions | length'")
    print("  3. Regenerate training: cd decider-service/data && python generate_training_from_registry.py")
    print("  4. Merge and retrain: python merge_training_data.py && python ../training/train.py")
