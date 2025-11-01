"""Quick test of trained models with all 119 functions"""
import joblib
import os

MODEL_DIR = "../model"

# Load models
perform_model = joblib.load(os.path.join(MODEL_DIR, "perform_model.pkl"))
perform_vect = joblib.load(os.path.join(MODEL_DIR, "perform_vectorizer.pkl"))
label_model = joblib.load(os.path.join(MODEL_DIR, "label_model.pkl"))
label_vect = joblib.load(os.path.join(MODEL_DIR, "label_vectorizer.pkl"))

print("=" * 80)
print("MODEL TESTING - ALL 119 FUNCTIONS")
print("=" * 80)

print(f"\nPerform classifier classes: {perform_model.classes_}")
print(f"Label classifier has {len(label_model.classes_)} unique functions")
print(f"\nFirst 20 functions:")
for i, fn in enumerate(label_model.classes_[:20], 1):
    print(f"  {i}. {fn}")

# Test queries
test_queries = [
    "analyze recalibration frequency",
    "show me failure trends",
    "check filter health",
    "analyze chilled water flow",
    "predict maintenance for fans",
    "calculate cooling cop",
    "show energy usage intensity",
    "analyze economizer opportunity",
    "check damper performance",
    "analyze zone temperature",
]

print(f"\n{'-' * 80}")
print("TEST QUERIES")
print("-" * 80)

for query in test_queries:
    # Perform prediction
    X_perf = perform_vect.transform([query])
    perform_pred = perform_model.predict(X_perf)[0]
    perform_probs = perform_model.predict_proba(X_perf)[0]
    perform_conf = perform_probs[list(perform_model.classes_).index(perform_pred)]
    
    if perform_pred == 1:
        # Label prediction
        X_label = label_vect.transform([query])
        label_probs = label_model.predict_proba(X_label)[0]
        top_3_idx = label_probs.argsort()[-3:][::-1]
        top_3 = [(label_model.classes_[i], label_probs[i]) for i in top_3_idx]
        
        print(f"\nQ: {query}")
        print(f"   Perform: YES (conf={perform_conf:.3f})")
        print(f"   Top-3 predictions:")
        for i, (fn, conf) in enumerate(top_3, 1):
            print(f"     {i}. {fn} (conf={conf:.3f})")
    else:
        print(f"\nQ: {query}")
        print(f"   Perform: NO (conf={perform_conf:.3f})")

print(f"\n{'-' * 80}")
print(f"✓ Models loaded successfully with {len(label_model.classes_)} functions!")
print("=" * 80)
