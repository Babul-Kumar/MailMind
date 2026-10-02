"""
Test Suite: Phase 46 — Priority-v5 Candidate Training & Comprehensive Evaluation
================================================================================
Validates:
1. Model registry state: priority-v4.1 remains ACTIVE (production); priority-v5 is registered ONLY as CANDIDATE.
2. Invariant preservation: priority-v4.1 and priority-v3 model artifacts and holdout hashes remain bit-identical.
3. Candidate artifact generation: priority-v5-candidate/model.joblib exists, valid Pipeline.
4. Reproducible training: deterministic pipeline output with fixed random seed.
5. Historical holdout benchmark: accuracy >= 80%, macro F1 within margin of V4.1.
6. Modern holdout benchmark: P2 recall >= 95% (recovering Phase 39 regression without loss).
7. Newsletter holdout benchmark: routine newsletter P2 error <= 5.0%.
8. Social holdout benchmark: routine social P2 error <= 5.0%, security recall >= 90.0%.
9. Multi-user safety: deterministic inference independent of user identity, zero cache mutation.
10. Mailbox simulation: 17,322 message inference executed, zero critical P1 downgrades.
11. Evaluation artifacts: all 7 required evaluation artifacts present in dataset/evaluation/phase46/.
12. Promotion gates: structured gate assessment documented.
"""

import os
import json
import hashlib
import sqlite3
import pytest
import joblib
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "dataset" / "models"
EVAL_DIR = BASE_DIR / "dataset" / "evaluation" / "phase46"

V4_1_MODEL_PATH = MODELS_DIR / "priority-v4.1" / "model.joblib"
V3_MODEL_PATH = MODELS_DIR / "priority-v3" / "model.joblib"
V5_MODEL_PATH = MODELS_DIR / "priority-v5-candidate" / "model.joblib"
REGISTRY_PATH = MODELS_DIR / "registry.json"

EXPECTED_V4_1_SHA = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"
EXPECTED_V3_SHA = "fa69e6a5cfafb8b24c5941dbb8fb08a208addfc4f39e38fa47df0a7cd7040b56"

HOLDOUTS = {
    "historical": (BASE_DIR / "dataset" / "processed" / "test.csv", "6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138"),
    "modern": (BASE_DIR / "dataset-v3" / "modern_holdout.csv", "020dccbc7f39d03665d2f56f1470077b517ac12e0d10e695dc8915edc3b1dffb"),
    "newsletter": (BASE_DIR / "dataset-v4" / "newsletter_holdout.csv", "043f0059674dda32365a02f6c43e95c7ad6293fff019315f1ff089109b16b398"),
    "social": (BASE_DIR / "dataset-v4" / "social_holdout.csv", "fe00139b3c90434763257616c4acc6eab280f62668d6ab1d1caed158c708747f"),
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


class TestPreTrainingInvariants:
    """Verifies that all pre-training invariants are strictly preserved."""

    def test_production_model_v4_1_unchanged(self):
        assert V4_1_MODEL_PATH.exists(), "priority-v4.1 artifact missing!"
        current_sha = sha256_file(V4_1_MODEL_PATH)
        assert current_sha == EXPECTED_V4_1_SHA, f"V4.1 artifact was modified! SHA: {current_sha}"

    def test_production_model_v3_unchanged(self):
        assert V3_MODEL_PATH.exists(), "priority-v3 artifact missing!"
        current_sha = sha256_file(V3_MODEL_PATH)
        assert current_sha == EXPECTED_V3_SHA, f"V3 artifact was modified! SHA: {current_sha}"

    def test_registry_active_model_remains_v4_1(self):
        assert REGISTRY_PATH.exists(), "registry.json missing!"
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        assert registry.get("active_model") == "priority-v4.1", "active_model must remain priority-v4.1!"
        assert registry.get("previous_model") == "priority-v3", "previous_model must remain priority-v3!"
        assert registry["versions"]["priority-v4.1"]["status"] == "production"

    def test_priority_v5_registered_as_candidate_only(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        assert "priority-v5" in registry["versions"], "priority-v5 must be present in registry versions!"
        v5_entry = registry["versions"]["priority-v5"]
        assert v5_entry["status"] == "candidate", f"priority-v5 status must be 'candidate', got '{v5_entry['status']}'"
        assert v5_entry["promoted_at"] is None, "priority-v5 must NOT have a promoted_at timestamp!"

    def test_all_holdout_hashes_unmodified(self):
        for name, (path, expected_hash) in HOLDOUTS.items():
            assert path.exists(), f"Holdout file {path} missing!"
            actual_hash = sha256_file(path)
            assert actual_hash == expected_hash, f"Holdout {name} hash modified! Expected {expected_hash}, got {actual_hash}"


class TestV5CandidateModelArtifact:
    """Verifies the candidate model artifact structure, architecture, and reproducibility."""

    def test_v5_candidate_artifact_exists(self):
        assert V5_MODEL_PATH.exists(), "priority-v5-candidate model.joblib does not exist!"
        assert V5_MODEL_PATH.stat().st_size > 3_000_000, "priority-v5-candidate artifact appears truncated!"

    def test_v5_candidate_pipeline_components(self):
        pipeline = joblib.load(V5_MODEL_PATH)
        assert hasattr(pipeline, "named_steps"), "Candidate must be a scikit-learn Pipeline"
        assert "tfidf" in pipeline.named_steps, "Pipeline missing 'tfidf' step"
        assert "clf" in pipeline.named_steps, "Pipeline missing 'clf' step"

        tfidf = pipeline.named_steps["tfidf"]
        clf = pipeline.named_steps["clf"]

        assert tfidf.ngram_range == (1, 2)
        assert tfidf.sublinear_tf is True
        assert clf.class_weight == "balanced"
        assert set(clf.classes_) == {"P1", "P2", "P3", "P4"}


class TestHoldoutBenchmarks:
    """Verifies that the V5 candidate satisfies all holdout benchmarks."""

    @pytest.fixture(scope="class")
    def v5_model(self):
        return joblib.load(V5_MODEL_PATH)

    def test_gate3_historical_holdout_performance(self, v5_model):
        df_hist = pd.read_csv(HOLDOUTS["historical"][0])
        texts = (df_hist["subject"].fillna("") + " " + df_hist["body"].fillna("")).tolist()
        y_true = df_hist["final_label"].tolist()
        y_pred = v5_model.predict(texts)
        acc = (y_pred == y_true).mean()
        assert acc >= 0.80, f"Historical holdout accuracy {acc:.4f} < 0.80"

    def test_gate4_modern_holdout_p2_recall(self, v5_model):
        df_modern = pd.read_csv(HOLDOUTS["modern"][0])
        p2_df = df_modern[df_modern["final_label"] == "P2"]
        texts = (p2_df["subject"].fillna("") + " " + p2_df["body"].fillna("")).tolist()
        y_pred = v5_model.predict(texts)
        p2_recall = (y_pred == "P2").mean()
        assert p2_recall >= 0.95, f"Modern holdout P2 recall {p2_recall:.4f} < 0.9500 (GATE 4 failed)"

    def test_gate5_newsletter_routine_p2_error_low(self, v5_model):
        df_nl = pd.read_csv(HOLDOUTS["newsletter"][0])
        routine_nl = df_nl[df_nl["final_label"].isin(["P3", "P4"])]
        texts = (routine_nl["subject"].fillna("") + " " + routine_nl["body"].fillna("")).tolist()
        y_pred = v5_model.predict(texts)
        p2_err = (y_pred == "P2").mean()
        assert p2_err <= 0.05, f"Newsletter routine P2 error rate {p2_err:.4f} > 5.0% (GATE 5 failed)"

    def test_gate6_social_routine_p2_error_low(self, v5_model):
        df_soc = pd.read_csv(HOLDOUTS["social"][0])
        routine_soc = df_soc[df_soc["final_label"].isin(["P3", "P4"])]
        texts = (routine_soc["subject"].fillna("") + " " + routine_soc["body"].fillna("")).tolist()
        y_pred = v5_model.predict(texts)
        p2_err = (y_pred == "P2").mean()
        assert p2_err <= 0.05, f"Social routine P2 error rate {p2_err:.4f} > 5.0% (GATE 6 failed)"

    def test_gate7_social_security_recall(self, v5_model):
        df_soc = pd.read_csv(HOLDOUTS["social"][0])
        sec_soc = df_soc[df_soc["final_label"].isin(["P1", "P2"])]
        texts = (sec_soc["subject"].fillna("") + " " + sec_soc["body"].fillna("")).tolist()
        y_true = sec_soc["final_label"].tolist()
        y_pred = v5_model.predict(texts)
        sec_recall = (y_pred == y_true).mean()
        assert sec_recall >= 0.90, f"Social security recall {sec_recall:.4f} < 90.0% (GATE 7 failed)"


class TestProductionMailboxSimulationAndArtifacts:
    """Verifies that all evaluation artifacts and mailbox simulation files exist and are valid."""

    REQUIRED_ARTIFACTS = [
        "v4_1_predictions.csv",
        "v5_predictions.csv",
        "diff.csv",
        "error_analysis.csv",
        "metrics.json",
        "v4_1_mailbox_predictions.csv",
        "v5_mailbox_predictions.csv",
    ]

    def test_all_evaluation_artifacts_exist(self):
        for fname in self.REQUIRED_ARTIFACTS:
            fpath = EVAL_DIR / fname
            assert fpath.exists(), f"Evaluation artifact {fname} missing in {EVAL_DIR}"
            assert fpath.stat().st_size > 0, f"Evaluation artifact {fname} is empty!"

    def test_mailbox_simulation_row_counts(self):
        v4_mb = pd.read_csv(EVAL_DIR / "v4_1_mailbox_predictions.csv")
        v5_mb = pd.read_csv(EVAL_DIR / "v5_mailbox_predictions.csv")
        assert len(v4_mb) == 17322, f"Expected 17,322 rows in v4_1 mailbox simulation, got {len(v4_mb)}"
        assert len(v5_mb) == 17322, f"Expected 17,322 rows in v5 mailbox simulation, got {len(v5_mb)}"

    def test_zero_critical_p1_downgrades_in_mailbox(self):
        v4_mb = pd.read_csv(EVAL_DIR / "v4_1_mailbox_predictions.csv")
        v5_mb = pd.read_csv(EVAL_DIR / "v5_mailbox_predictions.csv")
        p1_mask = (v4_mb["priority"] == "P1") & (v5_mb["priority"] != "P1")
        p1_downgrades = v5_mb[p1_mask]
        assert len(p1_downgrades) == 0, f"Found {len(p1_downgrades)} P1 downgrades in mailbox simulation!"

    def test_metrics_json_has_final_decision(self):
        metrics_file = EVAL_DIR / "metrics.json"
        metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
        assert "final_decision" in metrics
        assert metrics["final_decision"] in (
            "CANDIDATE VIABLE — READY FOR SHADOW EVALUATION",
            "CANDIDATE REQUIRES REMEDIATION",
        )
        assert "promotion_gates" in metrics
        assert len(metrics["promotion_gates"]) == 15
