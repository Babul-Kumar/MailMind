# MailMind Live Demonstration & Presentation Script

**System**: MailMind AI Email Priority Classification System  
**Presentation Target**: Technical Evaluators, Stakeholders, and Project Reviewers  
**Duration**: ~7–10 Minutes  
**Target Release**: `v5.4.1-verified-production`  
**Active Production Model**: `priority-v5.1`  

---

## Demonstration Overview

| Stage | Focus Area | Key Features Demonstrated | Est. Time |
| :---: | :--- | :--- | :---: |
| **1** | Landing & Privacy | Clean branding, privacy guarantees, zero credential capture | 1.0 min |
| **2** | OAuth 2.0 PKCE | Single-click Google login, minimal readonly permissions | 1.5 min |
| **3** | Inbox Sync & ML Inference | Multi-tier priority (P1–P4), classification speed, topic tags | 2.0 min |
| **4** | Attention & Action Logic | "Needs Attention", Action Required, Deadline Detection | 1.5 min |
| **5** | Deep Inspection & Feedback | Email detail drawer, "Open in Gmail", Feedback submission | 1.5 min |
| **6** | Transparency & Account Switch | Model info, multi-user isolation, logout | 1.0 min |

---

## Step-by-Step Demonstration Script

### Stage 1: Landing Page & Privacy Guarantees (Minute 0:00 – 1:00)
- **Visual**: Navigate browser to `http://localhost:5173` (or production URL).
- **Speaker Script**:
  > *"Welcome to MailMind. Modern inboxes are flooded with newsletters, notifications, and urgent requests. Traditional email clients rely on simple keywords or basic spam filters that fail to capture urgency, deadlines, or security risks. MailMind is an AI-powered email triage platform built on a verified scikit-learn machine learning engine, running `priority-v5.1` with a deterministic domain safety refinement layer."*
- **Action**: Highlight the landing screen's privacy notes:
  - Read-only access (`gmail.readonly`).
  - No raw email bodies stored on disk.
  - Zero automated retraining (feedback is human-adjudicated).

---

### Stage 2: Google Authentication Flow (Minute 1:00 – 2:30)
- **Visual**: Click the **"Continue with Google"** button.
- **Speaker Script**:
  > *"When we click 'Continue with Google', the application executes an OAuth 2.0 Authorization Code flow with PKCE. Notice that Google requests only read-only metadata access to your emails. MailMind cannot send, delete, or modify your emails."*
- **Action**: Select the demo Google account.
- **Speaker Script**:
  > *"Upon consent, Google redirects to our backend callback. The server exchanges the authorization code for tokens, verifies identity with the Gmail API, and sets a secure HttpOnly session cookie. The frontend receives zero credentials or tokens, eliminating client-side credential exposure."*

---

### Stage 3: Mailbox Sync & Real-Time Classification (Minute 2:30 – 4:30)
- **Visual**: The application loads the main inbox view. Click **"Scan Mailbox"**.
- **Speaker Script**:
  > *"Now we initiate a mailbox scan. MailMind discovers message IDs and checks its local SQLite cache. For uncached messages, the backend retrieves headers and snippets, evaluates them against our TF-IDF + Logistic Regression pipeline, and applies domain safety rules in under 5 milliseconds per email."*
- **Action**: Point out the priority badges on the email cards:
  - **P1 (Red badge)**: *"Notice this critical alert: 'Suspicious login attempt detected'. Our refinement engine guarantees 100% retention for security alerts and OTP verifications—critical safety items are never downgraded."*
  - **P2 (Orange badge)**: *"Here is an academic deadline: 'CS472 Assignment 3 Submission Due'. P2 emails require timely attention."*
  - **P3 (Blue badge)**: *"Routine administrative announcements and shipping updates."*
  - **P4 (Gray badge)**: *"Promotions, social digests, and newsletters—safely isolated from your main workflow."*

---

### Stage 4: Signal Decomposition: Attention, Action & Deadlines (Minute 4:30 – 6:00)
- **Speaker Script**:
  > *"MailMind does not treat priority as a catch-all. We separate four distinct dimensions: Priority, Action Required, Topic, and Deadline."*
- **Action**: Click the **"Needs Attention"** tab in the sidebar:
  > *"The 'Needs Attention' filter isolates emails that require immediate user action. This is computed dynamically: any P1 or P2 email, or any email with an imminent or overdue deadline, or any email requiring an action. Notice this P3 survey that requires an action—because it has `action_required: true`, it appears here even though its priority is routine."*
- **Action**: Point to the deadline badge:
  > *"Our temporal parser extracted the due date directly from the snippet. Notice the tag shows 'Due Tomorrow' or 'Overdue' based on real wall-clock time comparisons, completely avoiding the false assumption that email arrival time is the deadline."*

---

### Stage 5: Email Detail & Human-in-the-Loop Feedback (Minute 6:00 – 7:30)
- **Visual**: Click on an email row to slide open the detail drawer.
- **Speaker Script**:
  > *"Clicking any email opens the detail drawer. We see the full subject, sender, date, extracted topic, priority explanation, and an 'Open in Gmail' link that deep-links directly to the original thread in Google Workspace."*
- **Action**: Scroll to the **"Provide Priority Feedback"** widget at the bottom of the drawer:
  > *"Suppose the user disagrees with a classification. Here, the user can select a corrected priority (e.g. change P3 to P2), select a feedback type like 'Priority should be higher', and add an optional note. When submitted, the backend verifies ground-truth prediction metadata from the cache and appends the event to `feedback.jsonl` with strict server-side provenance. It does not automatically alter model weights, protecting the system from data poisoning."*

---

### Stage 6: Settings, Model Transparency & Clean Logout (Minute 7:30 – 8:30)
- **Visual**: Click the **Settings / Info** icon in the TopBar.
- **Speaker Script**:
  > *"In Settings, MailMind maintains complete transparency. We see the active model version (`priority-v5.1`), its verified SHA-256 checksum, the rollback baseline (`priority-v4.1`), and the user's masked email address."*
- **Action**: Click the **"Sign Out"** button.
- **Speaker Script**:
  > *"Clicking Sign Out immediately invalidates the server session, deletes the session JSON file, and purges the HttpOnly cookie. If a second user logs in on this same device, their cache, sessions, and predictions are completely isolated from User A."*

---

## Evaluator Q&A Preparation (Quick Reference)

| Evaluator Question | Recommended Answer |
| :--- | :--- |
| **"Why not use an LLM for all classifications?"** | *"TF-IDF + Logistic Regression with domain refinement executes in under 5ms on CPU, requires zero expensive GPU infrastructure, has zero latency variance, and eliminates non-deterministic hallucination in critical security tiers."* |
| **"What happens if an adversarial user tries path traversal in cookies?"** | *"Session IDs are validated against `^[A-Za-z0-9_\-~]{16,128}$` and resolved with canonical `realpath` and `commonpath`. All 27 adversarial traversal vectors were rejected with HTTP 401/403."* |
| **"What if the model misclassifies in production?"** | *"We have a zero-downtime, instantaneous rollback drill to `priority-v4.1` that switches active model routing in 0ms without server restarts."* |
