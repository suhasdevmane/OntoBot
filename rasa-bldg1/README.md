# Building 1 - ABACWS (Real University Testbed)

**Rasa Conversational AI Stack for Building 1 with Typo-Tolerant Sensor Resolution**

[![Rasa](https://img.shields.io/badge/Rasa-3.6.12-5A17EE?logo=rasa)](https://rasa.com/)
[![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Required-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

This directory contains the Rasa Open Source conversational AI stack specifically configured for **Building 1 (ABACWS)**, a real-world university testbed building at Cardiff University with comprehensive Indoor Environmental Quality (IEQ) monitoring.

## 🏢 Building Overview

| Property | Details |
|----------|---------|
| **Building Type** | Real University Testbed |
| **Location** | Cardiff University, Wales, UK |
| **Sensor Coverage** | 680 sensors across 34 zones (5.01–5.34) |
| **Focus Area** | Indoor Environmental Quality (IEQ) |
| **Database** | MySQL (port 3307) |
| **Knowledge Graph** | Brick Schema 1.3 via Jena Fuseki (port 3030) |
| **Compose File** | `docker-compose.bldg1.yml` (from repo root) |
| **Typo Tolerance** | ✅ Automatic sensor name correction with fuzzy matching |

### Sensor Types (20 sensors per zone)

**Air Quality Monitoring:**
- CO2, TVOC, Formaldehyde
- Particulate Matter (PM1, PM2.5, PM10)

**Multi-Gas Sensors:**
- MQ2 (Combustible Gas, Smoke)
- MQ3 (Alcohol Vapor)
- MQ5 (LPG, Natural Gas)
- MQ9 (Carbon Monoxide, Coal Gas)
- NO2, O2 Percentage
- Ethyl Alcohol (C2H5OH)

**Environmental Parameters:**
- Air Temperature & Humidity
- Illuminance (Light Levels)
- Sound/Noise (MEMS sensor)
- Air Quality Index

## 🚀 Services

This stack includes six integrated services:

| Service | Port | Purpose | Health Endpoint |
|---------|------|---------|-----------------|
| **Rasa Core** | 5005 | NLU/Dialogue engine | `GET /version` |
| **Action Server** | 5055 | Custom actions & integrations | `GET /health` |
| **Duckling** | 8000 | Entity extraction (dates, times) | `GET /` |
| **File Server** | 8080 | Artifact hosting (charts, CSV) | `GET /health` |
| **Rasa Editor** | 6080 | Web-based NLU editor | `GET /health` |
| **Frontend UI** | 3000 | React chat interface | N/A |

### Service Architecture

```
User Query → Frontend (3000)
    ↓
Rasa Core (5005) → NLU Processing
    ↓
Action Server (5055)
    ├── MySQL (3307) - Telemetry Data
    ├── Fuseki (3030) - Knowledge Graph (SPARQL)
    ├── Analytics (6001) - Time-series Analysis
    ├── Decider (6009) - Analytics Selection
    └── NL2SPARQL (6005) - Query Translation
    ↓
File Server (8080) ← Generated Artifacts
    ↓
Frontend (3000) ← Rich Response + Media
```

## 📦 Installation

### Prerequisites

- Docker Desktop 20.10+
- Docker Compose 2.0+
- 8GB RAM minimum (16GB recommended)
- 20GB free disk space

### Quick Start

```powershell
# From repository root
cd c:\Users\suhas\Documents\GitHub\OntoBot

# Start Building 1 stack
docker-compose -f docker-compose.bldg1.yml up -d --build

# Wait for services to be healthy (~2-3 minutes)
Start-Sleep -Seconds 180

# Verify services
docker-compose -f docker-compose.bldg1.yml ps
```

### Access Points

- **Frontend**: http://localhost:3000
- **Rasa Core**: http://localhost:5005/version
- **Action Server**: http://localhost:5055/health
- **File Server**: http://localhost:8080/health
- **Editor**: http://localhost:6080
- **Duckling**: http://localhost:8000

## ⚙️ Configuration

### Environment Variables

Action Server configuration (set in `docker-compose.bldg1.yml`):

```yaml
environment:
  # File Server
  BASE_URL: http://localhost:8080
  BUNDLE_MEDIA: "true"
  
  # MySQL Database
  DB_HOST: mysqlserver
  DB_NAME: telemetry
  DB_USER: root
  DB_PASSWORD: password
  DB_PORT: 3306
  
  # Service Integrations
  ANALYTICS_URL: http://microservices:6000/analytics/run
  DECIDER_URL: http://decider-service:6009/decide
  NL2SPARQL_URL: http://nl2sparql:6005/predict
  FUSEKI_URL: http://fuseki:3030/abacws/query
  
  # Feature Flags
  ENABLE_SUMMARIZATION: "true"
  ENABLE_ANALYTICS: "true"
  
  # Typo-Tolerant Sensor Resolution (NEW)
  FUZZY_THRESHOLD: 80              # Fuzzy matching threshold (0-100)
  SENSOR_LIST_RELOAD_SEC: 300      # Auto-reload sensor_list.txt interval
```

**Typo Tolerance Configuration:**
- `FUZZY_THRESHOLD`: Controls how strict fuzzy matching is (default: 80)
  - Lower (70): More lenient, tolerates more typos but may have false positives
  - Higher (90): Stricter, fewer false positives but less typo tolerance
- `SENSOR_LIST_RELOAD_SEC`: How often to reload sensor_list.txt (default: 300 seconds)

See [TYPO_TOLERANT_SENSORS.md](TYPO_TOLERANT_SENSORS.md) for complete documentation.

### Volumes

```yaml
volumes:
  ./rasa-bldg1:/app                    # Rasa project files
  ./rasa-bldg1/shared_data:/app/shared_data  # Artifacts
  ./rasa-bldg1/actions:/app/actions    # Custom actions (live reload)
  ./rasa-bldg1/models:/app/models      # Trained models
```

## 💬 Usage

### Example Queries

**Temperature Queries:**
```
What is the temperature in zone 5.04?
Show me temperature trends for zone 5.15
What's the average temperature today?
```

**Air Quality Queries:**
```
What's the CO2 level in zone 5.01?
Show me air quality trends for the last week
Is the air quality good in zone 5.20?
```

**Typo-Tolerant Queries (NEW):**
```
what is NO2 sensor? where this NO2 Level sensor 5.09 is located?
show me NO2  Level   Sensor  5.09  (multiple spaces)
NO2 Levl Sensor 5.09  (typo in "Level")
Carbon Monoxide Coal Gas Liquefied MQ9 Gas Sensor 5.25
```

**Note:** The system automatically corrects sensor name typos, spacing, and formatting errors:
- "NO2 Level sensor 5.09" → `NO2_Level_Sensor_5.09` (spaces fixed)
- "NO2 Levl Sensor 5.09" → `NO2_Level_Sensor_5.09` (typo corrected, score: 97.5)
- "NO2_Level_sensor_5.09" → `NO2_Level_Sensor_5.09` (case normalized)

**Analytics Queries:**
```
Detect anomalies in temperature for zone 5.04
Compare humidity between zones 5.01 and 5.10
Forecast CO2 levels for the next 2 hours
```

**Multi-Parameter Queries:**
```
Show correlation between temperature and humidity
What's the relationship between CO2 and occupancy?
Analyze particulate matter trends
```

### Response Format

The bot returns structured responses with:
- **Text**: Human-readable answer
- **Data**: Numerical values with units
- **Visualizations**: Charts (line, bar, scatter)
- **Artifacts**: Downloadable CSV/JSON

## 🔧 Development

### Project Structure

```
rasa-bldg1/
├── actions/
│   ├── actions.py           # Custom action logic with typo-tolerant resolution
│   ├── sensor_list.txt      # 680 ABACWS sensor names (canonical forms)
│   ├── sensor_uuids.txt     # UUID mappings
│   ├── requirements.txt     # Action dependencies (includes rapidfuzz)
│   └── test_sensor_extraction.py  # Test script for typo tolerance
├── data/
│   ├── nlu.yml              # NLU training examples
│   ├── rules.yml            # Conversation rules
│   └── stories.yml          # Dialogue stories
├── models/                  # Trained Rasa models
├── shared_data/
│   └── artifacts/           # Generated charts/CSV
├── config.yml               # Pipeline configuration
├── domain.yml               # Intents, entities, slots
├── endpoints.yml            # Service endpoints
└── credentials.yml          # Channel credentials
```

### Training a New Model

```powershell
# Option 1: Using Docker Compose
docker-compose -f docker-compose.bldg1.yml run --rm rasa_bldg1 train

# Option 2: Manual container (from rasa-bldg1/)
docker run --rm -v ${PWD}:/app rasa/rasa:3.6.12-full train

# Models are saved to ./models/
```

### Testing Locally

```powershell
# Test NLU only
docker-compose -f docker-compose.bldg1.yml run --rm rasa_bldg1 shell nlu

# Interactive chat
docker-compose -f docker-compose.bldg1.yml run --rm rasa_bldg1 shell

# REST API test
Invoke-RestMethod -Method Post -Uri http://localhost:5005/webhooks/rest/webhook `
  -ContentType "application/json" `
  -Body (@{sender="test"; message="What is the temperature?"} | ConvertTo-Json)
```

### Modifying Actions

Actions are live-mounted, so changes take effect immediately after container restart:

```powershell
# Edit actions/actions.py
# Then restart action server
docker-compose -f docker-compose.bldg1.yml restart action_server_bldg1
```

## 🧠 Typo-Tolerant Sensor Resolution

Building 1 includes **automatic sensor name correction** that handles typos, spacing errors, and formatting inconsistencies in user queries.

### Features

- ✅ **Space Normalization**: "NO2 Level Sensor 5.09" → `NO2_Level_Sensor_5.09`
- ✅ **Fuzzy Matching**: "NO2 Levl Sensor 5.09" → `NO2_Level_Sensor_5.09` (typo corrected, score: 97.5)
- ✅ **Case Correction**: "NO2_Level_sensor_5.09" → `NO2_Level_Sensor_5.09`
- ✅ **Number Formatting**: "NO2 Level Sensor 5.9" → `NO2_Level_Sensor_5.09`
- ✅ **SPARQL Postprocessing**: Fixes malformed queries automatically
- ✅ **Auto-Reload**: Updates when `sensor_list.txt` changes (300s interval)

### How It Works

1. **Text Extraction**: Detects sensor mentions in natural language
2. **Normalization**: Converts spaces to underscores
3. **Fuzzy Matching**: Matches against 680 canonical sensor names (threshold: 80)
4. **Question Rewrite**: Replaces mentions with canonical forms
5. **SPARQL Generation**: Creates valid queries with correct sensor names

### Configuration

```yaml
# docker-compose.bldg1.yml
action_server_bldg1:
  environment:
    - FUZZY_THRESHOLD=80        # Matching tolerance (0-100)
    - SENSOR_LIST_RELOAD_SEC=300  # Reload interval
```

### Testing

```powershell
# Run standalone test
cd rasa-bldg1/actions
python test_sensor_extraction.py

# Expected output:
# [Test 1]
# Input: what is NO2 sensor? where this NO2 Level sensor 5.09 is located?
# Extracted: 1 sensor(s)
#   'NO2 Level sensor 5.09' -> 'NO2_Level_Sensor_5.09'
# Rewritten: ...NO2_Level_Sensor_5.09...
```

### Documentation

- **Complete Guide**: [TYPO_TOLERANT_SENSORS.md](TYPO_TOLERANT_SENSORS.md)
- **Implementation Summary**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **Quick Start**: [QUICK_START_TYPO_TOLERANCE.md](QUICK_START_TYPO_TOLERANCE.md)

---

## 🏗️ Building-Specific Customization

### Sensor Naming Convention

ABACWS sensors follow this pattern:
```
{Parameter}_{Zone_ID}
```

Examples:
```
Air_Temperature_Sensor_5.04
CO2_Level_Sensor_5.01
Zone_Air_Humidity_Sensor_5.15
PM2.5_Level_Sensor_Atmospheric_5.20
```

### Zone Layout

- **Zones**: 5.01 through 5.34 (34 zones total)
- **Level**: Floor 5 of university building
- **Sensors per Zone**: 20 sensors
- **Total Sensors**: 680

### Database Schema

**MySQL Table: `sensor_data`**
```sql
CREATE TABLE sensor_data (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sensor_name VARCHAR(255),
  sensor_uuid VARCHAR(36),
  value FLOAT,
  unit VARCHAR(20),
  ts TIMESTAMP,
  INDEX idx_sensor_ts (sensor_name, ts),
  INDEX idx_uuid_ts (sensor_uuid, ts)
);
```

### Knowledge Graph (Brick Schema)

The ABACWS Brick ontology defines:
- 680 sensor instances
- 34 zone instances
- Equipment relationships
- Measurement capabilities

**Example SPARQL Query:**
```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
SELECT ?sensor ?zone WHERE {
  ?sensor a brick:Temperature_Sensor .
  ?sensor brick:isPartOf ?zone .
  ?zone brick:label "Zone 5.04" .
}
```

## 📊 Analytics Integration

### Available Analytics

The Action Server calls the Analytics Microservices with building-specific payloads:

**Statistical Analysis:**
- Mean, median, standard deviation
- Min/max values
- Percentiles and quartiles

**Trend Detection:**
- Linear regression
- Moving averages
- Seasonal decomposition

**Anomaly Detection:**
- Z-score method
- IQR (Interquartile Range)
- Isolation Forest

**Forecasting:**
- ARIMA models
- Prophet (Facebook)
- Exponential smoothing

**Correlation:**
- Pearson correlation
- Spearman rank correlation
- Cross-correlation

### Payload Format

```json
{
  "analysis_type": "analyze_temperatures",
  "1": {
    "Air_Temperature_Sensor_5.04": {
      "timeseries_data": [
        {"datetime": "2025-01-08T10:00:00Z", "reading_value": 22.5},
        {"datetime": "2025-01-08T10:15:00Z", "reading_value": 22.7}
      ]
    }
  },
  "acceptable_range": [18, 24],
  "unit": "°C"
}
```

## 🔍 Troubleshooting

### Common Issues

**1. Services Won't Start**
```powershell
# Check logs
docker-compose -f docker-compose.bldg1.yml logs rasa_bldg1

# Restart services
docker-compose -f docker-compose.bldg1.yml restart
```

**2. Action Server Can't Connect to MySQL**
```powershell
# Verify MySQL is running
docker-compose -f docker-compose.bldg1.yml ps mysqlserver

# Check connection from action server
docker-compose -f docker-compose.bldg1.yml exec action_server_bldg1 ping mysqlserver
```

**3. NLU Confidence Too Low**
```yaml
# Adjust pipeline in config.yml
pipeline:
  - name: DIETClassifier
    epochs: 200  # Increase from 100
    constrain_similarities: true
```

**4. Slow Training**
```yaml
# In domain.yml, reduce lookup table sizes
# Or use featurizers with lower dimensions
```

## 📚 Data & Artifacts

### Shared Data Volume

```
shared_data/
├── artifacts/                    # Generated files
│   ├── temperature_chart_*.png
│   ├── analytics_result_*.json
│   └── sensor_data_*.csv
├── sensor_mappings.json          # UUID to name mappings
└── cache/                        # Temporary files
```

### Artifact Access

**Via File Server:**
```
http://localhost:8080/artifacts/temperature_chart_20250108_143000.png
```

**Download Flag:**
```
http://localhost:8080/artifacts/data.csv?download=1
```

**Streaming (for large files):**
- File server supports HTTP Range requests
- Enables progressive loading in browser

## 🔗 Integration with Other Services

### Analytics Microservices (Port 6001)

```python
# From actions.py
import requests

response = requests.post(
    "http://microservices:6000/analytics/run",
    json={
        "analysis_type": "analyze_temperatures",
        "1": sensor_data
    }
)
```

### Decider Service (Port 6009)

```python
# Determine which analytics to run
response = requests.post(
    "http://decider-service:6009/decide",
    json={"question": user_message}
)

if response.json()["perform_analytics"]:
    analytics_type = response.json()["analytics"]
    # Run analytics
```

### NL2SPARQL (Port 6005)

```python
# Translate natural language to SPARQL
response = requests.post(
    "http://nl2sparql:6005/predict",
    json={"question": "What is the temperature in zone 5.04?"}
)

sparql_query = response.json()["sparql"]
# Execute against Fuseki
```

## 🧪 Testing

### Health Checks

```powershell
# Check all services
curl http://localhost:5005/version        # Rasa
curl http://localhost:5055/health         # Actions
curl http://localhost:8080/health         # File Server
curl http://localhost:6080/health         # Editor
curl http://localhost:8000                # Duckling
```

### End-to-End Test

```powershell
# Send a test message
$response = Invoke-RestMethod -Method Post `
  -Uri http://localhost:5005/webhooks/rest/webhook `
  -ContentType "application/json" `
  -Body (@{
    sender = "test_user"
    message = "What is the temperature in zone 5.04?"
  } | ConvertTo-Json)

# Should return temperature value with unit
Write-Output $response
```

### Smoke Test Script

```powershell
# Test all endpoints
$tests = @(
    @{Name="Rasa"; Url="http://localhost:5005/version"},
    @{Name="Actions"; Url="http://localhost:5055/health"},
    @{Name="FileServer"; Url="http://localhost:8080/health"}
)

foreach ($test in $tests) {
    try {
        $result = Invoke-RestMethod -Uri $test.Url -TimeoutSec 5
        Write-Host "✓ $($test.Name) OK" -ForegroundColor Green
    } catch {
        Write-Host "✗ $($test.Name) FAIL" -ForegroundColor Red
    }
}
```

## 📖 References

- **Rasa Documentation**: https://rasa.com/docs/rasa/
- **Brick Schema**: https://brickschema.org/
- **Apache Jena Fuseki**: https://jena.apache.org/documentation/fuseki2/
- **SPARQL 1.1**: https://www.w3.org/TR/sparql11-query/
- **RapidFuzz**: https://github.com/maxbachmann/RapidFuzz (fuzzy string matching)
- **OntoBot Main README**: [../README.md](../README.md)
- **Multi-Building Support**: [../MULTI_BUILDING_SUPPORT.md](../MULTI_BUILDING_SUPPORT.md)
- **Typo-Tolerant Sensors**: [TYPO_TOLERANT_SENSORS.md](TYPO_TOLERANT_SENSORS.md)
- **Analytics API**: [../analytics.md](../analytics.md)

## 🆘 Support

For issues specific to Building 1 (ABACWS):
- Check logs: `docker-compose -f docker-compose.bldg1.yml logs`
- Review main README: [../README.md](../README.md)
- See troubleshooting guide: [../TROUBLESHOOTING_SENSOR_DROPDOWN.md](../TROUBLESHOOTING_SENSOR_DROPDOWN.md)

## 📄 License

This project is part of OntoBot. See [../LICENSE](../LICENSE) for details.

---

**Next Steps:**
- [Building 2 (Office)](../rasa-bldg2/README.md) - Synthetic Office Building (329 sensors)
- [Building 3 (Data Center)](../rasa-bldg3/README.md) - Synthetic Data Center (597 sensors)
- [Frontend Documentation](../suhasdevmane.github.io/_docs/frontend_ui.md)
- [API Reference](../suhasdevmane.github.io/_docs/api_reference.md)
