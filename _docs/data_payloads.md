---
layout: post
title: Data Payloads & Message Formats
date: 2025-10-31
---

# Data Payloads & Message Formats

**Complete specification of request/response formats for all OntoBot services.**

---

## Table of Contents

1. [Overview](#overview)
2. [Rasa Webhook Payloads](#rasa-webhook-payloads)
3. [Analytics Request Payloads](#analytics-request-payloads)
4. [Database Query Results](#database-query-results)
5. [SPARQL Response Formats](#sparql-response-formats)
6. [Decider Service Payloads](#decider-service-payloads)
7. [NL2SPARQL Payloads](#nl2sparql-payloads)
8. [Artifact File Formats](#artifact-file-formats)
9. [Error Payloads](#error-payloads)
10. [Validation Rules](#validation-rules)

---

## Overview

### Payload Standards

**Content-Type**: `application/json` (all services)

**Encoding**: UTF-8

**Timestamp Format**: ISO 8601 or Unix milliseconds

**Number Format**: IEEE 754 double precision

---

### UUID Mapping

**Internal UUIDs** are mapped to **human-readable names** in Action Server.

**Example**:
- UUID: `4ab2f2a0-8b9e-11ef-9c1e-00155d016e0f`
- Human Name: `Air_Temperature_Sensor_5.01`

**Mapping Files**:
- `rasa-bldg1/actions/sensor_mappings.txt`
- `rasa-bldg1/actions/sensor_list.txt`

---

## Rasa Webhook Payloads

### User Message (Request)

**Endpoint**: `POST http://localhost:5005/webhooks/rest/webhook`

**Payload**:
```json
{
  "sender": "user123",
  "message": "show me temperature in zone 5.01"
}
```

**Fields**:
- `sender` (string, required): Unique user identifier
- `message` (string, required): Natural language query

---

### Bot Response (Response)

**Payload**:
```json
[
  {
    "recipient_id": "user123",
    "text": "Here is the temperature data for Air_Temperature_Sensor_5.01:",
    "custom": {
      "sensor_name": "Air_Temperature_Sensor_5.01",
      "sensor_type": "temperature",
      "current_value": 21.5,
      "unit": "°C",
      "timestamp": "2025-10-31T14:30:00Z",
      "statistics": {
        "count": 1440,
        "mean": 21.6,
        "median": 21.5,
        "std": 0.4,
        "min": 20.8,
        "max": 22.5
      },
      "data": [
        {"datetime": "2025-10-30T14:30:00Z", "reading_value": 21.2},
        {"datetime": "2025-10-30T15:30:00Z", "reading_value": 21.4},
        {"datetime": "2025-10-30T16:30:00Z", "reading_value": 21.6}
      ],
      "chart_url": "http://localhost:8080/artifacts/user123/temp_chart_20251031143000.png",
      "csv_url": "http://localhost:8080/artifacts/user123/temp_data_20251031143000.csv"
    }
  }
]
```

**Fields**:
- `recipient_id` (string): User identifier (echoed from request)
- `text` (string): Natural language response
- `custom` (object): Structured data payload
  - `sensor_name` (string): Human-readable sensor name
  - `sensor_type` (string): Sensor category (temperature, co2, humidity, etc.)
  - `current_value` (number): Most recent reading
  - `unit` (string): Measurement unit
  - `timestamp` (string): ISO 8601 timestamp
  - `statistics` (object): Summary statistics
  - `data` (array): Time-series data
  - `chart_url` (string, optional): Chart artifact URL
  - `csv_url` (string, optional): CSV export URL

---

### Multi-Response Payload

**Scenario**: Multiple bot messages (e.g., form questions + response)

**Payload**:
```json
[
  {
    "recipient_id": "user123",
    "text": "Which sensor would you like to query?"
  },
  {
    "recipient_id": "user123",
    "text": "Here is the data:",
    "custom": {
      "sensor_name": "Air_Temperature_Sensor_5.01",
      "data": [...]
    }
  }
]
```

---

## Analytics Request Payloads

### Flat Format (Simple)

**Endpoint**: `POST http://localhost:6001/analytics/run`

**Payload**:
```json
{
  "analysis_type": "summary_statistics",
  "timeseries_data": [
    {"datetime": "2025-10-30T14:30:00Z", "reading_value": 21.2},
    {"datetime": "2025-10-30T15:30:00Z", "reading_value": 21.4},
    {"datetime": "2025-10-30T16:30:00Z", "reading_value": 21.6}
  ],
  "sensor_name": "Air_Temperature_Sensor_5.01",
  "unit": "°C"
}
```

**Fields**:
- `analysis_type` (string, required): Analysis identifier (see [Analytics Types](#analytics-types))
- `timeseries_data` (array, required): Time-series data points
  - `datetime` (string, required): ISO 8601 timestamp
  - `reading_value` (number, required): Numeric value
- `sensor_name` (string, optional): Human-readable sensor name
- `unit` (string, optional): Measurement unit

---

### Nested Format (Multi-Sensor)

**Payload**:
```json
{
  "analysis_type": "comparative_analysis",
  "timeseries_data": [
    {
      "sensor_name": "Air_Temperature_Sensor_5.01",
      "unit": "°C",
      "data": [
        {"datetime": "2025-10-30T14:30:00Z", "reading_value": 21.2},
        {"datetime": "2025-10-30T15:30:00Z", "reading_value": 21.4}
      ]
    },
    {
      "sensor_name": "Air_Temperature_Sensor_5.10",
      "unit": "°C",
      "data": [
        {"datetime": "2025-10-30T14:30:00Z", "reading_value": 22.5},
        {"datetime": "2025-10-30T15:30:00Z", "reading_value": 22.7}
      ]
    }
  ]
}
```

**Fields**:
- `analysis_type` (string, required): Analysis identifier
- `timeseries_data` (array, required): Array of sensor objects
  - `sensor_name` (string, required): Sensor identifier
  - `unit` (string, optional): Measurement unit
  - `data` (array, required): Time-series data points

---

### Analytics Types

**Descriptive**:
- `summary_statistics`: Mean, median, std, min, max, quartiles
- `time_series_visualization`: Line charts, bar charts, scatter plots
- `distribution_analysis`: Histograms, box plots, density plots

**Diagnostic**:
- `trend_analysis`: Linear regression, trend detection
- `anomaly_detection`: Z-score, IQR, isolation forest
- `correlation_analysis`: Pearson, Spearman correlation
- `comparative_analysis`: T-tests, ANOVA, Mann-Whitney

**Predictive**:
- `forecast`: ARIMA, exponential smoothing, LSTM
- `regression`: Linear, polynomial, ridge, lasso
- `classification`: Decision trees, random forests, SVM
- `clustering`: K-means, DBSCAN, hierarchical

**Prescriptive**:
- `optimization`: Linear programming, gradient descent
- `recommendation`: Rule-based, collaborative filtering
- `scenario_analysis`: What-if modeling, sensitivity analysis

**Real-Time**:
- `stream_processing`: Moving averages, online learning
- `pattern_recognition`: Motif discovery, sequence matching
- `alerting`: Threshold monitoring, change detection

---

### Analytics Response

**Success Payload**:
```json
{
  "status": "success",
  "analysis_type": "summary_statistics",
  "results": {
    "count": 1440,
    "mean": 21.6,
    "median": 21.5,
    "std": 0.4,
    "min": 20.8,
    "max": 22.5,
    "range": 1.7,
    "quartiles": {
      "q1": 21.3,
      "q2": 21.5,
      "q3": 21.8
    }
  },
  "chart_path": "/artifacts/user123/summary_stats_20251031143000.png",
  "execution_time": 0.245
}
```

**Fields**:
- `status` (string): "success" or "error"
- `analysis_type` (string): Echoed from request
- `results` (object): Analysis-specific results
- `chart_path` (string, optional): Relative path to chart artifact
- `execution_time` (number): Analysis duration in seconds

---

## Database Query Results

### MySQL (Building 1)

**Query**:
```sql
SELECT ts, dbl_v
FROM ts_kv
WHERE key_name = 'Air_Temperature_Sensor_5.01'
  AND ts >= 1698768600000
  AND ts <= 1698855000000
ORDER BY ts ASC;
```

**Raw Result**:
```python
[
  (1698768600000, 21.2),
  (1698772200000, 21.4),
  (1698775800000, 21.6)
]
```

**Transformed Payload** (Action Server):
```json
{
  "sensor_name": "Air_Temperature_Sensor_5.01",
  "sensor_type": "temperature",
  "unit": "°C",
  "data": [
    {"datetime": "2025-10-30T14:30:00Z", "reading_value": 21.2},
    {"datetime": "2025-10-30T15:30:00Z", "reading_value": 21.4},
    {"datetime": "2025-10-30T16:30:00Z", "reading_value": 21.6}
  ]
}
```

---

### TimescaleDB (Building 2)

**Query**:
```sql
SELECT time_bucket('1 hour', time) AS bucket,
       avg(value) AS avg_value
FROM sensor_data
WHERE sensor_id = 'Air_Temperature_Sensor_2_01'
  AND time >= '2025-10-30 00:00:00'
  AND time <= '2025-10-31 00:00:00'
GROUP BY bucket
ORDER BY bucket ASC;
```

**Raw Result**:
```python
[
  (datetime(2025, 10, 30, 0, 0), 20.5),
  (datetime(2025, 10, 30, 1, 0), 20.3),
  (datetime(2025, 10, 30, 2, 0), 20.1)
]
```

**Transformed Payload**:
```json
{
  "sensor_name": "Air_Temperature_Sensor_2_01",
  "sensor_type": "temperature",
  "unit": "°C",
  "aggregation": "hourly_average",
  "data": [
    {"datetime": "2025-10-30T00:00:00Z", "reading_value": 20.5},
    {"datetime": "2025-10-30T01:00:00Z", "reading_value": 20.3},
    {"datetime": "2025-10-30T02:00:00Z", "reading_value": 20.1}
  ]
}
```

---

### Cassandra (Building 3)

**Query**:
```cql
SELECT timestamp, value
FROM datacenter.sensor_data
WHERE sensor_id = 'Air_Temperature_Sensor_3_01'
  AND date = '2025-10-30'
  AND timestamp >= '2025-10-30 00:00:00'
  AND timestamp <= '2025-10-30 23:59:59';
```

**Raw Result**:
```python
[
  Row(timestamp=datetime(2025, 10, 30, 0, 0), value=19.8),
  Row(timestamp=datetime(2025, 10, 30, 1, 0), value=19.6),
  Row(timestamp=datetime(2025, 10, 30, 2, 0), value=19.4)
]
```

**Transformed Payload**:
```json
{
  "sensor_name": "Air_Temperature_Sensor_3_01",
  "sensor_type": "temperature",
  "unit": "°C",
  "data": [
    {"datetime": "2025-10-30T00:00:00Z", "reading_value": 19.8},
    {"datetime": "2025-10-30T01:00:00Z", "reading_value": 19.6},
    {"datetime": "2025-10-30T02:00:00Z", "reading_value": 19.4}
  ]
}
```

---

## SPARQL Response Formats

### Sensor Discovery Query

**SPARQL**:
```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?sensor WHERE {
  ?sensor rdf:type brick:Temperature_Sensor .
}
```

**Fuseki JSON Response**:
```json
{
  "head": {
    "vars": ["sensor"]
  },
  "results": {
    "bindings": [
      {
        "sensor": {
          "type": "uri",
          "value": "http://example.org/building#Air_Temperature_Sensor_5.01"
        }
      },
      {
        "sensor": {
          "type": "uri",
          "value": "http://example.org/building#Air_Temperature_Sensor_5.10"
        }
      }
    ]
  }
}
```

**Action Server Extraction**:
```python
sensor_names = []
for binding in response['results']['bindings']:
    uri = binding['sensor']['value']
    name = uri.split('#')[-1]  # Extract "Air_Temperature_Sensor_5.01"
    sensor_names.append(name)
```

---

### Equipment Hierarchy Query

**SPARQL**:
```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX bf: <https://brickschema.org/schema/BrickFrame#>

SELECT ?sensor ?feeds ?ahu WHERE {
  ?sensor rdf:type brick:Temperature_Sensor .
  ?sensor bf:feeds ?ahu .
  ?ahu rdf:type brick:AHU .
}
```

**Fuseki JSON Response**:
```json
{
  "head": {
    "vars": ["sensor", "feeds", "ahu"]
  },
  "results": {
    "bindings": [
      {
        "sensor": {
          "type": "uri",
          "value": "http://example.org/building#Supply_Temp_AHU_1"
        },
        "feeds": {
          "type": "uri",
          "value": "https://brickschema.org/schema/BrickFrame#feeds"
        },
        "ahu": {
          "type": "uri",
          "value": "http://example.org/building#AHU_1"
        }
      }
    ]
  }
}
```

---

## Decider Service Payloads

### Classification Request

**Endpoint**: `POST http://localhost:6009/decide`

**Payload**:
```json
{
  "query": "show me the trend of temperature over time"
}
```

**Fields**:
- `query` (string, required): Natural language query

---

### Classification Response

**Payload**:
```json
{
  "query": "show me the trend of temperature over time",
  "analytics_type": "trend_analysis",
  "confidence": 0.95,
  "alternatives": [
    {"analytics_type": "time_series_visualization", "confidence": 0.72},
    {"analytics_type": "summary_statistics", "confidence": 0.45}
  ]
}
```

**Fields**:
- `query` (string): Echoed from request
- `analytics_type` (string): Predicted analysis type
- `confidence` (number): Classification confidence (0-1)
- `alternatives` (array): Alternative predictions with confidence scores

---

## NL2SPARQL Payloads

### Query Translation Request

**Endpoint**: `POST http://localhost:6005/nl2sparql`

**Payload**:
```json
{
  "query": "find all temperature sensors in the building"
}
```

**Fields**:
- `query` (string, required): Natural language query

---

### Translation Response

**Payload**:
```json
{
  "query": "find all temperature sensors in the building",
  "sparql": "PREFIX brick: <https://brickschema.org/schema/Brick#>\nPREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>\n\nSELECT ?sensor WHERE {\n  ?sensor rdf:type brick:Temperature_Sensor .\n}",
  "confidence": 0.88,
  "model": "t5-base-finetuned"
}
```

**Fields**:
- `query` (string): Echoed from request
- `sparql` (string): Generated SPARQL query
- `confidence` (number): Translation confidence (0-1)
- `model` (string): Model identifier

---

## Artifact File Formats

### CSV Export

**Format**: Standard CSV (RFC 4180)

**Example** (`temp_data_20251031143000.csv`):
```csv
datetime,reading_value,sensor_name,unit
2025-10-30T14:30:00Z,21.2,Air_Temperature_Sensor_5.01,°C
2025-10-30T15:30:00Z,21.4,Air_Temperature_Sensor_5.01,°C
2025-10-30T16:30:00Z,21.6,Air_Temperature_Sensor_5.01,°C
```

**Access**: `http://localhost:8080/artifacts/user123/temp_data_20251031143000.csv`

---

### JSON Export

**Format**: JSON Lines (one object per line) or single JSON array

**Example** (`temp_data_20251031143000.json`):
```json
[
  {"datetime": "2025-10-30T14:30:00Z", "reading_value": 21.2, "sensor_name": "Air_Temperature_Sensor_5.01", "unit": "°C"},
  {"datetime": "2025-10-30T15:30:00Z", "reading_value": 21.4, "sensor_name": "Air_Temperature_Sensor_5.01", "unit": "°C"},
  {"datetime": "2025-10-30T16:30:00Z", "reading_value": 21.6, "sensor_name": "Air_Temperature_Sensor_5.01", "unit": "°C"}
]
```

**Access**: `http://localhost:8080/artifacts/user123/temp_data_20251031143000.json`

---

### PNG Charts

**Format**: PNG (Portable Network Graphics)

**Dimensions**: 1200x800 pixels (default)

**Example**: `temp_chart_20251031143000.png`

**Access**: `http://localhost:8080/artifacts/user123/temp_chart_20251031143000.png`

**Metadata**:
- DPI: 100
- Color Mode: RGB
- Transparency: Supported
- Font: DejaVu Sans (matplotlib default)

---

## Error Payloads

### Rasa Error Response

**Payload**:
```json
[
  {
    "recipient_id": "user123",
    "text": "I'm sorry, I encountered an error processing your request. Please try again or rephrase your query."
  }
]
```

---

### Analytics Error Response

**Payload**:
```json
{
  "status": "error",
  "error_code": "INSUFFICIENT_DATA",
  "message": "At least 10 data points required for trend analysis. Received: 5",
  "details": {
    "required_points": 10,
    "received_points": 5,
    "analysis_type": "trend_analysis"
  }
}
```

**Error Codes**:
- `INVALID_ANALYSIS_TYPE`: Unknown analysis type
- `INSUFFICIENT_DATA`: Too few data points
- `MISSING_REQUIRED_FIELD`: Required field not provided
- `INVALID_TIMESTAMP`: Malformed datetime string
- `NUMERIC_VALUE_REQUIRED`: Non-numeric reading_value
- `INTERNAL_ERROR`: Unexpected server error

---

### Database Error Response (Action Server)

**Payload**:
```json
{
  "error": "database_connection_failed",
  "message": "Unable to connect to MySQL server at mysqlserver:3306",
  "details": {
    "host": "mysqlserver",
    "port": 3306,
    "database": "telemetry",
    "error_code": 2003
  }
}
```

---

### SPARQL Error Response

**Fuseki Payload**:
```json
{
  "error": "Parse error: Unresolved prefixed name: brick:Temperature_Sensor"
}
```

---

## Validation Rules

### Timestamp Validation

**Accepted Formats**:
- ISO 8601: `2025-10-31T14:30:00Z`, `2025-10-31T14:30:00+00:00`
- Unix milliseconds: `1698768600000`
- Unix seconds: `1698768600`

**Validation**:
```python
from datetime import datetime

def validate_timestamp(ts):
    """Validate and normalize timestamp."""
    # Try ISO 8601
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except:
        pass
    
    # Try Unix milliseconds
    try:
        return datetime.fromtimestamp(int(ts) / 1000)
    except:
        pass
    
    # Try Unix seconds
    try:
        return datetime.fromtimestamp(int(ts))
    except:
        raise ValueError(f"Invalid timestamp: {ts}")
```

---

### Numeric Value Validation

**Rules**:
- Must be finite (no NaN, ±Infinity)
- Must be numeric (int or float)
- Range validation (sensor-specific)

**Validation**:
```python
import math

def validate_reading(value, sensor_type):
    """Validate numeric reading value."""
    # Check numeric
    if not isinstance(value, (int, float)):
        raise ValueError(f"Non-numeric value: {value}")
    
    # Check finite
    if not math.isfinite(value):
        raise ValueError(f"Non-finite value: {value}")
    
    # Range validation (examples)
    ranges = {
        "temperature": (-40, 60),  # °C
        "humidity": (0, 100),      # %RH
        "co2": (0, 5000),          # ppm
        "pressure": (900, 1100)    # hPa
    }
    
    if sensor_type in ranges:
        min_val, max_val = ranges[sensor_type]
        if not (min_val <= value <= max_val):
            raise ValueError(f"Value {value} outside valid range [{min_val}, {max_val}]")
    
    return value
```

---

### Sensor Name Validation

**Rules**:
- Must be non-empty string
- Typo-tolerance: 80% fuzzy match threshold
- Whitespace normalization

**Validation**:
```python
from rapidfuzz import fuzz, process

def validate_sensor_name(query, sensor_list, threshold=80):
    """Validate and resolve sensor name with typo tolerance."""
    # Normalize whitespace
    query_normalized = ' '.join(query.lower().split())
    
    # Exact match
    if query in sensor_list:
        return query
    
    # Fuzzy match
    result = process.extractOne(
        query_normalized,
        [s.lower() for s in sensor_list],
        scorer=fuzz.ratio,
        score_cutoff=threshold
    )
    
    if result:
        matched_lower, score, idx = result
        original_name = sensor_list[idx]
        return original_name
    
    raise ValueError(f"Sensor '{query}' not found (threshold={threshold})")
```

---

### Data Completeness Validation

**Rules**:
- Minimum data points per analysis type
- Maximum gap tolerance in time series
- Missing value handling

**Validation**:
```python
from datetime import timedelta

def validate_data_completeness(data, analysis_type, max_gap_hours=24):
    """Validate data completeness for analysis."""
    min_points = {
        "summary_statistics": 10,
        "trend_analysis": 20,
        "forecast": 30,
        "anomaly_detection": 50,
        "clustering": 100
    }
    
    # Check minimum points
    required = min_points.get(analysis_type, 10)
    if len(data) < required:
        raise ValueError(
            f"{analysis_type} requires at least {required} points, got {len(data)}"
        )
    
    # Check gaps
    sorted_data = sorted(data, key=lambda x: x['datetime'])
    for i in range(1, len(sorted_data)):
        prev_time = datetime.fromisoformat(sorted_data[i-1]['datetime'].replace('Z', '+00:00'))
        curr_time = datetime.fromisoformat(sorted_data[i]['datetime'].replace('Z', '+00:00'))
        gap = (curr_time - prev_time).total_seconds() / 3600  # hours
        
        if gap > max_gap_hours:
            raise ValueError(
                f"Data gap of {gap:.1f} hours exceeds maximum {max_gap_hours} hours"
            )
    
    return True
```

---

## Example Workflows

### Complete Query Flow

1. **User sends message**:
```json
{"sender": "user123", "message": "show me temperature in zone 5.01 for the last 24 hours"}
```

2. **Rasa extracts entities** → Sets slots:
```python
{
  "sensor_type": "temperature",
  "zone": "5.01",
  "time_range": "24h"
}
```

3. **Action server queries database**:
```sql
SELECT ts, dbl_v FROM ts_kv WHERE key_name = 'Air_Temperature_Sensor_5.01' AND ts >= ...
```

4. **Database returns raw data**:
```python
[(1698768600000, 21.2), (1698772200000, 21.4), ...]
```

5. **Action server transforms**:
```json
{
  "sensor_name": "Air_Temperature_Sensor_5.01",
  "data": [
    {"datetime": "2025-10-30T14:30:00Z", "reading_value": 21.2},
    ...
  ]
}
```

6. **Decider classifies query** → `time_series_visualization`

7. **Analytics generates chart** → Returns artifact path

8. **Action server sends response**:
```json
[{
  "recipient_id": "user123",
  "text": "Here is the temperature data:",
  "custom": {
    "sensor_name": "Air_Temperature_Sensor_5.01",
    "data": [...],
    "chart_url": "http://localhost:8080/artifacts/user123/chart.png"
  }
}]
```

---

## Related Documentation

- **[Usage Guide](usage.md)**: Query examples and workflows
- **[Analytics API](analytics_api.md)**: Detailed analytics specifications
- **[API Reference](api_reference.md)**: REST endpoint documentation
- **[Action Server Architecture](action_server_architecture.md)**: Pipeline internals

---

**Data Payloads** - Complete message format specifications for OntoBot services. 📦🔄✨
