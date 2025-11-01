import os
import sys
import logging
import time
import requests
import pandas as pd
from rasa_sdk import Action
import numpy as np
import plotly.express as px
from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict
from typing import Any, Text, Dict, List, Tuple, Union, Optional
from rasa_sdk.events import FollowupAction
from SPARQLWrapper import SPARQLWrapper, JSON
import mysql.connector
import json
import wave
import struct
import math
from ollama import Client
import dateparser
from dateparser.search import search_dates
from datetime import datetime, timedelta
import re
from calendar import monthrange
from decimal import Decimal
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
import uuid
import time as _time
from rapidfuzz import process as rf_process, fuzz as rf_fuzz

logger = logging.getLogger(__name__)

# -----------------------------
# Structured pipeline logging helpers
# -----------------------------
def new_correlation_id() -> str:
    return uuid.uuid4().hex[:12]

class PipelineLogger:
    """Utility to log well delimited pipeline stages with timings.

    Usage:
        pl = PipelineLogger(corr_id, component)
        with pl.stage("nl2sparql"):   
            ...
    It automatically logs start/end + elapsed ms.
    """
    def __init__(self, correlation_id: str, component: str):
        self.correlation_id = correlation_id
        self.component = component

    def _log(self, level: int, message: str, **extra):
        payload = {
            "corr": self.correlation_id,
            "comp": self.component,
            **extra
        }
        logger.log(level, f"[{self.component}][{self.correlation_id}] {message} | extra={payload}")

    def info(self, msg: str, **extra):
        self._log(logging.INFO, msg, **extra)

    def warning(self, msg: str, **extra):
        self._log(logging.WARNING, msg, **extra)

    def error(self, msg: str, **extra):
        self._log(logging.ERROR, msg, **extra)

    class _StageCtx:
        def __init__(self, outer: 'PipelineLogger', name: str):
            self.outer = outer
            self.name = name
        def __enter__(self):
            self.start = _time.time()
            self.outer.info(f"START stage '{self.name}'")
            return self
        def __exit__(self, exc_type, exc, tb):
            elapsed = int((_time.time() - self.start) * 1000)
            if exc:
                self.outer.error(f"FAIL stage '{self.name}' after {elapsed} ms: {exc}")
            else:
                self.outer.info(f"END stage '{self.name}' ok in {elapsed} ms")
            # don't suppress exceptions
            return False

    def stage(self, name: str):
        return PipelineLogger._StageCtx(self, name)

# -----------------------------
# Per-user artifact helpers
# -----------------------------
def sanitize_username(name: str) -> str:
    try:
        # Keep alphanumeric, dash and underscore only; cap length
        return "".join(c for c in (name or "") if c.isalnum() or c in ("-", "_"))[:64] or "anonymous"
    except Exception:
        return "anonymous"

def get_user_artifacts_dir(tracker: Tracker) -> Tuple[str, str]:
    """
    Compute a safe username from tracker.sender_id and ensure artifacts/<username> exists.
    Returns (user_safe, absolute_dir_path)
    """
    user_raw = getattr(tracker, "sender_id", None) or "anonymous"
    user_safe = sanitize_username(user_raw)
    user_dir = os.path.join(ARTIFACTS_DIR, user_safe)
    os.makedirs(user_dir, exist_ok=True)
    return user_safe, user_dir

# Ensure the shared data directory exists
SHARED_DIR = "/app/shared_data"
os.makedirs(SHARED_DIR, exist_ok=True)
# Single folder to keep all generated artifacts that are shared with users
ARTIFACTS_DIR = os.path.join(SHARED_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

# Logs directory: prefer a dedicated logs folder under shared_data so logs are visible on host
LOG_DIR = os.getenv("ACTION_LOG_DIR", os.path.join(SHARED_DIR, "logs"))
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "action.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),  # Save to file
        logging.StreamHandler(sys.stdout),  # Also stream to container stdout for docker-compose logs
    ],
)
logger = logging.getLogger(__name__)

# Global constants
# Default to internal Docker DNS names so services work inside the compose network.
nl2sparql_url = os.getenv("NL2SPARQL_URL", "http://nl2sparql:6005/nl2sparql") # Original internal URL
# nl2sparql_url = os.getenv("NL2SPARQL_URL", "https://deep-gator-cleanly.ngrok-free.app") # Updated to external ngrok URL for testing
FUSEKI_URL = os.getenv("FUSEKI_URL", "http://jena-fuseki-rdf-store:3030/bldg2/sparql")
# Where to write downloadable files. Use the shared volume so http_server can serve them.
# Route everything through a single folder for easy sharing and cleanup.
ATTACHMENTS_DIR = ARTIFACTS_DIR
# Base URL for the simple HTTP server that exposes shared_data
BASE_URL_DEFAULT = "http://localhost:8080"
# Optional unified decider microservice
DECIDER_URL = os.getenv("DECIDER_URL")
# Summarization/Ollama base URL
# SUMMARIZATION_URL = os.getenv("SUMMARIZATION_URL", "http://ollama:11434") # Original internal URL
SUMMARIZATION_URL = os.getenv("SUMMARIZATION_URL", "https://dashing-sunfish-curiously.ngrok-free.app") # Updated to external ngrok URL for testing

def get_mysql_config() -> Dict[str, Any]:
    """Return a unified MySQL configuration using environment variables with sensible defaults.

    Environment variables supported:
      - DB_HOST (default: "mysqlserver")
      - DB_PORT (default: 3306)
      - DB_NAME (default: "sensordb")
      - DB_USER (default: "root")
      - DB_PASSWORD (default: "mysql")

    This single source of truth is used across the action server to avoid duplication and confusion.
    """
    host = os.getenv("DB_HOST", "mysqlserver")
    default_password = "root" if host == "localhost" else "mysql"
    # Build config
    cfg: Dict[str, Any] = {
        "host": host,
        "database": os.getenv("DB_NAME", "sensordb"),
        "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", default_password),
        "port": os.getenv("DB_PORT", "3306"),
    }
    # Ensure port is an int for mysql.connector
    try:
        if isinstance(cfg["port"], str) and cfg["port"].isdigit():
            cfg["port"] = int(cfg["port"]) 
    except Exception:
        pass
    return cfg

# Load VALID_SENSOR_TYPES from sensor_list.txt
try:
    # In the built image, files reside under /app; with WORKDIR=/app, use relative paths.
    # Prefer sensor_list.txt in current dir; fallback to legacy ./actions path if needed.
    candidates = [
        os.path.join(os.getcwd(), "sensor_list.txt"),
        os.path.join(os.getcwd(), "actions", "sensor_list.txt"),
    ]
    path = next((p for p in candidates if os.path.exists(p)), None)
    with open(path or "sensor_list.txt", "r") as f:
        VALID_SENSOR_TYPES = {line.strip() for line in f if line.strip()}
    logger.info(f"Loaded {len(VALID_SENSOR_TYPES)} sensor types from sensor_list.txt")
except FileNotFoundError:
    logger.error("sensor_list.txt not found in data/ directory")
    VALID_SENSOR_TYPES = set()
except Exception as e:
    logger.error(f"Error loading sensor_list.txt: {e}")
    VALID_SENSOR_TYPES = set()
# Initialize Ollama client
try:
    client = Client(host=SUMMARIZATION_URL)
    logger.info(f"Initialized Ollama client for {SUMMARIZATION_URL}")
except Exception as e:
    logger.error(f"Failed to initialize Ollama client: {e}")
    client = None


# ---------------------------------
# LLM response parsing helper (module scope)
# ---------------------------------
def extract_text_from_llm_response(resp: Any) -> Optional[str]:
    """Best-effort extraction of text from various LLM response shapes.

    Supports:
    - Ollama Python client: {"response": "..."}
    - OpenAI chat/completions: {"choices": [{"message": {"content": "..."}}]}
    - OpenAI completions (legacy): {"choices": [{"text": "..."}]}
    - Simple: {"text": "..."} or a plain string
    - {"message": "..."} / {"content": "..."}
    Returns a stripped string or None if nothing usable found.
    """
    try:
        if resp is None:
            return None
        # Plain string
        if isinstance(resp, str):
            return resp.strip() or None

        # Objects from clients (e.g., Ollama Response) may expose attributes instead of dict keys
        def getattr_str(obj: Any, name: str) -> Optional[str]:
            try:
                val = getattr(obj, name)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            except Exception:
                return None
            return None

        # 1) Try attribute-based extraction first
        for attr in ("response", "text", "content", "message"):
            val = getattr_str(resp, attr)
            if val:
                return val

        # If it has a choices attribute (OpenAI-like)
        try:
            choices_attr = getattr(resp, "choices", None)
            if isinstance(choices_attr, list) and choices_attr:
                first = choices_attr[0]
                # Dict-like entry
                if isinstance(first, dict):
                    msg = first.get("message")
                    if isinstance(msg, dict):
                        content = msg.get("content")
                        if isinstance(content, str) and content.strip():
                            return content.strip()
                    text_val = first.get("text")
                    if isinstance(text_val, str) and text_val.strip():
                        return text_val.strip()
        except Exception:
            pass

        # 2) Dict-based extraction
        if isinstance(resp, dict):
            if isinstance(resp.get("response"), str):
                return resp.get("response", "").strip() or None
            choices = resp.get("choices")
            if isinstance(choices, list) and choices:
                first = choices[0]
                if isinstance(first, dict):
                    msg = first.get("message")
                    if isinstance(msg, dict):
                        content = msg.get("content")
                        if isinstance(content, str) and content.strip():
                            return content.strip()
                    text_val = first.get("text")
                    if isinstance(text_val, str) and text_val.strip():
                        return text_val.strip()
            for key in ("text", "message", "content"):
                val = resp.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()

        # 3) If object can be converted to dict (pydantic), try that
        for to_dict in ("model_dump", "dict"):
            try:
                if hasattr(resp, to_dict):
                    data = getattr(resp, to_dict)()
                    if isinstance(data, dict):
                        return extract_text_from_llm_response(data)
            except Exception:
                pass

        # Fallback: do not return the verbose repr; better return None than leak internals
        return None
    except Exception:
        return None


class ValidateSensorForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_sensor_form"

    async def validate_sensor_type(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Handle comma-separated string input
        if isinstance(slot_value, str) and "," in slot_value:
            sensor_types = [s.strip() for s in slot_value.split(",")]
            logger.info(f"Split comma-separated input into: {sensor_types}")
        # Handle single string input
        elif isinstance(slot_value, str):
            sensor_types = [slot_value]
        # Handle list input (already a list)
        else:
            sensor_types = slot_value if isinstance(slot_value, list) else [slot_value]
            
        sensor_mappings = self.load_sensor_mappings()
        # Compile a regex to match canonical sensor names, e.g., Zone_Air_Humidity_Sensor_5.01
        sensor_regex = re.compile(r"^(?:[A-Za-z]+(?:_[A-Za-z0-9]+)*)_Sensor_[0-9]+(?:\.[0-9]+)?$")

        # Build a candidate list of canonical sensor names from mappings and curated list
        uuid_re = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
        mapping_names = {k for k in sensor_mappings.keys() if not uuid_re.match(k)}
        candidates: List[str] = sorted(set(VALID_SENSOR_TYPES) | set(mapping_names))

        valid_sensors: List[str] = []
        for s in sensor_types:
            if not isinstance(s, str):
                continue
            s_stripped = s.strip()
            # Quick exact acceptance
            if (
                s_stripped in sensor_mappings
                or s_stripped in VALID_SENSOR_TYPES
                or bool(sensor_regex.match(s_stripped))
            ):
                valid_sensors.append(s_stripped)
                continue

            # Try normalization (spaces <-> underscores) then exact
            alt = s_stripped.replace(" ", "_") if " " in s_stripped else s_stripped.replace("_", " ")
            if alt in candidates:
                logger.info(f"Canonicalized sensor by normalization: '{s_stripped}' -> '{alt}'")
                valid_sensors.append(alt.replace(" ", "_"))
                continue

            # Fuzzy match (~90+) against known candidates
            try:
                match = rf_process.extractOne(s_stripped, candidates, scorer=rf_fuzz.WRatio)
                if match and match[1] >= 90:
                    canon = match[0]
                    logger.info(f"Fuzzy-matched sensor '{s_stripped}' -> '{canon}' (score={match[1]})")
                    valid_sensors.append(canon)
                    continue
                # Retry with alt spacing
                match2 = rf_process.extractOne(alt, candidates, scorer=rf_fuzz.WRatio)
                if match2 and match2[1] >= 90:
                    canon2 = match2[0]
                    logger.info(f"Fuzzy-matched sensor (alt) '{s_stripped}' -> '{canon2}' (score={match2[1]})")
                    valid_sensors.append(canon2)
                    continue
            except Exception as fe:
                logger.warning(f"Fuzzy match error for '{s_stripped}': {fe}")

        # Deduplicate while preserving order
        seen = set()
        valid_sensors = [x for x in valid_sensors if not (x in seen or seen.add(x))]

        if not valid_sensors:
            dispatcher.utter_message(response="utter_ask_sensor_type")
            return {"sensor_type": None}
        
        logger.info(f"Validated sensor_types: {valid_sensors}")
        return {"sensor_type": valid_sensors}

    def load_sensor_mappings(self) -> Dict[str, str]:
        mappings = {}
        try:
            candidates = [
                os.path.join(os.getcwd(), "sensor_uuids.txt"),
                os.path.join(os.getcwd(), "actions", "sensor_uuids.txt"),
            ]
            path = next((p for p in candidates if os.path.exists(p)), None)
            with open(path or "sensor_uuids.txt", "r") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        if line.strip():
                            parts = line.strip().split(",")
                            if len(parts) == 2:
                                name, uuid = parts
                                # Store both directions for flexible lookup
                                mappings[name] = uuid  # For validation of names
                                mappings[uuid] = name  # For converting UUIDs to names
                            else:
                                logger.warning(f"Line {line_num}: Invalid format - expected 'name,uuid' but got: {line.strip()}")
                    except Exception as e:
                        logger.error(f"Error on line {line_num}: {e}")
            logger.info(f"Loaded {len(mappings)} sensor mappings")
        except FileNotFoundError:
            logger.error("sensor_uuids.txt not found")
            # Create an empty file to prevent future errors
            try:
                os.makedirs("./actions", exist_ok=True)
                with open("./actions/sensor_uuids.txt", "w") as f:
                    f.write("# Format: sensor_name,sensor_uuid\n")
                logger.info("Created empty sensor_uuids.txt file")
            except Exception as e:
                logger.error(f"Failed to create empty sensor_uuids.txt: {e}")
        return mappings

def extract_date_range(text: str) -> Dict[str, str]:
    """
    Extract date ranges from text using various common patterns.
    
    Args:
        text: The text to extract date ranges from
        
    Returns:
        Dictionary with 'start_date' and 'end_date' if found, empty dict otherwise
    """
    patterns = [
        # from DD/MM/YYYY to DD/MM/YYYY
        r"from\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})",
        # between DD/MM/YYYY and DD/MM/YYYY
        r"between\s+(\d{2}/\d{2}/\d{4})\s+and\s+(\d{2}/\d{2}/\d{4})",
        # DD/MM/YYYY - DD/MM/YYYY
        r"(\d{2}/\d{2}/\d{4})\s*[-–—]\s*(\d{2}/\d{2}/\d{4})",
        # YYYY-MM-DD to YYYY-MM-DD
        r"(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return {
                'start_date': match.group(1),
                'end_date': match.group(2)
            }
    
    return {}

# Helper to resolve common relative date phrases into explicit start/end datetimes
def resolve_relative_date_range(text: str) -> Optional[Tuple[datetime, datetime, str]]:
    """
    Recognize phrases like today, yesterday, now, last week, last month and return concrete datetimes.

    Returns:
        (start_dt, end_dt, label) or None if no known phrase found
    """
    if not text:
        return None

    t = text.strip().lower()
    now = datetime.now()
    today = datetime(year=now.year, month=now.month, day=now.day)

    def start_of_week(d: datetime) -> datetime:
        iso = d.isoweekday()
        return d - timedelta(days=iso - 1)

    def start_of_month(d: datetime) -> datetime:
        return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def start_of_quarter(d: datetime) -> datetime:
        q = (d.month - 1) // 3
        first_month = q * 3 + 1
        return datetime(d.year, first_month, 1)

    def start_of_year(d: datetime) -> datetime:
        return datetime(d.year, 1, 1)

    # today -> [today 00:00:00, now]
    if any(k in t for k in ["today", "todays", "to-day"]):
        return today, now, "today"

    # yesterday -> [yesterday 00:00:00, yesterday 23:59:59]
    if any(k in t for k in ["yesterday", "y-day", "yday"]):
        y = today - timedelta(days=1)
        return y, y.replace(hour=23, minute=59, second=59), "yesterday"

    # now -> interpret as an end instant; caller may use only for end_date
    if t in {"now", "right now", "just now"}:
        # Use the same instant for start=end; validators can override pairing
        return now, now, "now"

    # last week / previous week -> previous ISO week Mon 00:00 to Sun 23:59:59
    if any(k in t for k in ["last week", "previous week", "prev week"]):
        # ISO: Monday=1..Sunday=7
        start_this_week = start_of_week(today)
        start_prev_week = start_this_week - timedelta(days=7)
        end_prev_week = start_this_week - timedelta(seconds=1)
        end_prev_week = end_prev_week.replace(hour=23, minute=59, second=59)
        return start_prev_week, end_prev_week, "last_week"

    # last 7 days / past week -> [now-7d, now]
    if any(k in t for k in ["last 7 days", "past week", "previous 7 days", "past 7 days"]):
        start = now - timedelta(days=7)
        return start, now, "last_7_days"

    # last month / previous month -> full previous calendar month
    if any(k in t for k in ["last month", "previous month", "prev month"]):
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        first_prev_month = last_prev_month.replace(day=1)
        end_prev_month = last_prev_month.replace(hour=23, minute=59, second=59)
        return first_prev_month, end_prev_month, "last_month"

    # last year / previous year -> full previous calendar year
    if any(k in t for k in ["last year", "previous year", "prev year"]):
        start_prev_year = datetime(today.year - 1, 1, 1)
        end_prev_year = datetime(today.year - 1, 12, 31, 23, 59, 59)
        return start_prev_year, end_prev_year, "last_year"

    # last quarter / previous quarter -> full previous calendar quarter
    if any(k in t for k in ["last quarter", "previous quarter", "prev quarter"]):
        q = (today.month - 1) // 3 + 1
        if q == 1:
            year = today.year - 1
            start_month = 10
        else:
            year = today.year
            start_month = (q - 2) * 3 + 1
        start_prev_q = datetime(year, start_month, 1)
        end_prev_q = start_prev_q + relativedelta(months=3) - timedelta(seconds=1)
        end_prev_q = end_prev_q.replace(hour=23, minute=59, second=59)
        return start_prev_q, end_prev_q, "last_quarter"

    # last weekend -> previous Saturday 00:00:00 to Sunday 23:59:59
    if any(k in t for k in ["last weekend", "previous weekend", "prev weekend"]):
        sow = start_of_week(today)
        sat = sow - timedelta(days=2)
        sun = sow - timedelta(days=1)
        return sat, sun.replace(hour=23, minute=59, second=59), "last_weekend"

    # this week/month/quarter/year -> start of period to now
    if any(k in t for k in ["this week", "week to date", "wtd"]):
        sow = start_of_week(today)
        return sow, now, "this_week"
    if any(k in t for k in ["this month", "month to date", "mtd"]):
        som = start_of_month(today)
        return som, now, "this_month"
    if any(k in t for k in ["this quarter", "quarter to date", "qtd"]):
        soq = start_of_quarter(today)
        return soq, now, "this_quarter"
    if any(k in t for k in ["this year", "year to date", "ytd"]):
        soy = start_of_year(today)
        return soy, now, "this_year"

    # last N units or past/previous N units, includes 'in the last N'
    m = re.search(r"(last|past|previous|prev|in the last)\s+(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)", t)
    if m:
        n = int(m.group(2))
        unit = m.group(3)
        if unit.startswith('minute'):
            start = now - timedelta(minutes=n)
        elif unit.startswith('hour'):
            start = now - timedelta(hours=n)
        elif unit.startswith('day'):
            start = now - timedelta(days=n)
        elif unit.startswith('week'):
            start = now - timedelta(weeks=n)
        elif unit.startswith('month'):
            start = now - relativedelta(months=n)
        elif unit.startswith('year'):
            start = now - relativedelta(years=n)
        else:
            start = now
        return start, now, f"last_{n}_{unit}"

    # shortcuts: last 24 hours / 48 hours / 30 days
    if any(k in t for k in ["last 24 hours", "past 24 hours"]):
        return now - timedelta(hours=24), now, "last_24_hours"
    if any(k in t for k in ["last 48 hours", "past 48 hours"]):
        return now - timedelta(hours=48), now, "last_48_hours"
    if any(k in t for k in ["last 30 days", "past 30 days"]):
        return now - timedelta(days=30), now, "last_30_days"

    # since <date> -> [parsed date start-of-day, now]
    m2 = re.search(r"since\s+(.+)$", t)
    if m2:
        anchor = dateparser.parse(m2.group(1))
        if anchor:
            start = datetime(anchor.year, anchor.month, anchor.day)
            return start, now, "since"

    # until/till/up to <date> -> [unspecified, parsed date end-of-day]; caller must decide whether to fill start
    m3 = re.search(r"(until|till|up to)\s+(.+)$", t)
    if m3:
        anchor = dateparser.parse(m3.group(2))
        if anchor:
            end = datetime(anchor.year, anchor.month, anchor.day, 23, 59, 59)
            # Provide start=today for convenience; validators can ignore when label=='until'
            return today, end, "until"

    return None

class ValidateDatesForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_dates_form"

    async def validate_start_date(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Log the raw value received
        logger.info(f"Raw start_date input: '{slot_value}', type: {type(slot_value).__name__}")
        
        try:
            # Check message for dates in "from X to Y" format
            latest_message = tracker.latest_message.get("text", "")
            if latest_message:
                # Look for "from DD/MM/YYYY to DD/MM/YYYY" pattern
                date_match = re.search(r"from\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", latest_message)
                if date_match:
                    extracted_start = date_match.group(1)
                    extracted_end = date_match.group(2)
                    logger.info(f"Extracted dates from text: start={extracted_start}, end={extracted_end}")
                    
                    # Store end_date for later use
                    extra_slots = {}
                    if not tracker.get_slot("end_date"):
                        dispatcher.utter_message(text=f"I've noted the end date as {extracted_end}")
                        # Defer setting slot via returned dict instead of mutating tracker
                        extra_slots["end_date"] = extracted_end
                    # Use the extracted start date
                    slot_value = extracted_start
                    logger.info(f"Using start_date from text extraction: {slot_value}")
            
            # Quick path: handle Duckling interval dict with from/to
            if isinstance(slot_value, dict):
                # duckling interval example: {'from': '2025-02-01T00:00:00.000+00:00', 'to': '2025-02-07T23:59:59.000+00:00'}
                if 'from' in slot_value or 'to' in slot_value:
                    start_iso = slot_value.get('from') or slot_value.get('value')
                    end_iso = slot_value.get('to')
                    extra_slots = {}
                    if start_iso:
                        try:
                            sd = parse(start_iso)
                            start_str = sd.strftime("%d/%m/%Y")
                            extra_slots['start_date'] = start_str
                        except Exception:
                            pass
                    if end_iso and not tracker.get_slot('end_date'):
                        try:
                            ed = parse(end_iso)
                            end_str = ed.strftime("%d/%m/%Y")
                            extra_slots['end_date'] = end_str
                            dispatcher.utter_message(text=f"I've noted the end date as {end_str}")
                        except Exception:
                            pass
                    if extra_slots:
                        return extra_slots

            # Handle various input formats
            
            # 1. Handle Duckling entity extraction which can return a dictionary
            if isinstance(slot_value, dict) and "value" in slot_value:
                slot_value = slot_value["value"]
                logger.info(f"Extracted value from Duckling dict: {slot_value}")
            
            # 2. Handle list of values (Duckling sometimes returns a list)
            if isinstance(slot_value, list) and len(slot_value) > 0:
                logger.info(f"start_date is a list: {slot_value}")
                slot_value = slot_value[0]
                
            # 3. Clean up text input (remove prefixes like "from", etc.)
            if isinstance(slot_value, str):
                slot_value = re.sub(r'^(from|start|on|date\s*:?)\s*', '', slot_value.strip(), flags=re.IGNORECASE)
                logger.info(f"Cleaned start_date input: '{slot_value}'")
            
            # 4. Handle multiple date formats and relative phrases
            if isinstance(slot_value, str):
                # 4.0 Relative phrases like today/yesterday/now/last week/last month
                rel = resolve_relative_date_range(slot_value)
                if rel:
                    start_dt, end_dt, label = rel
                    result = {"start_date": start_dt.strftime("%d/%m/%Y")}
                    if not tracker.get_slot("end_date"):
                        # 'until' means user supplied only an upper bound; keep start_date as-is if already set later
                        result["end_date"] = end_dt.strftime("%d/%m/%Y")
                        if label in {"today", "last_7_days", "last_week", "last_month", "this_week", "this_month", "this_quarter", "this_year", "last_year", "last_quarter", "last_weekend", "last_24_hours", "last_48_hours", "last_30_days"} or label.startswith("last_"):
                            dispatcher.utter_message(text=f"Using {label.replace('_',' ')} as the date range.")
                        elif label == "now":
                            dispatcher.utter_message(text="Using now as the end time.")
                        elif label in {"since", "until"}:
                            dispatcher.utter_message(text=f"Using {label} window ending {end_dt.strftime('%d/%m/%Y') if label=='until' else 'now'}.")
                    if 'extra_slots' in locals():
                        result.update(extra_slots)
                    return result
                # 4.1. DD/MM/YYYY format
                if re.match(r"^\d{2}/\d{2}/\d{4}$", slot_value):
                    logger.info(f"start_date matched DD/MM/YYYY format: {slot_value}")
                    day, month, year = slot_value.split('/')
                    formatted_date = f"{year}-{month}-{day}"
                    parse(formatted_date)  # Validate
                    sql_date = formatted_date
                    logger.info(f"Converted to SQL date format: {sql_date}")
                    result = {"start_date": slot_value}
                    if 'extra_slots' in locals():
                        result.update(extra_slots)
                    return result
                    
                # 4.2. YYYY-MM-DD format
                elif re.match(r"^\d{4}-\d{2}-\d{2}$", slot_value):
                    logger.info(f"start_date is already in YYYY-MM-DD format: {slot_value}")
                    parse(slot_value)  # Validate
                    sql_date = slot_value
                    result = {"start_date": sql_date}
                    if 'extra_slots' in locals():
                        result.update(extra_slots)
                    return result
                    
                # 4.3. Try natural language parsing for other formats
                else:
                    logger.info(f"Trying to parse start_date with dateparser: {slot_value}")
                    parsed_date = dateparser.parse(slot_value)
                    if parsed_date:
                        formatted_date = parsed_date.strftime("%d/%m/%Y")
                        logger.info(f"Successfully parsed to: {formatted_date}")
                        result = {"start_date": formatted_date}
                        if 'extra_slots' in locals():
                            result.update(extra_slots)
                        return result
                    else:
                        # Try with dateutil's parse as fallback
                        logger.info(f"Trying to parse start_date with dateutil: {slot_value}")
                        parsed = parse(slot_value)
                        formatted_date = parsed.strftime("%d/%m/%Y") 
                        logger.info(f"Successfully parsed with dateutil to: {formatted_date}")
                        result = {"start_date": formatted_date}
                        if 'extra_slots' in locals():
                            result.update(extra_slots)
                        return result
            
            logger.error(f"Could not parse start_date value: {slot_value}")
            dispatcher.utter_message(text="I couldn't understand that date format. Please use DD/MM/YYYY (e.g., 01/02/2025).")
            return {"start_date": None}
            
        except ValueError as e:
            logger.error(f"start_date validation error: {e}, value: {slot_value}")
            dispatcher.utter_message(text="Invalid start date format. Please use DD/MM/YYYY.")
            return {"start_date": None}
        except Exception as e:
            logger.error(f"Unexpected error validating start_date: {str(e)}")
            dispatcher.utter_message(text="There was a problem processing the date. Please try again with format DD/MM/YYYY.")
            return {"start_date": None}

    async def validate_end_date(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Log the raw value received
        logger.info(f"Raw end_date input: '{slot_value}', type: {type(slot_value).__name__}")
        
        try:
            # Check message for dates in "from X to Y" format
            latest_message = tracker.latest_message.get("text", "")
            if latest_message:
                # Look for "from DD/MM/YYYY to DD/MM/YYYY" pattern
                date_match = re.search(r"from\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", latest_message)
                if date_match and not tracker.get_slot("start_date"):
                    extracted_start = date_match.group(1)
                    extracted_end = date_match.group(2)
                    logger.info(f"Extracted dates from text: start={extracted_start}, end={extracted_end}")
                    
                    # Store start_date for later use
                    extra_slots = {}
                    dispatcher.utter_message(text=f"I've noted the start date as {extracted_start}")
                    # Defer slot assignment via return dict
                    extra_slots["start_date"] = extracted_start
                    # Use the extracted end date
                    slot_value = extracted_end
                    logger.info(f"Using end_date from text extraction: {slot_value}")
            
            # Quick path: handle Duckling interval dict with from/to
            if isinstance(slot_value, dict):
                if 'to' in slot_value or 'from' in slot_value:
                    start_iso = slot_value.get('from')
                    end_iso = slot_value.get('to') or slot_value.get('value')
                    extra_slots = {}
                    if start_iso and not tracker.get_slot('start_date'):
                        try:
                            sd = parse(start_iso)
                            start_str = sd.strftime("%d/%m/%Y")
                            extra_slots['start_date'] = start_str
                            dispatcher.utter_message(text=f"I've noted the start date as {start_str}")
                        except Exception:
                            pass
                    if end_iso:
                        try:
                            ed = parse(end_iso)
                            end_str = ed.strftime("%d/%m/%Y")
                            extra_slots['end_date'] = end_str
                        except Exception:
                            pass
                    if extra_slots:
                        return extra_slots

            # Handle various input formats
            
            # 1. Handle Duckling entity extraction which can return a dictionary
            if isinstance(slot_value, dict) and "value" in slot_value:
                slot_value = slot_value["value"]
                logger.info(f"Extracted value from Duckling dict: {slot_value}")
            
            # 2. Handle list of values (Duckling sometimes returns a list)
            if isinstance(slot_value, list) and len(slot_value) > 0:
                logger.info(f"end_date is a list: {slot_value}")
                slot_value = slot_value[0]
                
            # 3. Clean up text input (remove prefixes like "to", etc.)
            if isinstance(slot_value, str):
                slot_value = re.sub(r'^(to|end|until|through)\s*', '', slot_value.strip(), flags=re.IGNORECASE)
                logger.info(f"Cleaned end_date input: '{slot_value}'")
            
            # 4. Handle multiple date formats and relative phrases
            if isinstance(slot_value, str):
                # 4.0 Relative phrases
                rel = resolve_relative_date_range(slot_value)
                if rel:
                    start_dt, end_dt, label = rel
                    # Preserve time-of-day for 'now' specifically
                    if label == "now":
                        result = {"end_date": end_dt.isoformat()}
                    else:
                        result = {"end_date": end_dt.strftime("%d/%m/%Y")}
                    if not tracker.get_slot("start_date") and label != "until":
                        result["start_date"] = start_dt.strftime("%d/%m/%Y")
                    if label in {"today", "last_7_days", "last_week", "last_month", "this_week", "this_month", "this_quarter", "this_year", "last_year", "last_quarter", "last_weekend", "last_24_hours", "last_48_hours", "last_30_days"} or label.startswith("last_"):
                        dispatcher.utter_message(text=f"Using {label.replace('_',' ')} as the date range.")
                    elif label == "now":
                        dispatcher.utter_message(text="Using now as the end time.")
                    elif label in {"since", "until"}:
                        dispatcher.utter_message(text=f"Using {label} window {'ending ' + end_dt.strftime('%d/%m/%Y') if label=='until' else 'from ' + start_dt.strftime('%d/%m/%Y') + ' to now'}.")
                    if 'extra_slots' in locals():
                        result.update(extra_slots)
                    return result
                # 4.1. DD/MM/YYYY format
                if re.match(r"^\d{2}/\d{2}/\d{4}$", slot_value):
                    logger.info(f"end_date matched DD/MM/YYYY format: {slot_value}")
                    day, month, year = slot_value.split('/')
                    formatted_date = f"{year}-{month}-{day}"
                    end_dt = parse(formatted_date)  # Validate
                    sql_date = formatted_date
                    logger.info(f"Converted to SQL date format: {sql_date}")
                    
                # 4.2. YYYY-MM-DD format
                elif re.match(r"^\d{4}-\d{2}-\d{2}$", slot_value):
                    logger.info(f"end_date is already in YYYY-MM-DD format: {slot_value}")
                    end_dt = parse(slot_value)  # Validate
                    sql_date = slot_value
                    
                # 4.3. Try natural language parsing for other formats
                else:
                    logger.info(f"Trying to parse end_date with dateparser: {slot_value}")
                    parsed_date = dateparser.parse(slot_value)
                    if parsed_date:
                        sql_date = parsed_date.strftime("%Y-%m-%d")
                        end_dt = parsed_date
                        slot_value = parsed_date.strftime("%d/%m/%Y")
                        logger.info(f"Successfully parsed to: {slot_value}, SQL format: {sql_date}")
                    else:
                        # Try with dateutil's parse as fallback
                        logger.info(f"Trying to parse end_date with dateutil: {slot_value}")
                        end_dt = parse(slot_value)
                        slot_value = end_dt.strftime("%d/%m/%Y")
                        sql_date = end_dt.strftime("%Y-%m-%d")
                        logger.info(f"Successfully parsed with dateutil to: {slot_value}, SQL format: {sql_date}")
                
                # Compare with start_date to ensure end_date is later
                start_date = tracker.get_slot("start_date")
                if start_date:
                    logger.info(f"Comparing with start_date: {start_date}")
                    
                    # Parse start_date in the same way
                    if re.match(r"^\d{2}/\d{2}/\d{4}$", start_date):
                        day, month, year = start_date.split('/')
                        formatted_start = f"{year}-{month}-{day}"
                        start_dt = parse(formatted_start)
                    elif re.match(r"^\d{4}-\d{2}-\d{2}$", start_date):
                        start_dt = parse(start_date)
                    else:
                        # Try with dateparser
                        parsed_start = dateparser.parse(start_date)
                        if parsed_start:
                            start_dt = parsed_start
                        else:
                            start_dt = parse(start_date)
                    
                    logger.info(f"start_dt: {start_dt}, end_dt: {end_dt}")
                    if end_dt <= start_dt:
                        dispatcher.utter_message(text="End date must be after start date.")
                        return {"end_date": None}
                
                logger.info(f"end_date validation successful: {slot_value}")
                result = {"end_date": slot_value}
                if 'extra_slots' in locals():
                    result.update(extra_slots)
                return result
            
            logger.error(f"Could not parse end_date value: {slot_value}")
            dispatcher.utter_message(text="I couldn't understand that date format. Please use DD/MM/YYYY (e.g., 05/02/2025).")
            return {"end_date": None}
            
        except ValueError as e:
            logger.error(f"end_date validation error: {e}, value: {slot_value}")
            dispatcher.utter_message(text="Invalid end date format. Please use DD/MM/YYYY.")
            return {"end_date": None}
        except Exception as e:
            logger.error(f"Unexpected error validating end_date: {str(e)}")
            dispatcher.utter_message(text="There was a problem processing the date. Please try again with format DD/MM/YYYY.")
            return {"end_date": None}

class ActionQuestionToBrickbot(Action):
    def name(self) -> Text:
        return "action_question_to_brickbot"

    def load_sensor_mappings(self) -> Dict[str, str]:
        mappings = {}
        try:
            with open("./actions/sensor_uuids.txt", "r") as f:
                for line in f:
                    if line.strip():
                        name, uuid = line.strip().split(",")
                        mappings[uuid] = name
            logger.info(f"Loaded {len(mappings)} sensor mappings")
        except FileNotFoundError:
            logger.error("sensor_uuids.txt not found")
        return mappings

    def query_service_requests(self, url: str, data: Dict) -> Dict:
            headers = {"Content-Type": "application/json"}
            try:
                response = requests.post(url, json=data, headers=headers, timeout=20)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to query nl2sparql endpoint: {e}")
                return {"error": str(e)}

    def add_sparql_prefixes(self, sparql_query: str) -> str:
        """
        Appends a set of predefined SPARQL prefixes to the query.
        """
        prefixes = [
            "PREFIX brick: <https://brickschema.org/schema/Brick#>",
            "PREFIX dcterms: <http://purl.org/dc/terms/>",
            "PREFIX owl: <http://www.w3.org/2002/07/owl#>",
            "PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>",
            "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>",
            "PREFIX sh: <http://www.w3.org/ns/shacl#>",
            "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>",
            "PREFIX sosa: <http://www.w3.org/ns/sosa/>",
            "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>",
            "PREFIX tag: <https://brickschema.org/schema/BrickTag#>",
            "PREFIX bldg: <http://buildsys.org/ontologies/bldg2#>",
            "PREFIX bsh: <https://brickschema.org/schema/BrickShape#>",
            "PREFIX s223: <http://data.ashrae.org/standard223#>",
            "PREFIX bacnet: <http://data.ashrae.org/bacnet/2020#>",
            "PREFIX g36: <http://data.ashrae.org/standard223/1.0/extensions/g36#>",
            "PREFIX qkdv: <http://qudt.org/vocab/dimensionvector/>",
            "PREFIX quantitykind: <http://qudt.org/vocab/quantitykind/>",
            "PREFIX qudt: <http://qudt.org/schema/qudt/>",
            "PREFIX rec: <https://w3id.org/rec#>",
            "PREFIX ref: <https://brickschema.org/schema/Brick/ref#>",
            "PREFIX s223tobrick: <https://brickschema.org/extension/brick_extension_interpret_223#>",
            "PREFIX schema1: <http://schema.org/>",
            "PREFIX unit: <http://qudt.org/vocab/unit/>",
            "PREFIX vcard: <http://www.w3.org/2006/vcard/ns#>",
        ]
        return "\n".join(prefixes) + "\n" + sparql_query

    def canonicalize_sensor_names(self, sensor_types: List[str]) -> List[str]:
        """Map provided sensor names to canonical ones using normalization + fuzzy matching (>=90)."""
        if not sensor_types:
            return sensor_types
        # Build candidate list
        mappings = self.load_sensor_mappings()
        uuid_re = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
        mapping_names = {k for k in mappings.keys() if not uuid_re.match(k)}
        candidates: List[str] = sorted(set(VALID_SENSOR_TYPES) | set(mapping_names))
        out: List[str] = []
        for s in sensor_types:
            if not isinstance(s, str):
                continue
            s_stripped = s.strip()
            # Exact or curated
            if s_stripped in candidates:
                out.append(s_stripped)
                continue
            alt = s_stripped.replace(" ", "_") if " " in s_stripped else s_stripped.replace("_", " ")
            if alt in candidates:
                out.append(alt.replace(" ", "_"))
                logger.info(f"Canonicalized sensor by normalization in QuestionToBrickbot: '{s_stripped}' -> '{alt}'")
                continue
            # Fuzzy fallback
            try:
                match = rf_process.extractOne(s_stripped, candidates, scorer=rf_fuzz.WRatio)
                if match and match[1] >= 90:
                    out.append(match[0])
                    logger.info(f"Fuzzy-matched (QuestionToBrickbot) '{s_stripped}' -> '{match[0]}' (score={match[1]})")
                    continue
                match2 = rf_process.extractOne(alt, candidates, scorer=rf_fuzz.WRatio)
                if match2 and match2[1] >= 90:
                    out.append(match2[0])
                    logger.info(f"Fuzzy-matched alt (QuestionToBrickbot) '{s_stripped}' -> '{match2[0]}' (score={match2[1]})")
                    continue
            except Exception as fe:
                logger.warning(f"Fuzzy match error in QuestionToBrickbot for '{s_stripped}': {fe}")
        # Dedup preserve order
        seen = set()
        return [x for x in out if not (x in seen or seen.add(x))]

    def execute_sparql_query(self, sparql_query: str) -> Dict:
        """
        Executes the given SPARQL query against the Fuseki endpoint.
        """
        sparql = SPARQLWrapper(FUSEKI_URL)
        sparql.setQuery(sparql_query)
        sparql.setReturnFormat(JSON)
        sparql.setTimeout(10)
        try:
            results = sparql.queryAndConvert()
            logger.info("SPARQL query executed successfully.")
            return results
        except Exception as e:
            logger.error(f"Error executing SPARQL query: {e}")
            return None

    def format_sparql_results(self, results: Dict) -> Text:
        """
        Formats SPARQL results for user-friendly summary display.
        """
        if (
            not results
            or "results" not in results
            or "bindings" not in results["results"]
        ):
            return "No results found."
        bindings = results["results"]["bindings"]
        if not bindings:
            return "No results found."
        formatted = []
        for binding in bindings:
            values = {key: val["value"] for key, val in binding.items()}
            formatted.append(f"Result: {values}")
        return "\n".join(formatted)[:500]

    def format_json_for_ui(self, json_data: Dict) -> Text:
            """
            Formats JSON for display in the chatbot UI.
            """
            try:
                json_str = json.dumps(json_data, indent=2)
                if len(json_str) > 1000:
                    json_str = json_str[:997] + "..."
                return f"Standardized JSON response:\n```json\n{json_str}\n```"
            except (TypeError, ValueError) as e:
                logger.error(f"Error formatting JSON for UI: {e}")
                return "Unable to display JSON response."

    def replace_uuids_with_sensor_types(self, data: Any, uuid_to_sensor: Dict[Text, Text]) -> Any:
                """Recursively replace UUIDs with sensor types in the data structure."""
                if isinstance(data, dict):
                    return {k: self.replace_uuids_with_sensor_types(v, uuid_to_sensor) for k, v in data.items()}
                elif isinstance(data, list):
                    return [self.replace_uuids_with_sensor_types(item, uuid_to_sensor) for item in data]
                elif isinstance(data, str) and data in uuid_to_sensor:
                    return uuid_to_sensor[data]
                return data

    def get_prefix_map(self) -> Dict[str, str]:
            """
            Returns a mapping of prefixes to URIs from add_sparql_prefixes.
            """
            prefixes = [
                ("brick", "https://brickschema.org/schema/Brick#"),
                ("dcterms", "http://purl.org/dc/terms/"),
                ("owl", "http://www.w3.org/2002/07/owl#"),
                ("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#"),
                ("rdfs", "http://www.w3.org/2000/01/rdf-schema#"),
                ("sh", "http://www.w3.org/ns/shacl#"),
                ("skos", "http://www.w3.org/2004/02/skos/core#"),
                ("sosa", "http://www.w3.org/ns/sosa/"),
                ("xsd", "http://www.w3.org/2001/XMLSchema#"),
                ("tag", "https://brickschema.org/schema/BrickTag#"),
                ("bldg", "http://abacwsbuilding.cardiff.ac.uk/abacws#"),
                ("bsh", "https://brickschema.org/schema/BrickShape#"),
                ("s223", "http://data.ashrae.org/standard223#"),
                ("bacnet", "http://data.ashrae.org/bacnet/2020#"),
                ("g36", "http://data.ashrae.org/standard223/1.0/extensions/g36#"),
                ("qkdv", "http://qudt.org/vocab/dimensionvector/"),
                ("quantitykind", "http://qudt.org/vocab/quantitykind/"),
                ("qudt", "http://qudt.org/schema/qudt/"),
                ("rec", "https://w3id.org/rec#"),
                ("ref", "https://brickschema.org/schema/Brick/ref#"),
                ("s223tobrick", "https://brickschema.org/extension/brick_extension_interpret_223#"),
                ("schema1", "http://schema.org/"),
                ("unit", "http://qudt.org/vocab/unit/"),
                ("vcard", "http://www.w3.org/2006/vcard/ns#"),
            ]
            return {uri: prefix for prefix, uri in prefixes}
    def standardize_sparql_json(
        self, results: Dict, user_question: str, sensor_type: str
    ) -> Dict:
        """
        Converts SPARQL JSON to a standardized format with prefixed URIs.
        """
        prefix_map = self.get_prefix_map()
        standardized = {"question": user_question, "sensor": sensor_type, "results": []}

        if (
            not results
            or "results" not in results
            or "bindings" not in results["results"]
        ):
            return standardized

        bindings = results["results"]["bindings"]
        for binding in bindings:
            result_entry = {}
            for key, val in binding.items():
                value_type = val.get("type")
                value = val.get("value", "")
                if value_type == "uri":
                    for uri, prefix in prefix_map.items():
                        if value.startswith(uri):
                            value = f"{prefix}:{value[len(uri):]}"
                            break
                elif value_type == "literal":
                    lang = val.get("xml:lang")
                    if lang:
                        value = f"{value}@{lang}"
                result_entry[key] = value
            standardized["results"].append(result_entry)

        return standardized


    def summarize_response(self, standardized_json: Dict) -> Text:
        """
        Generate a summary using the Mistral model based on the standardized JSON.

        :param standardized_json: Dict containing question, sensor, and results from SPARQL.
        :return: A short summary as a string or None if an error occurs.
        """
        if not client:
            logger.error("Ollama client is not initialized.")
            return None
            
        # Add detailed logging of input data
        logger.info("======== SUMMARY INPUT DATA (ActionQuestionToBrickbot) ========")
        logger.info(f"Input data type: {type(standardized_json).__name__}")
        
        # Log sensor information
        sensor_info = standardized_json.get("sensor", "No sensor info")
        logger.info(f"Sensor info: {sensor_info}")
        
        # Load sensor mappings once and reuse
        sensor_mappings = self.load_sensor_mappings()
        logger.info(f"Loaded {len(sensor_mappings)} sensor mappings")
        
        # Check for UUIDs and their mappings in the data
        uuid_pattern = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
        json_str = json.dumps(standardized_json)
        uuids_found = uuid_pattern.findall(json_str)
        
        if uuids_found:
            logger.info(f"UUIDs found in SPARQL data: {uuids_found}")
            # Check if we have mappings for these UUIDs
            for uuid in uuids_found:
                if uuid in sensor_mappings:
                    logger.info(f"UUID {uuid} maps to sensor name: {sensor_mappings[uuid]}")
                    # Consider replacing UUID with sensor name in the data before sending to LLM
                else:
                    logger.info(f"UUID {uuid} has no mapping in sensor_uuids.txt")
        
        # Log a sample of the JSON (truncated if too large)
        sample_json = json.dumps(standardized_json, indent=2)
        if len(sample_json) > 500:
            logger.info(f"Data sample (truncated): {sample_json[:500]}...")
        else:
            logger.info(f"Data sample: {sample_json}")
        logger.info("===============================================================")

        question = standardized_json.get("question", "")
        
        # Replace any UUIDs with sensor names in the data before generating the prompt
        processed_json = standardized_json
        if uuids_found and sensor_mappings:
            processed_json = self.replace_uuids_with_sensor_types(standardized_json, sensor_mappings)
            logger.info("Replaced UUIDs with sensor names in data for summary")
        
        sparql_response = json.dumps(processed_json, indent=2)
        logger.debug(f"Summarization input - question: {question}")
        logger.debug(f"Summarization input - SPARQL response: {sparql_response}")

        prompt = (
            "Instructions: Read the following smart building data received over an ontology created using BrickSchema "
            "and SQL sensor data or analytics output received and provide a short summary.\n"
            f"Question: {question}\n"
            f"SPARQL Response: {sparql_response}\n\n"
            "Explanation:"
        )
        logger.debug(f"Generated prompt: {prompt}")

        try:
            logger.debug(
                "Sending prompt to the model 'mistral:latest' with max_tokens=150"
            )
            response = client.generate(
                model="mistral:latest", prompt=prompt, options={"max_tokens": 150}
            )
            logger.debug(f"Response received: {response}")

            summary = extract_text_from_llm_response(response)
            if not summary:
                logger.error("Unexpected response structure from summarization service")
                return None
            logger.debug(f"Extracted summary: {summary}")
            return summary

        except Exception as e:
            logger.exception(f"An error occurred while generating the summary: {e}")
            return None

    async def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any],
        ) -> List[Dict[Text, Any]]:
            correlation_id = new_correlation_id()
            plog = PipelineLogger(correlation_id, "QuestionToBrickbot")
            with plog.stage("extract_user_message"):
                raw_text = tracker.latest_message.get("text")
                # Guard against None (e.g., when action is executed via the deprecated /execute endpoint)
                if not isinstance(raw_text, str):
                    raw_text = ""
                user_question = raw_text.strip()
            if not user_question:
                dispatcher.utter_message(text="Sorry, I couldn't understand your query. Please try again.")
                return [SlotSet("sparql_error", True)]

            # Early exit for pure social / greeting intents to prevent unnecessary sensor requests
            intent_name = (tracker.latest_message.get("intent") or {}).get("name")
            plog.info("Intent detected", intent=intent_name)
            greeting_regex = re.compile(r"^(hi|hello|hey|hey there|hi there)$", re.IGNORECASE)
            if intent_name in {"greet", "goodbye", "thank", "thanks", "chitchat", "bot_challenge"} or greeting_regex.match(user_question.lower()):
                plog.info("Non-informational greeting/utility intent - skipping Brickbot pipeline")
                # Let normal Rasa responses (e.g., utter_greet) handle it; do not start sensor form
                return []

            sensor_types = tracker.get_slot("sensor_type") or []
            plog.info("Message received", question=user_question, sensor_types=sensor_types)

            # Canonicalize any provided sensor names before proceeding
            if sensor_types:
                try:
                    canon_list = self.canonicalize_sensor_names(sensor_types)
                    if canon_list and canon_list != sensor_types:
                        plog.info("Canonicalized sensors", before=sensor_types, after=canon_list)
                        sensor_types = canon_list
                except Exception as e:
                    plog.warning("Failed to canonicalize sensor names", error=str(e))

            # ---------------- Query Type Heuristics (fallback/combined) ----------------
            def detect_query_type(q: str) -> str:
                ql = q.lower()
                listing_patterns = [
                    r"\bwhat (are|r) the sensors\b",
                    r"\b(list|show|which) (all )?(available )?sensors\b",
                    r"\bsensors (in|at|for)\b",
                    r"\bwhere are the sensors\b",
                ]
                for pat in listing_patterns:
                    if re.search(pat, ql):
                        return "listing"
                metric_keywords = [
                    "value","reading","average","mean","max","min","trend","today","yesterday","compare","deviation","increase","decrease","correlate","correlation","anomaly","anomalies"
                ]
                if any(k in ql for k in metric_keywords):
                    return "metric"
                return "unknown"

            query_type = detect_query_type(user_question)
            needs_sensor = query_type == "metric" and not sensor_types
            plog.info("Heuristic classification", query_type=query_type, needs_sensor=needs_sensor, provided_sensor_types=len(sensor_types))

            # Always include an 'entity' parameter for NL2SPARQL.
            entity_string = ", ".join([f"bldg:{sensor}" for sensor in sensor_types]) if sensor_types else ""
            entity_value = (entity_string).strip() or " "
            input_data = {"question": user_question, "entity": entity_value}
            plog.info(
                "Prepared NL2SPARQL payload",
                nl2sparql_url=nl2sparql_url,
                entity_sent=entity_value,
                used_fallback=(entity_value == " ")
            )
            logger.info(f"Prepared NL2SPARQL payload (pre-sensor prompt decision): {input_data}")
            dispatcher.utter_message(text="Understanding your question...")

            with plog.stage("nl2sparql_translate"):
                response = self.query_service_requests(nl2sparql_url, input_data)
                plog.info("NL2SPARQL raw response keys", keys=list(response.keys()))
            # Accept multiple possible keys from NL2SPARQL service (e.g., 'sparql_query' or 'sparql')
            sparql_query = (
                response.get("sparql_query")
                or response.get("sparql")
                or response.get("SPARQL")
                or response.get("query")
            )
            translation_error = "error" in response or not bool(sparql_query)
            plog.info("Translation status", translation_error=translation_error)

            if translation_error:
                if needs_sensor:
                    # Only now ask for sensor type because translation failed AND we think it's metric
                    dispatcher.utter_message(response="utter_ask_sensor_type")
                    plog.info("Decision", action="prompt_sensor_type", reason="translation_failed_metric")
                    return [{"event": "active_loop", "name": "sensor_form"}, SlotSet("sparql_error", False)]
                # For listing or unknown queries, treat as translation failure outright
                dispatcher.utter_message(response="utter_translation_error")
                plog.info("Decision", action="translation_error_message")
                return [SlotSet("sparql_error", True), SlotSet("timeseries_ids", None)]

            # sparql_query already extracted above to tolerate different key names
            if not sparql_query:
                if needs_sensor:
                    dispatcher.utter_message(response="utter_ask_sensor_type")
                    plog.info("Decision", action="prompt_sensor_type", reason="empty_query_metric")
                    return [{"event": "active_loop", "name": "sensor_form"}, SlotSet("sparql_error", False)]
                dispatcher.utter_message(text="No valid SPARQL query returned. Please try again.")
                plog.info("Decision", action="abort_no_query")
                return [SlotSet("sparql_error", True), SlotSet("timeseries_ids", None)]

            logger.info(f"Generated SPARQL query: {sparql_query}")
            full_sparql_query = self.add_sparql_prefixes(sparql_query)
            with plog.stage("fuseki_query"):
                sparql_results = self.execute_sparql_query(full_sparql_query)
            if sparql_results is None:
                if needs_sensor:
                    dispatcher.utter_message(response="utter_ask_sensor_type")
                    plog.info("Decision", action="prompt_sensor_type", reason="sparql_exec_failed_metric")
                    return [{"event": "active_loop", "name": "sensor_form"}, SlotSet("sparql_error", False)]
                dispatcher.utter_message(text="Error executing SPARQL query. Please try again later.")
                plog.info("Decision", action="abort_sparql_execution")
                return [SlotSet("sparql_error", True), SlotSet("timeseries_ids", None)]

            with plog.stage("format_results"):
                formatted_results = self.format_sparql_results(sparql_results)
            dispatcher.utter_message(text=f"SPARQL query results:\n{formatted_results}")

            # Standardize results early so both listing and metric flows can reuse it
            with plog.stage("standardize"):
                standardized_json = self.standardize_sparql_json(
                    sparql_results,
                    user_question,
                    sensor_types[0] if sensor_types else "",
                )
            # Helpful log for debugging summarization input (truncated)
            try:
                _sample_std = json.dumps(standardized_json)
                if len(_sample_std) > 800:
                    _sample_std = _sample_std[:800] + "..."
                logger.info(f"Standardized JSON sample: {_sample_std}")
            except Exception:
                logger.info("Standardized JSON sample: <unserializable>")

            # ----- Listing Query Info -----
            if query_type == "listing":
                bindings = sparql_results.get("results", {}).get("bindings", []) if sparql_results else []
                count = len(bindings)
                plog.info("Listing evaluation", bindings_count=count)
                if count == 0:
                    dispatcher.utter_message(text="I couldn't find any sensors matching your listing request.")
                    plog.info("Decision", action="answer_listing_empty")
                    # Do not return; continue to non-timeseries summarization below
                # Build a concise list of sensor URIs or labels
                sensor_names = []
                for b in bindings:
                    # pick first uri or literal that looks like a sensor
                    candidates = [v.get("value") for v in b.values() if isinstance(v, dict) and v.get("value")]
                    if candidates:
                        sensor_names.append(candidates[0])
                # Deduplicate & truncate
                sensor_names = list(dict.fromkeys(sensor_names))
                preview = sensor_names[:25]
                dispatcher.utter_message(text="Sensors found (showing up to 25):\n" + "\n".join(preview))
                if len(sensor_names) > 25:
                    dispatcher.utter_message(text=f"... and {len(sensor_names)-25} more.")
                plog.info("Decision", action="answer_listing", total=len(sensor_names))
                # Do not return; continue to non-timeseries summarization below
            

            # If results empty and we still have no sensor types in a metric-style question, now ask for them
            empty_bindings = not sparql_results.get("results", {}).get("bindings") if sparql_results else True
            if empty_bindings and needs_sensor and not sensor_types:
                dispatcher.utter_message(text="I need to know which sensor type you're interested in (e.g., CO2_Level_Sensor_5.14).")
                plog.info("Decision", action="prompt_sensor_type", reason="empty_results_metric")
                return [{"event": "active_loop", "name": "sensor_form"}, SlotSet("sparql_error", False)]
            base_url = os.getenv("BASE_URL", BASE_URL_DEFAULT)
            user_safe, user_dir = get_user_artifacts_dir(tracker)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sparql_response_{timestamp}.json"
            output_file = os.path.join(user_dir, filename)
            try:
                with open(output_file, "w") as f:
                    json.dump(standardized_json, f, indent=2)
                json_url = f"{base_url}/artifacts/{user_safe}/{filename}"
                dispatcher.utter_message(
                    text="SPARQL results saved as JSON:",
                    attachment={"type": "json", "url": json_url, "filename": filename}
                )
            except (IOError, TypeError) as e:
                logger.error(f"Failed to save SPARQL JSON: {e}")
                dispatcher.utter_message(text="Error saving SPARQL results. Inline results above.")

            with plog.stage("extract_timeseries_ids"):
                uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
                timeseries_ids = [
                    r.get("timeseriesId") for r in standardized_json.get("results", [])
                    if r.get("timeseriesId") and uuid_pattern.match(r.get("timeseriesId"))
                ]
                has_timeseries = bool(timeseries_ids)
                plog.info("Timeseries detection", has_timeseries=has_timeseries, count=len(timeseries_ids))
            # Add these helpful debug logs
            logger.info(f"Deciding path - has_timeseries: {has_timeseries}, start_date: {tracker.get_slot('start_date')}, end_date: {tracker.get_slot('end_date')}")
            logger.info(f"Will proceed to {'timeseries processing' if has_timeseries else 'direct summary'} path")
            is_auto_date = False
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            today_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
            midnight_str = f"{today_str} 00:00:00"
            # Collect slot override events before 'events' is initialized
            _pre_slot_events: List[Dict[str, Any]] = []
            # Force date override if the latest message explicitly contains a range like "from DD/MM/YYYY to DD/MM/YYYY" or "YYYY-MM-DD to YYYY-MM-DD"
            try:
                latest_text = (tracker.latest_message or {}).get("text", "") or ""
                override = extract_date_range(latest_text)
                if override.get("start_date") and override.get("end_date"):
                    # Keep the user's literal format; we'll normalize later in ProcessTimeseries
                    sd_raw = override["start_date"]
                    ed_raw = override["end_date"]
                    _pre_slot_events.extend([SlotSet("start_date", sd_raw), SlotSet("end_date", ed_raw)])
                    plog.info("Overrode date slots from latest message", start_date=sd_raw, end_date=ed_raw)
            except Exception as _e:
                plog.warning("Date override detection failed", error=str(_e))

            # After extracting timeseries_ids:
            events = [SlotSet("sparql_error", False)]
            if _pre_slot_events:
                events.extend(_pre_slot_events)
            # Helper to prefer pending SlotSet values created in this turn
            def _pending_slot(name: str, default: Any = None) -> Any:
                try:
                    for ev in reversed(_pre_slot_events):
                        # Handle dict-shaped events
                        if isinstance(ev, dict):
                            if ev.get("event") == "slot" and ev.get("name") == name:
                                return ev.get("value", default)
                        else:
                            # Handle Rasa SlotSet event objects
                            if getattr(ev, "key", None) == name:
                                return getattr(ev, "value", default)
                except Exception:
                    pass
                return default
            # Query the unified decider to decide if analytics should be performed and which one
            perform_analytics = None
            decided_analytics = None
            if DECIDER_URL:
                try:
                    with plog.stage("decider"):
                        d_resp = requests.post(DECIDER_URL, json={"question": user_question}, timeout=6)
                    if d_resp.ok:
                        dj = d_resp.json()
                        perform_analytics = bool(dj.get("perform_analytics"))
                        decided_analytics = dj.get("analytics")
                        plog.info("Decider response", perform=perform_analytics, analytics=decided_analytics)
                    else:
                        plog.warning("Decider returned non-200", status=d_resp.status_code)
                except Exception as e:
                    plog.warning("Decider call failed", error=str(e))

            def _supported_types() -> set:
                return {
                    "analyze_failure_trends",
                    "analyze_sensor_status",
                    "analyze_air_quality_trends",
                    "analyze_hvac_anomalies",
                    "analyze_supply_return_temp_difference",
                    "analyze_air_flow_variation",
                    "analyze_sensor_trend",
                    "aggregate_sensor_data",
                    "analyze_air_quality",
                    "analyze_formaldehyde_levels",
                    "analyze_co2_levels",
                    "analyze_pm_levels",
                    "analyze_temperatures",
                    "analyze_humidity",
                    "analyze_temperature_humidity",
                    "detect_potential_failures",
                    "forecast_downtimes",
                    "correlate_sensors",
                }

            def _pick_type_from_context(q: str, sensors: List[str]) -> str:
                ql = (q or "").lower()
                s_join = " ".join(sensors).lower() if sensors else ""
                if "humid" in ql or "humid" in s_join:
                    return "analyze_humidity"
                if "temp" in ql or "temperature" in ql or "temp" in s_join or "temperature" in s_join:
                    return "analyze_temperatures"
                if "co2" in ql or "co2" in s_join:
                    return "analyze_co2_levels"
                if "pm" in ql or "particulate" in ql:
                    return "analyze_pm_levels"
                if any(k in ql for k in ["trend", "over time", "time series", "history", "timeline"]):
                    return "analyze_sensor_trend"
                if any(k in ql for k in ["correlate", "correlation", "relationship"]):
                    return "correlate_sensors"
                if any(k in ql for k in ["anomaly", "outlier", "abnormal", "fault", "failure"]):
                    return "detect_potential_failures"
                return "analyze_sensor_trend"

            def fallback_decide(q: str) -> Tuple[bool, str]:
                ql = (q or "").lower()
                # TTL-only questions → no analytics
                if any(k in ql for k in ["label","type","class","category","installed","location","where is","which sensors","list sensors","show sensors"]):
                    return False, ""
                return True, _pick_type_from_context(q, sensor_types)

            if perform_analytics is None:
                perform_analytics, decided_analytics = fallback_decide(user_question)
                plog.info("Fallback decider applied", perform=perform_analytics, analytics=decided_analytics)

            if has_timeseries and perform_analytics:
                # Use decided analytics (or fallback to average)
                # Treat 'none'/''/None as empty and map unknowns to supported defaults
                raw_choice = decided_analytics
                if isinstance(raw_choice, str) and raw_choice.strip().lower() in {"none", "", "no", "false", "n"}:
                    raw_choice = None
                selected_analytics = raw_choice or _pick_type_from_context(user_question, sensor_types)
                if selected_analytics not in _supported_types():
                    plog.warning("Unsupported analytics type from decider; using fallback", got=raw_choice, fallback=selected_analytics)
                events.append(SlotSet("timeseries_ids", timeseries_ids))
                events.append(SlotSet("analytics_type", selected_analytics))
                dispatcher.utter_message(text=f"Proceeding with analytics: {selected_analytics} on IDs: {timeseries_ids}")
            
                # Refresh date slots after potential override, preferring any pending SlotSets from this turn
                start_date_tracker = tracker.get_slot("start_date")
                end_date_tracker = tracker.get_slot("end_date")
                start_date = _pending_slot("start_date", start_date_tracker)
                end_date = _pending_slot("end_date", end_date_tracker)

                # Add after checking if both dates are present
                if start_date and end_date:
                    # Initialize SQL date variables
                    start_date_sql = None
                    end_date_sql = None
                    
                    # Convert any ISO format dates to SQL format before returning
                    if 'T' in start_date:
                        parsed_date = parse(start_date)
                        start_date_sql = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        events.append(SlotSet("start_date", start_date_sql))
                        logger.info(f"Converted ISO start_date to SQL format: {start_date_sql}")
                    else:
                        # Keep the original if not ISO format
                        start_date_sql = start_date
                        
                    if 'T' in end_date:
                        parsed_date = parse(end_date)
                        end_date_sql = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        events.append(SlotSet("end_date", end_date_sql))
                        logger.info(f"Converted ISO start_date to SQL format: {end_date_sql}")
                    else:
                        end_date_sql = end_date
                       
                    
                    # Add right before the summary is generated (around line 741):
                    logger.info("==================== Date Debug Information ====================")
                    logger.info(f"Final tracker start_date before summarization: {tracker.get_slot('start_date')}")
                    logger.info(f"Final tracker end_date before summarization: {tracker.get_slot('end_date')}")
                    logger.info(f"Final start_date before summarization: {start_date_sql if 'start_date_sql' in locals() else tracker.get_slot('start_date')}")
                    logger.info(f"Final end_date before summarization: {end_date_sql if 'end_date_sql' in locals() else tracker.get_slot('end_date')}")
                    logger.info(f"Auto-generated dates: {is_auto_date}")
                    logger.info("===============================================================")

                    # summary = self.summarize_response(standardized_json)
                    # if summary:
                    #     logger.info(f"Generated SPARQL summary: {summary}")
                    #     dispatcher.utter_message(text=f"Summary: {summary}")
                    # else:
                    #     logger.debug("No summary generated for SPARQL results")

                    # Trigger the downstream timeseries processing action now that we have IDs and dates
                    plog.info("Triggering FollowupAction for timeseries processing")
                    events.append(FollowupAction("action_process_timeseries"))
                    return events
                else:
                    # If dates are missing, use the form to collect them
                    dispatcher.utter_message(response="utter_ask_start_date")
                    events.append({"event": "active_loop", "name": "dates_form"})
                    plog.info("Requesting dates form", reason="dates_missing_timeseries")
                    return events
            else:
                # No UUIDs present: summarize SPARQL results directly without asking for dates
                with plog.stage("summarize_without_timeseries"):
                    summary = self.summarize_response(standardized_json)
                if summary:
                    logger.info(f"Generated SPARQL summary (without timeseries): {summary}")
                    dispatcher.utter_message(text=f"Summary: {summary}")
                else:
                    logger.debug("No summary generated for SPARQL results")
                    dispatcher.utter_message(text="I found information based on your query, but couldn't generate a summary.")
                return events
            
class ActionDebugEntities(Action):
    def name(self) -> Text:
        return "action_debug_entities"
        
    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Gather all latest message data
        latest_message = tracker.latest_message
        
        # Log the entire message for debugging
        logger.info(f"Latest message: {json.dumps(latest_message, indent=2)}")
        
        # Extract and display entities
        entities = latest_message.get("entities", [])
        entity_text = "Extracted entities:\n" + json.dumps(entities, indent=2)
        logger.info(entity_text)
        dispatcher.utter_message(text=entity_text)
        
        # Check for date entities specifically
        date_entities = [e for e in entities if e.get("entity") == "time"]
        if date_entities:
            dates_text = "Date entities found:\n" + json.dumps(date_entities, indent=2)
            dispatcher.utter_message(text=dates_text)
            logger.info(dates_text)
        else:
            dispatcher.utter_message(text="No date entities found!")
            logger.info("No date entities found!")
            
        # Show current slot values
        dispatcher.utter_message(text=f"Current start_date: {tracker.get_slot('start_date')}")
        dispatcher.utter_message(text=f"Current end_date: {tracker.get_slot('end_date')}")
        dispatcher.utter_message(text=f"Current sensor_type slot: {tracker.get_slot('sensor_type')}")
        
        return []

class ActionProcessTimeseries(Action):
    def name(self) -> Text:
        return "action_process_timeseries"

    def fetch_sql_data(
        self,
        timeseries_ids: Union[str, List[str]],
        start_date: str,
        end_date: str,
        database: str,
        table_name: str,
        db_config: Dict,
        return_json: bool = True
    ) -> Tuple[Union[str, Dict], Union[str, None]]:
        """
        NOTE: For bldg2 we use TimescaleDB (PostgreSQL/ThingsBoard tables) for timeseries.
        This MySQL helper is retained for compatibility with other buildings and legacy flows.

        Fetches sensor data for multiple timeseries IDs and dates dynamically.

        Parameters:
            timeseries_ids: Single UUID or list of UUIDs (e.g., '249a4c9c-fe31-4649-a119-452e5e8e7dc5').
            start_date: Start timestamp as a string, e.g., '2025-02-10 00:00:00'.
            end_date: End timestamp as a string, e.g., '2025-02-20 23:59:59'.
            database: Name of the database (e.g., 'sensordb').
            table_name: Name of the table (e.g., 'sensor_data').
            db_config: Dictionary containing database connection parameters (host, user, password, etc.).
            return_json: If True, returns results as a JSON string; otherwise, returns a Python dict.

        Returns:
            A tuple (results, error) where error is None if successful. Results are formatted as:
            {
                "column_1": [
                    {"datetime": "2025-02-10 05:31:59", "reading_value": 27.99},
                    ...
                ],
                "column_2": [
                    {"datetime": "2025-02-10 06:00:00", "reading_value": 28.10},
                    ...
                ],
                ...
            }
        """
        
        try:   
            # Ensure timeseries_ids is a list
            if isinstance(timeseries_ids, str):
                timeseries_ids = [timeseries_ids]
        
            # Validate inputs
            if not timeseries_ids or not all(isinstance(tid, str) for tid in timeseries_ids):
                return None, "Invalid or empty timeseries_ids provided"
            if not start_date or not end_date:
                return None, "Start_date and end_date must be provided"
            if not database or not table_name:
                return None, "Database and table_name must be provided"

            # Establish database connection (ensure port is an int and log config)
            try:
                eff_host = db_config.get("host")
                eff_port = db_config.get("port")
                # mysql.connector accepts int for port; env gives strings
                if isinstance(eff_port, str) and eff_port.isdigit():
                    db_config["port"] = int(eff_port)
                logger.info(f"Connecting to MySQL with host={eff_host}, port={db_config.get('port')}, db={db_config.get('database')}")
            except Exception as _e:
                logger.warning(f"Failed to normalize DB config before connect: {_e}")
            connection = mysql.connector.connect(**db_config)
            if not connection.is_connected():
                return None, "Failed to connect to the database"

            cursor = connection.cursor(dictionary=True)
            results = {}

            # Construct dynamic SQL query
            # Select `Datetime` and all timeseries IDs as columns (backtick-quoted for consistency)
            columns = ["`Datetime`"] + [f"`{tid}`" for tid in timeseries_ids]
            columns_str = ", ".join(columns)

            # IMPORTANT: Do NOT AND all columns with IS NOT NULL for multi-UUID — that drops rows where any series is null.
            # We only constrain the time window and later filter per-timeseries in Python.
            # When exactly one UUID is requested, adding IS NOT NULL is safe and matches common single-series queries.
            where_clause = "`Datetime` BETWEEN %s AND %s"
            if len(timeseries_ids) == 1:
                only = timeseries_ids[0]
                where_clause += f" AND `{only}` IS NOT NULL"

            # Build the full query with a stable ordering
            query = f"""
                SELECT {columns_str}
                FROM `{database}`.`{table_name}`
                WHERE {where_clause}
            """

            logger.info(f"Executing SQL query over window: {start_date} -> {end_date}; columns={len(timeseries_ids)}")
            # Execute query with parameters
            cursor.execute(query, (start_date, end_date))
            # Log the final SQL statement with parameters substituted (as executed by the connector)
            try:
                logger.info(f"SQL executed: {cursor.statement}")
            except Exception:
                # Fallback: log the template and parameters separately
                logger.info(f"SQL template: {query.strip()} | params: {(start_date, end_date)}")
            rows = cursor.fetchall()

            # Initialize results dictionary
            for tid in timeseries_ids:
                results[tid] = []

            # Process each row
            for row in rows:
                dt_value = row.get("Datetime")
                if dt_value and hasattr(dt_value, "strftime"):
                    dt_value = dt_value.strftime("%Y-%m-%d %H:%M:%S")

                # Add data for each timeseries ID
                for tid in timeseries_ids:
                    reading_value = row.get(tid)
                    # Skip NULLs here; different columns may be sparsely populated per row
                    if reading_value is None:
                        continue
                    # Convert to float where sensible; keep strings (e.g., enum) as-is
                    if isinstance(reading_value, Decimal):
                        reading_value = float(reading_value)
                    elif isinstance(reading_value, (int, float)):
                        reading_value = float(reading_value)
                    else:
                        # Try best-effort float conversion for numeric-looking strings
                        try:
                            reading_value = float(str(reading_value))
                        except Exception:
                            # leave non-numeric values (e.g., enums) as-is
                            pass
                    results[tid].append(
                        {"datetime": dt_value, "reading_value": reading_value}
                    )

            # Clean up
            cursor.close()
            connection.close()

            # Return results in the requested format
            if return_json:
                return json.dumps(results, indent=4), None
            return results, None

        except mysql.connector.Error as e:
            logger.error(f"MySQL error: {e}")
            return None, f"MySQL error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None, f"Unexpected error: {str(e)}"

    def load_sensor_mappings(self) -> Dict[str, str]:
        mappings: Dict[str, str] = {}
        try:
            candidates = [
                os.path.join(os.getcwd(), "sensor_uuids.txt"),
                os.path.join(os.getcwd(), "actions", "sensor_uuids.txt"),
                "./actions/sensor_uuids.txt",
            ]
            path = next((p for p in candidates if os.path.exists(p)), None)
            with open(path or "./actions/sensor_uuids.txt", "r") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        if line.strip() and not line.strip().startswith("#"):
                            parts = line.strip().split(",")
                            if len(parts) == 2:
                                name, uuid = parts
                                mappings[name] = uuid
                                mappings[uuid] = name
                            else:
                                logger.warning(
                                    f"Line {line_num}: Invalid format - expected 'name,uuid' but got: {line.strip()}"
                                )
                    except Exception as e:
                        logger.error(f"Error on line {line_num}: {e}")
            logger.info(f"Loaded {len(mappings)} sensor mappings")
        except FileNotFoundError:
            logger.error("sensor_uuids.txt not found")
            try:
                os.makedirs("./actions", exist_ok=True)
                with open("./actions/sensor_uuids.txt", "w") as f:
                    f.write("# Format: sensor_name,sensor_uuid\n")
                logger.info("Created empty sensor_uuids.txt file")
            except Exception as e:
                logger.error(f"Failed to create empty sensor_uuids.txt: {e}")
        return mappings

    def replace_uuids_with_sensor_types(self, data: Any, uuid_to_sensor: Dict[Text, Text]) -> Any:
            """Recursively replace UUIDs with sensor types in the data structure."""
            if isinstance(data, dict):
                return {k: self.replace_uuids_with_sensor_types(v, uuid_to_sensor) for k, v in data.items()}
            elif isinstance(data, list):
                return [self.replace_uuids_with_sensor_types(item, uuid_to_sensor) for item in data]
            elif isinstance(data, str) and data in uuid_to_sensor:
                return uuid_to_sensor[data]
            return data

    def build_nested_payload_from_sql(
        self,
        sql_results_dict: Dict[str, List[Dict[str, Any]]],
        group_label: str = "1",
        collapse_to_base: bool = True,
        add_base_aggregates: bool = True,
    ) -> Dict[str, Any]:
        """Convert flat SQL results keyed by UUID to nested payload keyed by human-readable names.

        Args:
            sql_results_dict: Mapping of uuid -> list of {datetime, reading_value}
            group_label: Outer group key (default "1")
            collapse_to_base: If True, strip numeric suffix after "_Sensor" so multiple
                instances (e.g., Zone_Air_Humidity_Sensor_5.01, _5.02) merge under the base
                key "Zone_Air_Humidity_Sensor"; if False, keep full specific names.

        Output shape:
        {
          "<group_label>": {
            "Sensor_Name": { "timeseries_data": [ {datetime, reading_value}, ... ] },
            ...
          }
        }
        """
        uuid_to_sensor = self.load_sensor_mappings()
        nested: Dict[str, Any] = {group_label: {}}
        # Helper to strip numeric suffixes like _5 or _5.01 after the _Sensor token
        suffix_re = re.compile(r"^(.*?_Sensor)(?:_[0-9]+(?:\.[0-9]+)?)?$")

        def add_series(key: str, series: List[Dict[str, Any]]):
            bucket = nested[group_label].setdefault(key, {"timeseries_data": []})
            try:
                bucket["timeseries_data"].extend(list(series or []))
            except Exception:
                bucket["timeseries_data"] = list(series or [])

        for uuid_key, series in sql_results_dict.items():
            sensor_name = uuid_to_sensor.get(uuid_key, uuid_key)

            if collapse_to_base:
                # Original behavior: collapse to base key only
                base_key = sensor_name
                if isinstance(sensor_name, str):
                    m = suffix_re.match(sensor_name)
                    if m:
                        base_key = m.group(1)
                add_series(base_key, series)
            else:
                # New behavior: keep full specific key and optionally also add base aggregate
                full_key = sensor_name
                add_series(full_key, series)
                if add_base_aggregates and isinstance(sensor_name, str):
                    m = suffix_re.match(sensor_name)
                    if m:
                        base_key = m.group(1)
                        # Avoid double-adding when full_key already equals base_key
                        if base_key != full_key:
                            add_series(base_key, series)

        return nested

    def build_canonical_analytics_payload(
        self,
        analytics_type: str,
        sql_results_dict: Dict[str, List[Dict[str, Any]]],
        sensor_types: List[str],
    ) -> Dict[str, Any]:
        """Build a single canonical analytics payload and replace UUIDs with human-readable names.

        Rules:
        - For correlate_sensors: keep series separate using FULL sensor names (with instance suffix)
          to avoid accidental merging. Keys are readable names instead of UUIDs.
        - For all other analytics: collapse multiple instances of the same base sensor under a
          single key like "Zone_Air_Humidity_Sensor" and merge timeseries_data.
        - If exactly one sensor type was requested by the user, include a sensor_key equal to the
          base sensor name to guide microservices.
        """
        # Correlation expects a flat mapping of series; use readable names to replace UUIDs
        if analytics_type == "correlate_sensors":
            uuid_to_sensor = self.load_sensor_mappings()
            readable_flat: Dict[str, Any] = {}
            for uuid_key, series in sql_results_dict.items():
                readable_key = uuid_to_sensor.get(uuid_key, uuid_key)
                # Keep full specific name (do not collapse)
                readable_flat[readable_key] = series
            return {"analysis_type": analytics_type, **readable_flat}

        # Default path varies per analysis for compatibility and clarity
        if analytics_type == "analyze_humidity":
            # For humidity we send specific sensor names (e.g., Zone_Air_Humidity_Sensor_5.01)
            # without base duplicates so artifacts show real device names and avoid double counting.
            nested_payload = self.build_nested_payload_from_sql(
                sql_results_dict,
                group_label="1",
                collapse_to_base=False,
                add_base_aggregates=False,
            )
        else:
            # For other analytics, preserve legacy expectation that keys are base names
            # (e.g., Zone_Air_Humidity_Sensor) to keep microservices compatible.
            nested_payload = self.build_nested_payload_from_sql(
                sql_results_dict,
                group_label="1",
                collapse_to_base=True,
                add_base_aggregates=False,
            )
        payload: Dict[str, Any] = {"analysis_type": analytics_type, **nested_payload}

        # If exactly one sensor_type provided by user, include its base key as sensor_key
        if isinstance(sensor_types, list) and len(sensor_types) == 1 and isinstance(sensor_types[0], str):
            m = re.match(r"^(.*?_Sensor)(?:_[0-9]+(?:\.[0-9]+)?)?$", sensor_types[0])
            base_key = m.group(1) if m else sensor_types[0]
            payload["sensor_key"] = base_key
        return payload

    def query_analytics_type(self, url: str, prompt: str) -> List[str]:
            """Query the T5 model endpoint to retrieve analytics types."""
            headers = {"Content-Type": "application/json"}
            payload = {"prompt": prompt}
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=20)
                response.raise_for_status()
                analytics_types = response.json()
                if isinstance(analytics_types, list):
                    return analytics_types
                logger.error(f"Unexpected response format from T5 endpoint: {analytics_types}")
                return []
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to query T5 endpoint: {e}")
                return []

    def summarize_response(self, standardized_json: Dict) -> Text:
        """
        Generate a summary using the Mistral model based on the standardized JSON.

        :param standardized_json: Dict containing question, sensor, and results from analytics.
        :return: A short summary as a string or None if an error occurs.
        """
        if not client:
            logger.error("Ollama client is not initialized.")
            return None
            
        # Add detailed logging of input data
        logger.info("======== SUMMARY INPUT DATA (ActionProcessTimeseries) ========")
        logger.info(f"Input data type: {type(standardized_json).__name__}")
        
        # Check if this is analytics response data
        if "analysis_type" in standardized_json:
            logger.info(f"Analysis type: {standardized_json.get('analysis_type')}")
        
        # Check for UUIDs and their mappings in the data
        uuid_pattern = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
        json_str = json.dumps(standardized_json)
        uuids_found = uuid_pattern.findall(json_str)
        
        # Load sensor mappings once and reuse
        sensor_mappings = self.load_sensor_mappings()
        logger.info(f"Loaded {len(sensor_mappings)} sensor mappings")
        
        if uuids_found:
            logger.info(f"UUIDs found in analytics data: {uuids_found}")
            # Check if we have mappings for these UUIDs
            for uuid in uuids_found:
                if uuid in sensor_mappings:
                    logger.info(f"UUID {uuid} maps to sensor name: {sensor_mappings[uuid]}")
                else:
                    logger.info(f"UUID {uuid} has no mapping in sensor_uuids.txt")
        
        # Log a sample of the JSON (truncated if too large)
        sample_json = json.dumps(standardized_json, indent=2)
        if len(sample_json) > 500:
            logger.info(f"Data sample (truncated): {sample_json[:500]}...")
        else:
            logger.info(f"Data sample: {sample_json}")
        logger.info("===============================================================")

        question = standardized_json.get("question", "")
        
        # Replace any UUIDs with sensor names in the data before generating the prompt
        processed_json = standardized_json
        if uuids_found and sensor_mappings:
            processed_json = self.replace_uuids_with_sensor_types(standardized_json, sensor_mappings)
            logger.info("Replaced UUIDs with sensor names in data for summary")
            
        analytics_json = json.dumps(processed_json, indent=2)
        logger.debug(f"Summarization input - question: {question}")
        logger.debug(f"Summarization input - analytics/SQL merged response: {analytics_json}")

        prompt = (
            "Instructions: You are summarizing smart building sensor analytics. "
            "Provide a concise, user-friendly explanation of the key findings. "
            "Highlight trends, anomalies, comparisons and any notable deviations.\n"
            f"Original Question: {question}\n"
            f"Analytics Data (JSON): {analytics_json}\n\n"
            "Summary:"  # Let model complete the summary
        )
        logger.debug(f"Generated analytics summarization prompt: {prompt[:700]}...")

        try:
            response = client.generate(
                model="mistral:latest",
                prompt=prompt,
                options={"max_tokens": 180}
            )
            summary = extract_text_from_llm_response(response)
            if not summary:
                logger.error("Unexpected response structure from analytics summarization service")
                return None
            summary = summary.strip()
            logger.info(f"Analytics summary generated ({len(summary)} chars)")
            return summary
        except Exception as e:
            logger.exception(f"Error generating analytics summary: {e}")
            return None
    
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        correlation_id = new_correlation_id()
        plog = PipelineLogger(correlation_id, "ProcessTimeseries")
        with plog.stage("collect_slots"):
            timeseries_ids = tracker.get_slot("timeseries_ids") or []
        start_date = tracker.get_slot("start_date")
        end_date = tracker.get_slot("end_date")
        sensor_types = tracker.get_slot("sensor_type") or []
        
        # Detailed logging of received values
        logger.info("==================== ActionProcessTimeseries.run ====================")
        logger.info(f"Timeseries IDs: {timeseries_ids}")
        logger.info(f"Raw start_date: '{start_date}', type: {type(start_date).__name__}")
        logger.info(f"Raw end_date: '{end_date}', type: {type(end_date).__name__}")
        logger.info(f"Sensor types: {sensor_types}")
        logger.info("=====================================================================")
        
        # Debug the entire tracker slots
        logger.info("All slots in tracker:")
        for slot_name, slot_value in tracker.slots.items():
            if slot_value is not None:
                logger.info(f"  {slot_name}: {slot_value} ({type(slot_value).__name__})")
        logger.info(f"Timeseries IDs: {timeseries_ids}, Start date: {start_date}, End date: {end_date}, Sensor types: {sensor_types}")
       # Inside ActionProcessTimeseries class, modify the date processing part in run() method
        try:
            with plog.stage("normalize_dates"):
                # Initialize before date parsing
                start_date_sql = None
                end_date_sql = None
                # Log the date formats received
                logger.info(f"Processing dates - start: {start_date}, end: {end_date}")
            
            # Handle empty or None values
            if not start_date:
                dispatcher.utter_message(response="utter_ask_start_date")
                return [{"event": "active_loop", "name": "dates_form"}]
                
            if not end_date:
                dispatcher.utter_message(response="utter_ask_end_date")
                return [{"event": "active_loop", "name": "dates_form"}]
            #  NEW CODE: Handle Duckling dictionary format with from/to values
            if isinstance(start_date, dict) and 'from' in start_date:
                start_date = start_date['from']
                logger.info(f"Extracted 'from' value from start_date dictionary: {start_date}")
            
            if isinstance(end_date, dict) and 'to' in end_date:
                end_date = end_date['to']
                logger.info(f"Extracted 'to' value from end_date dictionary: {end_date}")
            # Convert start_date to SQL datetime format (YYYY-MM-DD HH:MM:SS)
            if isinstance(start_date, str):
                # Handle ISO 8601 format (2025-04-29T05:05:00.000+01:00)
                if 'T' in start_date:
                    # Parse using dateutil which handles ISO 8601 well
                    parsed_date = parse(start_date)
                    start_date_sql = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"Converted ISO start_date '{start_date}' to SQL format: '{start_date_sql}'")
                # Handle DD/MM/YYYY format
                elif re.match(r"^\d{2}/\d{2}/\d{4}$", start_date):
                    day, month, year = start_date.split('/')
                    start_date_sql = f"{year}-{month}-{day} 00:00:00"
                    logger.info(f"Converted start_date '{start_date}' to SQL format: '{start_date_sql}'")
                # Handle YYYY-MM-DD format
                elif re.match(r"^\d{4}-\d{2}-\d{2}$", start_date):
                    start_date_sql = f"{start_date} 00:00:00"
                    logger.info(f"Added time to start_date: '{start_date_sql}'")
                # Try parsing any other format
                else:
                    parsed_date = dateparser.parse(start_date)
                    if parsed_date:
                        start_date_sql = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        logger.info(f"Parsed start_date '{start_date}' to SQL format: '{start_date_sql}'")
                    else:
                        # Last resort: try with dateutil
                        parsed_date = parse(start_date)
                        start_date_sql = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                        logger.info(f"Parsed start_date with dateutil to: '{start_date_sql}'")
            
            # Convert end_date to SQL datetime format (YYYY-MM-DD HH:MM:SS)
            if isinstance(end_date, str):
                # If time-of-day is included anywhere, try to preserve it rather than forcing EOD
                has_time = bool(re.search(r"\d{2}:\d{2}:\d{2}|T\d{2}:\d{2}", end_date))
                # Handle ISO 8601 format (2025-04-29T05:05:00.000+01:00)
                if 'T' in end_date:
                    parsed_date = parse(end_date)
                    end_date_sql = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"Converted ISO end_date '{end_date}' to SQL format: '{end_date_sql}'")
                # Handle DD/MM/YYYY format
                elif re.match(r"^\d{2}/\d{2}/\d{4}$", end_date):
                    day, month, year = end_date.split('/')
                    end_date_sql = f"{year}-{month}-{day} {'23:59:59' if not has_time else '00:00:00'}"
                    logger.info(f"Converted end_date '{end_date}' to SQL format: '{end_date_sql}'")
                # Handle YYYY-MM-DD format
                elif re.match(r"^\d{4}-\d{2}-\d{2}$", end_date):
                    end_date_sql = f"{end_date} {'23:59:59' if not has_time else '00:00:00'}"
                    logger.info(f"Added time to end_date: '{end_date_sql}'")
                # Try parsing any other format
                else:
                    parsed_date = dateparser.parse(end_date)
                    if parsed_date:
                        end_date_sql = parsed_date.strftime("%Y-%m-%d %H:%M:%S" if has_time else "%Y-%m-%d 23:59:59")
                        logger.info(f"Parsed end_date '{end_date}' to SQL format: '{end_date_sql}'")
                    else:
                        parsed_date = parse(end_date)
                        end_date_sql = parsed_date.strftime("%Y-%m-%d %H:%M:%S" if has_time else "%Y-%m-%d 23:59:59")
                        logger.info(f"Parsed end_date with dateutil: '{end_date_sql}'")
            # After all your date parsing logic:
            if start_date_sql is None or end_date_sql is None:
                logger.error("Failed to convert dates to SQL format")
                dispatcher.utter_message(text="There was an error processing the date formats.")
                return []
            # Enforce a sane window: ensure end > start; if equal, extend end to end-of-day or +1s
            try:
                _sd = parse(start_date_sql)
                _ed = parse(end_date_sql)
                if _ed <= _sd:
                    # If only dates (00:00:00 times), bump end to end-of-day
                    if _sd.strftime("%H:%M:%S") == "00:00:00" and _ed.strftime("%H:%M:%S") == "00:00:00":
                        end_date_sql = _sd.strftime("%Y-%m-%d") + " 23:59:59"
                    else:
                        # Add a 1-second epsilon
                        end_date_sql = (_sd + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"Adjusted end_date_sql to ensure end>start: {end_date_sql}")
            except Exception as _e:
                logger.warning(f"Could not normalize date window strictly: {_e}")
        except ValueError as e:
            logger.error(f"Error parsing dates: {e}")
            dispatcher.utter_message(text="Invalid date format. Please provide dates in DD/MM/YYYY format.")
            return []

        # Continue with the rest of the code using start_date_sql and end_date_sql
        # TimescaleDB (PostgreSQL) fetch via ThingsBoard tables ts_kv and ts_kv_dictionary
        # Assume timeseries_ids are sensor UUID strings used as telemetry keys.
        def _pg_cfg() -> Dict[str, Any]:
            return {
                "host": os.getenv("PG_HOST", "timescaledb"),
                "port": int(os.getenv("PG_PORT", "5432")),
                "database": os.getenv("PG_DATABASE", "thingsboard"),
                "user": os.getenv("PG_USER", "thingsboard"),
                "password": os.getenv("PG_PASSWORD", "thingsboard"),
                "sslmode": os.getenv("PG_SSLMODE", "disable"),
            }

        # Convert the SQL-formatted timestamps to epoch ms for TB storage
        def _to_epoch_ms(s: str, end_of_day_if_date: bool = False) -> int:
            dt = parse(s)
            # if only date was provided, add end-of-day when requested
            if end_of_day_if_date and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                dt = dt.replace(hour=23, minute=59, second=59)
            epoch = datetime(1970, 1, 1)
            return int((dt - epoch).total_seconds() * 1000)

        try:
            import psycopg2
            import psycopg2.extras
        except Exception as e:
            logger.error(f"psycopg2 not available in action server image: {e}")
            dispatcher.utter_message(text="TimescaleDB driver not available. Please ensure psycopg2-binary is installed.")
            return []

        start_ms = _to_epoch_ms(start_date_sql, end_of_day_if_date=False)
        end_ms = _to_epoch_ms(end_date_sql, end_of_day_if_date=True)

        cfg = _pg_cfg()
        device_name = os.getenv("TB_DEVICE_NAME")
        device_id = os.getenv("TB_DEVICE_ID")

        def _resolve_device(conn, name: Optional[str], did: Optional[str]) -> Optional[str]:
            if did:
                return did
            if not name:
                return None
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute("SELECT id FROM device WHERE name = %s LIMIT 1", (name,))
                    row = cur.fetchone()
                    return row["id"] if row else None
            except Exception as e:
                logger.warning(f"Failed to resolve device '{name}': {e}")
                return None

        def _resolve_devices_by_tokens(conn, tokens: List[str]) -> List[Dict[str, str]]:
            """Resolve a list of ThingsBoard access tokens to device UUIDs (entity_ids).

            Returns a list of dicts with keys: id (UUID), name (device name), token (credentials_id).
            """
            out: List[Dict[str, str]] = []
            if not tokens:
                return out
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # Filter only ACCESS_TOKEN credentials type to avoid other kinds
                    cur.execute(
                        """
                        SELECT d.id, d.name, dc.credentials_id AS token
                        FROM device d
                        JOIN device_credentials dc ON d.id = dc.device_id
                        WHERE dc.credentials_type = 'ACCESS_TOKEN' AND dc.credentials_id = ANY(%s)
                        """,
                        (tokens,)
                    )
                    for row in cur.fetchall() or []:
                        out.append({"id": str(row["id"]), "name": row.get("name"), "token": row.get("token")})
            except Exception as e:
                logger.warning(f"Failed to resolve devices by tokens: {e}")
            return out

        def _lookup_key_ids(conn, keys: List[str]) -> Dict[str, int]:
            if not keys:
                return {}
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT key, key_id FROM ts_kv_dictionary WHERE key = ANY(%s)", (keys,))
                rows = cur.fetchall() or []
            return {r["key"]: int(r["key_id"]) for r in rows}

        def _fetch(conn, keys: List[str], start_ms: int, end_ms: int, entity_ids: Optional[List[str]]) -> Dict[str, List[Dict[str, Any]]]:
            out: Dict[str, List[Dict[str, Any]]] = {k: [] for k in keys}
            key_map = _lookup_key_ids(conn, keys)
            if not key_map:
                return out
            key_ids = list(key_map.values())
            params: List[Any] = [key_ids, start_ms, end_ms]
            where = ["d.key_id = ANY(%s)", "k.ts BETWEEN %s AND %s"]
            if entity_ids:
                # Filter across one or more device entity UUIDs
                where.append("k.entity_id = ANY(%s)")
                params.append(entity_ids)
            sql = f"""
                SELECT k.ts, d.key AS key, k.bool_v, k.long_v, k.dbl_v, k.str_v, k.json_v
                FROM ts_kv k
                JOIN ts_kv_dictionary d ON k.key = d.key_id
                WHERE {' AND '.join(where)}
                ORDER BY k.ts ASC
            """
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                for row in cur.fetchall() or []:
                    k = row["key"]
                    ts_ms = int(row["ts"]) if row["ts"] is not None else None
                    # choose numeric first, then bool, then string/json
                    val: Any = None
                    if row.get("dbl_v") is not None:
                        val = float(row["dbl_v"])
                    elif row.get("long_v") is not None:
                        val = float(row["long_v"])
                    elif row.get("bool_v") is not None:
                        val = 1.0 if row["bool_v"] else 0.0
                    elif row.get("str_v") is not None:
                        val = row["str_v"]
                    elif row.get("json_v") is not None:
                        val = row["json_v"]
                    if ts_ms is None or val is None:
                        continue
                    dt_iso = datetime.utcfromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d %H:%M:%S")
                    out.setdefault(k, []).append({"datetime": dt_iso, "reading_value": val})
            return out

        with plog.stage("pg_fetch"):
            try:
                conn = psycopg2.connect(
                    host=cfg["host"], port=cfg["port"], dbname=cfg["database"], user=cfg["user"], password=cfg["password"], sslmode=cfg.get("sslmode", "disable")
                )
            except Exception as e:
                logger.error(f"Failed to connect to TimescaleDB: {e}")
                dispatcher.utter_message(text=f"DB connection error: {e}")
                return []
            try:
                # 1) Try to read device tokens from slots or env and resolve to device IDs
                raw_tokens_slot = tracker.get_slot("device_tokens") or tracker.get_slot("access_tokens")
                tokens: List[str] = []
                if isinstance(raw_tokens_slot, list):
                    tokens = [str(t).strip() for t in raw_tokens_slot if str(t).strip()]
                elif isinstance(raw_tokens_slot, str):
                    tokens = [t.strip() for t in re.split(r"[,\s]+", raw_tokens_slot) if t.strip()]
                # Fallback to env var for tokens
                if not tokens:
                    env_tokens = os.getenv("TB_DEVICE_TOKENS", "").strip()
                    if env_tokens:
                        tokens = [t.strip() for t in re.split(r"[,\s]+", env_tokens) if t.strip()]

                entity_ids: Optional[List[str]] = None
                if tokens:
                    resolved = _resolve_devices_by_tokens(conn, tokens)
                    entity_ids = [r["id"] for r in resolved]
                    plog.info("Resolved devices by tokens", count=len(entity_ids))
                    if not entity_ids:
                        plog.warning("No devices found for provided tokens; falling back to TB_DEVICE_ID/NAME")

                # 2) If no tokens resolved, fall back to a single ID (env) or name
                if not entity_ids:
                    single_id = _resolve_device(conn, device_name, device_id)
                    if single_id:
                        entity_ids = [single_id]
                    elif device_name:
                        plog.warning("Device name not found; querying across all devices", device_name=device_name)

                # 3) Fetch data filtered by one or more device IDs if present
                data_by_uuid = _fetch(conn, list(timeseries_ids or []), start_ms, end_ms, entity_ids)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

        # Normalize into the same JSON shape as MySQL path produced
        sql_results = json.dumps(data_by_uuid, indent=2)

        dispatcher.utter_message(text="Timeseries query executed successfully.")
        base_url = os.getenv("BASE_URL", BASE_URL_DEFAULT)
        user_safe, user_dir = get_user_artifacts_dir(tracker)
        timestamp = int(time.time())
        filename = f"sql_results_{timestamp}.json"
        file_path = os.path.join(user_dir, filename)
        try:
            with open(file_path, "w") as f:
                json.dump(json.loads(sql_results), f, indent=2)
            json_url = f"{base_url}/artifacts/{user_safe}/{filename}"
            dispatcher.utter_message(
                text="SQL query results saved as JSON:",
                attachment={"type": "json", "url": json_url, "filename": filename}
            )
            # dispatcher.utter_message(text=f"SQL query results:\n{json.dumps(json.loads(sql_results), indent=2)}")
            logger.info(f"SQL results saved to {file_path}")
        except (IOError, TypeError) as e:
            logger.error(f"Failed to save SQL JSON: {e}")
            dispatcher.utter_message(text="Error saving SQL results. Inline results above.")

        # Analytics (optional) and summarization
        # Prefer analytics type chosen upstream in ActionQuestionToBrickbot
        analytics_type = tracker.get_slot("analytics_type")
        def _supported_types() -> set:
            return {
                "analyze_failure_trends",
                "analyze_sensor_status",
                "analyze_air_quality_trends",
                "analyze_hvac_anomalies",
                "analyze_supply_return_temp_difference",
                "analyze_air_flow_variation",
                "analyze_sensor_trend",
                "aggregate_sensor_data",
                "analyze_air_quality",
                "analyze_formaldehyde_levels",
                "analyze_co2_levels",
                "analyze_pm_levels",
                "analyze_temperatures",
                "analyze_humidity",
                "analyze_temperature_humidity",
                "detect_potential_failures",
                "forecast_downtimes",
                "correlate_sensors",
            }
        def _pick_type_from_context(question: str, sensors: List[str]) -> str:
            ql = (question or "").lower()
            s_join = " ".join(sensors).lower() if sensors else ""
            if "humid" in ql or "humid" in s_join:
                return "analyze_humidity"
            if "temp" in ql or "temperature" in ql or "temp" in s_join or "temperature" in s_join:
                return "analyze_temperatures"
            if "co2" in ql or "co2" in s_join:
                return "analyze_co2_levels"
            if "pm" in ql or "particulate" in ql:
                return "analyze_pm_levels"
            if any(k in ql for k in ["trend", "over time", "time series", "history", "timeline"]):
                return "analyze_sensor_trend"
            if any(k in ql for k in ["correlate", "correlation", "relationship"]):
                return "correlate_sensors"
            if any(k in ql for k in ["anomaly", "outlier", "abnormal", "fault", "failure"]):
                return "detect_potential_failures"
            return "analyze_sensor_trend"

        # Normalize invalid or 'none' values and select a supported default
        if isinstance(analytics_type, str) and analytics_type.strip().lower() in {"none", "", "no", "false", "n"}:
            analytics_type = None
        if not analytics_type or analytics_type not in _supported_types():
            # Use latest question from slots if available for context
            question = (tracker.latest_message or {}).get("text") or ""
            fallback_type = _pick_type_from_context(question, sensor_types)
            if analytics_type and analytics_type not in _supported_types():
                plog.warning("analytics_type not supported; falling back", got=analytics_type, fallback=fallback_type)
            analytics_type = fallback_type
        plog.info("Analytics type selected", analysis=analytics_type)
        ANALYTICS_URL = os.getenv("ANALYTICS_URL", "")

        # Parse the SQL results from string to dictionary
        sql_results_dict = json.loads(sql_results)

        # Build a canonical payload with human-readable names (UUIDs replaced) before saving/sending
        payload = self.build_canonical_analytics_payload(
            analytics_type=analytics_type,
            sql_results_dict=sql_results_dict,
            sensor_types=sensor_types,
        )
        analytics_response = payload

        # Save the analytics payload as an artifact for debugging/traceability
        try:
            nested_name = f"analytics_payload_{timestamp}.json"
            nested_path = os.path.join(user_dir, nested_name)
            with open(nested_path, "w") as nf:
                json.dump(payload, nf, indent=2)
            nested_url = f"{base_url}/artifacts/{user_safe}/{nested_name}"
            dispatcher.utter_message(
                text="Prepared analytics payload (nested):",
                attachment={"type": "json", "url": nested_url, "filename": nested_name}
            )
        except Exception as e:
            logger.warning(f"Failed to save analytics payload artifact: {e}")
        if ANALYTICS_URL:
            with plog.stage("analytics_call"):
                try:
                    resp = requests.post(ANALYTICS_URL, json=payload, timeout=30)
                    try:
                        analytics_response = resp.json()
                        if "error" in analytics_response:
                            logger.error(f"Analytics error: {analytics_response['error']}")
                            dispatcher.utter_message(text=f"Analytics error: {analytics_response['error']}")
                        else:
                            dispatcher.utter_message(text="Analytics results:")
                            # Keep output compact; attach full JSON as artifact if needed later
                            try:
                                preview = json.dumps(analytics_response)
                                if len(preview) > 1200:
                                    preview = preview[:1200] + "..."
                                dispatcher.utter_message(text=preview)
                            except Exception:
                                dispatcher.utter_message(text="<unserializable analytics JSON>")
                            logger.info(f"Analytics response: {analytics_response}")
                    except ValueError as e:
                        logger.error(f"Invalid JSON response from analytics service: {e}")
                        dispatcher.utter_message(text="Error: Invalid response format from analytics service")
                except Exception as e:
                    logger.error(f"Failed to query analytics service: {e}")
                    dispatcher.utter_message(text="Error querying analytics service. Using SQL results for summary.")
        else:
            plog.info("Skipping analytics service", reason="ANALYTICS_URL_not_set")

        # start performing pre-processing for summary
        with plog.stage("uuid_replace"):
            uuid_to_sensor = self.load_sensor_mappings()
            if not uuid_to_sensor:
                dispatcher.utter_message(text="Error: Could not load sensor mappings. Using raw analytics data for summarization.")
            else:
                analytics_response = self.replace_uuids_with_sensor_types(analytics_response, uuid_to_sensor)
                logger.info(f"Modified analytics response with sensor types: {analytics_response}")

        # start performing summary
        with plog.stage("summarize_timeseries"):
            summary = self.summarize_response(analytics_response)
        logger.info(f"Generated summary: {summary}")
        dispatcher.utter_message(text=f"Summary: {summary}" if summary else "Unable to generate summary.")

        return []

class ActionResetSlots(Action):
    def name(self) -> Text:
        return "action_reset_slots"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        return [
            SlotSet("sensor_type", None),
            SlotSet("analytics_type", None),
            SlotSet("start_date", None),
            SlotSet("end_date", None),
            SlotSet("timeseries_ids", None),
            SlotSet("request_dates", False),
            SlotSet("sparql_error", False),
        ]

# ---------------------------
# Action to test if the action server is working to give all format files
# ---------------------------
# Simple action to generate sample files in shared_data and share links
class ActionGenerateAndShareData(Action):
    def name(self) -> Text:
        return "action_generate_and_share_data"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        events: List[Dict[Text, Any]] = []
        base_url = os.getenv("BASE_URL", BASE_URL_DEFAULT)
        user_safe, user_dir = get_user_artifacts_dir(tracker)
        bundle_media = os.getenv("BUNDLE_MEDIA", "true").lower() in ("1", "true", "yes")
        media_items: List[Dict[str, str]] = []

        # 0) Generate sample downloadable files and share links (as attachments for frontend)
        try:
            os.makedirs(user_dir, exist_ok=True)
            now = datetime.now()
            rid = now.strftime("%Y%m%d_%H%M%S")
            json_name = f"report_{rid}.json"
            txt_name = f"placeholder_{rid}.txt"  # using text placeholder to avoid image libs
            json_path = os.path.join(user_dir, json_name)
            txt_path = os.path.join(user_dir, txt_name)

            payload = {
                "report_id": rid,
                "generated_on": now.isoformat(),
                "user_id": tracker.sender_id,
                "message": "Sample data report generated by action server.",
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("This is a placeholder for an image file. Replace with real content.")

            json_url = f"{base_url}/artifacts/{user_safe}/{json_name}"
            txt_url = f"{base_url}/artifacts/{user_safe}/{txt_name}"

            # Queue media items for a single bundled message
            media_items.append({"type": "json", "url": json_url, "filename": json_name})
            media_items.append({"type": "txt", "url": txt_url, "filename": txt_name})

            events.append(SlotSet("generated_urls", {"json": json_url, "file": txt_url}))
        except Exception as e:
            logger.exception("Failed to generate/share files: %s", e)
            dispatcher.utter_message(text="Error generating sample files.")

        # Log working directory
        try:
            logger.info(f"Working directory: {os.getcwd()}")
        except Exception:
            pass

        # 1) Include an example image
        media_items.append({
            "type": "image",
            "url": "https://picsum.photos/800/400",
            "filename": "sample.jpg",
        })

        # 2) Additional remote image
        media_items.append({
            "type": "image",
            "url": "https://picsum.photos/200/300",
            "filename": "dummy.jpg",
        })

        # 3) Remote PNG image
        media_items.append({
            "type": "image",
            "url": "https://file-examples.com/storage/feb797b78b68ccdb5a1194c/2017/10/file_example_PNG_500kB.png",
            "filename": "dummy.png",
        })

        # 4) Remote PDF example
        media_items.append({
            "type": "pdf",
            "url": "https://file-examples.com/wp-content/storage/2017/10/file-sample_150kB.pdf",
            "filename": "dummy.pdf",
        })

        # 5) Send a dummy CSV file (generated locally for download via local server)
        try:
            csv_name = f"sample_{int(time.time())}.csv"
            csv_path = os.path.join(user_dir, csv_name)
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("timestamp,value\n")
                for i in range(5):
                    ts = (datetime.utcnow() - timedelta(minutes=5 - i)).strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{ts},{round(np.random.rand(), 4)}\n")
            csv_url = f"{base_url}/artifacts/{user_safe}/{csv_name}"
            media_items.append({"type": "csv", "url": csv_url, "filename": csv_name})
        except Exception as e:
            logger.error(f"Failed to generate CSV: {e}")
            dispatcher.utter_message(text="Note: Could not generate CSV file.")

        # 6) Send dummy JSON data (as a downloadable local file)
        try:
            dummy_json_name = f"dummy_{int(time.time())}.json"
            dummy_json_path = os.path.join(user_dir, dummy_json_name)
            with open(dummy_json_path, "w", encoding="utf-8") as f:
                json.dump({"key": "value", "number": 123}, f, indent=2)
            dummy_json_url = f"{base_url}/artifacts/{user_safe}/{dummy_json_name}"
            media_items.append({"type": "json", "url": dummy_json_url, "filename": dummy_json_name})
        except Exception as e:
            logger.error(f"Failed to generate dummy JSON: {e}")
            dispatcher.utter_message(text="Note: Could not generate dummy JSON file.")

        # 7) Video: try downloading a small mp4 locally for playback via localhost
        try:
            video_name = f"sample_{int(time.time())}.mp4"
            video_path = os.path.join(user_dir, video_name)
            video_url_src = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/1080/Big_Buck_Bunny_1080_10s_1MB.mp4"
            resp = requests.get(video_url_src, stream=True, timeout=15)
            resp.raise_for_status()
            with open(video_path, "wb") as vf:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        vf.write(chunk)
            media_items.append({
                "type": "video",
                "url": f"{base_url}/artifacts/{user_safe}/{video_name}",
                "filename": video_name,
            })
        except Exception as e:
            logger.warning(f"Failed to download sample video locally: {e}. Falling back to remote URL")
            media_items.append({
                "type": "video",
                "url": "https://file-examples.com/storage/feb797b78b68ccdb5a1194c/2017/04/file_example_MP4_640_3MG.mp4",
                "filename": "dummy_video.mp4",
            })

        # 8) Dummy link
        media_items.append({
            "type": "link",
            "url": "https://www.wikipedia.org/",
            "filename": "dummy_link.html",
        })

        # 9) Generate a small WAV audio locally for reliable playback
        try:
            wav_name = f"sample_{int(time.time())}.wav"
            wav_path = os.path.join(user_dir, wav_name)
            framerate = 22050
            duration_sec = 2
            freq = 440.0  # A4 tone
            nframes = int(duration_sec * framerate)
            amp = 16000
            with wave.open(wav_path, 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(framerate)
                for i in range(nframes):
                    value = int(amp * math.sin(2 * math.pi * freq * (i / framerate)))
                    wf.writeframesraw(struct.pack('<h', value))
            media_items.append({
                "type": "audio",
                "url": f"{base_url}/artifacts/{user_safe}/{wav_name}",
                "filename": wav_name,
            })
        except Exception as e:
            logger.warning(f"Failed to generate local WAV: {e}. Falling back to remote MP3")
            media_items.append({
                "type": "audio",
                "url": "https://file-examples.com/storage/fe560e508068ccbf398f4e7/2017/11/file_example_WAV_1MG.wav",
                "filename": "Your_audio.mp3",
            })

        # 10) Generate and share chart (HTML) and optionally serve a PDF if present
        try:
            timestamps = pd.date_range(start="2025-01-01", periods=50, freq="min")
            sensor_values = np.random.rand(50)
            data = pd.DataFrame({"timestamp": timestamps, "sensor_value": sensor_values})
            fig = px.line(data, x="timestamp", y="sensor_value", title="Live Sensor Data")

            static_folder = user_dir
            os.makedirs(static_folder, exist_ok=True)

            chart_name = f"chart_{int(time.time())}.html"
            chart_path = os.path.join(static_folder, chart_name)
            fig.write_html(chart_path)
            logger.info(f"HTML chart saved at: {chart_path}")

            html_url = f"{base_url}/artifacts/{user_safe}/{chart_name}"
            # Queue chart as html and as simple link
            media_items.append({"type": "html", "url": html_url, "filename": chart_name})
            media_items.append({"type": "link", "url": html_url, "filename": chart_name})

            # PDF file handling (serve if a dummy file exists in shared folder)
            pdf_filename = "dummy.pdf"
            pdf_file_path = os.path.join(static_folder, pdf_filename)
            if os.path.exists(pdf_file_path):
                pdf_url = f"{base_url}/artifacts/{user_safe}/{pdf_filename}"
                logger.info(f"PDF file served from: {pdf_url}")
                media_items.append({"type": "pdf", "url": pdf_url, "filename": pdf_filename})
            else:
                logger.warning(f"PDF file {pdf_file_path} not found")
                # Optional notice; skip adding to media_items
        except Exception as e:
            logger.error(f"Error generating chart/PDF: {str(e)}")
            dispatcher.utter_message(text="Error: Could not generate or serve chart/PDF.")

        # Finally, send output according to toggle
        if media_items:
            if bundle_media:
                dispatcher.utter_message(
                    text="Yes. It is working as expected. Here are your generated artifacts shows you can successfully download and see them:",
                    json_message={"media": media_items},
                )
            else:
                dispatcher.utter_message(text="Generated artifacts:")
                for m in media_items:
                    # Prefer attachment objects for frontend rendering
                    dispatcher.utter_message(attachment=m)

        return events

