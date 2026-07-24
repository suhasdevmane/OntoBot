---
title: Backend Services
layout: post
category: docs
permalink: /docs/backend_services/
date: 2025-10-08
---


# Backend Services Reference# Backend Services Documentation


## Service OverviewComplete reference for all OntoBot backend services, their APIs, configuration, and integration patterns.


OntoBot consists of **7 core services** and **3 optional services** working together to deliver conversational AI for smart buildings.


### Service Map

### Service MapOntoBot's backend consists of multiple microservices, each responsible for specific functionality:


```| Service | Port | Purpose | Health Check |

┌─────────────────────────────────────────────────────────────────────────┐|---------|------|---------|--------------|

│                         OntoBot Service Stack                            │| **Rasa Core** | 5005 | Conversational AI engine | `/version` |

├─────────────────────────────────────────────────────────────────────────┤| **Action Server** | 5055 | Custom action logic | `/health` |

│                                                                          │| **Duckling** | 8000 | Entity extraction | `/` (HTML) |

│  Frontend Layer (Port 3000)                                             │| **Analytics Microservices** | 6001→6000 | Time-series analytics | `/health` |

│  ┌────────────────────────────────────────────────────────────────────┐ │| **Decider Service** | 6009 | Analytics type selection | `/health` |

│  │ React Frontend (rasa-frontend)                                     │ │| **File Server** | 8080 | Artifact storage & management | `/health` |

│  │ - Chat interface                                                   │ │| **NL2SPARQL** | 6005 | NL→SPARQL translation | `/health` |

│  │ - Artifact viewer (charts, tables)                                 │ │| **Ollama (Mistral)** | 11434 | Local LLM summarization | `/` |

│  │ - User authentication UI                                           │ │

│  └────────────────────────────────────────────────────────────────────┘ │## 1. Rasa Core Service

│                              ↓ HTTP (REST API)                          │

│                                                                          │**Port**: 5005  

│  Orchestration Layer (Ports 5005, 5055)                                │**Container**: `rasa_bldg1` (or bldg2/bldg3)  

│  ┌────────────────────────────────────────────────────────────────────┐ │**Technology**: Python, Rasa 3.6.12

│  │ Rasa Core (Port 5005)                                              │ │

│  │ - Intent classification                                            │ │### Purpose

│  │ - Entity extraction                                                │ │

│  │ - Dialogue management                                              │ │The Rasa service is the conversational AI engine that:

│  │ - Form handling                                                    │ │- Processes natural language user input

│  └────────────────────────────────────────────────────────────────────┘ │- Identifies intents and extracts entities

│                              ↓ HTTP (Action Endpoint)                   │- Manages dialogue state

│  ┌────────────────────────────────────────────────────────────────────┐ │- Triggers custom actions

│  │ Action Server (Port 5055)                                          │ │- Generates responses

│  │ - Query orchestration                                              │ │

│  │ - Sensor name canonicalization                                     │ │### Key Endpoints

│  │ - SPARQL execution                                                 │ │

│  │ - Analytics dispatch                                               │ │#### Get Rasa Version

│  └────────────────────────────────────────────────────────────────────┘ │```http

│                                                                          │GET http://localhost:5005/version

│            ↓                    ↓                    ↓                   │```

│                                                                          │

│  Core Services Layer                                                    │**Response:**

│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────┐           │```json

│  │ Jena Fuseki   │  │ Analytics     │  │ Decider Service  │           │{

│  │ (Port 3030)   │  │ (Port 6000)   │  │ (Port 6009)      │           │  "version": "3.6.12",

│  │               │  │               │  │                  │           │  "minimum_compatible_version": "3.0.0",

│  │ - SPARQL      │  │ - 30+         │  │ - Query type     │           │  "rasa": "3.6.12"

│  │   queries     │  │   analytics   │  │   classification │           │}

│  │ - Brick data  │  │ - Artifact    │  │ - Analytics      │           │```

│  │   store       │  │   generation  │  │   recommendation │           │

│  └───────────────┘  └───────────────┘  └──────────────────┘           │#### Send Message (Webhook)

│                                                                          │```http

│  Data Layer                                                             │POST http://localhost:5005/webhooks/rest/webhook

│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────┐           │Content-Type: application/json

│  │ MySQL         │  │ TimescaleDB   │  │ Cassandra        │           │

│  │ (Port 3306)   │  │ (Port 5432)   │  │ (Port 9042)      │           │{

│  │               │  │               │  │                  │           │  "sender": "user123",

│  │ Building 1    │  │ Building 2    │  │ Building 3       │           │  "message": "What is the temperature in zone 5.04?"

│  │ (680 sensors) │  │ (329 sensors) │  │ (597 sensors)    │           │}

│  └───────────────┘  └───────────────┘  └──────────────────┘           │```

│                                                                          │

│  Support Services                                                       │**Response:**

│  ┌───────────────┐                                                      │```json

│  │ HTTP Server   │                                                      │[

│  │ (Port 8080)   │                                                      │  {

│  │               │                                                      │    "recipient_id": "user123",

│  │ - Artifact    │                                                      │    "text": "The current temperature in zone 5.04 is 22.3°C."

│  │   serving     │                                                      │  }

│  └───────────────┘                                                      │]

│                                                                          │```

│  Optional Services (docker-compose.extras.yml)                         │

│  ┌───────────────┐  ┌───────────────────────────────────────┐         │#### Model Management

│  │ NL2SPARQL     │  │ Ollama (LLM)                          │         │```http

│  │ (Port 6005)   │  │ (Port 11434)                          │         │# Get current model

│  │               │  │                                        │         │GET http://localhost:5005/status

│  │ - T5-based    │  │ - Response summarization              │         │

│  │   translation │  │ - Mistral model                       │         │# Load specific model

│  └───────────────┘  └───────────────────────────────────────┘         │PUT http://localhost:5005/model

│                                                                          │Content-Type: application/json

└─────────────────────────────────────────────────────────────────────────┘

```

"model_file": "/app/models/20250108-123045-ancient-dust.tar.gz"

### Services at a glance

| Service | Port | Purpose | Health Check |
|---------|------|---------|--------------|
| Rasa Core | 5005 | Conversational AI engine | GET /version |
| Action Server | 5055 | Custom action logic | GET /health |
| Duckling | 8000 | Entity extraction | GET / (HTML) |
| Analytics Microservices | 6001→6000 | Time-series analytics | GET /health |
| Decider Service | 6009 | Analytics type selection | GET /health |
| File Server | 8080 | Artifact storage & management | GET /health |
| NL2SPARQL (optional) | 6005 | NL→SPARQL translation | GET /health |
| Ollama (optional) | 11434 | Local LLM summarization | GET / |

### 1. Rasa Core

### Configuration

**Purpose**: Conversational AI orchestrator

**File**: `rasa-bldg1/config.yml`

**Port**: 5005 (host), 5005 (internal)

```yaml

**Technology**: Rasa Open Source 3.6language: en

pipeline:

**Key Responsibilities**:  - name: WhitespaceTokenizer

- Intent classification (30+ intents)  - name: RegexFeaturizer

- Entity extraction (sensor_type, date ranges, analytics types)  - name: LexicalSyntacticFeaturizer

- Dialogue state tracking  - name: CountVectorsFeaturizer

- Form validation routing  - name: DIETClassifier

- Policy-based response selection    epochs: 100

  - name: DucklingEntityExtractor

**Endpoints**:    url: http://duckling_server:8000

```bash    dimensions: ["time", "number"]

# Health check  - name: EntitySynonymMapper

GET http://localhost:5005/  - name: ResponseSelector

    epochs: 100

# Version info

GET http://localhost:5005/versionpolicies:

  - name: MemoizationPolicy

# Conversational webhook (REST channel)  - name: RulePolicy

POST http://localhost:5005/webhooks/rest/webhook  - name: TEDPolicy

{    max_history: 5

  "sender": "user123",    epochs: 100

  "message": "What is the CO2 level?"```

}

### Docker Configuration

# Model loading

POST http://localhost:5005/model

```yaml

{services:

  "model_file": "models/20231031-123456.tar.gz"  rasa_bldg1:

}    image: rasa/rasa:3.6.12-full

```    ports:

      - "5005:5005"

**Internal URL**: `http://rasa:5005`    volumes:

      - ./rasa-bldg1:/app

**Configuration**:    command:

```yaml      - run

# rasa-bldgX/config.yml      - --enable-api

language: en      - --cors

pipeline:      - "*"

  - name: WhitespaceTokenizer      - --debug

  - name: RegexFeaturizer    healthcheck:

  - name: LexicalSyntacticFeaturizer      test: ["CMD", "curl", "-f", "http://localhost:5005/version"]

  - name: CountVectorsFeaturizer      interval: 30s

  - name: DIETClassifier      timeout: 10s

    epochs: 100      retries: 5

  - name: EntitySynonymMapper

```

  - name: ResponseSelector

    epochs: 100## 2. Action Server


policies:**Port**: 5055  

  - name: MemoizationPolicy**Container**: `action_server_bldg1`  

  - name: TEDPolicy**Technology**: Python, Rasa SDK

    max_history: 5

    epochs: 100### Purpose

  - name: RulePolicy

```Executes custom Python actions that:

- Query databases (MySQL, TimescaleDB, Cassandra)

**Docker Compose**:- Call SPARQL endpoints (Fuseki)

```yaml- Invoke analytics microservices

rasa_bldg1:- Fetch sensor data from ThingsBoard

  image: rasa/rasa:3.6.20-full- Format responses with artifacts

  ports:

    - "5005:5005"### Custom Actions

  volumes:

    - ./rasa-bldg1:/appLocated in: `rasa-bldg1/actions/actions.py`

  command: run --enable-api --cors "*"

  networks:**Available Actions:**

    - ontobot_network

```1. **`ActionGetSensorValue`**: Retrieve latest sensor reading

2. **`ActionGetAnalytics`**: Perform time-series analysis

---3. **`ActionListSensors`**: Show all available sensors

4. **`ActionShowTrend`**: Generate trend visualizations

### 2. Action Server5. **`ActionCompare`**: Compare multiple sensors

6. **`ActionCheckAnomaly`**: Detect anomalies

**Purpose**: Custom business logic executor7. **`ActionForecast`**: Predict future values

8. **`ActionSummarize`**: Generate natural language summaries

**Port**: 5055 (host), 5055 (internal)

### Integration Pattern

**Technology**: Rasa SDK 3.6, Python 3.10

```python

**Key Responsibilities**:from rasa_sdk import Action, Tracker

- Typo-tolerant sensor name resolution (fuzzy matching)from rasa_sdk.executor import CollectingDispatcher

- SPARQL query generation and executionimport requests

- Time-series data retrieval from databases

- Analytics service orchestrationclass ActionGetSensorValue(Action):

- LLM summarization (optional)    def name(self) -> str:

- Artifact management (charts, CSV, JSON)        return "action_get_sensor_value"

    

**Endpoints**:    def run(self, dispatcher, tracker, domain):

```bash        # 1. Extract entities

# Health check        sensor_name = tracker.get_slot("sensor")

GET http://localhost:5055/health        

        # 2. Query database or API

# Webhook (called by Rasa Core)        value = get_latest_value(sensor_name)

POST http://localhost:5055/webhook        

{        # 3. Optional: Call analytics

  "next_action": "action_question_to_brickbot",        payload = build_payload(sensor_name, value)

  "sender_id": "user123",        analytics_result = requests.post(

  "tracker": { ... }            "http://microservices:6000/analytics/run",

}            json=payload

```        ).json()

        

**Internal URL**: `http://action_server:5055`        # 4. Format response

        response = f"The {sensor_name} reads {value}."

**Key Actions**:        

- `action_question_to_brickbot`: Main query handler        # 5. Dispatch to user

- `validate_sensor_form`: Sensor name validation        dispatcher.utter_message(text=response)

- `validate_dates_form`: Date range validation        

- `action_process_timeseries`: Data fetch        return []

- `action_reset_all_slots`: State reset

```


**Environment Variables**:### Environment Variables

```bash

# Service URLs

```bash

NL2SPARQL_URL=http://nl2sparql:6005/nl2sparql# Database connections

FUSEKI_URL=http://fuseki:3030/abacws/queryDB_HOST=mysqlserver

DECIDER_URL=http://decider-service:6009/decideDB_PORT=3306

ANALYTICS_URL=http://microservices:6000/analytics/runDB_NAME=telemetry

SUMMARIZATION_URL=http://ollama:11434DB_USER=rasa

DB_PASSWORD=secure_password

# Feature flags

ENABLE_SUMMARIZATION=true# Service URLs

ENABLE_ANALYTICS=trueANALYTICS_URL=http://microservices:6000/analytics/run

DECIDER_URL=http://decider-service:6009/decide

# Typo toleranceBASE_URL=http://http_server:8080

SENSOR_FUZZY_THRESHOLD=80FUSEKI_URL=http://jena-fuseki-rdf-store:3030/abacws/sparql

SENSOR_LIST_RELOAD_SEC=300

# Optional services

# DatabaseNL2SPARQL_URL=http://nl2sparql:6005/nl2sparql

DB_HOST=mysqlserverOLLAMA_URL=http://ollama:11434/api/generate

DB_NAME=telemetry

```

DB_USER=root

DB_PASSWORD=password## 3. Analytics Microservices

```

**Port**: 6001 (host) → 6000 (container)  

**Docker Compose**:**Container**: `microservices_container`  

```yaml**Technology**: Python, Flask

action_server_bldg1:

  build: ./rasa-bldg1/actions### Purpose

  ports:

    - "5055:5055"Provides time-series analytics for sensor data:

  environment:- Statistical analysis (min, max, avg, std)

    - FUZZY_THRESHOLD=80- Trend detection

    - ANALYTICS_URL=http://microservices:6000/analytics/run- Anomaly detection

  volumes:- Forecasting

    - ./rasa-bldg1/shared_data:/app/shared_data- Correlation analysis

  networks:- Aggregation

    - ontobot_network

```### Architecture


**See Also**: [Action Server Architecture](action_server_architecture.md)

```

Flask App (app.py)

---├── Analytics Blueprint (/analytics/run)

├── Decider Blueprint (/decider)

### 3. Jena Fuseki└── T5 Training Blueprint (/api/t5/*)

```

**Purpose**: SPARQL endpoint for Brick knowledge graphs

### API Reference

**Port**: 3030 (host), 3030 (internal)

#### Run Analytics

**Technology**: Apache Jena Fuseki 4.7.0

```http

POST http://localhost:6001/analytics/run

**Key Responsibilities**:Content-Type: application/json

- Stores Brick TTL datasets

- Executes SPARQL queries (SELECT, CONSTRUCT, ASK){

- Provides semantic sensor metadata  "action": "analyze_sensor_trend",

- Supports 25+ ontology prefixes  "sensor_keys": ["Air_Temperature_Sensor_5.04"],

  "timeRange": "24h",

**Endpoints**:  "locationFilter": "zone_5_04",

```bash  "unit": "degC",

# Health check  "aggregation": "avg"

GET http://localhost:3030/$/ping}

```

# Query endpoint

POST http://localhost:3030/trial/sparql**Response:**

Content-Type: application/sparql-query

```json

{

SELECT ?sensor ?label WHERE {  "ok": true,

  ?sensor rdf:type brick:Temperature_Sensor .  "analysis_type": "trend",

  ?sensor rdfs:label ?label .  "summary": "Temperature trend is stable over the last 24 hours.",

}  "data": [

    {"timestamp": "2025-01-08T00:00:00", "value": 22.1},

# Update endpoint (admin only)    {"timestamp": "2025-01-08T01:00:00", "value": 22.3},

POST http://localhost:3030/trial/update    ...

  ],

# Dataset upload  "statistics": {

POST http://localhost:3030/$/datasets/trial/data    "min": 21.8,

Content-Type: text/turtle    "max": 23.1,

```    "avg": 22.4,

    "std": 0.4

**Internal URL**: `http://fuseki-db:3030`  },

  "artifact_url": "http://localhost:8080/artifacts/trend_12345.png"

**Dataset Structure**:}

```

bldg1/trial/dataset/

  ├── abacws.ttl               # Core building graph### Available Analysis Types

  ├── sensors.ttl              # Sensor definitions

  └── relationships.ttl        # Spatial/functional links1. **`retrieve_latest_value`**: Get most recent sensor reading

```   ```json

   {

**SPARQL Prefixes** (25 total):     "action": "retrieve_latest_value",

```sparql     "sensor_keys": ["CO2_Level_Sensor_5.04"]

PREFIX brick: <https://brickschema.org/schema/Brick#>   }

PREFIX bldg: <http://abacwsbuilding.cardiff.ac.uk/abacws#>   ```

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>2. **`analyze_sensor_trend`**: Time-series trend analysis

PREFIX owl: <http://www.w3.org/2002/07/owl#>   ```json

PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>   {

PREFIX foaf: <http://xmlns.com/foaf/0.1/>     "action": "analyze_sensor_trend",

PREFIX dcterms: <http://purl.org/dc/terms/>     "sensor_keys": ["Air_Temperature_Sensor_5.04"],

PREFIX skos: <http://www.w3.org/2004/02/skos/core#>     "timeRange": "7d"

PREFIX unit: <http://qudt.org/vocab/unit/>   }

PREFIX qudtqk: <http://qudt.org/vocab/quantitykind/>   ```

PREFIX sh: <http://www.w3.org/ns/shacl#>

PREFIX bacnet: <http://data.ashrae.org/bacnet/2020#>3. **`detect_anomalies`**: Statistical anomaly detection

PREFIX s223: <http://data.ashrae.org/standard223/1.0/model/all#>   ```json

PREFIX ref: <https://brickschema.org/schema/Brick/ref#>   {

PREFIX bsh: <https://brickschema.org/schema/BrickShape#>     "action": "detect_anomalies",

PREFIX sosa: <http://www.w3.org/ns/sosa/>     "sensor_keys": ["Zone_Air_Humidity_Sensor_5.04"],

PREFIX ssn: <http://www.w3.org/ns/ssn/>     "threshold": 2.0

PREFIX qudt: <http://qudt.org/schema/qudt/>   }

PREFIX vcard: <http://www.w3.org/2006/vcard/ns#>   ```

PREFIX schema: <http://schema.org/>

PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>4. **`compare_sensors`**: Multi-sensor comparison

PREFIX prov: <http://www.w3.org/ns/prov#>   ```json

PREFIX time: <http://www.w3.org/2006/time#>   {

PREFIX dbr: <http://dbpedia.org/resource/>     "action": "compare_sensors",

```     "sensor_keys": [

       "Air_Temperature_Sensor_5.01",

**Docker Compose**:       "Air_Temperature_Sensor_5.02"

```yaml     ],

fuseki-db:     "metric": "avg"

  image: stain/jena-fuseki:4.7.0   }

  ports:   ```

    - "3030:3030"

  environment:5. **`forecast_downtimes`**: Predictive maintenance

    - ADMIN_PASSWORD=admin   ```json

    - JVM_ARGS=-Xmx2g   {

  volumes:     "action": "forecast_downtimes",

    - ./bldg1/trial:/fuseki-base/databases/trial     "equipment_id": "AHU_01",

  networks:     "horizon": "7d"

    - ontobot_network   }

```   ```


---6. **`aggregate_sensor_data`**: Statistical aggregation

   ```json

### 4. Analytics Microservice   {

     "action": "aggregate_sensor_data",

**Purpose**: Statistical and machine learning analytics     "sensor_keys": ["Air_Temperature_Sensor_*"],

     "aggregation": "avg",

**Port**: 6001 (host), 6000 (internal)     "groupBy": "hour"

   }

**Technology**: Flask 3.0, Python 3.10, scikit-learn, pandas   ```


**Key Responsibilities**:### UK Defaults & Units

- 30+ analysis types (descriptive, diagnostic, predictive, prescriptive)

- Chart generation (PNG, base64)The analytics service applies UK-specific defaults:

- Anomaly detection (IQR, Z-score, Isolation Forest)

- Trend analysis (moving averages, ARIMA forecasts)**Temperature:**

- Artifact storage to shared volume- Default: °C

- Thresholds: 18-24°C (comfort)

**Endpoints**:- Alert: <16°C or >28°C

```bash

# Health check**CO2:**

GET http://localhost:6001/health- Default: ppm

- Threshold: 1000 ppm (HSE guideline)

# Run analysis- Alert: >1500 ppm

POST http://localhost:6001/analytics/run

Content-Type: application/json**Humidity:**

- Default: %RH

{- Threshold: 40-60%

  "analysis_type": "timeseries_analysis",- Alert: <30% or >70%

  "timeseries_data": [

    {**Illuminance:**

      "sensor_name": "Air_Temperature_Sensor_5.01",- Default: lux

      "data": [- Office: 500 lux minimum

        {"datetime": "2025-10-31T10:00:00", "reading_value": 21.5},- Alert: <300 lux

        {"datetime": "2025-10-31T10:01:00", "reading_value": 21.6}

      ]### Health Check

    }

```http

  ],GET http://localhost:6001/health

  "parameters": {```

    "window_size": 10,

    "threshold": 2.0**Response:**

  }

```json

}{

  "status": "ok",

# List available analyses  "components": ["analytics", "decider", "t5_training"],

GET http://localhost:6001/analytics/list  "timestamp": "2025-01-08T10:30:15Z"

```}

```

**Internal URL**: `http://microservices:6000`

## 4. Decider Service

**Supported Analysis Types** (30+):

```python**Port**: 6009  

DESCRIPTIVE = [**Container**: `decider_service`  

    "summary_statistics", "histogram", "distribution_analysis",**Technology**: Python, FastAPI

    "outlier_detection", "data_quality", "timeseries_analysis"

]### Purpose


DIAGNOSTIC = [Determines:

    "correlation_analysis", "comparative_analysis", "pattern_recognition",1. **Should analytics be performed?** (Yes/No)

    "variance_analysis", "lag_analysis", "seasonal_decomposition"2. **Which analytics function?** (trend, anomaly, compare, etc.)

]

### Decision Logic

PREDICTIVE = [

    "trend_analysis", "forecast", "anomaly_prediction",**ML-Based** (when models available):

    "regression_analysis", "classification", "clustering"- Binary classifier: perform analytics or not

]- Multi-class classifier: which analytics type

- Trained on question-label pairs

PRESCRIPTIVE = [

    "optimization", "what_if_scenario", "resource_allocation",**Rule-Based** (fallback):

    "scheduling", "anomaly_response", "threshold_recommendations"- Keyword matching

]- Pattern recognition

- Intent classification

REAL_TIME = [

    "streaming_analytics", "real_time_anomaly", "live_dashboard",### API Reference

    "alert_generation", "performance_monitoring"

]#### Decide

```http

POST http://localhost:6009/decide

**Docker Compose**:Content-Type: application/json

```yaml

microservices:{

  build: ./microservices  "question": "What is the temperature trend in zone 5.04?"

  ports:}

    - "6001:6000"```

  volumes:

    - ./rasa-bldg1/shared_data:/app/shared_data**Response:**

  environment:```json

    - FLASK_ENV=production{

  networks:  "perform_analytics": true,

    - ontobot_network  "analytics": "analyze_sensor_trend"

```}

```

**See Also**: [Analytics API Reference](analytics_api.md)

**Analytics Labels:**

---- `retrieve_latest_value`: Simple value retrieval

- `analyze_sensor_trend`: Trend over time

### 5. Decider Service- `detect_anomalies`: Anomaly detection

- `compare_sensors`: Multi-sensor comparison

**Purpose**: Query type classification and analytics recommendation- `forecast_downtimes`: Predictive maintenance

- `aggregate_sensor_data`: Statistical aggregation

**Port**: 6009 (host & internal)- `null`: No analytics needed (TTL query only)


**Technology**: Flask 3.0, Python 3.10### Training


**Key Responsibilities**:Located in: `decider-service/data/`

- Classify user intent into analytics categories

- Recommend appropriate analysis type**Training Data Generation:**

- Confidence scoring for recommendations

```bash

- Extensible rule-based logiccd decider-service/data

python build_decider_training_direct.py

**Endpoints**:```

```bash

# Health check**Model Training:**

GET http://localhost:6009/health

```bash

cd decider-service

# Decide analyticspython train.py

POST http://localhost:6009/decide

```

Content-Type: application/json

**Files:**

{- `decider_training.direct.jsonl`: Training data

  "question": "Show me the trend for temperature over the last week"- `model/perform_model.pkl`: Binary classifier

}- `model/label_model.pkl`: Multi-class classifier

- `model/*_vectorizer.pkl`: Feature extractors

# Response:

{### Environment Variables

  "perform_analytics": true,

  "analytics": "trend_analysis",```bash

  "confidence": 0.95# Model paths

}DECIDER_PERFORM_MODEL_PATH=model/perform_model.pkl

```DECIDER_LABEL_MODEL_PATH=model/label_model.pkl


**Internal URL**: `http://decider-service:6009`# Feature settings

MAX_FEATURES=1000

**Decision Logic**:MIN_DF=1

```python
MAX_DF=0.9

KEYWORD_MAPPINGS = {```

    "trend": "trend_analysis",

    "forecast": "forecast",## 5. File Server (HTTP Server)

    "anomaly|outlier|unusual": "anomaly_detection",

    "correlation|relationship": "correlation_analysis",**Port**: 8080  

    "summary|statistics": "summary_statistics",**Container**: `http_server_bldg1`  

    "histogram": "histogram",**Technology**: Python, Flask

    "compare": "comparative_analysis",

    "pattern": "pattern_recognition"### Purpose

}

```Serves:

- Trained Rasa models

**Docker Compose**:- Analysis artifacts (charts, CSVs)

```yaml- Static files

decider-service:- API for Rasa management

  build: ./decider-service

  ports:### Directory Structure

    - "6009:6009"

  networks:```

    - ontobot_network/app/

```├── artifacts/           ← Analysis results

│   ├── trend_12345.png

---│   ├── data_12345.csv

│   └── summary_12345.json

### 6. HTTP File Server├── models/              ← Rasa models

│   ├── 20250108-123045.tar.gz

**Purpose**: Static artifact serving│   └── 20250107-183012.tar.gz

└── static/              ← Web assets

**Port**: 8080 (host & internal)

```


**Technology**: Python http.server### API Reference


**Key Responsibilities**:#### Serve Artifact

- Serve generated charts (PNG)

```http

- Serve data exports (CSV, JSON)GET http://localhost:8080/artifacts/trend_12345.png

- Provide URLs for frontend attachment display

```


**Endpoints**:**Response**: Binary file (image, CSV, JSON, etc.)

```bash

# View artifact#### List Models

GET http://localhost:8080/artifacts/<user>/<filename>```http

GET http://localhost:8080/api/rasa/models

# Example:```

GET http://localhost:8080/artifacts/john_doe/20251031_chart.png

```**Response:**

```json

**Internal URL**: `http://http_server:8080`{

  "models": [

**Directory Structure**:    {

```      "name": "20250108-123045-ancient-dust.tar.gz",

shared_data/artifacts/      "mtime": 1704709845,

  ├── john_doe/      "size": 45678901,

  │   ├── 20251031_120000_chart.png      "active": true

  │   ├── 20251031_120001_data.csv    }

  │   └── 20251031_120002_results.json  ],

  └── jane_smith/  "current": "20250108-123045-ancient-dust.tar.gz"

      └── 20251031_130000_chart.png}

```


**Docker Compose**:#### Train Model (Job-based)

```yaml
```http

http_server:POST http://localhost:8080/api/rasa/train_job2

  image: python:3.10-slimContent-Type: application/json

  command: python -m http.server 8080

  working_dir: /data{}

  ports:```

    - "8080:8080"

  volumes:**Response:**

    - ./rasa-bldg1/shared_data:/data

```json

  networks:{

    - ontobot_network  "ok": true,

```  "jobId": "train_20250108_103015",

  "message": "Training job started"

---}

```

### 7. React Frontend

#### Get Training Status

**Purpose**: User interface

```http

GET http://localhost:8080/api/rasa/train_job2/{jobId}/status

**Port**: 3000 (host), 3000 (internal)

```


**Technology**: React 18, TypeScript, Material-UI**Response:**

```json

**Key Responsibilities**:{

- Chat interface (conversational UI)  "ok": true,

- Artifact rendering (charts, tables)  "status": "running",

- User session management  "progress": "training_core",

- Detail verbosity control (show_details toggle)  "logs": "Step 50/500 - Loss: 1.234...",

  "eta": 180

**Endpoints**:}

```bash
```

# Access UI

GET http://localhost:3000#### Start Rasa Server

```http

POST http://localhost:8080/api/rasa/start

**Internal URL**: `http://frontend:3000`Content-Type: application/json


**Key Features**:{}

- Real-time message streaming

```

- Image/chart inline display

- CSV table rendering#### Stop Rasa Server

- Markdown formatting support

```http

- Mobile-responsive designPOST http://localhost:8080/api/rasa/stop

Content-Type: application/json

**Docker Compose**:

```yaml{}

frontend:```

  build: ./rasa-frontend

  ports:### Health Check

    - "3000:3000"```http

  environment:GET http://localhost:8080/health

    - REACT_APP_RASA_URL=http://localhost:5005

```

  networks:

    - ontobot_network**Response:**

```json

{

**See Also**: [Frontend UI Guide](frontend_ui.md)  "status": "ok",

  "disk_space": {

---    "total": 500000000000,

    "used": 250000000000,

## Database Services    "free": 250000000000

  },

### MySQL (Building 1 - ABACWS)  "models_count": 5,

  "artifacts_count": 127

**Port**: 3306}

```

**Schema**:

```sql## 6. NL2SPARQL Service

CREATE TABLE telemetry (

  id BIGINT AUTO_INCREMENT PRIMARY KEY,**Port**: 6005  

  sensor_uuid VARCHAR(36) NOT NULL,**Container**: `nl2sparql_service`  

  timestamp DATETIME NOT NULL,**Technology**: Python, Flask, Transformers

  sensor_value FLOAT,

  INDEX idx_sensor_time (sensor_uuid, timestamp)### Purpose

);

```Translates natural language questions to SPARQL queries using fine-tuned T5 model.


**Docker Compose**:### API Reference

```yaml

mysqlserver:#### Translate Question

  image: mysql:8.0

```http

  environment:POST http://localhost:6005/nl2sparql

    MYSQL_ROOT_PASSWORD: passwordContent-Type: application/json

    MYSQL_DATABASE: telemetry

  ports:{

    - "3306:3306"  "question": "What is the temperature in zone 5.04?"

  volumes:}

    - mysql_data:/var/lib/mysql

```

```

**Response:**

---```json

{

### TimescaleDB (Building 2 - Office)  "sparql": "PREFIX brick: <https://brickschema.org/schema/Brick#>\nSELECT ?value WHERE {\n  <http://example.org/sensor/Air_Temperature_Sensor_5.04> brick:hasValue ?value .\n}",

  "confidence": 0.95,

**Port**: 5432  "execution_time_ms": 125

}

**Hypertable**:```

```sql

CREATE TABLE telemetry (### Model Configuration

  time TIMESTAMPTZ NOT NULL,

  sensor_uuid UUID NOT NULL,**Environment Variables:**

  value DOUBLE PRECISION

```bash

);MODEL_PATH=/app/checkpoint-3

DEVICE=cuda  # or cpu

SELECT create_hypertable('telemetry', 'time');MAX_LENGTH=512

```


**Docker Compose**:### Query Log

```yaml

timescaledb:The service maintains a log of recent translations:

  image: timescale/timescaledb:latest-pg14

  environment:```http

    POSTGRES_PASSWORD: passwordGET http://localhost:6005/

    POSTGRES_DB: telemetry

```

  ports:

    - "5432:5432"**Response**: HTML page showing last 50 queries with:

```- Input question

- Generated SPARQL

---- Timestamp

- Execution time

### Cassandra (Building 3 - Data Center)

### Health Check

**Port**: 9042

```http

GET http://localhost:6005/health

**Schema**:```

```cql

CREATE KEYSPACE telemetry WITH replication = {**Response:**

  'class': 'SimpleStrategy',```json

  'replication_factor': 1{

};  "status": "ok",

  "model_path": "/app/checkpoint-3",

CREATE TABLE telemetry.sensor_data (  "device": "cpu",

  sensor_uuid uuid,  "queries_cached": 50

  timestamp timestamp,}

  value double,```

  PRIMARY KEY (sensor_uuid, timestamp)

) WITH CLUSTERING ORDER BY (timestamp DESC);## 7. Ollama (Mistral) Service

```

**Port**: 11434  

**Docker Compose**:**Container**: `ollama`  

```yaml**Technology**: Ollama runtime, Mistral 7B model

cassandra:

  image: cassandra:4.0### Purpose

  ports:

    - "9042:9042"Provides local LLM capabilities for:

  environment:- Text summarization

    - MAX_HEAP_SIZE=512M- Response generation

    - HEAP_NEWSIZE=100M- Natural language explanations

```- Context-aware recommendations


---### API Reference


## Optional Services#### Generate Completion

```http

### NL2SPARQLPOST http://localhost:11434/api/generate

Content-Type: application/json

**Purpose**: Natural language to SPARQL translation

{

**Port**: 6005  "model": "mistral",

  "prompt": "Summarize the following sensor data: ...",

**Technology**: T5-base transformer model, PyTorch  "stream": false

}

**Endpoints**:```

```bash

POST http://localhost:6005/nl2sparql**Response:**

{```json

  "question": "Show me all temperature sensors in room 5.01",{

  "entity": "bldg:Air_Temperature_Sensor_5.01"  "model": "mistral",

}  "created_at": "2025-01-08T10:30:15Z",

  "response": "The sensor data shows...",

# Response:  "done": true

{}

  "sparql_query": "SELECT ?sensor WHERE { ?sensor a brick:Temperature_Sensor . ?sensor brick:hasLocation bldg:Room_5.01 . }"```

}

```#### List Models

```http

**Internal URL**: `http://nl2sparql:6005`GET http://localhost:11434/api/tags

```

**Docker Compose** (docker-compose.extras.yml):

```yaml**Response:**

nl2sparql:```json

  build: ./Transformers{

  ports:  "models": [

    - "6005:6005"    {

  volumes:      "name": "mistral:latest",

    - ./Transformers/models:/app/models      "modified_at": "2025-01-08T10:00:00Z",

  environment:      "size": 4109856768

    - MODEL_PATH=/app/models/t5_model_final    }

```  ]

}

---```


### Ollama (LLM)### Auto-Pull Configuration


**Purpose**: Response summarization and natural language generationModels are automatically pulled on container start:


**Port**: 11434

```yaml

services:

**Technology**: Ollama runtime, Mistral 7B model  ollama:

    environment:

**Endpoints**:      - OLLAMA_MODELS=mistral

```bash    command: >

POST http://localhost:11434/api/generate      sh -c "

{        ollama serve &

  "model": "mistral:latest",        sleep 10;

  "prompt": "Summarize: Temperature increased from 20°C to 25°C over 3 hours."        ollama pull mistral;

}        wait

```      "

```

**Internal URL**: `http://ollama:11434`

## 8. Duckling Entity Extractor

**Docker Compose** (docker-compose.extras.yml):

```yaml**Port**: 8000  

ollama:**Container**: `duckling_server_bldg1`  

  image: ollama/ollama:latest**Technology**: Haskell, Duckling

  ports:

    - "11434:11434"### Purpose

  volumes:

    - ollama_data:/root/.ollamaExtracts structured entities from text:

```- **Time**: dates, times, durations

- **Number**: integers, floats, ordinals

---- **Temperature**: temperatures with units

- **Distance**: distances with units

## Service Interaction Patterns

### API Reference

### Pattern 1: Simple Query (No Analytics)

#### Parse Text

```http

User → Frontend → Rasa → Action Server → Fuseki → Action Server → Rasa → FrontendPOST http://localhost:8000/parse

```Content-Type: application/json


Example: "List all sensors in room 5.01"{

  "text": "What was the temperature yesterday at 3pm?",

### Pattern 2: Analytics Query  "locale": "en_GB",

  "tz": "Europe/London"

```}

User → Frontend → Rasa → Action Server → Fuseki → Database → Decider → Analytics → HTTP Server → Action Server → Rasa → Frontend

```

```

**Response:**

Example: "Show me temperature trends for the last week"```json

[

### Pattern 3: LLM-Enhanced Response  {

    "body": "yesterday",

```    "start": 25,

User → Frontend → Rasa → Action Server → Fuseki → Database → Analytics → Ollama → Action Server → Rasa → Frontend    "end": 34,

```    "dim": "time",

    "latent": false,

Example: "Explain the temperature patterns over the last 24 hours"    "value": {

      "type": "value",

### Pattern 4: NL2SPARQL Translation      "value": "2025-01-07T00:00:00.000Z",

      "grain": "day"

```    }

User → Frontend → Rasa → Action Server → NL2SPARQL → Fuseki → Action Server → Rasa → Frontend  },

```  {

    "body": "3pm",

Example: "What sensors monitor air quality in building A?"    "start": 38,

    "end": 41,

---    "dim": "time",

    "value": {

## Health Monitoring      "type": "value",

      "value": "2025-01-08T15:00:00.000Z",

### Health Check Script      "grain": "hour"

    }

```powershell  }

# scripts/check-health.ps1]

$services = @(```

    @{Name="Rasa"; URL="http://localhost:5005/"},

    @{Name="Action Server"; URL="http://localhost:5055/health"},### Supported Dimensions

    @{Name="Fuseki"; URL="http://localhost:3030/$/ping"},

    @{Name="Analytics"; URL="http://localhost:6001/health"},- `time`: Dates, times, ranges

    @{Name="Decider"; URL="http://localhost:6009/health"},- `number`: Numeric values

    @{Name="File Server"; URL="http://localhost:8080/"},- `temperature`: With units (°C, °F)

    @{Name="Frontend"; URL="http://localhost:3000/"}- `distance`: With units (m, km, miles)

)- `volume`: With units (L, ml, gallons)

- `amount-of-money`: Currency

foreach ($svc in $services) {- `duration`: Time spans

    try {- `ordinal`: First, second, third...

        $response = Invoke-WebRequest -Uri $svc.URL -TimeoutSec 5

        Write-Host "✓ $($svc.Name): OK" -ForegroundColor Green## Service Integration Patterns

    } catch {

        Write-Host "✗ $($svc.Name): FAILED" -ForegroundColor Red### 1. Rasa → Action Server → Analytics

    }

}

```

```User: "Show me the temperature trend"

  ↓

### Expected Response TimesRasa identifies intent: get_trend

  ↓

 | Service | Health Check Latency | Query Latency | Action Server: ActionGetTrend

 | --------- | --------------------- | --------------- | ↓

 | Rasa | < 50 ms | 200-500 ms | Decider Service: "analyze_sensor_trend"

 | Action Server | < 20 ms | 1-3 seconds | ↓

 | Fuseki | < 10 ms | 50-200 ms | Analytics Microservices: Run analysis

 | Analytics | < 30 ms | 500 ms - 2s | ↓

 | Decider | < 20 ms | < 100 ms | Action Server: Format response + artifact

 | NL2SPARQL | < 50 ms | 300-800 ms | ↓

 | Ollama | < 100 ms | 2-5 seconds | Rasa: Send to user

```

---

### 2. NL2SPARQL → Fuseki Query

## Port Reference

```

### Host Ports (localhost access)User: "What sensors are in zone 5?"

  ↓

 | Service | Host Port | Container Port | Protocol | NL2SPARQL: Translate to SPARQL

 | --------- | ----------- | ---------------- | ---------- | ↓

 | Frontend | 3000 | 3000 | HTTP | Query Fuseki: Execute SPARQL

 | Rasa Core | 5005 | 5005 | HTTP | ↓

 | Action Server | 5055 | 5055 | HTTP | Parse Results: Extract sensor list

 | Fuseki | 3030 | 3030 | HTTP | ↓

 | MySQL | 3306 | 3306 | TCP | Format Response: Natural language

 | TimescaleDB | 5432 | 5432 | TCP | ```

 | Cassandra | 9042 | 9042 | TCP | 

 | Analytics | 6001 | 6000 | HTTP | ### 3. Ollama Summarization

 | NL2SPARQL | 6005 | 6005 | HTTP | 

 | Decider | 6009 | 6009 | HTTP | ```

 | HTTP Server | 8080 | 8080 | HTTP | Analytics Result: Large JSON dataset

 | Ollama | 11434 | 11434 | HTTP | ↓

Ollama: "Summarize this data for a non-technical user"

### Internal Service Names (Docker network)  ↓

Generated Summary: Natural language explanation

Use these names for inter-container communication:  ↓

Include in Response: User-friendly text

```python
```

# Action Server → Analytics

requests.post("http://microservices:6000/analytics/run", ...)## Deployment Considerations


# Action Server → Fuseki### Resource Requirements

requests.post("http://fuseki-db:3030/trial/sparql", ...)

 | Service | CPU | Memory | Disk | 

# Action Server → Decider|---------|-----|--------|------|

requests.post("http://decider-service:6009/decide", ...)| Rasa | 2 cores | 4 GB | 2 GB |

 | Actions | 1 core | 2 GB | 500 MB | 

# Action Server → NL2SPARQL| Analytics | 2 cores | 4 GB | 1 GB |

requests.post("http://nl2sparql:6005/nl2sparql", ...)| NL2SPARQL | 4 cores | 8 GB | 4 GB (model) |

 | Ollama | 4 cores | 8 GB | 8 GB (model) | 

# Action Server → Ollama| Duckling | 1 core | 1 GB | 100 MB |

requests.post("http://ollama:11434/api/generate", ...)

### Network Configuration

# Action Server → Database

mysql.connector.connect(host="mysqlserver", ...)All services use internal Docker network `ontobot-network`:

```

```yaml

---networks:

  ontobot-network:

## Troubleshooting    driver: bridge

```

### Service Won't Start

**Internal DNS:**

```bash- `rasa_bldg1:5005`

# Check container logs- `action_server_bldg1:5055`

docker logs <container_name>- `microservices:6000`

- `decider-service:6009`

# Check port conflicts- `nl2sparql:6005`

netstat -ano | findstr :<port>

### Health Monitoring

# Restart service

docker-compose restart <service_name>Setup health checks for all services:

```

```bash

### Service Unreachable# Check all services

curl http://localhost:5005/version

```bashcurl http://localhost:5055/health

# Verify network connectivitycurl http://localhost:6001/health

docker network inspect ontobot_networkcurl http://localhost:6009/health

curl http://localhost:6005/health

# Test from within containercurl http://localhost:8080/health

docker exec -it action_server_bldg1 curl http://fuseki-db:3030/$/ping

```

```

### Logging

### High Latency

View logs for debugging:

```bash

# Check resource usage

```bash

docker stats# Rasa

docker logs rasa_bldg1 --tail 100 -f

# Increase heap size (Fuseki)

environment:# Actions

  - JVM_ARGS=-Xmx4gdocker logs action_server_bldg1 --tail 100 -f


# Enable caching (Action Server)# Analytics

environment:docker logs microservices_container --tail 100 -f

  - SENSOR_LIST_RELOAD_SEC=600

```# All services

docker-compose -f docker-compose.bldg1.yml logs -f

---```


## Related Documentation## Next Steps


- **[Action Server Architecture](action_server_architecture.md)**: Detailed action server design- [Frontend UI Guide](./frontend_ui.md)

- **[Analytics API](analytics_api.md)**: Analytics service reference- [Multi-Building Guide](./multi_building.md)

- **[Database Integration](database_integration.md)**: Multi-database support- [T5 Training Guide](./t5_training_guide.md)

- **[Multi-Building Support](multi_building.md)**: Building-specific configurations- [API Reference](./api_reference.md)


---

**Backend Services** - The robust foundation of OntoBot. 🛠️⚙️
