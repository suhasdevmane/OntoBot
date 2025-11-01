"""
Pure ML-driven decider service (NO rule-based logic).
Uses predict_proba for confidence and top-N candidate predictions.
"""
import os
import json
import time
from typing import Optional, List, Dict, Any
from urllib.request import urlopen
from urllib.error import URLError

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import joblib


# =========================================
# CONFIGURATION
# =========================================
PERFORM_MODEL_PATH = os.getenv("PERFORM_MODEL_PATH", "model/perform_model.pkl")
PERFORM_VECT_PATH = os.getenv("PERFORM_VECT_PATH", "model/perform_vectorizer.pkl")
LABEL_MODEL_PATH = os.getenv("LABEL_MODEL_PATH", "model/label_model.pkl")
LABEL_VECT_PATH = os.getenv("LABEL_VECT_PATH", "model/label_vectorizer.pkl")

MICRO_BASE_URL = os.getenv("MICROSERVICES_BASE_URL", "http://microservices:6000")
REGISTRY_CACHE_TTL = int(os.getenv("REGISTRY_CACHE_TTL", "300"))

_REGISTRY_CACHE: Optional[Dict[str, Any]] = None
_REGISTRY_CACHE_TIME = 0


# =========================================
# PYDANTIC SCHEMAS
# =========================================
class DecideRequest(BaseModel):
    question: str = Field(..., description="User's natural language question")
    top_n: Optional[int] = Field(3, ge=1, le=10, description="Number of top candidates to return")


class Candidate(BaseModel):
    analytics: str = Field(..., description="Analytics function name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="ML model confidence")
    description: Optional[str] = Field(None, description="Function description from registry")


class DecideResponse(BaseModel):
    perform_analytics: bool = Field(..., description="Whether to perform analytics (ML decision)")
    analytics: Optional[str] = Field(None, description="Top analytics function (ML prediction)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="ML confidence for decision")
    candidates: List[Candidate] = Field(default_factory=list, description="Top-N candidates with confidence")


# =========================================
# MICROSERVICES REGISTRY (METADATA ONLY)
# =========================================
def _http_get_json(url: str, timeout: int = 5) -> Optional[dict]:
    """Fetch JSON from URL, return None on error."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            if resp.status == 200:
                return json.load(resp)
    except (URLError, json.JSONDecodeError, Exception):
        pass
    return None


def _get_registry_functions() -> List[Dict[str, Any]]:
    """
    Fetch analytics registry from microservices (metadata only, not for decision-making).
    Used ONLY to enrich response with descriptions.
    """
    global _REGISTRY_CACHE, _REGISTRY_CACHE_TIME
    
    now = time.time()
    if _REGISTRY_CACHE and (now - _REGISTRY_CACHE_TIME) < REGISTRY_CACHE_TTL:
        return _REGISTRY_CACHE
    
    data = _http_get_json(f"{MICRO_BASE_URL}/analytics/functions")
    if data and "functions" in data:
        _REGISTRY_CACHE = data["functions"]
        _REGISTRY_CACHE_TIME = now
        return _REGISTRY_CACHE
    
    return []


def _enrich_with_descriptions(candidates: List[Candidate]) -> List[Candidate]:
    """Add descriptions from registry to candidates (informational only)."""
    registry = _get_registry_functions()
    registry_map = {fn["name"]: fn.get("description", "") for fn in registry}
    
    for candidate in candidates:
        if not candidate.description and candidate.analytics in registry_map:
            candidate.description = registry_map[candidate.analytics]
    
    return candidates


# =========================================
# ML MODEL LOADING
# =========================================
def load_model(model_path: str, vect_path: str):
    """Load ML model and vectorizer."""
    if not os.path.exists(model_path) or not os.path.exists(vect_path):
        return None, None
    try:
        model = joblib.load(model_path)
        vectorizer = joblib.load(vect_path)
        return model, vectorizer
    except Exception:
        return None, None


# Load models at startup
perform_model, perform_vectorizer = load_model(PERFORM_MODEL_PATH, PERFORM_VECT_PATH)
label_model, label_vectorizer = load_model(LABEL_MODEL_PATH, LABEL_VECT_PATH)


# =========================================
# FASTAPI APP
# =========================================
app = FastAPI(title="Decider Service (Pure ML)", version="2.0")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the interactive HTML interface."""
    try:
        with open("app/static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Decider Service</h1><p>HTML interface not found. Use POST /decide endpoint.</p>",
            status_code=200
        )


@app.get("/health")
def health():
    """Health check with model and registry status."""
    registry = _get_registry_functions()
    return {
        "ok": True,
        "perform_model_loaded": perform_model is not None,
        "label_model_loaded": label_model is not None,
        "registry_count": len(registry),
        "mode": "pure_ml"
    }


@app.post("/decide", response_model=DecideResponse)
def decide(req: DecideRequest):
    """
    Pure ML-driven decision endpoint.
    NO rule-based logic, NO pattern overrides, ONLY ML predictions.
    """
    question = req.question.strip()
    top_n = req.top_n or 3
    
    # Validate models loaded
    if perform_model is None or label_model is None:
        raise HTTPException(
            status_code=503,
            detail="ML models not loaded. Train models first: python training/train.py"
        )
    
    # ========================================
    # STEP 1: ML PREDICT PERFORM_ANALYTICS
    # ========================================
    X_perform = perform_vectorizer.transform([question])
    perform_probs = perform_model.predict_proba(X_perform)[0]
    perform_classes = perform_model.classes_
    
    # Get probability for perform=1 (analytics)
    perform_idx = list(perform_classes).index(1) if 1 in perform_classes else 0
    perform_confidence = float(perform_probs[perform_idx])
    perform_decision = bool(perform_model.predict(X_perform)[0])
    
    # If ML says NO analytics, return immediately
    if not perform_decision:
        return DecideResponse(
            perform_analytics=False,
            analytics=None,
            confidence=1.0 - perform_confidence,  # Confidence in NOT performing
            candidates=[]
        )
    
    # ========================================
    # STEP 2: ML PREDICT ANALYTICS FUNCTION (TOP-N)
    # ========================================
    X_label = label_vectorizer.transform([question])
    label_probs = label_model.predict_proba(X_label)[0]
    label_classes = label_model.classes_
    
    # Get top-N predictions with confidence
    top_indices = label_probs.argsort()[-top_n:][::-1]
    
    candidates = []
    for idx in top_indices:
        analytics_name = label_classes[idx]
        confidence = float(label_probs[idx])
        
        # Skip 'none' or empty labels
        if analytics_name and analytics_name.lower() != "none":
            candidates.append(Candidate(
                analytics=analytics_name,
                confidence=confidence,
                description=None  # Will be enriched below
            ))
    
    # Enrich with registry descriptions (informational only)
    candidates = _enrich_with_descriptions(candidates)
    
    # Top candidate
    top_analytics = candidates[0].analytics if candidates else None
    top_confidence = candidates[0].confidence if candidates else 0.0
    
    # ========================================
    # RETURN PURE ML DECISION
    # ========================================
    return DecideResponse(
        perform_analytics=True,
        analytics=top_analytics,
        confidence=top_confidence,
        candidates=candidates
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=6009)
