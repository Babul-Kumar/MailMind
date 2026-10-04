# MailMind — Render Dependency & Free Tier Audit Report

---

## 1. Missing Dependency Fixed

### Issue Encountered
During Render deployment startup, Uvicorn crashed with:
```text
ModuleNotFoundError: No module named 'bs4'
```

### Root Cause
`backend/app/gmail/parser.py` imports `BeautifulSoup` on line 5:
```python
from bs4 import BeautifulSoup
```
While `beautifulsoup4` (v4.15.0) was present in the local development virtual environment, it was omitted from the root `requirements.txt`. When Render installed dependencies via `pip install -r requirements.txt`, `bs4` was absent in the clean container, causing an immediate startup failure.

### Remediation
Added `beautifulsoup4>=4.12.0` under `# HTML / MIME Email Body Parsing` in `requirements.txt`.
Verified with:
```bash
python -c "from bs4 import BeautifulSoup; print('BeautifulSoup OK')"
# Output: BeautifulSoup OK
```

---

## 2. Dependencies Removed

The following heavy deep learning packages were removed from `requirements.txt`:
1. `torch>=2.0.0`
2. `transformers>=4.30.0`

---

## 3. Why Each Removed Dependency Was Unnecessary for Production

| Dependency | Original Purpose | Why Unnecessary in Production | Render Free Tier Impact |
| :--- | :--- | :--- | :--- |
| **`torch`** | Offline exploratory research & BiLSTM benchmarking in `index.ipynb` | The production classifier is a frozen linear pipeline (**TF-IDF + Logistic Regression**). Neither `backend/app/` nor any production test imports `torch`. | Installing PyTorch wheels downloads ~800MB–2GB of binaries and CUDA bindings, exhausting Render's 512MB RAM and 15-minute build limit. |
| **`transformers`** | Offline DistilBERT fine-tuning comparisons in research notebooks | Pure linear inference does not load Hugging Face tokenizers or neural transformers. Zero runtime imports across `backend/app/`. | Avoids pulling heavy PyTorch/Hugging Face sub-dependencies, saving gigabytes of disk and minutes of build time. |

---

## 4. Final `requirements.txt` Summary

```text
# CSE472 - AI Email Priority Classification System
# Core Machine Learning & Data Processing (Frozen TF-IDF + Logistic Regression)
scikit-learn>=1.3.0
joblib>=1.3.0
pandas>=2.0.0
numpy>=1.24.0

# HTML / MIME Email Body Parsing
beautifulsoup4>=4.12.0

# Production REST API & Server
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
pydantic>=2.0.0

# Google Workspace / Gmail API (Read-Only OAuth 2.0)
google-api-python-client>=2.100.0
google-auth>=2.23.0
google-auth-oauthlib>=1.1.0
google-auth-httplib2>=0.1.1

# Testing & Quality Assurance
pytest>=7.4.0
httpx>=0.24.0
```

### Complete Runtime Dependency Trace
Every remaining dependency corresponds directly to an imported package in `backend/app`:
- `scikit-learn`, `joblib`, `numpy`, `pandas`: `backend.app.ml.predictor`, `backend.app.ml.registry`
- `beautifulsoup4`: `backend.app.gmail.parser`
- `fastapi`, `uvicorn`, `pydantic`: `backend.app.main`, `backend.app.api.*`
- `google-api-python-client`, `google-auth*`: `backend.app.gmail.client`, `backend.app.api.routes_auth`
- `pytest`, `httpx`: `tests/` and Starlette `TestClient`

---

## 5. Backend Import Verification

Verified that both `BeautifulSoup` and the full FastAPI backend import cleanly in a clean Python process:

```bash
python -c "from bs4 import BeautifulSoup; print('BeautifulSoup OK')"
# BeautifulSoup OK

python -c "from backend.app.main import app; print('FastAPI import OK')"
# FastAPI import OK
```

---

## 6. Test Results

### 6.1 Backend Test Suites
- **Full Backend Regression Suite**: `pytest tests/ -q`
  - **Result**: **591 / 591 PASSED** (0 failures, 0 errors, 33 warnings)
  - **Duration**: 59.13s
- **Render Deployment Readiness Suite**: `pytest tests/test_render_deployment_readiness.py -v`
  - **Result**: **13 / 13 PASSED**
- **Environment Separation Suite**: `pytest tests/test_environment_separation.py -v`
  - **Result**: **10 / 10 PASSED**
- **UI Refinement & Scan Engine Suite**: `pytest tests/test_ui_refinement.py -v`
  - **Result**: **6 / 6 PASSED**

### 6.2 Frontend Verification
- **Unit & Formatting Tests**: `npm test -- --run`
  - **Result**: **12 / 12 PASSED** (226ms)
- **Production Build**: `npm run build`
  - **Result**: Built cleanly in 4.56s (0 errors)

---

## 7. Confirmation That the Frozen Model Was Not Modified

Cryptographic SHA-256 validation verifies that all model artifacts and evaluation datasets remain 100% frozen:

| Artifact | File Path | Expected SHA-256 | Verified SHA-256 | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Production Model** | `dataset/models/priority-v5.1-candidate/model.joblib` | `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06` | `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06` | **VERIFIED (UNCHANGED)** |
| **Rollback Model** | `dataset/models/priority-v4.1/model.joblib` | `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0` | `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0` | **VERIFIED (UNCHANGED)** |
| **Frozen Holdout** | `dataset/processed/test.csv` | `6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138` | `6841cd44901fa56242bf3752257e991fd7ff474ed7e0f7a5d2b7065a0827c138` | **VERIFIED (UNCHANGED)** |

- Zero models were retrained, fitted, refitted, or recalibrated.
- Zero model files were modified.
- Zero external generative AI or LLM API calls exist in the runtime.
- The build is lightweight and optimized to deploy seamlessly on Render's Free Tier.
