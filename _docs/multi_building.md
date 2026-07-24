---
layout: post
title: Multi-Building Support Guide
date: 2025-10-31
---

# Multi-Building Support Guide

**Complete guide to managing, switching, and adapting OntoBot across three distinct smart building configurations.**

---

## Overview

OntoBot supports **three distinct smart buildings**, each with different sensor configurations, databases, and operational characteristics. The system is designed for **building portability**, allowing researchers and developers to adapt the framework to their own facilities.

### Building Taxonomy

 | Building | Type | Primary Focus | Sensors | Database | Port Offset | 
 | ---------- | ------ | --------------- | --------- | ---------- | ------------- | 
 | **Building 1 (ABACWS)** | Real Testbed | Indoor Environmental Quality | 680 | MySQL 8.0 | 3307 | 
 | **Building 2 (Office)** | Synthetic | HVAC & Thermal Comfort | 329 | TimescaleDB 2.11 | 5433 | 
 | **Building 3 (Data Center)** | Synthetic | Cooling & Power Distribution | 597 | Cassandra 4.1 | 9042 | 

**Total System Coverage**: **1,606 sensors** across all buildings

---

## Quick Reference: Port Mappings

### Building 1 (ABACWS)

 | Service | Host Port | Container Port | Internal DNS | 
 | --------- | ----------- | ---------------- | -------------- | 
 | MySQL | 3307 | 3306 | mysqlserver | 
 | Rasa Core | 5005 | 5005 | rasa-bldg1 | 
 | Action Server | 5055 | 5055 | rasa-action-server-bldg1 | 
 | Fuseki | 3030 | 3030 | fuseki-db | 
 | Analytics | 6001 | 6000 | microservices | 
 | Decider | 6009 | 6009 | decider-service | 
 | HTTP Server | 8080 | 8080 | http_server | 
 | Frontend | 3000 | 3000 | rasa-ui | 

**Compose File**: `docker-compose.bldg1.yml`

**Startup**:
```bash
docker compose -f docker-compose.bldg1.yml up -d
```

---

### Building 2 (Office)

 | Service | Host Port | Container Port | Internal DNS | 
 | --------- | ----------- | ---------------- | -------------- | 
 | TimescaleDB | 5433 | 5432 | timescaledb | 
 | Rasa Core | 5005 | 5005 | rasa-bldg2 | 
 | Action Server | 5055 | 5055 | rasa-action-server-bldg2 | 
 | Fuseki | 3030 | 3030 | fuseki-db | 
 | Analytics | 6001 | 6000 | microservices | 
 | Decider | 6009 | 6009 | decider-service | 
 | HTTP Server | 8080 | 8080 | http_server | 
 | Frontend | 3000 | 3000 | rasa-ui | 

**Compose File**: `docker-compose.bldg2.yml`

**Startup**:
```bash
docker compose -f docker-compose.bldg2.yml up -d
```

---

### Building 3 (Data Center)

 | Service | Host Port | Container Port | Internal DNS | 
 | --------- | ----------- | ---------------- | -------------- | 
 | Cassandra | 9042 | 9042 | cassandra | 
 | PostgreSQL (metadata) | 5434 | 5432 | postgres | 
 | Rasa Core | 5005 | 5005 | rasa-bldg3 | 
 | Action Server | 5055 | 5055 | rasa-action-server-bldg3 | 
 | Fuseki | 3030 | 3030 | fuseki-db | 
 | Analytics | 6001 | 6000 | microservices | 
 | Decider | 6009 | 6009 | decider-service | 
 | HTTP Server | 8080 | 8080 | http_server | 
 | Frontend | 3000 | 3000 | rasa-ui | 

**Compose File**: `docker-compose.bldg3.yml`

**Startup**:
```bash
docker compose -f docker-compose.bldg3.yml up -d
```

---

## Switching Between Buildings

### Safe Switching Procedure

**IMPORTANT**: Only run **one building stack at a time** to avoid port conflicts and data corruption.

**Step 1: Stop Current Building**

```powershell
# Stop Building 1
docker compose -f docker-compose.bldg1.yml down

# Stop Building 2
docker compose -f docker-compose.bldg2.yml down

# Stop Building 3
docker compose -f docker-compose.bldg3.yml down
```

**Step 2: Verify All Services Stopped**

```powershell
docker ps  # Should show no OntoBot containers
```

**Step 3: Start Target Building**

```powershell
# Start Building 2 (example)
docker compose -f docker-compose.bldg2.yml up -d
```

**Step 4: Wait for Services to Initialize**

```powershell
# Wait 30-60 seconds for databases to start
Start-Sleep -Seconds 60

# Check health
curl http://localhost:5005/version  # Rasa
curl http://localhost:3030/$/ping   # Fuseki
curl http://localhost:6001/health   # Analytics
```

**Step 5: Verify Frontend Connection**

Open browser: `http://localhost:3000`

Type: `"hello"` → Should see building-specific welcome message.

---

### Automated Switching Script

**PowerShell Script** (`scripts/switch-building.ps1`):

```powershell
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("1", "2", "3")]
    [string]$BuildingNumber
)

$composeFiles = @{
    "1" = "docker-compose.bldg1.yml"
    "2" = "docker-compose.bldg2.yml"
    "3" = "docker-compose.bldg3.yml"
}

$buildingNames = @{
    "1" = "ABACWS (680 sensors, MySQL)"
    "2" = "Office (329 sensors, TimescaleDB)"
    "3" = "Data Center (597 sensors, Cassandra)"
}

Write-Host "Switching to Building $BuildingNumber - $($buildingNames[$BuildingNumber])" -ForegroundColor Cyan

# Stop all buildings
Write-Host "`nStopping all building stacks..." -ForegroundColor Yellow
foreach ($file in $composeFiles.Values) {
    docker compose -f $file down 2>$null
}

# Wait for cleanup
Start-Sleep -Seconds 5

# Start target building
$targetFile = $composeFiles[$BuildingNumber]
Write-Host "`nStarting $targetFile..." -ForegroundColor Green
docker compose -f $targetFile up -d

# Wait for initialization
Write-Host "`nWaiting for services to initialize (60 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 60

# Health checks
Write-Host "`nPerforming health checks..." -ForegroundColor Cyan

$healthChecks = @(
    @{ Name = "Rasa Core"; Url = "http://localhost:5005/version" },
    @{ Name = "Fuseki"; Url = "http://localhost:3030/$/ping" },
    @{ Name = "Analytics"; Url = "http://localhost:6001/health" },
    @{ Name = "Decider"; Url = "http://localhost:6009/health" },
    @{ Name = "HTTP Server"; Url = "http://localhost:8080" },
    @{ Name = "Frontend"; Url = "http://localhost:3000" }
)

foreach ($check in $healthChecks) {
    try {
        $response = Invoke-WebRequest -Uri $check.Url -TimeoutSec 5 -UseBasicParsing
        Write-Host "✓ $($check.Name): OK" -ForegroundColor Green
    } catch {
        Write-Host "✗ $($check.Name): FAILED" -ForegroundColor Red
    }
}

Write-Host "`nBuilding $BuildingNumber is ready!" -ForegroundColor Green
Write-Host "Open browser: http://localhost:3000" -ForegroundColor Cyan
```

**Usage**:
```powershell
# Switch to Building 2
.\scripts\switch-building.ps1 -BuildingNumber 2

# Switch to Building 3
.\scripts\switch-building.ps1 -BuildingNumber 3
```

---

## Building-Specific Configuration

### Building 1 (ABACWS) - MySQL

**Environment Variables** (`rasa-action-server-bldg1`):
```yaml
environment:
  DB_TYPE: mysql
  DB_HOST: mysqlserver
  DB_PORT: 3306
  DB_NAME: telemetry
  DB_USER: rasa_user
  DB_PASSWORD: rasa_pass
  FUSEKI_ENDPOINT: http://fuseki-db:3030/trial/sparql
  ANALYTICS_URL: http://microservices:6000/analytics/run
  DECIDER_URL: http://decider-service:6009/decide
  FILE_SERVER_URL: http://http_server:8080
```

**Sensor List**: `rasa-bldg1/actions/sensor_list.txt` (680 sensors)

**Knowledge Graph**: `bldg1/trial/dataset/*.ttl`

**Unique Features**:
- 20 sensor types per zone (most comprehensive)
- Multi-gas sensors (MQ2, MQ3, MQ5, MQ9)
- Formaldehyde and NO2 monitoring
- Real-world data from Cardiff University

---

### Building 2 (Office) - TimescaleDB

**Environment Variables** (`rasa-action-server-bldg2`):
```yaml
environment:
  DB_TYPE: timescaledb
  DB_HOST: timescaledb
  DB_PORT: 5432
  DB_NAME: building2
  DB_USER: postgres
  DB_PASSWORD: postgres
  FUSEKI_ENDPOINT: http://fuseki-db:3030/trial/sparql
  ANALYTICS_URL: http://microservices:6000/analytics/run
  DECIDER_URL: http://decider-service:6009/decide
  FILE_SERVER_URL: http://http_server:8080
```

**Sensor List**: `rasa-bldg2/actions/sensor_list.txt` (329 sensors)

**Knowledge Graph**: `bldg2/trial/dataset/*.ttl`

**Unique Features**:
- 15 AHU units with 8 sensors each
- 50 thermal zones with temperature/occupancy/CO2
- Central plant equipment (chillers, boilers)
- Optimized for HVAC research

---

### Building 3 (Data Center) - Cassandra

**Environment Variables** (`rasa-action-server-bldg3`):
```yaml
environment:
  DB_TYPE: cassandra
  CASSANDRA_HOST: cassandra
  CASSANDRA_PORT: 9042
  CASSANDRA_KEYSPACE: building3
  PG_HOST: postgres
  PG_PORT: 5432
  PG_DATABASE: thingsboard
  PG_USER: postgres
  PG_PASSWORD: postgres
  FUSEKI_ENDPOINT: http://fuseki-db:3030/trial/sparql
  ANALYTICS_URL: http://microservices:6000/analytics/run
  DECIDER_URL: http://decider-service:6009/decide
  FILE_SERVER_URL: http://http_server:8080
```

**Sensor List**: `rasa-bldg3/actions/sensor_list.txt` (597 sensors)

**Knowledge Graph**: `bldg3/trial/dataset/*.ttl`

**Unique Features**:
- 12 CRAC units with 15 sensors each
- 10 UPS systems with battery monitoring
- 20 PDUs with 3-phase power tracking
- 40 racks with inlet/outlet/power sensors
- High-availability Cassandra cluster

---

## Shared vs Building-Specific Services

### Shared Services (Common Across All Buildings)

These services are **identical** and can be shared:

1. **Fuseki Knowledge Graph** (`fuseki-db`)
   - Hosts Brick Schema ontologies for all buildings
   - Dataset-specific: `bldg1/trial`, `bldg2/trial`, `bldg3/trial`
   - Port: 3030

2. **Analytics Microservices** (`microservices`)
   - 30+ analysis types (descriptive, diagnostic, predictive)
   - Building-agnostic algorithms
   - Port: 6001

3. **Decider Service** (`decider-service`)
   - Classifies queries into analytics types
   - Building-independent logic
   - Port: 6009

4. **HTTP File Server** (`http_server`)
   - Serves artifacts (charts, CSVs)
   - Shared volume: `rasa-ui/shared_data`
   - Port: 8080

5. **React Frontend** (`rasa-ui`)
   - Auto-detects active building via Rasa
   - Unified UI across buildings
   - Port: 3000

---

### Building-Specific Services

These services are **unique per building**:

1. **Database**
   - Building 1: MySQL (port 3307)
   - Building 2: TimescaleDB (port 5433)
   - Building 3: Cassandra (port 9042) + PostgreSQL (port 5434)

2. **Rasa Core**
   - Building-specific models in `rasa-bldgX/models/`
   - Training data in `rasa-bldgX/data/`
   - Config in `rasa-bldgX/config.yml`

3. **Action Server**
   - Building-specific actions in `rasa-bldgX/actions/`
   - Sensor lists: `rasa-bldgX/actions/sensor_list.txt`
   - Database connectors: `rasa-bldgX/actions/db_connector.py`

---

## Adapting OntoBot to Your Building

### 7-Step Adaptation Process

#### Step 1: Define Your Building Profile

**Questions to Answer**:
- What type of building? (office, residential, industrial, laboratory)
- How many sensors? What types?
- What database do you prefer? (MySQL, TimescaleDB, Cassandra, other)
- What are your primary use cases? (energy, comfort, IAQ, safety)

**Example Profile**:
```yaml
building:
  name: "Research Lab Building"
  type: "Laboratory"
  sensor_count: 450
  sensor_types:
    - temperature (50)
    - humidity (50)
    - co2 (40)
    - fume_hood_airflow (30)
    - chemical_storage_temperature (20)
    - pressure_differential (60)
    - gas_detection (50)
    - door_access (100)
  database: timescaledb
  use_cases:
    - fume hood safety monitoring
    - chemical storage compliance
    - lab pressure control
    - occupancy tracking
```

---

#### Step 2: Create Building Directory Structure

```bash
# Clone Building 2 as template (most generic)
cp -r rasa-bldg2 rasa-lab

# Update directory structure
rasa-lab/
├── actions/
│   ├── actions.py              # Custom actions
│   ├── db_connector.py         # Database interface
│   ├── sensor_list.txt         # All 450 sensors
│   └── sensor_mappings.txt     # Sensor metadata
├── data/
│   ├── nlu.yml                 # Training data
│   ├── rules.yml               # Conversation rules
│   └── stories.yml             # Conversation flows
├── models/                      # Trained models
├── config.yml                   # Rasa configuration
├── domain.yml                   # Intents, entities, slots
├── Dockerfile                   # Action server image
└── Dockerfile.rasa              # Rasa core image
```

---

#### Step 3: Define Sensor List

Create `rasa-lab/actions/sensor_list.txt`:

```
# Fume Hood Airflow Sensors
Fume_Hood_1_Airflow_Sensor
Fume_Hood_2_Airflow_Sensor
...
Fume_Hood_30_Airflow_Sensor

# Chemical Storage Temperature Sensors
Chemical_Storage_1_Temperature_Sensor
Chemical_Storage_2_Temperature_Sensor
...
Chemical_Storage_20_Temperature_Sensor

# Lab Room Temperature Sensors
Lab_101_Temperature_Sensor
Lab_102_Temperature_Sensor
...
Lab_150_Temperature_Sensor

# Pressure Differential Sensors
Lab_101_Pressure_Differential_Sensor
Lab_102_Pressure_Differential_Sensor
...
Lab_160_Pressure_Differential_Sensor

# Gas Detection Sensors (multiple types)
Lab_101_CO_Gas_Sensor
Lab_101_Chlorine_Gas_Sensor
Lab_101_Ammonia_Gas_Sensor
...
```

**Generate from Database**:
```python
# scripts/generate_sensor_list.py
import psycopg2

conn = psycopg2.connect(
    host="localhost", port=5433,
    database="research_lab",
    user="postgres", password="postgres"
)

cursor = conn.cursor()
cursor.execute("SELECT DISTINCT sensor_name FROM sensor_data ORDER BY sensor_name")

with open("rasa-lab/actions/sensor_list.txt", "w") as f:
    f.write("# Laboratory Sensors\n\n")
    for (sensor_name,) in cursor.fetchall():
        f.write(f"{sensor_name}\n")

print("sensor_list.txt generated with 450 sensors")
```

---

#### Step 4: Configure Database Connection

**Docker Compose** (`docker-compose.lab.yml`):

```yaml
services:
  # TimescaleDB for lab building
  timescaledb-lab:
    image: timescale/timescaledb:latest-pg15
    container_name: timescaledb-lab
    ports:
      - "5435:5432"  # Use unique port
    environment:
      POSTGRES_DB: research_lab
      POSTGRES_USER: lab_user
      POSTGRES_PASSWORD: lab_pass
    volumes:
      - timescaledb_lab_data:/var/lib/postgresql/data
      - ./lab/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - rasa-network

  # Action server for lab
  rasa-action-server-lab:
    build:
      context: ./rasa-lab
      dockerfile: Dockerfile
    container_name: rasa-action-server-lab
    ports:
      - "5055:5055"
    environment:
      DB_TYPE: timescaledb
      DB_HOST: timescaledb-lab
      DB_PORT: 5432
      DB_NAME: research_lab
      DB_USER: lab_user
      DB_PASSWORD: lab_pass
      FUSEKI_ENDPOINT: http://fuseki-db:3030/trial/sparql
      ANALYTICS_URL: http://microservices:6000/analytics/run
      DECIDER_URL: http://decider-service:6009/decide
      FILE_SERVER_URL: http://http_server:8080
    volumes:
      - ./rasa-lab/actions:/app/actions
      - ./rasa-ui/shared_data:/app/shared_data
    depends_on:
      - timescaledb-lab
      - fuseki-db
    networks:
      - rasa-network

  # Rasa core for lab
  rasa-lab:
    build:
      context: ./rasa-lab
      dockerfile: Dockerfile.rasa
    container_name: rasa-lab
    ports:
      - "5005:5005"
    environment:
      RASA_ACTION_ENDPOINT: http://rasa-action-server-lab:5055/webhook
    volumes:
      - ./rasa-lab/models:/app/models
      - ./rasa-lab/data:/app/data
    depends_on:
      - rasa-action-server-lab
    networks:
      - rasa-network

  # Shared services (Fuseki, Analytics, etc.)
  # ... include from docker-compose.bldg2.yml
```

---

#### Step 5: Create Brick Schema Knowledge Graph

**Generate TTL File** (`lab/trial/dataset/research_lab.ttl`):

```turtle
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix : <http://example.org/research_lab#> .

# Fume Hoods
:Fume_Hood_1 a brick:Fume_Hood ;
    brick:hasPoint :Fume_Hood_1_Airflow_Sensor .

:Fume_Hood_1_Airflow_Sensor a brick:Airflow_Sensor ;
    rdfs:label "Fume_Hood_1_Airflow_Sensor" .

# Labs
:Lab_101 a brick:Laboratory ;
    brick:hasPoint :Lab_101_Temperature_Sensor,
                   :Lab_101_Humidity_Sensor,
                   :Lab_101_CO2_Sensor,
                   :Lab_101_Pressure_Differential_Sensor .

:Lab_101_Temperature_Sensor a brick:Temperature_Sensor ;
    rdfs:label "Lab_101_Temperature_Sensor" .

:Lab_101_Humidity_Sensor a brick:Humidity_Sensor ;
    rdfs:label "Lab_101_Humidity_Sensor" .

:Lab_101_CO2_Sensor a brick:CO2_Level_Sensor ;
    rdfs:label "Lab_101_CO2_Sensor" .

:Lab_101_Pressure_Differential_Sensor a brick:Differential_Pressure_Sensor ;
    rdfs:label "Lab_101_Pressure_Differential_Sensor" .

# Repeat for all 50 labs...
```

**Automate TTL Generation**:
```python
# scripts/generate_brick_ttl.py
def generate_lab_ttl(lab_number):
    return f"""
:Lab_{lab_number} a brick:Laboratory ;
    brick:hasPoint :Lab_{lab_number}_Temperature_Sensor,
                   :Lab_{lab_number}_Humidity_Sensor,
                   :Lab_{lab_number}_CO2_Sensor,
                   :Lab_{lab_number}_Pressure_Differential_Sensor .

:Lab_{lab_number}_Temperature_Sensor a brick:Temperature_Sensor ;
    rdfs:label "Lab_{lab_number}_Temperature_Sensor" .

:Lab_{lab_number}_Humidity_Sensor a brick:Humidity_Sensor ;
    rdfs:label "Lab_{lab_number}_Humidity_Sensor" .
"""

with open("lab/trial/dataset/research_lab.ttl", "w") as f:
    f.write("@prefix brick: <https://brickschema.org/schema/Brick#> .\n")
    f.write("@prefix : <http://example.org/research_lab#> .\n\n")
    
    for lab_num in range(101, 151):  # 50 labs
        f.write(generate_lab_ttl(lab_num))

print("Brick TTL generated for 50 labs")
```

---

#### Step 6: Train Rasa Model with Lab-Specific NLU

**Update Training Data** (`rasa-lab/data/nlu.yml`):

```yaml
nlu:
- intent: query_fume_hood_airflow
  examples: |
    - show me fume hood 1 airflow
    - what is the airflow in fume hood 5
    - fume hood 10 airflow rate
    - check fume hood 15 airflow

- intent: query_pressure_differential
  examples: |
    - show me pressure differential in lab 101
    - what is the pressure in lab 105
    - check lab 110 pressure differential
    - compare pressure across labs 101 to 110

- intent: query_gas_detection
  examples: |
    - show me CO levels in lab 101
    - check chlorine gas in lab 105
    - detect ammonia in lab 110
    - show me all gas sensors in lab 115

- intent: query_chemical_storage
  examples: |
    - show me chemical storage 1 temperature
    - what is the temperature in chemical storage 5
    - check all chemical storage temperatures
```

**Train Model**:
```bash
docker compose -f docker-compose.lab.yml run --rm rasa-lab train
```

---

#### Step 7: Test and Deploy

**Start Lab Building**:
```bash
docker compose -f docker-compose.lab.yml up -d
```

**Test Queries**:
```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "test_user",
    "message": "show me fume hood 1 airflow for the last 24 hours"
  }'
```

**Expected Response**:
```json
{
  "recipient_id": "test_user",
  "text": "Here is the airflow data for Fume Hood 1 over the last 24 hours:",
  "custom": {
    "chart_url": "http://localhost:8080/artifacts/test_user/fume_hood_1_airflow.png",
    "data": [...]
  }
}
```

---

## Portability Features

### 1. Database-Agnostic Actions

OntoBot's action server abstracts database differences:

```python
# Same code works with MySQL, TimescaleDB, or Cassandra
from actions.db_factory import get_database_connector

db = get_database_connector()  # Auto-detects DB type
data = db.get_sensor_data(sensor_name, start_time, end_time)
```

---

### 2. Typo-Tolerant Sensor Resolution

RapidFuzz handles sensor name variations:

```python
from rapidfuzz import fuzz

user_input = "fumehood1 airflow"
sensor_name = "Fume_Hood_1_Airflow_Sensor"

score = fuzz.ratio(user_input, sensor_name)  # 75+
# Matches despite spacing, case, and partial name
```

---

### 3. Shared Analytics Pipeline

All buildings use the same 30+ analytics types:

```python
# Works for any building
response = requests.post(
    "http://localhost:6001/analytics/run",
    json={
        "analysis_type": "trend_analysis",
        "timeseries_data": [...]
    }
)
```

---

### 4. Brick Schema Standardization

Consistent ontology across buildings:

```sparql
# Same SPARQL query works for all buildings
SELECT ?sensor WHERE {
  ?sensor rdf:type brick:Temperature_Sensor .
}
```

---

## Troubleshooting Multi-Building Issues

### Issue 1: Port Already in Use

**Symptoms**:
- `Error: bind: address already in use`
- Services fail to start

**Solutions**:
1. **Stop all building stacks**:
   ```bash
   docker compose -f docker-compose.bldg1.yml down
   docker compose -f docker-compose.bldg2.yml down
   docker compose -f docker-compose.bldg3.yml down
   ```

2. **Verify ports are free**:
   ```powershell
   netstat -ano | Select-String "3307|5433|9042|5005|5055|3030"
   ```

3. **Kill orphaned processes** (if needed):
   ```powershell
   # Find process using port 5005
   $proc = Get-NetTCPConnection -LocalPort 5005 -ErrorAction SilentlyContinue
   Stop-Process -Id $proc.OwningProcess -Force
   ```

---

### Issue 2: Wrong Building Active

**Symptoms**:
- Sensor queries return "no data found"
- Frontend shows wrong building sensors

**Solutions**:
1. **Check active Rasa service**:
   ```bash
   curl http://localhost:5005/version
   # Should return building-specific version
   ```

2. **Verify action server environment**:
   ```bash
   docker exec rasa-action-server-bldg2 env | grep DB_HOST
   # Should match expected database service
   ```

3. **Restart target building**:
   ```bash
   docker compose -f docker-compose.bldg2.yml restart
   ```

---

### Issue 3: Data Mismatch Between Buildings

**Symptoms**:
- Building 2 queries return Building 1 data
- Artifacts show wrong sensor names

**Solutions**:
1. **Check shared volumes**:
   ```bash
   docker volume ls | grep ontobot
   # Ensure separate volumes for each building database
   ```

2. **Verify Fuseki dataset**:
   ```bash
   curl http://localhost:3030/$/datasets
   # Should show correct dataset (trial)
   ```

3. **Rebuild action server with correct sensor list**:
   ```bash
   docker compose -f docker-compose.bldg2.yml build rasa-action-server-bldg2
   docker compose -f docker-compose.bldg2.yml up -d
   ```

---

## Best Practices

### 1. One Building at a Time

**DO**:
- ✅ Stop all buildings before starting a new one
- ✅ Use automated switching script
- ✅ Verify services before querying

**DON'T**:
- ❌ Run multiple buildings concurrently
- ❌ Mix building configurations
- ❌ Share database volumes across buildings

---

### 2. Clear Separation

**DO**:
- ✅ Use unique ports for each building database
- ✅ Separate Docker volumes per building
- ✅ Building-specific sensor lists

**DON'T**:
- ❌ Reuse database ports
- ❌ Share sensor_list.txt across buildings
- ❌ Mix Brick Schema datasets

---

### 3. Testing Before Switching

**DO**:
- ✅ Test health endpoints after switching
- ✅ Verify sensor queries return expected data
- ✅ Check artifact generation

**DON'T**:
- ❌ Assume services are ready immediately
- ❌ Skip health checks
- ❌ Query before databases are initialized

---

## Related Documentation

- **[Building 1 (ABACWS)](building1_abacws.md)**: MySQL configuration details
- **[Building 2 (Office)](building2_office.md)**: TimescaleDB setup
- **[Building 3 (Data Center)](building3_datacenter.md)**: Cassandra cluster
- **[Database Integration](database_integration.md)**: Multi-database support
- **[Customization Guide](customization.md)**: Adapting OntoBot to your building

---

**Multi-Building Support** - Seamlessly manage 1,606 sensors across three distinct buildings. 🏢🔄🏗️
