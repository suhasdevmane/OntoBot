---
title: Quick Start Guide
layout: post
category: docs
permalink: /docs/quickstart/
date: 2025-10-08
---


# Quick Start Guide# Quick Start Guide


Get OntoBot up and running in **5 minutes**. This guide covers the essentials to start chatting with your building.Get OntoBot up and running in 30 minutes. This guide covers prerequisites, installation, and your first conversation with the chatbot.


---## Prerequisites


## Prerequisites### Required Software


### System Requirements| Software | Version | Purpose | Download |

 | ---------- | --------- | --------- | ---------- | 

**Minimum**:| **Docker Desktop** | 20.10+ | Container runtime | [docker.com](https://www.docker.com/products/docker-desktop) |

- 8 GB RAM| **Docker Compose** | 2.0+ | Multi-container orchestration | Included with Docker Desktop |

- 4 CPU cores| **Git** | 2.30+ | Version control | [git-scm.com](https://git-scm.com/) |

- 20 GB free disk space| **Node.js** | 16+ | Frontend development (optional) | [nodejs.org](https://nodejs.org/) |

- Windows 10/11, macOS 11+, or Linux (Ubuntu 20.04+)| **Python** | 3.8+ | Scripts & notebooks (optional) | [python.org](https://www.python.org/) |


**Recommended**:### System Requirements

- 16 GB RAM

- 8 CPU cores**Minimum:**

- 50 GB SSD- CPU: 4 cores

- Windows 11, macOS 13+, or Ubuntu 22.04 LTS- RAM: 8 GB

- Disk: 20 GB free space

### Required Software- OS: Windows 10/11, macOS 11+, Ubuntu 20.04+


 | Software | Version | Download | **Recommended:**

 | ---------- | --------- | ---------- | - CPU: 8 cores

 | **Docker Desktop** | 20.10+ | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) | - RAM: 16 GB

 | **Docker Compose** | 2.0+ | Included with Docker Desktop | - Disk: 50 GB SSD

 | **Git** | 2.30+ | [git-scm.com](https://git-scm.com/) | - OS: Windows 11, macOS 13+, Ubuntu 22.04+


### Docker Configuration### Docker Configuration


**Increase Memory Allocation**:**Memory Allocation:**

1. Open Docker Desktop

```

2. Settings → Resources → MemoryDocker Desktop → Settings → Resources → Memory: 8 GB minimum

3. Set to **8 GB minimum** (16 GB recommended)

```

4. Click "Apply & Restart"

**File Sharing (Windows):**

**Enable File Sharing (Windows)**:```

1. Settings → Resources → File SharingDocker Desktop → Settings → Resources → File Sharing

2. Add: `C:\Users\<username>\Documents\GitHub`Add: C:\Users\<username>\Documents\GitHub\OntoBot

3. Click "Apply & Restart"```


---**WSL2 Backend (Windows - Recommended):**

```

## InstallationDocker Desktop → Settings → General → Use WSL 2 based engine: ✓

```

### Step 1: Clone Repository

## Installation

```bash

git clone https://github.com/suhasdevmane/OntoBot.git### Step 1: Clone Repository

cd OntoBot

```bash

# Clone with submodules

**Repository Structure**:git clone --recursive https://github.com/suhasdevmane/OntoBot.git

```

OntoBot/# Or if already cloned

├── docker-compose.bldg1.yml      # Building 1 (ABACWS - 680 sensors)cd OntoBot

├── docker-compose.bldg2.yml      # Building 2 (Office - 329 sensors)git submodule update --init --recursive

├── docker-compose.bldg3.yml      # Building 3 (Data Center - 597 sensors)

```

├── docker-compose.extras.yml     # Optional: NL2SPARQL + Ollama

├── rasa-bldg1/                   # Rasa models & actions (Building 1)**Repository Structure:**

├── rasa-frontend/                # React chat interface

```

├── microservices/                # Analytics serviceOntoBot/

├── decider-service/              # Query classifier├── docker-compose.bldg1.yml    # Building 1 (ABACWS)

├── Transformers/                 # NL2SPARQL models (optional)├── docker-compose.bldg2.yml    # Building 2 (Office)

└── bldg1/, bldg2/, bldg3/        # Brick ontologies├── docker-compose.bldg3.yml    # Building 3 (Data Center)

```├── docker-compose.extras.yml   # AI services (optional)

├── rasa-bldg1/                 # Rasa project for Building 1

### Step 2: Choose a Building├── rasa-bldg2/                 # Rasa project for Building 2

├── rasa-bldg3/                 # Rasa project for Building 3

**For your first run, use Building 1 (ABACWS)** - it's the most validated with real data.├── rasa-frontend/              # React UI

├── microservices/              # Analytics API

 | Building | Sensors | Database | Best For | ├── Transformers/               # T5 NL2SPARQL models

 | ---------- | --------- | ---------- | ---------- | └── README.md

 | **Building 1 (ABACWS)** | 680 | MySQL | First-time users, development | ```

 | Building 2 (Office) | 329 | TimescaleDB | Time-series optimization | 

 | Building 3 (Data Center) | 597 | Cassandra | High-write throughput | ### Step 1.5: Configure environment (.env)


### Step 3: Start ServicesCompose files use environment variables for secrets and CORS. Create your local `.env` from the template and set the required values:


**Quick Start** (core services only):```powershell

```bash
Copy-Item -Path .env.example -Destination .env

docker-compose -f docker-compose.bldg1.yml up -d# Open .env and set values, especially:

```# FRONTEND_ORIGIN=http://localhost:3000

# ALLOWED_ORIGINS=http://localhost:3000

**With AI Services** (adds NL2SPARQL + Ollama):# JWT_SECRET=change_me_in_prod

```bash
```

docker-compose -f docker-compose.bldg1.yml -f docker-compose.extras.yml up -d

```Optional: Validate your chosen stack before starting:


**What's Starting**:```powershell

- ✅ Rasa Core (conversational AI)docker compose --env-file .env -f docker-compose.bldg1.yml config

- ✅ Action Server (business logic + typo tolerance)# Or for other stacks/overlays

- ✅ Jena Fuseki (knowledge graph)# docker compose --env-file .env -f docker-compose.bldg2.yml config

- ✅ MySQL (sensor telemetry)# docker compose --env-file .env -f docker-compose.bldg3.yml -f docker-compose.extras.yml config

- ✅ Analytics Service (30+ analysis types)

```

- ✅ Decider Service (query classification)

- ✅ HTTP File Server (artifact serving)If you see warnings like "The \"PG_THINGSBOARD_DB\" variable is not set.", add that variable to `.env` and re-run.

- ✅ React Frontend (chat UI)

- ✅ NL2SPARQL (optional - natural language to SPARQL)### Step 2: Choose a Building

- ✅ Ollama/Mistral (optional - LLM summaries)

For your first run, start with **Building 1 (ABACWS)** - it has real-world data and is the most validated.

### Step 4: Wait for Initialization

```powershell

Services take **2-3 minutes** to fully start:# Windows PowerShell

cd OntoBot

```bash

# Check status# Linux/macOS

docker pscd OntoBot

```

# Expected output (10 containers):

# CONTAINER ID   IMAGE                  STATUS         PORTS### Step 3: Start Services

# abc123...      rasa_bldg1            Up 2 mins      0.0.0.0:5005->5005/tcp

# def456...      action_server_bldg1   Up 2 mins      0.0.0.0:5055->5055/tcp**Option A: Basic Stack (Fastest)**

# ghi789...      frontend              Up 2 mins      0.0.0.0:3000->3000/tcp

# ...Starts Rasa chatbot + database only:

```

```bash

### Step 5: Verify Health# Windows PowerShell

docker-compose -f docker-compose.bldg1.yml up -d rasa_bldg1 action_server_bldg1 mysqlserver

**PowerShell** (Windows):

```powershell# Linux/macOS

pwsh -File scripts/check-health.ps1docker-compose -f docker-compose.bldg1.yml up -d rasa_bldg1 action_server_bldg1 mysqlserver

```


**Bash** (Linux/macOS):**Option B: Full Stack (Recommended)**

```bash

bash scripts/check-health.shIncludes analytics, frontend, and all features:

```

```bash

**Expected Output**:docker-compose -f docker-compose.bldg1.yml up -d

```

✓ Rasa Core: OK (http://localhost:5005)

✓ Action Server: OK (http://localhost:5055/health)**Option C: With AI Services**

✓ Fuseki: OK (http://localhost:3030/$/ping)

✓ Analytics: OK (http://localhost:6001/health)Adds NL2SPARQL and Mistral LLM:

✓ Decider: OK (http://localhost:6009/health)

✓ File Server: OK (http://localhost:8080/)

```bash

✓ Frontend: OK (http://localhost:3000)docker-compose -f docker-compose.bldg1.yml -f docker-compose.extras.yml up -d

```


---### Step 4: Wait for Services


## First ConversationServices take **2-3 minutes** to fully initialize:


### Open Chat Interface

```powershell

# Check status

Navigate to: **http://localhost:3000**docker ps


You'll see the chat interface with a welcome message.# Expected output:

# CONTAINER ID   IMAGE                    STATUS         PORTS

### Try Your First Query# abc123...      rasa_bldg1              Up 2 minutes   0.0.0.0:5005->5005/tcp

# def456...      action_server_bldg1     Up 2 minutes   0.0.0.0:5055->5055/tcp

**Simple Sensor Query**:# ghi789...      mysql:8.0               Up 2 minutes   0.0.0.0:3307->3306/tcp

```# jkl012...      rasa_frontend           Up 2 minutes   0.0.0.0:3000->3000/tcp

What is the temperature in room 5.01?```

```

**Health Check:**

**Expected Response** (~500ms):

```bash

The current temperature in room 5.01 is 21.5°C # Windows

(measured at 2025-10-31 14:30:00).curl http://localhost:5005/version

```

# Linux/macOS

---curl http://localhost:5005/version


## Example Queries# Expected: {"version": "3.6.12", "minimum_compatible_version": "3.0.0"}

```

### Basic Sensor Queries

### Step 5: Access the UI

```

What is the CO2 level in room 5.01?Open your browser to: **http://localhost:3000**

Show me the humidity in room 5.15

What's the air quality in room 5.20?You should see:

List all sensors in room 5.04

```![OntoBot Home Dashboard](../images/home-dashboard.png)


### Typo-Tolerant Queries (NEW)**Service Cards:**

- 🤖 **Rasa Core**: Green (Ready)

**The system automatically corrects sensor name typos:**- ⚙️ **Action Server**: Green (Ready)

- 🔌 **Analytics**: Green (Ready)

```- 📊 **Decider**: Green (Ready)

# Typo: "NO2 Levl Sensor 5.09"

# Auto-corrected to: "NO2_Level_Sensor_5.09" ✓## Your First Conversation


What is the NO2 Levl Sensor 5.09?### Chat Interface

Show me air temp sensor 501

What's the co2 level 5.04?1. Click **"Chat"** in the top navigation

```2. You'll see the chat interface with example questions

3. Try a simple query:

**How it works**:

- Fuzzy matching with 80% similarity threshold (configurable)

```

- Handles spaces, underscores, case variationsWhat is the temperature in zone 5.04?

- Corrects typos like "Levl" → "Level"```

- Score: 100 (exact match after normalization)

**Expected Response:**

📖 **[Learn more: Typo Tolerance Guide](typo_tolerance.md)**```

The current temperature in zone 5.04 is 22.5°C (measured at 2025-01-08 14:30:00).

### Time-Based Queries

```


```### Example Questions

What was the average temperature yesterday?

Show me CO2 levels for the last 3 hours**Simple Queries:**

What's the temperature trend over the last week?```

```What is the CO2 level in zone 5.01?

Show me the humidity in zone 5.15

### Analytics QueriesWhat's the air quality in zone 5.20?

```

**Trend Analysis**:

```**Time-Based Queries:**

Show me temperature trends for room 5.04

```

```What was the average temperature yesterday?

Show me CO2 levels for the last 3 hours

**Response** (~2-3 seconds):What's the peak humidity today?

- Natural language summary

```

- Line chart showing trend

- Statistics (mean, std dev, rate of change)**Comparative Queries:**

```

**Anomaly Detection**:Which zone has the highest temperature?

```Compare CO2 levels between zone 5.01 and 5.10

Detect anomalies in CO2 levels for the last 24 hoursWhat's the correlation between temperature and humidity?

```


**Response**:**Analytics Queries:**

- Anomaly count and timestamps

```

- Chart with anomalies highlightedShow me temperature trends for zone 5.04

- Recommended actionsDetect anomalies in CO2 levels

Predict the temperature for the next hour

**Forecasting**:```

```

Predict temperature for the next 2 hours### Understanding Responses

```

**Successful Query:**

**Response**:```json

- Forecast values{

- Confidence intervals  "response": "The current temperature is 22.5°C",

- Chart with predictions  "data": {

    "sensor": "Air_Temperature_Sensor_5.04",

**Comparative Analysis**:    "value": 22.5,

```    "unit": "°C",

Compare air quality between room 5.01 and room 5.10    "timestamp": "2025-01-08 14:30:00"

```  },

  "visualization": "chart_url"

**Response**:}

- Side-by-side comparison

```

- Statistical differences

- Recommendation (which room has better air quality)**Analytics Query:**

```json

---{

  "response": "Here's the temperature trend analysis:",

## Understanding Responses  "analytics_result": {

    "mean": 22.3,

### Response Components    "std_dev": 0.8,

    "trend": "increasing",

**1. Natural Language Summary**:    "anomalies": []

```  },

The temperature in room 5.01 has been gradually increasing over   "chart": "base64_encoded_image"

the last week, rising from 20.5°C to 22.3°C. This represents a }

1.8°C increase, which is within normal variation.```

```

## Configuration

**2. Data Attachment** (optional):

- **Charts**: Line charts, bar charts, scatter plots### Settings Page

- **Tables**: CSV exports with sensor data

- **JSON**: Raw data for programmatic accessNavigate to: **http://localhost:3000/settings**


**3. Metadata**:#### Step 1: Select Building

- Sensor name and UUID

- Location (room, floor, building)The UI auto-detects the active building:

- Unit of measurement- **Building 1**: 680 sensors (ABACWS)

- Timestamp of reading- **Building 2**: 329 sensors (Office)

- Confidence score (for predictions)- **Building 3**: 597 sensors (Data Center)


### Response TypesNo configuration needed - it just works!


**Simple Answer**:#### Step 2: Configure Endpoints

```

User: What is the temperature?Default endpoints (usually don't need changes):

Bot: 21.5°C

```yaml

Rasa Core: http://localhost:5005

**Detailed Answer with Context**:Action Server: http://localhost:5055

```Analytics: http://localhost:6001

User: What is the temperature in room 5.01?Decider: http://localhost:6009

Bot: The current temperature in room 5.01 is 21.5°C File Server: http://localhost:8080

     (measured at 2025-10-31 14:30:00). This is within NL2SPARQL: http://localhost:6005

     the comfortable range of 20-24°C.Ollama: http://localhost:11434

```Fuseki: http://localhost:3030

```

**Analytics Response with Artifact**:

```#### Step 3: Test Connectivity

User: Show me temperature trends

Bot: Here's the temperature trend analysis for room 5.01:Click **"Test All Endpoints"** button:

     [Chart showing 7-day temperature trend]

     ✅ All green = Ready to go  

     Summary:❌ Red indicators = Check Docker containers

     - Average: 21.8°C

     - Trend: Slightly increasing (+0.15°C/day)### Building Selection

     - Anomalies: None detected

```To switch buildings:


**Error Response with Suggestion**:```powershell

```# Stop current building

User: What is the sensor XYZ?docker-compose -f docker-compose.bldg1.yml down

Bot: I couldn't find sensor "XYZ". Did you mean:

     - Air_Temperature_Sensor_5.01 (similarity: 85%)# Start different building

     - NO2_Level_Sensor_5.09 (similarity: 80%)docker-compose -f docker-compose.bldg2.yml up -d

```

# Wait for startup

---Start-Sleep -Seconds 120


## Quick Configuration# Refresh browser

# Frontend auto-detects new building

### 1. Adjust Typo Tolerance Threshold

```


**Default**: 80% similarity## Training Your First Model


**Too many false matches?** Increase threshold:### T5 Model Training Tab

```yaml

# docker-compose.bldg1.yml1. Navigate to **Settings** → **T5 Model Training** tab

action_server_bldg1:2. Click **"Add New Training Example"**

  environment:

    - SENSOR_FUZZY_THRESHOLD=90  # More strict (90%)### Add Training Example

```

**Form Fields:**

**Too few matches?** Decrease threshold:

```yaml
```yaml

action_server_bldg1:Question: "What is the temperature in zone 5.04?"

  environment:Sensors: Air_Temperature_Sensor_5.04

    - SENSOR_FUZZY_THRESHOLD=70  # More lenient (70%)SPARQL Query: |

```  PREFIX brick: <https://brickschema.org/schema/Brick#>

  SELECT ?value ?timestamp WHERE {

**Restart to apply**:    <sensor:Air_Temperature_Sensor_5.04> brick:hasValue ?value .

```bash    <sensor:Air_Temperature_Sensor_5.04> brick:hasTimestamp ?timestamp .

docker-compose -f docker-compose.bldg1.yml restart action_server_bldg1  }

```Category: Temperature Query

Notes: Basic temperature retrieval for single zone

### 2. Enable/Disable AI Services

```


**Disable LLM Summarization** (faster responses):**Click "Add Example"**

```yaml

action_server_bldg1:### Train Model

  environment:

    - ENABLE_SUMMARIZATION=false1. Set **Training Epochs**: 3 (default)

```2. Click **"Train Model"** button

3. Monitor progress in real-time:

**Disable Analytics** (simple queries only):

```yaml
```

action_server_bldg1:Epoch 1/3 - Loss: 0.245 (30%)

  environment:Epoch 2/3 - Loss: 0.189 (60%)

    - ENABLE_ANALYTICS=falseEpoch 3/3 - Loss: 0.142 (100%)

```✓ Training complete!

```

### 3. Change Database Connection

### Start & Verify

**Building 1** uses MySQL by default. To use a different database:

```yaml1. **Start Service**: Click "Start NL2SPARQL Service"

action_server_bldg1:   - Status changes to: 🟢 Running

  environment:   

    - DB_HOST=your_mysql_host2. **Verify**: Click "Test NL2SPARQL"

    - DB_NAME=your_database   - Test query gets translated

    - DB_USER=your_username   - Response shows SPARQL output

    - DB_PASSWORD=your_password

```**Congratulations!** Your model is trained and ready.


---## Exploring Features


## Switching Buildings### Analytics


### Stop Current BuildingQuery types available:


```bash**Statistical Analysis:**

docker-compose -f docker-compose.bldg1.yml down

```

```Show me the average temperature for the last week

What's the standard deviation of CO2 levels?

### Start Different BuildingCalculate the correlation between temperature and humidity

```

**Building 2** (TimescaleDB):

```bash**Trend Detection:**

docker-compose -f docker-compose.bldg2.yml up -d

```

```Show me temperature trends for zone 5.04

Is the CO2 level increasing or decreasing?

**Building 3** (Cassandra):What's the pattern in humidity over time?

```bash
```

docker-compose -f docker-compose.bldg3.yml up -d

```**Anomaly Detection:**

```

### Frontend Auto-DetectionDetect unusual temperature readings

Find CO2 spikes in the last 24 hours

The frontend automatically detects the active building:Are there any anomalies in air quality?

1. Checks Rasa model name (bldg1, bldg2, or bldg3)

```

2. Loads appropriate sensor list

3. Adjusts query templates**Forecasting:**

4. No configuration needed!```

Predict the temperature for the next 2 hours

📖 **[Learn more: Multi-Building Support](multi_building.md)**Forecast CO2 levels for tomorrow

What will the humidity be this evening?

---```


## Troubleshooting### Data Visualization


### Issue 1: Services Won't StartCharts are automatically generated:


**Check logs**:- **Line Charts**: Time-series data

```bash- **Bar Charts**: Comparisons

docker logs rasa_bldg1- **Scatter Plots**: Correlations

docker logs action_server_bldg1- **Heatmaps**: Multi-sensor patterns

```

**View Options:**

**Common causes**:- Zoom in/out

- Insufficient memory → Increase Docker memory to 16 GB- Pan left/right

- Port conflicts → Check if ports 3000, 5005, 5055 are free- Download as PNG

- Missing files → Re-clone repository- View data table


**Solution**:### Health Monitoring

```bash

# Clean up and restartMonitor service health at: **http://localhost:3000/health**

docker-compose -f docker-compose.bldg1.yml down -v

docker system prune -f**Metrics:**

docker-compose -f docker-compose.bldg1.yml up -d- Request count

```- Success rate

- Average response time

### Issue 2: "No sensors found" Error- Error rate

- Service uptime

**Verify sensor list exists**:

```bash**Alerts:**

# Should show 680 sensor names- High error rate (>5%)

cat rasa-bldg1/actions/sensor_list.txt | wc -l- Slow responses (>2s)

```- Service down


**If missing, regenerate**:## Common Issues & Solutions

```bash

# Extract from ontology### Issue 1: Containers Won't Start

grep 'rdfs:label' bldg1/trial/dataset/abacws.ttl | \

  cut -d'"' -f2 > rasa-bldg1/actions/sensor_list.txt**Symptom:**

```

Error response from daemon: Conflict. The container name "/rasa_bldg1" is already in use

**Restart action server**:```

```bash

docker-compose -f docker-compose.bldg1.yml restart action_server_bldg1**Solution:**

```powershell

# Stop all containers

### Issue 3: Slow Responses (>5 seconds)docker-compose -f docker-compose.bldg1.yml down


**Check resource usage**:# Remove orphaned containers

```bashdocker rm -f $(docker ps -aq)

docker stats

```# Start fresh

docker-compose -f docker-compose.bldg1.yml up -d

**If high CPU/memory usage**:```

1. Increase Docker resources to 16 GB RAM

2. Close other applications### Issue 2: Port Already in Use

3. Use simpler queries without analytics

**Symptom:**

**If database is slow**:```

```bash
Error: bind: address already in use (port 5005)

# Check database health

```

docker exec -it mysqlserver mysql -uroot -ppassword -e "SHOW PROCESSLIST;"

```**Solution:**

```powershell

### Issue 4: Frontend Won't Load# Windows - Find process using port

netstat -ano | findstr :5005

**Check frontend container**:taskkill /PID <process_id> /F

```bash

docker logs frontend# Linux/macOS

```lsof -ti:5005 | xargs kill -9


**Common causes**:# Or change port in docker-compose.yml

- Port 3000 in use → Change to 3001 in docker-composeports:

- Build failed → Rebuild: `docker-compose build frontend`  - "5006:5005"  # Use 5006 instead

- CORS issues → Check ALLOWED_ORIGINS in .env

```


**Solution**:### Issue 3: Services Unhealthy

```bash

docker-compose -f docker-compose.bldg1.yml restart frontend**Symptom:**

```

Container status: unhealthy (health check failed)

### Issue 5: Analytics Not Working

```


**Test analytics endpoint**:**Solution:**

```bash
```bash

curl http://localhost:6001/health# Check logs

```docker logs rasa_bldg1


**If unhealthy**:# Common causes:

```bash# 1. Database not ready → Wait longer

# Check logs# 2. Missing files → Check volumes

docker logs microservices# 3. Memory exhausted → Increase Docker memory


# Restart# Restart specific service

docker-compose -f docker-compose.bldg1.yml restart microservicesdocker-compose -f docker-compose.bldg1.yml restart rasa_bldg1

```


📖 **[Full troubleshooting guide](troubleshooting.md)**### Issue 4: No Sensors in Dropdown


---**Symptom:** T5 Training GUI shows "No options" for sensors


## Next Steps**Solution:**

```bash

### Learn Advanced Features# Verify microservices port (should be 6001, not 6000)

curl http://localhost:6001/api/t5/sensors

1. **[Typo Tolerance](typo_tolerance.md)** - Deep dive into fuzzy matching (NEW)

2. **[Analytics API](analytics_api.md)** - 30+ analysis types# Expected: {"sensors": [...], "count": 680}

3. **[Multi-Building Support](multi_building.md)** - Work with different buildings

4. **[Customization](customization.md)** - Adapt to your building# If port 6000: Chrome blocks it (ERR_UNSAFE_PORT)

# See T5_TRAINING_PORT_FIX.md for fix

### Explore the System

```


**Service Architecture**:### Issue 5: Frontend Won't Load

```

User → Frontend (3000) → Rasa (5005) → Action Server (5055)**Symptom:** Browser shows "Connection refused" at localhost:3000

                                         ↓

                    ┌────────────────────┼────────────────────┐**Solution:**

                    ↓                    ↓                    ↓```bash

                 Fuseki (3030)    Analytics (6000)     Database (3306)# Check if container is running

```docker ps | grep rasa_frontend


📖 **[Architecture Guide](architecture.md)**# If not running, check logs

docker logs rasa_frontend

### Add Your Own Building

# Common causes:

**5-Step Process**:# 1. npm install failed → Rebuild image

1. Create Brick ontology (TTL file)# 2. Port 3000 in use → Change to 3001

2. Populate database with sensor telemetry# 3. Missing dependencies → Check package.json

3. Generate sensor_list.txt from ontology

4. Configure environment variables# Rebuild

5. Train Rasa modeldocker-compose -f docker-compose.bldg1.yml up -d --build rasa_frontend

```

📖 **[Customization Guide](customization.md)**

### Issue 6: Slow Responses

---

**Symptom:** Queries take 10+ seconds to respond

## Quick Reference

**Possible Causes:**

### Essential Commands1. **Analytics computation heavy**

   - Use simpler queries first

```bash   - Reduce time range

# Start services   

docker-compose -f docker-compose.bldg1.yml up -d2. **Database slow**

   - Check database container health

# Stop services   - Verify data loaded correctly

docker-compose -f docker-compose.bldg1.yml down   

3. **Insufficient resources**

# View logs (follow mode)   - Increase Docker memory to 16 GB

docker logs -f action_server_bldg1   - Close other applications


# Restart single service**Solution:**

docker-compose -f docker-compose.bldg1.yml restart rasa_bldg1

```bash

# Monitor resource usage

# Check healthdocker stats

pwsh -File scripts/check-health.ps1

# If memory exhausted:

# Clean up (removes volumes!)# Docker Desktop → Settings → Resources → Memory: 16 GB

docker-compose -f docker-compose.bldg1.yml down -v

```

```

## Next Steps

### Service URLs

### Learn More

 | Service | URL | Purpose | 

 | --------- | ----- | --------- | 1. **[Frontend UI Guide](./frontend_ui.md)** - Complete UI reference

 | **Frontend** | http://localhost:3000 | Chat interface | 2. **[T5 Training Guide](./t5_training_guide.md)** - Advanced model training

 | **Rasa Core** | http://localhost:5005 | Conversational AI | 3. **[Backend Services](./backend_services.md)** - Technical deep dive

 | **Action Server** | http://localhost:5055 | Business logic | 4. **[Multi-Building Guide](./multi_building.md)** - Working with different buildings

 | **Analytics** | http://localhost:6001 | Analysis service | 5. **[API Reference](./api_reference.md)** - REST API documentation

 | **Fuseki** | http://localhost:3030 | SPARQL endpoint | 

 | **File Server** | http://localhost:8080 | Artifact serving | ### Advanced Topics

 | **Decider** | http://localhost:6009 | Query classifier | 

**Add Custom Analytics:**

### Quick Tests

```python

# microservices/blueprints/custom_analytics.py

**Test Rasa**:@app.route('/api/analytics/custom', methods=['POST'])

```bashdef custom_analysis():

curl -X POST http://localhost:5005/webhooks/rest/webhook \    # Your analytics code here

  -H "Content-Type: application/json" \    pass

  -d '{"sender":"test","message":"What is the temperature?"}'```

```

**Extend Rasa Actions:**

**Test Action Server**:```python

```bash# rasa-bldg1/actions/actions.py

curl http://localhost:5055/healthclass ActionCustomQuery(Action):

```    def name(self):

        return "action_custom_query"

**Test Analytics**:    

```bash    def run(self, dispatcher, tracker, domain):

curl http://localhost:6001/health        # Your custom logic

```        pass

```

---

**Add Training Examples:**

## Summary

```json

// Transformers/t5_base/training/bldg1/correlation_fixes.json

You now have OntoBot running with:{

  "question": "Your new question",

✅ **10 microservices** orchestrated by Docker Compose    "sensors": ["Sensor_Name"],

✅ **Conversational AI** with Rasa (30+ intents)    "sparql": "Your SPARQL query",

✅ **Typo-tolerant queries** with fuzzy matching (NEW)    "category": "Custom Category"

✅ **30+ analytics types** (descriptive, diagnostic, predictive, prescriptive)  }

✅ **Knowledge graph** with 680+ sensors (Building 1)  ```

✅ **Real-time chat interface** with artifact rendering  

### Community & Support

**Setup Time**: ~5 minutes  

**First Query**: "What is the temperature in room 5.01?"  - **GitHub Issues**: [github.com/suhasdevmane/OntoBot/issues](https://github.com/suhasdevmane/OntoBot/issues)

**Response Time**: ~500ms (simple queries), ~2-3s (analytics queries)- **Documentation**: [suhasdevmane.github.io](https://suhasdevmane.github.io)

- **Email**: devmanesp1@cardiff.ac.uk

---

### Contributing

## Get Help

1. Fork the repository

- **Documentation**: [suhasdevmane.github.io](https://suhasdevmane.github.io)2. Create feature branch (`git checkout -b feature/amazing-feature`)

- **GitHub Issues**: [github.com/suhasdevmane/OntoBot/issues](https://github.com/suhasdevmane/OntoBot/issues)3. Commit changes (`git commit -m 'Add amazing feature'`)

- **Troubleshooting Guide**: [troubleshooting.md](troubleshooting.md)4. Push to branch (`git push origin feature/amazing-feature`)

5. Open Pull Request

**Ready to explore?** Try these queries next:

## Cheat Sheet

```

Show me temperature trends for the last week### Essential Commands

Detect anomalies in CO2 levels

Compare air quality between different rooms

```powershell

Predict humidity for the next 2 hours# Start Building 1

```docker-compose -f docker-compose.bldg1.yml up -d


---# Stop all services

docker-compose -f docker-compose.bldg1.yml down

**Quick Start Complete!** 🚀 Now explore the [full documentation](introduction.md) for advanced features.

# View logs
docker logs -f rasa_bldg1

# Restart service
docker-compose -f docker-compose.bldg1.yml restart rasa_bldg1

# Check health
curl http://localhost:5005/version

# List containers
docker ps

# Clean up
docker system prune -f
```

### Key URLs

 | Service | URL | 
 | --------- | ----- | 
 | Frontend | http://localhost:3000 | 
 | Chat | http://localhost:3000/chat | 
 | Settings | http://localhost:3000/settings | 
 | Health | http://localhost:3000/health | 
 | Rasa Core | http://localhost:5005 | 
 | Analytics | http://localhost:6001 | 
 | File Server | http://localhost:8080 | 
 | Fuseki | http://localhost:3030 | 
 | ThingsBoard | http://localhost:8082 | 

### Quick Tests

```bash
# Test Rasa
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","message":"hello"}'

# Test Analytics
curl http://localhost:6001/health

# Test NL2SPARQL
curl -X POST http://localhost:6005/predict \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the temperature?"}'

# Test Sensors API
curl http://localhost:6001/api/t5/sensors
```

## Summary

You now have OntoBot running with:
- ✅ Docker containers deployed
- ✅ Rasa chatbot responding
- ✅ Frontend UI accessible
- ✅ Analytics working
- ✅ First model trained

**Total Setup Time:** ~30 minutes

**Next:** Explore the [Frontend UI](./frontend_ui.md) and try advanced queries!
