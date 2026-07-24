---
layout: post
title: Usage Guide
date: 2025-10-31
---

# Usage Guide

**Complete end-to-end guide for using OntoBot - from basic queries to advanced analytics across all three buildings.**

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Sensor Queries](#basic-sensor-queries)
3. [Time-Range Queries](#time-range-queries)
4. [Analytics Queries](#analytics-queries)
5. [Multi-Sensor Comparisons](#multi-sensor-comparisons)
6. [Advanced Features](#advanced-features)
7. [Frontend Interface](#frontend-interface)
8. [Programmatic Access](#programmatic-access)
9. [Best Practices](#best-practices)

---

## Getting Started

### Service URLs

**Frontend (React UI)**: `http://localhost:3000`

**Rasa REST API**: `http://localhost:5005`

**Analytics API**: `http://localhost:6001`

**Artifact Server**: `http://localhost:8080`

**Fuseki SPARQL**: `http://localhost:3030`

---

### First Query

**Open Frontend**: Navigate to `http://localhost:3000`

**Type**: `"hello"`

**Expected Response**:
```
Welcome to OntoBot! I can help you query sensor data, run analytics, and 
visualize building performance. Try:
- "show me temperature in zone 5.01"
- "compare CO2 levels across all zones"
- "run trend analysis on humidity"
```

---

## Basic Sensor Queries

### Query Temperature

**Natural Language**:
```
"show me temperature in zone 5.01"
"what is the temperature sensor 5.01"
"display air temperature 5.01"
"temp zone 5.01"
```

**Response Format**:
```json
{
  "text": "Here is the temperature data for Air_Temperature_Sensor_5.01:",
  "custom": {
    "sensor_name": "Air_Temperature_Sensor_5.01",
    "current_value": 21.5,
    "unit": "°C",
    "timestamp": "2025-10-31T14:30:00Z",
    "statistics": {
      "mean": 21.6,
      "min": 20.8,
      "max": 22.5,
      "std": 0.4
    },
    "chart_url": "http://localhost:8080/artifacts/user123/temp_chart.png"
  }
}
```

---

### Query CO2 Levels

**Natural Language**:
```
"show me co2 in zone 5.01"
"what is the carbon dioxide level"
"display co2 sensor 5.01"
"co2 zone 5.01"
```

**Expected Values**:
- **Good**: 400-800 ppm (well-ventilated)
- **Acceptable**: 800-1000 ppm (adequate ventilation)
- **Poor**: 1000-2000 ppm (inadequate ventilation)
- **Hazardous**: >2000 ppm (immediate action required)

---

### Query Humidity

**Natural Language**:
```
"show me humidity in zone 5.01"
"what is the relative humidity"
"display moisture level"
"humidity sensor 5.01"
```

**Expected Values**:
- **Optimal**: 40-60% RH (comfortable)
- **Dry**: <40% RH (static electricity, dry skin)
- **Humid**: >60% RH (mold risk, discomfort)

---

### Query TVOC (Total Volatile Organic Compounds)

**Natural Language**:
```
"show me tvoc in zone 5.01"
"what is the air quality"
"display volatile organic compounds"
"tvoc sensor 5.01"
```

**Expected Values**:
- **Excellent**: 0-220 ppb
- **Good**: 220-660 ppb
- **Moderate**: 660-2200 ppb
- **Poor**: >2200 ppb

---

### Query Particulate Matter (PM2.5)

**Natural Language**:
```
"show me pm2.5 in zone 5.01"
"what is the particle concentration"
"display fine particulates"
"pm25 sensor 5.01"
```

**Expected Values**:
- **Good**: 0-12 μg/m³
- **Moderate**: 12-35 μg/m³
- **Unhealthy (sensitive)**: 35-55 μg/m³
- **Unhealthy**: >55 μg/m³

---

## Time-Range Queries

### Last 24 Hours

**Natural Language**:
```
"show me temperature for the last 24 hours"
"co2 levels past day"
"humidity in the last 24 hours"
"temperature yesterday"
```

**Chart Output**: Time-series line chart with hourly data points

---

### Last 7 Days

**Natural Language**:
```
"show me temperature for the last week"
"co2 levels past 7 days"
"humidity over the last week"
"weekly temperature trend"
```

**Chart Output**: Aggregated daily averages with trend line

---

### Last 30 Days

**Natural Language**:
```
"show me temperature for the last month"
"co2 levels past 30 days"
"monthly humidity data"
```

**Chart Output**: Daily aggregates with moving average

---

### Custom Time Ranges

**Natural Language**:
```
"show me temperature from October 1 to October 31"
"co2 between 2025-10-15 and 2025-10-20"
"humidity from last Monday to today"
```

**Supported Formats**:
- `YYYY-MM-DD` (e.g., 2025-10-31)
- `Month Day` (e.g., October 31)
- Relative: `yesterday`, `last week`, `last Monday`

---

## Analytics Queries

### Summary Statistics

**Natural Language**:
```
"calculate statistics for temperature in zone 5.01"
"show me summary stats for co2"
"get statistics on humidity"
```

**Response**:
```json
{
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
  }
}
```

---

### Trend Analysis

**Natural Language**:
```
"show me the trend of temperature"
"analyze temperature trend"
"is temperature increasing or decreasing"
"temperature trend analysis"
```

**Response**:
```json
{
  "analysis_type": "trend_analysis",
  "results": {
    "trend": "upward",
    "rate": 0.15,
    "confidence": 0.95,
    "equation": "y = 0.15x + 21.2",
    "r_squared": 0.88,
    "interpretation": "Temperature increasing at 0.15°C per hour"
  }
}
```

**Chart Output**: Scatter plot with linear trend line

---

### Anomaly Detection

**Natural Language**:
```
"detect anomalies in temperature"
"find unusual co2 readings"
"show me temperature outliers"
"identify abnormal humidity values"
```

**Response**:
```json
{
  "analysis_type": "anomaly_detection",
  "results": {
    "outlier_count": 3,
    "outlier_percentage": 2.1,
    "outliers": [
      {"datetime": "2025-10-31T02:30:00", "value": 28.5, "zscore": 3.2},
      {"datetime": "2025-10-31T14:15:00", "value": 29.0, "zscore": 3.5}
    ],
    "method": "zscore",
    "threshold": 3.0
  }
}
```

**Chart Output**: Time-series with outliers highlighted in red

---

### Forecasting

**Natural Language**:
```
"forecast temperature for the next 24 hours"
"predict co2 levels tomorrow"
"temperature prediction for next day"
```

**Response**:
```json
{
  "analysis_type": "forecast",
  "results": {
    "forecasts": [
      {"datetime": "2025-11-01T00:00:00", "value": 21.8, "lower": 20.9, "upper": 22.7},
      {"datetime": "2025-11-01T01:00:00", "value": 21.6, "lower": 20.6, "upper": 22.6}
    ],
    "model": "ARIMA(2,1,2)",
    "accuracy_metrics": {
      "mape": 2.3,
      "rmse": 0.5
    }
  }
}
```

**Chart Output**: Historical data + forecast with confidence intervals

---

### Correlation Analysis

**Natural Language**:
```
"correlate temperature and humidity"
"show correlation between co2 and occupancy"
"analyze relationship between temperature and tvoc"
```

**Response**:
```json
{
  "analysis_type": "correlation_analysis",
  "results": {
    "correlation_coefficient": -0.72,
    "p_value": 0.001,
    "significance": "strong_negative",
    "interpretation": "As temperature increases, humidity decreases"
  }
}
```

**Chart Output**: Scatter plot with regression line

---

### Comparative Analysis

**Natural Language**:
```
"compare temperature in zones 5.01 and 5.10"
"compare co2 levels across zones"
"difference between morning and evening temperature"
```

**Response**:
```json
{
  "analysis_type": "comparative_analysis",
  "results": {
    "comparison": [
      {"sensor": "Air_Temperature_Sensor_5.01", "mean": 21.5, "std": 0.8},
      {"sensor": "Air_Temperature_Sensor_5.10", "mean": 22.8, "std": 1.2}
    ],
    "statistical_test": {
      "test": "t-test",
      "p_value": 0.0001,
      "significant": true
    },
    "recommendation": "Zone 5.10 is significantly warmer than 5.01"
  }
}
```

**Chart Output**: Side-by-side box plots or bar charts

---

## Multi-Sensor Comparisons

### Compare Multiple Zones

**Natural Language**:
```
"compare temperatures in zones 5.01, 5.10, and 5.20"
"show me co2 levels across all zones"
"compare humidity in floor 5"
```

**Response**: Table or chart showing all requested sensors

**Chart Output**: Multi-line time-series chart or heatmap

---

### Compare Different Sensor Types

**Natural Language**:
```
"show me temperature, humidity, and co2 in zone 5.01"
"display all environmental sensors"
"compare air quality metrics"
```

**Response**: Multi-axis chart with different sensors

**Chart Output**: Dual-axis or normalized comparison chart

---

### Compare Time Periods

**Natural Language**:
```
"compare temperature this week vs last week"
"compare co2 today vs yesterday"
"compare humidity weekday vs weekend"
```

**Response**: Statistical comparison with significance testing

---

## Advanced Features

### Natural Language to SPARQL (Optional)

**Requires**: `docker-compose.extras.yml`

**Natural Language**:
```
"find all temperature sensors in the building"
"show me sensors connected to AHU 1"
"list all zones with occupancy sensors"
```

**Generated SPARQL**:
```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
SELECT ?sensor WHERE {
  ?sensor rdf:type brick:Temperature_Sensor .
}
```

**Workflow**:
1. User query → NL2SPARQL service
2. SPARQL query → Fuseki
3. Results → Action server
4. Response → User

---

### LLM Summarization (Optional)

**Requires**: `docker-compose.extras.yml` + Ollama

**Natural Language**:
```
"summarize temperature data"
"explain the co2 trend"
"what does this humidity pattern mean"
```

**LLM Response** (Mistral 7B):
```
The temperature in Zone 5.01 has remained relatively stable over the past 
24 hours, with an average of 21.6°C. The gradual upward trend of 0.15°C per 
hour suggests increasing thermal load, possibly due to occupancy or solar gain. 
Consider adjusting HVAC setpoints to maintain comfort.
```

---

### Batch Queries (REST API)

**Python Example**:
```python
import requests

sensors = [
    "Air_Temperature_Sensor_5.01",
    "Air_Temperature_Sensor_5.10",
    "Air_Temperature_Sensor_5.20"
]

for sensor in sensors:
    response = requests.post(
        "http://localhost:5005/webhooks/rest/webhook",
        json={
            "sender": "batch_user",
            "message": f"show me {sensor} for the last 24 hours"
        }
    )
    print(response.json())
```

---

### Scheduled Queries (Cron Jobs)

**PowerShell Script** (`scripts/daily_report.ps1`):
```powershell
# Run daily at 8 AM
$sensors = @(
    "temperature in zone 5.01",
    "co2 in zone 5.10",
    "humidity in zone 5.20"
)

foreach ($sensor in $sensors) {
    $response = Invoke-RestMethod `
        -Uri "http://localhost:5005/webhooks/rest/webhook" `
        -Method Post `
        -ContentType "application/json" `
        -Body (@{
            sender = "daily_report"
            message = "show me $sensor for yesterday"
        } | ConvertTo-Json)
    
    Write-Output $response
}
```

**Windows Task Scheduler**:
```powershell
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\OntoBot\scripts\daily_report.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 8am
Register-ScheduledTask -TaskName "OntoBot Daily Report" -Action $action -Trigger $trigger
```

---

## Frontend Interface

### Chat Interface

**Location**: `http://localhost:3000`

**Features**:
- Type natural language queries
- View real-time responses
- Click chart URLs to view visualizations
- Download CSV/JSON data
- View conversation history

---

### Message Input

**Input Box**: Type query and press Enter or click Send

**Example Queries**:
```
"show me temperature"
"compare co2 levels"
"run trend analysis"
"forecast humidity"
```

---

### Response Display

**Text Response**: Bot's natural language reply

**Chart Display**: Embedded PNG/SVG charts (if generated)

**Data Table**: Tabular data display (optional)

**Download Links**:
- CSV: Raw data export
- JSON: Structured data export
- PNG: Chart image

---

### Conversation History

**Sidebar**: View past queries and responses

**Search**: Filter conversations by keyword

**Export**: Download conversation transcript

---

## Programmatic Access

### REST API (Python)

```python
import requests
from datetime import datetime, timedelta

def query_sensor(sensor_name, hours=24):
    """Query sensor data via Rasa REST API."""
    url = "http://localhost:5005/webhooks/rest/webhook"
    
    payload = {
        "sender": "python_client",
        "message": f"show me {sensor_name} for the last {hours} hours"
    }
    
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    
    return response.json()

def run_analytics(analysis_type, sensor_name, hours=24):
    """Run analytics directly via Analytics API."""
    # 1. Fetch sensor data
    data = query_sensor(sensor_name, hours)
    
    # 2. Extract timeseries
    timeseries = data[0]['custom']['data']
    
    # 3. Call analytics
    analytics_url = "http://localhost:6001/analytics/run"
    payload = {
        "analysis_type": analysis_type,
        "timeseries_data": [{
            "sensor_name": sensor_name,
            "data": timeseries
        }]
    }
    
    response = requests.post(analytics_url, json=payload, timeout=60)
    response.raise_for_status()
    
    return response.json()

# Example usage
result = query_sensor("temperature in zone 5.01", hours=24)
print(f"Current temperature: {result[0]['custom']['current_value']}°C")

analytics = run_analytics("trend_analysis", "Air_Temperature_Sensor_5.01", hours=168)
print(f"Trend: {analytics['results']['trend']}")
print(f"Rate: {analytics['results']['rate']}°C/hour")
```

---

### REST API (JavaScript)

```javascript
const axios = require('axios');

async function querySensor(sensorName, hours = 24) {
  const url = 'http://localhost:5005/webhooks/rest/webhook';
  
  const payload = {
    sender: 'js_client',
    message: `show me ${sensorName} for the last ${hours} hours`
  };
  
  const response = await axios.post(url, payload, { timeout: 30000 });
  return response.data;
}

async function runAnalytics(analysisType, sensorName, hours = 24) {
  // 1. Fetch sensor data
  const data = await querySensor(sensorName, hours);
  
  // 2. Extract timeseries
  const timeseries = data[0].custom.data;
  
  // 3. Call analytics
  const analyticsUrl = 'http://localhost:6001/analytics/run';
  const payload = {
    analysis_type: analysisType,
    timeseries_data: [{
      sensor_name: sensorName,
      data: timeseries
    }]
  };
  
  const response = await axios.post(analyticsUrl, payload, { timeout: 60000 });
  return response.data;
}

// Example usage
(async () => {
  const result = await querySensor('temperature in zone 5.01', 24);
  console.log(`Current temperature: ${result[0].custom.current_value}°C`);
  
  const analytics = await runAnalytics('trend_analysis', 'Air_Temperature_Sensor_5.01', 168);
  console.log(`Trend: ${analytics.results.trend}`);
  console.log(`Rate: ${analytics.results.rate}°C/hour`);
})();
```

---

### Direct Database Access (Python)

```python
import mysql.connector
from datetime import datetime, timedelta

# Connect to MySQL (Building 1)
conn = mysql.connector.connect(
    host='localhost',
    port=3307,
    database='telemetry',
    user='rasa_user',
    password='rasa_pass'
)

cursor = conn.cursor()

# Query last 24 hours
end_time = int(datetime.now().timestamp() * 1000)
start_time = int((datetime.now() - timedelta(hours=24)).timestamp() * 1000)

query = """
SELECT ts, dbl_v
FROM ts_kv
WHERE key_name = %s
  AND ts >= %s
  AND ts <= %s
ORDER BY ts ASC
"""

cursor.execute(query, ('Air_Temperature_Sensor_5.01', start_time, end_time))
results = cursor.fetchall()

# Process results
for ts, value in results:
    dt = datetime.fromtimestamp(ts / 1000)
    print(f"{dt}: {value}°C")

cursor.close()
conn.close()
```

---

### SPARQL Queries (Python)

```python
import requests

def sparql_query(query):
    """Execute SPARQL query on Fuseki."""
    url = "http://localhost:3030/trial/sparql"
    
    headers = {
        "Content-Type": "application/sparql-query",
        "Accept": "application/sparql-results+json"
    }
    
    response = requests.post(url, data=query, headers=headers)
    response.raise_for_status()
    
    return response.json()

# Find all temperature sensors
query = """
PREFIX brick: <https://brickschema.org/schema/Brick#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?sensor WHERE {
  ?sensor rdf:type brick:Temperature_Sensor .
}
"""

results = sparql_query(query)

for binding in results['results']['bindings']:
    sensor_uri = binding['sensor']['value']
    sensor_name = sensor_uri.split('#')[-1]
    print(f"Sensor: {sensor_name}")
```

---

## Best Practices

### 1. Query Optimization

**DO**:
- ✅ Use specific time ranges (avoid querying years of data)
- ✅ Use exact sensor names when known
- ✅ Leverage typo-tolerance for natural queries
- ✅ Cache frequently accessed data

**DON'T**:
- ❌ Query full database without time filters
- ❌ Request minute-level data for long time ranges
- ❌ Make identical queries repeatedly
- ❌ Ignore pagination for large result sets

---

### 2. Analytics Usage

**DO**:
- ✅ Use summary statistics for quick overview
- ✅ Use trend analysis for long-term patterns
- ✅ Use anomaly detection for outlier identification
- ✅ Use forecasting for predictive insights

**DON'T**:
- ❌ Run complex analytics on <10 data points
- ❌ Ignore data quality issues
- ❌ Over-request analytics (use caching)
- ❌ Mix incompatible sensor types

---

### 3. Interpretation

**DO**:
- ✅ Consider context (occupancy, weather, time of day)
- ✅ Compare against baselines or standards
- ✅ Look for patterns across multiple sensors
- ✅ Validate unexpected results

**DON'T**:
- ❌ Rely on single data point
- ❌ Ignore sensor accuracy/calibration
- ❌ Over-interpret statistical significance
- ❌ Ignore physical constraints

---

### 4. Error Handling

**DO**:
- ✅ Check response status codes
- ✅ Handle missing data gracefully
- ✅ Implement retry logic with exponential backoff
- ✅ Log errors with context

**DON'T**:
- ❌ Assume all queries succeed
- ❌ Ignore error messages
- ❌ Retry immediately on failure
- ❌ Expose internal errors to users

---

## Common Use Cases

### Energy Management

**Goal**: Reduce energy consumption

**Queries**:
```
"show me electricity consumption for the last month"
"compare energy usage weekday vs weekend"
"forecast energy demand for next week"
"optimize HVAC electricity consumption"
```

---

### Indoor Air Quality Monitoring

**Goal**: Maintain healthy indoor environment

**Queries**:
```
"show me co2 levels in all zones"
"detect high TVOC readings"
"compare air quality before and after ventilation"
"forecast co2 levels during peak occupancy"
```

---

### Thermal Comfort Optimization

**Goal**: Maintain comfortable temperatures

**Queries**:
```
"show me temperature distribution across zones"
"find zones outside 20-24°C range"
"compare temperature morning vs afternoon"
"predict temperature for tomorrow"
```

---

### Fault Detection

**Goal**: Identify equipment issues

**Queries**:
```
"detect anomalies in AHU 1 supply temperature"
"show me sensors with no data in last hour"
"compare current readings vs baseline"
"identify sensors with excessive drift"
```

---

### Research & Analysis

**Goal**: Study building performance

**Queries**:
```
"correlate occupancy and co2 levels"
"cluster zones by thermal behavior"
"analyze seasonal temperature patterns"
"compare pre/post retrofit energy usage"
```

---

## Related Documentation

- **[Quick Start Guide](quickstart.md)**: 5-minute setup
- **[Analytics API Reference](analytics_api.md)**: 30+ analysis types
- **[API Reference](api_reference.md)**: REST API documentation
- **[Troubleshooting](troubleshooting.md)**: Common issues & solutions

---

**Usage Guide** - Master OntoBot from basic queries to advanced analytics. 🎯📊✨
