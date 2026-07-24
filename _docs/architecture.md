---
title: Architecture
layout: post
category: docs
permalink: /docs/architecture/
date: 2025-09-28
---


# OntoBot System Architecture# Architecture


## OverviewOntoBot is orchestrated by Docker Compose and consists of modular services:


OntoBot uses a **microservices architecture** with Docker containers orchestrated by Docker Compose. Each service has a single responsibility and communicates via HTTP/REST APIs.- Rasa: NLU and dialogue (5005)

- Action Server: custom logic, data-layer, analytics calls (5055)

### Design Principles- Duckling: entity extraction (8000)

- Analytics microservices: time-series analytics (6001 host → 6000 container)

1. **Separation of Concerns**: Each service handles one aspect (NLU, analytics, knowledge, etc.)- Decider service: selects analytics for a user question (6009)

2. **Building-Agnostic**: Core services work with any building that provides Brick ontology + telemetry- File server: serves artifacts and provides small utilities (8080)

3. **Extensibility**: New analytics or data sources can be added without modifying core services- Jena Fuseki: SPARQL endpoint (3030)

4. **Resilience**: Services fail independently with graceful degradation- Rasa Editor: light admin/UX (6080)

5. **Observability**: Health checks, logging, and correlation IDs throughout- Frontend: chat UI (3000)

- Optional: Abacws API and Visualiser (8091/8090), NL2SPARQL (6005), Ollama (11434)

---

## Data flow

## High-Level Architecture

1) User → Frontend → Rasa

```2) Rasa → Action Server (custom action)

┌────────────────────────────────────────────────────────────────────────┐3) Action → Data stores (SQL/SPARQL/files) and builds a standardized payload

│                          OntoBot Platform                               │4) Action → (optional) Decider → selected `analysis_type`

└────────────────────────────────────────────────────────────────────────┘5) Action → Analytics `/analytics/run` with payload

6) Analytics → unit-aware results with UK defaults

┌────────────────────────────────────────────────────────────────────────┐7) Action → Formats response + artifacts → File server → Frontend renders

│  Layer 1: User Interface                                               │

├────────────────────────────────────────────────────────────────────────┤## Compose mapping

│                                                                         │

│  ┌──────────────────────────────────────────────────────────────────┐ │Service names in code use internal DNS names (e.g., `microservices:6000`) while host access uses mapped ports (e.g., `localhost:6001`). See repo `docker-compose.yml` for the definitive mapping.

│  │  React Frontend (TypeScript)                    Port: 3000       │ │
│  │  - Chat interface with message history                           │ │
│  │  - Real-time artifact rendering (charts, tables)                 │ │
│  │  - Responsive design (mobile/tablet/desktop)                     │ │
│  │  - User session management                                       │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
                                  ↓ HTTP REST
┌────────────────────────────────────────────────────────────────────────┐
│  Layer 2: Conversational AI                                            │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Rasa Core (Python)                             Port: 5005       │ │
│  │  ┌────────────────────────────────────────────────────────────┐ │ │
│  │  │  NLU Pipeline                                              │ │ │
│  │  │  ├─ WhitespaceTokenizer: Split text into tokens            │ │ │
│  │  │  ├─ RegexFeaturizer: Extract regex patterns                │ │ │
│  │  │  ├─ LexicalSyntacticFeaturizer: POS tags, lemmas           │ │ │
│  │  │  ├─ CountVectorsFeaturizer: Bag-of-words features          │ │ │
│  │  │  ├─ DIETClassifier: Intent + entity extraction (100 epochs)│ │ │
│  │  │  ├─ EntitySynonymMapper: Map entity variations             │ │ │
│  │  │  └─ ResponseSelector: Choose responses (100 epochs)        │ │ │
│  │  └────────────────────────────────────────────────────────────┘ │ │
│  │  ┌────────────────────────────────────────────────────────────┐ │ │
│  │  │  Dialogue Management                                       │ │ │
│  │  │  ├─ MemoizationPolicy: Remember exact dialogue paths       │ │ │
│  │  │  ├─ TEDPolicy: Transformer-based dialogue (max_history=5)  │ │ │
│  │  │  └─ RulePolicy: Handle deterministic rules                 │ │ │
│  │  └────────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                  ↓ HTTP Action Endpoint                │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  Action Server (Rasa SDK, Python)               Port: 5055      │ │
│  │  ┌────────────────────────────────────────────────────────────┐ │ │
│  │  │  Core Actions                                              │ │ │
│  │  │  • action_question_to_brickbot (main orchestrator)         │ │ │
│  │  │  • validate_sensor_form (typo-tolerant validation)         │ │ │
│  │  │  • validate_dates_form (date parsing & normalization)      │ │ │
│  │  │  • action_process_timeseries (data fetch)                  │ │ │
│  │  │  • action_reset_all_slots (state cleanup)                  │ │ │
│  │  └────────────────────────────────────────────────────────────┘ │ │
│  │  ┌────────────────────────────────────────────────────────────┐ │ │
│  │  │  Typo-Tolerant Sensor Resolution (NEW)                     │ │ │
│  │  │  ├─ extract_sensors_from_text(): Regex extraction          │ │ │
│  │  │  ├─ _fuzzy_match_single(): RapidFuzz WRatio scoring        │ │ │
│  │  │  ├─ canonicalize_sensor_names(): Name normalization        │ │ │
│  │  │  └─ rewrite_question_with_sensors(): Query rewriting       │ │ │
│  │  │  Threshold: 80 (configurable via SENSOR_FUZZY_THRESHOLD)   │ │ │
│  │  └────────────────────────────────────────────────────────────┘ │ │
│  │  ┌────────────────────────────────────────────────────────────┐ │ │
│  │  │  Service Integration                                       │ │ │
│  │  │  • Query Fuseki (SPARQL)                                   │ │ │
│  │  │  • Fetch time-series data (MySQL/TimescaleDB/Cassandra)    │ │ │
│  │  │  • Call Decider for analytics recommendation               │ │ │
│  │  │  • Execute analytics via microservices                     │ │ │
│  │  │  • Generate artifacts (charts, CSV, JSON)                  │ │ │
│  │  │  • Optional: LLM summarization (Ollama)                    │ │ │
│  │  └────────────────────────────────────────────────────────────┘ │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  Layer 3: Core Services                                                │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐  ┌───────────────────┐  ┌──────────────────┐  │
│  │ Jena Fuseki       │  │ Analytics Service │  │ Decider Service  │  │
│  │ Port: 3030        │  │ Port: 6000 (6001) │  │ Port: 6009       │  │
│  ├───────────────────┤  ├───────────────────┤  ├──────────────────┤  │
│  │ Knowledge Store   │  │ Flask App         │  │ Flask App        │  │
│  │ • SPARQL endpoint │  │ • 30+ analytics   │  │ • Query classifier│ │
│  │ • Brick TTL data  │  │ • scikit-learn    │  │ • Keyword-based  │  │
│  │ • 25+ prefixes    │  │ • pandas/numpy    │  │ • Confidence     │  │
│  │ • TDB2 storage    │  │ • matplotlib      │  │   scoring        │  │
│  │                   │  │ • Artifact gen    │  │                  │  │
│  └───────────────────┘  └───────────────────┘  └──────────────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │ HTTP File Server                              Port: 8080        │  │
│  │ - Serves charts, CSV exports, JSON results                      │  │
│  │ - Path: /artifacts/<username>/<filename>                        │  │
│  │ - No authentication (internal use only)                         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  Layer 4: Data Storage                                                 │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐│
│  │ MySQL            │  │ TimescaleDB      │  │ Cassandra            ││
│  │ Port: 3306       │  │ Port: 5432       │  │ Port: 9042           ││
│  ├──────────────────┤  ├──────────────────┤  ├──────────────────────┤│
│  │ Building 1       │  │ Building 2       │  │ Building 3           ││
│  │ - 680 sensors    │  │ - 329 sensors    │  │ - 597 sensors        ││
│  │ - General RDBMS  │  │ - Hypertables    │  │ - Wide-row storage   ││
│  │ - telemetry table│  │ - Compression    │  │ - High write throughput││
│  └──────────────────┘  └──────────────────┘  └──────────────────────┘│
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│  Layer 5: Optional AI Services (docker-compose.extras.yml)            │
├────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────┐  ┌───────────────────────────────┐ │
│  │ NL2SPARQL                    │  │ Ollama (LLM)                  │ │
│  │ Port: 6005                   │  │ Port: 11434                   │ │
│  ├──────────────────────────────┤  ├───────────────────────────────┤ │
│  │ T5-base Transformer          │  │ Mistral 7B Model              │ │
│  │ • NL → SPARQL translation    │  │ • Response summarization      │ │
│  │ • 10,000+ training pairs     │  │ • Natural language generation │ │
│  │ • Building-specific entities │  │ • Local inference (no API)    │ │
│  └──────────────────────────────┘  └───────────────────────────────┘ │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Patterns

### Pattern 1: Simple Sensor Query (No Analytics)

**User Query**: *"What sensors are in room 5.01?"*

```
┌─────────┐     ┌─────────┐     ┌────────────────┐     ┌────────┐
│ Frontend│────▶│  Rasa   │────▶│ Action Server  │────▶│ Fuseki │
└─────────┘     └─────────┘     └────────────────┘     └────────┘
     ▲                                  │                     │
     │                                  ◀─────────────────────┘
     │                                  │
     │                                  │ Format results
     │                                  ▼
     └──────────────────────────────────┘
```

**Steps**:
1. Frontend sends message to Rasa Core (POST /webhooks/rest/webhook)
2. Rasa classifies intent: `query_sensors_in_location`
3. Rasa calls Action Server: `action_question_to_brickbot`
4. Action Server constructs SPARQL query:
   ```sparql
   SELECT ?sensor ?label WHERE {
     ?sensor brick:hasLocation bldg:Room_5.01 .
     ?sensor rdfs:label ?label .
   }
   ```
5. Action Server queries Fuseki (POST /trial/sparql)
6. Fuseki returns sensor list (JSON)
7. Action Server formats response
8. Rasa returns message to Frontend
9. Frontend displays chat bubble with sensor list

**Response Time**: ~500ms

---

### Pattern 2: Analytics Query with Typo Tolerance

**User Query**: *"Show me NO2 Levl Sensor 5.09 trends"*

```
┌─────────┐     ┌─────────┐     ┌────────────────┐
│ Frontend│────▶│  Rasa   │────▶│ Action Server  │
└─────────┘     └─────────┘     └────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
              ┌─────────┐         ┌─────────┐        ┌─────────┐
              │ Fuzzy   │         │ Fuseki  │        │Database │
              │ Match   │         │(metadata)│        │(MySQL)  │
              └─────────┘         └─────────┘        └─────────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
              ┌─────────┐         ┌─────────┐        ┌─────────┐
              │ Decider │         │Analytics│        │  HTTP   │
              │ Service │         │ Service │        │ Server  │
              └─────────┘         └─────────┘        └─────────┘
                    │                   │                   │
                    └───────────────────┴───────────────────┘
                                        │
                                        ▼
                                ┌────────────────┐
                                │ Action Server  │
                                │ (format result)│
                                └────────────────┘
                                        │
                                        ▼
┌─────────┐     ┌─────────┐     ┌────────────────┐
│ Frontend│◀────│  Rasa   │◀────│ Action Server  │
└─────────┘     └─────────┘     └────────────────┘
```

**Steps**:
1. Frontend → Rasa Core
2. Rasa classifies intent: `query_trend_analysis`
3. Rasa → Action Server: `action_question_to_brickbot`

**Step 3a: Typo-Tolerant Sensor Resolution**
4. Action Server extracts sensor from text:
   - Input: "NO2 Levl Sensor 5.09"
   - Regex patterns match: "NO2 Levl Sensor 5.09"
5. Action Server loads sensor list (cached from sensor_list.txt)
6. Action Server fuzzy matches:
   - Candidate: "NO2_Level_Sensor_5.09"
   - RapidFuzz WRatio score: 100 (exact after normalization)
7. Action Server rewrites query:
   - Original: "Show me NO2 Levl Sensor 5.09 trends"
   - Rewritten: "Show me NO2_Level_Sensor_5.09 trends"

**Step 3b: Metadata Fetch**
8. Action Server queries Fuseki for sensor metadata:
   ```sparql
   SELECT ?uuid ?location ?unit WHERE {
     bldg:NO2_Level_Sensor_5.09 brick:hasUUID ?uuid .
     bldg:NO2_Level_Sensor_5.09 brick:hasLocation ?location .
     bldg:NO2_Level_Sensor_5.09 brick:hasUnit ?unit .
   }
   ```

**Step 3c: Time-Series Data Fetch**
9. Action Server queries MySQL:
   ```sql
   SELECT timestamp, sensor_value 
   FROM telemetry 
   WHERE sensor_uuid = '12345678-...' 
     AND timestamp BETWEEN '2025-10-24' AND '2025-10-31'
   ORDER BY timestamp ASC
   ```

**Step 3d: Analytics Decision**
10. Action Server calls Decider Service:
    ```json
    POST http://decider-service:6009/decide
    {"question": "Show me NO2_Level_Sensor_5.09 trends"}
    ```
11. Decider responds:
    ```json
    {"perform_analytics": true, "analytics": "trend_analysis", "confidence": 0.95}
    ```

**Step 3e: Analytics Execution**
12. Action Server builds analytics payload:
    ```json
    {
      "analysis_type": "trend_analysis",
      "timeseries_data": [{
        "sensor_name": "NO2_Level_Sensor_5.09",
        "data": [
          {"datetime": "2025-10-24T10:00:00", "reading_value": 45.2},
          {"datetime": "2025-10-24T10:01:00", "reading_value": 45.5},
          ...
        ]
      }],
      "parameters": {"window_size": 10}
    }
    ```
13. Action Server calls Analytics Service:
    ```
    POST http://microservices:6000/analytics/run
    ```
14. Analytics Service:
    - Computes moving average
    - Identifies trend direction
    - Generates line chart (matplotlib)
    - Saves PNG to /app/shared_data/artifacts/user123/chart.png
15. Analytics Service responds:
    ```json
    {
      "success": true,
      "analysis": "upward_trend",
      "rate": 0.5,
      "artifacts": ["chart.png"]
    }
    ```

**Step 3f: Artifact Storage**
16. Action Server constructs file URL:
    ```
    http://localhost:8080/artifacts/user123/chart.png
    ```

**Step 3g: Response Formatting**
17. Action Server → Rasa Core:
    ```json
    {
      "text": "NO2 levels show an upward trend over the last week, increasing at 0.5 units/day.",
      "attachment": {
        "type": "image",
        "url": "http://localhost:8080/artifacts/user123/chart.png"
      }
    }
    ```
18. Rasa → Frontend
19. Frontend renders message + inline image

**Response Time**: ~2-3 seconds

---

### Pattern 3: NL2SPARQL Translation (Optional)

**User Query**: *"What sensors monitor air quality in building A?"*

```
┌─────────┐     ┌─────────┐     ┌────────────────┐     ┌───────────┐
│ Frontend│────▶│  Rasa   │────▶│ Action Server  │────▶│ NL2SPARQL │
└─────────┘     └─────────┘     └────────────────┘     └───────────┘
                                        │                     │
                                        ◀─────────────────────┘
                                        │
                                        ▼
                                   ┌────────┐
                                   │ Fuseki │
                                   └────────┘
                                        │
                                        ▼
                                ┌────────────────┐
                                │ Action Server  │
                                │ (format result)│
                                └────────────────┘
                                        │
                                        ▼
┌─────────┐     ┌─────────┐     ┌────────────────┐
│ Frontend│◀────│  Rasa   │◀────│ Action Server  │
└─────────┘     └─────────┘     └────────────────┘
```

**Steps**:
1. Frontend → Rasa Core
2. Rasa classifies intent: `ask_complex_sparql_query`
3. Rasa → Action Server
4. Action Server calls NL2SPARQL:
   ```json
   POST http://nl2sparql:6005/nl2sparql
   {
     "question": "What sensors monitor air quality in building A?",
     "entity": ""
   }
   ```
5. NL2SPARQL (T5 model) generates SPARQL:
   ```sparql
   SELECT ?sensor ?type WHERE {
     ?sensor rdf:type ?type .
     FILTER(?type IN (brick:CO2_Sensor, brick:NO2_Sensor, brick:VOC_Sensor))
     ?sensor brick:isPartOf bldg:Building_A .
   }
   ```
6. Action Server postprocesses query (safety checks)
7. Action Server adds prefixes and executes against Fuseki
8. Fuseki returns results
9. Action Server formats as natural language
10. Rasa → Frontend

**Response Time**: ~1 second

---

### Pattern 4: LLM-Enhanced Response (Optional)

**User Query**: *"Explain the temperature patterns over the last 24 hours"*

```
┌─────────┐     ┌─────────┐     ┌────────────────┐
│ Frontend│────▶│  Rasa   │────▶│ Action Server  │
└─────────┘     └─────────┘     └────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
              ┌─────────┐         ┌─────────┐        ┌─────────┐
              │ Fuseki  │         │Database │        │Analytics│
              └─────────┘         └─────────┘        └─────────┘
                    │                   │                   │
                    └───────────────────┴───────────────────┘
                                        │
                                        ▼
                                   ┌────────┐
                                   │ Ollama │
                                   │(Mistral)│
                                   └────────┘
                                        │
                                        ▼
                                ┌────────────────┐
                                │ Action Server  │
                                │(combine results)│
                                └────────────────┘
                                        │
                                        ▼
┌─────────┐     ┌─────────┐     ┌────────────────┐
│ Frontend│◀────│  Rasa   │◀────│ Action Server  │
└─────────┘     └─────────┘     └────────────────┘
```

**Steps**:
1-13. Same as Pattern 2 (fetch data, run analytics)
14. Action Server builds LLM prompt:
    ```
    User asked: "Explain the temperature patterns over the last 24 hours"
    
    Data summary:
    - Sensor: Air_Temperature_Sensor_5.01
    - Time range: 2025-10-30 10:00 to 2025-10-31 10:00
    - Readings: 1440 values (1-minute intervals)
    - Min: 20.1°C, Max: 23.5°C, Avg: 21.8°C
    - Trend: Upward (+0.15°C/hour)
    - Anomalies: 2 detected (spikes at 02:30 and 14:15)
    
    Please explain these patterns in natural language for a building operator.
    ```
15. Action Server calls Ollama:
    ```json
    POST http://ollama:11434/api/generate
    {
      "model": "mistral:latest",
      "prompt": "...",
      "stream": false
    }
    ```
16. Ollama (Mistral 7B) generates summary:
    ```
    The temperature in room 5.01 has shown a gradual warming trend 
    over the last 24 hours. Starting at 20.5°C this morning, it 
    reached a peak of 23.5°C around 2:30 PM, likely due to afternoon 
    solar gain and occupancy. Two brief temperature spikes were 
    detected at 2:30 AM and 2:15 PM, which may warrant investigation. 
    Overall, the temperature remains within comfortable range but is 
    trending slightly upward.
    ```
17. Action Server combines analytics chart + LLM summary
18. Rasa → Frontend (text summary + chart attachment)

**Response Time**: ~4-6 seconds (LLM inference adds 2-3 seconds)

---

## Component Details

### Rasa Core

**Configuration** (`rasa-bldgX/config.yml`):
```yaml
language: en
pipeline:
  - name: WhitespaceTokenizer
  - name: RegexFeaturizer
  - name: LexicalSyntacticFeaturizer
  - name: CountVectorsFeaturizer
  - name: DIETClassifier
    epochs: 100
    entity_recognition: true
  - name: EntitySynonymMapper
  - name: ResponseSelector
    epochs: 100

policies:
  - name: MemoizationPolicy
    max_history: 5
  - name: TEDPolicy
    max_history: 5
    epochs: 100
  - name: RulePolicy
    core_fallback_threshold: 0.4
```

**Training Data**:
- **Intents**: 30+ (query_sensor_value, ask_trend, detect_anomaly, etc.)
- **Entities**: sensor_type, date, time, location, analytics_type
- **Stories**: 50+ dialogue flows
- **Rules**: 20+ deterministic patterns

**Model Size**: ~50 MB (trained model .tar.gz)

---

### Action Server

**Core Modules**:
- `actions.py`: All custom action classes
- `sensor_management.py`: Fuzzy matching logic (NEW)
- `sparql_helpers.py`: SPARQL query construction
- `analytics_client.py`: Analytics service integration
- `db_connectors.py`: Multi-database support

**Key Dependencies**:
```python
rasa-sdk==3.6.0
rapidfuzz==2.13.7        # Typo tolerance
SPARQLWrapper==2.0.0     # SPARQL queries
mysql-connector-python   # MySQL
psycopg2-binary          # TimescaleDB
cassandra-driver         # Cassandra
ollama                   # LLM client
```

**Environment Configuration**:
```bash
# Service URLs (use internal DNS names)
FUSEKI_URL=http://fuseki-db:3030/trial/sparql
ANALYTICS_URL=http://microservices:6000/analytics/run
DECIDER_URL=http://decider-service:6009/decide
NL2SPARQL_URL=http://nl2sparql:6005/nl2sparql
SUMMARIZATION_URL=http://ollama:11434

# Typo tolerance (NEW)
SENSOR_FUZZY_THRESHOLD=80
SENSOR_LIST_RELOAD_SEC=300

# Feature flags
ENABLE_SUMMARIZATION=true
ENABLE_ANALYTICS=true

# Database (building-specific)
DB_HOST=mysqlserver
DB_NAME=telemetry
DB_USER=root
DB_PASSWORD=password
```

---

### Analytics Service

**Flask App Structure**:
```
microservices/
├── app.py                    # Flask routes
├── requirements.txt
├── blueprints/
│   ├── descriptive_analytics.py
│   ├── diagnostic_analytics.py
│   ├── predictive_analytics.py
│   ├── prescriptive_analytics.py
│   └── real_time_analytics.py
└── utils/
    ├── chart_generator.py
    ├── data_validator.py
    └── artifact_manager.py
```

**Key Routes**:
```python
@app.route('/health', methods=['GET'])
def health():
    return {"status": "healthy"}, 200

@app.route('/analytics/run', methods=['POST'])
def run_analytics():
    # Validate payload
    # Dispatch to appropriate blueprint
    # Generate artifacts
    # Return results

@app.route('/analytics/list', methods=['GET'])
def list_analytics():
    return {"analyses": _supported_types()}, 200
```

**Analysis Categories** (30+ total):
- **Descriptive** (6): summary_statistics, histogram, distribution_analysis, outlier_detection, data_quality, timeseries_analysis
- **Diagnostic** (6): correlation_analysis, comparative_analysis, pattern_recognition, variance_analysis, lag_analysis, seasonal_decomposition
- **Predictive** (6): trend_analysis, forecast, anomaly_prediction, regression_analysis, classification, clustering
- **Prescriptive** (6): optimization, what_if_scenario, resource_allocation, scheduling, anomaly_response, threshold_recommendations
- **Real-Time** (6): streaming_analytics, real_time_anomaly, live_dashboard, alert_generation, performance_monitoring

---

### Fuseki (Knowledge Store)

**TDB2 Dataset Structure**:
```
bldg1/trial/
├── dataset/
│   ├── abacws-building-v7.ttl       # Core building graph
│   ├── sensors-full.ttl             # All 680 sensors
│   └── relationships.ttl            # Spatial/functional links
└── configuration/
    └── config.ttl                   # Dataset configuration
```

**Supported Queries**:
- SELECT: Retrieve sensor metadata
- CONSTRUCT: Build new RDF graphs
- ASK: Boolean queries (sensor existence)
- DESCRIBE: Get all triples about a resource

**Performance**:
- Indexed by subject, predicate, object
- Typical query time: 50-200ms
- Dataset size: ~5 MB (680 sensors)

---

### Decider Service

**Decision Logic** (`decider-service/app.py`):
```python
KEYWORD_MAPPINGS = {
    "trend|trending|pattern": "trend_analysis",
    "forecast|predict|future": "forecast",
    "anomaly|outlier|unusual|abnormal": "anomaly_detection",
    "correlation|relationship|relate": "correlation_analysis",
    "summary|statistics|stats|average": "summary_statistics",
    "histogram|distribution": "histogram",
    "compare|comparison|versus": "comparative_analysis",
    "pattern|recurring": "pattern_recognition"
}

def decide(question):
    question_lower = question.lower()
    for pattern, analysis_type in KEYWORD_MAPPINGS.items():
        if re.search(pattern, question_lower):
            return {
                "perform_analytics": True,
                "analytics": analysis_type,
                "confidence": 0.9
            }
    return {"perform_analytics": False}
```

---

## Network Architecture

### Docker Network: `ontobot_network`

All services communicate over a single Docker bridge network:

```
docker network create ontobot_network
```

**Internal DNS Resolution**:
- `rasa` → Rasa Core container
- `action_server` → Action Server container
- `fuseki-db` → Fuseki container
- `microservices` → Analytics container
- `decider-service` → Decider container
- `mysqlserver` → MySQL container
- `timescaledb` → TimescaleDB container
- `cassandra` → Cassandra container
- `http_server` → File server container
- `frontend` → React app container
- `nl2sparql` → NL2SPARQL container (optional)
- `ollama` → Ollama container (optional)

**Port Mapping** (host:container):
```
3000:3000   # Frontend (React)
5005:5005   # Rasa Core
5055:5055   # Action Server
3030:3030   # Fuseki
3306:3306   # MySQL
5432:5432   # TimescaleDB
9042:9042   # Cassandra
6001:6000   # Analytics (host 6001 → container 6000)
6009:6009   # Decider
6005:6005   # NL2SPARQL (optional)
8080:8080   # HTTP File Server
11434:11434 # Ollama (optional)
```

---

## Security Considerations

### Current Implementation (Development)

- ❌ **No authentication** on any service
- ❌ **No encryption** (HTTP, not HTTPS)
- ❌ **No input sanitization** on SPARQL queries
- ❌ **Shared file server** (no user isolation)

### Production Recommendations

1. **Add API Gateway**: Nginx reverse proxy with rate limiting
2. **Enable HTTPS**: TLS certificates for all public endpoints
3. **Implement Authentication**: OAuth2 or JWT tokens
4. **Sanitize SPARQL**: Whitelist patterns, prevent injection
5. **User Isolation**: Separate artifact directories per user
6. **Network Segmentation**: Isolate databases from public network
7. **Secrets Management**: Use Docker secrets or Vault

---

## Scalability

### Current Limitations

- Single-node Docker Compose (no horizontal scaling)
- In-memory Rasa models (no external model store)
- Synchronous request processing (no queuing)

### Scale-Up Strategies

1. **Kubernetes Migration**: Use K8s for orchestration
2. **Load Balancing**: Multiple Action Server replicas
3. **Caching Layer**: Redis for sensor metadata
4. **Async Processing**: Celery for long-running analytics
5. **Database Replicas**: Read replicas for query distribution

---

## Observability

### Logging

- **Rasa**: Logs to stdout (captured by Docker)
- **Action Server**: Python logging module → stdout
- **Analytics**: Flask logger → stdout
- **Correlation IDs**: 12-character hex strings track requests across services

### Health Checks

All services expose health endpoints:
```bash
GET /health → {"status": "healthy"}
GET /         → 200 OK (basic services)
GET /$/ping   → 200 OK (Fuseki)
GET /version  → {...}  (Rasa)
```

### Monitoring Script

```powershell
# scripts/check-health.ps1
pwsh -File scripts/check-health.ps1
```

Output:
```
✓ Rasa: OK
✓ Action Server: OK
✓ Fuseki: OK
✓ Analytics: OK
✓ Decider: OK
✓ File Server: OK
✓ Frontend: OK
```

---

## Related Documentation

- **[Backend Services](backend_services.md)**: Detailed service reference
- **[Action Server Architecture](action_server_architecture.md)**: Deep dive into action server
- **[Typo Tolerance](typo_tolerance.md)**: Fuzzy matching system
- **[Multi-Building Support](multi_building.md)**: Building-specific configurations
- **[Database Integration](database_integration.md)**: Multi-database guide

---

**System Architecture** - The blueprint of OntoBot's intelligence. 🏗️📐
