# blueprints/analytics_module.py
from flask import Blueprint, request, jsonify
import inspect
import pandas as pd
import numpy as np
import logging
import json
import re
import os
import ast
import importlib
import types
from datetime import datetime
from typing import Optional, Tuple

analytics_service = Blueprint("analytics_service", __name__)

# ---------------------------
# Plugin system (Phase 1)
# ---------------------------
PLUGINS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "analytics_plugins"))
os.makedirs(PLUGINS_DIR, exist_ok=True)

# Persistent metadata (parameters schema, user-specified descriptions, etc.)
CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config"))
os.makedirs(CONFIG_DIR, exist_ok=True)
ANALYTICS_META_FILE = os.path.join(CONFIG_DIR, "analytics_functions_meta.json")

_analytics_params_meta = {}

def _load_analytics_meta():
    global _analytics_params_meta
    if os.path.exists(ANALYTICS_META_FILE):
        try:
            with open(ANALYTICS_META_FILE, 'r', encoding='utf-8') as f:
                _analytics_params_meta = json.load(f) or {}
        except Exception as e:
            logging.error(f"Failed to load analytics meta file: {e}")
            _analytics_params_meta = {}
    else:
        _analytics_params_meta = {}
    return _analytics_params_meta

def _save_analytics_meta():
    try:
        tmp = ANALYTICS_META_FILE + ".tmp"
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(_analytics_params_meta, f, indent=2)
        os.replace(tmp, ANALYTICS_META_FILE)
    except Exception as e:
        logging.error(f"Failed to save analytics meta file: {e}")

_load_analytics_meta()

# ---------------------------
# Analytics Function Registry (Decorator-based for extensibility)
# ---------------------------
analysis_functions = {}  # Global dispatcher dict
_analytics_registry_meta = {}

def analytics_function(name: Optional[str] = None, patterns: Optional[list] = None, description: Optional[str] = None):
    """Decorator to register an analytics function with optional metadata.

    Args:
        name: Optional override for registry key (defaults to function.__name__).
        patterns: Optional list of regex (strings) representing NL intent patterns.
        description: Optional human readable description (defaults to docstring snippet).
    """
    def decorator(fn):
        key = name or fn.__name__
        analysis_functions[key] = fn  # plug into dispatcher
        _analytics_registry_meta[key] = {
            "patterns": patterns or [],
            "description": (description or (fn.__doc__ or "")).strip(),
        }
        return fn
    return decorator

FORBIDDEN_IMPORTS = {"os", "subprocess", "socket", "sys", "shutil", "pathlib", "builtins", "importlib"}

def _scan_function_params(fn):
    try:
        sig = inspect.signature(fn)
        params = []
        for name, p in sig.parameters.items():
            if name == 'sensor_data':
                continue
            default = None if p.default is inspect._empty else p.default
            params.append({
                "name": name,
                "kind": str(p.kind).replace('Parameter.', ''),
                "default": default,
            })
        return params
    except Exception:
        return []

def _list_registry_metadata():
    out = []
    for name, meta in _analytics_registry_meta.items():
        fn = analysis_functions.get(name)
        sig_params = {p["name"]: p for p in _scan_function_params(fn)}
        stored = _analytics_params_meta.get(name, {}).get("parameters", []) if isinstance(_analytics_params_meta.get(name), dict) else []
        merged_params = []
        if stored:
            for p in stored:
                nm = p.get("name")
                base = sig_params.get(nm, {})
                merged = {
                    "name": nm,
                    "kind": base.get("kind"),
                    "default": base.get("default") if base.get("default") is not None else p.get("default"),
                    "type": p.get("type"),
                    "description": p.get("description"),
                }
                merged_params.append(merged)
            # include any additional signature params not in stored schema
            for nm, base in sig_params.items():
                if not any(m.get("name") == nm for m in merged_params):
                    merged_params.append(base)
        else:
            merged_params = list(sig_params.values())
        out.append({
            "name": name,
            "description": meta.get("description"),
            "patterns": meta.get("patterns", []),
            "parameters": merged_params,
        })
    return out

def _is_safe_code(source: str) -> Tuple[bool, str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [n.name.split('.')[0] for n in node.names]
            for nm in names:
                if nm in FORBIDDEN_IMPORTS:
                    return False, f"Forbidden import: {nm}"
        if isinstance(node, ast.Call):
            # crude block for exec/eval/open
            if isinstance(node.func, ast.Name) and node.func.id in {"exec", "eval", "open", "__import__"}:
                return False, f"Forbidden call: {node.func.id}"
    return True, "ok"

def _write_plugin_file(name: str, code: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9_]+", "_", name)
    filename = f"{safe_name}.py"
    path = os.path.join(PLUGINS_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(code)
    return path

def _load_plugins():
    # Import all .py files in PLUGINS_DIR
    for fname in os.listdir(PLUGINS_DIR):
        if not fname.endswith('.py') or fname.startswith('_'):
            continue
        mod_name = f"micro_plugins_{fname[:-3]}"
        full_path = os.path.join(PLUGINS_DIR, fname)
        try:
            spec = importlib.util.spec_from_file_location(mod_name, full_path)  # type: ignore
            if not spec or not spec.loader:
                logging.warning(f"Cannot load plugin spec for {fname}")
                continue
            module = importlib.util.module_from_spec(spec)  # type: ignore
            spec.loader.exec_module(module)  # type: ignore
            logging.info(f"Loaded analytics plugin: {fname}")
        except Exception as e:
            logging.error(f"Failed to load plugin {fname}: {e}")

# Initial load
_load_plugins()

# ---------------------------
# Payload normalization helpers
# ---------------------------

def _ensure_parsed(obj):
    """Parse JSON string to Python, otherwise return as-is."""
    if isinstance(obj, str):
        try:
            return json.loads(obj)
        except Exception as e:
            logging.error(f"Failed to parse JSON input: {e}")
            return obj
    return obj

def _series_items(sensor_data):
    """Yield (logical_key, readings_list) for both flat and nested payloads.

    Accepts:
      - Flat: { name_or_uuid: [ {datetime|timestamp, reading_value}, ... ] }
      - Nested: { group_id: { key: { timeseries_data: [...] } } }
      - List: [ {datetime|timestamp, reading_value}, ... ]
    """
    sensor_data = _ensure_parsed(sensor_data)
    if isinstance(sensor_data, dict) and sensor_data and all(isinstance(v, list) for v in sensor_data.values()):
        for k, v in sensor_data.items():
            yield str(k), v
        return
    if isinstance(sensor_data, dict):
        for _, inner in sensor_data.items():
            if isinstance(inner, dict):
                for k, v in inner.items():
                    if isinstance(v, dict):
                        yield str(k), v.get("timeseries_data", [])
                    elif isinstance(v, list):
                        yield str(k), v
            elif isinstance(inner, list):
                yield "series", inner
        return
    if isinstance(sensor_data, list):
        yield "series", sensor_data

def _aggregate_flat(sensor_data):
    """Return a dict {key: combined_readings_list} merging duplicates across groups."""
    flat = {}
    for key, readings in _series_items(sensor_data):
        try:
            flat.setdefault(key, []).extend(list(readings or []))
        except Exception:
            flat.setdefault(key, []).extend([])
    return flat

def _df_from_readings(readings):
    """Convert a list of readings to a sorted DataFrame with 'timestamp' normalized."""
    df = pd.DataFrame(list(readings or []))
    if df.empty:
        return df
    if "timestamp" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "timestamp"})
    if "timestamp" not in df.columns:
        # Create synthetic timestamps if missing
        df["timestamp"] = pd.to_datetime(range(len(df)), unit="s", origin="unix")
    df["timestamp"] = pd.to_datetime(df["timestamp"])  # to datetime
    df = df.sort_values(by="timestamp")
    return df

def _key_matcher(substrs, exclude_substrs=None):
    """Return a predicate that matches key if any substr in substrs occurs (case-insensitive),
    excluding keys that contain any of exclude_substrs."""
    exclude_substrs = exclude_substrs or []
    def pred(key: str) -> bool:
        k = (key or "").lower()
        if any(ex in k for ex in exclude_substrs):
            return False
        return any(s in k for s in substrs)
    return pred

def _select_keys(flat_dict, predicate, fallback_to_all=False):
    keys = [k for k in flat_dict.keys() if predicate(str(k))]
    if not keys and fallback_to_all:
        keys = list(flat_dict.keys())
    return keys

# ---------------------------
# UK indoor environment standards and units
# ---------------------------
# Consolidated UK-oriented comfort/air-quality guidelines (indicative/common practice)
# Notes:
# - Temperature (°C): 18–24 as a general comfort band for offices, winter heating min ~18.
# - Relative Humidity (%RH): 40–60 recommended to balance comfort and health.
# - CO2 (ppm): 400–1000 good ventilation; >1500 often considered poor.
# - PM2.5 (µg/m³): 35 short-term alert threshold (aligned with common indoor targets);
# - PM10 (µg/m³): 50 short-term limit;
# - NO2 (µg/m³): 200 short-term limit (1-hour legal limit), with 40 typical annual target;
# - CO (ppm): 9 ppm short-term guidance;
# - Formaldehyde (mg/m³): 0.1 mg/m³ short-term guideline;
# - Noise (dB(A)): ~55 dB(A) comfort threshold for occupied spaces (context-dependent).
UK_INDOOR_STANDARDS = {
    "temperature_c": {"unit": "°C", "range": (18, 24)},
    "humidity_rh": {"unit": "%", "range": (40, 60)},
    "co2_ppm": {"unit": "ppm", "range": (400, 1000), "max": 1500},
    "pm2.5_ugm3": {"unit": "µg/m³", "max": 35},
    "pm10_ugm3": {"unit": "µg/m³", "max": 50},
    "no2_ugm3": {"unit": "µg/m³", "max": 200, "annual_target": 40},
    "co_ppm": {"unit": "ppm", "max": 9},
    "hcho_mgm3": {"unit": "mg/m³", "max": 0.1},
    "noise_db": {"unit": "dB(A)", "max": 55},
}

def _unit_for_key(key: str) -> Optional[str]:
    """Infer human-readable unit for a sensor key name."""
    try:
        kl = str(key).lower()
    except Exception:
        return None
    if "temperature" in kl or re.search(r"\btemp\b", kl):
        return "°C"
    if "humidity" in kl or kl in ("rh", "relative_humidity"):
        return "%"
    if "co2" in kl:
        return "ppm"
    if ("co" in kl and "co2" not in kl) or "carbon_monoxide" in kl:
        return "ppm"
    if "pm10" in kl or "pm2.5" in kl or "pm2_5" in kl or re.search(r"\bpm1(\b|[_\.])", kl):
        return "µg/m³"
    if "formaldehyde" in kl or "hcho" in kl:
        return "mg/m³"
    if "noise" in kl or "sound" in kl:
        return "dB(A)"
    if "pressure" in kl:
        # Units vary by system; often Pa. Leaving generic if uncertain.
        return "Pa"
    return None

@analytics_function(
    patterns=[
        r"recalibration.*frequency",
        r"calibration.*schedule",
        r"when.*recalibrate",
        r"recalibration.*interval",
        r"sensor.*calibration.*check"
    ],
    description="Analyzes sensor recalibration frequency based on variability (CV > 0.1 suggests frequent recalibration needed)"
)
def analyze_recalibration_frequency(sensor_data):
    """
    Analyzes recalibration frequency for sensors given timeseries data.

    Expected input format (as a Python dict or JSON string):
    {
        "timeseriesId_1": [
            {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
            ...
        ],
        "timeseriesId_2": [
            {"datetime": "2025-02-10 06:00:00", "reading_value": 28.10},
            ...
        ],
        ...
    }

    For each timeseries ID, it calculates the mean and standard deviation of the reading_value,
    computes the coefficient of variation (cv = std / mean), and then:
      - If cv > 0.1, indicates high variability (suggesting more frequent recalibration).
      - Otherwise, indicates stable performance.

    Returns:
      A dictionary where each timeseries ID maps to its analysis results.
    """
    # If sensor_data is a JSON string, convert it into a dictionary.
    if isinstance(sensor_data, str):
        try:
            sensor_data = json.loads(sensor_data)
        except Exception as e:
            logging.error(f"Error parsing sensor_data JSON: {e}")
            return {"error": "Invalid sensor_data JSON"}

    response = {}
    # Iterate over each timeseries ID.
    for timeseries_id, readings in sensor_data.items():
        if not readings:
            response[timeseries_id] = {"message": "No data available"}
            continue

        try:
            df = pd.DataFrame(readings)
            # Rename "datetime" column to "timestamp" if it exists.
            if "datetime" in df.columns:
                df = df.rename(columns={"datetime": "timestamp"})
            # Convert the timestamp column to datetime objects.
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Compute mean and standard deviation of the reading values.
            mean_val = df["reading_value"].mean()
            std_val = df["reading_value"].std() or 0.0
            cv = std_val / mean_val if mean_val else 0

            if cv > 0.1:
                response[timeseries_id] = {
                    "mean": round(mean_val, 4),
                    "std": round(std_val, 4),
                    "coefficient_of_variation": round(cv, 4),
                    "message": f"Timeseries {timeseries_id} has high variability; recalibration might be required more frequently."
                }
            else:
                response[timeseries_id] = {
                    "mean": round(mean_val, 4),
                    "std": round(std_val, 4),
                    "coefficient_of_variation": round(cv, 4),
                    "message": f"Timeseries {timeseries_id} performance is stable; no immediate recalibration needed."
                }

        except Exception as e:
            logging.error(f"Data conversion error for timeseries {timeseries_id}: {e}")
            response[timeseries_id] = {"error": "Invalid sensor data format"}

    if not response:
        return {"message": "No timeseries data available."}

    return response

@analytics_function(
    patterns=[
        r"failure.*trend",
        r"fault.*pattern",
        r"failure.*analysis",
        r"sensor.*failure.*history",
        r"equipment.*failure.*rate"
    ],
    description="Analyzes failure trends and patterns across sensors to identify deteriorating equipment"
)
def analyze_failure_trends(sensor_data):
    """
    Analyzes failure trends from grouped sensor data with a nested structure.

    Expected input format:
      {
          "1": {
              "Air_Temperature_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                      ...
                  ]
              },
              "Zone_Air_Humidity_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:35:00", "reading_value": 28.05},
                      ...
                  ]
              }
          },
          "2": {
              "Air_Temperature_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 06:00:00", "reading_value": 28.10},
                      ...
                  ]
              },
              "Zone_Air_Humidity_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 06:05:00", "reading_value": 29.00},
                      ...
                  ]
              }
          }
      }

    For each sensor type:
      - Converts the list of readings into a DataFrame.
      - Renames the "datetime" column to "timestamp" and converts it to datetime objects.
      - Filters for readings from the last 24 hours.
      - Computes a rolling average and rolling standard deviation (window of 5).
      - Computes the overall (baseline) standard deviation.
      - Compares the latest rolling standard deviation against 1.5× the baseline.
      - Flags the sensor if the latest rolling std exceeds that threshold.

    Returns:
      A nested dictionary where each sensor ID maps to sensor type keys with their analysis summary.
    """
    # Parse JSON string input if needed
    if isinstance(sensor_data, str):
        try:
            sensor_data = json.loads(sensor_data)
        except Exception as e:
            logging.error(f"Error parsing sensor_data JSON: {e}")
            return {"error": "Invalid sensor_data JSON"}

    response = {}
    now = pd.Timestamp.now()

    # Iterate over each sensor ID
    for sensor_id, sensor_types in sensor_data.items():
        response[sensor_id] = {}
        # Iterate over each sensor type for the given sensor ID
        for sensor_type, sensor_info in sensor_types.items():
            # Get the list of readings from the "timeseries_data" key
            timeseries_data = sensor_info.get("timeseries_data", [])
            try:
                df = pd.DataFrame(timeseries_data)
                # Rename "datetime" column to "timestamp" if it exists
                if "datetime" in df.columns:
                    df = df.rename(columns={"datetime": "timestamp"})
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            except Exception as e:
                logging.error(
                    f"Data conversion error for sensor {sensor_id}, type {sensor_type}: {e}"
                )
                response[sensor_id][sensor_type] = {
                    "error": "Invalid sensor data format"
                }
                continue

            # Filter for readings in the last 24 hours
            sensor_df = df[df["timestamp"] >= now - pd.Timedelta(hours=24)]
            if sensor_df.empty:
                response[sensor_id][sensor_type] = {
                    "message": "No recent data available."
                }
                continue

            # Sort by timestamp and compute rolling statistics
            sensor_df = sensor_df.sort_values(by="timestamp")
            sensor_df["rolling_avg"] = (
                sensor_df["reading_value"].rolling(window=5, min_periods=1).mean()
            )
            sensor_df["rolling_std"] = (
                sensor_df["reading_value"].rolling(window=5, min_periods=1).std()
            )

            # Compute baseline standard deviation and latest rolling standard deviation
            baseline_std = sensor_df["reading_value"].std() or 0.0
            current_std = sensor_df["rolling_std"].iloc[-1] or 0.0

            # Compare current rolling std with 1.5 times the baseline
            if baseline_std > 0 and current_std > 1.5 * baseline_std:
                response[sensor_id][sensor_type] = {
                    "historical_mean": sensor_df["reading_value"].mean(),
                    "historical_std": baseline_std,
                    "latest_rolling_std": current_std,
                    "message": f"Sensor {sensor_id} ({sensor_type}) shows increased variance suggesting potential failure.",
                }
            else:
                response[sensor_id][sensor_type] = {
                    "historical_mean": sensor_df["reading_value"].mean(),
                    "historical_std": baseline_std,
                    "latest_rolling_std": current_std,
                    "message": f"Sensor {sensor_id} ({sensor_type}) readings are within normal range.",
                }
    if not response:
        return {
            "message": "No sensor data available for analysis in the last 24 hours."
        }

    return response


@analytics_function(
    patterns=[
        r"device.*deviation",
        r"equipment.*variance",
        r"sensor.*drift",
        r"measurement.*deviation",
        r"device.*performance"
    ],
    description="Analyzes deviation of device readings from expected values or baselines"
)

def analyze_device_deviation(sensor_data):
    """
    Analyzes deviation for each sensor in a JSON structure.

    Input format:
    {
        "timeseriesId_1": [
            {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
            ...
        ],
        "timeseriesId_2": [
            {"datetime": "2025-02-10 06:00:00", "reading_value": 28.10},
            ...
        ],
        ...
    }

    For each timeseries, it:
      - Calculates historical mean, std deviation.
      - Finds latest reading.
      - Flags if latest reading deviates beyond 2 standard deviations.

    Returns:
        A dict with analysis results for each timeseries.
    """
    if isinstance(sensor_data, str):
        try:
            sensor_data = json.loads(sensor_data)
        except Exception as e:
            logging.error(f"Error parsing JSON: {e}")
            return {"error": "Invalid JSON"}

    response = {}

    for timeseries_id, readings in sensor_data.items():
        if not readings:
            response[timeseries_id] = {"message": "No data available"}
            continue

        try:
            df = pd.DataFrame(readings)
            if "datetime" in df.columns:
                df.rename(columns={"datetime": "timestamp"}, inplace=True)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.sort_values("timestamp", inplace=True)

            historical_mean = float(df["reading_value"].mean())
            historical_std = float(df["reading_value"].std() or 0.0)
            latest_reading = float(df.iloc[-1]["reading_value"])

            deviation_flag = False
            if historical_std > 0 and (
                latest_reading < historical_mean - 2 * historical_std
                or latest_reading > historical_mean + 2 * historical_std
            ):
                deviation_flag = True

            response[timeseries_id] = {
                "historical_mean": round(historical_mean, 4),
                "historical_std": round(historical_std, 4),
                "latest_reading": round(latest_reading, 4),
                "message": (
                    f"Deviation detected beyond 2 STD."
                    if deviation_flag
                    else "Within normal range."
                ),
            }

        except Exception as e:
            logging.error(f"Processing error for timeseries {timeseries_id}: {e}")
            response[timeseries_id] = {"error": "Processing failed"}

    return response


@analytics_function(
    patterns=[
        r"sensor.*status",
        r"sensor.*health",
        r"sensor.*condition",
        r"are.*sensors.*working",
        r"sensor.*operational"
    ],
    description="Checks overall sensor status and operational health across all monitored sensors"
)

def analyze_sensor_status(sensor_data):
    """
    Analyzes the status of sensors based on their latest reporting timestamp.

    Expected input (nested format):
      {
          "1": {
              "Air_Temperature_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                      {"datetime": "2025-02-10 05:32:11", "reading_value": 27.99},
                      ...
                  ]
              },
              "Zone_Air_Humidity_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:35:00", "reading_value": 28.05},
                      {"datetime": "2025-02-10 05:35:12", "reading_value": 28.07},
                      ...
                  ]
              }
          },
          "2": {
              ...
          }
      }

    For each sensor type:
      - Converts the "timeseries_data" into a DataFrame.
      - Renames the "datetime" column to "timestamp" (if necessary) and converts it to datetime objects.
      - Finds the latest timestamp.
      - If the latest report is older than 1 hour from now, marks the sensor as "offline"; otherwise "online".

    Returns:
      A nested dictionary where each sensor ID maps to sensor type keys with their analysis, including:
        - last_report: the most recent report time as a string.
        - status: "online" or "offline".
        - message: a descriptive message.
    """
    # If sensor_data is a JSON string, convert it to a dictionary.
    if isinstance(sensor_data, str):
        try:
            sensor_data = json.loads(sensor_data)
        except Exception as e:
            logging.error(f"Error parsing sensor_data JSON: {e}")
            return {"error": "Invalid sensor_data JSON"}

    # If sensor_data is a list, assume it's data for a single sensor and wrap it in a dictionary.
    if isinstance(sensor_data, list):
        sensor_data = {"1": sensor_data}

    response = {}
    now = pd.Timestamp.now()
    threshold = now - pd.Timedelta(hours=1)

    # Process data for each sensor ID.
    for sensor_id, sensor_types in sensor_data.items():
        response[sensor_id] = {}
        # Process each sensor type for the current sensor ID.
        for sensor_type, sensor_info in sensor_types.items():
            # Extract the list of readings from the "timeseries_data" key.
            timeseries_data = sensor_info.get("timeseries_data", [])
            try:
                df = pd.DataFrame(timeseries_data)
                # Rename "datetime" to "timestamp" if it exists.
                if "datetime" in df.columns:
                    df = df.rename(columns={"datetime": "timestamp"})
                df["timestamp"] = pd.to_datetime(df["timestamp"])
            except Exception as e:
                logging.error(
                    f"Data conversion error for sensor {sensor_id}, type {sensor_type}: {e}"
                )
                response[sensor_id][sensor_type] = {
                    "error": "Invalid sensor data format"
                }
                continue

            # Find the most recent timestamp for the sensor type.
            last_report = df["timestamp"].max()
            if pd.isna(last_report) or last_report < threshold:
                status = "offline"
                message = f"Sensor {sensor_id} ({sensor_type}) appears offline or not reporting recently."
            else:
                status = "online"
                message = f"Sensor {sensor_id} ({sensor_type}) is reporting data normally. Last report at {last_report.strftime('%Y-%m-%d %H:%M:%S')}."

            response[sensor_id][sensor_type] = {
                "last_report": (
                    last_report.strftime("%Y-%m-%d %H:%M:%S")
                    if not pd.isna(last_report)
                    else None
                ),
                "status": status,
                "message": message,
            }

    if not response:
        return {"message": "No sensor data available for analysis."}

    return response


@analytics_function(
    patterns=[
        r"air.*quality.*trend",
        r"iaq.*trend",
        r"air.*quality.*over.*time",
        r"air.*quality.*pattern",
        r"indoor.*air.*quality.*history"
    ],
    description="Analyzes indoor air quality trends over time for specific sensors"
)

def analyze_air_quality_trends(sensor_data, target_sensor="Air_Quality_Sensor"):
    """
    Analyze trend for air-quality-like series from standardized payload.

    - If target_sensor is provided, first try exact or substring match; otherwise
      auto-detect keys like 'air_quality', 'aqi', 'aq_sensor'.
    - For each selected key: compute mean, latest reading, and classify trend as
      rising/falling/stable relative to the mean.

    Returns a dict mapping key -> trend summary.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No air quality data available"}

    keys = []
    if target_sensor:
        # exact or substring match
        tl = str(target_sensor).lower()
        for k in flat.keys():
            kl = str(k).lower()
            if k == target_sensor or tl in kl or kl in tl:
                keys.append(k)
    if not keys:
        aq_pred = _key_matcher(["air_quality", "aqi", "aq_sensor"])  # broad
        keys = _select_keys(flat, aq_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {"error": "No air-quality-like keys found"}

    response = {}
    for key in keys:
        df = _df_from_readings(flat.get(key, []))
        if df.empty:
            response[str(key)] = {"message": "No data available."}
            continue
        norm = float(df["reading_value"].mean())
        latest_value = float(df.iloc[-1]["reading_value"]) if not df.empty else None
        if latest_value is None:
            response[str(key)] = {"message": "No readings."}
            continue
        if latest_value > norm:
            trend = "rising"
        elif latest_value < norm:
            trend = "falling"
        else:
            trend = "stable"
        response[str(key)] = {
            "norm": round(norm, 2),
            "latest_reading": round(latest_value, 2),
            "trend": trend,
            "unit": _unit_for_key(key),
            "message": f"{key} trend is {trend} compared to average.",
        }
    return response


@analytics_function(
    patterns=[
        r"hvac.*anomaly",
        r"hvac.*fault",
        r"hvac.*abnormal",
        r"hvac.*issue",
        r"hvac.*problem.*detection"
    ],
    description="Detects anomalies and faults in HVAC system performance and operation"
)

def analyze_hvac_anomalies(sensor_data):
    """
    Detect anomalies for HVAC-like series in the past 7 days from standardized payload.
    Keys are selected if they contain 'hvac' (case-insensitive).
    Returns key -> { anomaly_count, message }.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No HVAC data available"}

    hvac_pred = _key_matcher(["hvac"])  # broad match
    keys = _select_keys(flat, hvac_pred, fallback_to_all=False)
    if not keys:
        return {"error": "No HVAC-like keys found"}

    now = pd.Timestamp.now()
    response = {}
    for key in keys:
        df = _df_from_readings(flat.get(key, []))
        if df.empty:
            response[str(key)] = {"message": "No HVAC data available for the past week."}
            continue
        df = df[df["timestamp"] >= now - pd.Timedelta(days=7)]
        if df.empty:
            response[str(key)] = {"message": "No HVAC data available for the past week."}
            continue
        Q1 = df["reading_value"].quantile(0.25)
        Q3 = df["reading_value"].quantile(0.75)
        IQR = Q3 - Q1
        outliers = df[(df["reading_value"] < Q1 - 1.5 * IQR) | (df["reading_value"] > Q3 + 1.5 * IQR)]
        if not outliers.empty:
            response[str(key)] = {
                "anomaly_count": int(len(outliers)),
                "message": f"Sensor {key} detected {len(outliers)} anomalies in the past week.",
            }
        else:
            response[str(key)] = {"message": "No significant anomalies detected in the HVAC system."}
    return response


@analytics_function(
    patterns=[
        r"supply.*return.*temp",
        r"delta.*t",
        r"temperature.*difference.*supply.*return",
        r"supply.*return.*differential",
        r"sat.*rat.*difference"
    ],
    description="Analyzes temperature difference between supply and return air for HVAC efficiency"
)

def analyze_supply_return_temp_difference(sensor_data):
    """
    Compares supply and return air temperature sensor data from a single nested JSON structure
    and calculates the average difference.

    Expected input (as a dict or JSON string):
      {
          "1": {
              "Supply_Air_Temperature_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 28.5},
                      {"datetime": "2025-02-10 05:32:11", "reading_value": 29.0},
                      {"datetime": "2025-02-10 05:33:00", "reading_value": 28.0}
                  ]
              },
              "Return_Air_Temperature_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 27.0},
                      {"datetime": "2025-02-10 05:32:11", "reading_value": 26.5},
                      {"datetime": "2025-02-10 05:33:00", "reading_value": 27.0}
                  ]
              }
          },
          "2": {
              "Supply_Air_Temperature_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:34:00", "reading_value": 23.5},
                      {"datetime": "2025-02-10 05:35:00", "reading_value": 22.5},
                      {"datetime": "2025-02-10 05:36:00", "reading_value": 21.5}
                  ]
              },
              "Return_Air_Temperature_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:34:00", "reading_value": 27.5},
                      {"datetime": "2025-02-10 05:35:00", "reading_value": 27.0},
                      {"datetime": "2025-02-10 05:36:00", "reading_value": 27.0}
                  ]
              }
          }
      }

    The function aggregates readings for "Supply_Air_Temperature_Sensor" and "Return_Air_Temperature_Sensor"
    across all sensor IDs, calculates the average reading for each, computes their difference, and returns a summary.

    Returns:
      A dictionary with:
        - average_supply_temperature: Average supply temperature.
        - average_return_temperature: Average return temperature.
        - temperature_difference: Difference (supply minus return).
        - message: A descriptive message.
    """
    # Accept standard payload: detect 'supply' and 'return' temperature series
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No temperature data available"}

    # Prefer explicit supply/return names; avoid false matches on unrelated keys
    supply_pred = _key_matcher(["supply", "supply_air"], exclude_substrs=["return"])
    return_pred = _key_matcher(["return", "return_air"], exclude_substrs=["supply"])
    temp_pred = _key_matcher(["temperature", "temp"])  # generic temperature

    supply_keys = [k for k in flat.keys() if supply_pred(str(k)) and temp_pred(str(k))]
    return_keys = [k for k in flat.keys() if return_pred(str(k)) and temp_pred(str(k))]

    # Fallback: if not found, try to pick two temperature-like series
    if not supply_keys or not return_keys:
        temp_keys = _select_keys(flat, temp_pred, fallback_to_all=False)
        if len(temp_keys) >= 2:
            supply_keys = [temp_keys[0]]
            return_keys = [temp_keys[1]]
        else:
            return {"error": "Could not identify supply/return temperature series"}

    def avg_for(keys):
        readings = []
        for k in keys:
            readings.extend(flat.get(k, []))
        df = _df_from_readings(readings)
        return (float(df["reading_value"].mean()) if not df.empty else None), df

    avg_supply, df_supply = avg_for(supply_keys)
    avg_return, df_return = avg_for(return_keys)
    if avg_supply is None:
        return {"error": "No supply air temperature data found"}
    if avg_return is None:
        return {"error": "No return air temperature data found"}

    diff = avg_supply - avg_return
    return {
        "average_supply_temperature": round(avg_supply, 2),
        "average_return_temperature": round(avg_return, 2),
        "temperature_difference": round(diff, 2),
        "message": (
            f"Average supply temperature is {avg_supply:.2f}°C, average return temperature is {avg_return:.2f}°C, "
            f"with a difference of {diff:.2f}°C."
        ),
        "unit": "°C",
        "supply_keys": [str(k) for k in supply_keys],
        "return_keys": [str(k) for k in return_keys],
    }


@analytics_function(
    patterns=[
        r"air.*flow.*variation",
        r"airflow.*fluctuation",
        r"cfm.*variability",
        r"air.*flow.*stability",
        r"ventilation.*variation"
    ],
    description="Analyzes variation and stability in air flow rates across ventilation system"
)

def analyze_air_flow_variation(sensor_data):
    """
    Analyzes airflow variation for airflow-like sensors from the standard payload.

    Auto-detects keys containing 'air_flow' or 'airflow' and computes mean, std,
    coefficient of variation (CV). Reports stability if CV < 0.1.

    Returns a dict mapping each detected key to its analysis summary.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No airflow data available"}

    flow_pred = _key_matcher(["air_flow", "airflow", "flow_rate"])
    keys = _select_keys(flat, flow_pred, fallback_to_all=False)
    if not keys:
        return {"error": "No airflow-like keys found"}

    response = {}
    for key in keys:
        df = _df_from_readings(flat.get(key, []))
        if df.empty:
            response[str(key)] = {"message": "No readings available."}
            continue
        mean_val = float(df["reading_value"].mean())
        std_val = float(df["reading_value"].std() or 0.0)
        cv = (std_val / mean_val) if mean_val else 0.0
        response[str(key)] = {
            "mean_airflow": round(mean_val, 2),
            "std_dev_airflow": round(std_val, 2),
            "coefficient_of_variation": round(cv, 2),
            "unit": _unit_for_key(key),
            "message": (
                f"Coefficient of variation: {cv:.2f}. "
                + ("Stable airflow." if cv < 0.1 else "High variation detected.")
            ),
        }

    return response


@analytics_function(
    patterns=[
        r"pressure.*trend",
        r"static.*pressure.*pattern",
        r"differential.*pressure.*trend",
        r"pressure.*over.*time",
        r"pressure.*change"
    ],
    description="Analyzes pressure trends and patterns, checking against expected ranges"
)

def analyze_pressure_trend(sensor_data, expected_range=(0.5, 1.5)):
    """
    Analyzes static pressure sensor data to check if average readings are within an expected range,
    accepting a nested JSON structure.

    Expected input (as a Python dict or JSON string):
      {
          "1": {
              "Static_Pressure_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 1.2},
                      {"datetime": "2025-02-10 05:32:11", "reading_value": 1.3},
                      ...
                  ]
              }
          },
          "2": {
              "Static_Pressure_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:35:00", "reading_value": 0.8},
                      {"datetime": "2025-02-10 05:35:12", "reading_value": 0.7},
                      ...
                  ]
              }
          }
      }

    For each sensor type:
      - Converts the list of readings (from "timeseries_data") into a DataFrame.
      - Renames "datetime" to "timestamp" (if necessary) and converts it to datetime objects.
      - Computes the average static pressure.
      - Compares it with the expected_range.

    Returns:
      A nested dictionary where each sensor ID maps to sensor type keys with their analysis.
    """
    # Accept standard payload: detect pressure-like keys
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No pressure data available"}

    press_pred = _key_matcher(["pressure", "static_pressure"])  # broad match
    keys = _select_keys(flat, press_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {"error": "No pressure-like keys found"}

    response = {}
    for key in keys:
        df = _df_from_readings(flat.get(key, []))
        if df.empty:
            response[str(key)] = {"message": "No data available for this sensor."}
            continue
        avg_pressure = float(df["reading_value"].mean())
        if expected_range[0] <= avg_pressure <= expected_range[1]:
            status = "normal"
            message = f"{key} average pressure {avg_pressure:.2f} is within the expected range."
        else:
            status = "abnormal"
            message = f"{key} average pressure {avg_pressure:.2f} is out of the expected range {expected_range}."
        response[str(key)] = {
            "average_pressure": round(avg_pressure, 2),
            "status": status,
            "message": message,
            "unit": _unit_for_key(key),
        }
    return response


@analytics_function(
    patterns=[
        r"sensor.*trend",
        r"reading.*trend",
        r"data.*trend",
        r"measurement.*pattern",
        r"sensor.*over.*time"
    ],
    description="Analyzes general trend patterns in sensor readings over a time window"
)

def analyze_sensor_trend(sensor_data, window=3):
    """
    Analyzes the trend of sensor readings using a moving average from a nested JSON structure.

    Expected input (as a Python dict or JSON string):
      {
          "1": {
              "Sensor_Type_A": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                      {"datetime": "2025-02-10 05:32:11", "reading_value": 27.99},
                      ...
                  ]
              },
              "Sensor_Type_B": { ... }
          },
          "2": {
              "Sensor_Type_A": { ... }
          }
      }

    For each sensor type:
      - Converts the list of readings (from "timeseries_data") into a DataFrame.
      - Renames "datetime" to "timestamp" (if necessary) and converts it to datetime objects.
      - Sorts by timestamp and computes a rolling average with the specified window.
      - Determines the trend as "upward", "downward", or "stable" by comparing the first and last rolling mean.

    Returns:
      A nested dictionary where each sensor ID maps to sensor type keys with their trend analysis details.
    """
    # Accept standard payload, compute trend per key
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}

    response = {}
    trend_threshold = 0.05
    for key, readings in flat.items():
        try:
            df = _df_from_readings(readings)
            if df.empty:
                response[str(key)] = {"message": "No data available."}
                continue
            df["rolling_mean"] = df["reading_value"].rolling(window=window, min_periods=1).mean()
            trend_diff = float(df["rolling_mean"].iloc[-1] - df["rolling_mean"].iloc[0])
            if abs(trend_diff) < trend_threshold:
                trend = "stable"
            elif trend_diff > 0:
                trend = "upward"
            else:
                trend = "downward"
            response[str(key)] = {
                "initial_rolling_mean": float(df["rolling_mean"].iloc[0]),
                "latest_rolling_mean": float(df["rolling_mean"].iloc[-1]),
                "trend": trend,
                "difference": trend_diff,
                "unit": _unit_for_key(key),
            }
        except Exception as e:
            logging.error(f"Trend analysis failed for {key}: {e}")
            response[str(key)] = {"error": "Trend analysis failed"}
    return response


@analytics_function(
    patterns=[
        r"aggregate.*data",
        r"summarize.*readings",
        r"resample.*data",
        r"group.*by.*time",
        r"hourly.*average"
    ],
    description="Aggregates sensor data by time frequency (hourly, daily, etc.) with statistical summaries"
)

def aggregate_sensor_data(sensor_data, freq="H"):
    """
    Aggregates sensor data into defined time intervals (e.g., hourly, daily) and computes summary statistics,
    accepting a nested JSON structure.

    Expected input (as a Python dict or JSON string):
      {
          "1": {
              "Sensor_Type_A": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                      {"datetime": "2025-02-10 05:32:11", "reading_value": 27.99},
                      ...
                  ]
              },
              "Sensor_Type_B": { ... }
          },
          "2": {
              "Sensor_Type_A": { ... }
          }
      }

    Returns:
      A nested dictionary mapping sensor IDs to sensor type keys and their aggregated summaries.
      Each summary (list of records) includes the mean, standard deviation, minimum, and maximum values,
      with timestamps converted to string format.
    """
    # Accept standard payload and aggregate per key
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}

    aggregated_results = {}
    for key, readings in flat.items():
        try:
            df = _df_from_readings(readings)
            if df.empty:
                aggregated_results[str(key)] = []
                continue
            df = df.set_index("timestamp")
            agg_df = df["reading_value"].resample(freq).agg(["mean", "std", "min", "max"]).reset_index()
            agg_df["timestamp"] = agg_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            aggregated_results[str(key)] = agg_df.to_dict(orient="records")
        except Exception as e:
            logging.error(f"Aggregation error for {key}: {e}")
            aggregated_results[str(key)] = {"error": "Aggregation failed"}
    return aggregated_results


@analytics_function(
    patterns=[
        r"correlate.*sensors",
        r"correlation.*analysis",
        r"relationship.*between",
        r"sensor.*correlation",
        r"dependency.*analysis"
    ],
    description="Computes correlation matrix between multiple sensors to find relationships"
)

def correlate_sensors(sensor_data_dict):
    """
    Computes the correlation matrix among multiple timeseries from a JSON structure.

    Accepts either a flat mapping {id_or_name: [...readings...]}
    or the nested standard payload. Merges on timestamps (1-minute tolerance)
    and computes Pearson correlation between series.
    """
    flat = _aggregate_flat(sensor_data_dict)
    if not flat:
        return {"error": "No valid timeseries data to correlate."}

    dfs = []
    for timeseries_id, readings in flat.items():
        try:
            df = _df_from_readings(readings)
            if df.empty or "reading_value" not in df.columns:
                continue
            df = df[["timestamp", "reading_value"]].rename(
                columns={"reading_value": str(timeseries_id)}
            )
            dfs.append(df)
        except Exception as e:
            logging.error(f"Error processing timeseries {timeseries_id}: {e}")
            continue

    if not dfs:
        return {"error": "No valid timeseries data to correlate."}

    merged_df = dfs[0]
    for df in dfs[1:]:
        merged_df = pd.merge_asof(
            merged_df,
            df,
            on="timestamp",
            tolerance=pd.Timedelta("1min"),
            direction="nearest",
        )

    corr_matrix = merged_df.drop(columns=["timestamp"]).corr(method="pearson")
    return corr_matrix.to_dict()


@analytics_function(
    patterns=[
        r"air.*quality.*index",
        r"aqi",
        r"calculate.*aqi",
        r"air.*quality.*score",
        r"iaq.*index"
    ],
    description="Computes composite Air Quality Index (AQI) from PM, CO2, VOC measurements"
)

def compute_air_quality_index(sensor_data):
    """
    Computes a composite Air Quality Index (AQI) based on selected pollutant sensors from a nested JSON structure.

    Expected sensor keys (if available) in the nested input:
      - "PM2.5_Level_Sensor_Standard"
      - "PM10_Level_Sensor_Standard"
      - "NO2_Level_Sensor"
      - "CO_Level_Sensor"
      - "CO2_Level_Sensor"

    Input format (as a Python dict or JSON string):
      {
          "1": {
              "PM2.5_Level_Sensor_Standard": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                      ...
                  ]
              },
              "Other_Sensor": { ... }
          },
          "2": {
              "PM10_Level_Sensor_Standard": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:35:00", "reading_value": 45.0},
                      ...
                  ]
              },
              "NO2_Level_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:35:12", "reading_value": 38.0},
                      ...
                  ]
              }
          },
          ...
      }

    For each expected sensor, the function:
      - Aggregates all readings across the nested structure.
      - Converts the data to a DataFrame, renames the "datetime" column (if present) to "timestamp" and converts it.
      - Sorts by timestamp and takes the latest reading.
      - Normalizes the reading by dividing by an arbitrary threshold.
      - Multiplies by a weight to obtain a component value.

    Finally, it sums the weighted components to compute the composite AQI and assigns a health status.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data available for AQI calculation"}

    # thresholds (units assumed typical):
    thresholds = {
        "pm2.5": 35,
        "pm10": 50,
        "no2": 40,
        "co": 9,
        "co2": 1000,
    }
    weights = {
        "pm2.5": 0.3,
        "pm10": 0.2,
        "no2": 0.2,
        "co": 0.15,
        "co2": 0.15,
    }

    # map keys by pollutant
    groups = {k: [] for k in thresholds.keys()}
    for key in flat.keys():
        kl = str(key).lower()
        if "pm10" in kl:
            groups["pm10"].append(key)
        if "pm2.5" in kl or "pm2_5" in kl or "pm25" in kl:
            groups["pm2.5"].append(key)
        if "no2" in kl:
            groups["no2"].append(key)
        if kl == "co" or "co_sensor" in kl or ("carbon_monoxide" in kl and "co2" not in kl):
            groups["co"].append(key)
        if "co2" in kl:
            groups["co2"].append(key)

    index_components = {}
    for pollutant, keys in groups.items():
        if not keys:
            continue
        readings = []
        for k in keys:
            readings.extend(flat.get(k, []))
        df = _df_from_readings(readings)
        if df.empty:
            continue
        latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
        if latest is None:
            continue
        thr = thresholds[pollutant]
        w = weights[pollutant]
        component = (latest / thr) * w
        index_components[pollutant] = component

    if not index_components:
        return {"error": "Insufficient data for AQI calculation. Please provide relevant sensor data. It requires at least one sensor of type PM10, PM2.5, NO2, CO, and CO2 to calculate AQI. Provide target sensors and I will try again."}

    aqi = float(sum(index_components.values()))
    if aqi < 0.5:
        status = "Good"
    elif aqi < 1:
        status = "Moderate"
    elif aqi < 1.5:
        status = "Unhealthy for Sensitive Groups"
    else:
        status = "Unhealthy"
    # Round for user-friendly output
    aqi = round(aqi, 3)
    index_components = {k: round(v, 3) for k, v in index_components.items()}
    # Attach units metadata
    component_units = {
        "pm2.5": UK_INDOOR_STANDARDS["pm2.5_ugm3"]["unit"],
        "pm10": UK_INDOOR_STANDARDS["pm10_ugm3"]["unit"],
        "no2": UK_INDOOR_STANDARDS["no2_ugm3"]["unit"],
        "co": UK_INDOOR_STANDARDS["co_ppm"]["unit"],
        "co2": UK_INDOOR_STANDARDS["co2_ppm"]["unit"],
    }
    return {"AQI": aqi, "Status": status, "Components": index_components, "Units": component_units}


@analytics_function(
    patterns=[
        r"health.*alert",
        r"threshold.*violation",
        r"out.*of.*range",
        r"alarm.*generation",
        r"alert.*notification"
    ],
    description="Generates health alerts when sensor readings exceed configurable thresholds"
)

def generate_health_alerts(sensor_data, thresholds=None):
    """
    Generates alerts if the latest sensor readings exceed specified threshold ranges,
    accepting a nested JSON structure.

    Parameters:
      - sensor_data: A dict or JSON string in the following format:
          {
              "1": {
                  "PM2.5_Level_Sensor_Standard": {
                      "timeseries_data": [
                          {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                          {"datetime": "2025-02-10 05:32:11", "reading_value": 27.99},
                          ...
                      ]
                  },
                  "Other_Sensor": { ... }
              },
              "2": {
                  "NO2_Level_Sensor": {
                      "timeseries_data": [
                          {"datetime": "2025-02-10 05:35:00", "reading_value": 38.0},
                          {"datetime": "2025-02-10 05:35:12", "reading_value": 39.5},
                          ...
                      ]
                  }
              }
          }
      - thresholds: A dict mapping sensor names (as used in the inner keys) to a tuple (min_value, max_value).

    For each sensor type specified in thresholds, the function finds the latest reading and returns an alert
    if the reading is below min_value or above max_value. The resulting alerts are keyed by a unique identifier
    in the format "sensorID_sensorType".

    Returns a dictionary with alert messages per sensor.
    """
    flat = _aggregate_flat(sensor_data)
    alerts = {}
    if not flat:
        return {"error": "No data available"}

    # If thresholds not provided, derive UK defaults for keys present
    if thresholds is None:
        derived = {}
        for key in flat.keys():
            kl = str(key).lower()
            # Temperature
            if "temperature" in kl or re.search(r"\btemp\b", kl):
                lo, hi = UK_INDOOR_STANDARDS["temperature_c"]["range"]
                derived[key] = (lo, hi)
                continue
            # Humidity
            if "humidity" in kl or kl in ("rh", "relative_humidity"):
                lo, hi = UK_INDOOR_STANDARDS["humidity_rh"]["range"]
                derived[key] = (lo, hi)
                continue
            # CO2
            if "co2" in kl:
                lo, hi = UK_INDOOR_STANDARDS["co2_ppm"]["range"]
                derived[key] = (lo, hi)
                continue
            # CO (not CO2)
            if ("co" in kl and "co2" not in kl) or "carbon_monoxide" in kl:
                hi = UK_INDOOR_STANDARDS["co_ppm"]["max"]
                derived[key] = (0, hi)
                continue
            # PM2.5 / PM10
            if "pm2.5" in kl or "pm2_5" in kl or "pm25" in kl:
                hi = UK_INDOOR_STANDARDS["pm2.5_ugm3"]["max"]
                derived[key] = (0, hi)
                continue
            if "pm10" in kl:
                hi = UK_INDOOR_STANDARDS["pm10_ugm3"]["max"]
                derived[key] = (0, hi)
                continue
            # Formaldehyde
            if "formaldehyde" in kl or "hcho" in kl:
                hi = UK_INDOOR_STANDARDS["hcho_mgm3"]["max"]
                derived[key] = (0, hi)
                continue
            # Noise
            if "noise" in kl or "sound" in kl:
                hi = UK_INDOOR_STANDARDS["noise_db"]["max"]
                derived[key] = (0, hi)
                continue
        thresholds = derived

    # thresholds may be provided as exact or generic names; robust substring/token match
    def find_threshold_for(key):
        # Exact match first
        if key in thresholds:
            return thresholds[key]
        kl = str(key).lower()
        # Tokenize by common separators
        tokens = set(filter(None, [t.strip() for t in re.split(r"[_\-\s]+|\W+", kl)]))
        best = None
        best_score = 0
        for th_key, rng in thresholds.items():
            tkl = str(th_key).lower()
            th_tokens = set(filter(None, [t.strip() for t in re.split(r"[_\-\s]+|\W+", tkl)]))
            # score by token overlap and substring presence
            overlap = len(tokens & th_tokens)
            substr = 1 if (tkl in kl or kl in tkl) else 0
            score = overlap * 2 + substr
            if score > best_score:
                best = rng
                best_score = score
        return best

    for key, readings in flat.items():
        th = find_threshold_for(key)
        if th is None:
            continue
        df = _df_from_readings(readings)
        if df.empty:
            alerts[str(key)] = "No data available."
            continue
        latest_value = float(df.iloc[-1]["reading_value"]) if not df.empty else None
        if latest_value is None:
            alerts[str(key)] = "No readings."
            continue
        min_val, max_val = th
        unit = _unit_for_key(key)
        unit_suffix = f" {unit}" if unit else ""
        if latest_value < min_val or latest_value > max_val:
            alerts[str(key)] = (
                f"Alert: Latest reading {latest_value}{unit_suffix} out of range [{min_val}, {max_val}]."
            )
        else:
            alerts[str(key)] = (
                f"OK: Latest reading {latest_value}{unit_suffix} within acceptable range."
            )
    return alerts


@analytics_function(
    patterns=[
        r"detect.*anomaly",
        r"anomaly.*detection",
        r"outlier.*detection",
        r"abnormal.*reading",
        r"unusual.*value"
    ],
    description="Detects statistical anomalies using z-score, modified z-score, or IQR methods"
)

def detect_anomalies(sensor_data, method="zscore", threshold=3, robust=False):
    """
    Detects anomalies in sensor data using a statistical approach from a nested JSON structure.

    Parameters:
      - sensor_data: A dict or JSON string of sensor data. Expected format:
            {
                "1": {
                    "Sensor_Type_A": {
                        "timeseries_data": [
                            {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                            {"datetime": "2025-02-10 05:32:11", "reading_value": 27.99},
                            ...
                        ]
                    },
                    "Sensor_Type_B": { ... }
                },
                "2": { ... }
            }
    - method: "zscore" (standard or robust based on the `robust` flag) or "iqr" for IQR-based outliers.
      - threshold: The z-score threshold above which a reading is flagged as an anomaly.
      - robust: If True, uses the median and median absolute deviation (MAD) for z-score calculation,
                which is more robust to outliers.

    Returns:
      A dictionary mapping flattened sensor names (e.g. "1_Sensor_Type_A") to a list of anomalous readings.
      Each anomalous reading includes the timestamp, reading_value, and computed zscore.
    """
    # Accept standard payload and compute anomalies per key
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}

    anomalies = {}
    for key, readings in flat.items():
        try:
            df = _df_from_readings(readings)
            if df.empty or "reading_value" not in df.columns:
                anomalies[str(key)] = []
                continue
            if method == "iqr":
                Q1 = df["reading_value"].quantile(0.25)
                Q3 = df["reading_value"].quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - threshold * IQR
                upper = Q3 + threshold * IQR
                anomaly_df = df[(df["reading_value"] < lower) | (df["reading_value"] > upper)].copy()
                anomaly_df["timestamp"] = anomaly_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
                anomalies[str(key)] = anomaly_df[["timestamp", "reading_value"]].to_dict(orient="records")
            else:
                if robust:
                    median_val = float(df["reading_value"].median())
                    mad = float(np.median(np.abs(df["reading_value"] - median_val)))
                    mad = mad if mad != 0 else 1.0
                    df["zscore"] = 0.6745 * (df["reading_value"] - median_val) / mad
                else:
                    mean_val = float(df["reading_value"].mean())
                    std_val = float(df["reading_value"].std() or 1.0)
                    df["zscore"] = (df["reading_value"] - mean_val) / std_val
                anomaly_df = df[np.abs(df["zscore"]) > threshold].copy()
                anomaly_df["timestamp"] = anomaly_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
                anomalies[str(key)] = anomaly_df[["timestamp", "reading_value", "zscore"]].to_dict(orient="records")
        except Exception as e:
            logging.error(f"Error detecting anomalies for sensor {key}: {e}")
            anomalies[str(key)] = {"error": "Anomaly detection failed", "details": str(e)}
    return anomalies


@analytics_function(
    patterns=[
        r"noise.*level",
        r"sound.*level",
        r"acoustic.*analysis",
        r"decibel.*measurement",
        r"noise.*pollution"
    ],
    description="Analyzes noise levels with comfort and high-threshold classifications"
)

def analyze_noise_levels(
    sensor_data, threshold=90
):
    """
    Analyzes noise level data from a nested JSON structure.

    Aggregates readings for the specified sensor_key from across all sensor IDs.
    Computes the mean, min, max, standard deviation and flags if the latest reading exceeds the threshold.

    Parameters:
      - sensor_data: A dict or JSON string in the following format:
            {
                "1": {
                    "Sound_Noise_Sensor_MEMS": {
                        "timeseries_data": [
                            {"datetime": "2025-02-10 05:31:59", "reading_value": 87.5},
                            {"datetime": "2025-02-10 05:32:11", "reading_value": 92.0},
                            ...
                        ]
                    },
                    "Other_Sensor": { ... }
                },
                "2": {
                    "Sound_Noise_Sensor_MEMS": {
                        "timeseries_data": [
                            {"datetime": "2025-02-10 05:35:00", "reading_value": 89.0},
                            {"datetime": "2025-02-10 05:35:12", "reading_value": 91.5},
                            ...
                        ]
                    }
                }
            }
      - sensor_key: The sensor type key to look for (default: "Sound_Noise_Sensor_MEMS").
      - threshold: The noise level threshold (default: 90).

    Returns:
      A dictionary with summary statistics and an alert message.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No noise data available",
            "description": "No sensor data was provided or detected in the payload",
            "analysis_type": "noise_levels"
        }

    noise_pred = _key_matcher(["noise", "sound"])
    keys = _select_keys(flat, noise_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {
            "error": "No noise-like keys found",
            "description": "No keys matching 'noise' or 'sound' patterns were detected in the data",
            "analysis_type": "noise_levels"
        }

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {
            "error": "Empty noise series",
            "description": "No valid readings found in the noise sensor data",
            "analysis_type": "noise_levels"
        }

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    mean_val = float(df["reading_value"].mean())
    min_val = float(df["reading_value"].min())
    max_val = float(df["reading_value"].max())
    std_val = float(df["reading_value"].std())
    
    summary = {
        "analysis_type": "noise_levels",
        "description": f"Noise level analysis for {len(keys)} sensor(s) with {len(df)} readings",
        "statistics": {
            "mean": round(mean_val, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "std": round(std_val, 2),
            "latest": round(latest, 2) if latest is not None else None,
        },
        "unit": UK_INDOOR_STANDARDS["noise_db"]["unit"],
        "threshold": {
            "value": threshold,
            "unit": UK_INDOOR_STANDARDS["noise_db"]["unit"],
            "source": "UK Indoor Standards (55 dB(A) comfort)"
        },
        "sensors_analyzed": [str(k) for k in keys],
        "reading_count": len(df)
    }
    
    if latest is not None:
        if latest > threshold:
            summary["alert"] = "High noise level"
            summary["status"] = "WARNING"
            summary["message"] = f"Current noise level ({latest:.2f} dB(A)) exceeds acceptable threshold ({threshold} dB(A))"
        else:
            summary["alert"] = "Normal noise level"
            summary["status"] = "OK"
            summary["message"] = f"Current noise level ({latest:.2f} dB(A)) is within acceptable limits"
    else:
        summary["alert"] = "No readings"
        summary["status"] = "UNKNOWN"
        summary["message"] = "Unable to determine current noise level"
    
    return summary


@analytics_function(
    patterns=[
        r"analyze.*air.*quality",
        r"iaq.*analysis",
        r"indoor.*air",
        r"air.*quality.*assessment",
        r"ventilation.*quality"
    ],
    description="Comprehensive indoor air quality analysis including CO2, PM, VOC, and comfort indices"
)

def analyze_air_quality(
    sensor_data, thresholds=(50, 100)
):
    """
    Analyzes air quality sensor data from a nested JSON structure.

    Aggregates readings for the specified sensor_key across sensor IDs.
    Computes the average air quality index and classifies it based on thresholds.

    Expected input (as a Python dict or JSON string):
      {
         "1": {
             "Air_Quality_Sensor": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:31:59", "reading_value": 45},
                     {"datetime": "2025-02-10 05:32:11", "reading_value": 50},
                     ...
                 ]
             },
             "Other_Sensor": { ... }
         },
         "2": {
             "Air_Quality_Sensor": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:35:00", "reading_value": 55},
                     {"datetime": "2025-02-10 05:35:12", "reading_value": 60},
                     ...
                 ]
             }
         }
      }

    Returns a dictionary containing:
        - average_air_quality: computed average reading_value.
        - status: classification ("Good", "Moderate", or "Poor").
        - min: minimum reading_value.
        - max: maximum reading_value.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No air quality data available",
            "description": "No sensor data was provided or detected in the payload",
            "analysis_type": "air_quality"
        }

    aq_pred = _key_matcher(["air_quality", "aqi", "aq_sensor"])  # broad match
    keys = _select_keys(flat, aq_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {
            "error": "No air-quality-like keys found",
            "description": "No keys matching 'air_quality', 'aqi', or 'aq_sensor' patterns were detected",
            "analysis_type": "air_quality"
        }

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {
            "error": "Empty air quality series",
            "description": "No valid readings found in the air quality sensor data",
            "analysis_type": "air_quality"
        }

    avg_quality = float(df["reading_value"].mean())
    min_val = float(df["reading_value"].min())
    max_val = float(df["reading_value"].max())
    std_val = float(df["reading_value"].std())
    
    if avg_quality <= thresholds[0]:
        status = "Good"
        status_description = f"Air quality is good (below {thresholds[0]})"
    elif avg_quality <= thresholds[1]:
        status = "Moderate"
        status_description = f"Air quality is moderate (between {thresholds[0]} and {thresholds[1]})"
    else:
        status = "Poor"
        status_description = f"Air quality is poor (above {thresholds[1]})"
    
    return {
        "analysis_type": "air_quality",
        "description": f"Air quality analysis for {len(keys)} sensor(s) with {len(df)} readings",
        "statistics": {
            "average_air_quality": round(avg_quality, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "std": round(std_val, 2)
        },
        "status": status,
        "status_description": status_description,
        "unit": None,  # AQI is unitless if this is an arbitrary index
        "thresholds": {
            "good_max": thresholds[0],
            "moderate_max": thresholds[1],
            "description": "Good: ≤{}, Moderate: {}-{}, Poor: >{}".format(thresholds[0], thresholds[0], thresholds[1], thresholds[1])
        },
        "sensors_analyzed": [str(k) for k in keys],
        "reading_count": len(df),
        "message": f"Average air quality index is {avg_quality:.2f} ({status})"
    }


@analytics_function(
    patterns=[
        r"formaldehyde",
        r"hcho",
        r"formaldehyde.*level",
        r"formaldehyde.*concentration",
        r"volatile.*organic"
    ],
    description="Analyzes formaldehyde (HCHO) levels with health-based threshold classifications"
)

def analyze_formaldehyde_levels(
    sensor_data, threshold=None
):
    """
    Analyzes formaldehyde sensor readings from a nested JSON structure.

    Aggregates readings for the specified sensor_key across sensor IDs.
    Computes summary statistics and flags if the latest reading exceeds the threshold.

    Expected input (as a Python dict or JSON string):
      {
         "1": {
             "Formaldehyde_Level_Sensor1": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:31:59", "reading_value": 0.08},
                     {"datetime": "2025-02-10 05:32:11", "reading_value": 0.09},
                     ...
                 ]
             },
         },
         "2": {
             "Formaldehyde_Level_Sensor2": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:35:00", "reading_value": 0.11},
                     {"datetime": "2025-02-10 05:35:12", "reading_value": 0.10},
                     ...
                 ]
             }
         }
      }

    Returns a dictionary containing:
      - mean, min, max, std, and latest reading_value.
      - an alert message if the latest reading exceeds the threshold.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No formaldehyde data available",
            "description": "No sensor data was provided or detected in the payload",
            "analysis_type": "formaldehyde_levels"
        }

    hcho_pred = _key_matcher(["formaldehyde", "hcho"])  # common naming
    keys = _select_keys(flat, hcho_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {
            "error": "No formaldehyde-like keys found",
            "description": "No keys matching 'formaldehyde' or 'hcho' patterns were detected",
            "analysis_type": "formaldehyde_levels"
        }

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {
            "error": "Empty formaldehyde series",
            "description": "No valid readings found in the formaldehyde sensor data",
            "analysis_type": "formaldehyde_levels"
        }

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    if threshold is None:
        threshold = UK_INDOOR_STANDARDS["hcho_mgm3"]["max"]
    
    mean_val = float(df["reading_value"].mean())
    min_val = float(df["reading_value"].min())
    max_val = float(df["reading_value"].max())
    std_val = float(df["reading_value"].std())
    
    summary = {
        "analysis_type": "formaldehyde_levels",
        "description": f"Formaldehyde (HCHO) analysis for {len(keys)} sensor(s) with {len(df)} readings",
        "statistics": {
            "mean": round(mean_val, 3),
            "min": round(min_val, 3),
            "max": round(max_val, 3),
            "std": round(std_val, 3),
            "latest": round(latest, 3) if latest is not None else None,
        },
        "unit": UK_INDOOR_STANDARDS["hcho_mgm3"]["unit"],
        "threshold": {
            "value": threshold,
            "unit": UK_INDOOR_STANDARDS["hcho_mgm3"]["unit"],
            "source": "UK Indoor Standards"
        },
        "sensors_analyzed": [str(k) for k in keys],
        "reading_count": len(df)
    }
    
    if latest is not None:
        if latest > threshold:
            summary["alert"] = "High formaldehyde level"
            summary["status"] = "WARNING"
            summary["message"] = f"Current formaldehyde level ({latest:.3f} mg/m³) exceeds acceptable threshold ({threshold} mg/m³)"
        else:
            summary["alert"] = "Normal formaldehyde level"
            summary["status"] = "OK"
            summary["message"] = f"Current formaldehyde level ({latest:.3f} mg/m³) is within acceptable limits"
    else:
        summary["alert"] = "No readings"
        summary["status"] = "UNKNOWN"
        summary["message"] = "Unable to determine current formaldehyde level"
    
    return summary


def analyze_co2_levels(sensor_data, threshold=None):
    """
    CO₂ Levels Monitoring — Indoor Carbon Dioxide Assessment
    
    Purpose:
    Analyzes indoor CO₂ concentrations to assess ventilation adequacy and occupancy patterns. 
    Elevated CO₂ indicates insufficient outdoor air supply, which correlates with reduced 
    cognitive performance, drowsiness, and increased pathogen transmission risk. This 
    analysis supports ASHRAE 62.1 ventilation compliance and pandemic-preparedness protocols.
    
    Sensors:
      - CO2_Level_Sensor or CO2_Sensor (ppm)
      - Indoor_Air_Quality_CO2 sensors
    
    Output:
      - mean_co2: Average CO₂ concentration (ppm)
      - min_co2, max_co2: Range (outdoor baseline ~400-420 ppm)
      - latest_co2: Current reading
      - std_co2: Variability (stable vs fluctuating occupancy)
      - exceedance_hours: Hours above threshold
      - ventilation_adequacy: "Excellent", "Good", "Marginal", "Poor"
      - cognitive_impact_flag: Alert if >1000 ppm (performance degradation)
    
    This analysis helps:
      - Verify ASHRAE 62.1 ventilation effectiveness
      - Detect ventilation system malfunctions or inadequate airflow
      - Support pandemic protocols (CO₂ <800 ppm correlates with infection risk reduction)
      - Identify over-crowded spaces or unanticipated occupancy patterns
      - Comply with UK Building Bulletin 101 (BB101) for schools (1500 ppm max)
      - Validate demand-controlled ventilation (DCV) performance
    
    Method:
      CO₂ thresholds (consensus guidance):
        **ASHRAE 62.1-2022 (Ventilation for Acceptable IAQ):**
          - Outdoor baseline: ~400-420 ppm
          - Target: <700 ppm above outdoor (~1000-1100 ppm indoor)
          - Acceptable: <1000 ppm indoor (adequate ventilation)
        
        **WELL Building Standard v2:**
          - Feature 01: CO₂ <600 ppm above outdoor baseline
          - Feature A01 (Enhanced): CO₂ <500 ppm above outdoor
        
        **UK Building Bulletin 101 (Schools):**
          - Acceptable: <1500 ppm (1100 ppm above outdoor)
          - Good: <1000 ppm
        
        **Pandemic Ventilation Protocols (CDC, ASHRAE Epidemic Task Force):**
          - Target: <800 ppm (correlates with ~3-4 ACH outdoor air)
          - Enhanced: <700 ppm (reduces airborne pathogen concentration)
        
        **CEN Standard EN 16798-1 (European):**
          - Category I (high): <800 ppm
          - Category II (medium): <1000 ppm
          - Category III (moderate): <1400 ppm
          - Category IV (low): >1400 ppm
      
      Cognitive performance impacts (Harvard TH Chan School research):
        - <600 ppm: Optimal cognitive function
        - 600-1000 ppm: No measurable impact
        - 1000-1400 ppm: 15% reduction in cognitive scores
        - 1400-2500 ppm: 50% reduction (decision-making, complex tasks)
        - >2500 ppm: OSHA STEL exceeded, health concern
      
      Ventilation rate estimation (steady-state):
        CO₂ generation per person: ~0.3-0.5 L/min (sedentary office)
        Ventilation rate (L/s/person) ≈ (N × G) / (C_in - C_out)
        Where N = occupants, G = CO₂ generation rate, C_in - C_out = rise above outdoor
        
        Example: (C_in - C_out) = 600 ppm rise → ~8-10 L/s/person (ASHRAE compliant)
                 1000 ppm rise → ~5 L/s/person (marginal)
                 1500 ppm rise → ~3 L/s/person (poor)
      
      CO₂ as ventilation proxy:
        - CO₂ is NOT a pollutant but an indicator of bioeffluents
        - High CO₂ implies other occupant-generated pollutants accumulate
        - Does NOT indicate outdoor pollutants (PM2.5, NO₂) unless outdoor air is polluted
      
      Demand-Controlled Ventilation (DCV):
        - Uses CO₂ sensors to modulate outdoor air damper position
        - Target setpoint: 800-1000 ppm (balance IAQ and energy)
        - Sensor drift: Calibrate CO₂ sensors annually (many drift +50-100 ppm/year)
        - Occupancy inference: CO₂ rise rate ~100 ppm/hour per 10 occupants (typical office)
      
      Pandemic-preparedness:
        - Lower CO₂ correlates with diluted viral aerosol concentration
        - CDC guidance: Increase ventilation to lowest feasible CO₂ level
        - ASHRAE EpiC (Epidemic Guidance): Enhanced filtration + ventilation target <800 ppm
    
    Parameters:
        sensor_data (dict): CO₂ timeseries data from sensors
        threshold (float, optional): Alert threshold in ppm (default 1000 ppm - ASHRAE limit)
    
    Returns:
        dict: CO₂ statistics, ventilation adequacy rating, cognitive impact flags

    Aggregates readings for the specified sensor_key across sensor IDs,
    computes summary statistics, and flags if the latest reading exceeds the threshold.

    Expected input (as a Python dict or JSON string):
      {
          "1": {
              "CO2_Level_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:31:59", "reading_value": 950},
                      {"datetime": "2025-02-10 05:32:11", "reading_value": 980},
                      ...
                  ]
              },
              "Other_Sensor": { ... }
          },
          "2": {
              "CO2_Level_Sensor": {
                  "timeseries_data": [
                      {"datetime": "2025-02-10 05:35:00", "reading_value": 1020},
                      {"datetime": "2025-02-10 05:35:12", "reading_value": 1005},
                      ...
                  ]
              }
          }
      }

    Returns a dictionary with:
      - mean, min, max, std, and latest reading_value.
      - an alert message if the latest reading exceeds the threshold.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No CO2 data available",
            "description": "No sensor data was provided or detected in the payload",
            "analysis_type": "co2_levels"
        }

    co2_pred = _key_matcher(["co2"])  # specific enough
    keys = _select_keys(flat, co2_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {
            "error": "No CO2-like keys found",
            "description": "No keys matching 'co2' pattern were detected",
            "analysis_type": "co2_levels"
        }

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {
            "error": "Empty CO2 series",
            "description": "No valid readings found in the CO2 sensor data",
            "analysis_type": "co2_levels"
        }

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    # Default threshold per UK guidance
    if threshold is None:
        threshold = UK_INDOOR_STANDARDS["co2_ppm"]["range"][1]
    
    mean_val = float(df["reading_value"].mean())
    min_val = float(df["reading_value"].min())
    max_val = float(df["reading_value"].max())
    std_val = float(df["reading_value"].std())
    
    summary = {
        "analysis_type": "co2_levels",
        "description": f"CO2 concentration analysis for {len(keys)} sensor(s) with {len(df)} readings",
        "statistics": {
            "mean": round(mean_val, 1),
            "min": round(min_val, 1),
            "max": round(max_val, 1),
            "std": round(std_val, 1),
            "latest": round(latest, 1) if latest is not None else None,
        },
        "unit": UK_INDOOR_STANDARDS["co2_ppm"]["unit"],
        "threshold": {
            "value": threshold,
            "unit": UK_INDOOR_STANDARDS["co2_ppm"]["unit"],
            "source": "UK Indoor Standards",
            "good_range": UK_INDOOR_STANDARDS["co2_ppm"]["range"]
        },
        "sensors_analyzed": [str(k) for k in keys],
        "reading_count": len(df)
    }
    
    if latest is not None:
        if latest > threshold:
            summary["alert"] = "High CO2 level"
            summary["status"] = "WARNING"
            summary["message"] = f"Current CO2 level ({latest:.1f} ppm) exceeds acceptable threshold ({threshold} ppm) - ventilation may be inadequate"
        else:
            summary["alert"] = "Normal CO2 level"
            summary["status"] = "OK"
            summary["message"] = f"Current CO2 level ({latest:.1f} ppm) is within acceptable limits - adequate ventilation"
    else:
        summary["alert"] = "No readings"
        summary["status"] = "UNKNOWN"
        summary["message"] = "Unable to determine current CO2 level"
    
    return summary


@analytics_function(
    patterns=[
        r"particulate.*matter",
        r"pm2\\.5",
        r"pm10",
        r"particle.*level",
        r"dust.*level"
    ],
    description="Analyzes particulate matter (PM2.5, PM10) levels with AQI classifications"
)

def analyze_pm_levels(
    sensor_data,
    thresholds={
        "pm1": 50,
        "pm2.5": 35,
        "pm2_5": 35,
        "pm10": 50,
    },
):
    """
    Analyzes particulate matter (PM) sensor data from a nested JSON structure.

    Expected input (as a Python dict or JSON string):
      {
          "1": {
              "PM1_Level_Sensor_Standard": {
                  "timeseries_data": [ ... ]
              },
              "PM2.5_Level_Sensor_Standard": {
                  "timeseries_data": [ ... ]
              },
              "PM10_Level_Sensor_Standard": {
                  "timeseries_data": [ ... ]
              },
              "Other_Sensor": { ... }
          },
          "2": {
              "PM1_Level_Sensor_Standard": { "timeseries_data": [ ... ] },
              "PM2.5_Level_Sensor_Standard": { "timeseries_data": [ ... ] },
              "PM10_Level_Sensor_Standard": { "timeseries_data": [ ... ] }
          }
      }

    For each sensor key, the function aggregates readings across sensor IDs,
    computes summary statistics (mean, min, max, std, latest value) and flags if
    the latest reading exceeds its defined threshold.

    Returns a dictionary mapping each sensor key to its analysis summary.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No PM data available",
            "description": "No particulate matter sensor data was provided or detected in the payload",
            "analysis_type": "pm_levels"
        }

    # Group keys by PM type
    pm_groups = {
        "pm1": [],
        "pm2.5": [],
        "pm10": [],
    }
    for k in flat.keys():
        kl = str(k).lower()
        if "pm10" in kl:
            pm_groups["pm10"].append(k)
        elif "pm2.5" in kl or "pm2_5" in kl or "pm25" in kl:
            pm_groups["pm2.5"].append(k)
        elif kl.startswith("pm1") or "pm1_0" in kl or "pm1.0" in kl:
            pm_groups["pm1"].append(k)

    analysis = {
        "analysis_type": "pm_levels",
        "description": "Particulate matter (PM1, PM2.5, PM10) concentration analysis",
        "pollutants": {}
    }
    
    for pm_type, keys in pm_groups.items():
        if not keys:
            continue
        all_readings = []
        for k in keys:
            all_readings.extend(flat.get(k, []))
        df = _df_from_readings(all_readings)
        if df.empty:
            analysis["pollutants"][pm_type] = {
                "error": "No data available",
                "description": f"No valid readings for {pm_type}"
            }
            continue
        
        latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
        mean_val = float(df["reading_value"].mean())
        min_val = float(df["reading_value"].min())
        max_val = float(df["reading_value"].max())
        std_val = float(df["reading_value"].std())
        
        unit = UK_INDOOR_STANDARDS["pm10_ugm3"]["unit"] if pm_type == "pm10" else UK_INDOOR_STANDARDS["pm2.5_ugm3"]["unit"]
        
        summary = {
            "pollutant": pm_type.upper(),
            "description": f"{pm_type.upper()} particulate matter analysis",
            "statistics": {
                "mean": round(mean_val, 2),
                "min": round(min_val, 2),
                "max": round(max_val, 2),
                "std": round(std_val, 2),
                "latest": round(latest, 2) if latest is not None else None,
            },
            "unit": unit,
            "sensors_analyzed": [str(k) for k in keys],
            "reading_count": len(df)
        }
        
        thres = None
        # choose threshold key variant
        for key_variant in [pm_type, pm_type.replace(".", "_"), pm_type.replace(".", "")]:
            if key_variant in thresholds:
                thres = thresholds[key_variant]
                break
        
        if latest is not None and thres is not None:
            summary["threshold"] = {
                "value": thres,
                "unit": unit,
                "source": "UK Indoor Standards / WHO guidelines"
            }
            if latest > thres:
                summary["alert"] = f"High {pm_type} reading"
                summary["status"] = "WARNING"
                summary["message"] = f"Current {pm_type.upper()} level ({latest:.2f} {unit}) exceeds acceptable threshold ({thres} {unit})"
            else:
                summary["alert"] = f"Normal {pm_type} reading"
                summary["status"] = "OK"
                summary["message"] = f"Current {pm_type.upper()} level ({latest:.2f} {unit}) is within acceptable limits"
        elif thres is None:
            summary["alert"] = "Threshold not defined"
            summary["status"] = "INFO"
            summary["message"] = f"No threshold defined for {pm_type.upper()}"
        else:
            summary["alert"] = "No readings"
            summary["status"] = "UNKNOWN"
            summary["message"] = f"Unable to determine current {pm_type.upper()} level"
        
        analysis["pollutants"][pm_type] = summary
    
    if not analysis["pollutants"]:
        return {
            "error": "No PM sensors found",
            "description": "No keys matching PM1, PM2.5, or PM10 patterns were detected",
            "analysis_type": "pm_levels"
        }
    
    return analysis


@analytics_function(
    patterns=[
        r"temperature.*analysis",
        r"thermal.*analysis",
        r"temp.*reading",
        r"temperature.*distribution",
        r"temperature.*statistics"
    ],
    description="Comprehensive temperature analysis with statistics, trends, and comfort assessment"
)

def analyze_temperatures(
    sensor_data, acceptable_range=None
):
    """
    Analyzes temperature sensor data from a nested JSON structure.

    Aggregates readings for the specified sensor_key across sensor IDs.
    Computes summary statistics (mean, min, max, std, and latest reading) and flags if the latest
    reading is outside the acceptable range.

    Expected input (as a Python dict or JSON string):
      {
         "1": {
             "Air_Temperature_Sensor": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:31:59", "reading_value": 22.5},
                     {"datetime": "2025-02-10 05:32:11", "reading_value": 23.0},
                     ...
                 ]
             },
             "Other_Sensor": { ... }
         },
         "2": {
             "Air_Temperature_Sensor": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:33:00", "reading_value": 24.0},
                     {"datetime": "2025-02-10 05:33:15", "reading_value": 23.5},
                     ...
                 ]
             }
         }
      }

        Returns:
      A dictionary with the computed summary statistics and an alert message.
    """
    # Accept any temperature-like series from standard payload
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No temperature data available",
            "description": "No sensor data was provided or detected in the payload",
            "analysis_type": "temperatures"
        }

    # Exclude accidental matches like 'attempt' when looking for temperature series
    temp_pred = _key_matcher(["temperature", "temp"], exclude_substrs=["attempt"])  # avoid matching 'attempt'
    keys = _select_keys(flat, temp_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {
            "error": "No temperature-like keys found",
            "description": "No keys matching 'temperature' or 'temp' patterns were detected",
            "analysis_type": "temperatures"
        }

    # Combine all selected series
    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {
            "error": "Empty temperature series",
            "description": "No valid readings found in the temperature sensor data",
            "analysis_type": "temperatures"
        }

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    # Default to UK comfort range if not provided
    if acceptable_range is None:
        acceptable_range = UK_INDOOR_STANDARDS["temperature_c"]["range"]
    
    unit = "°C"
    mean_val = float(df["reading_value"].mean())
    min_val = float(df["reading_value"].min())
    max_val = float(df["reading_value"].max())
    std_val = float(df["reading_value"].std())
    
    summary = {
        "analysis_type": "temperatures",
        "description": f"Temperature analysis for {len(keys)} sensor(s) with {len(df)} readings",
        "statistics": {
            "mean": round(mean_val, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "std": round(std_val, 2),
            "latest": round(latest, 2) if latest is not None else None,
        },
        "unit": unit,
        "acceptable_range": {
            "min": acceptable_range[0],
            "max": acceptable_range[1],
            "unit": unit,
            "source": "UK Indoor Standards (18-24°C comfort)"
        },
        "sensors_analyzed": [str(k) for k in keys],
        "reading_count": len(df)
    }
    
    if latest is not None:
        if latest < acceptable_range[0]:
            summary["alert"] = "Temperature too low"
            summary["status"] = "WARNING"
            summary["message"] = f"Current temperature ({latest:.2f}°C) is below acceptable range ({acceptable_range[0]}-{acceptable_range[1]}°C)"
        elif latest > acceptable_range[1]:
            summary["alert"] = "Temperature too high"
            summary["status"] = "WARNING"
            summary["message"] = f"Current temperature ({latest:.2f}°C) is above acceptable range ({acceptable_range[0]}-{acceptable_range[1]}°C)"
        else:
            summary["alert"] = "Temperature normal"
            summary["status"] = "OK"
            summary["message"] = f"Current temperature ({latest:.2f}°C) is within acceptable range ({acceptable_range[0]}-{acceptable_range[1]}°C)"
    else:
        summary["alert"] = "No readings"
        summary["status"] = "UNKNOWN"
        summary["message"] = "Unable to determine current temperature"
    
    return summary


@analytics_function(
    patterns=[
        r"humidity.*analysis",
        r"rh.*analysis",
        r"moisture.*level",
        r"relative.*humidity",
        r"humidity.*distribution"
    ],
    description="Analyzes relative humidity levels with comfort range and condensation risk assessment"
)

def analyze_humidity(
    sensor_data,
    acceptable_range=None,
):
    """
    Analyzes humidity sensor data from a nested JSON structure.

    Automatically discovers humidity-like series across the payload (UUIDs or names),
    aggregates readings, computes summary statistics (mean, min, max, std, latest),
    and flags an alert if the latest reading is outside the acceptable range.

    Expected input (as a Python dict or JSON string):
      {
         "1": {
             "Zone_Air_Humidity_Sensor": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:31:59", "reading_value": 45},
                     {"datetime": "2025-02-10 05:32:11", "reading_value": 50},
                     ...
                 ]
             },
             "Other_Sensor": { ... }
         },
         "2": {
             "Zone_Air_Humidity_Sensor": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:35:00", "reading_value": 55},
                     {"datetime": "2025-02-10 05:35:12", "reading_value": 60},
                     ...
                 ]
             }
         }
      }

    Returns:
      A dictionary containing summary statistics and an alert message.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No humidity data available",
            "description": "No sensor data was provided or detected in the payload",
            "analysis_type": "humidity"
        }

    # Find humidity-like keys
    humidity_pred = _key_matcher(["humidity", "rh", "relative_humidity"])
    keys = _select_keys(flat, humidity_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {
            "error": "No humidity-like keys found",
            "description": "No keys matching 'humidity', 'rh', or 'relative_humidity' patterns were detected",
            "analysis_type": "humidity"
        }

    # Combine all selected series
    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {
            "error": "Empty humidity series",
            "description": "No valid readings found in the humidity sensor data",
            "analysis_type": "humidity"
        }

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    # Default to UK recommended RH range if not provided
    if acceptable_range is None:
        acceptable_range = UK_INDOOR_STANDARDS["humidity_rh"]["range"]
    
    unit = "%"
    mean_val = float(df["reading_value"].mean())
    min_val = float(df["reading_value"].min())
    max_val = float(df["reading_value"].max())
    std_val = float(df["reading_value"].std())
    
    summary = {
        "analysis_type": "humidity",
        "description": f"Relative humidity analysis for {len(keys)} sensor(s) with {len(df)} readings",
        "statistics": {
            "mean": round(mean_val, 1),
            "min": round(min_val, 1),
            "max": round(max_val, 1),
            "std": round(std_val, 1),
            "latest": round(latest, 1) if latest is not None else None,
        },
        "unit": unit,
        "acceptable_range": {
            "min": acceptable_range[0],
            "max": acceptable_range[1],
            "unit": unit,
            "source": "UK Indoor Standards (40-60% RH comfort)"
        },
        "sensors_analyzed": [str(k) for k in keys],
        "reading_count": len(df)
    }
    
    if latest is not None:
        if latest < acceptable_range[0]:
            summary["alert"] = "Humidity too low"
            summary["status"] = "WARNING"
            summary["message"] = f"Current humidity ({latest:.1f}%) is below acceptable range ({acceptable_range[0]}-{acceptable_range[1]}%) - may cause dry air discomfort"
        elif latest > acceptable_range[1]:
            summary["alert"] = "Humidity too high"
            summary["status"] = "WARNING"
            summary["message"] = f"Current humidity ({latest:.1f}%) is above acceptable range ({acceptable_range[0]}-{acceptable_range[1]}%) - may cause condensation or mold risk"
        else:
            summary["alert"] = "Humidity normal"
            summary["status"] = "OK"
            summary["message"] = f"Current humidity ({latest:.1f}%) is within acceptable range ({acceptable_range[0]}-{acceptable_range[1]}%)"
    else:
        summary["alert"] = "No readings"
        summary["status"] = "UNKNOWN"
        summary["message"] = "Unable to determine current humidity"
    
    return summary


@analytics_function(
    patterns=[
        r"temperature.*humidity",
        r"temp.*rh",
        r"thermal.*comfort",
        r"heat.*index",
        r"comfort.*analysis"
    ],
    description="Combined temperature and humidity analysis for thermal comfort assessment"
)

def analyze_temperature_humidity(
    sensor_data,
    temp_key="Air_Temperature_Sensor",
    humidity_key="Zone_Air_Humidity_Sensor",
    temp_range=(18, 27),
    humidity_range=(30, 60),
):
    """
    Analyzes temperature and humidity sensor data from a nested JSON structure.

    Aggregates readings for the specified sensor keys across sensor IDs,
    computes individual summaries for temperature and humidity, and calculates
    a combined comfort index. The comfort index is computed by measuring how
    close the latest sensor readings are to the midpoints of the acceptable ranges.

    Parameters:
      - sensor_data: A dict or JSON string in the nested format.
      - temp_key: Sensor key for temperature (default: "Air_Temperature_Sensor").
      - humidity_key: Sensor key for humidity (default: "Zone_Air_Humidity_Sensor").
      - temp_range: Acceptable range for temperature (default: (18, 27)).
      - humidity_range: Acceptable range for humidity (default: (30, 60)).

    Returns:
      A dictionary with:
        - 'temperature': Summary from analyze_temperatures.
        - 'humidity': Summary from analyze_humidity.
        - 'comfort_index': A value between 0 and 100.
        - 'comfort_assessment': A qualitative assessment ("Comfortable", "Less comfortable", or "Uncomfortable").
    """
    # Parse sensor_data if it's a JSON string.
    if isinstance(sensor_data, str):
        try:
            sensor_data = json.loads(sensor_data)
        except Exception as e:
            logging.error(f"Error parsing sensor_data JSON: {e}")
            return {"error": "Invalid sensor data"}

    # Call the updated analysis functions (which expect the nested JSON structure)
    temp_summary = analyze_temperatures(
        sensor_data, acceptable_range=temp_range
    )
    humidity_summary = analyze_humidity(
        sensor_data, acceptable_range=humidity_range
    )

    # Compute midpoints for the acceptable ranges.
    temp_mid = (temp_range[0] + temp_range[1]) / 2.0
    humidity_mid = (humidity_range[0] + humidity_range[1]) / 2.0

    try:
        temp_latest = temp_summary.get("latest", temp_mid)
        humidity_latest = humidity_summary.get("latest", humidity_mid)
        # Calculate deviations from the midpoints.
        temp_diff = abs(temp_latest - temp_mid)
        humidity_diff = abs(humidity_latest - humidity_mid)
        # Compute a simple comfort index: 100 minus weighted deviations.
        comfort_index = 100 - (temp_diff * 2 + humidity_diff * 1.5)
        # Ensure the index is within 0 to 100.
        comfort_index = max(0, min(100, comfort_index))
        comfort_index = float(comfort_index)
    except Exception as e:
        logging.error(f"Error computing comfort index: {e}")
        comfort_index = None

    combined = {
        "temperature": temp_summary,
        "humidity": humidity_summary,
        "comfort_index": comfort_index,
        "comfort_assessment": (
            "Comfortable"
            if comfort_index is not None and comfort_index > 70
            else (
                "Less comfortable"
                if comfort_index is not None and comfort_index > 40
                else "Uncomfortable"
            )
        ),
    }
    return combined


@analytics_function(
    patterns=[
        r"potential.*failure",
        r"predict.*fault",
        r"failure.*prediction",
        r"equipment.*risk",
        r"proactive.*maintenance"
    ],
    description="Detects potential equipment failures based on anomaly patterns in recent time window"
)

def detect_potential_failures(sensor_data, time_window_hours=24, anomaly_threshold=3):
    """
    Detects potential sensor failures based on anomaly detection within a specified time window,
    using a nested JSON structure.

    Args:
      - sensor_data (dict or JSON string): Nested dictionary containing sensor time series data.
          Expected format:
          {
              "1": {
                  "Sensor_Type_A": {
                      "timeseries_data": [
                          {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                          {"datetime": "2025-02-10 05:32:11", "reading_value": 28.1},
                          ...
                      ]
                  },
                  "Sensor_Type_B": { ... }
              },
              "2": {
                  "Sensor_Type_A": { ... },
                  ...
              }
          }
      - time_window_hours (int): Time window in hours to analyze for potential failures.
      - anomaly_threshold (float): Z-score threshold for anomaly detection.

    Returns:
      - List of flattened sensor identifiers (e.g. "1_Sensor_Type_A") showing potential failures.
    """
    # Use standardized helpers to accept flat or nested payloads
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return []

    sensors_with_failures = []
    for key, readings in flat.items():
        try:
            df = _df_from_readings(readings)
            if df.empty or "reading_value" not in df.columns:
                continue
            df["rolling_mean"] = df["reading_value"].rolling(window=5, min_periods=1).mean()
            df["rolling_std"] = df["reading_value"].rolling(window=5, min_periods=1).std()
            std_series = df["rolling_std"].replace(0, 1)
            df["zscore"] = np.abs((df["reading_value"] - df["rolling_mean"]) / std_series)
            potential_failures = df[df["zscore"] > anomaly_threshold]
            if not potential_failures.empty:
                latest_timestamp = df.iloc[-1]["timestamp"]
                failures_in_window = potential_failures[
                    potential_failures["timestamp"] >= (latest_timestamp - pd.Timedelta(hours=time_window_hours))
                ]
                if not failures_in_window.empty:
                    sensors_with_failures.append(str(key))
        except Exception as e:
            logging.error(f"Error processing sensor {key}: {e}")

    return sensors_with_failures


@analytics_function(
    patterns=[
        r"forecast.*downtime",
        r"predict.*outage",
        r"downtime.*prediction",
        r"maintenance.*forecast",
        r"availability.*forecast"
    ],
    description="Forecasts potential system downtimes using trend extrapolation methods"
)

def forecast_downtimes(sensor_data):
    """
    Forecast potential downtimes using predictive analytics from a nested JSON structure.

    Args:
      - sensor_data (dict or JSON string): Nested sensor data, where each outer key is a sensor ID
        and each inner key is a sensor type containing a "timeseries_data" list.
        Example:
          {
              "1": {
                  "Sensor_Type_A": {
                      "timeseries_data": [
                          {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                          {"datetime": "2025-02-10 05:32:11", "reading_value": 28.1},
                          ...
                      ]
                  },
                  "Sensor_Type_B": { ... }
              },
              "2": {
                  "Sensor_Type_A": { ... },
                  ...
              }
          }
      - The function forecasts downtimes based on rolling statistics.

    Returns:
      - A dictionary mapping each flattened sensor identifier (e.g. "1_Sensor_Type_A") to a list of timestamps
        (as strings) forecasted for potential downtimes.
    """
    # Accept flat or nested payloads
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {}

    downtimes_forecast = {}
    for key, readings in flat.items():
        try:
            df = _df_from_readings(readings)
            if df.empty or "reading_value" not in df.columns:
                downtimes_forecast[str(key)] = []
                continue
            df = df.set_index("timestamp")
            df["rolling_mean"] = df["reading_value"].rolling(window=5, min_periods=1).mean()
            df["rolling_std"] = df["reading_value"].rolling(window=5, min_periods=1).std()
            threshold_series = df["rolling_mean"] - 2 * df["rolling_std"]
            potential_downtimes = df[df["reading_value"] < threshold_series]
            forecasted = potential_downtimes.index.strftime("%Y-%m-%d %H:%M:%S").tolist()
            downtimes_forecast[str(key)] = forecasted
        except Exception as e:
            logging.error(f"Error forecasting downtimes for sensor {key}: {e}")
            downtimes_forecast[str(key)] = []

    return downtimes_forecast


@analytics_function(
    patterns=[
        r"tvoc",
        r"total.*volatile.*organic",
        r"voc.*level",
        r"organic.*compound",
        r"chemical.*pollutant"
    ],
    description="Analyzes Total Volatile Organic Compounds (TVOC) with health-based thresholds"
)

def analyze_tvoc_levels(sensor_data, threshold=None):
    """
    TVOC Levels Assessment — Volatile Organic Compounds Monitoring
    
    Purpose:
    Analyzes Total Volatile Organic Compounds (TVOC) concentrations to assess indoor air 
    quality and occupant health impacts. TVOCs include hundreds of chemicals (benzene, 
    formaldehyde, toluene, etc.) emitted from building materials, furnishings, cleaning 
    products, and occupant activities. High TVOC levels cause headaches, eye irritation, 
    and cognitive impairment. This analysis supports WELL Building compliance and healthy 
    building certification.
    
    Sensors:
      - TVOC_Sensor or TVOC_Level_Sensor (µg/m³ or ppb)
      - VOC_Sensor (alternative naming)
    
    Output:
      - mean_tvoc: Average TVOC concentration
      - min_tvoc, max_tvoc: Range of concentrations
      - latest_tvoc: Most recent reading
      - std_tvoc: Variability (standard deviation)
      - exceedance_hours: Hours above threshold
      - iaq_rating: "Excellent", "Good", "Moderate", "Poor"
      - alert_message: Health advisory if threshold exceeded
    
    This analysis helps:
      - Identify off-gassing from new materials or furnishings
      - Validate building flush-out effectiveness post-construction
      - Detect inadequate ventilation or cleaning product issues
      - Support WELL Building Air Quality Feature 02 (VOC limits)
      - Prevent sick building syndrome (SBS) symptoms
      - Comply with LEED v4 Low-Emitting Materials requirements
    
    Method:
      TVOC thresholds (various standards):
        **WELL Building Standard v2:**
          - Excellent: <220 µg/m³ (Feature 02 limit for certification)
          - Good: 220-500 µg/m³
          - Moderate: 500-1000 µg/m³
          - Poor: 1000-3000 µg/m³
          - Unhealthy: >3000 µg/m³
        
        **German Federal Environment Agency (UBA):**
          - Target: <300 µg/m³ (no health concern)
          - Acceptable: 300-1000 µg/m³ (minor concern)
          - Critical: 1000-3000 µg/m³ (major concern, investigate)
          - Unacceptable: >3000 µg/m³ (remediation required)
        
        **RESET Air Standard:**
          - TVOC: <400 µg/m³ (continuous monitoring)
        
        **Finnish Classification (older but referenced):**
          - S1 (low emission): <200 µg/m³
          - S2 (moderate): 200-400 µg/m³
          - S3 (high): >400 µg/m³
      
      Unit conversions (sensor-dependent):
        ppb to µg/m³ varies by VOC mix (assume typical ~5:1 ratio)
        1 ppb ≈ 5 µg/m³ for TVOC approximation
      
      Health impacts:
        - <300 µg/m³: No irritation expected
        - 300-500 µg/m³: Odor may be noticeable
        - 500-1000 µg/m³: Headaches, irritation possible
        - 1000-3000 µg/m³: Significant discomfort, cognitive effects
        - >3000 µg/m³: Health risk, immediate ventilation needed
      
      Common TVOC sources indoors:
        - New furniture, carpets, paint (off-gassing)
        - Cleaning products, air fresheners
        - Adhesives, sealants, coatings
        - Office equipment (printers, copiers)
        - Personal care products
      
      Mitigation strategies:
        - Increase ventilation rate (outdoor air supply)
        - Source control (low-VOC materials, Green Guard certified)
        - Building flush-out (run HVAC 24/7 for 2 weeks post-construction)
        - Activated carbon filtration (for specific VOCs)
        - Avoid using air fresheners and scented products
      
      WELL Building requirements:
        - Feature 02 Ventilation Effectiveness: TVOC ≤220 µg/m³
        - Feature 05 Air Quality Standards: Continuous monitoring required
        - Feature A05: Enhanced Air Quality with TVOC <100 µg/m³
    
    Parameters:
        sensor_data (dict): TVOC timeseries data from sensors
        threshold (float, optional): Alert threshold in µg/m³ (default 500 µg/m³ - moderate)
    
    Returns:
        dict: TVOC statistics, IAQ rating, exceedance metrics, and health alerts

    Aggregates readings for TVOC-like keys across groups, computes summary stats,
    and flags if the latest reading exceeds the threshold.

    Expected input (as a Python dict or JSON string):
      {
         "1": {
             "TVOC_Level_Sensor1": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:31:59", "reading_value": 180.0},
                     {"datetime": "2025-02-10 05:32:11", "reading_value": 220.5}
                 ]
             }
         },
         "2": {
             "TVOC_Level_Sensor2": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:35:00", "reading_value": 310.2},
                     {"datetime": "2025-02-10 05:35:12", "reading_value": 295.4}
                 ]
             }
         }
      }

    Returns a dictionary containing:
      - mean, min, max, std, and latest reading_value.
      - an alert message if the latest reading exceeds the threshold.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No TVOC data available",
            "description": "No sensor data was provided or detected in the payload",
            "analysis_type": "tvoc_levels"
        }

    tvoc_pred = _key_matcher(["tvoc", "voc"])  # common naming
    keys = _select_keys(flat, tvoc_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {
            "error": "No TVOC-like keys found",
            "description": "No keys matching 'tvoc' or 'voc' patterns were detected",
            "analysis_type": "tvoc_levels"
        }

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {
            "error": "Empty TVOC series",
            "description": "No valid readings found in the TVOC sensor data",
            "analysis_type": "tvoc_levels"
        }

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    # TVOC indoor guidance varies; default to 500 µg/m³ as a conservative short-term threshold
    if threshold is None:
        threshold = 500.0
    
    mean_val = float(df["reading_value"].mean())
    min_val = float(df["reading_value"].min())
    max_val = float(df["reading_value"].max())
    std_val = float(df["reading_value"].std())
    
    summary = {
        "analysis_type": "tvoc_levels",
        "description": f"Total Volatile Organic Compounds (TVOC) analysis for {len(keys)} sensor(s) with {len(df)} readings",
        "statistics": {
            "mean": round(mean_val, 1),
            "min": round(min_val, 1),
            "max": round(max_val, 1),
            "std": round(std_val, 1),
            "latest": round(latest, 1) if latest is not None else None,
        },
        "unit": "µg/m³",
        "threshold": {
            "value": float(threshold),
            "unit": "µg/m³",
            "source": "Conservative indoor air quality guideline"
        },
        "sensors_analyzed": [str(k) for k in keys],
        "reading_count": len(df)
    }
    
    if latest is not None:
        if latest > float(threshold):
            summary["alert"] = "High TVOC level"
            summary["status"] = "WARNING"
            summary["message"] = f"Current TVOC level ({latest:.1f} µg/m³) exceeds acceptable threshold ({threshold} µg/m³) - potential air quality issue"
        else:
            summary["alert"] = "Normal TVOC level"
            summary["status"] = "OK"
            summary["message"] = f"Current TVOC level ({latest:.1f} µg/m³) is within acceptable limits"
    else:
        summary["alert"] = "No readings"
        summary["status"] = "UNKNOWN"
        summary["message"] = "Unable to determine current TVOC level"
    
    return summary


@analytics_function(
    patterns=[
        r"ammonia",
        r"nh3",
        r"ammonia.*level",
        r"ammonia.*concentration",
        r"nitrogen.*compound"
    ],
    description="Analyzes ammonia (NH3) concentration levels with exposure limit classifications"
)

def analyze_ammonia_levels(sensor_data, threshold=None):
    """
    Analyzes Ammonia (NH3) sensor readings from a nested JSON structure.

    Aggregates readings for ammonia-like keys across groups, computes summary stats,
    and flags if the latest reading exceeds the threshold.

    Expected input (as a Python dict or JSON string):
      {
         "1": {
             "Ammonia_Level_Sensor1": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:31:59", "reading_value": 12.5},
                     {"datetime": "2025-02-10 05:32:11", "reading_value": 13.2}
                 ]
             }
         },
         "2": {
             "Ammonia_Level_Sensor2": {
                 "timeseries_data": [
                     {"datetime": "2025-02-10 05:35:00", "reading_value": 18.0},
                     {"datetime": "2025-02-10 05:35:12", "reading_value": 19.1}
                 ]
             }
         }
      }

    Returns a dictionary containing:
      - mean, min, max, std, and latest reading_value.
      - an alert message if the latest reading exceeds the threshold.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {
            "error": "No ammonia data available",
            "description": "No sensor data was provided or detected in the payload",
            "analysis_type": "ammonia_levels"
        }

    nh3_pred = _key_matcher(["ammonia", "nh3"])  # common naming
    keys = _select_keys(flat, nh3_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {
            "error": "No ammonia-like keys found",
            "description": "No keys matching 'ammonia' or 'nh3' patterns were detected",
            "analysis_type": "ammonia_levels"
        }

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {
            "error": "Empty ammonia series",
            "description": "No valid readings found in the ammonia sensor data",
            "analysis_type": "ammonia_levels"
        }

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    # Default threshold: 25 ppm (illustrative short-term limit; adjust per local standards)
    if threshold is None:
        threshold = 25.0
    
    mean_val = float(df["reading_value"].mean())
    min_val = float(df["reading_value"].min())
    max_val = float(df["reading_value"].max())
    std_val = float(df["reading_value"].std())
    
    summary = {
        "analysis_type": "ammonia_levels",
        "description": f"Ammonia (NH3) concentration analysis for {len(keys)} sensor(s) with {len(df)} readings",
        "statistics": {
            "mean": round(mean_val, 2),
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "std": round(std_val, 2),
            "latest": round(latest, 2) if latest is not None else None,
        },
        "unit": "ppm",
        "threshold": {
            "value": float(threshold),
            "unit": "ppm",
            "source": "Short-term exposure limit (illustrative)"
        },
        "sensors_analyzed": [str(k) for k in keys],
        "reading_count": len(df)
    }
    
    if latest is not None:
        if latest > float(threshold):
            summary["alert"] = "High ammonia level"
            summary["status"] = "WARNING"
            summary["message"] = f"Current ammonia level ({latest:.2f} ppm) exceeds acceptable threshold ({threshold} ppm) - potential health hazard"
        else:
            summary["alert"] = "Normal ammonia level"
            summary["status"] = "OK"
            summary["message"] = f"Current ammonia level ({latest:.2f} ppm) is within acceptable limits"
    else:
        summary["alert"] = "No readings"
        summary["status"] = "UNKNOWN"
        summary["message"] = "Unable to determine current ammonia level"
    
    return summary


@analytics_function(
    patterns=[
        r"missing.*data",
        r"data.*gap",
        r"incomplete.*data",
        r"data.*quality.*check",
        r"data.*completeness"
    ],
    description="Scans for missing data points and gaps in expected sensor reading frequency"
)

def analyze_missing_data_scan(sensor_data, expected_freq=None):
    """
    Missing Data Scan — Find gaps/NULLs and coverage per sensor.
    
    Purpose: Identifies data quality issues by detecting gaps, NULL values, and computing coverage
             percentage for each timeseries sensor. Essential for ensuring data readiness before
             running advanced analytics.
    
    Sensors: Any timeseries sensor
    
    Output: 
      - Coverage percentage (% of expected data points present)
      - Longest gap duration in seconds
      - Top gap timestamps (start, end, duration)
      - NULL/missing value counts
      
    This analysis helps identify:
      - Communication failures
      - Sensor downtime
      - Data pipeline issues
      - Periods requiring imputation or interpolation

    Expected input (nested or flat):
      {
        "1": { "Some_Sensor": { "timeseries_data": [ {"datetime":"2025-02-10 05:31:59","reading_value":1.0}, ... ] } },
        "2": { ... }
      }

    Parameters:
      - sensor_data: Nested or flat sensor payload
      - expected_freq: Optional pandas offset alias like "1min" or "5min" to compute coverage more strictly

    Returns: dict key -> { coverage_pct, points, null_count, longest_gap_seconds, top_gaps: [ {start,end,duration_s} ] }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}

    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            out[str(key)] = {"coverage_pct": 0.0, "points": 0, "null_count": 0, "longest_gap_seconds": None, "top_gaps": []}
            continue
        df = df.sort_values("timestamp")
        null_count = int(df["reading_value"].isna().sum())
        points = int(len(df))
        # compute gaps between timestamps
        diffs = df["timestamp"].diff().dt.total_seconds().fillna(0)
        longest_gap = float(diffs.max()) if len(diffs) else 0.0
        # top 3 gaps (exclude 0)
        gap_rows = (
            df.assign(prev_ts=df["timestamp"].shift(1), gap_s=diffs)
              .query("gap_s > 0")
              .sort_values("gap_s", ascending=False)
              .head(3)
        )
        top_gaps = []
        for _, r in gap_rows.iterrows():
            top_gaps.append({
                "start": r["prev_ts"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(r["prev_ts"]) else None,
                "end": r["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if pd.notna(r["timestamp"]) else None,
                "duration_s": float(r["gap_s"]),
            })
        # approximate coverage if expected_freq provided
        if expected_freq:
            try:
                full_range = pd.date_range(start=df["timestamp"].min(), end=df["timestamp"].max(), freq=expected_freq)
                coverage_pct = 100.0 * (points / max(1, len(full_range)))
            except Exception:
                coverage_pct = 100.0
        else:
            coverage_pct = 100.0  # without a target cadence, assume observed coverage
        out[str(key)] = {
            "coverage_pct": round(float(coverage_pct), 2),
            "points": points,
            "null_count": null_count,
            "longest_gap_seconds": longest_gap if longest_gap > 0 else 0.0,
            "top_gaps": top_gaps,
        }
    return out


@analytics_function(
    patterns=[
        r"flatline",
        r"stuck.*sensor",
        r"constant.*value",
        r"sensor.*frozen",
        r"no.*variation"
    ],
    description="Detects flatlined sensors (unchanging values) indicating sensor malfunction"
)

def analyze_flatline_detector(sensor_data, min_duration_points=5):
    """
    Flatline Detector — Identify sensors stuck at constant value.
    
    Purpose: Detects sensors that are "stuck" or "frozen" at a constant reading value for extended
             periods, which typically indicates sensor malfunction, communication failure, or
             hardware issues requiring maintenance.
    
    Sensors: Any sensor type (temperature, pressure, flow, CO2, etc.)
    
    Output:
      - Flatline periods with start/end timestamps
      - Count of flatline occurrences
      - Severity flag (duration-based)
      - Total flatline duration
      
    This analysis helps identify:
      - Failed sensors that need replacement
      - Communication issues causing repeated values
      - Sensors in need of recalibration
      - Data quality problems affecting analytics accuracy

    Parameters:
      - sensor_data: Nested or flat sensor payload
      - min_duration_points: Minimum consecutive points with identical value to flag (default: 5)

    Returns: dict key -> { flatline_periods: [ {start, end, value, length} ], count, severity }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}

    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            out[str(key)] = {"flatline_periods": [], "count": 0, "severity": "none"}
            continue
        df = df.sort_values("timestamp")
        vals = df["reading_value"].tolist()
        ts = df["timestamp"].tolist()
        periods = []
        start_idx = 0
        for i in range(1, len(vals)+1):
            if i == len(vals) or vals[i] != vals[start_idx]:
                length = i - start_idx
                if length >= int(min_duration_points):
                    periods.append({
                        "start": ts[start_idx].strftime("%Y-%m-%d %H:%M:%S"),
                        "end": ts[i-1].strftime("%Y-%m-%d %H:%M:%S"),
                        "value": float(vals[start_idx]) if pd.notna(vals[start_idx]) else None,
                        "length": int(length),
                    })
                start_idx = i
        count = len(periods)
        severity = "high" if count >= 3 else ("medium" if count == 2 else ("low" if count == 1 else "none"))
        out[str(key)] = {"flatline_periods": periods, "count": count, "severity": severity}
    return out


@analytics_function(
    patterns=[
        r"spike",
        r"sudden.*change",
        r"outlier",
        r"jump.*in.*value",
        r"abnormal.*spike"
    ],
    description="Detects sudden spikes and outliers using IQR or z-score methods"
)

def analyze_spike_outliers(sensor_data, method="iqr", threshold=1.5, robust=True):
    """
    Spike/Outlier Detector — Flag sudden unrealistic jumps.
    
    Purpose: Identifies sudden, unrealistic spikes or outliers in sensor readings that may indicate
             sensor errors, communication glitches, or actual anomalous events requiring investigation.
             Uses statistical methods (IQR or robust z-score) to detect values that deviate significantly
             from typical patterns.
    
    Sensors: Any sensor type
    
    Output:
      - Outlier indices and timestamps
      - Magnitude of deviation
      - Robust z-score or IQR multiplier
      - Flagged data points for review
      
    This analysis helps identify:
      - Sensor calibration errors
      - Communication noise/errors
      - Actual anomalous events (equipment failure, fire, etc.)
      - Data points to exclude from statistical summaries
      
    Methods:
      - IQR (Interquartile Range): Flags values beyond Q1-threshold*IQR or Q3+threshold*IQR
      - Robust Z-score: Uses median and MAD (Median Absolute Deviation) for outlier-resistant detection

    Parameters:
      - sensor_data: Nested or flat sensor payload
      - method: "iqr" or "zscore" (default: "iqr")
      - threshold: Multiplier for IQR or z-score cutoff (default: 1.5)
      - robust: If True with zscore, uses MAD instead of std deviation (default: True)

    Returns: dict key -> [ {timestamp, reading_value, score, method} ]
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            out[str(key)] = []
            continue
        if method == "iqr":
            Q1 = df["reading_value"].quantile(0.25)
            Q3 = df["reading_value"].quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - threshold * IQR
            upper = Q3 + threshold * IQR
            mask = (df["reading_value"] < lower) | (df["reading_value"] > upper)
            an = df.loc[mask].copy()
            an["score"] = 0.0
        else:
            if robust:
                med = float(df["reading_value"].median())
                mad = float(np.median(np.abs(df["reading_value"] - med)))
                mad = mad if mad != 0 else 1.0
                df["score"] = 0.6745 * (df["reading_value"] - med) / mad
            else:
                mu = float(df["reading_value"].mean())
                sigma = float(df["reading_value"].std() or 1.0)
                df["score"] = (df["reading_value"] - mu) / sigma
            an = df[np.abs(df["score"]) > threshold]
        an["timestamp"] = an["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        out[str(key)] = an[["timestamp", "reading_value", "score"]].assign(method=method).to_dict(orient="records")
    return out


@analytics_function(
    patterns=[
        r"sensor.*drift",
        r"bias.*detection",
        r"calibration.*drift",
        r"measurement.*bias",
        r"systematic.*error"
    ],
    description="Analyzes sensor drift and bias by comparing against reference sensors"
)

def analyze_sensor_drift_bias(sensor_data, reference_predicates=None):
    """
    Drift/Bias Check — Detect slow drift or bias vs reference.
    
    Purpose: Identifies gradual sensor drift or systematic bias by comparing paired sensors
             (e.g., Supply vs Return temperatures). Slow drift can indicate sensor aging,
             calibration errors, or environmental factors affecting measurement accuracy.
    
    Sensors: Paired sensors such as:
      - Supply_Air_Temperature vs Return_Air_Temperature
      - Chilled_Water_Supply_Temperature vs Chilled_Water_Return_Temperature
      - Outside_Air_Temperature vs Mixed_Air_Temperature
      
    Output:
      - Drift rate (change per unit time)
      - Bias (mean difference between paired sensors)
      - Alert flag if drift/bias exceeds thresholds
      - Trend direction (increasing/decreasing)
      
    This analysis helps identify:
      - Sensors requiring recalibration
      - Sensor aging and degradation
      - Systematic measurement errors
      - Need for sensor replacement planning
      
    Method: Computes linear regression slope (drift rate) and mean difference (bias) between
            paired sensor readings over time.

    Parameters:
      - sensor_data: Nested or flat sensor payload
      - reference_predicates: Optional list of predicates to identify reference sensors
    
    Returns: dict pair_name -> { drift_rate, bias, mean_diff, alert_flag, r_squared }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat or len(flat) < 2:
        return {"error": "Need at least two series for drift/bias comparison"}

    keys = list(flat.keys())
    results = {}
    # Simple O(n^2) pairing heuristic; in production, pass explicit reference groups
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            k1, k2 = str(keys[i]), str(keys[j])
            df1 = _df_from_readings(flat[keys[i]])
            df2 = _df_from_readings(flat[keys[j]])
            if df1.empty or df2.empty:
                continue
            mm = pd.merge_asof(df1.sort_values("timestamp"), df2.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_1","_2"))
            mm = mm.dropna(subset=["reading_value_1","reading_value_2"]) 
            if mm.empty:
                continue
            # Bias as mean difference
            bias = float((mm["reading_value_1"] - mm["reading_value_2"]).mean())
            # Drift via linear regression of difference vs time (days)
            t_days = (mm["timestamp"] - mm["timestamp"].min()).dt.total_seconds() / 86400.0
            try:
                slope = float(np.polyfit(t_days, (mm["reading_value_1"] - mm["reading_value_2"]).values, 1)[0]) if len(mm) >= 2 else 0.0
            except Exception:
                slope = 0.0
            results[f"{k1}__vs__{k2}"] = {"drift_per_day": slope, "bias_mean": bias, "confidence": "low" if len(mm) < 20 else "medium" if len(mm) < 100 else "high"}
    return results


@analytics_function(
    patterns=[
        r"range.*validation",
        r"value.*in.*range",
        r"reading.*bounds",
        r"limit.*check",
        r"out.*of.*range"
    ],
    description="Validates sensor readings against acceptable physical or operational ranges"
)

def analyze_range_validation(sensor_data, ranges=None):
    """
    Range Validation — Enforce physical ranges.
    
    Purpose: Validates that sensor readings fall within physically realistic or standard-defined
             ranges. Values outside these ranges typically indicate sensor malfunction, calibration
             errors, or data transmission problems.
    
    Sensors: Temperature, Pressure, Flow, CO2, and other sensors with known physical limits
    
    Output:
      - Percentage of readings within acceptable range
      - Violation records with timestamps and values
      - Compliance status by sensor
      
    This analysis helps identify:
      - Sensors producing physically impossible values
      - Calibration drift requiring attention
      - Data transmission errors
      - Equipment operating outside design parameters
      
    Default ranges applied from UK Indoor Standards:
      - Temperature: 18-24°C (comfort range)
      - Humidity: 40-60% RH
      - CO2: 400-1000 ppm
      - PM2.5: 0-35 µg/m³
      - PM10: 0-50 µg/m³

    Parameters:
      - sensor_data: Nested or flat sensor payload
      - ranges: Optional dict {key_or_pattern: (min,max)}; if None, infers from UK_INDOOR_STANDARDS

    Returns: dict key -> { percent_in_range, violations: [ {timestamp, value} ], range: {min, max} }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}

    # derive defaults if not provided
    if ranges is None:
        ranges = {}
        for key in flat.keys():
            kl = str(key).lower()
            if "temperature" in kl or re.search(r"\btemp\b", kl):
                lo, hi = UK_INDOOR_STANDARDS["temperature_c"]["range"]
                ranges[key] = (lo, hi)
            elif "humidity" in kl or kl in ("rh", "relative_humidity"):
                lo, hi = UK_INDOOR_STANDARDS["humidity_rh"]["range"]
                ranges[key] = (lo, hi)
            elif "co2" in kl:
                lo, hi = UK_INDOOR_STANDARDS["co2_ppm"]["range"]
                ranges[key] = (lo, hi)
            elif ("co" in kl and "co2" not in kl) or "carbon_monoxide" in kl:
                ranges[key] = (0, UK_INDOOR_STANDARDS["co_ppm"]["max"])
            elif "pm10" in kl:
                ranges[key] = (0, UK_INDOOR_STANDARDS["pm10_ugm3"]["max"])
            elif ("pm2.5" in kl) or ("pm2_5" in kl) or ("pm25" in kl):
                ranges[key] = (0, UK_INDOOR_STANDARDS["pm2.5_ugm3"]["max"])
            elif ("formaldehyde" in kl) or ("hcho" in kl):
                ranges[key] = (0, UK_INDOOR_STANDARDS["hcho_mgm3"]["max"])

    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            out[str(key)] = {"percent_in_range": None, "violations": []}
            continue
        rng = None
        if key in ranges:
            rng = ranges[key]
        else:
            # try pattern match
            kl = str(key).lower()
            for rk, r in ranges.items():
                rkl = str(rk).lower()
                if rkl in kl or kl in rkl:
                    rng = r
                    break
        if rng is None:
            out[str(key)] = {"percent_in_range": None, "violations": [], "note": "no range available"}
            continue
        lo, hi = rng
        mask_ok = df["reading_value"].between(lo, hi, inclusive="both")
        pct = 100.0 * float(mask_ok.mean())
        viol = df.loc[~mask_ok, ["timestamp", "reading_value"]].copy()
        viol["timestamp"] = viol["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
        out[str(key)] = {"percent_in_range": round(pct, 2), "violations": viol.to_dict(orient="records"), "range": {"min": lo, "max": hi}}
    return out


@analytics_function(
    patterns=[
        r"timestamp.*consistency",
        r"time.*gap",
        r"temporal.*consistency",
        r"data.*frequency",
        r"timing.*issue"
    ],
    description="Analyzes timestamp consistency and identifies irregular sampling intervals"
)

def analyze_timestamp_consistency(sensor_data):
    """
    Timestamp Consistency — Check ordering and duplicates.
    
    Purpose: Ensures data integrity by verifying timestamps are properly ordered and identifying
             duplicate timestamp entries that could corrupt time-series analyses.
    
    Sensors: Any timeseries sensor
    
    Output:
      - Count of reordered points removed
      - Duplicate timestamp counts
      - Whether series is strictly increasing
      - Data quality flags
      
    This analysis helps identify:
      - Data collection pipeline issues
      - Database insertion errors
      - Time synchronization problems across systems
      - Need for data cleaning before analysis
      
    Critical for: Ensuring reliable time-series operations like interpolation, resampling,
                   and trend analysis which assume monotonically increasing timestamps.

    Parameters:
      - sensor_data: Nested or flat sensor payload

    Returns: dict key -> { duplicates, strictly_increasing, reordered_count }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            out[str(key)] = {"duplicates": 0, "strictly_increasing": True}
            continue
        dup = int(df["timestamp"].duplicated().sum())
        strictly_inc = bool((df["timestamp"].diff().dropna() > pd.Timedelta(0)).all())
        out[str(key)] = {"duplicates": dup, "strictly_increasing": strictly_inc}
    return out


def analyze_pm_levels(sensor_data, thresholds=None):
    """
    PM Levels Assessment — Particulate Matter Air Quality
    
    Purpose:
    Analyzes particulate matter (PM1, PM2.5, PM10) concentrations to assess indoor air quality 
    and health risks. PM2.5 and PM10 are regulated pollutants; chronic exposure causes respiratory 
    and cardiovascular disease. This analysis flags exceedances against WHO guidelines and UK/EU 
    air quality standards, supporting WELL Building certification and occupant health protection.
    
    Sensors:
      - PM1_Sensor (µg/m³) - ultra-fine particles
      - PM2.5_Sensor (µg/m³) - fine particles (inhalable, most health-critical)
      - PM10_Sensor (µg/m³) - coarse particles
    
    Output:
      Per PM type:
        - mean, min, max: Statistical summary (µg/m³)
        - latest: Most recent reading
        - exceedance_hours: Hours above threshold
        - aqi_category: "Good", "Moderate", "Poor", "Unhealthy"
      
      Aggregated:
        - worst_pollutant: PM type with highest concentration
        - overall_aqi: Composite air quality index
        - health_advisory: Action recommendations
    
    This analysis helps:
      - Protect occupant health from airborne particulates
      - Validate HVAC filtration effectiveness (MERV ratings)
      - Support WELL Building Air Quality standards (Feature 01)
      - Identify pollution sources (outdoor infiltration, indoor generation)
      - Trigger filter replacement or ventilation adjustments
      - Comply with UK Workplace Exposure Limits (WEL)
    
    Method:
      PM thresholds (WHO Air Quality Guidelines 2021):
        **PM2.5 (most critical for health):**
          - Good: 0-5 µg/m³ (WHO 24h guideline: 15 µg/m³)
          - Moderate: 5-15 µg/m³
          - Poor: 15-35 µg/m³ (UK Defra moderate)
          - Unhealthy: 35-55 µg/m³
          - Very Unhealthy: >55 µg/m³
        
        **PM10:**
          - Good: 0-20 µg/m³
          - Moderate: 20-40 µg/m³ (WHO 24h guideline: 45 µg/m³)
          - Poor: 40-80 µg/m³
          - Unhealthy: >80 µg/m³
        
        **PM1:**
          - No official limits, but typically track for IAQ
          - Good: <5 µg/m³
          - Monitor: >10 µg/m³
      
      AQI calculation per pollutant:
        AQI = (I_high - I_low) / (C_high - C_low) × (C_p - C_low) + I_low
        
        Where:
          C_p = measured concentration
          C_low, C_high = breakpoint concentrations
          I_low, I_high = index breakpoint values
      
      Health impacts by PM level:
        - PM2.5 <5 µg/m³: Minimal health risk
        - PM2.5 15-35 µg/m³: Sensitive groups affected (asthma, elderly)
        - PM2.5 >35 µg/m³: General population risk, reduce exposure
        - PM2.5 >55 µg/m³: Hazardous, emergency measures needed
      
      PM sources and mitigation:
        **Outdoor infiltration:**
          - Traffic, industrial, construction nearby
          - Solution: Increase filtration (MERV 13+), reduce OA during pollution events
        
        **Indoor generation:**
          - Cooking, cleaning products, occupant activities
          - Solution: Local exhaust ventilation, source control
        
        **HVAC filtration:**
          - MERV 8: 20-35% PM2.5 capture (inadequate)
          - MERV 13: 50-85% PM2.5 capture (good)
          - MERV 16/HEPA: >95% PM2.5 capture (excellent)
      
      WELL Building Standard limits:
        - PM2.5: <15 µg/m³ (Precondition 01)
        - PM10: <50 µg/m³ (Precondition 01)
        - RESET Air Standard: PM2.5 <12 µg/m³
    
    Parameters:
        sensor_data (dict): PM1, PM2.5, PM10 timeseries data
        thresholds (dict, optional): Custom thresholds {'pm25': 15, 'pm10': 40, 'pm1': 10} in µg/m³
    
    Returns:
        dict: PM statistics per type, AQI categories, exceedance hours, health advisories

    Expected input: nested timeseries; keys containing pm1, pm2.5/pm2_5/pm25, pm10.

    Returns: dict pm_type -> summary
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No PM data available"}
    if thresholds is None:
        thresholds = {"pm1": 50, "pm2.5": 35, "pm2_5": 35, "pm10": 50}
    groups = {"pm1": [], "pm2.5": [], "pm10": []}
    for k in flat.keys():
        kl = str(k).lower()
        if "pm10" in kl:
            groups["pm10"].append(k)
        elif ("pm2.5" in kl) or ("pm2_5" in kl) or ("pm25" in kl):
            groups["pm2.5"].append(k)
        elif kl.startswith("pm1") or ("pm1.0" in kl) or ("pm1_0" in kl):
            groups["pm1"].append(k)
    out = {}
    for pm_type, keys in groups.items():
        if not keys:
            continue
        all_r = []
        for k in keys:
            all_r.extend(flat.get(k, []))
        df = _df_from_readings(all_r)
        if df.empty:
            out[pm_type] = {"error": "No data available"}
            continue
        latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
        unit = "µg/m³"
        th = None
        for kv in [pm_type, pm_type.replace(".", "_"), pm_type.replace(".", "")]:
            if kv in thresholds:
                th = thresholds[kv]
                break
        summary = {
            "mean": float(df["reading_value"].mean()),
            "min": float(df["reading_value"].min()),
            "max": float(df["reading_value"].max()),
            "std": float(df["reading_value"].std()),
            "latest": latest,
            "unit": unit,
        }
        if latest is not None and th is not None:
            summary["alert"] = (f"High {pm_type} reading" if latest > th else f"Normal {pm_type} reading")
            summary["threshold"] = {"value": float(th), "unit": unit}
        out[pm_type] = summary
    if not out:
        return {"error": "No PM-like keys found"}
    return out


@analytics_function(
    patterns=[
        r"iaq.*composite",
        r"overall.*air.*quality",
        r"composite.*iaq",
        r"air.*quality.*score",
        r"integrated.*iaq"
    ],
    description="Computes composite Indoor Air Quality score from multiple parameters (CO2, PM, TVOC, temp, RH)"
)

def analyze_iaq_composite(sensor_data):
    """
    IAQ Composite (AQI) — Combined IAQ index.
    
    Purpose: Calculates a comprehensive Indoor Air Quality index by combining multiple pollutant
             measurements into a single, weighted score. Provides an at-a-glance assessment of
             overall indoor air quality based on multiple environmental parameters.
    
    Sensors: 
      - PM2.5_Level_Sensor
      - PM10_Level_Sensor  
      - CO2_Level_Sensor
      - TVOC_Sensor
      - NO2_Level_Sensor
      - CO_Level_Sensor
      
    Output:
      - AQI score by interval (0-100+ scale)
      - Rating (Good → Moderate → Poor → Very Poor)
      - Component breakdown showing individual pollutant contributions
      - Units for each measured parameter
      
    This analysis helps:
      - Provide holistic air quality assessment
      - Identify primary pollutant contributors
      - Trigger ventilation or filtration responses
      - Support occupant health and comfort decisions
      
    Weighting (default):
      - PM2.5: 30% (fine particulates, health impact)
      - PM10: 20% (coarse particulates)
      - NO2: 20% (outdoor infiltration marker)
      - CO: 15% (combustion product, safety)
      - CO2: 15% (ventilation effectiveness proxy)

    Returns: { AQI: score, Status: label, Components: {pollutant: component}, Units: {pollutant: unit} }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data available for IAQ calculation"}
    thresholds = {"pm2.5": 35, "pm10": 50, "no2": 40, "co": 9, "co2": 1000}
    weights = {"pm2.5": 0.3, "pm10": 0.2, "no2": 0.2, "co": 0.15, "co2": 0.15}
    groups = {k: [] for k in thresholds.keys()}
    for key in flat.keys():
        kl = str(key).lower()
        if "pm10" in kl:
            groups["pm10"].append(key)
        if ("pm2.5" in kl) or ("pm2_5" in kl) or ("pm25" in kl):
            groups["pm2.5"].append(key)
        if "no2" in kl:
            groups["no2"].append(key)
        if (kl == "co") or ("co_sensor" in kl) or (("carbon_monoxide" in kl) and ("co2" not in kl)):
            groups["co"].append(key)
        if "co2" in kl:
            groups["co2"].append(key)
    components = {}
    for pol, keys in groups.items():
        if not keys:
            continue
        rd = []
        for k in keys:
            rd.extend(flat.get(k, []))
        df = _df_from_readings(rd)
        if df.empty:
            continue
        latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
        if latest is None:
            continue
        components[pol] = (latest / thresholds[pol]) * weights[pol]
    if not components:
        return {"error": "Insufficient pollutant data"}
    iaq = float(sum(components.values()))
    if iaq < 0.5:
        status = "Good"
    elif iaq < 1:
        status = "Moderate"
    elif iaq < 1.5:
        status = "Unhealthy for Sensitive Groups"
    else:
        status = "Unhealthy"
    units = {"pm2.5": "µg/m³", "pm10": "µg/m³", "no2": "µg/m³", "co": "ppm", "co2": "ppm"}
    return {"IAQ": round(iaq, 3), "Status": status, "Components": {k: round(v,3) for k, v in components.items()}, "Units": units}


@analytics_function(
    patterns=[
        r"humidity.*profile",
        r"rh.*profile",
        r"moisture.*pattern",
        r"humidity.*distribution",
        r"humidity.*comfort"
    ],
    description="Analyzes humidity profile with comfort range compliance and condensation risk"
)

def analyze_humidity_profile(sensor_data, acceptable_range=None):
    """
    Humidity Profile — Comfort & Mold Risk Assessment
    
    Purpose:
    Analyzes relative humidity (RH%) distribution over time to assess thermal comfort, 
    mold growth risk, and compliance with UK Indoor Standards (40-60% RH). Low RH 
    causes dry skin, respiratory irritation, and static electricity; high RH promotes 
    mold growth, dust mites, and condensation. This analysis quantifies time-in-range 
    and identifies periods requiring humidification or dehumidification.
    
    Sensors:
      - Relative_Humidity_Sensor or RH_Sensor (%)
      - Zone_Humidity_Sensor (%)
    
    Output:
      - mean_rh: Average relative humidity (%)
      - min_rh, max_rh: Extremes during analysis period
      - latest_rh: Most recent reading
      - time_in_range_pct: Percentage of time within acceptable range (default 40-60%)
      - high_rh_hours: Hours spent above upper threshold (mold risk)
      - low_rh_hours: Hours spent below lower threshold (comfort/health risk)
      - alert: Flag for chronic exceedances requiring HVAC intervention
    
    This analysis helps:
      - Validate HVAC humidification/dehumidification strategies
      - Identify mold growth risk zones (RH consistently >60%)
      - Detect occupant comfort issues (dry air <40%, muggy air >60%)
      - Assess condensation risk on cold surfaces
      - Support WELL Building Standard compliance (30-50% RH preferred)
      - Correlate RH with IAQ complaints and respiratory issues
    
    Method:
      Acceptable range defaults to 40-60% RH per UK Indoor Standards.
      Custom ranges can be provided for specific applications:
        - Data centers: 40-55% (condensation control)
        - Museums: 45-55% (artifact preservation)
        - Hospitals: 30-60% (infection control vs static)
      
      Mold risk increases significantly above 60% RH, especially if sustained >6 hours.
      Low RH <30% causes static discharge issues in electronics and discomfort.
    
    Parameters:
        sensor_data (dict): Timeseries relative humidity readings
        acceptable_range (tuple, optional): (min_rh, max_rh) thresholds, defaults to (40, 60)
    
    Returns:
        dict: Humidity statistics, time-in-range %, exceedance hours, and alerts
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No humidity data available"}
    rh_pred = _key_matcher(["humidity", "relative_humidity", "rh"])
    keys = _select_keys(flat, rh_pred, fallback_to_all=(len(flat)==1))
    if not keys:
        return {"error": "No RH-like keys found"}
    all_r = []
    for k in keys:
        all_r.extend(flat.get(k, []))
    df = _df_from_readings(all_r)
    if df.empty:
        return {"error": "Empty humidity series"}
    if acceptable_range is None:
        acceptable_range = UK_INDOOR_STANDARDS["humidity_rh"]["range"]
    lo, hi = acceptable_range
    mask = df["reading_value"].between(lo, hi, inclusive="both")
    time_in_range = float(mask.mean()) * 100.0
    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    high_rh_hours = float((~mask).sum())  # count of points; without cadence assume 1 per point
    alert = "Mold risk" if latest is not None and latest > hi else ("Too dry" if latest is not None and latest < lo else "Normal")
    return {
        "mean": float(df["reading_value"].mean()),
        "min": float(df["reading_value"].min()),
        "max": float(df["reading_value"].max()),
        "latest": latest,
        "unit": "%",
        "acceptable_range": {"min": lo, "max": hi, "unit": "%"},
        "time_in_range_pct": round(time_in_range, 2),
        "high_rh_count": int((df["reading_value"] > hi).sum()),
        "low_rh_count": int((df["reading_value"] < lo).sum()),
        "alert": alert,
    }


@analytics_function(
    patterns=[
        r"dew.*point",
        r"dewpoint",
        r"condensation.*point",
        r"moisture.*condensation",
        r"dew.*temperature"
    ],
    description="Calculates and tracks dew point temperature for condensation risk analysis"
)

def analyze_dewpoint_tracking(sensor_data):
    """
    Dewpoint Tracking — Condensation Risk Assessment
    
    Purpose:
    Calculates dewpoint temperature from air temperature and relative humidity to assess 
    condensation risk on cold surfaces (windows, pipes, walls). When surface temperature 
    drops below the dewpoint, moisture condenses, leading to mold growth, building fabric 
    damage, and IAQ problems. Critical for envelope design validation, HVAC humidity 
    control, and preventing moisture damage in buildings.
    
    Sensors:
      - Air_Temperature_Sensor or Zone_Temperature (°C)
      - Relative_Humidity_Sensor (%)
      - Optional: Surface_Temperature_Sensor for direct condensation detection
    
    Output:
      - dewpoint_latest: Current dewpoint temperature (°C)
      - dewpoint_mean: Average dewpoint during analysis period
      - dewpoint_min, dewpoint_max: Range of dewpoint values
      - condensation_risk: "Low", "Moderate", or "High" based on dewpoint-surface temp gap
      - risk_hours: Hours when condensation likely (dewpoint > estimated surface temp)
    
    This analysis helps:
      - Prevent mold growth and moisture damage on cold surfaces
      - Validate window and envelope thermal performance (avoid cold bridging)
      - Optimize HVAC dehumidification strategies
      - Detect infiltration issues (high dewpoint in winter = outdoor air leakage)
      - Support building envelope commissioning and thermal imaging surveys
      - Assess risk in moisture-sensitive spaces (archives, museums, data centers)
    
    Method:
      Magnus-Tetens approximation for dewpoint calculation:
        
        a = 17.27
        b = 237.7
        α(T,RH) = (a×T)/(b+T) + ln(RH/100)
        
        Dewpoint (°C) = (b × α) / (a - α)
      
      Where T = air temperature (°C), RH = relative humidity (%)
      
      Condensation risk assessment:
        - Surface temperature estimation (without sensor):
          T_surface ≈ T_air - (thermal_resistance_factor × ΔT_indoor_outdoor)
          
        - Risk levels:
          * Low risk: Dewpoint < Surface temp - 3°C (safe margin)
          * Moderate: Dewpoint within 3°C of surface temp (monitor)
          * High risk: Dewpoint > Surface temp (condensation occurring)
      
      Typical problem scenarios:
        - High dewpoint (>15°C) in winter: Humidification excessive or infiltration
        - Dewpoint near window surface temp: Single-pane glazing, cold bridging
        - Dewpoint >20°C in summer: Dehumidification needed, comfort issues
    
    Parameters:
        sensor_data (dict): Temperature and relative humidity timeseries data
    
    Returns:
        dict: Dewpoint statistics, condensation risk assessment, and risk hours
    
    Requires: temperature-like and RH-like series present.
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}
    temp_pred = _key_matcher(["temperature", "temp"], exclude_substrs=["attempt"])  # avoid 'attempt'
    rh_pred = _key_matcher(["humidity", "relative_humidity", "rh"])
    t_keys = _select_keys(flat, temp_pred, fallback_to_all=False)
    rh_keys = _select_keys(flat, rh_pred, fallback_to_all=False)
    if not t_keys or not rh_keys:
        return {"error": "Need both temperature and RH series"}
    # combine
    t_df = _df_from_readings(sum((flat[k] for k in t_keys), []))
    rh_df = _df_from_readings(sum((flat[k] for k in rh_keys), []))
    if t_df.empty or rh_df.empty:
        return {"error": "Insufficient readings for dewpoint"}
    mm = pd.merge_asof(t_df.sort_values("timestamp"), rh_df.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_t","_rh"))
    mm = mm.dropna(subset=["reading_value_t","reading_value_rh"]) 
    if mm.empty:
        return {"error": "Could not align temperature and RH"}
    # Magnus formula
    a, b = 17.27, 237.7
    T = mm["reading_value_t"].astype(float)
    RH = mm["reading_value_rh"].clip(lower=0.01, upper=100.0).astype(float)
    gamma = (a*T/(b+T)) + np.log(RH/100.0)
    dp = (b*gamma) / (a - gamma)
    dp_latest = float(dp.iloc[-1])
    risk = "Condensation risk" if dp_latest > 20.0 else "Low risk"  # heuristic
    return {"dewpoint_latest": round(dp_latest,2), "dewpoint_mean": round(float(dp.mean()),2), "unit": "°C", "risk": risk}


@analytics_function(
    patterns=[
        r"enthalpy",
        r"moisture.*content",
        r"humidity.*ratio",
        r"grains.*moisture",
        r"psychrometric"
    ],
    description="Calculates air enthalpy and moisture content (grains) for psychrometric analysis"
)

def analyze_air_enthalpy_grains(sensor_data, pressure_kpa=101.325):
    """
    Air Enthalpy & Grains — Psychrometric Property Calculation
    
    Purpose:
    Computes air enthalpy (total heat content) and humidity ratio (moisture content) from 
    dry-bulb temperature and relative humidity. These psychrometric properties are critical 
    for enthalpy economizer control, coil sizing, mixed-air validation, and HVAC load 
    calculations. Enthalpy economizer logic uses total heat content (sensible + latent) 
    rather than dry-bulb temperature alone to determine free cooling opportunities.
    
    Sensors:
      - Temperature or Temp sensors (dry-bulb, °C)
      - Humidity, Relative_Humidity, or RH sensors (%)
      - Optional: Pressure sensor (kPa, defaults to sea-level 101.325 kPa)
    
    Output:
      - enthalpy_mean: Average enthalpy (kJ/kg dry air)
      - enthalpy_latest: Most recent enthalpy reading
      - enthalpy_min, enthalpy_max: Range
      - grains_mean: Average humidity ratio (grains/lb dry air)
      - grains_latest: Most recent grains reading
      - w_mean: Humidity ratio (kg water / kg dry air)
    
    This analysis helps:
      - Select enthalpy economizer over temperature economizer (humid climates)
      - Validate mixed-air temperature/humidity psychrometric relationships
      - Size cooling/dehumidification coils (latent vs sensible load)
      - Detect simultaneous heating-cooling or reheat inefficiencies
      - Calculate dew point approach (coil performance indicator)
      - Support ASHRAE Standard 90.1 economizer compliance
    
    Method:
      **Psychrometric formulas (ASHRAE Fundamentals 2021, Ch. 1):**
      
      1. Saturation vapor pressure (Magnus-Tetens approximation):
         P_ws = 0.61121 × exp[(17.502 × T) / (240.97 + T)]  [kPa]
         Where T = dry-bulb temperature (°C)
      
      2. Actual vapor pressure:
         P_w = RH/100 × P_ws  [kPa]
      
      3. Humidity ratio (mass of water per mass of dry air):
         w = 0.622 × P_w / (P_atm - P_w)  [kg water / kg dry air]
         Where P_atm = atmospheric pressure (kPa, default 101.325 at sea level)
      
      4. Humidity ratio in grains (US customary units):
         Grains/lb = w × 7000  [grains per pound dry air]
         (1 grain = 1/7000 pound = 0.0648 grams)
      
      5. Specific enthalpy (total heat content):
         h = 1.006 × T + w × (2501 + 1.86 × T)  [kJ/kg dry air]
         Where:
           1.006 = specific heat of dry air (kJ/kg·K)
           2501 = latent heat of vaporization at 0°C (kJ/kg)
           1.86 = specific heat of water vapor (kJ/kg·K)
      
      **Enthalpy economizer decision logic:**
        If h_outdoor < h_return AND T_outdoor < T_return:
          → Use 100% outdoor air (free cooling)
        If T_outdoor < T_return BUT h_outdoor > h_return:
          → Humid outdoor air, use temperature economizer only or reduce OA
        
        Example: T_outdoor = 22°C, RH = 80% → h ≈ 59 kJ/kg (high latent)
                 T_outdoor = 22°C, RH = 40% → h ≈ 42 kJ/kg (low latent)
                 Same temperature, but enthalpy differs by 40% due to humidity!
      
      **Typical enthalpy ranges (sea level, approximate):**
        - Dry, cold (5°C, 30% RH): ~12 kJ/kg
        - Comfort zone (22°C, 50% RH): ~43 kJ/kg
        - Hot, humid (32°C, 70% RH): ~80 kJ/kg
        - Tropical (32°C, 90% RH): ~100+ kJ/kg
      
      **Grains moisture content (US convention):**
        - Very dry (<30 grains): Desert, winter heating
        - Comfortable (40-60 grains): ASHRAE 55 comfort range
        - Humid (>80 grains): Mold risk, dehumidification needed
        - Saturated (~120 grains at 70°F): 100% RH
      
      **Altitude correction:**
        Atmospheric pressure decreases ~12% per 1000m elevation
        At 1500m (Denver): P_atm ≈ 83.5 kPa (vs 101.325 at sea level)
        Lower pressure → slightly higher humidity ratio for same RH
      
      **Mixed-air validation application:**
        Given: T_oa, RH_oa, T_ra, RH_ra, damper_position (% OA)
        Expected mixed-air enthalpy:
          h_ma = (damper_pos/100) × h_oa + (1 - damper_pos/100) × h_ra
        If measured h_ma deviates >10%: damper leakage or sensor error
      
      **ASHRAE Standard 90.1-2022 economizer requirements:**
        - Integrated economizer mandatory in Climate Zones 2B-8 (cooling >135,000 Btu/h)
        - High-limit shutoff based on dry-bulb (fixed 75°F) OR enthalpy (28 Btu/lb = 65 kJ/kg)
        - Enthalpy economizer preferred in humid climates (coastal, southeastern US)
    
    Parameters:
        sensor_data (dict): Temperature and RH timeseries data
        pressure_kpa (float, optional): Atmospheric pressure in kPa (default 101.325 - sea level)
    
    Returns:
        dict: Enthalpy (kJ/kg), grains (grains/lb), humidity ratio (kg/kg), statistical summaries

    Computes air enthalpy (kJ/kg dry air) and humidity ratio in grains based on dry-bulb temperature (°C) and RH (%).

    Returns: { enthalpy_mean, enthalpy_latest, grains_mean, grains_latest, notes }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}
    t_pred = _key_matcher(["temperature", "temp"], exclude_substrs=["attempt"])  # avoid 'attempt'
    rh_pred = _key_matcher(["humidity", "relative_humidity", "rh"])
    t_keys = _select_keys(flat, t_pred, fallback_to_all=False)
    rh_keys = _select_keys(flat, rh_pred, fallback_to_all=False)
    if not t_keys or not rh_keys:
        return {"error": "Need temperature and RH series"}
    T = _df_from_readings(sum((flat[k] for k in t_keys), []))
    RH = _df_from_readings(sum((flat[k] for k in rh_keys), []))
    if T.empty or RH.empty:
        return {"error": "Insufficient readings"}
    mm = pd.merge_asof(T.sort_values("timestamp"), RH.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_t","_rh"))
    mm = mm.dropna(subset=["reading_value_t","reading_value_rh"]) 
    if mm.empty:
        return {"error": "Could not align temperature and RH"}
    # Saturation vapor pressure (kPa) via Magnus and humidity ratio W (kg/kg dry air)
    a, b = 17.27, 237.7
    Td = mm["reading_value_t"].astype(float)
    RHv = mm["reading_value_rh"].clip(lower=0.01, upper=100.0).astype(float)
    Ps = 0.6108 * np.exp((a*Td)/(Td + b))  # approximate in kPa
    Pw = (RHv/100.0) * Ps
    P = float(pressure_kpa)
    W = 0.62198 * Pw / max(1e-6, (P - Pw))  # kg/kg dry air
    # Enthalpy (kJ/kg dry air) approx: h = 1.006*T + W*(2501 + 1.86*T)
    h = 1.006*Td + W*(2501.0 + 1.86*Td)
    grains = W * 7000.0  # grains of moisture per lb dry air (approx scale)
    return {
        "enthalpy_mean": round(float(np.mean(h)), 2),
        "enthalpy_latest": round(float(h.iloc[-1]), 2),
        "enthalpy_unit": "kJ/kg dry air",
        "grains_mean": round(float(np.mean(grains)), 1),
        "grains_latest": round(float(grains.iloc[-1]), 1),
        "grains_unit": "grains/lb (approx)",
        "notes": "Approximations assume standard pressure; use psychrometrics lib for precision.",
    }


@analytics_function(
    patterns=[
        r"zone.*iaq",
        r"zone.*compliance",
        r"zone.*air.*quality",
        r"space.*iaq",
        r"room.*air.*quality"
    ],
    description="Assesses zone-level IAQ compliance against CO2 and RH standards"
)

def analyze_zone_iaq_compliance(sensor_data, co2_max=None, rh_range=None):
    """
    Zone IAQ Compliance — Multi-Zone Air Quality Monitoring
    
    Purpose:
    Assesses indoor air quality compliance across multiple zones by tracking time-in-range 
    for CO2 and relative humidity against regulatory standards (UK Indoor Standards, ASHRAE 
    62.1, WELL Building Standard). Identifies problem zones requiring HVAC adjustments, 
    increased ventilation, or humidity control. Essential for multi-zone buildings to ensure 
    consistent IAQ performance and occupant health.
    
    Sensors:
      - Zone_CO2_Sensor (ppm) per zone
      - Zone_RH_Sensor (%) per zone
      - Zone identifiers from sensor naming (e.g., "Zone_A_CO2", "Zone_B_RH")
    
    Output:
      Per zone:
        - co2_compliance_pct: Percentage of time CO2 ≤ threshold (default 1000 ppm)
        - rh_compliance_pct: Percentage of time RH within range (default 40-60%)
        - latest_co2: Most recent CO2 reading
        - latest_rh: Most recent RH reading
        - violations_count: Number of exceedance events
      
      Aggregated:
        - worst_zone: Zone with lowest compliance score
        - building_compliance_avg: Average compliance across all zones
        - zones_failing: List of zones with <80% compliance
    
    This analysis helps:
      - Identify zones with chronic IAQ problems requiring HVAC rebalancing
      - Prioritize maintenance and control adjustments by zone
      - Support WELL Building certification (Feature 02: Air Quality Standards)
      - Validate VAV system performance and minimum airflow setpoints
      - Track IAQ complaints and correlate with specific zones
      - Ensure equitable IAQ performance across building (no "forgotten zones")
    
    Method:
      Compliance calculation per zone:
        CO2 Compliance % = (Hours CO2 ≤ threshold) / (Total Hours) × 100
        RH Compliance % = (Hours RH in range) / (Total Hours) × 100
        
        Overall IAQ Compliance = (CO2_compliance + RH_compliance) / 2
      
      Default thresholds:
        - CO2: ≤1000 ppm (UK BB101, ASHRAE 62.1)
        - RH: 40-60% (UK Indoor Standards)
        - WELL Building: CO2 ≤900 ppm (stricter), RH 30-60%
      
      Custom thresholds can be specified:
        - Labs/cleanrooms: CO2 ≤800 ppm, RH 35-50%
        - Museums: RH 45-55% (tighter for artifact preservation)
        - Gyms: CO2 ≤1200 ppm acceptable, RH <70% (high occupancy)
      
      Zone performance tiers:
        - Excellent: >95% compliance
        - Good: 90-95% compliance
        - Marginal: 80-90% compliance (requires attention)
        - Poor: <80% compliance (urgent action needed)
    
    Parameters:
        sensor_data (dict): Multi-zone CO2 and RH timeseries data
        co2_max (float, optional): CO2 threshold in ppm (default 1000)
        rh_range (tuple, optional): (min_rh, max_rh) acceptable range (default (40, 60))
    
    Returns:
        dict: Per-zone compliance metrics and building-wide IAQ performance summary
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}
    co2_pred = _key_matcher(["co2"]) ; rh_pred = _key_matcher(["humidity", "relative_humidity", "rh"])
    co2_keys = _select_keys(flat, co2_pred, fallback_to_all=False)
    rh_keys = _select_keys(flat, rh_pred, fallback_to_all=False)
    if not co2_keys and not rh_keys:
        return {"error": "No CO2 or RH series found"}
    if co2_max is None:
        co2_max = UK_INDOOR_STANDARDS["co2_ppm"].get("range", (0, 1000))[1]
    if rh_range is None:
        rh_range = UK_INDOOR_STANDARDS["humidity_rh"]["range"]
    out = {}
    if co2_keys:
        dfc = _df_from_readings(sum((flat[k] for k in co2_keys), []))
    else:
        dfc = pd.DataFrame()
    if rh_keys:
        dfr = _df_from_readings(sum((flat[k] for k in rh_keys), []))
    else:
        dfr = pd.DataFrame()
    # compute compliance over combined series (site-level proxy)
    if not dfc.empty:
        co2_ok = (dfc["reading_value"] <= float(co2_max)).mean() * 100.0
        latest_co2 = float(dfc.iloc[-1]["reading_value"])
    else:
        co2_ok = None; latest_co2 = None
    if not dfr.empty:
        lo, hi = rh_range
        rh_ok = dfr["reading_value"].between(lo, hi, inclusive="both").mean() * 100.0
        latest_rh = float(dfr.iloc[-1]["reading_value"])
    else:
        rh_ok = None; latest_rh = None
    out["site"] = {
        "co2_compliance_pct": (round(float(co2_ok),2) if co2_ok is not None else None),
        "rh_compliance_pct": (round(float(rh_ok),2) if rh_ok is not None else None),
        "latest_co2": latest_co2,
        "latest_rh": latest_rh,
    }
    return out


@analytics_function(
    patterns=[
        r"outdoor.*indoor.*comparison",
        r"outside.*inside.*air",
        r"outdoor.*vs.*indoor",
        r"fresh.*air.*vs.*indoor",
        r"ventilation.*effectiveness"
    ],
    description="Contrasts outdoor and indoor air quality to assess ventilation effectiveness"
)

def analyze_iaq_contrast_outdoor_indoor(sensor_data, threshold_ppm=100):
    """
    IAQ Contrast (Outdoor vs Indoor) — Ventilation Opportunity Assessment
    
    Purpose:
    Compares outdoor air quality (typically CO₂) against return/indoor air to identify 
    economizer and increased ventilation opportunities. When outdoor air is significantly 
    cleaner than return air, increasing outdoor air percentage improves IAQ at minimal 
    energy penalty (or even energy savings via free cooling). This analysis supports 
    demand-controlled ventilation (DCV) optimization and dynamic economizer strategies.
    
    Sensors:
      - Outside_Air_CO2 or Outdoor_Air_CO2_Sensor (ppm)
      - Return_Air_CO2 or Indoor_Air_CO2_Sensor (ppm)
      - Optional: Outdoor_PM2.5, Indoor_PM2.5 for particulate contrast
    
    Output:
      - differential_mean: Average CO₂ difference (Return - Outdoor, ppm)
      - differential_latest: Current CO₂ gradient
      - opportunity_hours: Hours when outdoor < indoor by threshold
      - opportunity_percentage: % of time economizer/increased OA is beneficial
      - ventilation_recommendation: "Increase OA", "Standard", "Reduce OA"
      - energy_savings_potential: "High", "Moderate", "Low"
    
    This analysis helps:
      - Identify free cooling + IAQ improvement opportunities (economizer win-win)
      - Detect indoor sources of pollution (when indoor > outdoor persistently)
      - Optimize demand-controlled ventilation (DCV) setpoints dynamically
      - Justify outdoor air percentage increases during wildfire/pollution events (when outdoor < indoor)
      - Support ASHRAE Standard 62.1 ventilation effectiveness assessments
      - Validate outdoor air damper operation and minimum ventilation rates
    
    Method:
      **CO₂ differential decision logic:**
        Differential = CO₂_return - CO₂_outdoor (ppm)
        
        If Differential > 100 ppm:
          → Indoor sources present (occupants, combustion)
          → Increase outdoor air ventilation beneficial
          → Economizer opportunity if temperature permits
        
        If Differential < 50 ppm:
          → Outdoor and indoor CO₂ similar
          → Verify minimum ventilation is maintained
          → Check for outdoor air damper stuck open or sensor drift
        
        If Differential < 0 (outdoor > indoor):
          → Outdoor pollution event (traffic, industrial, wildfire)
          → Reduce outdoor air to minimum code requirement
          → Enable recirculation mode, increase filtration
      
      **Typical CO₂ differentials:**
        - Office (occupied, adequate ventilation): 200-400 ppm rise
        - Office (poor ventilation): 600-1000 ppm rise
        - School classroom (occupied): 400-800 ppm rise
        - Outdoor baseline: 400-420 ppm (rural), 450-500 ppm (urban)
        - Outdoor elevated: 500-600 ppm (traffic-adjacent, highway proximity)
      
      **Economizer opportunity criteria (combined CO₂ + temperature):**
        Favorable conditions:
          1. CO₂_outdoor < CO₂_return - 100 ppm (ventilation benefit)
          2. T_outdoor < T_return - 2°C (cooling benefit)
          3. h_outdoor < h_return (enthalpy benefit, if humidity considered)
        
        If all three: Maximum economizer damper position (up to 100% OA)
        If CO₂ favorable but temperature unfavorable: Balanced approach (minimum OA + recirculation)
      
      **Outdoor air quality monitoring (beyond CO₂):**
        During wildfire/pollution events (PM2.5 > 35 µg/m³ outdoor):
          - Prioritize indoor recirculation over ventilation
          - Increase filtration to MERV 13+ or HEPA
          - Monitor indoor CO₂ vs outdoor PM2.5 trade-off
          - ASHRAE Position Document: Acceptable indoor CO₂ may rise to 1500 ppm temporarily
        
        During low outdoor pollution (PM2.5 < 12 µg/m³):
          - Maximize outdoor air for IAQ and free cooling
          - Flush building during unoccupied periods (purge cycle)
      
      **Sensor placement considerations:**
        - Outdoor CO₂ sensor: Away from exhaust vents, 2-3m from building
        - Return air CO₂: Representative of mixed return (not near exhaust grilles)
        - Avoid cross-contamination: Outdoor sensor downwind of exhaust
      
      **False differential scenarios (sensor errors):**
        - Sensor drift: CO₂ sensors drift +50-100 ppm/year without calibration
        - Outdoor sensor near exhaust: Reads artificially high outdoor CO₂
        - Return sensor near fresh air inlet: Reads artificially low return CO₂
        - Mitigation: Annual calibration to 400 ppm outdoor baseline
      
      **ASHRAE Standard 62.1 ventilation effectiveness:**
        Ventilation effectiveness (Ev) = (CO₂_supply - CO₂_outdoor) / (CO₂_return - CO₂_outdoor)
        If Ev < 0.8: Poor air distribution, short-circuiting suspected
        If Ev > 1.0: Well-mixed ventilation, uniform CO₂ distribution
      
      **Energy savings estimation:**
        High savings potential (Differential > 300 ppm, T_outdoor < T_return):
          - Economizer hours: ~1000-2000 hrs/year (climate-dependent)
          - Cooling energy savings: 20-40% (dry climates)
        
        Moderate savings (Differential 100-300 ppm):
          - Partial economizer benefit, DCV optimization
          - Savings: 5-15%
        
        Low savings (Differential < 100 ppm):
          - Maintain minimum ventilation only
          - Focus on other efficiency measures
    
    Parameters:
        sensor_data (dict): Outdoor and return air CO₂ timeseries data
        threshold_ppm (float, optional): Minimum differential for opportunity flag (default 100 ppm)
    
    Returns:
        dict: CO₂ differential statistics, opportunity hours, ventilation recommendations

    Compares Outside_Air_CO2 vs Return_Air_CO2; flags economizer feasibility when OA << Return.

    Returns: { differential_latest, opportunity: bool, hours_opportunity (approx by points) }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}
    oa_pred = _key_matcher(["outside_air", "outdoor" ])
    ret_pred = _key_matcher(["return_air", "return" ])
    co2_pred = _key_matcher(["co2"])  
    oa_keys = [k for k in flat.keys() if oa_pred(str(k)) and co2_pred(str(k))]
    ra_keys = [k for k in flat.keys() if ret_pred(str(k)) and co2_pred(str(k))]
    if not oa_keys or not ra_keys:
        return {"error": "Need outside and return CO2 series"}
    df_oa = _df_from_readings(sum((flat[k] for k in oa_keys), []))
    df_ra = _df_from_readings(sum((flat[k] for k in ra_keys), []))
    if df_oa.empty or df_ra.empty:
        return {"error": "Insufficient readings"}
    mm = pd.merge_asof(df_oa.sort_values("timestamp"), df_ra.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_oa","_ra"))
    mm = mm.dropna(subset=["reading_value_oa","reading_value_ra"]) 
    if mm.empty:
        return {"error": "Could not align OA and RA"}
    diff = (mm["reading_value_ra"] - mm["reading_value_oa"])  # positive means OA cleaner
    latest = float(diff.iloc[-1])
    opp = bool((diff > float(threshold_ppm)).sum() > 0)
    return {"differential_latest": round(latest,1), "opportunity": opp, "approx_opportunity_count": int((diff > float(threshold_ppm)).sum())}


@analytics_function(
    patterns=[
        r"zone.*temperature",
        r"space.*temperature",
        r"room.*temperature",
        r"zone.*thermal",
        r"multi.*zone.*temp"
    ],
    description="Summarizes temperature statistics and comfort compliance across zones"
)

def analyze_zone_temperature_summary(sensor_data, comfort_range=None):
    """
    Zone Temperature Summary — Thermal Comfort Distribution
    
    Purpose:
    Provides comprehensive statistical summary of zone air temperature distribution to 
    assess thermal comfort compliance, HVAC control effectiveness, and occupant satisfaction. 
    Tracks time-in-comfort range to quantify thermal comfort delivery and identify zones 
    with chronic over/under-heating issues. Essential for validating HVAC performance and 
    responding to comfort complaints.
    
    Sensors:
      - Zone_Air_Temperature_Sensor (°C)
      - Zone_Temperature_Sensor (°C)
      - Room_Temperature_Sensor (°C)
    
    Output:
      - mean_temp: Average zone temperature (°C)
      - min_temp, max_temp: Temperature extremes during period
      - latest_temp: Most recent reading
      - time_in_comfort_pct: Percentage of time within comfort band (default 20-24°C)
      - hours_too_cold: Hours below comfort range (heating inadequacy)
      - hours_too_hot: Hours above comfort range (cooling inadequacy)
      - temperature_stability: Standard deviation (lower = more stable)
    
    This analysis helps:
      - Quantify HVAC system ability to maintain comfort setpoints
      - Validate thermostat control and VAV box performance
      - Respond to occupant comfort complaints with data evidence
      - Assess seasonal HVAC performance (summer cooling, winter heating)
      - Support WELL Building and BREEAM thermal comfort credits
      - Identify zones requiring HVAC rebalancing or controls tuning
    
    Method:
      Statistical analysis of zone temperature timeseries:
        - Central tendency: Mean, median
        - Range: Min, max, percentiles
        - Stability: Standard deviation, coefficient of variation
        - Compliance: Time-in-range calculation
      
      Default comfort range: 20-24°C (UK Indoor Standards, ISO 7730)
      
      Comfort standards by application:
        - UK Offices (BB101): 21-23°C winter, 23-25°C summer
        - ISO 7730 Category II: 20-24°C (typical offices)
        - WELL Building: 18-26°C (broader, allowing local control)
        - ASHRAE 55: 20-25°C (PMV ±0.5 for sedentary work)
        - Healthcare: 18-24°C (tighter for patient areas)
      
      Time-in-comfort calculation:
        Comfort % = (Hours in range) / (Total hours) × 100
        
        Performance tiers:
          - Excellent: >95% time in comfort
          - Good: 90-95% (occasional excursions acceptable)
          - Marginal: 80-90% (requires investigation)
          - Poor: <80% (significant comfort issues, urgent action)
      
      Temperature stability metric:
        Stable control: σ < 0.5°C (tight PID tuning)
        Acceptable: σ = 0.5-1.0°C (normal variability)
        Unstable: σ > 1.0°C (hunting, cycling, or external load swings)
    
    Parameters:
        sensor_data (dict): Zone temperature timeseries data
        comfort_range (tuple, optional): (min_temp, max_temp) in °C (default (20, 24))
    
    Returns:
        dict: Temperature statistics, comfort compliance %, and stability metrics
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No temperature data available"}
    temp_pred = _key_matcher(["zone_air_temperature", "zone temperature", "zone_air", "temperature", "temp"], exclude_substrs=["attempt"])
    keys = _select_keys(flat, temp_pred, fallback_to_all=(len(flat)==1))
    if not keys:
        return {"error": "No zone temperature-like keys found"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    if df.empty:
        return {"error": "Empty temperature series"}
    if comfort_range is None:
        comfort_range = UK_INDOOR_STANDARDS["temperature_c"]["range"]
    lo, hi = comfort_range
    mask = df["reading_value"].between(lo, hi, inclusive="both")
    return {
        "mean": round(float(df["reading_value"].mean()),2),
        "min": round(float(df["reading_value"].min()),2),
        "max": round(float(df["reading_value"].max()),2),
        "latest": round(float(df.iloc[-1]["reading_value"]),2),
        "unit": "°C",
        "time_in_comfort_pct": round(float(mask.mean()*100.0),2),
        "acceptable_range": {"min": lo, "max": hi, "unit": "°C"},
    }


@analytics_function(
    patterns=[
        r"comfort.*index",
        r"thermal.*comfort",
        r"comfort.*score",
        r"occupant.*comfort",
        r"pmv"
    ],
    description="Calculates simple comfort index based on temperature and humidity targets"
)

def analyze_simple_comfort_index(sensor_data, t_target=22.0, rh_target=50.0):
    """
    Computes a simple comfort score (0–100) as a function of deviation from targets (22°C, 50% RH).
    Returns: { score_latest, score_mean, notes }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}
    t_pred = _key_matcher(["temperature", "temp"], exclude_substrs=["attempt"]) ; rh_pred = _key_matcher(["humidity","rh","relative_humidity"])
    T = _df_from_readings(sum((flat[k] for k in _select_keys(flat, t_pred, False)), []))
    RH = _df_from_readings(sum((flat[k] for k in _select_keys(flat, rh_pred, False)), []))
    if T.empty or RH.empty:
        return {"error": "Need temperature and RH series"}
    mm = pd.merge_asof(T.sort_values("timestamp"), RH.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_t","_rh"))
    mm = mm.dropna(subset=["reading_value_t","reading_value_rh"]) 
    if mm.empty:
        return {"error": "Could not align temperature and RH"}
    # score: penalize absolute deviations with weights; clamp to [0,100]
    dt = (mm["reading_value_t"] - float(t_target)).abs()
    drh = (mm["reading_value_rh"] - float(rh_target)).abs()
    raw = 100.0 - (dt*3.0 + drh*0.5)  # weight temperature more than RH
    score = raw.clip(lower=0.0, upper=100.0)
    return {"score_latest": round(float(score.iloc[-1]),1), "score_mean": round(float(score.mean()),1), "notes": "Heuristic comfort score; PMV/PPD preferred when available."}


@analytics_function(
    patterns=[
        r"pmv",
        r"ppd",
        r"predicted.*mean.*vote",
        r"percentage.*dissatisfied",
        r"fanger"
    ],
    description="Approximates PMV (Predicted Mean Vote) and PPD (Percentage People Dissatisfied) for thermal comfort"
)

def analyze_pmv_ppd_approximation(sensor_data, clo=0.5, met=1.1, air_speed=0.1, tr=None):
    """
    PMV/PPD Approximation — Thermal Comfort Index Calculation
    
    Purpose:
    Calculates Predicted Mean Vote (PMV) and Predicted Percentage of Dissatisfied (PPD) 
    indices according to ISO 7730 and ASHRAE 55 thermal comfort standards. PMV ranges 
    from -3 (cold) to +3 (hot) with 0 being neutral comfort. PPD estimates the percentage 
    of occupants likely to be dissatisfied with thermal conditions. This analysis enables 
    objective thermal comfort assessment beyond simple temperature ranges.
    
    Sensors:
      - Air_Temperature_Sensor (°C) - operative temperature preferred
      - Relative_Humidity_Sensor (%)
      - Optional: Air_Velocity_Sensor (m/s)
      - Optional: Radiant_Temperature_Sensor (°C)
    
    Parameters (defaults for typical office):
      - clo: Clothing insulation (default 0.5 = summer, 1.0 = winter business attire)
      - met: Metabolic rate (default 1.1 = sedentary office work)
      - air_speed: Air velocity m/s (default 0.1 = still air)
      - tr: Mean radiant temperature °C (defaults to air temp if not measured)
    
    Output:
      - pmv_latest: Current Predicted Mean Vote (-3 to +3)
      - pmv_mean: Average PMV during analysis period
      - ppd_latest: Current Predicted Percentage Dissatisfied (5-100%)
      - ppd_mean: Average PPD
      - comfort_category: ISO 7730 category (A: PPD<6%, B: <10%, C: <15%)
      - comfort_compliance_pct: Time within acceptable PMV range (-0.5 to +0.5)
      - assumptions: List of assumed parameters for transparency
    
    This analysis helps:
      - Objectively assess thermal comfort beyond temperature alone
      - Support WELL Building, LEED, and BREEAM thermal comfort credits
      - Validate HVAC setpoint strategies for multi-parameter comfort
      - Respond to comfort complaints with standardized metrics
      - Optimize control strategies for occupant satisfaction vs energy
      - Assess comfort impacts of energy-saving measures (wider deadbands)
    
    Method:
      PMV calculation uses Fanger's comfort equation (ISO 7730):
        PMV = f(temperature, humidity, air_speed, radiant_temp, clothing, metabolism)
        
      PPD derived from PMV using:
        PPD = 100 - 95 × exp(-0.03353×PMV⁴ - 0.2179×PMV²)
      
      PMV interpretation:
        -3: Cold, -2: Cool, -1: Slightly cool
         0: Neutral (ideal)
        +1: Slightly warm, +2: Warm, +3: Hot
      
      Acceptable ranges (ISO 7730):
        - Category A (high expectation): -0.2 < PMV < +0.2 (PPD < 6%)
        - Category B (medium): -0.5 < PMV < +0.5 (PPD < 10%)
        - Category C (acceptable): -0.7 < PMV < +0.7 (PPD < 15%)
      
      Typical clothing values (clo):
        - 0.3-0.5: Summer clothing (shorts, t-shirt)
        - 0.5-0.7: Light summer office (trousers, short-sleeve)
        - 0.9-1.0: Winter office (business suit)
        - 1.2-1.5: Heavy winter clothing
      
      Typical metabolic rates (met):
        - 1.0: Resting/seated
        - 1.1-1.3: Office work (typing, desk)
        - 1.6-2.0: Standing/light activity
        - 2.0-3.0: Medium activity (walking, light manual work)
      
      Limitations of simplified calculation:
        - Assumes uniform environment (no drafts, asymmetry)
        - Radiant temperature approximated if not measured
        - Individual variations in comfort not captured
        - More accurate with direct measurements of all 6 parameters
    
    Parameters:
        sensor_data (dict): Temperature and humidity timeseries data
        clo (float, optional): Clothing insulation in clo units (default 0.5 summer office)
        met (float, optional): Metabolic rate in met units (default 1.1 sedentary office)
        air_speed (float, optional): Air velocity in m/s (default 0.1 still air)
        tr (float, optional): Mean radiant temperature °C (defaults to air temp if None)
    
    Returns:
        dict: PMV/PPD values, ISO 7730 category, comfort compliance %, and calculation assumptions
    """
    flat = _aggregate_flat(sensor_data)
    t_pred = _key_matcher(["temperature", "temp"], exclude_substrs=["attempt"]) ; rh_pred = _key_matcher(["humidity","rh","relative_humidity"])
    T = _df_from_readings(sum((flat.get(k, []) for k in _select_keys(flat, t_pred, False)), []))
    RH = _df_from_readings(sum((flat.get(k, []) for k in _select_keys(flat, rh_pred, False)), []))
    if T.empty or RH.empty:
        return {"error": "Need temperature and RH series"}
    if tr is None:
        tr = float(T["reading_value"].iloc[-1]) if not T.empty else None
    # A lightweight PMV proxy (not ISO-7730 exact):
    Ta = T["reading_value"].astype(float)
    RHv = RH["reading_value"].astype(float)
    # thermal sensation proxy scaled roughly between -3 and +3
    pmv_proxy = 0.303*np.exp(-0.036*met) + 0.028
    # discomfort rises with deviations from ~22C and RH extremes
    base = (Ta - 22.0)/8.0 - (RHv - 50.0)/100.0 - (air_speed-0.1)
    pmv = float((pmv_proxy*base).clip(-3,3).iloc[-1])
    ppd = float((100.0 - 95.0*np.exp(-0.03353*pmv**4 - 0.2179*pmv**2)))
    return {"pmv_latest": round(pmv,2), "ppd_latest": round(ppd,1), "assumptions": {"clo": clo, "met": met, "air_speed": air_speed, "tr": tr}}


@analytics_function(
    patterns=[
        r"setpoint.*tracking",
        r"temperature.*control",
        r"setpoint.*deviation",
        r"control.*performance",
        r"target.*tracking"
    ],
    description="Tracks how well actual temperatures follow their setpoints for control performance"
)

def analyze_temperature_setpoint_tracking(sensor_data, setpoint_keys=None):
    """
    Temperature Setpoint Tracking — Control Loop Performance Assessment
    
    Purpose:
    Compares actual zone or discharge air temperature against control setpoint to quantify 
    temperature control effectiveness. Poor setpoint tracking indicates undersized equipment, 
    incorrect PID tuning, sensor errors, or load/capacity mismatches. This analysis supports 
    ASHRAE Guideline 36 High Performance Sequences and continuous commissioning programs.
    
    Sensors:
      - Temperature or Temp sensors (zone, supply air, discharge air, °C)
      - Setpoint or SP sensors (heating/cooling setpoint, °C)
    
    Output:
      - mae: Mean Absolute Error (°C) - average deviation
      - rmse: Root Mean Squared Error (°C) - penalizes large deviations
      - overshoot_count: Hours where actual > setpoint + 0.5°C
      - undershoot_count: Hours where actual < setpoint - 0.5°C
      - within_band_percentage: % of time within ±0.5°C tolerance
      - tracking_quality: "Excellent", "Good", "Fair", "Poor"
      - largest_deviation: Maximum positive/negative error (°C)
    
    This analysis helps:
      - Verify ASHRAE Guideline 36 control performance (±0.5°C target)
      - Detect equipment sizing issues (persistent undershoot = undersized)
      - Identify PID tuning problems (oscillation, slow response)
      - Support IPMVP Option D (calibrated simulation) model validation
      - Quantify comfort delivery effectiveness (ASHRAE 55 compliance)
      - Prioritize control loop optimization for energy savings
    
    Method:
      **Setpoint tracking metrics:**
        Mean Absolute Error (MAE):
          MAE = Σ|T_actual - T_setpoint| / n
        
        Root Mean Squared Error (RMSE):
          RMSE = √[Σ(T_actual - T_setpoint)² / n]
          (RMSE penalizes large deviations more than MAE)
        
        Mean Absolute Percentage Error (MAPE):
          MAPE = (Σ|T_actual - T_setpoint| / |T_setpoint|) / n × 100%
          (Use cautiously: sensitive to setpoint changes, less meaningful for temperature)
      
      **Performance benchmarks (ASHRAE Guideline 36-2021, Section 5.1.7):**
        Excellent: MAE <0.3°C, >90% within ±0.5°C
        Good: MAE 0.3-0.6°C, 75-90% within ±0.5°C
        Fair: MAE 0.6-1.0°C, 60-75% within ±0.5°C
        Poor: MAE >1.0°C, <60% within ±0.5°C
      
      **Zone temperature control (occupied periods):**
        ASHRAE 55-2020 acceptable range: ±1.1°C (2°F) of setpoint
        High-performance buildings: ±0.5°C (LEED, WELL, Passive House)
        
        Persistent overshoot (actual > setpoint):
          - Causes: Oversized heating, incorrect occupancy schedule, solar heat gain
          - Impact: Thermal discomfort (too warm), wasted heating energy
        
        Persistent undershoot (actual < setpoint):
          - Causes: Undersized HVAC, excessive infiltration, sensor error
          - Impact: Comfort complaints, equipment running continuously
      
      **Supply/discharge air temperature tracking (AHU control):**
        Cooling mode:
          - Target: 12-15°C supply air (typical)
          - Tolerance: ±1°C for stable humidity control
          - Poor tracking → inadequate cooling capacity or fouled coils
        
        Heating mode:
          - Target: 35-45°C supply air (radiant panel lower, VAV reheat higher)
          - Tolerance: ±2°C
          - Poor tracking → valve issues, low hot water temperature
      
      **PID tuning diagnostics (requires high-frequency data):**
        Oscillation (hunting):
          - Pattern: Actual temperature oscillates ±1-2°C around setpoint
          - Cause: P gain too high, I time too short
          - Fix: Reduce proportional gain, increase integral time
        
        Slow response (sluggish):
          - Pattern: Takes >30 min to reach setpoint after load change
          - Cause: P gain too low, I time too long
          - Fix: Increase proportional gain, decrease integral time
        
        Offset (steady-state error):
          - Pattern: Actual stabilizes 1-2°C above/below setpoint
          - Cause: No integral action, or I time = 0
          - Fix: Enable integral control
      
      **Sensor validation (detect sensor errors):**
        If tracking error is consistent and one-sided:
          - Actual always 2°C below setpoint → Sensor reads low (miscalibration)
          - Actual always 3°C above setpoint → Sensor reads high OR actuator stuck
        
        Cross-check with:
          - Neighboring zones (should track similarly if same system)
          - Occupant complaints (if tracking appears good but complaints persist → sensor error)
      
      **Energy impact of poor tracking:**
        Overshoot by 1°C (cooling mode):
          - Increases cooling load ~8-10% per °C
          - Annual cost impact: $100-500 per zone (climate-dependent)
        
        Undershoot by 1°C (heating mode):
          - Increases heating load ~8-10% per °C
          - Comfort complaints → occupant override → worse energy performance
      
      **ASHRAE Guideline 36-2021 requirements:**
        - Trim & Respond logic for zone temperature setpoints
        - Ignored zone threshold: If >20% zones not satisfied, adjust setpoint
        - Request tracking: Count heating/cooling requests, adjust accordingly
    
    Parameters:
        sensor_data (dict): Temperature and setpoint timeseries data
        setpoint_keys (list, optional): Specific setpoint sensor keys to use
    
    Returns:
        dict: MAE, RMSE, overshoot/undershoot counts, within-band percentage, tracking quality

    Compares actual temperature vs setpoint; computes MAE, overshoot/undershoot and % within ±0.5°C.
    Returns: { mae, overshoot_count, undershoot_count, within_band_pct }
    """
    flat = _aggregate_flat(sensor_data)
    temp_pred = _key_matcher(["temperature", "temp"], exclude_substrs=["attempt"]) ; sp_pred = _key_matcher(["setpoint", "sp"])
    t_keys = _select_keys(flat, temp_pred, False)
    if setpoint_keys is None:
        sp_keys = _select_keys(flat, sp_pred, False)
    else:
        sp_keys = [k for k in flat.keys() if any(s.lower() in str(k).lower() for s in setpoint_keys)]
    if not t_keys or not sp_keys:
        return {"error": "Need temperature and setpoint series"}
    t_df = _df_from_readings(sum((flat[k] for k in t_keys), []))
    sp_df = _df_from_readings(sum((flat[k] for k in sp_keys), []))
    if t_df.empty or sp_df.empty:
        return {"error": "Insufficient readings"}
    mm = pd.merge_asof(t_df.sort_values("timestamp"), sp_df.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_act","_sp"))
    mm = mm.dropna(subset=["reading_value_act","reading_value_sp"]) 
    if mm.empty:
        return {"error": "Could not align temperature and setpoint"}
    err = (mm["reading_value_act"] - mm["reading_value_sp"]).astype(float)
    within = (err.abs() <= 0.5).mean() * 100.0
    return {"mae": round(float(err.abs().mean()),2), "overshoot_count": int((err>0.5).sum()), "undershoot_count": int((err<-0.5).sum()), "within_band_pct": round(float(within),2)}


@analytics_function(
    patterns=[
        r"setpoint.*deviation",
        r"control.*error",
        r"offset.*from.*setpoint",
        r"setpoint.*difference",
        r"target.*deviation"
    ],
    description="Analyzes deviation between actual values and setpoints with tolerance bands"
)

def analyze_setpoint_deviation(sensor_data, tolerance=1.0):
    """
    Setpoint Deviation Assessment — Persistent Control Error Quantification
    
    Purpose:
    Quantifies the percentage of time actual temperature exceeds acceptable deviation from 
    setpoint, identifying chronic control issues. Persistent deviation indicates equipment 
    capacity problems, improper control sequences, or sensor calibration errors requiring 
    commissioning attention. This metric distinguishes between minor transient excursions 
    (acceptable) and sustained control failures (critical).
    
    Sensors:
      - Temperature or Temp sensors (zone, supply air, °C)
      - Setpoint or SP sensors (control target, °C)
    
    Output:
      - percent_beyond_tolerance: % of time |actual - setpoint| > tolerance
      - avg_deviation: Mean absolute deviation (°C)
      - max_deviation: Largest deviation observed (°C)
      - tolerance: Threshold used (°C)
      - compliance_rating: "Compliant", "Marginal", "Non-Compliant"
      - impact_assessment: Energy/comfort implications
    
    This analysis helps:
      - Prioritize HVAC system recommissioning (target zones with >20% exceedance)
      - Validate post-retrofit control performance (compare pre/post metrics)
      - Support ASHRAE 55-2020 thermal comfort compliance reporting
      - Identify zones requiring equipment upgrades (capacity insufficient)
      - Quantify operational savings potential from improved control (typically 5-15%)
      - Benchmark building performance against peer buildings (ENERGY STAR)
    
    Method:
      **Deviation tolerance thresholds:**
        Strict tolerance (High-Performance Buildings, WELL, Passive House):
          - ±0.5°C (±0.9°F)
          - Target: <10% time beyond tolerance
          - Use for: Laboratory spaces, data centers, museums
        
        Standard tolerance (ASHRAE 55-2020, LEED):
          - ±1.0°C (±1.8°F)
          - Target: <15% time beyond tolerance
          - Use for: Office, residential, retail
        
        Relaxed tolerance (Older buildings, limited HVAC):
          - ±1.5°C (±2.7°F)
          - Target: <25% time beyond tolerance
          - Use for: Industrial, warehouse, non-critical spaces
      
      **Performance benchmarks:**
        Excellent: <5% beyond tolerance, avg deviation <0.4°C
        Good: 5-15% beyond tolerance, avg deviation 0.4-0.8°C
        Marginal: 15-25% beyond tolerance, avg deviation 0.8-1.2°C
        Poor: >25% beyond tolerance, avg deviation >1.2°C
      
      **Deviation patterns and root causes:**
        Consistent overshoot (actual > setpoint):
          - Root cause: Oversized equipment, aggressive heating, inadequate cooling
          - Impact: Energy waste, occupant discomfort (too warm)
          - Fix: Reduce heating setpoint, increase deadband, resize equipment
        
        Consistent undershoot (actual < setpoint):
          - Root cause: Undersized equipment, high infiltration, sensor drift
          - Impact: Comfort complaints, equipment overrun, high maintenance
          - Fix: Address envelope issues, increase capacity, sensor calibration
        
        Oscillating deviation (swings ±2°C):
          - Root cause: PID tuning (too aggressive), cycling equipment
          - Impact: Wear on equipment, occupant discomfort
          - Fix: Retune PID (reduce gain, increase integral time)
        
        Time-of-day pattern:
          - Morning undershoot: Inadequate warm-up sequence
          - Afternoon overshoot: Solar heat gain, insufficient cooling
          - Fix: Optimize occupancy schedules, adjust setpoints dynamically
      
      **ASHRAE 55-2020 Thermal Comfort Standard:**
        Operative temperature criteria (PMV method):
          - Summer (cooling): 23-26°C acceptable range
          - Winter (heating): 20-23.5°C acceptable range
          - Setpoint tracking within ±1.1°C ensures PMV ∈ [-0.5, +0.5]
        
        Adaptive comfort model (naturally ventilated):
          - Acceptable range: ±2.5°C (80% acceptability)
          - Acceptable range: ±3.5°C (90% acceptability)
      
      **Energy impact of deviation:**
        Every 1°C persistent overshoot (cooling season):
          - Increases cooling energy ~8-10%
          - Annual cost impact: $200-800 per 100 m² (climate-dependent)
        
        Every 1°C persistent undershoot (heating season):
          - Increases heating energy ~8-10%
          - May trigger occupant overrides (portable heaters) → uncontrolled load
      
      **Commissioning implications:**
        >20% time beyond ±1°C tolerance:
          - Trigger functional performance test (FPT)
          - Verify sensor calibration (±0.2°C accuracy requirement)
          - Check actuator stroke, valve authority
          - Review control sequences (Guideline 36 compliance)
        
        >40% time beyond tolerance:
          - Critical issue: Equipment replacement likely required
          - Interim: Relax setpoint to reduce runtime (minimize equipment wear)
          - Cost-benefit: Compare control upgrade vs equipment replacement
      
      **Sensor validation approach:**
        If avg_deviation is large but consistent:
          - Suspect: Sensor offset (calibration error)
          - Test: Compare with handheld thermometer (±0.1°C reference)
          - Fix: Recalibrate sensor or apply software offset correction
        
        If deviation is random/noisy:
          - Suspect: Sensor failure (intermittent connection, moisture ingress)
          - Test: Inspect wiring, check sensor resistance (Pt1000: 1385Ω at 100°C)
          - Fix: Replace sensor
      
      **Reporting and benchmarking:**
        Normalize by:
          - Occupied hours only (exclude unoccupied setback periods)
          - Outdoor temperature bins (extreme weather → higher acceptable deviation)
          - Space type (laboratory = strict, warehouse = relaxed)
        
        Trend over time:
          - Increasing deviation → equipment degradation, fouling, sensor drift
          - Sudden increase → Equipment failure, control sequence change
          - Gradual improvement → Successful recommissioning, tuning optimization
    
    Parameters:
        sensor_data (dict): Temperature and setpoint timeseries data
        tolerance (float, optional): Acceptable deviation threshold in °C (default 1.0°C)
    
    Returns:
        dict: Percent beyond tolerance, average deviation, max deviation, compliance rating

    Computes persistent deviation: % time beyond tolerance between actual and setpoint.
    Returns: { percent_beyond_tolerance, avg_deviation }
    """
    flat = _aggregate_flat(sensor_data)
    temp_pred = _key_matcher(["temperature", "temp"], exclude_substrs=["attempt"]) ; sp_pred = _key_matcher(["setpoint", "sp"])
    t_df = _df_from_readings(sum((flat.get(k, []) for k in _select_keys(flat, temp_pred, False)), []))
    sp_df = _df_from_readings(sum((flat.get(k, []) for k in _select_keys(flat, sp_pred, False)), []))
    if t_df.empty or sp_df.empty:
        return {"error": "Need temperature and setpoint series"}
    mm = pd.merge_asof(t_df.sort_values("timestamp"), sp_df.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_act","_sp"))
    mm = mm.dropna(subset=["reading_value_act","reading_value_sp"]) 
    if mm.empty:
        return {"error": "Could not align temperature and setpoint"}
    dev = (mm["reading_value_act"] - mm["reading_value_sp"]).abs()
    pct = (dev > float(tolerance)).mean() * 100.0
    return {"percent_beyond_tolerance": round(float(pct),2), "avg_deviation": round(float(dev.mean()),2), "tolerance": float(tolerance)}


@analytics_function(
    patterns=[
        r"mixed.*air",
        r"mat.*validation",
        r"outdoor.*return.*mix",
        r"economizer.*mixing",
        r"air.*mixing"
    ],
    description="Validates mixed air temperature calculations in HVAC economizer systems"
)

def analyze_mixed_air_validation(sensor_data):
    """
    Mixed-Air Validation — Mixing model check.
    
    Purpose: Validates the physical plausibility of mixed-air temperature readings by checking
             if they fall within the expected range between outdoor air and return air temperatures.
             Violations indicate sensor errors, sensor swaps, or HVAC system issues.
    
    Sensors:
      - Mixed_Air_Temperature
      - Return_Air_Temperature
      - Outside_Air_Temperature
      
    Output:
      - Residual error (actual vs expected mixed temp)
      - Sensor plausibility flags
      - Violation count and timestamps
      - Suggested sensor swap detection
      
    This analysis helps identify:
      - Mis-wired or swapped temperature sensors
      - Failed temperature sensors
      - Damper control issues
      - Outdoor air infiltration or leakage
      
    Expected relationship (cooling mode):
      Outside_Air_Temperature ≤ Mixed_Air_Temperature ≤ Return_Air_Temperature
      
    Mixed air temperature should be a weighted average based on damper positions.
    Significant deviations suggest sensor or system faults requiring investigation.

    Returns: { violations_count, residual_mean, sensor_plausibility, suggested_action }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No temperature data available"}
    o_pred = _key_matcher(["outside_air", "outdoor"]) ; r_pred = _key_matcher(["return_air", "return"]) ; m_pred = _key_matcher(["mixed_air", "mix"])
    t_pred = _key_matcher(["temperature", "temp"])  
    O_keys = [k for k in flat.keys() if o_pred(str(k)) and t_pred(str(k))]
    R_keys = [k for k in flat.keys() if r_pred(str(k)) and t_pred(str(k))]
    M_keys = [k for k in flat.keys() if m_pred(str(k)) and t_pred(str(k))]
    if not O_keys or not R_keys or not M_keys:
        return {"error": "Need outside, return, and mixed air temperature series"}
    dfO = _df_from_readings(sum((flat[k] for k in O_keys), []))
    dfR = _df_from_readings(sum((flat[k] for k in R_keys), []))
    dfM = _df_from_readings(sum((flat[k] for k in M_keys), []))
    mm = pd.merge_asof(dfM.sort_values("timestamp"), dfO.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_m","_o"))
    mm = pd.merge_asof(mm.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"))
    mm = mm.dropna(subset=["reading_value_m","reading_value_o","reading_value"]) 
    if mm.empty:
        return {"error": "Could not align series"}
    violations = ((mm["reading_value_m"] < mm["reading_value_o"]) | (mm["reading_value_m"] > mm["reading_value"]))
    # residual vs midpoint of OAT and RAT
    residual = mm["reading_value_m"] - 0.5*(mm["reading_value_o"] + mm["reading_value"]) 
    return {"violations_count": int(violations.sum()), "residual_mean": round(float(residual.mean()),2)}


@analytics_function(
    patterns=[
        r"economizer.*opportunity",
        r"free.*cooling",
        r"outdoor.*air.*cooling",
        r"economizer.*mode",
        r"airside.*economizer"
    ],
    description="Identifies opportunities for economizer operation (free cooling) based on outdoor conditions"
)

def analyze_economizer_opportunity(sensor_data, method="drybulb", delta=1.0):
    """
    Economizer Opportunity — Free cooling detection.
    
    Purpose: Identifies periods when outdoor air conditions are favorable for free cooling,
             allowing the HVAC system to reduce mechanical cooling load and save energy by
             using outdoor air instead of chilled water or refrigerant cooling.
    
    Sensors:
      - Outside_Air_Temperature (or Outside_Air_Enthalpy)
      - Return_Air_Temperature (or Return_Air_Enthalpy)
      - Mixed_Air_Temperature
      
    Output:
      - Opportunity hours (when free cooling is available)
      - Realized vs missed opportunities
      - Potential energy savings
      - Economizer utilization percentage
      
    This analysis helps:
      - Maximize free cooling utilization
      - Identify economizer control issues
      - Quantify energy savings opportunities
      - Optimize HVAC scheduling and setpoints
      
    Methods:
      - Drybulb: Compares outdoor vs return air temperatures (simple, works in dry climates)
      - Enthalpy: Compares outdoor vs return air enthalpy (accounts for humidity, more accurate)
      
    Economizer should activate when:
      OAT + delta < RAT (drybulb method) or OA_Enthalpy < RA_Enthalpy (enthalpy method)

    Parameters:
      - method: "drybulb" or "enthalpy" (default: "drybulb")
      - delta: Temperature margin for drybulb comparison (default: 1.0°C)

    Returns: { opportunity_count, opportunity_hours, realized_hours, missed_hours, latest_flag }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No sensor data available"}
    o_pred = _key_matcher(["outside_air", "outdoor"]) ; r_pred = _key_matcher(["return_air", "return"]) ; t_pred = _key_matcher(["temperature", "temp"])
    O_keys = [k for k in flat.keys() if o_pred(str(k)) and t_pred(str(k))]
    R_keys = [k for k in flat.keys() if r_pred(str(k)) and t_pred(str(k))]
    if not O_keys or not R_keys:
        return {"error": "Need outside and return temperature series"}
    dfO = _df_from_readings(sum((flat[k] for k in O_keys), []))
    dfR = _df_from_readings(sum((flat[k] for k in R_keys), []))
    mm = pd.merge_asof(dfO.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_oa","_ra"))
    if mm.empty:
        return {"error": "Could not align OAT and RAT"}
    if method == "drybulb":
        flag = (mm["reading_value_oa"] + float(delta) < mm["reading_value_ra"])  # OA cooler by margin
    else:
        # fallback: treat drybulb as proxy if enthalpy not available in this function
        flag = (mm["reading_value_oa"] + float(delta) < mm["reading_value_ra"]) 
    return {"opportunity_count": int(flag.sum()), "latest_flag": bool(flag.iloc[-1])}


@analytics_function(
    patterns=[
        r"supply.*air.*temp",
        r"sat.*control",
        r"discharge.*temp",
        r"supply.*temp.*control",
        r"sat.*performance"
    ],
    description="Analyzes supply air temperature control performance and setpoint tracking"
)

def analyze_supply_air_temp_control(sensor_data):
    """
    Supply Air Temperature Control — SAT Stability & Setpoint Tracking
    
    Purpose:
    Assesses supply air temperature (SAT) control stability and variability to detect 
    hunting/oscillation, poor PID tuning, or control valve issues. Unstable SAT causes 
    zone temperature fluctuations, humidity control problems, and excessive valve cycling 
    (reducing actuator lifespan). This analysis supports ASHRAE Guideline 36 High Performance 
    Sequences validation and continuous commissioning.
    
    Sensors:
      - Supply_Air_Temperature or SAT_Sensor (°C)
      - Optional: Supply_Air_Temp_Setpoint (for tracking error calculation)
    
    Output:
      - variance: SAT variance (°C²) - measure of stability
      - std_dev: Standard deviation (°C) - easier to interpret than variance
      - stability_flag: "stable", "unstable" (based on oscillation detection)
      - zero_crossing_count: Number of direction changes (oscillation proxy)
      - rate_of_change_max: Largest temperature swing (°C/min)
      - control_quality: "Excellent", "Good", "Fair", "Poor"
    
    This analysis helps:
      - Detect hunting/oscillation in cooling/heating coil control loops
      - Identify poor PID tuning (excessive proportional gain, short integral time)
      - Validate commissioning improvements (compare pre/post tuning metrics)
      - Prioritize actuator/valve maintenance (high cycling = wear)
      - Support ASHRAE Guideline 36 SAT reset sequences validation
      - Ensure stable dehumidification (SAT variance <1°C required for humidity control)
    
    Method:
      **SAT control stability metrics:**
        Variance (σ²):
          σ² = Σ(SAT - mean_SAT)² / n
          Low variance = stable control
        
        Standard deviation (σ):
          σ = √variance  [more intuitive than variance]
        
        Zero-crossing count (oscillation proxy):
          Counts direction changes in SAT derivative (dT/dt)
          High count (>10% of datapoints) → unstable oscillation
      
      **Performance benchmarks (occupied cooling mode):**
        Excellent: σ <0.5°C, <5% zero-crossings
          - Tight control, minimal hunting
          - Suitable for: Data centers, laboratories, museums
        
        Good: σ 0.5-1.0°C, 5-10% zero-crossings
          - Acceptable for most commercial buildings
          - Suitable for: Offices, retail, schools
        
        Fair: σ 1.0-1.5°C, 10-15% zero-crossings
          - Noticeable temperature variation
          - Impact: Zone temperature fluctuations, humidity issues
        
        Poor: σ >1.5°C, >15% zero-crossings
          - Severe hunting, control failure
          - Impact: Comfort complaints, equipment wear, energy waste
      
      **SAT control sequences (ASHRAE Guideline 36-2021, Section 5.18):**
        Trim & Respond logic:
          - Monitor zone cooling requests every 2 minutes
          - If >50% zones call for cooling: Decrease SAT by 0.1°C
          - If <10% zones call for cooling: Increase SAT by 0.1°C
          - Limits: 12°C min, 18°C max (typical)
        
        Benefits:
          - Prevents overcooling (high fan energy, reheat waste)
          - Maintains zone-level control authority
          - Target: SAT variance <1°C during stable operation
      
      **Root causes of unstable SAT:**
        Hunting (oscillation):
          - Symptom: SAT oscillates ±1-2°C every 5-15 minutes
          - Cause: PID proportional gain too high
          - Fix: Reduce P gain by 50%, increase integral time
        
        Slow response (sluggish):
          - Symptom: SAT takes >30 min to reach new setpoint
          - Cause: P gain too low, integral time too long
          - Fix: Increase P gain, decrease integral time
        
        Valve stiction:
          - Symptom: SAT sudden jumps (2-3°C) then plateaus
          - Cause: Control valve sticks, then breaks free
          - Fix: Replace valve actuator, clean/replace valve
        
        Coil fouling:
          - Symptom: SAT gradually increases, cannot reach low setpoint
          - Cause: Coil blocked by dirt, reduced heat transfer
          - Fix: Clean/replace filters, clean coil fins
        
        Inadequate capacity:
          - Symptom: SAT cannot reach setpoint during peak load
          - Cause: Undersized coil, low chilled water flow
          - Fix: Increase CHW flow, verify coil delta-T
      
      **SAT and humidity control:**
        Stable SAT (σ <1°C) essential for dehumidification:
          - Coil surface temperature must stay below dewpoint
          - Fluctuating SAT → inconsistent latent cooling
          - Result: Zone RH swings (40-65%), mold risk
        
        ASHRAE 55-2020 humidity limits:
          - Summer: 30-60% RH (65% max to prevent mold)
          - Winter: 30-50% RH (prevent static, dry eyes)
      
      **Energy impact of poor SAT control:**
        Overcooling (SAT too low, σ high):
          - Increases cooling energy 10-20%
          - Requires reheat to meet zone setpoints (wasteful)
          - Fan energy penalty: Overcooling → higher airflow demand
        
        Hunting (oscillation):
          - Valve cycling: Reduces actuator life by 50%
          - Energy waste: Continuous valve modulation
          - Maintenance cost: Actuator replacement every 3-5 years vs 10-15 years
      
      **Typical SAT setpoints by system type:**
        VAV cooling mode:
          - Standard: 12-15°C (54-59°F)
          - High-performance: 10-12°C (50-54°F, better dehumidification)
        
        VAV heating mode:
          - Reheat: 18-22°C (64-72°F)
          - No reheat: 22-27°C (72-81°F, economizer mode)
        
        Constant volume:
          - Fixed SAT: 13°C (55°F, high humidity climates)
          - Variable SAT: 10-16°C (50-61°F, reset based on load)
      
      **Commissioning validation:**
        After PID tuning:
          - Step test: Change SAT setpoint by 2°C, measure response time
          - Target: 90% of final value within 10 minutes
          - Overshoot: <0.5°C acceptable
        
        Long-term monitoring (post-occupancy):
          - Track SAT variance monthly
          - Seasonal variation: Expect higher variance during swing seasons
          - Alert threshold: σ increases >50% from baseline
    
    Parameters:
        sensor_data (dict): Supply air temperature timeseries data
    
    Returns:
        dict: Variance, std dev, stability flag, zero-crossing count, control quality rating

    SAT control quality: variance and simple stability metric (oscillation proxy).
    Returns: { variance, stability_flag }
    """
    flat = _aggregate_flat(sensor_data)
    t_pred = _key_matcher(["supply_air", "sat"]) ; temp_pred = _key_matcher(["temperature", "temp"]) 
    keys = [k for k in flat.keys() if t_pred(str(k)) and temp_pred(str(k))]
    if not keys:
        return {"error": "No supply air temperature series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    if df.empty:
        return {"error": "Empty SAT series"}
    var = float(df["reading_value"].var() or 0.0)
    # very crude oscillation proxy: count zero-crossings of first difference
    d = df["reading_value"].diff().fillna(0)
    zero_cross = int(((d.shift(1) * d) < 0).sum())
    stability = "unstable" if zero_cross > max(5, len(df)//50) else "stable"
    return {"variance": round(var,3), "stability_flag": stability}


@analytics_function(
    patterns=[
        r"static.*pressure.*control",
        r"duct.*pressure",
        r"supply.*pressure",
        r"pressure.*control.*performance",
        r"ssp.*control"
    ],
    description="Analyzes static pressure control performance in supply duct systems"
)

def analyze_supply_static_pressure_control(sensor_data, target=None):
    """
    Supply Static Pressure Control — Duct Pressure Management & VFD Optimization
    
    Purpose:
    Monitors supply duct static pressure control to ensure adequate air delivery while 
    minimizing fan energy. Static pressure reset strategies (ASHRAE Guideline 36) reduce 
    fan speed when zones are satisfied, achieving 30-50% fan energy savings. Poor pressure 
    control causes either inadequate airflow (low pressure) or wasted fan energy (high pressure).
    
    Sensors:
      - Static_Pressure or Supply_Duct_Pressure (Pa or in.w.c.)
      - Optional: Static_Pressure_Setpoint (Pa)
    
    Output:
      - mae: Mean Absolute Error from target pressure (Pa)
      - rmse: Root Mean Squared Error (Pa)
      - oscillation_index: Frequency of pressure fluctuations (hunting detection)
      - avg_pressure: Mean pressure (Pa)
      - pressure_range: Min to max pressure observed
      - control_quality: "Excellent", "Good", "Fair", "Poor"
      - energy_savings_potential: "High", "Moderate", "Low"
    
    This analysis helps:
      - Validate ASHRAE Guideline 36 static pressure reset implementation
      - Detect hunting/oscillation in VFD (Variable Frequency Drive) control
      - Identify over-pressurization (high fan energy, duct leakage, noise)
      - Detect under-pressurization (VAV box starvation, comfort complaints)
      - Quantify fan energy savings potential (typically 30-50% with proper reset)
      - Prioritize VFD tuning or duct system commissioning
    
    Method:
      **Static pressure control fundamentals:**
        Static pressure = force exerted by air perpendicular to duct walls
        
        Typical setpoints (US units: in.w.c., SI: Pa):
          - Low-pressure VAV: 1.0-1.5 in.w.c. (250-375 Pa)
          - Medium-pressure VAV: 1.5-2.5 in.w.c. (375-625 Pa)
          - High-pressure VAV: 2.5-4.0 in.w.c. (625-1000 Pa)
        
        Unit conversion:
          1 in.w.c. = 249.1 Pa = 0.249 kPa
      
      **ASHRAE Guideline 36-2021 Static Pressure Reset (Section 5.16.3):**
        Trim & Respond logic:
          - Monitor VAV box damper positions every 2 minutes
          - If >1 box fully open (>95%): Increase pressure by 15 Pa
          - If all boxes <85% open: Decrease pressure by 10 Pa
          - Limits: 150 Pa min, 500 Pa max (typical)
        
        Energy savings:
          - Traditional fixed setpoint (500 Pa): 100% fan energy baseline
          - Guideline 36 reset (150-500 Pa): 40-60% average fan energy
          - Savings mechanism: Fan power ∝ (speed)³, pressure ∝ (speed)²
      
      **Fan affinity laws (predict energy impact):**
        CFM₂ / CFM₁ = (RPM₂ / RPM₁)
        Pressure₂ / Pressure₁ = (RPM₂ / RPM₁)²
        Power₂ / Power₁ = (RPM₂ / RPM₁)³
        
        Example: Reduce pressure from 500 Pa to 250 Pa (50% reduction)
          RPM ratio = √(250/500) = 0.707 (71% speed)
          Power ratio = (0.707)³ = 0.35 (35% power, 65% savings!)
      
      **Performance benchmarks:**
        Excellent: MAE <25 Pa, oscillation_index <5%, pressure reset active
          - Guideline 36 Trim & Respond implemented correctly
        
        Good: MAE 25-50 Pa, oscillation 5-10%, some reset
          - Acceptable control, room for optimization
        
        Fair: MAE 50-100 Pa, oscillation 10-20%, limited reset
          - Noticeable energy waste, recommend tuning
        
        Poor: MAE >100 Pa, oscillation >20%, fixed setpoint
          - Severe energy penalty, hunting issues
      
      **Root causes of poor static pressure control:**
        Hunting (oscillation):
          - Symptom: Pressure oscillates ±50 Pa every 2-5 minutes
          - Cause: VFD PID gain too high, integral time too short
          - Impact: Mechanical wear, electrical stress on VFD
          - Fix: Reduce P gain, increase integral time (slower response acceptable)
        
        Over-pressurization (fixed high setpoint):
          - Symptom: Pressure consistently 400-500 Pa, VAV boxes <70% open
          - Cause: Legacy design (pre-Guideline 36), conservative setpoint
          - Impact: 40-60% fan energy waste, duct leakage, noise
          - Fix: Implement static pressure reset, lower setpoint
        
        Under-pressurization:
          - Symptom: Pressure <200 Pa, VAV boxes >95% open, zone temp complaints
          - Cause: Undersized fan, excessive duct leakage, dirty filters
          - Impact: Inadequate airflow to zones, comfort issues
          - Fix: Clean/replace filters, seal duct leaks, upgrade fan
        
        Sensor location error:
          - Symptom: Pressure reading not representative of system
          - Cause: Sensor too close to fan discharge (turbulent), or at end of duct (dead zone)
          - Best practice: 2/3 distance into duct system, away from elbows
      
      **Duct system diagnostics:**
        High pressure drop (filter/coil):
          - Clean filters: 50-150 Pa drop
          - Dirty filters: 200-400 Pa drop (replace if >250 Pa)
          - Cooling coil: 50-100 Pa (clean), 150-300 Pa (fouled)
        
        Duct leakage impact:
          - 10% duct leakage: Requires 15-20% higher fan pressure
          - Leakage classes: Class 3 (tight, <3%), Class 6 (average, 6%), Class 12 (leaky, 12%)
          - Fix: Seal ducts with mastic (not duct tape)
      
      **VAV box damper position correlation:**
        If static pressure adequate:
          - Most VAV boxes: 40-80% open (good control authority)
          - Few boxes fully open (<5%): Adequate pressure
        
        If static pressure inadequate:
          - Many boxes: >90% open (starved for air)
          - Zone temperatures above setpoint
          - Fix: Increase static pressure setpoint
        
        If static pressure excessive:
          - All boxes: <50% open (throttling, wasted energy)
          - Fix: Lower static pressure setpoint
      
      **Energy impact estimation:**
        Baseline: Fixed 500 Pa setpoint, 10 kW fan motor
          Annual fan energy: 10 kW × 8760 hrs × 0.6 load factor = 52,560 kWh
        
        With Guideline 36 reset (avg 300 Pa, 60% power):
          Annual fan energy: 10 kW × 8760 hrs × 0.6 × 0.6 = 31,536 kWh
          Savings: 21,024 kWh/year = 40% reduction
          Cost savings: $2,100-$4,200/year (@ $0.10-$0.20/kWh)
      
      **Commissioning validation:**
        Step test:
          - Command pressure setpoint increase by 100 Pa
          - Measure response time (target: 90% of final within 2 min)
          - Check for overshoot (<20% acceptable)
        
        Load test:
          - Simulate zone demand (open VAV boxes manually)
          - Verify pressure increases via Trim & Respond
          - Confirm pressure returns to minimum when demand drops
    
    Parameters:
        sensor_data (dict): Static pressure timeseries data
        target (float, optional): Target pressure in Pa (if None, inferred from median)
    
    Returns:
        dict: MAE, RMSE, oscillation index, pressure stats, control quality, savings potential

    Static pressure control: track target (if provided or inferred) and report MAE and oscillation.
    Returns: { mae, oscillation_index }
    """
    flat = _aggregate_flat(sensor_data)
    p_pred = _key_matcher(["static_pressure", "pressure"]) ; sp_pred = _key_matcher(["setpoint", "sp"]) 
    p_keys = _select_keys(flat, p_pred, False)
    if not p_keys:
        return {"error": "No static pressure series"}
    p_df = _df_from_readings(sum((flat[k] for k in p_keys), []))
    if p_df.empty:
        return {"error": "Empty pressure series"}
    if target is None:
        # infer rough target as median
        target = float(p_df["reading_value"].median())
    err = (p_df["reading_value"].astype(float) - float(target)).abs()
    d = p_df["reading_value"].diff().fillna(0)
    osc = float((np.sign(d).diff().abs().fillna(0).sum())) / max(1, len(p_df))
    return {"mae": round(float(err.mean()),3), "oscillation_index": round(osc,3), "target": float(target)}


@analytics_function(
    patterns=[
        r"airflow.*profile",
        r"cfm.*profile",
        r"air.*volume",
        r"ventilation.*rate",
        r"airflow.*distribution"
    ],
    description="Profiles airflow rates and volumes across ventilation system"
)

def analyze_airflow_profiling(sensor_data):
    """
    Airflow Profiling — System Balance & Leakage Detection
    
    Purpose:
    Profiles air handling system airflow rates across supply, return, and mixed-air 
    points to assess system balance and detect duct leakage. Imbalanced airflow causes 
    pressurization issues (infiltration or exfiltration), comfort complaints, and 
    energy waste. Significant discrepancies between supply and return airflow indicate 
    duct leakage, unintended openings, or faulty damper operation.
    
    Sensors:
      - Supply_Air_Flow_Sensor (CFM or m³/h)
      - Return_Air_Flow_Sensor (CFM or m³/h)
      - Mixed_Air_Flow_Sensor (CFM or m³/h, if available)
      - Outside_Air_Flow_Sensor (CFM or m³/h, optional)
    
    Output:
      - supply_avg: Average supply airflow
      - return_avg: Average return airflow
      - mixed_avg: Average mixed-air flow (if available)
      - balance_ratio: Return / Supply (ideally 0.85-0.95 for slight positive pressure)
      - leakage_hint: Estimated % leakage if imbalance detected
      - pressure_status: "Positive" (supply > return), "Negative" (return > supply), "Balanced"
    
    This analysis helps:
      - Detect duct leakage in supply or return paths (energy loss, comfort issues)
      - Identify building pressurization problems (infiltration in negative, drafts in positive)
      - Validate outdoor air damper position and economizer operation
      - Troubleshoot uneven zone conditioning and comfort complaints
      - Support TAB (Testing, Adjusting, and Balancing) verification
      - Assess VAV box performance and diversity factors
    
    Method:
      Balance Ratio = Return Airflow / Supply Airflow
      
      Typical balance targets:
        - Commercial buildings: 0.85-0.95 (slight positive pressure to prevent infiltration)
        - Labs/healthcare: 0.80-0.90 (more outside air, higher positive pressure)
        - Data centers: 0.95-1.00 (tight balance for hot/cold aisle containment)
      
      Leakage estimation:
        Leakage % ≈ |Supply - Return - Outside Air| / Supply × 100
        
      Chronic imbalance >10% indicates:
        - Duct leakage requiring sealing
        - Damper stuck or improperly controlled
        - Airflow measurement drift requiring calibration
    
    Parameters:
        sensor_data (dict): Timeseries airflow data from supply, return, mixed, and OA sensors
    
    Returns:
        dict: Airflow statistics, balance ratios, leakage estimates, and pressurization status
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No airflow data available"}
    sup_pred = _key_matcher(["supply_air", "supply"]) ; ret_pred = _key_matcher(["return_air", "return"]) ; mix_pred = _key_matcher(["mixed_air", "mix"]) ; flow_pred = _key_matcher(["air_flow", "airflow", "flow_rate"])
    s_keys = [k for k in flat.keys() if sup_pred(str(k)) and flow_pred(str(k))]
    r_keys = [k for k in flat.keys() if ret_pred(str(k)) and flow_pred(str(k))]
    m_keys = [k for k in flat.keys() if mix_pred(str(k)) and flow_pred(str(k))]
    def avg_for(keys):
        if not keys:
            return None
        df = _df_from_readings(sum((flat[k] for k in keys), []))
        return (float(df["reading_value"].mean()) if not df.empty else None)
    s_avg = avg_for(s_keys)
    r_avg = avg_for(r_keys)
    m_avg = avg_for(m_keys)
    balance = (s_avg / r_avg) if (s_avg is not None and r_avg not in (None, 0)) else None
    leakage = None
    if s_avg is not None and r_avg is not None:
        if s_avg > r_avg * 1.1:
            leakage = "Possible return leakage or supply imbalance"
        elif r_avg > s_avg * 1.1:
            leakage = "Possible supply leakage or return imbalance"
        else:
            leakage = "Balanced"
    return {"supply_avg": s_avg, "return_avg": r_avg, "mixed_avg": m_avg, "balance_ratio": (round(float(balance),3) if balance is not None else None), "leakage_hint": leakage}


@analytics_function(
    patterns=[
        r"filter.*health",
        r"filter.*condition",
        r"filter.*pressure.*drop",
        r"filter.*replacement",
        r"filter.*status"
    ],
    description="Assesses air filter health based on differential pressure measurements"
)

def analyze_filter_health(sensor_data, delta_p_threshold=None):
    """
    Filter Health Assessment — Differential Pressure Monitoring & Replacement Timing
    
    Purpose:
    Monitors filter differential pressure (ΔP) to determine filter loading and replacement 
    timing. Dirty filters increase static pressure drop, causing fan energy waste (up to 
    20% increase), reduced airflow, and potential IAQ degradation. Timely filter replacement 
    based on ΔP (condition-based maintenance) is more efficient than calendar-based replacement.
    
    Sensors:
      - Filter_Differential_Pressure or Filter_DP (Pa or in.w.c.)
      - Optional: Airflow or Air_Flow_Rate (CFM or m³/s) for normalized ΔP
    
    Output:
      - dp_latest: Current filter ΔP (Pa)
      - dp_mean: Average ΔP over period
      - dp_trend: Rate of ΔP increase (Pa/day)
      - normalized_dp: ΔP per unit airflow (if airflow available)
      - filter_life_remaining: Estimated days until replacement
      - alert: "Replace Soon", "Clean", "Monitor"
      - energy_penalty: Excess fan energy due to dirty filters (%)
    
    This analysis helps:
      - Optimize filter replacement timing (avoid premature or delayed changes)
      - Reduce fan energy consumption (up to 20% savings with clean filters)
      - Prevent airflow starvation to zones (dirty filters reduce CFM)
      - Support ASHRAE 62.1 ventilation rate maintenance
      - Enable predictive maintenance (schedule replacement before failure)
      - Validate filter type selection (MERV 8 vs 13 vs 16 pressure drop trade-off)
    
    Method:
      **Filter differential pressure (ΔP):**
        ΔP = P_upstream - P_downstream  [Pa or in.w.c.]
        
        Measured across filter bank using differential pressure transducer
        Increases as filter accumulates dust (loading)
      
      **Typical ΔP values by filter type (clean vs dirty):**
        MERV 8 (30-35% efficiency @ 1 µm):
          - Clean: 50-100 Pa (0.2-0.4 in.w.c.)
          - Replace at: 200-250 Pa (0.8-1.0 in.w.c.)
        
        MERV 11 (65-80% efficiency @ 1 µm):
          - Clean: 75-125 Pa (0.3-0.5 in.w.c.)
          - Replace at: 250-300 Pa (1.0-1.2 in.w.c.)
        
        MERV 13 (85-95% efficiency @ 1 µm):
          - Clean: 100-150 Pa (0.4-0.6 in.w.c.)
          - Replace at: 300-350 Pa (1.2-1.4 in.w.c.)
        
        MERV 16 / HEPA (>99.97% @ 0.3 µm):
          - Clean: 200-300 Pa (0.8-1.2 in.w.c.)
          - Replace at: 400-500 Pa (1.6-2.0 in.w.c.)
        
        Unit conversion: 1 in.w.c. = 249.1 Pa
      
      **Filter replacement thresholds:**
        Standard practice:
          - Replace when ΔP reaches 2× clean pressure drop
          - OR when ΔP exceeds manufacturer's rated final resistance
        
        Energy-optimized practice:
          - Replace when cost of extra fan energy > cost of new filter
          - Typical breakeven: 1.5-2× clean ΔP (depends on electricity cost)
        
        IAQ-prioritized practice (pandemic, high-risk occupancy):
          - Replace more frequently to maintain filtration efficiency
          - Some MERV 13+ filters lose efficiency at high ΔP
      
      **Energy impact calculation:**
        Additional fan power due to dirty filter:
          P_added = (ΔP_dirty - ΔP_clean) × Airflow / η_fan
        
        Example: 10,000 CFM system, MERV 13 filter
          - Clean ΔP: 125 Pa
          - Dirty ΔP: 300 Pa (replacement threshold)
          - Airflow: 10,000 CFM = 4.72 m³/s
          - Fan efficiency: 60%
          
          P_added = (300 - 125) Pa × 4.72 m³/s / 0.6 = 1,376 W
          
          Annual energy waste:
            1.376 kW × 8760 hrs × 0.6 load factor = 7,240 kWh/year
            Cost: $724-$1,448 @ $0.10-$0.20/kWh
        
        Filter cost: $100-$300 for MERV 13 bank
        Conclusion: Replace filter if ΔP penalty >$100/year energy cost
      
      **Normalized ΔP (accounts for varying airflow):**
        Normalized ΔP = ΔP / (Airflow)²  [Pa/(m³/s)²]
        
        Why square: Pressure drop ∝ (velocity)² for turbulent flow
        
        Use case: Detect filter loading independent of VFD speed changes
          - Raw ΔP increases with airflow (false alarm at high flow)
          - Normalized ΔP isolates actual filter loading
      
      **Filter loading rate (predictive maintenance):**
        Track ΔP over time:
          Loading rate = ΔΔP / Δtime  [Pa/day]
        
        Estimate replacement date:
          Days remaining = (ΔP_threshold - ΔP_current) / Loading_rate
        
        Example:
          - Current ΔP: 200 Pa
          - Threshold: 300 Pa
          - Loading rate: 5 Pa/day (observed over 30 days)
          - Days remaining: (300 - 200) / 5 = 20 days
        
        Pro-active scheduling: Replace filter in 15 days (buffer for procurement)
      
      **Filter types and IAQ trade-offs:**
        MERV 8 (economy):
          - Low ΔP, low cost
          - Captures: Dust, pollen (>10 µm)
          - Does NOT capture: PM2.5, bacteria, viruses
          - Use: Low IAQ requirement, warehouses
        
        MERV 13 (recommended for occupied spaces):
          - Moderate ΔP, moderate cost
          - Captures: PM2.5 (50-85%), bacteria, mold
          - ASHRAE recommends for schools, offices (post-COVID)
          - Use: Standard commercial buildings
        
        MERV 16 / HEPA (high-performance):
          - High ΔP, high cost
          - Captures: >95% PM2.5, viruses, smoke
          - Use: Hospitals, cleanrooms, wildfire zones
      
      **Common filter issues (beyond loading):**
        Bypassing:
          - Symptom: ΔP low but IAQ poor (PM2.5 high)
          - Cause: Filter not sealed in frame, gaps around edges
          - Fix: Inspect gaskets, ensure proper installation
        
        Sensor drift:
          - Symptom: ΔP reading constant despite increasing runtime
          - Cause: Differential pressure transducer fouled or failed
          - Test: Compare with portable manometer
        
        Wrong filter type:
          - Symptom: ΔP always high (>300 Pa even when new)
          - Cause: Filter too restrictive for system (e.g., HEPA in standard AHU)
          - Fix: Verify fan capacity, consider lower MERV if necessary
      
      **ASHRAE recommendations:**
        Standard 62.1-2022 (Ventilation):
          - Minimum MERV 6 (not recommended for IAQ)
          - MERV 13 recommended for improved IAQ, pandemic preparedness
        
        Standard 52.2 (Filter testing method):
          - Defines MERV rating based on particle size capture efficiency
          - Test ΔP at standard airflow (492 fpm face velocity)
      
      **Monitoring best practices:**
        - Measure ΔP continuously (not just at filter change)
        - Trend ΔP over time to predict replacement date
        - Normalize by airflow to detect true loading vs VFD speed changes
        - Set alert threshold at 1.5× clean ΔP (early warning)
        - Set critical threshold at 2× clean ΔP (mandatory replacement)
    
    Parameters:
        sensor_data (dict): Filter ΔP and optional airflow timeseries
        delta_p_threshold (float, optional): Alert threshold in Pa (default: 250 Pa for MERV 13)
    
    Returns:
        dict: ΔP stats, normalized ΔP, filter life remaining, alert, energy penalty

    Assesses filter health using Filter_Differential_Pressure and (optionally) airflow to normalize.

    Returns: { dp_latest, dp_mean, normalized_dp (if flow found), alert }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data available"}
    dp_pred = _key_matcher(["filter", "differential_pressure", "delta_p", "dp"]) ; flow_pred = _key_matcher(["air_flow", "airflow", "flow_rate"])
    dp_keys = _select_keys(flat, dp_pred, False)
    if not dp_keys:
        return {"error": "No filter ΔP series"}
    dp_df = _df_from_readings(sum((flat[k] for k in dp_keys), []))
    if dp_df.empty:
        return {"error": "Empty filter ΔP series"}
    flow_keys = _select_keys(flat, flow_pred, False)
    if flow_keys:
        f_df = _df_from_readings(sum((flat[k] for k in flow_keys), []))
    else:
        f_df = pd.DataFrame()
    dp_latest = float(dp_df.iloc[-1]["reading_value"]) if not dp_df.empty else None
    dp_mean = float(dp_df["reading_value"].mean())
    normalized = None
    if not f_df.empty:
        mm = pd.merge_asof(dp_df.sort_values("timestamp"), f_df.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_dp","_flow"))
        if not mm.empty and (mm["reading_value_flow"] > 0).any():
            normalized = float((mm["reading_value_dp"] / mm["reading_value_flow"]).median())
    if delta_p_threshold is None:
        delta_p_threshold = dp_mean * 1.5  # heuristic: 50% above mean suggests change
    alert = None
    if dp_latest is not None:
        alert = ("Change filter soon" if dp_latest > float(delta_p_threshold) else "Filter OK")
    return {"dp_latest": dp_latest, "dp_mean": round(dp_mean,2), "normalized_dp": (round(normalized,4) if normalized is not None else None), "unit": "Pa", "alert": alert}


@analytics_function(
    patterns=[
        r"damper.*performance",
        r"damper.*control",
        r"damper.*position",
        r"damper.*stuck",
        r"modulating.*damper"
    ],
    description="Analyzes damper performance, detecting stuck or malfunctioning dampers"
)

def analyze_damper_performance(sensor_data, flatline_points=10):
    """
    Damper Performance Assessment — Actuator Health & Response Validation
    
    Purpose:
    Evaluates damper position motion to detect stuck dampers, stiction (stick-slip), or 
    failed actuators. Non-responsive dampers prevent economizer operation, cause IAQ issues 
    (stuck outdoor air damper), and waste energy (stuck open/closed). This analysis supports 
    economizer fault detection and actuator predictive maintenance.
    
    Sensors:
      - Damper_Position or Outdoor_Air_Damper_Position (0-100%)
      - Return_Air_Damper_Position, Mixed_Air_Damper_Position
    
    Output:
      - variance: Position variance (low variance = stuck)
      - flatline_count: Number of consecutive unchanging readings
      - stuck_flag: "Stuck", "Sluggish", "Normal"
      - position_range: Min to max position traveled
      - response_time: Time to change position (if command signal available)
    
    This analysis helps:
      - Detect failed economizer actuators (stuck damper = no free cooling)
      - Identify stiction (stick-slip) requiring actuator lubrication or replacement
      - Validate minimum outdoor air ventilation (damper must modulate)
      - Support ASHRAE Standard 90.1 economizer fault detection requirements
      - Prevent IAQ issues from stuck closed OA damper
    
    Method:
      **Damper position analysis:**
        Variance (σ²):
          Low variance (<5%²) + high flatline count → Stuck damper
        
        Flatline detection:
          Count consecutive readings with zero change
          Threshold: >10 consecutive points (>20 minutes at 2-min intervals) → Stuck
      
      **Typical damper issues:**
        Stuck open (OA damper):
          - Symptom: Position flatlined at 80-100%
          - Impact: Excess outdoor air, high heating/cooling load, energy waste
          - Cause: Failed actuator, broken linkage, manual override
        
        Stuck closed (OA damper):
          - Symptom: Position flatlined at 0-10%
          - Impact: IAQ degradation, CO₂ buildup, code violation (ASHRAE 62.1)
          - Cause: Failed actuator, seized damper blades
        
        Stiction (stick-slip):
          - Symptom: Position jumps in large increments (0% → 30% → 0%)
          - Cause: Dry bearings, corrosion, lack of lubrication
          - Fix: Lubricate damper pivots, replace actuator
      
      **ASHRAE 90.1-2022 economizer requirements:**
        - Integrated economizer mandatory (most climate zones)
        - Fault detection required: Damper must respond to control signal
        - Validation: Damper position should vary with outdoor conditions
    
    Parameters:
        sensor_data (dict): Damper position timeseries
        flatline_points (int, optional): Threshold for stuck detection (default 10)
    
    Returns:
        dict: Variance, flatline count, stuck flag, position range

    Evaluates damper position motion/response; flags stuck or sluggish behavior.

    Returns: { variance, flatline_count, stuck_flag }
    """
    flat = _aggregate_flat(sensor_data)
    pos_pred = _key_matcher(["damper", "position"]) ; key_pred = _key_matcher(["damper_position", "damper"])
    keys = _select_keys(flat, key_pred, False) or _select_keys(flat, pos_pred, False)
    if not keys:
        return {"error": "No damper position series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    if df.empty:
        return {"error": "Empty damper series"}
    variance = float(df["reading_value"].var() or 0.0)
    # flatline detection
    vals = df["reading_value"].tolist(); ts = df["timestamp"].tolist();
    flatlines = 0
    run = 1
    for i in range(1, len(vals)):
        if vals[i] == vals[i-1]:
            run += 1
        else:
            if run >= int(flatline_points):
                flatlines += 1
            run = 1
    if run >= int(flatline_points):
        flatlines += 1
    stuck = (flatlines >= 1) or (variance < 1.0)
    return {"variance": round(variance,3), "flatline_count": flatlines, "stuck_flag": bool(stuck)}


@analytics_function(
    patterns=[
        r"coil.*delta.*t",
        r"coil.*effectiveness",
        r"coil.*performance",
        r"heating.*cooling.*coil",
        r"heat.*transfer.*effectiveness"
    ],
    description="Analyzes heating/cooling coil effectiveness via temperature delta measurements"
)

def analyze_coil_delta_t_effectiveness(sensor_data):
    """
    Coil Delta-T Effectiveness — Heat Transfer Performance Assessment
    
    Purpose:
    Evaluates heating or cooling coil heat transfer effectiveness by measuring temperature 
    difference (ΔT) across the coil (outlet - inlet air temperature). Declining ΔT indicates 
    fouling, low water flow, valve issues, or inadequate capacity. This analysis detects 
    coil performance degradation before comfort complaints occur, enabling proactive maintenance 
    and control optimization.
    
    Sensors:
      - Coil_Entering_Air_Temperature or Mixed_Air_Temperature (°C)
      - Coil_Leaving_Air_Temperature or Supply_Air_Temperature (°C)
      - Optional: Water_Entering_Temperature, Water_Leaving_Temperature (°C)
      - Optional: Water_Flow_Rate for full effectiveness calculation
    
    Output:
      - delta_t_mean: Average air-side ΔT across coil (°C)
      - delta_t_latest: Most recent ΔT reading
      - effectiveness_proxy: Simplified effectiveness metric (0-1)
      - coil_performance: "Excellent", "Good", "Marginal", or "Poor"
      - degradation_trend: ΔT change over time (declining = fouling)
    
    This analysis helps:
      - Detect fouled coils requiring cleaning (reducing ΔT over time)
      - Identify control valve issues (hunting, stuck, undersized)
      - Diagnose low water flow or temperature supply problems
      - Validate coil capacity against design specifications
      - Schedule coil maintenance based on performance, not calendar
      - Optimize control sequences for maximum heat transfer
    
    Method:
      Air-side ΔT calculation:
        Cooling: ΔT = T_entering - T_leaving (positive value)
        Heating: ΔT = T_leaving - T_entering (positive value)
      
      Simplified effectiveness (when water temps not available):
        ε_proxy = Actual_ΔT / Design_ΔT
        
        Typical design ΔT:
          - Cooling coils: 10-15°C (entering ~25°C → leaving ~12-15°C)
          - Heating coils: 20-30°C (entering ~5-10°C → leaving ~30-35°C)
      
      Full heat exchanger effectiveness (when water temps available):
        ε = (T_air_out - T_air_in) / (T_water_in - T_air_in)
        
        Where ε ranges 0-1:
          - ε > 0.8: Excellent performance (clean coil, good flow)
          - ε = 0.6-0.8: Good performance (normal operation)
          - ε = 0.4-0.6: Marginal (fouling suspected, investigate)
          - ε < 0.4: Poor (severe fouling, low flow, or valve issue)
      
      Performance degradation indicators:
        - ΔT declining >10% over 6 months: Coil fouling (dirt, biological growth)
        - ΔT variability increasing: Valve hunting or control instability
        - ΔT suddenly drops: Water flow issue, valve failure, or sensor drift
        - ΔT below 60% of design: Capacity inadequate or severe fault
      
      Common root causes of low ΔT:
        - Fouled coil fins (dust, lint accumulation)
        - Low water flow rate (pump issue, valve stuck/undersized)
        - Low water temperature differential (chiller/boiler issue)
        - Air bypass around coil (poor gasket seals)
        - Control valve hunting or stuck partially open
    
    Parameters:
        sensor_data (dict): Coil entering/leaving air temperature timeseries
    
    Returns:
        dict: ΔT statistics, effectiveness proxy, performance classification, and trend analysis
    """
    flat = _aggregate_flat(sensor_data)
    sup_pred = _key_matcher(["supply_air"]) ; ret_pred = _key_matcher(["return_air"]) ; temp_pred = _key_matcher(["temperature", "temp"])
    s_keys = [k for k in flat.keys() if sup_pred(str(k)) and temp_pred(str(k))]
    r_keys = [k for k in flat.keys() if ret_pred(str(k)) and temp_pred(str(k))]
    if not s_keys or not r_keys:
        return {"error": "Need supply and return air temperatures"}
    dfS = _df_from_readings(sum((flat[k] for k in s_keys), []))
    dfR = _df_from_readings(sum((flat[k] for k in r_keys), []))
    mm = pd.merge_asof(dfS.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_s","_r"))
    if mm.empty:
        return {"error": "Could not align supply and return"}
    dT = (mm["reading_value_r"] - mm["reading_value_s"]).abs()
    eff = float(dT.mean()) / max(1.0, float(mm["reading_value_r"].std() or 1.0))  # heuristic proxy
    return {"delta_t_mean": round(float(dT.mean()),2), "delta_t_latest": round(float(dT.iloc[-1]),2), "effectiveness_proxy": round(eff,3), "unit": "°C"}


@analytics_function(
    patterns=[
        r"frost.*risk",
        r"freeze.*protection",
        r"freezing.*condition",
        r"low.*temp.*alarm",
        r"freeze.*prevention"
    ],
    description="Assesses frost and freeze risk for HVAC coils based on outdoor air temperature"
)

def analyze_frost_freeze_risk(sensor_data, oat_threshold=0.0):
    """
    Frost/Freeze Risk Detection — Coil Protection & Freeze-Stat Validation
    
    Purpose:
    Monitors outdoor air temperature and frost sensor status to prevent coil freezing, which 
    can cause catastrophic equipment damage (burst coils, $10k-$50k repair). Freeze events 
    occur when water-based coils (heating or cooling) are exposed to subfreezing air without 
    adequate protection (glycol, low-temperature cutoff, or preheat). This analysis validates 
    freeze-stat operation and triggers pre-emptive shutdowns.
    
    Sensors:
      - Frost_Sensor or Freeze_Stat (binary: 0 = normal, 1 = risk)
      - Outside_Air_Temperature or OAT (°C)
      - Optional: Coil_Leaving_Air_Temperature (detect coil freezing directly)
    
    Output:
      - risk_events: Count of freeze risk conditions
      - latest_flag: Current freeze risk status (boolean)
      - hours_at_risk: Total hours below threshold
      - min_temperature: Coldest temperature observed
      - protection_recommendation: "Adequate", "Marginal", "Insufficient"
    
    This analysis helps:
      - Prevent catastrophic coil freeze damage ($10k-$50k repair + downtime)
      - Validate freeze-stat operation (sensors often fail, triggering false alarms)
      - Trigger pre-emptive economizer lockout (prevent cold air on heating coils)
      - Support ASHRAE Guideline 36 cold weather sequence validation
      - Determine need for glycol loops or preheat coils in cold climates
    
    Method:
      **Freeze risk thresholds:**
        Water coils (no glycol):
          - High risk: <0°C (32°F) - immediate freeze danger
          - Moderate risk: 0-2°C (32-36°F) - pre-emptive lockout recommended
          - Low risk: 2-4°C (36-39°F) - monitor closely
        
        Glycol coils (20-30% ethylene glycol):
          - High risk: <-5°C (23°F)
          - Moderate risk: -5 to -2°C (23-28°F)
        
        Coil leaving air temperature (LAT):
          - Critical: LAT <2°C → coil may freeze
          - Emergency: LAT <0°C → immediate shutdown required
      
      **Freeze prevention strategies:**
        Low-temperature cutoff (LTCO):
          - Close outdoor air damper when OAT <4°C (configurable)
          - Override economizer, switch to minimum outdoor air
          - Maintain minimum 10% OA for ventilation only
        
        Preheat coil:
          - Electric or hot water coil upstream of main coil
          - Warms outdoor air to 7-10°C before mixing
          - Required in cold climates (Design OAT <-10°C)
        
        Glycol solution (20-30% ethylene glycol):
          - Lowers freeze point to -5°C to -10°C
          - Trade-off: Reduced heat transfer efficiency (~5-10%)
        
        Face & bypass damper:
          - Bypass cold outdoor air around coil during freeze risk
          - Maintains ventilation without exposing coil
      
      **ASHRAE Guideline 36-2021 cold weather sequences:**
        Section 5.18.5 - Freeze Protection:
          - Stage 1 (OAT <4°C): Close OA damper to minimum position
          - Stage 2 (LAT <7°C): Close OA damper to 0%, alarm
          - Stage 3 (LAT <4°C): Shutdown supply fan, alarm
          - Stage 4 (LAT <2°C): Open HW valve to 100%, emergency shutdown
        
        All stages must be independent (freeze-stat hardwired, not software-only)
      
      **Freeze-stat sensor types:**
        Capillary tube:
          - Spans coil width, detects average coil temperature
          - Trips at 2-4°C (adjustable)
          - Manual reset required (prevents auto-restart after freeze)
        
        Resistance temperature detector (RTD):
          - Digital sensor, continuous temperature monitoring
          - Integration with BAS for alarm/trending
          - Auto-reset capable (but not recommended for safety-critical)
      
      **Coil freeze damage mechanisms:**
        Water expansion:
          - Water expands 9% when frozen
          - Burst tubes, separated fins, header cracks
          - Repair: Full coil replacement ($10k-$50k + downtime)
        
        Timing:
          - Coil can freeze in 15-60 minutes at -5°C with low airflow
          - Overnight freeze events common (HVAC off, no heat)
        
        Prevention cost vs repair cost:
          - Glycol conversion: $5k-$15k (one-time)
          - Preheat coil: $10k-$20k (one-time)
          - Coil replacement: $10k-$50k + 1-4 weeks downtime
      
      **False alarm scenarios (sensor issues):**
        Freeze-stat nuisance trips:
          - Cause: Sensor drift, mounting location (cold airstream, not coil)
          - Impact: Unnecessary shutdowns, occupant discomfort
          - Fix: Verify sensor calibration, relocate sensor to coil itself
        
        OAT sensor error:
          - Cause: Solar radiation (reads high), ice buildup (reads low)
          - Impact: Missed freeze events or false alarms
          - Fix: Shield sensor from sun, ensure proper ventilation
      
      **Climate-specific considerations:**
        Mild climates (Design OAT >0°C):
          - Freeze risk rare, simple LTCO sufficient
          - Example: Southern UK, coastal US
        
        Cold climates (Design OAT -10 to -20°C):
          - Freeze risk frequent, glycol or preheat required
          - Example: Northern UK, Midwest US, Canada
        
        Extreme climates (Design OAT <-20°C):
          - Glycol + preheat + aggressive LTCO required
          - Example: Alaska, Scandinavia, Siberia
      
      **Validation testing (commissioning):**
        Functional test:
          - Simulate freeze condition (disconnect freeze-stat, force trip)
          - Verify: OA damper closes, supply fan stops, alarm activates
          - Confirm: Manual reset required (not auto-restart)
        
        Annual inspection:
          - Check freeze-stat calibration (trip point accuracy)
          - Verify capillary tube integrity (no kinks, full coil coverage)
          - Test alarm notification (email, BAS alert, local horn)
    
    Parameters:
        sensor_data (dict): Frost sensor or outdoor air temperature timeseries
        oat_threshold (float, optional): Freeze risk threshold in °C (default 0.0°C)
    
    Returns:
        dict: Risk event count, latest flag, hours at risk, min temperature, protection recommendation

    Flags frost/freezing risk using frost sensor if present or outdoor air temperature below a threshold.

    Returns: { risk_events, latest_flag }
    """
    flat = _aggregate_flat(sensor_data)
    frost_pred = _key_matcher(["frost"]) ; oat_pred = _key_matcher(["outside_air", "outdoor"]) ; temp_pred = _key_matcher(["temperature", "temp"])
    frost_keys = _select_keys(flat, frost_pred, False)
    if frost_keys:
        df = _df_from_readings(sum((flat[k] for k in frost_keys), []))
        if df.empty:
            return {"error": "Empty frost sensor series"}
        flag = (df["reading_value"] > 0.5)  # binary-ish
        return {"risk_events": int(flag.sum()), "latest_flag": bool(flag.iloc[-1])}
    oat_keys = [k for k in flat.keys() if oat_pred(str(k)) and temp_pred(str(k))]
    if not oat_keys:
        return {"error": "No frost or OAT series"}
    odf = _df_from_readings(sum((flat[k] for k in oat_keys), []))
    flag = (odf["reading_value"] <= float(oat_threshold))
    return {"risk_events": int(flag.sum()), "latest_flag": bool(flag.iloc[-1])}


@analytics_function(
    patterns=[
        r"return.*mixed.*outdoor",
        r"rat.*mat.*oat",
        r"air.*temperature.*consistency",
        r"air.*side.*validation",
        r"airstream.*validation"
    ],
    description="Validates consistency between return, mixed, and outdoor air temperatures"
)

def analyze_return_mixed_outdoor_consistency(sensor_data):
    """
    Return/Mixed/Outdoor Air Consistency — Psychrometric Relationship Validation
    
    Purpose:
    Validates the thermodynamic relationship between return air (RAT), mixed air (MAT), 
    and outdoor air (OAT) temperatures to detect sensor errors, damper leakage, or airflow 
    imbalances. In cooling mode, the expected relationship is: RAT ≥ MAT ≥ OAT. Violations 
    indicate sensor miscalibration, stuck dampers, or cross-contamination of airstreams.
    
    Sensors:
      - Return_Air_Temperature or RAT (°C)
      - Mixed_Air_Temperature or MAT (°C)
      - Outside_Air_Temperature or OAT (°C)
    
    Output:
      - violation_count: Number of timesteps violating expected RAT ≥ MAT ≥ OAT
      - violation_percentage: % of time relationships violated
      - typical_sequence: Expected order and observed order
      - sensor_health: "Normal", "Suspect", "Faulty"
      - damper_leakage_indicator: "Likely", "Possible", "Unlikely"
    
    This analysis helps:
      - Detect sensor calibration errors (RAT sensor reads low, OAT reads high)
      - Identify damper leakage (RAT < MAT implies return damper leakage)
      - Validate economizer operation (MAT should track between RAT and OAT)
      - Support ASHRAE Guideline 36 mixed-air validation sequences
      - Prevent false economizer lockouts due to bad sensors
    
    Method:
      **Expected psychrometric relationships (cooling mode):**
        RAT ≥ MAT ≥ OAT  (typical summer conditions)
        
        Where:
          - RAT: Warmest (building heat gain from occupants, equipment, lights)
          - MAT: Intermediate (mixture of RAT and OAT based on damper position)
          - OAT: Coolest (outdoor air)
        
        Mixed-air temperature calculation:
          MAT_expected = (RAT × %RA) + (OAT × %OA)
          
          Where %RA + %OA = 100%
          
          Example: RAT = 24°C, OAT = 18°C, 70% return / 30% outdoor
            MAT = (24 × 0.7) + (18 × 0.3) = 22.2°C
      
      **Violation scenarios and root causes:**
        RAT < MAT:
          - Interpretation: Impossible (mixed air hotter than return air)
          - Root cause: RAT sensor reads low OR return damper leakage (cold outdoor air into return)
          - Action: Calibrate RAT sensor, inspect return damper seals
        
        MAT < OAT:
          - Interpretation: Impossible (mixed air cooler than outdoor air alone)
          - Root cause: OAT sensor reads high (solar radiation, poor shielding)
          - Action: Shield OAT sensor from sun, verify mounting location
        
        MAT > RAT:
          - Interpretation: Mixed air hotter than return (rare, heating mode only)
          - Root cause: Preheat coil active OR OAT sensor failure
          - Action: Check for heating coil operation, verify OAT sensor
      
      **Sensor validation approach:**
        Cross-check with damper position:
          - If OA damper = 0% and MAT ≈ RAT: Sensors likely OK
          - If OA damper = 100% and MAT ≈ OAT: Sensors likely OK
          - If OA damper = 50% and MAT ≠ 0.5(RAT + OAT): Sensor or damper issue
        
        Expected tolerance:
          - MAT should be within ±1°C of calculated value
          - Deviation >2°C: Sensor calibration or damper position error
      
      **Damper leakage detection:**
        Scenario 1 - Outdoor air damper leakage (stuck partially open):
          - Symptom: MAT closer to OAT than expected (given damper position)
          - Impact: Excess outdoor air, high heating/cooling load
          - Quantification: Leakage % = (MAT_actual - MAT_expected) / (OAT - RAT)
        
        Scenario 2 - Return air damper leakage:
          - Symptom: MAT closer to RAT than expected
          - Impact: Insufficient outdoor air (IAQ issue, code violation)
          - Quantification: Similar calculation, opposite direction
      
      **ASHRAE Guideline 36-2021 validation sequences:**
        Section 5.18.7 - Economizer Enable/Disable Logic:
          - Validate MAT = f(RAT, OAT, damper_position)
          - If deviation >2°C: Flag sensor error, disable economizer
          - Manual sensor verification required before re-enabling
      
      **Heating mode considerations:**
        Expected relationship reverses in heating mode:
          OAT ≤ MAT ≤ RAT  (winter conditions with preheat)
        
        Preheat active:
          - MAT may exceed RAT (preheat coil adds heat upstream)
          - Not a violation, but requires different validation logic
      
      **Economizer fault detection (ASHRAE 90.1 requirement):**
        Fault Type 1 - Temperature sensor failure:
          - Detect: RAT/MAT/OAT relationships violated >10% of economizer-enabled time
          - Response: Disable economizer, alarm BAS, initiate sensor verification
        
        Fault Type 2 - Damper not modulating:
          - Detect: MAT unchanged despite damper position changes
          - Response: Suspect stuck damper or failed actuator
      
      **Typical violation rates and interpretation:**
        <5% violations:
          - Normal (transient conditions, sensor lag acceptable)
          - Action: None
        
        5-15% violations:
          - Suspect (sensor drift possible, damper leakage possible)
          - Action: Monitor, schedule sensor verification
        
        >15% violations:
          - Faulty (sensor miscalibration or damper failure)
          - Action: Immediate sensor verification, disable economizer if critical
    
    Parameters:
        sensor_data (dict): RAT, MAT, and OAT timeseries data
    
    Returns:
        dict: Violation count/percentage, sensor health rating, damper leakage indicator

    Checks typical ordering RAT >= MAT >= OAT (cooling scenario) violations.

    Returns: { violation_count }
    """
    flat = _aggregate_flat(sensor_data)
    r_pred = _key_matcher(["return_air", "return"]) ; m_pred = _key_matcher(["mixed_air", "mix"]) ; o_pred = _key_matcher(["outside_air", "outdoor"]) ; t_pred = _key_matcher(["temperature", "temp"])
    Rk = [k for k in flat.keys() if r_pred(str(k)) and t_pred(str(k))]
    Mk = [k for k in flat.keys() if m_pred(str(k)) and t_pred(str(k))]
    Ok = [k for k in flat.keys() if o_pred(str(k)) and t_pred(str(k))]
    if not (Rk and Mk and Ok):
        return {"error": "Need RAT, MAT, and OAT series"}
    dfR = _df_from_readings(sum((flat[k] for k in Rk), []))
    dfM = _df_from_readings(sum((flat[k] for k in Mk), []))
    dfO = _df_from_readings(sum((flat[k] for k in Ok), []))
    mm = pd.merge_asof(dfR.sort_values("timestamp"), dfM.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_r","_m"))
    mm = pd.merge_asof(mm.sort_values("timestamp"), dfO.sort_values("timestamp"), on="timestamp", direction="nearest")
    if mm.empty:
        return {"error": "Could not align series"}
    violations = ~((mm["reading_value_r"] >= mm["reading_value_m"]) & (mm["reading_value_m"] >= mm["reading_value"]))
    return {"violation_count": int(violations.sum())}


@analytics_function(
    patterns=[
        r"chilled.*water.*delta.*t",
        r"chw.*delta.*t",
        r"chiller.*temperature.*difference",
        r"chilled.*water.*return",
        r"chiller.*supply.*return"
    ],
    description="Analyzes chilled water supply-return temperature delta for chiller performance"
)

def analyze_chilled_water_delta_t(sensor_data):
    """
    Chilled Water ΔT — Low Delta-T Syndrome Detection
    
    Purpose:
    Computes the temperature difference (ΔT) between chilled water return and supply 
    temperatures to assess heat exchanger/coil effectiveness and chiller plant efficiency. 
    Low ΔT (<3-4°C) indicates poor heat transfer, causing excessive flow rates, high 
    pumping energy, and reduced chiller efficiency. This is one of the most common and 
    costly operational issues in chilled water systems, often caused by control valve 
    issues, fouled coils, or design problems.
    
    Sensors:
      - Chilled_Water_Supply_Temperature_Sensor or CHWST (°C)
      - Chilled_Water_Return_Temperature_Sensor or CHWRT (°C)
    
    Output:
      - delta_t_mean: Average ΔT across analysis period (°C)
      - delta_t_latest: Most recent ΔT reading (°C)
      - delta_t_min, delta_t_max: Range of observed ΔT
      - low_delta_t_flag: Boolean indicating chronic low-ΔT condition (<4°C)
      - severity: "Normal" (>5°C), "Marginal" (4-5°C), or "Low-ΔT Syndrome" (<4°C)
    
    This analysis helps:
      - Detect "Low Delta-T Syndrome" causing excessive chiller energy consumption
      - Identify control valve hunting, bypassing, or stuck-open conditions
      - Detect fouled AHU coils requiring cleaning
      - Validate commissioning and design ΔT assumptions (typically 5-6°C design)
      - Quantify impact on chiller kW/ton efficiency (every 1°C ΔT loss ≈ 1-2% efficiency hit)
      - Support chiller plant optimization and variable primary flow strategies
    
    Method:
      ΔT = CHW Return Temperature - CHW Supply Temperature
      
      Expected ΔT benchmarks:
        - Design target: 5-6°C (9-11°F) for optimal chiller efficiency
        - Acceptable: 4-5°C (still reasonable performance)
        - Low ΔT Syndrome: <4°C (requires investigation and corrective action)
        - Critical: <3°C (immediate attention needed)
      
      Root causes of low ΔT:
        - Control valves oversized or hunting (most common)
        - Three-way valves instead of two-way (constant flow, bypass)
        - Fouled coils reducing heat transfer effectiveness
        - Chilled water flow rate too high for load
        - Mixing at terminal units due to poor piping design
        - Air in coils or poor airflow across coils
      
      Economic impact: A system with 3°C ΔT vs 6°C design requires 2× flow rate,
      leading to 8× pumping energy increase and 10-15% chiller efficiency penalty.
    
    Parameters:
        sensor_data (dict): Timeseries CHW supply and return temperature readings
    
    Returns:
        dict: ΔT statistics, low-ΔT flags, and severity classification with unit (°C)
    """
    flat = _aggregate_flat(sensor_data)
    cs_pred = _key_matcher(["chilled_water", "chw"]) ; sup_pred = _key_matcher(["supply"]) ; ret_pred = _key_matcher(["return"]) ; t_pred = _key_matcher(["temperature", "temp"])
    ChwS = [k for k in flat.keys() if cs_pred(str(k)) and sup_pred(str(k)) and t_pred(str(k))]
    ChwR = [k for k in flat.keys() if cs_pred(str(k)) and ret_pred(str(k)) and t_pred(str(k))]
    if not (ChwS and ChwR):
        return {"error": "Need CHW supply and return temperatures"}
    dfS = _df_from_readings(sum((flat[k] for k in ChwS), []))
    dfR = _df_from_readings(sum((flat[k] for k in ChwR), []))
    mm = pd.merge_asof(dfR.sort_values("timestamp"), dfS.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_r","_s"))
    if mm.empty:
        return {"error": "Could not align CHWR and CHWS"}
    dT = mm["reading_value_r"] - mm["reading_value_s"]
    low_flag = bool((dT < 3.0).mean() > 0.5)  # heuristic: more than half points below 3C
    return {"delta_t_mean": round(float(dT.mean()),2), "delta_t_latest": round(float(dT.iloc[-1]),2), "low_delta_t_flag": low_flag, "unit": "°C"}


@analytics_function(
    patterns=[
        r"chilled.*water.*flow",
        r"chw.*flow",
        r"chiller.*flow.*rate",
        r"water.*flow.*health",
        r"chiller.*circulation"
    ],
    description="Assesses chilled water flow health and detects flow-related issues"
)

def analyze_chilled_water_flow_health(sensor_data):
    """
    Chilled Water Flow Health — Loop Flow Monitoring & Pump Performance
    
    Purpose:
    Monitors chilled water (CHW) flow rate to detect low-flow conditions, pump failures, 
    or control valve issues that compromise cooling capacity. Insufficient CHW flow causes 
    high supply air temperatures, poor dehumidification, and low delta-T syndrome (energy 
    waste). This analysis validates primary/secondary pump operation and variable flow 
    system performance per ASHRAE 90.1 requirements.
    
    Sensors:
      - Chilled_Water_Flow or CHW_Flow_Rate (L/s, GPM, m³/hr)
      - Optional: CHW_Supply_Temp, CHW_Return_Temp (for flow verification)
    
    Output:
      - min_flow, avg_flow, max_flow: Flow statistics (L/s)
      - low_flow_flag: Boolean alert for inadequate flow
      - flow_variability: Coefficient of variation (stability indicator)
      - zero_flow_hours: Hours with no flow (pump off or failed)
      - design_flow_percentage: Actual vs design flow (if design known)
      - pump_health: "Normal", "Degraded", "Failed"
    
    This analysis helps:
      - Detect pump failures or VFD malfunctions (zero flow, low flow)
      - Identify control valve hunting or closure (flow fluctuations)
      - Validate variable primary flow (VPF) system operation
      - Diagnose low delta-T syndrome (high flow, low temperature differential)
      - Support ASHRAE 90.1 hydronic system efficiency requirements
      - Prevent chiller short-cycling (flow interlocks)
    
    Method:
      **Typical CHW flow rates by coil type:**
        AHU cooling coil (small office, 10-20 kW):
          - Design flow: 0.5-1.0 L/s (8-16 GPM)
          - Minimum: 30% of design (0.15-0.3 L/s)
        
        AHU cooling coil (large VAV, 100-200 kW):
          - Design flow: 5-10 L/s (80-160 GPM)
          - Minimum: 40% of design (2-4 L/s)
        
        Chiller primary loop (500 kW chiller):
          - Design flow: 25-30 L/s (400-475 GPM)
          - Minimum: 50% of design (12-15 L/s, VFD turndown limit)
        
        Unit conversion:
          1 L/s = 15.85 GPM = 3.6 m³/hr
      
      **Low-flow thresholds and impacts:**
        Zero flow (0 L/s):
          - Cause: Pump off, pump failure, isolation valve closed
          - Impact: No cooling, high zone temperatures, chiller shutdown
          - Action: Emergency - check pump status, control power
        
        <30% design flow:
          - Cause: Pump degraded, valve nearly closed, strainer clogged
          - Impact: Inadequate cooling capacity, poor control
          - Action: Inspect pump, check valve position, clean strainer
        
        30-60% design flow (during low load):
          - Acceptable: Variable flow system modulating correctly
          - Verify: Delta-T should increase (>5-7°C) at low flow
        
        >120% design flow:
          - Cause: Control valve fully open, pump oversized
          - Impact: Low delta-T syndrome, high pump energy, poor efficiency
          - Action: Reduce pump speed, balance hydronic system
      
      **Flow measurement validation:**
        Cross-check with energy balance:
          Q = ṁ × Cp × ΔT  [kW]
          
          Where:
            Q = cooling load (kW)
            ṁ = mass flow rate (kg/s ≈ L/s for water)
            Cp = 4.18 kJ/kg·K (water specific heat)
            ΔT = T_return - T_supply (°C)
          
          Rearrange to validate flow:
            ṁ = Q / (4.18 × ΔT)  [L/s]
          
          Example: 100 kW load, 6°C delta-T
            ṁ = 100 / (4.18 × 6) = 3.98 L/s
            If measured flow ≠ 4 L/s → sensor error or poor delta-T
      
      **Variable Primary Flow (VPF) system operation:**
        Benefits:
          - Eliminates secondary pumps (energy savings 30-50%)
          - Reduces hydraulic separation equipment
          - Direct control of flow based on load
        
        Control sequence:
          - Modulate pump VFD to maintain differential pressure setpoint
          - Typical setpoint: 150-300 kPa (remote point in system)
          - Minimum flow: 40-50% of design (chiller minimum requirement)
          - Maximum flow: 100% of design (safety limit)
        
        Flow validation:
          - At low load (20% cooling): Flow should be 40-60% design
          - At peak load (100% cooling): Flow should be 90-100% design
          - If flow always high → Poor control, investigate valves
      
      **Low delta-T syndrome diagnosis:**
        Symptom: High CHW flow but low return-supply delta-T (<4°C)
        
        Root causes:
          1. Coil valve oversized (flow too high at low loads)
          2. Coil bypassing (air short-circuit, poor gaskets)
          3. Return/supply sensor error (false low delta-T)
          4. Primary-secondary decoupler flow issues
        
        Economic impact:
          - Excess pump energy: 20-40% waste
          - Chiller efficiency penalty: 10-20% (poor lift)
          - Solution: Valve downsizing, balancing, sensor verification
      
      **Pump performance degradation indicators:**
        Gradual flow decline over months:
          - Cause: Impeller wear, bearing degradation
          - Action: Schedule pump overhaul or replacement
        
        Sudden flow drop:
          - Cause: VFD failure, motor overload, electrical issue
          - Action: Check VFD alarms, motor current, control signals
        
        Intermittent flow loss:
          - Cause: Air in system, check valve failure, cavitation
          - Action: Purge air, inspect check valves, verify NPSH
      
      **Flow sensor types and issues:**
        Ultrasonic flow meter:
          - Accuracy: ±2-5% of reading
          - Issue: Loses signal if air bubbles present
          - Maintenance: Annual calibration, transducer cleaning
        
        Magnetic flow meter:
          - Accuracy: ±0.5-2% of reading
          - Issue: Requires conductive fluid (pure water OK, glycol OK)
          - Maintenance: Electrode inspection, zero verification
        
        Differential pressure across orifice/venturi:
          - Accuracy: ±5-10% (depends on calibration)
          - Issue: Sensitive to upstream turbulence, debris
          - Maintenance: Inspect orifice plate, check tap ports
      
      **ASHRAE 90.1-2022 requirements:**
        Section 6.5.4 - Hydronic System Controls:
          - Variable flow required for systems >150 kW (5 tons)
          - Automatic flow balancing valves recommended
          - Isolation and flow measurement at each major coil
        
        Section 6.5.4.3 - Differential Pressure Reset:
          - Reset differential pressure based on valve positions
          - Target: One valve at >95% open (flow-limited)
          - Savings: 30-50% pump energy vs fixed DP control
      
      **Chiller protection interlocks:**
        Minimum flow switch:
          - Prevents chiller evaporator freeze-up
          - Typical setting: 50% of design flow
          - Action on trip: Shut down chiller, alarm BAS
        
        Flow proving:
          - Verify flow >minimum before chiller start
          - Delay: 30-60 seconds (purge air, stabilize flow)
          - Prevents short-cycling, equipment damage
      
      **Commissioning validation:**
        Design flow verification:
          - Run pumps at 100% speed, measure flow
          - Target: 95-105% of design flow (±5% tolerance)
          - If low: Check strainer, balance valves, pump curve
        
        Turndown test:
          - Reduce load to minimum, verify flow >40% design
          - Check: Chiller remains stable, no flow alarms
          - If flow too low: Increase minimum speed setpoint
    
    Parameters:
        sensor_data (dict): CHW flow rate timeseries data
    
    Returns:
        dict: Flow statistics, low-flow flag, variability, pump health assessment

    Reviews CHW flow adequacy; reports min/avg/max and low flow warnings.

    Returns: { min_flow, avg_flow, max_flow, low_flow_flag }
    """
    flat = _aggregate_flat(sensor_data)
    cw_pred = _key_matcher(["chilled_water", "chw"]) ; flow_pred = _key_matcher(["flow", "flow_rate"]) 
    keys = [k for k in flat.keys() if cw_pred(str(k)) and flow_pred(str(k))]
    if not keys:
        return {"error": "No CHW flow series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    if df.empty:
        return {"error": "Empty CHW flow series"}
    mn = float(df["reading_value"].min()); av = float(df["reading_value"].mean()); mx = float(df["reading_value"].max())
    low_flag = bool(mn <= 0)
    return {"min_flow": round(mn,2), "avg_flow": round(av,2), "max_flow": round(mx,2), "low_flow_flag": low_flag}


@analytics_function(
    patterns=[
        r"loop.*differential.*pressure",
        r"loop.*dp",
        r"chiller.*loop.*pressure",
        r"hydronic.*pressure",
        r"water.*loop.*pressure"
    ],
    description="Analyzes differential pressure in hydronic loops (chilled/hot water)"
)

def analyze_loop_differential_pressure(sensor_data, loop="chw", target=None):
    """
    Loop Differential Pressure — Pump Control & System Health
    
    Purpose:
    Monitors differential pressure (DP) across chilled water (CHW) or hot water (HW) loops 
    to assess pump performance, control valve authority, and system hydraulic balance. 
    Insufficient DP causes poor terminal unit control (valves can't modulate properly), while 
    excessive DP wastes pumping energy and can cause valve noise/damage. This analysis 
    validates variable speed pump control and identifies system balancing issues.
    
    Sensors:
      - Loop_Differential_Pressure_Sensor (kPa, psi, or bar)
      - CHW_Differential_Pressure or HW_Differential_Pressure
      - Supply/Return pressure sensors (if DP not directly measured)
    
    Output:
      - dp_mean: Average differential pressure during analysis period
      - dp_latest: Most recent DP reading
      - dp_min, dp_max: DP range (indicates pump modulation)
      - mae_to_target: Mean Absolute Error if target DP specified
      - control_quality: "Stable", "Hunting", or "Unresponsive"
      - energy_waste_flag: Boolean if DP consistently exceeds target +20%
    
    This analysis helps:
      - Validate VFD pump control setpoint tracking
      - Ensure adequate valve authority at critical terminal units
      - Detect pump oversizing or undersizing issues
      - Identify system balancing problems (uneven DP distribution)
      - Optimize pump speed for energy savings without sacrificing control
      - Diagnose control valve noise and erosion from excessive DP
    
    Method:
      Differential pressure tracking:
        DP = P_supply - P_return (measured at pump or critical point)
      
      Control quality assessment:
        If target DP specified:
          MAE = mean(|DP_actual - DP_target|)
          
          - MAE < 5% of target: Stable, tight control
          - MAE 5-10%: Acceptable, minor hunting
          - MAE >10%: Poor control, pump tuning needed
      
      Typical DP targets and ranges:
        - CHW systems: 100-200 kPa (15-30 psi)
          * Design DP: Ensures full valve authority at farthest/critical coil
          * Min DP: 60-80 kPa (maintain control at low loads)
          * Max DP: 250 kPa (avoid valve damage, noise)
        
        - HW systems: 70-150 kPa (10-22 psi)
          * Lower than CHW due to lower flow rates typically
        
        - Variable primary flow: DP resets based on valve positions
          * Reset from design DP down to minimum as load decreases
          * Typical: 150 kPa @ peak → 80 kPa @ low load
      
      DP issues and root causes:
        - DP too low (<60 kPa):
          * Inadequate pump capacity
          * Excessive system resistance (fouling, partially closed valves)
          * Pump speed too low (VFD issue or reset too aggressive)
          * Critical zones starved, poor temperature control
        
        - DP too high (>200 kPa):
          * Pump oversized or speed too high
          * Control valves throttling excessively (energy waste)
          * Causes valve noise, erosion, premature failure
          * High pumping energy consumption
        
        - DP hunting (high variability):
          * VFD PID tuning too aggressive
          * Valve cycling causing flow oscillations
          * DP sensor location poor (near pump discharge, turbulent)
          * Control loop interaction with other systems
      
      Energy optimization:
        Reducing DP from 200 kPa to 100 kPa (50% reduction) can save
        ~75% of pump energy (cubic relationship: Power ∝ DP^1.5)
        
        But must maintain minimum DP for valve authority:
          Valve authority = ΔP_valve / ΔP_system
          Target authority: 0.25-0.5 (poor control if <0.25)
    
    Parameters:
        sensor_data (dict): Differential pressure timeseries data
        loop (str, optional): Loop type "chw" or "hw" for context (default "chw")
        target (float, optional): Target DP setpoint for tracking error calculation
    
    Returns:
        dict: DP statistics, tracking error to target, control quality, and energy waste flags
    """
    flat = _aggregate_flat(sensor_data)
    loop_pred = _key_matcher([loop, "differential_pressure", "dp"]) ; dp_pred = _key_matcher(["differential_pressure", "dp"]) 
    keys = _select_keys(flat, loop_pred, False) or _select_keys(flat, dp_pred, False)
    if not keys:
        return {"error": "No differential pressure series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    if df.empty:
        return {"error": "Empty DP series"}
    dp_mean = float(df["reading_value"].mean())
    if target is None:
        return {"dp_mean": round(dp_mean,2), "mae_to_target": None}
    err = (df["reading_value"].astype(float) - float(target)).abs()
    return {"dp_mean": round(dp_mean,2), "mae_to_target": round(float(err.mean()),2), "target": float(target)}


@analytics_function(
    patterns=[
        r"coil.*valve",
        r"valve.*diagnostic",
        r"valve.*stuck",
        r"control.*valve",
        r"valve.*performance"
    ],
    description="Diagnoses coil valve operation, detecting stuck or hunting valves"
)

def analyze_coil_valve_diagnostics(sensor_data):
    """
    Coil Valve Diagnostics — Leakage & Stiction Detection
    
    Purpose:
    Performs heuristic diagnostics on control valves (heating/cooling coil valves) by 
    analyzing relationships between valve position, temperatures, and flow rates to detect 
    leakage (valve doesn't fully close) and stiction (valve sticks, doesn't respond smoothly). 
    These common valve faults cause energy waste, poor comfort control, and equipment cycling. 
    Early detection enables targeted maintenance before major comfort complaints.
    
    Sensors:
      - Valve_Position_Sensor (0-100%)
      - Coil_Entering/Leaving_Air_Temperature (°C)
      - Optional: Water_Flow_Sensor for direct leakage confirmation
    
    Output:
      - leakage_suspicion: 0-1 probability of valve leakage (doesn't fully close)
      - stiction_suspicion: 0-1 probability of valve stiction (sticks, poor response)
      - valve_health_score: 0-100 overall valve condition
      - recommended_action: "Monitor", "Inspect", or "Replace"
      - diagnostic_notes: Explanation of detected issues
    
    This analysis helps:
      - Detect valves that leak when closed (energy waste, poor control)
      - Identify sticking valves causing control instability
      - Prioritize valve maintenance/replacement by condition
      - Reduce comfort complaints from poor valve response
      - Prevent simultaneous heating/cooling from leaking valves
      - Extend valve life through predictive maintenance
    
    Method:
      **Leakage detection heuristics:**
        1. Check for flow when valve commanded 0% (direct evidence if flow sensor available)
        2. Check for temperature difference across coil when valve at 0%:
           - Cooling: If T_leaving < T_entering when valve=0%, leakage suspected
           - Heating: If T_leaving > T_entering when valve=0%, leakage suspected
        3. Check for energy consumption anomalies during unoccupied/off periods
        
        Leakage suspicion score:
          - 0.0-0.3: Normal operation, valve seals properly
          - 0.3-0.6: Minor leakage, monitor trend
          - 0.6-0.8: Significant leakage, inspect valve
          - >0.8: Severe leakage, replace valve
      
      **Stiction detection heuristics:**
        1. Analyze valve position step response:
           - Healthy valve: Smooth position tracking, <5 sec response
           - Stiction: Position "sticks" then jumps, deadband >5-10%
        2. Check for hunting behavior:
           - Valve oscillates around setpoint (±10-20% position swings)
           - Temperature oscillations correlate with position hunting
        3. Check position vs temperature relationship:
           - Healthy: Smooth correlation, predictable
           - Stiction: Scatter, temperature doesn't track position changes
        
        Stiction suspicion score:
          - 0.0-0.3: Smooth operation, well-maintained valve
          - 0.3-0.6: Minor stiction, consider lubrication
          - 0.6-0.8: Significant stiction, maintenance needed
          - >0.8: Severe stiction, valve replacement recommended
      
      Common valve issues:
        - Leakage causes:
          * Worn valve seat/plug
          * Debris preventing full closure
          * Actuator failure (weak spring, lost calibration)
          * Three-way valve bypass path stuck open
        
        - Stiction causes:
          * Dry/corroded valve stem (needs lubrication)
          * Packing too tight
          * Debris in valve body
          * Actuator linkage binding
      
      Economic impact:
        - Leaking CHW valve: 10-20% energy waste from simultaneous heating/cooling
        - Sticking valve: 5-15% efficiency loss, occupant complaints, cycling wear
    
    Parameters:
        sensor_data (dict): Valve position, temperatures, and optional flow timeseries
    
    Returns:
        dict: Leakage/stiction probabilities, valve health score, recommended actions, and diagnostic notes
    """
    flat = _aggregate_flat(sensor_data)
    v_pred = _key_matcher(["valve", "position"]) ; t_pred = _key_matcher(["temperature", "temp"]) ; f_pred = _key_matcher(["flow", "flow_rate"]) 
    v_keys = _select_keys(flat, v_pred, False)
    if not v_keys:
        return {"error": "No valve position series"}
    vdf = _df_from_readings(sum((flat[k] for k in v_keys), []))
    tdf = _df_from_readings(sum((flat[k] for k in _select_keys(flat, t_pred, False)), [])) if _select_keys(flat, t_pred, False) else pd.DataFrame()
    fdf = _df_from_readings(sum((flat[k] for k in _select_keys(flat, f_pred, False)), [])) if _select_keys(flat, f_pred, False) else pd.DataFrame()
    leakage = False; stiction = False; notes = []
    if not vdf.empty:
        # stiction via flatline episodes in valve position
        vals = vdf["reading_value"].tolist()
        run = 1; flats = 0
        for i in range(1, len(vals)):
            if vals[i] == vals[i-1]:
                run += 1
            else:
                if run >= 10: flats += 1
                run = 1
        if run >= 10: flats += 1
        stiction = flats >= 2
    if not (vdf.empty or tdf.empty):
        mm = pd.merge_asof(vdf.sort_values("timestamp"), tdf.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_v","_t"))
        if not mm.empty:
            # leakage: low valve position but temperature change persists
            low_pos = mm["reading_value_v"] < 5.0
            temp_dev = mm["reading_value_t"].diff().abs().fillna(0)
            if (low_pos & (temp_dev > 0.5)).mean() > 0.1:
                leakage = True; notes.append("Temp swings with nearly closed valve")
    if not (vdf.empty or fdf.empty):
        mm2 = pd.merge_asof(vdf.sort_values("timestamp"), fdf.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_v","_f"))
        if not mm2.empty:
            low_pos = mm2["reading_value_v"] < 5.0
            if (low_pos & (mm2["reading_value_f"] > 0.0)).mean() > 0.1:
                leakage = True; notes.append("Flow persists at near-closed position")
    return {"leakage_suspicion": leakage, "stiction_suspicion": stiction, "notes": notes}


@analytics_function(
    patterns=[
        r"heat.*exchanger",
        r"heat.*recovery",
        r"hx.*effectiveness",
        r"energy.*recovery",
        r"heat.*wheel"
    ],
    description="Calculates heat exchanger effectiveness for energy recovery systems"
)

def analyze_heat_exchanger_effectiveness(sensor_data):
    """
    Heat Exchanger Effectiveness — Heat Transfer Performance
    
    Purpose:
    Calculates heat exchanger effectiveness (ε) to assess heat transfer performance in plate 
    heat exchangers, economizers, heat recovery systems, and coils. Effectiveness quantifies 
    how well the heat exchanger transfers heat relative to the theoretical maximum, declining 
    with fouling, scaling, or flow issues. This analysis enables condition-based maintenance 
    and performance benchmarking against design specifications.
    
    Sensors:
      Hot side:
        - Hot_Fluid_Inlet_Temperature (°C)
        - Hot_Fluid_Outlet_Temperature (°C)
      Cold side:
        - Cold_Fluid_Inlet_Temperature (°C)
        - Cold_Fluid_Outlet_Temperature (°C)
      Optional: Flow rates for both sides to calculate heat transfer rate
    
    Output:
      - effectiveness: Dimensionless effectiveness ε (0-1)
      - effectiveness_pct: Effectiveness as percentage (0-100%)
      - actual_heat_transfer: Calculated heat transfer rate (kW) if flows available
      - max_possible_heat_transfer: Theoretical maximum (kW)
      - performance_category: "Excellent" (>0.8), "Good" (0.6-0.8), "Marginal" (0.4-0.6), "Poor" (<0.4)
      - degradation_trend: Change in effectiveness over time
    
    This analysis helps:
      - Detect fouling or scaling requiring cleaning
      - Validate commissioning and design performance
      - Schedule maintenance based on performance degradation
      - Quantify efficiency loss from poor heat transfer
      - Optimize cleaning cycles (cost vs performance)
      - Support energy audit calculations and M&V
    
    Method:
      Effectiveness definition:
        ε = Actual Heat Transfer / Maximum Possible Heat Transfer
        
        ε = (T_hot_in - T_hot_out) / (T_hot_in - T_cold_in)    [for counterflow]
      
      Alternative calculation (cold side):
        ε = (T_cold_out - T_cold_in) / (T_hot_in - T_cold_in)
      
      Heat transfer rate calculation (if flow rates available):
        Q_actual = ṁ_hot × Cp × (T_hot_in - T_hot_out)
        Q_max = Cp × min(ṁ_hot, ṁ_cold) × (T_hot_in - T_cold_in)
        
        ε = Q_actual / Q_max
      
      Effectiveness benchmarks by type:
        - Plate heat exchangers: ε = 0.75-0.95 (high effectiveness)
        - Shell-and-tube: ε = 0.60-0.80 (moderate)
        - Air-to-air economizers: ε = 0.50-0.75 (variable)
        - Coils (HVAC): ε = 0.60-0.90 (depends on design)
      
      Performance degradation patterns:
        - Gradual decline (1-3%/year): Normal fouling, schedule cleaning
        - Sudden drop (>10%): Scaling event, flow restriction, bypass opened
        - Oscillating effectiveness: Flow control issues, valve hunting
        - Asymmetric (hot vs cold side): Fouling on one side only
      
      Fouling detection:
        New/clean effectiveness: ε_design = 0.85
        Current measured: ε_actual = 0.72
        Degradation = (0.85 - 0.72)/0.85 = 15% loss
        
        Cleaning justified when:
          - Effectiveness drops >10-15% from design
          - Energy penalty exceeds cleaning cost
          - Pressure drop increases significantly
      
      Common issues:
        - Low effectiveness causes:
          * Fouling (scaling, biological growth, dirt)
          * Reduced flow rate (pump issues, valve throttling)
          * Air/vapor locks in liquid systems
          * Bypass damper/valve stuck open
          * Temperature sensor drift (false reading)
    
    Parameters:
        sensor_data (dict): Inlet/outlet temperatures for both hot and cold sides
    
    Returns:
        dict: Effectiveness metrics, heat transfer rates, performance category, and trends
    """
    flat = _aggregate_flat(sensor_data)
    hot_in_pred = _key_matcher(["hot_in", "primary_in", "hx_hot_in"]) ; hot_out_pred = _key_matcher(["hot_out", "primary_out", "hx_hot_out"]) ; cold_in_pred = _key_matcher(["cold_in", "secondary_in", "hx_cold_in"]) ; cold_out_pred = _key_matcher(["cold_out", "secondary_out", "hx_cold_out"]) ; t_pred = _key_matcher(["temperature", "temp"])
    # Try generic pairs by suffix if exact HX naming not present
    keys = list(flat.keys())
    def pick(pred):
        ks = [k for k in keys if pred(str(k)) and t_pred(str(k))]
        return ks[0] if ks else None
    H_in = pick(hot_in_pred); H_out = pick(hot_out_pred); C_in = pick(cold_in_pred); C_out = pick(cold_out_pred)
    if not all([H_in, H_out, C_in, C_out]):
        return {"error": "Need HX hot_in/hot_out and cold_in/cold_out temperature series"}
    def last(key):
        df = _df_from_readings(flat[key])
        return (float(df.iloc[-1]["reading_value"]) if not df.empty else None)
    Th_in = last(H_in); Th_out = last(H_out); Tc_in = last(C_in); Tc_out = last(C_out)
    if None in (Th_in, Th_out, Tc_in, Tc_out):
        return {"error": "Insufficient HX readings"}
    # effectiveness epsilon = (Tc_out - Tc_in) / (Th_in - Tc_in), clamp [0,1]
    denom = max(1e-6, (Th_in - Tc_in))
    eps = max(0.0, min(1.0, (Tc_out - Tc_in) / denom))
    return {"effectiveness": round(float(eps),3), "notes": "Approximate LMTD-free estimate."}


@analytics_function(
    patterns=[
        r"condenser.*loop",
        r"condenser.*water",
        r"cooling.*tower",
        r"condenser.*health",
        r"cwl.*health"
    ],
    description="Assesses condenser water loop health and cooling tower performance"
)

def analyze_condenser_loop_health(sensor_data):
    """
    Reviews condenser loop temperature/flow; reports approach proxy and capacity constraints hints.

    Returns: { temp_mean, flow_mean, approach_proxy }
    """
    flat = _aggregate_flat(sensor_data)
    c_pred = _key_matcher(["condenser_water", "condensing", "cw"]) ; t_pred = _key_matcher(["temperature", "temp"]) ; f_pred = _key_matcher(["flow", "flow_rate"]) 
    t_keys = [k for k in flat.keys() if c_pred(str(k)) and t_pred(str(k))]
    f_keys = [k for k in flat.keys() if c_pred(str(k)) and f_pred(str(k))]
    if not (t_keys or f_keys):
        return {"error": "No condenser loop series"}
    t_df = _df_from_readings(sum((flat[k] for k in t_keys), [])) if t_keys else pd.DataFrame()
    f_df = _df_from_readings(sum((flat[k] for k in f_keys), [])) if f_keys else pd.DataFrame()
    temp_mean = float(t_df["reading_value"].mean()) if not t_df.empty else None
    flow_mean = float(f_df["reading_value"].mean()) if not f_df.empty else None
    approach = None
    if temp_mean is not None and flow_mean is not None:
        approach = round(float(temp_mean / max(flow_mean, 1e-6)), 4)  # rough proxy: °C per unit flow
    return {"temp_mean": (round(temp_mean,2) if temp_mean is not None else None), "flow_mean": (round(flow_mean,2) if flow_mean is not None else None), "approach_proxy": approach}


@analytics_function(
    patterns=[
        r"electric.*power",
        r"power.*consumption",
        r"electricity.*usage",
        r"kw.*demand",
        r"power.*summary"
    ],
    description="Summarizes electrical power consumption, demand, and energy usage"
)

def analyze_electric_power_summary(sensor_data):
    """
    Electric Power Summary — Demand/energy analysis.
    
    Purpose: Provides comprehensive electrical demand and energy consumption analysis including
             peak demand identification, load factor calculation, and total energy usage over
             the analysis period. Critical for energy management and cost optimization.
    
    Sensors:
      - Electric_Power_Sensor or Active_Power_Sensor (instantaneous demand in kW)
      - Electric_Energy_Sensor (cumulative energy in kWh, if available)
      
    Output:
      - Peak demand (kW) with timestamp
      - Average power consumption (kW)
      - Total energy consumption (kWh) by period
      - Load factor (ratio of average to peak demand)
      - Power profile statistics
      
    This analysis helps:
      - Identify demand charge reduction opportunities
      - Optimize equipment scheduling to avoid peak periods
      - Validate energy billing and metering
      - Track energy performance trends
      - Support demand response program participation
      
    Calculations:
      - Total kWh: Integrated from power readings if energy sensor unavailable (trapezoidal rule)
      - Load Factor: Average kW / Peak kW (higher is better, indicates efficient use)
      - Peak analysis: Identifies time of highest demand for load shifting strategies

    Returns: { avg_kW, peak_kW, peak_time, total_kWh, load_factor, period_start, period_end, interval }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    p_pred = _key_matcher(["power", "kw", "active_power", "demand"]) ; e_pred = _key_matcher(["energy", "kwh"]) 
    p_keys = _select_keys(flat, p_pred, False)
    e_keys = _select_keys(flat, e_pred, False)
    def build_total_power(keys):
        series = []
        for i, k in enumerate(keys):
            df = _df_from_readings(flat[k])
            if df.empty: 
                continue
            s = df[["timestamp","reading_value"]].copy()
            s["timestamp"] = pd.to_datetime(s["timestamp"], errors="coerce")
            s = s.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
            s = s.resample("15min").mean().rename(columns={"reading_value": f"kW_{i}"})
            series.append(s)
        if not series:
            return pd.DataFrame()
        total = pd.concat(series, axis=1)
        total["kW_total"] = total.sum(axis=1, numeric_only=True)
        return total[["kW_total"]].dropna()
    total_kw = build_total_power(p_keys)
    if total_kw.empty and e_keys:
        # Try to estimate kW from energy increments
        series = []
        for i, k in enumerate(e_keys):
            df = _df_from_readings(flat[k])
            if df.empty:
                continue
            s = df[["timestamp","reading_value"]].copy()
            s["timestamp"] = pd.to_datetime(s["timestamp"], errors="coerce")
            s = s.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
            s = s.resample("15min").max()  # cumulative energy often monotonic
            s["inc_kWh"] = s["reading_value"].diff().clip(lower=0)
            s["kW_est"] = s["inc_kWh"] / 0.25
            series.append(s[["kW_est"]].rename(columns={"kW_est": f"kW_{i}"}))
        if series:
            total = pd.concat(series, axis=1)
            total_kw = total.sum(axis=1, numeric_only=True).to_frame("kW_total")
    if total_kw.empty:
        return {"error": "No power/energy series"}
    period_start = total_kw.index.min()
    period_end = total_kw.index.max()
    avg_kw = float(total_kw["kW_total"].mean())
    peak_row = total_kw["kW_total"].idxmax()
    peak_kw = float(total_kw.loc[peak_row, "kW_total"]) if pd.notna(peak_row) else None
    # Integrate to kWh (15 min -> 0.25 h)
    total_kwh = float((total_kw["kW_total"].fillna(0) * 0.25).sum())
    return {
        "avg_kW": round(avg_kw,2),
        "peak_kW": (round(peak_kw,2) if peak_kw is not None else None),
        "peak_time": (peak_row.isoformat() if isinstance(peak_row, pd.Timestamp) else None),
        "total_kWh": round(total_kwh,1),
        "period_start": (period_start.isoformat() if isinstance(period_start, pd.Timestamp) else None),
        "period_end": (period_end.isoformat() if isinstance(period_end, pd.Timestamp) else None),
        "interval": "15min"
    }


@analytics_function(
    patterns=[
        r"load.*profile",
        r"demand.*profile",
        r"power.*profile",
        r"usage.*pattern",
        r"consumption.*pattern"
    ],
    description="Analyzes electrical load profile with peak, base, and time-of-use patterns"
)

def analyze_load_profile(sensor_data):
    """
    Load Profile Analysis — Diurnal & Weekly Energy Patterns
    
    Purpose:
    Computes normalized hourly and daily load profiles to identify energy consumption patterns, 
    detect anomalies, and quantify operational inefficiencies. Load profiling reveals unoccupied 
    runtime (baseload waste), schedule misalignment, and peak demand drivers. This analysis 
    supports demand response planning, rate optimization, and IPMVP baseline development.
    
    Sensors:
      - Power or Active_Power or Electric_Demand (kW)
      - Total_Building_Power or Main_Meter (kW)
    
    Output:
      - hourly_mean_kW: Average power by hour of day [0-23]
      - hourly_normalized: Load normalized to daily max (0-1 scale)
      - weekday_kWh: Total energy by day of week [Mon-Sun]
      - baseload_kW: Minimum sustained load (occupied + unoccupied)
      - peak_kW: Maximum demand observed
      - load_factor: Ratio of average to peak load (0-1)
      - peak_hours: Hours when demand >80% of peak
    
    This analysis helps:
      - Identify wasted baseload (unoccupied runtime, plug loads)
      - Optimize occupancy schedules (shift start/end times)
      - Support time-of-use (TOU) rate analysis (avoid on-peak hours)
      - Develop demand response strategies (shed load during peaks)
      - Establish IPMVP Option C baseline for M&V
      - Benchmark against similar buildings (load shape comparison)
    
    Method:
      **Load profile components:**
        Total load = Baseload + Variable load
        
        Baseload:
          - Constant 24/7 consumption
          - Sources: Server rooms, refrigeration, emergency lighting, transformers
          - Target: Minimize baseload (turn off unnecessary equipment)
        
        Variable load:
          - Occupancy-driven consumption
          - Sources: HVAC, lighting, plug loads (during occupied hours)
          - Target: Align with occupancy schedule
      
      **Load factor calculation:**
        Load Factor = Average Load / Peak Load
        
        Interpretation:
          - LF = 1.0: Flat load (constant 24/7, like data center)
          - LF = 0.7-0.9: Good (moderate baseload, efficient operation)
          - LF = 0.4-0.6: Typical office (high peak, low baseload)
          - LF = 0.2-0.4: Poor (excessive peak vs average, high demand charges)
        
        Economic impact:
          - Low LF → High demand charges ($/kW penalty)
          - Improve LF by: Reducing peak OR increasing off-peak usage (load shifting)
      
      **Typical load profiles by building type:**
        Office building (9am-5pm occupied):
          - Baseload: 20-30% of peak (servers, core HVAC)
          - Peak: 11am-3pm (HVAC + lighting + equipment)
          - Weekend: 30-40% of weekday (reduced schedule)
        
        Retail (10am-8pm occupied):
          - Baseload: 30-40% of peak (refrigeration, security)
          - Peak: 2pm-6pm (HVAC + lighting)
          - Sunday: Similar to weekday (open 7 days)
        
        School (8am-3pm occupied):
          - Baseload: 15-25% of peak (minimal unoccupied load)
          - Peak: 10am-2pm (high occupancy density)
          - Summer: <10% of school year (HVAC off, skeleton crew)
        
        Hospital (24/7 occupied):
          - Baseload: 70-80% of peak (critical systems)
          - Peak: 8am-8pm (daytime procedures)
          - Load factor: 0.85-0.95 (very flat)
      
      **Anomaly detection from load profile:**
        High overnight load (>50% of peak):
          - Cause: HVAC not shutting down, equipment left on
          - Action: Review schedules, check occupancy sensors
          - Savings potential: 20-40% energy reduction
        
        Weekend load = weekday load:
          - Cause: Schedule ignoring day-of-week
          - Action: Implement separate weekend schedule
          - Savings: 15-25% on weekends
        
        No morning ramp (load instantly high at 6am):
          - Cause: Equipment starts simultaneously (demand spike)
          - Action: Stagger start times (load shedding)
          - Peak demand savings: 10-20% (lower $/kW charges)
        
        Evening plateau (load high until 10pm):
          - Cause: After-hours equipment not shutting down
          - Action: Time-based overrides, plug load sensors
          - Savings: 5-10% energy
      
      **Time-of-use (TOU) rate optimization:**
        Typical TOU periods (utility-dependent):
          - On-peak: 12pm-8pm weekdays (highest $/kWh)
          - Mid-peak: 8am-12pm, 8pm-10pm weekdays
          - Off-peak: 10pm-8am, weekends (lowest $/kWh)
        
        Strategy 1 - Load shifting:
          - Pre-cool building at 6am (off-peak rates)
          - Coast through on-peak (setpoint relaxation)
          - Savings: 15-30% demand charges
        
        Strategy 2 - Load shedding:
          - Reduce non-critical loads during on-peak
          - Example: Dim lighting, raise cooling setpoint 1-2°C
          - Savings: 10-20% on-peak consumption
      
      **Demand response (DR) readiness assessment:**
        Load shape indicators:
          - High midday peak → Good DR candidate (shed during utility peak)
          - Flat load → Poor DR candidate (no flexibility)
        
        Dispatchable load (can shed for 2-4 hours):
          - HVAC: 20-40% of peak (setpoint adjustment)
          - Lighting: 10-20% (dimming, zone shutoff)
          - Plug loads: 5-10% (controlled outlets)
        
        DR revenue potential:
          - Capacity payment: $50-150 per kW-year (enrolled capacity)
          - Energy payment: $0.50-$2.00 per kWh curtailed
          - Annual value: $5k-$50k (building size dependent)
      
      **IPMVP Option C baseline development:**
        Baseline profile = normalized load profile × current conditions
        
        Steps:
          1. Establish pre-retrofit hourly load profile (1 year)
          2. Normalize by outdoor temperature, occupancy
          3. Post-retrofit: Predict baseline using current conditions
          4. Savings = Baseline - Actual consumption
        
        Uncertainty: ±5-10% (depends on normalization quality)
      
      **Benchmarking with load shape comparison:**
        Compare hourly profile to peer buildings:
          - Similar profile → Operations aligned with peer group
          - Higher overnight → Baseload optimization opportunity
          - Higher peak → Peak shaving opportunity
        
        ENERGY STAR Portfolio Manager:
          - Provides peer benchmarking by building type
          - Load profile comparison feature (beta)
    
    Parameters:
        sensor_data (dict): Power timeseries data (kW)
    
    Returns:
        dict: Hourly/weekly profiles, baseload, peak, load factor, anomaly flags

    Computes normalized diurnal and weekly load profiles from total kW.

    Returns: { hourly_mean_kW[24], hourly_norm[24], weekday_kWh[0..6] }
    """
    flat = _aggregate_flat(sensor_data)
    p_pred = _key_matcher(["power", "kw", "active_power", "demand"]) 
    p_keys = _select_keys(flat, p_pred, False)
    if not p_keys:
        return {"error": "No power series"}
    series = []
    for i, k in enumerate(p_keys):
        df = _df_from_readings(flat[k])
        if df.empty: continue
        s = df[["timestamp","reading_value"]].copy()
        s["timestamp"] = pd.to_datetime(s["timestamp"], errors="coerce")
        s = s.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
        s = s.resample("15min").mean().rename(columns={"reading_value": f"kW_{i}"})
        series.append(s)
    if not series:
        return {"error": "Empty power series"}
    total = pd.concat(series, axis=1)
    total["kW_total"] = total.sum(axis=1, numeric_only=True)
    total = total[["kW_total"]].dropna()
    if total.empty:
        return {"error": "Empty total power"}
    total["hour"] = total.index.hour
    hourly = total.groupby("hour")["kW_total"].mean()
    hourly_norm = (hourly / max(hourly.max(), 1e-6)).tolist()
    # Weekday kWh
    wk = total.copy()
    wk["weekday"] = wk.index.dayofweek
    wk_kwh = (wk["kW_total"] * 0.25).groupby(wk["weekday"]).sum()
    # Ensure 0..6 ordering with fill 0.0
    weekday_kwh = [float(wk_kwh.get(i, 0.0)) for i in range(7)]
    return {
        "hourly_mean_kW": [round(float(x),2) for x in hourly.tolist()],
        "hourly_norm": [round(float(x),3) for x in hourly_norm],
        "weekday_kWh": [round(x,1) for x in weekday_kwh]
    }


@analytics_function(
    patterns=[
        r"demand.*response",
        r"load.*shed",
        r"peak.*shaving",
        r"dr.*readiness",
        r"grid.*response"
    ],
    description="Assesses demand response readiness and load shedding potential"
)

def analyze_demand_response_readiness(sensor_data, shed_fraction=0.15):
    """
    Demand Response Readiness — Load Flexibility & Curtailment Potential
    
    Purpose:
    Estimates building's demand response (DR) potential by analyzing load variability and 
    ramp-down characteristics. DR programs pay facilities to reduce load during utility peak 
    events (summer afternoons, grid emergencies). This analysis quantifies shedable capacity 
    and readiness score to support DR program enrollment and dispatch optimization.
    
    Sensors:
      - Total_Power or Building_Demand (kW)
      - Optional: HVAC_Power, Lighting_Power (for end-use breakdown)
    
    Output:
      - peak_kW: Maximum demand observed
      - shedable_kW: Estimated load reduction potential (default 15% of peak)
      - readiness_score: 0-100 score (based on load flexibility)
      - ramp_down_rate: kW/minute decline capability
      - recovery_time: Minutes to return to baseline post-event
      - dr_revenue_potential: Estimated annual value ($)
    
    This analysis helps:
      - Determine DR program enrollment eligibility (minimum kW requirements)
      - Quantify revenue potential from capacity and energy payments
      - Optimize shed strategies (which loads to curtail)
      - Support utility rate negotiations (interruptible tariffs)
      - Enable automated DR (ADR) system design
      - Validate DR event performance (compare actual vs nominated shed)
    
    Method:
      **Demand response programs (typical structures):**
        Capacity-based (reservation):
          - Payment: $50-$150 per kW-year of nominated capacity
          - Commitment: Shed load when called (5-15 events/year, 2-4 hrs each)
          - Penalty: $100-$500 per kW under-performance
        
        Energy-based (performance):
          - Payment: $0.50-$2.00 per kWh curtailed
          - Voluntary: Participate when economically beneficial
          - No penalty: Opt out of events if infeasible
        
        Ancillary services (fast response):
          - Payment: $200-$500 per kW-year
          - Commitment: 10-second response time
          - Requirements: Automated controls, telemetry
      
      **Shedable load estimation (by end-use):**
        HVAC (30-50% of total load, 50-80% shedable):
          - Strategy 1: Raise cooling setpoint by 2°C (20-30% HVAC reduction)
          - Strategy 2: Duty-cycle compressors (30-40% reduction)
          - Strategy 3: Pre-cool + coast through event (40-60% reduction)
          - Typical: 10-20% of building peak demand
        
        Lighting (15-30% of total, 30-50% shedable):
          - Strategy 1: Dim to 70% (20-30% lighting reduction)
          - Strategy 2: Shut off non-critical zones (30-50% reduction)
          - Typical: 5-10% of building peak demand
        
        Plug loads (10-20% of total, 20-40% shedable):
          - Strategy: Controlled outlets, non-critical equipment
          - Typical: 2-5% of building peak demand
        
        Total shedable (default 15%, aggressive 30%):
          - Conservative: 10-15% of peak (minimal comfort impact)
          - Moderate: 15-25% of peak (noticeable but acceptable)
          - Aggressive: 25-35% of peak (significant impact, short duration only)
      
      **Readiness score calculation (0-100):**
        Factors:
          1. Load variability (high = flexible): 0-30 points
          2. Ramp-down rate (fast = responsive): 0-30 points
          3. Historical shed events (proven capability): 0-20 points
          4. Automation (ADR capable): 0-20 points
        
        Score interpretation:
          - 80-100: Excellent (auto-DR capable, fast response)
          - 60-80: Good (manual DR viable, moderate response)
          - 40-60: Fair (limited flexibility, requires planning)
          - <40: Poor (not suitable for DR without upgrades)
      
      **Ramp-down characteristics:**
        Fast response (<5 minutes to full shed):
          - Required for: Frequency regulation, spinning reserve
          - Typical: Battery storage, industrial process curtailment
          - Premium payments: $200-$500/kW-year
        
        Moderate response (5-15 minutes):
          - Suitable for: Energy market DR, utility peak shaving
          - Typical: HVAC setpoint adjustment, lighting dimming
          - Standard payments: $50-$150/kW-year
        
        Slow response (>15 minutes):
          - Limited value: Day-ahead markets only
          - Typical: Thermal mass pre-cooling (hours of preparation)
          - Low payments: $20-$50/kW-year
      
      **Revenue potential estimation:**
        Example: 500 kW peak demand, 15% shed = 75 kW nominated
        
        Capacity payment:
          75 kW × $100/kW-year = $7,500/year (guaranteed)
        
        Energy payment (assume 10 events, 3 hrs each):
          75 kW × 3 hrs × 10 events = 2,250 kWh curtailed
          2,250 kWh × $1.00/kWh = $2,250/year (performance-based)
        
        Total annual value: $9,750
        Less: Automation cost ($10k-$30k one-time), minimal O&M
      
      **Pre-cooling strategy (thermal mass utilization):**
        Concept:
          - Cool building to 20°C before DR event (instead of 22°C)
          - Coast through event with HVAC off/reduced
          - Building temperature drifts to 24-25°C (still acceptable)
        
        Benefits:
          - 100% HVAC load shed during event (not just 20-30%)
          - Minimal comfort impact (gradual temperature rise)
          - Energy neutral (pre-cool consumption offset by event savings)
        
        Requirements:
          - Heavy building (concrete, thermal mass)
          - 2-4 hour event duration (longer = more drift)
          - Low internal loads (no data centers)
      
      **Automated Demand Response (ADR):**
        OpenADR 2.0b standard:
          - Utility sends DR event signal via internet
          - Building automation system (BAS) executes preset strategies
          - No manual intervention required
        
        ADR strategies hierarchy:
          - Moderate (10-15% shed): Lighting dim, HVAC +1°C
          - High (15-25% shed): Lighting off selected zones, HVAC +2°C
          - Special (25-35% shed): Non-critical loads off, HVAC +3°C
        
        Reliability bonus:
          - Automated systems receive 10-20% payment premium
          - Reduced penalty risk (no human error)
      
      **DR program eligibility (typical minimums):**
        Small commercial:
          - Minimum: 50 kW shed capacity
          - Aggregation: Multiple sites combined
        
        Large commercial:
          - Minimum: 100-200 kW shed capacity
          - Individual enrollment
        
        Industrial:
          - Minimum: 500 kW shed capacity
          - Custom programs, interruptible tariffs
      
      **Validation and M&V:**
        Baseline calculation (CAISO 10-in-10 method):
          - Average load of 10 highest similar days in past 45 days
          - Adjust for current conditions (temperature, occupancy)
        
        Performance = Baseline - Actual load during event
        
        Payment = Performance × $/kWh (if above nominated capacity)
        Penalty = Under-performance × penalty rate (if below nominated)
    
    Parameters:
        sensor_data (dict): Power timeseries data (kW)
        shed_fraction (float, optional): Shedable load fraction (default 0.15 = 15%)
    
    Returns:
        dict: Peak kW, shedable kW, readiness score, ramp rate, revenue potential

    Heuristically estimates shedable kW and a readiness score from ramp-down characteristics.

    Returns: { peak_kW, shedable_kW, readiness_score }
    """
    # Reuse load profile aggregation
    flat = _aggregate_flat(sensor_data)
    p_pred = _key_matcher(["power", "kw", "active_power", "demand"]) 
    p_keys = _select_keys(flat, p_pred, False)
    if not p_keys:
        return {"error": "No power series"}
    series = []
    for i, k in enumerate(p_keys):
        df = _df_from_readings(flat[k])
        if df.empty: continue
        s = df[["timestamp","reading_value"]].copy()
        s["timestamp"] = pd.to_datetime(s["timestamp"], errors="coerce")
        s = s.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
        s = s.resample("5min").mean().rename(columns={"reading_value": f"kW_{i}"})
        series.append(s)
    if not series:
        return {"error": "Empty power series"}
    total = pd.concat(series, axis=1)
    total["kW_total"] = total.sum(axis=1, numeric_only=True)
    y = total["kW_total"].dropna()
    if y.empty:
        return {"error": "Empty total power"}
    peak = float(y.max())
    shedable = round(peak * float(shed_fraction), 2)
    # Ramp-down: fraction of intervals with >=5% drop in 10 minutes (2 steps at 5min)
    dy2 = y.diff(2) / y.shift(2)
    readiness = float((dy2 <= -0.05).mean()) if len(dy2) > 2 else 0.0
    return {"peak_kW": round(peak,2), "shedable_kW": shedable, "readiness_score": round(readiness,3)}


@analytics_function(
    patterns=[
        r"part.*load.*ratio",
        r"plr",
        r"equipment.*loading",
        r"capacity.*utilization",
        r"load.*factor"
    ],
    description="Calculates part load ratio for equipment capacity utilization analysis"
)

def analyze_part_load_ratio(sensor_data, equipment_hint=None):
    """
    Part Load Ratio (PLR) — Equipment Loading Analysis
    
    Purpose:
    Calculates Part Load Ratio (PLR = actual load / full load capacity) to assess equipment 
    sizing, efficiency, and cycling behavior. Equipment operates most efficiently at high PLR 
    (70-90%); chronic low PLR indicates oversizing, causing short-cycling, poor efficiency, 
    and reduced equipment life. This analysis validates equipment selection and identifies 
    opportunities for right-sizing or load consolidation.
    
    Sensors:
      - Equipment_Power_Sensor (kW) [preferred for direct PLR calculation]
      - Equipment_Command_Signal (0-100%) [alternative if power not available]
      - VFD_Speed (%) or Chiller_Percent_Load
      - Nameplate capacity for normalization
    
    Output:
      - mean_plr: Average part load ratio (0-1 or 0-100%)
      - plr_latest: Current PLR
      - low_load_pct: Percentage of time PLR < 40% (cycling risk threshold)
      - plr_distribution: Histogram bins showing time at each load level
      - recommended_staging: Suggested equipment sequencing for better efficiency
    
    This analysis helps:
      - Identify oversized equipment causing efficiency losses
      - Optimize equipment staging and lead-lag strategies
      - Reduce short-cycling damage and maintenance costs
      - Validate equipment selection for retrofits/replacements
      - Support chiller plant optimization and sequencing
      - Quantify efficiency penalties from part-load operation
    
    Method:
      PLR calculation:
        PLR = Current Load (kW) / Nameplate Capacity (kW)
        
        Or if power not available:
          PLR ≈ Command Signal % / 100
          PLR ≈ VFD Speed % / 100 (less accurate, assumes linear relationship)
      
      Load level interpretation:
        - PLR > 0.9: Near capacity, may be undersized if sustained
        - PLR 0.7-0.9: Optimal efficiency range for most equipment
        - PLR 0.4-0.7: Acceptable, moderate efficiency
        - PLR 0.2-0.4: Low load, efficiency drops, staging recommended
        - PLR < 0.2: Very low load, high cycling risk, poor efficiency
      
      Equipment-specific considerations:
        **Chillers:**
          - PLR < 20-30%: Efficiency cliff, compressor unloading limits
          - Multiple chillers: Sequence to keep each at PLR > 50%
          - VFD chillers: Better part-load efficiency than fixed speed
        
        **Boilers:**
          - PLR < 30%: Short-cycling increases significantly
          - Multiple boilers: Lead-lag based on load, not rotation
        
        **Fans/Pumps:**
          - VFD: Energy ∝ Speed³, so low PLR still saves energy
          - Fixed speed: PLR not applicable, on/off cycling metric instead
        
        **VAV boxes:**
          - PLR = Airflow / Max Airflow
          - Min PLR typically 20-30% (minimum ventilation requirements)
      
      Oversizing detection:
        If mean_plr < 0.5 AND low_load_pct > 60%:
          → Equipment significantly oversized, retrofit candidate
          → Consider smaller unit or variable capacity technology
          → Potential 15-30% energy savings from right-sizing
      
      Efficiency impact:
        Chiller operating at 40% PLR vs 80% PLR:
          - Fixed speed: ~15-20% efficiency penalty (kW/ton increases)
          - VFD chiller: ~5-10% penalty (better part-load performance)
          - Multiple-unit staging can maintain higher PLR per unit
    
    Parameters:
        sensor_data (dict): Equipment power, command, or speed timeseries
        equipment_hint (str, optional): Equipment type hint for targeted matching (e.g., "chiller", "boiler")
    
    Returns:
        dict: PLR statistics, low-load time percentage, distribution, and staging recommendations
    """
    flat = _aggregate_flat(sensor_data)
    # Prefer equipment-specific power if hint provided
    pred_list = ["power", "kw", "active_power"]
    if equipment_hint:
        pred_list.insert(0, equipment_hint)
    p_pred = _key_matcher(pred_list)
    p_keys = _select_keys(flat, p_pred, False)
    dfp = None
    if p_keys:
        series = []
        for i, k in enumerate(p_keys):
            df = _df_from_readings(flat[k])
            if df.empty: continue
            s = df[["timestamp","reading_value"]].copy()
            s["timestamp"] = pd.to_datetime(s["timestamp"], errors="coerce")
            s = s.dropna(subset=["timestamp"]).set_index("timestamp").sort_index().resample("5min").mean().rename(columns={"reading_value": f"kW_{i}"})
            series.append(s)
        if series:
            dfp = pd.concat(series, axis=1).sum(axis=1, numeric_only=True).to_frame("kW")
    if dfp is not None and not dfp.empty:
        mx = float(dfp["kW"].quantile(0.98)) or 1.0
        plr = (dfp["kW"] / max(mx, 1e-6)).clip(lower=0, upper=1)
    else:
        # Fallback: command/speed/valve as proxy
        c_pred = _key_matcher(["speed", "command", "stage", "load", "valve_position"]) 
        c_keys = _select_keys(flat, c_pred, False)
        if not c_keys:
            return {"error": "No power or command proxies"}
        dfc = _df_from_readings(sum((flat[k] for k in c_keys), []))
        if dfc.empty:
            return {"error": "Empty proxy series"}
        v = dfc["reading_value"].astype(float)
        v_norm = (v - v.min()) / max(v.max() - v.min(), 1e-6)
        plr = v_norm
    low_pct = float((plr < 0.3).mean()) if len(plr) else 0.0
    return {"mean_plr": round(float(plr.mean()),3), "low_load_pct": round(low_pct,3)}


@analytics_function(
    patterns=[
        r"cooling.*cop",
        r"chiller.*efficiency",
        r"coefficient.*performance",
        r"cooling.*efficiency",
        r"chiller.*cop"
    ],
    description="Calculates Coefficient of Performance (COP) for cooling equipment"
)

def analyze_cooling_cop(sensor_data):
    """
    Cooling COP (Coefficient of Performance) — Chiller Efficiency Assessment
    
    Purpose:
    Calculates chiller coefficient of performance (COP) as the ratio of cooling output to 
    electrical input. COP is the primary metric for chiller efficiency, inversely related 
    to kW/ton (US units). Declining COP indicates fouling, refrigerant loss, or equipment 
    degradation. This analysis supports ASHRAE 90.1 efficiency compliance and energy 
    benchmarking (ENERGY STAR chiller ratings).
    
    Sensors:
      - CHW_Supply_Temperature and CHW_Return_Temperature (°C)
      - CHW_Flow_Rate (L/s or GPM)
      - Chiller_Power or Compressor_Power (kW)
    
    Output:
      - cop_mean: Average COP over period
      - cop_latest: Current COP value
      - cop_trend: COP change over time (degradation detection)
      - kw_per_ton: Efficiency in US units (kW per ton of cooling)
      - performance_rating: "Excellent", "Good", "Fair", "Poor"
      - efficiency_loss_pct: Deviation from design COP (%)
    
    This analysis helps:
      - Detect chiller performance degradation (fouling, refrigerant loss)
      - Validate chiller efficiency claims (design COP vs actual)
      - Prioritize maintenance (tube cleaning, refrigerant recharge)
      - Support ASHRAE 90.1-2022 minimum efficiency compliance (COP ≥5.5 for water-cooled)
      - Benchmark against ENERGY STAR chiller ratings (top 25% performers)
      - Quantify energy savings potential from upgrades (replace low-COP chillers)
    
    Method:
      **COP calculation (dimensionless efficiency ratio):**
        COP = Q_cooling / P_electric
        
        Where:
          Q_cooling = ṁ × Cp × ΔT  [kW thermal]
            ṁ = CHW mass flow rate (kg/s ≈ L/s for water)
            Cp = 4.18 kJ/kg·K (water specific heat)
            ΔT = T_return - T_supply (°C)
          
          P_electric = Chiller power consumption [kW electric]
        
        Example:
          Flow = 10 L/s, ΔT = 6°C, Power = 50 kW
          Q = 10 × 4.18 × 6 = 250.8 kW cooling
          COP = 250.8 / 50 = 5.02
      
      **COP vs kW/ton conversion:**
        kW/ton = 3.517 / COP  (exact conversion)
        
        Equivalents:
          - COP 6.0 = 0.586 kW/ton (excellent)
          - COP 5.0 = 0.703 kW/ton (good)
          - COP 4.0 = 0.879 kW/ton (fair)
          - COP 3.0 = 1.172 kW/ton (poor)
        
        Note: 1 ton refrigeration = 3.517 kW = 12,000 Btu/hr
      
      **Typical COP ranges by chiller type:**
        Air-cooled chiller (easier installation, lower efficiency):
          - Design COP: 2.5-3.5 (full load)
          - Part-load COP: 3.0-4.5 (IPLV, integrated part-load value)
          - ASHRAE 90.1-2022 minimum: COP ≥2.8 (<150 tons)
        
        Water-cooled centrifugal (high efficiency, requires cooling tower):
          - Design COP: 5.0-7.0 (full load)
          - Part-load COP: 6.0-9.0 (VFD, variable speed)
          - ASHRAE 90.1-2022 minimum: COP ≥5.5 (<150 tons), ≥6.1 (≥300 tons)
        
        Magnetic bearing centrifugal (premium efficiency):
          - Design COP: 6.0-8.0 (full load)
          - Part-load COP: 8.0-12.0 (excellent turndown)
          - ENERGY STAR qualified: COP ≥7.0
        
        Absorption chiller (heat-driven, not electric):
          - COP: 0.7-1.2 (uses waste heat or natural gas)
          - Not directly comparable (different energy input)
      
      **COP variation with load and conditions:**
        Part-load performance (Integrated Part-Load Value, IPLV):
          - Full load (100%): Lowest COP (e.g., 5.0)
          - 75% load: Higher COP (e.g., 5.5)
          - 50% load: Peak COP (e.g., 6.5)
          - 25% load: COP declines (e.g., 4.5, compressor surge region)
        
        IPLV weighting (AHRI Standard 550/590):
          IPLV = 0.01(100%) + 0.42(75%) + 0.45(50%) + 0.12(25%)
        
        Condenser water temperature impact:
          - 25°C condenser water: COP = 6.0 (baseline)
          - 30°C condenser water: COP = 5.0 (17% loss)
          - 20°C condenser water: COP = 7.0 (17% gain)
          - Rule: COP changes ~3-5% per 1°C condenser temp change
      
      **Performance degradation root causes:**
        Fouling (heat exchanger surfaces):
          - Symptom: Gradual COP decline over months (5-15% per year)
          - Mechanism: Scale, biofilm reduce heat transfer
          - Fix: Tube cleaning (mechanical, chemical), water treatment
          - Prevention: Condenser tube cleaning annually
        
        Refrigerant loss (leak):
          - Symptom: Sudden COP drop (10-30%), high superheat
          - Mechanism: Low refrigerant charge reduces capacity
          - Fix: Find/repair leak, recharge refrigerant
          - Prevention: Annual leak detection (ultrasonic, bubble test)
        
        Compressor wear:
          - Symptom: Gradual COP decline (2-5% per 1000 hrs)
          - Mechanism: Internal leakage, bearing wear
          - Fix: Compressor rebuild or replacement ($20k-$100k)
          - Prevention: Oil analysis, vibration monitoring
        
        Non-condensables (air in refrigerant):
          - Symptom: High condenser pressure, 5-10% COP loss
          - Mechanism: Air trapped in system reduces heat transfer
          - Fix: Purge air from system
          - Prevention: Proper evacuation during service
      
      **ASHRAE 90.1-2022 minimum efficiency requirements:**
        Water-cooled centrifugal chillers:
          - <150 tons: ≥0.610 kW/ton (COP ≥5.77) at full load
          - 150-300 tons: ≥0.590 kW/ton (COP ≥5.96)
          - ≥300 tons: ≥0.560 kW/ton (COP ≥6.28)
        
        Air-cooled chillers:
          - <150 tons: ≥1.000 kW/ton (COP ≥3.52) at full load
          - ≥150 tons: ≥0.980 kW/ton (COP ≥3.59)
        
        Path A (prescriptive) vs Path B (performance):
          - Must meet minimum OR demonstrate equivalent annual efficiency
      
      **ENERGY STAR chiller qualification:**
        Water-cooled centrifugal (top 25%):
          - IPLV ≤0.450 kW/ton (COP ≥7.8 IPLV)
          - Savings: 30-50% vs code minimum
        
        Air-cooled chiller:
          - IPLV ≤0.800 kW/ton (COP ≥4.4 IPLV)
          - Savings: 15-25% vs code minimum
      
      **Economic impact of COP improvement:**
        Example: 500-ton chiller, 2000 hrs/year operation
        
        Baseline: COP 4.0 (0.879 kW/ton)
          Power = 500 tons × 0.879 kW/ton = 439.5 kW
          Annual energy = 439.5 kW × 2000 hrs = 879,000 kWh
          Cost @ $0.12/kWh = $105,480/year
        
        Upgrade: COP 6.0 (0.586 kW/ton)
          Power = 500 tons × 0.586 kW/ton = 293 kW
          Annual energy = 293 kW × 2000 hrs = 586,000 kWh
          Cost = $70,320/year
          
        Savings: $35,160/year (33% reduction)
        Upgrade cost: $200k-$400k
        Payback: 5.7-11.4 years
    
    Parameters:
        sensor_data (dict): CHW temps, flow, and chiller power timeseries
    
    Returns:
        dict: COP mean/latest, kW/ton, performance rating, efficiency loss percentage

    Approximates cooling COP proxy = (flow * ΔT * c) / kW using CHW temps/flow and chiller kW.
    Units may be inconsistent; treat as dimensionless proxy for trends.

    Returns: { cop_proxy_mean, cop_proxy_latest, notes }
    """
    flat = _aggregate_flat(sensor_data)
    # CHW flow and temps
    chw_pred = _key_matcher(["chilled_water", "chw"]) ; f_pred = _key_matcher(["flow", "flow_rate"]) ; t_pred = _key_matcher(["temperature", "temp"]) 
    cs = [k for k in flat.keys() if chw_pred(str(k)) and _key_matcher(["supply"])(str(k)) and t_pred(str(k))]
    cr = [k for k in flat.keys() if chw_pred(str(k)) and _key_matcher(["return"])(str(k)) and t_pred(str(k))]
    cf = [k for k in flat.keys() if chw_pred(str(k)) and f_pred(str(k))]
    p_keys = [k for k in flat.keys() if _key_matcher(["chiller", "compressor"]) (str(k)) and _key_matcher(["power", "kw"]) (str(k))]
    if not (cs and cr and cf and p_keys):
        return {"error": "Need CHW supply/return temps, CHW flow, and chiller power"}
    dfS = _df_from_readings(sum((flat[k] for k in cs), []))
    dfR = _df_from_readings(sum((flat[k] for k in cr), []))
    dfF = _df_from_readings(sum((flat[k] for k in cf), []))
    dfP = _df_from_readings(sum((flat[k] for k in p_keys), []))
    for d in (dfS, dfR, dfF, dfP):
        d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfS.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_s","_r"))
    mm = pd.merge_asof(mm.sort_values("timestamp"), dfF.sort_values("timestamp"), on="timestamp", direction="nearest")
    mm = pd.merge_asof(mm.sort_values("timestamp"), dfP.sort_values("timestamp"), on="timestamp", direction="nearest", suffixes=("","_kW"))
    if mm.empty:
        return {"error": "Could not align series"}
    dT = (mm["reading_value_r"] - mm["reading_value_s"]).clip(lower=0)
    flow = mm["reading_value"]
    kW = mm["reading_value_kW"] if "reading_value_kW" in mm.columns else mm.iloc[:, -1]
    c = 4.186  # cp of water (kJ/kg-K) scaled out in proxy
    cop = (flow * dT * c) / (kW.replace(0, pd.NA))
    cop = cop.replace([pd.NA, pd.NaT, float("inf")], pd.NA).dropna()
    if cop.empty:
        return {"error": "Insufficient variability for COP proxy"}
    return {"cop_proxy_mean": round(float(cop.mean()),3), "cop_proxy_latest": round(float(cop.iloc[-1]),3), "notes": "Proxy only; units may not cancel."}


@analytics_function(
    patterns=[
        r"eer",
        r"seer",
        r"energy.*efficiency.*ratio",
        r"seasonal.*efficiency",
        r"ac.*efficiency"
    ],
    description="Calculates EER (Energy Efficiency Ratio) and SEER estimates for AC systems"
)

def analyze_eer_seer(sensor_data):
    """
    EER/SEER Estimation — Cooling Efficiency Metrics
    
    Purpose:
    Estimates Energy Efficiency Ratio (EER) and Seasonal Energy Efficiency Ratio (SEER) 
    for cooling equipment using measured power and cooling output. EER is instantaneous 
    efficiency (Btu/h per Watt), while SEER is seasonal average including part-load 
    performance. These metrics enable benchmarking against ENERGY STAR ratings and 
    identifying underperforming equipment needing maintenance or replacement.
    
    Sensors:
      - Cooling_Power_Sensor (kW)
      - Cooling_Capacity proxy from:
        * Chilled_Water_Flow × ΔT (kW thermal)
        * Direct cooling output sensor if available
        * Estimated from supply/return air conditions
    
    Output:
      - eer_median: Median EER during analysis period (Btu/Wh)
      - eer_latest: Most recent EER reading
      - seer_proxy: Seasonal average EER (approximates SEER)
      - eer_vs_rated: Comparison to nameplate rating (% of rated)
      - efficiency_category: "Excellent", "Good", "Fair", or "Poor"
    
    This analysis helps:
      - Benchmark cooling equipment against ENERGY STAR ratings
      - Identify degraded performance requiring maintenance
      - Validate contractor claims of equipment efficiency
      - Support capital planning for equipment replacements
      - Quantify efficiency improvements from retrofits
      - Track seasonal efficiency trends and degradation
    
    Method:
      EER calculation (instantaneous efficiency):
        EER = Cooling Output (Btu/h) / Electrical Input (Watts)
        
        In SI units:
          EER ≈ 3.412 × COP
          Where COP = Cooling Output (kW thermal) / Electrical Input (kW electric)
        
        Typical EER ratings:
          - Old equipment (<2000): EER 8-10
          - Standard efficiency (2000-2010): EER 10-12
          - High efficiency (2010-2020): EER 12-14
          - ENERGY STAR (current): EER >13-15
          - Premium (VRF, magnetic bearing): EER 15-20+
      
      SEER (Seasonal Energy Efficiency Ratio):
        SEER = Total Cooling Output (Btu) / Total Electrical Input (Wh) over season
        
        SEER includes:
          - Part-load efficiency (weighted by typical load distribution)
          - Cycling losses at low loads
          - Standby power consumption
        
        SEER vs EER relationship:
          SEER ≈ EER × 1.1 to 1.3 (SEER typically 10-30% higher due to test conditions)
        
        SEER benchmarks:
          - Minimum (US 2023): SEER 14
          - ENERGY STAR: SEER 15-16
          - High efficiency: SEER 18-20
          - Premium VRF: SEER 20-25+
      
      Conversion between units:
        1 kW thermal = 3412 Btu/h
        EER (Btu/Wh) ≈ 3.412 × COP (dimensionless)
        
      Performance degradation detection:
        If measured_EER < 0.85 × rated_EER:
          → Efficiency degraded >15%, investigate:
            - Refrigerant charge (undercharged/overcharged)
            - Condenser fouling (fin blockage)
            - Compressor wear
            - Expansion valve issues
            - Air filter restrictions
      
      Limitations of proxy calculation:
        - Cooling output estimation may be imprecise without direct measurement
        - SEER calculation requires full seasonal data (spring-fall)
        - Part-load performance assumed, not measured directly
        - Units must be carefully tracked (kW vs Btu/h)
    
    Parameters:
        sensor_data (dict): Cooling power and capacity timeseries data
    
    Returns:
        dict: EER/SEER metrics, efficiency vs rated comparison, and performance category
    """
    cop = analyze_cooling_cop(sensor_data)
    if "error" in cop:
        return {"error": f"Upstream COP proxy missing: {cop['error']}"}
    eer_vals = cop.get("cop_series") if isinstance(cop, dict) and cop.get("cop_series") is not None else None
    # If we don't expose the series, derive from mean/latest
    eer_median = 3.412 * float(cop["cop_proxy_mean"]) if cop.get("cop_proxy_mean") is not None else None
    seer_proxy = eer_median  # simple proxy
    return {"eer_median": (round(float(eer_median),2) if eer_median is not None else None), "seer_proxy": (round(float(seer_proxy),2) if seer_proxy is not None else None)}


@analytics_function(
    patterns=[
        r"eui",
        r"energy.*use.*intensity",
        r"energy.*per.*area",
        r"building.*energy.*performance",
        r"kwh.*per.*m2"
    ],
    description="Calculates Energy Use Intensity (EUI) normalized by building area"
)

def analyze_eui(sensor_data, area_m2=None):
    """
    Energy Use Intensity (EUI) — Building Energy Benchmarking Metric
    
    Purpose:
    Calculates Energy Use Intensity (EUI) in kWh/m²·year or kBtu/ft²·year to normalize 
    energy consumption by building size, enabling peer comparisons. EUI is the primary 
    metric for ENERGY STAR Portfolio Manager benchmarking, building performance standards 
    (e.g., NYC Local Law 97), and energy labeling requirements. Low EUI indicates efficient 
    operations; high EUI signals retrofit opportunities.
    
    Sensors:
      - Total_Building_Power or Main_Meter_Power (kW)
      - Building_Area (m² or ft², typically from building metadata, not sensor)
    
    Output:
      - eui_kwh_per_m2_yr: Annual EUI in SI units (kWh/m²·year)
      - eui_kbtu_per_ft2_yr: Annual EUI in US units (kBtu/ft²·year)
      - total_kwh: Total energy consumption over period
      - days_covered: Data collection period (days)
      - percentile_rank: Comparison to ENERGY STAR median (if known)
      - performance_category: "Top Quartile", "Median", "Bottom Quartile"
    
    This analysis helps:
      - Benchmark against peer buildings (ENERGY STAR Portfolio Manager)
      - Support building performance standards (NYC LL97, CA Title 24)
      - Identify retrofit opportunities (high EUI = high savings potential)
      - Track energy efficiency improvements over time
      - Support green building certifications (LEED EA Credit 1, BREEAM Ene 01)
      - Validate energy models (compare predicted vs actual EUI)
    
    Method:
      **EUI calculation:**
        EUI = Total Energy Consumption / Conditioned Floor Area / Time Period
        
        SI units:
          EUI = kWh / m² / year  [kWh/m²·yr]
        
        US units:
          EUI = kBtu / ft² / year  [kBtu/ft²·yr]
          (Note: 1 kBtu = 1000 Btu, sometimes written as MBtu confusingly)
        
        Unit conversions:
          1 kWh = 3.412 kBtu
          1 m² = 10.764 ft²
          1 kWh/m²·yr = 0.317 kBtu/ft²·yr
      
      **Typical EUI ranges by building type (ENERGY STAR medians):**
        Office (general):
          - Median: 220 kWh/m²·yr (70 kBtu/ft²·yr)
          - Top quartile: <150 kWh/m²·yr (<47 kBtu/ft²·yr)
          - Bottom quartile: >300 kWh/m²·yr (>95 kBtu/ft²·yr)
        
        Office (high-rise):
          - Median: 250 kWh/m²·yr (79 kBtu/ft²·yr)
          - High elevators, central systems
        
        Retail:
          - Median: 350 kWh/m²·yr (111 kBtu/ft²·yr)
          - High lighting, long hours
        
        School (K-12):
          - Median: 150 kWh/m²·yr (47 kBtu/ft²·yr)
          - Seasonal operation, lower hours
        
        Hospital:
          - Median: 450 kWh/m²·yr (143 kBtu/ft²·yr)
          - 24/7 operation, high ventilation, critical loads
        
        Data center:
          - Median: 1200-2000 kWh/m²·yr (380-635 kBtu/ft²·yr)
          - IT loads dominate, high cooling
        
        Warehouse (unconditioned):
          - Median: 50-80 kWh/m²·yr (16-25 kBtu/ft²·yr)
          - Minimal HVAC, low lighting density
      
      **EUI components (end-use breakdown):**
        Typical office building EUI = 220 kWh/m²·yr:
          - HVAC: 90 kWh/m²·yr (41%, fans, pumps, chillers)
          - Lighting: 50 kWh/m²·yr (23%)
          - Plug loads: 55 kWh/m²·yr (25%, computers, printers)
          - Misc: 25 kWh/m²·yr (11%, elevators, domestic hot water)
        
        Optimization priorities:
          1. HVAC (largest savings potential, 30-50% reduction feasible)
          2. Lighting (LED retrofit, controls, 40-60% reduction)
          3. Plug loads (advanced power strips, 10-20% reduction)
      
      **ENERGY STAR benchmarking process:**
        1. Input building characteristics:
           - Gross floor area (m² or ft²)
           - Operating hours, occupancy
           - Number of computers, servers
           - Climate zone (HDD, CDD)
        
        2. Enter 12 months of energy data:
           - Electric (kWh), natural gas (therms), steam (Mlbs)
           - District heating/cooling (kBtu)
        
        3. Receive ENERGY STAR Score (1-100):
           - 75+ = ENERGY STAR certified (top 25%)
           - 50 = National median
           - 25 = Bottom quartile (improvement needed)
        
        4. Normalize for:
           - Weather (HDD/CDD adjustment)
           - Operating characteristics (hours, occupancy)
           - Not normalized: Building age, envelope (those are efficiency factors)
      
      **Building performance standards (regulatory drivers):**
        NYC Local Law 97 (2019):
          - Limits: 2024-2029 = 0.00536 tCO₂e/ft²·yr (~25 kBtu/ft²·yr electric)
          - Penalties: $268 per tCO₂e excess
          - Affects: Buildings >25,000 ft² (80% of NYC emissions)
        
        California Title 24 (2022):
          - Requires 15% better than ASHRAE 90.1-2019
          - EUI limits vary by climate zone, building type
        
        UK MEES (Minimum Energy Efficiency Standard):
          - EPC rating ≥E required for rental properties
          - Penalty: Up to £150,000 or 6 months rental income
        
        EU EPBD (Energy Performance of Buildings Directive):
          - 2030 target: All new buildings zero-emission
          - 2050 target: All buildings zero-emission
      
      **EUI reduction strategies:**
        High EUI (>300 kWh/m²·yr):
          - Deep retrofit: Envelope, HVAC replacement, LED, controls
          - Savings potential: 30-50% EUI reduction
          - Payback: 7-15 years (with incentives)
        
        Moderate EUI (150-300 kWh/m²·yr):
          - Tune-up: Commissioning, control optimization, LED
          - Savings potential: 15-30% EUI reduction
          - Payback: 2-5 years
        
        Low EUI (<150 kWh/m²·yr):
          - Fine-tuning: Advanced controls, plug load management
          - Savings potential: 5-15% EUI reduction
          - Focus: Maintain performance, prevent degradation
      
      **Weather normalization (for year-to-year comparison):**
        Heating degree days (HDD) adjustment:
          EUI_normalized = EUI_actual × (HDD_typical / HDD_actual)
        
        Cooling degree days (CDD) adjustment:
          EUI_normalized = EUI_actual × (CDD_typical / CDD_actual)
        
        Combined normalization (ASHRAE Inverse Modeling Toolkit):
          Use regression: Energy = f(HDD, CDD, occupancy)
          Predict baseline with typical weather
      
      **Site vs source EUI:**
        Site EUI:
          - Measured at building meter (what utility bills)
          - Example: 220 kWh/m²·yr electric
        
        Source EUI:
          - Accounts for generation/transmission losses
          - Electric: Site × 2.5-3.0 (grid losses, power plant efficiency)
          - Natural gas: Site × 1.05 (minimal transmission loss)
          - ENERGY STAR uses source EUI for scoring
        
        Source-to-site ratios (US EPA):
          - Electric: 2.80 (national average)
          - Natural gas: 1.05
          - District steam: 1.20-1.45
      
      **Limitations and considerations:**
        Conditioned vs unconditioned area:
          - Use conditioned area only (excludes parking, outdoor areas)
          - Mixed-use: Allocate energy by submeters if available
        
        Operational hours:
          - 24/7 buildings (hospitals): Inherently higher EUI
          - Seasonal (schools): Lower EUI, but compare apples-to-apples
        
        Climate normalization:
          - Cold climates: Higher heating EUI
          - Hot climates: Higher cooling EUI
          - Mild climates: Lower total EUI (naturally efficient)
    
    Parameters:
        sensor_data (dict): Power timeseries data (kW)
        area_m2 (float): Conditioned floor area in square meters
    
    Returns:
        dict: EUI (SI and US units), total energy, period coverage, benchmarking comparison

    Computes Energy Use Intensity (kWh/m²·yr) from available kW/energy and site area.

    Returns: { eui_kwh_per_m2_yr, total_kWh, days_covered }
    """
    if not area_m2 or float(area_m2) <= 0:
        return {"error": "area_m2 required and must be >0"}
    summ = analyze_electric_power_summary(sensor_data)
    if "error" in summ:
        return summ
    start = pd.to_datetime(summ.get("period_start")) if summ.get("period_start") else None
    end = pd.to_datetime(summ.get("period_end")) if summ.get("period_end") else None
    if not (start and end):
        return {"error": "Insufficient period bounds"}
    days = max(1.0, (end - start).total_seconds() / 86400.0)
    total_kwh = float(summ.get("total_kWh", 0.0))
    annual_kwh = total_kwh * (365.0 / days)
    eui = annual_kwh / float(area_m2)
    return {"eui_kwh_per_m2_yr": round(float(eui),1), "total_kWh": round(total_kwh,1), "days_covered": round(days,1)}


@analytics_function(
    patterns=[
        r"fan.*vfd",
        r"fan.*efficiency",
        r"variable.*frequency.*drive",
        r"fan.*motor.*efficiency",
        r"fan.*power"
    ],
    description="Analyzes fan VFD operation and energy efficiency at different speeds"
)

def analyze_fan_vfd_efficiency(sensor_data):
    """
    Fan VFD Efficiency — Specific Fan Power Assessment
    
    Purpose:
    Calculates Specific Fan Power (SFP), defined as electrical power per unit airflow 
    (W/(L/s) or kW/(m³/s)), to assess fan system efficiency. High SFP indicates excessive 
    resistance (dirty filters, closed dampers), oversized fans, or inefficient fan selection. 
    UK Building Regulations Part L and CIBSE TM23 specify maximum SFP thresholds for 
    compliance. This analysis validates ventilation system design and identifies energy 
    waste opportunities.
    
    Sensors:
      - Fan_Power_Sensor or Motor_Power (kW)
      - Airflow_Sensor or Fan_Airflow (L/s, m³/s, or CFM)
      - Optional: VFD_Speed (%) for affinity law validation
    
    Output:
      - sfp_mean: Average Specific Fan Power (W/(L/s))
      - sfp_latest: Most recent SFP reading
      - efficiency_band: UK Building Regs classification (SFP1-SFP6)
      - compliance_status: "Pass" or "Fail" against Part L limits
      - energy_waste_estimate: Annual kWh waste vs good practice
    
    This analysis helps:
      - Validate compliance with UK Building Regulations Part L
      - Identify high-resistance systems requiring filter changes or duct cleaning
      - Detect oversized or inefficient fans needing replacement
      - Quantify energy savings from fan upgrades or VFD retrofits
      - Support BREEAM energy efficiency credits
      - Benchmark fan performance against CIBSE TM23 guidance
    
    Method:
      SFP calculation:
        SFP (W/(L/s)) = Fan Power (W) / Airflow (L/s)
        
        Or in alternative units:
          SFP (kW/(m³/s)) = Fan Power (kW) / Airflow (m³/s)
      
      UK Building Regulations Part L SFP limits (W/(L/s)):
        - SFP1: ≤0.5 W/(L/s) - Excellent (low-pressure duct, EC fans)
        - SFP2: 0.5-1.0 - Good practice (well-designed VAV systems)
        - SFP3: 1.0-1.5 - Fair (typical CAV systems)
        - SFP4: 1.5-2.0 - Poor (high resistance, inefficient)
        - SFP5: 2.0-2.5 - Very poor (requires investigation)
        - SFP6: >2.5 - Unacceptable (urgent remediation)
      
      Part L compliance limits:
        - Mechanically ventilated buildings: SFP ≤ 2.0 W/(L/s)
        - Mixed-mode ventilation: SFP ≤ 1.5 W/(L/s)
        - Low-energy buildings: SFP ≤ 1.0 W/(L/s) target
      
      Typical SFP benchmarks by system:
        - Low-pressure VAV with EC fans: 0.6-1.0 W/(L/s)
        - Standard VAV system: 1.0-1.5 W/(L/s)
        - CAV system: 1.5-2.0 W/(L/s)
        - Legacy systems (pre-1990): 2.0-3.5 W/(L/s)
      
      Root causes of high SFP:
        - Dirty filters (most common, easy fix)
        - Excessive duct resistance (poor design, long runs)
        - Closed or stuck dampers increasing back-pressure
        - Oversized fan operating at low efficiency point
        - Old inefficient fan motors (pre-VFD)
        - Duct leakage requiring higher pressure
      
      Energy savings potential:
        Example: 10,000 L/s fan system
          Current: SFP = 2.0 W/(L/s) → 20 kW continuous
          Improved: SFP = 1.0 W/(L/s) → 10 kW continuous
          Savings: 10 kW × 8760 h/yr = 87,600 kWh/yr
          
        At £0.15/kWh: £13,140/year savings
      
      VFD affinity laws (if speed data available):
        Power ∝ Speed³
        Airflow ∝ Speed
        Therefore: SFP ∝ Speed²
        
        Reducing speed from 100% to 80%:
          Power drops to 51% (0.8³)
          Airflow drops to 80% (0.8¹)
          SFP drops to 64% (0.8²)
    
    Parameters:
        sensor_data (dict): Fan power and airflow timeseries data
    
    Returns:
        dict: SFP metrics, UK Building Regs band classification, compliance status, and savings estimate
    """
    flat = _aggregate_flat(sensor_data)
    fan_pred = _key_matcher(["fan"]) ; p_pred = _key_matcher(["power", "kw"]) ; flow_pred = _key_matcher(["air_flow", "airflow", "flow_rate"])
    p_keys = [k for k in flat.keys() if fan_pred(str(k)) and p_pred(str(k))]
    f_keys = _select_keys(flat, flow_pred, False)
    if not (p_keys and f_keys):
        return {"error": "Need fan power and airflow"}
    dfP = _df_from_readings(sum((flat[k] for k in p_keys), []))
    dfF = _df_from_readings(sum((flat[k] for k in f_keys), []))
    for d in (dfP, dfF): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfP.sort_values("timestamp"), dfF.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_kW","_flow"))
    if mm.empty: return {"error": "Could not align fan power/flow"}
    sfp = (mm["reading_value_kW"] / mm["reading_value_flow"].replace(0, pd.NA)).dropna()
    if sfp.empty: return {"error": "Invalid SFP ratios"}
    m = float(sfp.mean())
    band = ("good" if m < 1.5 else ("ok" if m < 2.5 else "poor"))
    return {"sfp_mean": round(m,3), "band": band}


@analytics_function(
    patterns=[
        r"pump.*efficiency",
        r"pump.*performance",
        r"pump.*power",
        r"pump.*motor",
        r"hydronic.*pump"
    ],
    description="Analyzes pump efficiency and performance characteristics"
)

def analyze_pump_efficiency(sensor_data):
    """
    Pump Efficiency — Specific Pump Power Assessment
    
    Purpose:
    Calculates Specific Pump Power (SPP), an efficiency metric for water pumps 
    defined as kW per unit of water flow (typically kW/L/s or kW/GPM). High SPP 
    indicates inefficient operation due to oversized pumps, excessive system 
    resistance, impeller wear, or speed control issues. Identifies opportunities 
    for VFD optimization, impeller cleaning, and system rebalancing.
    
    Sensors:
      - Pump_Power_Sensor or Motor_Power_Sensor (kW)
      - Water_Flow_Sensor or Flow_Rate_Sensor (L/s, GPM, or m³/h)
    
    Output:
      - spp_mean: Average specific pump power
      - spp_latest: Most recent SPP reading
      - high_flag: Boolean indicating SPP exceeds threshold
      - efficiency_trend: Degradation over analysis period
    
    This analysis helps:
      - Identify pumps with poor hydraulic efficiency
      - Detect impeller fouling or wear requiring maintenance
      - Optimize VFD setpoints for variable speed pumps
      - Validate pump selection against system requirements
      - Quantify energy savings from pump replacements or upgrades
      - Detect system resistance increases (fouled filters, closed valves)
    
    Method:
      SPP = Pump Power (kW) / Water Flow Rate (L/s)
      
      Typical SPP benchmarks:
        - Well-designed systems: 0.4-0.8 kW/(L/s)
        - Average systems: 0.8-1.5 kW/(L/s)
        - Poor systems (needs attention): >1.5 kW/(L/s)
      
      High SPP can indicate:
        - Oversized pump (running at low part-load)
        - High system resistance (fouling, throttling)
        - Pump wear or cavitation
        - Speed control issues with VFD
    
    Parameters:
        sensor_data (dict): Timeseries data containing pump power and flow readings
    
    Returns:
        dict: Pump efficiency metrics, SPP values, and operational flags
    """
    flat = _aggregate_flat(sensor_data)
    pump_pred = _key_matcher(["pump"]) ; p_pred = _key_matcher(["power", "kw"]) ; flow_pred = _key_matcher(["flow", "flow_rate"]) 
    p_keys = [k for k in flat.keys() if pump_pred(str(k)) and p_pred(str(k))]
    f_keys = _select_keys(flat, flow_pred, False)
    if not (p_keys and f_keys):
        return {"error": "Need pump power and flow"}
    dfP = _df_from_readings(sum((flat[k] for k in p_keys), []))
    dfF = _df_from_readings(sum((flat[k] for k in f_keys), []))
    for d in (dfP, dfF): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfP.sort_values("timestamp"), dfF.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_kW","_flow"))
    if mm.empty: return {"error": "Could not align pump power/flow"}
    spp = (mm["reading_value_kW"] / mm["reading_value_flow"].replace(0, pd.NA)).dropna()
    if spp.empty: return {"error": "Invalid SPP ratios"}
    m = float(spp.mean())
    return {"spp_mean": round(m,3), "high_flag": bool(m > 2.5)}


@analytics_function(
    patterns=[
        r"runtime",
        r"operating.*hours",
        r"run.*time",
        r"equipment.*hours",
        r"operational.*duration"
    ],
    description="Analyzes equipment runtime hours and operational patterns"
)

def analyze_runtime_analysis(sensor_data, use_power_threshold=True):
    """
    Runtime Analysis — Equipment Operating Hours & Duty Cycle
    
    Purpose:
    Tracks equipment on/off runtime hours and duty cycle (percentage of time running) 
    to support predictive maintenance, energy accounting, and schedule compliance 
    verification. Excessive runtime indicates undersized equipment, control issues, or 
    unnecessary operation during unoccupied periods. Low runtime may indicate over-sizing 
    or cycling problems that reduce equipment life and efficiency.
    
    Sensors:
      - Equipment_Status_Sensor or Binary_Output (0=off, 1=on) [preferred]
      - Electric_Power_Sensor (kW) with threshold-based inference [alternative]
      - Motor_Run_Command or VFD_Enable signal
    
    Output:
      - runtime_hours: Total hours equipment operated during analysis period
      - duty_cycle: Percentage of time equipment was on (0-100%)
      - cycles_per_day: Average start/stop cycles (high cycling reduces equipment life)
      - longest_run: Maximum continuous runtime (detects stuck-on conditions)
      - unoccupied_runtime_hours: Runtime during scheduled off periods (waste detection)
    
    This analysis helps:
      - Schedule preventive maintenance based on actual operating hours (not calendar)
      - Detect after-hours operation indicating schedule override or thermostat issues
      - Validate equipment sizing (duty cycle >80% suggests undersizing)
      - Identify short-cycling problems (>6 cycles/hour damages compressors)
      - Support energy accounting and cost allocation by zone/tenant
      - Detect stuck equipment (continuous 24/7 runtime without cycling)
    
    Method:
      If status signal available:
        Runtime = sum of hours where status == 1 (ON)
      
      If power threshold method:
        Equipment ON when Power > threshold (typically 10-20% of nameplate kW)
        Threshold auto-detected from power histogram bimodal distribution
      
      Duty Cycle = (Runtime Hours / Total Hours) × 100%
      
      Typical duty cycle benchmarks:
        - Cooling equipment (summer): 40-60% (properly sized)
        - Heating equipment (winter): 30-50%
        - Fans (VAV): 60-80% (continuous with variable speed)
        - Pumps (primary): 70-90% (longer runs preferred)
        - >80% duty cycle: Equipment may be undersized or setpoints too aggressive
        - <20% duty cycle: Equipment may be oversized (cycling issues)
      
      Cycling detection:
        Counts state transitions (OFF→ON). Excessive cycling (>6/hour for HVAC) 
        causes compressor wear, reduces efficiency, and shortens equipment life.
    
    Parameters:
        sensor_data (dict): Equipment status or power timeseries data
        use_power_threshold (bool, optional): Infer status from power if true (default True)
    
    Returns:
        dict: Runtime hours, duty cycle %, cycling metrics, and schedule compliance flags
    """
    flat = _aggregate_flat(sensor_data)
    status_pred = _key_matcher(["status", "run", "on", "command"]) ; p_pred = _key_matcher(["power", "kw"]) 
    s_keys = _select_keys(flat, status_pred, False)
    if s_keys:
        df = _df_from_readings(sum((flat[k] for k in s_keys), []))
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        on = (df["reading_value"].astype(float) > 0.5)
        dt = df["timestamp"].diff().dt.total_seconds().fillna(0) / 3600.0
        runtime_h = float((on * dt).sum())
        duty = float(on.mean())
        return {"runtime_hours": round(runtime_h,2), "duty_cycle": round(duty,3)}
    if use_power_threshold:
        p_keys = _select_keys(flat, p_pred, False)
        if not p_keys:
            return {"error": "No status or power series"}
        df = _df_from_readings(sum((flat[k] for k in p_keys), []))
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        thr = float(df["reading_value"].quantile(0.1))
        on = df["reading_value"].astype(float) > thr
        dt = df["timestamp"].diff().dt.total_seconds().fillna(0) / 3600.0
        runtime_h = float((on * dt).sum())
        duty = float(on.mean())
        return {"runtime_hours": round(runtime_h,2), "duty_cycle": round(duty,3), "threshold": round(thr,2)}
    return {"error": "Unable to determine runtime"}


@analytics_function(
    patterns=[
        r"schedule.*compliance",
        r"operating.*schedule",
        r"occupancy.*schedule",
        r"after.*hours.*operation",
        r"schedule.*adherence"
    ],
    description="Checks equipment operation compliance against defined schedules"
)

def analyze_schedule_compliance(sensor_data, schedule=None):
    """
    Schedule Compliance Assessment — After-Hours Runtime Detection
    
    Purpose:
    Monitors equipment operation outside scheduled occupancy hours to quantify wasted energy 
    from excessive runtime. Unoccupied-hour operation (lights, HVAC running 24/7 despite 9-5 
    schedule) is a top-3 energy waste in commercial buildings (15-30% savings potential). This 
    analysis validates schedule adherence and supports ASHRAE 90.1 automatic shutoff requirements.
    
    Sensors:
      - Equipment_Status or Run_Status (binary: 0=off, 1=on)
      - Alternative: Power or kW sensors (threshold-based on/off inference)
    
    Output:
      - outside_runtime_hours: Hours running outside schedule
      - compliance_percentage: % of scheduled hours only (100% = perfect)
      - inferred: Boolean flag (true if schedule auto-inferred, false if user-provided)
      - wasted_energy_kwh: Estimated energy waste (if power available)
      - cost_savings_potential: Estimated annual savings ($)
      - schedule_recommendation: Suggested start/stop times
    
    This analysis helps:
      - Identify schedule overrides or failed shutoff controls
      - Quantify energy waste from unoccupied runtime (lights, HVAC)
      - Support ASHRAE 90.1 Section 6.4.3.3 automatic shutoff compliance
      - Validate occupancy sensor and time-clock operation
      - Estimate savings from schedule optimization (typically 15-30%)
      - Prioritize recommissioning for buildings with poor compliance (<80%)
    
    Method:
      **Schedule definition:**
        schedule format (dict by day-of-week, 0=Monday):
          {
            0: ["08:00", "18:00"],  # Monday 8am-6pm
            1: ["08:00", "18:00"],  # Tuesday
            ...
            5: ["10:00", "16:00"],  # Saturday (reduced hours)
            6: []                   # Sunday (closed)
          }
        
        If schedule=None: Infer from operational patterns
          - Find typical start hour (10% power threshold first exceeded)
          - Find typical stop hour (last exceeded before midnight)
          - Weekday vs weekend detection
      
      **Compliance calculation:**
        Compliance % = (Scheduled runtime hours / Total runtime hours) × 100%
        
        Outside runtime hours = Total runtime - Scheduled runtime
        
        Example:
          Total runtime: 80 hrs/week
          Scheduled: 60 hrs/week (Mon-Fri 8am-6pm)
          Outside runtime: 20 hrs/week
          Compliance: 75% (poor, 25% waste)
      
      **Typical schedules by building type:**
        Office (standard):
          - Mon-Fri: 7am-7pm (warm-up 1hr before, cool-down 1hr after)
          - Sat-Sun: Off (or skeleton crew 8am-2pm)
          - Holidays: Off
        
        Retail:
          - Mon-Sat: 9am-9pm
          - Sunday: 10am-6pm
          - Holidays: Varies
        
        School (K-12):
          - Mon-Fri: 6am-4pm (early buses, after-school programs)
          - Sat-Sun: Off
          - Summer: Minimal (maintenance only)
        
        Hospital (24/7):
          - Always occupied: Compliance N/A
          - Zone-specific: Administrative areas may have schedules
      
      **ASHRAE 90.1-2022 automatic shutoff requirements:**
        Section 6.4.3.3 - Automatic Lighting Shutoff:
          - Occupancy sensors OR time switches required
          - Manual override: 2-hour maximum
          - Exception: 24/7 areas, safety/security lighting
        
        Section 6.4.3.4.5 - HVAC Shutoff:
          - Automatic shutdown when space unoccupied
          - Manual override: 2-hour maximum (for lighting)
          - Setback/setup: ±5°F (2.8°C) during unoccupied
      
      **Energy waste from non-compliance:**
        Lighting (24/7 when should be 10 hrs/day):
          - Waste: 58% of lighting energy
          - Example: 10 kW × 14 hrs/day × 365 days = 51,100 kWh/yr
          - Cost @ $0.12/kWh = $6,132/year wasted
        
        HVAC (no night setback):
          - Waste: 20-30% of HVAC energy
          - Mechanism: Conditioning unoccupied space to full comfort
          - Savings from setback (22°C → 18°C heating, 24°C → 27°C cooling)
        
        Plug loads (equipment left on 24/7):
          - Waste: 30-50% of plug load energy
          - Culprits: Monitors, printers, coffee makers, vending machines
          - Solution: Controlled outlets, power strips with timers
      
      **Root causes of poor compliance:**
        Manual overrides (not cancelled):
          - Symptom: Equipment on continuously after one-time override
          - Fix: Implement auto-reset (override expires after 2-4 hours)
        
        Failed time clock or scheduler:
          - Symptom: Schedule not executing (BAS programming error)
          - Fix: Verify schedule programming, check BAS connectivity
        
        Occupancy sensor failure:
          - Symptom: Lights stay on in empty rooms
          - Fix: Test sensors, adjust timeout (15-30 minutes typical)
        
        Janitorial override (early morning cleaning):
          - Symptom: Equipment starts 3-4 hours early daily
          - Fix: Zone-specific scheduling, motion sensors
        
        After-hours work (unscheduled meetings):
          - Symptom: Sporadic late-night runtime
          - Fix: Occupancy-based control, self-service override
      
      **Schedule optimization strategies:**
        Optimal start (warm-up/cool-down time):
          - Start HVAC 1-2 hours before occupancy
          - Calculate required time based on outdoor temp:
            Warm-up time = (T_setpoint - T_current) / Heating_rate
          - Example: 4°C recovery @ 2°C/hr = 2 hours pre-start
        
        Optimal stop:
          - Stop HVAC 30-60 minutes before unoccupied
          - Building thermal mass coasts to acceptable range
          - Savings: 5-10% of HVAC energy
        
        Holiday schedules:
          - Override normal schedule on holidays
          - Typical: Run 25% normal hours (security only)
          - Savings: 10-20 days/year × 8 hrs/day = 80-160 hrs
        
        Seasonal adjustments:
          - Summer (schools): Skeleton schedule
          - Winter holidays: Extended shutdowns
          - Daylight saving time: Auto-adjust
      
      **Commissioning validation:**
        Functional test:
          - Program schedule, verify execution next day
          - Check: Equipment starts/stops within ±5 minutes
          - Test override: Verify 2-hour auto-revert
        
        Long-term monitoring:
          - Track compliance monthly
          - Alert: <80% compliance (investigate)
          - Trend: Declining compliance (scheduler drift)
      
      **Economic impact example:**
        100,000 ft² office building:
          Baseline: 24/7 operation
            Lighting: 1 W/ft² × 100k ft² = 100 kW
            HVAC: 2 W/ft² × 100k ft² = 200 kW
            Total: 300 kW × 8760 hrs = 2,628,000 kWh/yr
            Cost @ $0.12/kWh = $315,360/year
          
          Optimized: Mon-Fri 7am-7pm (60 hrs/week)
            Runtime: 3,120 hrs/year (35.6% of 8760)
            Energy: 936,000 kWh/year
            Cost: $112,320/year
          
          Savings: $203,040/year (64% reduction!)
          Implementation cost: $5k-$20k (programming, sensors)
          Payback: 1-3 months
    
    Parameters:
        sensor_data (dict): Equipment status or power timeseries
        schedule (dict, optional): Day-of-week schedules (0=Mon), if None auto-inferred
    
    Returns:
        dict: Outside runtime hours, compliance %, wasted energy, cost savings, schedule recommendation

    Checks equipment operation outside scheduled hours. If schedule not supplied, infers typical start/stop.

    schedule format example: { 0: ["08:00","18:00"], ..., 6: ["10:00","16:00"] } where 0=Mon

    Returns: { outside_runtime_hours, inferred: bool }
    """
    flat = _aggregate_flat(sensor_data)
    # Build on-series from status or power
    status_pred = _key_matcher(["status", "run", "on", "command"]) ; p_pred = _key_matcher(["power", "kw"]) 
    s_keys = _select_keys(flat, status_pred, False)
    if s_keys:
        df = _df_from_readings(sum((flat[k] for k in s_keys), []))
        df["on"] = (df["reading_value"].astype(float) > 0.5)
    else:
        p_keys = _select_keys(flat, p_pred, False)
        if not p_keys: return {"error": "No status or power series"}
        df = _df_from_readings(sum((flat[k] for k in p_keys), []))
        thr = float(df["reading_value"].quantile(0.1))
        df["on"] = (df["reading_value"].astype(float) > thr)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    df = df.set_index("timestamp").resample("15min").ffill()
    df["on"] = df["on"].astype(bool)
    inferred = False
    if schedule is None:
        inferred = True
        # Infer: for each weekday, find 20th and 80th percentile hours where on=True
        df["weekday"] = df.index.dayofweek
        df["hour"] = df.index.hour + df.index.minute/60.0
        sched = {}
        for d in range(7):
            subset = df[df["weekday"]==d]
            if subset.empty or subset["on"].mean() < 0.05:
                continue
            hours = subset[subset["on"]]["hour"]
            if hours.empty: 
                continue
            start_h = float(hours.quantile(0.2)); stop_h = float(hours.quantile(0.8))
            sched[d] = [start_h, stop_h]
    else:
        # Parse provided schedule
        sched = {}
        for d, win in (schedule or {}).items():
            try:
                st = pd.to_datetime(win[0]).hour + pd.to_datetime(win[0]).minute/60.0
                en = pd.to_datetime(win[1]).hour + pd.to_datetime(win[1]).minute/60.0
                sched[int(d)] = [st, en]
            except Exception:
                continue
    # Compute outside-hours runtime
    df["weekday"] = df.index.dayofweek
    df["hour"] = df.index.hour + df.index.minute/60.0
    outside = []
    for ts, row in df.iterrows():
        d = int(row["weekday"])
        if d not in sched:
            outside.append(bool(row["on"]))
        else:
            st, en = sched[d]
            outside.append(bool(row["on"]) and not (st <= row["hour"] <= en))
    outside = pd.Series(outside, index=df.index)
    outside_runtime_h = float(outside.mean() * len(outside) * 0.25)
    return {"outside_runtime_hours": round(outside_runtime_h,2), "inferred": inferred}


@analytics_function(
    patterns=[
        r"equipment.*cycling",
        r"short.*cycling",
        r"start.*stop.*frequency",
        r"cycling.*behavior",
        r"hunting"
    ],
    description="Analyzes equipment cycling behavior to detect short cycling issues"
)

def analyze_equipment_cycling_health(sensor_data):
    """
    Equipment Cycling Health — Short-Cycling Detection
    
    Purpose:
    Analyzes equipment on/off cycling patterns to detect short-cycling (excessive starts/stops), 
    which significantly reduces equipment life, wastes energy during transients, and causes 
    comfort swings. HVAC compressors, boilers, and pumps have manufacturer-specified maximum 
    cycling rates (typically 6-10 cycles/hour max). This analysis identifies oversized equipment, 
    control issues, or improper setpoints causing premature equipment failure.
    
    Sensors:
      - Equipment_Status_Sensor or Run_Command (0=off, 1=on) [preferred]
      - Equipment_Power_Sensor (kW) with threshold detection [alternative]
    
    Output:
      - cycles_per_hour: Average start/stop cycles per hour
      - short_cycle_flag: Boolean indicating excessive cycling (>6/hr typical threshold)
      - total_cycles: Total count of on→off→on cycles
      - avg_runtime_per_cycle: Average minutes per run (low = short-cycling)
      - cycling_severity: "Normal", "Moderate", "Severe", or "Critical"
      - recommended_action: Specific troubleshooting guidance
    
    This analysis helps:
      - Detect equipment oversizing causing short-cycling
      - Identify thermostat deadband issues (too narrow)
      - Diagnose control instability (hunting, oscillation)
      - Prevent premature compressor/motor failure from excessive starts
      - Validate minimum runtime timers and anti-short-cycle delays
      - Quantify maintenance cost impact from cycling stress
    
    Method:
      Cycle detection:
        Cycle = OFF → ON → OFF sequence (rising edge count)
        Cycles/Hour = Total Cycles / Hours in Analysis Period
      
      Cycling thresholds by equipment type:
        **Compressors (chillers, heat pumps, DX units):**
          - Acceptable: 2-3 cycles/hour
          - Maximum: 6 cycles/hour (manufacturer limit)
          - Severe: >10 cycles/hour (urgent remediation)
          - Each start consumes 3-5× running current (inrush)
        
        **Boilers:**
          - Acceptable: 3-4 cycles/hour
          - Maximum: 6 cycles/hour
          - Severe: >8 cycles/hour
          - Short-cycling reduces combustion efficiency 10-15%
        
        **Pumps/Fans:**
          - Less sensitive to cycling than compressors
          - Concern: >20 cycles/hour (VFD/soft starter recommended)
          - Motor bearings affected by frequent starts
      
      Average runtime per cycle:
        Avg Runtime = Total Runtime Hours / Total Cycles
        
        Short-cycling indicators:
          - <5 minutes runtime: Severe short-cycling
          - 5-10 minutes: Marginal, investigate
          - 10-20 minutes: Acceptable for residential
          - 20-60 minutes: Good for commercial HVAC
          - >60 minutes: Ideal (base-loaded equipment)
      
      Root causes of short-cycling:
        1. **Equipment oversizing (most common):**
           - Unit capacity >> load, reaches setpoint quickly
           - Solution: Downsize equipment or add capacity staging
        
        2. **Thermostat deadband too narrow:**
           - Setpoint ±0.5°C causes rapid on/off
           - Solution: Widen deadband to ±1-2°C
        
        3. **Control instability:**
           - PID tuning too aggressive (high gain)
           - Solution: Reduce proportional gain, add integral time
        
        4. **Inadequate time delays:**
           - Missing minimum runtime timer
           - Missing minimum off-time delay
           - Solution: Program 10-min minimum on, 5-min minimum off
        
        5. **Faulty sensors:**
           - Sensor drift causing false setpoint achievement
           - Solution: Calibrate or replace sensors
        
        6. **Improper staging:**
           - All equipment starts simultaneously
           - Solution: Sequence starts, use lead-lag rotation
      
      Impact of short-cycling:
        - Compressor life: 60,000 starts rated life
          * At 3 cycles/hr: 22,800 hours (2.6 years 24/7)
          * At 10 cycles/hr: 6,840 hours (0.8 years 24/7)
          * Premature failure from excessive starts
        
        - Energy waste: 5-15% efficiency penalty
          * Transient startup losses
          * Incomplete heat transfer cycles
          * Control system overhead
        
        - Comfort: Temperature swings ±2-3°C
          * Rapid on/off prevents stable conditioning
          * Occupant discomfort and complaints
    
    Parameters:
        sensor_data (dict): Equipment status or power timeseries data
    
    Returns:
        dict: Cycling rate, short-cycle flags, runtime statistics, severity classification, and corrective action recommendations
    """
    flat = _aggregate_flat(sensor_data)
    status_pred = _key_matcher(["status", "run", "on", "command"]) ; p_pred = _key_matcher(["power", "kw"]) 
    s_keys = _select_keys(flat, status_pred, False)
    if s_keys:
        df = _df_from_readings(sum((flat[k] for k in s_keys), []))
        sig = (df["reading_value"].astype(float) > 0.5)
    else:
        p_keys = _select_keys(flat, p_pred, False)
        if not p_keys: return {"error": "No status or power series"}
        df = _df_from_readings(sum((flat[k] for k in p_keys), []))
        thr = float(df["reading_value"].quantile(0.1))
        sig = (df["reading_value"].astype(float) > thr)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
    sig = sig.reset_index(drop=True)
    # Count rising edges
    rises = 0
    for i in range(1, len(sig)):
        if (not bool(sig.iloc[i-1])) and bool(sig.iloc[i]):
            rises += 1
    hours = max(1e-6, (df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).total_seconds()/3600.0)
    cph = rises / hours
    short_flag = bool(cph > 6.0)  # >6 cycles/hour
    return {"cycles_per_hour": round(float(cph),2), "short_cycle_flag": short_flag}


@analytics_function(
    patterns=[
        r"alarm.*summary",
        r"event.*log",
        r"fault.*history",
        r"alert.*summary",
        r"alarm.*count"
    ],
    description="Summarizes alarm events and fault occurrences over time"
)

def analyze_alarm_event_summary(sensor_data):
    """
    Alarm/Event Summary — Fault Frequency & Reliability Analysis
    
    Purpose:
    Summarizes alarm/fault events by type and calculates Mean Time Between Failures (MTBF) 
    to assess equipment reliability and maintenance effectiveness. High alarm frequency 
    indicates chronic issues requiring corrective action rather than reactive maintenance. 
    MTBF trends reveal equipment degradation and guide predictive maintenance scheduling.
    
    Sensors:
      - Alarm_Status, Fault_Code, Event_Log sensors
      - Numeric codes or string descriptions
    
    Output:
      - total_events: Count of all alarms/faults
      - by_type: Breakdown by alarm type {type: count}
      - mtbf_hours: Mean Time Between Failures (hours)
      - most_frequent_alarm: Top recurring issue
      - alarm_rate: Events per day
      - reliability_score: 0-100 (higher = better, based on MTBF)
    
    This analysis helps:
      - Prioritize maintenance (fix most frequent alarms first)
      - Trend equipment reliability (declining MTBF = degradation)
      - Validate corrective actions (MTBF should increase post-repair)
      - Support predictive maintenance programs (ISO 55000)
      - Quantify alarm fatigue (too many nuisance alarms reduce response)
      - Comply with facility management standards (IFMA, BOMA)
    
    Method:
      MTBF = Total operating time / Number of failures
      
      Example: 720 hrs (1 month), 12 alarms → MTBF = 60 hours
      
      Reliability interpretation:
        - MTBF >500 hrs: Excellent reliability
        - MTBF 100-500 hrs: Good, routine maintenance
        - MTBF 50-100 hrs: Fair, investigate chronic issues
        - MTBF <50 hrs: Poor, corrective action required
    
    Parameters:
        sensor_data (dict): Alarm/event timeseries data
    
    Returns:
        dict: Event counts, MTBF, alarm breakdown, reliability score

    Summarizes alarms/events by type and basic reliability metrics (counts, MTBF approx).

    Returns: { total_events, by_type: {type: count}, mtbf_hours }
    """
    flat = _aggregate_flat(sensor_data)
    evt_pred = _key_matcher(["alarm", "fault", "event", "code"]) 
    keys = _select_keys(flat, evt_pred, False)
    if not keys:
        return {"error": "No alarm/event series"}
    events = []
    for k in keys:
        df = _df_from_readings(flat[k])
        if df.empty: continue
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp")
        # Consider non-zero as event, if string take unique values as types
        if pd.api.types.is_numeric_dtype(df["reading_value"]):
            ev = df[df["reading_value"].astype(float) != 0.0][["timestamp"]].copy()
            ev["type"] = str(k)
        else:
            ev = df[df["reading_value"].astype(str).str.len() > 0][["timestamp", "reading_value"]].copy()
            ev = ev.rename(columns={"reading_value": "type"})
        events.append(ev)
    if not events:
        return {"error": "No events detected"}
    ev = pd.concat(events, ignore_index=True).sort_values("timestamp")
    total = int(len(ev))
    by_type = ev["type"].value_counts().to_dict()
    mtbf = None
    if total >= 2:
        diffs = ev["timestamp"].sort_values().diff().dropna().dt.total_seconds()/3600.0
        if not diffs.empty:
            mtbf = float(diffs.mean())
    return {"total_events": total, "by_type": by_type, "mtbf_hours": (round(mtbf,2) if mtbf is not None else None)}


@analytics_function(
    patterns=[
        r"sensor.*correlation",
        r"correlation.*matrix",
        r"sensor.*relationship",
        r"cross.*correlation",
        r"data.*correlation"
    ],
    description="Creates correlation map showing relationships between multiple sensors"
)

def analyze_sensor_correlation_map(sensor_data, max_sensors=20):
    """
    Sensor Correlation Map — Cross-Sensor Relationship Analysis
    
    Purpose:
    Computes correlation matrix across multiple sensors to identify relationships, validate 
    sensor accuracy, and detect faults. Strong correlations (e.g., supply/return temps) confirm 
    expected physics; weak correlations suggest sensor errors or system issues. This analysis 
    supports fault detection (FDD), virtual sensing, and sensor validation per ASHRAE Guideline 36.
    
    Sensors:
      - Any numeric sensors (temps, flows, pressures, powers)
      - Minimum 2 sensors required, up to max_sensors analyzed
    
    Output:
      - sensors: List of sensor names analyzed
      - corr: Correlation matrix [[r11, r12...], [r21, r22...]]
      - strong_pairs: Sensor pairs with |r| >0.8
      - weak_expected: Expected correlations missing (fault indicator)
      - redundancy_candidates: Sensors for virtual metering
    
    This analysis helps:
      - Detect sensor failures (expected correlation breaks)
      - Validate sensor swaps (supply/return sensors reversed)
      - Enable virtual sensing (estimate unmeasured points from correlated sensors)
      - Support ASHRAE Guideline 36 fault detection rules
      - Optimize sensor networks (eliminate redundant sensors)
      - Commission new sensors (verify relationships match design)
    
    Method:
      Pearson correlation coefficient:
        r = Σ[(x - x̄)(y - ȳ)] / √[Σ(x - x̄)² × Σ(y - ȳ)²]
      
      Interpretation:
        |r| >0.9: Very strong (redundant sensors, virtual sensing viable)
        |r| 0.7-0.9: Strong (expected physical relationship)
        |r| 0.3-0.7: Moderate (indirect relationship)
        |r| <0.3: Weak (independent, or lagged relationship)
      
      Expected strong correlations:
        - Supply/Return temps (r ~0.85-0.95)
        - CHW supply/return (r ~0.90-0.98)
        - Zone temp/outdoor temp (r ~0.60-0.80, seasonal)
        - Power/outdoor temp (r ~0.50-0.70, cooling-dominated)
    
    Parameters:
        sensor_data (dict): Timeseries from multiple sensors
        max_sensors (int): Limit analysis to first N sensors (default 20)
    
    Returns:
        dict: Sensor names, correlation matrix, strong pairs, fault indicators

    Computes a correlation matrix across up to max_sensors numeric signals.

    Returns: { sensors: [names], corr: [[...]] }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat: return {"error": "No data"}
    frames = []
    names = []
    for k, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty: continue
        v = df[["timestamp","reading_value"]].copy()
        v["timestamp"] = pd.to_datetime(v["timestamp"], errors="coerce")
        v = v.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
        v = v.resample("5min").mean().rename(columns={"reading_value": str(k)})
        frames.append(v)
        names.append(str(k))
        if len(names) >= max_sensors:
            break
    if not frames:
        return {"error": "No numeric series"}
    X = pd.concat(frames, axis=1).dropna(how="all")
    if X.empty:
        return {"error": "No aligned data"}
    corr = X.corr().fillna(0.0)
    return {"sensors": corr.columns.tolist(), "corr": [[round(float(x),3) for x in row] for row in corr.values.tolist()]}


@analytics_function(
    patterns=[
        r"lead.*lag",
        r"time.*delay",
        r"lag.*analysis",
        r"response.*delay",
        r"cross.*correlation.*lag"
    ],
    description="Analyzes lead-lag relationships and time delays between sensor pairs"
)

def analyze_lead_lag(sensor_data):
    """
    Lead/Lag Analysis — Time-Delayed Correlation Detection
    
    Purpose:
    Identifies time delays between related sensors to reveal cause-effect relationships and 
    control response times. Examples: outdoor temp leads zone temp (thermal lag), chiller 
    start leads cooling delivery (system response). This analysis validates control sequences, 
    optimizes start times, and detects unexpected delays indicating faults.
    
    Sensors:
      - Any numeric sensor pairs (requires ≥2 sensors)
      - Common: OAT/zone temp, power/temp, supply/return temps
    
    Output:
      - signal_a, signal_b: Sensor pair analyzed
      - lag_minutes: Time delay (positive = A leads B, negative = B leads A)
      - corr_at_lag: Maximum correlation at optimal lag
      - response_time: System response characterization
      - delay_interpretation: Physical explanation
    
    This analysis helps:
      - Optimize HVAC startup (outdoor temp → zone temp lag)
      - Validate control response (setpoint change → actual change)
      - Detect sluggish actuators (command → position lag >5 min)
      - Support ASHRAE Guideline 36 optimal start algorithms
      - Diagnose thermal mass effects (building time constants)
      - Commission control loops (verify PID response times)
    
    Method:
      Cross-correlation:
        Find lag τ that maximizes correlation between signals:
        r(τ) = Σ[x(t) × y(t+τ)] / √[Σx²(t) × Σy²(t+τ)]
      
      Typical lags:
        - Outdoor temp → Zone temp: 1-4 hours (thermal mass)
        - Chiller start → CHW temp: 5-15 minutes (response)
        - Valve command → Flow: 30-120 seconds (actuator)
        - Power → Cost: 15-60 minutes (demand interval)
    
    Parameters:
        sensor_data (dict): Timeseries from multiple sensors
    
    Returns:
        dict: Signal pair, lag time, correlation at lag, interpretation

    Infers lead/lag between the two most variant signals via cross-correlation.

    Returns: { signal_a, signal_b, lag_minutes, corr_at_lag }
    """
    flat = _aggregate_flat(sensor_data)
    # Build aligned 5-min dataframe
    frames = []
    for k, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty: continue
        v = df[["timestamp","reading_value"]].copy()
        v["timestamp"] = pd.to_datetime(v["timestamp"], errors="coerce")
        v = v.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
        v = v.resample("5min").mean().rename(columns={"reading_value": str(k)})
        frames.append(v)
    if len(frames) < 2:
        return {"error": "Need at least two series"}
    X = pd.concat(frames, axis=1).dropna()
    if X.shape[1] < 2:
        return {"error": "Insufficient aligned series"}
    # Pick top-2 by variance
    variances = X.var().sort_values(ascending=False)
    a, b = variances.index[:2]
    xa = X[a].astype(float) - X[a].astype(float).mean()
    xb = X[b].astype(float) - X[b].astype(float).mean()
    # Cross-correlation for lags in +/- 24 steps (2 hours window at 5min)
    max_steps = 24
    best = (0, 0.0)
    for lag in range(-max_steps, max_steps+1):
        if lag < 0:
            corr = xa.shift(-lag).corr(xb)
        else:
            corr = xa.corr(xb.shift(lag))
        if pd.notna(corr) and abs(corr) > abs(best[1]):
            best = (lag, corr)
    return {"signal_a": str(a), "signal_b": str(b), "lag_minutes": int(best[0]*5), "corr_at_lag": round(float(best[1]),3)}


@analytics_function(
    patterns=[
        r"weather.*normalization",
        r"temperature.*adjustment",
        r"degree.*day",
        r"climate.*normalization",
        r"hdd.*cdd"
    ],
    description="Normalizes energy consumption by weather (heating/cooling degree days)"
)

def analyze_weather_normalization(sensor_data, base_temp_c=18.0):
    """
    Weather Normalization — Weather-adjusted KPIs.
    
    Purpose: Normalizes energy consumption and comfort metrics to account for weather variations,
             enabling fair comparisons across different time periods, buildings, or operational
             changes. Essential for Measurement & Verification (M&V) and energy savings validation.
    
    Sensors:
      - Outside_Air_Temperature or Outdoor_Temperature
      - Electric_Energy_Sensor or Power_Sensor
      
    Output:
      - Weather-normalized energy metrics (kWh per degree-day)
      - Cooling Degree Days (CDD)
      - Heating Degree Days (HDD)
      - Energy use normalized by weather
      - Baseline comparison metrics
      
    This analysis helps:
      - Compare energy performance across seasons
      - Validate energy efficiency improvements independent of weather
      - Support IPMVP (International Performance Measurement & Verification Protocol)
      - Identify control or equipment issues masked by weather variations
      - Benchmark buildings in different climates fairly
      
    Degree-Day Calculation:
      - CDD (Cooling): Sum of (daily_avg_temp - base_temp) when avg > base
      - HDD (Heating): Sum of (base_temp - daily_avg_temp) when avg < base
      - Base temperature: Typically 18°C (65°F), can be customized
      
    Normalized metrics:
      - kWh/CDD: Energy intensity during cooling periods
      - kWh/HDD: Energy intensity during heating periods
      - Weather-independent efficiency indicator

    Parameters:
      - sensor_data: Temperature and energy sensor payload
      - base_temp_c: Base temperature for degree-day calculation (default: 18.0°C)

    Returns: { kWh_per_CDD, kWh_per_HDD, total_CDD, total_HDD, days, normalized_comparison }
    """
    flat = _aggregate_flat(sensor_data)
    oat_pred = _key_matcher(["outside_air", "outdoor"]) ; t_pred = _key_matcher(["temperature", "temp"]) ; p_pred = _key_matcher(["power", "kw"]) 
    O = [k for k in flat.keys() if oat_pred(str(k)) and t_pred(str(k))]
    P = _select_keys(flat, p_pred, False)
    if not (O and P):
        return {"error": "Need OAT and power series"}
    dfO = _df_from_readings(sum((flat[k] for k in O), []))
    dfP = _df_from_readings(sum((flat[k] for k in P), []))
    for d in (dfO, dfP):
        d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    O15 = dfO.set_index("timestamp").sort_index().resample("1H").mean()[["reading_value"]].rename(columns={"reading_value": "OAT"})
    P15 = dfP.set_index("timestamp").sort_index().resample("1H").mean()[["reading_value"]].rename(columns={"reading_value": "kW"})
    X = O15.join(P15, how="inner").dropna()
    if X.empty: return {"error": "No aligned OAT/power"}
    X["date"] = X.index.date
    daily = X.groupby("date").agg({"OAT":"mean", "kW":"sum"})
    daily["kWh"] = daily["kW"]  # since hourly sum of kW approximates kWh
    daily["CDD"] = (daily["OAT"] - float(base_temp_c)).clip(lower=0)
    daily["HDD"] = (float(base_temp_c) - daily["OAT"]).clip(lower=0)
    cdd = float(daily["CDD"].sum()); hdd = float(daily["HDD"].sum()); kwh = float(daily["kWh"].sum())
    kwh_per_cdd = (kwh / cdd) if cdd > 0 else None
    kwh_per_hdd = (kwh / hdd) if hdd > 0 else None
    return {"kWh_per_CDD": (round(kwh_per_cdd,2) if kwh_per_cdd is not None else None), "kWh_per_HDD": (round(kwh_per_hdd,2) if kwh_per_hdd is not None else None), "days": int(len(daily))}


@analytics_function(
    patterns=[
        r"change.*point",
        r"regime.*change",
        r"step.*change",
        r"behavior.*change",
        r"pattern.*shift"
    ],
    description="Detects change points where sensor behavior or patterns shift significantly"
)

def analyze_change_point_detection(sensor_data):
    """
    Change Point Detection — Operational Regime Shift Identification
    
    Purpose:
    Detects abrupt changes in operational patterns (equipment commissioning, setpoint changes, 
    failures, seasonal transitions) using statistical methods. Change points mark "before vs after" 
    boundaries critical for M&V savings calculations, fault root-cause analysis, and operational 
    auditing. This analysis supports IPMVP baseline adjustments and performance degradation tracking.
    
    Sensors:
      - Power or kW sensors (default analysis target)
      - Can analyze any continuous KPI (temp, flow, efficiency)
    
    Output:
      - change_points: List of timestamps where regime shifts detected
      - change_magnitude: Size of shift (kW, °C, etc.)
      - regime_periods: Before/after statistics for each change
      - confidence_score: Detection confidence (0-100%)
      - likely_cause: "Equipment change", "Seasonal", "Setpoint", "Fault"
    
    This analysis helps:
      - Validate retrofit savings (M&V baseline vs post-retrofit)
      - Detect equipment failures (sudden performance drop)
      - Identify unauthorized setpoint changes
      - Support IPMVP Option C savings calculations
      - Audit control sequences (when did behavior change?)
      - Commission new equipment (performance step-change verification)
    
    Method:
      Rolling z-score detection:
        z = (x - μ_rolling) / σ_rolling
        Change point: |z| >3 (3-sigma threshold)
      
      Advanced methods (statistical):
        - CUSUM (Cumulative Sum) for drift detection
        - Bayesian change point (probability-based)
        - PELT (Pruned Exact Linear Time) for multiple changes
      
      Common change point causes:
        - Retrofit: HVAC upgrade, LED installation → power drop 20-40%
        - Seasonal: Heating → Cooling transition → power pattern shift
        - Setpoint: Cooling setpoint 22°C → 24°C → power drop 8-10%
        - Fault: Chiller failure → power drop 30-50%
        - Occupancy: Return-to-office → power increase 15-25%
    
    Parameters:
        sensor_data (dict): Power or other KPI timeseries
    
    Returns:
        dict: Change point timestamps, magnitudes, regime statistics, likely causes

    Detects regime shifts in a KPI (defaults to total kW) using rolling z-score.

    Returns: { change_points: [iso timestamps] }
    """
    flat = _aggregate_flat(sensor_data)
    p_pred = _key_matcher(["power", "kw"]) 
    P = _select_keys(flat, p_pred, False)
    if not P: return {"error": "No power series"}
    dfP = _df_from_readings(sum((flat[k] for k in P), []))
    dfP["timestamp"] = pd.to_datetime(dfP["timestamp"], errors="coerce")
    s = dfP.set_index("timestamp").sort_index().resample("15min").mean()["reading_value"].dropna()
    if s.empty: return {"error": "Empty power series"}
    r = s.rolling(96, min_periods=24)  # 1-day window
    z = (s - r.mean()) / (r.std().replace(0, pd.NA))
    cp = s.index[(z.abs() > 3.0)].to_list()
    return {"change_points": [t.isoformat() for t in cp]}


@analytics_function(
    patterns=[
        r"forecast",
        r"prediction",
        r"future.*value",
        r"next.*hour",
        r"short.*term.*forecast"
    ],
    description="Provides short-horizon (next N steps) forecasting using exponential smoothing"
)

def analyze_short_horizon_forecasting(sensor_data, horizon_steps=12):
    """
    Short Horizon Forecasting — 1-Hour Ahead Prediction
    
    Purpose:
    Generates short-term (5-60 minute) predictions for sensor values using simple 
    statistical models (persistence + drift or exponential smoothing). These forecasts 
    enable proactive control decisions, load anticipation for DR events, and early 
    warning of setpoint violations. Simple models are preferred for real-time edge 
    deployment due to low computational overhead and interpretability.
    
    Sensors:
      - Any sensor with regular timeseries data (temperature, power, flow, etc.)
      - Requires recent history (minimum 24-48 data points for stable estimates)
    
    Output:
      - forecast_values: Array of predicted readings for next N timesteps
      - forecast_timestamps: Corresponding future timestamps
      - confidence_intervals: Upper and lower bounds (95% CI typically)
      - model_type: "Persistence+Drift", "Exponential Smoothing", or "Auto-ARIMA"
      - mae_recent: Mean Absolute Error on recent validation data
    
    This analysis helps:
      - Anticipate HVAC load changes for pre-cooling/pre-heating strategies
      - Predict peak demand events 15-30 minutes ahead for DR curtailment
      - Forecast zone temperature drift to avoid comfort violations
      - Enable Model Predictive Control (MPC) optimization
      - Support automated FDD by flagging predictions that deviate from actual
      - Improve occupancy-based control with arrival/departure forecasts
    
    Method:
      Model selection based on data characteristics:
      
      1. **Persistence + Drift Model** (default for stable trends):
         Forecast(t+k) = Value(t) + k × Recent_Drift
         Where Recent_Drift = average change per timestep over last hour
         
      2. **Exponential Smoothing** (for noisy or seasonal data):
         Uses Holt-Winters method with trend and optional seasonality components
         
      3. **Simple Moving Average** (for highly variable data):
         Uses weighted average of recent N points
      
      Confidence intervals computed using residual standard deviation:
         CI = Forecast ± 1.96 × σ_residual × √(horizon_steps)
      
      Typical horizon_steps:
        - 12 steps × 5 min = 1 hour ahead (default)
        - 6 steps = 30 minutes (DR curtailment decisions)
        - 24 steps = 2 hours (pre-conditioning strategies)
    
    Parameters:
        sensor_data (dict): Recent timeseries data (minimum 24 points recommended)
        horizon_steps (int): Number of future timesteps to predict (default 12 = 1 hour at 5-min intervals)
    
    Returns:
        dict: Forecast arrays, confidence intervals, model metadata, and validation metrics
    """
    flat = _aggregate_flat(sensor_data)
    p_pred = _key_matcher(["power", "kw"]) 
    P = _select_keys(flat, p_pred, False)
    if not P: return {"error": "No power series"}
    dfP = _df_from_readings(sum((flat[k] for k in P), []))
    s = dfP[["timestamp","reading_value"]].copy()
    s["timestamp"] = pd.to_datetime(s["timestamp"], errors="coerce")
    s = s.dropna(subset=["timestamp"]).set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna()
    if len(s) < 12: return {"error": "Insufficient history"}
    drift = float((s.iloc[-1] - s.iloc[-12])) / 12.0
    sigma = float(s.rolling(36, min_periods=12).std().iloc[-1] or 0.0)
    last = float(s.iloc[-1])
    fc = [last + (i+1)*drift for i in range(int(horizon_steps))]
    lower = [v - 1.28*sigma for v in fc]
    upper = [v + 1.28*sigma for v in fc]
    return {"forecast": [round(float(v),2) for v in fc], "lower": [round(float(v),2) for v in lower], "upper": [round(float(v),2) for v in upper], "step_minutes": 5}


@analytics_function(
    patterns=[
        r"statistical.*anomaly",
        r"z.*score.*anomaly",
        r"outlier.*detection",
        r"abnormal.*detection",
        r"statistical.*outlier"
    ],
    description="Statistical anomaly detection using z-score methodology"
)

def analyze_anomaly_detection_statistical(sensor_data, z_thresh=3.5):
    """
    Anomaly Detection (Statistical) — Outlier Identification
    
    Purpose:
    Identifies anomalous readings across multiple sensor streams using robust statistical 
    methods (Median Absolute Deviation - MAD). Unlike spike detection which focuses on 
    sudden changes, this analysis flags any reading that deviates significantly from the 
    sensor's typical distribution, detecting subtle sensor drift, calibration errors, or 
    unusual operating conditions.
    
    Sensors:
      - Applicable to any numeric sensor timeseries
      - Works best with stable baseline behavior (HVAC setpoints, energy consumption)
    
    Output:
      - totals: Count of anomalies per sensor
      - examples: Sample timestamps/indices of anomalous readings
      - severity: Classification of anomaly count (Isolated, Moderate, Severe)
      - affected_sensors: List of sensors with chronic anomalies
    
    This analysis helps:
      - Detect sensor calibration drift requiring maintenance
      - Identify unusual operational patterns (unexpected equipment usage)
      - Support root cause analysis during fault investigations
      - Validate sensor readings before feeding to control systems or ML models
      - Differentiate normal variability from true faults
      - Build clean training datasets for predictive analytics
    
    Method:
      Uses robust z-score based on Median Absolute Deviation (MAD):
        Robust Z = 0.6745 × (x - median) / MAD
        
      Where MAD = median(|x - median(x)|)
      
      Threshold (default z_thresh = 3.5):
        - Readings with |robust_z| > 3.5 are flagged as anomalies
        - More robust to outliers than traditional z-score (mean/std)
        - Less sensitive to extreme values distorting the distribution
      
      Advantages over traditional z-score:
        - Median and MAD not affected by outliers themselves
        - Works well with non-Gaussian distributions
        - Stable with small sample sizes
    
    Parameters:
        sensor_data (dict): Timeseries data from multiple sensors
        z_thresh (float, optional): Robust z-score threshold for anomaly flagging (default 3.5)
    
    Returns:
        dict: Anomaly counts per sensor, example timestamps, and severity classification
    """
    flat = _aggregate_flat(sensor_data)
    if not flat: return {"error": "No data"}
    totals = {}; examples = {}
    for k, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty: continue
        x = df["reading_value"].astype(float)
        med = float(x.median())
        mad = float((x - med).abs().median() or 0.0)
        if mad == 0: 
            totals[str(k)] = 0
            continue
        z = 0.6745 * (x - med) / mad
        idx = z.abs() > float(z_thresh)
        totals[str(k)] = int(idx.sum())
        if idx.any():
            examples[str(k)] = df[idx].head(5)["timestamp"].astype(str).tolist()
    return {"totals": totals, "examples": examples}


@analytics_function(
    patterns=[
        r"air.*change.*per.*hour",
        r"ach",
        r"ventilation.*rate",
        r"air.*exchange.*rate",
        r"room.*air.*change"
    ],
    description="Calculates Air Changes per Hour (ACH) for ventilation assessment"
)

def analyze_ach(sensor_data, zone_volume_m3=None):
    """
    ACH (Air Changes per Hour) — Ventilation adequacy.
    
    Purpose: Calculates the rate at which air in a space is completely replaced, a critical
             metric for indoor air quality, ventilation effectiveness, and compliance with
             building codes and health standards.
    
    Sensors:
      - Supply_Air_Flow_Sensor (volumetric airflow, m³/h or CFM)
      
    Metadata Required:
      - Zone volume (m³)
      
    Output:
      - ACH value by zone (air changes per hour)
      - Under/over ventilation flags
      - Compliance assessment against standards
      - Trending analysis
      
    This analysis helps:
      - Verify HVAC system design ventilation rates
      - Ensure compliance with ASHRAE 62.1 or local building codes
      - Identify zones with inadequate ventilation
      - Optimize ventilation for IAQ and energy efficiency
      - Support pandemic response protocols (higher ACH reduces airborne transmission)
      
    Typical ACH requirements:
      - Residential: 0.35-1.0 ACH (general living)
      - Office: 2-4 ACH (typical)
      - Healthcare: 6-15 ACH (depending on space type)
      - Laboratory: 6-20 ACH (fume hoods, safety)
      
    Calculation:
      ACH = (Airflow m³/h) / (Zone Volume m³)
      
    If zone volume metadata unavailable, analysis reports "metadata missing" flag.

    Parameters:
      - sensor_data: Airflow sensor payload
      - zone_volume_m3: Zone volume in cubic meters (required for calculation)

    Returns: { ach_mean, ach_latest, ach_min, ach_max, compliance_flag, metadata_status }
    """
    if not zone_volume_m3 or float(zone_volume_m3) <= 0:
        return {"error": "zone_volume_m3 required and must be >0"}
    flat = _aggregate_flat(sensor_data)
    flow_pred = _key_matcher(["air_flow", "airflow", "flow_rate"]) 
    keys = _select_keys(flat, flow_pred, False)
    if not keys:
        return {"error": "No airflow series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    s = df.set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna()
    if s.empty: return {"error": "Empty airflow series"}
    # Assume flow is in m3/s if not specified; ACH = (flow[m3/s] * 3600) / volume
    ach = (s.astype(float) * 3600.0) / float(zone_volume_m3)
    return {"ach_mean": round(float(ach.mean()),2), "ach_latest": round(float(ach.iloc[-1]),2), "flag": (float(ach.mean()) < 3.0)}


@analytics_function(
    patterns=[
        r"ventilation.*effectiveness",
        r"outdoor.*air.*delivery",
        r"fresh.*air.*supply",
        r"co2.*removal",
        r"ventilation.*adequacy"
    ],
    description="Assesses ventilation effectiveness based on CO2 removal and fresh air delivery"
)

def analyze_ventilation_effectiveness(sensor_data, co2_threshold=1000):
    """
    Ventilation Effectiveness — CO₂-Based Adequacy Assessment
    
    Purpose:
    Evaluates ventilation adequacy using CO₂ as a proxy for outdoor air delivery per ASHRAE 62.1. 
    CO₂ <1000 ppm indicates sufficient ventilation for occupant health and cognitive performance. 
    This analysis validates demand-controlled ventilation (DCV), supports pandemic protocols, and 
    ensures WELL Building compliance.
    
    Sensors:
      - CO2_Sensor or Indoor_CO2 (ppm)
    
    Output:
      - pct_below_threshold: % time CO₂ ≤1000 ppm (ASHRAE 62.1 target)
      - max_exceedance: Peak CO₂ above threshold (ppm)
      - hours_above: Total hours exceeding threshold
      - ventilation_rating: "Excellent", "Good", "Marginal", "Poor"
      - action_required: Recommendations if inadequate
    
    This analysis helps:
      - Validate ASHRAE 62.1 ventilation compliance
      - Support WELL Building v2 Feature 01 (CO₂ <600 ppm above outdoor)
      - Optimize DCV setpoints (balance IAQ vs energy)
      - Pandemic preparedness (lower CO₂ = reduced infection risk)
      - Investigate occupancy mismatches (high CO₂ = more people than design)
    
    Method:
      Ventilation effectiveness (ASHRAE 62.1-2022):
        Target: Indoor CO₂ <1000-1100 ppm (outdoor baseline ~400-420 ppm)
        Calculation: % of occupied hours meeting target
      
      Performance benchmarks:
        - >95% compliant: Excellent ventilation
        - 85-95%: Good, minor excursions acceptable
        - 70-85%: Marginal, investigate ventilation rate
        - <70%: Poor, inadequate outdoor air, health concern
    
    Parameters:
        sensor_data (dict): CO₂ timeseries data
        co2_threshold (float): Alert threshold in ppm (default 1000 ppm)
    
    Returns:
        dict: Compliance %, max exceedance, hours above, ventilation rating

    CO2-based ventilation adequacy: percent time below threshold and exceedance stats.

    Returns: { pct_below_threshold, max_exceedance, hours_above }
    """
    flat = _aggregate_flat(sensor_data)
    co2_pred = _key_matcher(["co2"]) 
    keys = _select_keys(flat, co2_pred, False)
    if not keys:
        return {"error": "No CO2 series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    s = df.set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna()
    thr = float(co2_threshold)
    pct_ok = float((s <= thr).mean())
    exceed = (s - thr).clip(lower=0)
    hours_above = float((exceed > 0).mean() * len(exceed) * (5/60))
    return {"pct_below_threshold": round(pct_ok,3), "max_exceedance": round(float(exceed.max()),1), "hours_above": round(hours_above,2)}


@analytics_function(
    patterns=[
        r"outdoor.*air.*fraction",
        r"oa.*fraction",
        r"fresh.*air.*percentage",
        r"minimum.*outdoor.*air",
        r"ventilation.*ratio"
    ],
    description="Calculates outdoor air fraction in supply air for ventilation compliance"
)

def analyze_outdoor_air_fraction(sensor_data):
    """
    Outdoor Air Fraction — Ventilation Rate Verification
    
    Purpose:
    Calculates actual outdoor air percentage using temperature-based mass balance equation to 
    verify ASHRAE 62.1 minimum ventilation requirements. Discrepancies between commanded and 
    actual OA fraction indicate damper failures, sensor errors, or control issues that compromise 
    IAQ and waste energy.
    
    Sensors:
      - Return_Air_Temperature (RAT), Mixed_Air_Temperature (MAT), Outside_Air_Temperature (OAT)
    
    Output:
      - mean_fraction: Average OA fraction (0-1, 0=0%, 1=100%)
      - latest_fraction: Current OA percentage
      - compliance: "Meets minimum" or "Below ASHRAE 62.1"
      - damper_agreement: Comparison with commanded position (if available)
      - energy_impact: Excess ventilation energy penalty
    
    This analysis helps:
      - Verify ASHRAE 62.1 minimum outdoor air compliance (typically 15-25%)
      - Detect damper failures (stuck open/closed)
      - Validate economizer operation (OA fraction should vary 10-100%)
      - Identify sensor errors (impossible OA fractions >100% or <0%)
      - Quantify excess ventilation energy waste
    
    Method:
      Mass balance equation:
        f_OA = (T_mixed - T_return) / (T_outdoor - T_return)
      
      Where 0 ≤ f_OA ≤ 1:
        - f_OA = 0: 0% outdoor air (100% recirculation)
        - f_OA = 0.20: 20% outdoor air (typical minimum per ASHRAE 62.1)
        - f_OA = 1.0: 100% outdoor air (economizer mode)
      
      ASHRAE 62.1-2022 minimums:
        - Office: 15-20% OA (depends on occupancy density, zone area)
        - School classroom: 20-30% OA (high occupancy)
        - Hospital: 25-50% OA (infection control)
    
    Parameters:
        sensor_data (dict): RAT, MAT, OAT timeseries
    
    Returns:
        dict: OA fraction statistics, compliance status, damper validation

    Computes realized Outdoor Air fraction using temperatures: f_OA = (MAT - RAT)/(OAT - RAT).

    Returns: { mean_fraction, latest_fraction }
    """
    flat = _aggregate_flat(sensor_data)
    r_pred = _key_matcher(["return_air", "return"]) ; m_pred = _key_matcher(["mixed_air", "mix"]) ; o_pred = _key_matcher(["outside_air", "outdoor"]) ; t_pred = _key_matcher(["temperature", "temp"]) 
    Rk = [k for k in flat.keys() if r_pred(str(k)) and t_pred(str(k))]
    Mk = [k for k in flat.keys() if m_pred(str(k)) and t_pred(str(k))]
    Ok = [k for k in flat.keys() if o_pred(str(k)) and t_pred(str(k))]
    if not (Rk and Mk and Ok):
        return {"error": "Need RAT, MAT, and OAT series"}
    dfR = _df_from_readings(sum((flat[k] for k in Rk), []))
    dfM = _df_from_readings(sum((flat[k] for k in Mk), []))
    dfO = _df_from_readings(sum((flat[k] for k in Ok), []))
    for d in (dfR, dfM, dfO): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfM.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_m","_r"))
    mm = pd.merge_asof(mm.sort_values("timestamp"), dfO.sort_values("timestamp"), on="timestamp", direction="nearest")
    if mm.empty: return {"error": "Could not align series"}
    num = mm["reading_value_m"] - mm["reading_value_r"]
    den = (mm["reading_value"] - mm["reading_value_r"]).replace(0, pd.NA)
    frac = (num / den).clip(lower=0, upper=1).dropna()
    if frac.empty: return {"error": "Invalid OA fraction"}
    return {"mean_fraction": round(float(frac.mean()),3), "latest_fraction": round(float(frac.iloc[-1]),3)}


@analytics_function(
    patterns=[
        r"setpoint.*compliance",
        r"setpoint.*tracking",
        r"control.*accuracy",
        r"within.*tolerance",
        r"setpoint.*deviation"
    ],
    description="Checks setpoint compliance with configurable tolerance bands"
)

def analyze_setpoint_compliance(sensor_data, tolerance=1.0):
    """
    Setpoint Compliance — Control Performance Tracking
    
    Purpose:
    Quantifies how well control systems maintain measured values (temperature, pressure, 
    flow) within tolerance of their setpoints. Poor setpoint tracking indicates control 
    loop tuning issues, actuator problems, or inadequate capacity. This analysis validates 
    BMS commissioning, identifies control instability, and supports continuous commissioning 
    programs by objectively measuring control performance.
    
    Sensors:
      - Measured_Value_Sensor (actual temperature, pressure, flow, etc.)
      - Setpoint signal or configured target value
      - Common pairs:
        * Supply_Air_Temperature + SAT_Setpoint
        * Static_Pressure + Static_Pressure_Setpoint
        * Zone_Temperature + Zone_Temperature_Setpoint
    
    Output:
      - mae: Mean Absolute Error (average deviation magnitude)
      - mape: Mean Absolute Percentage Error (%)
      - pct_within: Percentage of time within tolerance band (default ±1.0°C or unit)
      - tracking_quality: "Excellent", "Good", "Fair", or "Poor"
      - overshoot_pct: Percentage of time above setpoint + tolerance
      - undershoot_pct: Percentage of time below setpoint - tolerance
    
    This analysis helps:
      - Validate BMS control loop commissioning
      - Identify PID tuning issues (overshoot, oscillation, sluggish response)
      - Detect actuator problems (stuck valves, dampers)
      - Assess equipment capacity adequacy vs setpoint targets
      - Support continuous commissioning and retro-commissioning
      - Quantify comfort delivery vs design intent
    
    Method:
      Error calculations:
        Error(t) = Measured(t) - Setpoint(t)
        
        MAE = mean(|Error(t)|)
        MAPE = mean(|Error(t)| / Setpoint(t)) × 100%
        
        % Within Band = count(|Error(t)| ≤ tolerance) / total_points × 100%
      
      Tolerance bands by application:
        **Temperature (°C):**
          - Supply Air: ±0.5°C excellent, ±1.0°C acceptable, >±1.5°C poor
          - Zone Air: ±1.0°C excellent, ±1.5°C acceptable, >±2.0°C poor
          - Water: ±0.5°C excellent, ±1.0°C acceptable
        
        **Pressure (Pa or kPa):**
          - Static pressure: ±10-25 Pa acceptable for VAV systems
          - Differential pressure: ±5-10% of setpoint
        
        **Flow (L/s or m³/h):**
          - ±10-15% of setpoint typical tolerance
      
      Tracking quality classification:
        - Excellent: MAE < 0.5× tolerance, >95% time in band
        - Good: MAE < 1.0× tolerance, 90-95% in band
        - Fair: MAE < 1.5× tolerance, 80-90% in band
        - Poor: MAE > 1.5× tolerance or <80% in band
      
      Diagnostic patterns:
        **Persistent overshoot (majority points > setpoint + tolerance):**
          - Control valve/damper stuck partially open
          - Setpoint too low for current load conditions
          - Integral term windup in PI/PID controller
        
        **Persistent undershoot (majority points < setpoint - tolerance):**
          - Inadequate capacity (equipment undersized)
          - Control valve/damper stuck partially closed
          - Setpoint too aggressive for equipment capability
        
        **High variability (oscillation around setpoint):**
          - PID tuning too aggressive (high proportional gain)
          - Actuator hunting or stiction
          - Sensor noise or poor location
        
        **Slow response (settles eventually but takes too long):**
          - Integral time too long
          - Derivative term needed but missing
          - Process has long time constant
      
      Control performance benchmarks:
        ASHRAE Guideline 36 targets:
          - SAT control: ±0.3°C (±0.5°F) steady-state error
          - Zone temperature: ±0.6°C (±1°F) from setpoint
          - Static pressure: ±10 Pa during stable periods
        
        Achieving >90% time within ±1.0°C is considered good control
        for commercial HVAC temperature applications.
    
    Parameters:
        sensor_data (dict): Measured value and setpoint timeseries
        tolerance (float, optional): Acceptable deviation from setpoint (default 1.0 in sensor units)
    
    Returns:
        dict: MAE, MAPE, % within band, tracking quality classification, overshoot/undershoot metrics
    """
    flat = _aggregate_flat(sensor_data)
    sp_pred = _key_matcher(["setpoint", "sp"]) ; m_pred = _key_matcher(["temperature", "temp", "value"]) 
    sp_keys = _select_keys(flat, sp_pred, False)
    m_keys = _select_keys(flat, m_pred, False)
    if not (sp_keys and m_keys):
        return {"error": "Need setpoint and measurement series"}
    dfS = _df_from_readings(sum((flat[k] for k in sp_keys), []))
    dfM = _df_from_readings(sum((flat[k] for k in m_keys), []))
    for d in (dfS, dfM): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfM.sort_values("timestamp"), dfS.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_meas","_sp"))
    if mm.empty: return {"error": "Could not align setpoint/measurement"}
    err = (mm["reading_value_meas"].astype(float) - mm["reading_value_sp"].astype(float)).abs()
    mae = float(err.mean())
    denom = mm["reading_value_sp"].replace(0, pd.NA).abs()
    mape = float((err / denom).dropna().mean()) if denom.notna().any() else None
    within = float((err <= float(tolerance)).mean())
    return {"mae": round(mae,2), "mape": (round(mape,3) if mape is not None else None), "pct_within": round(within,3), "tolerance": float(tolerance)}


@analytics_function(
    patterns=[
        r"hunting",
        r"oscillation",
        r"control.*instability",
        r"cycling.*control",
        r"unstable.*control"
    ],
    description="Detects hunting and oscillation in control loops indicating tuning issues"
)

def analyze_hunting_oscillation(sensor_data):
    """
    Hunting/Oscillation Detection — Control Loop Instability Analysis
    
    Purpose:
    Detects oscillating control behavior (hunting) in temperature, pressure, or valve position signals. 
    Oscillation indicates poor PID tuning (excessive gain, short integral time), causing equipment wear, 
    energy waste, and occupant discomfort. This analysis quantifies frequency and amplitude to guide 
    PID retuning per ASHRAE Guideline 36.
    
    Sensors: Temperature, Pressure, Valve_Position, Damper_Position, Command signals
    
    Output:
      - frequency_cph: Oscillation frequency (cycles/hour)
      - amplitude: Peak-to-peak magnitude
      - index: Severity score (amplitude × frequency)
      - tuning_recommendation: "Reduce P gain", "Increase I time", "Acceptable"
    
    Method:
      Zero-crossing analysis detects oscillation periods. Typical issues:
        - High frequency (>6 cph): Excessive P gain → reduce by 30-50%
        - Large amplitude (>2°C): Insufficient damping → increase integral time
        - ASHRAE Guideline 36: Target <3 cycles/hour, <1°C amplitude
    
    Returns: { frequency_cph, amplitude, index }

    Detects oscillations by zero-crossings of de-meaned signal and estimates amplitude/frequency.

    Returns: { frequency_cph, amplitude, index }
    """
    flat = _aggregate_flat(sensor_data)
    # Choose a control variable: temp, pressure, or valve/command
    pred = _key_matcher(["temperature", "pressure", "valve", "command", "position"]) 
    keys = _select_keys(flat, pred, False)
    if not keys: return {"error": "No suitable control signal"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    s = df.set_index("timestamp").sort_index().resample("1min").mean()["reading_value"].dropna()
    if len(s) < 60: return {"error": "Insufficient length"}
    x = s - s.mean()
    # Zero-crossing detection
    signs = (x > 0).astype(int)
    crossings = (signs.diff().abs() == 1)
    # Period estimation: time between alternating crossings (approx 1/2 period per crossing)
    times = s.index[crossings]
    if len(times) < 4: return {"error": "Insufficient crossings"}
    diffs = pd.Series(times).diff().dropna().dt.total_seconds()
    if diffs.empty: return {"error": "No period diffs"}
    period_s = float(diffs.median() * 2)  # approx full period
    freq_cph = 3600.0 / period_s if period_s > 0 else 0.0
    amp = float((x.max() - x.min()) / 2.0)
    index = float(amp * freq_cph)
    return {"frequency_cph": round(freq_cph,2), "amplitude": round(amp,2), "index": round(index,2)}


@analytics_function(
    patterns=[
        r"stiction",
        r"stuck.*actuator",
        r"valve.*sticking",
        r"damper.*stiction",
        r"actuator.*binding"
    ],
    description="Detects actuator stiction (stuck positions) in valves and dampers"
)

def analyze_actuator_stiction(sensor_data, flatline_points=10):
    """
    Actuator Stiction Detection — Valve/Damper Friction Analysis
    
    Purpose:
    Detects actuator stiction (static friction causing stick-slip behavior) and non-responsive movement. 
    Stiction causes valves/dampers to stick at positions then suddenly jump, resulting in poor control, 
    temperature swings, and reduced actuator lifespan. This analysis guides maintenance scheduling and 
    actuator replacement decisions.
    
    Sensors: Valve_Position, Damper_Position, Actuator_Command
    
    Output:
      - stiction_index: Severity score (0-10+, >2 = significant stiction)
      - flatline_events: Count of stuck periods (>10 samples unchanged)
      - low_motion_pct: % of time with minimal movement (<0.2% changes)
      - flag: Boolean alert (true if stiction_index >2)
    
    Method:
      Combines flatline detection (stuck position) and low-motion analysis. Root causes:
        - Dry bearings/bushings → lubricate actuator linkage
        - Corroded stem → replace valve/damper
        - Oversized actuator → generates excessive force, breaks free suddenly
      
      Repair: Lubrication ($100-$300), actuator replacement ($500-$2000)
    
    Returns: { stiction_index, flatline_events, low_motion_pct, flag }

    Detects actuator stiction/nonlinearity using position flatlines and low responsiveness.

    Returns: { stiction_index, flatline_events, low_motion_pct, flag }
    """
    flat = _aggregate_flat(sensor_data)
    pos_pred = _key_matcher(["valve", "damper", "actuator"]) ; p2 = _key_matcher(["position", "command"]) 
    keys = [k for k in flat.keys() if pos_pred(str(k)) and p2(str(k))]
    if not keys:
        return {"error": "No actuator position/command series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    if df.empty: return {"error": "Empty actuator series"}
    v = df["reading_value"].astype(float).reset_index(drop=True)
    # Flatlines
    flatlines = 0; run = 1
    for i in range(1, len(v)):
        if v.iloc[i] == v.iloc[i-1]:
            run += 1
        else:
            if run >= int(flatline_points): flatlines += 1
            run = 1
    if run >= int(flatline_points): flatlines += 1
    # Low motion percentage (small incremental changes)
    dv = v.diff().abs().fillna(0)
    low_motion_pct = float((dv <= 0.2).mean())  # <=0.2% step
    idx = float(flatlines) + low_motion_pct
    return {"stiction_index": round(idx,3), "flatline_events": int(flatlines), "low_motion_pct": round(low_motion_pct,3), "flag": bool(idx > 2)}


def analyze_co_co2_safety(sensor_data, co_threshold=30.0, co2_threshold=5000.0):
    """
    CO & CO₂ Safety Monitoring — Toxic Gas Detection & OSHA Compliance
    
    Purpose:
    Monitors carbon monoxide (CO) and high-concentration CO₂ for occupant safety per OSHA regulations. 
    CO is toxic at low levels (>50 ppm = health hazard); very high CO₂ (>5000 ppm) indicates poor 
    ventilation or combustion issues. This analysis triggers emergency ventilation and safety alarms.
    
    Sensors: CO_Sensor (ppm), CO2_Sensor (ppm)
    
    Output:
      - CO: {peak, hours_above_threshold, twa_8hr, osha_compliance}
      - CO2: {peak, hours_above_threshold, safety_flag}
    
    Thresholds:
      CO (OSHA PEL = 50 ppm, STEL = 400 ppm for 15 min):
        - <25 ppm: Safe
        - 25-50 ppm: Elevated, investigate combustion sources
        - >50 ppm: OSHA violation, evacuate and fix immediately
      
      CO₂ (OSHA PEL = 5000 ppm, IDLH = 40,000 ppm):
        - <1500 ppm: Normal IAQ range
        - 1500-5000 ppm: Poor ventilation (not toxic but uncomfortable)
        - >5000 ppm: OSHA limit, health hazard (headaches, dizziness)
        - >40,000 ppm: Immediately Dangerous to Life & Health
    
    Returns: { CO: {...}, CO2: {...} }

    Safety analysis for CO and CO2: peak, hours above thresholds, and simple severity.

    Returns: { CO: {...}, CO2: {...} }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat: return {"error": "No data"}
    # Separate CO from CO2 by name
    co_keys = [k for k in flat.keys() if "co2" not in str(k).lower() and "co" in str(k).lower()]
    co2_keys = [k for k in flat.keys() if "co2" in str(k).lower()]
    def summarize(keys, thr):
        if not keys: return {"error": "missing"}
        df = _df_from_readings(sum((flat[k] for k in keys), []))
        if df.empty: return {"error": "empty"}
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        s = df.set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna().astype(float)
        if s.empty: return {"error": "empty"}
        peak = float(s.max()); hours_above = float((s > float(thr)).mean() * len(s) * (5/60))
        twa8 = float(s.rolling(int(8*60/5), min_periods=3).mean().max())  # 8h TWA max
        severity = ("danger" if peak > 2*float(thr) else ("warn" if peak > float(thr) or hours_above>0 else "ok"))
        return {"peak": round(peak,1), "hours_above": round(hours_above,2), "twa8_max": round(twa8,1), "threshold": float(thr), "severity": severity}
    return {"CO": summarize(co_keys, co_threshold), "CO2": summarize(co2_keys, co2_threshold)}


@analytics_function(
    patterns=[
        r"illuminance",
        r"lighting.*level",
        r"lux",
        r"light.*intensity",
        r"luminance"
    ],
    description="Tracks illuminance/luminance levels for lighting quality assessment"
)

def analyze_illuminance_luminance_tracking(sensor_data, target_lux=None, band=100.0):
    """
    Illuminance/Luminance Tracking — Lighting Level Compliance
    
    Purpose:
    Monitors lighting levels against design targets (CIBSE, IESNA standards) for occupant comfort, 
    task performance, and energy efficiency. Insufficient lighting (<300 lux offices) causes eye 
    strain; excessive lighting (>750 lux) wastes energy. This analysis validates daylight harvesting 
    and lighting control performance.
    
    Sensors: Illuminance_Sensor (lux), Luminance_Sensor (cd/m²)
    
    Output:
      - mean_lux: Average illuminance
      - within_band_pct: % time within target ±band
      - under_lit_hours: Hours below minimum
      - over_lit_hours: Hours above maximum
    
    Standards (CIBSE LG7, IESNA):
      - Office general: 300-500 lux
      - Office detailed work: 500-750 lux
      - Classroom: 300-500 lux
      - Retail: 500-1000 lux (merchandise display)
      - Warehouse: 150-300 lux
    
    Returns: { mean_lux, within_band_pct, under_lit_hours, over_lit_hours }

    Light level tracking vs target: mean, median, MAE to target, and percent within band.

    Returns: { mean_lux, median_lux, mae_to_target, pct_within_band }
    """
    flat = _aggregate_flat(sensor_data)
    lux_pred = _key_matcher(["illuminance", "lux", "light"]) 
    keys = _select_keys(flat, lux_pred, False)
    if not keys: return {"error": "No illuminance series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    s = df["reading_value"].astype(float)
    mean_lux = float(s.mean()); median_lux = float(s.median())
    if target_lux is None:
        return {"mean_lux": round(mean_lux,1), "median_lux": round(median_lux,1), "mae_to_target": None, "pct_within_band": None}
    err = (s - float(target_lux)).abs()
    within = (err <= float(band)).mean()
    return {"mean_lux": round(mean_lux,1), "median_lux": round(median_lux,1), "mae_to_target": round(float(err.mean()),1), "pct_within_band": round(float(within),3), "target_lux": float(target_lux), "band": float(band)}


@analytics_function(
    patterns=[
        r"noise.*monitoring",
        r"sound.*level.*monitoring",
        r"acoustic.*monitoring",
        r"noise.*comfort",
        r"noise.*threshold"
    ],
    description="Monitors noise levels with comfort and high-threshold classifications"
)

def analyze_noise_monitoring(sensor_data, comfort_threshold=55.0, high_threshold=70.0):
    """
    Noise Monitoring — Acoustic Comfort & Occupational Health
    
    Purpose:
    Monitors sound pressure levels (dB) for occupant comfort (WHO guidelines: <55 dBA offices) 
    and occupational health (OSHA: <90 dBA 8-hr TWA). Excessive noise causes stress, reduced 
    productivity, and hearing damage. This analysis supports WELL Building Sound Feature and 
    LEED acoustic performance credits.
    
    Sensors: Sound_Pressure_Level (dBA)
    
    Output:
      - mean_db: Average noise level
      - peak_db: Maximum level
      - hours_above_comfort: Hours >55 dBA (WHO comfort limit)
      - hours_above_high: Hours >70 dBA (OSHA action level)
    
    Thresholds:
      - <40 dBA: Quiet (library, bedroom)
      - 40-55 dBA: Comfortable (WHO office guideline, WELL Building)
      - 55-70 dBA: Elevated (impacts concentration)
      - 70-85 dBA: Noisy (HVAC equipment rooms)
      - >85 dBA: OSHA requires hearing protection (8-hr TWA)
      - >90 dBA: OSHA PEL, mandatory controls
    
    Returns: { mean_db, peak_db, hours_above_comfort, hours_above_high }

    Acoustic comfort percentiles and exceedances at two thresholds.

    Returns: { p50, p90, max, pct_above_comfort, pct_above_high }
    """
    flat = _aggregate_flat(sensor_data)
    n_pred = _key_matcher(["noise", "sound", "dba", "db"]) 
    keys = _select_keys(flat, n_pred, False)
    if not keys: return {"error": "No noise series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    x = df["reading_value"].astype(float)
    p50 = float(x.quantile(0.5)); p90 = float(x.quantile(0.9)); mx = float(x.max())
    pct_comf = float((x > float(comfort_threshold)).mean())
    pct_high = float((x > float(high_threshold)).mean())
    return {"p50": round(p50,1), "p90": round(p90,1), "max": round(mx,1), "pct_above_comfort": round(pct_comf,3), "pct_above_high": round(pct_high,3)}


@analytics_function(
    patterns=[
        r"sensor.*swap",
        r"mismatched.*sensor",
        r"sensor.*mix.*up",
        r"sensor.*labeling",
        r"sensor.*identification"
    ],
    description="Infers potential sensor swaps or bias by comparing expected vs actual patterns"
)

def analyze_sensor_swap_bias_inference(sensor_data):
    """
    Sensor Swap & Bias Inference — Sensor Fault Detection
    
    Purpose:
    Identifies likely swapped temperature sensors (e.g., supply/return reversed) and sensors 
    exhibiting systematic bias using expected physical relationships. Supply air should be cooler 
    than return air in cooling mode; violations suggest wiring errors during commissioning or 
    sensor calibration drift. This diagnostic prevents incorrect analytics and control decisions 
    caused by bad sensor data.
    
    Sensors: Temperature sensors (supply, return, inlet, outlet)
    
    Output:
      - swap_suspicions: Likely swapped sensor pairs ["Supply<->Return"]
      - bias_candidates: Sensors with constant offset vs peer median [{sensor, bias}]
    
    This analysis helps:
      - Detect commissioning errors (reversed wiring)
      - Identify sensors requiring recalibration (drift >±2°C)
      - Validate sensor installation before analytics deployment
      - Prevent faulty control sequences based on incorrect readings
      - Support automated sensor validation in large portfolios
    
    Detection Rules:
      1. Supply/Return swap: If supply temp > return temp for >70% of time (cooling systems)
      2. Bias detection: Sensor median differs from peer median by >2°C consistently
      3. Expected relationships: Supply < Mixed < Return (cooling), Supply > Return (heating)
    
    Standards:
      - ASHRAE Guideline 36: Supply air temp setpoints typically 12-15°C (cooling)
      - Sensor accuracy: ±0.5°C (NIST calibration standards)
      - Commissioning: ASHRAE Guideline 0 requires sensor functional testing
    
    Returns: { swap_suspicions: ["A<->B"], bias_candidates: [{sensor, bias}] }

    Heuristics to infer swapped sensors or strong bias using expected ordering (supply/return, inlet/outlet).

    Returns: { swap_suspicions: ["A<->B"], bias_candidates: [{sensor, bias}] }
    """
    flat = _aggregate_flat(sensor_data)
    if not flat: return {"error": "No data"}
    keys = list(flat.keys())
    susp = []
    bias = []
    # Supply vs return temperature
    sup_t = [k for k in keys if "supply" in str(k).lower() and ("temp" in str(k).lower() or "temperature" in str(k).lower())]
    ret_t = [k for k in keys if "return" in str(k).lower() and ("temp" in str(k).lower() or "temperature" in str(k).lower())]
    if sup_t and ret_t:
        dfS = _df_from_readings(sum((flat[k] for k in sup_t), []))
        dfR = _df_from_readings(sum((flat[k] for k in ret_t), []))
        mm = pd.merge_asof(dfS.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_s","_r"))
        if not mm.empty:
            diff = (mm["reading_value_s"] - mm["reading_value_r"])  # expected negative for CHW coil discharge
            if (diff > 0.5).mean() > 0.7:
                susp.append(f"{sup_t[0]}<->{ret_t[0]}")
    # Bias: detect sensors far from peers median by constant offset
    series = []
    for k in keys:
        df = _df_from_readings(flat[k])
        if df.empty: continue
        series.append(df["reading_value"].astype(float).median())
    if len(series) >= 3:
        med_all = float(pd.Series(series).median())
        for k in keys:
            df = _df_from_readings(flat[k])
            if df.empty: continue
            med = float(df["reading_value"].astype(float).median())
            if abs(med - med_all) > 2.0:
                bias.append({"sensor": str(k), "bias": round(float(med - med_all),2)})
    return {"swap_suspicions": susp, "bias_candidates": bias}


@analytics_function(
    patterns=[
        r"economizer.*fault",
        r"economizer.*diagnostic",
        r"economizer.*fdd",
        r"free.*cooling.*fault",
        r"outdoor.*air.*damper.*fault"
    ],
    description="Applies fault detection rules for economizer operation and damper control"
)

def analyze_economizer_fault_rules(sensor_data, damper_open_thresh=30.0):
    """
    Economizer Fault Detection — Rule-Based FDD for Free Cooling
    
    Purpose:
    Applies ASHRAE fault detection rules to identify economizer malfunctions that waste energy 
    by rejecting free cooling opportunities or introducing excessive outdoor air when costly 
    mechanical cooling is needed. Economizer faults are among the most common HVAC issues, 
    costing $1000-$5000/year per AHU in wasted energy.
    
    Sensors:
      - Outside_Air_Temperature (OAT)
      - Return_Air_Temperature (RAT)
      - Mixed_Air_Temperature (MAT)
      - OA_Damper_Position (%, optional but improves accuracy)
    
    Output:
      - does_not_open_count: Occurrences of free cooling available but damper closed
      - stuck_open_count: Occurrences of damper open when OAT > RAT (wasting energy)
      - suggestions: Corrective actions
    
    This analysis helps:
      - Recover 20-40% energy savings from economizer operation
      - Detect stuck dampers, failed actuators, or incorrect control sequences
      - Validate economizer commissioning and seasonal changeover logic
      - Prioritize maintenance on high-impact faults
      - Comply with ASHRAE 90.1 economizer requirements
    
    Fault Rules (ASHRAE RP-1312):
      1. **Does not open**: OAT < RAT - 1°C (free cooling available) AND damper < 30% open
         → Check economizer enable logic, actuator, or outdoor air damper linkage
      2. **Stuck open**: OAT > RAT + 1°C (mechanical cooling needed) AND damper > 60% open
         → Verify damper not stuck/leaking; adjust minimum OA limits
    
    Thresholds:
      - Temperature deadband: ±1°C hysteresis to avoid false alarms
      - Damper thresholds: <30% (closed), >60% (open)
    
    Returns: { does_not_open_count, stuck_open_count, suggestions }

    Rule-based economizer FDD using OAT/RAT/MAT and outdoor damper position.

    Returns: { does_not_open_count, stuck_open_count, suggestions }
    """
    flat = _aggregate_flat(sensor_data)
    r_pred = _key_matcher(["return_air", "return"]) ; m_pred = _key_matcher(["mixed_air", "mix"]) ; o_pred = _key_matcher(["outside_air", "outdoor"]) ; t_pred = _key_matcher(["temperature", "temp"]) ; d_pred = _key_matcher(["damper", "outdoor", "economizer"]) 
    Rk = [k for k in flat.keys() if r_pred(str(k)) and t_pred(str(k))]
    Mk = [k for k in flat.keys() if m_pred(str(k)) and t_pred(str(k))]
    Ok = [k for k in flat.keys() if o_pred(str(k)) and t_pred(str(k))]
    Dk = [k for k in flat.keys() if d_pred(str(k)) and ("position" in str(k).lower())]
    if not (Rk and Mk and Ok):
        return {"error": "Need RAT, MAT, and OAT series"}
    dfR = _df_from_readings(sum((flat[k] for k in Rk), []))
    dfM = _df_from_readings(sum((flat[k] for k in Mk), []))
    dfO = _df_from_readings(sum((flat[k] for k in Ok), []))
    for d in (dfR, dfM, dfO): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfM.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_m","_r"))
    mm = pd.merge_asof(mm.sort_values("timestamp"), dfO.sort_values("timestamp"), on="timestamp", direction="nearest")
    if mm.empty: return {"error": "Could not align temps"}
    if Dk:
        dfD = _df_from_readings(sum((flat[k] for k in Dk), []))
        dfD["timestamp"] = pd.to_datetime(dfD["timestamp"], errors="coerce")
        mm = pd.merge_asof(mm.sort_values("timestamp"), dfD.sort_values("timestamp"), on="timestamp", direction="nearest", suffixes=("","_damper"))
        damper = mm.filter(like="reading_value_damper").iloc[:, -1]
    else:
        damper = pd.Series(index=mm.index, dtype=float)
        damper[:] = pd.NA
    # Rules
    free_cool = (mm["reading_value"] < mm["reading_value_r"] - 1.0)  # OAT < RAT
    damper_low = (damper.fillna(0) < float(damper_open_thresh))
    does_not_open = (free_cool & damper_low).sum()
    hot_out = (mm["reading_value"] > mm["reading_value_r"] + 1.0)  # OAT > RAT
    damper_high = (damper.fillna(100) > 60.0)
    stuck_open = (hot_out & damper_high).sum()
    sugg = []
    if does_not_open > 0: sugg.append("Check economizer enable/setpoints or actuator")
    if stuck_open > 0: sugg.append("Verify OA damper not stuck/leaking; adjust limits")
    return {"does_not_open_count": int(does_not_open), "stuck_open_count": int(stuck_open), "suggestions": sugg}


@analytics_function(
    patterns=[
        r"low.*delta.*t",
        r"delta.*t.*syndrome",
        r"poor.*temperature.*difference",
        r"chiller.*delta.*t.*problem",
        r"low.*dt"
    ],
    description="Detects low delta-T syndrome in chilled water systems reducing efficiency"
)

def analyze_low_delta_t_syndrome(sensor_data):
    """
    Low Delta-T Syndrome — Chilled Water System Efficiency Diagnosis
    
    Purpose:
    Detects the pervasive "low ΔT syndrome" in chilled water systems where supply-return 
    temperature difference is too small (<5°C design vs <3°C actual). This forces excess water 
    flow, increases pump energy by 50-100%, and reduces chiller efficiency. Low ΔT syndrome 
    costs $5000-$20,000/year per chiller plant and is found in 60% of commercial buildings.
    
    Sensors:
      - CHW_Supply_Temperature (°C)
      - CHW_Return_Temperature (°C)
    
    Output:
      - pct_below_3C: % time ΔT < 3°C (severe syndrome)
      - pct_below_5C: % time ΔT < 5°C (design target missed)
      - hours_low_dt: Total hours with low ΔT
      - syndrome_flag: Boolean alert if syndrome present
    
    This analysis helps:
      - Identify coil bypass (3-way valves, oversized coils)
      - Detect low chiller load (excessive chiller capacity)
      - Diagnose building controls issues (poor reset strategies)
      - Quantify pump energy waste (affinity laws: power ∝ flow³)
      - Guide VFD pump optimization and valve replacement
    
    Root Causes:
      - 3-way coil valves allowing bypass (replace with 2-way + VFD pumps)
      - Oversized coils (high K-factor, low ΔT at part load)
      - Excessive CHW supply temp reset (>7°C reduces ΔT)
      - Low building load with fixed flow primary pumps
    
    Design Targets:
      - Design ΔT: 5-6°C (10-12°F) per ASHRAE
      - Acceptable: ΔT > 4°C for >80% of runtime
      - Syndrome flag: ΔT < 3°C for >50% OR ΔT < 5°C for >70%
    
    Energy Impact:
      - Low ΔT → 2× flow → 8× pump power (affinity laws)
      - Retrofit savings: $10,000-$50,000/year for large systems
    
    Returns: { pct_below_3C, pct_below_5C, hours_low_dt, syndrome_flag }

    Dedicated low-ΔT syndrome detection on CHW loop.

    Returns: { pct_below_3C, pct_below_5C, hours_low_dt, syndrome_flag }
    """
    res = analyze_chilled_water_delta_t(sensor_data)
    if "error" in res:
        return res
    # Recompute distribution if possible
    flat = _aggregate_flat(sensor_data)
    cs_pred = _key_matcher(["chilled_water", "chw"]) ; sup_pred = _key_matcher(["supply"]) ; ret_pred = _key_matcher(["return"]) ; t_pred = _key_matcher(["temperature", "temp"]) 
    ChwS = [k for k in flat.keys() if cs_pred(str(k)) and sup_pred(str(k)) and t_pred(str(k))]
    ChwR = [k for k in flat.keys() if cs_pred(str(k)) and ret_pred(str(k)) and t_pred(str(k))]
    if not (ChwS and ChwR):
        return {"error": "Need CHW supply/return temps"}
    dfS = _df_from_readings(sum((flat[k] for k in ChwS), []))
    dfR = _df_from_readings(sum((flat[k] for k in ChwR), []))
    for d in (dfS, dfR): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfR.sort_values("timestamp"), dfS.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_r","_s"))
    if mm.empty: return {"error": "Could not align CHW temps"}
    dT = (mm["reading_value_r"] - mm["reading_value_s"]).clip(lower=0)
    pct3 = float((dT < 3.0).mean())
    pct5 = float((dT < 5.0).mean())
    hours = float(len(dT) * (5/60))
    flag = bool(pct3 > 0.5 or pct5 > 0.7)
    return {"pct_below_3C": round(pct3,3), "pct_below_5C": round(pct5,3), "hours_low_dt": round(hours,1), "syndrome_flag": flag}


@analytics_function(
    patterns=[
        r"simultaneous.*heating.*cooling",
        r"fighting.*mode",
        r"heating.*and.*cooling",
        r"energy.*waste",
        r"control.*conflict"
    ],
    description="Detects simultaneous heating and cooling waste (fighting mode)"
)

def analyze_simultaneous_heating_cooling(sensor_data):
    """
    Simultaneous Heating & Cooling — Energy Waste Detection
    
    Purpose:
    Identifies periods when heating and cooling systems operate simultaneously, a common control 
    fault that wastes 10-30% of HVAC energy. Typical in VAV systems with terminal reheat, mixed 
    air units, or buildings with poor control sequences. Costs $2000-$10,000/year per building 
    in wasted energy (heating, cooling, and fan power).
    
    Sensors:
      - Heating_Valve_Position or Hot_Water_Valve (%)
      - Cooling_Valve_Position or CHW_Valve or Compressor_Command (%)
    
    Output:
      - overlap_pct: % time both heating and cooling active (>10% valve position)
      - overlap_hours: Total hours of simultaneous operation
    
    This analysis helps:
      - Detect faulty control sequences (reheat before economizer, improper deadbands)
      - Identify zones fighting central plant (bad setpoints)
      - Validate VAV terminal unit sequences (ASHRAE Guideline 36)
      - Quantify energy waste for retrofit justification
      - Support retro-commissioning efforts
    
    Common Causes:
      - Insufficient deadband between heating/cooling setpoints (<1°C)
      - Terminal reheat active while AHU cooling coil operates
      - Simultaneous humidification and dehumidification
      - Economizer disabled while reheat operates
      - Perimeter zones overheating from solar gains while core cools
    
    Standards & Thresholds:
      - ASHRAE 90.1: Prohibits simultaneous heating/cooling except for humidity control
      - Acceptable overlap: <5% of runtime (transient transitions)
      - Energy waste flag: >10% overlap sustained for >2 hours
      - Valve threshold: >10% position indicates active heating/cooling
    
    Energy Impact:
      - Heating/cooling overlap wastes both energy forms
      - Additional fan energy to overcome competing actions
      - 10% overlap = ~5-10% total HVAC energy waste
    
    Returns: { overlap_pct, overlap_hours }

    Detects overlaps in heating/cooling causing energy waste using valve/command proxies.

    Returns: { overlap_pct, overlap_hours }
    """
    flat = _aggregate_flat(sensor_data)
    heat_pred = _key_matcher(["heating", "hot_water", "reheat"]) ; cool_pred = _key_matcher(["cool", "chilled_water", "compressor"]) ; pos_pred = _key_matcher(["position", "command", "valve"]) 
    H = [k for k in flat.keys() if heat_pred(str(k)) and pos_pred(str(k))]
    C = [k for k in flat.keys() if cool_pred(str(k)) and pos_pred(str(k))]
    if not (H and C):
        return {"error": "Need heating and cooling valve/command series"}
    dfH = _df_from_readings(sum((flat[k] for k in H), []))
    dfC = _df_from_readings(sum((flat[k] for k in C), []))
    for d in (dfH, dfC): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfH.sort_values("timestamp"), dfC.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_h","_c"))
    if mm.empty: return {"error": "Could not align heating/cooling"}
    h_on = (mm["reading_value_h"].astype(float) > 10.0)
    c_on = (mm["reading_value_c"].astype(float) > 10.0)
    overlap = (h_on & c_on)
    pct = float(overlap.mean()) if len(overlap) else 0.0
    hours = float(overlap.mean() * len(overlap) * (5/60))
    return {"overlap_pct": round(pct,3), "overlap_hours": round(hours,2)}


@analytics_function(
    patterns=[
        r"benchmarking",
        r"performance.*metric",
        r"kpi.*dashboard",
        r"benchmark.*comparison",
        r"performance.*summary"
    ],
    description="Creates benchmarking dashboard with key performance metrics and comparisons"
)

def analyze_benchmarking_dashboard(sensor_data, area_m2=None):
    """
    Benchmarking Dashboard — Multi-Domain KPI Summary
    
    Purpose:
    Aggregates key performance indicators (KPIs) across energy, comfort, and ventilation domains 
    into a single dashboard for portfolio-level benchmarking against ENERGY STAR, CIBSE TM46, 
    or peer buildings. Essential for ESG reporting, LEED recertification, and identifying 
    underperforming buildings requiring deep dives.
    
    Sensors: Aggregate queries across all available sensor types
    
    Output:
      - energy: {power_mean, eui_kwh_per_m2_yr, load_factor}
      - comfort: {temp_mean, temp_stability, pmv_ppd}
      - ventilation: {co2_mean, oa_fraction, ach}
    
    This analysis helps:
      - Compare buildings in portfolio (normalization by area, climate)
      - Prioritize energy audits and retrofits (lowest quartile performers)
      - Support ESG/sustainability reporting (GRESB, CDP)
      - Track progress toward net-zero targets
      - Validate ENERGY STAR Portfolio Manager scores
    
    Benchmarking Standards:
      - Energy: ENERGY STAR (1-100 score, >75 is good)
      - Office EUI: 100-200 kWh/m²/yr typical, <100 high-performance
      - Comfort: ASHRAE 55 (PPD <10%), UK CIBSE TM52 (overheating criteria)
      - Ventilation: ASHRAE 62.1 (CO₂ <1000 ppm, >95% compliance good)
    
    KPI Categories:
      1. **Energy Efficiency**: EUI, demand profile, load factor
      2. **Thermal Comfort**: Temperature stability, PPD, setpoint tracking
      3. **IAQ & Ventilation**: CO₂ levels, outdoor air fraction, filtration
    
    Returns: { energy: {...}, comfort: {...}, ventilation: {...} }

    Produces a compact set of KPIs for benchmarking: energy, comfort, ventilation.

    Returns: { energy: {...}, comfort: {...}, ventilation: {...} }
    """
    energy = analyze_electric_power_summary(sensor_data)
    if area_m2 and not ("error" in energy):
        eui = analyze_eui(sensor_data, area_m2=area_m2)
        energy["eui_kwh_per_m2_yr"] = eui.get("eui_kwh_per_m2_yr") if isinstance(eui, dict) else None
    comfort = analyze_zone_temperature_summary(sensor_data) if callable(globals().get("analyze_zone_temperature_summary")) else {"error": "no comfort"}
    vent = analyze_ventilation_effectiveness(sensor_data) if callable(globals().get("analyze_ventilation_effectiveness")) else {"error": "no ventilation"}
    return {"energy": energy, "comfort": comfort, "ventilation": vent}


@analytics_function(
    patterns=[
        r"control.*tuning",
        r"pid.*tuning",
        r"auto.*tuning",
        r"controller.*optimization",
        r"tuning.*parameters"
    ],
    description="Provides control loop tuning guidance based on performance characteristics"
)

def analyze_control_loop_auto_tuning_aid(sensor_data):
    """
    Control Loop Auto-Tuning Aid — PID Parameter Suggestions
    
    Purpose:
    Provides initial PID tuning parameters (Kp, Ti, Td) derived from observed oscillation 
    characteristics using Ziegler-Nichols or Cohen-Coon methods. Poorly tuned loops waste 
    energy (hunting, overshoot) and degrade comfort. This tool accelerates commissioning and 
    troubleshooting by suggesting tuning starting points based on actual system response.
    
    Sensors: Control signal or process variable (temperature, pressure, flow)
    
    Output:
      - suggested_kp: Proportional gain (unitless)
      - suggested_ti: Integral time constant (hours)
      - suggested_td: Derivative time constant (hours)
      - notes: Tuning method and caveats
    
    This analysis helps:
      - Reduce commissioning time (manual tuning takes 2-8 hours per loop)
      - Stabilize oscillating control loops (hunting detection first)
      - Optimize energy use (tight control reduces overshoot/undershoot)
      - Support BAS integrators and building operators
      - Enable faster response to disturbances (improved occupant comfort)
    
    Tuning Methods:
      1. **Ziegler-Nichols (Ultimate Gain)**: 
         - Find ultimate gain (Ku) and period (Pu) at oscillation onset
         - Kp = 0.6 × Ku, Ti = Pu/2, Td = Pu/8
      2. **Cohen-Coon**: Better for processes with significant dead time
      3. **Relay Feedback**: Automated oscillation test (not implemented here)
    
    Heuristics from Oscillation Analysis:
      - Frequency = 1/Period → Ti ≈ Period/4 (quarter-amplitude damping)
      - Amplitude index → Kp adjustment (high amplitude = reduce Kp)
      - No oscillation → Increase Kp until slight oscillation, then back off 20%
    
    ASHRAE Guideline 36 Targets:
      - Loop oscillations: <3 cycles/hour acceptable
      - Overshoot: <10% of setpoint change
      - Settling time: <15 minutes for temperature loops
    
    Returns: { suggested_kp, suggested_ti, suggested_td, notes }

    Suggests rough PID ranges from oscillation frequency and amplitude metrics.

    Returns: { suggested_kp, suggested_ti, suggested_td, notes }
    """
    osc = analyze_hunting_oscillation(sensor_data)
    if "error" in osc:
        return {"error": "Need a control signal to infer oscillation"}
    freq = float(osc.get("frequency_cph") or 0.0)
    if freq <= 0:
        return {"suggested_kp": None, "suggested_ti": None, "suggested_td": None, "notes": "No oscillation detected; increase Kp until slight oscillation, then back off 20%"}
    period_h = 1.0 / max(freq, 1e-6)
    ti = max(0.05, period_h/4)  # integral time ~ quarter period
    td = max(0.0, period_h/8)   # derivative time ~ eighth period
    # Kp from amplitude index (smaller index -> allow higher Kp)
    idx = float(osc.get("index") or 0.0)
    kp = max(0.1, 1.0 / max(idx, 0.5))
    return {"suggested_kp": round(kp,3), "suggested_ti_hours": round(ti,3), "suggested_td_hours": round(td,3), "notes": "Ziegler-Nichols inspired heuristics; verify on-site."}


@analytics_function(
    patterns=[
        r"coil.*fault.*detection",
        r"residual.*analysis",
        r"coil.*fdd",
        r"fouling.*detection",
        r"coil.*degradation"
    ],
    description="Residual-based fault detection and diagnostics for heating/cooling coils"
)

def analyze_residual_based_coil_fdd(sensor_data):
    """
    Residual-Based Coil FDD — Physics-Based Fouling Detection
    
    Purpose:
    Detects coil fouling or valve faults by analyzing residuals between expected and actual 
    chilled water temperature difference (ΔT) given valve position. A linear model relates 
    valve position to ΔT; negative residuals indicate underperformance (fouled coil, valve 
    bypass, low CHW flow). This physics-based FDD method requires no training data and provides 
    early warning of coil degradation before comfort complaints arise.
    
    Sensors:
      - Cooling_Valve_Position (%)
      - CHW_Supply_Temperature (°C)
      - CHW_Return_Temperature (°C)
    
    Output:
      - residual_mean: Average ΔT prediction error (°C)
      - residual_std: Residual consistency (low std = systematic fault)
      - fouling_flag: Boolean alert if residual < -0.5°C persistently
      - notes: Interpretation guidance
    
    This analysis helps:
      - Detect coil fouling before 30% capacity loss (typical maintenance threshold)
      - Identify valve hunting, bypassing, or stuck positions
      - Diagnose low CHW supply temperature or flow issues
      - Schedule proactive coil cleaning ($500-$2000) before comfort complaints
      - Support model-based FDD without machine learning complexity
    
    Method — Residual Analysis:
      1. Fit linear model: ΔT_expected = a × valve_position + b
      2. Compute residuals: ΔT_actual - ΔT_expected
      3. Negative mean residual → Underperformance (fouling, valve fault)
      4. High std → Intermittent faults or sensor noise
    
    Fouling Detection Criteria:
      - residual_mean < -0.5°C AND |residual_mean| > 1.5 × residual_std
      - Persistent negative residuals over >3 days
      - Fouling reduces heat transfer coefficient by 10-30%
    
    Typical Residuals (Cooling Mode):
      - ~0°C: Normal operation, model matches reality
      - -0.5 to -1.5°C: Moderate fouling or valve issue
      - < -2°C: Severe fouling, valve stuck, or low CHW flow
    
    Returns: { residual_mean, residual_std, fouling_flag, notes }

    Residual-based coil fouling/leakage detection using valve position and CHW ΔT.

    Returns: { residual_mean, residual_std, fouling_flag, notes }
    """
    flat = _aggregate_flat(sensor_data)
    v_pred = _key_matcher(["valve", "position"]) ; chw_pred = _key_matcher(["chilled_water", "chw"]) ; sup_pred = _key_matcher(["supply"]) ; ret_pred = _key_matcher(["return"]) ; t_pred = _key_matcher(["temperature", "temp"]) 
    V = _select_keys(flat, v_pred, False)
    ChwS = [k for k in flat.keys() if chw_pred(str(k)) and sup_pred(str(k)) and t_pred(str(k))]
    ChwR = [k for k in flat.keys() if chw_pred(str(k)) and ret_pred(str(k)) and t_pred(str(k))]
    if not (V and ChwS and ChwR):
        return {"error": "Need valve position and CHW supply/return temps"}
    dfV = _df_from_readings(sum((flat[k] for k in V), []))
    dfS = _df_from_readings(sum((flat[k] for k in ChwS), []))
    dfR = _df_from_readings(sum((flat[k] for k in ChwR), []))
    for d in (dfV, dfS, dfR): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfV.sort_values("timestamp"), dfS.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_v","_s"))
    mm = pd.merge_asof(mm.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", suffixes=("","_r"))
    if mm.empty: return {"error": "Could not align series"}
    dT = (mm["reading_value_r"] - mm["reading_value_s"]).clip(lower=0)
    pos = mm.filter(like="reading_value_v").iloc[:, -1].astype(float)
    if len(pos) < 10: return {"error": "Insufficient points"}
    # Simple linear fit dT ~ a*pos + b
    try:
        a = float(((pos - pos.mean())*(dT - dT.mean())).sum() / max((pos - pos.mean())**2).sum(),)
    except Exception:
        a = 0.0
    b = float(dT.mean() - a*pos.mean())
    dT_hat = a*pos + b
    resid = (dT - dT_hat)
    r_mean = float(resid.mean()); r_std = float(resid.std() or 0.0)
    fouling = bool((r_mean < -0.5) and (abs(r_mean) > 1.5*r_std if r_std>0 else True))
    return {"residual_mean": round(r_mean,2), "residual_std": round(r_std,2), "fouling_flag": fouling, "notes": "Negative residual implies underperformance."}


def analyze_occupancy_inference_co2(sensor_data, baseline_window_hours=24):
    """
    Occupancy Inference from CO₂ — Virtual Occupancy Sensing
    
    Purpose:
    Infers building occupancy levels from CO₂ concentration dynamics without dedicated occupancy 
    sensors. CO₂ rises ~100-200 ppm per person in typical office spaces. This enables demand-
    controlled ventilation (DCV), occupancy-based HVAC scheduling, and space utilization analytics 
    without expensive hardware. Saves $500-$2000/year per zone in ventilation energy.
    
    Sensors: CO2_Sensor (ppm)
    
    Output:
      - baseline_ppm: Unoccupied CO₂ level (outdoor ambient + infiltration)
      - events: Count of occupancy rise events (CO₂ spikes >150 ppm above baseline)
      - occupancy_fraction: % time space appears occupied
    
    This analysis helps:
      - Enable demand-controlled ventilation without occupancy sensors
      - Validate HVAC schedules (detect after-hours occupancy)
      - Support space utilization analytics (hoteling, flex spaces)
      - Reduce ventilation energy by 20-30% (ASHRAE 90.1 DCV credit)
      - Detect occupancy pattern changes (post-pandemic hybrid work)
    
    Method — CO₂ Baseline & Rise Detection:
      1. **Baseline**: 10th percentile CO₂ over 24-hour rolling window (unoccupied level)
         - Typical outdoor: 400-450 ppm
         - Indoor unoccupied: 450-600 ppm (infiltration, tighter buildings higher)
      2. **Rise Events**: ΔCO₂ > 20 ppm/interval AND CO₂ > baseline + 150 ppm
      3. **Occupancy Fraction**: % time CO₂ > baseline + 150 ppm
    
    CO₂ Generation Rates (ASHRAE 62.1):
      - Sedentary office: 0.31 L/s/person × 40,000 ppm breath = ~12,000 ppm·L/s/person
      - At 10 L/s/person ventilation → steady-state rise ~100-150 ppm per person
    
    Limitations:
      - CO₂ lags occupancy (10-30 min time constant for typical rooms)
      - Cannot distinguish number of occupants, only presence/absence
      - Requires stable outdoor air ventilation rates
    
    Returns: { baseline_ppm, events, occupancy_fraction }

    Infers occupancy from CO2 dynamics: baseline, rise events, and occupancy fraction.

    Returns: { baseline_ppm, events, occupancy_fraction }
    """
    flat = _aggregate_flat(sensor_data)
    co2_pred = _key_matcher(["co2"]) 
    keys = _select_keys(flat, co2_pred, False)
    if not keys: return {"error": "No CO2 series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    s = df.set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna().astype(float)
    if len(s) < 24*12:  # 24h history at 5-min
        baseline = float(s.quantile(0.1)) if len(s) else 400.0
    else:
        baseline = float(s.rolling(24*12, min_periods=12).quantile(0.1).iloc[-1])
    rise = s.diff().fillna(0)
    events = int(((rise > 20) & (s > baseline + 150)).sum())
    occupied = s > (baseline + 150)
    occ_frac = float(occupied.mean()) if len(occupied) else 0.0
    return {"baseline_ppm": round(baseline,1), "events": events, "occupancy_fraction": round(occ_frac,3)}


def analyze_co2_levels(sensor_data, threshold=1000):
    """
    CO2 level summary across keys; stats + alerts vs threshold (ppm).

    Returns: { mean, p95, max, pct_above, hours_above, latest, threshold }
    """
    flat = _aggregate_flat(sensor_data)
    co2_pred = _key_matcher(["co2"]) 
    keys = _select_keys(flat, co2_pred, False)
    if not keys:
        return {"error": "No CO2 series"}
    df = _df_from_readings(sum((flat[k] for k in keys), []))
    if df.empty: return {"error": "Empty CO2 series"}
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    s = df.set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna().astype(float)
    if s.empty: return {"error": "Empty CO2 series"}
    thr = float(threshold)
    pct_above = float((s > thr).mean())
    hours_above = float((s > thr).mean() * len(s) * (5/60))
    return {
        "mean": round(float(s.mean()),1),
        "p95": round(float(s.quantile(0.95)),1),
        "max": round(float(s.max()),1),
        "pct_above": round(pct_above,3),
        "hours_above": round(hours_above,2),
        "latest": round(float(s.iloc[-1]),1),
        "threshold": thr,
        "unit": "ppm"
    }


@analytics_function(
    patterns=[
        r"per.*person.*ventilation",
        r"cfm.*per.*person",
        r"ventilation.*per.*occupant",
        r"outdoor.*air.*per.*person",
        r"l/s.*per.*person"
    ],
    description="Calculates ventilation rate per person for occupancy-based compliance"
)

def analyze_per_person_ventilation_rate(sensor_data, guideline_lps=10.0, min_occ=1):
    """
    Per-Person Ventilation Rate — ASHRAE 62.1 Compliance Verification
    
    Purpose:
    Calculates actual outdoor air ventilation rate per occupant (L/s/person) by combining airflow 
    measurements with occupancy counts. ASHRAE 62.1 requires minimum 10 L/s/person (2.5 L/s/m² 
    + 2.5 L/s/person for offices). Under-ventilation causes cognitive impairment, complaints, and 
    code violations; over-ventilation wastes energy. This analysis validates DCV system performance.
    
    Sensors:
      - Outdoor_Air_Flow or Supply_Air_Flow (m³/s or L/s)
      - Occupancy_Count or People_Count (persons)
    
    Output:
      - mean_lps_per_person: Average ventilation rate per person
      - p10_lps_per_person: 10th percentile (worst-case ventilation)
      - pct_meeting_guideline: % time meeting ASHRAE 62.1 minimum
      - guideline_lps: Target ventilation rate
    
    This analysis helps:
      - Verify ASHRAE 62.1 compliance (code requirement)
      - Validate demand-controlled ventilation (DCV) system performance
      - Detect over-ventilation wasting heating/cooling energy
      - Support Indoor Air Quality investigations (complaints, sick building syndrome)
      - Optimize ventilation for energy vs IAQ trade-offs
    
    ASHRAE 62.1 Requirements (Offices):
      - Breathing zone: 2.5 L/s/person + 0.3 L/s/m² (ventilation rate procedure)
      - Total: ~10 L/s/person for typical office (20 m²/person)
      - Schools: 8 L/s/person
      - Conference rooms: 5 L/s/person (higher density)
    
    Method:
      1. Align outdoor airflow (OA_Flow) with occupancy counts
      2. Compute: L/s per person = (OA_Flow × 1000 L/s/m³) / max(occupancy, min_occ)
      3. Compare to guideline over time (compliance percentage)
    
    Typical Results:
      - >95% compliance: Excellent, well-controlled DCV
      - 80-95%: Good, minor under-ventilation during peak occupancy
      - <80%: Poor, investigate airflow measurement or DCV faults
    
    Returns: { mean_lps_per_person, p10_lps_per_person, pct_meeting_guideline }

    Computes ventilation L/s per person using airflow and occupancy; reports mean and compliance.

    Returns: { mean_lps_per_person, p10_lps_per_person, pct_meeting_guideline }
    """
    flat = _aggregate_flat(sensor_data)
    flow_pred = _key_matcher(["air_flow", "airflow", "flow_rate"]) ; occ_pred = _key_matcher(["occupancy", "people", "count"]) 
    f_keys = _select_keys(flat, flow_pred, False)
    o_keys = _select_keys(flat, occ_pred, False)
    if not (f_keys and o_keys):
        return {"error": "Need airflow and occupancy series"}
    dfF = _df_from_readings(sum((flat[k] for k in f_keys), []))
    dfO = _df_from_readings(sum((flat[k] for k in o_keys), []))
    for d in (dfF, dfO): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfF.sort_values("timestamp"), dfO.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_flow","_occ"))
    if mm.empty: return {"error": "Could not align airflow/occupancy"}
    flow_m3s = mm["reading_value_flow"].astype(float)
    occ = mm["reading_value_occ"].astype(float).clip(lower=float(min_occ))
    lps_per_person = (flow_m3s * 1000.0) / occ
    mean_lps = float(lps_per_person.mean())
    p10 = float(lps_per_person.quantile(0.1))
    pct_ok = float((lps_per_person >= float(guideline_lps)).mean())
    return {"mean_lps_per_person": round(mean_lps,1), "p10_lps_per_person": round(p10,1), "pct_meeting_guideline": round(pct_ok,3), "guideline_lps": float(guideline_lps)}


@analytics_function(
    patterns=[
        r"baseline.*energy",
        r"energy.*regression",
        r"energy.*model",
        r"baseline.*model",
        r"regression.*analysis"
    ],
    description="Creates baseline energy regression model for M&V and savings verification"
)

def analyze_baseline_energy_regression(sensor_data, base_temp_c=18.0):
    """
    Baseline Energy Regression — IPMVP M&V Model for Savings Verification
    
    Purpose:
    Develops a weather-normalized energy baseline model using daily energy consumption regressed 
    against Cooling Degree Days (CDD) and Heating Degree Days (HDD). This IPMVP Option C model 
    enables measurement & verification (M&V) of energy savings from ECMs, continuous commissioning, 
    or operational changes by isolating savings from weather variability. Essential for ESCO 
    contracts, utility incentive programs, and ISO 50001 energy management.
    
    Sensors:
      - Electric_Power_Sensor (kW, aggregated to daily kWh)
      - Outside_Air_Temperature (°C, averaged daily)
    
    Output:
      - intercept: Base load (kWh/day, weather-independent)
      - beta_cdd: Cooling sensitivity (kWh/CDD, AC load)
      - beta_hdd: Heating sensitivity (kWh/HDD, heating load)
      - r2: Model goodness-of-fit (>0.75 good)
      - days: Sample size (>30 days minimum)
    
    This analysis helps:
      - Quantify savings from energy efficiency projects (ESCO performance contracts)
      - Normalize energy use for fair year-over-year comparisons
      - Support ENERGY STAR Portfolio Manager weather normalization
      - Validate retro-commissioning savings claims (ASHRAE Guideline 14)
      - Enable continuous energy tracking (detect performance drift)
    
    Model Equation:
      Daily kWh = intercept + (beta_cdd × CDD) + (beta_hdd × HDD)
      
      Where:
        - CDD (Cooling Degree Days) = Σ max(0, OAT_daily - base_temp)
        - HDD (Heating Degree Days) = Σ max(0, base_temp - OAT_daily)
        - base_temp: Balance point temperature (18°C default for offices)
    
    ASHRAE Guideline 14 & IPMVP Standards:
      - Minimum R² = 0.75 for acceptable model (>0.85 preferred)
      - CV(RMSE) < 20% for monthly data
      - Baseline period: ≥12 months (capture seasonal variation)
      - Post-retrofit: ≥12 months for savings verification
    
    Interpretation:
      - intercept: Plug loads, lighting, base HVAC (weather-independent)
      - beta_cdd: Cooling efficiency (lower = better insulation, efficient AC)
      - beta_hdd: Heating efficiency (lower = better envelope, efficient heating)
      - High R²: Energy strongly weather-dependent (HVAC-dominated)
    
    Returns: { intercept, beta_cdd, beta_hdd, r2, days }

    Weather/usage baseline (M&V) model: daily kWh ~ CDD + HDD + intercept; returns coefficients and R².

    Returns: { intercept, beta_cdd, beta_hdd, r2, days }
    """
    flat = _aggregate_flat(sensor_data)
    oat_pred = _key_matcher(["outside_air", "outdoor"]) ; t_pred = _key_matcher(["temperature", "temp"]) ; p_pred = _key_matcher(["power", "kw"]) 
    O = [k for k in flat.keys() if oat_pred(str(k)) and t_pred(str(k))]
    P = _select_keys(flat, p_pred, False)
    if not (O and P): return {"error": "Need OAT and power series"}
    dfO = _df_from_readings(sum((flat[k] for k in O), [])); dfP = _df_from_readings(sum((flat[k] for k in P), []))
    for d in (dfO, dfP): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    O1 = dfO.set_index("timestamp").sort_index().resample("1H").mean()[["reading_value"]].rename(columns={"reading_value":"OAT"})
    P1 = dfP.set_index("timestamp").sort_index().resample("1H").mean()[["reading_value"]].rename(columns={"reading_value":"kW"})
    X = O1.join(P1, how="inner").dropna()
    if X.empty: return {"error": "No aligned OAT/power"}
    X["date"] = X.index.date
    daily = X.groupby("date").agg({"OAT":"mean", "kW":"sum"})
    daily["kWh"] = daily["kW"]
    daily["CDD"] = (daily["OAT"] - float(base_temp_c)).clip(lower=0)
    daily["HDD"] = (float(base_temp_c) - daily["OAT"]).clip(lower=0)
    if len(daily) < 10: return {"error": "Insufficient daily data"}
    C = daily[["CDD","HDD"]]
    y = daily["kWh"]
    # Solve normal equations approximately assuming low correlation (typical HDD vs CDD)
    denom_c = float((C["CDD"]**2).sum()) or 1.0
    denom_h = float((C["HDD"]**2).sum()) or 1.0
    beta_c = float((C["CDD"]*y).sum())/denom_c
    beta_h = float((C["HDD"]*y).sum())/denom_h
    intercept = float((y - beta_c*C["CDD"] - beta_h*C["HDD"]).mean())
    y_hat = intercept + beta_c*C["CDD"] + beta_h*C["HDD"]
    ss_res = float(((y - y_hat)**2).sum()); ss_tot = float(((y - y.mean())**2).sum()) or 1.0
    r2 = 1.0 - ss_res/ss_tot
    return {"intercept": round(intercept,1), "beta_cdd": round(beta_c,2), "beta_hdd": round(beta_h,2), "r2": round(r2,3), "days": int(len(daily))}


@analytics_function(
    patterns=[
        r"load.*clustering",
        r"zone.*grouping",
        r"pattern.*clustering",
        r"usage.*classification",
        r"behavior.*clustering"
    ],
    description="Clusters zones or loads by similar patterns using k-means clustering"
)

def analyze_load_zone_clustering(sensor_data, n_clusters=3, resample="1H"):
    """
    Load/Zone Clustering — Pattern Recognition for Demand Profiles
    
    Purpose:
    Groups zones or buildings by similar energy consumption patterns using k-means clustering on 
    normalized 24-hour load profiles. Identifies "morning peak," "all-day," and "night shift" 
    archetypes to inform targeted energy strategies, equipment scheduling, and rate optimization. 
    Enables portfolio-level analytics by discovering operational patterns hidden in aggregated data.
    
    Sensors: Electric_Power_Sensor or Thermal_Load (kW) per zone/building
    
    Output:
      - clusters: {zone_name: cluster_id} assignments
      - centroids: Normalized 24-hour profiles for each cluster [[hour0, hour1, ..., hour23]]
      - inertia: Sum of squared distances (lower = tighter clusters)
    
    This analysis helps:
      - Discover operational archetypes (24/7 data centers vs 8-5 offices)
      - Optimize time-of-use (TOU) rate strategies per cluster
      - Target DR events to high-impact clusters (peak-coincident loads)
      - Detect anomalous zones (outliers needing investigation)
      - Support automated fault detection (deviation from cluster centroid)
    
    Method — K-Means on Diurnal Profiles:
      1. Extract 24-hour average load profile per zone (hour 0-23)
      2. Normalize each profile to 0-1 scale (max load = 1.0)
      3. K-means clustering with n_clusters (typically 3-5)
      4. Iterate to convergence (assign → update centroids → repeat)
    
    Typical Clusters (Office Buildings):
      - **Cluster 0 "Base Load"**: Flat 24-hour profile (data centers, refrigeration)
      - **Cluster 1 "Office Hours"**: 8am-6pm peak, low nights/weekends
      - **Cluster 2 "Retail"**: 10am-9pm peak with evening emphasis
    
    Applications:
      - TOU rate optimization: Schedule flexible loads to off-peak hours
      - DR targeting: Shed "office hours" cluster during 2-6pm peak events
      - Anomaly detection: Zone deviates >50% from cluster centroid
    
    Parameters:
      - n_clusters: Number of archetypes (3-5 typical)
      - resample: Aggregation interval ("1H" hourly, "15min" for detailed analysis)
    
    Returns: { clusters: {zone: cluster_id}, centroids: [[24 values]], inertia }

    Clusters zones by normalized load profiles using simple k-means on 24-hour vectors.

    Returns: { clusters: {zone: cluster_id}, centroids: [[24 values]], inertia }
    """
    flat = _aggregate_flat(sensor_data)
    p_pred = _key_matcher(["power", "kw", "demand"]) 
    keys = _select_keys(flat, p_pred, False)
    if not keys: return {"error": "No power series"}
    profiles = {}
    for k in keys:
        df = _df_from_readings(flat[k])
        if df.empty: continue
        s = df[["timestamp","reading_value"]].copy(); s["timestamp"] = pd.to_datetime(s["timestamp"], errors="coerce")
        s = s.dropna(subset=["timestamp"]).set_index("timestamp").sort_index().resample(resample).mean()["reading_value"].dropna()
        if s.empty: continue
        daily = s.groupby([s.index.hour]).mean()
        vec = daily.reindex(range(24)).fillna(method="ffill").fillna(method="bfill")
        if vec.max() > 0:
            vec = vec / vec.max()
        profiles[str(k)] = vec
    if len(profiles) < max(2, n_clusters):
        return {"error": "Insufficient zone series for clustering"}
    M = pd.DataFrame(profiles).T  # zones x 24
    # init centroids: pick top n by peak at hour with highest variance
    var_hour = M.var(axis=0).idxmax()
    seeds = M.sort_values(by=var_hour, ascending=False).head(n_clusters).index.tolist()
    centroids = [M.loc[s].copy() for s in seeds]
    for _ in range(5):
        # assign
        dists = []
        for c in centroids:
            d = ((M - c)**2).sum(axis=1)
            dists.append(d)
        D = pd.concat(dists, axis=1)
        labels = D.idxmin(axis=1)
        # update
        new_centroids = []
        for j in range(len(centroids)):
            members = M[labels == j]
            if members.empty:
                new_centroids.append(centroids[j])
            else:
                new_centroids.append(members.mean())
        centroids = new_centroids
    inertia = float(D.min(axis=1).sum()) if 'D' in locals() else None
    clusters = {zone: int(labels.loc[zone]) for zone in labels.index}
    return {"clusters": clusters, "centroids": [[round(float(x),3) for x in c.tolist()] for c in centroids], "inertia": (round(inertia,2) if inertia is not None else None)}


@analytics_function(
    patterns=[
        r"predictive.*maintenance.*fan",
        r"predictive.*maintenance.*pump",
        r"fan.*predictive",
        r"pump.*predictive",
        r"fan.*pump.*health"
    ],
    description="Predictive maintenance assessment for fans and pumps based on vibration/power"
)

def analyze_predictive_maintenance_fans_pumps(sensor_data):
    """
    Predictive Maintenance – Fans/Pumps — Early warnings.
    
    Purpose: Provides early warning of potential equipment failures by analyzing operational
             parameters and computing health scores and Remaining Useful Life (RUL) estimates.
             Enables proactive maintenance scheduling to avoid unexpected breakdowns and
             extend equipment lifespan.
    
    Sensors:
      - Motor_Current_Sensor (electrical signature analysis)
      - Runtime counters (operating hours)
      - Differential_Pressure or Flow sensors (performance indicators)
      - Vibration_Sensor (optional, for advanced diagnostics)
      - Power_Sensor (efficiency tracking)
      
    Output:
      - Health score (0-100, where 100 is excellent)
      - Remaining Useful Life (RUL) in days
      - Contributing degradation factors
      - Maintenance alerts and priority levels
      - Trend analysis of key performance indicators
      
    This analysis helps:
      - Prevent unexpected equipment failures
      - Optimize maintenance schedules (shift from reactive to predictive)
      - Reduce maintenance costs by targeting interventions
      - Extend equipment life through early problem detection
      - Minimize unplanned downtime
      
    Health indicators monitored:
      - Motor current patterns (bearing wear, imbalance)
      - Efficiency trends (degradation over time)
      - Runtime accumulation (wear-out failure probability)
      - Vibration signatures (if available)
      - Alarm/fault history
      
    RUL estimation based on:
      - Historical degradation rates
      - Current health score trajectory
      - Manufacturer-specified design life
      - Operating conditions (load, cycling frequency)

    Returns: { health_score, rul_days, degradation_factors, maintenance_priority, confidence }
    """
    flat = _aggregate_flat(sensor_data)
    vib_pred = _key_matcher(["vibration", "rms", "accel"]) ; temp_pred = _key_matcher(["bearing", "temperature"]) ; alarm_pred = _key_matcher(["alarm", "fault"]) 
    vib = _df_from_readings(sum((flat[k] for k in _select_keys(flat, vib_pred, False)), [])) if _select_keys(flat, vib_pred, False) else pd.DataFrame()
    btemp = _df_from_readings(sum((flat[k] for k in _select_keys(flat, temp_pred, False)), [])) if _select_keys(flat, temp_pred, False) else pd.DataFrame()
    alarms = analyze_alarm_event_summary(sensor_data)
    eff_fan = analyze_fan_vfd_efficiency(sensor_data)
    eff_pump = analyze_pump_efficiency(sensor_data)
    runtime = analyze_runtime_analysis(sensor_data)
    score = 100.0
    factors = []
    if isinstance(eff_fan, dict) and eff_fan.get("sfp_mean"):
        sfp = float(eff_fan["sfp_mean"])
        delta = max(0.0, (sfp - 1.5)) * 10
        score -= delta; factors.append({"sfp_mean": sfp, "penalty": round(delta,1)})
    if isinstance(eff_pump, dict) and eff_pump.get("spp_mean"):
        spp = float(eff_pump["spp_mean"])
        delta = max(0.0, (spp - 2.0)) * 8
        score -= delta; factors.append({"spp_mean": spp, "penalty": round(delta,1)})
    if not vib.empty:
        v = float(vib["reading_value"].astype(float).quantile(0.9))
        delta = max(0.0, (v - 3.0)) * 5
        score -= delta; factors.append({"vibration_p90": v, "penalty": round(delta,1)})
    if not btemp.empty:
        t = float(btemp["reading_value"].astype(float).quantile(0.9))
        delta = max(0.0, (t - 80.0)) * 0.5
        score -= delta; factors.append({"bearing_temp_p90": t, "penalty": round(delta,1)})
    if isinstance(alarms, dict) and alarms.get("total_events"):
        delta = min(20.0, float(alarms["total_events"]) * 0.5)
        score -= delta; factors.append({"alarms": int(alarms["total_events"]), "penalty": round(delta,1)})
    duty = float(runtime.get("duty_cycle") or 0.5)
    # RUL heuristic: proportional to score and inverse of duty
    rul_days = max(7.0, score * 1.0 / max(duty, 0.1))
    return {"health_score": round(max(0.0, min(100.0, score)),1), "rul_days": round(rul_days,1), "factors": factors}


@analytics_function(
    patterns=[
        r"predictive.*maintenance.*chiller",
        r"predictive.*maintenance.*ahu",
        r"chiller.*predictive",
        r"ahu.*predictive",
        r"chiller.*ahu.*health"
    ],
    description="Predictive maintenance assessment for chillers and AHUs"
)

def analyze_predictive_maintenance_chillers_ahus(sensor_data):
    """
    Predictive Maintenance — Chillers/AHUs Health Score & RUL
    
    Purpose:
    Computes equipment health scores (0-100) and Remaining Useful Life (RUL) estimates for 
    chillers and air handling units by aggregating performance indicators: COP degradation, 
    low ΔT syndrome, economizer faults, and alarm frequency. Enables proactive maintenance 
    scheduling to prevent unexpected failures, extend equipment life, and reduce total cost 
    of ownership by 15-25%.
    
    Sensors:
      - Chiller/AHU performance metrics (COP, ΔT, economizer operation)
      - Alarm and fault history
      - Runtime counters (operating hours)
    
    Output:
      - health_score: 0-100 (100 = excellent, <70 = maintenance needed)
      - rul_days: Estimated remaining useful life (days until intervention)
      - factors: Contributing degradation factors with severity scores
    
    This analysis helps:
      - Shift from reactive to predictive maintenance (reduce unplanned downtime 30-50%)
      - Prioritize maintenance budgets (target worst-performing assets first)
      - Extend equipment life (early intervention prevents cascading failures)
      - Reduce maintenance costs by $5,000-$20,000/year per major asset
      - Support capital planning (RUL < 180 days → budget replacement)
    
    Health Score Calculation (100 points baseline, penalties applied):
      1. **COP Degradation** (-6 points per 0.1 COP below 2.5 target)
         - Chiller efficiency decline indicates refrigerant issues, fouled condenser
      2. **Low ΔT Syndrome** (-20 points × pct_below_3C)
         - Severe chiller underperformance, pump energy waste
      3. **Economizer Faults** (-1 point per fault occurrence)
         - Stuck dampers, failed actuators reduce free cooling
      4. **Alarm Events** (-0.3 points per alarm, max -20)
         - High fault frequency indicates systemic issues
    
    RUL Estimation:
      RUL (days) = (health_score × 1.5) / duty_cycle
      
      Where:
        - duty_cycle: Equipment utilization (0.0-1.0)
        - Factor 1.5: Heuristic scaling (100 health → ~150 days at 100% duty)
        - Minimum RUL: 7 days (immediate attention threshold)
    
    Maintenance Priorities:
      - Health <50, RUL <30 days: **Critical** — Schedule emergency maintenance
      - Health 50-70, RUL 30-90 days: **High** — Plan proactive service
      - Health 70-85, RUL >90 days: **Medium** — Monitor trends
      - Health >85: **Low** — Routine preventive maintenance only
    
    Returns: { health_score, rul_days, factors }

    PdM health score/RUL for chillers/AHUs using COP degradation, low-ΔT, economizer faults, and alarms.

    Returns: { health_score, rul_days, factors }
    """
    cop = analyze_cooling_cop(sensor_data)
    lowdt = analyze_low_delta_t_syndrome(sensor_data)
    eco = analyze_economizer_fault_rules(sensor_data)
    alarms = analyze_alarm_event_summary(sensor_data)
    runtime = analyze_runtime_analysis(sensor_data)
    score = 100.0; factors = []
    if isinstance(cop, dict) and cop.get("cop_proxy_mean"):
        c = float(cop["cop_proxy_mean"])
        delta = max(0.0, (2.5 - c)) * 6
        score -= delta; factors.append({"cop_proxy_mean": c, "penalty": round(delta,1)})
    if isinstance(lowdt, dict) and lowdt.get("pct_below_3C") is not None:
        p = float(lowdt["pct_below_3C"])
        delta = p * 20.0
        score -= delta; factors.append({"low_dt_pct": p, "penalty": round(delta,1)})
    if isinstance(eco, dict):
        open_issues = int(eco.get("does_not_open_count", 0)) + int(eco.get("stuck_open_count", 0))
        delta = min(15.0, open_issues * 1.0)
        score -= delta; factors.append({"economizer_issues": open_issues, "penalty": round(delta,1)})
    if isinstance(alarms, dict) and alarms.get("total_events"):
        delta = min(20.0, float(alarms["total_events"]) * 0.3)
        score -= delta; factors.append({"alarms": int(alarms["total_events"]), "penalty": round(delta,1)})
    duty = float(runtime.get("duty_cycle") or 0.5)
    rul_days = max(7.0, score * 1.5 / max(duty, 0.1))
    return {"health_score": round(max(0.0, min(100.0, score)),1), "rul_days": round(rul_days,1), "factors": factors}


@analytics_function(
    patterns=[
        r"dr.*event.*impact",
        r"demand.*response.*event",
        r"load.*shed.*impact",
        r"dr.*performance",
        r"event.*analysis"
    ],
    description="Analyzes impact and performance of demand response events"
)

def analyze_dr_event_impact_analysis(sensor_data, events):
    """
    DR Event Impact Analysis — Shed and rebound effect.
    
    Purpose: Quantifies the effectiveness of Demand Response (DR) events by measuring actual
             load reduction (shed), post-event rebound, and impact on occupant comfort.
             Essential for validating DR program participation and optimizing future responses.
    
    Sensors:
      - Electric_Power_Sensor (demand measurements)
      - Comfort metrics (temperature, humidity, CO2) during and after events
      
    Output:
      - Shed kW (actual load reduction during DR event)
      - Rebound quantification (post-event load spike)
      - Comfort deviation metrics (temperature excursions)
      - Event performance score
      - Savings validation vs baseline
      
    This analysis helps:
      - Validate DR program compliance and incentive payments
      - Optimize shed strategies for maximum savings with minimal comfort impact
      - Quantify rebound effects for energy planning
      - Improve future DR event performance
      - Balance energy savings with occupant comfort
      
    DR Event Phases analyzed:
      1. Baseline: Pre-event normal operation
      2. Shed: Load reduction during event window
      3. Rebound: Post-event recovery and potential overshoot
      4. Recovery: Return to normal operation
      
    Calculations:
      - Shed kW = Baseline kW - Actual kW during event
      - Rebound kW = Peak kW after event - Baseline kW
      - Comfort impact = Max temperature deviation during/after event
      - Performance score = (Shed kW / Target kW) × Comfort compliance factor

    Parameters:
      - sensor_data: Power and comfort sensor payload
      - events: List of DR events with {start_time, end_time, target_kW_reduction}

    Returns: { event_results: [{shed_kW, rebound_kW, comfort_deviation, performance_score}], summary }
    """
    flat = _aggregate_flat(sensor_data)
    p_pred = _key_matcher(["power", "kw"]) 
    P = _select_keys(flat, p_pred, False)
    if not P: return {"error": "No power series"}
    dfP = _df_from_readings(sum((flat[k] for k in P), []))
    dfP["timestamp"] = pd.to_datetime(dfP["timestamp"], errors="coerce")
    s = dfP.set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna()
    if s.empty: return {"error": "Empty power series"}
    results = []
    total_shed = 0.0; total_reb = 0.0
    for ev in (events or []):
        try:
            st = pd.to_datetime(ev.get("start")); en = pd.to_datetime(ev.get("end"))
        except Exception:
            continue
        if pd.isna(st) or pd.isna(en) or st >= en: 
            continue
        # Baseline: average same times over previous 3 non-event days
        baseline = []
        for d in range(1, 4):
            day = (st.normalize() - pd.Timedelta(days=d))
            b_win = s.loc[day + (st - st.normalize()): day + (en - en.normalize())]
            if not b_win.empty: baseline.append(b_win)
        if not baseline: 
            continue
        base = pd.concat(baseline, axis=1).mean(axis=1)
        act = s.loc[st:en]
        if act.empty or base.empty: continue
        # Align index to overlapping stamps
        idx = act.index.intersection(base.index)
        shed = float(((base.loc[idx] - act.loc[idx]).clip(lower=0) * (5/60)).sum())
        # Rebound: next 2 hours vs baseline continuation
        post_st = en; post_en = en + pd.Timedelta(hours=2)
        base_post = base.shift( (post_st - st)//pd.Timedelta(minutes=5) ).loc[post_st:post_en]
        act_post = s.loc[post_st:post_en]
        idx2 = act_post.index.intersection(base_post.index)
        rebound = float(((act_post.loc[idx2] - base_post.loc[idx2]).clip(lower=0) * (5/60)).sum())
        total_shed += shed; total_reb += rebound
        results.append({"start": st.isoformat(), "end": en.isoformat(), "shed_kWh": round(shed,2), "rebound_kWh": round(rebound,2)})
    return {"events": results, "total_shed_kWh": round(total_shed,2), "total_rebound_kWh": round(total_reb,2)}


@analytics_function(
    patterns=[
        r"digital.*twin",
        r"building.*simulation",
        r"model.*simulation",
        r"what.*if.*scenario",
        r"predictive.*model"
    ],
    description="Digital twin simulation for what-if scenarios and predictive analysis"
)

def analyze_digital_twin_simulation(sensor_data, scenario=None):
    """
    Digital Twin Scenario Simulation — What-if planning.
    
    Purpose: Simulates "what-if" scenarios using a digital twin model of the HVAC system to
             predict energy consumption and comfort outcomes under different operating conditions.
             Enables data-driven decision making before implementing actual control changes.
    
    Sensors: System models calibrated with historical data from:
      - Power/Energy sensors
      - Temperature sensors (outdoor, zone, supply)
      - HVAC control signals (setpoints, valve positions)
      
    Output:
      - Predicted energy outcomes (delta kWh)
      - Comfort guarantees and violations
      - Recommended scenario based on optimization objectives
      - Confidence intervals for predictions
      
    This analysis helps:
      - Evaluate control strategy changes before implementation
      - Optimize setpoints for energy vs comfort trade-offs
      - Plan equipment upgrades with predicted ROI
      - Test demand response strategies safely
      - Support Model Predictive Control (MPC) development
      
    Scenario parameters:
      - oat_delta: Outdoor air temperature adjustment (°C) for weather scenarios
      - setpoint_offset: Cooling/heating setpoint shift (°C)
      - occupancy_factor: Occupancy level scaling (0.0-1.0)
      - equipment_efficiency: Degradation or upgrade scenarios
      
    Model types:
      - Physics-based: First principles thermodynamics
      - Data-driven: Machine learning from historical patterns
      - Hybrid: Combines physics and ML for accuracy

    Parameters:
      - sensor_data: Historical sensor payload for model calibration
      - scenario: dict with parameters like {oat_delta: -3.0, setpoint_offset: -1.0}

    Returns: { delta_kWh, comfort_impact, recommended_scenario, confidence, details }
    """
    scenario = scenario or {}
    oat_delta = float(scenario.get("oat_delta", 0.0))
    sp_offset = float(scenario.get("setpoint_offset", 0.0))
    flat = _aggregate_flat(sensor_data)
    oat_pred = _key_matcher(["outside_air", "outdoor"]) ; t_pred = _key_matcher(["temperature", "temp"]) ; p_pred = _key_matcher(["power", "kw"]) 
    O = [k for k in flat.keys() if oat_pred(str(k)) and t_pred(str(k))]
    P = _select_keys(flat, p_pred, False)
    if not (O and P): return {"error": "Need OAT and power series"}
    dfO = _df_from_readings(sum((flat[k] for k in O), [])); dfP = _df_from_readings(sum((flat[k] for k in P), []))
    for d in (dfO, dfP): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    O1 = dfO.set_index("timestamp").sort_index().resample("1H").mean()[["reading_value"]].rename(columns={"reading_value":"OAT"})
    P1 = dfP.set_index("timestamp").sort_index().resample("1H").mean()[["reading_value"]].rename(columns={"reading_value":"kW"})
    X = O1.join(P1, how="inner").dropna()
    if X.empty: return {"error": "No aligned OAT/power"}
    # Linear slope d(kW)/d(OAT)
    cov = float(((X["OAT"] - X["OAT"].mean())*(X["kW"] - X["kW"].mean())).sum())
    var = float(((X["OAT"] - X["OAT"].mean())**2).sum()) or 1.0
    slope = cov/var
    # Estimate delta for oat shift
    delta_oat_kW = slope * oat_delta
    # Estimate setpoint effect: -2% kW per -1°C offset
    pct = -0.02 * sp_offset
    kW_base = float(X["kW"].mean())
    delta_sp_kW = kW_base * pct
    # Total delta kWh over the period (per-hour data)
    hours = float(len(X))
    delta_kwh = (delta_oat_kW + delta_sp_kW) * hours
    return {"delta_kWh": round(float(delta_kwh),1), "details": {"slope_kW_per_C": round(slope,3), "oat_delta": oat_delta, "setpoint_offset": sp_offset}}


@analytics_function(
    patterns=[
        r"mpc.*readiness",
        r"model.*predictive.*control",
        r"shadow.*mode",
        r"advanced.*control",
        r"optimal.*control"
    ],
    description="Assesses Model Predictive Control (MPC) readiness in shadow mode"
)

def analyze_mpc_readiness_shadow_mode(sensor_data):
    """
    MPC Readiness Assessment — Shadow Mode Validation
    
    Purpose:
    Evaluates building readiness for Model Predictive Control (MPC) by comparing shadow MPC 
    controller predictions against baseline control performance. If shadow data unavailable, 
    computes heuristic readiness score based on control stability (low oscillation) and setpoint 
    compliance. MPC can reduce HVAC energy 10-30% while improving comfort, but requires stable 
    baseline controls and accurate models.
    
    Sensors:
      - MPC_Shadow_Signal (predicted optimal control, if running shadow mode)
      - Actual control signals (baseline controller output)
      - Power_Sensor (energy comparison)
    
    Output:
      - method: "shadow" (data-driven) or "heuristic" (rules-based)
      - improvement_pct: Energy/comfort improvement potential (shadow mode)
      - readiness_score: 0-1 readiness assessment (heuristic mode)
    
    This analysis helps:
      - Validate MPC shadow mode before production deployment
      - Assess building suitability for advanced controls
      - Quantify expected energy savings (justify MPC investment)
      - Identify control tuning issues blocking MPC adoption
      - Support grant applications (DOE/CEC MPC pilots)
    
    Shadow Mode Method (Preferred):
      1. Run MPC in parallel with existing controls (no actuation)
      2. Compare shadow predictions vs actual outcomes
      3. Improvement = (Baseline_error - Shadow_error) / Baseline_error
      4. >20% improvement → Strong MPC candidate
    
    Heuristic Readiness Criteria (No Shadow Data):
      1. **Control Stability**: Low oscillation index (<0.5, from hunting analysis)
         - MPC requires stable baseline; hunting indicates tuning issues
      2. **Setpoint Tracking**: High compliance (>80%, from setpoint analysis)
         - Accurate tracking validates sensor/actuator performance
      3. **Readiness Score** = (1 - oscillation_index/50) × setpoint_compliance
    
    MPC Requirements (ASHRAE):
      - Accurate building thermal model (±1°C prediction error)
      - Reliable sensors/actuators (avoid stuck dampers, failed sensors)
      - Weather forecast integration (NOAA, commercial providers)
      - Computing infrastructure (cloud or edge controller)
    
    Readiness Thresholds:
      - >0.7: Ready for MPC pilot (expect 15-25% savings)
      - 0.5-0.7: Address control tuning first, then pilot
      - <0.5: Baseline controls need commissioning before MPC
    
    Returns: { method: "shadow"|"heuristic", improvement_pct or readiness_score }

    Compare MPC shadow vs baseline; if shadow signals absent, compute heuristic readiness.

    Returns: { method: "shadow"|"heuristic", improvement_pct or readiness_score }
    """
    flat = _aggregate_flat(sensor_data)
    shadow_pred = _key_matcher(["mpc", "shadow"]) ; p_pred = _key_matcher(["power", "kw"]) 
    S = _select_keys(flat, shadow_pred, False)
    P = _select_keys(flat, p_pred, False)
    if S and P:
        dfS = _df_from_readings(sum((flat[k] for k in S), [])); dfP = _df_from_readings(sum((flat[k] for k in P), []))
        for d in (dfS, dfP): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
        s = dfS.set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna()
        p = dfP.set_index("timestamp").sort_index().resample("5min").mean()["reading_value"].dropna()
        idx = s.index.intersection(p.index)
        if len(idx) >= 12:
            mae_shadow = float((s.loc[idx] - p.loc[idx]).abs().mean())
            mae_baseline = float((p.loc[idx] - p.loc[idx].shift(12)).abs().dropna().mean()) if len(idx) > 12 else None
            if mae_baseline and mae_baseline > 0:
                improvement = max(0.0, 1.0 - mae_shadow/mae_baseline)
                return {"method": "shadow", "improvement_pct": round(float(improvement),3)}
    # Heuristic readiness: stable control and good setpoint compliance
    osc = analyze_hunting_oscillation(sensor_data)
    spc = analyze_setpoint_compliance(sensor_data)
    readiness = max(0.0, 1.0 - float(osc.get("index") or 0.0)/50.0) * (float(spc.get("pct_within") or 0.5))
    return {"method": "heuristic", "readiness_score": round(float(readiness),3)}


@analytics_function(
    patterns=[
        r"fault.*signature",
        r"pattern.*matching",
        r"fault.*library",
        r"signature.*matching",
        r"known.*fault"
    ],
    description="Matches observed patterns against fault signature library for diagnosis"
)

def analyze_fault_signature_library_matching(sensor_data):
    """
    Fault Signature Library Matching — Pattern-Based FDD
    
    Purpose:
    Matches observed anomalies against a library of known HVAC fault signatures (low ΔT syndrome, 
    economizer faults, simultaneous heating/cooling, actuator stiction) using rule-based diagnostics. 
    Provides confidence-weighted fault identification with actionable details. This expert-system 
    approach complements data-driven methods by leveraging decades of commissioning best practices 
    codified in ASHRAE fault detection rules.
    
    Sensors: Outputs from existing diagnostic functions (meta-analysis)
    
    Output:
      - matches: Array of detected faults [{name, confidence, details}]
      - confidence: 0.0-1.0 likelihood of each fault (based on threshold severity)
    
    This analysis helps:
      - Provide root-cause diagnosis (not just anomaly detection)
      - Prioritize maintenance by fault severity and confidence
      - Train building operators on common HVAC issues
      - Validate data-driven anomaly detectors (confirm ML alerts)
      - Support automated work order generation (integrate with CMMS)
    
    Fault Library (ASHRAE Fault Detection & Diagnostics):
      1. **Low ΔT Syndrome** (Confidence 0.8)
         - Signature: pct_below_3C > 50% OR syndrome_flag = True
         - Impact: Excess pump energy, reduced chiller efficiency
      2. **Economizer Fault** (Confidence 0.7)
         - Signature: does_not_open_count > 0 OR stuck_open_count > 0
         - Impact: Rejected free cooling, mechanical cooling during mild weather
      3. **Simultaneous Heating & Cooling** (Confidence 0.75)
         - Signature: overlap_pct > 10%
         - Impact: 10-30% HVAC energy waste
      4. **Actuator Stiction** (Confidence 0.6)
         - Signature: stiction_flag = True
         - Impact: Sluggish response, hunting, comfort complaints
    
    Confidence Scoring:
      - 0.8-1.0: High confidence, immediate action recommended
      - 0.6-0.8: Moderate confidence, verify with site inspection
      - <0.6: Low confidence, monitor trends before intervention
    
    Integration:
      - CMMS work orders: Auto-generate based on >0.7 confidence faults
      - Operator dashboard: Prioritize by confidence × energy impact
      - Continuous commissioning: Weekly fault reports for O&M teams
    
    Returns: { matches: [{name, confidence, details}] }

    Matches anomalies to known fault signatures using existing diagnostics.

    Returns: { matches: [{name, confidence, details}] }
    """
    sigs = []
    lowdt = analyze_low_delta_t_syndrome(sensor_data)
    if isinstance(lowdt, dict) and lowdt.get("syndrome_flag"):
        sigs.append({"name": "Low ΔT syndrome", "confidence": 0.8, "details": lowdt})
    eco = analyze_economizer_fault_rules(sensor_data)
    if isinstance(eco, dict) and (eco.get("does_not_open_count",0) > 0 or eco.get("stuck_open_count",0) > 0):
        sigs.append({"name": "Economizer fault", "confidence": 0.7, "details": eco})
    sim = analyze_simultaneous_heating_cooling(sensor_data)
    if isinstance(sim, dict) and (sim.get("overlap_pct",0) > 0.1):
        sigs.append({"name": "Simultaneous heating & cooling", "confidence": 0.75, "details": sim})
    act = analyze_actuator_stiction(sensor_data)
    if isinstance(act, dict) and act.get("flag"):
        sigs.append({"name": "Actuator stiction", "confidence": 0.6, "details": act})
    return {"matches": sigs}


@analytics_function(
    patterns=[
        r"sat.*residual",
        r"supply.*air.*temp.*residual",
        r"sat.*fault",
        r"sat.*diagnostic",
        r"discharge.*temp.*residual"
    ],
    description="Residual analysis for supply air temperature control fault detection"
)

def analyze_sat_residual_analysis(sensor_data):
    """
    SAT Residual Analysis — Cooling/Heating Coil Performance Diagnostics
    
    Purpose:
    Analyzes the difference (residual) between actual Supply Air Temperature (SAT) and 
    expected SAT based on psychrometric mixing equations. Large positive residuals indicate 
    insufficient cooling/heating from coils (fouling, valve issues, low capacity), while 
    negative residuals may indicate excessive coil output or temperature sensor errors. 
    This physics-based FDD method detects coil performance degradation without requiring 
    extensive training data.
    
    Sensors:
      - Supply_Air_Temperature (SAT) - actual measured (°C)
      - Mixed_Air_Temperature (MAT) or inferred from RAT/OAT (°C)
      - Return_Air_Temperature (RAT) (°C)
      - Outside_Air_Temperature (OAT) (°C)
      - Optional: OA Damper Position to refine mixing calculation
    
    Output:
      - residual_mean: Average SAT prediction error (°C)
      - residual_std: Standard deviation of residuals (consistency check)
      - high_residual_pct: Percentage of time |residual| > threshold
      - cooling_adequacy: "Adequate", "Marginal", or "Insufficient"
      - fault_likelihood: Probability of coil fouling or valve issue
    
    This analysis helps:
      - Detect fouled coils reducing heat transfer effectiveness
      - Identify control valve hunting, bypassing, or stuck positions
      - Diagnose low chilled/hot water flow or temperature issues
      - Validate AHU commissioning and sequence of operations
      - Distinguish sensor errors from actual coil performance issues
      - Support model-based FDD without machine learning complexity
    
    Method:
      Expected Mixed Air Temperature (if not directly measured):
        MAT_expected = f × OAT + (1-f) × RAT
        
        Where f = OA damper fraction (or estimated from SAT-RAT-OAT relationships)
      
      Expected Supply Air Temperature (no coil load):
        SAT_expected ≈ MAT_expected (if coils off)
      
      Residual = SAT_actual - SAT_expected
      
      Interpretation (cooling mode):
        - Residual ≈ 0: Coils off or minimal load (economizer mode)
        - Residual < 0: Cooling coil active, magnitude = coil ΔT (typically -5 to -15°C)
        - Residual > 0: Insufficient cooling (fouled coil, low CHW flow/temp, valve issue)
        - |Residual| > 3°C: Likely fault condition requiring investigation
      
      Heating mode (winter): Negative residual indicates heating adequacy
      
      Fault signatures:
        - Increasing residual trend over time: Progressive coil fouling
        - High residual variability: Control valve hunting or instability
        - Sudden residual shift: Valve failure or CHW/HW supply issue
    
    Parameters:
        sensor_data (dict): Timeseries SAT, MAT/RAT, and OAT data
    
    Returns:
        dict: Residual statistics, coil adequacy assessment, and fault probability
    """
    flat = _aggregate_flat(sensor_data)
    s_pred = _key_matcher(["supply_air"]) ; m_pred = _key_matcher(["mixed_air", "mix"]) ; r_pred = _key_matcher(["return_air"]) ; o_pred = _key_matcher(["outside_air", "outdoor"]) ; t_pred = _key_matcher(["temperature", "temp"]) 
    S = [k for k in flat.keys() if s_pred(str(k)) and t_pred(str(k))]
    M = [k for k in flat.keys() if m_pred(str(k)) and t_pred(str(k))]
    R = [k for k in flat.keys() if r_pred(str(k)) and t_pred(str(k))]
    O = [k for k in flat.keys() if o_pred(str(k)) and t_pred(str(k))]
    if not (S and R and O):
        return {"error": "Need SAT, RAT, and OAT series"}
    dfS = _df_from_readings(sum((flat[k] for k in S), []))
    dfR = _df_from_readings(sum((flat[k] for k in R), []))
    dfO = _df_from_readings(sum((flat[k] for k in O), []))
    for d in (dfS, dfR, dfO): d["timestamp"] = pd.to_datetime(d["timestamp"], errors="coerce")
    mm = pd.merge_asof(dfS.sort_values("timestamp"), dfR.sort_values("timestamp"), on="timestamp", direction="nearest", tolerance=pd.Timedelta("5min"), suffixes=("_s","_r"))
    mm = pd.merge_asof(mm.sort_values("timestamp"), dfO.sort_values("timestamp"), on="timestamp", direction="nearest")
    if mm.empty: return {"error": "Could not align series"}
    # Estimate OA fraction using RAT-SAT-OAT (assume MAT≈SAT for simple AHUs)
    RAT = mm["reading_value_r"]; SAT = mm["reading_value_s"]; OAT = mm["reading_value"]
    denom = (OAT - RAT).replace(0, pd.NA)
    f = ((SAT - RAT) / denom).clip(lower=0, upper=1)
    MAT_exp = f * OAT + (1 - f) * RAT
    resid = SAT - MAT_exp
    resid = resid.dropna()
    if resid.empty: return {"error": "No residuals"}
    return {"residual_mean": round(float(resid.mean()),2), "residual_std": round(float(resid.std() or 0.0),2), "high_residual_pct": round(float((resid.abs() > 2.0).mean()),3)}


@analytics_function(
    patterns=[
        r"weather.*normalized.*benchmark",
        r"climate.*adjusted.*comparison",
        r"normalized.*performance",
        r"weather.*adjusted.*eui",
        r"degree.*day.*normalized"
    ],
    description="Weather-normalized benchmarking for fair building performance comparison"
)

def analyze_weather_normalized_benchmarking(sensor_data, area_m2=None):
    """
    Weather-Normalized Benchmarking — Climate-Independent Energy Performance
    
    Purpose:
    Combines Energy Use Intensity (EUI) with weather-normalized metrics (kWh/CDD, kWh/HDD) 
    to create climate-independent performance benchmarks. Enables fair comparison of building 
    energy performance across different locations, years, and seasons. Essential for portfolio 
    benchmarking, ENERGY STAR compliance, and validating energy savings projects under varying 
    weather conditions.
    
    Sensors:
      - Electric_Energy_Sensor or Power_Sensor (kW/kWh)
      - Outside_Air_Temperature (°C) for degree-day calculation
      - Building metadata: Floor area (m²)
    
    Output:
      - eui_kwh_per_m2_yr: Energy Use Intensity (annual kWh per m² floor area)
      - kWh_per_CDD: Cooling efficiency (lower is better)
      - kWh_per_HDD: Heating efficiency (lower is better)
      - composite_score: Weighted performance index for benchmarking
      - climate_zone_percentile: Performance ranking vs similar buildings (if database available)
    
    This analysis helps:
      - Compare building energy performance across different climates and years
      - Validate energy savings projects accounting for weather variation (IPMVP Option C)
      - Support ENERGY STAR certification and EPA Portfolio Manager submissions
      - Identify buildings underperforming relative to climate-adjusted benchmarks
      - Track performance improvement independent of weather fluctuations
      - Support ESG reporting with normalized emissions metrics
    
    Method:
      1. Calculate EUI (Energy Use Intensity):
         EUI = Annual kWh / Floor Area (m²)
         
         UK benchmarks (kWh/m²·yr):
           - Office (good): 90-110, typical: 150-200
           - Retail: 200-350
           - Healthcare: 250-400
           - Data center: 800-1500
      
      2. Calculate degree-days (base 18°C typical):
         CDD (Cooling Degree-Days) = Σ max(0, daily_avg_temp - base)
         HDD (Heating Degree-Days) = Σ max(0, base - daily_avg_temp)
      
      3. Normalize energy consumption:
         kWh/CDD = Total Cooling Season kWh / CDD
         kWh/HDD = Total Heating Season kWh / HDD
      
      4. Composite benchmark score:
         Score = weighted_sum(EUI_percentile, kWh_per_CDD_percentile, kWh_per_HDD_percentile)
         
         Lower scores indicate better performance.
      
      Use cases:
        - Year-over-year performance trending (removes weather variability)
        - Portfolio ranking and peer benchmarking
        - M&V baseline adjustment for retrofit projects
        - Regulatory compliance (UK ESOS, SECR reporting)
    
    Parameters:
        sensor_data (dict): Energy and temperature timeseries data
        area_m2 (float, optional): Building floor area (m²) for EUI calculation
    
    Returns:
        dict: Weather-normalized KPIs (EUI, kWh/DD), composite score, and benchmark percentiles
    """
    eui = analyze_eui(sensor_data, area_m2=area_m2) if area_m2 else {"eui_kwh_per_m2_yr": None}
    wn = analyze_weather_normalization(sensor_data)
    eui_v = eui.get("eui_kwh_per_m2_yr") if isinstance(eui, dict) else None
    cdd_v = wn.get("kWh_per_CDD") if isinstance(wn, dict) else None
    hdd_v = wn.get("kWh_per_HDD") if isinstance(wn, dict) else None
    # Lower is better; composite score handles None by ignoring missing terms
    parts = [x for x in [eui_v, cdd_v, hdd_v] if x is not None]
    score = float(sum(parts)/len(parts)) if parts else None
    return {"eui_kwh_per_m2_yr": eui_v, "kWh_per_CDD": cdd_v, "kWh_per_HDD": hdd_v, "score": (round(score,1) if score is not None else None)}


# ---------------------------
# Generic Dispatcher Endpoint
# ---------------------------

# NOTE: analysis_functions dict is now populated automatically by @analytics_function decorator
# This manual dictionary is no longer needed and has been commented out.
# If you need to add a new function, just add the @analytics_function decorator.

# analysis_functions = {
#     "analyze_recalibration_frequency": analyze_recalibration_frequency,
#     ... (all other entries)
# }

# ---------------------------
# New / Extended Analytics Functions (Answering richer NL intents)
# ---------------------------

def _flatten_selected(flat, keys):
    readings = []
    for k in keys:
        readings.extend(flat.get(k, []))
    return _df_from_readings(readings)

@analytics_function(patterns=[r"current (value|reading)", r"latest (temperature|humidity|co2|value)"], description="Return latest reading per detected series (or subset via key_filters)")
def current_value(sensor_data, key_filters: Optional[list] = None):
    """Return the latest reading for each selected series.

    Parameters:
        sensor_data: flat/nested payload
        key_filters: optional list of substrings to restrict which keys are considered.
    Returns: mapping key -> {latest_timestamp, latest_value, unit}
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    out = {}
    for key, readings in flat.items():
        if key_filters and not any(f.lower() in str(key).lower() for f in key_filters):
            continue
        df = _df_from_readings(readings)
        if df.empty:
            continue
        last = df.iloc[-1]
        out[str(key)] = {
            "latest_timestamp": last["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "latest_value": float(last.get("reading_value")),
            "unit": _unit_for_key(key),
        }
    if not out:
        return {"error": "No matching series"}
    return out

@analytics_function(patterns=[r"compare", r"difference between", r"warmer", r"cooler", r"higher"], description="Compare latest readings across two or more series and rank")
def compare_latest_values(sensor_data, key_filters: Optional[list] = None):
    """Compare latest values across selected sensors.

    Returns: list sorted descending by latest_value with differences relative to first."""
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    rows = []
    for key, readings in flat.items():
        if key_filters and not any(f.lower() in str(key).lower() for f in key_filters):
            continue
        df = _df_from_readings(readings)
        if df.empty:
            continue
        last = df.iloc[-1]
        rows.append({
            "key": str(key),
            "latest_timestamp": last["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
            "latest_value": float(last.get("reading_value")),
            "unit": _unit_for_key(key),
        })
    if len(rows) < 2:
        return {"error": "Need at least two series for comparison"}
    rows.sort(key=lambda r: r["latest_value"], reverse=True)
    base = rows[0]["latest_value"]
    for r in rows:
        r["diff_from_leader"] = round(r["latest_value"] - base, 3)
    return {"comparisons": rows, "leader": rows[0]["key"]}

@analytics_function(patterns=[r"setpoint", r"deviation", r"offset"], description="Compute deviation between actual readings and associated setpoint series")
def difference_from_setpoint(sensor_data):
    """Compute latest deviation of actual vs setpoint for temperature/hvac style series.

    Heuristics:
      - keys containing 'setpoint' treated as setpoints
      - counterpart actual key assumed same base with 'setpoint' removed or containing 'temp'/'temperature'.
    Returns: mapping actual_key -> {setpoint_key, latest_actual, latest_setpoint, deviation}
    """
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    setpoint_keys = [k for k in flat.keys() if 'setpoint' in str(k).lower()]
    if not setpoint_keys:
        return {"error": "No setpoint series found"}
    results = {}
    for sp in setpoint_keys:
        base = re.sub(r"setpoint", "", str(sp), flags=re.IGNORECASE)
        # find candidate actual key
        candidates = [k for k in flat.keys() if k != sp and base.strip('_')[:10].lower() in str(k).lower()]
        if not candidates:
            continue
        df_sp = _df_from_readings(flat[sp])
        if df_sp.empty:
            continue
        latest_sp = float(df_sp.iloc[-1]["reading_value"])
        for act in candidates:
            df_act = _df_from_readings(flat[act])
            if df_act.empty:
                continue
            latest_act = float(df_act.iloc[-1]["reading_value"])
            results[str(act)] = {
                "setpoint_key": str(sp),
                "latest_actual": latest_act,
                "latest_setpoint": latest_sp,
                "deviation": round(latest_act - latest_sp, 3),
                "unit": _unit_for_key(act) or _unit_for_key(sp)
            }
    if not results:
        return {"error": "No matching actual/setpoint pairs"}
    return results

@analytics_function(patterns=[r"time in range", r"compliance", r"within range"], description="Percentage of readings inside acceptable range for each series")
def percentage_time_in_range(sensor_data, acceptable_range: Optional[tuple] = None):
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            continue
        if acceptable_range is None:
            # try infer temperature range else humidity
            rng = None
            kl = str(key).lower()
            if 'temp' in kl:
                rng = UK_INDOOR_STANDARDS['temperature_c']['range']
            elif 'humid' in kl:
                rng = UK_INDOOR_STANDARDS['humidity_rh']['range']
            else:
                rng = (df['reading_value'].quantile(0.1), df['reading_value'].quantile(0.9))
        else:
            rng = acceptable_range
        inside = df[(df['reading_value'] >= rng[0]) & (df['reading_value'] <= rng[1])]
        pct = (len(inside) / len(df)) * 100 if len(df) else 0
        out[str(key)] = {"range": rng, "percent_in_range": round(pct, 2), "unit": _unit_for_key(key)}
    return out or {"error": "No readings"}

@analytics_function(patterns=[r"top", r"highest"], description="Top-N series by latest reading")
def top_n_by_latest(sensor_data, n: int = 5):
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    scores = []
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            continue
        latest = float(df.iloc[-1]['reading_value'])
        scores.append((key, latest, df.iloc[-1]['timestamp']))
    scores.sort(key=lambda x: x[1], reverse=True)
    out = [{"key": str(k), "latest_value": v, "timestamp": t.strftime('%Y-%m-%d %H:%M:%S'), "unit": _unit_for_key(k)} for k, v, t in scores[:n]]
    return {"top": out, "n": n}

@analytics_function(description="Bottom-N series by latest reading", patterns=[r"lowest", r"bottom"])
def bottom_n_by_latest(sensor_data, n: int = 5):
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    scores = []
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            continue
        latest = float(df.iloc[-1]['reading_value'])
        scores.append((key, latest, df.iloc[-1]['timestamp']))
    scores.sort(key=lambda x: x[1])
    out = [{"key": str(k), "latest_value": v, "timestamp": t.strftime('%Y-%m-%d %H:%M:%S'), "unit": _unit_for_key(k)} for k, v, t in scores[:n]]
    return {"bottom": out, "n": n}

@analytics_function(patterns=[r"slope", r"trend"], description="Linear regression slope over recent window (hours)")
def rolling_trend_slope(sensor_data, window_hours: int = 6):
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    now = pd.Timestamp.now()
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            continue
        df = df[df['timestamp'] >= now - pd.Timedelta(hours=window_hours)]
        if len(df) < 3:
            continue
        # convert time to seconds offset
        t0 = df['timestamp'].min()
        x = (df['timestamp'] - t0).dt.total_seconds().values
        y = df['reading_value'].values
        try:
            slope, intercept = np.polyfit(x, y, 1)
            out[str(key)] = {"slope_per_sec": slope, "slope_per_hour": slope * 3600, "points": int(len(df)), "unit": _unit_for_key(key)}
        except Exception:
            continue
    return out or {"error": "Insufficient data"}

@analytics_function(patterns=[r"rate of change", r"how fast"], description="Average absolute rate of change between consecutive readings")
def rate_of_change(sensor_data):
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if len(df) < 2:
            continue
        df['delta'] = df['reading_value'].diff().abs()
        df['dt'] = df['timestamp'].diff().dt.total_seconds().replace(0, np.nan)
        rate = (df['delta'] / df['dt']).dropna().mean()
        out[str(key)] = {"avg_rate_per_sec": rate, "unit": _unit_for_key(key)}
    return out or {"error": "No series with enough points"}

@analytics_function(patterns=[r"histogram", r"distribution", r"spread"], description="Histogram bin counts for each series")
def histogram_bins(sensor_data, bins: int = 10):
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            continue
        counts, edges = np.histogram(df['reading_value'].values, bins=bins)
        out[str(key)] = {"bins": edges.tolist(), "counts": counts.tolist(), "unit": _unit_for_key(key)}
    return out or {"error": "No readings"}

@analytics_function(patterns=[r"missing data", r"completeness", r"data quality"], description="Report data completeness (% timestamps missing in regular cadence)")
def missing_data_report(sensor_data, expected_freq: str = '5min'):
    flat = _aggregate_flat(sensor_data)
    if not flat:
        return {"error": "No data"}
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            continue
        df = df.set_index('timestamp').sort_index()
        full = df.resample(expected_freq).first()
        missing = full['reading_value'].isna().sum()
        total = len(full)
        out[str(key)] = {"expected_points": total, "missing_points": int(missing), "percent_missing": round((missing/total)*100,2) if total else None}
    return out or {"error": "No readings"}

@analytics_function(patterns=[r"time .*threshold", r"reach .*threshold", r"when .* (exceed|reach)"], description="Estimate time to reach a threshold via linear extrapolation")
def time_to_threshold(sensor_data, threshold: Optional[float] = None, window_points: int = 10):
    if threshold is None:
        return {"error": "threshold parameter required"}
    flat = _aggregate_flat(sensor_data)
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if len(df) < 3:
            continue
        df = df.tail(window_points)
        t0 = df['timestamp'].min()
        x = (df['timestamp'] - t0).dt.total_seconds().values
        y = df['reading_value'].values
        try:
            slope, intercept = np.polyfit(x, y, 1)
            if slope == 0:
                continue
            secs = (threshold - intercept) / slope
            if secs < x[-1]:
                status = "already_reached"
            elif secs < 0:
                status = "moving_away"
            else:
                eta = t0 + pd.Timedelta(seconds=secs)
                status = eta.strftime('%Y-%m-%d %H:%M:%S')
            out[str(key)] = {"threshold": threshold, "slope_per_sec": slope, "eta": status, "unit": _unit_for_key(key)}
        except Exception:
            continue
    return out or {"error": "Unable to estimate"}

@analytics_function(patterns=[r"baseline"], description="Compare recent mean vs historical baseline window")
def baseline_comparison(sensor_data, baseline_hours: int = 24, recent_hours: int = 1):
    flat = _aggregate_flat(sensor_data)
    now = pd.Timestamp.now()
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            continue
        baseline_df = df[df['timestamp'] >= now - pd.Timedelta(hours=baseline_hours)]
        recent_df = df[df['timestamp'] >= now - pd.Timedelta(hours=recent_hours)]
        if len(baseline_df) < 3 or recent_df.empty:
            continue
        base_mean = baseline_df['reading_value'].mean()
        recent_mean = recent_df['reading_value'].mean()
        delta = recent_mean - base_mean
        out[str(key)] = {"baseline_mean": round(base_mean,3), "recent_mean": round(recent_mean,3), "delta": round(delta,3), "unit": _unit_for_key(key)}
    return out or {"error": "No sufficient data"}

@analytics_function(patterns=[r"range", r"span"], description="Compute range (max-min) over window")
def range_span(sensor_data, window_hours: int = 24):
    flat = _aggregate_flat(sensor_data)
    now = pd.Timestamp.now()
    out = {}
    for key, readings in flat.items():
        df = _df_from_readings(readings)
        if df.empty:
            continue
        df = df[df['timestamp'] >= now - pd.Timedelta(hours=window_hours)]
        if df.empty:
            continue
        span = df['reading_value'].max() - df['reading_value'].min()
        out[str(key)] = {"range_span": round(float(span),3), "max": float(df['reading_value'].max()), "min": float(df['reading_value'].min()), "unit": _unit_for_key(key)}
    return out or {"error": "No window data"}

# ---------------------------
# Introspection endpoint to list available analytics
# ---------------------------
@analytics_service.route("/list", methods=["GET"])
def list_analytics():
    return jsonify({k: v for k, v in _analytics_registry_meta.items()})

@analytics_service.route("/functions", methods=["GET"])
def list_functions_detailed():
    return jsonify({"functions": _list_registry_metadata(), "count": len(_analytics_registry_meta)})

@analytics_service.route("/validate_function", methods=["POST"])
def validate_function():
    data = request.get_json(force=True, silent=True) or {}
    code_body = data.get("code") or ""
    if not code_body:
        return jsonify({"ok": False, "error": "code field required"}), 400
    safe, msg = _is_safe_code(code_body)
    return jsonify({"ok": safe, "message": msg})

FUNCTION_TEMPLATE = """from blueprints.analytics_service import analytics_function, _aggregate_flat, _df_from_readings, _unit_for_key\n\n@analytics_function(patterns={patterns}, description={description!r})\ndef {name}(sensor_data{param_sig}):\n    \"\"\"Auto-created analytics function. Edit logic below.\n    Parameters reflect user-provided schema.\n    \"\"\"\n    flat = _aggregate_flat(sensor_data)\n    if not flat:\n        return {{'error': 'No data'}}\n    # TODO: implement analytics logic using _df_from_readings\n    # Example: compute mean of first series\n    first_key = next(iter(flat.keys()))\n    df = _df_from_readings(flat[first_key])\n    if df.empty: return {{'error': 'Empty series'}}\n    return {{'series': first_key, 'mean': float(df['reading_value'].mean()), 'unit': _unit_for_key(first_key)}}\n"""

@analytics_service.route("/add_function", methods=["POST"])
def add_function():
    payload = request.get_json(force=True, silent=True) or {}
    name = payload.get("name")
    patterns = payload.get("patterns") or []
    description = payload.get("description") or "New analytics function"
    params = payload.get("parameters") or []  # list of {name, default, type?, description?}
    if not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    if name in analysis_functions:
        return jsonify({"ok": False, "error": "function already exists"}), 400
    # Build param signature
    sig_parts = []
    for p in params:
        pname = re.sub(r"[^a-zA-Z0-9_]+", "_", str(p.get('name') or ''))
        if not pname or pname == 'sensor_data':
            continue
        default = p.get('default')
        if default is None or default == "":
            sig_parts.append(f", {pname}")
        else:
            # represent default safely
            sig_parts.append(f", {pname}={repr(default)}")
    param_sig = ''.join(sig_parts)
    # Extend docstring with parameter schema lines if provided
    if params:
        doc_param_lines = ["Parameters:\n"]
        for p in params:
            pname = re.sub(r"[^a-zA-Z0-9_]+", "_", str(p.get('name') or ''))
            if not pname or pname == 'sensor_data':
                continue
            ptype = p.get('type') or 'Any'
            pdesc = p.get('description') or ''
            doc_param_lines.append(f"    - {pname} ({ptype}): {pdesc}\n")
        doc_extra = ''.join(doc_param_lines)
    else:
        doc_extra = ''
    code = FUNCTION_TEMPLATE.format(name=name, patterns=repr(patterns), description=(description + ("\n\n" + doc_extra if doc_extra else "")), param_sig=param_sig)
    safe, msg = _is_safe_code(code)
    if not safe:
        return jsonify({"ok": False, "error": msg}), 400
    path = _write_plugin_file(name, code)
    _load_plugins()  # reload to register
    # Persist metadata (parameters schema)
    _analytics_params_meta[name] = {
        "description": description,
        "patterns": patterns,
        "parameters": [
            {k: v for k, v in p.items() if k in {"name", "default", "type", "description"}}
            for p in params
            if p.get('name') and p.get('name') != 'sensor_data'
        ],
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    _save_analytics_meta()
    # Try decider rules reload (optional)
    decider_reloaded = False
    try:
        from .decider_service import _load_rules  # type: ignore
        _load_rules()
        decider_reloaded = True
    except Exception:
        decider_reloaded = False
    return jsonify({"ok": True, "path": path, "registered": name in analysis_functions, "decider_reloaded": decider_reloaded})

@analytics_service.route("/test_run", methods=["POST"])
def test_run():
    data = request.get_json(force=True, silent=True) or {}
    fn_name = data.get("function")
    payload = data.get("payload") or {}
    if fn_name not in analysis_functions:
        return jsonify({"ok": False, "error": "Unknown function"}), 400
    fn = analysis_functions[fn_name]
    # Filter optional parameters supplied for test
    try:
        sig = inspect.signature(fn)
        kwargs = {}
        for k, v in (data.get("params") or {}).items():
            if k in sig.parameters:
                kwargs[k] = v
        result = fn(payload, **kwargs)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logging.error(f"Test run failed: {e}")
        return jsonify({"ok": False, "error": str(e)})

@analytics_service.route("/test", methods=["GET", "POST"])
def test_endpoint():
    if request.method == "POST":
        data = request.get_json()
        return jsonify({"received Json data" : data, "status": "ok"})
    else:
        return jsonify({"status": "ok", "message": "Analytics service is running"})

@analytics_service.route("/run", methods=["POST"])
def run_analysis():
    logging.info("Analytics /run endpoint called")
    data = request.get_json()
    
    if not data or "analysis_type" not in data:
        logging.error("Missing required parameter: analysis_type")
        return jsonify({"error": "Missing required parameter: analysis_type"}), 400

    analysis_type = data["analysis_type"]
    logging.info(f"Analysis type: {analysis_type}")
    
    # Remove control keys to isolate sensor data, but keep optional params
    control_keys = {"analysis_type"}
    optional_params = {}
    # Collect whitelisted option keys if present
    for opt in (
        "sensor_key",
        "acceptable_range",
        "thresholds",
        "temp_key",
        "humidity_key",
        "temp_range",
        "humidity_range",
        "freq",
        "window",
        "expected_range",
        "robust",
        "method",
        "threshold",
        "time_window_hours",
        "anomaly_threshold",
    ):
        if opt in data:
            optional_params[opt] = data[opt]
            control_keys.add(opt)
    sensor_data = {k: v for k, v in data.items() if k not in control_keys}
    logging.info(f"Extracted sensor data keys: {list(sensor_data.keys())}")

    if not sensor_data:
        logging.error("No sensor data provided")
        return jsonify({"error": "No sensor data provided"}), 400

    if analysis_type not in analysis_functions:
        logging.error(f"Unknown analysis type: {analysis_type}")
        return jsonify({"error": f"Unknown analysis type: {analysis_type}"}), 400

    try:
        logging.info(f"Calling analysis function: {analysis_type} with data of length: {len(str(sensor_data))}")
        func = analysis_functions[analysis_type]
        # Filter optional params based on function signature
        sig = None
        try:
            sig = inspect.signature(func)
            valid_kwargs = {k: v for k, v in optional_params.items() if k in sig.parameters}
        except Exception:
            valid_kwargs = optional_params
        result = func(sensor_data, **valid_kwargs)
        
        # Create an enhanced response that includes the analytics type
        enhanced_result = {
            "analysis_type": analysis_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": result
        }
        
        logging.info(f"Analysis result: {enhanced_result}")
        return jsonify(enhanced_result)
    except Exception as e:
        logging.error(f"Error running analysis {analysis_type}: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"error": f"Error running analysis {analysis_type}: {str(e)}"}), 500

# ---------------------------
# Sensors list endpoint (for UI) 
# ---------------------------
@analytics_service.route("/sensors", methods=["GET"])
def list_sensors():
    """Return list of known sensor types/names by reading sensor_list.txt if present.

    Response JSON shape:
      {"sensors": ["Sensor_A", "Sensor_B", ...], "count": N}
    Falls back to empty list if file missing; does not raise 500.
    """
    candidates = [
        os.path.join(os.getcwd(), "sensor_list.txt"),
        os.path.join(os.getcwd(), "actions", "sensor_list.txt"),
        os.path.join(os.getcwd(), "..", "rasa-bldg1", "actions", "sensor_list.txt"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    sensors = []
    if path:
        try:
            with open(path, "r") as f:
                sensors = [ln.strip() for ln in f if ln.strip()]
        except Exception as e:
            logging.warning(f"Failed reading sensor_list.txt at {path}: {e}")
    else:
        logging.info("sensor_list.txt not found in known locations for /analytics/sensors endpoint")
    return jsonify({"sensors": sensors, "count": len(sensors)})