"""
Enhanced training script for decider-service.
Uses predict_proba for confidence scores and top-N predictions.
"""
import os
import json
import argparse
from typing import List, Tuple
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
import numpy as np

ROOT = Path(__file__).parent.parent
MODEL_DIR = ROOT / "model"
DATA_DIR = ROOT / "data"

# Default dataset combining perform flag and analytics label
DEFAULT_DATA = DATA_DIR / "decider_training_full.jsonl"


def ensure_dirs():
    """Ensure model and data directories exist."""
    MODEL_DIR.mkdir(exist_ok=True, parents=True)
    DATA_DIR.mkdir(exist_ok=True, parents=True)


def load_combined_dataset(path: str) -> Tuple[List[str], List[int], List[str]]:
    texts: List[str] = []
    perform_flags: List[int] = []
    labels: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            q = obj.get("text") or obj.get("question") or ""
            perform = int(obj.get("perform", obj.get("perform_analytics", 0)))
            analytics = obj.get("analytics")
            texts.append(q)
            perform_flags.append(perform)
            labels.append(analytics if analytics is not None else "none")
    return texts, perform_flags, labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--test-split", type=float, default=0.2, help="Test set size (0-1)")
    args = parser.parse_args()

    MODEL_DIR.mkdir(exist_ok=True, parents=True)
    DATA_DIR.mkdir(exist_ok=True, parents=True)

    if not os.path.exists(args.data):
        raise FileNotFoundError(f"Dataset not found: {args.data}\nGenerate training data first.")

    texts, perform_flags, labels = load_combined_dataset(args.data)
    print(f"Loaded {len(texts)} training examples")
    
    # Train/test split for evaluation
    X_train_text, X_test_text, y_train_perform, y_test_perform, y_train_label, y_test_label = train_test_split(
        texts, perform_flags, labels, test_size=args.test_split, random_state=42, stratify=perform_flags
    )
    print(f"Split: {len(X_train_text)} train, {len(X_test_text)} test")

    # ========================================
    # TRAIN PERFORM_ANALYTICS CLASSIFIER
    # ========================================
    print("\n[1/2] Training perform_analytics classifier...")
    perf_vect = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=5000)
    Xp_train = perf_vect.fit_transform(X_train_text)
    Xp_test = perf_vect.transform(X_test_text)
    
    perf_clf = LogisticRegression(
        max_iter=1000, 
        random_state=42, 
        C=1.0, 
        class_weight='balanced',
        solver='lbfgs'
    )
    perf_clf.fit(Xp_train, y_train_perform)
    
    # Evaluate with probabilities
    train_acc = perf_clf.score(Xp_train, y_train_perform)
    test_acc = perf_clf.score(Xp_test, y_test_perform)
    
    # Check predict_proba works
    test_probs = perf_clf.predict_proba(Xp_test)
    avg_confidence = test_probs.max(axis=1).mean()
    
    joblib.dump(perf_clf, MODEL_DIR / "perform_model.pkl")
    joblib.dump(perf_vect, MODEL_DIR / "perform_vectorizer.pkl")
    print(f"  ✓ Saved perform model")
    print(f"    Train accuracy: {train_acc:.3f}")
    print(f"    Test accuracy:  {test_acc:.3f}")
    print(f"    Avg confidence: {avg_confidence:.3f}")
    print(f"    Classes: {perf_clf.classes_.tolist()}")

    # ========================================
    # TRAIN ANALYTICS LABEL CLASSIFIER
    # ========================================
    print("\n[2/2] Training analytics label classifier...")
    
    # Filter for perform=1 examples only
    train_analytics_texts = [t for t, p in zip(X_train_text, y_train_perform) if p == 1]
    train_analytics_labels = [l for l, p in zip(y_train_label, y_train_perform) if p == 1]
    test_analytics_texts = [t for t, p in zip(X_test_text, y_test_perform) if p == 1]
    test_analytics_labels = [l for l, p in zip(y_test_label, y_test_perform) if p == 1]
    
    if len(train_analytics_labels) == 0:
        print("  ✗ ERROR: No analytics examples (perform=1). Check training data.")
        return
    
    print(f"  Analytics examples: {len(train_analytics_texts)} train, {len(test_analytics_texts)} test")
    
    lab_vect = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=5000)
    Xl_train = lab_vect.fit_transform(train_analytics_texts)
    Xl_test = lab_vect.transform(test_analytics_texts) if test_analytics_texts else None
    
    lab_clf = LogisticRegression(
        max_iter=1000,
        random_state=42,
        C=1.0,
        multi_class='multinomial',
        class_weight='balanced',
        solver='lbfgs'
    )
    lab_clf.fit(Xl_train, train_analytics_labels)
    
    # Evaluate with probabilities
    train_acc = lab_clf.score(Xl_train, train_analytics_labels)
    test_acc = lab_clf.score(Xl_test, test_analytics_labels) if Xl_test is not None and len(test_analytics_labels) > 0 else 0.0
    
    # Check predict_proba and top-N
    test_probs = lab_clf.predict_proba(Xl_test) if Xl_test is not None and len(test_analytics_labels) > 0 else None
    if test_probs is not None:
        avg_confidence = test_probs.max(axis=1).mean()
        # Top-3 accuracy
        top3_correct = sum(
            1 for probs, true_label in zip(test_probs, test_analytics_labels)
            if true_label in [lab_clf.classes_[i] for i in np.argsort(probs)[-3:]]
        )
        top3_acc = top3_correct / len(test_analytics_labels) if test_analytics_labels else 0.0
    else:
        avg_confidence = 0.0
        top3_acc = 0.0
    
    joblib.dump(lab_clf, MODEL_DIR / "label_model.pkl")
    joblib.dump(lab_vect, MODEL_DIR / "label_vectorizer.pkl")
    print(f"  ✓ Saved label model")
    print(f"    Train accuracy: {train_acc:.3f}")
    print(f"    Test accuracy:  {test_acc:.3f}")
    print(f"    Top-3 accuracy: {top3_acc:.3f}")
    print(f"    Avg confidence: {avg_confidence:.3f}")
    print(f"    Classes: {len(lab_clf.classes_)} ({', '.join(lab_clf.classes_[:5].tolist())}...)")
    
    print("\n✓ Training complete! Models support predict_proba for confidence and top-N.")


if __name__ == "__main__":
    main()
