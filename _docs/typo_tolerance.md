---
layout: post
title: Typo-Tolerant Sensor Resolution
date: 2025-10-31
---

# Typo-Tolerant Sensor Resolution

## Overview

OntoBot includes an advanced **typo-tolerant sensor name resolution system** that automatically corrects spelling errors, spacing issues, and formatting inconsistencies in sensor names. This feature ensures that users can query building systems using natural language without worrying about exact sensor name formatting.

## The Problem

In smart buildings, sensors have standardized naming conventions like:
- `NO2_Level_Sensor_5.09`
- `Air_Quality_Level_Sensor_5.01`
- `Carbon_Monoxide_Coal_Gas_Liquefied_MQ9_Gas_Sensor_5.25`

Users often make mistakes when referencing these sensors:
- **Spacing errors**: "NO2 Level Sensor 5.09" (spaces instead of underscores)
- **Typos**: "NO2 Levl Sensor 5.09" (misspelled "Level")
- **Case errors**: "NO2_Level_sensor_5.09" (wrong case on "sensor")
- **Number formatting**: "NO2 Level Sensor 5.9" (missing leading zero)

Without correction, these errors cause SPARQL query failures and frustrate users.

## The Solution

OntoBot implements a **three-layer defense system** to handle sensor name errors:

### Layer 1: Text Extraction
Automatically detects sensor mentions in natural language using regex patterns:

**Pattern 1**: Underscore-joined form
```python
"NO2_Level_Sensor_5.09" → NO2_Level_Sensor_5.09
```

**Pattern 2**: Space-separated form (natural language)
```python
"NO2 Level Sensor 5.09" → NO2_Level_Sensor_5.09
```

### Layer 2: Fuzzy Canonicalization
Maps extracted names to canonical forms using:
1. **Exact match** against `sensor_list.txt`
2. **Space/underscore normalization**
3. **RapidFuzz matching** with configurable threshold (default: 80)

```python
"NO2 Levl Sensor 5.09" → NO2_Level_Sensor_5.09 (fuzzy score: 97.5)
```

### Layer 3: SPARQL Postprocessing
Fixes residual issues in generated SPARQL as a safety net:
- Collapses spaces in sensor names: `Sensor 5.09` → `Sensor_5.09`
- Corrects prefixes: `brick:Air_Quality_Sensor_5.01` → `bldg:Air_Quality_Sensor_5.01`

## How It Works

### Step-by-Step Process

```
1. USER INPUT
   "what is NO2 sensor? where this NO2 Level sensor 5.09 is located?"
                              ↓
2. EXTRACTION
   Pattern match: "NO2 Level sensor 5.09"
   Normalized: "NO2_Level_Sensor_5.09"
                              ↓
3. CANONICALIZATION
   Fuzzy match against sensor_list.txt
   Match: "NO2_Level_Sensor_5.09" (exact, score: 100)
                              ↓
4. QUESTION REWRITE
   Original: "...where this NO2 Level sensor 5.09 is located?"
   Rewritten: "...where this NO2_Level_Sensor_5.09 is located?"
                              ↓
5. NL2SPARQL TRANSLATION
   Input: {"question": "...NO2_Level_Sensor_5.09...",
           "entity": "bldg:NO2_Level_Sensor_5.09"}
   Output: Valid SPARQL with correct sensor name
                              ↓
6. SPARQL POSTPROCESSING (Safety Net)
   Fix: "Sensor 5.09" → "Sensor_5.09"
   Fix: "brick:Type_Sensor_#" → "bldg:Type_Sensor_#"
                              ↓
7. EXECUTE SPARQL QUERY ✓
```

## Configuration

### Environment Variables

Configure the typo tolerance system in `docker-compose.bldgX.yml`:

```yaml
action_server_bldg1:
  environment:
    # Fuzzy matching threshold (0-100)
    # Lower = more tolerant, Higher = stricter
    - FUZZY_THRESHOLD=80
    
    # Auto-reload sensor_list.txt interval (seconds)
    - SENSOR_LIST_RELOAD_SEC=300
    
    # Path to sensor list file (optional override)
    - SENSOR_LIST_FILE=sensor_list.txt
```

### Threshold Tuning

**Lower Threshold (70-75)**:
- More lenient matching
- Tolerates more typos
- Risk of false positives (wrong sensor matched)
- Use when: Sensor names are very similar or users make many typos

**Default Threshold (80)**:
- Balanced approach
- Good typo tolerance with minimal false positives
- Recommended for most use cases

**Higher Threshold (85-95)**:
- Stricter matching
- Fewer false positives
- Requires more accurate user input
- Use when: Sensor names are distinct or accuracy is critical

## Examples

### Example 1: Space Normalization
```
Input:  "show me NO2  Level   Sensor  5.09"
Match:  NO2_Level_Sensor_5.09 (multiple spaces normalized)
Score:  97.67
Output: NO2_Level_Sensor_5.09
```

### Example 2: Typo Correction
```
Input:  "NO2 Levl Sensor 5.09"
Match:  NO2_Level_Sensor_5.09 (typo in "Level" corrected)
Score:  97.56
Output: NO2_Level_Sensor_5.09
```

### Example 3: Case Normalization
```
Input:  "NO2_Level_sensor_5.09"
Match:  NO2_Level_Sensor_5.09 (case corrected)
Score:  100 (exact after normalization)
Output: NO2_Level_Sensor_5.09
```

### Example 4: Number Formatting
```
Input:  "NO2 Level Sensor 5.9"
Match:  NO2_Level_Sensor_5.09 (leading zero added)
Score:  97.56
Output: NO2_Level_Sensor_5.09
```

### Example 5: Complex Sensor Names
```
Input:  "Carbon Monoxide Coal Gas Liquefied MQ9 Gas Sensor 5.25"
Match:  Carbon_Monoxide_Coal_Gas_Liquefied_MQ9_Gas_Sensor_5.25
Score:  100 (exact match)
Output: Carbon_Monoxide_Coal_Gas_Liquefied_MQ9_Gas_Sensor_5.25
```

## Building-Agnostic Design

The typo-tolerant system works across all buildings automatically:

✅ **No Hardcoding**: No sensor names in code  
✅ **Auto-Detection**: Loads sensor_list.txt from active building  
✅ **Auto-Reload**: Picks up changes within 300 seconds  
✅ **Portable**: Same code works for bldg1, bldg2, bldg3  

### How It Adapts

```
Building 1 Active:
  → Loads rasa-bldg1/actions/sensor_list.txt (680 sensors)
  → Fuzzy matches against ABACWS sensor names

Switch to Building 2:
  → Automatically loads rasa-bldg2/actions/sensor_list.txt (329 sensors)
  → Fuzzy matches against Office building sensor names

Switch to Building 3:
  → Automatically loads rasa-bldg3/actions/sensor_list.txt (597 sensors)
  → Fuzzy matches against Data Center sensor names
```

## Testing

### Manual Testing

```powershell
# Run standalone test script
cd rasa-bldg1/actions
python test_sensor_extraction.py

# Expected output:
[Test 1]
Input: what is NO2 sensor? where this NO2 Level sensor 5.09 is located?
Extracted: 1 sensor(s)
  'NO2 Level sensor 5.09' -> 'NO2_Level_Sensor_5.09'
Rewritten: ...NO2_Level_Sensor_5.09...
```

### Integration Testing

```powershell
# Test via Rasa UI
1. Navigate to http://localhost:3000
2. Send query: "what is NO2 sensor? where this NO2 Level sensor 5.09 is located?"
3. Verify: No SPARQL errors, correct sensor data returned

# Check logs for extraction
docker logs action_server_bldg1 --tail 50 | Select-String "Extracted sensors"

# Check logs for fuzzy matching
docker logs action_server_bldg1 --tail 50 | Select-String "Fuzzy-matched"
```

## Performance

### Metrics

- **Extraction**: ~5-10ms per query (regex + fuzzy matching)
- **Canonicalization**: ~2-5ms per sensor (cached list, threshold 80)
- **Postprocessing**: <1ms (simple regex replacements)
- **Total Overhead**: ~10-20ms per query

### Impact

The performance overhead is negligible compared to:
- NL2SPARQL translation: 200-500ms
- SPARQL execution: 100-300ms
- Analytics processing: 500-2000ms

Total query latency: 800-2800ms (typo tolerance adds <1%)

## Troubleshooting

### Issue: Sensor Not Detected

**Symptoms**: Extraction returns empty list

**Solutions**:
1. Check sensor exists in `sensor_list.txt`
2. Lower `FUZZY_THRESHOLD` (e.g., 70)
3. Add more regex patterns to extraction logic

### Issue: Wrong Sensor Matched

**Symptoms**: Fuzzy match returns incorrect sensor

**Solutions**:
1. Increase `FUZZY_THRESHOLD` (e.g., 90)
2. Check for duplicate/similar names in `sensor_list.txt`
3. Review fuzzy match logs for score details

### Issue: SPARQL Still Malformed

**Symptoms**: Parse errors after postprocessing

**Solutions**:
1. Check NL2SPARQL service logs
2. Manually inspect generated SPARQL in logs
3. Add additional patterns to `postprocess_sparql_query()`

## Migration to Custom Buildings

### Step 1: Prepare Sensor List

Create `sensor_list.txt` with canonical sensor names:

```
Air_Temperature_Sensor_1.01
CO2_Level_Sensor_1.01
Humidity_Sensor_1.01
...
```

### Step 2: Copy Code

The typo-tolerant code is already included in the action server. No code changes needed!

### Step 3: Configure Environment

```yaml
action_server_custom:
  environment:
    - FUZZY_THRESHOLD=80
    - SENSOR_LIST_RELOAD_SEC=300
    - SENSOR_LIST_FILE=sensor_list.txt  # Or custom path
```

### Step 4: Test

```powershell
# Test with your sensor names
cd rasa-custom/actions
python test_sensor_extraction.py
```

### Step 5: Tune Threshold

Monitor logs and adjust `FUZZY_THRESHOLD` based on:
- False positive rate (wrong sensors matched)
- False negative rate (sensors not matched)

## Implementation Details

### Key Methods

#### `extract_sensors_from_text(text: str) -> List[Tuple[str, str, str]]`
Extracts sensor mentions from natural language text using multiple regex patterns.

**Returns**: List of (original_mention, normalized_form, canonical_name) tuples

#### `_fuzzy_match_single(sensor_name: str, candidates: List[str]) -> Optional[str]`
Matches a single sensor name against the canonical list using:
1. Exact match
2. Space/underscore normalization
3. RapidFuzz WRatio scoring

**Returns**: Canonical name if score >= FUZZY_THRESHOLD, else None

#### `canonicalize_sensor_names(sensor_types: List[str]) -> List[str]`
Maps a list of sensor names to their canonical forms.

**Returns**: Deduplicated list of canonical sensor names

#### `postprocess_sparql_query(sparql: str) -> str`
Applies regex-based fixes to generated SPARQL queries:
- Fixes spaces in sensor names
- Corrects brick:/bldg: prefixes
- Collapses multiple spaces

**Returns**: Corrected SPARQL query string

#### `rewrite_question_with_sensors(question: str, mappings: List) -> str`
Replaces sensor mentions in the user's question with canonical forms.

**Returns**: Rewritten question string

### Algorithm: RapidFuzz WRatio

OntoBot uses **WRatio** (Weighted Ratio) scoring from RapidFuzz:

```python
from rapidfuzz import process as rf_process, fuzz as rf_fuzz

match = rf_process.extractOne(
    "NO2 Levl Sensor 5.09",  # Query
    candidates,               # List of canonical names
    scorer=rf_fuzz.WRatio     # Scoring function
)
# Returns: ("NO2_Level_Sensor_5.09", 97.5)
```

**Why WRatio?**
- Handles partial matches well
- Considers token order
- Performs well on multi-word strings
- Balances speed and accuracy

## Best Practices

### 1. Maintain Clean Sensor Lists

**Do**:
```
Air_Temperature_Sensor_1.01
Air_Temperature_Sensor_1.02
CO2_Level_Sensor_1.01
```

**Don't**:
```
Air_Temperature_Sensor_1.01
air_temperature_sensor_1.01  # Duplicate with different case
AirTemperatureSensor_1.01    # Different format
```

### 2. Use Consistent Naming

Follow a standard pattern:
```
{Type}_{Subtype}_{Sensor}_{Zone}.{Subzone}
```

Examples:
```
Air_Quality_Level_Sensor_5.01
Zone_Air_Humidity_Sensor_5.02
PM2.5_Level_Sensor_Atmospheric_5.03
```

### 3. Monitor Fuzzy Match Logs

Regularly check logs for:
- Low scores (< 85): May indicate missing sensors or typos in list
- High frequency matches: Common user mistakes to document

### 4. Update Threshold Based on Usage

Track metrics:
- False positive rate: Wrong sensor matched
- False negative rate: No match found
- Average match score

Adjust `FUZZY_THRESHOLD` accordingly.

### 5. Document Custom Sensor Names

For custom buildings, create documentation explaining:
- Naming convention
- Zone/subzone structure
- Sensor type abbreviations
- Common aliases

## Related Documentation

- **[Implementation Summary](https://github.com/suhasdevmane/OntoBot/blob/dev/rasa-bldg1/IMPLEMENTATION_SUMMARY.md)**: Technical details of code changes
- **[Quick Start Guide](https://github.com/suhasdevmane/OntoBot/blob/dev/rasa-bldg1/QUICK_START_TYPO_TOLERANCE.md)**: Deployment instructions
- **[Multi-Building Support](multi_building.md)**: Building-agnostic design
- **[Customization Guide](customization.md)**: Adapt to your building

---

**Typo-Tolerant Sensor Resolution** - Making building queries forgiving and user-friendly. 🔍✨
