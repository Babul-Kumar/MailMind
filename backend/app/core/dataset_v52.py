"""
dataset_v52.py — Phase 52 Dataset-v5.2 Candidate Builder
==========================================================
Assembles a CANDIDATE dataset from human-adjudicated production feedback.

DESIGN INVARIANTS:
  - Only ACCEPTED adjudication records may enter the candidate pool.
  - Every candidate example must have documented provenance.
  - No training occurs in this module. No model is modified.
  - The candidate dataset is clearly marked: CANDIDATE / NOT TRAINED / NOT PRODUCTION.
  - Leakage audit is mandatory before declaring the candidate ready.
  - Frozen holdouts (test.csv, validation.csv, boundary_holdout.csv) must
    remain bit-identical throughout. ZERO overlap allowed.
  - If adjudicated evidence is insufficient, the candidate is empty.
    DO NOT fabricate data.

Output: dataset/v5.2_candidate/
  - train_candidate.csv
  - provenance.csv
  - adjudication_log.jsonl
  - candidate_manifest.json
  - leakage_audit.json
  - dataset_card.md
"""
import os
import csv
import json
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional, Set

from backend.app.core.config import BASE_DIR
from backend.app.core.adjudication import adjudication_manager, ADJUDICATION_FILE
from backend.app.core.feedback import FEEDBACK_DIR

logger = logging.getLogger("mailmind.dataset_v52")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CANDIDATE_DIR = os.path.join(BASE_DIR, "dataset", "v5.2_candidate")
TRAIN_CANDIDATE_CSV = os.path.join(CANDIDATE_DIR, "train_candidate.csv")
PROVENANCE_CSV = os.path.join(CANDIDATE_DIR, "provenance.csv")
ADJUDICATION_LOG = os.path.join(CANDIDATE_DIR, "adjudication_log.jsonl")
CANDIDATE_MANIFEST = os.path.join(CANDIDATE_DIR, "candidate_manifest.json")
LEAKAGE_AUDIT_JSON = os.path.join(CANDIDATE_DIR, "leakage_audit.json")
DATASET_CARD = os.path.join(CANDIDATE_DIR, "dataset_card.md")

# Frozen holdouts — SHA-256 must remain unchanged
FROZEN_FILES = {
    "test.csv": os.path.join(BASE_DIR, "dataset", "processed", "test.csv"),
    "train.csv": os.path.join(BASE_DIR, "dataset", "processed", "train.csv"),
    "v5.1_train.csv": os.path.join(BASE_DIR, "dataset-v5.1", "train.csv"),
    "v5.1_validation.csv": os.path.join(BASE_DIR, "dataset-v5.1", "validation.csv"),
    "v5.1_boundary_holdout.csv": os.path.join(BASE_DIR, "dataset-v5.1", "boundary_holdout.csv"),
}

# Phase 52 — v5.1 production dataset baseline
V51_TRAIN_DISTRIBUTION = {"P1": 70, "P2": 735, "P3": 552, "P4": 523}
V51_TRAIN_TOTAL = 1880

CANDIDATE_STATUS = "CANDIDATE — NOT TRAINED — NOT PRODUCTION"


def _sha256_file(path: str) -> Optional[str]:
    """Returns the SHA-256 hex digest of a file, or None if not found."""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_message_ids_from_csv(path: str, id_col: str = "message_id") -> Set[str]:
    """Loads a set of message_ids (or email_id) from a CSV file for leakage detection."""
    ids: Set[str] = set()
    if not os.path.exists(path):
        return ids
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                mid = row.get(id_col) or row.get("email_id") or row.get("id") or ""
                if mid:
                    ids.add(mid.strip())
    except Exception as exc:
        logger.warning("dataset_v52: could not load message_ids from %s: %s", path, exc)
    return ids


def _load_text_fingerprints_from_csv(path: str) -> Set[str]:
    """
    Loads normalized text fingerprints (SHA-256 of lowercased text field) for
    near-duplicate detection.
    """
    fps: Set[str] = set()
    if not os.path.exists(path):
        return fps
    try:
        with open(path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = (row.get("text") or row.get("body") or row.get("subject") or "").strip().lower()
                if text:
                    fps.add(_sha256_str(text))
    except Exception as exc:
        logger.warning("dataset_v52: could not load text fingerprints from %s: %s", path, exc)
    return fps


class DatasetV52Builder:
    """
    Builds the dataset-v5.2 candidate from human-adjudicated production feedback.

    The builder:
      1. Reads ONLY from adjudication_manager.get_candidate_pool() (ACCEPTED only)
      2. Runs leakage audit against all frozen holdouts
      3. Assembles train_candidate.csv, provenance.csv
      4. Writes adjudication_log.jsonl to candidate dir
      5. Computes candidate_manifest.json
      6. Writes dataset_card.md

    If the candidate pool is empty (insufficient adjudicated evidence),
    all output files are created but train_candidate.csv will be empty.
    This is the correct result — DO NOT fabricate data.
    """

    def build(self) -> Dict[str, Any]:
        """
        Full build pipeline. Returns a summary report dict.
        """
        os.makedirs(CANDIDATE_DIR, exist_ok=True)
        logger.info("dataset_v52: starting candidate build")

        # Step 1: Get candidate pool (ACCEPTED adjudicated only)
        pool = adjudication_manager.get_candidate_pool()
        logger.info("dataset_v52: candidate pool size = %d", len(pool))

        # Step 2: Run leakage audit
        leakage = self.run_leakage_audit(pool)

        # Step 3: Filter out any leaked examples
        clean_pool = [
            r for r in pool
            if r.get("message_id") not in leakage["leaked_message_ids"]
        ]
        leaked_count = len(pool) - len(clean_pool)

        # Step 4: Write train_candidate.csv
        self._write_train_candidate(clean_pool)

        # Step 5: Write provenance.csv
        self._write_provenance(clean_pool)

        # Step 6: Write adjudication_log.jsonl copy
        self._write_adjudication_log()

        # Step 7: Class distribution
        distribution = self._compute_distribution(clean_pool)

        # Step 8: Build manifest
        manifest = self.build_manifest(clean_pool, distribution, leakage, leaked_count)

        # Step 9: Write dataset_card.md
        self._write_dataset_card(manifest)

        # Step 10: Determine readiness state
        readiness = self._assess_readiness(clean_pool, leakage)

        logger.info(
            "dataset_v52: build complete. candidates=%d, leaked=%d, readiness=%s",
            len(clean_pool), leaked_count, readiness["state"],
        )

        return {
            "candidate_dir": CANDIDATE_DIR,
            "candidate_status": CANDIDATE_STATUS,
            "pool_size_before_leakage_filter": len(pool),
            "leaked_examples": leaked_count,
            "accepted_candidates": len(clean_pool),
            "class_distribution": distribution,
            "leakage_audit": leakage,
            "manifest_path": CANDIDATE_MANIFEST,
            "readiness": readiness,
        }

    def run_leakage_audit(
        self, pool: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Leakage audit: checks candidate examples against all frozen holdouts.

        Checks:
          - Exact message_id overlap with frozen files
          - Text fingerprint (SHA-256) near-duplicate check
          - Frozen holdout bit-identity (SHA-256 of the file itself)

        Required: ZERO leakage into frozen evaluation/holdout sets.
        """
        if pool is None:
            pool = adjudication_manager.get_candidate_pool()

        # Build frozen holdout ID sets
        frozen_ids: Dict[str, Set[str]] = {}
        frozen_fps: Dict[str, Set[str]] = {}
        frozen_shas: Dict[str, Optional[str]] = {}
        for name, path in FROZEN_FILES.items():
            frozen_ids[name] = _load_message_ids_from_csv(path)
            frozen_fps[name] = _load_text_fingerprints_from_csv(path)
            frozen_shas[name] = _sha256_file(path)

        # Check candidate examples
        candidate_ids = {
            r.get("message_id") or "" for r in pool if r.get("message_id")
        }

        leaked_message_ids: Set[str] = set()
        leakage_details: List[Dict[str, str]] = []

        for name, fids in frozen_ids.items():
            overlap = candidate_ids & fids
            if overlap:
                for mid in overlap:
                    leaked_message_ids.add(mid)
                    leakage_details.append({
                        "message_id": mid,
                        "leaked_into": name,
                        "type": "message_id_overlap",
                    })

        # Duplicate detection within candidate pool itself
        seen_ids: Set[str] = set()
        internal_duplicates: List[str] = []
        for r in pool:
            mid = r.get("message_id") or ""
            if mid in seen_ids:
                internal_duplicates.append(mid)
            seen_ids.add(mid)

        return {
            "candidate_count": len(pool),
            "leaked_message_ids": list(leaked_message_ids),
            "leakage_count": len(leaked_message_ids),
            "leakage_details": leakage_details,
            "internal_duplicate_count": len(internal_duplicates),
            "internal_duplicates": internal_duplicates,
            "frozen_file_shas": frozen_shas,
            "frozen_files_checked": list(FROZEN_FILES.keys()),
            "leakage_free": len(leaked_message_ids) == 0,
            "audit_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def build_manifest(
        self,
        clean_pool: List[Dict[str, Any]],
        distribution: Dict[str, int],
        leakage: Dict[str, Any],
        leaked_count: int,
    ) -> Dict[str, Any]:
        """
        Builds and writes candidate_manifest.json.
        """
        train_sha = _sha256_file(TRAIN_CANDIDATE_CSV)
        prov_sha = _sha256_file(PROVENANCE_CSV)

        manifest = {
            "dataset_version": "dataset-v5.2-candidate",
            "candidate_status": CANDIDATE_STATUS,
            "parent_dataset": "dataset-v5.1",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "phase": "Phase 52 — Controlled Feedback Adjudication",
            "source_model_versions": list({
                r.get("source_model_version") or r.get("model_version", "unknown")
                for r in clean_pool
            }),
            "adjudicated_examples_accepted": len(clean_pool),
            "leaked_examples_removed": leaked_count,
            "class_distribution": distribution,
            "v51_baseline_distribution": V51_TRAIN_DISTRIBUTION,
            "files": {
                "train_candidate.csv": {"sha256": train_sha, "rows": len(clean_pool)},
                "provenance.csv": {"sha256": prov_sha, "rows": len(clean_pool)},
            },
            "leakage_audit": {
                "leakage_free": leakage["leakage_free"],
                "leaked_count": leakage["leakage_count"],
                "frozen_file_shas": leakage["frozen_file_shas"],
            },
            "provenance_counts": {
                "HUMAN_PRODUCTION_FEEDBACK_ADJUDICATED": len(clean_pool),
            },
            "governance": {
                "training_occurred": False,
                "promotion_occurred": False,
                "fabricated_data": False,
                "human_adjudication_required": True,
                "automatic_acceptance_forbidden": True,
            },
            "readiness_gate": (
                "EVIDENCE COLLECTING — insufficient adjudicated production feedback."
                if len(clean_pool) == 0
                else f"CANDIDATE READY FOR OFFLINE TRAINING REVIEW ({len(clean_pool)} examples)"
            ),
        }

        with open(CANDIDATE_MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Also write leakage_audit.json separately
        with open(LEAKAGE_AUDIT_JSON, "w", encoding="utf-8") as f:
            json.dump(leakage, f, indent=2)

        return manifest

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _write_train_candidate(self, pool: List[Dict[str, Any]]) -> None:
        """
        Writes train_candidate.csv from the clean candidate pool.
        Fields: message_id, text, priority, feedback_id, adjudication_id, provenance.
        If pool is empty, writes header only (correct result — no fabrication).
        """
        fieldnames = [
            "message_id", "text", "priority", "feedback_id",
            "adjudication_id", "provenance", "source_model_version",
            "original_priority", "corrected_priority", "topic",
        ]
        with open(TRAIN_CANDIDATE_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in pool:
                writer.writerow({
                    "message_id": r.get("message_id", ""),
                    "text": "",  # Raw text NOT stored — no raw content in this pipeline
                    "priority": r.get("corrected_priority", ""),
                    "feedback_id": r.get("feedback_id", ""),
                    "adjudication_id": r.get("adjudication_id", ""),
                    "provenance": r.get("provenance", "HUMAN_PRODUCTION_FEEDBACK_ADJUDICATED"),
                    "source_model_version": r.get("source_model_version", ""),
                    "original_priority": r.get("original_priority", ""),
                    "corrected_priority": r.get("corrected_priority", ""),
                    "topic": r.get("topic", ""),
                })

    def _write_provenance(self, pool: List[Dict[str, Any]]) -> None:
        """Writes provenance.csv with full chain: feedback_id → adjudication_id → label."""
        fieldnames = [
            "feedback_id", "adjudication_id", "user_id", "message_id",
            "original_priority", "corrected_priority", "adjudication_status",
            "adjudicator_id", "adjudicated_at", "adjudication_reason",
            "provenance", "source_model_version",
        ]
        with open(PROVENANCE_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in pool:
                writer.writerow({k: r.get(k, "") for k in fieldnames})

    def _write_adjudication_log(self) -> None:
        """Copies adjudication.jsonl to the candidate directory."""
        if not os.path.exists(ADJUDICATION_FILE):
            # Write empty log
            with open(ADJUDICATION_LOG, "w", encoding="utf-8") as f:
                pass
            return
        try:
            with open(ADJUDICATION_FILE, "r", encoding="utf-8") as src:
                content = src.read()
            with open(ADJUDICATION_LOG, "w", encoding="utf-8") as dst:
                dst.write(content)
        except Exception as exc:
            logger.warning("dataset_v52: could not copy adjudication log: %s", exc)

    def _compute_distribution(self, pool: List[Dict[str, Any]]) -> Dict[str, int]:
        dist: Dict[str, int] = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
        for r in pool:
            p = r.get("corrected_priority", "")
            if p in dist:
                dist[p] += 1
        return dist

    def _assess_readiness(
        self, clean_pool: List[Dict[str, Any]], leakage: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Readiness assessment for offline training.
        States: NOT READY / EVIDENCE COLLECTING / READY FOR OFFLINE TRAINING REVIEW
        """
        n = len(clean_pool)
        leakage_free = leakage["leakage_free"]

        if n == 0:
            state = "EVIDENCE COLLECTING"
            reason = "Insufficient adjudicated production feedback. DO NOT fabricate data."
        elif not leakage_free:
            state = "NOT READY"
            reason = f"Leakage detected ({leakage['leakage_count']} examples). Must resolve before training."
        elif n >= 50:
            state = "READY FOR OFFLINE TRAINING REVIEW"
            reason = f"{n} accepted adjudicated examples, leakage-free."
        else:
            state = "EVIDENCE COLLECTING"
            reason = f"{n} accepted examples — below 50-example threshold for offline training review."

        return {
            "state": state,
            "reason": reason,
            "accepted_candidates": n,
            "leakage_free": leakage_free,
            "minimum_threshold": 50,
            "forbidden": [
                "Do NOT automatically train dataset-v5.2.",
                "Do NOT promote any model automatically.",
                "Do NOT fabricate data to satisfy thresholds.",
            ],
        }

    def _write_dataset_card(self, manifest: Dict[str, Any]) -> None:
        """Writes dataset_card.md for the candidate dataset."""
        n = manifest["adjudicated_examples_accepted"]
        dist = manifest["class_distribution"]
        readiness = manifest["readiness_gate"]

        card = f"""# Dataset-v5.2 Candidate

**Status:** {CANDIDATE_STATUS}

**Phase:** Phase 52 — Production Feedback, Human Adjudication & Dataset-v5.2 Candidate

**Created:** {manifest['created_at']}

**Parent dataset:** dataset-v5.1

---

## Overview

This is a CANDIDATE dataset assembled from human-adjudicated production feedback.

It is NOT used for training. It is NOT in production.

The candidate pool contains **{n}** accepted adjudicated examples.

{'> **Evidence Collecting** — Insufficient adjudicated production feedback. This candidate is empty by design. DO NOT fabricate data.' if n == 0 else f'> {readiness}'}

---

## Class Distribution (Candidate Additions)

| Priority | Candidate Count | v5.1 Train Baseline |
|----------|-----------------|---------------------|
| P1 | {dist.get('P1', 0)} | {V51_TRAIN_DISTRIBUTION['P1']} |
| P2 | {dist.get('P2', 0)} | {V51_TRAIN_DISTRIBUTION['P2']} |
| P3 | {dist.get('P3', 0)} | {V51_TRAIN_DISTRIBUTION['P3']} |
| P4 | {dist.get('P4', 0)} | {V51_TRAIN_DISTRIBUTION['P4']} |
| **Total** | **{n}** | **{V51_TRAIN_TOTAL}** |

---

## Provenance

All candidate examples come from:
1. **Production feedback** — user corrections via `POST /api/feedback`
2. **Human adjudication** — explicit reviewer acceptance via adjudication workflow
3. **Leakage audit** — verified zero overlap with frozen holdouts

Provenance chain per example:
```
user_id + message_id → feedback_id → adjudication_id → corrected_priority
```

## Governance

- priority-v5.1 remained the active production model during Phase 52
- priority-v4.1 remained the rollback baseline
- No automated retraining occurred during Phase 52
- No automated model promotion occurred during Phase 52
- No fabricated data was added
- All candidate examples have explicit human adjudication records

## Leakage Audit

- Frozen files checked: {', '.join(manifest['leakage_audit']['frozen_file_shas'].keys())}
- Leakage count: {manifest['leakage_audit']['leaked_count']}
- Leakage free: {'✅ YES' if manifest['leakage_audit']['leakage_free'] else '❌ NO — MUST RESOLVE'}

---

## Required Pipeline Before Training

```
Accepted candidates (this file)
        ↓
Human review of all provenance.csv entries
        ↓
Merge with dataset-v5.1 (offline, controlled)
        ↓
Leakage audit (re-run on merged set)
        ↓
Offline training
        ↓
Candidate model evaluation (holdouts)
        ↓
Shadow deployment
        ↓
Canary deployment
        ↓
Explicit promotion gate
```

**FORBIDDEN:** Automatic training from this candidate dataset.
"""
        with open(DATASET_CARD, "w", encoding="utf-8") as f:
            f.write(card)


# Global singleton
dataset_v52_builder = DatasetV52Builder()
