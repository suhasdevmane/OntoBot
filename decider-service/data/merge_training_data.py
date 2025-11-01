"""
Merge existing training data with registry-generated data.
Deduplicates, balances, and creates final training dataset.
"""
import json
import os
from collections import Counter, defaultdict
from typing import List, Dict, Any

# Input files
EXISTING_DATA = "decider_training.direct.jsonl"  # Your manually created data
REGISTRY_DATA = "registry_training.jsonl"  # Generated from registry
ALL_FUNCTIONS_DATA = "all_functions_training.jsonl"  # All 93 functions
OUTPUT_FILE = "decider_training_full.jsonl"


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load JSONL file."""
    if not os.path.exists(path):
        print(f"Warning: {path} not found, skipping")
        return []
    
    data = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return data


def normalize_text(text: str) -> str:
    """Normalize text for deduplication."""
    import re
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text


def deduplicate_examples(examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate questions, keeping the first occurrence."""
    seen_texts = set()
    unique = []
    
    for ex in examples:
        norm_text = normalize_text(ex.get("text", ""))
        if norm_text not in seen_texts:
            seen_texts.add(norm_text)
            unique.append(ex)
    
    return unique


def balance_dataset(examples: List[Dict[str, Any]], max_per_label: int = 20) -> List[Dict[str, Any]]:
    """Balance dataset to prevent overfitting on frequent labels."""
    # Group by analytics label
    by_label = defaultdict(list)
    for ex in examples:
        label = ex.get("analytics") if ex.get("perform") == 1 else None
        by_label[label].append(ex)
    
    balanced = []
    
    # Add all ontology examples (perform=0)
    balanced.extend(by_label[None])
    
    # Balance analytics examples
    for label, items in by_label.items():
        if label is None:
            continue
        
        if len(items) > max_per_label:
            # Keep diverse examples (every nth item)
            step = len(items) / max_per_label
            sampled = [items[int(i * step)] for i in range(max_per_label)]
            balanced.extend(sampled)
        else:
            balanced.extend(items)
    
    return balanced


def main():
    data_dir = os.path.dirname(__file__)
    
    # Load datasets
    existing = load_jsonl(os.path.join(data_dir, EXISTING_DATA))
    registry = load_jsonl(os.path.join(data_dir, REGISTRY_DATA))
    all_functions = load_jsonl(os.path.join(data_dir, ALL_FUNCTIONS_DATA))
    
    print(f"Loaded {len(existing)} examples from existing dataset")
    print(f"Loaded {len(registry)} examples from registry")
    print(f"Loaded {len(all_functions)} examples from all functions")
    
    # Merge
    all_examples = existing + registry + all_functions
    print(f"Combined: {len(all_examples)} examples")
    
    # Deduplicate
    unique_examples = deduplicate_examples(all_examples)
    print(f"After deduplication: {len(unique_examples)} examples")
    
    # Balance
    balanced_examples = balance_dataset(unique_examples, max_per_label=25)
    print(f"After balancing: {len(balanced_examples)} examples")
    
    # Analyze distribution
    perform_dist = Counter(ex.get("perform") for ex in balanced_examples)
    analytics_dist = Counter(ex.get("analytics") for ex in balanced_examples if ex.get("perform") == 1)
    
    print(f"\nPerform distribution:")
    print(f"  perform=0 (no analytics): {perform_dist.get(0, 0)}")
    print(f"  perform=1 (analytics): {perform_dist.get(1, 0)}")
    
    print(f"\nTop 10 analytics labels:")
    for label, count in analytics_dist.most_common(10):
        print(f"  {label}: {count}")
    
    # Write output
    output_path = os.path.join(data_dir, OUTPUT_FILE)
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in balanced_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    print(f"\n✓ Saved {len(balanced_examples)} examples to {output_path}")
    print(f"\nTo train models, run:")
    print(f"  cd decider-service")
    print(f"  python training/train.py --data data/{OUTPUT_FILE}")


if __name__ == "__main__":
    main()
