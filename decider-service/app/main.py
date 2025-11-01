from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
import os
import joblib
import time
import re
import json
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

app = FastAPI(title="Decider Service")

# Model paths (can be overridden via env)
PERFORM_MODEL_PATH = os.getenv("DECIDER_PERFORM_MODEL_PATH", "model/perform_model.pkl")
PERFORM_VECT_PATH = os.getenv("DECIDER_PERFORM_VECT_PATH", "model/perform_vectorizer.pkl")
LABEL_MODEL_PATH = os.getenv("DECIDER_LABEL_MODEL_PATH", "model/label_model.pkl")
LABEL_VECT_PATH = os.getenv("DECIDER_LABEL_VECT_PATH", "model/label_vectorizer.pkl")


class DecideRequest(BaseModel):
    question: str
    top_n: Optional[int] = 3


class Candidate(BaseModel):
    name: str
    score: float
    reason: Optional[str] = None


class DecideResponse(BaseModel):
    perform_analytics: bool
    analytics: Optional[str] = None
    confidence: Optional[float] = None
    candidates: Optional[List[Candidate]] = None


MICRO_BASE_URL = os.getenv("MICROSERVICES_BASE_URL", "http://microservices:6000")
REGISTRY_CACHE_TTL = int(os.getenv("REGISTRY_CACHE_TTL", "300"))  # seconds

_REGISTRY_CACHE: Dict[str, Any] = {"ts": 0.0, "functions": []}


def _http_get_json(url: str, timeout: float = 2.5) -> Dict[str, Any] | List[Dict[str, Any]]:
    req = urlrequest.Request(url, headers={"Accept": "application/json"})
    with urlrequest.urlopen(req, timeout=timeout) as resp:  # type: ignore
        data = resp.read().decode("utf-8")
        try:
            return json.loads(data)
        except Exception:
            return {}


def _get_registry_functions(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """Fetch analytics registry metadata from microservices and cache it.
    Expected response from /analytics/functions:
    { "functions": [ {"name": str, "description": str, "patterns": [regex...], "parameters": [...] } ], "count": n }
    """
    now = time.time()
    if (not force_refresh) and _REGISTRY_CACHE["functions"] and (now - _REGISTRY_CACHE["ts"] < REGISTRY_CACHE_TTL):
        return _REGISTRY_CACHE["functions"]
    url = f"{MICRO_BASE_URL.rstrip('/')}/analytics/functions"
    try:
        payload = _http_get_json(url)
        funcs = []
        if isinstance(payload, dict) and isinstance(payload.get("functions"), list):
            funcs = payload.get("functions", [])
        elif isinstance(payload, list):
            funcs = payload
        _REGISTRY_CACHE.update({"ts": now, "functions": funcs})
    except (URLError, HTTPError):
        # keep old cache
        pass
    return _REGISTRY_CACHE["functions"]


@app.get("/health")
async def health():
    funcs = _get_registry_functions(force_refresh=False)
    return {"ok": True, "registry_count": len(funcs)}


def rule_based_decide(q: str) -> Tuple[bool, Optional[str]]:
    """Simple keyword-based fallback when models are unavailable.
    Returns (perform_analytics, analytics_label or None).
    """
    ql = (q or "").lower()
    # TTL/ontology-only questions → no analytics
    if any(k in ql for k in [
        "label", "type", "class", "category", "installed", "location",
        "where is", "which sensors", "list sensors", "show sensors"
    ]):
        return False, None

    # Otherwise, assume analytics is desired and pick a label
    if any(k in ql for k in ["average", "avg", "mean"]):
        return True, "average"
    if any(k in ql for k in ["maximum", "max", "peak"]):
        return True, "max"
    if any(k in ql for k in ["minimum", "min", "lowest"]):
        return True, "min"
    if any(k in ql for k in ["trend", "trending", "over time", "time series"]):
        return True, "analyze_sensor_trend"
    if any(k in ql for k in ["anomaly", "outlier", "abnormal"]):
        return True, "detect_anomalies"
    if any(k in ql for k in ["correlate", "correlation", "relationship"]):
        return True, "correlate_sensors"
    if any(k in ql for k in ["sum", "total", "aggregate"]):
        return True, "sum"
    # Reasonable default when we think analytics is needed
    return True, "analyze_sensor_trend"


def is_ttl_only(q: str) -> bool:
    """Detect ontology/listing-only questions that shouldn't trigger analytics.
    This is applied as a hard override even when models are present to avoid
    running analytics for queries clearly about metadata or listings.
    """
    ql = (q or "").lower()
    # If clear analytics cues are present, do NOT treat as TTL-only
    analytics_cues = [
        "top", "highest", "lowest", "trend", "trending", "range",
        "compliance", "time in range", "deviation", "setpoint", "anomaly",
        "correlat", "forecast", "baseline", "slope", "rate of change",
    ]
    if any(cue in ql for cue in analytics_cues):
        return False
    # Quick keyword checks for ontology/listing-style prompts
    ttl_keywords = [
        "label", "type", "class", "category", "installed", "location",
        "where is", "where are",
    ]
    if any(k in ql for k in ttl_keywords):
        return True
    # Listing-style regex patterns (flexible word gaps)
    patterns = [
        r"\bwhat\s+(are|r)\s+the\s+sensors\b",
        r"\b(list|show|which)\b.*\bsensors?\b",
        r"\bsensors?\s+(in|at|for)\b",
        r"\bwhere\s+are\s+the\s+sensors\b",
    ]
    return any(re.search(p, ql) for p in patterns)


def load_model(path_model: str, path_vect: str):
    if os.path.exists(path_model) and os.path.exists(path_vect):
        model = joblib.load(path_model)
        vect = joblib.load(path_vect)
        return model, vect
    return None, None


PERFORM_MODEL, PERFORM_VECT = load_model(PERFORM_MODEL_PATH, PERFORM_VECT_PATH)
LABEL_MODEL, LABEL_VECT = load_model(LABEL_MODEL_PATH, LABEL_VECT_PATH)


def _score_candidates(question: str, functions: List[Dict[str, Any]]) -> List[Tuple[str, float, str]]:
    """Score registry functions against the question using regex patterns and simple textual cues.
    Returns list of (name, score, reason). Score in [0,1].
    """
    q = question or ""
    ql = q.lower()
    results: List[Tuple[str, float, str]] = []
    for f in functions:
        name = str(f.get("name"))
        desc = str(f.get("description") or "")
        patterns = f.get("patterns") or []
        score = 0.0
        reason = ""
        # 1) Regex pattern hits carry strong weight
        hit = False
        for pat in patterns:
            try:
                if re.search(pat, q, flags=re.IGNORECASE):
                    hit = True
                    break
            except re.error:
                # ignore bad patterns
                continue
        if hit:
            score = max(score, 0.8)
            reason = "pattern match"
        # 2) Token overlap with function name
        name_tokens = re.split(r"[_\-\s]+", name.lower())
        overlap = sum(1 for t in name_tokens if t and t in ql)
        if overlap:
            # normalize by token count
            score = max(score, min(0.6, overlap / max(1.0, len(name_tokens))))
            if not reason:
                reason = "name token overlap"
        # 3) Keyword overlap with description
        if desc:
            dtoks = [t for t in re.split(r"[^a-z0-9]+", desc.lower()) if len(t) > 3]
            dov = sum(1 for t in set(dtoks) if t in ql)
            if dov:
                score = max(score, min(0.5, dov / 10.0))
                if not reason:
                    reason = "description overlap"
        if score > 0:
            results.append((name, float(round(score, 4)), reason or "heuristic"))
    # sort by score desc, then name
    results.sort(key=lambda x: (-x[1], x[0]))
    return results


@app.post("/decide", response_model=DecideResponse)
async def decide(req: DecideRequest):
    global PERFORM_MODEL, PERFORM_VECT, LABEL_MODEL, LABEL_VECT

    # TTL/listing-only override: never perform analytics for these
    if is_ttl_only(req.question):
        return {"perform_analytics": False, "analytics": None, "confidence": 1.0, "candidates": []}

    # Fetch registry and score candidates using patterns/metadata
    funcs = _get_registry_functions(force_refresh=False)
    ranked = _score_candidates(req.question, funcs)
    top_n = int(req.top_n or 3)
    top_candidates = [
        {"name": n, "score": s, "reason": r}
        for (n, s, r) in ranked[:top_n]
    ]

    # Fallback logic if models missing
    if PERFORM_MODEL is None or PERFORM_VECT is None or LABEL_MODEL is None or LABEL_VECT is None:
        perform, label = rule_based_decide(req.question)
        # if we plan to perform but label not available, use top candidate if any
        if perform and (not label) and top_candidates:
            label = top_candidates[0]["name"]
        conf = (top_candidates[0]["score"] if top_candidates else (1.0 if not perform else 0.5))
        return {"perform_analytics": perform, "analytics": label, "confidence": conf, "candidates": top_candidates}

    # Predict perform_analytics (boolean)
    x_perf = PERFORM_VECT.transform([req.question])
    perform_pred = PERFORM_MODEL.predict(x_perf)[0]
    perform = bool(perform_pred)

    label: Optional[str] = None
    if perform:
        # Only predict label if we plan to perform analytics
        x_lab = LABEL_VECT.transform([req.question])
        label_pred = str(LABEL_MODEL.predict(x_lab)[0])
        # Prefer a known function from registry; if predicted label not in registry, fall back to top-ranked
        registry_names = {f.get("name") for f in funcs if f.get("name")}
        label = label_pred if label_pred in registry_names else (top_candidates[0]["name"] if top_candidates else label_pred)
        # Update candidates to include ML-pred on top if not present
        if label_pred and label_pred not in [c["name"] for c in top_candidates]:
            top_candidates = ([{"name": label_pred, "score": 0.65, "reason": "ml-pred"}] + top_candidates)[:top_n]
    else:
        # If ML says no but patterns strongly suggest analytics, override to perform
        if top_candidates and float(top_candidates[0]["score"]) >= 0.75:
            perform = True
            label = top_candidates[0]["name"]

    # Confidence heuristic: top score if available; else 0.5 for perform-only or 0.8 if both sources agree
    conf = None
    if top_candidates:
        conf = float(top_candidates[0]["score"])
        if label and label == top_candidates[0]["name"] and conf < 0.85:
            conf = round(min(0.95, conf + 0.15), 3)

    return {"perform_analytics": perform, "analytics": label, "confidence": conf, "candidates": top_candidates}
