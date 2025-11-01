"""
Test sensor extraction and canonicalization from natural language text.

This demonstrates the typo-tolerant sensor name resolution that works
across any building when sensor_list.txt changes.
"""
import re
from typing import List, Tuple, Optional
from rapidfuzz import process as rf_process, fuzz as rf_fuzz

# Mock get_valid_sensor_types for testing
def get_valid_sensor_types() -> set:
    """Load from sensor_list.txt for testing."""
    with open('sensor_list.txt', 'r') as f:
        return {line.strip() for line in f if line.strip() and not line.startswith('#')}

FUZZY_THRESHOLD = 80

def extract_sensors_from_text(text: str) -> List[Tuple[str, str, str]]:
    """Extract sensor mentions from natural language text.
    
    Returns: List of (original_mention, normalized_form, canonical_name) tuples
    """
    if not isinstance(text, str) or not text.strip():
        return []
    
    results: List[Tuple[str, str, str]] = []
    candidates = sorted(get_valid_sensor_types())
    
    # Pattern 1: Underscore-joined form (already canonical)
    pattern1 = r'\b([A-Za-z0-9_]+_[Ss]ensor_\d+(?:\.\d+)?)\b'
    for match in re.finditer(pattern1, text, re.IGNORECASE):
        original = match.group(1)
        normalized = original.replace('_sensor_', '_Sensor_')
        canonical = fuzzy_match_single(normalized, candidates)
        if canonical:
            results.append((original, normalized, canonical))
    
    # Pattern 2: Space-separated form "Prefix words sensor number"
    pattern2 = r'\b([A-Z][A-Za-z0-9_\s]+?)\s+[Ss]ensor\s+(\d+(?:\.\d+)?)\b'
    for match in re.finditer(pattern2, text):
        original = match.group(0)
        prefix = match.group(1).strip().replace(' ', '_')
        number = match.group(2)
        normalized = f"{prefix}_Sensor_{number}"
        canonical = fuzzy_match_single(normalized, candidates)
        if canonical:
            results.append((original, normalized, canonical))
    
    # Deduplicate by canonical name
    seen = set()
    unique_results = []
    for orig, norm, canon in results:
        if canon not in seen:
            seen.add(canon)
            unique_results.append((orig, norm, canon))
    
    return unique_results

def fuzzy_match_single(sensor_name: str, candidates: List[str]) -> Optional[str]:
    """Fuzzy match a single sensor name against candidates."""
    if not sensor_name or not candidates:
        return None
    
    s_stripped = sensor_name.strip()
    
    # Exact match first
    if s_stripped in candidates:
        return s_stripped
    
    # Try underscore/space swap
    alt = s_stripped.replace(' ', '_') if ' ' in s_stripped else s_stripped.replace('_', ' ')
    if alt in candidates:
        return alt.replace(' ', '_')
    
    # Fuzzy match
    try:
        match = rf_process.extractOne(s_stripped, candidates, scorer=rf_fuzz.WRatio)
        if match and match[1] >= FUZZY_THRESHOLD:
            print(f"✓ Fuzzy-matched '{s_stripped}' -> '{match[0]}' (score={match[1]})")
            return match[0]
        
        # Try with alt form
        match2 = rf_process.extractOne(alt, candidates, scorer=rf_fuzz.WRatio)
        if match2 and match2[1] >= FUZZY_THRESHOLD:
            print(f"✓ Fuzzy-matched (alt) '{s_stripped}' -> '{match2[0]}' (score={match2[1]})")
            return match2[0]
    except Exception as e:
        print(f"⚠ Fuzzy match error for '{s_stripped}': {e}")
    
    return None

def rewrite_question_with_sensors(question: str, sensor_mappings: List[Tuple[str, str, str]]) -> str:
    """Rewrite question replacing sensor mentions with canonical forms."""
    rewritten = question
    # Sort by length (longest first) to avoid partial replacements
    sorted_mappings = sorted(sensor_mappings, key=lambda x: len(x[0]), reverse=True)
    
    for original, _, canonical in sorted_mappings:
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        rewritten = pattern.sub(canonical, rewritten)
    
    return rewritten

# Test cases
if __name__ == "__main__":
    test_cases = [
        # Original user request
        "what is NO2 sensor? what does it measure? where this NO2 Level sensor 5.09 is located?",
        
        # Additional typo variations
        "show me NO2  Level   Sensor  5.09",  # Multiple spaces
        "NO2_Level_sensor_5.09",  # Wrong case
        "NO2 Levl Sensor 5.09",  # Typo in "Level"
        "NO2 Level Sensor 5.9",  # Missing leading zero
        
        # Complex sensor name
        "Carbon Monoxide Coal Gas Liquefied MQ9 Gas Sensor 5.25",
        "Carbon_Monoxide_Coal_Gas_Liquefied_MQ9_Gas_Sensor_5.25",
        
        # Mixed patterns
        "compare Air_Quality_Level_Sensor_5.01 with NO2 Level Sensor 5.09",
    ]
    
    print("=" * 80)
    print("SENSOR EXTRACTION & CANONICALIZATION TEST")
    print("Building-agnostic typo-tolerant resolution using sensor_list.txt")
    print("=" * 80)
    
    for i, question in enumerate(test_cases, 1):
        print(f"\n[Test {i}]")
        print(f"Input: {question}")
        
        mappings = extract_sensors_from_text(question)
        if mappings:
            print(f"Extracted: {len(mappings)} sensor(s)")
            for orig, norm, canon in mappings:
                print(f"  '{orig}' -> '{canon}'")
            
            rewritten = rewrite_question_with_sensors(question, mappings)
            if rewritten != question:
                print(f"Rewritten: {rewritten}")
        else:
            print("No sensors extracted")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
