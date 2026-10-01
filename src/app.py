"""Backward-compatibility wrapper for backend.app.main."""
from backend.app.main import app
from backend.app.gmail.client import fetch_emails
from backend.app.ml.predictor import load_model, predict_batch, get_model_info
from backend.app.ml.priority import PRIORITY_MAPPING
