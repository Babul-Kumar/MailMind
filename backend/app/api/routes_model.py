from fastapi import APIRouter, HTTPException
from backend.app.ml.predictor import load_model, get_model_info
from backend.app.ml.priority import PRIORITY_MAPPING
from backend.app.ml.registry import model_registry

router = APIRouter(tags=["Model"])


@router.get("/api/model-info")
@router.get("/api/model/info")
def model_information():
    """Returns metadata about the active version-controlled ML production model."""
    try:
        model = load_model()
        info = get_model_info(model)
        active_version = model_registry.get_active_version()
        meta = model_registry.get_active_metadata()

        return {
            "status": "success",
            "model_name": "TF-IDF + Logistic Regression",
            "model_version": active_version,
            "model_state": "Strictly Frozen",
            "lifecycle": "Version controlled",
            "dataset_version": meta.get("dataset_version", "dataset-v1"),
            "feature_version": meta.get("feature_version", "tfidf-v1"),
            "vocabulary_features": info.get("vocabulary_size", 0),
            "classes": info.get("classes", []),
            "priority_mapping": PRIORITY_MAPPING,
            "verification_status": "Zero Retraining during inference (read-only production)",
            "artifact_sha256": meta.get("artifact_sha256", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load model information: {str(e)}")
