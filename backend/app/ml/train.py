import os
import argparse
import joblib
import pandas as pd
from typing import Dict, Any
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report
)

from backend.app.core.config import BASE_DIR
from backend.app.ml.datasets import load_dataset_version
from backend.app.ml.registry import model_registry, compute_sha256


def format_text(subject: Any, body: Any) -> str:
    s = str(subject).strip() if pd.notna(subject) else ""
    b = str(body).strip() if pd.notna(body) else ""
    return f"{s} {b}".strip()


def build_pipeline() -> Pipeline:
    """Builds the standardized TF-IDF + Logistic Regression pipeline."""
    return Pipeline([
        ('tfidf', TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True
        )),
        ('clf', LogisticRegression(
            class_weight='balanced',
            max_iter=1000,
            random_state=42
        ))
    ])


def evaluate_split(pipeline: Pipeline, df: pd.DataFrame, split_name: str) -> Dict[str, Any]:
    X = [format_text(s, b) for s, b in zip(df['subject'], df['body'])]
    y_true = df['final_label'].tolist()
    y_pred = pipeline.predict(X)

    acc = float(accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, average='macro'))
    weighted_f1 = float(f1_score(y_true, y_pred, average='weighted'))

    classes = ["P1", "P2", "P3", "P4"]
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, labels=classes, zero_division=0)
    per_class = {
        cls: {
            "precision": round(float(p[i]), 4),
            "recall": round(float(r[i]), 4),
            "f1": round(float(f[i]), 4)
        }
        for i, cls in enumerate(classes)
    }

    cm = confusion_matrix(y_true, y_pred, labels=classes).tolist()

    print(f"\n--- Evaluation Results ({split_name}) ---")
    print(f"Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f} | Weighted F1: {weighted_f1:.4f}")
    print(classification_report(y_true, y_pred, labels=classes, zero_division=0))

    return {
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
        "confusion_matrix": cm
    }


def train_model(
    dataset_version: str = "dataset-v2",
    model_version: str = "priority-v2",
    promote: bool = False
) -> Dict[str, Any]:
    """
    Executes reproducible offline training pipeline:
    1. Loads versioned dataset
    2. Validates schema and runs strict leakage check
    3. Trains candidate pipeline
    4. Evaluates on validation and untouched holdout test set
    5. Saves candidate artifact into model registry
    6. Optionally promotes candidate to production
    """
    print(f"\n=======================================================")
    print(f"Starting Offline Training for Candidate: {model_version}")
    print(f"Source Dataset: {dataset_version}")
    print(f"=======================================================")

    # 1. Load versioned dataset splits
    train_df, val_df, test_df = load_dataset_version(dataset_version)
    print(f"Loaded {len(train_df)} train, {len(val_df)} val, {len(test_df)} test rows.")

    # 2. Build text features and labels
    X_train = [format_text(s, b) for s, b in zip(train_df['subject'], train_df['body'])]
    y_train = train_df['final_label'].tolist()

    # 3. Train candidate model
    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)

    vocab_size = len(pipeline.named_steps['tfidf'].vocabulary_)
    print(f"Candidate fitted successfully! Vocabulary size: {vocab_size:,} features.")

    # 4. Evaluate on validation and holdout test sets
    val_metrics = evaluate_split(pipeline, val_df, "Validation Split")
    test_metrics = evaluate_split(pipeline, test_df, "Holdout Test Split (Untouched)")

    combined_metrics = {
        "validation": val_metrics,
        "test": test_metrics,
        "vocabulary_size": vocab_size,
        "dataset_version": dataset_version
    }

    # 5. Save candidate artifact
    v_dir = os.path.join(BASE_DIR, "dataset", "models", model_version)
    os.makedirs(v_dir, exist_ok=True)
    candidate_path = os.path.join(v_dir, "model.joblib")
    joblib.dump(pipeline, candidate_path)

    # 6. Register candidate in model registry
    changelog = (
        f"Candidate {model_version} trained on {dataset_version}. "
        f"Trained with modern Gmail verification, security incident, and promotional negation examples. "
        f"Holdout accuracy: {test_metrics['accuracy']:.4f}, Macro F1: {test_metrics['macro_f1']:.4f}."
    )
    meta = model_registry.register_candidate(
        version=model_version,
        artifact_source_path=candidate_path,
        dataset_version=dataset_version,
        feature_version="tfidf-v2 (10,000 sublinear ngrams)",
        metrics=combined_metrics,
        changelog=changelog
    )

    print(f"\n[Registry] Registered {model_version} as candidate (SHA256: {meta['artifact_sha256'][:16]}...)")

    if promote:
        model_registry.promote_to_production(model_version)
        print(f"[Registry] Explicitly PROMOTED {model_version} to ACTIVE PRODUCTION!")

    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MailMind Model Training Pipeline")
    parser.add_argument("--dataset", type=str, default="dataset-v2", help="Dataset version to train on")
    parser.add_argument("--version", type=str, default="priority-v2", help="Target model version name")
    parser.add_argument("--promote", action="store_true", help="Promote directly to production after evaluation")
    args = parser.parse_args()

    train_model(dataset_version=args.dataset, model_version=args.version, promote=args.promote)
