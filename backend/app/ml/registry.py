import os
import json
import time
import hashlib
import shutil
from typing import Dict, Any, Optional, Tuple
from backend.app.core.config import BASE_DIR

MODELS_DIR = os.path.join(BASE_DIR, "dataset", "models")
REGISTRY_PATH = os.path.join(MODELS_DIR, "registry.json")
BASELINE_MODEL_PATH = os.path.join(MODELS_DIR, "tfidf_logistic_baseline.joblib")


def compute_sha256(filepath: str) -> str:
    """Calculates SHA256 checksum of a file."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def initialize_registry_if_missing():
    """Initializes registry.json with priority-v1 (baseline) if not present."""
    if os.path.exists(REGISTRY_PATH):
        return
    os.makedirs(MODELS_DIR, exist_ok=True)
    v1_dir = os.path.join(MODELS_DIR, "priority-v1")
    os.makedirs(v1_dir, exist_ok=True)
    v1_model_target = os.path.join(v1_dir, "model.joblib")

    # Ensure priority-v1 model artifact exists
    if not os.path.exists(v1_model_target) and os.path.exists(BASELINE_MODEL_PATH):
        shutil.copy2(BASELINE_MODEL_PATH, v1_model_target)

    artifact_hash = compute_sha256(BASELINE_MODEL_PATH) if os.path.exists(BASELINE_MODEL_PATH) else ""

    v1_metadata = {
        "model_version": "priority-v1",
        "name": "TF-IDF + Logistic Regression Baseline",
        "status": "production",
        "dataset_version": "dataset-v1",
        "feature_version": "tfidf-v1 (10,000 sublinear ngrams)",
        "label_schema_version": "v1.0 (P1/P2/P3/P4)",
        "created_at": "2026-09-20T00:00:00Z",
        "promoted_at": "2026-09-20T00:00:00Z",
        "artifact_path": "priority-v1/model.joblib",
        "artifact_sha256": artifact_hash,
        "changelog": "Initial baseline production model trained on Enron corporate communications."
    }

    v1_metrics = {
        "accuracy": 0.8067,
        "macro_f1": 0.7943,
        "weighted_f1": 0.8041,
        "per_class": {
            "P1": {"precision": 0.625, "recall": 0.500, "f1": 0.556},
            "P2": {"precision": 0.812, "recall": 0.843, "f1": 0.827},
            "P3": {"precision": 0.781, "recall": 0.760, "f1": 0.770},
            "P4": {"precision": 0.852, "recall": 0.831, "f1": 0.841}
        },
        "holdout_test_verified": True
    }

    with open(os.path.join(v1_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(v1_metadata, f, indent=2)

    with open(os.path.join(v1_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(v1_metrics, f, indent=2)

    if not os.path.exists(REGISTRY_PATH):
        initial_registry = {
            "active_model": "priority-v1",
            "previous_model": None,
            "versions": {
                "priority-v1": v1_metadata
            }
        }
        with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
            json.dump(initial_registry, f, indent=2)


class ModelRegistry:
    """
    Central registry for versioned production and candidate machine learning models.
    Supports offline training registration, explicit promotion, rollback, and metadata lookup.
    """
    def __init__(self):
        initialize_registry_if_missing()

    def get_registry(self) -> Dict[str, Any]:
        initialize_registry_if_missing()
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_registry(self, data: Dict[str, Any]):
        """
        Atomically saves registry.json using write-temp -> validate -> fsync -> atomic replace.
        Ensures active_model points to an existing artifact and structure is valid.
        """
        if not isinstance(data, dict) or "active_model" not in data or "versions" not in data:
            raise ValueError("Invalid registry structure: missing 'active_model' or 'versions'")
        active = data["active_model"]
        if active not in data["versions"]:
            raise ValueError(f"active_model '{active}' is not defined in versions")

        rel_path = data["versions"][active].get("artifact_path", f"{active}/model.joblib")
        abs_path = os.path.join(MODELS_DIR, rel_path)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Artifact for active_model '{active}' does not exist at {abs_path}")

        temp_path = f"{REGISTRY_PATH}.tmp.{os.getpid()}"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # Validate temporary file
            with open(temp_path, "r", encoding="utf-8") as f:
                read_back = json.load(f)
                if read_back.get("active_model") != active:
                    raise ValueError(f"Registry validation failed: active_model mismatch in temp file")

            # Atomic replace
            os.replace(temp_path, REGISTRY_PATH)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            raise

    def get_active_version(self) -> str:
        reg = self.get_registry()
        return reg.get("active_model", "priority-v1")

    def get_active_model_path(self) -> str:
        """Returns the absolute file path to the active model artifact."""
        reg = self.get_registry()
        active = reg.get("active_model", "priority-v1")
        version_info = reg.get("versions", {}).get(active, {})
        rel_path = version_info.get("artifact_path", f"{active}/model.joblib")
        abs_path = os.path.join(MODELS_DIR, rel_path)
        if os.path.exists(abs_path):
            return abs_path
        # Fallback to baseline
        return BASELINE_MODEL_PATH

    def get_active_metadata(self) -> Dict[str, Any]:
        """Returns metadata for the currently active production model."""
        reg = self.get_registry()
        active = reg.get("active_model", "priority-v1")
        return reg.get("versions", {}).get(active, {})

    def register_candidate(
        self,
        version: str,
        artifact_source_path: str,
        dataset_version: str,
        feature_version: str,
        metrics: Dict[str, Any],
        changelog: str
    ) -> Dict[str, Any]:
        """
        Registers a newly trained model artifact as a candidate version.
        Candidate versions are NOT automatically activated.
        """
        v_dir = os.path.join(MODELS_DIR, version)
        os.makedirs(v_dir, exist_ok=True)
        dest_model = os.path.join(v_dir, "model.joblib")
        if artifact_source_path != dest_model:
            shutil.copy2(artifact_source_path, dest_model)

        sha256 = compute_sha256(dest_model)
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        metadata = {
            "model_version": version,
            "name": f"MailMind Priority Classifier {version}",
            "status": "candidate",
            "dataset_version": dataset_version,
            "feature_version": feature_version,
            "label_schema_version": "v1.0 (P1/P2/P3/P4)",
            "created_at": now_iso,
            "promoted_at": None,
            "artifact_path": f"{version}/model.joblib",
            "artifact_sha256": sha256,
            "changelog": changelog
        }

        with open(os.path.join(v_dir, "metadata.json"), "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        with open(os.path.join(v_dir, "metrics.json"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        reg = self.get_registry()
        reg["versions"][version] = metadata
        self._save_registry(reg)
        return metadata

    def promote_to_production(self, version: str) -> bool:
        """
        Explicitly promotes an approved candidate model version to active production.
        Preserves the previous version identifier for instant rollback.
        """
        reg = self.get_registry()
        if version not in reg.get("versions", {}):
            raise ValueError(f"Version '{version}' is not registered in the model registry.")

        current_active = reg.get("active_model")
        if current_active == version:
            return True  # Already active

        # Mark current active as previous
        if current_active and current_active in reg["versions"]:
            reg["versions"][current_active]["status"] = "retired"
            reg["previous_model"] = current_active

        # Activate target version
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        reg["versions"][version]["status"] = "production"
        reg["versions"][version]["promoted_at"] = now_iso
        reg["active_model"] = version
        if reg.get("candidate_model") == version:
            reg["candidate_model"] = None

        self._save_registry(reg)

        # Invalidate in-memory predictor cache so next inference loads new model
        from backend.app.ml.predictor import invalidate_cached_pipeline
        invalidate_cached_pipeline()
        return True

    def get_version(self, version: str) -> Optional[Dict[str, Any]]:
        """Returns metadata dictionary for a specific model version."""
        reg = self.get_registry()
        return reg.get("versions", {}).get(version)

    def set_active(self, version: str) -> bool:
        """Alias for promoting/activating a specific model version."""
        return self.promote_to_production(version)

    def promote_candidate(self, version: str) -> bool:
        """Promotes a candidate model version to active production."""
        return self.promote_to_production(version)

    def rollback(self, target_version: Optional[str] = None) -> bool:
        """
        Rolls back active model to the previous registered version without retraining.
        """
        reg = self.get_registry()
        current_active = reg.get("active_model", "priority-v1")
        previous = target_version or reg.get("previous_model") or "priority-v1"

        if previous == current_active:
            return current_active

        if previous not in reg.get("versions", {}):
            raise ValueError(f"Rollback target version '{previous}' does not exist in registry.")

        reg["versions"][current_active]["status"] = "retired"
        reg["versions"][previous]["status"] = "production"
        reg["previous_model"] = current_active
        reg["active_model"] = previous
        if current_active == "priority-v5.1":
            reg["candidate_model"] = current_active
        self._save_registry(reg)

        from backend.app.ml.predictor import invalidate_cached_pipeline
        invalidate_cached_pipeline()
        return previous


# Global registry singleton
model_registry = ModelRegistry()


if __name__ == "__main__":
    import sys
    import argparse
    parser = argparse.ArgumentParser(description="MailMind Model Registry CLI")
    parser.add_argument("--list", action="store_true", help="List all registered model versions")
    parser.add_argument("--promote", type=str, help="Promote a candidate version to production")
    parser.add_argument("--rollback", action="store_true", help="Rollback to previous production model")
    parser.add_argument("--activate", type=str, help="Activate a specific version")
    args = parser.parse_args()

    reg = ModelRegistry()
    if args.list:
        data = reg.get_registry()
        print(f"Active Model: {data.get('active_model')}")
        print(f"Previous Model: {data.get('previous_model')}")
        print("\nRegistered Versions:")
        for v, meta in data.get("versions", {}).items():
            print(f"  • {v} [{meta.get('status')}] - {meta.get('name')} (SHA: {meta.get('artifact_sha256')[:12]}...)")
    elif args.promote:
        reg.promote_to_production(args.promote)
        print(f"Successfully promoted '{args.promote}' to production!")
    elif args.rollback:
        active = reg.rollback()
        print(f"Successfully rolled back active model to: {active}")
    elif args.activate:
        reg.promote_to_production(args.activate)
        print(f"Successfully activated: {args.activate}")
    else:
        parser.print_help()
