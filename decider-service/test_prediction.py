"""Test the model prediction directly."""
import joblib

print("Loading models...")
perform_model = joblib.load('model/perform_model.pkl')
perform_vect = joblib.load('model/perform_vectorizer.pkl')
label_model = joblib.load('model/label_model.pkl')
label_vect = joblib.load('model/label_vectorizer.pkl')

query = "can you analyze Zone_Air_Humidity_Sensor_5.04 sensor data for the deviations from 02/02/2025 to 03/02/2025?"

print(f'\nTesting query: {query}\n')

# Perform classification
X_perform = perform_vect.transform([query])
perform_pred = perform_model.predict(X_perform)[0]
perform_proba = perform_model.predict_proba(X_perform)[0]

print(f'Perform prediction: {perform_pred}')
print(f'Perform probabilities: class 0={perform_proba[0]:.4f}, class 1={perform_proba[1]:.4f}')
print(f'Confidence: {max(perform_proba):.4f}')

if perform_pred == 1:
    X_label = label_vect.transform([query])
    label_pred = label_model.predict(X_label)[0]
    label_proba = label_model.predict_proba(X_label)[0]
    top_3_idx = label_proba.argsort()[-3:][::-1]
    
    print(f'\nLabel prediction: {label_pred}')
    print(f'Top 3 candidates:')
    for i, idx in enumerate(top_3_idx, 1):
        print(f'  {i}. {label_model.classes_[idx]} (prob={label_proba[idx]:.4f})')
else:
    print('\nPerform=0, no label prediction')

# Also test a simpler query
print('\n' + '='*80)
query2 = "What is the average deviation for sensor 5.04?"
print(f'\nTesting query: {query2}\n')

X_perform2 = perform_vect.transform([query2])
perform_pred2 = perform_model.predict(X_perform2)[0]
perform_proba2 = perform_model.predict_proba(X_perform2)[0]

print(f'Perform prediction: {perform_pred2}')
print(f'Perform probabilities: class 0={perform_proba2[0]:.4f}, class 1={perform_proba2[1]:.4f}')
