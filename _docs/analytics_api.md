---
title: Analytics API Reference
layout: post
category: docs
permalink: /docs/analytics_api/
date: 2025-09-28
---


# Analytics API Reference# Analytics API Reference


Complete reference for OntoBot's analytics microservice - 30+ analysis types covering descriptive, diagnostic, predictive, and prescriptive analytics.Base: `http://localhost:6001`


---## POST /analytics/run


## Service OverviewBody fields:


**Base URL**: `http://localhost:6001` (host) or `http://microservices:6000` (internal)- `analysis_type` (string, required)

- Sensor data: flat or nested payload (see Data & Payloads)

**Technology**: Flask 3.0, Python 3.10, scikit-learn, pandas, matplotlib- Optional parameters vary per function, e.g.:

  - `acceptable_range`: `[min, max]` for temperature/humidity

**Capabilities**:  - `thresholds`: object with pollutant limits or AQI weights

- 30+ pre-built analysis types  - `method`: `zscore` or `iqr` for anomalies

- Automatic chart generation (PNG/base64)  - `window`: integer for rolling computations

- CSV/JSON export

- Real-time and batch processingResponse:

- Artifact storage to shared volumes

```json

---{

  "analysis_type": "analyze_temperatures",

## Quick Start  "timestamp": "2025-02-10T06:00:00Z",

  "results": { "..." }

### Health Check}

```

```bash

GET http://localhost:6001/healthNotes:

```

- Results include `unit` and UK defaults metadata wherever applicable (e.g., `acceptable_range`, `acceptable_max`).

**Response**:- Keys are derived from sensor names; robust matching avoids false positives (e.g., excludes "attempt" for temperature).

```json

{## Analysis catalog (highlights)

  "status": "healthy",

  "service": "analytics",- Environmental:

  "version": "3.0.0"  - `analyze_temperatures`, `analyze_humidity`, `analyze_co2_levels`, `analyze_pm_levels`, `analyze_formaldehyde_levels`, `analyze_noise_levels`, `analyze_air_quality`, `compute_air_quality_index`

}- HVAC/air:

```  - `analyze_supply_return_temp_difference`, `analyze_air_flow_variation`, `analyze_pressure_trend`, `analyze_air_quality_trends`, `analyze_hvac_anomalies`

- Generic:

### List Available Analyses  - `aggregate_sensor_data`, `correlate_sensors`, `analyze_sensor_trend`, `detect_anomalies`, `detect_potential_failures`, `forecast_downtimes`

- Ops:

```bash  - `analyze_device_deviation`, `analyze_failure_trends`, `analyze_recalibration_frequency`

GET http://localhost:6001/analytics/list

```For per-function inputs/outputs see `microservices/README.md` or the source `microservices/blueprints/analytics_service.py`.


**Response**:
```json
{
  "analyses": [
    "summary_statistics",
    "timeseries_analysis",
    "trend_analysis",
    "anomaly_detection",
    "forecast",
    ...
  ],
  "count": 30
}
```

---

## Core Endpoint

### POST /analytics/run

Execute an analysis on time-series sensor data.

**Request Format**:
```json
{
  "analysis_type": "trend_analysis",
  "timeseries_data": [
    {
      "sensor_name": "Air_Temperature_Sensor_5.01",
      "data": [
        {"datetime": "2025-10-31T10:00:00", "reading_value": 21.5},
        {"datetime": "2025-10-31T10:01:00", "reading_value": 21.6},
        {"datetime": "2025-10-31T10:02:00", "reading_value": 21.7}
      ]
    }
  ],
  "parameters": {
    "window_size": 10,
    "threshold": 2.0
  }
}
```

**Response Format**:
```json
{
  "success": true,
  "analysis_type": "trend_analysis",
  "timestamp": "2025-10-31T14:30:00Z",
  "results": {
    "trend": "upward",
    "rate": 0.1,
    "confidence": 0.95,
    "statistics": {
      "mean": 21.6,
      "std": 0.1,
      "min": 21.5,
      "max": 21.7
    }
  },
  "artifacts": [
    "trend_chart.png",
    "data_export.csv"
  ],
  "artifact_urls": [
    "http://localhost:8080/artifacts/user123/trend_chart.png"
  ]
}
```

---

## Analysis Categories

### 1. Descriptive Analytics

#### summary_statistics

**Purpose**: Compute basic statistical measures

**Request**:
```json
{
  "analysis_type": "summary_statistics",
  "timeseries_data": [{
    "sensor_name": "Air_Temperature_Sensor_5.01",
    "data": [
      {"datetime": "2025-10-31T10:00:00", "reading_value": 21.5},
      {"datetime": "2025-10-31T11:00:00", "reading_value": 22.0},
      {"datetime": "2025-10-31T12:00:00", "reading_value": 22.5}
    ]
  }]
}
```

**Response**:
```json
{
  "results": {
    "count": 3,
    "mean": 22.0,
    "median": 22.0,
    "mode": null,
    "std": 0.5,
    "variance": 0.25,
    "min": 21.5,
    "max": 22.5,
    "range": 1.0,
    "quartiles": {
      "q1": 21.75,
      "q2": 22.0,
      "q3": 22.25
    },
    "iqr": 0.5
  }
}
```

---

#### histogram

**Purpose**: Generate frequency distribution

**Request**:
```json
{
  "analysis_type": "histogram",
  "timeseries_data": [...],
  "parameters": {
    "bins": 10
  }
}
```

**Response**:
```json
{
  "results": {
    "bins": [21.0, 21.5, 22.0, 22.5, 23.0],
    "frequencies": [5, 12, 18, 10, 5],
    "density": [0.1, 0.24, 0.36, 0.2, 0.1]
  },
  "artifacts": ["histogram.png"]
}
```

**Generated Chart**:
- Bar chart showing frequency distribution
- X-axis: Value bins
- Y-axis: Frequency or density

---

#### distribution_analysis

**Purpose**: Analyze data distribution characteristics

**Request**:
```json
{
  "analysis_type": "distribution_analysis",
  "timeseries_data": [...]
}
```

**Response**:
```json
{
  "results": {
    "distribution_type": "normal",
    "skewness": 0.15,
    "kurtosis": -0.5,
    "normality_test": {
      "statistic": 0.98,
      "p_value": 0.23,
      "is_normal": true
    }
  }
}
```

---

#### outlier_detection

**Purpose**: Identify statistical outliers

**Request**:
```json
{
  "analysis_type": "outlier_detection",
  "timeseries_data": [...],
  "parameters": {
    "method": "iqr",  // or "zscore"
    "threshold": 1.5
  }
}
```

**Response**:
```json
{
  "results": {
    "outlier_count": 3,
    "outlier_percentage": 2.1,
    "outliers": [
      {"datetime": "2025-10-31T02:30:00", "value": 28.5, "zscore": 3.2},
      {"datetime": "2025-10-31T14:15:00", "value": 29.0, "zscore": 3.5},
      {"datetime": "2025-10-31T19:00:00", "value": 15.0, "zscore": -3.1}
    ],
    "method": "iqr",
    "threshold": 1.5
  },
  "artifacts": ["outliers_chart.png"]
}
```

**Chart**: Scatter plot with outliers highlighted in red

---

#### data_quality

**Purpose**: Assess data completeness and quality

**Request**:
```json
{
  "analysis_type": "data_quality",
  "timeseries_data": [...]
}
```

**Response**:
```json
{
  "results": {
    "total_records": 1440,
    "valid_records": 1432,
    "missing_records": 8,
    "duplicate_records": 0,
    "completeness": 99.4,
    "quality_score": 98.5,
    "issues": [
      {"timestamp": "2025-10-31T03:15:00", "issue": "missing_value"},
      {"timestamp": "2025-10-31T14:30:00", "issue": "suspected_outlier"}
    ]
  }
}
```

---

#### timeseries_analysis

**Purpose**: Comprehensive time-series metrics

**Request**:
```json
{
  "analysis_type": "timeseries_analysis",
  "timeseries_data": [...],
  "parameters": {
    "window_size": 10
  }
}
```

**Response**:
```json
{
  "results": {
    "statistics": {
      "mean": 22.0,
      "std": 0.8,
      "min": 20.1,
      "max": 23.5
    },
    "trend": {
      "direction": "increasing",
      "rate": 0.15,
      "significance": 0.95
    },
    "seasonality": {
      "detected": true,
      "period": 24,
      "strength": 0.7
    },
    "stationarity": {
      "is_stationary": false,
      "adf_statistic": -2.1,
      "p_value": 0.08
    }
  },
  "artifacts": ["timeseries_chart.png"]
}
```

---

### 2. Diagnostic Analytics

#### correlation_analysis

**Purpose**: Find relationships between multiple sensors

**Request**:
```json
{
  "analysis_type": "correlation_analysis",
  "timeseries_data": [
    {
      "sensor_name": "Air_Temperature_Sensor_5.01",
      "data": [...]
    },
    {
      "sensor_name": "Humidity_Sensor_5.01",
      "data": [...]
    }
  ],
  "parameters": {
    "method": "pearson"  // or "spearman", "kendall"
  }
}
```

**Response**:
```json
{
  "results": {
    "correlation_matrix": {
      "Air_Temperature_Sensor_5.01": {
        "Air_Temperature_Sensor_5.01": 1.0,
        "Humidity_Sensor_5.01": -0.72
      },
      "Humidity_Sensor_5.01": {
        "Air_Temperature_Sensor_5.01": -0.72,
        "Humidity_Sensor_5.01": 1.0
      }
    },
    "strong_correlations": [
      {
        "sensor_1": "Air_Temperature_Sensor_5.01",
        "sensor_2": "Humidity_Sensor_5.01",
        "coefficient": -0.72,
        "p_value": 0.001,
        "significance": "strong_negative"
      }
    ]
  },
  "artifacts": ["correlation_heatmap.png"]
}
```

**Chart**: Heatmap showing correlation coefficients

---

#### comparative_analysis

**Purpose**: Compare multiple sensors or time periods

**Request**:
```json
{
  "analysis_type": "comparative_analysis",
  "timeseries_data": [
    {"sensor_name": "Air_Temperature_Sensor_5.01", "data": [...]},
    {"sensor_name": "Air_Temperature_Sensor_5.10", "data": [...]}
  ]
}
```

**Response**:
```json
{
  "results": {
    "comparison": [
      {
        "sensor": "Air_Temperature_Sensor_5.01",
        "mean": 21.5,
        "std": 0.8
      },
      {
        "sensor": "Air_Temperature_Sensor_5.10",
        "mean": 22.8,
        "std": 1.2
      }
    ],
    "statistical_test": {
      "test": "t-test",
      "statistic": -8.5,
      "p_value": 0.0001,
      "significant": true,
      "interpretation": "Sensors show significantly different temperatures"
    },
    "recommendation": "Investigate HVAC zoning imbalance"
  },
  "artifacts": ["comparison_chart.png"]
}
```

---

#### pattern_recognition

**Purpose**: Identify recurring patterns

**Request**:
```json
{
  "analysis_type": "pattern_recognition",
  "timeseries_data": [...],
  "parameters": {
    "pattern_length": 24,  // hours
    "similarity_threshold": 0.8
  }
}
```

**Response**:
```json
{
  "results": {
    "patterns_found": 3,
    "patterns": [
      {
        "pattern_id": 1,
        "occurrences": 5,
        "description": "Temperature increase between 08:00-10:00",
        "average_magnitude": 2.5,
        "confidence": 0.92
      }
    ],
    "recommendations": [
      "Adjust HVAC pre-cooling schedule to 07:30"
    ]
  }
}
```

---

#### variance_analysis

**Purpose**: Analyze variability over time

**Request**:
```json
{
  "analysis_type": "variance_analysis",
  "timeseries_data": [...],
  "parameters": {
    "grouping": "hourly"  // or "daily", "weekly"
  }
}
```

**Response**:
```json
{
  "results": {
    "overall_variance": 0.64,
    "by_period": {
      "morning": {"mean": 20.5, "variance": 0.3},
      "afternoon": {"mean": 22.5, "variance": 1.2},
      "evening": {"mean": 21.0, "variance": 0.5}
    },
    "highest_variance_period": "afternoon",
    "interpretation": "Temperature most unstable during afternoon"
  }
}
```

---

### 3. Predictive Analytics

#### trend_analysis

**Purpose**: Identify and quantify trends

**Request**:
```json
{
  "analysis_type": "trend_analysis",
  "timeseries_data": [...],
  "parameters": {
    "method": "linear"  // or "polynomial", "exponential"
  }
}
```

**Response**:
```json
{
  "results": {
    "trend": "upward",
    "rate": 0.15,
    "confidence": 0.95,
    "equation": "y = 0.15x + 21.5",
    "r_squared": 0.87,
    "interpretation": "Temperature increasing at 0.15°C per hour",
    "projection_24h": 25.1
  },
  "artifacts": ["trend_chart.png"]
}
```

**Chart**: Line chart with trend line overlay

---

#### forecast

**Purpose**: Predict future values

**Request**:
```json
{
  "analysis_type": "forecast",
  "timeseries_data": [...],
  "parameters": {
    "horizon": 24,  // hours to forecast
    "model": "arima",  // or "prophet", "exponential_smoothing"
    "confidence_level": 0.95
  }
}
```

**Response**:
```json
{
  "results": {
    "forecasts": [
      {"datetime": "2025-11-01T00:00:00", "value": 21.8, "lower": 20.9, "upper": 22.7},
      {"datetime": "2025-11-01T01:00:00", "value": 21.6, "lower": 20.6, "upper": 22.6},
      ...
    ],
    "model": "ARIMA(2,1,2)",
    "accuracy_metrics": {
      "mape": 2.3,
      "rmse": 0.5
    }
  },
  "artifacts": ["forecast_chart.png"]
}
```

**Chart**: Line chart with historical data + forecast + confidence intervals

---

#### anomaly_prediction

**Purpose**: Predict likelihood of future anomalies

**Request**:
```json
{
  "analysis_type": "anomaly_prediction",
  "timeseries_data": [...],
  "parameters": {
    "lookback": 168,  // hours
    "horizon": 24
  }
}
```

**Response**:
```json
{
  "results": {
    "anomaly_risk": "medium",
    "risk_score": 0.65,
    "high_risk_periods": [
      {"datetime": "2025-11-01T14:00:00", "risk": 0.85, "reason": "Historical pattern"}
    ],
    "recommendations": [
      "Monitor temperature closely between 14:00-16:00",
      "Ensure HVAC system operational before peak period"
    ]
  }
}
```

---

#### regression_analysis

**Purpose**: Model relationships between variables

**Request**:
```json
{
  "analysis_type": "regression_analysis",
  "timeseries_data": [
    {"sensor_name": "Occupancy_Sensor_5.01", "data": [...]},  // Independent
    {"sensor_name": "CO2_Level_Sensor_5.01", "data": [...]}   // Dependent
  ],
  "parameters": {
    "model_type": "linear"  // or "polynomial", "ridge", "lasso"
  }
}
```

**Response**:
```json
{
  "results": {
    "equation": "CO2 = 400 + 15.5 * Occupancy",
    "coefficients": {
      "intercept": 400,
      "Occupancy_Sensor_5.01": 15.5
    },
    "r_squared": 0.89,
    "p_values": {
      "intercept": 0.001,
      "Occupancy_Sensor_5.01": 0.0001
    },
    "interpretation": "Each additional occupant increases CO2 by ~15.5 ppm"
  },
  "artifacts": ["regression_chart.png"]
}
```

---

#### classification

**Purpose**: Categorize sensor states or conditions

**Request**:
```json
{
  "analysis_type": "classification",
  "timeseries_data": [...],
  "parameters": {
    "classes": ["normal", "warning", "critical"],
    "features": ["temperature", "humidity", "co2"]
  }
}
```

**Response**:
```json
{
  "results": {
    "current_state": "warning",
    "confidence": 0.87,
    "class_distribution": {
      "normal": 0.10,
      "warning": 0.87,
      "critical": 0.03
    },
    "contributing_factors": [
      {"feature": "co2", "importance": 0.65},
      {"feature": "temperature", "importance": 0.25},
      {"feature": "humidity", "importance": 0.10}
    ],
    "recommendation": "Increase ventilation rate"
  }
}
```

---

#### clustering

**Purpose**: Group similar sensors or time periods

**Request**:
```json
{
  "analysis_type": "clustering",
  "timeseries_data": [...],  // Multiple sensors
  "parameters": {
    "n_clusters": 3,
    "method": "kmeans"  // or "hierarchical", "dbscan"
  }
}
```

**Response**:
```json
{
  "results": {
    "clusters": [
      {
        "cluster_id": 0,
        "sensors": ["Air_Temperature_Sensor_5.01", "Air_Temperature_Sensor_5.02"],
        "characteristics": "Stable, low variance",
        "count": 12
      },
      {
        "cluster_id": 1,
        "sensors": ["Air_Temperature_Sensor_5.15", "Air_Temperature_Sensor_5.16"],
        "characteristics": "High temperature, high variance",
        "count": 8
      }
    ],
    "silhouette_score": 0.72
  },
  "artifacts": ["cluster_chart.png"]
}
```

---

### 4. Prescriptive Analytics

#### optimization

**Purpose**: Find optimal setpoints or schedules

**Request**:
```json
{
  "analysis_type": "optimization",
  "timeseries_data": [...],
  "parameters": {
    "objective": "minimize_energy",
    "constraints": {
      "comfort_min": 20,
      "comfort_max": 24
    }
  }
}
```

**Response**:
```json
{
  "results": {
    "optimal_setpoint": 21.5,
    "current_setpoint": 22.0,
    "potential_savings": {
      "energy": "15%",
      "cost": "$250/month"
    },
    "comfort_impact": "negligible",
    "recommendation": "Reduce setpoint by 0.5°C during unoccupied hours"
  }
}
```

---

#### what_if_scenario

**Purpose**: Simulate impacts of changes

**Request**:
```json
{
  "analysis_type": "what_if_scenario",
  "timeseries_data": [...],
  "parameters": {
    "scenario": "reduce_setpoint",
    "change": -1.0  // Reduce by 1°C
  }
}
```

**Response**:
```json
{
  "results": {
    "scenario": "reduce_setpoint_by_1C",
    "predicted_impact": {
      "energy_savings": "20%",
      "occupant_comfort": -5,  // Slight decrease
      "equipment_runtime": -15
    },
    "risks": [
      "Some occupants may feel cold during morning hours"
    ],
    "recommendations": [
      "Implement gradual reduction over 2 weeks",
      "Monitor comfort complaints"
    ]
  }
}
```

---

#### threshold_recommendations

**Purpose**: Suggest optimal alert thresholds

**Request**:
```json
{
  "analysis_type": "threshold_recommendations",
  "timeseries_data": [...],
  "parameters": {
    "false_positive_rate": 0.05
  }
}
```

**Response**:
```json
{
  "results": {
    "recommended_thresholds": {
      "upper_warning": 23.5,
      "upper_critical": 25.0,
      "lower_warning": 19.5,
      "lower_critical": 18.0
    },
    "current_thresholds": {
      "upper_warning": 24.0,
      "upper_critical": 26.0
    },
    "justification": "Based on historical 95th percentile",
    "expected_alerts_per_week": 2.5
  }
}
```

---

### 5. Real-Time Analytics

#### streaming_analytics

**Purpose**: Process live sensor streams

**Request**:
```json
{
  "analysis_type": "streaming_analytics",
  "timeseries_data": [...],  // Recent window
  "parameters": {
    "window_size": 60,  // minutes
    "update_interval": 5
  }
}
```

**Response**:
```json
{
  "results": {
    "current_value": 22.3,
    "rolling_average": 22.1,
    "rate_of_change": 0.05,
    "trend": "stable",
    "alerts": []
  }
}
```

---

#### real_time_anomaly

**Purpose**: Detect anomalies in live data

**Request**:
```json
{
  "analysis_type": "real_time_anomaly",
  "timeseries_data": [...],
  "parameters": {
    "sensitivity": "medium"  // or "low", "high"
  }
}
```

**Response**:
```json
{
  "results": {
    "is_anomaly": true,
    "anomaly_score": 0.87,
    "severity": "warning",
    "message": "Temperature 2.5°C above expected range",
    "action": "Alert facilities management"
  }
}
```

---

## Error Handling

### Error Response Format

```json
{
  "success": false,
  "error": "Invalid analysis type",
  "details": "Analysis type 'invalid_analysis' not found. Available types: ...",
  "timestamp": "2025-10-31T14:30:00Z"
}
```

### Common Error Codes

 | HTTP Code | Error | Solution | 
 | ----------- | ------- | ---------- | 
 | 400 | Invalid request | Check payload format | 
 | 404 | Analysis not found | Use valid analysis_type | 
 | 422 | Insufficient data | Provide more data points | 
 | 500 | Internal error | Check service logs | 

---

## Best Practices

### 1. Data Preparation

**DO**:
- ✅ Sort data chronologically
- ✅ Use consistent datetime format (ISO 8601)
- ✅ Remove duplicates before sending
- ✅ Provide enough data points (minimum 10, recommended 100+)

**DON'T**:
- ❌ Send unsorted data
- ❌ Include null/missing values without handling
- ❌ Mix time zones
- ❌ Send duplicate timestamps

### 2. Performance Optimization

**For Fast Analysis**:
- Limit data to last 24-48 hours
- Use aggregated data (hourly vs minute-level)
- Request only needed analyses

**For Accuracy**:
- Provide at least 7 days of data
- Include full context (all related sensors)
- Use minute-level granularity

### 3. Artifact Management

**Chart Generation**:
- Artifacts saved to `/app/shared_data/artifacts/<user>/`
- Served via HTTP server at `http://localhost:8080/artifacts/`
- Automatic cleanup after 7 days

---

## Related Documentation

- **[Backend Services](backend_services.md)**: Analytics service architecture
- **[Action Server Architecture](action_server_architecture.md)**: How action server calls analytics
- **[Data Payloads](data_payloads.md)**: Payload format details

---

**Analytics API** - 30+ analysis types for comprehensive building intelligence. 📊🔬✨
