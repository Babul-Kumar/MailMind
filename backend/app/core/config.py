import os
from typing import List

# Base repository root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Data and session persistence directory (supports Render Persistent Disk mount e.g. /var/data)
DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "google_auth"))

# Authentication and OAuth client secret path
CREDENTIALS_FILE = (
    os.getenv("CREDENTIALS_PATH")
    or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    or os.path.join(BASE_DIR, "google_auth", "credentials.json")
)
TOKEN_FILE = (
    os.path.join(DATA_DIR, "token.json")
    if os.path.exists(os.path.join(DATA_DIR, "token.json"))
    else os.path.join(BASE_DIR, "google_auth", "token.json")
)

# Machine Learning Artifacts (FROZEN)
MODEL_PATH = os.path.join(BASE_DIR, "dataset", "models", "tfidf_logistic_baseline.joblib")
TEST_CSV_PATH = os.path.join(BASE_DIR, "dataset", "processed", "test.csv")

# Frontend static distribution build directory
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")

# Gmail Read-Only OAuth Scope
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Base CORS allowed origins (Local development defaults)
_DEFAULT_ORIGINS: List[str] = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8001",
    "http://localhost:8001",
    "http://127.0.0.1:8080",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

# Support production custom domains via ALLOWED_ORIGINS or BASE_URL
_extra_origins_env = os.getenv("ALLOWED_ORIGINS", "")
_extra_origins = [o.strip() for o in _extra_origins_env.split(",") if o.strip()]
_base_url_env = os.getenv("BASE_URL", "").strip().rstrip("/")
if _base_url_env and _base_url_env not in _extra_origins:
    _extra_origins.append(_base_url_env)

ALLOWED_ORIGINS: List[str] = list(dict.fromkeys(_DEFAULT_ORIGINS + _extra_origins))

