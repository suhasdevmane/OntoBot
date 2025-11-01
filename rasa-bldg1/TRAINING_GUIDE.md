# Building-Agnostic Rasa Training Guide

## Overview
This Rasa model is designed to be **building-agnostic**, meaning it can work with different buildings by simply updating the sensor list and retraining.

## Architecture

### Pipeline Flow
```
User Input
   ↓
Questions_to_brickbot intent → ActionQuestionToBrickbot
   ↓
[NL2SPARQL translation] → [SPARQL query to Fuseki]
   ↓
[If timeseries found] → date_range_choice_form
   ↓
ValidateDatesForm (Duckling time entity extraction with roles: start/end)
   ↓
ActionProcessTimeseries (MySQL/TimescaleDB/Cassandra fetch + Analytics)
   ↓
Summarization (Ollama/Mistral) → ActionResetSlots
```

### Essential Actions
All 9 actions in domain.yml are required:

1. **action_question_to_brickbot** - Main entry point for sensor queries
2. **action_process_timeseries** - Fetches SQL data and runs analytics
3. **action_generate_and_share_data** - Test action for file generation
4. **validate_sensor_form** - Validates sensor types against sensor_list.txt
5. **validate_dates_form** - Validates start/end dates
6. **validate_date_range_choice_form** - Validates date range selection
7. **action_route_after_date_choice** - Routes based on date choice (last24h/custom)
8. **action_reset_slots** - Cleanup after completion
9. **action_debug_entities** - Debug tool (useful for development)

## Building-Specific Customization

### 1. Sensor List (`data/sensor_list.txt`)
**Purpose:** Contains all valid sensor instances for the current building.

**Format:** One sensor per line
```
Air_Quality_Level_Sensor_5.01
Air_Temperature_Sensor_5.02
CO2_Level_Sensor_5.03
...
```

**Building-Specific Differences:**
- **Building 1 (bldg1):** Uses MySQL, sensors named `*_5.*`
- **Building 2 (bldg2):** Uses TimescaleDB, different sensor naming
- **Building 3 (bldg3):** Uses Cassandra, different schema

### 2. Sensor UUID Mappings (`actions/sensor_uuids.txt`)
**Purpose:** Maps human-readable sensor names to UUID column names in the database.

**Format:** `sensor_name,uuid` (comma-separated)
```
Air_Temperature_Sensor_5.01,249a4c9c-fe31-4649-a119-452e5e8e7dc5
Zone_Air_Humidity_Sensor_5.02,3f8b2e1a-9c4d-4e6f-8a7b-1d5c9e2f4a8b
```

**Why Needed:**
- Database columns are UUID-based (`249a4c9c-...`)
- User speaks in sensor names (`Air_Temperature_Sensor_5.01`)
- Actions convert between both for queries and summaries

## Retraining for a New Building

### Step 1: Update Sensor List
1. Get the new building's sensor inventory
2. Replace `data/sensor_list.txt` with the new list
3. Ensure format is consistent (one sensor per line, no extra whitespace)

### Step 2: Update UUID Mappings
1. Query the new building's database to get UUID→name mappings
2. Update `actions/sensor_uuids.txt`
3. Validate format: `sensor_name,uuid` with no extra spaces

### Step 3: Update Lookup Table
The existing `data/nlu/sensor_lookup.yml` already references `sensor_list.txt` entries.

If sensors have changed significantly:
```bash
# Regenerate lookup file from sensor_list.txt
pwsh -Command "Get-Content data/sensor_list.txt | ForEach-Object { '      - ' + $_ } | Set-Content data/nlu/sensor_lookup.yml -Encoding UTF8"
```

### Step 4: Validate Training Data
```bash
cd rasa-bldg1
rasa data validate -v
```

**Expected warnings (safe to ignore):**
- `utter_ask_date_range_mode not used in story` - Used by forms automatically
- `provide_sensor_type not used in story` - Used for slot filling

### Step 5: Train Model
```bash
# Via Docker (recommended)
docker compose --project-directory . run --rm rasa-train

# Or locally
rasa train
```

### Step 6: Test
```bash
# Interactive shell test
rasa shell

# Example queries:
# "Show me air quality for Air_Quality_Sensor_5.01 from 01/02/2025 to 02/02/2025"
# "Analyze humidity trends for Zone_Air_Humidity_Sensor_5.05 last 7 days"
```

## Date Extraction Strategy

### Duckling Integration
The model uses **DucklingEntityExtractor** to extract dates with roles:

**Entity:** `time` with roles `start` and `end`

**Supported Formats:**
- Explicit: `from 01/02/2025 to 02/02/2025`
- ISO: `from 2025-02-01 to 2025-02-07`
- Intervals: `from yesterday to today`
- Relative: `last 24 hours`, `past week`, `last month`

**Domain Mapping Strategy:**
```yaml
start_date:
  mappings:
    - type: from_entity
      entity: time
      role: start
    - type: from_entity
      entity: time
      role: end
      conditions:
        - active_loop: dates_form
        - requested_slot: start_date
```

This allows:
1. **Primary:** Extract `time:start` → `start_date` slot
2. **Fallback:** If user provides `time:end` when `start_date` is needed, use it

### Date Validation Flow
1. **ValidateDatesForm** extracts dates from entities
2. Handles multiple formats: DD/MM/YYYY, YYYY-MM-DD, ISO 8601
3. Resolves relative phrases (today, yesterday, last week)
4. Ensures end_date > start_date
5. Converts to SQL format: `YYYY-MM-DD HH:MM:SS`

## NLU Training Strategy

### Generic Intent Examples
The NLU uses **building-agnostic examples** to ensure portability:

```yaml
# ✅ GOOD - Generic sensor patterns
- analyze humidity for [Zone_Air_Humidity_Sensor](sensor_type)
- check [CO2_Level_Sensor](sensor_type) readings

# ❌ AVOID - Building-specific instances  
- analyze [Zone_Air_Humidity_Sensor_5.05](sensor_type)
```

### Lookup Tables
**Purpose:** Train the model to recognize all valid sensor names without hardcoding them in intent examples.

**File:** `data/nlu/sensor_lookup.yml`
```yaml
nlu:
  - lookup: sensor_type
    examples: |
      - Air_Quality_Level_Sensor_5.01
      - Air_Quality_Sensor_5.02
      - ...all entries from sensor_list.txt...
```

**How It Works:**
1. `RegexEntityExtractor` uses lookup table during training
2. Model learns to recognize sensor name patterns
3. At runtime, extracts any sensor matching the learned patterns
4. `ValidateSensorForm` validates against `sensor_list.txt`

### Entity Extraction
**Regex Pattern:**
```yaml
- regex: sensor_type
  examples: |
    - (?:(?:[A-Za-z]+(?:[_\s][A-Za-z0-9]+)*)[_\s]Sensor[_\s][0-9]+(?:\.[0-9]+)?)
```

This matches:
- `Air_Temperature_Sensor_5.01`
- `CO2_Level_Sensor_5.14`
- `Zone_Air_Humidity_Sensor_5.22`

## Database Flexibility

### Multi-Database Support
Actions.py supports multiple database backends via environment variables:

**MySQL (Building 1):**
```env
DB_HOST=mysqlserver
DB_PORT=3306
DB_NAME=sensordb
DB_TABLE=sensor_data
DB_USER=root
DB_PASSWORD=mysql
```

**TimescaleDB (Building 2):**
```env
DB_HOST=timescaledb
DB_PORT=5432
...
```

**Cassandra (Building 3):**
```env
DB_HOST=cassandra
DB_PORT=9042
...
```

### Dynamic SQL Query
The `fetch_sql_data` method constructs queries dynamically:
```python
# Builds: SELECT `Datetime`, `uuid1`, `uuid2` FROM table WHERE ...
columns = ["`Datetime`"] + [f"`{tid}`" for tid in timeseries_ids]
query = f"SELECT {columns_str} FROM `{database}`.`{table_name}` WHERE `Datetime` BETWEEN %s AND %s"
```

## Analytics Integration

### Decider Service
**Purpose:** Classifies user questions to select the appropriate analytics type.

**Endpoint:** `POST /decide`
```json
{
  "question": "Show me humidity trends",
  "analytics": "analyze_humidity",
  "perform_analytics": true
}
```

### Supported Analytics
All analytics are defined in `actions.py`:
```python
_STATIC_ANALYTICS_FALLBACK = {
    "analyze_humidity",
    "analyze_temperatures",
    "analyze_co2_levels",
    "analyze_pm_levels",
    "correlate_sensors",
    "detect_potential_failures",
    "analyze_sensor_trend",
    ...
}
```

## Testing & Validation

### 1. Validate Training Data
```bash
rasa data validate -v
```

### 2. Test Date Extraction
```python
# In rasa shell:
"analyze air quality from 01/02/2025 to 07/02/2025"
# Should extract: start_date="01/02/2025", end_date="07/02/2025"

"show me last week trends"
# Should auto-fill: start_date=[7 days ago], end_date=[now]
```

### 3. Test Sensor Validation
```python
# Valid sensor (in sensor_list.txt)
"show Air_Temperature_Sensor_5.01"
# Should proceed to date collection

# Invalid sensor
"show Air_Temperature_Sensor_99.99"
# Should ask: "Please provide a valid sensor type"
```

### 4. Test Analytics Flow
```python
"correlate Air_Temperature_Sensor_5.01 and Zone_Air_Humidity_Sensor_5.02 last 30 days"
# Should:
# 1. Extract sensors and dates
# 2. Query SQL
# 3. Call analytics microservice
# 4. Generate summary
```

## Common Issues & Solutions

### Issue: "Invalid sensor type"
**Cause:** Sensor not in `sensor_list.txt`
**Solution:** Add sensor to the list and retrain

### Issue: Dates not extracted
**Cause:** Duckling server not running or wrong URL
**Solution:** Check `config.yml` DucklingEntityExtractor URL

### Issue: UUID not found in SQL
**Cause:** Mismatch between `sensor_uuids.txt` and database columns
**Solution:** Verify UUID mappings match the database schema

### Issue: Analytics returns error
**Cause:** Incompatible data format
**Solution:** Check analytics microservice logs for expected payload shape

## Production Deployment

### Environment Variables
```bash
# Core services
NL2SPARQL_URL=http://nl2sparql:6005/nl2sparql
FUSEKI_URL=http://jena-fuseki-rdf-store:3030/trial/sparql
ANALYTICS_URL=http://microservices:6000/analytics/run
DECIDER_URL=http://decider-service:6009/decide
SUMMARIZATION_URL=http://ollama:11434

# Database (varies per building)
DB_HOST=mysqlserver
DB_PORT=3306
DB_NAME=sensordb
DB_TABLE=sensor_data
DB_USER=root
DB_PASSWORD=mysql

# File serving
BASE_URL=http://localhost:8080
```

### Docker Compose
```bash
# Building 1 stack
docker-compose -f docker-compose.bldg1.yml up -d

# Building 2 stack  
docker-compose -f docker-compose.bldg2.yml up -d

# Building 3 stack
docker-compose -f docker-compose.bldg3.yml up -d
```

## Summary

✅ **Building-agnostic by design**
- Update `sensor_list.txt` and `sensor_uuids.txt`
- Retrain model
- Update environment variables
- Deploy

✅ **Robust date extraction**
- Duckling time entity with roles
- Handles multiple formats and relative phrases
- Validates and normalizes to SQL format

✅ **Flexible analytics**
- Dynamic analytics type selection via decider
- Human-readable payload with sensor names
- UUID→name conversion for summarization

✅ **All 9 actions are essential**
- Each serves a specific role in the pipeline
- Remove any at the risk of breaking the flow
