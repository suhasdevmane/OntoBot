"""
Generate comprehensive training data from ALL 80+ analytics functions.
Fetches registry and creates extensive question variations for each function.
"""
import json
import os
import re
from typing import List, Dict, Any
from urllib import request as urlrequest

MICRO_BASE_URL = os.getenv("MICROSERVICES_BASE_URL", "http://localhost:6001")
OUTPUT_FILE = "registry_training.jsonl"


def fetch_registry() -> List[Dict[str, Any]]:
    """Fetch ALL analytics functions from microservices registry."""
    url = f"{MICRO_BASE_URL}/analytics/functions"
    print(f"Fetching registry from {url}...")
    try:
        req = urlrequest.Request(url, headers={"Accept": "application/json"})
        with urlrequest.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            functions = data.get("functions", [])
            print(f"✓ Fetched {len(functions)} functions from registry")
            return functions
    except Exception as e:
        print(f"✗ Error fetching registry: {e}")
        print("  Ensure microservices is running: docker-compose up -d microservices")
        return []


def clean_pattern(pat: str) -> List[str]:
    """Extract meaningful phrases from regex patterns."""
    results = []
    
    # Remove regex special chars but preserve word boundaries
    simple = re.sub(r'\.\*', ' ', pat)
    simple = re.sub(r'[()\[\]\\|]', ' ', simple)
    simple = re.sub(r'\?', '', simple)
    simple = re.sub(r'\s+', ' ', simple).strip()
    
    if len(simple) > 3 and simple.count(' ') <= 8:
        results.append(simple)
    
    # Try to extract alternatives from (option1|option2) patterns
    alt_matches = re.findall(r'\(([^)]+)\)', pat)
    for alt_group in alt_matches:
        if '|' in alt_group:
            for opt in alt_group.split('|'):
                opt_clean = opt.strip()
                if len(opt_clean) > 2:
                    # Build variations
                    base = re.sub(r'\([^)]+\)', opt_clean, pat)
                    base = re.sub(r'[()[\]\\|]', '', base)
                    base = re.sub(r'\s+', ' ', base).strip()
                    if len(base) > 3:
                        results.append(base)
    
    return results


def generate_variations(function_name: str, description: str, patterns: List[str]) -> List[str]:
    """Generate 20+ natural language question variations for each function."""
    questions = set()
    
    # Extract from patterns
    for pat in patterns:
        for phrase in clean_pattern(pat):
            questions.add(phrase)
            # Add question forms
            questions.add(f"show me {phrase}")
            questions.add(f"can you {phrase}")
            questions.add(f"analyze {phrase}")
            questions.add(f"calculate {phrase}")
            questions.add(f"what is the {phrase}")
    
    # Extract key terms from description
    desc_lower = description.lower()
    
    # Common templates based on description keywords
    templates = [
        "{keyword}",
        "show me {keyword}",
        "analyze {keyword}",
        "calculate {keyword}",
        "what is the {keyword}",
        "can you analyze {keyword}",
        "give me {keyword}",
        "display {keyword}",
        "compute {keyword}",
        "check {keyword}",
        "find {keyword}",
        "get {keyword}",
        "detect {keyword}",
        "identify {keyword}",
        "measure {keyword}",
        "monitor {keyword}",
        "track {keyword}",
        "evaluate {keyword}",
        "assess {keyword}",
    ]
    
    # Extract meaningful noun phrases from description (3-5 words)
    desc_words = desc_lower.split()
    for i in range(len(desc_words) - 2):
        phrase = ' '.join(desc_words[i:i+3])
        phrase = re.sub(r'[^a-z0-9\s]', '', phrase).strip()
        if len(phrase) > 10 and not phrase.startswith(('the ', 'and ', 'or ', 'for ', 'with ')):
            for template in templates[:10]:  # Use first 10 templates
                questions.add(template.format(keyword=phrase))
    
    # Function name variations (convert underscores to spaces)
    fn_readable = function_name.replace('_', ' ').replace('analyze ', '').replace('detect ', '').replace('compute ', '')
    questions.add(fn_readable)
    questions.add(f"show me {fn_readable}")
    questions.add(f"analyze {fn_readable}")
    questions.add(f"calculate {fn_readable}")
    questions.add(f"what is the {fn_readable}")
    questions.add(f"can you analyze {fn_readable}")
    
    # Add domain-specific variations based on keywords in description
    keywords_map = {
        'temperature': ['temp', 'thermal', 'heating', 'cooling', 'degrees'],
        'humidity': ['moisture', 'rh', 'relative humidity', 'dampness'],
        'co2': ['carbon dioxide', 'co2 levels', 'co2 ppm', 'air quality co2'],
        'pressure': ['static pressure', 'differential pressure', 'pressure drop'],
        'airflow': ['air flow', 'cfm', 'air volume', 'ventilation rate'],
        'energy': ['power', 'electricity', 'consumption', 'demand', 'kw', 'kwh'],
        'setpoint': ['target', 'desired value', 'control point', 'set point'],
        'anomaly': ['outlier', 'abnormal', 'unusual', 'irregular', 'fault'],
        'trend': ['pattern', 'tendency', 'direction', 'slope', 'change over time'],
        'efficiency': ['performance', 'cop', 'eer', 'effectiveness'],
        'compliance': ['conformance', 'adherence', 'meeting requirements', 'within limits'],
        'failure': ['fault', 'malfunction', 'breakdown', 'error', 'problem'],
        'correlation': ['relationship', 'connection', 'association', 'dependency'],
        'forecast': ['prediction', 'projection', 'future', 'estimate', 'anticipate'],
        'baseline': ['reference', 'normal', 'typical', 'standard', 'historical'],
        'deviation': ['difference', 'variance', 'offset', 'divergence', 'gap'],
        'alarm': ['alert', 'warning', 'notification', 'event', 'trigger'],
        'filter': ['air filter', 'filtration', 'filter health', 'filter status'],
        'damper': ['damper position', 'damper control', 'modulating damper'],
        'coil': ['heating coil', 'cooling coil', 'heat exchanger'],
        'chiller': ['chilled water', 'chiller plant', 'cooling system'],
        'pump': ['circulation pump', 'water pump', 'pump operation'],
        'fan': ['supply fan', 'exhaust fan', 'fan speed', 'vfd'],
        'economizer': ['free cooling', 'outdoor air', 'air-side economizer'],
        'occupancy': ['occupied', 'people count', 'occupants', 'vacancy'],
        'schedule': ['time schedule', 'operating hours', 'calendar'],
    }
    
    for keyword, synonyms in keywords_map.items():
        if keyword in desc_lower:
            for syn in synonyms[:3]:  # Use first 3 synonyms
                questions.add(f"analyze {syn}")
                questions.add(f"show me {syn}")
                questions.add(f"what is the {syn}")
    
    # Limit to 25 most diverse questions
    questions_list = list(questions)
    if len(questions_list) > 25:
        # Prioritize: keep shorter, more natural questions
        questions_list.sort(key=lambda q: (len(q), -q.count(' ')))
        questions_list = questions_list[:25]
    
    return questions_list


def generate_ontology_examples() -> List[Dict[str, Any]]:
    """Generate ontology/TTL-only questions (perform=0)."""
    ontology_questions = [
        "list all temperature sensors",
        "show me sensors in zone 2",
        "what sensors are in the building",
        "describe the sensor hierarchy",
        "show me all HVAC equipment",
        "list all zones",
        "what rooms are in zone 3",
        "show me the building structure",
        "list all equipment types",
        "what is the Brick schema",
        "show me sensor relationships",
        "list all points",
        "what equipment is in room 101",
        "show me the ontology",
        "describe the HVAC system",
        "list all air handling units",
        "what sensors measure CO2",
        "show me all VAV boxes",
        "list all temperature setpoints",
        "what is the building layout",
        "show me all sensor types",
        "list chillers in the building",
        "what zones have humidity sensors",
        "show me equipment hierarchy",
        "list all damper positions",
        "what is a VAV box",
        "show me all meters",
        "list occupancy sensors",
        "what equipment is controlled",
        "show me the floor plan",
    ]
    
    examples = []
    for q in ontology_questions:
        examples.append({
            "text": q,
            "perform": 0,
            "analytics": None
        })
    
    return examples


def main():
    """Generate comprehensive training data from ALL registry functions."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, OUTPUT_FILE)
    
    print("=" * 80)
    print("GENERATING COMPREHENSIVE TRAINING DATA")
    print("=" * 80)
    
    # Fetch registry
    functions = fetch_registry()
    if not functions:
        print("\n✗ No functions fetched. Exiting.")
        return 1
    
    print(f"\n[1/3] Processing {len(functions)} analytics functions...")
    
    # Generate training examples for each function
    all_examples = []
    for i, func in enumerate(functions, 1):
        name = func.get("name", "unknown")
        description = func.get("description", "")
        patterns = func.get("patterns", [])
        
        variations = generate_variations(name, description, patterns)
        
        for question in variations:
            all_examples.append({
                "text": question,
                "perform": 1,
                "analytics": name
            })
        
        print(f"  [{i}/{len(functions)}] {name}: generated {len(variations)} questions")
    
    print(f"\n✓ Generated {len(all_examples)} analytics training examples")
    
    # Add ontology examples
    print("\n[2/3] Adding ontology/TTL-only examples...")
    ontology_examples = generate_ontology_examples()
    all_examples.extend(ontology_examples)
    print(f"✓ Added {len(ontology_examples)} ontology examples")
    
    # Write output
    print(f"\n[3/3] Writing to {OUTPUT_FILE}...")
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    
    print(f"✓ Saved {len(all_examples)} total examples")
    
    # Statistics
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    analytics_examples = [ex for ex in all_examples if ex["perform"] == 1]
    analytics_dist = {}
    for ex in analytics_examples:
        fn = ex["analytics"]
        analytics_dist[fn] = analytics_dist.get(fn, 0) + 1
    
    print(f"Total examples: {len(all_examples)}")
    print(f"  Perform=1 (analytics): {len(analytics_examples)}")
    print(f"  Perform=0 (ontology): {len(ontology_examples)}")
    print(f"Unique analytics functions: {len(analytics_dist)}")
    print(f"Avg questions per function: {len(analytics_examples) / len(analytics_dist):.1f}")
    
    print(f"\nTop 10 functions by example count:")
    for fn, count in sorted(analytics_dist.items(), key=lambda x: -x[1])[:10]:
        print(f"  {fn}: {count}")
    
    print(f"\n✓ Training data generation complete!")
    print(f"✓ Output: {output_path}")
    print(f"\nNext steps:")
    print(f"  1. python merge_training_data.py")
    print(f"  2. cd .. && python training/train.py --data data/decider_training_full.jsonl")
    print(f"  3. docker-compose restart decider-service")
    
    return 0


if __name__ == "__main__":
    exit(main())
