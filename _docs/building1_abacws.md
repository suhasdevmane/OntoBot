---
title: Building 1 - ABACWS (Real University Testbed)
layout: post
category: docs
permalink: /docs/building1_abacws/
---

# Building 1 - ABACWS (Real University Testbed)

## Overview

**Rasa Conversational AI Stack for Building 1**

**ABACWS** (Cardiff University's smart building testbed) is OntoBot's primary demonstration platform - a real-world university building with comprehensive Indoor Environmental Quality (IEQ) monitoring across 34 zones.

![Building 1 - ABACWS Visualizer]({{ '/assets/images/bldg1_visulizer.png' | relative_url }})

## Overview

### Quick Facts

Building 1 (ABACWS) is a real-world university testbed building at Cardiff University, Wales, UK, with comprehensive Indoor Environmental Quality (IEQ) monitoring. This building serves as the primary demonstration and research platform for OntoBot's capabilities.

 | Property | Value | 

 | ---------- | ------- | ### Key Specifications

 | **Building Type** | University Research Testbed | 

 | **Location** | Cardiff University, Wales, UK | | Property | Details | 

 | **Total Sensors** | 680 sensors | | ---------- | --------- | 

 | **Zones Covered** | 34 zones (5.01–5.34) | | **Building Type** | Real University Testbed | 

 | **Sensors per Zone** | 20 multi-parameter sensors | | **Location** | Cardiff University, Wales, UK | 

 | **Database** | MySQL 8.0 (Port 3306 internal, 3307 host) | | **Sensor Coverage** | 680 sensors across 34 zones (5.01–5.34) | 

 | **Knowledge Graph** | Jena Fuseki + Brick 1.3 (Port 3030) | | **Focus Area** | Indoor Environmental Quality (IEQ) | 

 | **Compose File** | `docker-compose.bldg1.yml` | | **Database** | MySQL (port 3307) | 

 | **Data Retention** | 6+ months of historical data | | **Knowledge Graph** | Brick Schema 1.3 via Jena Fuseki (port 3030) | 

 | **Compose File** | `docker-compose.bldg1.yml` | 

---| **Technology Stack** | Rasa 3.6.12, Python 3.10, Docker, MySQL 8.0 |


## Sensor Infrastructure## Sensor Infrastructure


### Comprehensive Monitoring### Sensor Distribution


Each of the 34 zones is equipped with a **multi-parameter environmental sensor** providing 20 simultaneous measurements:ABACWS features **20 sensors per zone** across 34 zones on the 5th floor, providing comprehensive environmental monitoring:


```- **Total Sensors**: 680

Zone 5.01 Sensors (20):- **Zones**: 5.01 through 5.34

├── Air Quality (5)- **Sensors per Zone**: 20

│   ├── CO2 Level Sensor- **Data Collection**: Real-time telemetry stored in MySQL

│   ├── TVOC Sensor

│   ├── Formaldehyde Sensor### Sensor Types

│   ├── NO2 Level Sensor

│   └── Ethanol Sensor#### Air Quality Monitoring

├── Particulate Matter (3)

│   ├── PM1 Sensor**Primary Air Quality Metrics:**

│   ├── PM2.5 Sensor- **CO2 Sensors** - Carbon dioxide concentration (ppm)

│   └── PM10 Sensor- **TVOC** - Total Volatile Organic Compounds (ppb)

├── Environmental Comfort (4)- **Formaldehyde** - CH₂O concentration (µg/m³)

│   ├── Air Temperature Sensor

│   ├── Humidity Sensor**Particulate Matter Sensors:**

│   ├── Air Pressure Sensor- **PM1** - Particles < 1µm diameter (µg/m³)

│   └── Noise Level Sensor- **PM2.5** - Particles < 2.5µm diameter (µg/m³)

├── Lighting (3)- **PM10** - Particles < 10µm diameter (µg/m³)

│   ├── Illuminance Sensor

│   ├── Light Sensor (Lux)#### Multi-Gas Sensors

│   └── Brightness Sensor

└── Additional Metrics (5)**MQ Series Sensors:**

    ├── AQI (Air Quality Index)- **MQ2** - Combustible Gas & Smoke detection

    ├── IAQ (Indoor Air Quality)- **MQ3** - Alcohol Vapor detection

    ├── Battery Voltage- **MQ5** - LPG & Natural Gas detection

    ├── Sensor Status- **MQ9** - Carbon Monoxide & Coal Gas detection

    └── Data Quality Flag

**Additional Gas Sensors:**

Total: 20 sensors × 34 zones = 680 sensors- **NO2** - Nitrogen Dioxide concentration

```- **O2** - Oxygen percentage

- **C2H5OH** - Ethyl Alcohol concentration

### Sensor Categories

#### Environmental Parameters

#### 1. Air Quality Sensors (5 per zone)

- **Air Temperature** - °C with 0.1°C precision

**CO2 Level Sensor**- **Relative Humidity** - % RH

- **Measurement**: Carbon dioxide concentration- **Illuminance** - Light levels (lux)

- **Unit**: ppm (parts per million)- **Sound Level** - MEMS noise sensor (dB)

- **Range**: 400-5000 ppm- **Air Quality Index** - Composite IEQ score

- **Acceptable**: < 1000 ppm (UK guidelines)

- **Use Case**: Ventilation effectiveness, occupancy estimation## Database Integration


**TVOC Sensor**### MySQL Configuration

- **Measurement**: Total Volatile Organic Compounds

- **Unit**: ppb (parts per billion)Building 1 uses MySQL 8.0 for telemetry storage, optimized for time-series queries:

- **Range**: 0-10000 ppb

- **Acceptable**: < 500 ppb

```yaml

- **Use Case**: Indoor air pollution, material emissions# docker-compose.bldg1.yml

mysqlserver:

**Formaldehyde Sensor**  image: mysql:8.0

- **Measurement**: CH₂O concentration  ports:

- **Unit**: µg/m³ (micrograms per cubic meter)    - "3307:3306"

- **Range**: 0-2000 µg/m³  environment:

- **Acceptable**: < 100 µg/m³ (WHO guideline)    MYSQL_ROOT_PASSWORD: password

- **Use Case**: Building material emissions, air quality    MYSQL_DATABASE: telemetry

    MYSQL_USER: rasa_user

**NO2 Level Sensor**    MYSQL_PASSWORD: rasa_pass

- **Measurement**: Nitrogen dioxide  volumes:

- **Unit**: ppb    - mysql_data:/var/lib/mysql

- **Range**: 0-500 ppb

```

- **Acceptable**: < 40 ppb (annual average)

- **Use Case**: Outdoor air intrusion, combustion sources### Database Schema


**Ethanol Sensor**```sql

- **Measurement**: Ethanol vapor concentration-- Telemetry table structure

- **Unit**: ppbCREATE TABLE sensor_readings (

- **Range**: 0-5000 ppb    id BIGINT AUTO_INCREMENT PRIMARY KEY,

- **Use Case**: Cleaning product detection, occupancy proxy    sensor_uuid VARCHAR(36) NOT NULL,

    sensor_name VARCHAR(255),

#### 2. Particulate Matter Sensors (3 per zone)    zone_id VARCHAR(10),

    timestamp DATETIME(6) NOT NULL,

**PM1 Sensor**    value DOUBLE NOT NULL,

- **Measurement**: Particles < 1µm diameter    unit VARCHAR(20),

- **Unit**: µg/m³    sensor_type VARCHAR(50),

- **Health Impact**: Reaches deep into lungs    INDEX idx_sensor_time (sensor_uuid, timestamp),

- **Acceptable**: < 10 µg/m³    INDEX idx_zone_time (zone_id, timestamp),

    INDEX idx_type (sensor_type)

**PM2.5 Sensor**) ENGINE=InnoDB;

- **Measurement**: Particles < 2.5µm diameter

- **Unit**: µg/m³-- Sensor metadata

- **Health Impact**: Respiratory and cardiovascular effectsCREATE TABLE sensors (

- **Acceptable**: < 25 µg/m³ (24-hour mean, WHO)    uuid VARCHAR(36) PRIMARY KEY,

    name VARCHAR(255) NOT NULL,

**PM10 Sensor**    zone_id VARCHAR(10) NOT NULL,

- **Measurement**: Particles < 10µm diameter    sensor_type VARCHAR(50) NOT NULL,

- **Unit**: µg/m³    unit VARCHAR(20),

- **Health Impact**: Respiratory irritation    location_description TEXT,

- **Acceptable**: < 50 µg/m³ (24-hour mean, WHO)    brick_class VARCHAR(100),

    last_reading DATETIME(6),

#### 3. Environmental Comfort Sensors (4 per zone)    UNIQUE KEY unique_name (name)

) ENGINE=InnoDB;

**Air Temperature Sensor**

- **Measurement**: Ambient air temperature-- Zone information

- **Unit**: °CCREATE TABLE zones (

- **Range**: 0-50°C    zone_id VARCHAR(10) PRIMARY KEY,

- **Comfort Zone**: 20-24°C (winter), 23-26°C (summer)    floor INT NOT NULL,

- **Accuracy**: ±0.3°C    building VARCHAR(50) NOT NULL,

    zone_type VARCHAR(50),

**Humidity Sensor**    area_sqm DOUBLE,

- **Measurement**: Relative humidity    occupancy_capacity INT,

- **Unit**: % RH    description TEXT

- **Range**: 0-100%) ENGINE=InnoDB;

- **Comfort Zone**: 40-60% RH

```

- **Accuracy**: ±3%

### Query Examples

**Air Pressure Sensor**

- **Measurement**: Barometric pressure**Get Recent CO2 Readings:**

- **Unit**: hPa (hectopascals)

```sql

- **Range**: 950-1050 hPaSELECT 

- **Use Case**: Weather correlation, HVAC optimization    s.name AS sensor_name,

    s.zone_id,

**Noise Level Sensor**    sr.timestamp,

- **Measurement**: Sound pressure level    sr.value AS co2_ppm

- **Unit**: dB (decibels)FROM sensor_readings sr

- **Range**: 30-100 dBJOIN sensors s ON sr.sensor_uuid = s.uuid

- **Acceptable**: < 45 dB (office), < 35 dB (classroom)WHERE s.sensor_type = 'CO2'

    AND sr.timestamp >= NOW() - INTERVAL 1 HOUR

#### 4. Lighting Sensors (3 per zone)ORDER BY sr.timestamp DESC

LIMIT 100;

**Illuminance Sensor**```

- **Measurement**: Visible light intensity

- **Unit**: Lux**Calculate Zone Average Temperature:**

- **Range**: 0-10000 lux

```sql

- **Recommended**: 300-500 lux (office work)SELECT 

    s.zone_id,

**Light Sensor (Alternative Lux)**    AVG(sr.value) AS avg_temp,

- **Measurement**: Light level (alternative metric)    MIN(sr.value) AS min_temp,

- **Unit**: Lux    MAX(sr.value) AS max_temp,

- **Use Case**: Redundancy, cross-validation    COUNT(*) AS reading_count

FROM sensor_readings sr

**Brightness Sensor**JOIN sensors s ON sr.sensor_uuid = s.uuid

- **Measurement**: Perceived brightnessWHERE s.sensor_type = 'Temperature'

- **Unit**: Arbitrary units (0-100)    AND sr.timestamp >= NOW() - INTERVAL 24 HOUR

- **Use Case**: Visual comfort assessmentGROUP BY s.zone_id

ORDER BY s.zone_id;

#### 5. Composite Indices (2 per zone)

```


**AQI (Air Quality Index)****Detect Threshold Violations:**

- **Calculation**: Composite of CO2, TVOC, PM2.5, NO2

```sql

- **Scale**: 0-500SELECT 

- **Categories**:    s.name,

  - 0-50: Good (Green)    s.zone_id,

  - 51-100: Moderate (Yellow)    sr.timestamp,

  - 101-150: Unhealthy for Sensitive Groups (Orange)    sr.value AS co2_ppm

  - 151-200: Unhealthy (Red)FROM sensor_readings sr

  - 201+: Very Unhealthy (Purple)JOIN sensors s ON sr.sensor_uuid = s.uuid

WHERE s.sensor_type = 'CO2'

**IAQ (Indoor Air Quality)**    AND sr.value > 1000  -- CO2 threshold

- **Calculation**: Weighted average of all air quality sensors    AND sr.timestamp >= NOW() - INTERVAL 1 HOUR

- **Scale**: 0-100 (100 = excellent)ORDER BY sr.value DESC;

- **Factors**: CO2, TVOC, formaldehyde, particulates

```


---## Service Architecture


## Database Schema### Core Services


### MySQL ConfigurationBuilding 1 runs 8 core services:


**Connection Details**:| Service | Port | Purpose | Health Endpoint |

```yaml|---------|------|---------|-----------------|

Host: mysqlserver (internal) / localhost (host)| **Rasa Core** | 5005 | NLU/Dialogue engine | `GET /version` |

Port: 3306 (internal) / 3307 (host)| **Action Server** | 5055 | Custom actions & integrations | `GET /health` |

Database: telemetry| **Duckling** | 8000 | Entity extraction (dates, times) | `GET /` |

User: root| **File Server** | 8080 | Artifact hosting (charts, CSV) | `GET /health` |

Password: password (change in production!)| **Rasa Editor** | 6080 | Web-based NLU editor | `GET /health` |

```| **Frontend UI** | 3000 | React chat interface | N/A |

 | **Analytics** | 6001 | Time-series analytics microservice | `GET /health` | 

### Table Structure| **Decider** | 6009 | Analytics selection logic | `GET /health` |


```sql### Data Flow

CREATE TABLE telemetry (

  id BIGINT AUTO_INCREMENT PRIMARY KEY,```

  sensor_uuid VARCHAR(36) NOT NULL,User Query → Frontend (3000)

  timestamp DATETIME NOT NULL,    ↓

  sensor_value FLOAT,Rasa Core (5005) → NLU Processing

  quality_flag TINYINT DEFAULT 1,  -- 1=good, 0=suspect    ↓

  INDEX idx_sensor_time (sensor_uuid, timestamp),Action Server (5055)

  INDEX idx_timestamp (timestamp)    ├── MySQL (3307) → Telemetry Data

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;    ├── Fuseki (3030) → Knowledge Graph (SPARQL)

```    ├── Analytics (6001) → Time-series Analysis

    ├── Decider (6009) → Analytics Selection

### Sample Data    └── NL2SPARQL (6005) → Query Translation

    ↓

```sql
File Server (8080) ← Generated Artifacts

-- Example: Temperature reading from Zone 5.01    ↓

INSERT INTO telemetry VALUES (Frontend (3000) ← Rich Response + Media

  1,```

  '12345678-1234-1234-1234-123456789abc',  -- UUID for Air_Temperature_Sensor_5.01

  '2025-10-31 14:30:00',### Optional Services

  21.5,  -- °C

  1      -- Quality: Good- **NL2SPARQL** (6005) - T5-based NL→SPARQL translator

);- **Ollama** (11434) - Mistral LLM for summarization

- **Fuseki** (3030) - SPARQL endpoint for Brick knowledge graph

-- Example: CO2 reading from Zone 5.01- **MySQL** (3307) - Primary telemetry database

INSERT INTO telemetry VALUES (- **pgAdmin** (5050) - Web-based database administration

  2,

  '87654321-4321-4321-4321-cba987654321',  -- UUID for CO2_Level_Sensor_5.01## Installation & Setup

  '2025-10-31 14:30:00',

  650.0,  -- ppm### Quick Start

  1       -- Quality: Good

);```powershell

```# From repository root

cd C:\Users\<username>\Documents\GitHub\OntoBot

### Data Volume

# Start Building 1 stack

**Statistics** (as of October 2025):docker-compose -f docker-compose.bldg1.yml up -d --build

- **Total Records**: ~45 million readings

- **Daily Insertions**: ~68,000 readings (680 sensors × 100 readings/day)# Wait for services to be healthy (~2-3 minutes)

- **Database Size**: ~8 GB (6 months retention)Start-Sleep -Seconds 180

- **Query Performance**: < 100ms (indexed queries)

# Verify services

---docker-compose -f docker-compose.bldg1.yml ps

```

## Knowledge Graph (Brick Ontology)

### Access Points

### Fuseki Configuration

- **Frontend**: http://localhost:3000

**Endpoint**: `http://localhost:3030/trial/sparql`- **Rasa Core**: http://localhost:5005/version

- **Action Server**: http://localhost:5055/health

**Dataset Structure**:- **File Server**: http://localhost:8080/health

```- **Editor**: http://localhost:6080

bldg1/trial/dataset/- **Duckling**: http://localhost:8000

├── abacws-building-v7.ttl       # Core building structure- **pgAdmin**: http://localhost:5050 (admin@admin.com / admin)

├── sensors-full.ttl             # All 680 sensor definitions- **Fuseki**: http://localhost:3030

└── relationships.ttl            # Spatial/functional relationships

```### Environment Configuration


### Sample SPARQL Queries

```yaml

# Action Server Environment Variables

**Query 1: Get all sensors in Zone 5.01**environment:

```sparql  # File Server

PREFIX brick: <https://brickschema.org/schema/Brick#>  BASE_URL: http://localhost:8080

PREFIX bldg: <http://abacwsbuilding.cardiff.ac.uk/abacws#>  BUNDLE_MEDIA: "true"

PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>  

  # MySQL Database

SELECT ?sensor ?label ?type WHERE {  DB_HOST: mysqlserver

  ?sensor brick:hasLocation bldg:Zone_5.01 .  DB_NAME: telemetry

  ?sensor rdfs:label ?label .  DB_USER: root

  ?sensor a ?type .  DB_PASSWORD: password

  FILTER(STRSTARTS(STR(?type), "https://brickschema.org/schema/Brick#"))  DB_PORT: 3306

}  

ORDER BY ?label  # Service Integrations

```  ANALYTICS_URL: http://microservices:6000/analytics/run

  DECIDER_URL: http://decider-service:6009/decide

**Query 2: Get temperature sensor metadata**  NL2SPARQL_URL: http://nl2sparql:6005/predict

```sparql  FUSEKI_URL: http://fuseki:3030/abacws/query

PREFIX brick: <https://brickschema.org/schema/Brick#>  

PREFIX bldg: <http://abacwsbuilding.cardiff.ac.uk/abacws#>  # Feature Flags

  ENABLE_SUMMARIZATION: "true"

SELECT ?sensor ?uuid ?location ?unit WHERE {  ENABLE_ANALYTICS: "true"

  ?sensor a brick:Temperature_Sensor .```

  ?sensor brick:hasUUID ?uuid .

  ?sensor brick:hasLocation ?location .## Usage Examples

  ?sensor brick:hasUnit ?unit .

  FILTER(REGEX(STR(?sensor), "5.01"))### Indoor Environmental Quality Queries

}

```**CO2 Monitoring:**

```

**Query 3: Find all air quality sensors**"What's the CO2 level in zone 5.12?"

```sparql"Show me CO2 trends for the past hour in zone 5.15"

PREFIX brick: <https://brickschema.org/schema/Brick#>"Which zones have high CO2 levels?"

"Alert me if CO2 exceeds 1000 ppm"

SELECT ?sensor ?label WHERE {```

  ?sensor a ?type .

  ?sensor rdfs:label ?label .**Air Quality:**

  FILTER(```

    ?type IN ("Show PM2.5 levels across all zones"

      brick:CO2_Level_Sensor,"What's the air quality in zone 5.20?"

      brick:TVOC_Sensor,"Display TVOC trends for today"

      brick:Formaldehyde_Sensor,"Compare air quality between zones 5.10 and 5.20"

      brick:NO2_Level_Sensor,```

      brick:PM25_Sensor

    )**Temperature & Humidity:**

  )

```

}"What's the temperature in zone 5.08?"

```"Show humidity trends for the past week"

"Which zones are too warm?"

---"Compare temperature across all zones"

```

## Typical Query Examples

**Multi-Parameter Queries:**

### Basic Queries

```

"Show me all environmental parameters for zone 5.15"

**Current Sensor Value**:"What zones have poor air quality?"

```"Display IEQ summary for floor 5"

User: What is the temperature in zone 5.04?"Compare comfort metrics across zones"

Bot: The current temperature in zone 5.04 is 22.3°C ```

     (measured at 2025-10-31 14:30:00).

```### Analytics Capabilities


**Air Quality Check**:Building 1 supports 30+ analytics types via the Analytics Microservice:

```

User: What's the CO2 level in zone 5.01?**Statistical Analysis:**

Bot: The CO2 level in zone 5.01 is 650 ppm, which is - Mean, median, mode

     within acceptable range (< 1000 ppm).- Standard deviation

```- Min/max values

- Quartiles & percentiles

**Multi-Sensor Query**:

```**Time-Series Analysis:**

User: Show me all air quality metrics in zone 5.15- Moving averages

Bot: Air quality in zone 5.15:- Exponential smoothing

     • CO2: 720 ppm (Good)- Trend detection

     • TVOC: 250 ppb (Good)- Seasonality analysis

     • PM2.5: 8 µg/m³ (Good)

     • NO2: 15 ppb (Good)**Advanced Analytics:**

     • AQI: 45 (Good)- Anomaly detection (Isolation Forest, Z-score)

```- Forecasting (ARIMA, Prophet)

- Correlation analysis

### Typo-Tolerant Queries (NEW)- Threshold violation detection


**Space Normalization**:**Example Request:**

```python

User: What is the air temp sensor 5.04?import requests

↓ Auto-corrected to:

"Air_Temperature_Sensor_5.04"# Get CO2 forecast

Bot: The temperature is 22.3°Cresponse = requests.post(

```    'http://localhost:6001/analytics/run',

    json={

**Typo Correction**:        'analysis_type': 'forecast',

```        'sensor_id': 'CO2-Zone-5.12',

User: Show me NO2 Levl Sensor 5.09        'method': 'prophet',

↓ Fuzzy matched (score: 100)        'periods': 24,

"NO2_Level_Sensor_5.09"        'interval': '1h'

Bot: NO2 level is 18 ppb    }

```)

```

**Case Insensitivity**:

```## Knowledge Graph Integration

User: what is the co2 level sensor 5.01?

↓ Normalized to:### Brick Schema

"CO2_Level_Sensor_5.01"

Bot: CO2 level is 650 ppmBuilding 1 uses Brick Schema 1.3 for semantic building representation:

```

```turtle

### Time-Based Queries# ABACWS Building Model (excerpt)

@prefix brick: <https://brickschema.org/schema/Brick#> .

**Historical Average**:@prefix abacws: <http://example.org/abacws#> .

```

User: What was the average temperature in zone 5.01 yesterday?abacws:Building1 a brick:Building ;

Bot: The average temperature in zone 5.01 yesterday was 21.8°C    brick:hasFloor abacws:Floor5 .

     (based on 1440 readings).

```abacws:Floor5 a brick:Floor ;

    brick:hasZone abacws:Zone_5_12 .

**Peak Values**:

```abacws:Zone_5_12 a brick:HVAC_Zone ;

User: What was the maximum CO2 level today?    brick:hasPoint abacws:CO2_Sensor_5_12 ,

Bot: The maximum CO2 level today was 1250 ppm in zone 5.20                   abacws:Temp_Sensor_5_12 ,

     at 14:00 (lunch period).                   abacws:Humidity_Sensor_5_12 .

```

abacws:CO2_Sensor_5_12 a brick:CO2_Level_Sensor ;

### Analytics Queries    brick:hasUnit "ppm" ;

    brick:uuid "uuid-co2-5-12" .

**Trend Analysis**:```

```

User: Show me temperature trends for zone 5.04 over the last week### SPARQL Queries

Bot: [Chart showing 7-day temperature trend]

     Temperature in zone 5.04 has been stable at 21.5±0.8°C**Find All CO2 Sensors:**

     over the last week. Slight increase on weekdays due to

```sparql

     occupancy. Trend: +0.1°C/day.PREFIX brick: <https://brickschema.org/schema/Brick#>

```PREFIX abacws: <http://example.org/abacws#>


**Anomaly Detection**:SELECT ?sensor ?zone ?uuid

```WHERE {

User: Detect anomalies in CO2 levels for zone 5.01    ?sensor a brick:CO2_Level_Sensor ;

Bot: [Chart with anomalies highlighted]            brick:isPointOf ?zone ;

     Detected 3 CO2 spikes in zone 5.01:            brick:uuid ?uuid .

     • 2025-10-29 14:30: 1850 ppm (meeting)}

     • 2025-10-30 10:15: 1650 ppm (class)

```

     • 2025-10-31 13:00: 1720 ppm (lunch)

     **Get Zone Equipment:**

     Recommendation: Increase ventilation rate during

```sparql

     peak occupancy periods.PREFIX brick: <https://brickschema.org/schema/Brick#>

```

SELECT ?equipment ?type

**Comparative Analysis**:WHERE {

```    <http://example.org/abacws#Zone_5_12> brick:hasPoint ?equipment .

User: Compare air quality between zone 5.01 and zone 5.10    ?equipment a ?type .

Bot: [Side-by-side comparison chart]}

     Air Quality Comparison:```

     Zone 5.01:

     • AQI: 45 (Good)## Development

     • CO2: 650 ppm

     • PM2.5: 8 µg/m³### Project Structure

     

     Zone 5.10:```

     • AQI: 72 (Moderate)rasa-bldg1/

     • CO2: 950 ppm├── actions/

     • PM2.5: 18 µg/m³│   ├── actions.py           # Custom actions (live reload)

     │   └── mysql_client.py      # MySQL integration

     Zone 5.01 has better air quality. Zone 5.10 may need├── data/

     improved ventilation.│   ├── nlu.yml             # NLU training data (IEQ specific)

```│   ├── rules.yml           # Conversation rules

│   └── stories.yml         # Conversation flows

**Forecasting**:├── models/                  # Trained Rasa models

```├── shared_data/

User: Predict temperature for the next 2 hours in zone 5.04│   ├── artifacts/          # Generated charts, CSV files

Bot: [Forecast chart with confidence intervals]│   └── sensor_mappings/    # UUID to sensor name mappings

     Temperature forecast for zone 5.04:├── config.yml              # Rasa pipeline configuration

     • 15:00: 22.5°C (±0.3°C)├── domain.yml              # Intents, entities, responses

     • 16:00: 22.7°C (±0.5°C)├── endpoints.yml           # Action server & event broker

     └── credentials.yml         # Channel credentials

     Based on current trend and historical patterns.```

     Confidence: 85%

```### Custom Actions


---```python

# actions/actions.py

## Docker Compose Configurationfrom typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker

### Quick Startfrom rasa_sdk.executor import CollectingDispatcher

import mysql.connector

```bash

# Start Building 1class ActionQueryCO2(Action):

docker-compose -f docker-compose.bldg1.yml up -d    def name(self) -> Text:

        return "action_query_co2"

# Check health

pwsh -File scripts/check-health.ps1    def run(

        self, 

# View logs        dispatcher: CollectingDispatcher,

docker logs -f action_server_bldg1        tracker: Tracker,

```        domain: Dict[Text, Any]

    ) -> List[Dict[Text, Any]]:

### Service Stack        

        zone = tracker.get_slot("zone_id")

**Core Services**:        

- `rasa_bldg1`: Conversational AI (Port 5005)        # Connect to MySQL

- `action_server_bldg1`: Business logic + typo tolerance (Port 5055)        conn = mysql.connector.connect(

- `mysqlserver`: Telemetry database (Port 3307)            host='mysqlserver',

- `fuseki-db`: Knowledge graph (Port 3030)            database='telemetry',

- `microservices`: Analytics (Port 6001)            user='root',

- `decider-service`: Query classifier (Port 6009)            password='password'

- `http_server`: Artifact serving (Port 8080)        )

- `frontend`: React UI (Port 3000)        

        cursor = conn.cursor(dictionary=True)

**Optional Services** (docker-compose.extras.yml):        query = """

- `nl2sparql`: T5-based NL→SPARQL (Port 6005)            SELECT sr.value, sr.timestamp, s.unit

- `ollama`: Mistral LLM for summaries (Port 11434)            FROM sensor_readings sr

            JOIN sensors s ON sr.sensor_uuid = s.uuid

### Environment Variables            WHERE s.zone_id = %s 

              AND s.sensor_type = 'CO2'

```yaml            ORDER BY sr.timestamp DESC

action_server_bldg1:            LIMIT 1

  environment:        """

    # Service URLs        cursor.execute(query, (zone,))

    - FUSEKI_URL=http://fuseki-db:3030/trial/sparql        result = cursor.fetchone()

    - ANALYTICS_URL=http://microservices:6000/analytics/run        

    - DECIDER_URL=http://decider-service:6009/decide        if result:

    - NL2SPARQL_URL=http://nl2sparql:6005/nl2sparql            message = f"CO2 level in zone {zone}: {result['value']:.1f} {result['unit']}"

    - SUMMARIZATION_URL=http://ollama:11434        else:

                message = f"No CO2 data found for zone {zone}"

    # Database (MySQL)        

    - DB_HOST=mysqlserver        dispatcher.utter_message(text=message)

    - DB_NAME=telemetry        return []

    - DB_USER=root

```

    - DB_PASSWORD=password

    - DB_PORT=3306### Adding IEQ-Specific Intents

    

    # Typo tolerance (NEW)

```yaml

    - SENSOR_FUZZY_THRESHOLD=80# data/nlu.yml

    - SENSOR_LIST_RELOAD_SEC=300- intent: query_co2

      examples: |

    # Feature flags    - what's the CO2 in [zone 5.12](zone_id)

    - ENABLE_SUMMARIZATION=true    - show me CO2 levels in [5.15](zone_id)

    - ENABLE_ANALYTICS=true    - CO2 reading for [zone 5.20](zone_id)

        - carbon dioxide level in [5.08](zone_id)

    # File paths

    - SENSOR_LIST_FILE=/app/actions/sensor_list.txt- intent: query_air_quality

    - SENSOR_UUIDS_FILE=/app/actions/sensor_uuids.txt  examples: |

```    - how's the air quality in [zone 5.12](zone_id)

    - show PM2.5 levels in [5.15](zone_id)

---    - what's the AQI for [zone 5.20](zone_id)

    - air quality status in [5.08](zone_id)

## Performance Characteristics

- intent: query_temperature

### Query Response Times  examples: |

    - what's the temperature in [zone 5.12](zone_id)

 | Query Type | Avg Time | Max Time | Notes | - show me temp for [5.15](zone_id)

 | ------------ | ---------- | ---------- | ------- | - how warm is [zone 5.20](zone_id)

 | Simple sensor value | 500ms | 1s | Direct database query | - temperature reading for [5.08](zone_id)

 | SPARQL metadata | 200ms | 500ms | Indexed Fuseki query | ```

 | Typo correction | 50ms | 150ms | Cached sensor list + fuzzy match | 

 | Historical data (1 day) | 800ms | 2s | 1440 readings | ## Testing & Monitoring

 | Historical data (1 week) | 1.5s | 3s | 10,080 readings | 

 | Analytics (trend) | 2s | 5s | Computation + chart generation | ### Health Checks

 | Analytics (anomaly) | 3s | 7s | ML model inference | 

 | Analytics (forecast) | 4s | 8s | ARIMA/Prophet model | ```powershell

 | LLM summary | 3s | 6s | Ollama Mistral inference | # Check all services

docker-compose -f docker-compose.bldg1.yml ps

### Resource Usage

# Individual health checks

**Docker Memory Allocation** (8 GB total):curl http://localhost:5005/version        # Rasa

- Rasa Core: 1.5 GBcurl http://localhost:5055/health         # Actions

- Action Server: 800 MBcurl http://localhost:8080/health         # File Server

- MySQL: 1.2 GBcurl http://localhost:6001/health         # Analytics

- Fuseki: 1 GBcurl http://localhost:6009/health         # Decider

- Analytics: 1 GB

- Frontend: 300 MB# MySQL connectivity

- Other services: 2.2 GBdocker-compose -f docker-compose.bldg1.yml exec mysqlserver mysql -u root -ppassword -e "SELECT 1"

```

**CPU Usage** (under load):

- Rasa Core: 20-30%### Test Conversations

- Action Server: 10-15%

- Analytics: 30-50% (during computation)

```powershell

- MySQL: 5-10%# Start interactive shell

docker-compose -f docker-compose.bldg1.yml exec rasa rasa shell

---

# Example conversation:

## Research Use Cases# You: what's the CO2 in zone 5.12?

# Bot: [Displays CO2 reading with timestamp]

### 1. Indoor Air Quality Studies# You: show me temperature trends

# Bot: [Generates chart and displays link]

**Research Question**: How does occupancy affect CO2 levels?# You: which zones have high CO2?

# Bot: [Lists zones with CO2 > threshold]

**Approach**:```

```

1. Query CO2 data for all zones over 1 month### Performance Monitoring

2. Correlate with occupancy sensor data

3. Identify patterns (weekday vs weekend, time of day)**MySQL Query Performance:**

4. Optimize ventilation schedules

```sql

```-- Enable slow query log

SET GLOBAL slow_query_log = 'ON';

**OntoBot Query**:SET GLOBAL long_query_time = 2;

```

Show me CO2 trends for all zones over the last month-- Check table sizes

Correlate CO2 with occupancy in zone 5.01SELECT 

```    table_name,

    ROUND((data_length + index_length) / 1024 / 1024, 2) AS size_mb

### 2. HVAC OptimizationFROM information_schema.tables

WHERE table_schema = 'telemetry'

**Research Question**: Can we reduce energy while maintaining comfort?ORDER BY (data_length + index_length) DESC;


**Approach**:-- Analyze queries

```EXPLAIN SELECT * FROM sensor_readings WHERE sensor_uuid = 'uuid-123';

1. Analyze temperature setpoints vs actual temperatures

```

2. Detect zones with excessive heating/cooling

3. Identify opportunities for setback schedules## Troubleshooting

4. Predict optimal setpoints using ML

```### Common Issues


**OntoBot Query**:**Problem: MySQL container fails to start**

```powershell

Compare temperature setpoints vs actual temperatures# Check logs

Predict optimal temperature for zone 5.04docker-compose -f docker-compose.bldg1.yml logs mysqlserver

What if we reduce heating by 1°C?

```# Solution: Reset MySQL volume

docker-compose -f docker-compose.bldg1.yml down -v

### 3. Ventilation Effectivenessdocker volume rm ontobot_mysql_data

docker-compose -f docker-compose.bldg1.yml up -d mysqlserver

**Research Question**: Are current ventilation rates adequate?```


**Approach**:**Problem: Slow queries**

```sql

1. Monitor CO2 decay rates after occupancy-- Add indexes

2. Calculate air change rates (ACH)CREATE INDEX idx_sensor_type_time ON sensor_readings(sensor_type, timestamp);

3. Compare to ASHRAE standardsCREATE INDEX idx_zone_type_time ON sensor_readings(zone_id, sensor_type, timestamp);

4. Recommend improvements

```-- Optimize table

OPTIMIZE TABLE sensor_readings;

**OntoBot Query**:```

```

Show me CO2 decay rates after occupancy**Problem: Action server can't connect to MySQL**

Calculate air change rate for zone 5.01

```yaml

Is ventilation adequate in zone 5.15?# Check environment variables in docker-compose.bldg1.yml

```environment:

  DB_HOST: mysqlserver  # Must match service name

### 4. Lighting and Productivity  DB_PORT: 3306         # Internal port, not host port

```

**Research Question**: How does lighting affect occupant comfort?

## Research & Academic Use

**Approach**:

```### Data Collection

1. Correlate illuminance with occupancy duration

2. Identify zones with poor lightingABACWS serves as a real-world testbed for:

3. Recommend lighting adjustments- Indoor air quality research

```- Occupant comfort studies

- Energy efficiency optimization

**OntoBot Query**:- HVAC control strategies

```- Sensor network deployment

Show me illuminance levels across all zones

Which zones have insufficient lighting?### Publications

Correlate lighting with occupancy patterns

```Building 1 data has been used in research on:

- CO2-based ventilation control

---- Particulate matter health impacts

- Multi-sensor data fusion

## Troubleshooting- Predictive maintenance

- Occupancy detection

### Common Issues

### Data Access

**Issue 1: No sensor data returned**

For academic research access to ABACWS data, contact the Building Management Systems team at Cardiff University.

**Symptoms**:

```## Related Documentation

User: What is the temperature in zone 5.01?

Bot: I couldn't find any data for that sensor.- [Building 2 - Office Building](/docs/building2/) - Synthetic HVAC-focused building

```- [Building 3 - Data Center](/docs/building3/) - Critical infrastructure monitoring

- [MySQL Integration Guide](/docs/mysql_integration/) - Detailed database guide

**Solutions**:- [Analytics API Reference](/docs/analytics_api/) - Analytics capabilities

```bash- [Multi-Building Support](/docs/multi_building/) - Switching between buildings

# Check database connection

docker exec -it mysqlserver mysql -uroot -ppassword \## Support & Resources

  -e "SELECT COUNT(*) FROM telemetry.telemetry;"

- **Main Documentation**: [OntoBot GitHub](https://github.com/suhasdevmane/OntoBot)

# Verify sensor UUID exists- **MySQL Documentation**: [MySQL 8.0 Reference](https://dev.mysql.com/doc/)

docker exec -it mysqlserver mysql -uroot -ppassword \- **Brick Schema**: [brickschema.org](https://brickschema.org/)

  -e "SELECT DISTINCT sensor_uuid FROM telemetry.telemetry LIMIT 10;"- **Rasa Documentation**: [rasa.com/docs](https://rasa.com/docs/)


# Check sensor list---

cat rasa-bldg1/actions/sensor_list.txt | grep -i "temp.*5.01"

```**Building 1 (ABACWS)** represents real-world deployment with:

- ✅ 680 real sensors across 34 zones

**Issue 2: Fuzzy matching too strict**- ✅ Comprehensive IEQ monitoring

- ✅ MySQL time-series storage

**Symptoms**:- ✅ Brick Schema knowledge graph

```- ✅ Academic research platform

User: What is the temp sensor 501?
Bot: I couldn't find sensor "temp sensor 501"
```

**Solution**:
```yaml
# Lower threshold in docker-compose.bldg1.yml
action_server_bldg1:
  environment:
    - SENSOR_FUZZY_THRESHOLD=70  # Was 80
```

**Issue 3: Slow analytics queries**

**Symptoms**: Analytics take > 10 seconds

**Solutions**:
```bash
# Check database indexes
docker exec -it mysqlserver mysql -uroot -ppassword \
  -e "SHOW INDEX FROM telemetry.telemetry;"

# Add index if missing
docker exec -it mysqlserver mysql -uroot -ppassword \
  -e "CREATE INDEX idx_sensor_time ON telemetry.telemetry(sensor_uuid, timestamp);"

# Limit time range
# Instead of: "Show me trends for the last year"
# Use: "Show me trends for the last week"
```

---

## Best Practices

### 1. Query Optimization

**DO**:
- ✅ Use specific zone numbers: "zone 5.01" not "zone 5"
- ✅ Limit time ranges: "last 24 hours" not "all time"
- ✅ Use sensor names consistently: "Air_Temperature_Sensor_5.01"

**DON'T**:
- ❌ Use ambiguous terms: "temperature" (which zone?)
- ❌ Query too much data: "show me everything"
- ❌ Mix sensor types: "temperature and CO2 and humidity and..." (do separate queries)

### 2. Typo Tolerance

**Effective Queries** (work well with fuzzy matching):
```
air temp sensor 5.01     ✓ Score: 97.5
NO2 Levl Sensor 5.09     ✓ Score: 100
co2 level 5.04           ✓ Score: 95.8
humidity sensor 515      ✓ Score: 92.3
```

**Ineffective Queries** (too ambiguous):
```
sensor 1                 ✗ (Which sensor?)
temp                     ✗ (Too short)
5.01                     ✗ (Zone or sensor?)
```

### 3. Analytics Usage

**For Fast Insights**:
- Use summary statistics
- Limit to 1-7 days of data
- Use pre-computed indices (AQI, IAQ)

**For Deep Analysis**:
- Use forecasting models
- Aggregate by hour/day
- Export CSV for external analysis

---

## Next Steps

### Learn More

- **[Typo Tolerance Guide](typo_tolerance.md)**: Deep dive into fuzzy matching
- **[Analytics API](analytics_api.md)**: Full analytics reference
- **[Multi-Building Support](multi_building.md)**: Switch to Building 2 or 3
- **[Customization](customization.md)**: Adapt to your building

### Explore Data

**Access MySQL directly**:
```bash
docker exec -it mysqlserver mysql -uroot -ppassword telemetry
```

**Access Fuseki UI**:
```
http://localhost:3030
# Login: admin / admin
```

**Export Data**:
```sql
-- Export zone 5.01 temperature for last 7 days
SELECT timestamp, sensor_value
FROM telemetry
WHERE sensor_uuid = '...'
  AND timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
INTO OUTFILE '/tmp/temp_5.01.csv'
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n';
```

---

**Building 1 (ABACWS)** - Real-world university testbed with 680 sensors. The reference implementation for OntoBot. 🏢📊✨
