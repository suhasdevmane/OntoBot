# How Analytics Type is Selected in OntoBot

## Overview

When a user asks a question like *"Show me temperature trends from last week"*, your system automatically determines:
1. **Should analytics be performed?** (vs just returning ontology facts)
2. **Which analytics function?** (e.g., `analyze_temperatures`, `detect_anomalies`, `correlate_sensors`)

This document explains the complete pipeline from user question to analytics function execution.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER QUESTION                               │
│    "Show me temperature trends for Sensor 5.01 from last week"     │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│              Rasa: Questions_to_brickbot intent                     │
│              Triggers: action_question_to_brickbot                  │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│         ActionQuestionToBrickbot (actions.py:1876-1935)             │
│  1. Extracts user_question from tracker                             │
│  2. Calls NL2SPARQL service (translates to SPARQL query)            │
│  3. Queries Jena Fuseki (Brick ontology)                            │
│  4. Detects timeseries UUIDs in SPARQL results                      │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼ If timeseries UUIDs found
┌─────────────────────────────────────────────────────────────────────┐
│                    DECIDER SERVICE CALL                             │
│  POST http://decider-service:6009/decide                            │
│  Request: { "question": "Show me temperature trends..." }           │
│                                                                      │
│  Decider Service (FastAPI microservice)                             │
│  ├─ Step 1: Check if TTL/listing-only question                      │
│  │   (keywords: "label", "type", "where is", "list sensors")        │
│  │   → If yes: return {perform_analytics: false}                    │
│  │                                                                   │
│  ├─ Step 2: Use ML models (if available)                            │
│  │   Model 1: perform_model.pkl (classification: yes/no analytics)  │
│  │   Model 2: label_model.pkl (multi-class: which analytics type)   │
│  │   ├─ perform_vectorizer.pkl: TF-IDF vectorization               │
│  │   └─ label_vectorizer.pkl: TF-IDF vectorization                 │
│  │                                                                   │
│  └─ Step 3: Fallback to rule-based (if models missing)              │
│      Keyword matching:                                               │
│      - "trend", "over time" → analyze_sensor_trend                   │
│      - "anomaly", "outlier" → detect_anomalies                       │
│      - "correlate", "relationship" → correlate_sensors               │
│      - "average", "mean" → average                                   │
│      - "maximum", "peak" → max                                       │
│                                                                      │
│  Response: {                                                         │
│    "perform_analytics": true,                                        │
│    "analytics": "analyze_sensor_trend"                               │
│  }                                                                   │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│         ActionQuestionToBrickbot (continued)                        │
│  5. Process decider response                                         │
│     - If perform_analytics = false → summarize ontology facts only   │
│     - If perform_analytics = true:                                   │
│       ├─ Validate analytics type against registry                    │
│       ├─ Apply fallback rules if type unsupported                    │
│       └─ Set slots: timeseries_ids, analytics_type                   │
│  6. Trigger date collection (if dates missing)                       │
│     → date_range_choice_form → dates_form                            │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│         ActionProcessTimeseries (actions.py:2300-2600)              │
│  1. Fetch SQL data from database (MySQL/TimescaleDB/Cassandra)      │
│  2. Build standardized JSON payload:                                 │
│     {                                                                │
│       "analysis_type": "analyze_sensor_trend",  ← from analytics_type slot
│       "Air_Temperature_Sensor_5.01": [          ← human-readable name
│         {"datetime": "2025-01-01 00:00:00", "reading_value": 22.5}, │
│         {"datetime": "2025-01-01 01:00:00", "reading_value": 22.8}, │
│         ...                                                          │
│       ]                                                              │
│     }                                                                │
│  3. POST to Analytics Microservice                                   │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│          ANALYTICS MICROSERVICE                                     │
│  POST http://microservices:6000/analytics/run                       │
│                                                                      │
│  analytics_service.py:2759 - /run endpoint                          │
│  1. Extract analysis_type from JSON body                             │
│  2. Validate analysis_type exists in registry                        │
│  3. Route to appropriate analytics function:                         │
│                                                                      │
│     analysis_functions = {                                           │
│       "analyze_sensor_trend": analyze_sensor_trend,                  │
│       "detect_anomalies": detect_anomalies,                          │
│       "correlate_sensors": correlate_sensors,                        │
│       "analyze_temperatures": analyze_temperatures,                  │
│       "analyze_humidity": analyze_humidity,                          │
│       "analyze_co2_levels": analyze_co2_levels,                      │
│       "detect_potential_failures": detect_potential_failures,        │
│       ... (30+ analytics functions)                                  │
│     }                                                                │
│                                                                      │
│  4. Execute selected function with sensor_data + optional params     │
│  5. Return results with metadata:                                    │
│     {                                                                │
│       "analysis_type": "analyze_sensor_trend",                       │
│       "timestamp": "2025-10-31 12:00:00",                            │
│       "results": {                                                   │
│         "trend_direction": "increasing",                             │
│         "avg_change_per_hour": 0.3,                                  │
│         "visualization_artifacts": [...],                            │
│         ...                                                          │
│       }                                                              │
│     }                                                                │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│         ActionProcessTimeseries (continued)                         │
│  6. Receive analytics results                                        │
│  7. Save artifacts (JSON, CSV, PNG charts) to shared_data            │
│  8. Call Ollama/Mistral for natural language summarization          │
│  9. Return summary + download links to user                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Decider Service (decider-service/)

**Location:** `http://decider-service:6009` (internal Docker network)

**Purpose:** Binary classifier + multi-class labeler
- **Binary:** Should analytics be performed? (yes/no)
- **Multi-class:** Which analytics function? (30+ types)

**Models:**
- `model/perform_model.pkl` - Trained classifier (sklearn)
- `model/perform_vectorizer.pkl` - TF-IDF vectorizer
- `model/label_model.pkl` - Multi-class classifier
- `model/label_vectorizer.pkl` - TF-IDF vectorizer

**Training Data:** Auto-generated from T5 NL2SPARQL corpus
- `data/generate_decider_data.py` - Generates training dataset
- `training/train.py` - Trains both models

**Fallback Logic (if models missing):**
```python
# decider-service/app/main.py:32-54
def rule_based_decide(q: str) -> tuple[bool, Optional[str]]:
    ql = (q or "").lower()
    
    # TTL/ontology-only questions → no analytics
    if any(k in ql for k in ["label", "type", "class", "where is", "list sensors"]):
        return False, None
    
    # Keyword-based analytics type selection
    if any(k in ql for k in ["average", "avg", "mean"]):
        return True, "average"
    if any(k in ql for k in ["trend", "trending", "over time"]):
        return True, "analyze_sensor_trend"
    if any(k in ql for k in ["anomaly", "outlier", "abnormal"]):
        return True, "detect_anomalies"
    if any(k in ql for k in ["correlate", "correlation", "relationship"]):
        return True, "correlate_sensors"
    
    return True, "analyze_sensor_trend"  # Default fallback
```

**Hard Override (always applied):**
```python
# decider-service/app/main.py:57-75
def is_ttl_only(q: str) -> bool:
    """Detect ontology/listing-only questions."""
    ql = (q or "").lower()
    ttl_keywords = ["label", "type", "class", "where is", "where are"]
    if any(k in ql for k in ttl_keywords):
        return True
    
    # Regex patterns for listing questions
    patterns = [
        r"\bwhat\s+(are|r)\s+the\s+sensors\b",
        r"\b(list|show|which)\b.*\bsensors?\b",
        r"\bsensors?\s+(in|at|for)\b",
    ]
    return any(re.search(p, ql) for p in patterns)
```

**Configuration in docker-compose.bldg1.yml:**
```yaml
decider-service:
  build: ./decider-service
  container_name: decider_service
  ports:
    - "6009:6009"
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:6009/health').read()"]
  networks:
    - ontobot-network
```

**Environment Variable in action_server:**
```yaml
action_server:
  environment:
    - DECIDER_URL=http://decider-service:6009/decide
```

---

### 2. Action Server Integration (rasa-bldg1/actions/actions.py)

**Key Function:** `ActionQuestionToBrickbot.run()` (lines 1876-1935)

**Step 1: Call Decider Service**
```python
# actions.py:1879-1891
if DECIDER_URL:
    try:
        with plog.stage("decider"):
            d_resp = requests.post(DECIDER_URL, json={"question": user_question}, timeout=6)
        if d_resp.ok:
            dj = d_resp.json()
            perform_analytics = bool(dj.get("perform_analytics"))
            decided_analytics = dj.get("analytics")
            plog.info("Decider response", perform=perform_analytics, analytics=decided_analytics)
        else:
            plog.warning("Decider returned non-200", status=d_resp.status_code)
    except Exception as e:
        plog.warning("Decider call failed", error=str(e))
```

**Step 2: Fallback Logic (if decider unavailable)**
```python
# actions.py:1895-1916
def _pick_type_from_context(q: str, sensors: List[str]) -> str:
    ql = (q or "").lower()
    s_join = " ".join(sensors).lower() if sensors else ""
    
    if "humid" in ql or "humid" in s_join:
        return "analyze_humidity"
    if any(k in ql or k in s_join for k in ["temp","temperature"]):
        return "analyze_temperatures"
    if "co2" in ql or "co2" in s_join:
        return "analyze_co2_levels"
    if "pm" in ql or "particulate" in ql:
        return "analyze_pm_levels"
    if any(k in ql for k in ["correlate","correlation","relationship"]):
        return "correlate_sensors"
    if any(k in ql for k in ["anomaly","outlier","abnormal","fault","failure"]):
        return "detect_potential_failures"
    if any(k in ql for k in ["trend","over time","time series","history","timeline"]):
        return "analyze_sensor_trend"
    
    return "analyze_sensor_trend"  # Final fallback

def fallback_decide(q: str) -> Tuple[bool, str]:
    ql = (q or "").lower()
    # TTL-only questions → no analytics
    if any(k in ql for k in ["label","type","class","category","installed","location"]):
        return False, ""
    return True, _pick_type_from_context(q, sensor_types)
```

**Step 3: Validate and Set analytics_type Slot**
```python
# actions.py:1926-1935
if has_timeseries and perform_analytics:
    raw_choice = decided_analytics
    # Normalize empty/null values
    if isinstance(raw_choice, str) and raw_choice.strip().lower() in {"none", "", "no", "false"}:
        raw_choice = None
    
    selected_analytics = raw_choice or _pick_type_from_context(user_question, sensor_types)
    
    # Validate against supported types
    if selected_analytics not in _supported_types():
        plog.warning("Unsupported analytics type from decider; using fallback", 
                     got=raw_choice, fallback=selected_analytics)
    
    events.append(SlotSet("analytics_type", selected_analytics))
```

**Dynamic Registry Support:**
```python
# actions.py:291-324
def _supported_types() -> set:
    """Fetch live from analytics microservice + static fallback."""
    if ANALYTICS_URL:
        try:
            resp = requests.get(f"{ANALYTICS_URL.rsplit('/', 1)[0]}/types", timeout=3)
            if resp.ok:
                return set(resp.json().get("analytics_types", []))
        except Exception:
            pass
    
    # Static fallback (20+ types)
    return {
        "analyze_sensor_trend", "detect_anomalies", "correlate_sensors",
        "analyze_temperatures", "analyze_humidity", "analyze_co2_levels",
        "analyze_pm_levels", "detect_potential_failures", "average", "max", "min",
        "compute_air_quality_index", "analyze_indoor_comfort", ...
    }
```

---

### 3. Analytics Microservice (microservices/)

**Location:** `http://microservices:6000` (internal Docker network)

**Endpoint:** `POST /analytics/run`

**Request Format:**
```json
{
  "analysis_type": "analyze_sensor_trend",
  "Air_Temperature_Sensor_5.01": [
    {"datetime": "2025-01-01 00:00:00", "reading_value": 22.5},
    {"datetime": "2025-01-01 01:00:00", "reading_value": 22.8}
  ],
  "Zone_Air_Humidity_Sensor_5.02": [
    {"datetime": "2025-01-01 00:00:00", "reading_value": 45.2},
    {"datetime": "2025-01-01 01:00:00", "reading_value": 46.1}
  ]
}
```

**Processing Logic:**
```python
# microservices/blueprints/analytics_service.py:2759-2820
@analytics_service.route("/run", methods=["POST"])
def run_analysis():
    data = request.get_json()
    
    # Extract analysis_type
    if not data or "analysis_type" not in data:
        return jsonify({"error": "Missing required parameter: analysis_type"}), 400
    
    analysis_type = data["analysis_type"]
    
    # Separate control keys from sensor data
    control_keys = {"analysis_type"}
    optional_params = {}
    
    # Extract optional parameters (sensor_key, thresholds, etc.)
    for opt in ["sensor_key", "acceptable_range", "thresholds", "temp_range", ...]:
        if opt in data:
            optional_params[opt] = data[opt]
            control_keys.add(opt)
    
    sensor_data = {k: v for k, v in data.items() if k not in control_keys}
    
    # Validate analysis_type
    if analysis_type not in analysis_functions:
        return jsonify({"error": f"Unknown analysis type: {analysis_type}"}), 400
    
    # Execute analytics function
    func = analysis_functions[analysis_type]
    
    # Filter optional params based on function signature
    sig = inspect.signature(func)
    valid_kwargs = {k: v for k, v in optional_params.items() if k in sig.parameters}
    
    result = func(sensor_data, **valid_kwargs)
    
    # Return enhanced response
    return jsonify({
        "analysis_type": analysis_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": result
    })
```

**Analytics Functions Registry:**
```python
# microservices/blueprints/analytics_service.py:700-800
analysis_functions = {
    "analyze_sensor_trend": analyze_sensor_trend,
    "detect_anomalies": detect_anomalies,
    "correlate_sensors": correlate_sensors,
    "analyze_temperatures": analyze_temperatures,
    "analyze_humidity": analyze_humidity,
    "analyze_co2_levels": analyze_co2_levels,
    "analyze_pm_levels": analyze_pm_levels,
    "detect_potential_failures": detect_potential_failures,
    "compute_air_quality_index": compute_air_quality_index,
    "analyze_indoor_comfort": analyze_indoor_comfort,
    "forecast_sensor_values": forecast_sensor_values,
    "calculate_thermal_comfort": calculate_thermal_comfort,
    "energy_consumption_analysis": energy_consumption_analysis,
    "occupancy_pattern_analysis": occupancy_pattern_analysis,
    # ... 30+ total functions
}
```

**Configuration in docker-compose.bldg1.yml:**
```yaml
microservices:
  build:
    context: ./microservices
  container_name: microservices_container
  ports:
    - "6001:6000"  # host 6001 → container 6000
  volumes:
    - microservices-bldg1-plugins:/app/analytics_plugins
    - microservices-bldg1-meta:/app/analytics_meta
    - ./rasa-bldg1:/app/rasa-bldg1:ro
  networks:
    - ontobot-network
```

**Environment Variable in action_server:**
```yaml
action_server:
  environment:
    - ANALYTICS_URL=http://microservices:6000/analytics/run
```

---

## Example Flow: Temperature Trend Analysis

**User Input:** *"Show me temperature trends for Air_Temperature_Sensor_5.01 from last week"*

### Step-by-Step Execution:

**1. Rasa Intent Recognition**
- Intent: `Questions_to_brickbot`
- Triggers: `action_question_to_brickbot`

**2. NL2SPARQL Translation**
- User question → SPARQL query
- Query Jena Fuseki (Brick ontology)
- Extracts: `timeseries_ids = ["249a4c9c-fe31-4649-a119-452e5e8e7dc5"]`

**3. Decider Service Call**
```http
POST http://decider-service:6009/decide
Content-Type: application/json

{
  "question": "Show me temperature trends for Air_Temperature_Sensor_5.01 from last week"
}
```

**Decider Response:**
```json
{
  "perform_analytics": true,
  "analytics": "analyze_sensor_trend"
}
```

**4. Slot Setting**
- `analytics_type` = `"analyze_sensor_trend"`
- `timeseries_ids` = `["249a4c9c-fe31-4649-a119-452e5e8e7dc5"]`
- `sensor_type` = `["Air_Temperature_Sensor_5.01"]`

**5. Date Collection**
- Trigger `date_range_choice_form` → "Use last 24 hours?" → No
- Trigger `dates_form` → Extract dates from "last week"
- Duckling parses: `start_date="2025-10-24 00:00:00"`, `end_date="2025-10-31 00:00:00"`

**6. SQL Data Fetch** (ActionProcessTimeseries)
```sql
SELECT datetime, `249a4c9c-fe31-4649-a119-452e5e8e7dc5` AS reading_value
FROM sensor_data
WHERE datetime BETWEEN '2025-10-24 00:00:00' AND '2025-10-31 00:00:00'
ORDER BY datetime;
```

**7. Build Analytics Payload**
```python
payload = {
    "analysis_type": "analyze_sensor_trend",
    "Air_Temperature_Sensor_5.01": [
        {"datetime": "2025-10-24 00:00:00", "reading_value": 21.5},
        {"datetime": "2025-10-24 01:00:00", "reading_value": 21.3},
        # ... 168 records (7 days * 24 hours)
    ]
}
```

**8. Analytics Microservice Call**
```http
POST http://microservices:6000/analytics/run
Content-Type: application/json

{
  "analysis_type": "analyze_sensor_trend",
  "Air_Temperature_Sensor_5.01": [...]
}
```

**9. Analytics Execution**
- Function: `analyze_sensor_trend(sensor_data)`
- Calculates: trend direction, rate of change, statistics
- Generates: line chart PNG, CSV data, JSON summary

**10. Analytics Response**
```json
{
  "analysis_type": "analyze_sensor_trend",
  "timestamp": "2025-10-31 12:00:00",
  "results": {
    "trend_direction": "increasing",
    "avg_change_per_hour": 0.12,
    "overall_change": 20.16,
    "min_value": 21.3,
    "max_value": 24.8,
    "avg_value": 22.9,
    "visualization_artifacts": [
      {"type": "line_chart", "file": "trend_chart_20251031120000.png"}
    ]
  }
}
```

**11. Summarization** (Ollama/Mistral)
```http
POST http://ollama:11434/api/generate
{
  "model": "mistral:latest",
  "prompt": "Summarize this temperature trend analysis: {...}"
}
```

**12. User Response**
```
Temperature trends for Air_Temperature_Sensor_5.01 over the past week show an 
increasing trend with an average change of 0.12°C per hour. The temperature 
ranged from 21.3°C to 24.8°C with an average of 22.9°C.

Download artifacts:
- Chart: http://localhost:8080/artifacts/user123/trend_chart_20251031120000.png
- Data: http://localhost:8080/artifacts/user123/data_20251031120000.json
```

---

## Fallback Hierarchy

Your system has **3 layers of fallback** to ensure robustness:

### Layer 1: Decider ML Models (Primary)
- Trained on 1000+ examples from T5 NL2SPARQL corpus
- High accuracy for common building management questions
- Location: `decider-service/model/*.pkl`

### Layer 2: Decider Rule-Based (Secondary)
- Keyword matching with 15+ patterns
- Handles edge cases and unseen phrasings
- Location: `decider-service/app/main.py:32-54`

### Layer 3: Action Server Context-Based (Tertiary)
- Uses sensor types and question keywords
- Applied when decider service is unavailable
- Location: `rasa-bldg1/actions/actions.py:1895-1916`

**Fallback Flow:**
```
ML Models Available?
  ├─ YES → Use ML predictions
  └─ NO → Use decider rule-based

Decider Service Reachable?
  ├─ YES → Use decider response
  └─ NO → Use action server context-based fallback
```

---

## Supported Analytics Types (30+)

| Analytics Type | Purpose | Typical Keywords |
|----------------|---------|------------------|
| `analyze_sensor_trend` | Time series trends | trend, over time, history |
| `detect_anomalies` | Outlier detection | anomaly, outlier, abnormal |
| `correlate_sensors` | Cross-sensor relationships | correlate, relationship, compare |
| `analyze_temperatures` | Temperature analysis | temperature, temp, thermal |
| `analyze_humidity` | Humidity analysis | humidity, moisture, RH |
| `analyze_co2_levels` | CO2 monitoring | co2, carbon dioxide, ventilation |
| `analyze_pm_levels` | Particulate matter | PM2.5, PM10, air quality |
| `detect_potential_failures` | Fault prediction | failure, fault, malfunction |
| `compute_air_quality_index` | AQI calculation | air quality, AQI, pollution |
| `analyze_indoor_comfort` | Comfort assessment | comfort, uncomfortable, thermal |
| `forecast_sensor_values` | Predictive analytics | forecast, predict, future |
| `calculate_thermal_comfort` | PMV/PPD calculation | thermal comfort, PMV, PPD |
| `energy_consumption_analysis` | Energy usage | energy, consumption, usage |
| `occupancy_pattern_analysis` | Occupancy detection | occupancy, occupied, presence |
| `average` | Mean calculation | average, avg, mean |
| `max` | Maximum value | maximum, max, peak |
| `min` | Minimum value | minimum, min, lowest |
| `sum` | Total aggregation | sum, total, aggregate |
| ... | ... | ... |

**Full list available:** `GET http://localhost:6001/analytics/types`

---

## Training the Decider Service

### Generate Training Data
```powershell
cd decider-service
python data/generate_decider_data.py

# Generates: data/decider_training.auto.jsonl
# Format: {"question": "...", "perform_analytics": true, "analytics": "..."}
```

### Train Models
```powershell
python training/train.py --data data/decider_training.auto.jsonl

# Outputs:
# - model/perform_model.pkl (binary classifier)
# - model/perform_vectorizer.pkl (TF-IDF)
# - model/label_model.pkl (multi-class classifier)
# - model/label_vectorizer.pkl (TF-IDF)
```

### Rebuild and Deploy
```powershell
docker compose -f docker-compose.bldg1.yml build decider-service
docker compose -f docker-compose.bldg1.yml up -d decider-service
```

---

## Testing Analytics Type Selection

### Test Decider Service Directly
```powershell
# TTL-only question (no analytics)
curl -X POST http://localhost:6009/decide `
  -H "Content-Type: application/json" `
  -d '{"question": "What sensors are installed in the building?"}'
# Response: {"perform_analytics": false, "analytics": null}

# Trend analysis
curl -X POST http://localhost:6009/decide `
  -H "Content-Type: application/json" `
  -d '{"question": "Show me temperature trends from last week"}'
# Response: {"perform_analytics": true, "analytics": "analyze_sensor_trend"}

# Anomaly detection
curl -X POST http://localhost:6009/decide `
  -H "Content-Type: application/json" `
  -d '{"question": "Detect anomalies in humidity data"}'
# Response: {"perform_analytics": true, "analytics": "detect_anomalies"}
```

### Test End-to-End via Rasa
```powershell
cd rasa-bldg1
rasa shell --debug

# Test queries:
> Show me temperature trends for sensor 5.01 from last week
> Correlate temperature and humidity over the last 30 days
> Detect anomalies in CO2 levels for the past month
> What sensors are installed on floor 5?  # Should NOT trigger analytics
```

### Check Logs
```powershell
# Action server logs (analytics_type selection)
docker logs action_server_bldg1 -f | grep -i "analytics_type\|decider"

# Decider service logs
docker logs decider_service -f

# Microservices logs (analytics execution)
docker logs microservices_container -f | grep -i "analysis_type"
```

---

## Debugging

### Common Issues

**1. analytics_type is always "analyze_sensor_trend"**
- Check if decider service is running: `docker ps | grep decider`
- Verify DECIDER_URL env var: `docker exec action_server_bldg1 env | grep DECIDER`
- Test decider health: `curl http://localhost:6009/health`
- Check action server logs for decider errors

**2. Analytics returns "Unknown analysis type"**
- List available types: `curl http://localhost:6001/analytics/types`
- Verify analysis_type matches registry exactly (case-sensitive)
- Check for typos in decider label_model.pkl training data

**3. Decider always returns fallback**
- Check if models exist: `docker exec decider_service ls -la model/`
- Retrain models if missing (see Training section above)
- Verify training data quality in `data/decider_training.auto.jsonl`

---

## Summary

**Analytics type selection is automatic and robust:**

1. **User asks question** (no need to specify analytics type)
2. **Decider service** classifies question (ML or rules)
3. **Action server** validates and sets `analytics_type` slot
4. **Analytics microservice** routes to correct function
5. **User receives** natural language summary + artifacts

**Key Advantages:**
- ✅ **Zero user burden** - no technical knowledge required
- ✅ **30+ analytics types** automatically selected
- ✅ **ML-powered** with rule-based fallbacks
- ✅ **Building-agnostic** - retrainable per building
- ✅ **Extensible** - add new analytics types dynamically

---

## Related Documentation
- `analytics.md` - Analytics functions detailed specs
- `decider-service/README.md` - Decider training guide
- `IMPROVEMENTS_SUMMARY.md` - Recent Rasa improvements
- `TRAINING_GUIDE.md` - Rasa retraining workflow
