# Pure ML Decider - Quick Reference

## 🚀 Quick Start (One Command)

```powershell
pwsh -File c:\Users\suhas\Documents\GitHub\OntoBot\scripts\migrate-to-pure-ml.ps1
```

**What it does:** Generate training data → Train ML models → Update service → Validate

**Time:** 2-3 minutes

---

## ✅ Requirements Met

| Your Requirement | Implementation |
|-----------------|----------------|
| "Advanced ML approach to decide analytics function" | ✅ TF-IDF + LogisticRegression with predict_proba |
| "Use ALL functions from analytics_service.py" | ✅ Auto-generates training from registry (13+ functions) |
| "NO rule-based logic" | ✅ Removed all keyword matching, pattern overrides |
| "Boolean perform + which analytics" | ✅ Returns both with ML confidence |
| "Integrate with Rasa workflow" | ✅ Backward-compatible API |

---

## 📁 New Files (All Created)

| File | Purpose |
|------|---------|
| `decider-service/data/generate_training_from_registry.py` | Auto-gen training from registry |
| `decider-service/data/merge_training_data.py` | Merge & balance datasets |
| `decider-service/app/main_ml_only.py` | Pure ML service (no rules) |
| `decider-service/validate_ml_decider.py` | 17-query validation tests |
| `decider-service/ML_MIGRATION_GUIDE.md` | Full migration guide |
| `scripts/migrate-to-pure-ml.ps1` | Automated execution |

---

## 🔄 Manual Steps (If Needed)

```powershell
# 1. Generate training
cd decider-service/data
python generate_training_from_registry.py
python merge_training_data.py

# 2. Train models
cd ..
python training/train.py --data data/decider_training_full.jsonl

# 3. Update service
cd app
Copy-Item main.py main_hybrid_backup.py -Force
Copy-Item main_ml_only.py main.py -Force

# 4. Restart
cd ..\..
docker-compose build decider-service
docker-compose up -d decider-service

# 5. Validate
cd decider-service
python validate_ml_decider.py
```

---

## 🧪 Test Query Examples

```powershell
# Time-based
curl -X POST http://localhost:6009/decide -H "Content-Type: application/json" `
  -d '{"question": "show me time in range for CO2 in the last week"}'
# Expected: perform=true, analytics=percentage_time_in_range

# Ranking
curl -X POST http://localhost:6009/decide -H "Content-Type: application/json" `
  -d '{"question": "which sensors have the highest values"}'
# Expected: perform=true, analytics=top_n_by_latest

# Ontology (no analytics)
curl -X POST http://localhost:6009/decide -H "Content-Type: application/json" `
  -d '{"question": "list all temperature sensors"}'
# Expected: perform=false
```

---

## 📊 Expected Results

| Metric | Target | Actual (After Migration) |
|--------|--------|--------------------------|
| Validation accuracy | ≥80% | Check validate_ml_decider.py output |
| Confidence (correct) | ≥0.7 | Check response.confidence |
| Top-3 includes expected | ≥90% | Check response.candidates |
| Model loading | 100% | Check /health endpoint |

---

## 🔧 Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| Models not loading | `python training/train.py --data data/decider_training_full.jsonl` |
| Low accuracy (<60%) | Add examples to `data/decider_training.direct.jsonl`, remerge, retrain |
| Service won't start | `docker-compose logs decider-service` |
| Wrong predictions | Update patterns in `analytics_service.py`, regenerate, retrain |
| Microservices not running | `docker-compose up -d microservices` |

---

## 📈 Improving Performance

**Add new analytics function:**
```python
# In microservices/blueprints/analytics_service.py
@analytics_function(
    name="your_function",
    description="Clear description with keywords",
    patterns=[r"keyword1", r"phrase.*pattern"]
)
def your_function(data): pass
```

**Then:**
```powershell
cd decider-service/data
python generate_training_from_registry.py
python merge_training_data.py
cd ..
python training/train.py --data data/decider_training_full.jsonl
docker-compose restart decider-service
```

**Add manual examples:**
```json
// In data/decider_training.direct.jsonl
{"text": "your question", "perform": 1, "analytics": "function_name"}
```

**Then:**
```powershell
python data/merge_training_data.py
python training/train.py --data data/decider_training_full.jsonl
docker-compose restart decider-service
```

---

## 🔙 Rollback (If Needed)

```powershell
cd decider-service/app
Copy-Item main_hybrid_backup.py main.py -Force
docker-compose restart decider-service
```

---

## 📖 Full Documentation

| Document | Purpose |
|----------|---------|
| `ML_MIGRATION_GUIDE.md` | Detailed guide, troubleshooting |
| `PURE_ML_IMPLEMENTATION_COMPLETE.md` | Full summary, all changes |
| `validate_ml_decider.py` | Validation script source |

---

## ✨ Key Changes

### Removed (Rule-Based)
- ❌ `is_ttl_only()` - hard override
- ❌ `rule_based_decide()` - keyword fallback
- ❌ Pattern override logic (line 233-237)
- ❌ Heuristic confidence calculation

### Added (Pure ML)
- ✅ `predict_proba` for confidence scores
- ✅ Top-N predictions from probabilities
- ✅ Auto-training from registry metadata
- ✅ Balanced dataset generation
- ✅ Train/test split validation

---

## 🎯 Success Checklist

- [ ] Run migration script (`migrate-to-pure-ml.ps1`)
- [ ] Check health: `curl http://localhost:6009/health`
- [ ] Validate: 14+/17 tests passing
- [ ] Test with Rasa: send sample queries
- [ ] Monitor confidence scores (0.7-0.95)
- [ ] Review candidates list (top-3 includes expected)

---

## 🚨 Critical Differences

### Before (Hybrid)
```python
# Hard-coded rules
if is_ttl_only(question):
    return no_analytics

# Pattern matching
if pattern_score >= 0.75:
    override_ml_prediction()

# Heuristic confidence
confidence = pattern_score * 0.5 + ml_score * 0.5
```

### After (Pure ML)
```python
# Pure ML
perform_probs = perform_model.predict_proba(X)[0]
perform_decision = bool(perform_model.predict(X)[0])

label_probs = label_model.predict_proba(X)[0]
top_indices = label_probs.argsort()[-3:][::-1]

confidence = float(label_probs[top_indices[0]])
```

---

## 📞 Need Help?

1. Check validation output: `python validate_ml_decider.py`
2. Review logs: `docker-compose logs decider-service`
3. Read guide: `ML_MIGRATION_GUIDE.md`
4. Check health: `curl http://localhost:6009/health`
5. Test registry: `curl http://localhost:6001/analytics/functions`

---

**Everything is ready! Run the migration script and validate.** 🎉
