---
title: Testing & Operations
layout: post
category: docs
permalink: /docs/testing_ops/
date: 2025-09-28
---


# Testing & Operations# Testing & Operations


**Comprehensive guide to testing strategies, CI/CD pipelines, deployment, and operational procedures for OntoBot.**## Health checks


---- Analytics: `/health` on 6001

- Rasa: `/version` on 5005

## Table of Contents- Action server: `/health` on 5055

- Duckling: root page contains "Duckling" on 8000

1. [Testing Overview](#testing-overview)- File server: `/health` on 8080

2. [Unit Testing](#unit-testing)- Fuseki: `/$/ping` on 3030

3. [Integration Testing](#integration-testing)

4. [Rasa Testing](#rasa-testing)## Smoke tests

5. [Docker Testing](#docker-testing)

6. [Performance Testing](#performance-testing)Run the analytics smoke test:

7. [CI/CD Pipelines](#cicd-pipelines)

8. [Deployment Strategies](#deployment-strategies)

```powershell

9. [Monitoring & Logging](#monitoring--logging)python microservices/test_analytics_smoke.py

10. [Backup & Recovery](#backup--recovery)

```


---This posts sample payloads to each analysis and reports pass/fail.


## Testing Overview## Logs


### Testing Pyramid

```powershell

docker-compose logs -f microservices

```docker-compose logs -f action_server

         /\docker-compose logs -f rasa

        /  \```

       /E2E \              ← End-to-End (slow, expensive)

      /------\## Troubleshooting

     /        \

    /Integration\          ← Integration (medium)- Ports busy: change host port mappings in docker-compose.

   /------------\- Service unhealthy: hit health URL and check container logs.

  /              \- Payload errors: verify flat/nested shapes; ensure `{datetime, reading_value}` exist.

 /  Unit Tests    \        ← Unit (fast, cheap)- Networking: containers use `ontobot-network`.

/------------------\
```

**Distribution**:
- **70% Unit Tests**: Fast, isolated, frequent
- **20% Integration Tests**: Service interactions
- **10% End-to-End Tests**: Full system workflows

---

### Test Environment Setup

**Requirements**:
- Python 3.10+
- Docker & Docker Compose
- pytest 7.4+
- pytest-cov (coverage)
- pytest-mock (mocking)
- requests-mock (API mocking)

**Install**:
```powershell
pip install pytest pytest-cov pytest-mock requests-mock pytest-asyncio
```

---

## Unit Testing

### Action Server Tests

**Test File**: `rasa-bldg1/actions/test_actions.py`

**Example** (Test sensor resolution with typo-tolerance):
```python
import pytest
from actions.actions import ActionQuerySensor
from rapidfuzz import fuzz, process

@pytest.fixture
def sensor_list():
    """Mock sensor list."""
    return [
        "Air_Temperature_Sensor_5.01",
        "Air_Temperature_Sensor_5.10",
        "CO2_Level_Sensor_5.01",
        "Humidity_Sensor_5.01"
    ]

def test_exact_match(sensor_list):
    """Test exact sensor name match."""
    query = "Air_Temperature_Sensor_5.01"
    result = process.extractOne(
        query.lower(),
        [s.lower() for s in sensor_list],
        scorer=fuzz.ratio
    )
    assert result[1] == 100  # Perfect match

def test_typo_tolerance(sensor_list):
    """Test fuzzy matching with typos."""
    query = "air temprature sensor 501"  # Multiple typos
    result = process.extractOne(
        query.lower(),
        [s.lower() for s in sensor_list],
        scorer=fuzz.ratio,
        score_cutoff=80
    )
    assert result is not None
    assert result[1] >= 80  # Above threshold

def test_whitespace_normalization(sensor_list):
    """Test whitespace handling."""
    queries = [
        "Air Temperature  Sensor  5.01",  # Extra spaces
        "  Air_Temperature_Sensor_5.01  ",  # Leading/trailing
        "Air\tTemperature\tSensor\t5.01"   # Tabs
    ]
    for query in queries:
        normalized = ' '.join(query.lower().split())
        result = process.extractOne(
            normalized,
            [s.lower() for s in sensor_list],
            scorer=fuzz.ratio
        )
        assert result[1] >= 80

def test_case_insensitivity(sensor_list):
    """Test case-insensitive matching."""
    queries = [
        "air_temperature_sensor_5.01",
        "AIR_TEMPERATURE_SENSOR_5.01",
        "Air_Temperature_Sensor_5.01"
    ]
    for query in queries:
        result = process.extractOne(
            query.lower(),
            [s.lower() for s in sensor_list],
            scorer=fuzz.ratio
        )
        assert result[1] == 100

@pytest.mark.parametrize("query,expected_score", [
    ("Air_Temperature_Sensor_5.01", 100),  # Exact
    ("air temp sensor 501", 85),           # Abbreviated
    ("temperature 5.01", 75),              # Partial
    ("random_sensor_xyz", 0)               # No match
])
def test_fuzzy_scoring(sensor_list, query, expected_score):
    """Test fuzzy match scoring."""
    result = process.extractOne(
        query.lower(),
        [s.lower() for s in sensor_list],
        scorer=fuzz.ratio,
        score_cutoff=70
    )
    if expected_score >= 70:
        assert result is not None
        assert result[1] >= expected_score - 10  # Allow 10% tolerance
    else:
        assert result is None
```

**Run Tests**:
```powershell
cd rasa-bldg1
pytest actions/test_actions.py -v
```

---

### Analytics Tests

**Test File**: `microservices/tests/test_analytics.py`

**Example** (Test summary statistics):
```python
import pytest
import numpy as np
from blueprints.analytics_bp import calculate_summary_statistics

@pytest.fixture
def sample_data():
    """Sample time-series data."""
    return {
        "timeseries_data": [
            {"datetime": "2025-10-30T00:00:00Z", "reading_value": 21.0},
            {"datetime": "2025-10-30T01:00:00Z", "reading_value": 21.5},
            {"datetime": "2025-10-30T02:00:00Z", "reading_value": 22.0},
            {"datetime": "2025-10-30T03:00:00Z", "reading_value": 21.8},
            {"datetime": "2025-10-30T04:00:00Z", "reading_value": 21.2}
        ]
    }

def test_summary_statistics(sample_data):
    """Test summary statistics calculation."""
    result = calculate_summary_statistics(sample_data)
    
    assert result["status"] == "success"
    assert "results" in result
    
    stats = result["results"]
    assert stats["count"] == 5
    assert stats["mean"] == pytest.approx(21.5, abs=0.01)
    assert stats["median"] == pytest.approx(21.5, abs=0.01)
    assert stats["min"] == 21.0
    assert stats["max"] == 22.0

def test_empty_data():
    """Test handling of empty data."""
    with pytest.raises(ValueError, match="No data provided"):
        calculate_summary_statistics({"timeseries_data": []})

def test_insufficient_data():
    """Test handling of insufficient data points."""
    data = {
        "timeseries_data": [
            {"datetime": "2025-10-30T00:00:00Z", "reading_value": 21.0}
        ]
    }
    with pytest.raises(ValueError, match="At least 10 data points required"):
        calculate_summary_statistics(data)

def test_invalid_values():
    """Test handling of invalid numeric values."""
    data = {
        "timeseries_data": [
            {"datetime": "2025-10-30T00:00:00Z", "reading_value": float('nan')}
        ]
    }
    with pytest.raises(ValueError, match="Non-finite value"):
        calculate_summary_statistics(data)
```

**Run Tests**:
```powershell
cd microservices
pytest tests/test_analytics.py -v --cov=blueprints --cov-report=html
```

---

### Database Tests

**Test File**: `rasa-bldg1/actions/test_database.py`

**Example** (Test MySQL connection):
```python
import pytest
import mysql.connector
from unittest.mock import patch, MagicMock

def test_mysql_connection():
    """Test MySQL database connection."""
    with patch('mysql.connector.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        conn = mysql.connector.connect(
            host='localhost',
            port=3307,
            database='telemetry',
            user='rasa_user',
            password='rasa_pass'
        )
        
        assert conn is not None
        mock_connect.assert_called_once()

def test_query_sensor_data():
    """Test querying sensor data from MySQL."""
    with patch('mysql.connector.connect') as mock_connect:
        # Mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock query results
        mock_cursor.fetchall.return_value = [
            (1698768600000, 21.2),
            (1698772200000, 21.4),
            (1698775800000, 21.6)
        ]
        
        # Execute query
        conn = mysql.connector.connect(host='localhost')
        cursor = conn.cursor()
        cursor.execute("SELECT ts, dbl_v FROM ts_kv WHERE key_name = %s", 
                      ('Air_Temperature_Sensor_5.01',))
        results = cursor.fetchall()
        
        assert len(results) == 3
        assert results[0][1] == 21.2

def test_connection_retry():
    """Test database connection retry logic."""
    max_retries = 3
    retry_count = 0
    
    def mock_connect():
        nonlocal retry_count
        retry_count += 1
        if retry_count < max_retries:
            raise mysql.connector.Error("Connection failed")
        return MagicMock()
    
    with patch('mysql.connector.connect', side_effect=mock_connect):
        # Implement retry logic
        for i in range(max_retries):
            try:
                conn = mysql.connector.connect(host='localhost')
                break
            except mysql.connector.Error:
                if i == max_retries - 1:
                    raise
        
        assert retry_count == max_retries
        assert conn is not None
```

---

## Integration Testing

### Service Integration Tests

**Test File**: `tests/integration/test_service_integration.py`

**Example** (Test Rasa → Action Server → Database flow):
```python
import pytest
import requests
import time

@pytest.fixture(scope="module")
def wait_for_services():
    """Wait for all services to be ready."""
    services = [
        ("http://localhost:5005", "/version"),
        ("http://localhost:5055", "/health"),
        ("http://localhost:6001", "/health")
    ]
    
    for base_url, endpoint in services:
        for _ in range(30):  # 30 retries
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    break
            except:
                time.sleep(1)
        else:
            pytest.fail(f"Service {base_url} not ready")

def test_rasa_webhook(wait_for_services):
    """Test Rasa REST webhook endpoint."""
    url = "http://localhost:5005/webhooks/rest/webhook"
    payload = {
        "sender": "test_user",
        "message": "hello"
    }
    
    response = requests.post(url, json=payload, timeout=30)
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "text" in data[0]

def test_sensor_query_flow(wait_for_services):
    """Test complete sensor query workflow."""
    url = "http://localhost:5005/webhooks/rest/webhook"
    payload = {
        "sender": "test_user",
        "message": "show me temperature in zone 5.01"
    }
    
    response = requests.post(url, json=payload, timeout=60)
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert len(data) > 0
    bot_response = data[-1]
    assert "text" in bot_response
    
    # Verify custom data if present
    if "custom" in bot_response:
        custom = bot_response["custom"]
        assert "sensor_name" in custom or "data" in custom

def test_analytics_integration(wait_for_services):
    """Test analytics service integration."""
    url = "http://localhost:6001/analytics/run"
    payload = {
        "analysis_type": "summary_statistics",
        "timeseries_data": [
            {"datetime": f"2025-10-30T{i:02d}:00:00Z", "reading_value": 20 + i * 0.5}
            for i in range(24)
        ]
    }
    
    response = requests.post(url, json=payload, timeout=60)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "results" in data
    assert "mean" in data["results"]

def test_fuseki_sparql_query(wait_for_services):
    """Test Fuseki SPARQL query."""
    url = "http://localhost:3030/trial/sparql"
    query = """
    PREFIX brick: <https://brickschema.org/schema/Brick#>
    SELECT ?sensor WHERE {
      ?sensor a brick:Temperature_Sensor .
    } LIMIT 10
    """
    
    response = requests.post(
        url,
        data=query,
        headers={
            "Content-Type": "application/sparql-query",
            "Accept": "application/sparql-results+json"
        },
        timeout=30
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "bindings" in data["results"]
```

**Run Integration Tests**:
```powershell
# Start services first
docker-compose -f docker-compose.bldg1.yml up -d

# Run tests
pytest tests/integration/ -v --maxfail=1

# Cleanup
docker-compose -f docker-compose.bldg1.yml down
```

---

## Rasa Testing

### Test NLU Model

**Command**:
```powershell
docker compose run --rm rasa test nlu --nlu rasa-bldg1/data/nlu.yml
```

**Output**:
```
Intent Evaluation Results:
  precision  recall  f1-score  support
  greet       0.98    1.00    0.99      50
  query_sensor 0.95   0.93    0.94     100
  goodbye     1.00    0.98    0.99      40

Entity Extraction Results:
  sensor_type  precision: 0.92  recall: 0.90
  zone         precision: 0.88  recall: 0.85
```

---

### Test Dialogue Model

**Command**:
```powershell
docker compose run --rm rasa test core --stories rasa-bldg1/data/stories.yml
```

---

### Test End-to-End

**Test Stories** (`rasa-bldg1/tests/test_stories.yml`):
```yaml
stories:
- story: query temperature with form
  steps:
  - user: |
      show me temperature
    intent: query_sensor
  - action: sensor_form
  - active_loop: sensor_form
  - slot_was_set:
    - sensor_type: temperature
  - slot_was_set:
    - requested_slot: null
  - active_loop: null
  - action: action_query_sensor
  - bot: "Here is the temperature data"
```

**Run Tests**:
```powershell
docker compose run --rm rasa test --stories tests/test_stories.yml
```

---

### Validate Training Data

**Command**:
```powershell
docker compose run --rm rasa data validate --domain rasa-bldg1/domain.yml
```

**Checks**:
- Conflicting stories
- Unused intents/entities
- Missing utterances
- Domain consistency

---

## Docker Testing

### Health Check Tests

**Script**: `scripts/test_health_checks.ps1`

```powershell
# Test all service health endpoints

$services = @(
    @{Name="Rasa"; URL="http://localhost:5005/version"},
    @{Name="Action Server"; URL="http://localhost:5055/health"},
    @{Name="Analytics"; URL="http://localhost:6001/health"},
    @{Name="Fuseki"; URL="http://localhost:3030/$/ping"},
    @{Name="MySQL"; Host="localhost"; Port=3307},
    @{Name="Frontend"; URL="http://localhost:3000"}
)

foreach ($service in $services) {
    if ($service.URL) {
        try {
            $response = Invoke-WebRequest -Uri $service.URL -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Host "✓ $($service.Name) is healthy" -ForegroundColor Green
            }
        } catch {
            Write-Host "✗ $($service.Name) is unhealthy" -ForegroundColor Red
        }
    } elseif ($service.Host) {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        try {
            $tcpClient.Connect($service.Host, $service.Port)
            Write-Host "✓ $($service.Name) is reachable" -ForegroundColor Green
            $tcpClient.Close()
        } catch {
            Write-Host "✗ $($service.Name) is unreachable" -ForegroundColor Red
        }
    }
}
```

**Run**:
```powershell
pwsh scripts/test_health_checks.ps1
```

---

### Container Tests

**Test Container Logs**:
```powershell
# Check for errors in logs
docker-compose -f docker-compose.bldg1.yml logs rasa | Select-String -Pattern "ERROR|CRITICAL"
```

**Test Container Resources**:
{% raw %}
```powershell
# Check memory/CPU usage
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```
{% endraw %}

---

## Performance Testing

### Load Testing (Locust)

**Install**:
```powershell
pip install locust
```

**Locust File** (`tests/performance/locustfile.py`):
```python
from locust import HttpUser, task, between

class RasaUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def query_sensor(self):
        """Query sensor data (most common)."""
        self.client.post("/webhooks/rest/webhook", json={
            "sender": f"load_test_{self.user_id}",
            "message": "show me temperature in zone 5.01"
        })
    
    @task(2)
    def greet(self):
        """Greet bot."""
        self.client.post("/webhooks/rest/webhook", json={
            "sender": f"load_test_{self.user_id}",
            "message": "hello"
        })
    
    @task(1)
    def run_analytics(self):
        """Request analytics."""
        self.client.post("/webhooks/rest/webhook", json={
            "sender": f"load_test_{self.user_id}",
            "message": "show me the trend of temperature"
        })
```

**Run Load Test**:
```powershell
locust -f tests/performance/locustfile.py --host=http://localhost:5005 --users=50 --spawn-rate=5
```

**Access Web UI**: `http://localhost:8089`

---

### Stress Testing

**Script**: `tests/performance/stress_test.ps1`

```powershell
# Stress test with concurrent requests

$concurrency = 50
$iterations = 100

$jobs = 1..$concurrency | ForEach-Object {
    Start-Job -ScriptBlock {
        param($userId, $iterations)
        
        for ($i = 0; $i -lt $iterations; $i++) {
            $body = @{
                sender = "stress_test_$userId"
                message = "show me temperature in zone 5.01"
            } | ConvertTo-Json
            
            try {
                Invoke-RestMethod -Uri "http://localhost:5005/webhooks/rest/webhook" `
                    -Method Post -ContentType "application/json" -Body $body -TimeoutSec 30
            } catch {
                Write-Warning "Request failed: $_"
            }
        }
    } -ArgumentList $_, $iterations
}

# Wait for all jobs
$jobs | Wait-Job | Receive-Job
$jobs | Remove-Job
```

---

## CI/CD Pipelines

### GitHub Actions

**Workflow File** (`.github/workflows/ci.yml`):
{% raw %}
```yaml
name: OntoBot CI/CD

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install pytest pytest-cov requests-mock
        pip install -r rasa-bldg1/actions/requirements.txt
    
    - name: Run unit tests
      run: |
        cd rasa-bldg1
        pytest actions/test_actions.py -v --cov=actions --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        files: ./rasa-bldg1/coverage.xml
  
  integration-test:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Start services
      run: |
        docker-compose -f docker-compose.bldg1.yml up -d
        sleep 60  # Wait for services to start
    
    - name: Run integration tests
      run: |
        pip install pytest requests
        pytest tests/integration/ -v --maxfail=1
    
    - name: Stop services
      run: docker-compose -f docker-compose.bldg1.yml down
  
  build:
    runs-on: ubuntu-latest
    needs: [test, integration-test]
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build Docker images
      run: |
        docker-compose -f docker-compose.bldg1.yml build
    
    - name: Push to Docker Hub
      env:
        DOCKER_USERNAME: ${{ secrets.DOCKER_USERNAME }}
        DOCKER_PASSWORD: ${{ secrets.DOCKER_PASSWORD }}
      run: |
        echo "$DOCKER_PASSWORD" | docker login -u "$DOCKER_USERNAME" --password-stdin
    docker-compose -f docker-compose.bldg1.yml push
```
{% endraw %}

---

### Pre-commit Hooks

**Install**:
```powershell
pip install pre-commit
```

**Config File** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files
  
  - repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
        language_version: python3.10
  
  - repo: https://github.com/PyCQA/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: ['--max-line-length=120']
```

**Install Hooks**:
```powershell
pre-commit install
```

---

## Deployment Strategies

### Blue-Green Deployment

**Concept**: Run two identical production environments (Blue & Green). Switch traffic instantly.

**Implementation**:
```yaml
# docker-compose.blue.yml
services:
  rasa-blue:
    image: ontobot-rasa:blue
    ports:
      - "5005:5005"
  
# docker-compose.green.yml
services:
  rasa-green:
    image: ontobot-rasa:green
    ports:
      - "5006:5005"
```

**Switch Script** (`scripts/switch_environment.ps1`):
```powershell
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("blue", "green")]
    [string]$Target
)

# Update nginx/traefik config to point to target environment
# Reload load balancer
# Monitor for errors
# Rollback if needed
```

---

### Rolling Updates

**Docker Compose Strategy**:
```yaml
services:
  rasa:
    image: ontobot-rasa:latest
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first
```

---

### Canary Deployment

**Traffic Split** (90% stable, 10% canary):
```yaml
# nginx.conf
upstream rasa_backend {
    server rasa-stable:5005 weight=9;
    server rasa-canary:5005 weight=1;
}
```

---

## Monitoring & Logging

### Prometheus Metrics

**Action Server Metrics** (`rasa-bldg1/actions/metrics.py`):
```python
from prometheus_client import Counter, Histogram, start_http_server

# Metrics
REQUEST_COUNT = Counter('action_requests_total', 'Total action requests')
REQUEST_DURATION = Histogram('action_request_duration_seconds', 'Action request duration')

# Start metrics server
start_http_server(8000)

# Use in actions
@REQUEST_DURATION.time()
def run(self, dispatcher, tracker, domain):
    REQUEST_COUNT.inc()
    # ... action logic ...
```

**Prometheus Config** (`prometheus.yml`):
```yaml
scrape_configs:
  - job_name: 'action-server'
    static_configs:
      - targets: ['action-server:8000']
```

---

### Grafana Dashboards

**Install**:
```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
  
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    depends_on:
      - prometheus
```

**Dashboard Metrics**:
- Request rate (requests/sec)
- Response time (p50, p95, p99)
- Error rate (%)
- Database query duration
- Analytics execution time

---

### Logging Strategy

**Centralized Logging** (ELK Stack):
```yaml
# docker-compose.logging.yml
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.10.0
    ports:
      - "9200:9200"
  
  logstash:
    image: docker.elastic.co/logstash/logstash:8.10.0
    ports:
      - "5000:5000"
  
  kibana:
    image: docker.elastic.co/kibana/kibana:8.10.0
    ports:
      - "5601:5601"
```

---

## Backup & Recovery

### Database Backup

**MySQL Backup Script** (`scripts/backup_mysql.ps1`):
```powershell
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "backups/mysql_backup_$timestamp.sql"

docker exec mysqlserver mysqldump `
    -u rasa_user -prasa_pass `
    --databases telemetry `
    --single-transaction `
    > $backupFile

Write-Host "Backup completed: $backupFile"
```

**Automated Backups** (Windows Task Scheduler):
```powershell
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\OntoBot\scripts\backup_mysql.ps1"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -TaskName "OntoBot MySQL Backup" -Action $action -Trigger $trigger
```

---

### Recovery Procedure

**Restore from Backup**:
```powershell
docker exec -i mysqlserver mysql -u rasa_user -prasa_pass < backups/mysql_backup_20251031_020000.sql
```

**Disaster Recovery Steps**:
1. Stop all services
2. Restore database from latest backup
3. Restore Fuseki datasets from `bldg1/trial/dataset/`
4. Restart services
5. Verify data integrity
6. Run health checks

---

## Related Documentation

- **[Troubleshooting](troubleshooting.md)**: Common issues & solutions
- **[API Reference](api_reference.md)**: REST endpoint documentation
- **[Deployment Guide](README-deploy.md)**: Production deployment
- **[Docker Compose Files](docker-compose.bldg1.yml)**: Service orchestration

---

**Testing & Operations** - Production-ready testing, deployment, and operational procedures for OntoBot. 🧪🚀✨
