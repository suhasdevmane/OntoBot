---
title: Database Integration Guide
layout: post
category: docs
permalink: /docs/database_integration/
date: 2025-10-08
---

# Database Integration Guide

# Database Integration Guide

**Complete guide to integrating MySQL, TimescaleDB, and Cassandra databases with OntoBot's action server and analytics services.**

OntoBot supports three different database systems, each optimized for specific building types and use cases. This guide covers MySQL, TimescaleDB, and Cassandra integration.

---

## Overview

## Overview

 | Database | Building | Use Case | Strengths | Best For | 

OntoBot supports **three database systems**, each optimized for specific building types and operational requirements. The action server provides a unified abstraction layer, allowing identical query patterns across all database types.|----------|----------|----------|-----------|----------|

 | **MySQL 8.0** | Building 1 | Traditional relational | ACID compliance, mature tooling | Structured data, joins, transactions | 

### Database Comparison| **TimescaleDB 2.11** | Building 2 | Time-series | Automatic partitioning, compression | HVAC analytics, energy monitoring |

 | **Cassandra 4.1** | Building 3 | Distributed NoSQL | High availability, write throughput | Critical infrastructure, scalability | 

 | Feature | MySQL 8.0 | TimescaleDB 2.11 | Cassandra 4.1 | 

 | --------- | ----------- | ------------------ | --------------- | ---

 | **Type** | Relational (RDBMS) | Time-Series (PostgreSQL) | Distributed NoSQL | 

 | **Building** | Building 1 (ABACWS) | Building 2 (Office) | Building 3 (Data Center) | ## MySQL Integration (Building 1)

 | **Port** | 3307 (host), 3306 (container) | 5433 (host), 5432 (container) | 9042 (both) | 

 | **Best For** | Structured data, joins | Time-series analytics | High availability, writes | ### Configuration

 | **ACID** | ✅ Full ACID compliance | ✅ Full ACID compliance | ⚠️ Tunable consistency | 

 | **Scalability** | Vertical (single node) | Vertical (single node) | Horizontal (multi-node) | ```yaml

 | **Query Language** | SQL | SQL (+ time-series functions) | CQL (Cassandra Query Language) | # docker-compose.bldg1.yml

 | **Indexes** | B-tree, full-text | B-tree, BRIN, hypertables | Partition key, clustering | mysqlserver:

 | **Compression** | ❌ No automatic compression | ✅ Automatic compression (10:1) | ✅ Automatic compression | image: mysql:8.0

 | **Replication** | Master-slave | Streaming replication | Multi-datacenter replication | ports:

 | **Typical Use Case** | Transactional systems | Monitoring dashboards | Mission-critical IoT | - "3307:3306"

  environment:

---    MYSQL_ROOT_PASSWORD: password

    MYSQL_DATABASE: telemetry

## MySQL Integration (Building 1)    MYSQL_USER: rasa_user

    MYSQL_PASSWORD: rasa_pass

### Configuration  volumes:

    - mysql_data:/var/lib/mysql

**Docker Compose** (`docker-compose.bldg1.yml`):  command: --default-authentication-plugin=mysql_native_password

```

```yaml

mysqlserver:### Schema Design

  image: mysql:8.0

  container_name: mysqlserver

```sql

  ports:-- Create telemetry database

    - "3307:3306"CREATE DATABASE IF NOT EXISTS telemetry

  environment:  CHARACTER SET utf8mb4

    MYSQL_ROOT_PASSWORD: password  COLLATE utf8mb4_unicode_ci;

    MYSQL_DATABASE: telemetry

    MYSQL_USER: rasa_userUSE telemetry;

    MYSQL_PASSWORD: rasa_pass

    TZ: UTC-- Sensor readings (time-series data)

  volumes:CREATE TABLE sensor_readings (

    - mysql_data:/var/lib/mysql    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    - ./bldg1/init.sql:/docker-entrypoint-initdb.d/init.sql    sensor_uuid VARCHAR(36) NOT NULL,

  command: >    sensor_name VARCHAR(255),

    --default-authentication-plugin=mysql_native_password    zone_id VARCHAR(10),

    --max_connections=500    timestamp DATETIME(6) NOT NULL,

    --innodb_buffer_pool_size=2G    value DOUBLE NOT NULL,

    --innodb_log_file_size=512M    unit VARCHAR(20),

  networks:    sensor_type VARCHAR(50),

    - rasa-network    quality_flag TINYINT DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

rasa-action-server-bldg1:    

  environment:    INDEX idx_sensor_time (sensor_uuid, timestamp),

    DB_HOST: mysqlserver    INDEX idx_zone_time (zone_id, timestamp),

    DB_PORT: 3306    INDEX idx_type_time (sensor_type, timestamp),

    DB_NAME: telemetry    INDEX idx_timestamp (timestamp)

    DB_USER: rasa_user) ENGINE=InnoDB 

    DB_PASSWORD: rasa_pass  ROW_FORMAT=COMPRESSED

```  COMMENT='Time-series sensor telemetry data';


----- Sensor metadata

CREATE TABLE sensors (

### Schema Design    uuid VARCHAR(36) PRIMARY KEY,

    name VARCHAR(255) NOT NULL,

**Main Table**: `ts_kv`    zone_id VARCHAR(10) NOT NULL,

    sensor_type VARCHAR(50) NOT NULL,

```sql    unit VARCHAR(20),

CREATE DATABASE IF NOT EXISTS telemetry    location_description TEXT,

  CHARACTER SET utf8mb4    brick_class VARCHAR(100),

  COLLATE utf8mb4_unicode_ci;    metadata JSON,

    last_reading DATETIME(6),

USE telemetry;    last_value DOUBLE,

    active BOOLEAN DEFAULT TRUE,

CREATE TABLE ts_kv (    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    entity_id VARCHAR(36) NOT NULL,    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    entity_type VARCHAR(50) NOT NULL DEFAULT 'DEVICE',    

    key_name VARCHAR(255) NOT NULL,    UNIQUE KEY unique_name (name),

    ts BIGINT(20) NOT NULL,    INDEX idx_zone (zone_id),

    bool_v TINYINT(1) DEFAULT NULL,    INDEX idx_type (sensor_type),

    str_v VARCHAR(10000) DEFAULT NULL,    INDEX idx_active (active)

    long_v BIGINT(20) DEFAULT NULL,) ENGINE=InnoDB;

    dbl_v DOUBLE DEFAULT NULL,

    json_v JSON DEFAULT NULL,-- Zone information

    PRIMARY KEY (entity_id, key_name, ts),CREATE TABLE zones (

    KEY idx_ts (ts),    zone_id VARCHAR(10) PRIMARY KEY,

    KEY idx_key_name (key_name, ts)    floor INT NOT NULL,

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;    building VARCHAR(50) NOT NULL DEFAULT 'Building1',

```    zone_type VARCHAR(50),

    area_sqm DOUBLE,

**Key Design Choices**:    occupancy_capacity INT,

- **Composite Primary Key**: (entity_id, key_name, ts) ensures unique sensor readings    description TEXT,

- **Timestamp as BIGINT**: Milliseconds since epoch for precision    metadata JSON,

- **Multi-type Values**: `bool_v`, `str_v`, `long_v`, `dbl_v`, `json_v` for flexibility    

- **Indexes**: Speed up queries by timestamp and key_name    INDEX idx_floor (floor),

    INDEX idx_building (building)

---) ENGINE=InnoDB;


### Sample Data-- Alarm history

CREATE TABLE alarm_history (

**Insert Temperature Reading**:    id BIGINT AUTO_INCREMENT PRIMARY KEY,

```sql    alarm_id VARCHAR(36) NOT NULL,

INSERT INTO ts_kv (entity_id, entity_type, key_name, ts, dbl_v)    sensor_uuid VARCHAR(36),

VALUES (    timestamp DATETIME(6) NOT NULL,

    'a1b2c3d4-e5f6-7890-abcd-ef1234567890',    severity ENUM('INFO', 'WARNING', 'CRITICAL') NOT NULL,

    'DEVICE',    message TEXT,

    'Air_Temperature_Sensor_5.01',    acknowledged BOOLEAN DEFAULT FALSE,

    1730379600000,  -- 2025-10-31 10:00:00 UTC in milliseconds    acknowledged_by VARCHAR(100),

    21.5    acknowledged_at DATETIME(6),

);    

```    INDEX idx_sensor_time (sensor_uuid, timestamp),

    INDEX idx_timestamp (timestamp),

**Insert Multiple Sensors**:    INDEX idx_severity (severity),

```sql    INDEX idx_acknowledged (acknowledged)

INSERT INTO ts_kv (entity_id, entity_type, key_name, ts, dbl_v) VALUES) ENGINE=InnoDB;

('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'DEVICE', 'Air_Temperature_Sensor_5.01', 1730379600000, 21.5),```

('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'DEVICE', 'CO2_Level_Sensor_5.01', 1730379600000, 650.0),

('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'DEVICE', 'Humidity_Sensor_5.01', 1730379600000, 45.2),### Python Client

('a1b2c3d4-e5f6-7890-abcd-ef1234567890', 'DEVICE', 'TVOC_Sensor_5.01', 1730379600000, 120.0);

```python

# mysql_client.py

---import mysql.connector

from mysql.connector import pooling

### Action Server Integrationfrom datetime import datetime, timedelta

from typing import List, Dict, Optional

**Python Connection** (`rasa-bldg1/actions/db_connector.py`):import os


```pythonclass MySQLClient:

import mysql.connector    def __init__(self):

from mysql.connector import pooling        self.config = {

from datetime import datetime            'host': os.getenv('DB_HOST', 'mysqlserver'),

            'port': int(os.getenv('DB_PORT', 3306)),

class MySQLConnector:            'database': os.getenv('DB_NAME', 'telemetry'),

    def __init__(self, host, port, database, user, password):            'user': os.getenv('DB_USER', 'root'),

        self.pool = mysql.connector.pooling.MySQLConnectionPool(            'password': os.getenv('DB_PASSWORD', 'password'),

            pool_name="ontobot_pool",            'pool_name': 'ontobot_pool',

            pool_size=10,            'pool_size': 10,

            pool_reset_session=True,            'pool_reset_session': True

            host=host,        }

            port=port,        self.pool = mysql.connector.pooling.MySQLConnectionPool(**self.config)

            database=database,    

            user=user,    def get_connection(self):

            password=password        """Get connection from pool"""

        )        return self.pool.get_connection()

        

    def get_sensor_data(self, sensor_name, start_time, end_time):    def get_recent_reading(self, sensor_uuid: str) -> Optional[Dict]:

        """        """Get most recent reading for a sensor"""

        Fetch sensor data for a given time range.        conn = self.get_connection()

                cursor = conn.cursor(dictionary=True)

        Args:        

            sensor_name: Sensor key_name (e.g., "Air_Temperature_Sensor_5.01")        query = """

            start_time: datetime object            SELECT sr.timestamp, sr.value, sr.unit, s.name, s.zone_id

            end_time: datetime object            FROM sensor_readings sr

                    JOIN sensors s ON sr.sensor_uuid = s.uuid

        Returns:            WHERE sr.sensor_uuid = %s

            List of tuples: [(timestamp, value), ...]            ORDER BY sr.timestamp DESC

        """            LIMIT 1

        connection = self.pool.get_connection()        """

        cursor = connection.cursor()        cursor.execute(query, (sensor_uuid,))

                result = cursor.fetchone()

        # Convert datetime to milliseconds        

        start_ms = int(start_time.timestamp() * 1000)        cursor.close()

        end_ms = int(end_time.timestamp() * 1000)        conn.close()

                return result

        query = """    

        SELECT ts, dbl_v    def get_time_series(

        FROM ts_kv        self, 

        WHERE key_name = %s        sensor_uuid: str, 

          AND ts >= %s        start_time: datetime, 

          AND ts <= %s        end_time: datetime,

        ORDER BY ts ASC        aggregation: Optional[str] = None

        """    ) -> List[Dict]:

                """Get time-series data with optional aggregation"""

        cursor.execute(query, (sensor_name, start_ms, end_ms))        conn = self.get_connection()

        results = cursor.fetchall()        cursor = conn.cursor(dictionary=True)

                

        cursor.close()        if aggregation:

        connection.close()            # Aggregated query (e.g., '1h', '15m', '1d')

                    query = f"""

        # Convert milliseconds back to datetime                SELECT 

        return [                    DATE_FORMAT(timestamp, %s) AS time_bucket,

            (datetime.fromtimestamp(ts / 1000), value)                    AVG(value) AS avg_value,

            for ts, value in results                    MIN(value) AS min_value,

        ]                    MAX(value) AS max_value,

```                    COUNT(*) AS count

                FROM sensor_readings

**Usage in Action**:                WHERE sensor_uuid = %s

```python                  AND timestamp BETWEEN %s AND %s

from actions.db_connector import MySQLConnector                GROUP BY time_bucket

import os                ORDER BY time_bucket

            """

db = MySQLConnector(            time_format = self._get_mysql_time_format(aggregation)

    host=os.getenv("DB_HOST", "mysqlserver"),            cursor.execute(query, (time_format, sensor_uuid, start_time, end_time))

    port=int(os.getenv("DB_PORT", 3306)),        else:

    database=os.getenv("DB_NAME", "telemetry"),            # Raw data

    user=os.getenv("DB_USER", "rasa_user"),            query = """

    password=os.getenv("DB_PASSWORD", "rasa_pass")                SELECT timestamp, value, unit

)                FROM sensor_readings

                WHERE sensor_uuid = %s

# Fetch last 24 hours of temperature data                  AND timestamp BETWEEN %s AND %s

from datetime import datetime, timedelta                ORDER BY timestamp

end_time = datetime.now()            """

start_time = end_time - timedelta(hours=24)            cursor.execute(query, (sensor_uuid, start_time, end_time))

        

data = db.get_sensor_data("Air_Temperature_Sensor_5.01", start_time, end_time)        results = cursor.fetchall()

# data = [(datetime(2025,10,31,10,0,0), 21.5), ...]        cursor.close()

```        conn.close()

        return results

---    

    def get_zone_statistics(self, zone_id: str, sensor_type: str, hours: int = 24) -> Dict:

### Query Optimization        """Get aggregated statistics for a zone"""

        conn = self.get_connection()

**1. Use Indexes Effectively**:        cursor = conn.cursor(dictionary=True)

```sql        

-- Good: Uses index on (key_name, ts)        query = """

SELECT ts, dbl_v            SELECT 

FROM ts_kv                s.zone_id,

WHERE key_name = 'Air_Temperature_Sensor_5.01'                COUNT(DISTINCT sr.sensor_uuid) AS sensor_count,

  AND ts >= 1730293200000                AVG(sr.value) AS avg_value,

  AND ts <= 1730379600000;                MIN(sr.value) AS min_value,

                MAX(sr.value) AS max_value,

-- Bad: Full table scan                STDDEV(sr.value) AS stddev_value,

SELECT ts, dbl_v                MAX(sr.timestamp) AS last_updated

FROM ts_kv            FROM sensor_readings sr

WHERE dbl_v > 20.0;  -- No index on dbl_v            JOIN sensors s ON sr.sensor_uuid = s.uuid

```            WHERE s.zone_id = %s

              AND s.sensor_type = %s

**2. Batch Inserts**:              AND sr.timestamp >= DATE_SUB(NOW(), INTERVAL %s HOUR)

```python            GROUP BY s.zone_id

# Good: Batch insert (much faster)        """

data = [        cursor.execute(query, (zone_id, sensor_type, hours))

    ('entity1', 'DEVICE', 'temp', 1730379600000, 21.5),        result = cursor.fetchone()

    ('entity1', 'DEVICE', 'temp', 1730379660000, 21.6),        

    # ... 1000 more rows        cursor.close()

]        conn.close()

        return result or {}

cursor.executemany(    

    "INSERT INTO ts_kv (entity_id, entity_type, key_name, ts, dbl_v) VALUES (%s, %s, %s, %s, %s)",    def insert_reading(self, sensor_uuid: str, value: float, timestamp: datetime = None):

    data        """Insert new sensor reading"""

)        if timestamp is None:

            timestamp = datetime.now()

# Bad: Individual inserts        

for row in data:        conn = self.get_connection()

    cursor.execute("INSERT INTO ts_kv ...", row)        cursor = conn.cursor()

```        

        query = """

**3. Partition Large Tables** (for production):            INSERT INTO sensor_readings (sensor_uuid, timestamp, value)

```sql            VALUES (%s, %s, %s)

-- Partition by year        """

ALTER TABLE ts_kv        cursor.execute(query, (sensor_uuid, timestamp, value))

PARTITION BY RANGE (YEAR(FROM_UNIXTIME(ts/1000))) (        

    PARTITION p2024 VALUES LESS THAN (2025),        # Update sensor metadata

    PARTITION p2025 VALUES LESS THAN (2026),        update_query = """

    PARTITION p2026 VALUES LESS THAN (2027),            UPDATE sensors 

    PARTITION p_future VALUES LESS THAN MAXVALUE            SET last_reading = %s, last_value = %s 

);            WHERE uuid = %s

```        """

        cursor.execute(update_query, (timestamp, value, sensor_uuid))

---        

        conn.commit()

## TimescaleDB Integration (Building 2)        cursor.close()

        conn.close()

### Configuration    

    def _get_mysql_time_format(self, aggregation: str) -> str:

**Docker Compose** (`docker-compose.bldg2.yml`):        """Convert aggregation string to MySQL DATE_FORMAT"""

        formats = {

```yaml            '1m': '%Y-%m-%d %H:%i:00',

timescaledb:            '5m': '%Y-%m-%d %H:%i:00',

  image: timescale/timescaledb:latest-pg15            '15m': '%Y-%m-%d %H:%i:00',

  container_name: timescaledb            '1h': '%Y-%m-%d %H:00:00',

  ports:            '1d': '%Y-%m-%d 00:00:00'

    - "5433:5432"        }

  environment:        return formats.get(aggregation, '%Y-%m-%d %H:%i:00')

    POSTGRES_DB: building2

```

    POSTGRES_USER: postgres

    POSTGRES_PASSWORD: postgres### Optimization Tips

    PGDATA: /var/lib/postgresql/data/pgdata

  volumes:```sql

    - timescaledb_data:/var/lib/postgresql/data-- Partition by month for large tables

    - ./bldg2/init.sql:/docker-entrypoint-initdb.d/init.sqlALTER TABLE sensor_readings

  networks:PARTITION BY RANGE (YEAR(timestamp) * 100 + MONTH(timestamp)) (

    - rasa-network    PARTITION p202310 VALUES LESS THAN (202311),

    PARTITION p202311 VALUES LESS THAN (202312),

rasa-action-server-bldg2:    PARTITION p202312 VALUES LESS THAN (202401),

  environment:    PARTITION p_future VALUES LESS THAN MAXVALUE

    DB_HOST: timescaledb);

    DB_PORT: 5432

    DB_NAME: building2-- Add covering indexes

    DB_USER: postgresCREATE INDEX idx_covering ON sensor_readings(sensor_uuid, timestamp) 

    DB_PASSWORD: postgresINCLUDE (value, unit);

```

-- Enable query cache (if appropriate)

---SET GLOBAL query_cache_type = 1;

SET GLOBAL query_cache_size = 268435456;  -- 256MB

### Schema Design (Hypertables)

-- Optimize table regularly

**Main Table**: `sensor_data`OPTIMIZE TABLE sensor_readings;


```sql-- Analyze for better query plans

CREATE TABLE sensor_data (ANALYZE TABLE sensor_readings;

    id SERIAL,```

    sensor_id VARCHAR(100) NOT NULL,

    sensor_name VARCHAR(255) NOT NULL,---

    sensor_type VARCHAR(100) NOT NULL,

    reading_value NUMERIC(10,2) NOT NULL,## TimescaleDB Integration (Building 2)

    reading_unit VARCHAR(20),

    timestamp TIMESTAMP NOT NULL,### Configuration

    zone_id VARCHAR(50),

    equipment_id VARCHAR(50),```yaml

    PRIMARY KEY (id, timestamp)# docker-compose.bldg2.yml

);timescale:

  image: timescale/timescaledb:2.11.0-pg15

-- Convert to hypertable (automatic time-based partitioning)  ports:

SELECT create_hypertable(    - "5433:5432"

    'sensor_data',  environment:

    'timestamp',    POSTGRES_DB: telemetry_bldg2

    chunk_time_interval => INTERVAL '1 day'    POSTGRES_USER: postgres

);    POSTGRES_PASSWORD: postgres

    TIMESCALEDB_TELEMETRY: off

-- Create indexes for fast queries  volumes:

CREATE INDEX idx_sensor_name_ts ON sensor_data (sensor_name, timestamp DESC);    - timescale_data:/var/lib/postgresql/data

CREATE INDEX idx_sensor_type_ts ON sensor_data (sensor_type, timestamp DESC);  command: postgres -c shared_preload_libraries=timescaledb -c max_connections=200

CREATE INDEX idx_zone_id_ts ON sensor_data (zone_id, timestamp DESC);```

CREATE INDEX idx_equipment_id_ts ON sensor_data (equipment_id, timestamp DESC);

```### Schema Design


**Key Features**:```sql

- **Hypertable**: Automatically partitions data into 1-day chunks-- Create database

- **Compression**: Compress chunks older than 7 days (10:1 ratio)CREATE DATABASE telemetry_bldg2;

- **Retention**: Auto-delete data older than 2 years\c telemetry_bldg2

- **Continuous Aggregates**: Pre-computed hourly/daily summaries

-- Enable TimescaleDB

---CREATE EXTENSION IF NOT EXISTS timescaledb;


### TimescaleDB Advanced Features-- Create sensor readings table

CREATE TABLE sensor_readings (

**1. Enable Compression**:    time TIMESTAMPTZ NOT NULL,

```sql    sensor_id TEXT NOT NULL,

ALTER TABLE sensor_data SET (    sensor_type TEXT NOT NULL,

    timescaledb.compress,    zone_id TEXT,

    timescaledb.compress_segmentby = 'sensor_name',    equipment_id TEXT,

    timescaledb.compress_orderby = 'timestamp DESC'    value DOUBLE PRECISION NOT NULL,

);    unit TEXT,

    quality_flag INTEGER DEFAULT 0,

-- Compress data older than 7 days    metadata JSONB

SELECT add_compression_policy('sensor_data', INTERVAL '7 days'););

```

-- Convert to hypertable (partitioned by time)

**2. Continuous Aggregates** (pre-computed hourly averages):SELECT create_hypertable('sensor_readings', 'time', chunk_time_interval => INTERVAL '1 day');

```sql

CREATE MATERIALIZED VIEW sensor_data_hourly-- Create indexes

WITH (timescaledb.continuous) ASCREATE INDEX idx_sensor_time ON sensor_readings (sensor_id, time DESC);

SELECT CREATE INDEX idx_zone_time ON sensor_readings (zone_id, time DESC) WHERE zone_id IS NOT NULL;

    sensor_name,CREATE INDEX idx_equipment_time ON sensor_readings (equipment_id, time DESC) WHERE equipment_id IS NOT NULL;

    time_bucket('1 hour', timestamp) AS hour,CREATE INDEX idx_type_time ON sensor_readings (sensor_type, time DESC);

    AVG(reading_value) AS avg_value,

    MAX(reading_value) AS max_value,-- Enable compression (90%+ savings)

    MIN(reading_value) AS min_value,ALTER TABLE sensor_readings SET (

    COUNT(*) AS sample_count    timescaledb.compress,

FROM sensor_data    timescaledb.compress_segmentby = 'sensor_id, sensor_type',

GROUP BY sensor_name, hour;    timescaledb.compress_orderby = 'time DESC'

);

-- Automatically refresh every hour

SELECT add_continuous_aggregate_policy(-- Add compression policy (compress after 7 days)

    'sensor_data_hourly',SELECT add_compression_policy('sensor_readings', INTERVAL '7 days');

    start_offset => INTERVAL '3 hours',

    end_offset => INTERVAL '1 hour',-- Add retention policy (drop after 1 year)

    schedule_interval => INTERVAL '1 hour'SELECT add_retention_policy('sensor_readings', INTERVAL '1 year');

);

```-- Create continuous aggregates (pre-computed rollups)

CREATE MATERIALIZED VIEW sensor_readings_hourly

**3. Data Retention Policy**:WITH (timescaledb.continuous) AS

```sql
SELECT 

-- Delete data older than 2 years    time_bucket('1 hour', time) AS bucket,

SELECT add_retention_policy('sensor_data', INTERVAL '2 years');    sensor_id,

```    sensor_type,

    zone_id,

---    equipment_id,

    AVG(value) AS avg_value,

### Action Server Integration    MIN(value) AS min_value,

    MAX(value) AS max_value,

**Python Connection** (`rasa-bldg2/actions/db_connector.py`):    STDDEV(value) AS stddev_value,

    COUNT(*) AS reading_count

```python
FROM sensor_readings

import psycopg2GROUP BY bucket, sensor_id, sensor_type, zone_id, equipment_id;

from psycopg2 import pool

from datetime import datetime-- Refresh policy for continuous aggregate

SELECT add_continuous_aggregate_policy('sensor_readings_hourly',

class TimescaleDBConnector:    start_offset => INTERVAL '3 hours',

    def __init__(self, host, port, database, user, password):    end_offset => INTERVAL '1 hour',

        self.pool = psycopg2.pool.SimpleConnectionPool(    schedule_interval => INTERVAL '1 hour');

            minconn=1,```

            maxconn=10,

            host=host,### Python Client

            port=port,

            database=database,```python

            user=user,# timescale_client.py

            password=passwordimport psycopg2

        )from psycopg2.extras import RealDictCursor, execute_values

    from datetime import datetime, timedelta

    def get_sensor_data(self, sensor_name, start_time, end_time):from typing import List, Dict, Optional

        """import os

        Fetch sensor data for a given time range.

        class TimescaleClient:

        Args:    def __init__(self):

            sensor_name: Sensor name (e.g., "Zone_101_Temperature_Sensor")        self.config = {

            start_time: datetime object            'host': os.getenv('DB_HOST', 'timescale'),

            end_time: datetime object            'port': int(os.getenv('DB_PORT', 5432)),

                    'database': os.getenv('DB_NAME', 'telemetry_bldg2'),

        Returns:            'user': os.getenv('DB_USER', 'postgres'),

            List of tuples: [(timestamp, value), ...]            'password': os.getenv('DB_PASSWORD', 'postgres')

        """        }

        connection = self.pool.getconn()        self.conn = None

        cursor = connection.cursor()    

            def connect(self):

        query = """        """Establish database connection"""

        SELECT timestamp, reading_value        if self.conn is None or self.conn.closed:

        FROM sensor_data            self.conn = psycopg2.connect(**self.config)

        WHERE sensor_name = %s        return self.conn

          AND timestamp >= %s    

          AND timestamp <= %s    def get_time_series(

        ORDER BY timestamp ASC        self,

        """        sensor_id: str,

                start_time: datetime,

        cursor.execute(query, (sensor_name, start_time, end_time))        end_time: datetime,

        results = cursor.fetchall()        bucket_size: str = '1 hour'

            ) -> List[Dict]:

        cursor.close()        """Get time-bucketed data"""

        self.pool.putconn(connection)        conn = self.connect()

                cursor = conn.cursor(cursor_factory=RealDictCursor)

        return results        

            query = """

    def get_hourly_aggregates(self, sensor_name, start_time, end_time):            SELECT 

        """Use continuous aggregate for faster queries."""                time_bucket(%s, time) AS bucket,

        connection = self.pool.getconn()                AVG(value) AS avg_value,

        cursor = connection.cursor()                MIN(value) AS min_value,

                        MAX(value) AS max_value,

        query = """                COUNT(*) AS count

        SELECT hour, avg_value, max_value, min_value            FROM sensor_readings

        FROM sensor_data_hourly            WHERE sensor_id = %s

        WHERE sensor_name = %s              AND time BETWEEN %s AND %s

          AND hour >= %s            GROUP BY bucket

          AND hour <= %s            ORDER BY bucket

        ORDER BY hour ASC        """

        """        cursor.execute(query, (bucket_size, sensor_id, start_time, end_time))

                results = cursor.fetchall()

        cursor.execute(query, (sensor_name, start_time, end_time))        cursor.close()

        results = cursor.fetchall()        return results

            

        cursor.close()    def get_hvac_efficiency(

        self.pool.putconn(connection)        self,

                equipment_id: str,

        return results        hours: int = 24

```    ) -> Dict:

        """Calculate HVAC equipment efficiency (COP/EER)"""

**Usage**:        conn = self.connect()

```python        cursor = conn.cursor(cursor_factory=RealDictCursor)

from actions.db_connector import TimescaleDBConnector        

import os        query = """

            WITH equipment_data AS (

db = TimescaleDBConnector(                SELECT 

    host=os.getenv("DB_HOST", "timescaledb"),                    time_bucket('15 minutes', time) AS bucket,

    port=int(os.getenv("DB_PORT", 5432)),                    AVG(CASE WHEN sensor_type = 'CoolingOutput' THEN value END) AS cooling_kw,

    database=os.getenv("DB_NAME", "building2"),                    AVG(CASE WHEN sensor_type = 'PowerInput' THEN value END) AS power_kw

    user=os.getenv("DB_USER", "postgres"),                FROM sensor_readings

    password=os.getenv("DB_PASSWORD", "postgres")                WHERE equipment_id = %s

)                  AND time >= NOW() - INTERVAL '%s hours'

                GROUP BY bucket

# Fast: Hourly aggregates for 1 month            )

hourly_data = db.get_hourly_aggregates(            SELECT 

    "Zone_101_Temperature_Sensor",                bucket,

    datetime(2025, 10, 1),                cooling_kw,

    datetime(2025, 10, 31)                power_kw,

)                CASE 

                    WHEN power_kw > 0 THEN cooling_kw / power_kw 

# Detailed: Raw data for 24 hours                    ELSE NULL 

raw_data = db.get_sensor_data(                END AS cop

    "Zone_101_Temperature_Sensor",            FROM equipment_data

    datetime(2025, 10, 31, 0, 0, 0),            WHERE cooling_kw IS NOT NULL AND power_kw IS NOT NULL

    datetime(2025, 10, 31, 23, 59, 59)            ORDER BY bucket DESC

)        """

```        cursor.execute(query, (equipment_id, hours))

        results = cursor.fetchall()

---        cursor.close()

        return results

### Query Optimization    

    def get_thermal_comfort(self, zone_id: str, hours: int = 24) -> Dict:

**1. Use Time Buckets for Aggregates**:        """Calculate thermal comfort metrics"""

```sql        conn = self.connect()

-- Good: Time bucket aggregates        cursor = conn.cursor(cursor_factory=RealDictCursor)

SELECT         

    time_bucket('15 minutes', timestamp) AS bucket,        query = """

    AVG(reading_value) AS avg_temp            SELECT 

FROM sensor_data                AVG(value) AS avg_temp,

WHERE sensor_name = 'Zone_101_Temperature_Sensor'                MIN(value) AS min_temp,

  AND timestamp >= NOW() - INTERVAL '7 days'                MAX(value) AS max_temp,

GROUP BY bucket                STDDEV(value) AS temp_variance,

ORDER BY bucket;                COUNT(*) FILTER (WHERE value < 20 OR value > 24) AS out_of_comfort_count,

                COUNT(*) AS total_readings

-- Bad: Full resolution for long time range            FROM sensor_readings

SELECT timestamp, reading_value            WHERE zone_id = %s

FROM sensor_data              AND sensor_type = 'ZoneTemp'

WHERE sensor_name = 'Zone_101_Temperature_Sensor'              AND time >= NOW() - INTERVAL '%s hours'

  AND timestamp >= NOW() - INTERVAL '1 year';  -- 525,600 rows!        """

```        cursor.execute(query, (zone_id, hours))

        result = cursor.fetchone()

**2. Leverage Continuous Aggregates**:        cursor.close()

```sql        return result or {}

-- Good: Use pre-computed hourly view    

SELECT hour, avg_value    def bulk_insert(self, readings: List[Dict]):

FROM sensor_data_hourly        """Bulk insert sensor readings"""

WHERE sensor_name = 'Zone_101_Temperature_Sensor'        conn = self.connect()

  AND hour >= NOW() - INTERVAL '30 days';        cursor = conn.cursor()

        

-- Bad: Re-compute aggregates every time        query = """

SELECT             INSERT INTO sensor_readings 

    time_bucket('1 hour', timestamp) AS hour,            (time, sensor_id, sensor_type, zone_id, equipment_id, value, unit)

    AVG(reading_value)            VALUES %s

FROM sensor_data        """

WHERE sensor_name = 'Zone_101_Temperature_Sensor'        

  AND timestamp >= NOW() - INTERVAL '30 days'        values = [

GROUP BY hour;            (

```                r.get('time', datetime.now()),

                r['sensor_id'],

---                r['sensor_type'],

                r.get('zone_id'),

## Cassandra Integration (Building 3)                r.get('equipment_id'),

                r['value'],

### Configuration                r.get('unit')

            )

**Docker Compose** (`docker-compose.bldg3.yml`):            for r in readings

        ]

```yaml        

cassandra:        execute_values(cursor, query, values)

  image: cassandra:4.1        conn.commit()

  container_name: cassandra        cursor.close()

  ports:```

    - "9042:9042"

  environment:### Advanced Queries

    CASSANDRA_CLUSTER_NAME: "Building3Cluster"

    CASSANDRA_DC: "DC1"```sql

    CASSANDRA_RACK: "Rack1"-- Time-weighted average (accounts for irregular sampling)

    CASSANDRA_ENDPOINT_SNITCH: "GossipingPropertyFileSnitch"SELECT 

    MAX_HEAP_SIZE: "4G"    sensor_id,

    HEAP_NEWSIZE: "800M"    time_weight('average', time, value) AS weighted_avg

  volumes:FROM sensor_readings

    - cassandra_data:/var/lib/cassandraWHERE time >= NOW() - INTERVAL '24 hours'

    - ./bldg3/init.cql:/docker-entrypoint-initdb.d/init.cqlGROUP BY sensor_id;

  healthcheck:

    test: ["CMD", "cqlsh", "-e", "describe keyspaces"]-- Gap filling (interpolate missing data)

    interval: 30sSELECT 

    timeout: 10s    time_bucket_gapfill('5 minutes', time) AS bucket,

    retries: 5    sensor_id,

  networks:    AVG(value) AS avg_value,

    - rasa-network    interpolate(AVG(value)) AS interpolated_value

FROM sensor_readings

rasa-action-server-bldg3:WHERE time >= NOW() - INTERVAL '1 hour'

  environment:GROUP BY bucket, sensor_id;

    CASSANDRA_HOST: cassandra

    CASSANDRA_PORT: 9042-- First and last values in time range

    CASSANDRA_KEYSPACE: building3SELECT 

```    sensor_id,

    first(value, time) AS first_value,

---    last(value, time) AS last_value,

    last(time, time) AS last_timestamp

### Schema Design (Partition Keys)FROM sensor_readings

WHERE time >= NOW() - INTERVAL '24 hours'

**Keyspace**: `building3`GROUP BY sensor_id;

```

```cql

CREATE KEYSPACE building3---

WITH REPLICATION = {

  'class': 'SimpleStrategy',## Cassandra Integration (Building 3)

  'replication_factor': 3

};### Configuration


USE building3;```yaml

```# docker-compose.bldg3.yml

cassandra:

**Main Table**: `sensor_data`  image: cassandra:4.1

  ports:

```cql    - "9042:9042"

CREATE TABLE sensor_data (  environment:

    sensor_id TEXT,    CASSANDRA_CLUSTER_NAME: "DataCenter-Cluster"

    sensor_name TEXT,    CASSANDRA_DC: "DC1"

    sensor_type TEXT,    CASSANDRA_ENDPOINT_SNITCH: "GossipingPropertyFileSnitch"

    timestamp TIMESTAMP,    MAX_HEAP_SIZE: "4G"

    reading_value DOUBLE,    HEAP_NEWSIZE: "800M"

    reading_unit TEXT,  volumes:

    zone_id TEXT,    - cassandra_data:/var/lib/cassandra

    equipment_id TEXT,```

    alarm_status TEXT,

    PRIMARY KEY ((sensor_id), timestamp)### Schema Design

) WITH CLUSTERING ORDER BY (timestamp DESC)

  AND compaction = {```cql

      'class': 'TimeWindowCompactionStrategy',-- Create keyspace with replication

      'compaction_window_size': 1,CREATE KEYSPACE IF NOT EXISTS telemetry_bldg3

      'compaction_window_unit': 'DAYS'WITH replication = {

  }    'class': 'SimpleStrategy',

  AND default_time_to_live = 63072000;  -- 2 years    'replication_factor': 1  -- Change to 3 for production cluster

```};


**Key Design Choices**:USE telemetry_bldg3;

- **Partition Key**: `sensor_id` (distributes sensors across nodes)

- **Clustering Key**: `timestamp DESC` (newest data first)-- Sensor readings (partition by sensor, cluster by time)

- **Time-Window Compaction**: Optimized for time-series dataCREATE TABLE IF NOT EXISTS sensor_data (

- **TTL**: Automatic 2-year expiry    sensor_uuid UUID,

    timestamp TIMESTAMP,

---    value DOUBLE,

    unit TEXT,

### Action Server Integration    zone TEXT,

    equipment_type TEXT,

**Python Connection** (`rasa-bldg3/actions/db_connector.py`):    equipment_id TEXT,

    sensor_type TEXT,

```python    quality_flag INT,

from cassandra.cluster import Cluster    PRIMARY KEY ((sensor_uuid), timestamp)

from cassandra.query import SimpleStatement) WITH CLUSTERING ORDER BY (timestamp DESC)

from datetime import datetime  AND compaction = {

      'class': 'TimeWindowCompactionStrategy',

class CassandraConnector:      'compaction_window_unit': 'HOURS',

    def __init__(self, hosts, port, keyspace):      'compaction_window_size': '24'

        self.cluster = Cluster(  }

            contact_points=[hosts],  AND default_time_to_live = 31536000;  -- 1 year TTL

            port=port

        )-- Alarms (partition by equipment, cluster by time)

        self.session = self.cluster.connect(keyspace)CREATE TABLE IF NOT EXISTS alarms (

            alarm_id UUID,

        # Prepare statements for better performance    equipment_id TEXT,

        self.select_stmt = self.session.prepare(    timestamp TIMESTAMP,

            """    severity TEXT,

            SELECT timestamp, reading_value    equipment_type TEXT,

            FROM sensor_data    message TEXT,

            WHERE sensor_id = ?    acknowledged BOOLEAN,

              AND timestamp >= ?    acknowledged_by TEXT,

              AND timestamp <= ?    acknowledged_at TIMESTAMP,

            ORDER BY timestamp ASC    PRIMARY KEY ((equipment_id), timestamp)

            """) WITH CLUSTERING ORDER BY (timestamp DESC);

        )

    -- Equipment status (single partition per equipment)

    def get_sensor_data(self, sensor_id, start_time, end_time):CREATE TABLE IF NOT EXISTS equipment_status (

        """    equipment_id TEXT PRIMARY KEY,

        Fetch sensor data for a given time range.    equipment_type TEXT,

            zone TEXT,

        Args:    status TEXT,

            sensor_id: Sensor ID (partition key)    last_updated TIMESTAMP,

            start_time: datetime object    metadata MAP<TEXT, TEXT>

            end_time: datetime object);

        

        Returns:-- Hourly aggregates (partition by sensor and day)

            List of tuples: [(timestamp, value), ...]CREATE TABLE IF NOT EXISTS hourly_aggregates (

        """    sensor_uuid UUID,

        rows = self.session.execute(    date DATE,

            self.select_stmt,    hour TIMESTAMP,

            (sensor_id, start_time, end_time)    avg_value DOUBLE,

        )    min_value DOUBLE,

            max_value DOUBLE,

        return [(row.timestamp, row.reading_value) for row in rows]    sample_count INT,

        PRIMARY KEY ((sensor_uuid, date), hour)

    def close(self):) WITH CLUSTERING ORDER BY (hour DESC);

        self.cluster.shutdown()

```-- Zone rollups (partition by zone and day)

CREATE TABLE IF NOT EXISTS zone_rollups (

**Usage**:    zone TEXT,

```python    sensor_type TEXT,

from actions.db_connector import CassandraConnector    date DATE,

import os    hour TIMESTAMP,

    avg_value DOUBLE,

db = CassandraConnector(    min_value DOUBLE,

    hosts=os.getenv("CASSANDRA_HOST", "cassandra"),    max_value DOUBLE,

    port=int(os.getenv("CASSANDRA_PORT", 9042)),    PRIMARY KEY ((zone, sensor_type, date), hour)

    keyspace=os.getenv("CASSANDRA_KEYSPACE", "building3")) WITH CLUSTERING ORDER BY (hour DESC);

)

```


# Fetch data (must specify partition key!)### Python Client

data = db.get_sensor_data(

    "crac1_supply_temp",  # sensor_id

```python

    datetime(2025, 10, 31, 0, 0, 0),# cassandra_client.py

    datetime(2025, 10, 31, 23, 59, 59)from cassandra.cluster import Cluster

)from cassandra.auth import PlainTextAuthProvider

```from cassandra.query import SimpleStatement, BatchStatement, BatchType

from datetime import datetime, timedelta

---import uuid

from typing import List, Dict, Optional

### Query Optimizationimport os


**1. ALWAYS Specify Partition Key**:class CassandraClient:

```cql    def __init__(self):

-- Good: Partition-aware query        self.hosts = os.getenv('CASSANDRA_HOSTS', 'cassandra').split(',')

SELECT timestamp, reading_value        self.port = int(os.getenv('CASSANDRA_PORT', 9042))

FROM sensor_data        self.keyspace = os.getenv('CASSANDRA_KEYSPACE', 'telemetry_bldg3')

WHERE sensor_id = 'crac1_supply_temp'        

  AND timestamp >= '2025-10-31 00:00:00'        self.cluster = Cluster(self.hosts, port=self.port)

  AND timestamp <= '2025-10-31 23:59:59';        self.session = self.cluster.connect(self.keyspace)

    

-- Bad: Full cluster scan (very slow!)    def get_sensor_data(

SELECT timestamp, reading_value        self,

FROM sensor_data        sensor_uuid: str,

WHERE timestamp >= '2025-10-31 00:00:00';  -- Missing sensor_id        start_time: datetime,

```        end_time: datetime

    ) -> List[Dict]:

**2. Avoid ALLOW FILTERING**:        """Get sensor readings in time range"""

```cql        query = """

-- Bad: Requires ALLOW FILTERING (slow)            SELECT timestamp, value, unit, equipment_id

SELECT * FROM sensor_data            FROM sensor_data

WHERE reading_value > 25.0            WHERE sensor_uuid = ?

ALLOW FILTERING;              AND timestamp >= ?

              AND timestamp <= ?

-- Good: Query by partition key, filter in application            ORDER BY timestamp DESC

SELECT * FROM sensor_data        """

WHERE sensor_id = 'crac1_supply_temp'        statement = SimpleStatement(query, fetch_size=1000)

  AND timestamp >= '2025-10-31';        rows = self.session.execute(statement, (uuid.UUID(sensor_uuid), start_time, end_time))

-- Then filter reading_value > 25.0 in Python        return [dict(row) for row in rows]

```    

    def get_active_alarms(

**3. Batch Writes**:        self,

```python        equipment_id: Optional[str] = None,

from cassandra.query import BatchStatement        severity: Optional[str] = None

    ) -> List[Dict]:

batch = BatchStatement()        """Get active (unacknowledged) alarms"""

        if equipment_id:

for reading in readings:            query = """

    batch.add(insert_stmt, (                SELECT * FROM alarms

        reading['sensor_id'],                WHERE equipment_id = ?

        reading['timestamp'],                  AND acknowledged = false

        reading['value']                ORDER BY timestamp DESC

    ))            """

            rows = self.session.execute(query, (equipment_id,))

session.execute(batch)        else:

```            # Note: This requires ALLOW FILTERING or secondary index

            query = """

---                SELECT * FROM alarms

                WHERE acknowledged = false

## Unified Action Server Abstraction                ALLOW FILTERING

            """

To support all three databases with identical query patterns, OntoBot uses a **database factory pattern**.            rows = self.session.execute(query)

        

**Database Factory** (`rasa-bldgX/actions/db_factory.py`):        return [dict(row) for row in rows]

    

```python    def calculate_pue(self, timestamp: Optional[datetime] = None) -> Optional[float]:

import os        """Calculate Power Usage Effectiveness"""

from .mysql_connector import MySQLConnector        if timestamp is None:

from .timescaledb_connector import TimescaleDBConnector            timestamp = datetime.now()

from .cassandra_connector import CassandraConnector        

        # Get total facility power

def get_database_connector():        total_power = self._get_latest_reading('total-facility-power-uuid', timestamp)

    """        

    Return appropriate database connector based on environment.        # Get IT equipment power

    """        it_power = self._get_latest_reading('it-equipment-power-uuid', timestamp)

    db_type = os.getenv("DB_TYPE", "mysql")        

            if total_power and it_power and it_power > 0:

    if db_type == "mysql":            return total_power / it_power

        return MySQLConnector(        return None

            host=os.getenv("DB_HOST"),    

            port=int(os.getenv("DB_PORT", 3306)),    def _get_latest_reading(self, sensor_uuid: str, before: datetime) -> Optional[float]:

            database=os.getenv("DB_NAME"),        """Get latest reading before timestamp"""

            user=os.getenv("DB_USER"),        query = """

            password=os.getenv("DB_PASSWORD")            SELECT value FROM sensor_data

        )            WHERE sensor_uuid = ?

                  AND timestamp <= ?

    elif db_type == "timescaledb":            ORDER BY timestamp DESC

        return TimescaleDBConnector(            LIMIT 1

            host=os.getenv("DB_HOST"),        """

            port=int(os.getenv("DB_PORT", 5432)),        row = self.session.execute(query, (uuid.UUID(sensor_uuid), before)).one()

            database=os.getenv("DB_NAME"),        return row.value if row else None

            user=os.getenv("DB_USER"),    

            password=os.getenv("DB_PASSWORD")    def insert_reading(

        )        self,

            sensor_uuid: str,

    elif db_type == "cassandra":        value: float,

        return CassandraConnector(        unit: str,

            hosts=os.getenv("CASSANDRA_HOST"),        equipment_id: str,

            port=int(os.getenv("CASSANDRA_PORT", 9042)),        sensor_type: str,

            keyspace=os.getenv("CASSANDRA_KEYSPACE")        timestamp: Optional[datetime] = None

        )    ):

            """Insert single sensor reading"""

    else:        if timestamp is None:

        raise ValueError(f"Unsupported database type: {db_type}")            timestamp = datetime.now()

```        

        query = """

**Usage in Actions**:            INSERT INTO sensor_data 

```python            (sensor_uuid, timestamp, value, unit, equipment_id, sensor_type)

from actions.db_factory import get_database_connector            VALUES (?, ?, ?, ?, ?, ?)

        """

class ActionGetSensorData(Action):        self.session.execute(

    def name(self) -> Text:            query,

        return "action_get_sensor_data"            (uuid.UUID(sensor_uuid), timestamp, value, unit, equipment_id, sensor_type)

            )

    def run(self, dispatcher, tracker, domain):    

        # Works with MySQL, TimescaleDB, or Cassandra!    def bulk_insert(self, readings: List[Dict]):

        db = get_database_connector()        """Bulk insert sensor readings using batch"""

                batch = BatchStatement(batch_type=BatchType.UNLOGGED)

        sensor_name = tracker.get_slot("sensor_name")        

        start_time = tracker.get_slot("start_date")        query = """

        end_time = tracker.get_slot("end_date")            INSERT INTO sensor_data 

                    (sensor_uuid, timestamp, value, unit, equipment_id, sensor_type)

        data = db.get_sensor_data(sensor_name, start_time, end_time)            VALUES (?, ?, ?, ?, ?, ?)

                """

        # Process data...        

        return []        for reading in readings:

```            batch.add(query, (

                uuid.UUID(reading['sensor_uuid']),

---                reading.get('timestamp', datetime.now()),

                reading['value'],

## Migration Between Databases                reading.get('unit'),

                reading.get('equipment_id'),

### Exporting Data                reading.get('sensor_type')

            ))

**MySQL Export**:        

```bash        self.session.execute(batch)

mysqldump -h localhost -P 3307 -u rasa_user -p telemetry ts_kv > bldg1_export.sql    

```    def acknowledge_alarm(self, alarm_id: str, acknowledged_by: str):

        """Acknowledge an alarm"""

**TimescaleDB Export**:        query = """

```bash            UPDATE alarms

pg_dump -h localhost -p 5433 -U postgres building2 > bldg2_export.sql            SET acknowledged = true,

```                acknowledged_by = ?,

                acknowledged_at = ?

**Cassandra Export**:            WHERE alarm_id = ?

```bash        """

cqlsh localhost 9042 -e "COPY building3.sensor_data TO 'bldg3_export.csv' WITH HEADER=TRUE"        self.session.execute(

```            query,

            (acknowledged_by, datetime.now(), uuid.UUID(alarm_id))

---        )

    

### Converting Between Databases    def close(self):

        """Close connection"""

**MySQL to TimescaleDB**:        self.cluster.shutdown()

```python
```

import mysql.connector

import psycopg2### Performance Tuning

from datetime import datetime

```cql

# Connect to MySQL-- Change compaction strategy for time-series

mysql_conn = mysql.connector.connect(ALTER TABLE sensor_data

    host="localhost", port=3307, database="telemetry",WITH compaction = {

    user="rasa_user", password="rasa_pass"    'class': 'TimeWindowCompactionStrategy',

)    'compaction_window_unit': 'HOURS',

mysql_cursor = mysql_conn.cursor()    'compaction_window_size': '24'

};

# Connect to TimescaleDB

pg_conn = psycopg2.connect(-- Add TTL for automatic data expiration

    host="localhost", port=5433, database="building2",ALTER TABLE sensor_data

    user="postgres", password="postgres"WITH default_time_to_live = 31536000;  -- 1 year

)

pg_cursor = pg_conn.cursor()-- Adjust read/write consistency

-- In Python client:

# Extract from MySQLfrom cassandra import ConsistencyLevel

mysql_cursor.execute("SELECT entity_id, key_name, ts, dbl_v FROM ts_kv")statement = SimpleStatement(query, consistency_level=ConsistencyLevel.LOCAL_QUORUM)

```

# Load into TimescaleDB

for row in mysql_cursor.fetchall():---

    entity_id, key_name, ts_ms, value = row

    timestamp = datetime.fromtimestamp(ts_ms / 1000)## Comparison & Best Practices

    

    pg_cursor.execute(### When to Use Each Database

        """

        INSERT INTO sensor_data (sensor_id, sensor_name, timestamp, reading_value)**MySQL:**

        VALUES (%s, %s, %s, %s)- ✅ Structured data with relationships

        """,- ✅ ACID transactions required

        (entity_id, key_name, timestamp, value)- ✅ Complex joins and aggregations

    )- ✅ Mature ecosystem and tools

- ❌ Limited horizontal scalability

pg_conn.commit()- ❌ Not optimized for time-series

```

**TimescaleDB:**

---- ✅ Time-series data (sensor readings)

- ✅ Automatic partitioning by time

## Best Practices- ✅ 90%+ compression

- ✅ PostgreSQL compatibility

### 1. Connection Pooling- ✅ Continuous aggregates

- ❌ Single-server (vertical scaling)

**DO**:

- ✅ Use connection pools (10-20 connections)**Cassandra:**

- ✅ Reuse connections across requests- ✅ High availability required

- ✅ Set connection timeouts (30 seconds)- ✅ Massive write throughput

- ✅ Handle connection failures gracefully- ✅ Linear horizontal scalability

- ✅ Geographic distribution

**DON'T**:- ✅ No single point of failure

- ❌ Create new connection for every query- ❌ No joins or transactions

- ❌ Leave connections open indefinitely- ❌ Eventual consistency

- ❌ Ignore connection pool exhaustion

### Connection Pooling

---

All clients should use connection pooling:

### 2. Query Performance

```python

**DO**:# MySQL

- ✅ Always use indexes (sensor_name, timestamp)from mysql.connector import pooling

- ✅ Limit result size with LIMIT clause

- ✅ Use batch inserts for high-volume writespool = pooling.MySQLConnectionPool(

- ✅ Monitor query execution plans (EXPLAIN)    pool_name="ontobot_pool",

    pool_size=10,

**DON'T**:    **config

- ❌ Query without WHERE clause (full table scan))

- ❌ Fetch more data than needed

- ❌ Use SELECT * (specify columns)# PostgreSQL/TimescaleDB

- ❌ Ignore slow query logsfrom psycopg2 import pool


---connection_pool = pool.SimpleConnectionPool(

    minconn=1,

### 3. Data Retention    maxconn=10,

    **config

**DO**:)

- ✅ Implement automatic retention policies

- ✅ Archive old data before deletion# Cassandra (built-in)

- ✅ Compress historical datacluster = Cluster(hosts, port=port)

- ✅ Monitor disk usagesession = cluster.connect()

```

**DON'T**:

- ❌ Keep unlimited historical data### Backup Strategies

- ❌ Delete data without backups

- ❌ Ignore disk space warnings

```bash

# MySQL

---mysqldump -u root -p telemetry > backup.sql


## Troubleshooting# PostgreSQL/TimescaleDB

pg_dump -U postgres telemetry_bldg2 > backup.sql

### Issue 1: Connection Timeout

# Cassandra

**Symptoms**:nodetool snapshot telemetry_bldg3

- Action server logs: `Connection timeout` or `Connection refused

````


**Solutions**:---

1. **Verify database is running**:

   ```bash## Related Documentation

   docker ps | grep mysql

   docker ps | grep timescaledb- [Building 1 - ABACWS](/docs/building1_abacws/) - MySQL implementation

   docker ps | grep cassandra- [Building 2 - Office](/docs/building2_office/) - TimescaleDB implementation

   ```- [Building 3 - Data Center](/docs/building3_datacenter/) - Cassandra implementation

- [Analytics API](/docs/analytics_api/) - Database queries via API

2. **Check database health**:- [Multi-Building Support](/docs/multi_building/) - Switching databases

   ```bash

   # MySQL---

   docker exec mysqlserver mysqladmin ping -u root -p

   **Database Selection Matrix:**

   # TimescaleDB

   docker exec timescaledb pg_isready| Requirement | MySQL | TimescaleDB | Cassandra |

 | ------------- | ------- | ------------- | ----------- | 

   # Cassandra (takes 30-60 seconds to start)| Time-series optimization | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

   docker exec cassandra nodetool status| High availability | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

   ```| Write throughput | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

 | Query flexibility | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 

3. **Test connection from host**:| Horizontal scalability | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |

   ```bash| Operational complexity | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |

   # MySQL
   mysql -h localhost -P 3307 -u rasa_user -p
   
   # TimescaleDB
   psql -h localhost -p 5433 -U postgres -d building2
   
   # Cassandra
   cqlsh localhost 9042
   ```

---

### Issue 2: Slow Queries

**Symptoms**:
- Queries take >5 seconds
- Dashboard feels sluggish

**Solutions**:
1. **Check indexes** (MySQL/TimescaleDB):
   ```sql
   EXPLAIN SELECT * FROM sensor_data WHERE sensor_name = 'Zone_101_Temperature_Sensor';
   ```

2. **Monitor Cassandra performance**:
   ```bash
   docker exec cassandra nodetool cfstats building3.sensor_data
   ```

3. **Enable query logging**:
   ```sql
   -- MySQL
   SET GLOBAL slow_query_log = 'ON';
   SET GLOBAL long_query_time = 2;
   
   -- PostgreSQL
   ALTER SYSTEM SET log_min_duration_statement = 2000;
   SELECT pg_reload_conf();
   ```

---

### Issue 3: Data Mismatch

**Symptoms**:
- Sensor shows no data despite data existing
- Query returns empty results

**Solutions**:
1. **Verify data exists**:
   ```sql
   -- Check count
   SELECT COUNT(*) FROM sensor_data WHERE sensor_name = 'Zone_101_Temperature_Sensor';
   
   -- Check timestamp range
   SELECT MIN(timestamp), MAX(timestamp) FROM sensor_data WHERE sensor_name = 'Zone_101_Temperature_Sensor';
   ```

2. **Check sensor name spelling**:
   ```sql
   SELECT DISTINCT sensor_name FROM sensor_data ORDER BY sensor_name;
   ```

3. **Verify timezone handling**:
   ```python
   # Ensure timestamps are in UTC
   import pytz
   start_time = datetime(2025, 10, 31, 0, 0, 0, tzinfo=pytz.UTC)
   ```

---

## Related Documentation

- **[Building 1 (ABACWS)](building1_abacws.md)**: MySQL schema and queries
- **[Building 2 (Office)](building2_office.md)**: TimescaleDB hypertables
- **[Building 3 (Data Center)](building3_datacenter.md)**: Cassandra partition keys
- **[Backend Services](backend_services.md)**: Database service architecture
- **[Multi-Building Support](multi_building.md)**: Switching databases

---

**Database Integration** - Unified abstraction across MySQL, TimescaleDB, and Cassandra. 🗄️🔗✨
