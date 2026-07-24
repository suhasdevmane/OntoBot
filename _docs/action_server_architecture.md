---
layout: post
title: Action Server Architecture
date: 2025-10-31
---

# Custom Action Server Architecture

## Overview

The Custom Action Server is the **orchestration layer** of OntoBot, coordinating all services to fulfill user queries. It's a Python application built on Rasa SDK that handles:

- Sensor name canonicalization and typo correction
- SPARQL query generation and execution
- Analytics orchestration
- Artifact generation (charts, CSV, JSON)
- Database queries (MySQL, TimescaleDB, Cassandra)
- LLM response generation

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Custom Action Server                         │
│                      (Port 5055)                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │          Form Validation Layer                            │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  - ValidateSensorForm                                    │ │
│  │    • Fuzzy match sensor names (threshold: 80)            │ │
│  │    • Normalize case and spacing                          │ │
│  │    • Handle comma-separated lists                        │ │
│  │                                                           │ │
│  │  - ValidateDatesForm                                     │ │
│  │    • Parse DD/MM/YYYY and YYYY-MM-DD                     │ │
│  │    • Handle relative dates (today, last week, etc.)      │ │
│  │    • Validate date ranges                                │ │
│  │                                                           │ │
│  │  - ValidateDateRangeChoiceForm                           │ │
│  │    • Quick acceptance of last 24 hours                   │ │
│  │    • Parse explicit date ranges                          │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │          Core Action: ActionQuestionToBrickbot            │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │                                                           │ │
│  │  1. Sensor Extraction & Canonicalization                │ │
│  │     ├─→ extract_sensors_from_text()                      │ │
│  │     ├─→ _fuzzy_match_single()                            │ │
│  │     ├─→ canonicalize_sensor_names()                      │ │
│  │     └─→ rewrite_question_with_sensors()                  │ │
│  │                                                           │ │
│  │  2. Query Type Detection                                 │ │
│  │     ├─→ Listing queries (show all sensors)              │ │
│  │     ├─→ Metric queries (get sensor values)              │ │
│  │     └─→ Unknown (fallback to NL2SPARQL)                 │ │
│  │                                                           │ │
│  │  3. NL2SPARQL Translation                                │ │
│  │     ├─→ Send rewritten question + entity                │ │
│  │     ├─→ Receive SPARQL query                            │ │
│  │     └─→ postprocess_sparql_query()                       │ │
│  │                                                           │ │
│  │  4. SPARQL Execution                                     │ │
│  │     ├─→ Add prefixes (Brick, bldg, etc.)                │ │
│  │     ├─→ Execute against Fuseki                           │ │
│  │     └─→ Parse results (JSON)                             │ │
│  │                                                           │ │
│  │  5. Time-Series Data Fetch                               │ │
│  │     ├─→ Extract sensor UUIDs from SPARQL results        │ │
│  │     ├─→ Query database (MySQL/TimescaleDB/Cassandra)    │ │
│  │     └─→ Map UUIDs to human-readable names               │ │
│  │                                                           │ │
│  │  6. Analytics Decision                                   │ │
│  │     ├─→ Call Decider Service                            │ │
│  │     ├─→ Receive analytics type recommendation           │ │
│  │     └─→ Validate against 30+ supported types            │ │
│  │                                                           │ │
│  │  7. Analytics Execution                                  │ │
│  │     ├─→ Build payload (timeseries_data + params)        │ │
│  │     ├─→ Call Analytics Microservice                     │ │
│  │     └─→ Receive results + artifacts                     │ │
│  │                                                           │ │
│  │  8. LLM Summarization (Optional)                        │ │
│  │     ├─→ Build prompt with query + results               │ │
│  │     ├─→ Call Ollama (Mistral)                           │ │
│  │     └─→ Extract natural language summary                │ │
│  │                                                           │ │
│  │  9. Artifact Management                                  │ │
│  │     ├─→ Save charts to shared_data/artifacts/<user>/    │ │
│  │     ├─→ Generate file server URLs                       │ │
│  │     └─→ Return attachment objects to frontend           │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │          Utility Actions                                  │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  - ActionDebugEntities: Log extracted entities           │ │
│  │  - ActionProcessTimeseries: Standalone data fetch        │ │
│  │  - ActionRouteAfterDateChoice: Form routing logic        │ │
│  │  - ActionResetSlots: Clear conversation state            │ │
│  │  - ActionGenerateAndShareData: Export functionality      │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Sensor Management

#### Sensor List Loading
```python
# Auto-reloading sensor list with caching
_SENSOR_LIST_CACHE: Set[str] = set()
_SENSOR_LIST_CACHE_MTIME: Optional[float] = None
_SENSOR_LIST_RELOAD_SEC = int(os.getenv("SENSOR_LIST_RELOAD_SEC", "300"))

def _load_sensor_list(force: bool = False) -> Set[str]:
    # Searches for sensor_list.txt in multiple locations
    # Caches for 300 seconds by default
    # Auto-reloads when file changes
```

**Search Order**:
1. `SENSOR_LIST_FILE` environment variable (if set)
2. `./sensor_list.txt` (container working directory)
3. `./actions/sensor_list.txt` (legacy path)

#### Sensor UUID Mapping
```python
# Bidirectional name <-> UUID mapping
_SENSOR_UUID_CACHE: Dict[str, str] = {}
_SENSOR_UUID_RELOAD_SEC = int(os.getenv("SENSOR_UUIDS_RELOAD_SEC", "300"))

def _load_sensor_uuid_map(force: bool = False) -> Dict[str, str]:
    # Loads sensor_uuids.txt (format: name,uuid)
    # Returns both directions: name->uuid and uuid->name
```

**File Format** (`sensor_uuids.txt`):
```
Air_Temperature_Sensor_5.01,12345678-1234-1234-1234-123456789abc
CO2_Level_Sensor_5.01,87654321-4321-4321-4321-cba987654321
# Comments start with #
```

### 2. Fuzzy Matching System

#### Configuration
```python
FUZZY_THRESHOLD: int = 80  # Configurable via SENSOR_FUZZY_THRESHOLD env
```

#### Matching Strategy
```python
def _fuzzy_match_single(sensor_name: str, candidates: List[str]) -> Optional[str]:
    # 1. Exact match
    if sensor_name in candidates:
        return sensor_name
    
    # 2. Space/underscore normalization
    alt = sensor_name.replace(' ', '_') if ' ' in sensor_name else sensor_name.replace('_', ' ')
    if alt in candidates:
        return alt.replace(' ', '_')
    
    # 3. RapidFuzz WRatio scoring
    match = rf_process.extractOne(sensor_name, candidates, scorer=rf_fuzz.WRatio)
    if match and match[1] >= FUZZY_THRESHOLD:
        return match[0]
    
    return None
```

### 3. Query Processing Pipeline

#### Step 1: Extract User Message
```python
raw_text = tracker.latest_message.get("text")
user_question = raw_text.strip()
```

#### Step 2: Extract Sensors from Text
```python
sensor_mappings = self.extract_sensors_from_text(user_question)
# Returns: [(original, normalized, canonical), ...]

if sensor_mappings:
    extracted_sensors = [canonical for _, _, canonical in sensor_mappings]
    rewritten_question = self.rewrite_question_with_sensors(user_question, sensor_mappings)
```

**Regex Patterns**:
- Pattern 1: `\b([A-Za-z0-9_]+_[Ss]ensor_\d+(?:\.\d+)?)\b` (underscore form)
- Pattern 2: `\b([A-Z][A-Za-z0-9_\s]+?)\s+[Ss]ensor\s+(\d+(?:\.\d+)?)\b` (space form)

#### Step 3: Canonicalize Sensors
```python
canon_list = self.canonicalize_sensor_names(sensor_types)
```

#### Step 4: Detect Query Type
```python
def detect_query_type(q: str) -> str:
    # Listing: "what are the sensors", "list all sensors"
    # Metric: "value", "reading", "average", "trend", etc.
    # Unknown: fallback
```

#### Step 5: Translate to SPARQL
```python
input_data = {
    "question": rewritten_question,  # With canonical sensor names
    "entity": ", ".join([f"bldg:{s}" for s in sensor_types])
}

response = requests.post(nl2sparql_url, json=input_data)
sparql_query = response.json()["sparql_query"]

# Postprocess for safety
sparql_query = self.postprocess_sparql_query(sparql_query)
```

#### Step 6: Execute SPARQL
```python
full_query = self.add_sparql_prefixes(sparql_query)
results = self.execute_sparql_query(full_query)
```

**SPARQL Prefixes** (25 total):
```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bldg: <http://abacwsbuilding.cardiff.ac.uk/abacws#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
... (21 more)
```

#### Step 7: Fetch Time-Series Data
```python
# Extract UUIDs from SPARQL results
uuids = extract_uuids_from_results(results)

# Query database
db_config = get_mysql_config()  # Or get_timescaledb_config(), etc.
connection = mysql.connector.connect(**db_config)

for uuid in uuids:
    cursor.execute("""
        SELECT timestamp, sensor_value 
        FROM telemetry 
        WHERE sensor_uuid = %s AND timestamp BETWEEN %s AND %s
        ORDER BY timestamp ASC
    """, (uuid, start_date, end_date))
```

#### Step 8: Decide Analytics
```python
response = requests.post(DECIDER_URL, json={"question": user_question})

if response.json()["perform_analytics"]:
    analytics_type = response.json()["analytics"]
    # Validate against _supported_types()
```

#### Step 9: Execute Analytics
```python
payload = {
    "analysis_type": analytics_type,
    "timeseries_data": [
        {
            "sensor_name": "Air_Temperature_Sensor_5.01",
            "data": [
                {"datetime": "2025-10-31T10:00:00", "reading_value": 21.5},
                {"datetime": "2025-10-31T10:01:00", "reading_value": 21.6},
                ...
            ]
        }
    ],
    "parameters": {"threshold": 2.0, "window_size": 10}
}

response = requests.post(ANALYTICS_URL, json=payload)
```

#### Step 10: Generate Summary (Optional)
```python
if ENABLE_SUMMARIZATION:
    prompt = f"User asked: {user_question}\nResults: {json.dumps(results)}\nSummarize:"
    response = client.generate(model="mistral:latest", prompt=prompt)
    summary = extract_text_from_llm_response(response)
```

#### Step 11: Save Artifacts
```python
user_safe, user_dir = get_user_artifacts_dir(tracker)
# Returns: ("john_doe", "/app/shared_data/artifacts/john_doe")

chart_path = os.path.join(user_dir, f"{timestamp}_chart.png")
plt.savefig(chart_path)

# Generate URL
file_url = f"{BASE_URL}/artifacts/{user_safe}/{timestamp}_chart.png"
```

#### Step 12: Return Response
```python
dispatcher.utter_message(
    text=summary,
    attachment={
        "type": "image",
        "url": file_url,
        "title": "Temperature Analysis"
    }
)
```

### 4. Database Integration

#### MySQL (Building 1)
```python
def get_mysql_config() -> Dict[str, Any]:
    return {
        "host": os.getenv("DB_HOST", "mysqlserver"),
        "database": os.getenv("DB_NAME", "telemetry"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "password"),
        "port": int(os.getenv("DB_PORT", "3306"))
    }
```

#### TimescaleDB (Building 2)
```python
# Uses psycopg2 for PostgreSQL connections
# TimescaleDB-specific features:
# - Hypertables for time-series optimization
# - Continuous aggregates for performance
# - Compression for storage efficiency
```

#### Cassandra (Building 3)
```python
from cassandra.cluster import Cluster

cluster = Cluster(['cassandra'])
session = cluster.connect('telemetry')

# Wide-row storage for sensor data
# Optimized for high-write throughput
```

### 5. Error Handling

#### Graceful Degradation
```python
try:
    response = self.query_service_requests(nl2sparql_url, input_data)
except Exception as e:
    logger.error(f"NL2SPARQL failed: {e}")
    # Fallback: Ask user for clarification
    dispatcher.utter_message(response="utter_translation_error")
    return [SlotSet("sparql_error", True)]
```

#### Informative Error Messages
```python
# User-facing errors (critical)
emit_message(dispatcher, tracker, 
             text="Sorry, I couldn't connect to the analytics service. Please try again later.",
             detail=False)  # Always shown

# Debug messages (optional)
emit_message(dispatcher, tracker,
             text="Understanding your question...",
             detail=True)  # Shown if show_details=True
```

### 6. Logging & Monitoring

#### Pipeline Logger
```python
class PipelineLogger:
    def __init__(self, correlation_id: str, component: str):
        self.correlation_id = correlation_id
        self.component = component
    
    def stage(self, name: str):
        # Context manager for timing stages
        return PipelineLogger._StageCtx(self, name)

# Usage:
plog = PipelineLogger(correlation_id, "QuestionToBrickbot")

with plog.stage("nl2sparql_translate"):
    response = self.query_service_requests(nl2sparql_url, input_data)
# Logs: START stage 'nl2sparql_translate'
#       END stage 'nl2sparql_translate' ok in 250 ms
```

#### Correlation IDs
```python
def new_correlation_id() -> str:
    return uuid.uuid4().hex[:12]  # 12-character hex string

# Tracks request flow across services
# Example: a1b2c3d4e5f6
```

### 7. Frontend Integration

#### Detail Verbosity Control
```python
def _frontend_show_details(tracker: Tracker) -> bool:
    # Frontend sends metadata: { show_details: bool }
    meta = tracker.latest_message.get('metadata') or {}
    return meta.get('show_details', True)

def emit_message(dispatcher, tracker, *, text=None, attachment=None, detail=True):
    # detail=True: only send if show_details=True
    # detail=False: always send (critical messages)
    if detail and not _frontend_show_details(tracker):
        return
    dispatcher.utter_message(text=text, attachment=attachment)
```

#### Attachment Format
```python
{
    "type": "image",  # or "file", "chart"
    "url": "http://localhost:8080/artifacts/john_doe/chart.png",
    "title": "Temperature Trends",
    "description": "Last 7 days of temperature data"
}
```

### 8. Configuration Management

#### Environment Variables
```python
# Service URLs
nl2sparql_url = os.getenv("NL2SPARQL_URL", "http://nl2sparql:6005/nl2sparql")
FUSEKI_URL = os.getenv("FUSEKI_URL", "http://fuseki:3030/abacws/query")
DECIDER_URL = os.getenv("DECIDER_URL", "http://decider-service:6009/decide")
ANALYTICS_URL = os.getenv("ANALYTICS_URL", "http://microservices:6000/analytics/run")
SUMMARIZATION_URL = os.getenv("SUMMARIZATION_URL", "http://ollama:11434")

# Feature Flags
ENABLE_SUMMARIZATION = os.getenv("ENABLE_SUMMARIZATION", "true").lower() == "true"
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "true").lower() == "true"

# Thresholds
FUZZY_THRESHOLD = int(os.getenv("SENSOR_FUZZY_THRESHOLD", "80"))
```

## Performance Optimizations

### 1. Caching
- **Sensor List**: Cached for 300 seconds (configurable)
- **UUID Mappings**: Cached for 300 seconds (configurable)
- **Analytics Registry**: Cached for 60 seconds (TTL)

### 2. Lazy Loading
- Database connections opened only when needed
- LLM client initialized once on startup

### 3. Connection Pooling
- Reuses database connections across requests
- HTTP session pooling for service calls

### 4. Timeout Management
```python
response = requests.post(url, json=data, timeout=20)  # 20-second timeout
```

## Testing

### Unit Tests
```python
# Test fuzzy matching
assert _fuzzy_match_single("NO2 Levl Sensor 5.09", candidates) == "NO2_Level_Sensor_5.09"

# Test sensor extraction
results = extract_sensors_from_text("show me NO2 Level Sensor 5.09")
assert len(results) == 1
assert results[0][2] == "NO2_Level_Sensor_5.09"
```

### Integration Tests
```bash
# Test action server health
curl http://localhost:5055/health

# Test end-to-end query
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender": "test", "message": "What is the temperature?"}'
```

### Smoke Tests
```python
# microservices/test_analytics_smoke.py
# Tests analytics service with sample payload
```

## Deployment

### Docker Compose
```yaml
action_server_bldg1:
  build: ./rasa-bldg1/actions
  ports:
    - "5055:5055"
  environment:
    - FUZZY_THRESHOLD=80
    - SENSOR_LIST_RELOAD_SEC=300
    - ANALYTICS_URL=http://microservices:6000/analytics/run
  volumes:
    - ./rasa-bldg1/actions:/app/actions
    - ./rasa-bldg1/shared_data:/app/shared_data
  networks:
    - ontobot_network
```

### Health Check
```python
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "action_server"}), 200
```

## Related Documentation

- **[Typo Tolerance](typo_tolerance.md)**: Fuzzy matching system details
- **[Analytics API](analytics_api.md)**: Analytics service integration
- **[Backend Services](backend_services.md)**: All service endpoints
- **[Database Integration](database_integration.md)**: Multi-database support

---

**Custom Action Server** - The intelligent orchestration layer of OntoBot. 🧠⚙️
