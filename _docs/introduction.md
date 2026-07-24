---
title: OntoBot Introduction
layout: post
category: docs
permalink: /docs/introduction/
date: 2025-09-28
---


# OntoBot: Conversational AI for Smart Buildings# OntoBot: Talking Buildings


## What is OntoBot?OntoBot is a modular platform for human–building interaction in natural language. It combines:


OntoBot is a **production-ready conversational AI platform** that enables natural language interaction with smart building systems. Ask questions like:- A Rasa-based conversational layer (NLU + Actions)

- An analytics microservice for time-series sensor data

- *"What's the CO2 level in room 5.01?"*- Knowledge stores (MySQL for telemetry, Jena Fuseki for SPARQL)

- *"Show me temperature trends for the last week"*- Optional AI helpers (NL2SPARQL, local LLM via Ollama)

- *"Are there any anomalies in HVAC performance today?"*- A frontend chat UI and optional 3D visualiser/API

- *"Compare air quality between the office and data center"*

The goal: enable occupants and operators to ask questions like “What’s the CO2 in room 2.11?” or “Are there anomalies in HVAC today?” and receive clear, unit-aware answers with sensible defaults (UK indoor guidelines) and data-backed artifacts.

...and receive **instant, data-backed answers** with charts, insights, and actionable recommendations.

Key features:

### Why OntoBot?

- Standardized payloads from actions to analytics (flat or nested)

Traditional building management systems require:- Robust key matching and timestamp normalization

- ❌ Complex interfaces with hundreds of menus- UK-oriented thresholds/units in responses

- ❌ Technical knowledge of sensor IDs and database schemas- Health checks and a smoke test for end-to-end validation

- ❌ Manual data export and analysis in spreadsheets

- ❌ Hours of work for simple questionsNext, see Setup, Services, and Customization for new buildings.


**OntoBot changes this:**
- ✅ **Natural language queries** - just ask like you're talking to a colleague
- ✅ **Typo-tolerant** - "NO2 Levl Sensor" → "NO2_Level_Sensor" (fuzzy matching)
- ✅ **Instant analytics** - 30+ analysis types with auto-generated charts
- ✅ **Semantic understanding** - knows relationships between sensors, rooms, and systems
- ✅ **Multi-building support** - switch between buildings seamlessly
- ✅ **Production-grade** - Docker-first, health-monitored, fully documented

---

## Architecture Overview

OntoBot is built on a **microservices architecture** with clear separation of concerns:

```
┌──────────────────────────────────────────────────────────────┐
│                     User Interface                           │
│  React Frontend (Port 3000) - Chat UI, Artifact Viewer      │
└────────────────────────┬─────────────────────────────────────┘
                         │ REST API
┌────────────────────────▼─────────────────────────────────────┐
│                  Conversational AI                           │
│  Rasa Core (5005) - Intent/Entity/Dialogue                  │
│  Action Server (5055) - Business Logic & Orchestration      │
└─┬──────────────┬──────────────┬──────────────┬──────────────┘
  │              │              │              │
  ▼              ▼              ▼              ▼
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐
│Knowledge│  │Analytics│  │Decider  │  │  Databases  │
│ Fuseki  │  │ Service │  │ Service │  │MySQL/TSDB/  │
│ (3030)  │  │ (6000)  │  │ (6009)  │  │Cassandra    │
└─────────┘  └─────────┘  └─────────┘  └─────────────┘
```

### Core Components

#### 1. **Frontend Layer**
- **React-based chat interface** with real-time message streaming
- **Artifact viewer** for charts, tables, and data exports
- **Responsive design** - works on desktop, tablet, and mobile

#### 2. **Conversational AI Layer**
- **Rasa Core**: Intent classification (30+ intents), entity extraction, dialogue management
- **Action Server**: Query orchestration, sensor name resolution, SPARQL execution, analytics dispatch
- **Typo-tolerant**: Uses RapidFuzz for 80%+ similarity matching (configurable threshold)

#### 3. **Knowledge Layer**
- **Jena Fuseki**: SPARQL endpoint storing Brick-schema knowledge graphs
- **680-1600 sensors** per building with semantic relationships
- **25+ ontology prefixes** (Brick, SOSA, QUDT, BACnet, etc.)

#### 4. **Analytics Layer**
- **30+ analysis types**: Descriptive, diagnostic, predictive, prescriptive
- **Auto-generated artifacts**: PNG charts, CSV exports, JSON results
- **Machine learning**: Anomaly detection, forecasting, clustering

#### 5. **Data Layer**
- **Multi-database support**: MySQL (Building 1), TimescaleDB (Building 2), Cassandra (Building 3)
- **Time-series optimized**: Efficient storage and retrieval of sensor telemetry
- **Scalable**: Handles millions of readings per day

---

## Key Features

### 🧠 Intelligent Sensor Resolution

**Problem**: Users don't know exact sensor names ("NO2 Levl Sensor 5.09" vs "NO2_Level_Sensor_5.09")

**Solution**: Three-layer fuzzy matching system
1. **Extract patterns**: Regex extraction of sensor-like strings
2. **Normalize**: Space/underscore/case normalization
3. **Fuzzy match**: RapidFuzz WRatio scoring (default threshold: 80)

**Result**: 
- "air temp sensor 501" → "Air_Temperature_Sensor_5.01" (Score: 97.5)
- "NO2 Levl Sensor 509" → "NO2_Level_Sensor_5.09" (Score: 100)
- "co2 level 5.04" → "CO2_Level_Sensor_5.04" (Score: 95.8)

📖 **[Read more: Typo Tolerance Guide](typo_tolerance.md)**

---

### 📊 Automated Analytics

**Problem**: Manual data analysis is time-consuming and error-prone

**Solution**: 30+ pre-built analysis types with one-click execution

**Categories**:
- **Descriptive**: Summary statistics, histograms, distributions
- **Diagnostic**: Correlation analysis, pattern recognition, variance analysis
- **Predictive**: Trend forecasting, anomaly prediction, regression
- **Prescriptive**: Optimization, what-if scenarios, threshold recommendations
- **Real-time**: Live dashboards, streaming analytics, alert generation

**Example Query**:
```
User: "Show me temperature trends for the last week"
```

**OntoBot Response**:
1. Extracts sensor: "temperature" → "Air_Temperature_Sensor_5.01"
2. Queries Fuseki for sensor metadata (UUID, location, unit)
3. Fetches time-series data from database (7 days)
4. Calls Decider Service → recommends "trend_analysis"
5. Executes analytics → generates chart + CSV
6. Returns summary: "Temperature averaged 21.5°C with slight upward trend..."

📖 **[Read more: Analytics API](analytics_api.md)**

---

### 🏢 Multi-Building Support

**Problem**: Different buildings have different databases, sensor counts, and schemas

**Solution**: Building-specific Docker Compose files with auto-detection

**Supported Buildings**:
- **Building 1 (ABACWS)**: 680 sensors, MySQL database, office environment
- **Building 2 (Office)**: 329 sensors, TimescaleDB, commercial workspace
- **Building 3 (Data Center)**: 597 sensors, Cassandra, high-availability IT facility

**Switch Buildings**:
```powershell
# Stop current building
docker-compose -f docker-compose.bldg1.yml down

# Start different building
docker-compose -f docker-compose.bldg2.yml up -d
```

📖 **[Read more: Multi-Building Configuration](multi_building.md)**

---

### 🎯 Semantic Understanding

**Problem**: Users want to ask conceptual questions, not SQL queries

**Solution**: Brick-schema knowledge graphs + SPARQL queries

**Example**:
```
User: "What sensors monitor air quality in room 5.01?"

Semantic Resolution:
1. "air quality" → [CO2_Level, NO2_Level, VOC_Level, Particulate_Matter]
2. "room 5.01" → brick:hasLocation bldg:Room_5.01
3. SPARQL query: Find all air-quality-related sensors in that location

Result: 4 sensors found with current readings + metadata
```

**Relationships Understood**:
- Spatial: `brick:hasLocation`, `brick:isPartOf`
- Functional: `brick:feeds`, `brick:controls`
- Taxonomic: `brick:Temperature_Sensor` → `brick:Sensor`

📖 **[Read more: Knowledge Graphs](knowledge_graphs.md)**

---

### 🔄 Natural Language to SPARQL (Optional)

**Problem**: Hand-crafting SPARQL queries for every user question is impractical

**Solution**: T5-based transformer model trained on 10,000+ NL-SPARQL pairs

**Example**:
```
Input: "Show me all temperature sensors on floor 5"

NL2SPARQL Output:
SELECT ?sensor ?label WHERE {
  ?sensor rdf:type brick:Temperature_Sensor .
  ?sensor brick:hasLocation ?room .
  ?room brick:isPartOf bldg:Floor_5 .
  ?sensor rdfs:label ?label .
}
```

**Training Dataset**: Custom-generated from building ontologies (see `Assets/dataset_generator/`)

📖 **[Read more: NL2SPARQL Setup](nl2sparql.md)**

---

### 💬 LLM Response Enhancement (Optional)

**Problem**: Raw data isn't always user-friendly

**Solution**: Ollama + Mistral 7B for natural language summaries

**Example**:
```
Raw Data:
{
  "Air_Temperature_Sensor_5.01": [21.5, 21.6, 21.8, 22.1, 22.3],
  "analysis": "upward_trend",
  "rate_of_change": 0.2
}

LLM Summary:
"The temperature in room 5.01 has been gradually increasing over 
the last 5 hours, rising from 21.5°C to 22.3°C. This represents 
a 0.8°C increase, which is within normal daily variation. The 
current temperature is comfortable and within the recommended 
range of 20-24°C for office environments."
```

📖 **[Read more: LLM Integration](llm_integration.md)**

---

## Technology Stack

### Core Technologies

 | Component | Technology | Version | Purpose | 
 | ----------- | ----------- | --------- | --------- | 
 | **Conversational AI** | Rasa Open Source | 3.6.20 | Intent/entity/dialogue | 
 | **Action Server** | Rasa SDK | 3.6.0 | Custom business logic | 
 | **Knowledge Store** | Apache Jena Fuseki | 4.7.0 | SPARQL endpoint | 
 | **Analytics** | Flask + scikit-learn | 3.0 / 1.3 | Time-series analysis | 
 | **Frontend** | React + TypeScript | 18 / 5.0 | User interface | 
 | **Fuzzy Matching** | RapidFuzz | 2.13.7 | Sensor name resolution | 

### Databases

 | Building | Database | Version | Optimized For | 
 | ---------- | ---------- | --------- | --------------- | 
 | Building 1 | MySQL | 8.0 | General-purpose RDBMS | 
 | Building 2 | TimescaleDB | 14 | Time-series queries | 
 | Building 3 | Cassandra | 4.0 | High-write throughput | 

### Optional Services

 | Service | Technology | Purpose | 
 | --------- | ----------- | --------- | 
 | **NL2SPARQL** | T5-base (Hugging Face) | NL → SPARQL translation | 
 | **LLM** | Ollama + Mistral 7B | Response summarization | 

---

## Use Cases

### 1. Building Operations
- **"What's the current HVAC status?"** → Real-time system overview
- **"Are there any equipment failures?"** → Anomaly detection across all systems
- **"Show me energy consumption trends"** → Historical analysis with forecasting

### 2. Indoor Environmental Quality
- **"Is the air quality acceptable in meeting room 3?"** → Multi-sensor assessment
- **"Why is it cold in office 5.01?"** → Diagnostic analysis of temperature control
- **"Compare comfort levels across floors"** → Comparative analytics

### 3. Energy Management
- **"Which zones are using the most energy?"** → Resource allocation insights
- **"Predict energy usage for next week"** → Forecasting with ARIMA/Prophet
- **"Optimize HVAC schedule for cost savings"** → Prescriptive recommendations

### 4. Maintenance Planning
- **"When was sensor X last calibrated?"** → Metadata queries
- **"Show me sensors with unusual readings"** → Anomaly detection
- **"Generate monthly sensor health report"** → Automated reporting

### 5. Research & Analytics
- **"Correlation between temperature and occupancy"** → Statistical analysis
- **"Cluster similar spaces by environmental patterns"** → Machine learning
- **"Export last month's data for all CO2 sensors"** → Data extraction

---

## System Requirements

### Development Environment
- **OS**: Windows 10/11, Linux (Ubuntu 20.04+), macOS 11+
- **RAM**: 8 GB minimum, 16 GB recommended
- **Storage**: 20 GB free space
- **Docker**: Docker Desktop 4.0+ or Docker Engine 20.10+
- **Docker Compose**: 2.0+

### Production Deployment
- **Server**: 4 CPU cores, 16 GB RAM minimum
- **Storage**: 100 GB SSD (database growth depends on sensor count and retention)
- **Network**: 1 Gbps network interface
- **OS**: Linux server (Ubuntu 22.04 LTS recommended)

### Browser Support (Frontend)
- Chrome 90+, Firefox 88+, Safari 14+, Edge 90+

---

## Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/suhasdevmane/OntoBot.git
cd OntoBot
```

### 2. Choose Building
```bash
# Building 1 (MySQL, 680 sensors)
docker-compose -f docker-compose.bldg1.yml up -d

# Building 2 (TimescaleDB, 329 sensors)
docker-compose -f docker-compose.bldg2.yml up -d

# Building 3 (Cassandra, 597 sensors)
docker-compose -f docker-compose.bldg3.yml up -d
```

### 3. Verify Services
```powershell
# Run health check script
pwsh -File scripts/check-health.ps1
```

### 4. Open Frontend
```
http://localhost:3000
```

### 5. Start Chatting
```
You: What sensors are available?
Bot: I found 680 sensors in the ABACWS building...

You: Show me temperature in room 5.01
Bot: Current temperature: 21.5°C [Chart attached]
```

📖 **[Read more: Quickstart Guide](quickstart.md)**

---

## Adapting to Your Building

OntoBot is designed to be **building-agnostic**. Here's how to adapt it:

### Step 1: Create Brick Ontology
```turtle
# your-building.ttl
@prefix brick: <https://brickschema.org/schema/Brick#> .
@prefix mybldg: <http://yourbuilding.example.com#> .

mybldg:Temp_Sensor_101 a brick:Temperature_Sensor ;
    rdfs:label "Temperature Sensor 101" ;
    brick:hasLocation mybldg:Room_101 ;
    brick:hasUnit unit:DEG_C .
```

### Step 2: Populate Database
```sql
CREATE TABLE telemetry (
  sensor_uuid VARCHAR(36),
  timestamp DATETIME,
  sensor_value FLOAT
);

-- Import historical data
LOAD DATA INFILE 'sensor_data.csv' INTO TABLE telemetry;
```

### Step 3: Generate Sensor List
```bash
# Extract sensor names from ontology
cat your-building.ttl | grep "rdfs:label" | cut -d'"' -f2 > sensor_list.txt
```

### Step 4: Configure Environment
```yaml
# docker-compose.yml
action_server:
  environment:
    - DB_HOST=your_mysql_server
    - FUSEKI_URL=http://fuseki:3030/your_building/sparql
    - SENSOR_FUZZY_THRESHOLD=80
```

### Step 5: Train Rasa Model
```bash
docker-compose run --rm rasa-train
```

📖 **[Read more: Customization Guide](customization.md)**

---

## Documentation Structure

### Getting Started
- **[Introduction](introduction.md)** ← You are here
- **[Quickstart](quickstart.md)** - 5-minute setup guide
- **[Installation](installation.md)** - Detailed setup instructions
- **[Architecture](architecture.md)** - System design overview

### Core Features
- **[Typo Tolerance](typo_tolerance.md)** - Fuzzy sensor matching
- **[Analytics API](analytics_api.md)** - 30+ analysis types
- **[Backend Services](backend_services.md)** - Service reference
- **[Action Server Architecture](action_server_architecture.md)** - Deep dive

### Building-Specific Guides
- **[Building 1: ABACWS](building1_abacws.md)** - 680 sensors, MySQL
- **[Building 2: Office](building2_office.md)** - 329 sensors, TimescaleDB
- **[Building 3: Data Center](building3_datacenter.md)** - 597 sensors, Cassandra

### Advanced Topics
- **[Multi-Building Support](multi_building.md)** - Switching between buildings
- **[Database Integration](database_integration.md)** - Multi-DB support
- **[NL2SPARQL Training](nl2sparql.md)** - Train custom models
- **[LLM Integration](llm_integration.md)** - Ollama setup
- **[Customization](customization.md)** - Adapt to your building
- **[Testing & Operations](testing_ops.md)** - Production deployment

### Reference
- **[API Reference](api_reference.md)** - Complete API documentation
- **[Data Payloads](data_payloads.md)** - Message formats
- **[Frontend UI](frontend_ui.md)** - React app guide
- **[Troubleshooting](troubleshooting.md)** - Common issues

---

## Project Goals

1. **Democratize building data** - Make sensor data accessible to everyone, not just data scientists
2. **Natural interaction** - Enable building conversations, not database queries
3. **Actionable insights** - Provide recommendations, not just raw data
4. **Production-ready** - Battle-tested, documented, and maintainable
5. **Open and extensible** - Easy to adapt to new buildings, sensors, and analytics

---

## Research Foundation

OntoBot is built on research in:
- **Semantic Web**: Brick schema, SPARQL, RDF triple stores
- **Natural Language Processing**: Intent classification, entity extraction, seq2seq models
- **Conversational AI**: Dialogue management, slot filling, form validation
- **Time-Series Analytics**: Anomaly detection, forecasting, statistical analysis
- **Human-Building Interaction**: Usability, accessibility, domain-specific language understanding

📄 **Publication**: *[OntoBot: A Conversational AI Framework for Smart Buildings]* (Link to paper)

---

## Community & Support

- **GitHub**: [github.com/suhasdevmane/OntoBot](https://github.com/suhasdevmane/OntoBot)
- **Documentation**: [suhasdevmane.github.io](https://suhasdevmane.github.io)
- **Issues**: Report bugs and request features on GitHub Issues
- **Discussions**: Join conversations on GitHub Discussions

---

## License

OntoBot is released under the **MIT License**. See [LICENSE](https://github.com/suhasdevmane/OntoBot/blob/main/LICENSE) for details.

---

## Next Steps

Ready to get started? Choose your path:

- 🚀 **[Quickstart](quickstart.md)** - Get running in 5 minutes
- 📚 **[Architecture](architecture.md)** - Understand the system design
- 🏗️ **[Customization](customization.md)** - Adapt to your building
- 🔧 **[Backend Services](backend_services.md)** - Deep dive into services

---

**OntoBot** - Making buildings talk, listen, and understand. 🏢💬🤖
