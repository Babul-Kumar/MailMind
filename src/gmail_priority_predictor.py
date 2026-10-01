"""Backward-compatibility wrapper for backend.app.ml."""
from backend.app.ml.predictor import (
    load_model,
    format_email_text,
    predict_email,
    predict_batch,
    get_model_info
)
from backend.app.ml.priority import (
    PRIORITY_MAPPING,
    PRIORITY_DESCRIPTIONS,
    PRIORITY_RANK
)
from backend.app.ml.explanations import (
    extract_feature_signals,
    explain_prediction
)
