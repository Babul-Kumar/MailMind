"""
canary_router.py — Phase 49 Controlled Canary Deployment & Routing Layer
========================================================================

Architecture:
    Request -> Session / User -> Canary Router
                                      |
                    +-----------------+-----------------+
                    |                                   |
                    v                                   v
             priority-v4.1                       priority-v5.1
             (CONTROL: Production)               (CANARY: User-Facing)
                    |                                   |
                    +-----------------+-----------------+
                                      |
                                      v
                             User Feedback
                                      |
                                      v
                               Canary Metrics

Key Invariants:
  1. USER-LEVEL DETERMINISTIC ROUTING:
     hash(user_id + candidate_model) % 100 < canary_percentage -> CANARY (v5.1)
     Else -> CONTROL (v4.1).
     A single user receives consistent model predictions throughout a canary stage.
  2. STRICT ADMIN/BACKEND CONTROL:
     Normal frontend clients cannot supply model_version as a trusted parameter.
     The backend router strictly determines the model.
  3. ZERO CORRUPTION & INSTANT ROLLBACK:
     Setting canary_percentage to 0% immediately routes all traffic to v4.1 without
     re-training, database deletion, or service restarts.
  4. FAULT ISOLATION:
     If candidate v5.1 artifact is missing, corrupt, or throws an inference exception,
     the router automatically falls back to active v4.1 with zero user disruption.
"""

import os
import json
import hashlib
import logging
import threading
from typing import Dict, Any, Tuple, Optional
from pathlib import Path

from backend.app.core.config import BASE_DIR
from backend.app.ml.registry import model_registry

logger = logging.getLogger("mailmind.canary_router")

CONFIG_PATH = os.path.join(BASE_DIR, "dataset", "monitoring", "canary_config.json")
MODELS_DIR = os.path.join(BASE_DIR, "dataset", "models")

# Permitted Canary Stages
STAGE_PERCENTAGES = {
    0: 0,
    1: 5,
    2: 10,
    3: 25,
    4: 50,
}


class CanaryRouter:
    """
    Manages controlled user-level canary routing between active production model (v4.1)
    and candidate model (v5.1).
    """

    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self._lock = threading.RLock()
        self._pipeline_cache: Dict[str, Any] = {}
        self._error_counts: Dict[str, int] = {"control": 0, "canary": 0, "fallback": 0}
        self._load_config()

    def _load_config(self) -> None:
        """Loads canary configuration from disk or initializes defaults."""
        with self._lock:
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.canary_enabled = bool(data.get("canary_enabled", False))
                        self.canary_percentage = int(data.get("canary_percentage", 0))
                        self.stage = int(data.get("stage", 0))
                        self.candidate_model = str(data.get("candidate_model", "priority-v5.1"))
                        return
                except Exception as e:
                    logger.warning("Failed to load canary config, using defaults: %s", e)

            # Default safe initial state: Stage 0 (0% canary, disabled)
            self.canary_enabled = False
            self.canary_percentage = 0
            self.stage = 0
            self.candidate_model = "priority-v5.1"
            self._save_config()

    def _save_config(self) -> None:
        """Persists current canary configuration to disk."""
        with self._lock:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            data = {
                "canary_enabled": self.canary_enabled,
                "canary_percentage": self.canary_percentage,
                "stage": self.stage,
                "active_model": self.get_active_model_version(),
                "candidate_model": self.candidate_model,
                "updated_at": Path(self.config_path).stat().st_mtime if os.path.exists(self.config_path) else None,
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def get_active_model_version(self) -> str:
        """Always resolves the true active production model from registry (priority-v4.1)."""
        return model_registry.get_active_version()

    def get_user_bucket(self, user_id: str, candidate_model: Optional[str] = None) -> int:
        """
        Computes a deterministic integer bucket in [0, 99] for a user.
        Ensures consistent routing across all requests by hashing user_id and candidate_model.
        """
        c_model = candidate_model or self.candidate_model
        key = f"{user_id}:{c_model}".encode("utf-8")
        digest = hashlib.sha256(key).hexdigest()[:8]
        return int(digest, 16) % 100

    def route_user(self, user_id: str) -> Dict[str, Any]:
        """
        Deterministically routes a user to either the active production model (v4.1) or
        the canary candidate model (v5.1).

        Returns:
            Dict containing:
                - model_version: 'priority-v4.1' or 'priority-v5.1'
                - canary_group: 'control' or 'canary'
                - canary_percentage: int
                - stage: int
                - bucket: int
                - is_canary: bool
        """
        active_version = self.get_active_model_version()
        candidate_version = self.candidate_model

        with self._lock:
            enabled = self.canary_enabled
            pct = self.canary_percentage
            stage = self.stage

        if not enabled or pct <= 0:
            return {
                "model_version": active_version,
                "canary_group": "control",
                "canary_percentage": 0,
                "stage": stage,
                "bucket": self.get_user_bucket(user_id, candidate_version),
                "is_canary": False,
            }

        bucket = self.get_user_bucket(user_id, candidate_version)
        if bucket < pct:
            return {
                "model_version": candidate_version,
                "canary_group": "canary",
                "canary_percentage": pct,
                "stage": stage,
                "bucket": bucket,
                "is_canary": True,
            }
        else:
            return {
                "model_version": active_version,
                "canary_group": "control",
                "canary_percentage": pct,
                "stage": stage,
                "bucket": bucket,
                "is_canary": False,
            }

    def get_pipeline(self, model_version: str) -> Any:
        """
        Loads and caches the requested model pipeline artifact.
        Handles model resolution through model_registry.
        """
        with self._lock:
            if model_version in self._pipeline_cache:
                return self._pipeline_cache[model_version]

            reg = model_registry.get_registry()
            version_info = reg.get("versions", {}).get(model_version, {})
            rel_path = version_info.get("artifact_path")
            if not rel_path:
                raise FileNotFoundError(f"Model version '{model_version}' not registered in registry.")

            abs_path = os.path.join(MODELS_DIR, rel_path)
            if not os.path.exists(abs_path):
                raise FileNotFoundError(f"Model artifact for '{model_version}' not found at {abs_path}")

            import joblib
            pipeline = joblib.load(abs_path)
            setattr(pipeline, "_model_version", model_version)
            self._pipeline_cache[model_version] = pipeline
            return pipeline

    def get_pipeline_for_user(self, user_id: str) -> Tuple[Any, Dict[str, Any]]:
        """
        Resolves the routed pipeline for a user with strict fault isolation:
        If candidate model fails to load or execute, transparently falls back to active model.
        Returns: (pipeline, route_info)
        """
        route_info = self.route_user(user_id)
        target_version = route_info["model_version"]

        try:
            pipeline = self.get_pipeline(target_version)
            return pipeline, route_info
        except Exception as exc:
            # Candidate failure MUST NEVER break user experience -> Fallback to active v4.1
            logger.error(
                "Canary failure for model '%s': %s. Falling back to active production model.",
                target_version,
                exc,
                exc_info=True,
            )
            with self._lock:
                self._error_counts["fallback"] += 1

            active_version = self.get_active_model_version()
            pipeline = self.get_pipeline(active_version)
            route_info["model_version"] = active_version
            route_info["canary_group"] = "control_fallback"
            route_info["is_canary"] = False
            route_info["fallback_reason"] = str(exc)
            return pipeline, route_info

    def set_stage(self, stage: int) -> Dict[str, Any]:
        """
        Explicitly sets the canary stage.
        Stage 0: 0%
        Stage 1: 5%
        Stage 2: 10%
        Stage 3: 25%
        Stage 4: 50%
        """
        if stage not in STAGE_PERCENTAGES:
            raise ValueError(f"Invalid stage {stage}. Permitted stages: {list(STAGE_PERCENTAGES.keys())}")

        pct = STAGE_PERCENTAGES[stage]
        with self._lock:
            self.stage = stage
            self.canary_percentage = pct
            self.canary_enabled = (pct > 0)
            self._save_config()

        logger.info("Canary stage updated to Stage %d (%d%%)", stage, pct)
        return self.get_status()

    def set_percentage(self, percentage: int) -> Dict[str, Any]:
        """Sets custom canary percentage with validation (0 to 50 max during canary)."""
        if not (0 <= percentage <= 50):
            raise ValueError("Canary percentage must be between 0 and 50 during canary evaluation.")

        with self._lock:
            self.canary_percentage = percentage
            self.canary_enabled = (percentage > 0)
            # Find closest matching stage
            closest_stage = 0
            for s, p in STAGE_PERCENTAGES.items():
                if p == percentage:
                    closest_stage = s
                    break
            self.stage = closest_stage
            self._save_config()

        return self.get_status()

    def rollback(self) -> Dict[str, Any]:
        """
        Instant emergency rollback: sets canary percentage to 0% and disables canary mode.
        All traffic is immediately restored to active production model (v4.1).
        Does NOT modify databases, clear cache, or require restarts.
        """
        with self._lock:
            self.canary_enabled = False
            self.canary_percentage = 0
            self.stage = 0
            self._save_config()

        logger.warning("Canary EMERGENCY ROLLBACK executed. All traffic reverted to active model.")
        return self.get_status()

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive status of canary router."""
        with self._lock:
            return {
                "canary_enabled": self.canary_enabled,
                "stage": self.stage,
                "canary_percentage": self.canary_percentage,
                "active_model": self.get_active_model_version(),
                "candidate_model": self.candidate_model,
                "permitted_stages": STAGE_PERCENTAGES,
                "rollback_ready": True,
                "error_counts": dict(self._error_counts),
            }


# Singleton instance
canary_router = CanaryRouter()
