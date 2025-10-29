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
        return {"error": "No noise data available"}

    noise_pred = _key_matcher(["noise", "sound"])
    keys = _select_keys(flat, noise_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {"error": "No noise-like keys found"}

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {"error": "Empty noise series"}

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    summary = {
        "mean": float(df["reading_value"].mean()),
        "min": float(df["reading_value"].min()),
        "max": float(df["reading_value"].max()),
        "std": float(df["reading_value"].std()),
        "latest": latest,
        "unit": UK_INDOOR_STANDARDS["noise_db"]["unit"],
        "acceptable_max": threshold,
    }
    if latest is not None:
        summary["alert"] = (
            "High noise level" if latest > threshold else "Normal noise level"
        )
    else:
        summary["alert"] = "No readings"
    return summary


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
        return {"error": "No air quality data available"}

    aq_pred = _key_matcher(["air_quality", "aqi", "aq_sensor"])  # broad match
    keys = _select_keys(flat, aq_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {"error": "No air-quality-like keys found"}

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {"error": "Empty air quality series"}

    avg_quality = float(df["reading_value"].mean())
    if avg_quality <= thresholds[0]:
        status = "Good"
    elif avg_quality <= thresholds[1]:
        status = "Moderate"
    else:
        status = "Poor"
    return {
        "average_air_quality": avg_quality,
        "status": status,
        "min": float(df["reading_value"].min()),
        "max": float(df["reading_value"].max()),
        "unit": None,  # AQI is unitless if this is an arbitrary index
        "thresholds": {"good_max": thresholds[0], "moderate_max": thresholds[1]},
    }


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
        return {"error": "No formaldehyde data available"}

    hcho_pred = _key_matcher(["formaldehyde", "hcho"])  # common naming
    keys = _select_keys(flat, hcho_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {"error": "No formaldehyde-like keys found"}

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {"error": "Empty formaldehyde series"}

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    if threshold is None:
        threshold = UK_INDOOR_STANDARDS["hcho_mgm3"]["max"]
    summary = {
        "mean": float(df["reading_value"].mean()),
        "min": float(df["reading_value"].min()),
        "max": float(df["reading_value"].max()),
        "std": float(df["reading_value"].std()),
        "latest": latest,
        "unit": UK_INDOOR_STANDARDS["hcho_mgm3"]["unit"],
        "acceptable_max": threshold,
    }
    if latest is not None:
        summary["alert"] = (
            "High formaldehyde level"
            if latest > threshold
            else "Normal formaldehyde level"
        )
    else:
        summary["alert"] = "No readings"
    return summary


def analyze_co2_levels(sensor_data, threshold=None):
    """
    Analyzes CO2 sensor readings from a nested JSON structure.

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
        return {"error": "No CO2 data available"}

    co2_pred = _key_matcher(["co2"])  # specific enough
    keys = _select_keys(flat, co2_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {"error": "No CO2-like keys found"}

    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {"error": "Empty CO2 series"}

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    # Default threshold per UK guidance
    if threshold is None:
        threshold = UK_INDOOR_STANDARDS["co2_ppm"]["range"][1]
    summary = {
        "mean": float(df["reading_value"].mean()),
        "min": float(df["reading_value"].min()),
        "max": float(df["reading_value"].max()),
        "std": float(df["reading_value"].std()),
        "latest": latest,
        "unit": UK_INDOOR_STANDARDS["co2_ppm"]["unit"],
        "acceptable_max": threshold,
    }
    if latest is not None:
        summary["alert"] = (
            "High CO2 level" if latest > threshold else "Normal CO2 level"
        )
    else:
        summary["alert"] = "No readings"
    return summary


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
        return {"error": "No PM data available"}

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

    analysis = {}
    for pm_type, keys in pm_groups.items():
        if not keys:
            continue
        all_readings = []
        for k in keys:
            all_readings.extend(flat.get(k, []))
        df = _df_from_readings(all_readings)
        if df.empty:
            analysis[pm_type] = {"error": "No data available"}
            continue
        latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
        unit = UK_INDOOR_STANDARDS["pm10_ugm3"]["unit"] if pm_type == "pm10" else UK_INDOOR_STANDARDS["pm2.5_ugm3"]["unit"] if pm_type.startswith("pm2") else UK_INDOOR_STANDARDS["pm2.5_ugm3"]["unit"]
        summary = {
            "mean": float(df["reading_value"].mean()),
            "min": float(df["reading_value"].min()),
            "max": float(df["reading_value"].max()),
            "std": float(df["reading_value"].std()),
            "latest": latest,
            "unit": unit,
        }
        thres = None
        # choose threshold key variant
        for key_variant in [pm_type, pm_type.replace(".", "_"), pm_type.replace(".", "")]:
            if key_variant in thresholds:
                thres = thresholds[key_variant]
                break
        if latest is not None and thres is not None:
            summary["alert"] = (
                f"High {pm_type} reading" if latest > thres else f"Normal {pm_type} reading"
            )
            summary["threshold"] = {"value": thres, "unit": unit}
        elif thres is None:
            summary["alert"] = "Threshold not defined"
        else:
            summary["alert"] = "No readings"
        analysis[pm_type] = summary
    if not analysis:
        return {"error": "No PM-like keys found"}
    return analysis


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
        return {"error": "No temperature data available"}

    # Exclude accidental matches like 'attempt' when looking for temperature series
    temp_pred = _key_matcher(["temperature", "temp"], exclude_substrs=["attempt"])  # avoid matching 'attempt'
    keys = _select_keys(flat, temp_pred, fallback_to_all=(len(flat) == 1))
    if not keys:
        return {"error": "No temperature-like keys found"}

    # Combine all selected series
    all_readings = []
    for k in keys:
        all_readings.extend(flat.get(k, []))
    df = _df_from_readings(all_readings)
    if df.empty:
        return {"error": "Empty temperature series"}

    latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
    # Default to UK comfort range if not provided
    if acceptable_range is None:
        acceptable_range = UK_INDOOR_STANDARDS["temperature_c"]["range"]
    unit = "°C"
    summary = {
        "mean": float(df["reading_value"].mean()),
        "min": float(df["reading_value"].min()),
        "max": float(df["reading_value"].max()),
        "std": float(df["reading_value"].std()),
        "latest": latest,
        "unit": unit,
        "acceptable_range": {"min": acceptable_range[0], "max": acceptable_range[1], "unit": unit},
    }
    if latest is not None:
        summary["alert"] = (
            "Temperature out of range"
            if (latest < acceptable_range[0] or latest > acceptable_range[1])
            else "Temperature normal"
        )
    else:
        summary["alert"] = "No readings"
    return summary


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
    # Parse sensor_data if provided as a JSON string.
    if isinstance(sensor_data, str):
        try:
            sensor_data = json.loads(sensor_data)
        except Exception as e:
            logging.error(f"Error parsing sensor_data JSON: {e}")
            return {"error": "Invalid sensor_data JSON"}

    # Helper to detect humidity-like keys
    def is_humidity_key(key: str) -> bool:
        try:
            k = key.lower()
        except Exception:
            return False
        return ("humidity" in k) or (k == "rh") or ("relative_humidity" in k)

    aggregated_readings = []

    # If the payload is a flat mapping: {name_or_uuid: [ {datetime, reading_value}, ... ]}
    if isinstance(sensor_data, dict) and sensor_data and all(
        isinstance(v, list) for v in sensor_data.values()
    ):
        # Prefer humidity-like keys; else if one key, use it; else aggregate all keys
        keys_to_use = [k for k in sensor_data.keys() if is_humidity_key(str(k))]
        if not keys_to_use:
            if len(sensor_data) == 1:
                keys_to_use = list(sensor_data.keys())
            else:
                # Fall back to all keys if ambiguous
                keys_to_use = list(sensor_data.keys())
        for k in keys_to_use:
            readings = sensor_data.get(k, [])
            if isinstance(readings, list):
                aggregated_readings.extend(readings)

    # Else, expect nested mapping: { group_id: { inner_key: { timeseries_data: [...] } } }
    elif isinstance(sensor_data, dict):
        for group_id, inner in sensor_data.items():
            if not isinstance(inner, dict):
                # If inner is a list, treat as direct readings for this group
                if isinstance(inner, list):
                    aggregated_readings.extend(inner)
                continue

            # Determine which inner keys to use for this group
            selected_keys = [k for k in inner.keys() if is_humidity_key(str(k))]
            if not selected_keys:
                if len(inner) == 1:
                    selected_keys = list(inner.keys())
                else:
                    # Choose key(s) with max number of readings; if empty, use all
                    lengths = []
                    for k, v in inner.items():
                        if isinstance(v, dict):
                            readings = v.get("timeseries_data", [])
                        elif isinstance(v, list):
                            readings = v
                        else:
                            readings = []
                        lengths.append((k, len(readings)))
                    if lengths:
                        max_len = max(l for _, l in lengths)
                        selected_keys = [k for k, l in lengths if l == max_len]
                    else:
                        selected_keys = list(inner.keys())

            for k in selected_keys:
                info = inner.get(k)
                if isinstance(info, dict):
                    aggregated_readings.extend(info.get("timeseries_data", []))
                elif isinstance(info, list):
                    aggregated_readings.extend(info)

    # If sensor_data is already a list of readings
    elif isinstance(sensor_data, list):
        aggregated_readings = sensor_data

    if not aggregated_readings:
        # Give a clearer error, mentioning both the requested key and fallback behavior
        return {"error": "No humidity-like data found (searched names, UUIDs, and fallbacks)"}

    try:
        df = pd.DataFrame(aggregated_readings)
        # Normalize timestamp column
        if "timestamp" not in df.columns and "datetime" in df.columns:
            df = df.rename(columns={"datetime": "timestamp"})
        if "timestamp" not in df.columns:
            # If still not present, create a dummy monotonic timestamp based on index
            df["timestamp"] = pd.to_datetime(range(len(df)), unit="s", origin="unix")
        df["timestamp"] = pd.to_datetime(df["timestamp"]) 
        df = df.sort_values(by="timestamp")
        latest = float(df.iloc[-1]["reading_value"]) if not df.empty else None
        # Default to UK recommended RH range if not provided
        if acceptable_range is None:
            acceptable_range = UK_INDOOR_STANDARDS["humidity_rh"]["range"]
        unit = "%"
        summary = {
            "mean": float(df["reading_value"].mean()) if not df.empty else None,
            "min": float(df["reading_value"].min()) if not df.empty else None,
            "max": float(df["reading_value"].max()) if not df.empty else None,
            "std": float(df["reading_value"].std()) if not df.empty else None,
            "latest": latest,
            "unit": unit,
            "acceptable_range": {"min": acceptable_range[0], "max": acceptable_range[1], "unit": unit},
        }
        if latest is not None:
            summary["alert"] = (
                "Humidity out of range"
                if (latest < acceptable_range[0] or latest > acceptable_range[1])
                else "Humidity normal"
            )
        else:
            summary["alert"] = "No readings"
        return summary
    except Exception as e:
        logging.error(f"Error analyzing humidity: {e}")
        return {"error": "Failed to analyze humidity"}


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


# ---------------------------
# Generic Dispatcher Endpoint
# ---------------------------

analysis_functions = {
    "analyze_recalibration_frequency": analyze_recalibration_frequency,
    "analyze_failure_trends": analyze_failure_trends,
    "analyze_device_deviation": analyze_device_deviation,
    "analyze_sensor_status": analyze_sensor_status,
    "analyze_air_quality_trends": analyze_air_quality_trends,
    "analyze_hvac_anomalies": analyze_hvac_anomalies,
    "analyze_supply_return_temp_difference": analyze_supply_return_temp_difference,
    "analyze_air_flow_variation": analyze_air_flow_variation,
    "analyze_sensor_trend": analyze_sensor_trend,
    "aggregate_sensor_data": aggregate_sensor_data,
    "correlate_sensors": correlate_sensors,
    "compute_air_quality_index": compute_air_quality_index,
    "generate_health_alerts": generate_health_alerts,
    "detect_anomalies": detect_anomalies,
    "analyze_noise_levels": analyze_noise_levels,
    "analyze_air_quality": analyze_air_quality,
    "analyze_formaldehyde_levels": analyze_formaldehyde_levels,
    "analyze_co2_levels": analyze_co2_levels,
    "analyze_pm_levels": analyze_pm_levels,
    "analyze_temperatures": analyze_temperatures,
    "analyze_humidity": analyze_humidity,
    "analyze_temperature_humidity": analyze_temperature_humidity,
    "detect_potential_failures": detect_potential_failures,
    "forecast_downtimes": forecast_downtimes,
}

# ---------------------------
# Analytics Function Registry (Decorator-based for extensibility)
# ---------------------------
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