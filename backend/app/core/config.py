import os
from typing import List

# Base repository root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Authentication and OAuth token paths
CREDENTIALS_FILE = os.path.join(BASE_DIR, "google_auth", "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, "google_auth", "token.json")

# Machine Learning Artifacts (FROZEN)
MODEL_PATH = os.path.join(BASE_DIR, "dataset", "models", "tfidf_logistic_baseline.joblib")
TEST_CSV_PATH = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")

# Frontend static distribution build directory
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")

# Gmail Read-Only OAuth Scope
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Local development CORS allowed origins
ALLOWED_ORIGINS: List[str] = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8001",
    "http://localhost:8001",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5173"
]
