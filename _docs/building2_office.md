---
title: Building 2 - Synthetic Office Building
layout: post
category: docs
permalink: /docs/building2_office/
---

# Building 2 - Synthetic Office Building

**Commercial workspace with 329 sensors optimized for HVAC research and thermal comfort studies using TimescaleDB.**

**Rasa Conversational AI Stack for Building 2**

---

## Overview

Building 2 is a synthetic commercial office building designed for HVAC optimization and thermal comfort research. It features TimescaleDB for advanced time-series analytics and comprehensive HVAC system monitoring.

Building 2 represents a modern commercial office building designed for HVAC optimization, energy efficiency research, and occupant thermal comfort studies. With 329 sensors monitoring HVAC systems, thermal zones, and environmental conditions, this testbed provides comprehensive insights into building automation and energy management.

### Key Specifications

### Key Specifications

 | Property | Details | 

 | Property | Value | | ---------- | --------- | 

 | ---------- | ------- | | **Building Type** | Synthetic Commercial Office | 

 | **Building Type** | Synthetic Commercial Office | | **Purpose** | HVAC Optimization & Thermal Comfort Research | 

 | **Primary Focus** | HVAC Optimization & Thermal Comfort | | **Sensor Coverage** | 329 sensors across multiple zones | 

 | **Total Sensors** | 329 distributed across 50 thermal zones | | **Focus Area** | HVAC Systems & Thermal Comfort | 

 | **Database** | TimescaleDB (PostgreSQL 15 + extension) | | **Database** | TimescaleDB (PostgreSQL extension, port 5433) | 

 | **Port** | 5433 (host), 5432 (container) | | **Knowledge Graph** | Brick Schema 1.3 via Jena Fuseki (port 3030) | 

 | **Knowledge Graph** | Brick Schema 1.3 via Jena Fuseki | | **Compose File** | `docker-compose.bldg2.yml` | 

 | **Compose File** | `docker-compose.bldg2.yml` | | **Technology Stack** | Rasa 3.6.12, Python 3.10, Docker, TimescaleDB 2.11 | 

 | **Tech Stack** | Rasa 3.6.12, Python 3.10, Docker, TimescaleDB 2.11 | 

 | **Dataset** | `bldg2/trial/dataset/*.ttl` | ## HVAC System Architecture


---### Equipment Coverage


## Sensor Infrastructure**Air Handling Units (AHUs):**

- **15 AHUs** serving different building zones

### Total Sensor Breakdown- Supply/Return air temperature sensors

- Airflow rate monitoring

Building 2 deploys **329 sensors** across **5 major categories**:- Fan speed control feedback

- Filter status indicators

1. **HVAC Equipment** (120 sensors)

   - Air Handling Units (AHUs)**Zone-Level Monitoring:**

   - Chillers and boilers- **50 thermal zones** with individual control

   - Pumps and fans- Zone temperature setpoints

   - Dampers and valves- Occupancy sensors

- VAV box position sensors

2. **Thermal Zones** (150 sensors)- Damper positions

   - Zone temperature sensors

   - Occupancy sensors**Central Plant:**

   - CO₂ sensors- **3 Chillers** for cooling

   - VAV box positions- **2 Boilers** for heating

- Supply/Return water temperatures

3. **Central Plant** (30 sensors)- Flow rates & pressures

   - Chilled water temperatures- Energy consumption meters

   - Hot water temperatures

   - Flow rates### Sensor Distribution (329 Total)

   - Pressures

 | System | Sensors | Measurements | 

4. **Environmental Monitoring** (24 sensors)|--------|---------|--------------|

   - Outdoor air temperature| **AHUs** | 75 | Supply/Return temps, airflow, fan speed, filters |

   - Humidity| **Zones** | 150 | Temperature, setpoint, occupancy, VAV position |

   - Wind speed| **Chillers** | 36 | Temp, flow, pressure, power, COP |

   - Solar radiation| **Boilers** | 24 | Temp, flow, pressure, power, efficiency |

 | **Other** | 44 | OA temp, humidity, outdoor air dampers | 

5. **Energy Metering** (5 sensors)

   - Whole-building electricity## TimescaleDB Integration

   - HVAC electricity

   - Lighting electricity### Why TimescaleDB?

   - Gas consumption

   - Renewable generationTimescaleDB is a PostgreSQL extension optimized for time-series data, perfect for HVAC monitoring:


---**Benefits:**

- ✅ **Automatic Partitioning** - Time-based chunks for better performance

## HVAC System Architecture- ✅ **Compression** - Reduces storage by 90%+

- ✅ **Continuous Aggregates** - Pre-computed rollups

### Air Handling Units (15 AHUs)- ✅ **Retention Policies** - Automatic old data deletion

- ✅ **PostgreSQL Compatibility** - All PostgreSQL features available

Each AHU monitors:- ✅ **Time-Series Functions** - time_bucket, first, last, interpolate


 | Sensor Type | Measurement | Range | Update Frequency | ### Database Configuration

 | ------------- | ------------- | ------- | ------------------ | 

 | Supply Air Temperature | Temperature after conditioning | 10-25°C | 1 minute | ```yaml

 | Return Air Temperature | Temperature from zones | 18-28°C | 1 minute | # docker-compose.bldg2.yml

 | Mixed Air Temperature | Fresh + return air mix | 12-26°C | 1 minute | timescale:

 | Supply Airflow Rate | CFM delivered to zones | 0-15,000 CFM | 1 minute | image: timescale/timescaledb:2.11.0-pg15

 | Fan Speed | VFD percentage | 0-100% | 1 minute | ports:

 | Filter Status | Differential pressure | 0-2.5 inWC | 5 minutes | - "5433:5432"

 | Cooling Coil Valve | Position 0-100% | 0-100% | 1 minute | environment:

 | Heating Coil Valve | Position 0-100% | 0-100% | 1 minute | POSTGRES_DB: telemetry_bldg2

    POSTGRES_USER: postgres

**Total AHU Sensors**: 15 AHUs × 8 sensors = **120 sensors**    POSTGRES_PASSWORD: postgres

    TIMESCALEDB_TELEMETRY: off

**Example AHU Sensor Names**:  volumes:

```    - timescale_data:/var/lib/postgresql/data

AHU_1_Supply_Air_Temperature_Sensor

```

AHU_1_Return_Air_Temperature_Sensor

AHU_1_Mixed_Air_Temperature_Sensor### Hypertable Schema

AHU_1_Supply_Airflow_Rate_Sensor

AHU_1_Fan_Speed_Sensor

```sql

AHU_1_Filter_Status_Sensor-- Create database

AHU_1_Cooling_Coil_Valve_Position_SensorCREATE DATABASE telemetry_bldg2;

AHU_1_Heating_Coil_Valve_Position_Sensor\c telemetry_bldg2

```

-- Enable TimescaleDB extension

---CREATE EXTENSION IF NOT EXISTS timescaledb;


### Thermal Zones (50 zones)-- Create sensor readings table

CREATE TABLE sensor_readings (

Each zone has **3 sensors**:    time TIMESTAMPTZ NOT NULL,

    sensor_id TEXT NOT NULL,

 | Sensor Type | Purpose | Range | Update Frequency | sensor_type TEXT NOT NULL,

 | ------------- | --------- | ------- | ------------------ | zone_id TEXT,

 | Zone Temperature | Current thermal state | 18-28°C | 1 minute | equipment_id TEXT,

 | Occupancy | People present | 0/1 or count | 5 minutes | value DOUBLE PRECISION NOT NULL,

 | CO₂ Level | Ventilation demand indicator | 400-2000 ppm | 5 minutes | unit TEXT,

    quality_flag INTEGER DEFAULT 0

**Total Zone Sensors**: 50 zones × 3 sensors = **150 sensors**);


**Example Zone Sensor Names**:-- Convert to hypertable (automatic time-based partitioning)

```SELECT create_hypertable('sensor_readings', 'time');

Zone_101_Temperature_Sensor

Zone_101_Occupancy_Sensor-- Create indexes

Zone_101_CO2_Level_SensorCREATE INDEX idx_sensor_id_time ON sensor_readings (sensor_id, time DESC);

Zone_201_Temperature_SensorCREATE INDEX idx_zone_time ON sensor_readings (zone_id, time DESC);

Zone_201_Occupancy_SensorCREATE INDEX idx_equipment_time ON sensor_readings (equipment_id, time DESC);

Zone_201_CO2_Level_SensorCREATE INDEX idx_type_time ON sensor_readings (sensor_type, time DESC);

```

-- Enable compression (90%+ space savings)

---ALTER TABLE sensor_readings SET (

    timescaledb.compress,

### Central Plant Equipment    timescaledb.compress_segmentby = 'sensor_id, sensor_type',

    timescaledb.compress_orderby = 'time DESC'

**3 Chillers**:);

- Chilled water supply temperature (6-12°C)

- Chilled water return temperature (10-16°C)-- Add compression policy (compress data older than 7 days)

- Chilled water flow rate (0-500 GPM)SELECT add_compression_policy('sensor_readings', INTERVAL '7 days');

- Power consumption (kW)

- **Total**: 3 chillers × 4 sensors = 12 sensors-- Add retention policy (drop data older than 1 year)

SELECT add_retention_policy('sensor_readings', INTERVAL '1 year');

**2 Boilers**:```

- Hot water supply temperature (60-82°C)

- Hot water return temperature (50-70°C)### Continuous Aggregates (Rollups)

- Hot water flow rate (0-300 GPM)

- Gas flow rate (CFH)

```sql

- **Total**: 2 boilers × 4 sensors = 8 sensors-- Hourly averages (pre-computed for fast queries)

CREATE MATERIALIZED VIEW sensor_readings_hourly

**Pumps**:WITH (timescaledb.continuous) AS

- Chilled water pumps (3): speed, powerSELECT 

- Hot water pumps (2): speed, power    time_bucket('1 hour', time) AS bucket,

- **Total**: 5 pumps × 2 sensors = 10 sensors    sensor_id,

    sensor_type,

**Total Central Plant Sensors**: 12 + 8 + 10 = **30 sensors**    zone_id,

    AVG(value) AS avg_value,

---    MIN(value) AS min_value,

    MAX(value) AS max_value,

### Environmental Sensors    COUNT(*) AS reading_count

FROM sensor_readings

**Outdoor Weather Station** (4 sensors):GROUP BY bucket, sensor_id, sensor_type, zone_id;

- Outdoor air temperature (-20 to 40°C)

- Outdoor humidity (0-100% RH)-- Refresh policy (update every hour)

- Wind speed (0-50 mph)SELECT add_continuous_aggregate_policy('sensor_readings_hourly',

- Solar radiation (0-1200 W/m²)    start_offset => INTERVAL '3 hours',

    end_offset => INTERVAL '1 hour',

**Perimeter Sensors** (20 locations × 1 sensor):    schedule_interval => INTERVAL '1 hour');

- Window blind positions

- Daylight sensors-- Daily aggregates

CREATE MATERIALIZED VIEW sensor_readings_daily

**Total Environmental Sensors**: 4 + 20 = **24 sensors**WITH (timescaledb.continuous) AS

SELECT 

---    time_bucket('1 day', time) AS bucket,

    sensor_id,

### Energy Metering    sensor_type,

    zone_id,

**Whole-Building Meters** (5 sensors):    AVG(value) AS avg_value,

```    MIN(value) AS min_value,

Whole_Building_Electricity_Meter       (kW)    MAX(value) AS max_value,

HVAC_Electricity_Meter                 (kW)    STDDEV(value) AS stddev_value

Lighting_Electricity_Meter             (kW)FROM sensor_readings

Gas_Consumption_Meter                  (CFH)GROUP BY bucket, sensor_id, sensor_type, zone_id;

Solar_Generation_Meter                 (kW)

```

```

### Time-Series Queries

**Update Frequency**: 15 minutes (aligned with utility billing intervals)

**Recent Zone Temperature:**

---```sql

SELECT 

## TimescaleDB Schema    time,

    sensor_id,

### Database Configuration    zone_id,

    value AS temperature

Building 2 uses **TimescaleDB**, a PostgreSQL extension optimized for time-series data.FROM sensor_readings

WHERE sensor_type = 'ZoneTemp'

**Connection Details**:    AND zone_id = 'Zone-01'

```yaml    AND time > NOW() - INTERVAL '1 hour'

Host: timescaledb (internal) / localhost (host)ORDER BY time DESC;

Port: 5432 (internal) / 5433 (host)

```

Database: building2

Username: postgres**Hourly Average with time_bucket:**

Password: postgres (development only!)

```sql

```SELECT 

    time_bucket('1 hour', time) AS hour,

---    zone_id,

    AVG(value) AS avg_temp,

### Hypertable Structure    MIN(value) AS min_temp,

    MAX(value) AS max_temp

TimescaleDB converts regular PostgreSQL tables into **hypertables** with automatic time-based partitioning.FROM sensor_readings

WHERE sensor_type = 'ZoneTemp'

**Main Table**: `sensor_data`    AND time > NOW() - INTERVAL '24 hours'

GROUP BY hour, zone_id

```sql
ORDER BY hour DESC, zone_id;

CREATE TABLE sensor_data (```

    id SERIAL,

    sensor_id VARCHAR(100) NOT NULL,**HVAC Efficiency Analysis:**

    sensor_name VARCHAR(255) NOT NULL,```sql

    sensor_type VARCHAR(100) NOT NULL,-- Calculate COP (Coefficient of Performance) for chillers

    reading_value NUMERIC(10,2) NOT NULL,WITH chiller_data AS (

    reading_unit VARCHAR(20),    SELECT 

    timestamp TIMESTAMP NOT NULL,        time_bucket('15 minutes', time) AS bucket,

    zone_id VARCHAR(50),        equipment_id,

    equipment_id VARCHAR(50),        AVG(CASE WHEN sensor_type = 'CoolingOutput' THEN value END) AS cooling_kw,

    PRIMARY KEY (id, timestamp)        AVG(CASE WHEN sensor_type = 'PowerInput' THEN value END) AS power_kw

);    FROM sensor_readings

    WHERE equipment_id LIKE 'Chiller-%'

-- Convert to hypertable (partitioned by time)        AND time > NOW() - INTERVAL '24 hours'

SELECT create_hypertable('sensor_data', 'timestamp', chunk_time_interval => INTERVAL '1 day');    GROUP BY bucket, equipment_id

)

-- Create indexes for fast queriesSELECT 

CREATE INDEX idx_sensor_name ON sensor_data(sensor_name, timestamp DESC);    bucket,

CREATE INDEX idx_sensor_type ON sensor_data(sensor_type, timestamp DESC);    equipment_id,

CREATE INDEX idx_zone_id ON sensor_data(zone_id, timestamp DESC);    cooling_kw,

CREATE INDEX idx_equipment_id ON sensor_data(equipment_id, timestamp DESC);    power_kw,

```    CASE 

        WHEN power_kw > 0 THEN cooling_kw / power_kw 

**Key Features**:        ELSE NULL 

- **Automatic Chunking**: Data partitioned into 1-day chunks    END AS cop

- **Compression**: Old chunks compressed automatically (10:1 ratio)FROM chiller_data

- **Continuous Aggregates**: Pre-computed hourly/daily summariesWHERE cooling_kw IS NOT NULL AND power_kw IS NOT NULL

- **Retention Policies**: Auto-delete data older than 2 yearsORDER BY bucket DESC;

```

---

**Thermal Comfort Analysis:**

### Sample Data

```sql

-- Find zones outside comfort range

**Temperature Sensor Data**:SELECT 

```sql    zone_id,

INSERT INTO sensor_data (sensor_id, sensor_name, sensor_type, reading_value, reading_unit, timestamp, zone_id)    AVG(value) AS avg_temp,

VALUES    STDDEV(value) AS temp_variance,

('temp_zone101', 'Zone_101_Temperature_Sensor', 'temperature', 22.5, 'C', '2025-10-31 10:00:00', 'Zone_101'),    COUNT(*) AS reading_count,

('temp_zone101', 'Zone_101_Temperature_Sensor', 'temperature', 22.6, 'C', '2025-10-31 10:01:00', 'Zone_101'),    COUNT(*) FILTER (WHERE value < 20 OR value > 24) AS out_of_comfort

('temp_zone101', 'Zone_101_Temperature_Sensor', 'temperature', 22.4, 'C', '2025-10-31 10:02:00', 'Zone_101');FROM sensor_readings

```WHERE sensor_type = 'ZoneTemp'

    AND time > NOW() - INTERVAL '1 day'

**AHU Equipment Data**:GROUP BY zone_id

```sql
HAVING AVG(value) < 20 OR AVG(value) > 24

INSERT INTO sensor_data (sensor_id, sensor_name, sensor_type, reading_value, reading_unit, timestamp, equipment_id)ORDER BY out_of_comfort DESC;

VALUES

```

('ahu1_supply_temp', 'AHU_1_Supply_Air_Temperature_Sensor', 'temperature', 14.5, 'C', '2025-10-31 10:00:00', 'AHU_1'),

('ahu1_fan_speed', 'AHU_1_Fan_Speed_Sensor', 'percentage', 75.0, '%', '2025-10-31 10:00:00', 'AHU_1'),## HVAC Optimization Features

('ahu1_airflow', 'AHU_1_Supply_Airflow_Rate_Sensor', 'cfm', 12500, 'CFM', '2025-10-31 10:00:00', 'AHU_1');

```### Thermal Comfort Monitoring


---**Predicted Mean Vote (PMV) Calculation:**

- Air temperature

### Database Performance- Relative humidity

- Air velocity

**Storage Statistics** (1 year of data):- Metabolic rate (occupancy-based)

- Clothing insulation (seasonal)

 | Metric | Value | 

 | -------- | ------- | **Comfort Metrics:**

 | Raw Data Size | 28 GB | - PMV: -3 (cold) to +3 (hot), target: -0.5 to +0.5

 | Compressed Size | 3.2 GB | - PPD: Percentage of People Dissatisfied

 | Compression Ratio | 8.75:1 | - Operative temperature

 | Total Records | 172 million | - Thermal sensation

 | Daily Inserts | 470,000 | 

### Energy Efficiency Analytics

**Query Performance**:

**Performance Indicators:**

 | Query Type | Response Time | - **COP** (Coefficient of Performance) - Chillers

 | ------------ | --------------- | - **Boiler Efficiency** - Combustion efficiency %

 | Single sensor, 24 hours | 15-30 ms | - **AHU Energy Consumption** - kWh per CFM

 | All zones, 1 hour | 50-100 ms | - **Zone Temperature Variance** - Comfort stability

 | Aggregated hourly, 1 week | 80-150 ms | 

 | Complex analytics (multiple sensors) | 200-500 ms | **Optimization Strategies:**

- Optimal start/stop times

**Optimization Features**:- Supply air temperature reset

- Continuous aggregates for hourly/daily summaries- Static pressure reset

- Automatic compression after 7 days- Economizer operation

- Retention policy: 2 years- Demand-controlled ventilation

- Index on (sensor_name, timestamp DESC) for fast queries

### Predictive Maintenance

---

**Equipment Monitoring:**

## Brick Schema Knowledge Graph- Filter differential pressure trends

- Fan vibration analysis

### Ontology Structure- Bearing temperature monitoring

- Valve position feedback

Building 2's knowledge graph uses **Brick Schema 1.3** with 329 sensor entities.- Compressor runtime tracking


**Fuseki Endpoint**: `http://localhost:3030/trial/sparql`**Maintenance Alerts:**

- Filter replacement due (ΔP > threshold)

**Dataset Location**: `bldg2/trial/dataset/*.ttl`- Fan bearing wear detection

- Valve stuck detection

---- Refrigerant leak indicators


### Sample SPARQL Queries## Usage Examples


#### Query 1: Find All Zone Temperature Sensors### Zone Comfort Queries


```sparql
```

PREFIX brick: <https://brickschema.org/schema/Brick#>"What's the temperature in Zone 01?"

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>"Show me thermal comfort for all zones"

"Which zones are too hot?"

SELECT ?sensor ?zone"Display temperature trends for Zone 05 today"

WHERE {"Compare setpoint vs actual temperature"

  ?sensor rdf:type brick:Temperature_Sensor .```

  ?sensor brick:isPointOf ?zone .

  ?zone rdf:type brick:HVAC_Zone .### HVAC System Queries

}

ORDER BY ?zone

```

```"Show me AHU-1 performance"

"What's the supply air temperature from AHU-3?"

**Results**: 50 temperature sensors (one per zone)"Display chiller efficiency"

"Show all AHU fan speeds"

**Sample Output**:"What's the current cooling load?"

```

 | sensor | zone | 

 | --------------------------------- | ----------- | ### Energy & Efficiency

 | :Zone_101_Temperature_Sensor | :Zone_101 | 

 | :Zone_102_Temperature_Sensor | :Zone_102 | ```

 | :Zone_201_Temperature_Sensor | :Zone_201 | "Calculate building energy consumption today"

..."What's the COP of Chiller 2?"

```"Show me boiler efficiency trends"

"Compare energy use this week vs last week"

---"Display power consumption by system"

```

#### Query 2: Get All Sensors for a Specific AHU

### Maintenance & Alerts

```sparql

PREFIX brick: <https://brickschema.org/schema/Brick#>```

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>"Which filters need replacement?"

"Show equipment alarms"

SELECT ?sensor ?sensorType"Display maintenance due items"

WHERE {"What's the runtime on AHU-5?"

  ?sensor brick:isPointOf :AHU_1 ."Show me valve position feedback"

  ?sensor rdf:type ?sensorType .```

  FILTER(STRSTARTS(STR(?sensorType), "https://brickschema.org/schema/Brick#"))

}## pgAdmin Integration

ORDER BY ?sensorType

```Building 2 includes pgAdmin for web-based database management:


**Results**: 8 sensors for AHU_1

```yaml

# Pre-configured pgAdmin

**Sample Output**:pgadmin:

```  image: dpage/pgadmin4:latest

 | sensor | sensorType | ports:

 | --------------------------------------------- | ----------------------------- | - "5050:80"

 | :AHU_1_Cooling_Coil_Valve_Position_Sensor | brick:Valve_Position_Sensor | environment:

 | :AHU_1_Fan_Speed_Sensor | brick:Speed_Sensor | PGADMIN_DEFAULT_EMAIL: admin@admin.com

 | :AHU_1_Filter_Status_Sensor | brick:Filter_Status | PGADMIN_DEFAULT_PASSWORD: admin

 | :AHU_1_Supply_Air_Temperature_Sensor | brick:Temperature_Sensor | volumes:

...    - ./bldg2/servers.json:/pgadmin4/servers.json

```


---**Access:** http://localhost:5050 (admin@admin.com / admin)


#### Query 3: Find Zones Served by a Specific AHU**Pre-configured Connection:**

- Host: timescale

```sparql- Port: 5432

PREFIX brick: <https://brickschema.org/schema/Brick#>- Database: telemetry_bldg2

- Username: postgres

SELECT ?zone ?zoneName

WHERE {## Analytics Integration

  :AHU_1 brick:feeds ?zone .

  ?zone rdf:type brick:HVAC_Zone .### HVAC-Specific Analytics

  OPTIONAL { ?zone brick:hasName ?zoneName }

}**Thermal Analysis:**

ORDER BY ?zone- Zone temperature profiling

```- Setpoint tracking

- Comfort index calculation

**Results**: ~3-4 zones per AHU (15 AHUs serving 50 zones)- Thermal lag analysis


---**Equipment Performance:**

- COP/EER calculation

## Typo-Tolerant Query Examples- Runtime analysis

- Cycling frequency

Building 2's action server uses **RapidFuzz** (80% threshold) to handle natural language variations.- Load profiles


### Air Temperature Queries**Energy Analytics:**

- Baseline consumption

**User Inputs** (all resolve to same sensors):- Energy signatures

```- Degree-day normalization

"show me air temp in zone 101"        → Zone_101_Temperature_Sensor- Peak demand analysis

"air temprature zone101"              → Zone_101_Temperature_Sensor (typo: temprature)

"AIRTEMPERATURE  zone   101"          → Zone_101_Temperature_Sensor (spacing)### API Examples

"air_temperature_sensor_zone_101"     → Zone_101_Temperature_Sensor (underscores)

```python

import requests

**Matching Process**:

1. Normalize: "air temp" → "air temperature"# Get zone thermal comfort analysis

2. Fuzzy match against 329 sensor namesresponse = requests.post(

3. Filter by zone context ("zone 101" → Zone_101)    'http://localhost:6001/analytics/run',

4. Return exact sensor: `Zone_101_Temperature_Sensor`    json={

        'analysis_type': 'thermal_comfort',

---        'zone_id': 'Zone-01',

        'start_time': '2025-10-01T00:00:00Z',

### AHU Equipment Queries        'end_time': '2025-10-08T23:59:59Z',

        'comfort_range': {'min': 20, 'max': 24}

**User Inputs**:    }

```)

"ahu1 fan speed"                      → AHU_1_Fan_Speed_Sensor

"air handling unit 1 fan"             → AHU_1_Fan_Speed_Sensor# Calculate HVAC efficiency

"ahu 1 supply air temperature"        → AHU_1_Supply_Air_Temperature_Sensorresponse = requests.post(

"ahu1supplytempereture"               → AHU_1_Supply_Air_Temperature_Sensor (typos)    'http://localhost:6001/analytics/run',

```    json={

        'analysis_type': 'hvac_efficiency',

---        'equipment_id': 'Chiller-01',

        'metric': 'cop',

### Multi-Sensor Queries        'aggregation': '15min'

    }

**User Input**: `"compare temperatures in zones 101 102 and 103"`)

```

**Resolution**:

```## Development

Zone 101 → Zone_101_Temperature_Sensor (match: 100%)

Zone 102 → Zone_102_Temperature_Sensor (match: 100%)### Custom Actions

Zone 103 → Zone_103_Temperature_Sensor (match: 100%)

```python

# actions/actions.py

**Action Server** fetches data for all 3 sensors in parallel.import psycopg2

from psycopg2.extras import RealDictCursor

---

class ActionQueryZoneTemp(Action):

## Docker Compose Configuration    def name(self) -> Text:

        return "action_query_zone_temp"

### Building 2 Stack

    def run(self, dispatcher, tracker, domain):

**File**: `docker-compose.bldg2.yml`        zone = tracker.get_slot("zone_id")

        

```yaml        # Connect to TimescaleDB

services:        conn = psycopg2.connect(

  # TimescaleDB database            host='timescale',

  timescaledb:            database='telemetry_bldg2',

    image: timescale/timescaledb:latest-pg15            user='postgres',

    container_name: timescaledb            password='postgres'

    ports:        )

      - "5433:5432"        

    environment:        cursor = conn.cursor(cursor_factory=RealDictCursor)

      POSTGRES_DB: building2        query = """

      POSTGRES_USER: postgres            SELECT 

      POSTGRES_PASSWORD: postgres                time,

    volumes:                value AS temperature,

      - timescaledb_data:/var/lib/postgresql/data                unit

      - ./bldg2/init.sql:/docker-entrypoint-initdb.d/init.sql            FROM sensor_readings

    networks:            WHERE sensor_type = 'ZoneTemp'

      - rasa-network              AND zone_id = %s

            ORDER BY time DESC

  # Rasa action server            LIMIT 1

  rasa-action-server-bldg2:        """

    build:        cursor.execute(query, (zone,))

      context: ./rasa-bldg2        result = cursor.fetchone()

      dockerfile: Dockerfile        

    image: rasa-action-server-bldg2:latest        if result:

    container_name: rasa-action-server-bldg2            message = f"Temperature in {zone}: {result['temperature']:.1f}°C"

    ports:        else:

      - "5055:5055"            message = f"No temperature data for {zone}"

    environment:        

      DB_HOST: timescaledb        dispatcher.utter_message(text=message)

      DB_PORT: 5432        return []

      DB_NAME: building2

```

      DB_USER: postgres

      DB_PASSWORD: postgres### HVAC-Specific Intents

      FUSEKI_ENDPOINT: http://fuseki-db:3030/trial/sparql

      ANALYTICS_URL: http://microservices:6000/analytics/run

```yaml

      DECIDER_URL: http://decider-service:6009/decide# data/nlu.yml

      FILE_SERVER_URL: http://http_server:8080- intent: query_zone_temperature

    volumes:  examples: |

      - ./rasa-bldg2/actions:/app/actions    - what's the temperature in [Zone 01](zone_id)

      - ./rasa-ui/shared_data:/app/shared_data    - show me [Zone 05](zone_id) temp

    depends_on:    - temperature reading for [Zone 12](zone_id)

      - timescaledb    - how warm is [Zone 03](zone_id)

      - fuseki-db

      - microservices- intent: query_ahu_status

    networks:  examples: |

      - rasa-network    - show me [AHU-1](equipment_id) status

    - what's [AHU-3](equipment_id) supply air temp

  # Rasa core    - display [AHU-5](equipment_id) fan speed

  rasa-bldg2:    - [AHU-2](equipment_id) performance

    build:

      context: ./rasa-bldg2- intent: query_hvac_efficiency

      dockerfile: Dockerfile.rasa  examples: |

    image: rasa-bldg2:latest    - what's the COP of [Chiller 1](equipment_id)

    container_name: rasa-bldg2    - show [Chiller 2](equipment_id) efficiency

    ports:    - [Boiler 1](equipment_id) combustion efficiency

      - "5005:5005"    - calculate building energy use

    environment:```

      RASA_ACTION_ENDPOINT: http://rasa-action-server-bldg2:5055/webhook

    volumes:## Testing & Monitoring

      - ./rasa-bldg2/models:/app/models

      - ./rasa-bldg2/data:/app/data### TimescaleDB Health

      - ./rasa-bldg2/config.yml:/app/config.yml

    depends_on:```powershell

      - rasa-action-server-bldg2# Check TimescaleDB version

    networks:docker-compose -f docker-compose.bldg2.yml exec timescale psql -U postgres -d telemetry_bldg2 -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"

      - rasa-network

# Check hypertable stats

  # Fuseki knowledge graph (shared)docker-compose -f docker-compose.bldg2.yml exec timescale psql -U postgres -d telemetry_bldg2 -c "SELECT * FROM timescaledb_information.hypertables;"

  fuseki-db:

    image: secoresearch/fuseki# Check compression stats

    container_name: fuseki-dbdocker-compose -f docker-compose.bldg2.yml exec timescale psql -U postgres -d telemetry_bldg2 -c "SELECT * FROM timescaledb_information.compression_settings;"

    ports:```

      - "3030:3030"

    environment:### Query Performance

      ADMIN_PASSWORD: admin123

      JVM_ARGS: "-Xmx4g"```sql

    volumes:-- Analyze query plan

      - fuseki_data:/fusekiEXPLAIN ANALYZE

      - ./bldg2/trial/dataset:/fuseki-base/databases/trialSELECT time_bucket('1 hour', time), AVG(value)

    networks:FROM sensor_readings

      - rasa-networkWHERE time > NOW() - INTERVAL '24 hours'

GROUP BY 1;

  # Analytics microservices (shared)

  microservices:-- Check chunk size

    build: ./microservicesSELECT * FROM timescaledb_information.chunks;

    container_name: microservices

    ports:-- Monitor continuous aggregates

      - "6001:6000"SELECT * FROM timescaledb_information.continuous_aggregates;

    volumes:```

      - ./rasa-ui/shared_data:/app/shared_data

    networks:## Troubleshooting

      - rasa-network

### Common Issues

  # Decider service (shared)

  decider-service:**Problem: Slow queries**

    build: ./decider-service

```sql

    container_name: decider-service-- Ensure hypertable is created

    ports:SELECT * FROM timescaledb_information.hypertables;

      - "6009:6009"

    networks:-- Check if compression is enabled

      - rasa-networkSELECT * FROM timescaledb_information.compression_settings;


  # HTTP file server (shared)-- Reindex if needed

  http_server:REINDEX TABLE sensor_readings;

    image: python:3.10-slim

```

    container_name: http_server

    command: python -m http.server 8080**Problem: High disk usage**

    working_dir: /data

```sql

    ports:-- Check table sizes

      - "8080:8080"SELECT 

    volumes:    hypertable_name,

      - ./rasa-ui/shared_data:/data    pg_size_pretty(hypertable_size(hypertable_name::regclass)) AS total_size,

    networks:    pg_size_pretty(hypertable_size(hypertable_name::regclass, 'uncompressed')) AS uncompressed,

      - rasa-network    pg_size_pretty(hypertable_size(hypertable_name::regclass, 'compressed')) AS compressed

FROM timescaledb_information.hypertables;

  # React frontend (shared)

  rasa-ui:-- Manually compress chunks

    build: ./rasa-frontendSELECT compress_chunk(i) FROM show_chunks('sensor_readings') i;

    container_name: rasa-ui

    ports:-- Adjust retention policy

      - "3000:3000"SELECT remove_retention_policy('sensor_readings');

    environment:SELECT add_retention_policy('sensor_readings', INTERVAL '6 months');

      REACT_APP_RASA_URL: http://localhost:5005

```

    networks:

      - rasa-network## Related Documentation


volumes:- [Building 1 - ABACWS](/docs/building1_abacws/) - Real university testbed

  timescaledb_data:- [Building 3 - Data Center](/docs/building3_datacenter/) - Critical infrastructure

  fuseki_data:- [TimescaleDB Integration Guide](/docs/timescaledb_integration/) - Detailed database guide

- [HVAC Analytics Guide](/docs/hvac_analytics/) - Thermal comfort & efficiency

networks:- [Multi-Building Support](/docs/multi_building/) - Switching between buildings

  rasa-network:

    driver: bridge## Support & Resources

```

- **TimescaleDB Documentation**: [docs.timescale.com](https://docs.timescale.com/)

---- **HVAC Best Practices**: [ASHRAE Standards](https://www.ashrae.org/)

- **Thermal Comfort**: [ISO 7730](https://www.iso.org/standard/39155.html)

### Starting Building 2- **Building Automation**: [BACnet Standard](http://www.bacnet.org/)


**One-Command Startup**:---

```bash

docker compose -f docker-compose.bldg2.yml up -d**Building 2 (Office)** represents HVAC optimization with:

```- ✅ 329 sensors across AHUs, zones, chillers, boilers

- ✅ TimescaleDB time-series optimization

**Service Order**:- ✅ HVAC efficiency monitoring

1. TimescaleDB starts first (dependency for action server)- ✅ Thermal comfort analytics

2. Fuseki, microservices, decider, HTTP server start (parallel)- ✅ Energy optimization research

3. Action server waits for DB + Fuseki
4. Rasa core waits for action server
5. Frontend connects to Rasa

**Verify Services**:
```powershell
# Health checks
curl http://localhost:5433  # TimescaleDB (psql client required)
curl http://localhost:3030/$/ping  # Fuseki
curl http://localhost:5005/version  # Rasa
curl http://localhost:5055  # Action server
curl http://localhost:6001/health  # Analytics
curl http://localhost:6009/health  # Decider
curl http://localhost:8080  # HTTP server
curl http://localhost:3000  # Frontend
```

---

## Use Cases & Applications

### 1. HVAC Optimization

**Scenario**: Optimize AHU setpoints to minimize energy while maintaining comfort.

**Queries**:
```
"show me AHU 1 supply air temperature for the last 24 hours"
"compare fan speeds across all AHUs"
"find zones with temperatures outside 20-24°C"
"run optimization analysis on HVAC electricity consumption"
```

**Analytics**:
- Trend analysis on equipment efficiency
- Correlation between outdoor temp and HVAC load
- Forecasting energy demand
- What-if scenarios for setpoint changes

**Expected Outcome**: 15-25% energy savings through optimal scheduling and setpoints.

---

### 2. Thermal Comfort Studies

**Scenario**: Analyze occupant comfort across 50 zones.

**Queries**:
```
"show me temperature distribution across all zones"
"find zones with high occupancy and high CO2 levels"
"compare zone temperatures during occupied vs unoccupied hours"
"run clustering analysis on thermal zones"
```

**Analytics**:
- Zone temperature variance analysis
- Correlation between occupancy and temperature
- Identification of "hot spots" and "cold spots"
- Comfort classification (comfortable/warning/uncomfortable)

**Expected Outcome**: Identify zones needing HVAC balancing or additional controls.

---

### 3. Ventilation Effectiveness

**Scenario**: Ensure adequate fresh air supply based on occupancy.

**Queries**:
```
"show me CO2 levels in zone 201 for the last week"
"find zones where CO2 exceeded 1000 ppm"
"compare occupancy and CO2 levels in zone 101"
"run anomaly detection on CO2 sensors"
```

**Analytics**:
- CO₂ vs occupancy regression
- Ventilation rate optimization
- Anomaly detection for IAQ issues
- Predictive alerts for high CO₂ periods

**Expected Outcome**: Maintain CO₂ < 1000 ppm 95% of occupied hours.

---

### 4. Energy Management

**Scenario**: Track and reduce building energy consumption.

**Queries**:
```
"show me whole building electricity for the last month"
"compare HVAC electricity vs lighting electricity"
"find days with highest energy consumption"
"run forecast analysis on electricity demand"
```

**Analytics**:
- Energy baseline modeling
- Peak demand forecasting
- Anomaly detection for equipment faults
- Cost optimization with time-of-use rates

**Expected Outcome**: 10-20% reduction in energy costs through load shifting and fault detection.

---

## Performance Characteristics

### Query Response Times

**TimescaleDB Queries** (single sensor):

 | Time Range | Records | Response Time | 
 | ------------ | --------- | --------------- | 
 | 1 hour | 60 | 10-15 ms | 
 | 24 hours | 1,440 | 15-30 ms | 
 | 1 week | 10,080 | 50-100 ms | 
 | 1 month | 43,200 | 150-300 ms | 

**Multi-Sensor Queries** (10 sensors):

 | Time Range | Total Records | Response Time | 
 | ------------ | --------------- | --------------- | 
 | 1 hour | 600 | 30-50 ms | 
 | 24 hours | 14,400 | 80-150 ms | 
 | 1 week | 100,800 | 300-600 ms | 

**Analytics Processing**:

 | Analysis Type | Data Points | Processing Time | 
 | --------------- | ------------- | ----------------- | 
 | Summary statistics | 1,440 | <1 second | 
 | Trend analysis | 10,080 | 2-3 seconds | 
 | Anomaly detection | 43,200 | 5-8 seconds | 
 | Forecasting (ARIMA) | 10,080 | 10-15 seconds | 

---

### Resource Usage

**TimescaleDB Container**:
- CPU: 5-10% idle, 30-50% under load
- Memory: 2-4 GB (with 4 GB JVM heap)
- Disk I/O: 10-50 MB/s during inserts

**Action Server**:
- CPU: 2-5% idle, 15-30% during analytics
- Memory: 500 MB - 1 GB
- Concurrent requests: 10-20

**Total Stack**:
- CPU: 4 cores recommended
- Memory: 16 GB recommended (12 GB minimum)
- Disk: 50 GB for 2 years of data

---

## Troubleshooting

### Issue 1: TimescaleDB Connection Failed

**Symptoms**:
- Action server logs: `psycopg2.OperationalError: could not connect to server`
- Frontend queries fail silently

**Solutions**:
1. **Check TimescaleDB is running**:
   ```bash
   docker ps | grep timescaledb
   ```

2. **Verify port mapping**:
   ```bash
   docker port timescaledb
   # Should show: 5432/tcp -> 0.0.0.0:5433
   ```

3. **Test connection from host**:
   ```bash
   psql -h localhost -p 5433 -U postgres -d building2
   # Enter password: postgres
   ```

4. **Check action server environment**:
   ```bash
   docker exec rasa-action-server-bldg2 env | grep DB_
   # Should show: DB_HOST=timescaledb, DB_PORT=5432
   ```

---

### Issue 2: Slow Query Performance

**Symptoms**:
- Queries take >5 seconds for simple time ranges
- Dashboard feels sluggish

**Solutions**:
1. **Check index usage**:
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM sensor_data
   WHERE sensor_name = 'Zone_101_Temperature_Sensor'
   AND timestamp > NOW() - INTERVAL '24 hours';
   ```

2. **Rebuild indexes if needed**:
   ```sql
   REINDEX INDEX idx_sensor_name;
   ```

3. **Enable continuous aggregates**:
   ```sql
   CREATE MATERIALIZED VIEW sensor_data_hourly
   WITH (timescaledb.continuous) AS
   SELECT sensor_name,
          time_bucket('1 hour', timestamp) AS hour,
          AVG(reading_value) AS avg_value,
          MAX(reading_value) AS max_value,
          MIN(reading_value) AS min_value
   FROM sensor_data
   GROUP BY sensor_name, hour;
   ```

4. **Increase compression**:
   ```sql
   ALTER TABLE sensor_data SET (
     timescaledb.compress,
     timescaledb.compress_segmentby = 'sensor_name',
     timescaledb.compress_orderby = 'timestamp DESC'
   );

   SELECT add_compression_policy('sensor_data', INTERVAL '7 days');
   ```

---

### Issue 3: Sensor Name Mismatches

**Symptoms**:
- "No data found for sensor" despite data existing
- Typo-tolerant matching fails

**Solutions**:
1. **Verify sensor names in database**:
   ```sql
   SELECT DISTINCT sensor_name FROM sensor_data ORDER BY sensor_name;
   ```

2. **Check action server sensor list**:
   ```bash
   docker exec rasa-action-server-bldg2 cat /app/actions/sensor_list.txt
   ```

3. **Rebuild sensor lookup**:
   ```bash
   docker exec rasa-action-server-bldg2 python /app/actions/update_sensor_mappings.py
   ```

4. **Test fuzzy matching**:
   ```python
   from rapidfuzz import fuzz
   score = fuzz.ratio("zone101 temperature", "Zone_101_Temperature_Sensor")
   print(score)  # Should be > 80
   ```

---

## Best Practices

### 1. Query Optimization

**DO**:
- ✅ Use time-bucketed queries for long time ranges
- ✅ Leverage continuous aggregates for hourly/daily data
- ✅ Filter by sensor_name or sensor_type in WHERE clause
- ✅ Use indexes on (sensor_name, timestamp DESC)

**DON'T**:
- ❌ Query full table without WHERE clause
- ❌ Use LIKE '%pattern%' on large tables
- ❌ Fetch more data than needed (use LIMIT)
- ❌ Run analytics on raw data for long time ranges

---

### 2. Typo-Tolerant Queries

**DO**:
- ✅ Use natural language: "zone 101 temperature"
- ✅ Include sensor type: "temperature", "occupancy", "co2"
- ✅ Specify equipment: "AHU 1", "Chiller 2"
- ✅ Accept minor typos: "temprature", "ocupancy"

**DON'T**:
- ❌ Assume exact sensor names required
- ❌ Mix multiple sensor types without context
- ❌ Use ambiguous terms without zone/equipment IDs

---

### 3. Analytics Best Practices

**DO**:
- ✅ Use at least 24 hours of data for trend analysis
- ✅ Provide 7+ days for forecasting
- ✅ Include related sensors for correlation analysis
- ✅ Specify acceptable ranges for anomaly detection

**DON'T**:
- ❌ Run complex analytics on <1 hour of data
- ❌ Ignore data quality issues (gaps, outliers)
- ❌ Over-request analytics (cache results when possible)

---

## Related Documentation

- **[Building 1 (ABACWS)](building1_abacws.md)**: Real testbed with 680 sensors
- **[Building 3 (Data Center)](building3_datacenter.md)**: High-availability with Cassandra
- **[Database Integration](database_integration.md)**: Multi-database support guide
- **[Analytics API](analytics_api.md)**: 30+ analysis types reference
- **[Multi-Building Support](multi_building.md)**: Switching between buildings

---

**Building 2** - 329 sensors optimizing commercial office HVAC and thermal comfort. 🏢🌡️⚡
