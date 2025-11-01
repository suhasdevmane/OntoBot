# Pure ML Migration Guide

## Overview

This guide covers the migration from the hybrid ML+rules decider service to a **pure ML-driven approach**. The new implementation:

✅ Uses ONLY machine learning for all decisions  
✅ NO rule-based logic, NO pattern overrides, NO keyword matching  
✅ Confidence scores from `predict_proba` (not heuristics)  
✅ Top-N candidate predictions from ML probabilities  
✅ Training data auto-generated from microservices registry metadata  

---

## Architecture Changes

### Before (Hybrid)
```
User Query → is_ttl_only() → [Hard Override]
           ↓
           ML Perform Classifier → Pattern Override → Final Decision
           ↓
           ML Label Classifier → Pattern Scoring → Top Candidate
           ↓
           Heuristic Confidence Calculation
```

**Problems:**
- `is_ttl_only()` bypassed ML for listing queries
- `rule_based_decide()` fallback used hardcoded keywords
- `_score_candidates()` pattern matching influenced decisions
- Pattern scores overrode ML predictions (line 233-237)
- Confidence calculated from pattern matching, not ML

### After (Pure ML)
```
User Query → ML Perform Classifier (predict_proba)
           ↓
           [If perform=False, return immediately with confidence]
           ↓
           ML Label Classifier (predict_proba, top-N)
           ↓
           Return top candidates with ML confidence
           ↓
           [Registry used ONLY for enriching descriptions]
```

**Benefits:**
- Pure ML decision-making
- Confidence directly from `predict_proba`
- Top-N predictions from probability ranking
- Registry metadata informational only
- Fully trainable and improvable

---

## Migration Steps

### Step 1: Generate Training Data from Registry

```powershell
# Ensure microservices is running (for registry access)
docker-compose up -d microservices

# Wait for service to be healthy
Start-Sleep -Seconds 5

# Generate registry-based training data
cd decider-service/data
python generate_training_from_registry.py

# Expected output: registry_training.jsonl with 200+ examples
```

**What it does:**
- Fetches live analytics registry from microservices
- Generates 15 question variations per function from patterns/descriptions
- Creates 25 ontology-only examples (perform=0)
- Produces balanced training data

### Step 2: Merge Training Datasets

```powershell
# Merge existing + registry data, deduplicate, balance
cd decider-service/data
python merge_training_data.py

# Expected output: decider_training_full.jsonl with ~300-500 examples
```

**What it does:**
- Loads existing `decider_training.direct.jsonl` (manual examples)
- Loads generated `registry_training.jsonl`
- Deduplicates by normalized text
- Balances labels (max 25 per analytics function)
- Analyzes distribution (perform=0 vs perform=1, analytics labels)

### Step 3: Train Enhanced ML Models

```powershell
# Train models with predict_proba support
cd decider-service
python training/train.py --data data/decider_training_full.jsonl --test-split 0.2

# Expected output:
#   ✓ Saved perform model (train: 0.95+, test: 0.90+, avg confidence: 0.85+)
#   ✓ Saved label model (train: 0.85+, test: 0.75+, top-3: 0.90+, 13+ classes)
```

**What it does:**
- Train/test split (80/20) for validation
- Perform classifier: TF-IDF + LogisticRegression with class balancing
- Label classifier: Multi-class with balanced weights
- Saves models to `model/` directory
- Reports train/test accuracy, confidence, top-3 accuracy

**Key improvements:**
- Uses `predict_proba()` for confidence scores
- Evaluates top-N accuracy
- Class balancing to handle imbalanced data
- Higher max_features (5000) for better coverage

### Step 4: Update Decider Service

```powershell
# Replace main.py with pure ML version
cd decider-service/app
mv main.py main_hybrid_backup.py
mv main_ml_only.py main.py

# Rebuild and restart container
cd ../..  # Back to repo root
docker-compose build decider-service
docker-compose up -d decider-service

# Wait for startup
Start-Sleep -Seconds 5
```

**What changed:**
- Removed `is_ttl_only()` hard override
- Removed `rule_based_decide()` fallback
- Removed pattern override logic (lines 233-237)
- Confidence from `predict_proba`, not heuristics
- Top-N candidates from ML probabilities
- Registry used ONLY for description enrichment

### Step 5: Validate ML Decider

```powershell
# Run validation script with 17 test queries
cd decider-service
python validate_ml_decider.py

# Expected: 80%+ success rate (14+/17 tests passing)
```

**Test coverage:**
- Time-based analytics (time in range, duration above threshold)
- Ranking/aggregation (top N, highest/lowest values)
- Statistical (average, trend, standard deviation)
- Setpoint/threshold (difference, crossings)
- Anomaly/failure detection
- Correlation analysis
- Recalibration scheduling
- Peak detection
- Ontology queries (perform=0)

**Success criteria:**
- Perform decision matches expected (True/False)
- Predicted analytics in expected list (for perform=True)
- Confidence scores reasonable (>0.5 for correct predictions)
- Top-N candidates include expected function

---

## File Reference

### New Files

| File | Purpose |
|------|---------|
| `data/generate_training_from_registry.py` | Auto-generate training from microservices registry |
| `data/merge_training_data.py` | Merge, deduplicate, balance training datasets |
| `app/main_ml_only.py` | Pure ML decider (no rules) |
| `validate_ml_decider.py` | Validation script with 17 test queries |
| `ML_MIGRATION_GUIDE.md` | This guide |

### Modified Files

| File | Changes |
|------|---------|
| `training/train.py` | Added predict_proba, top-N, train/test split, class balancing |
| `app/main.py` | **Replaced** with pure ML version (backup as `main_hybrid_backup.py`) |

### Training Data

| File | Source | Examples |
|------|--------|----------|
| `decider_training.direct.jsonl` | Manual (existing) | ~50-100 |
| `registry_training.jsonl` | Auto-generated from registry | ~200-250 |
| `decider_training_full.jsonl` | Merged + deduplicated | ~300-500 |

---

## API Contract (Unchanged)

The decider service API remains backward-compatible with Rasa actions:

### Request
```json
{
  "question": "show me time in range for CO2 in the last week",
  "top_n": 3  // Optional, default 3
}
```

### Response
```json
{
  "perform_analytics": true,
  "analytics": "percentage_time_in_range",
  "confidence": 0.95,
  "candidates": [
    {
      "analytics": "percentage_time_in_range",
      "confidence": 0.95,
      "description": "Calculate percentage of time readings were within specified range"
    },
    {
      "analytics": "duration_in_range",
      "confidence": 0.82,
      "description": "Calculate total duration readings were within range"
    },
    {
      "analytics": "time_above_threshold",
      "confidence": 0.65,
      "description": null
    }
  ]
}
```

**Rasa actions.py compatibility:**
```python
# Existing code works unchanged
response = requests.post(DECIDER_URL, json={"question": user_question})
result = response.json()

if result["perform_analytics"]:
    analytics_type = result["analytics"]  # Top ML prediction
    confidence = result["confidence"]     # ML confidence from predict_proba
    # Proceed with analytics workflow
else:
    # Ontology-only query
```

---

## Improving Model Performance

### Add More Training Examples

If validation fails for specific query types:

1. **Manually add examples** to `data/decider_training.direct.jsonl`:
```json
{"text": "your question here", "perform": 1, "analytics": "function_name"}
{"text": "another variation", "perform": 1, "analytics": "function_name"}
```

2. **Regenerate from registry** with updated patterns in `microservices/blueprints/analytics_service.py`:
```python
@analytics_function(
    name="your_function",
    description="Clear description of what it does",
    patterns=[
        r"keyword1",
        r"keyword2.*variation",
        r"natural language phrase"
    ]
)
```

3. **Retrain**:
```powershell
cd decider-service
python data/generate_training_from_registry.py
python data/merge_training_data.py
python training/train.py --data data/decider_training_full.jsonl
docker-compose restart decider-service
python validate_ml_decider.py
```

### Tune Model Hyperparameters

Edit `training/train.py`:

```python
# Adjust TF-IDF features
TfidfVectorizer(
    ngram_range=(1, 3),      # Include trigrams
    min_df=1,                # Lower threshold for rare terms
    max_features=10000       # More features
)

# Adjust LogisticRegression
LogisticRegression(
    max_iter=2000,           # More iterations
    C=0.5,                   # Stronger regularization
    class_weight='balanced'  # Always keep this for imbalanced data
)
```

### Address Class Imbalance

If one analytics function dominates training data:

```powershell
# Check distribution
cd decider-service/data
python merge_training_data.py  # Shows label counts

# Adjust max_per_label in merge_training_data.py:
balanced_examples = balance_dataset(unique_examples, max_per_label=15)
```

---

## Troubleshooting

### Service Won't Start
```powershell
# Check logs
docker-compose logs decider-service

# Common issues:
# - Models not found → Train first: python training/train.py
# - Port conflict → Check PORTS.md, ensure 6009 available
# - Import errors → Rebuild: docker-compose build decider-service
```

### Low Validation Accuracy
```powershell
# Check training data quality
cd decider-service/data
python -c "
import json
with open('decider_training_full.jsonl') as f:
    data = [json.loads(line) for line in f if line.strip()]
    print(f'Total: {len(data)}')
    print(f'Perform=1: {sum(1 for d in data if d[\"perform\"] == 1)}')
    print(f'Perform=0: {sum(1 for d in data if d[\"perform\"] == 0)}')
"

# Expected: 60-80% perform=1, 20-40% perform=0
# If imbalanced, adjust merge_training_data.py

# Retrain with more data
python data/generate_training_from_registry.py
python data/merge_training_data.py
python training/train.py --data data/decider_training_full.jsonl --test-split 0.2
```

### Predictions Don't Match Expectations

1. **Check if function is in registry:**
```powershell
curl http://localhost:6001/analytics/functions | jq '.functions[].name'
```

2. **Check if function has good patterns/description:**
```python
# In microservices/blueprints/analytics_service.py
@analytics_function(
    name="function_name",
    description="Clear, detailed description with keywords",
    patterns=[
        r"specific.*pattern",
        r"another keyword phrase"
    ]
)
```

3. **Add manual training examples** for edge cases

### Confidence Scores Too Low

```python
# In training/train.py, try softer regularization
LogisticRegression(
    C=2.0,  # Less regularization (default 1.0)
    max_iter=2000
)
```

---

## Rollback Plan

If pure ML doesn't meet requirements:

```powershell
# Restore hybrid version
cd decider-service/app
mv main.py main_ml_only.py
mv main_hybrid_backup.py main.py

# Restart service
docker-compose restart decider-service
```

**When to rollback:**
- Validation accuracy <60%
- Critical business queries fail
- Confidence scores unreliable (<0.5 for correct predictions)
- Top-N doesn't include expected function

**When to iterate:**
- Validation accuracy 60-80% → Add more training data
- Specific analytics fail → Update registry patterns/descriptions
- Ontology queries get perform=True → Add more perform=0 examples

---

## Next Steps

Once migration is complete and validated:

1. **Integration Testing with Rasa:**
```powershell
# Test full workflow: decider → dates → SQL → analytics → summary
# See rasa-bldg*/actions/actions.py
```

2. **Monitor Production Performance:**
   - Log predictions vs actual user satisfaction
   - Collect edge cases for retraining
   - Track confidence score distribution

3. **Continuous Improvement:**
   - Weekly retrain with new examples
   - Quarterly review of registry metadata
   - A/B test model variants

4. **Documentation:**
   - Update DECIDER_SERVICE_ADDITION_SUMMARY.md
   - Update analytics.md with ML approach
   - Update QUICKSTART_GUI.md with validation steps

---

## Support

If you encounter issues:

1. **Check validation output** for specific failing queries
2. **Review training data distribution** for class imbalance
3. **Inspect registry metadata** for missing/poor descriptions
4. **Add manual examples** for critical business queries
5. **Retrain and validate** iteratively

**Success Criteria:**
- ✅ Validation accuracy ≥80% (14+/17 tests)
- ✅ Confidence ≥0.7 for correct predictions
- ✅ Top-3 includes expected function 90%+ of the time
- ✅ Rasa workflow integration works end-to-end
- ✅ No rule-based overrides in production code

---

**Version:** 2.0 (Pure ML)  
**Last Updated:** 2024  
**Author:** OntoBot Team
