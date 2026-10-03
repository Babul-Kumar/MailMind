import hashlib
import os
from pathlib import Path
import pytest

EXPECTED_V51_SHA = "8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06"
EXPECTED_V41_SHA = "09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0"
EXPECTED_TEST_CSV_SHA = "6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138"


def compute_sha256(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


@pytest.fixture(scope="session", autouse=True)
def protect_production_state():
    """Pre-test check & post-test verification of immutable artifacts and state."""
    repo_root = Path(__file__).resolve().parent.parent
    v51_path = repo_root / "dataset" / "models" / "priority-v5.1-candidate" / "model.joblib"
    v41_path = repo_root / "dataset" / "models" / "priority-v4.1" / "model.joblib"
    test_csv = repo_root / "dataset" / "processed" / "test.csv"
    registry_path = repo_root / "dataset" / "models" / "registry.json"
    feedback_path = repo_root / "dataset" / "feedback" / "feedback.jsonl"
    canary_path = repo_root / "dataset" / "monitoring" / "canary_config.json"

    assert v51_path.exists(), "v5.1 model missing"
    assert v41_path.exists(), "v4.1 model missing"
    assert test_csv.exists(), "test.csv holdout missing"

    assert compute_sha256(str(v51_path)) == EXPECTED_V51_SHA, "v5.1 hash corrupted pre-test"
    assert compute_sha256(str(v41_path)) == EXPECTED_V41_SHA, "v4.1 hash corrupted pre-test"
    assert compute_sha256(str(test_csv)) == EXPECTED_TEST_CSV_SHA, "test.csv hash corrupted pre-test"

    reg_content = registry_path.read_text(encoding="utf-8") if registry_path.exists() else None
    feedback_content = feedback_path.read_text(encoding="utf-8") if feedback_path.exists() else None
    canary_content = canary_path.read_text(encoding="utf-8") if canary_path.exists() else None

    pred_logs_dir = repo_root / "dataset" / "monitoring" / "prediction_logs"
    pred_logs_backup = {}
    if pred_logs_dir.exists():
        for log_file in pred_logs_dir.glob("*.jsonl"):
            pred_logs_backup[log_file.name] = log_file.read_text(encoding="utf-8")

    yield

    # Post-test verification
    assert compute_sha256(str(v51_path)) == EXPECTED_V51_SHA, "v5.1 hash mutated during tests"
    assert compute_sha256(str(v41_path)) == EXPECTED_V41_SHA, "v4.1 hash mutated during tests"
    assert compute_sha256(str(test_csv)) == EXPECTED_TEST_CSV_SHA, "test.csv hash mutated during tests"

    # Restore dynamic tracking files if any test touched them
    if reg_content is not None:
        registry_path.write_text(reg_content, encoding="utf-8")
    if feedback_content is not None:
        feedback_path.write_text(feedback_content, encoding="utf-8")
    if canary_content is not None:
        canary_path.write_text(canary_content, encoding="utf-8")

    # Restore prediction logs directory to clean state
    if pred_logs_dir.exists():
        for fname, content in pred_logs_backup.items():
            (pred_logs_dir / fname).write_text(content, encoding="utf-8")
        for log_file in pred_logs_dir.glob("*.jsonl"):
            if log_file.name not in pred_logs_backup:
                try:
                    log_file.unlink()
                except Exception:
                    pass
