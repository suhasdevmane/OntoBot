# Analytics & Decider Deep Dive

This document explains how natural language questions become "analytics applications" inside OntoBot: the data flow, the function contract, how to add new analytics routines, and how the Rasa Action Server (and optionally the Decider service) chooses which analytic to run.

---
## 1. End‑to‑End Flow (High Level)

1. User asks a question in the chat UI.
2. Rasa NLU classifies the intent + extracts entities / slots (e.g., `sensor_type`).
3. The Action Server (`actions.py`) executes a custom action (main pipeline) which:
   - Calls the NL→SPARQL service (`nl2sparql`) to translate the question into a SPARQL query.
   - Executes the SPARQL query on Fuseki to resolve ontology entities / external references (e.g., timeseries UUIDs, setpoints).
   - Standardizes any SQL / SPARQL / telemetry response into the canonical analytics payload shape.
   - Chooses an `analytics_type` (either heuristically, from a Rasa slot, or via the Decider microservice).
   - POSTs the payload to the Analytics Service (`/analytics/run`).
4. The Analytics Service dispatches to a registered function (e.g., `analyze_temperatures`, `compare_latest_values`).
5. Result is summarized by the LLM (Ollama/Mistral) and returned to user + artifacts (JSON, charts) are stored.

---
## 2. Canonical Analytics Request Contract

Endpoint: `POST /analytics/run`

Minimal shape sent by the Action Server (keys other than control parameters become sensor data):
```jsonc
{
  "analysis_type": "analyze_temperatures",   // REQUIRED: name of a registered function
  "sensor_uuid_A": [ {"datetime": "2025-02-10 05:31:59", "reading_value": 22.4}, ... ],
  "sensor_uuid_B": [ ... ],
  "humidity_series": [ ... ],
  // Optional tuning parameters (only if the target function signature supports them):
  "acceptable_range": [18, 24],
  "freq": "H",
  "window": 5
}
```

Accepted payload flexibility (auto-normalized by helper utilities in `analytics_service.py`):
- Flat mapping: `{ series_key: [ {timestamp|datetime, reading_value}, ... ], ... }`
- Nested mapping: `{ group_id: { inner_key: { timeseries_data: [...] }, ... }, ... }`
- Single list: `[ {timestamp|datetime, reading_value}, ... ]` (treated as one anonymous series)

The dispatcher extracts control keys (`analysis_type`, known optional params) and regards the rest as time-series collections.

Response skeleton:
```jsonc
{
  "analysis_type": "analyze_temperatures",
  "timestamp": "2025-10-05 12:34:56",
  "results": { /* function specific result */ }
}
```

---
## 3. Registered Analytics Functions (Current Inventory)

Core (pre‑existing) analytics functions:
- analyze_recalibration_frequency
- analyze_failure_trends
- analyze_device_deviation
- analyze_sensor_status
- analyze_air_quality_trends
- analyze_hvac_anomalies
- analyze_supply_return_temp_difference
- analyze_air_flow_variation
- analyze_sensor_trend
- aggregate_sensor_data
- correlate_sensors
- compute_air_quality_index
- generate_health_alerts
- detect_anomalies
- analyze_noise_levels
- analyze_air_quality
- analyze_formaldehyde_levels
- analyze_co2_levels
- analyze_pm_levels
- analyze_temperatures
- analyze_humidity
- analyze_temperature_humidity
- detect_potential_failures
- forecast_downtimes

Decorator‑registered (new extended set):
- current_value
- compare_latest_values
- difference_from_setpoint
- percentage_time_in_range
- top_n_by_latest
- bottom_n_by_latest
- rolling_trend_slope
- rate_of_change
- histogram_bins
- missing_data_report
- time_to_threshold
- baseline_comparison
- range_span

You can see decorator metadata (patterns & descriptions) via: `GET /analytics/list`.

---
## 4. Anatomy of a Function

Example (`current_value`):
```python
@analytics_function(patterns=[r"current (value|reading)", r"latest (temperature|humidity|co2|value)"],
                   description="Return latest reading per detected series")
def current_value(sensor_data, key_filters: Optional[list] = None):
    flat = _aggregate_flat(sensor_data)
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty: continue
        last = df.iloc[-1]
        out[str(key)] = {
            "latest_timestamp": last["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "latest_value": float(last["reading_value"]),
            "unit": _unit_for_key(key),
        }
    return out or {"error": "No matching series"}
```
Key points:
- Accepts the generic `sensor_data` structure (flat or nested). Helpers `_aggregate_flat` and `_df_from_readings` normalize.
- Optional parameters must appear in the signature to be auto‑passed from the POST body.
- Returns plain JSON‑serializable types (dicts, lists, primitives). No Pandas objects.

---
## 5. Adding a New Analytics Function

1. Open `microservices/blueprints/analytics_service.py`.
2. Implement a function that accepts `sensor_data` first.
3. (Preferred) Decorate with `@analytics_function(...)` to auto‑register and expose metadata.
4. If you **don't** use the decorator, add it manually to the `analysis_functions` dict.
5. (Optional) Add regex patterns (NL hints) – these are advisory for future intent routing.
6. Test locally via curl / Postman:
```bash
curl -X POST http://localhost:6001/analytics/run \
  -H "Content-Type: application/json" \
  -d '{
        "analysis_type": "current_value",
        "seriesA": [{"datetime": "2025-10-05 10:00:00", "reading_value": 21.1}],
        "seriesB": [{"datetime": "2025-10-05 10:00:30", "reading_value": 22.9}]
      }'
```
7. Add documentation (update this file) if the function is broadly useful.

Design guidelines:
- Keep runtime O(n) on number of points per series.
- Fail soft (return `{ "error": "..." }`), never raise.
- Add units where inferable.
- Avoid wide floating precision – round where human‑friendly.

---
## 6. Choosing an Analytics Function (Decision Layer)

There are *three* potential decision paths:

A. Slot / Direct User Trigger:
- A Rasa form or button sets slot `analytics_type` explicitly (e.g., `top_n_by_latest`).
- Action Server trusts the slot if it is in the `_supported_types()` set.

B. Heuristic Fallback (currently active in `actions.py`):
- `_supported_types()` enumerates allowed functions.
- `_pick_type_from_context(question, sensor_types)` inspects keywords:
  - "humid" → `analyze_humidity`
  - "temp" / "temperature" → `analyze_temperatures`
  - "co2" → `analyze_co2_levels`
  - "pm" / "particulate" → `analyze_pm_levels`
  - correlation keywords → `correlate_sensors`
  - anomaly / failure words → `detect_potential_failures`
  - otherwise → `analyze_sensor_trend`

C. Decider Microservice (recommended path for scale):
- Invoke: `POST {DECIDER_URL}/decide { "question": "..." }`.
- Response: `{ "perform_analytics": true, "analytics": "analyze_temperatures" }`.
- If `perform_analytics` is false → *skip* analytics call (question is ontology/listing style).
- If label is not in the analytics registry → fallback to heuristic or default.

---
## 7. Integrating Decider in `actions.py` (Example Snippet)

```python
if DECIDER_URL:
    try:
        dresp = requests.post(f"{DECIDER_URL}/decide", json={"question": user_question}, timeout=4).json()
        if dresp.get("perform_analytics"):
            candidate = dresp.get("analytics")
            if candidate in SUPPORTED_ANALYTICS:  # union of registry + static dict
                analytics_type = candidate
        else:
            analytics_type = None  # ontology or listing question
    except Exception:
        logger.warning("Decider fallback – using heuristic")
```

Then continue building the analytics payload only when `analytics_type` is truthy.

---
## 8. Mapping SPARQL/SQL Results to Payload

Typical steps inside the Action Server before calling analytics:
1. Execute SPARQL to fetch external references (timeseries UUIDs) for requested sensors.
2. Retrieve SQL timeseries (or pre‑fetched telemetry) keyed by UUID.
3. Build a JSON object where each UUID (or friendly alias) maps to a list of `{ datetime | timestamp, reading_value }` objects.
4. Add `analysis_type` and any user‑derived parameters.
5. POST to `/analytics/run`.

Helper target structure:
```json
{
  "analysis_type": "compare_latest_values",
  "temp_uuid_1": [{"timestamp": "2025-10-05T10:00:00Z", "reading_value": 21.4}, ...],
  "temp_uuid_2": [{"timestamp": "2025-10-05T10:00:00Z", "reading_value": 22.0}, ...]
}
```

---
## 9. Using the Registry for Dynamic Discovery

The decorator fills `_analytics_registry_meta` with `patterns` and `description`. A future improvement is to let the Decider or Action Server:
- Pull `/analytics/list` on startup.
- Build a dynamic intent classification map (regex or embeddings) → analytics function name.

---
## 10. Testing & Validation Strategy

Recommended minimal checks when adding a new function:
- Empty payload returns a graceful error.
- Single series path works.
- Multi-series path works (if applicable).
- Parameter validation (e.g., threshold required) returns clear message.
- Performance: test with 10k points per series (profiling optional).

Consider adding lightweight unit tests (pytest) that import the blueprint file and call functions directly with synthetic data.

---
## 11. Extending Beyond Statistical Analytics

Ideas:
- Forecasting: ARIMA / Prophet / simple exponential smoothing (with a `forecast_next_hours`).
- Anomaly ensembles: combine z-score + IQR + seasonal decomposition.
- Occupancy‑aware comfort index blending temperature, humidity, CO2.
- Multi-floor aggregation analytics (group key inference on sensor names).
- Visualization endpoints that store base64 PNG charts into artifacts automatically.

---
## 12. Operational Notes

- All analytics run in a single process – heavy CPU tasks could block; consider async pool or Celery for long jobs.
- Add rate limiting if exposed externally.
- Keep response sizes modest; for huge time windows return aggregate + artifact link to full data.

---
## 13. Quick Checklist for Adding an Analytics

| Step | Action | Done? |
|------|--------|-------|
| 1 | Write function accepting `sensor_data` |  |
| 2 | Use `@analytics_function` decorator |  |
| 3 | Add docstring + description |  |
| 4 | (Optional) Patterns for NL hints |  |
| 5 | Local curl test |  |
| 6 | Rasa heuristic / Decider mapping updated |  |
| 7 | Documentation (this file) updated |  |
| 8 | Commit & push |  |

---
## 14. FAQ

**Q: My function needs additional parameters (e.g. `threshold`). How do I pass them?**  
Include them at the top level of the JSON body. The dispatcher inspects the function signature and only forwards matching keyword arguments.

**Q: The analytics output is huge. How can I keep the chat concise?**  
Return summary stats and optionally write the full detail to a JSON artifact file (Action Server already demonstrates how for SPARQL responses).

**Q: How do I support both SPARQL-only (ontology) queries and analytics queries?**  
The Decider or heuristic distinguishes them; if analytics not required, skip the `/analytics/run` call and just summarize or list results.

---
## 15. Roadmap Hooks

Planned / suggested evolutions:
- Embedding-based intent routing (e.g., sentence-transformers) using the registry descriptions as candidate labels.
- Confidence score + fallback chain (Decider → heuristic → default).
- Pluggable analytics packages loaded dynamically from a folder (`analytics_plugins/`).
- Structured provenance block in every response: `{ "source": "analytics_service", "function": "...", "inputs": {..}, "generated_at": "..." }`.

---
**End of analytics.md**
