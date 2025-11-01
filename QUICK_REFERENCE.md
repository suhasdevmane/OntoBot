# 🚀 Quick Reference: ML Decider Service

## ✅ Current Status
- **117 functions** in registry (was 13)
- **Pure ML decider** deployed (no rules)
- **92% top-3 accuracy** (119 classes)
- **All tests passing** ✅

## 🎯 Test Endpoints

### Registry (117 functions)
```bash
curl http://localhost:6001/analytics/functions | jq '.functions | length'
# Returns: 117
```

### Decider (ML predictions)
```bash
curl -X POST http://localhost:6009/decide \
  -H "Content-Type: application/json" \
  -d '{"question": "analyze filter health"}'

# Returns:
# {
#   "perform_analytics": true,
#   "analytics": "analyze_filter_health",
#   "confidence": 0.493,
#   "candidates": [top 3 predictions with descriptions]
# }
```

## 🗑️ Clean Up Obsolete Files

```powershell
cd decider-service/data
Remove-Item add_all_functions_training.py
Remove-Item all_functions_training.jsonl
Remove-Item decider_training.direct.jsonl
Remove-Item decider_training.direct.jsonl.bak
```

## 🔄 Add New Function Workflow

1. **Add decorator** in `microservices/blueprints/analytics_service.py`:
   ```python
   @analytics_function(
       patterns=[r"pattern1", r"pattern2", ...],
       description="What it does"
   )
   def analyze_new_feature(sensor_data):
       ...
   ```

2. **Restart & retrain**:
   ```powershell
   docker-compose -f docker-compose.bldg1.yml restart microservices
   cd decider-service/data
   python generate_training_from_registry.py
   python merge_training_data.py
   cd ../training
   python train.py --data ../data/decider_training_full.jsonl
   cd ../..
   docker-compose -f docker-compose.bldg1.yml restart decider-service
   ```

## 📊 Performance
- Perform: **99.4%** test accuracy
- Label: **85.6%** test (119 classes)
- Top-3: **92.0%** accuracy

## 📚 Documentation
- `FINAL_SUMMARY_ML_DECIDER_COMPLETE.md` - Complete results
- `ANALYTICS_DECORATORS_COMPLETE.md` - Decorator details
- `CLEANUP_AND_DEPLOYMENT.md` - Deployment guide

## ✨ Key Achievement
**Pure ML approach with 117 functions, zero hardcoding!** 🎉
