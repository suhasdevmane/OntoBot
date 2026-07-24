---
title: Customization
layout: post
category: docs
permalink: /docs/customization/
date: 2025-09-28
---


# Customization Guide: Adapt OntoBot to Your Building# Customization for New Buildings


This guide shows you how to adapt OntoBot to work with **your own smart building** in 7 steps. By the end, you'll have a fully functional conversational AI for your building's sensor network.Step-by-step to adapt OntoBot to a new site.


---## 1) Ontologies and TTLs


## Overview- Prepare/build TTLs for devices, locations, and relationships.

- Load TTLs into Jena Fuseki.

OntoBot is **building-agnostic** by design. The core services (Rasa, Action Server, Analytics) work with any building that provides:- Align your entity names in Rasa with ontology terms.


1. **Brick-schema ontology** (TTL files describing sensors, rooms, relationships)## 2) Sensors and mapping

2. **Time-series database** (MySQL, TimescaleDB, Cassandra, or PostgreSQL)

3. **Sensor metadata** (UUIDs, names, locations, units)- Export device list and create a UUID→sensor name mapping.

- Store mappings under `rasa-ui/shared_data/` or integrate a registry query in actions.

### What You'll Create

## 3) Data sources

```

your-building/- SQL: adjust queries in actions to your schema.

├── trial/- SPARQL: configure Fuseki dataset and credentials; optionally enable NL2SPARQL.

│   └── dataset/

│       ├── your-building.ttl          # Brick ontology## 4) Rasa training

│       ├── sensors.ttl                # Sensor definitions

│       └── relationships.ttl          # Spatial/functional links- Update intents/entities in `rasa-ui/data/` to include building-specific vocabulary.

├── docker-compose.your-building.yml   # Custom compose file- Re-train with docker compose’s `rasa-train` profile or use the Editor (6080).

└── rasa-your-building/

    ├── actions/## 5) Analytics thresholds

    │   ├── sensor_list.txt            # All sensor names

    │   ├── sensor_uuids.txt           # Name→UUID mapping- UK defaults included; override via request params (`acceptable_range`, `thresholds`).

    │   └── actions.py                 # Custom actions- Add custom analyses by editing `microservices/blueprints/analytics_service.py` and registering in the dispatcher.

    ├── data/

    │   ├── nlu.yml                    # Training examples## 6) Visualisation (optional)

    │   ├── stories.yml                # Dialogue flows

    │   └── rules.yml                  # Deterministic rules- Enable Abacws API/Visualiser in compose.

    └── models/                        # Trained models- Add your building model and update device/location overlays.

```- Set `API_HOST` for the visualiser to point to your API container.


### Time Estimate## 7) Frontend UX


- **With existing ontology**: 2-4 hours- Customize labels and shortcuts for common building queries.

- **Creating ontology from scratch**: 1-2 days- Keep action names/intents aligned with Rasa config.

- **Advanced customization**: 3-5 days

---

## Step 1: Create Brick Ontology

### Option A: Convert Existing Building Model

If you have BACnet, Haystack, or custom metadata:

**1. Install Brick tools**:
```bash
pip install brickschema brickify
```

**2. Convert to Brick**:
```python
# convert_to_brick.py
from brickschema import Graph
from brickschema.namespaces import BRICK, UNIT

g = Graph()

# Define building
g.add((
    URIRef("http://yourbuilding.example.com#Building"),
    RDF.type,
    BRICK.Building
))

# Add sensors
g.add((
    URIRef("http://yourbuilding.example.com#Temp_Sensor_101"),
    RDF.type,
    BRICK.Temperature_Sensor
))

g.add((
    URIRef("http://yourbuilding.example.com#Temp_Sensor_101"),
    RDFS.label,
    Literal("Temperature Sensor 101")
))

# Add location
g.add((
    URIRef("http://yourbuilding.example.com#Temp_Sensor_101"),
    BRICK.hasLocation,
    URIRef("http://yourbuilding.example.com#Room_101")
))

# Add unit
g.add((
    URIRef("http://yourbuilding.example.com#Temp_Sensor_101"),
    BRICK.hasUnit,
    UNIT.DEG_C
))

# Save
g.serialize("your-building.ttl", format="turtle")
```

**3. Validate**:
```python
from brickschema import Graph

g = Graph()
g.load_file("your-building.ttl")

# Check for errors
valid, _, report = g.validate()
if not valid:
    print(report)
```

### Option B: Use Brick Builder GUI

**1. Install Brick Builder**:
```bash
git clone https://github.com/BrickSchema/brick-builder
cd brick-builder
npm install
npm start
```

**2. Create building visually**:
- Add rooms/floors/zones
- Add sensors (temperature, CO2, humidity, etc.)
- Define relationships (hasLocation, isPartOf, feeds)
- Export as TTL

### Option C: Manual TTL Creation

**Template** (`your-building.ttl`):
```turtle
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix mybldg: <http://yourbuilding.example.com#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix unit: <http://qudt.org/vocab/unit/> .

# Building
mybldg:Building_Main a brick:Building ;
    rdfs:label "Main Building" .

# Floor
mybldg:Floor_1 a brick:Floor ;
    rdfs:label "Floor 1" ;
    brick:isPartOf mybldg:Building_Main .

# Room
mybldg:Room_101 a brick:Room ;
    rdfs:label "Room 101" ;
    brick:isPartOf mybldg:Floor_1 .

# Temperature Sensor
mybldg:Temp_Sensor_101 a brick:Temperature_Sensor ;
    rdfs:label "Temperature_Sensor_101" ;
    brick:hasLocation mybldg:Room_101 ;
    brick:hasUnit unit:DEG_C ;
    brick:hasUUID "12345678-1234-1234-1234-123456789abc" .

# CO2 Sensor
mybldg:CO2_Sensor_101 a brick:CO2_Level_Sensor ;
    rdfs:label "CO2_Level_Sensor_101" ;
    brick:hasLocation mybldg:Room_101 ;
    brick:hasUnit unit:PPM ;
    brick:hasUUID "87654321-4321-4321-4321-cba987654321" .

# Humidity Sensor
mybldg:Humidity_Sensor_101 a brick:Humidity_Sensor ;
    rdfs:label "Humidity_Sensor_101" ;
    brick:hasLocation mybldg:Room_101 ;
    brick:hasUnit unit:PERCENT ;
    brick:hasUUID "11111111-2222-3333-4444-555555555555" .

# HVAC Zone
mybldg:HVAC_Zone_1 a brick:HVAC_Zone ;
    rdfs:label "HVAC Zone 1" ;
    brick:hasPart mybldg:Room_101 .

# AHU (Air Handling Unit)
mybldg:AHU_1 a brick:Air_Handler_Unit ;
    rdfs:label "AHU 1" ;
    brick:feeds mybldg:HVAC_Zone_1 .
```

### Key Brick Classes for Smart Buildings

**Sensors**:
```turtle
brick:Temperature_Sensor
brick:CO2_Level_Sensor
brick:Humidity_Sensor
brick:Occupancy_Sensor
brick:Air_Quality_Sensor
brick:Luminance_Sensor
brick:Power_Sensor
brick:Energy_Sensor
brick:Flow_Sensor
brick:Pressure_Sensor
brick:VOC_Level_Sensor
brick:PM25_Sensor
brick:NO2_Level_Sensor
```

**Equipment**:
```turtle
brick:Air_Handler_Unit
brick:Fan_Coil_Unit
brick:Boiler
brick:Chiller
brick:Pump
brick:Damper
brick:Valve
brick:Variable_Frequency_Drive
```

**Locations**:
```turtle
brick:Building
brick:Floor
brick:Room
brick:Zone
brick:HVAC_Zone
brick:Lighting_Zone
```

**Relationships**:
```turtle
brick:hasLocation       # Sensor → Room
brick:isPartOf          # Room → Floor
brick:feeds             # AHU → Zone
brick:controls          # VFD → Fan
brick:hasPoint          # Equipment → Sensor
brick:hasUnit           # Sensor → Unit
brick:hasUUID           # Sensor → UUID
```

---

## Step 2: Load Ontology into Fuseki

### Create Fuseki Dataset

**1. Prepare directory**:
```bash
mkdir -p your-building/trial/dataset
cp your-building.ttl your-building/trial/dataset/
```

**2. Update docker-compose**:
```yaml
# docker-compose.your-building.yml
fuseki-db:
  image: stain/jena-fuseki:4.7.0
  ports:
    - "3030:3030"
  environment:
    - ADMIN_PASSWORD=admin
    - JVM_ARGS=-Xmx2g
  volumes:
    - ./your-building/trial:/fuseki-base/databases/trial
  networks:
    - ontobot_network
```

**3. Start Fuseki**:
```bash
docker-compose -f docker-compose.your-building.yml up -d fuseki-db
```

**4. Verify dataset**:
```bash
# Access Fuseki UI
open http://localhost:3030

# Login: admin / admin
# Dataset: trial
# Should show your sensors
```

**5. Test SPARQL query**:
```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?sensor ?label WHERE {
  ?sensor a brick:Temperature_Sensor .
  ?sensor rdfs:label ?label .
}
```

---

## Step 3: Generate Sensor Lists

### Create sensor_list.txt

**From TTL file** (automated):
```bash
# Extract all sensor labels
grep 'rdfs:label' your-building/trial/dataset/your-building.ttl | \
  cut -d'"' -f2 | \
  grep -i 'sensor' | \
  sort -u > rasa-your-building/actions/sensor_list.txt
```

**Manual creation**:
```bash
# rasa-your-building/actions/sensor_list.txt
Temperature_Sensor_101
Temperature_Sensor_102
CO2_Level_Sensor_101
CO2_Level_Sensor_102
Humidity_Sensor_101
Humidity_Sensor_102
# ... (one sensor name per line)
```

### Create sensor_uuids.txt

**Format**: `sensor_name,uuid`

```bash
# rasa-your-building/actions/sensor_uuids.txt
Temperature_Sensor_101,12345678-1234-1234-1234-123456789abc
Temperature_Sensor_102,87654321-4321-4321-4321-cba987654321
CO2_Level_Sensor_101,11111111-2222-3333-4444-555555555555
CO2_Level_Sensor_102,22222222-3333-4444-5555-666666666666
Humidity_Sensor_101,33333333-4444-5555-6666-777777777777
Humidity_Sensor_102,44444444-5555-6666-7777-888888888888
```

**From SPARQL** (automated):
```python
# generate_sensor_uuids.py
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("http://localhost:3030/trial/sparql")
sparql.setQuery("""
    PREFIX brick: <https://brickschema.org/schema/Brick#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    
    SELECT ?label ?uuid WHERE {
      ?sensor a brick:Sensor .
      ?sensor rdfs:label ?label .
      ?sensor brick:hasUUID ?uuid .
    }
""")

sparql.setReturnFormat(JSON)
results = sparql.query().convert()

with open("rasa-your-building/actions/sensor_uuids.txt", "w") as f:
    for result in results["results"]["bindings"]:
        label = result["label"]["value"]
        uuid = result["uuid"]["value"]
        f.write(f"{label},{uuid}\n")
```

### Verify Sensor Lists

```bash
# Count sensors
wc -l rasa-your-building/actions/sensor_list.txt
# Expected: Your sensor count (e.g., 150 sensors)

# Check format (sensor_uuids.txt)
head -5 rasa-your-building/actions/sensor_uuids.txt
# Expected: sensor_name,uuid format
```

---

## Step 4: Configure Database

### Option A: MySQL

**1. Create database**:
```sql
CREATE DATABASE telemetry;
USE telemetry;

CREATE TABLE telemetry (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  sensor_uuid VARCHAR(36) NOT NULL,
  timestamp DATETIME NOT NULL,
  sensor_value FLOAT,
  INDEX idx_sensor_time (sensor_uuid, timestamp)
);
```

**2. Import historical data**:
```bash
# CSV format: sensor_uuid,timestamp,sensor_value
mysql -u root -p telemetry < sensor_data.csv
```

**3. Configure action server**:
```yaml
# docker-compose.your-building.yml
action_server:
  environment:
    - DB_HOST=mysqlserver
    - DB_NAME=telemetry
    - DB_USER=root
    - DB_PASSWORD=your_password
    - DB_PORT=3306
```

### Option B: TimescaleDB

**1. Create hypertable**:
```sql
CREATE TABLE telemetry (
  time TIMESTAMPTZ NOT NULL,
  sensor_uuid UUID NOT NULL,
  value DOUBLE PRECISION
);

SELECT create_hypertable('telemetry', 'time');
```

**2. Configure action server**:
```yaml
action_server:
  environment:
    - DB_TYPE=timescaledb
    - DB_HOST=timescaledb
    - DB_NAME=telemetry
    - DB_USER=postgres
    - DB_PASSWORD=your_password
    - DB_PORT=5432
```

### Option C: Cassandra

**1. Create keyspace and table**:
```cql
CREATE KEYSPACE telemetry WITH replication = {
  'class': 'SimpleStrategy',
  'replication_factor': 1
};

CREATE TABLE telemetry.sensor_data (
  sensor_uuid uuid,
  timestamp timestamp,
  value double,
  PRIMARY KEY (sensor_uuid, timestamp)
) WITH CLUSTERING ORDER BY (timestamp DESC);
```

**2. Configure action server**:
```yaml
action_server:
  environment:
    - DB_TYPE=cassandra
    - DB_HOST=cassandra
    - DB_KEYSPACE=telemetry
    - DB_PORT=9042
```

---

## Step 5: Configure Action Server

### Update Environment Variables

```yaml
# docker-compose.your-building.yml
action_server:
  build: ./rasa-your-building/actions
  ports:
    - "5055:5055"
  environment:
    # Service URLs (use internal Docker DNS names)
    - FUSEKI_URL=http://fuseki-db:3030/trial/sparql
    - ANALYTICS_URL=http://microservices:6000/analytics/run
    - DECIDER_URL=http://decider-service:6009/decide
    - NL2SPARQL_URL=http://nl2sparql:6005/nl2sparql
    - SUMMARIZATION_URL=http://ollama:11434
    
    # Database
    - DB_HOST=mysqlserver
    - DB_NAME=telemetry
    - DB_USER=root
    - DB_PASSWORD=your_password
    
    # Typo tolerance (adjust based on your sensor naming)
    - SENSOR_FUZZY_THRESHOLD=80
    - SENSOR_LIST_RELOAD_SEC=300
    
    # Feature flags
    - ENABLE_SUMMARIZATION=true
    - ENABLE_ANALYTICS=true
    
    # File paths
    - SENSOR_LIST_FILE=/app/actions/sensor_list.txt
    - SENSOR_UUIDS_FILE=/app/actions/sensor_uuids.txt
  
  volumes:
    - ./rasa-your-building/actions:/app/actions
    - ./rasa-your-building/shared_data:/app/shared_data
  
  networks:
    - ontobot_network
```

### Adjust Fuzzy Matching Threshold

**Guidelines**:

 | Threshold | Behavior | Use Case | 
 | ----------- | ---------- | ---------- | 
 | 70-75 | Very lenient | High typo tolerance, risk of false matches | 
 | 80 (default) | Balanced | Good for most buildings | 
 | 85-90 | Strict | Precise sensor naming, fewer false positives | 
 | 95-100 | Exact | No fuzzy matching (underscore/space normalization only) | 

**Example scenarios**:

```python
# Threshold 70:
"temp sensor 101" → "Temperature_Sensor_101" ✓ (score: 75)
"tmp snsr 101" → "Temperature_Sensor_101" ✓ (score: 72)

# Threshold 80 (default):
"temp sensor 101" → "Temperature_Sensor_101" ✓ (score: 85)
"tmp snsr 101" → No match (score: 72)

# Threshold 90:
"Temperature Sensor 101" → "Temperature_Sensor_101" ✓ (score: 100)
"temp sensor 101" → No match (score: 85)
```

---

## Step 6: Train Rasa Model

### Create Training Data

**1. Copy template**:
```bash
cp -r rasa-bldg1/data rasa-your-building/data
```

**2. Update intents** (`data/nlu.yml`):
```yaml
version: "3.1"
nlu:
- intent: query_sensor_value
  examples: |
    - What is the temperature in room 101?
    - Show me CO2 levels in room 102
    - What's the humidity in room 103?
    - Get me the [temperature](sensor_type) in [room 101](location)
    - Show [CO2 level](sensor_type) for [room 102](location)

- intent: query_trend
  examples: |
    - Show me temperature trends in room 101
    - What's the trend for CO2 in room 102?
    - Display humidity patterns in room 103
    - Trend analysis for [temperature](sensor_type) in [room 101](location)

- intent: detect_anomaly
  examples: |
    - Are there any anomalies in room 101?
    - Detect unusual temperature readings
    - Find CO2 spikes in room 102
    - Anomaly detection for [temperature](sensor_type)
```

**3. Add entities**:
```yaml
- entity: sensor_type
  examples: |
    - temperature
    - CO2 level
    - humidity
    - air quality
    - occupancy

- entity: location
  examples: |
    - room 101
    - room 102
    - floor 1
    - zone A
```

**4. Create stories** (`data/stories.yml`):
```yaml
version: "3.1"
stories:
- story: query sensor value
  steps:
  - intent: query_sensor_value
    entities:
    - sensor_type: "temperature"
    - location: "room 101"
  - action: action_question_to_brickbot
  - action: utter_sensor_value

- story: query with typo
  steps:
  - intent: query_sensor_value
    entities:
    - sensor_type: "temperatur"  # Typo!
    - location: "room 101"
  - action: validate_sensor_form  # Auto-corrects typo
  - action: action_question_to_brickbot
  - action: utter_sensor_value
```

### Train Model

**Option A: Docker Compose**:
```bash
docker-compose run --rm rasa-train

# Or use VS Code task
# Task: "Train Rasa model"
```

**Option B: Manual training**:
```bash
cd rasa-your-building
rasa train
```

**Expected output**:
```
Starting training...
Training NLU model...
Training Core model...
✓ Your Rasa model is trained and saved at 'models/20251031-143052.tar.gz'.
```

### Validate Training Data

```bash
docker-compose run --rm rasa data validate

# Expected output:
# ✓ No errors found in training data
```

---

## Step 7: Test Your Deployment

### Start All Services

```bash
docker-compose -f docker-compose.your-building.yml up -d
```

### Health Check

```bash
# PowerShell
pwsh -File scripts/check-health.ps1

# Bash
bash scripts/check-health.sh
```

### Test Query

**Via REST API**:
```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test_user",
    "message": "What is the temperature in room 101?"
  }'
```

**Expected response**:
```json
[
  {
    "recipient_id": "test_user",
    "text": "The current temperature in room 101 is 22.3°C (measured at 2025-10-31 14:30:00)."
  }
]
```

### Test Typo Tolerance

```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test_user",
    "message": "What is the temperatur in room 101?"
  }'
```

**Should auto-correct** "temperatur" → "Temperature_Sensor_101"

### Test Analytics

```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test_user",
    "message": "Show me temperature trends for room 101"
  }'
```

**Expected response**:
- Text summary of trends
- Chart attachment URL
- Statistical metrics

---

## Advanced Customization

### Add Custom Analytics

**1. Create blueprint** (`microservices/blueprints/custom_analytics.py`):
```python
from flask import Blueprint, request, jsonify
import pandas as pd

custom_bp = Blueprint('custom', __name__)

@custom_bp.route('/custom/building_efficiency', methods=['POST'])
def building_efficiency():
    data = request.json
    
    # Your custom analysis logic
    timeseries = data['timeseries_data']
    df = pd.DataFrame(timeseries[0]['data'])
    
    # Calculate efficiency metric
    efficiency = calculate_efficiency(df)
    
    return jsonify({
        "success": True,
        "efficiency_score": efficiency,
        "recommendation": "Increase HVAC setpoint by 1°C"
    })
```

**2. Register blueprint** (`microservices/app.py`):
```python
from blueprints.custom_analytics import custom_bp

app.register_blueprint(custom_bp, url_prefix='/api')
```

### Add Custom Rasa Action

**1. Create action** (`rasa-your-building/actions/actions.py`):
```python
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

class ActionCustomQuery(Action):
    def name(self) -> str:
        return "action_custom_query"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        
        # Your custom logic
        user_message = tracker.latest_message.get("text")
        
        # Call your API
        result = call_custom_api(user_message)
        
        # Respond
        dispatcher.utter_message(text=f"Result: {result}")
        
        return []
```

**2. Register in domain** (`rasa-your-building/domain.yml`):
```yaml
actions:
  - action_custom_query
```

### Customize UI

**1. Update frontend config** (`rasa-frontend/src/config.js`):
```javascript
export const config = {
  buildingName: "Your Building Name",
  sensorCount: 150,  // Your sensor count
  welcomeMessage: "Welcome to Your Building AI Assistant!",
  exampleQueries: [
    "What is the temperature in room 101?",
    "Show me CO2 trends",
    "Detect anomalies in HVAC"
  ]
};
```

**2. Rebuild frontend**:
```bash
docker-compose -f docker-compose.your-building.yml build frontend
docker-compose -f docker-compose.your-building.yml up -d frontend
```

---

## Optimization Tips

### 1. Sensor Naming Conventions

**Best practices**:
- Use consistent format: `{Type}_{Subtype}_Sensor_{ID}`
- Examples:
  - ✅ `Air_Temperature_Sensor_101`
  - ✅ `CO2_Level_Sensor_101`
  - ✅ `Occupancy_Binary_Sensor_101`
  - ❌ `Temp101` (too short)
  - ❌ `air_temp_room_101_sensor` (inconsistent order)

### 2. Database Indexing

**MySQL**:
```sql
CREATE INDEX idx_sensor_time ON telemetry(sensor_uuid, timestamp);
CREATE INDEX idx_time ON telemetry(timestamp);
```

**TimescaleDB**:
```sql
CREATE INDEX ON telemetry (sensor_uuid, time DESC);
```

**Cassandra**:
```cql
-- Primary key already provides optimal indexing
PRIMARY KEY (sensor_uuid, timestamp)
```

### 3. Rasa Training Optimization

**Balance training time vs accuracy**:
```yaml
# config.yml
pipeline:
  - name: DIETClassifier
    epochs: 50  # Reduce from 100 for faster training
    
policies:
  - name: TEDPolicy
    epochs: 50  # Reduce from 100
```

### 4. Analytics Performance

**Limit data range**:
```python
# Default to last 24 hours instead of full history
start_date = datetime.now() - timedelta(days=1)
```

**Use database aggregation**:
```sql
-- Pre-aggregate in database instead of Python
SELECT 
  DATE(timestamp) as date,
  AVG(sensor_value) as avg_value
FROM telemetry
WHERE sensor_uuid = ?
GROUP BY DATE(timestamp)
```

---

## Testing Checklist

### Functional Tests

- [ ] Rasa responds to "hello"
- [ ] Simple sensor query returns value
- [ ] Typo correction works (test with deliberate typo)
- [ ] Time-based query returns historical data
- [ ] Analytics query generates chart
- [ ] Frontend displays chat messages
- [ ] Artifacts render correctly (charts, tables)
- [ ] Health endpoints return 200 OK
- [ ] SPARQL queries return sensor metadata
- [ ] Database queries return telemetry

### Performance Tests

- [ ] Simple query responds in < 1 second
- [ ] Analytics query responds in < 5 seconds
- [ ] Health checks respond in < 100 ms
- [ ] Frontend loads in < 3 seconds
- [ ] 10 concurrent users supported
- [ ] Memory usage < 8 GB
- [ ] CPU usage < 80% under load

### Error Handling Tests

- [ ] Unknown sensor returns helpful error
- [ ] Invalid date returns error message
- [ ] Database connection failure handled gracefully
- [ ] Missing sensor data returns informative message
- [ ] SPARQL query timeout handled
- [ ] Analytics service failure doesn't crash action server

---

## Deployment

### Production Checklist

**Security**:
- [ ] Change default passwords
- [ ] Enable HTTPS (TLS certificates)
- [ ] Add authentication (OAuth2/JWT)
- [ ] Sanitize SPARQL queries (prevent injection)
- [ ] Isolate databases from public network
- [ ] Use Docker secrets for credentials

**Monitoring**:
- [ ] Set up log aggregation (ELK/Splunk)
- [ ] Configure health check alerts
- [ ] Monitor resource usage (Prometheus/Grafana)
- [ ] Track error rates
- [ ] Monitor response times

**Backup**:
- [ ] Database backups (daily)
- [ ] Ontology backups (weekly)
- [ ] Model backups (after each training)
- [ ] Configuration backups (version control)

---

## Troubleshooting

### Issue: Sensor not found

**Check**:
1. Sensor exists in `sensor_list.txt`
2. Sensor exists in ontology (SPARQL query)
3. Fuzzy matching threshold appropriate
4. Sensor name format consistent

**Solution**:
```bash
# Verify sensor exists
grep -i "temp.*101" rasa-your-building/actions/sensor_list.txt

# Test fuzzy matching
python -c "from rapidfuzz import fuzz; print(fuzz.WRatio('temp sensor 101', 'Temperature_Sensor_101'))"
```

### Issue: No telemetry data

**Check**:
1. Database connection working
2. Data exists for sensor UUID
3. Date range valid
4. Query syntax correct

**Solution**:
```sql
-- Verify data exists
SELECT COUNT(*) FROM telemetry WHERE sensor_uuid = '...';

-- Check date range
SELECT MIN(timestamp), MAX(timestamp) FROM telemetry;
```

### Issue: Rasa training fails

**Check**:
1. YAML syntax valid
2. Entity annotations correct
3. Story format valid
4. Sufficient training examples

**Solution**:
```bash
# Validate data
rasa data validate

# Check for errors in logs
docker logs rasa-train
```

---

## Next Steps

### Enhance Your Deployment

1. **Add more sensor types**: Expand ontology with new sensor classes
2. **Create custom analytics**: Build domain-specific analysis functions
3. **Improve NLU**: Add more training examples for edge cases
4. **Optimize database**: Tune indexes and queries for performance
5. **Customize UI**: Brand frontend with your building's identity

### Learn More

- **[Typo Tolerance](typo_tolerance.md)**: Deep dive into fuzzy matching
- **[Analytics API](analytics_api.md)**: Full analytics reference
- **[Multi-Building Support](multi_building.md)**: Manage multiple buildings
- **[Backend Services](backend_services.md)**: Architecture details

---

## Community Support

- **GitHub Issues**: [github.com/suhasdevmane/OntoBot/issues](https://github.com/suhasdevmane/OntoBot/issues)
- **Documentation**: [suhasdevmane.github.io](https://suhasdevmane.github.io)
- **Email**: devmanesp1@cardiff.ac.uk

---

**Customization Complete!** 🎉 Your building is now ready to talk with OntoBot.
