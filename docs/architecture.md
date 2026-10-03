# MailMind System Architecture Specification

**System**: MailMind AI Email Priority Classification System  
**Version**: `v5.4.1-verified-production`  
**Active Production Model**: `priority-v5.1` (SHA-256: `8524ad73965859ee022f1271caee0040928e7805ab7d32c49b2f26e994f98c06`)  
**Rollback Model Baseline**: `priority-v4.1` (SHA-256: `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0`)  
**Target Environment**: Enterprise Google Workspace / Gmail Integration  

---

## 1. High-Level System Architecture

MailMind operates on a decoupled client-server architecture consisting of a modern React/Vite single-page application (SPA) and an asynchronous Python FastAPI service. The backend interfaces with the official Google Gmail REST API via user-delegated OAuth 2.0 credentials and executes on-device inference using scikit-learn machine learning pipelines hardened with domain refinement rules.

```mermaid
graph TD
    User([User Browser]) -->|HTTPS / UI Interactions| Frontend[React 18 / Vite SPA]
    Frontend -->|REST API / HttpOnly Cookie| Backend[FastAPI Backend Application]
    
    subgraph Security & Session
        Backend -->|Session Lookup & Path Guard| SessionMgr[SessionManager / SESSIONS_DIR]
    end

    subgraph External Cloud Services
        Backend -->|OAuth 2.0 PKCE / Readonly Scope| GoogleAuth[Google Identity / OAuth]
        Backend -->|Message Discovery & Snippet Fetch| GmailAPI[Google Gmail API v1]
    end

    subgraph Data & Storage Layer
        Backend -->|User-Scoped Cache| SQLiteCache[(SQLite Cache: mailmind_cache.db)]
        Backend -->|Feedback Append Store| FeedbackStore[(Feedback Store: feedback.jsonl)]
        Backend -->|Per-User Audit Logs| PredictionLogs[(Prediction Logs: hashed_user.jsonl)]
    end

    subgraph Machine Learning Subsystem
        Backend -->|Inference Execution| Predictor[Predictor Pipeline]
        Predictor -->|Dynamic Active Pointer| ModelReg[(Model Registry: registry.json)]
        ModelReg -->|Read-Only Model Weights| ModelV51[Active Model: priority-v5.1]
        ModelReg -.->|Instant Rollback Pointer| ModelV41[Rollback Model: priority-v4.1]
        Predictor -->|Domain Contextual Safety| Refinement[Refinement & Deadline Engine]
    end
```

---

## 2. Authentication Flow

Authentication is executed via Google OAuth 2.0 with Proof Key for Code Exchange (PKCE) and state protection.

```mermaid
sequenceDiagram
    autonumber
    actor User as User Browser
    participant FE as React Frontend
    participant BE as FastAPI Backend
    participant SM as Session Manager
    participant GAuth as Google OAuth 2.0
    participant GMail as Gmail API

    User->>FE: Click "Continue with Google"
    FE->>BE: GET /api/auth/login?prompt=select_account
    BE->>BE: Generate cryptographic State & PKCE Code Verifier
    BE-->>FE: Return Google OAuth Authorization URL
    FE->>GAuth: Redirect to accounts.google.com
    User->>GAuth: Authenticate & Consent (gmail.readonly scope)
    GAuth-->>BE: Redirect to /api/auth/callback?code=...&state=...
    BE->>BE: Validate State & Consume PKCE Verifier
    BE->>GAuth: Exchange authorization code for OAuth tokens
    GAuth-->>BE: Return Access Token & Refresh Token
    BE->>GMail: GET /users/me/profile (Verify Identity)
    GMail-->>BE: Return emailAddress & user_id
    BE->>SM: Create new isolated session (random token)
    SM->>SM: Validate safe session ID & persist session
    BE-->>User: Set-Cookie: mailmind_session (HttpOnly, SameSite=Lax, Secure in Prod)
    BE-->>FE: Redirect 302 to /
    FE->>BE: GET /api/auth/status
    BE-->>FE: Return { authenticated: true, user: { email, masked_email, user_id } }
```

### Security Properties
- **Zero Client-Side Credentials**: OAuth client secrets, access tokens, and refresh tokens are stored exclusively in backend sessions and are never transmitted to the frontend.
- **Session Hardening**: Session IDs are constrained to `^[A-Za-z0-9_\-~]{16,128}$` and strictly validated against path traversal (`_is_safe_session_id`).
- **Cookie Flags**: In production (`ENVIRONMENT=production`), cookies enforce `Secure=True`, preventing transmission over unencrypted HTTP.

---

## 3. Gmail Ingestion & Mailbox Scan Flow

The scan pipeline discovers email headers and metadata without storing raw email bodies permanently on disk.

```mermaid
sequenceDiagram
    autonumber
    participant FE as React Frontend
    participant BE as FastAPI Backend
    participant GMail as Gmail API
    participant Cache as SQLite Cache
    participant ML as ML Predictor

    FE->>BE: POST /api/scan/start { scope: 'mailbox', mode: 'incremental', query: null }
    BE->>BE: Verify active session from cookie
    BE->>BE: Normalize & whitelist parameters (query length <= 200)
    BE->>GMail: users.messages.list(q, pageToken)
    GMail-->>BE: List of message IDs
    BE->>Cache: Filter message IDs already cached for user_id and active model
    BE-->>FE: Return scan initiated / status polling URL

    loop For uncached / modified message IDs in batches
        BE->>GMail: users.messages.get(id, format='metadata')
        GMail-->>BE: Headers (Subject, From, Date) & Snippet
        BE->>ML: predict_email(subject, snippet, from_addr, date)
        ML-->>BE: Return { predicted_priority, confidence, action_required, deadline_status, topic, needs_attention }
        BE->>Cache: UPSERT into email_cache (user_id, message_id, model_version, ...)
    end

    FE->>BE: GET /api/emails?page=1&pageSize=50
    BE->>Cache: SELECT from email_cache WHERE user_id = ? ORDER BY date DESC
    Cache-->>BE: Paginated email records
    BE-->>FE: Return { total, emails: [...] }
```

---

## 4. Prediction Flow & Refinement Pipeline

MailMind decouples raw statistical inference from domain-specific deterministic safety rules.

```mermaid
flowchart TD
    RawInput[Email: Subject, Snippet, Sender, Date] --> Formatter[Text Formatter: 'Subject Snippet']
    Formatter --> Vectorizer[TF-IDF Vectorizer: 68,394 features]
    Vectorizer --> LogReg[Logistic Regression Classifier]
    LogReg --> RawScores[Raw Class Probabilities: P1, P2, P3, P4]
    
    RawScores --> RefinementEngine{Refinement & Safety Rules}
    RawInput --> RefinementEngine
    
    RefinementEngine -->|Security / Auth Override| P1_Override[Priority: P1 Critical]
    RefinementEngine -->|Active Assignment / Imminent Due| P2_Override[Priority: P2 Urgent]
    RefinementEngine -->|Routine Marketing / Social Digest| Downgrade[Priority: P3 / P4]
    RefinementEngine -->|Statistical Confidence Preserved| ModelClass[Statistical Priority]
    
    P1_Override --> Synthesizer
    P2_Override --> Synthesizer
    Downgrade --> Synthesizer
    ModelClass --> Synthesizer
    
    subgraph Signal Decomposition
        RawInput --> DeadlineDetector[Temporal Parser & Deadline Engine]
        DeadlineDetector --> DeadlineStatus[Status: IMMINENT / UPCOMING / EXTENDED / OVERDUE / NONE]
        
        RawInput --> ActionClassifier[Action Intent Classifier]
        ActionClassifier --> ActionRequired[Action Required: True / False]
        
        RawInput --> TopicTaxonomy[Domain Topic Classifier]
        TopicTaxonomy --> Topic[Topic: security / academic / operational / newsletter / social]
    end
    
    Synthesizer[Metadata Synthesizer] --> CompositeDecision[Compute Needs Attention]
    DeadlineStatus --> CompositeDecision
    ActionRequired --> CompositeDecision
    
    CompositeDecision --> FinalOutput[Final Classification Payload: Priority, Confidence, Action, Deadline, Needs Attention]
```

### Signal Separation Rationale
- **Priority (P1–P4)**: Represents intrinsic email importance and processing urgency.
- **Action Required (Boolean)**: Completely orthogonal to priority. For example, a low-priority routine survey (P3) may require user action, while an urgent high-priority server alert (P1) is purely informational.
- **Deadline Detection**: Identifies concrete temporal commitments, comparing due dates against message timestamp and current wall-clock time.
- **Needs Attention**: Evaluated as `(priority in ['P1', 'P2']) or action_required or (deadline_status in ['IMMINENT', 'OVERDUE'])`.

---

## 5. Feedback Governance & Human Adjudication Flow

Production feedback is strictly separated from model training. **Under no circumstances does user feedback trigger automatic model retraining or parameter fitting.**

```mermaid
sequenceDiagram
    autonumber
    actor User as User Browser
    participant BE as FastAPI Backend
    participant Cache as User Email Cache
    participant Feedback as feedback.jsonl
    participant Admin as Human Reviewer / ML Engineer
    participant Adjudicator as Adjudication Engine
    participant DatasetPool as Candidate Dataset Pool

    User->>BE: POST /api/feedback { message_id, corrected_priority, feedback_type, notes }
    BE->>BE: Validate session & user_id
    BE->>Cache: user_email_cache.get(user_id, message_id, model_version='priority-v5.1')
    Cache-->>BE: Verified ground-truth prediction record
    BE->>BE: Bind server-side predicted_priority, confidence, topic, and model_version
    BE->>Feedback: Append record to dataset/feedback/feedback.jsonl (provenance=PRODUCTION_FEEDBACK)
    BE-->>User: HTTP 200 OK ("Feedback recorded for review")

    Note over Feedback,Admin: Offline Governed Lifecycle
    Admin->>Adjudicator: Run adjudication audit CLI / review queue
    Adjudicator->>Admin: Present priority_wrong & safety cases
    Admin->>Adjudicator: Adjudicate: ACCEPT / REJECT with mandatory reason
    Adjudicator->>Adjudicator: Execute Holdout Leakage Audit against test.csv
    Adjudicator->>DatasetPool: Output candidate records to dataset/v5.x_candidate/
    Note over DatasetPool: Manual offline model training, shadow evaluation, canary testing, and explicit promotion
```

---

## 6. Model Lifecycle & Promotion Gates

Every ML model must progress through eight formal, non-bypassable promotion gates before production activation.

```mermaid
stateDiagram-v2
    [*] --> OfflineTraining: Curated & Adjudicated Dataset
    OfflineTraining --> BenchmarkAudit: Candidate Model Artifact
    
    state BenchmarkAudit {
        [*] --> HistoricalHoldout: test.csv (Accuracy >= 82%, Macro F1 >= 0.80)
        HistoricalHoldout --> ModernHoldout: modern_holdout.csv (P2 Recall >= 95%)
        ModernHoldout --> SafetyGates: 0 P1 Downgrades & 100% OTP Retention
    }
    
    BenchmarkAudit --> ShadowEvaluation: Passed All Benchmarks
    
    state ShadowEvaluation {
        [*] --> RealMailboxShadow: Dual-inference on live Gmail scan
        RealMailboxShadow --> LatencyCheck: Overhead <= 5.0ms
        LatencyCheck --> SafetyRetention: 0 Critical Security Downgrades
    }
    
    ShadowEvaluation --> CanaryRollout: Shadow Gate Approved
    
    state CanaryRollout {
        [*] --> Stage1_5pct: 5% Traffic Routing
        Stage1_5pct --> Stage2_10pct: 10% Traffic Routing
        Stage2_10pct --> Stage3_25pct: 25% Traffic Routing
        Stage3_25pct --> Stage4_50pct: 50% Traffic Routing
        Stage4_50pct --> Stage5_100pct: 100% Canary Verification
    }
    
    CanaryRollout --> ProductionPromotion: Canary Passed (13/13 Gates)
    ProductionPromotion --> [*]: Explicit Atomic Registry Update
    
    CanaryRollout --> EmergencyRollback: Any Safety Violation (P1 Downgrade / Exception)
    EmergencyRollback --> [*]: Instant Reversion to Rollback Model (v4.1)
```

---

## 7. Multi-User Isolation Architecture

MailMind isolates users at every logical and physical boundary:

```mermaid
graph TD
    subgraph User A Context
        SessionA[Session A: user_a_id]
        CacheA[(Cache A: WHERE user_id = user_a_id)]
        LogA[(Prediction Log: sha256_user_a.jsonl)]
    end

    subgraph User B Context
        SessionB[Session B: user_b_id]
        CacheB[(Cache B: WHERE user_id = user_b_id)]
        LogB[(Prediction Log: sha256_user_b.jsonl)]
    end

    subgraph Shared Immutables
        ModelRegistry[(Model Registry: registry.json)]
        ModelArtifact[Active Model Artifact: priority-v5.1]
    end

    SessionA --> CacheA
    SessionA --> LogA
    SessionB --> CacheB
    SessionB --> LogB
    
    CacheA -.->|No Cross-Read| CacheB
    LogA -.->|No Cross-Read| LogB
    
    SessionA --> ModelArtifact
    SessionB --> ModelArtifact
```

1. **Session Isolation**: Each user receives an independent cryptographic session ID bound to their unique Google account `user_id` and `email`.
2. **Cache Isolation**: The SQLite `email_cache` table uses a composite primary key `(user_id, message_id, model_version)`. Every query enforces `WHERE user_id = :user_id`.
3. **Feedback Isolation**: User feedback queries filter by `session.user_id`. Users cannot view or tamper with other users' feedback.
4. **Log Pseudonymization**: Prediction audit logs are written to per-user JSONL files named after a SHA-256 hash prefix of the user's ID (`predictions_<sha256[:16]>.jsonl`), preventing user enumeration.

---

## 8. Cache Architecture

The SQLite cache (`backend/mailmind_cache.db`) stores scan results to optimize latency and minimize Gmail API quota usage:

```sql
CREATE TABLE IF NOT EXISTS email_cache (
    user_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    thread_id TEXT,
    subject TEXT,
    from_address TEXT,
    date TEXT,
    snippet TEXT,
    predicted_priority TEXT,
    final_priority TEXT,
    confidence REAL,
    action_required INTEGER,
    deadline_detected INTEGER,
    deadline_date TEXT,
    deadline_status TEXT,
    topic TEXT,
    needs_attention INTEGER,
    first_seen_timestamp TEXT,
    last_updated_timestamp TEXT,
    PRIMARY KEY (user_id, message_id, model_version)
);
```

- **Composite Key**: `(user_id, message_id, model_version)` allows side-by-side coexistence of predictions across model version evaluations without collision or cache eviction.
- **No Raw Body**: Only message headers, snippets, and inference metadata are stored. Raw email message bodies are never written to the SQLite cache.

---

## 9. Rollback Architecture

MailMind incorporates an instantaneous, non-destructive rollback mechanism.

```mermaid
sequenceDiagram
    autonumber
    actor Admin as System Administrator / Canary Monitor
    participant Registry as models/registry.json
    participant Router as canary_router.py
    participant Predictor as predictor.py
    participant ModelV41 as priority-v4.1.joblib

    Admin->>Router: canary_router.rollback() OR registry update
    Router->>Registry: Update active_model -> "priority-v4.1"
    Router->>Predictor: invalidate_cached_pipeline()
    Predictor->>Predictor: Clear in-memory _CACHED_PIPELINE
    Note over Predictor: Next inference request executes:
    Predictor->>Registry: get_active_model_path() -> priority-v4.1
    Predictor->>ModelV41: Load verified baseline weights
    Predictor-->>Admin: Rollback completed in 0ms (zero server restart)
```

- **Rollback Target**: `priority-v4.1` (SHA-256: `09fe269f19ad6afb38e71b56f8c6ee7a386e59605c62c892478400bc09d5cbd0`).
- **Rollback Verification**: Instantaneous, zero-downtime transition without server reboots, cache deletions, or session resets.

---

## 10. Security Boundaries & Component Mutability

| Component | Mutability Classification | Security Boundary & Protections |
| :--- | :--- | :--- |
| **USER DATA** | **Transient / Ephemeral** | Raw email body and attachments are processed strictly in RAM during classification. Never written to disk or logs. |
| **MODEL ARTIFACT** | **IMMUTABLE (FROZEN)** | `priority-v5.1` and `priority-v4.1` are binary-locked and hash-verified before and after test execution. |
| **MODEL REGISTRY** | **Controlled / Versioned** | `dataset/models/registry.json` updated only via explicit, audited administrative promotions. |
| **FEEDBACK** | **Append-Only Store** | `dataset/feedback/feedback.jsonl` stores user-submitted corrections with cryptographic provenance. |
| **CACHE** | **Persistent Scoped Store** | `mailmind_cache.db` partitioned strictly by `user_id`. Stores only snippets and inference metadata. |
| **SESSION** | **Ephemeral Server State** | `SESSIONS_DIR` files protected by regex validation, realpath normalization, and commonpath enforcement. |
| **GMAIL API** | **External Boundary** | Communicates exclusively over TLS using OAuth 2.0 with minimal `https://www.googleapis.com/auth/gmail.readonly` scope. |
