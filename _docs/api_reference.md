---
title: API Reference
layout: post
category: docs
permalink: /docs/api_reference/
date: 2025-10-08
---


# Complete API Reference# API Reference


**Comprehensive REST API documentation for all OntoBot services with request/response examples, authentication, and best practices.**Complete REST API documentation for all OntoBot services. This reference covers authentication, request/response formats, and detailed endpoint specifications.


---## Table of Contents


## Table of Contents1. [Authentication](#authentication)

2. [Rasa Core API (Port 5005)](#rasa-core-api)

1. [Service Overview](#service-overview)3. [Action Server API (Port 5055)](#action-server-api)

2. [Authentication](#authentication)4. [Analytics Microservices (Port 6001)](#analytics-microservices)

3. [Rasa Core API](#rasa-core-api)5. [Decider Service (Port 6009)](#decider-service)

4. [Action Server API](#action-server-api)6. [File Server (Port 8080)](#file-server)

5. [Analytics Microservices](#analytics-microservices)7. [NL2SPARQL Service (Port 6005)](#nl2sparql-service)

6. [Decider Service](#decider-service)8. [Ollama/Mistral (Port 11434)](#ollama-api)

7. [File Server](#file-server)9. [Fuseki SPARQL (Port 3030)](#fuseki-sparql)

8. [Fuseki SPARQL](#fuseki-sparql)10. [Error Handling](#error-handling)

9. [NL2SPARQL Service](#nl2sparql-service)11. [Rate Limiting](#rate-limiting)

10. [Ollama/Mistral](#ollama-api)12. [Webhooks](#webhooks)

11. [Error Handling](#error-handling)

12. [Rate Limiting](#rate-limiting)## Authentication


---### Current Status


## Service Overview**Internal Services**: No authentication required (development mode)


### Core Services (Always Running)**Production Recommendations**:

- Implement JWT tokens for frontend-to-backend

 | Service | Port | Protocol | Purpose | - Use API keys for service-to-service

 | --------- | ------ | ---------- | --------- | - Enable HTTPS/TLS for all endpoints

 | Rasa Core | 5005 | HTTP | Conversational AI orchestration | - Add rate limiting per client

 | Action Server | 5055 | HTTP | Custom actions & business logic | 

 | Analytics | 6001 | HTTP | Data analysis & visualization | ### Future Authentication

 | Decider | 6009 | HTTP | Query classification | 

 | File Server | 8080 | HTTP | Static file serving (artifacts) | ```http

 | Fuseki | 3030 | HTTP | SPARQL knowledge graph queries | POST /api/auth/login

Content-Type: application/json

### Optional Services

{

 | Service | Port | Protocol | Purpose | "username": "user@example.com",

 | --------- | ------ | ---------- | --------- | "password": "secure_password"

 | NL2SPARQL | 6005 | HTTP | Natural language to SPARQL translation | }

 | Ollama | 11434 | HTTP | LLM summarization (Mistral) | 

Response:

### Database Ports{

  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",

 | Database | Building | Port (Host) | Port (Container) | "token_type": "Bearer",

 | ---------- | ---------- | ------------- | ------------------ | "expires_in": 3600

 | MySQL | Building 1 | 3307 | 3306 | }

 | TimescaleDB | Building 2 | 5433 | 5432 | ```

 | Cassandra | Building 3 | 9042 | 9042 | 

 | PostgreSQL | Building 3 (metadata) | 5434 | 5432 | **Usage:**

```http

---Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

```

## Authentication

## Rasa Core API

### Current Status (Development Mode)

**Base URL**: `http://localhost:5005`

**All services**: No authentication required

### Version Info

**Internal Communication**: Services use Docker DNS names (e.g., `http://microservices:6000`)

```http

**External Access**: Services exposed on localhost ports (e.g., `http://localhost:6001`)GET /version

```

---

**Response:**

### Production Authentication (Recommended)

```json

{

**JWT Token-Based Authentication**:  "version": "3.6.12",

  "minimum_compatible_version": "3.0.0",

```http  "python": "3.10.12"

POST /api/auth/login}

Content-Type: application/json

```


{### Health Check

  "username": "user@example.com",

  "password": "secure_password"```http

}GET /

```


**Response:**

```json
{
  "access_token": "***",
  "status": "ok",
  "token_type": "Bearer",
  "message": "Rasa Core is running",
  "expires_in": 3600
}
```

### Webhook - Send Message

**Using Token**:

```http
```http

GET /analytics/runPOST /webhooks/rest/webhook

Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...Content-Type: application/json

```


**Implementation Example** (Flask middleware):**Request:**

```json

```python{

from functools import wraps  "sender": "user123",

import jwt  "message": "What is the temperature in zone 5.04?"

from flask import request, jsonify}

```

SECRET_KEY = "your-secret-key-here"

**Response:**

def token_required(f):```json

    @wraps(f)[

    def decorated(*args, **kwargs):  {

        token = request.headers.get('Authorization')    "recipient_id": "user123",

            "text": "The current temperature in zone 5.04 is 22.5°C (measured at 2025-01-08 14:30:00)."

        if not token:  }

            return jsonify({'error': 'Token missing'}), 401]

        ```

        try:

            token = token.replace('Bearer ', '')**Response with Custom Payload:**

            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

```json

        except:[

            return jsonify({'error': 'Invalid token'}), 401  {

            "recipient_id": "user123",

        return f(*args, **kwargs)    "text": "Here's the temperature trend:",

        "custom": {

    return decorated      "type": "chart",

      "data": {

@app.route('/analytics/run', methods=['POST'])        "sensor": "Air_Temperature_Sensor_5.04",

@token_required        "values": [22.1, 22.3, 22.5, 22.4, 22.6],

def run_analytics():        "timestamps": ["14:00", "14:15", "14:30", "14:45", "15:00"]

    # Protected endpoint      },

    pass      "chart_url": "http://localhost:6001/chart/temp_trend_123.png"

```    }

  }

---]

```

## Rasa Core API

### Tracker State

**Base URL**: `http://localhost:5005`

```http

**Internal URL**: `http://rasa-bldg1:5005` (or bldg2, bldg3)GET /conversations/{sender_id}/tracker

```

---

**Response:**

### GET /version

```json

{

Get Rasa server version and build information.  "sender_id": "user123",

  "slots": {

**Request**:    "sensor_name": "Air_Temperature_Sensor_5.04",

```http    "zone": "5.04",

GET http://localhost:5005/version    "time_range": "current"

```  },

  "latest_message": {

**Response**:    "intent": {

```json      "name": "query_temperature",

{      "confidence": 0.98

  "version": "3.6.12",    },

  "minimum_compatible_version": "3.0.0",    "entities": [

  "rasa_sdk_version": "3.6.1"      {

}        "entity": "zone",

```        "value": "5.04",

        "start": 32,

**Use Case**: Health check, verify service is running        "end": 36

      }

---    ]

  },

### POST /webhooks/rest/webhook  "events": [...]

}

Send a message to the Rasa chatbot and receive a response.```


**Request**:### Continue Conversation

```http

POST http://localhost:5005/webhooks/rest/webhook

```http

Content-Type: application/jsonPOST /conversations/{sender_id}/execute

Content-Type: application/json

{```

  "sender": "user123",

  "message": "show me temperature in zone 5.01 for the last 24 hours"**Request:**

}

```json

```{

  "action": "action_query_sensor"

**Response**:}

```json
```

[

  {**Response:**

    "recipient_id": "user123",```json

    "text": "Here is the temperature data for Air_Temperature_Sensor_5.01 over the last 24 hours:",{

    "custom": {  "tracker": {...},

      "chart_url": "http://localhost:8080/artifacts/user123/temperature_chart.png",  "messages": [...]

      "data": [}

        {"datetime": "2025-10-30T10:00:00", "value": 21.5},```

        {"datetime": "2025-10-30T11:00:00", "value": 21.8},

        ...### Model Info

      ],

      "statistics": {```http

        "mean": 21.6,GET /status

        "min": 20.8,```

        "max": 22.5,

        "std": 0.4**Response:**

      }

```json

    }{

  }  "model_file": "models/20250108-143000.tar.gz",

]  "model_id": "20250108-143000",

```  "training_data": "data/nlu.yml",

  "num_active_training_jobs": 0

**Common Message Patterns**:}

```

```json

// Simple sensor query### Parse Message (NLU only)

{"sender": "user1", "message": "show me co2 in zone 5.01"}

```http

// Time-range queryPOST /model/parse

{"sender": "user1", "message": "temperature last 7 days"}Content-Type: application/json

```

// Analytics request

{"sender": "user1", "message": "run trend analysis on temperature"}**Request:**

```json

// Multi-sensor comparison{

{"sender": "user1", "message": "compare temperatures in zones 5.01 and 5.10"}  "text": "What is the temperature in zone 5.04?"

}

// Forecast request

```

{"sender": "user1", "message": "forecast temperature for next 24 hours"}

```**Response:**

```json

---{

  "intent": {

### GET /conversations/{sender_id}/tracker    "name": "query_temperature",

    "confidence": 0.982

Get conversation state and slots for a specific user.  },

  "entities": [

**Request**:    {

```http      "entity": "zone",

GET http://localhost:5005/conversations/user123/tracker      "value": "5.04",

```      "confidence": 0.95,

      "start": 32,

**Response**:      "end": 36,

```json      "extractor": "DIETClassifier"

{    }

  "sender_id": "user123",  ],

  "slots": {  "intent_ranking": [

    "sensor_name": "Air_Temperature_Sensor_5.01",    {"name": "query_temperature", "confidence": 0.982},

    "sensor_type": "temperature",    {"name": "query_humidity", "confidence": 0.012},

    "start_date": "2025-10-30T00:00:00",    {"name": "query_co2", "confidence": 0.006}

    "end_date": "2025-10-31T00:00:00",  ],

    "analytics_type": "trend_analysis"  "text": "What is the temperature in zone 5.04?"

  },}

  "latest_message": {```

    "intent": "query_sensor_data",

    "entities": [## Action Server API

      {"entity": "sensor_type", "value": "temperature"},

      {"entity": "zone_id", "value": "5.01"}**Base URL**: `http://localhost:5055`

    ]

  },### Health Check

  "events": [...]

}

```http

```GET /health

```

**Use Case**: Debug conversation flow, inspect slot values

**Response:**

---```json

{

### POST /conversations/{sender_id}/execute  "status": "ok"

}

Trigger a specific action directly (debugging).```


**Request**:### Webhook - Execute Action

```http

POST http://localhost:5005/conversations/user123/execute

```http

Content-Type: application/jsonPOST /webhook

Content-Type: application/json

{```

  "name": "action_get_sensor_data"

}**Request:**

```json

{

**Response**:  "next_action": "action_query_sensor",

```json  "sender_id": "user123",

{  "tracker": {

  "events": [    "sender_id": "user123",

    {"event": "action", "name": "action_get_sensor_data"},    "slots": {

    {"event": "bot", "text": "Fetching sensor data..."}      "sensor_name": "Air_Temperature_Sensor_5.04"

  ]    },

}    "latest_message": {

```      "intent": {"name": "query_temperature"}

    }

---  },

  "domain": {...}

### POST /model/train}

```

Train a new Rasa model (asynchronous).

**Response:**

**Request**:```json

```http{

POST http://localhost:5005/model/train  "events": [

Content-Type: application/json    {

      "event": "slot",

{      "name": "sensor_value",

  "domain": "...",      "value": "22.5"

  "config": "...",    }

  "nlu": "...",  ],

  "stories": "..."  "responses": [

}    {

```      "text": "The current temperature is 22.5°C"

    }

**Response**:  ]

```json}

{```

  "info": "New model is being trained",

  "model_file": "models/20251031-143000.tar.gz"### Actions List

}

```http

GET /actions

**Use Case**: Dynamic model retraining

```


---**Response:**

```json

## Action Server API{

  "actions": [

**Base URL**: `http://localhost:5055`    "action_query_sensor",

    "action_analytics_request",

**Internal URL**: `http://rasa-action-server-bldg1:5055`    "action_list_sensors",

    "action_compare_sensors",

---    "action_fetch_historical_data"

  ]

### POST /webhook}

```

Rasa calls this endpoint to execute custom actions.

## Analytics Microservices

**Request** (from Rasa):

```json**Base URL**: `http://localhost:6001`

{

  "next_action": "action_get_sensor_data",### Health Check

  "sender_id": "user123",

  "tracker": {```http

    "sender_id": "user123",GET /health

    "slots": {```

      "sensor_name": "Air_Temperature_Sensor_5.01",

      "start_date": "2025-10-30T00:00:00",**Response:**

      "end_date": "2025-10-31T00:00:00"```json

    },{

    "latest_message": {...},  "status": "ok",

    "events": [...]  "service": "analytics-microservices",

  },  "version": "1.0.0",

  "domain": {...}  "timestamp": "2025-01-08T14:30:00Z"

}}

```


**Response** (to Rasa):### Statistical Analysis

```json

{```http

  "events": [POST /api/analytics/statistics

    {Content-Type: application/json

      "event": "slot",```

      "name": "sensor_data",

      "value": [...]**Request:**

    }

```json

  ],{

  "responses": [  "sensor": "Air_Temperature_Sensor_5.04",

    {  "start_time": "2025-01-08T00:00:00Z",

      "text": "Here is the temperature data for the last 24 hours:",  "end_time": "2025-01-08T23:59:59Z",

      "custom": {  "metrics": ["mean", "std", "min", "max", "median"]

        "chart_url": "http://localhost:8080/artifacts/user123/temp.png",}

        "data": [...]

```

      }

    }**Response:**

  ]

```json

}{

```  "sensor": "Air_Temperature_Sensor_5.04",

  "period": {

**Note**: This endpoint is called internally by Rasa, not directly by users.    "start": "2025-01-08T00:00:00Z",

    "end": "2025-01-08T23:59:59Z",

---    "duration_hours": 24

  },

### GET /health (Custom Endpoint)  "statistics": {

    "mean": 22.3,

Check action server health.    "std": 0.8,

    "min": 20.5,

**Request**:    "max": 24.1,

```http    "median": 22.4,

GET http://localhost:5055/health    "count": 288

```  }

}

**Response**:```

```json

{### Trend Analysis

  "status": "healthy",

  "database": "connected",```http

  "fuseki": "reachable",POST /api/analytics/trend

  "analytics": "reachable"Content-Type: application/json

}

```

```

**Request:**

---```json

{

## Analytics Microservices  "sensor": "CO2_Level_Sensor_5.01",

  "start_time": "2025-01-08T00:00:00Z",

**Base URL**: `http://localhost:6001`  "end_time": "2025-01-08T23:59:59Z",

  "method": "linear_regression"

**Internal URL**: `http://microservices:6000`}

```

---

**Response:**

### GET /health

```json

{

Check analytics service health.  "sensor": "CO2_Level_Sensor_5.01",

  "trend": {

**Request**:    "direction": "increasing",

```http    "slope": 2.3,

GET http://localhost:6001/health    "r_squared": 0.87,

```    "p_value": 0.001,

    "confidence": 0.95

**Response**:  },

```json  "interpretation": "Significant upward trend detected",

{  "recommendation": "Increase ventilation during peak hours"

  "status": "healthy",}

  "service": "analytics",```

  "version": "3.0.0"

}### Anomaly Detection

```

```http

---POST /api/analytics/anomalies

Content-Type: application/json

### GET /analytics/list

```


Get available analysis types.**Request:**

```json

**Request**:{

```http  "sensor": "Air_Temperature_Sensor_5.04",

GET http://localhost:6001/analytics/list  "start_time": "2025-01-08T00:00:00Z",

```  "end_time": "2025-01-08T23:59:59Z",

  "method": "isolation_forest",

**Response**:  "sensitivity": 0.1

```json}

{```

  "analyses": [

    "summary_statistics",**Response:**

    "histogram",```json

    "distribution_analysis",{

    "outlier_detection",  "sensor": "Air_Temperature_Sensor_5.04",

    "data_quality",  "anomalies": [

    "timeseries_analysis",    {

    "correlation_analysis",      "timestamp": "2025-01-08T03:15:00Z",

    "comparative_analysis",      "value": 18.2,

    "pattern_recognition",      "score": -0.65,

    "variance_analysis",      "severity": "high",

    "trend_analysis",      "expected_range": [21.5, 23.5]

    "forecast",    },

    "anomaly_prediction",    {

    "regression_analysis",      "timestamp": "2025-01-08T15:45:00Z",

    "classification",      "value": 26.3,

    "clustering",      "score": -0.58,

    "optimization",      "severity": "medium",

    "what_if_scenario",      "expected_range": [21.5, 23.5]

    "threshold_recommendations",    }

    "streaming_analytics",  ],

    "real_time_anomaly"  "total_anomalies": 2,

  ],  "anomaly_rate": 0.69

  "count": 21}

}

```

```

### Forecasting

---

```http

### POST /analytics/runPOST /api/analytics/forecast

Content-Type: application/json

Execute an analysis on sensor data.```


**Request**:**Request:**

```http
```json

POST http://localhost:6001/analytics/run{

Content-Type: application/json  "sensor": "Zone_Air_Humidity_Sensor_5.04",

  "historical_hours": 48,

{  "forecast_hours": 4,

  "analysis_type": "trend_analysis",  "model": "prophet"

  "timeseries_data": [}

    {```

      "sensor_name": "Air_Temperature_Sensor_5.01",

      "data": [**Response:**

        {"datetime": "2025-10-30T10:00:00", "reading_value": 21.5},```json

        {"datetime": "2025-10-30T11:00:00", "reading_value": 21.8},{

        {"datetime": "2025-10-30T12:00:00", "reading_value": 22.1}  "sensor": "Zone_Air_Humidity_Sensor_5.04",

      ]  "forecast": [

    }    {

  ],      "timestamp": "2025-01-08T15:00:00Z",

  "parameters": {      "predicted_value": 45.2,

    "method": "linear"      "confidence_lower": 42.1,

  }      "confidence_upper": 48.3,

}      "confidence_level": 0.95

```    },

    {

**Response**:      "timestamp": "2025-01-08T16:00:00Z",

```json      "predicted_value": 46.1,

{      "confidence_lower": 42.8,

  "success": true,      "confidence_upper": 49.4,

  "analysis_type": "trend_analysis",      "confidence_level": 0.95

  "timestamp": "2025-10-31T14:30:00Z",    }

  "results": {  ],

    "trend": "upward",  "model_metrics": {

    "rate": 0.3,    "mae": 1.2,

    "confidence": 0.95,    "rmse": 1.8,

    "equation": "y = 0.3x + 21.2",    "mape": 2.3

    "r_squared": 0.88  }

  },}

  "artifacts": [```

    "trend_chart.png"

  ],### Correlation Analysis

  "artifact_urls": [

    "http://localhost:8080/artifacts/user123/trend_chart.png"```http

  ]POST /api/analytics/correlation

}Content-Type: application/json

```


**See Also**: [Analytics API Reference](analytics_api.md) for all 30+ analysis types**Request:**

```json

---{

  "sensor1": "Air_Temperature_Sensor_5.04",

## Decider Service  "sensor2": "Zone_Air_Humidity_Sensor_5.04",

  "start_time": "2025-01-08T00:00:00Z",

**Base URL**: `http://localhost:6009`  "end_time": "2025-01-08T23:59:59Z",

  "method": "pearson"

**Internal URL**: `http://decider-service:6009`}

```

---

**Response:**

### GET /health

```json

{

Check decider service health.  "sensor1": "Air_Temperature_Sensor_5.04",

  "sensor2": "Zone_Air_Humidity_Sensor_5.04",

**Request**:  "correlation": {

```http    "coefficient": -0.68,

GET http://localhost:6009/health    "p_value": 0.0001,

```    "method": "pearson",

    "interpretation": "Strong negative correlation"

**Response**:  },

```json  "relationship": "As temperature increases, humidity decreases",

{  "strength": "strong"

  "status": "healthy",}

  "model": "loaded",```

  "classes": 21

}### Visualization

```

```http

---POST /api/analytics/visualize

Content-Type: application/json

### POST /decide

```


Classify a user query into an analytics type.**Request:**

```json

**Request**:{

```http  "sensor": "Air_Temperature_Sensor_5.04",

POST http://localhost:6009/decide  "start_time": "2025-01-08T00:00:00Z",

Content-Type: application/json  "end_time": "2025-01-08T23:59:59Z",

  "chart_type": "line",

{  "options": {

  "query": "show me the trend of temperature over the last week"    "title": "Temperature Trend - Zone 5.04",

}    "width": 800,

```    "height": 400,

    "format": "png"

**Response**:  }

```json}

{```

  "query": "show me the trend of temperature over the last week",

  "predicted_class": "trend_analysis",**Response:**

  "confidence": 0.92,```json

  "alternatives": [{

    {"class": "timeseries_analysis", "confidence": 0.06},  "chart_url": "http://localhost:6001/charts/temp_trend_20250108_143000.png",

    {"class": "forecast", "confidence": 0.02}  "chart_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA...",

  ]  "metadata": {

}    "width": 800,

```    "height": 400,

    "format": "png",

**Classification Types**:    "created_at": "2025-01-08T14:30:00Z"

```  }

- summary_statistics}

- trend_analysis

```

- anomaly_detection

- forecast### T5 Training - Get Sensors

- correlation_analysis

- comparative_analysis

```http

- clusteringGET /api/t5/sensors

- classification

```

- optimization

- what_if_scenario**Response:**

- threshold_recommendations

```json

- real_time_anomaly{

... (21 total)  "sensors": [

```    "Air_Quality_Level_Sensor_5.01",

    "Air_Quality_Sensor_5.01",

---    "Air_Temperature_Sensor_5.01",

    ...

## File Server  ],

  "count": 680,

**Base URL**: `http://localhost:8080`  "building": "bldg1"

}

**Internal URL**: `http://http_server:8080

````


---### T5 Training - Get Examples


### GET /artifacts/{user}/{filename}

```http

GET /api/t5/examples

Retrieve generated artifacts (charts, CSVs).```


**Request**:**Response:**

```http
```json

GET http://localhost:8080/artifacts/user123/temperature_chart.png{

```  "examples": [

    {

**Response**: Binary file (PNG image)      "id": 1,

      "question": "What is the temperature in zone 5.04?",

**Content-Type**: `image/png`      "sensors": ["Air_Temperature_Sensor_5.04"],

      "sparql": "PREFIX brick: ...",

---      "category": "Temperature Query",

      "notes": "Basic temperature retrieval",

### GET /artifacts/{user}/      "created_at": "2025-01-08T10:00:00Z"

    }

List all artifacts for a user.  ],

  "count": 45

**Request**:}

```http
```

GET http://localhost:8080/artifacts/user123/

```### T5 Training - Add Example


**Response**: HTML directory listing

```http

POST /api/t5/examples

```htmlContent-Type: application/json

<html>```

  <body>

    <ul>**Request:**

      <li><a href="temperature_chart.png">temperature_chart.png</a></li>```json

      <li><a href="trend_analysis.csv">trend_analysis.csv</a></li>{

      <li><a href="forecast_results.json">forecast_results.json</a></li>  "question": "What is the temperature in zone 5.04?",

    </ul>  "sensors": ["Air_Temperature_Sensor_5.04"],

  </body>  "sparql": "PREFIX brick: <https://brickschema.org/schema/Brick#>\nSELECT ?value WHERE { ... }",

</html>  "category": "Temperature Query",

```  "notes": "Basic temperature retrieval"

}

---```


### Artifact Structure**Response:**

```json

**Directory Layout**:{

```  "status": "success",

rasa-ui/shared_data/artifacts/  "example_id": 46,

├── user123/  "message": "Training example added successfully"

│   ├── temperature_chart.png}

│   ├── trend_analysis.csv

```

│   └── forecast_results.json

├── user456/### T5 Training - Update Example

│   ├── co2_analysis.png

│   └── correlation_matrix.png

```http

└── test_user/PUT /api/t5/examples/{example_id}

    └── demo_chart.pngContent-Type: application/json

```


**Cleanup Policy**: Artifacts older than 7 days are automatically deleted.**Request:**

```json

---{

  "question": "What is the current temperature in zone 5.04?",

## Fuseki SPARQL  "sensors": ["Air_Temperature_Sensor_5.04"],

  "sparql": "PREFIX brick: ...",

**Base URL**: `http://localhost:3030`  "category": "Temperature Query",

  "notes": "Updated with 'current' keyword"

**Internal URL**: `http://fuseki-db:3030`}

```

---

**Response:**

### GET /$/ping

```json

{

Health check endpoint.  "status": "success",

  "example_id": 46,

**Request**:  "message": "Training example updated successfully"

```http}

GET http://localhost:3030/$/ping

```

```

### T5 Training - Delete Example

**Response**: 200 OK (empty body)

```http

---DELETE /api/t5/examples/{example_id}

```

### GET /$/datasets

**Response:**

List available datasets.```json

{

**Request**:  "status": "success",

```http  "example_id": 46,

GET http://localhost:3030/$/datasets  "message": "Training example deleted successfully"

```}

```

**Response**:

```json### T5 Training - Train Model

{

  "datasets": [```http

    {POST /api/t5/train

      "ds.name": "/trial",Content-Type: application/json

      "ds.state": true,```

      "ds.services": [

        {"srv.type": "SPARQL", "srv.endpoint": "/trial/sparql"},**Request:**

        {"srv.type": "GSP", "srv.endpoint": "/trial/data"}

```json

      ]{

    }  "epochs": 3,

  ]  "batch_size": 4,

}  "learning_rate": 5e-5,

```  "output_dir": "checkpoint-3"

}

---```


### POST /trial/sparql**Response (SSE Stream):**

```

Execute a SPARQL query.data: {"type": "progress", "epoch": 1, "total_epochs": 3, "loss": 0.245, "percentage": 30}


**Request**:data: {"type": "progress", "epoch": 2, "total_epochs": 3, "loss": 0.189, "percentage": 60}

```http

POST http://localhost:3030/trial/sparqldata: {"type": "progress", "epoch": 3, "total_epochs": 3, "loss": 0.142, "percentage": 100}

Content-Type: application/sparql-query

data: {"type": "complete", "message": "Training complete", "output_dir": "checkpoint-3"}

PREFIX brick: <https://brickschema.org/schema/Brick#>```

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

### T5 Training - Get Training Status

SELECT ?sensor WHERE {

  ?sensor rdf:type brick:Temperature_Sensor .```http

}GET /api/t5/training/status

LIMIT 10

```

```

**Response:**

**Response**:```json

```json{

{  "status": "training",

  "head": {  "current_epoch": 2,

    "vars": ["sensor"]  "total_epochs": 3,

  },  "current_loss": 0.189,

  "results": {  "progress_percentage": 60,

    "bindings": [  "estimated_completion": "2025-01-08T14:45:00Z"

      {"sensor": {"type": "uri", "value": "http://example.org/building#Air_Temperature_Sensor_5.01"}},}

      {"sensor": {"type": "uri", "value": "http://example.org/building#Air_Temperature_Sensor_5.02"}},```

      ...

    ]### T5 Training - Deploy Model

  }

}

```http

```POST /api/t5/deploy

Content-Type: application/json

---```


### Common SPARQL Queries**Request:**

```json

**Find All Sensors by Type**:{

```sparql  "checkpoint": "checkpoint-3"

PREFIX brick: <https://brickschema.org/schema/Brick#>}

PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>```


SELECT ?sensor ?sensorType**Response:**

WHERE {```json

  ?sensor rdf:type ?sensorType .{

  FILTER(STRSTARTS(STR(?sensorType), "https://brickschema.org/schema/Brick#"))  "status": "success",

}  "message": "Model deployed successfully",

ORDER BY ?sensorType  "checkpoint": "checkpoint-3",

```  "deployed_at": "2025-01-08T14:50:00Z"

}

**Get Sensors in a Specific Zone**:```

```sparql

PREFIX brick: <https://brickschema.org/schema/Brick#>## Decider Service


SELECT ?sensor ?zone**Base URL**: `http://localhost:6009`

WHERE {

  ?sensor brick:isPointOf ?zone .### Health Check

  ?zone brick:hasName "Zone_5.01" .

}

```http

```GET /health

```

**Find Equipment and Its Sensors**:

```sparql**Response:**

PREFIX brick: <https://brickschema.org/schema/Brick#>```json

{

SELECT ?equipment ?sensor  "status": "ok",

WHERE {  "service": "decider-service"

  ?equipment rdf:type brick:HVAC_Equipment .}

  ?sensor brick:isPointOf ?equipment .```

}

```### Decide Analytics Method


---```http

POST /decide

## NL2SPARQL ServiceContent-Type: application/json

```

**Base URL**: `http://localhost:6005`

**Request:**

**Internal URL**: `http://nl2sparql:6005

````json

{

**Status**: Optional overlay (requires `docker-compose.extras.yml`)  "query": "Show me the temperature trend for zone 5.04",

  "intent": "analytics_request",

---  "entities": {

    "sensor": "Air_Temperature_Sensor_5.04",

### POST /nl2sparql    "analysis_type": "trend"

  }

Convert natural language to SPARQL query.}

```

**Request**:

```http**Response:**

POST http://localhost:6005/nl2sparql

```json

Content-Type: application/json{

  "decision": {

{    "method": "trend_analysis",

  "query": "show me all temperature sensors in zone 5.01"    "parameters": {

}      "sensor": "Air_Temperature_Sensor_5.04",

```      "start_time": "2025-01-07T14:30:00Z",

      "end_time": "2025-01-08T14:30:00Z",

**Response**:      "method": "linear_regression"

```json    },

{    "endpoint": "http://localhost:6001/api/analytics/trend",

  "natural_language": "show me all temperature sensors in zone 5.01",    "confidence": 0.92

  "sparql_query": "PREFIX brick: <https://brickschema.org/schema/Brick#>\nSELECT ?sensor WHERE {\n  ?sensor rdf:type brick:Temperature_Sensor .\n  ?sensor brick:isPointOf ?zone .\n  ?zone brick:hasName \"Zone_5.01\" .\n}",  },

  "confidence": 0.89  "alternatives": [

}    {

```      "method": "moving_average",

      "confidence": 0.78

**Use Case**: Generate SPARQL queries from user questions    }

  ]

---}

```

## Ollama API

## File Server

**Base URL**: `http://localhost:11434`

**Base URL**: `http://localhost:8080`

**Internal URL**: `http://ollama:11434`

### Health Check

**Status**: Optional overlay (requires `docker-compose.extras.yml`)

```http

**Model**: Mistral 7BGET /health

```

---

**Response:**

### POST /api/generate

```json

{

Generate text completion (summarization, explanation).  "status": "ok",

  "service": "file-server"

**Request**:}

```http
```

POST http://localhost:11434/api/generate

Content-Type: application/json### List Files


{```http

  "model": "mistral",GET /files

  "prompt": "Summarize this sensor data: Temperature ranged from 20.5°C to 23.1°C over 24 hours with an average of 21.8°C and standard deviation of 0.6°C. The trend shows a gradual increase of 0.1°C per hour.",```

  "stream": false

}**Response:**

```json

{

**Response**:  "files": [

```json    {

{      "name": "20250108-143000.tar.gz",

  "model": "mistral",      "type": "rasa_model",

  "created_at": "2025-10-31T14:30:00Z",      "size": 145678901,

  "response": "The temperature in this space remained relatively stable, fluctuating within a 2.6°C range. The average temperature of 21.8°C indicates comfortable conditions. The gradual upward trend suggests increasing thermal load, possibly due to occupancy or solar gain.",      "created_at": "2025-01-08T14:30:00Z",

  "done": true      "path": "/app/models/20250108-143000.tar.gz"

}    }

```  ],

  "count": 1

---}

```

### POST /api/chat

### Download File

Chat-based completion (multi-turn conversation).

```http

**Request**:GET /files/{filename}

```http
```

POST http://localhost:11434/api/chat

Content-Type: application/json**Response:** Binary file content


{### Upload File

  "model": "mistral",

  "messages": [```http

    {"role": "system", "content": "You are a building automation expert."},POST /upload

    {"role": "user", "content": "Why is the temperature increasing in zone 5.01?"}Content-Type: multipart/form-data

  ],```

  "stream": false

}**Request:**

```

------WebKitFormBoundary

**Response**:Content-Disposition: form-data; name="file"; filename="model.tar.gz"

```json
Content-Type: application/gzip

{

  "model": "mistral",<binary content>

  "created_at": "2025-10-31T14:30:00Z",------WebKitFormBoundary--

  "message": {```

    "role": "assistant",

    "content": "Temperature increases in a zone can be caused by several factors: 1) Increased occupancy generating body heat, 2) Solar gain through windows, 3) Equipment heat load (computers, lights), 4) HVAC system adjustments or setpoint changes, 5) Reduced ventilation or cooling capacity. Check occupancy sensors, equipment schedules, and HVAC system status to diagnose the root cause."**Response:**

  },```json

  "done": true{

}  "status": "success",

```  "filename": "model.tar.gz",

  "size": 145678901,

---  "path": "/app/models/model.tar.gz"

}

## Error Handling

```


### Standard Error Response Format### Delete File


All services return errors in this format:```http

DELETE /files/{filename}

```json
```

{

  "success": false,**Response:**

  "error": "Error message",```json

  "details": "Additional context about the error",{

  "timestamp": "2025-10-31T14:30:00Z",  "status": "success",

  "request_id": "abc123"  "message": "File deleted successfully",

}  "filename": "model.tar.gz"

```}

```

---

### Get Model Info

### HTTP Status Codes

```http

 | Code | Meaning | Common Causes | GET /models/{model_id}

 | ------ | --------- | --------------- | ```

 | 200 | Success | Request completed successfully | 

 | 400 | Bad Request | Invalid payload, missing required fields | **Response:**

 | 401 | Unauthorized | Missing or invalid authentication token | ```json

 | 404 | Not Found | Resource does not exist (sensor, analysis type) | {

 | 422 | Unprocessable Entity | Valid format but invalid data (e.g., insufficient data points) | "model_id": "20250108-143000",

 | 429 | Too Many Requests | Rate limit exceeded | "filename": "20250108-143000.tar.gz",

 | 500 | Internal Server Error | Service crashed, database unavailable | "size": 145678901,

 | 503 | Service Unavailable | Service temporarily down (maintenance) | "metadata": {

    "trained_at": "2025-01-08T14:30:00Z",

---    "training_data": "data/nlu.yml",

    "config": "config.yml",

### Error Examples    "version": "3.6.12"

  }

**400 Bad Request**:}

```json
```

{

  "success": false,## NL2SPARQL Service

  "error": "Missing required field: analysis_type",

  "details": "The 'analysis_type' field is required for /analytics/run endpoint",**Base URL**: `http://localhost:6005`

  "timestamp": "2025-10-31T14:30:00Z"

}### Health Check

```

```http

**404 Not Found**:GET /health

```json
```

{

  "success": false,**Response:**

  "error": "Sensor not found",```json

  "details": "No sensor found matching 'Invalid_Sensor_Name'. Did you mean 'Air_Temperature_Sensor_5.01'?",{

  "timestamp": "2025-10-31T14:30:00Z"  "status": "ok",

}  "service": "nl2sparql",

```  "model": "t5-base",

  "checkpoint": "checkpoint-3"

**422 Unprocessable Entity**:}

```json
```

{

  "success": false,### Translate Natural Language to SPARQL

  "error": "Insufficient data for analysis",

  "details": "Trend analysis requires at least 10 data points. Received: 3",```http

  "timestamp": "2025-10-31T14:30:00Z"POST /predict

}Content-Type: application/json

```


**500 Internal Server Error**:

```json
{
  "success": false,
  "question": "What is the temperature in zone 5.04?",
  "error": "Database connection failed",
  "details": "Could not connect to MySQL server at mysqlserver:3306. Check if database service is running.",
  "timestamp": "2025-10-31T14:30:00Z"
}
```

**Request:**

```json

{

---  "question": "What is the temperature in zone 5.04?",

  "sparql": "PREFIX brick: <https://brickschema.org/schema/Brick#>\nSELECT ?value ?timestamp WHERE {\n  <sensor:Air_Temperature_Sensor_5.04> brick:hasValue ?value .\n  <sensor:Air_Temperature_Sensor_5.04> brick:hasTimestamp ?timestamp .\n}",

## Rate Limiting  "confidence": 0.95,

  "model": "checkpoint-3"

### Current Status (Development)}

```

**No rate limiting** - Unlimited requests

### Batch Prediction

---

```http

### Production Rate Limiting (Recommended)POST /predict/batch

Content-Type: application/json

**Implement token bucket algorithm**:```


```python**Request:**

from flask_limiter import Limiter

```json

from flask_limiter.util import get_remote_address{

  "questions": [

limiter = Limiter(    "What is the temperature in zone 5.04?",

    app,    "Show me CO2 levels in zone 5.01",

    key_func=get_remote_address,    "What's the humidity in zone 5.15?"

    default_limits=["200 per day", "50 per hour"]  ]

)}

```

@app.route("/analytics/run")

@limiter.limit("10 per minute")**Response:**

def run_analytics():```json

    # Rate-limited endpoint{

    pass  "predictions": [

```    {

      "question": "What is the temperature in zone 5.04?",

**Rate Limit Headers**:      "sparql": "PREFIX brick: ...",

```http      "confidence": 0.95

HTTP/1.1 200 OK    },

X-RateLimit-Limit: 10    {

X-RateLimit-Remaining: 7      "question": "Show me CO2 levels in zone 5.01",

X-RateLimit-Reset: 1698765600      "sparql": "PREFIX brick: ...",

```      "confidence": 0.92

    },

**Rate Limit Exceeded Response**:    {

```http      "question": "What's the humidity in zone 5.15?",

HTTP/1.1 429 Too Many Requests      "sparql": "PREFIX brick: ...",

Retry-After: 30      "confidence": 0.97

    }

{  ],

  "error": "Rate limit exceeded",  "count": 3

  "details": "Maximum 10 requests per minute. Try again in 30 seconds.",}

  "retry_after": 30

```

}

```## Ollama API


---**Base URL**: `http://localhost:11434`


## Best Practices### List Models


### 1. Request Optimization

```http

GET /api/tags

**DO**:```

- ✅ Batch multiple sensors in single request

- ✅ Use appropriate time ranges (avoid years of data)**Response:**

- ✅ Specify required fields only

```json

- ✅ Cache responses when possible{

  "models": [

**DON'T**:    {

- ❌ Make separate requests for each sensor      "name": "mistral:latest",

- ❌ Request full-resolution data for long time ranges      "modified_at": "2025-01-08T10:00:00Z",

- ❌ Fetch all fields when only a few are needed      "size": 4109856401,

- ❌ Re-request unchanging data      "digest": "sha256:abc123...",

      "details": {

---        "format": "gguf",

        "family": "mistral",

### 2. Error Handling        "parameter_size": "7B"

      }

**DO**:    }

- ✅ Check HTTP status code before parsing response  ]

- ✅ Implement exponential backoff for retries}

- ✅ Log errors with request context

```

- ✅ Provide user-friendly error messages

### Generate Response

**DON'T**:

- ❌ Assume all requests succeed

```http

- ❌ Retry immediately on failurePOST /api/generate

- ❌ Ignore error detailsContent-Type: application/json

- ❌ Expose internal error messages to users

```


---**Request:**

```json

### 3. Performance{

  "model": "mistral:latest",

**DO**:  "prompt": "Explain the temperature reading of 22.5°C in a building context",

- ✅ Use connection pooling  "stream": false

- ✅ Implement request timeouts (30 seconds)}

- ✅ Compress large payloads (gzip)

```

- ✅ Monitor API latency

**Response:**

**DON'T**:```json

- ❌ Create new connection for each request{

- ❌ Wait indefinitely for responses  "model": "mistral:latest",

- ❌ Send uncompressed large datasets  "created_at": "2025-01-08T14:30:00Z",

- ❌ Ignore slow endpoints  "response": "A temperature of 22.5°C (72.5°F) is within the comfortable range for most indoor environments...",

  "done": true,

---  "context": [1234, 5678, ...],

  "total_duration": 1234567890,

## Code Examples  "load_duration": 123456789,

  "prompt_eval_count": 45,

### Python (requests)  "eval_count": 89

}

```python
```

import requests

from datetime import datetime, timedelta### Chat Completion


# Query sensor data via Rasa

```http

def query_sensor_rasa(sensor_name, hours=24):POST /api/chat

    url = "http://localhost:5005/webhooks/rest/webhook"Content-Type: application/json

    ```

    payload = {

        "sender": "python_client",**Request:**

        "message": f"show me {sensor_name} for the last {hours} hours"```json

    }{

      "model": "mistral:latest",

    response = requests.post(url, json=payload, timeout=30)  "messages": [

    response.raise_for_status()    {

          "role": "system",

    return response.json()      "content": "You are a building management assistant."

    },

# Run analytics directly    {

def run_analytics(analysis_type, sensor_data):      "role": "user",

    url = "http://localhost:6001/analytics/run"      "content": "Is 22.5°C a good temperature for an office?"

        }

    payload = {  ],

        "analysis_type": analysis_type,  "stream": false

        "timeseries_data": sensor_data}

    }

```

    

    response = requests.post(url, json=payload, timeout=60)**Response:**

    response.raise_for_status()

```json

    {

    return response.json()  "model": "mistral:latest",

  "created_at": "2025-01-08T14:30:00Z",

# Example usage  "message": {

result = query_sensor_rasa("temperature in zone 5.01", hours=24)    "role": "assistant",

print(result[0]["text"])    "content": "Yes, 22.5°C is an excellent temperature for an office environment..."

  },

# Direct analytics call  "done": true

sensor_data = [}

    {```

        "sensor_name": "Air_Temperature_Sensor_5.01",

        "data": [## Fuseki SPARQL

            {"datetime": "2025-10-30T10:00:00", "reading_value": 21.5},

            {"datetime": "2025-10-30T11:00:00", "reading_value": 21.8}**Base URL**: `http://localhost:3030`

        ]

    }### Query (GET)

]

```http

analytics_result = run_analytics("trend_analysis", sensor_data)GET /abacws/query?query={encoded_query}

print(f"Trend: {analytics_result['results']['trend']}")Accept: application/sparql-results+json

```


---**Example:**

```http

### JavaScript (axios)GET /abacws/query?query=PREFIX%20brick%3A%20%3Chttps%3A%2F%2Fbrickschema.org%2Fschema%2FBrick%23%3E%0ASELECT%20%3Fsensor%20WHERE%20%7B%0A%20%20%3Fsensor%20a%20brick%3ATemperature_Sensor%20.%0A%7D

```

```javascript

const axios = require('axios');### Query (POST)


// Query sensor data via Rasa

```http

async function querySensorRasa(sensorName, hours = 24) {POST /abacws/query

  const url = 'http://localhost:5005/webhooks/rest/webhook';Content-Type: application/sparql-query

  Accept: application/sparql-results+json

  const payload = {```

    sender: 'js_client',

    message: `show me ${sensorName} for the last ${hours} hours`**Request:**

  };```sparql

  PREFIX brick: <https://brickschema.org/schema/Brick#>

  const response = await axios.post(url, payload, { timeout: 30000 });SELECT ?sensor ?location WHERE {

  return response.data;  ?sensor a brick:Temperature_Sensor .

}  ?sensor brick:hasLocation ?location .

}

### Client example (JavaScript)

```javascript
async function runAnalytics(analysisType, timeseriesData) {
  const url = 'http://localhost:6001/analytics/run';
  const payload = {
    analysis_type: analysisType,
    timeseries_data: timeseriesData
  };
  const response = await axios.post(url, payload, { timeout: 60000 });
  return response.data;
}

(async () => {
  const analyticsResult = await runAnalytics('trend_analysis', [
    {
      sensor_name: 'Air_Temperature_Sensor_5.01',
      data: [
        { datetime: '2025-10-30T10:00:00Z', reading_value: 21.5 },
        { datetime: '2025-10-30T11:00:00Z', reading_value: 21.8 }
      ]
    }
  ]);
  console.log(`Trend: ${analyticsResult.results?.trend}`);
})();
```

### Update

```http
POST /abacws/update
Content-Type: application/sparql-update
```

**Request:**

```sparql
PREFIX brick: <https://brickschema.org/schema/Brick#>
INSERT DATA {
  <sensor:New_Sensor_5.35> a brick:Temperature_Sensor .
  <sensor:New_Sensor_5.35> brick:hasLocation <zone:5.35> .
}
```

Response: 204 No Content (success)

### cURL (bash)

```bash
# Query sensor data via Rasa
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "sender": "curl_client",
    "message": "show me temperature in zone 5.01 for the last 24 hours"
  }'
```

## Error Handling


### Standard Error Response

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Invalid sensor name provided",
    "details": {
      "field": "sensor",
      "received": "Invalid_Sensor",
      "expected": "Valid sensor from sensor_list.txt"
    }
  },
  "timestamp": "2025-01-08T14:30:00Z",
  "request_id": "req_abc123"
}
```

}

# SPARQL query to Fuseki

```

curl -X POST http://localhost:3030/trial/sparql \

  -H "Content-Type: application/sparql-query" \### Error Codes

  --data 'PREFIX brick: <https://brickschema.org/schema/Brick#>

SELECT ?sensor WHERE {| Code | HTTP Status | Description |

  ?sensor rdf:type brick:Temperature_Sensor .|------|-------------|-------------|

} LIMIT 10'| `INVALID_REQUEST` | 400 | Malformed request or invalid parameters |

```| `UNAUTHORIZED` | 401 | Authentication required |

 | `FORBIDDEN` | 403 | Insufficient permissions | 

---| `NOT_FOUND` | 404 | Resource not found |

 | `METHOD_NOT_ALLOWED` | 405 | HTTP method not supported | 

## Related Documentation| `CONFLICT` | 409 | Resource conflict (e.g., duplicate) |

 | `UNPROCESSABLE_ENTITY` | 422 | Valid syntax but semantic error | 

- **[Analytics API Reference](analytics_api.md)**: Detailed analytics endpoint documentation| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |

- **[Backend Services](backend_services.md)**: Service architecture overview| `INTERNAL_ERROR` | 500 | Server-side error |

- **[Data Payloads](data_payloads.md)**: Payload format specifications| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

- **[Frontend UI](frontend_ui.md)**: React app integration| `GATEWAY_TIMEOUT` | 504 | Upstream service timeout |


---### Example Errors


**Complete API Reference** - Comprehensive REST API documentation for all OntoBot services. 🔌📡✨**Invalid Sensor:**

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Sensor 'Invalid_Sensor' not found",
    "details": {
      "sensor": "Invalid_Sensor",
      "available_count": 680
    }
  }
}
```

**Missing Parameter:**
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required parameter: sensor",
    "details": {
      "missing_fields": ["sensor"]
    }
  }
}
```

**Service Unavailable:**
```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "Analytics service is temporarily unavailable",
    "details": {
      "service": "analytics-microservices",
      "retry_after": 30
    }
  }
}
```

## Rate Limiting

### Future Implementation

**Headers:**
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704723600
```

**Limits (Planned):**
- Anonymous: 60 requests/minute
- Authenticated: 1000 requests/minute
- Admin: Unlimited

**Rate Limit Response:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Try again in 45 seconds.",
    "details": {
      "limit": 60,
      "remaining": 0,
      "reset_at": "2025-01-08T14:31:00Z"
    }
  }
}
```

## Webhooks

### Rasa Webhook Events

Subscribe to conversation events:

```http
POST /webhooks/callback
Content-Type: application/json
```

**Event: Message Received**
```json
{
  "event": "user_message",
  "sender_id": "user123",
  "message": "What is the temperature?",
  "timestamp": "2025-01-08T14:30:00Z"
}
```

**Event: Bot Response**
```json
{
  "event": "bot_response",
  "sender_id": "user123",
  "response": "The current temperature is 22.5°C",
  "timestamp": "2025-01-08T14:30:05Z"
}
```

**Event: Action Executed**
```json
{
  "event": "action_executed",
  "action_name": "action_query_sensor",
  "sender_id": "user123",
  "success": true,
  "duration_ms": 234,
  "timestamp": "2025-01-08T14:30:03Z"
}
```

## SDK Examples

### Python SDK

```python
import requests

class OntoBot:
    def __init__(self, base_url="http://localhost:5005"):
        self.base_url = base_url
        self.session = requests.Session()
    
    def send_message(self, user_id, message):
        """Send a message to the chatbot"""
        response = self.session.post(
            f"{self.base_url}/webhooks/rest/webhook",
            json={"sender": user_id, "message": message}
        )
        return response.json()
    
    def get_analytics(self, sensor, analysis_type="statistics"):
        """Get analytics for a sensor"""
        response = self.session.post(
            "http://localhost:6001/api/analytics/statistics",
            json={"sensor": sensor}
        )
        return response.json()
    
    def translate_query(self, question):
        """Translate natural language to SPARQL"""
        response = self.session.post(
            "http://localhost:6005/predict",
            json={"question": question}
        )
        return response.json()

# Usage
bot = OntoBot()
response = bot.send_message("user123", "What is the temperature?")
print(response)
```

### JavaScript/Node.js SDK

```javascript
class OntoBot {
  constructor(baseUrl = 'http://localhost:5005') {
    this.baseUrl = baseUrl;
  }
  
  async sendMessage(userId, message) {
    const response = await fetch(`${this.baseUrl}/webhooks/rest/webhook`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sender: userId, message})
    });
    return response.json();
  }
  
  async getAnalytics(sensor, analysisType = 'statistics') {
    const response = await fetch('http://localhost:6001/api/analytics/statistics', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({sensor})
    });
    return response.json();
  }
  
  async translateQuery(question) {
    const response = await fetch('http://localhost:6005/predict', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question})
    });
    return response.json();
  }
}

// Usage
const bot = new OntoBot();
const response = await bot.sendMessage('user123', 'What is the temperature?');
console.log(response);
```

### cURL Examples

**Send Message:**
```bash
curl -X POST http://localhost:5005/webhooks/rest/webhook \
  -H "Content-Type: application/json" \
  -d '{"sender":"user123","message":"What is the temperature?"}'
```

**Get Analytics:**
```bash
curl -X POST http://localhost:6001/api/analytics/statistics \
  -H "Content-Type: application/json" \
  -d '{"sensor":"Air_Temperature_Sensor_5.04","metrics":["mean","std"]}'
```

**Translate Query:**
```bash
curl -X POST http://localhost:6005/predict \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the temperature in zone 5.04?"}'
```

**SPARQL Query:**
```bash
curl -X POST http://localhost:3030/abacws/query \
  -H "Content-Type: application/sparql-query" \
  -H "Accept: application/sparql-results+json" \
  -d 'PREFIX brick: <https://brickschema.org/schema/Brick#>
SELECT ?sensor WHERE { ?sensor a brick:Temperature_Sensor . }'
```

## Postman Collection

Download the complete API collection:
- [OntoBot.postman_collection.json](../postman/OntoBot.postman_collection.json)

Import into Postman for easy testing and exploration.

## Next Steps

- [Frontend UI Guide](./frontend_ui.md)
- [Backend Services Documentation](./backend_services.md)
- [T5 Training Guide](./t5_training_guide.md)
- [Multi-Building Guide](./multi_building.md)
- [Quick Start Guide](./quickstart.md)
