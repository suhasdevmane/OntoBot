---
title: Building 3 - Synthetic Data Center
layout: post
category: docs
permalink: /docs/building3_datacenter/
---

# Building 3 - Synthetic Data Center

**Critical infrastructure facility with 597 sensors for data center operations, cooling systems, and power distribution using Cassandra.**

**Rasa Conversational AI Stack for Building 3**

---

## Overview

Building 3 is a synthetic critical infrastructure data center focused on cooling systems, power distribution, and alarm monitoring with high-availability Cassandra storage.

Building 3 represents a Tier III data center facility designed for high-availability monitoring, mission-critical operations, and fault-tolerant infrastructure. With 597 sensors covering CRAC units, UPS systems, PDUs, and environmental monitoring, this testbed provides comprehensive insights into data center reliability, energy efficiency, and uptime management.

### Key Specifications

### Key Specifications

 | Property | Details | 

 | Property | Value | | ---------- | --------- | 

 | ---------- | ------- | | **Building Type** | Synthetic Critical Infrastructure | 

 | **Building Type** | Synthetic Critical Infrastructure | | **Purpose** | Data Center Operations & Monitoring | 

 | **Primary Focus** | Data Center Operations & Uptime | | **Sensor Coverage** | 597 sensors across multiple zones | 

 | **Total Sensors** | 597 distributed across power + cooling + alarms | | **Focus Area** | Cooling Systems, Power Distribution & Alarms | 

 | **Database** | Cassandra 4.1 (distributed NoSQL) | | **Database** | Cassandra (port 9042) - Distributed NoSQL | 

 | **Metadata Store** | PostgreSQL 15 (ThingsBoard entities) | | **Metadata Store** | PostgreSQL (port 5434) - ThingsBoard entities | 

 | **Port (Cassandra)** | 9042 (host & container) | | **Knowledge Graph** | Brick Schema 1.3 via Jena Fuseki (port 3030) | 

 | **Port (PostgreSQL)** | 5434 (host), 5432 (container) | | **Compose File** | `docker-compose.bldg3.yml` | 

 | **Knowledge Graph** | Brick Schema 1.3 via Jena Fuseki | | **Technology Stack** | Rasa 3.6.12, Python 3.10, Docker, Cassandra 4.1 | 

 | **Compose File** | `docker-compose.bldg3.yml` | 

 | **Tech Stack** | Rasa 3.6.12, Python 3.10, Docker, Cassandra 4.1 | ## Critical Infrastructure Monitoring

 | **Dataset** | `bldg3/trial/dataset/*.ttl` | 

### Equipment Coverage (597 Sensors)

---

**CRAC Units (Computer Room Air Conditioning):**

## Sensor Infrastructure- Supply/Return Air Temperature sensors

- Airflow Rate & Pressure monitoring

### Total Sensor Breakdown- Cooling Capacity measurement

- Efficiency metrics

Building 3 deploys **597 sensors** across **6 major categories**:- Alarm status indicators

- **Total CRAC Sensors**: ~150

1. **Cooling Systems (CRAC Units)** (180 sensors)

   - Supply/return air temperature**UPS Systems (Uninterruptible Power Supply):**

   - Airflow rates- Input/Output Voltage monitoring

   - Humidity control- Battery Charge Level & Health

   - Cooling capacity- Power Load & Capacity tracking

   - Efficiency metrics- Alarm Conditions

   - Alarm states- Runtime on battery

- **Total UPS Sensors**: ~120

2. **Power Distribution (UPS + PDUs)** (240 sensors)

   - UPS input/output voltage**PDUs (Power Distribution Units):**

   - Battery health and charge- Phase Voltages (L1, L2, L3)

   - Power load tracking- Current Draw per Phase

   - Phase voltages- Power Factor measurement

   - Circuit breaker states- Circuit Breaker Status

- Branch circuit monitoring

3. **Rack-Level Monitoring** (120 sensors)- **Total PDU Sensors**: ~180

   - Rack inlet/outlet temperature

   - Power consumption per rack**Rack-Level Monitoring:**

   - Airflow sensors- Inlet/Outlet Temperature per rack

   - Hot aisle temperature- Humidity sensors

- Hot Aisle/Cold Aisle Temperature

4. **Environmental Monitoring** (30 sensors)- Power Consumption per Rack

   - Room temperature/humidity- Airflow sensors

   - Leak detection sensors- **Total Rack Sensors**: ~120

   - Smoke detectors

   - Door access sensors**Alarm Systems:**

- Environmental Alarms

5. **Alarm & Security Systems** (20 sensors)- Equipment Failure Alerts

   - Fire alarms- Threshold Violations

   - Water leak alarms- Critical System Warnings

   - Intrusion detection- **Total Alarm Points**: ~27

   - Access control events

### Data Center Metrics

6. **IT Equipment Metrics** (7 sensors)

   - Server CPU utilization**PUE (Power Usage Effectiveness):**

   - Network bandwidth utilization

```

   - Storage capacityPUE = Total Facility Power / IT Equipment Power

   - Compute loadTarget: < 1.5 (Excellent), < 2.0 (Good)

```

---

**DCiE (Data Center Infrastructure Efficiency):**

## Cooling Systems (CRAC Units)

```

DCiE = 1 / PUE × 100%

### CRAC Unit Architecture (12 units × 15 sensors = 180 sensors)Target: > 67% (Excellent), > 50% (Good)

```

Each CRAC unit monitors:

**Other Metrics:**

 | Sensor Type | Measurement | Range | Update Frequency | - Cooling efficiency (kW per ton)

 | ------------- | ------------- | ------- | ------------------ | - Server inlet temperature

 | Supply Air Temperature | Cooled air delivered to room | 15-25°C | 30 seconds | - Return temperature index (RTI)

 | Return Air Temperature | Air returned from room | 20-35°C | 30 seconds | - Cooling capacity utilization

 | Supply Airflow Rate | CFM delivered | 0-20,000 CFM | 1 minute | - Power capacity utilization

 | Return Humidity | Moisture content | 30-60% RH | 1 minute | 

 | Cooling Capacity | Ton or kW | 0-50 tons | 1 minute | ## Cassandra Database Architecture

 | Compressor Status | On/Off/Fault | Boolean | 30 seconds | 

 | Fan Speed | Percentage | 0-100% | 1 minute | ### Why Cassandra?

 | Condensate Drain Status | OK/Clogged | Boolean | 5 minutes | 

 | Efficiency Metric | COP or EER | 2.0-5.0 | 5 minutes | Cassandra is a distributed NoSQL database ideal for mission-critical data:

 | Alarm Status | Normal/Warning/Critical | Enum | 30 seconds | 

 | Power Consumption | kW | 0-25 kW | 1 minute | **Benefits:**

 | Filter Status | Clean/Dirty | Boolean | 1 hour | - ✅ **High Availability** - No single point of failure

 | Refrigerant Pressure (High) | psi | 200-450 psi | 1 minute | - ✅ **Linear Scalability** - Add nodes without downtime

 | Refrigerant Pressure (Low) | psi | 50-100 psi | 1 minute | - ✅ **Write Performance** - Millions of writes/second

 | Water Leak Sensor | Dry/Wet | Boolean | 30 seconds | - ✅ **Geographic Distribution** - Multi-datacenter replication

- ✅ **Tunable Consistency** - Balance between consistency & availability

**Example CRAC Sensor Names**:- ✅ **Time-Series Optimized** - Perfect for sensor data

```

CRAC_1_Supply_Air_Temperature_Sensor### Database Configuration

CRAC_1_Return_Air_Temperature_Sensor

CRAC_1_Supply_Airflow_Rate_Sensor

```yaml

CRAC_1_Return_Humidity_Sensor# docker-compose.bldg3.yml

CRAC_1_Cooling_Capacity_Sensorcassandra:

CRAC_1_Compressor_Status_Sensor  image: cassandra:4.1

CRAC_1_Fan_Speed_Sensor  ports:

CRAC_1_Efficiency_Metric_Sensor    - "9042:9042"

CRAC_1_Alarm_Status_Sensor  environment:

CRAC_1_Power_Consumption_Sensor    CASSANDRA_CLUSTER_NAME: "DataCenter-Cluster"

```    CASSANDRA_DC: "DC1"

    CASSANDRA_ENDPOINT_SNITCH: "GossipingPropertyFileSnitch"

**Total CRAC Sensors**: 12 units × 15 sensors = **180 sensors**    MAX_HEAP_SIZE: "4G"

    HEAP_NEWSIZE: "800M"

---  volumes:

    - cassandra_data:/var/lib/cassandra

## Power Distribution (UPS + PDUs)

```


### UPS Systems (10 units × 12 sensors = 120 sensors)### Cassandra Schema


Each UPS monitors:```cql

-- Create keyspace with replication

 | Sensor Type | Measurement | Range | Update Frequency | CREATE KEYSPACE IF NOT EXISTS telemetry_bldg3

 | ------------- | ------------- | ------- | ------------------ | WITH replication = {

 | Input Voltage (Phase A) | AC voltage in | 200-250V | 1 second | 'class': 'SimpleStrategy',

 | Input Voltage (Phase B) | AC voltage in | 200-250V | 1 second | 'replication_factor': 3  -- For production cluster

 | Input Voltage (Phase C) | AC voltage in | 200-250V | 1 second | };

 | Output Voltage | AC voltage out | 210-230V | 1 second | 

 | Output Current | Amps delivered | 0-200A | 1 second | USE telemetry_bldg3;

 | Output Power | kW | 0-100 kW | 1 second | 

 | Battery Charge Level | Percentage | 0-100% | 1 minute | -- Sensor readings table (time-series)

 | Battery Voltage | DC volts | 200-300V | 1 minute | CREATE TABLE IF NOT EXISTS sensor_data (

 | Battery Temperature | Celsius | 20-30°C | 5 minutes | sensor_uuid UUID,

 | Load Percentage | Percentage of capacity | 0-100% | 1 second | timestamp TIMESTAMP,

 | Runtime Remaining | Minutes on battery | 0-60 min | 1 minute | value DOUBLE,

 | Alarm Status | Normal/Fault | Enum | 1 second | unit TEXT,

    zone TEXT,

**Example UPS Sensor Names**:    equipment_type TEXT,

```    equipment_id TEXT,

UPS_1_Input_Voltage_PhaseA_Sensor    sensor_type TEXT,

UPS_1_Input_Voltage_PhaseB_Sensor    PRIMARY KEY ((sensor_uuid), timestamp)

UPS_1_Input_Voltage_PhaseC_Sensor) WITH CLUSTERING ORDER BY (timestamp DESC)

UPS_1_Output_Voltage_Sensor  AND compaction = {

UPS_1_Output_Current_Sensor      'class': 'TimeWindowCompactionStrategy',

UPS_1_Output_Power_Sensor      'compaction_window_unit': 'HOURS',

UPS_1_Battery_Charge_Level_Sensor      'compaction_window_size': '24'

UPS_1_Battery_Voltage_Sensor  };

UPS_1_Battery_Temperature_Sensor

UPS_1_Load_Percentage_Sensor-- Alarms table

UPS_1_Runtime_Remaining_SensorCREATE TABLE IF NOT EXISTS alarms (

UPS_1_Alarm_Status_Sensor    alarm_id UUID,

```    timestamp TIMESTAMP,

    severity TEXT,

**Total UPS Sensors**: 10 units × 12 sensors = **120 sensors**    equipment_id TEXT,

    equipment_type TEXT,

---    message TEXT,

    acknowledged BOOLEAN,

### PDUs (Power Distribution Units) (20 units × 6 sensors = 120 sensors)    acknowledged_by TEXT,

    acknowledged_at TIMESTAMP,

Each PDU monitors:    PRIMARY KEY ((equipment_id), timestamp)

) WITH CLUSTERING ORDER BY (timestamp DESC);

 | Sensor Type | Measurement | Range | Update Frequency | 

 | ------------- | ------------- | ------- | ------------------ | -- Equipment status table

 | Voltage Phase L1 | AC voltage | 210-230V | 1 second | CREATE TABLE IF NOT EXISTS equipment_status (

 | Voltage Phase L2 | AC voltage | 210-230V | 1 second | equipment_id TEXT,

 | Voltage Phase L3 | AC voltage | 210-230V | 1 second | equipment_type TEXT,

 | Total Power | kW across all phases | 0-50 kW | 1 second | zone TEXT,

 | Total Current | Amps across all phases | 0-150A | 1 second | status TEXT,

 | Circuit Breaker Status | OK/Tripped | Boolean | 1 second | last_updated TIMESTAMP,

    metadata MAP<TEXT, TEXT>,

**Example PDU Sensor Names**:    PRIMARY KEY (equipment_id)

```);

PDU_Rack_A01_Voltage_PhaseL1_Sensor

PDU_Rack_A01_Voltage_PhaseL2_Sensor-- Aggregated metrics (rollups)

PDU_Rack_A01_Voltage_PhaseL3_SensorCREATE TABLE IF NOT EXISTS hourly_aggregates (

PDU_Rack_A01_Total_Power_Sensor    sensor_uuid UUID,

PDU_Rack_A01_Total_Current_Sensor    hour TIMESTAMP,

PDU_Rack_A01_Circuit_Breaker_Status_Sensor    avg_value DOUBLE,

```    min_value DOUBLE,

    max_value DOUBLE,

**Total PDU Sensors**: 20 units × 6 sensors = **120 sensors**    sample_count INT,

    PRIMARY KEY ((sensor_uuid), hour)

---) WITH CLUSTERING ORDER BY (hour DESC);

```

## Rack-Level Monitoring (40 racks × 3 sensors = 120 sensors)

### CQL Query Examples

Each rack monitors:

**Get Recent CRAC Temperature:**

 | Sensor Type | Measurement | Range | Update Frequency | ```cql

 | ------------- | ------------- | ------- | ------------------ | SELECT timestamp, value, unit, equipment_id

 | Rack Inlet Temperature | Cold aisle temp | 18-27°C | 1 minute | FROM sensor_data

 | Rack Outlet Temperature | Hot aisle temp | 25-45°C | 1 minute | WHERE sensor_uuid = uuid-crac-001

 | Rack Power Consumption | kW | 0-20 kW | 1 minute | AND timestamp >= '2025-10-08 00:00:00'

  AND timestamp <= '2025-10-08 23:59:59'

**Example Rack Sensor Names**:ORDER BY timestamp DESC

```LIMIT 100;

Rack_A01_Inlet_Temperature_Sensor

```

Rack_A01_Outlet_Temperature_Sensor

Rack_A01_Power_Consumption_Sensor**Query Active Alarms:**

Rack_B15_Inlet_Temperature_Sensor

```cql

Rack_B15_Outlet_Temperature_SensorSELECT alarm_id, timestamp, severity, message

Rack_B15_Power_Consumption_SensorFROM alarms

```WHERE equipment_id = 'CRAC-A-01'

  AND acknowledged = false

**Total Rack Sensors**: 40 racks × 3 sensors = **120 sensors**ORDER BY timestamp DESC;

```

---

**Get Hourly Averages:**

## Environmental Monitoring

```cql

SELECT hour, avg_value, min_value, max_value

### Room-Level Sensors (6 rooms × 5 sensors = 30 sensors)FROM hourly_aggregates

WHERE sensor_uuid = uuid-ups-battery-001

Each room monitors:  AND hour >= '2025-10-01 00:00:00'

  AND hour <= '2025-10-08 00:00:00'

 | Sensor Type | Measurement | Range | Update Frequency | ORDER BY hour DESC;

 | ------------- | ------------- | ------- | ------------------ | ```

 | Room Temperature | Ambient temp | 18-30°C | 1 minute | 

 | Room Humidity | Relative humidity | 30-60% RH | 1 minute | ### Python Client Integration

 | Leak Detection | Dry/Wet | Boolean | 30 seconds | 

 | Smoke Detector | Clear/Smoke | Boolean | 1 second | ```python

 | Door Access | Closed/Open | Boolean | 1 second | # actions/cassandra_client.py

from cassandra.cluster import Cluster

**Example Room Sensor Names**:from cassandra.auth import PlainTextAuthProvider

```from datetime import datetime, timedelta

Room_ServerHall_1_Temperature_Sensorimport uuid

Room_ServerHall_1_Humidity_Sensor

Room_ServerHall_1_Leak_Detection_Sensorclass CassandraClient:

Room_ServerHall_1_Smoke_Detector_Sensor    def __init__(self, hosts=['cassandra'], port=9042, keyspace='telemetry_bldg3'):

Room_ServerHall_1_Door_Access_Sensor        self.cluster = Cluster(hosts, port=port)

```        self.session = self.cluster.connect(keyspace)

    

**Total Environmental Sensors**: 6 rooms × 5 sensors = **30 sensors**    def get_sensor_data(self, sensor_uuid, hours_back=1):

        """Get recent sensor readings"""

---        query = """

        SELECT timestamp, value, unit, equipment_id

## Alarm & Security Systems (20 sensors)        FROM sensor_data

        WHERE sensor_uuid = %s

**Fire Alarms** (6 zones):          AND timestamp >= %s

```        ORDER BY timestamp DESC

Fire_Alarm_Zone_1_Status_Sensor        """

Fire_Alarm_Zone_2_Status_Sensor        start_time = datetime.now() - timedelta(hours=hours_back)

...        return self.session.execute(query, (uuid.UUID(sensor_uuid), start_time))

```    

    def get_active_alarms(self, equipment_id=None, severity=None):

**Water Leak Alarms** (8 locations):        """Get active (unacknowledged) alarms"""

```        if equipment_id:

Water_Leak_Alarm_CRAC_1_Sensor            query = """

Water_Leak_Alarm_UPS_Room_Sensor            SELECT * FROM alarms

...            WHERE equipment_id = %s

```              AND acknowledged = false

            ORDER BY timestamp DESC

**Intrusion Detection** (4 zones):            """

```            return self.session.execute(query, (equipment_id,))

Intrusion_Detection_Zone_A_Sensor        else:

Intrusion_Detection_Zone_B_Sensor            # Note: This requires ALLOW FILTERING or secondary index

...            query = """

```            SELECT * FROM alarms

            WHERE acknowledged = false

**Access Control Events** (2 main doors):            ALLOW FILTERING

```            """

Access_Control_MainEntrance_Sensor            return self.session.execute(query)

Access_Control_ServerRoom_Sensor    

```    def calculate_pue(self, timestamp=None):

        """Calculate Power Usage Effectiveness"""

**Total Alarm Sensors**: **20 sensors**        if timestamp is None:

            timestamp = datetime.now()

---        

        # Get total facility power

## IT Equipment Metrics (7 sensors)        total_power_query = """

        SELECT value FROM sensor_data

**Aggregate Metrics**:        WHERE sensor_uuid = %s

```          AND timestamp <= %s

Aggregate_Server_CPU_Utilization_Sensor       (%)        ORDER BY timestamp DESC

Aggregate_Server_Memory_Utilization_Sensor    (%)        LIMIT 1

Aggregate_Storage_Capacity_Utilization_Sensor (%)        """

Aggregate_Network_Bandwidth_Utilization_Sensor (%)        

Aggregate_Compute_Load_Sensor                 (normalized)        # Get IT equipment power

Aggregate_Virtualization_Host_Count_Sensor    (count)        it_power_query = """

Aggregate_Active_VM_Count_Sensor              (count)        SELECT value FROM sensor_data

```        WHERE sensor_uuid = %s

          AND timestamp <= %s

**Update Frequency**: 5 minutes (less critical than physical infrastructure)        ORDER BY timestamp DESC

        LIMIT 1

---        """

        

## Cassandra Database Architecture        total_power_result = self.session.execute(

            total_power_query, 

### Why Cassandra for Data Centers?            (uuid.UUID('total-facility-power-uuid'), timestamp)

        ).one()

**High Availability**:        

- No single point of failure        it_power_result = self.session.execute(

- Multi-datacenter replication            it_power_query,

- Automatic failover            (uuid.UUID('it-equipment-power-uuid'), timestamp)

- Tunable consistency (AP from CAP theorem)        ).one()

        

**Scalability**:        if total_power_result and it_power_result:

- Linear scalability (add nodes without downtime)            total_power = total_power_result.value

- Write-optimized (critical for high-frequency sensor data)            it_power = it_power_result.value

- Handles 597 sensors × 1-second updates = ~600 writes/sec            pue = total_power / it_power if it_power > 0 else None

            return pue

**Fault Tolerance**:        return None

- Replication factor 3 (data replicated to 3 nodes)    

- Survives node failures automatically    def insert_sensor_reading(self, sensor_uuid, value, unit, equipment_id, sensor_type):

- Ideal for mission-critical infrastructure        """Insert new sensor reading"""

        query = """

---        INSERT INTO sensor_data (sensor_uuid, timestamp, value, unit, equipment_id, sensor_type)

        VALUES (%s, %s, %s, %s, %s, %s)

### Cassandra Schema        """

        self.session.execute(

**Keyspace**: `building3`            query,

            (uuid.UUID(sensor_uuid), datetime.now(), value, unit, equipment_id, sensor_type)

```cql        )

CREATE KEYSPACE building3    

WITH REPLICATION = {    def acknowledge_alarm(self, alarm_id, acknowledged_by):

  'class': 'SimpleStrategy',        """Acknowledge an alarm"""

  'replication_factor': 3        query = """

};        UPDATE alarms

        SET acknowledged = true,

USE building3;            acknowledged_by = %s,

```            acknowledged_at = %s

        WHERE alarm_id = %s

**Main Table**: `sensor_data`        """

        self.session.execute(query, (acknowledged_by, datetime.now(), uuid.UUID(alarm_id)))

```cql
```

CREATE TABLE sensor_data (

    sensor_id TEXT,## Usage Examples

    sensor_name TEXT,

    sensor_type TEXT,### Cooling System Monitoring

    timestamp TIMESTAMP,

    reading_value DOUBLE,```

    reading_unit TEXT,"Show me CRAC unit 1 temperature trends"

    zone_id TEXT,"What's the cooling efficiency in zone A?"

    equipment_id TEXT,"Alert me if any CRAC units have alarms"

    alarm_status TEXT,"Compare supply vs return air temperatures"

    PRIMARY KEY ((sensor_id), timestamp)"Display CRAC airflow rates"

) WITH CLUSTERING ORDER BY (timestamp DESC)

```

  AND compaction = {'class': 'TimeWindowCompactionStrategy', 'compaction_window_size': 1, 'compaction_window_unit': 'DAYS'}

  AND default_time_to_live = 63072000;  -- 2 years### Power Distribution

```

```

**Key Design Choices**:"What's the current load on PDU 3?"

- **Partition Key**: `sensor_id` (distribute sensors across nodes)"Show UPS battery status for all units"

- **Clustering Key**: `timestamp DESC` (newest data first)"What's our current PUE?"

- **Time-Window Compaction**: Optimize for time-series data"Display power consumption by rack"

- **TTL**: 2 years automatic expiry"Show phase balance on PDU 1"

```

---

### Alarm Management

### Sample Data

```

**CRAC Unit Data**:"Show all active alarms"

```cql"What critical alarms were triggered today?"

INSERT INTO sensor_data (sensor_id, sensor_name, sensor_type, timestamp, reading_value, reading_unit, equipment_id, alarm_status)"Display temperature threshold violations"

VALUES ('crac1_supply_temp', 'CRAC_1_Supply_Air_Temperature_Sensor', 'temperature', '2025-10-31 10:00:00', 18.5, 'C', 'CRAC_1', 'normal');"Show equipment failure alerts"

"Acknowledge alarm [ID]"

INSERT INTO sensor_data (sensor_id, sensor_name, sensor_type, timestamp, reading_value, reading_unit, equipment_id, alarm_status)

```

VALUES ('crac1_alarm', 'CRAC_1_Alarm_Status_Sensor', 'alarm', '2025-10-31 10:00:00', 0, 'boolean', 'CRAC_1', 'normal');

```### Environmental Monitoring


**UPS Data**:```

```cql"Show hot aisle temperatures in zone B"

INSERT INTO sensor_data (sensor_id, sensor_name, sensor_type, timestamp, reading_value, reading_unit, equipment_id, alarm_status)"What's the humidity in rack 15?"

VALUES ('ups1_battery_charge', 'UPS_1_Battery_Charge_Level_Sensor', 'percentage', '2025-10-31 10:00:00', 98.5, '%', 'UPS_1', 'normal');"Display inlet/outlet temperature differential"

"Show me cooling load trends this week"

INSERT INTO sensor_data (sensor_id, sensor_name, sensor_type, timestamp, reading_value, reading_unit, equipment_id, alarm_status)"Compare rack temperatures"

VALUES ('ups1_load', 'UPS_1_Load_Percentage_Sensor', 'percentage', '2025-10-31 10:00:00', 67.3, '%', 'UPS_1', 'normal');```

```

### Efficiency Metrics

**Rack Data**:

```cql
```

INSERT INTO sensor_data (sensor_id, sensor_name, sensor_type, timestamp, reading_value, reading_unit, zone_id, alarm_status)"Calculate our DCiE for today"

VALUES ('racka01_inlet_temp', 'Rack_A01_Inlet_Temperature_Sensor', 'temperature', '2025-10-31 10:00:00', 22.5, 'C', 'Rack_A01', 'normal');"Show power usage effectiveness trend"

"What's the cooling efficiency?"

INSERT INTO sensor_data (sensor_id, sensor_name, sensor_type, timestamp, reading_value, reading_unit, zone_id, alarm_status)"Display energy consumption by zone"

VALUES ('racka01_power', 'Rack_A01_Power_Consumption_Sensor', 'power', '2025-10-31 10:00:00', 12.3, 'kW', 'Rack_A01', 'normal');"Show PUE history for the past month"

```


---## High Availability Features


### Database Performance### Replication Strategy


**Storage Statistics** (1 year of data):**Production Setup (3+ nodes):**

```cql

 | Metric | Value | CREATE KEYSPACE telemetry_bldg3

 | -------- | ------- | WITH replication = {

 | Raw Data Size | 78 GB (3 nodes, RF=3 → 234 GB total) | 'class': 'NetworkTopologyStrategy',

 | Total Records | 315 million | 'DC1': 3,  -- 3 replicas in datacenter 1

 | Daily Inserts | 860,000 | 'DC2': 2   -- 2 replicas in datacenter 2 (DR site)

 | Write Throughput | 600-1,000 writes/sec | };

 | Read Throughput | 200-500 reads/sec | ```


**Query Performance** (single node):**Consistency Levels:**

- **QUORUM** - Majority of replicas (recommended for critical data)

 | Query Type | Response Time | - **LOCAL_QUORUM** - Majority within local DC (better latency)

 | ------------ | --------------- | - **ALL** - All replicas (highest consistency, lowest availability)

 | Single sensor, 1 hour | 20-40 ms | - **ONE** - Single replica (best performance, lowest consistency)

 | Single sensor, 24 hours | 50-100 ms | 

 | Single sensor, 1 week | 150-300 ms | ### Multi-Datacenter Replication

 | Multi-sensor (10), 1 hour | 100-200 ms | 

```yaml

**Cassandra Optimizations**:# docker-compose-prod.yml

- Partition-aware queries (always specify sensor_id)cassandra-dc1-node1:

- Clustering order DESC (newest data cached)  image: cassandra:4.1

- Time-window compaction (efficient time-series queries)  environment:

- Automatic TTL (no manual cleanup)    CASSANDRA_CLUSTER_NAME: "DataCenter-Cluster"

    CASSANDRA_DC: "DC1"

---    CASSANDRA_SEEDS: "cassandra-dc1-node1,cassandra-dc2-node1"


## PostgreSQL Metadata Storecassandra-dc1-node2:

  image: cassandra:4.1

Building 3 uses **PostgreSQL** (port 5434) to store ThingsBoard entity metadata.  environment:

    CASSANDRA_DC: "DC1"

**Connection**:    CASSANDRA_SEEDS: "cassandra-dc1-node1,cassandra-dc2-node1"

```yaml

Host: postgres (internal) / localhost (host)cassandra-dc2-node1:

Port: 5432 (internal) / 5434 (host)  image: cassandra:4.1

Database: thingsboard  environment:

Username: postgres    CASSANDRA_DC: "DC2"

Password: postgres    CASSANDRA_SEEDS: "cassandra-dc1-node1,cassandra-dc2-node1"

```


**Metadata Tables**:### Backup & Recovery

- `device`: Sensor device entities

- `asset`: Logical groupings (racks, rooms)

```bash

- `entity_relation`: Relationships between entities# Create snapshot

- `alarm`: Alarm configurationsdocker-compose -f docker-compose.bldg3.yml exec cassandra nodetool snapshot telemetry_bldg3


**Example Query** (get all CRAC units):# List snapshots

```sqldocker-compose -f docker-compose.bldg3.yml exec cassandra nodetool listsnapshots

SELECT id, name, type

FROM device# Export data

WHERE type = 'CRAC_Unit'docker-compose -f docker-compose.bldg3.yml exec cassandra cqlsh -e "COPY telemetry_bldg3.sensor_data TO '/backup/sensor_data.csv'"

ORDER BY name;

```# Restore from snapshot

# 1. Stop Cassandra

---# 2. Copy snapshot files to data directory

# 3. Start Cassandra

## Brick Schema Knowledge Graph# 4. Run: nodetool refresh telemetry_bldg3 sensor_data

```

### Ontology Structure

## Performance Optimization

Building 3's knowledge graph uses **Brick Schema 1.3** with 597 sensor entities.

### Compaction Strategy

**Fuseki Endpoint**: `http://localhost:3030/trial/sparql`

For time-series data, use TimeWindowCompactionStrategy:

**Dataset Location**: `bldg3/trial/dataset/*.ttl`

```cql

---ALTER TABLE sensor_data

WITH compaction = {

### Sample SPARQL Queries    'class': 'TimeWindowCompactionStrategy',

    'compaction_window_unit': 'HOURS',

#### Query 1: Find All CRAC Units and Their Sensors    'compaction_window_size': '24'

};

```sparql
```

PREFIX brick: <https://brickschema.org/schema/Brick#>

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>**Benefits:**

- Automatic cleanup of old SSTables

SELECT ?crac ?sensor ?sensorType- Better read performance

WHERE {- Efficient disk usage

  ?crac rdf:type brick:CRAC .- Time-based data organization

  ?sensor brick:isPointOf ?crac .

  ?sensor rdf:type ?sensorType .### Memory Settings

}

ORDER BY ?crac ?sensor

```yaml

```# Production memory configuration

environment:

**Results**: 12 CRACs × 15 sensors = 180 sensors  MAX_HEAP_SIZE: "8G"      # 1/4 to 1/2 of available RAM

  HEAP_NEWSIZE: "2G"       # 1/4 of MAX_HEAP_SIZE

---  CASSANDRA_MEMTABLE_HEAP_SPACE_IN_MB: "2048"

  CASSANDRA_MEMTABLE_OFFHEAP_SPACE_IN_MB: "2048"

#### Query 2: Get All UPS Battery Status Sensors

```


```sparql### Monitoring Commands

PREFIX brick: <https://brickschema.org/schema/Brick#>

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>```bash

# Cluster status

SELECT ?ups ?batterySensornodetool status

WHERE {

  ?ups rdf:type brick:UPS .# Ring topology

  ?batterySensor brick:isPointOf ?ups .nodetool ring

  ?batterySensor rdf:type brick:Battery_Voltage_Sensor .

}# Compaction statistics

ORDER BY ?upsnodetool compactionstats

```

# Table statistics

**Results**: 10 UPS unitsnodetool tablestats telemetry_bldg3.sensor_data


---# Node info

nodetool info

#### Query 3: Find Racks with High Power Consumption

# Performance stats

```sparqlnodetool tpstats

PREFIX brick: <https://brickschema.org/schema/Brick#>```

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

## Analytics Integration

SELECT ?rack ?powerSensor

WHERE {### Data Center-Specific Analytics

  ?rack rdf:type brick:Rack .

  ?powerSensor brick:isPointOf ?rack .**Temperature Monitoring:**

  ?powerSensor rdf:type brick:Power_Sensor .- Time-series analysis of CRAC supply/return temperatures

}- Hot aisle/cold aisle differential monitoring

ORDER BY ?rack- Rack-level thermal mapping

```- Anomaly detection for temperature spikes


**Results**: 40 racks**Power Analysis:**

- UPS load trending

**Combine with Cassandra query** to find racks consuming > 15 kW.- PDU phase balance analysis

- PUE/DCiE calculation

---- Power consumption forecasting

- Peak demand prediction

## Typo-Tolerant Query Examples

**Cooling Efficiency:**

Building 3's action server uses **RapidFuzz** (80% threshold) to handle natural language variations.- CRAC efficiency scoring

- Cooling capacity utilization

### CRAC Unit Queries- Airflow optimization analysis

- Energy consumption per cooling ton

**User Inputs** (all resolve to same sensor):- Return Temperature Index (RTI)

```

"show me crac 1 supply air temperature"   → CRAC_1_Supply_Air_Temperature_Sensor**Alarm Analytics:**

"crac1 supply temp"                        → CRAC_1_Supply_Air_Temperature_Sensor- Alarm frequency analysis

"CRAC  1  supplyairtemperature"           → CRAC_1_Supply_Air_Temperature_Sensor (spacing)- Root cause correlation

"crac1supplytempereture"                   → CRAC_1_Supply_Air_Temperature_Sensor (typos)- Predictive maintenance triggers

```- Threshold optimization

- Mean time between failures (MTBF)

---

### API Examples

### UPS Queries

```python

**User Inputs**:import requests

```

"ups 1 battery charge"                     → UPS_1_Battery_Charge_Level_Sensor# Get CRAC temperature analysis

"ups1 battery level"                       → UPS_1_Battery_Charge_Level_Sensorresponse = requests.post(

"uninterruptible power supply 1 battery"   → UPS_1_Battery_Charge_Level_Sensor    'http://localhost:6001/analytics/run',

"ups1 load percentage"                     → UPS_1_Load_Percentage_Sensor    json={

```        'analysis_type': 'time_series',

        'sensor_id': 'CRAC-A-01-Supply-Temp',

---        'start_time': '2025-10-01T00:00:00Z',

        'end_time': '2025-10-08T23:59:59Z',

### Rack Queries        'aggregation': '1h'

    }

**User Inputs**:)

```

"rack a01 inlet temperature"               → Rack_A01_Inlet_Temperature_Sensor# Calculate PUE

"rack a01 power consumption"               → Rack_A01_Power_Consumption_Sensorresponse = requests.post(

"racka01 inlet temp"                       → Rack_A01_Inlet_Temperature_Sensor    'http://localhost:6001/analytics/run',

```    json={

        'analysis_type': 'pue_calculation',

---        'building_id': 'bldg3',

        'timestamp': '2025-10-08T12:00:00Z'

### Multi-Equipment Queries    }

)

**User Input**: `"compare battery levels across all UPS systems"`

# Detect temperature anomalies

**Resolution**:response = requests.post(

```    'http://localhost:6001/analytics/run',

UPS 1 → UPS_1_Battery_Charge_Level_Sensor (match: 100%)    json={

UPS 2 → UPS_2_Battery_Charge_Level_Sensor (match: 100%)        'analysis_type': 'anomaly_detection',

...        'sensor_id': 'CRAC-A-01-Supply-Temp',

UPS 10 → UPS_10_Battery_Charge_Level_Sensor (match: 100%)        'method': 'isolation_forest',

```        'sensitivity': 0.95

    }

**Action Server** fetches data for all 10 UPS battery sensors in parallel.)


---# Alarm correlation analysis

response = requests.post(

## Docker Compose Configuration    'http://localhost:6001/analytics/run',

    json={

### Building 3 Stack        'analysis_type': 'alarm_correlation',

        'start_time': '2025-10-01T00:00:00Z',

**File**: `docker-compose.bldg3.yml`        'end_time': '2025-10-08T23:59:59Z',

        'equipment_types': ['CRAC', 'UPS', 'PDU']

```yaml    }

services:)

  # Cassandra database

```

  cassandra:

    image: cassandra:4.1## Development

    container_name: cassandra

    ports:### Custom Actions

      - "9042:9042"

    environment:```python

      CASSANDRA_CLUSTER_NAME: "Building3Cluster"# actions/actions.py

      CASSANDRA_DC: "DC1"from typing import Any, Text, Dict, List

      CASSANDRA_RACK: "Rack1"from rasa_sdk import Action, Tracker

      CASSANDRA_ENDPOINT_SNITCH: "GossipingPropertyFileSnitch"from rasa_sdk.executor import CollectingDispatcher

      MAX_HEAP_SIZE: "4G"from .cassandra_client import CassandraClient

      HEAP_NEWSIZE: "800M"

    volumes:class ActionQueryCRACStatus(Action):

      - cassandra_data:/var/lib/cassandra    def name(self) -> Text:

      - ./bldg3/init.cql:/docker-entrypoint-initdb.d/init.cql        return "action_query_crac_status"

    networks:

      - rasa-network    def run(

        self, 

  # PostgreSQL metadata store        dispatcher: CollectingDispatcher,

  postgres:        tracker: Tracker,

    image: postgres:15        domain: Dict[Text, Any]

    container_name: postgres    ) -> List[Dict[Text, Any]]:

    ports:        

      - "5434:5432"        equipment_id = tracker.get_slot("equipment_id")

    environment:        

      POSTGRES_DB: thingsboard        # Connect to Cassandra

      POSTGRES_USER: postgres        client = CassandraClient()

      POSTGRES_PASSWORD: postgres        

    volumes:        # Get recent readings

      - postgres_data:/var/lib/postgresql/data        sensor_uuid = f"uuid-{equipment_id.lower()}-supply-temp"

      - ./bldg3/init_pg.sql:/docker-entrypoint-initdb.d/init.sql        readings = client.get_sensor_data(sensor_uuid, hours_back=1)

    networks:        

      - rasa-network        if readings:

            latest = list(readings)[0]

  # Rasa action server            message = f"{equipment_id} Supply Temperature: {latest.value:.1f} {latest.unit}"

  rasa-action-server-bldg3:        else:

    build:            message = f"No data found for {equipment_id}"

      context: ./rasa-bldg3        

      dockerfile: Dockerfile        dispatcher.utter_message(text=message)

    image: rasa-action-server-bldg3:latest        return []

    container_name: rasa-action-server-bldg3

    ports:class ActionCalculatePUE(Action):

      - "5055:5055"    def name(self) -> Text:

    environment:        return "action_calculate_pue"

      CASSANDRA_HOST: cassandra

      CASSANDRA_PORT: 9042    def run(

      CASSANDRA_KEYSPACE: building3        self,

      PG_HOST: postgres        dispatcher: CollectingDispatcher,

      PG_PORT: 5432        tracker: Tracker,

      PG_DATABASE: thingsboard        domain: Dict[Text, Any]

      PG_USER: postgres    ) -> List[Dict[Text, Any]]:

      PG_PASSWORD: postgres        

      FUSEKI_ENDPOINT: http://fuseki-db:3030/trial/sparql        client = CassandraClient()

      ANALYTICS_URL: http://microservices:6000/analytics/run        pue = client.calculate_pue()

      DECIDER_URL: http://decider-service:6009/decide        

      FILE_SERVER_URL: http://http_server:8080        if pue:

    volumes:            dcit = (1 / pue) * 100

      - ./rasa-bldg3/actions:/app/actions            message = f"Current PUE: {pue:.2f} (DCiE: {dcit:.1f}%)"

      - ./rasa-ui/shared_data:/app/shared_data            

    depends_on:            if pue < 1.5:

      - cassandra                message += " - Excellent efficiency!"

      - postgres            elif pue < 2.0:

      - fuseki-db                message += " - Good efficiency"

      - microservices            else:

    networks:                message += " - Consider optimization"

      - rasa-network        else:

            message = "Unable to calculate PUE at this time"

  # Rasa core        

  rasa-bldg3:        dispatcher.utter_message(text=message)

    build:        return []

      context: ./rasa-bldg3

```

      dockerfile: Dockerfile.rasa

    image: rasa-bldg3:latest### Data Center-Specific Intents

    container_name: rasa-bldg3

    ports:```yaml

      - "5005:5005"# data/nlu.yml

    environment:- intent: query_crac_status

      RASA_ACTION_ENDPOINT: http://rasa-action-server-bldg3:5055/webhook  examples: |

    volumes:    - show me [CRAC unit 1](equipment_id) status

      - ./rasa-bldg3/models:/app/models    - what's the temperature of [CRAC-A-01](equipment_id)

      - ./rasa-bldg3/data:/app/data    - display cooling efficiency for [zone A](zone_name)

      - ./rasa-bldg3/config.yml:/app/config.yml    - how is [CRAC unit 3](equipment_id) performing

    depends_on:

      - rasa-action-server-bldg3- intent: query_ups_status

    networks:  examples: |

      - rasa-network    - show UPS battery levels

    - what's the status of [UPS 2](equipment_id)

  # Fuseki knowledge graph (shared)    - display power load on [UPS-B-01](equipment_id)

  fuseki-db:    - how much charge does [UPS 1](equipment_id) have

    image: secoresearch/fuseki

    container_name: fuseki-db- intent: query_alarms

    ports:  examples: |

      - "3030:3030"    - show all active alarms

    environment:    - what [critical](alarm_severity) alarms do we have

      ADMIN_PASSWORD: admin123    - display [temperature](alarm_type) alarms

      JVM_ARGS: "-Xmx4g"    - show me equipment failure alerts

    volumes:

      - fuseki_data:/fuseki- intent: calculate_pue

      - ./bldg3/trial/dataset:/fuseki-base/databases/trial  examples: |

    networks:    - what's our PUE

      - rasa-network    - calculate power usage effectiveness

    - show me energy efficiency

  # Analytics microservices (shared)    - what's the DCiE

  microservices:```

    build: ./microservices

    container_name: microservices## Testing & Monitoring

    ports:

      - "6001:6000"### Health Checks

    volumes:

      - ./rasa-ui/shared_data:/app/shared_data

```powershell

    networks:# Check Cassandra status

      - rasa-networkdocker-compose -f docker-compose.bldg3.yml exec cassandra nodetool status


  # Decider service (shared)# Check connectivity

  decider-service:docker-compose -f docker-compose.bldg3.yml exec cassandra cqlsh -e "DESCRIBE KEYSPACES"

    build: ./decider-service

    container_name: decider-service# Verify data

    ports:docker-compose -f docker-compose.bldg3.yml exec cassandra cqlsh -e "SELECT COUNT(*) FROM telemetry_bldg3.sensor_data"

      - "6009:6009"

    networks:# Check PostgreSQL (ThingsBoard metadata)

      - rasa-networkdocker-compose -f docker-compose.bldg3.yml exec tb-postgres pg_isready

```

  # HTTP file server (shared)

  http_server:### Performance Testing

    image: python:3.10-slim

    container_name: http_server

```bash

    command: python -m http.server 8080# Cassandra stress test

    working_dir: /datadocker-compose -f docker-compose.bldg3.yml exec cassandra cassandra-stress write n=1000000 -rate threads=50

    ports:

      - "8080:8080"# Monitor performance

    volumes:docker-compose -f docker-compose.bldg3.yml exec cassandra nodetool tpstats

      - ./rasa-ui/shared_data:/datadocker-compose -f docker-compose.bldg3.yml exec cassandra nodetool proxyhistograms

    networks:```

      - rasa-network

## Troubleshooting

  # React frontend (shared)

  rasa-ui:### Common Issues

    build: ./rasa-frontend

    container_name: rasa-ui**Problem: Cassandra fails to start**

    ports:```bash

      - "3000:3000"# Check logs

    environment:docker-compose -f docker-compose.bldg3.yml logs cassandra

      REACT_APP_RASA_URL: http://localhost:5005

    networks:# Common causes:

      - rasa-network# - Insufficient memory (increase Docker RAM to 8GB+)

# - Port conflict on 9042

volumes:# - Corrupted data volume

  cassandra_data:

  postgres_data:# Solution: Reset Cassandra

  fuseki_data:docker-compose -f docker-compose.bldg3.yml down -v

docker volume rm ontobot_cassandra_data

networks:docker-compose -f docker-compose.bldg3.yml up -d cassandra

  rasa-network:```

    driver: bridge

```**Problem: Slow queries**

```bash

---# Check node status

nodetool status

### Starting Building 3

# Monitor compaction

**One-Command Startup**:nodetool compactionstats

```bash

docker compose -f docker-compose.bldg3.yml up -d# Optimize table

```nodetool compact telemetry_bldg3 sensor_data

```

**Service Order**:

1. Cassandra + PostgreSQL start first (5-10 seconds)**Problem: High disk usage**

2. Fuseki, microservices, decider, HTTP server start (parallel)

```bash

3. Action server waits for Cassandra + PostgreSQL + Fuseki# Check disk usage

4. Rasa core waits for action servernodetool tablestats telemetry_bldg3.sensor_data

5. Frontend connects to Rasa

# Clear old snapshots

**Verify Services**:nodetool clearsnapshot

```powershell

# Health checks# Adjust retention (if using TTL)

cqlsh localhost 9042  # Cassandra (cqlsh client required)# Data expires automatically with TTL set

psql -h localhost -p 5434 -U postgres -d thingsboard  # PostgreSQL

```

curl http://localhost:3030/$/ping  # Fuseki

curl http://localhost:5005/version  # Rasa## Related Documentation

curl http://localhost:5055  # Action server

curl http://localhost:6001/health  # Analytics- [Building 1 - ABACWS](/docs/building1_abacws/) - Real university testbed

curl http://localhost:6009/health  # Decider- [Building 2 - Office](/docs/building2_office/) - HVAC optimization

curl http://localhost:8080  # HTTP server- [Cassandra Integration Guide](/docs/cassandra_integration/) - Detailed database guide

curl http://localhost:3000  # Frontend- [Data Center Best Practices](/docs/datacenter_best_practices/) - Operations guide

```- [Multi-Building Support](/docs/multi_building/) - Switching between buildings


---## Support & Resources


## Use Cases & Applications- **Cassandra Documentation**: [cassandra.apache.org](https://cassandra.apache.org/doc/)

- **Data Center Standards**: [Uptime Institute](https://uptimeinstitute.com/)

### 1. Cooling System Optimization- **PUE Guidelines**: [The Green Grid](https://www.thegreengrid.org/)

- **ThingsBoard Documentation**: [thingsboard.io/docs](https://thingsboard.io/docs/)

**Scenario**: Optimize CRAC units to minimize energy while maintaining safe operating temperatures.

---

**Queries**:

```**Building 3 (Data Center)** represents critical infrastructure with:

"show me CRAC 1 supply air temperature for the last 24 hours"- ✅ 597 sensors (CRAC, UPS, PDU, Racks, Alarms)

"compare efficiency across all CRAC units"- ✅ Cassandra high-availability storage

"find racks with inlet temperature above 27°C"- ✅ Real-time alarm monitoring

"run optimization analysis on CRAC power consumption"- ✅ Cooling system optimization

```- ✅ Power distribution tracking

- ✅ PUE/DCiE efficiency metrics

**Analytics**:
- Trend analysis on CRAC efficiency
- Correlation between rack load and cooling demand
- Forecasting cooling requirements
- What-if scenarios for setpoint changes

**Expected Outcome**: 10-20% energy savings through dynamic setpoint adjustment and load balancing.

---

### 2. Power Distribution Monitoring

**Scenario**: Ensure reliable power distribution and prevent overloads.

**Queries**:
```
"show me UPS 1 load percentage for the last week"
"find PDUs with load above 80%"
"compare battery charge levels across all UPS systems"
"run anomaly detection on circuit breaker status"
```

**Analytics**:
- Load trend analysis
- Battery health prediction
- Anomaly detection for voltage fluctuations
- Threshold recommendations for alerts

**Expected Outcome**: Prevent downtime through predictive maintenance and proactive load balancing.

---

### 3. Hot Spot Detection

**Scenario**: Identify thermal hot spots in server racks.

**Queries**:
```
"show me rack outlet temperatures across all racks"
"find racks with delta T (outlet - inlet) > 15°C"
"compare rack temperatures in hot aisle vs cold aisle"
"run clustering analysis on rack temperatures"
```

**Analytics**:
- Temperature variance analysis
- Correlation between rack power and temperature
- Pattern recognition for hot spot formation
- Comparative analysis across aisles

**Expected Outcome**: Improve airflow management and prevent equipment overheating.

---

### 4. Uptime & Reliability Tracking

**Scenario**: Monitor critical infrastructure for 99.982% uptime (Tier III target).

**Queries**:
```
"show me alarm status across all CRAC units"
"find UPS systems with battery charge below 90%"
"detect water leak alarms in the last 24 hours"
"run anomaly prediction on power systems"
```

**Analytics**:
- Real-time anomaly detection
- Predictive alerts for potential failures
- Classification of alarm severity
- Reliability metrics (MTBF, MTTR)

**Expected Outcome**: Achieve 99.982% uptime through proactive monitoring and rapid response.

---

## Performance Characteristics

### Query Response Times

**Cassandra Queries** (single sensor):

 | Time Range | Records | Response Time | 
 | ------------ | --------- | --------------- | 
 | 1 hour | 120 | 20-40 ms | 
 | 24 hours | 2,880 | 50-100 ms | 
 | 1 week | 20,160 | 150-300 ms | 
 | 1 month | 86,400 | 400-800 ms | 

**Multi-Sensor Queries** (10 sensors):

 | Time Range | Total Records | Response Time | 
 | ------------ | --------------- | --------------- | 
 | 1 hour | 1,200 | 100-200 ms | 
 | 24 hours | 28,800 | 300-600 ms | 
 | 1 week | 201,600 | 1-2 seconds | 

**Analytics Processing**:

 | Analysis Type | Data Points | Processing Time | 
 | --------------- | ------------- | ----------------- | 
 | Summary statistics | 2,880 | <1 second | 
 | Trend analysis | 20,160 | 2-4 seconds | 
 | Anomaly detection | 86,400 | 6-10 seconds | 
 | Forecasting (ARIMA) | 20,160 | 12-20 seconds | 

---

### Resource Usage

**Cassandra Container**:
- CPU: 10-20% idle, 50-80% under load
- Memory: 4-8 GB (with 4 GB heap)
- Disk I/O: 20-100 MB/s during writes

**PostgreSQL Container**:
- CPU: 2-5% (metadata only)
- Memory: 256-512 MB
- Disk I/O: <10 MB/s

**Action Server**:
- CPU: 2-5% idle, 15-30% during analytics
- Memory: 500 MB - 1 GB
- Concurrent requests: 10-20

**Total Stack**:
- CPU: 6 cores recommended (8 cores ideal)
- Memory: 24 GB recommended (16 GB minimum)
- Disk: 100 GB for 2 years of data (Cassandra RF=3)

---

## Troubleshooting

### Issue 1: Cassandra Connection Failed

**Symptoms**:
- Action server logs: `cassandra.cluster.NoHostAvailable`
- Frontend queries fail silently

**Solutions**:
1. **Check Cassandra is running**:
   ```bash
   docker ps | grep cassandra
   ```

2. **Verify Cassandra is ready** (takes 30-60 seconds to start):
   ```bash
   docker logs cassandra | grep "Starting listening for CQL clients"
   ```

3. **Test connection from host**:
   ```bash
   cqlsh localhost 9042
   # Should see: Connected to Building3Cluster
   ```

4. **Check action server environment**:
   ```bash
   docker exec rasa-action-server-bldg3 env | grep CASSANDRA
   # Should show: CASSANDRA_HOST=cassandra, CASSANDRA_PORT=9042
   ```

---

### Issue 2: Slow Query Performance

**Symptoms**:
- Queries take >5 seconds for small time ranges
- Dashboard feels sluggish

**Solutions**:
1. **Check partition key usage** (must always specify sensor_id):
   ```cql
   -- BAD (full table scan)
   SELECT * FROM sensor_data WHERE timestamp > '2025-10-31';
   
   -- GOOD (partition-aware)
   SELECT * FROM sensor_data
   WHERE sensor_id = 'crac1_supply_temp'
   AND timestamp > '2025-10-31 00:00:00';
   ```

2. **Enable tracing**:
   ```cql
   TRACING ON;
   SELECT * FROM sensor_data WHERE sensor_id = 'crac1_supply_temp' AND timestamp > '2025-10-31';
   -- Review query plan
   ```

3. **Adjust compaction strategy** (if needed):
   ```cql
   ALTER TABLE sensor_data
   WITH compaction = {
     'class': 'TimeWindowCompactionStrategy',
     'compaction_window_size': 1,
     'compaction_window_unit': 'DAYS'
   };
   ```

4. **Increase Cassandra memory**:
   ```yaml
   # docker-compose.bldg3.yml
   environment:
     MAX_HEAP_SIZE: "8G"  # Increase from 4G
     HEAP_NEWSIZE: "1600M"
   ```

---

### Issue 3: Alarm Data Not Appearing

**Symptoms**:
- Alarm status sensors show no data
- Alarm queries return empty results

**Solutions**:
1. **Verify alarm data exists**:
   ```cql
   SELECT * FROM sensor_data
   WHERE sensor_id = 'crac1_alarm'
   AND timestamp > '2025-10-31'
   LIMIT 10;
   ```

2. **Check alarm sensor names**:
   ```bash
   docker exec rasa-action-server-bldg3 cat /app/actions/sensor_list.txt | grep Alarm
   ```

3. **Rebuild sensor lookup**:
   ```bash
   docker exec rasa-action-server-bldg3 python /app/actions/update_sensor_mappings.py
   ```

4. **Test fuzzy matching**:
   ```python
   from rapidfuzz import fuzz
   score = fuzz.ratio("crac1 alarm", "CRAC_1_Alarm_Status_Sensor")
   print(score)  # Should be > 80
   ```

---

## Best Practices

### 1. Query Optimization

**DO**:
- ✅ Always specify partition key (sensor_id)
- ✅ Use clustering key for time range filtering
- ✅ Limit result size with LIMIT clause
- ✅ Use ALLOW FILTERING sparingly (or not at all)

**DON'T**:
- ❌ Query without partition key (full cluster scan)
- ❌ Use secondary indexes on high-cardinality columns
- ❌ Fetch more data than needed
- ❌ Run analytics on raw data for long time ranges

---

### 2. Typo-Tolerant Queries

**DO**:
- ✅ Use natural language: "crac 1 supply temperature"
- ✅ Include equipment type: "CRAC", "UPS", "Rack"
- ✅ Specify equipment ID: "CRAC 1", "UPS 5", "Rack A01"
- ✅ Accept minor typos: "tempereture", "battry"

**DON'T**:
- ❌ Assume exact sensor names required
- ❌ Mix multiple equipment types without context
- ❌ Use ambiguous terms without IDs

---

### 3. High-Availability Best Practices

**DO**:
- ✅ Use replication factor 3 (survives 2 node failures)
- ✅ Monitor Cassandra cluster health regularly
- ✅ Set up continuous backups (nodetool snapshot)
- ✅ Test failover scenarios periodically

**DON'T**:
- ❌ Use replication factor 1 in production
- ❌ Ignore node failure alerts
- ❌ Skip testing disaster recovery procedures

---

## Related Documentation

- **[Building 1 (ABACWS)](building1_abacws.md)**: Real testbed with 680 sensors
- **[Building 2 (Office)](building2_office.md)**: Commercial workspace with TimescaleDB
- **[Database Integration](database_integration.md)**: Multi-database support guide
- **[Analytics API](analytics_api.md)**: 30+ analysis types reference
- **[Multi-Building Support](multi_building.md)**: Switching between buildings

---

**Building 3** - 597 sensors ensuring data center uptime and reliability. 💾⚡🔒
