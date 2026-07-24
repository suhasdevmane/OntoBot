---
title: Troubleshooting & FAQ
layout: post
category: docs
permalink: /docs/troubleshooting/
date: 2025-10-08
---

# Troubleshooting & FAQ

# Troubleshooting & FAQ

**Comprehensive troubleshooting guide for OntoBot covering Docker, databases, services, performance, and building-specific issues.**

Comprehensive troubleshooting guide for OntoBot covering common issues across all buildings and services.

---

## Table of Contents

## Table of Contents

- [Docker & Compose Issues](#docker--compose-issues)

1. [Docker & Compose Issues](#docker--compose-issues)- [Database Problems](#database-problems)

2. [Database Problems](#database-problems)- [Service Health Issues](#service-health-issues)

3. [Service Health Issues](#service-health-issues)- [Building-Specific Issues](#building-specific-issues)

4. [Rasa & NLU Issues](#rasa--nlu-issues)- [Performance Problems](#performance-problems)

5. [Analytics Problems](#analytics-problems)- [Development Issues](#development-issues)

6. [Building-Specific Issues](#building-specific-issues)- [FAQ](#faq)

7. [Performance Problems](#performance-problems)

8. [Development Issues](#development-issues)---

9. [Network & Connectivity](#network--connectivity)

10. [FAQ](#frequently-asked-questions)## Docker & Compose Issues


---### Problem: Containers fail to start


## Docker & Compose Issues**Symptoms:**

- `docker-compose up` exits with errors

### Issue 1: Containers Fail to Start- Services show "Exited (1)" status

- Port binding errors

**Symptoms**:

- `docker compose up` exits with errors**Solutions:**

- Services show "Exited (1)" status

- Error: "port is already allocated"```powershell

# Check Docker is running

**Solutions**:docker --version

docker ps

**1. Check Docker is running**:

```powershell# Check port conflicts

docker --versionnetstat -ano | findstr "5005"  # Windows

docker pslsof -i :5005                   # Mac/Linux

```

# Stop conflicting services

**2. Check for port conflicts**:docker-compose down

```powershelldocker-compose -f docker-compose.bldg1.yml down

# Windowsdocker-compose -f docker-compose.bldg2.yml down

netstat -ano | Select-String "5005|5055|3030|6001"docker-compose -f docker-compose.bldg3.yml down


# Linux/Mac# Clean up and restart

lsof -i :5005docker system prune -f

lsof -i :5055docker-compose -f docker-compose.bldg1.yml up --build

```


**3. Stop all building stacks**:### Problem: Out of memory errors

```powershell

docker compose -f docker-compose.bldg1.yml down**Symptoms:**

docker compose -f docker-compose.bldg2.yml down- Services crash randomly

docker compose -f docker-compose.bldg3.yml down- "Cannot allocate memory" errors

```- Slow performance


**4. Clean up Docker resources**:**Solutions:**

```powershell

# Remove stopped containers

```

docker container prune -fDocker Desktop → Settings → Resources

- Memory: Increase to 8GB minimum (16GB recommended)

# Remove unused networks- CPUs: Allocate 4+ cores

docker network prune -f- Disk: Ensure 50GB+ free space

```

# Remove dangling volumes (CAUTION: data loss)

docker volume prune -f### Problem: Volume mount issues (Windows)


# Full cleanup (removes everything)**Symptoms:**

docker system prune -a --volumes- Files not updating in containers

```- Permission denied errors

- Empty volumes

**5. Restart Docker Desktop** (Windows/Mac):

- Right-click Docker tray icon → Quit Docker Desktop**Solutions:**

- Start Docker Desktop again

- Wait 30 seconds for full initialization

```powershell

# Enable file sharing

---Docker Desktop → Settings → Resources → File Sharing

Add: C:\Users\<username>\Documents\GitHub\OntoBot

### Issue 2: "No Space Left on Device"

# Reset Docker

**Symptoms**:Docker Desktop → Troubleshoot → Reset to factory defaults

- Docker build fails with disk space error

- Containers crash with I/O errors# Use WSL2 backend (recommended)

Docker Desktop → Settings → General → Use WSL2 based engine

**Solutions**:```


**1. Check Docker disk usage**:### Problem: Network connectivity between containers

```powershell

docker system df**Symptoms:**

```- Services can't reach each other

- Connection refused errors

**Output example**:- DNS resolution failures

```

TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE**Solutions:**

Images          15        5         8.5GB     5.2GB (61%)

Containers      8         3         2.1GB     1.8GB (85%)

```yaml

Local Volumes   12        4         15GB      10GB (66%)# Ensure all services use same network

```networks:

  ontobot_network:

**2. Clean up unused resources**:    driver: bridge

```powershell

# Remove unused images# Use service names (not localhost) in URLs

docker image prune -aANALYTICS_URL: http://microservices:6000  # ✅ Correct

ANALYTICS_URL: http://localhost:6001      # ❌ Wrong

# Remove stopped containers

```

docker container prune

---

# Remove unused volumes (CAUTION)

docker volume prune## Database Problems

```

### MySQL (Building 1)

**3. Increase Docker disk limit** (Docker Desktop):

- Settings → Resources → Disk image size → Increase to 100GB+**Problem: MySQL container fails to start**


---```powershell

# Check logs

### Issue 3: Build Context Too Largedocker-compose -f docker-compose.bldg1.yml logs mysqlserver


**Symptoms**:# Common causes:

- `docker build` takes >10 minutes# 1. Corrupted data volume

- "Sending build context" shows large sizedocker-compose -f docker-compose.bldg1.yml down -v

docker volume rm ontobot_mysql_data

**Solutions**:docker-compose -f docker-compose.bldg1.yml up -d mysqlserver


**1. Create `.dockerignore`**:# 2. Port conflict (3307 in use)

```netstat -ano | findstr "3307"

# .dockerignore# Kill conflicting process or change port

**/__pycache__

**/*.pyc# 3. Insufficient memory

**/.git# Increase Docker memory to 8GB+

**/node_modules

```

**/venv

**/.venv**Problem: Slow queries**

**/models/*.tar.gz

**/logs

```sql

**/.DS_Store-- Enable slow query log

```SET GLOBAL slow_query_log = 'ON';

SET GLOBAL long_query_time = 2;

**2. Build specific services only**:

```powershell-- Check slow queries

docker compose -f docker-compose.bldg1.yml build rasa-action-server-bldg1SELECT * FROM mysql.slow_log;

```

-- Add missing indexes

---EXPLAIN SELECT * FROM sensor_readings WHERE sensor_uuid = 'uuid-123';

CREATE INDEX idx_missing ON sensor_readings(sensor_uuid, timestamp);

## Database Problems

-- Optimize table

### Issue 1: MySQL Connection FailedOPTIMIZE TABLE sensor_readings;

ANALYZE TABLE sensor_readings;

**Symptoms**:```

- Action server logs: `Can't connect to MySQL server`

- Error: `Connection refused` or `Unknown MySQL server host`**Problem: Connection timeouts**


**Solutions**:```python

# Increase connection timeout

**1. Verify MySQL is running**:import mysql.connector

```powershell

docker ps | Select-String "mysql"config = {

```    'host': 'mysqlserver',

    'user': 'root',

**2. Check MySQL health**:    'password': 'password',

```powershell    'database': 'telemetry',

docker logs mysqlserver --tail 50    'connect_timeout': 60,      # Increase from default 10

    'connection_timeout': 60

# Should see: "ready for connections"}

```


**3. Test connection from host**:### TimescaleDB (Building 2)

```powershell

mysql -h localhost -P 3307 -u rasa_user -p**Problem: TimescaleDB extension not loaded**

# Enter password: rasa_pass

```sql

-- Check if extension is loaded

**4. Test connection from action server**:SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';

```powershell

docker exec rasa-action-server-bldg1 env | Select-String "DB_"-- If not loaded, load it

CREATE EXTENSION IF NOT EXISTS timescaledb;

# Should show:

# DB_HOST=mysqlserver-- Verify hypertables

# DB_PORT=3306SELECT * FROM timescaledb_information.hypertables;

# DB_NAME=telemetry

```

```

**Problem: High disk usage**

**5. Restart database**:

```powershell
```sql

docker compose -f docker-compose.bldg1.yml restart mysqlserver-- Check table sizes

Start-Sleep -Seconds 10SELECT 

docker logs mysqlserver    hypertable_name,

```    pg_size_pretty(hypertable_size(hypertable_name::regclass)) AS total_size,

    pg_size_pretty(hypertable_size(hypertable_name::regclass, 'uncompressed')) AS uncompressed,

---    pg_size_pretty(hypertable_size(hypertable_name::regclass, 'compressed')) AS compressed

FROM timescaledb_information.hypertables;

### Issue 2: TimescaleDB Query Timeout

-- Enable compression if not already

**Symptoms**:ALTER TABLE sensor_readings SET (timescaledb.compress);

- Queries take >30 seconds

- Action server logs: `Query execution timeout`-- Manually compress chunks

SELECT compress_chunk(i) FROM show_chunks('sensor_readings') i;

**Solutions**:

-- Adjust retention policy

**1. Check hypertable compression**:SELECT remove_retention_policy('sensor_readings');

```sql
SELECT add_retention_policy('sensor_readings', INTERVAL '6 months');

SELECT * FROM timescaledb_information.chunks

```

WHERE hypertable_name = 'sensor_data'

ORDER BY chunk_name;**Problem: Continuous aggregate not updating**

```

```sql

**2. Enable compression policy** (if not already):-- Check continuous aggregate status

```sql
SELECT * FROM timescaledb_information.continuous_aggregates;

ALTER TABLE sensor_data SET (

    timescaledb.compress,-- Manually refresh

    timescaledb.compress_segmentby = 'sensor_name',CALL refresh_continuous_aggregate('sensor_readings_hourly', NULL, NULL);

    timescaledb.compress_orderby = 'timestamp DESC'

);-- Check refresh policy

SELECT * FROM timescaledb_information.jobs

SELECT add_compression_policy('sensor_data', INTERVAL '7 days');WHERE application_name LIKE 'Continuous%';

```

-- Re-create refresh policy

**3. Use continuous aggregates for long time ranges**:SELECT remove_continuous_aggregate_policy('sensor_readings_hourly');

```sql
SELECT add_continuous_aggregate_policy('sensor_readings_hourly',

-- Query hourly aggregate instead of raw data    start_offset => INTERVAL '3 hours',

SELECT hour, avg_value    end_offset => INTERVAL '1 hour',

FROM sensor_data_hourly    schedule_interval => INTERVAL '1 hour');

WHERE sensor_name = 'Zone_101_Temperature_Sensor'```

  AND hour >= NOW() - INTERVAL '30 days';

```### Cassandra (Building 3)


**4. Increase shared_buffers**:**Problem: Cassandra fails to start**

```yaml

# docker-compose.bldg2.yml

```powershell

timescaledb:# Check logs

  command: >docker-compose -f docker-compose.bldg3.yml logs cassandra

    postgres

    -c shared_buffers=2GB# Common causes:

    -c work_mem=50MB# 1. Insufficient memory (needs 4GB+ heap)

```# Increase Docker memory to 16GB total


---# 2. Port conflict (9042 in use)

netstat -ano | findstr "9042"

### Issue 3: Cassandra Node Not Ready

# 3. Corrupted data

**Symptoms**:docker-compose -f docker-compose.bldg3.yml down -v

- Cassandra takes >60 seconds to startdocker volume rm ontobot_cassandra_data

- Action server logs: `NoHostAvailable: ('Unable to connect to any servers')`docker-compose -f docker-compose.bldg3.yml up -d cassandra


**Solutions**:# Wait for Cassandra to start (3-5 minutes)

Start-Sleep -Seconds 300

**1. Wait for Cassandra initialization** (takes 30-90 seconds):```

```powershell

docker logs cassandra --follow**Problem: Slow queries**


# Wait for: "Starting listening for CQL clients"```bash

```# Check node status

docker-compose -f docker-compose.bldg3.yml exec cassandra nodetool status

**2. Check Cassandra status**:

```powershell# Monitor compaction

docker exec cassandra nodetool statusdocker-compose -f docker-compose.bldg3.yml exec cassandra nodetool compactionstats


# Should show: UN (Up/Normal)# Force compaction

```docker-compose -f docker-compose.bldg3.yml exec cassandra nodetool compact telemetry_bldg3 sensor_data


**3. Increase memory allocation**:# Check if compression enabled

```yaml# Change compaction strategy if needed

# docker-compose.bldg3.ymlALTER TABLE sensor_data

cassandra:WITH compaction = {

  environment:    'class': 'TimeWindowCompactionStrategy',

    MAX_HEAP_SIZE: "8G"  # Increase from 4G    'compaction_window_unit': 'HOURS',

    HEAP_NEWSIZE: "1600M"    'compaction_window_size': '24'

```};

```

**4. Test CQL connection**:

```powershell**Problem: Write timeouts**

docker exec -it cassandra cqlsh

```python

# Should see: Connected to Building3Cluster# Increase timeouts in client

```from cassandra.cluster import Cluster

from cassandra.policies import ExponentialReconnectionPolicy

---

cluster = Cluster(

## Service Health Issues    ['cassandra'],

    reconnection_policy=ExponentialReconnectionPolicy(1, 60),

### Issue 1: Rasa Core Not Responding    protocol_version=4,

    connect_timeout=30,

**Symptoms**:    control_connection_timeout=30

- `curl http://localhost:5005/version` times out)

- Frontend shows "Connection failed"

# Use prepared statements

**Solutions**:prepare = session.prepare("""

    INSERT INTO sensor_data (sensor_uuid, timestamp, value)

**1. Check Rasa is running**:    VALUES (?, ?, ?)

```powershell""")

docker ps | Select-String "rasa"session.execute(prepare, (uuid, timestamp, value))

```

# Use batch for bulk inserts

**2. Check Rasa logs**:from cassandra.query import BatchStatement, BatchType

```powershellbatch = BatchStatement(batch_type=BatchType.UNLOGGED)

docker logs rasa-bldg1 --tail 100

```


# Look for errors or "Rasa server is up and running"---

```

## Service Health Issues

**3. Verify model is loaded**:

```powershell### Rasa Core (5005)

docker logs rasa-bldg1 | Select-String "model"

**Problem: Rasa fails to start or crashes**

# Should see: "Loading model: /app/models/20251031-140000.tar.gz"

```powershell

# Check logs

**4. Check if model exists**:docker-compose -f docker-compose.bldg1.yml logs rasa

```powershell

docker exec rasa-bldg1 ls -lh /app/models/# Common causes:

# 1. Model not found

# Should show at least one .tar.gz filedocker-compose -f docker-compose.bldg1.yml exec rasa rasa train

```docker-compose -f docker-compose.bldg1.yml restart rasa


**5. Train new model if missing**:# 2. Invalid domain.yml or config.yml

```powershelldocker-compose -f docker-compose.bldg1.yml exec rasa rasa data validate

docker compose -f docker-compose.bldg1.yml run --rm rasa-train

```# 3. Port conflict

netstat -ano | findstr "5005"

**6. Restart Rasa**:```

```powershell

docker compose -f docker-compose.bldg1.yml restart rasa-bldg1**Problem: NLU not detecting intents**

```

```powershell

---# Test NLU

docker-compose -f docker-compose.bldg1.yml exec rasa rasa shell nlu

### Issue 2: Action Server Crashes on Startup

# Retrain model

**Symptoms**:docker-compose -f docker-compose.bldg1.yml exec rasa rasa train nlu --force

- Action server container exits immediately

- Logs show Python import errors# Check intent examples

docker-compose -f docker-compose.bldg1.yml exec rasa rasa data validate --domain domain.yml

**Solutions**:```


**1. Check Python dependencies**:### Action Server (5055)

```powershell

docker logs rasa-action-server-bldg1**Problem: Action server not responding**


# Look for: ModuleNotFoundError, ImportError

```powershell

```# Check health

curl http://localhost:5055/health

**2. Rebuild action server image**:

```powershell# Check logs

docker compose -f docker-compose.bldg1.yml build --no-cache rasa-action-server-bldg1docker-compose -f docker-compose.bldg1.yml logs actions

docker compose -f docker-compose.bldg1.yml up -d rasa-action-server-bldg1

```# Common causes:

# 1. Database connection failure

**3. Verify sensor_list.txt exists**:# Check DB_HOST, DB_PORT, DB_PASSWORD environment variables

```powershell

docker exec rasa-action-server-bldg1 ls -lh /app/actions/sensor_list.txt# 2. Missing dependencies

docker-compose -f docker-compose.bldg1.yml exec actions pip list

# Should exist and be >0 bytes

```# 3. Python syntax errors in actions.py

docker-compose -f docker-compose.bldg1.yml exec actions python -m py_compile /app/actions/actions.py

**4. Check environment variables**:```

```powershell

docker exec rasa-action-server-bldg1 env | Select-String "DB_|FUSEKI|ANALYTICS"**Problem: Custom actions failing**

```

```python

**5. Test action server manually**:# Add logging to actions

```powershellimport logging

docker exec -it rasa-action-server-bldg1 python -c "from actions.actions import ActionGetSensorData"logger = logging.getLogger(__name__)


# Should not show errorsclass ActionQueryCO2(Action):

```    def run(self, dispatcher, tracker, domain):

        try:

---            # Your code here

            logger.info("Action executed successfully")

### Issue 3: Analytics Service 500 Error        except Exception as e:

            logger.error(f"Action failed: {str(e)}")

**Symptoms**:            dispatcher.utter_message(text="Sorry, something went wrong")

- Analytics returns HTTP 500 Internal Server Error        return []

- Logs show Python exceptions

```


**Solutions**:### Analytics Microservice (6001)


**1. Check analytics logs**:**Problem: Analytics service not starting**

```powershell

docker logs microservices --tail 100

```powershell

```# Check logs

docker-compose -f docker-compose.bldg1.yml logs microservices

**2. Test analytics health**:

```powershell# Check dependencies

curl http://localhost:6001/healthdocker-compose -f docker-compose.bldg1.yml exec microservices pip list

```

# Common causes:

**3. Verify shared_data volume is writable**:# 1. Import errors

```powershelldocker-compose -f docker-compose.bldg1.yml exec microservices python -c "import pandas, numpy, sklearn"

docker exec microservices ls -la /app/shared_data/artifacts/

# 2. Port conflict

# Should be writablenetstat -ano | findstr "6001"

```


**4. Restart analytics service**:**Problem: Analytics requests timing out**

```powershell

docker compose -f docker-compose.bldg1.yml restart microservices

```python

```# Increase timeout in requests

import requests

**5. Check disk space for artifacts**:

```powershellresponse = requests.post(

docker exec microservices df -h /app/shared_data    'http://localhost:6001/analytics/run',

```    json={...},

    timeout=300  # Increase from default 30s

---)


## Rasa & NLU Issues# Check analytics logs for errors

docker-compose -f docker-compose.bldg1.yml logs -f microservices

### Issue 1: Intent Not Recognized

```


**Symptoms**:### Frontend (3000)

- User query triggers fallback intent

- Bot responds: "I didn't understand that"**Problem: Frontend not loading**


**Solutions**:```powershell

# Check if running

**1. Check training data has examples**:curl http://localhost:3000

```yaml

# rasa-bldg1/data/nlu.yml# Rebuild frontend

- intent: query_sensor_datadocker-compose -f docker-compose.bldg1.yml up --build frontend

  examples: |

    - show me temperature# Check logs

    - what is the co2 leveldocker-compose -f docker-compose.bldg1.yml logs frontend

    - display humidity data

```# Common causes:

# 1. Node modules not installed

**2. Test NLU directly**:docker-compose -f docker-compose.bldg1.yml exec frontend npm install

```bash

curl -X POST http://localhost:5005/model/parse \# 2. Environment variables missing

  -H "Content-Type: application/json" \# Check REACT_APP_RASA_URL, REACT_APP_FILE_SERVER_URL

  -d '{"text": "show me temperature"}'```

```

**Problem: Frontend can't connect to Rasa**

**Response shows intent confidence**:

```json
```javascript

{// Check CORS settings in rasa/credentials.yml

  "intent": {"name": "query_sensor_data", "confidence": 0.92},socketio:

  "entities": [{"entity": "sensor_type", "value": "temperature"}]  user_message_evt: user_uttered

}  bot_message_evt: bot_uttered

```  session_persistence: true

  cors: ["*"]  # Or specific origin: ["http://localhost:3000"]

**3. Add more training examples** if confidence <0.7:

```yaml// Check environment variables

- intent: query_sensor_dataconsole.log(process.env.REACT_APP_RASA_URL);

  examples: |```

    - show me temperature

    - display temperature---

    - get temperature data

    - what is the temperature## Building-Specific Issues

    - tell me the temperature

    - temperature reading### Building 1 (ABACWS) - MySQL

    - temp data

```**Problem: No sensor data**


**4. Retrain model**:```sql

```powershell-- Check if data exists

docker compose -f docker-compose.bldg1.yml run --rm rasa-trainSELECT COUNT(*) FROM sensor_readings;

docker compose -f docker-compose.bldg1.yml restart rasa-bldg1SELECT COUNT(*) FROM sensors;

```

-- Check latest readings

---SELECT * FROM sensor_readings ORDER BY timestamp DESC LIMIT 10;


### Issue 2: Entity Not Extracted-- If empty, check data ingestion

-- Verify ThingsBoard or data pipeline is running

**Symptoms**:```

- Slot `sensor_type` is None

- Action fails: "Missing required slot"**Problem: Missing zones**


**Solutions**:```sql

-- List all zones

**1. Check entity in training data**:SELECT DISTINCT zone_id FROM sensors;

```yaml

- intent: query_sensor_data-- Add missing zones

  examples: |INSERT INTO zones (zone_id, floor, building, description)

    - show me [temperature](sensor_type)VALUES ('5.12', 5, 'Building1', 'Zone 5.12');

    - what is the [co2](sensor_type) level

```

```

### Building 2 (Office) - TimescaleDB

**2. Use lookup tables for sensor types**:

```yaml**Problem: Hypertable not created**

# rasa-bldg1/data/nlu.yml

- lookup: sensor_type

```sql

  examples: |-- Check if table is a hypertable

    - temperatureSELECT * FROM timescaledb_information.hypertables;

    - humidity

    - co2-- If not, convert to hypertable

    - tvocSELECT create_hypertable('sensor_readings', 'time');

    - pm25

```-- Verify

\d+ sensor_readings

**3. Test entity extraction**:```

```bash

curl -X POST http://localhost:5005/model/parse \**Problem: No HVAC data**

  -d '{"text": "show me temperature"}'

```sql

-- Check equipment IDs

**4. Check domain.yml has entity defined**:SELECT DISTINCT equipment_id FROM sensor_readings;

```yaml

entities:-- Check sensor types

  - sensor_typeSELECT DISTINCT sensor_type, COUNT(*) FROM sensor_readings GROUP BY sensor_type;

  - zone_id

  - time_range-- Verify data pipeline for AHU, Chiller, Boiler data

```


---### Building 3 (Data Center) - Cassandra


### Issue 3: Form Not Filling Slots**Problem: No telemetry data**


**Symptoms**:```cql

- Bot keeps asking for same slot-- Check keyspace

- Form doesn't progressDESCRIBE KEYSPACES;

USE telemetry_bldg3;

**Solutions**:

-- Check tables

**1. Check form definition in domain.yml**:DESCRIBE TABLES;

```yaml

forms:-- Count records

  sensor_form:SELECT COUNT(*) FROM sensor_data;  -- Note: Expensive on Cassandra

    required_slots:

      - sensor_type-- Check recent data

      - start_dateSELECT * FROM sensor_data LIMIT 10;

      - end_date

```

```

**Problem: Alarm table empty**

**2. Verify slot mappings**:

```yaml
```cql

slots:-- Verify alarm table exists

  sensor_type:DESCRIBE TABLE alarms;

    type: text

    mappings:-- Check if data ingestion is working

      - type: from_entity-- Alarms should be generated by monitoring service

        entity: sensor_type

```

```

---

**3. Check form validation in actions**:

```python## Performance Problems

class ValidateSensorForm(FormValidationAction):

    def name(self) -> Text:### Slow Dashboard Loading

        return "validate_sensor_form"

    ```

    def validate_sensor_type(self, slot_value, dispatcher, tracker, domain):1. Check database query performance (see database sections above)

        # Ensure valid sensor type2. Verify Analytics service is responsive

        if slot_value in ["temperature", "humidity", "co2"]:3. Check network latency between services

            return {"sensor_type": slot_value}4. Review frontend console for errors (F12 in browser)

        else:5. Consider caching frequently accessed data

            return {"sensor_type": None}

```

```

### High CPU Usage

---

```powershell

## Analytics Problems# Check container resource usage

docker stats

### Issue 1: "Insufficient Data for Analysis"

# Identify problematic container

**Symptoms**:# Common culprits:

- Analytics returns 422 error# - Rasa (model loading, NLU processing)

- Message: "Requires at least 10 data points"# - Analytics (heavy computation)

# - Cassandra (compaction)

**Solutions**:

# Allocate more resources in docker-compose.yml

**1. Check data query time range**:services:

```python  rasa:

# Increase time range    deploy:

start_time = datetime.now() - timedelta(hours=48)  # Instead of 1 hour      resources:

```        limits:

          cpus: '2.0'

**2. Verify data exists in database**:          memory: 4G

```sql
```

SELECT COUNT(*)

FROM ts_kv### Memory Leaks

WHERE key_name = 'Air_Temperature_Sensor_5.01'

  AND ts >= 1730293200000;```powershell

```# Monitor memory usage over time

docker stats --no-stream

**3. Check sensor name spelling**:

```python# Restart leaking containers

from rapidfuzz import fuzzdocker-compose -f docker-compose.bldg1.yml restart <service>


score = fuzz.ratio("temp sensor 501", "Air_Temperature_Sensor_5.01")# Check for connection leaks in custom code

print(score)  # Should be >80# Always close database connections:

```cursor.close()

conn.close()

**4. Use different analysis type** (some require less data):```

```python

# summary_statistics requires ≥1 data point---

# trend_analysis requires ≥10 data points

# forecast requires ≥50 data points## Development Issues

```

### Code Changes Not Reflecting

---

```powershell

### Issue 2: Chart Generation Fails# For action server (live reload enabled)

docker-compose -f docker-compose.bldg1.yml restart actions

**Symptoms**:

- Analytics completes but no chart URL# For frontend (should auto-reload)

- Artifacts directory emptydocker-compose -f docker-compose.bldg1.yml restart frontend


**Solutions**:# Force rebuild if needed

docker-compose -f docker-compose.bldg1.yml up --build <service>

**1. Check shared_data volume mount**:```

```powershell

docker inspect microservices | Select-String "Mounts" -Context 5### Python Import Errors

```

```powershell

**2. Verify artifacts directory exists**:# Check installed packages

```powershelldocker-compose -f docker-compose.bldg1.yml exec actions pip list

docker exec microservices mkdir -p /app/shared_data/artifacts/test_user

```# Install missing packages

docker-compose -f docker-compose.bldg1.yml exec actions pip install <package>

**3. Test matplotlib**:

```powershell# Or add to requirements.txt and rebuild

docker exec microservices python -c "docker-compose -f docker-compose.bldg1.yml up --build actions

import matplotlib

```

matplotlib.use('Agg')

import matplotlib.pyplot as plt### Training Fails

plt.plot([1,2,3], [4,5,6])

plt.savefig('/app/shared_data/artifacts/test.png')

```powershell

print('Chart saved')# Validate data

"docker-compose -f docker-compose.bldg1.yml exec rasa rasa data validate

```

# Check for duplicate stories

**4. Check HTTP server can serve artifacts**:# Check for conflicting intents

```powershell# Review domain.yml for syntax errors

curl http://localhost:8080/artifacts/test_user/

```# Train with debug output

docker-compose -f docker-compose.bldg1.yml exec rasa rasa train --debug

---```


### Issue 3: Analytics Timeout---


**Symptoms**:## FAQ

- Analytics request times out after 60 seconds

- No response received### Q: How do I switch between buildings?


**Solutions**:```powershell

# Stop current building

**1. Reduce data volume**:docker-compose -f docker-compose.bldg1.yml down

```python

# Use aggregated data for long time ranges# Start different building

data = db.get_hourly_aggregates(sensor_name, start_time, end_time)docker-compose -f docker-compose.bldg2.yml up -d

# Instead of raw minute-level data

```# Or use specific services

docker-compose -f docker-compose.bldg3.yml up -d rasa actions frontend

**2. Increase timeout**:```

```python

response = requests.post(### Q: How do I reset everything?

    analytics_url,

    json=payload,```powershell

    timeout=120  # Increase from 60# Stop all containers

)docker-compose down

```docker-compose -f docker-compose.bldg1.yml down

docker-compose -f docker-compose.bldg2.yml down

**3. Use faster analysis types**:docker-compose -f docker-compose.bldg3.yml down

```python

# Fast: summary_statistics, histogram (< 1 second)# Remove volumes (WARNING: deletes all data)

# Medium: trend_analysis, correlation (2-5 seconds)docker-compose down -v

# Slow: forecast, clustering (10-30 seconds)

```# Remove all OntoBot images

docker images | grep ontobot | awk '{print $3}' | xargs docker rmi

**4. Check analytics service resources**:

```powershell# Clean Docker system

docker stats microservicesdocker system prune -a -f --volumes

```

# CPU should be <80%, Memory <2GB

```### Q: How do I backup my data?


---```powershell

# MySQL

## Building-Specific Issuesdocker-compose -f docker-compose.bldg1.yml exec mysqlserver mysqldump -u root -ppassword telemetry > backup.sql


### Building 1 (MySQL) Issues# PostgreSQL/TimescaleDB

docker-compose -f docker-compose.bldg2.yml exec timescale pg_dump -U postgres telemetry_bldg2 > backup.sql

**Issue: Sensor UUID Not Mapped**

# Cassandra

**Symptoms**:docker-compose -f docker-compose.bldg3.yml exec cassandra nodetool snapshot telemetry_bldg3

- Query returns UUID instead of human-readable name

```

- Artifacts show: `a1b2c3d4-e5f6-7890...`

### Q: How do I restore data?

**Solutions**:

```powershell

**1. Check sensor mappings exist**:# MySQL

```powershelldocker-compose -f docker-compose.bldg1.yml exec -T mysqlserver mysql -u root -ppassword telemetry < backup.sql

docker exec rasa-action-server-bldg1 cat /app/actions/sensor_mappings.txt | Select-String "a1b2c3d4"

```# PostgreSQL/TimescaleDB

docker-compose -f docker-compose.bldg2.yml exec -T timescale psql -U postgres telemetry_bldg2 < backup.sql

**2. Regenerate mappings**:

```powershell# Cassandra

docker exec rasa-action-server-bldg1 python /app/actions/update_sensor_mappings.py# 1. Stop Cassandra

```# 2. Copy snapshot files to data directory

# 3. Start Cassandra

**3. Verify UUID→Name mapping in action**:# 4. Run: nodetool refresh telemetry_bldg3 sensor_data

```python
```

# actions/actions.py

sensor_mappings = {### Q: How do I update Rasa or other services?

    "a1b2c3d4-e5f6-7890-abcd-ef1234567890": "Air_Temperature_Sensor_5.01",

    ...```yaml

}# Update image version in docker-compose.yml

services:

sensor_name = sensor_mappings.get(uuid, uuid)  # Fallback to UUID  rasa:

```    image: rasa/rasa:3.6.12-full  # Change version here


---# Then rebuild

docker-compose -f docker-compose.bldg1.yml up --build rasa

### Building 2 (TimescaleDB) Issues

```


**Issue: Hypertable Not Created**### Q: How do I add a new sensor?


**Symptoms**:```sql

- Queries are slow-- MySQL (Building 1)

- Missing timescaledb-specific featuresINSERT INTO sensors (uuid, name, zone_id, sensor_type, unit, brick_class)

VALUES ('new-uuid', 'New Sensor', '5.25', 'Temperature', '°C', 'brick:Temperature_Sensor');

**Solutions**:

-- PostgreSQL/TimescaleDB (Building 2)

**1. Check if table is hypertable**:-- Just insert readings; sensor metadata can be in separate table or JSON

```sql

SELECT * FROM timescaledb_information.hypertables-- Cassandra (Building 3)

WHERE hypertable_name = 'sensor_data';-- Insert readings directly; no separate sensor table needed

```INSERT INTO sensor_data (sensor_uuid, timestamp, value, unit, sensor_type)

VALUES (uuid(), toTimestamp(now()), 22.5, '°C', 'Temperature');

**2. Convert to hypertable**:```

```sql

SELECT create_hypertable('sensor_data', 'timestamp', if_not_exists => TRUE);### Q: How do I monitor system health?

```

```powershell

**3. Verify chunks are created**:# All services status

```sqldocker-compose -f docker-compose.bldg1.yml ps

SELECT * FROM timescaledb_information.chunks

WHERE hypertable_name = 'sensor_data'# Health checks

ORDER BY range_start DESCcurl http://localhost:5005/version        # Rasa

LIMIT 10;curl http://localhost:5055/health         # Actions

```curl http://localhost:8080/health         # File Server

curl http://localhost:6001/health         # Analytics

---curl http://localhost:6009/health         # Decider


### Building 3 (Cassandra) Issues# Database connectivity

# MySQL

**Issue: Partition Key Error**docker-compose -f docker-compose.bldg1.yml exec mysqlserver mysql -u root -ppassword -e "SELECT 1"


**Symptoms**:# TimescaleDB

- Query returns: "Cannot execute this query as it might involve data filtering"docker-compose -f docker-compose.bldg2.yml exec timescale pg_isready


**Solutions**:# Cassandra

docker-compose -f docker-compose.bldg3.yml exec cassandra nodetool status

**1. Always specify partition key**:```

```cql

-- Bad: Missing partition key### Q: How do I enable debug logging?

SELECT * FROM sensor_data

WHERE timestamp > '2025-10-31';```yaml

# In docker-compose.yml, add environment variables

-- Good: Includes partition keyservices:

SELECT * FROM sensor_data  rasa:

WHERE sensor_id = 'crac1_supply_temp'    environment:

  AND timestamp > '2025-10-31';      - LOG_LEVEL=DEBUG

```  

  actions:

**2. Avoid ALLOW FILTERING**:    environment:

```cql      - LOG_LEVEL=DEBUG

-- Slow and resource-intensive      - PYTHONUNBUFFERED=1

SELECT * FROM sensor_data

WHERE reading_value > 25.0# Or in code (actions.py)

ALLOW FILTERING;import logging

```logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

**3. Use secondary indexes carefully**:```

```cql

-- Only if low cardinality---

CREATE INDEX ON sensor_data (alarm_status);

```## Getting Help


---### Logs to Check


## Performance Problems

```powershell

# All services

### Issue 1: High Memory Usagedocker-compose -f docker-compose.bldg1.yml logs


**Symptoms**:# Specific service

- Docker uses >16GB RAMdocker-compose -f docker-compose.bldg1.yml logs rasa

- System becomes slowdocker-compose -f docker-compose.bldg1.yml logs actions

docker-compose -f docker-compose.bldg1.yml logs microservices

**Solutions**:

# Follow logs in real-time

**1. Check container memory usage**:docker-compose -f docker-compose.bldg1.yml logs -f

```powershell

docker stats --no-stream# Last 100 lines

```docker-compose -f docker-compose.bldg1.yml logs --tail=100

```

**2. Limit container memory**:

```yaml### Diagnostic Commands

# docker-compose.bldg1.yml

mysqlserver:```powershell

  mem_limit: 2g# Docker info

  memswap_limit: 2gdocker info

```docker version


**3. Reduce database buffer pools**:# Network inspection

```yamldocker network ls

# MySQLdocker network inspect ontobot_default

mysqlserver:

  command: --innodb_buffer_pool_size=1G# Volume inspection

docker volume ls

# TimescaleDBdocker volume inspect ontobot_mysql_data

timescaledb:

  command: postgres -c shared_buffers=1GB# Container inspection

docker inspect ontobot_rasa_1

# Cassandra

```

cassandra:

  environment:### Support Resources

    MAX_HEAP_SIZE: "4G"

```- **GitHub Issues**: [OntoBot Issues](https://github.com/suhasdevmane/OntoBot/issues)

- **Documentation**: [OntoBot GitHub Pages](https://suhasdevmane.github.io/)

**4. Stop unused services**:- **Rasa Community**: [forum.rasa.com](https://forum.rasa.com/)

```powershell- **Docker Documentation**: [docs.docker.com](https://docs.docker.com/)

# Stop optional services

docker stop nl2sparql ollama---

```

**Still having issues?** Create a GitHub issue with:

---1. Error message (full stack trace)

2. Docker logs (`docker-compose logs`)

### Issue 2: Slow Query Performance3. System info (`docker info`, OS version)

4. Steps to reproduce

**Symptoms**:5. Expected vs actual behavior

- Queries take >10 seconds
- Dashboard is unresponsive

**Solutions**:

**1. Add database indexes** (if missing):
```sql
-- MySQL
CREATE INDEX idx_sensor_ts ON ts_kv(key_name, ts);

-- TimescaleDB
CREATE INDEX idx_sensor_name_ts ON sensor_data(sensor_name, timestamp DESC);

-- Cassandra (careful with secondary indexes)
CREATE INDEX ON sensor_data (zone_id);
```

**2. Use query EXPLAIN**:
```sql
EXPLAIN ANALYZE
SELECT * FROM sensor_data
WHERE sensor_name = 'Zone_101_Temperature_Sensor'
  AND timestamp > NOW() - INTERVAL '24 hours';
```

**3. Optimize time ranges**:
```python
# Bad: Query 1 year of minute-level data
start_time = datetime.now() - timedelta(days=365)

# Good: Query 24 hours or use aggregates
start_time = datetime.now() - timedelta(hours=24)
```

**4. Cache frequently accessed data**:
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_sensor_data(sensor_name, start_ts, end_ts):
    # Cached for repeated queries
    return db.query(sensor_name, start_ts, end_ts)
```

---

### Issue 3: High CPU Usage

**Symptoms**:
- Docker uses >80% CPU
- Fans running constantly

**Solutions**:

**1. Identify CPU-intensive container**:
```powershell
docker stats --no-stream | Sort-Object -Property CPU -Descending
```

**2. Limit CPU usage**:
```yaml
# docker-compose.bldg1.yml
rasa-bldg1:
  cpus: "2.0"  # Limit to 2 CPU cores
```

**3. Reduce Rasa NLU pipeline complexity**:
```yaml
# config.yml - Use faster pipeline
pipeline:
  - name: WhitespaceTokenizer
  - name: CountVectorsFeaturizer
  - name: DIETClassifier
    epochs: 50  # Reduce from 100
```

**4. Disable unnecessary services**:
```yaml
# Comment out in docker-compose
# nl2sparql:
#   ...
```

---

## Development Issues

### Issue 1: Code Changes Not Reflected

**Symptoms**:
- Modified action code doesn't take effect
- Old behavior persists

**Solutions**:

**1. Rebuild action server image**:
```powershell
docker compose -f docker-compose.bldg1.yml build rasa-action-server-bldg1
docker compose -f docker-compose.bldg1.yml up -d rasa-action-server-bldg1
```

**2. Check volume mounts** (for hot reload):
```yaml
# docker-compose.bldg1.yml
rasa-action-server-bldg1:
  volumes:
    - ./rasa-bldg1/actions:/app/actions  # Hot reload
```

**3. Restart service**:
```powershell
docker compose -f docker-compose.bldg1.yml restart rasa-action-server-bldg1
```

**4. Clear Python cache**:
```powershell
docker exec rasa-action-server-bldg1 find /app -name "*.pyc" -delete
docker exec rasa-action-server-bldg1 find /app -name "__pycache__" -type d -exec rm -r {} +
```

---

### Issue 2: Model Training Fails

**Symptoms**:
- `rasa train` exits with errors
- No model file generated

**Solutions**:

**1. Validate training data**:
```powershell
docker compose -f docker-compose.bldg1.yml run --rm rasa-bldg1 data validate
```

**2. Check for YAML syntax errors**:
```powershell
# Validate YAML
docker compose -f docker-compose.bldg1.yml run --rm rasa-bldg1 data validate --max-history 5
```

**3. Train with verbose output**:
```powershell
docker compose -f docker-compose.bldg1.yml run --rm rasa-train --debug
```

**4. Increase training resources**:
```yaml
# docker-compose.rasatrain.yml
rasa-train:
  mem_limit: 8g
  environment:
    - TF_FORCE_GPU_ALLOW_GROWTH=true
```

---

### Issue 3: Hot Reload Not Working

**Symptoms**:
- Volume-mounted code changes don't take effect
- Need to restart container manually

**Solutions**:

**1. Verify volume mount syntax**:
```yaml
volumes:
  - ./rasa-bldg1/actions:/app/actions  # Relative path
  # NOT: - rasa-bldg1/actions:/app/actions (missing ./)
```

**2. Use absolute paths on Windows**:
```yaml
volumes:
  - C:/Users/user/OntoBot/rasa-bldg1/actions:/app/actions
```

**3. Enable file watching** (if supported):
```yaml
rasa-action-server-bldg1:
  command: rasa run actions --auto-reload
```

**4. Check file permissions**:
```powershell
# Ensure files are writable
icacls "C:\Users\user\OntoBot\rasa-bldg1\actions" /grant Everyone:F
```

---

## Network & Connectivity

### Issue 1: Services Can't Communicate

**Symptoms**:
- Action server can't reach database
- Error: "Name or service not known"

**Solutions**:

**1. Verify all services on same network**:
```yaml
# All services must use: networks: - rasa-network
services:
  mysqlserver:
    networks:
      - rasa-network
  rasa-action-server-bldg1:
    networks:
      - rasa-network
```

**2. Use Docker DNS names (not localhost)**:
```yaml
# Good: http://microservices:6000
# Bad: http://localhost:6001
environment:
  ANALYTICS_URL: http://microservices:6000/analytics/run
```

**3. Test DNS resolution**:
```powershell
docker exec rasa-action-server-bldg1 ping mysqlserver
docker exec rasa-action-server-bldg1 nslookup microservices
```

**4. Recreate network**:
```powershell
docker network rm rasa-network
docker network create rasa-network
docker compose -f docker-compose.bldg1.yml up -d
```

---

### Issue 2: Frontend Can't Reach Rasa

**Symptoms**:
- Browser console: "Failed to fetch"
- CORS errors

**Solutions**:

**1. Check Rasa is accessible from host**:
```powershell
curl http://localhost:5005/version
```

**2. Enable CORS in Rasa**:
```yaml
# rasa-bldg1/endpoints.yml
action_endpoint:
  url: http://rasa-action-server-bldg1:5055/webhook

cors:
  enabled: true
  origins: "*"
```

**3. Verify frontend environment variable**:
```yaml
# docker-compose.bldg1.yml
rasa-ui:
  environment:
    REACT_APP_RASA_URL: http://localhost:5005  # Use localhost, not service name
```

**4. Check browser DevTools Network tab**:
- Status: Should be 200
- Response: Should have JSON data
- CORS headers: `Access-Control-Allow-Origin: *`

---

## Frequently Asked Questions

### Q1: How do I switch between buildings?

**A**: Stop all building stacks, then start target building:

```powershell
# Stop all
docker compose -f docker-compose.bldg1.yml down
docker compose -f docker-compose.bldg2.yml down
docker compose -f docker-compose.bldg3.yml down

# Start Building 2
docker compose -f docker-compose.bldg2.yml up -d

# Wait 60 seconds for initialization
Start-Sleep -Seconds 60

# Verify
curl http://localhost:5005/version
```

**See**: [Multi-Building Support Guide](multi_building.md)

---

### Q2: Why does Cassandra take so long to start?

**A**: Cassandra initialization takes 30-90 seconds due to:
- JVM startup
- Cluster formation
- Schema validation
- Data recovery

**Wait for log message**: `"Starting listening for CQL clients"`

---

### Q3: How do I add a new sensor?

**A**: 

**1. Add sensor to database** (insert readings)

**2. Add to sensor_list.txt**:
```
# rasa-bldg1/actions/sensor_list.txt
New_Sensor_Name
```

**3. Add to Brick Schema TTL**:
```turtle
:New_Sensor a brick:Temperature_Sensor ;
    rdfs:label "New_Sensor_Name" .
```

**4. Update training data** (if needed):
```yaml
# rasa-bldg1/data/nlu.yml
- intent: query_sensor_data
  examples: |
    - show me new sensor data
```

**5. Retrain model**:
```powershell
docker compose -f docker-compose.bldg1.yml run --rm rasa-train
docker compose -f docker-compose.bldg1.yml restart rasa-bldg1
```

---

### Q4: Can I run multiple buildings simultaneously?

**A**: **No** - Port conflicts will occur. Rasa (5005), Action Server (5055), and shared services use fixed ports.

**Alternative**: Use different host machines or change ports in compose files.

---

### Q5: How do I backup my data?

**A**:

**MySQL**:
```powershell
docker exec mysqlserver mysqldump -u rasa_user -p telemetry > backup.sql
```

**TimescaleDB**:
```powershell
docker exec timescaledb pg_dump -U postgres building2 > backup.sql
```

**Cassandra**:
```powershell
docker exec cassandra nodetool snapshot building3
docker exec cassandra tar -czf backup.tar.gz /var/lib/cassandra/data
```

**Docker Volumes**:
```powershell
docker run --rm -v mysql_data:/data -v C:\backup:/backup ubuntu tar czf /backup/mysql_backup.tar.gz /data
```

---

### Q6: How do I restore from backup?

**A**:

**MySQL**:
```powershell
docker exec -i mysqlserver mysql -u rasa_user -p telemetry < backup.sql
```

**TimescaleDB**:
```powershell
docker exec -i timescaledb psql -U postgres -d building2 < backup.sql
```

**Cassandra**:
```powershell
docker exec cassandra nodetool restore
```

---

### Q7: What are the minimum system requirements?

**A**:

**Minimum**:
- CPU: 4 cores
- RAM: 12 GB
- Disk: 50 GB
- OS: Windows 10/11, Ubuntu 20.04+, macOS 11+

**Recommended**:
- CPU: 8 cores
- RAM: 24 GB
- Disk: 100 GB SSD
- OS: Windows 11, Ubuntu 22.04, macOS 12+

---

### Q8: How do I enable NL2SPARQL and Ollama?

**A**:

```powershell
# Start with extras overlay
docker compose -f docker-compose.bldg1.yml -f docker-compose.extras.yml up -d

# Verify
curl http://localhost:6005/health  # NL2SPARQL
curl http://localhost:11434/api/tags  # Ollama
```

**Note**: Requires additional 8GB RAM and 10GB disk space.

---

### Q9: Can I use a different database?

**A**: Yes, implement a new database connector:

**1. Create connector** (`rasa-bldgX/actions/mongodb_connector.py`):
```python
class MongoDBConnector:
    def get_sensor_data(self, sensor_name, start_time, end_time):
        # Your MongoDB query logic
        pass
```

**2. Update factory** (`db_factory.py`):
```python
elif db_type == "mongodb":
    return MongoDBConnector(...)
```

**3. Set environment**:
```yaml
environment:
  DB_TYPE: mongodb
  MONGO_HOST: mongodb
  MONGO_PORT: 27017
```

---

### Q10: How do I contribute to OntoBot?

**A**:

1. Fork the repository
2. Create feature branch: `git checkout -b feature/new-feature`
3. Make changes and test thoroughly
4. Commit: `git commit -m "Add new feature"`
5. Push: `git push origin feature/new-feature`
6. Create Pull Request on GitHub

**See**: Project README for contribution guidelines

---

## Related Documentation

- **[Quick Start Guide](quickstart.md)**: 5-minute setup
- **[Multi-Building Support](multi_building.md)**: Switching buildings
- **[Database Integration](database_integration.md)**: Database troubleshooting
- **[Backend Services](backend_services.md)**: Service architecture

---

**Troubleshooting & FAQ** - Solve common OntoBot issues and find answers fast. 🔧❓✅
