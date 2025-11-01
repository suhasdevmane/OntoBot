"""
Fix training data labels: If an example has analytics function specified,
it MUST have perform=1 (because analytics functions perform analytics!).
"""
import json
import os

DATA_DIR = os.path.dirname(__file__)
INPUT_FILE = os.path.join(DATA_DIR, "decider_training_full.jsonl")
OUTPUT_FILE = os.path.join(DATA_DIR, "decider_training_full_fixed.jsonl")

def fix_labels():
    """Fix inconsistent labels where analytics is set but perform=0."""
    
    examples = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    ex = json.loads(line)
                    examples.append(ex)
                except json.JSONDecodeError:
                    continue
    
    print(f"Loaded {len(examples)} examples")
    
    # Fix inconsistent labels
    fixed_count = 0
    for ex in examples:
        analytics = ex.get("analytics")
        perform = ex.get("perform")
        
        # If analytics function is specified, perform MUST be 1
        if analytics is not None and analytics != "" and perform != 1:
            ex["perform"] = 1
            fixed_count += 1
    
    print(f"Fixed {fixed_count} inconsistent labels")
    
    # Analyze distribution after fix
    perform_0 = sum(1 for ex in examples if ex.get("perform") == 0)
    perform_1 = sum(1 for ex in examples if ex.get("perform") == 1)
    
    print(f"\nDistribution after fix:")
    print(f"  perform=0 (no analytics): {perform_0}")
    print(f"  perform=1 (analytics): {perform_1}")
    
    # Count analytics functions
    analytics_set = set()
    for ex in examples:
        if ex.get("perform") == 1 and ex.get("analytics"):
            analytics_set.add(ex.get("analytics"))
    
    print(f"  Unique analytics functions: {len(analytics_set)}")
    
    # Write fixed data
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    print(f"\n✓ Saved fixed data to {OUTPUT_FILE}")
    print(f"✓ Ready to retrain models!")
    
    return fixed_count

if __name__ == "__main__":
    count = fix_labels()
    
    if count > 0:
        print(f"\n{'='*60}")
        print(f"IMPORTANT: {count} examples were incorrectly labeled!")
        print(f"{'='*60}")
        print(f"\nNext steps:")
        print(f"  1. Backup old models: mv model model.backup")
        print(f"  2. Train with fixed data:")
        print(f"     cd training")
        print(f"     python train.py --data ../data/decider_training_full_fixed.jsonl")
        print(f"  3. Restart decider service:")
        print(f"     docker-compose -f docker-compose.bldg1.yml restart decider-service")
