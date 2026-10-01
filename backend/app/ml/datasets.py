import os
import json
import hashlib
import pandas as pd
from typing import Dict, Any, List, Tuple
from backend.app.core.config import BASE_DIR, TEST_CSV_PATH

VERSIONS_DIR = os.path.join(BASE_DIR, "dataset", "versions")
PROCESSED_DIR = os.path.join(BASE_DIR, "dataset", "processed")


def hash_text(text: str) -> str:
    """Computes a normalized SHA256 of text for deduplication and leakage checking."""
    norm = " ".join(str(text or "").lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def check_leakage(train_df: pd.DataFrame, test_df: pd.DataFrame) -> List[str]:
    """
    Checks for any text leakage between training and holdout test sets.
    Returns a list of leaked email IDs or review IDs if any overlap is detected.
    """
    test_hashes = set()
    for _, row in test_df.iterrows():
        subj = str(row.get("subject", ""))
        body = str(row.get("body", ""))
        test_hashes.add(hash_text(f"{subj} {body}"))

    leaked = []
    for _, row in train_df.iterrows():
        subj = str(row.get("subject", ""))
        body = str(row.get("body", ""))
        h = hash_text(f"{subj} {body}")
        if h in test_hashes:
            leaked.append(str(row.get("review_id", row.get("email_id", "unknown"))))
    return leaked


def initialize_dataset_v1():
    """Initializes dataset-v1 from the baseline processed Enron splits."""
    v1_dir = os.path.join(VERSIONS_DIR, "dataset-v1")
    os.makedirs(v1_dir, exist_ok=True)

    train_src = os.path.join(PROCESSED_DIR, "train.csv")
    val_src = os.path.join(PROCESSED_DIR, "validation.csv")

    train_target = os.path.join(v1_dir, "train.csv")
    val_target = os.path.join(v1_dir, "validation.csv")

    if os.path.exists(train_src) and not os.path.exists(train_target):
        df_tr = pd.read_csv(train_src)
        df_tr.to_csv(train_target, index=False)

    if os.path.exists(val_src) and not os.path.exists(val_target):
        df_val = pd.read_csv(val_src)
        df_val.to_csv(val_target, index=False)

    meta_target = os.path.join(v1_dir, "metadata.json")
    if not os.path.exists(meta_target):
        meta = {
            "dataset_version": "dataset-v1",
            "name": "Enron Human-Reviewed Priority Benchmark v1",
            "total_examples": 2000,
            "train_examples": 1400,
            "validation_examples": 300,
            "test_examples": 300,
            "class_distribution_train": {"P2": 666, "P4": 381, "P3": 317, "P1": 36},
            "source_categories": ["Enron Corporate Email Communications"],
            "label_schema_version": "v1.0 (P1/P2/P3/P4)",
            "deduplication_status": "Deduplicated by content hash",
            "leakage_checks": "Disjoint review_id partition across train/val/test",
            "created_at": "2026-09-15T00:00:00Z",
            "changelog": "Initial baseline split from 2,000 gold human-labeled Enron emails."
        }
        with open(meta_target, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)


def get_dataset_version_path(version: str) -> str:
    """Returns the directory path for a specific dataset version."""
    v_dir = os.path.join(VERSIONS_DIR, version)
    if not os.path.exists(v_dir):
        raise FileNotFoundError(f"Dataset version '{version}' not found at: {v_dir}")
    return v_dir


def load_dataset_version(version: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Loads train, validation, and holdout test DataFrames for a dataset version."""
    v_dir = get_dataset_version_path(version)
    train_path = os.path.join(v_dir, "train.csv")
    val_path = os.path.join(v_dir, "validation.csv")

    if not os.path.exists(train_path) or not os.path.exists(val_path):
        raise FileNotFoundError(f"Train/validation splits missing in {v_dir}")

    train_df = pd.read_csv(train_path)
    val_df = pd.read_csv(val_path)
    test_df = pd.read_csv(TEST_CSV_PATH)

    # Perform runtime leakage check
    leaks = check_leakage(train_df, test_df)
    if leaks:
        raise ValueError(f"CRITICAL: Data leakage detected between train and test! Leaked items: {leaks}")

    return train_df, val_df, test_df
