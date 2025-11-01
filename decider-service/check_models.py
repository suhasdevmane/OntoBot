"""Quick script to check model metadata."""
import joblib

print("Loading models...")
pm = joblib.load('model/perform_model.pkl')
lm = joblib.load('model/label_model.pkl')

print(f'\nPerform model classes: {pm.classes_}')
print(f'Perform model n_features: {pm.n_features_in_}')

print(f'\nLabel model classes: {len(lm.classes_)} total')
print(f'First 10: {lm.classes_[:10].tolist()}')
print(f'Has analyze_device_deviation: {"analyze_device_deviation" in lm.classes_}')

# Check if the model has analyze_device_deviation
if "analyze_device_deviation" in lm.classes_:
    idx = list(lm.classes_).index("analyze_device_deviation")
    print(f'analyze_device_deviation is class index: {idx}')
