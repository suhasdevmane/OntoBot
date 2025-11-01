# Decider Service

Single endpoint that decides whether to perform analytics for a user question and, if yes, which analytics function to apply.

Multi‑building deployment notes:
- Default host port (bldg1/2): `6009`
- Alternate host port (bldg3 variant): `6010`
- Internal DNS name inside Docker network: `decider-service:6009` (container port consistent)
- See root `README.md` isolation section if you need concurrent stacks.

- POST /decide
  - Request: { "question": "..." }
  - Response: { "perform_analytics": boolean, "analytics": string|null }

When ML models are absent, the service falls back to robust rule-based logic.

## Integration

- Action Server calls this service before analytics to determine if and what to run.
- If `perform_analytics` is false, the action crafts a non-analytics response.
- If true, the action posts a standardized payload to Analytics (`/analytics/run`) with the selected `analysis_type`.

## Training

1) Generate dataset from the T5 corpus:
- Run data/generate_decider_data.py to create data/decider_training.auto.jsonl

2) Train models:
- python training/train.py --data data/decider_training.auto.jsonl
- Models and vectorizers will be saved under decider-service/model/

## Run

Docker (standalone dev):

```powershell
docker build -t decider-service .
docker run -p 6009:6009 decider-service
```

Concurrent building test (example alt port):

```powershell
docker run -p 6010:6009 --name decider_bldg3 decider-service
```

Local (no Docker):

```powershell
uvicorn app.main:app --reload --port 6009
```

## Env overrides

- DECIDER_PERFORM_MODEL_PATH
- DECIDER_PERFORM_VECT_PATH
- DECIDER_LABEL_MODEL_PATH
- DECIDER_LABEL_VECT_PATH

## Customize for your building

- Extend training data with building-specific intents and phrasing.
- Define mapping from question categories to `analysis_type` aligned with your sensors and analytics.
- Keep a rule-based fallback for robustness when models are absent.

After adding new functions, **retrain decider service** to recognize them:

```powershell
cd decider-service

# 1. Generate new training data with your new analytics types
python data/generate_decider_data.py

# 2. Retrain models
python training/train.py --data data/decider_training.auto.jsonl

# 3. Rebuild & restart decider service
docker compose -f ../docker-compose.bldg1.yml build decider-service
docker compose -f ../docker-compose.bldg1.yml up -d decider-service
```