# CSE472 Live Demonstration Script: AI Email Priority Dashboard

**Course Project:** AI Email Priority Classification System  
**Presenter:** Babul Kumar  
**Target Duration:** 3–5 Minutes  
**Prerequisites:** Internet connection, Google Chrome or Firefox, active FastAPI server on port 8000.  

---

## 1. Pre-Flight Checklist (T-minus 2 Minutes)
1. Ensure virtual environment is active:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
2. Verify server is running on port 8000:
   ```bash
   python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read().decode())"
   ```
3. Open browser tab to `http://127.0.0.1:8000`.
4. Keep terminal window visible in split-screen to show server logs if requested.

---

## 2. Live Demo Script (Step-by-Step)

### Step 1: Introduction & Connection Verification (0:00 – 0:30)
- **Action:** Open `http://127.0.0.1:8000` in the browser. Point to the top-right status badge.
- **Spoken Narration:**
  > *"Welcome to the live demonstration of the AI Email Priority Classification Dashboard. As you can see in the upper right header, the application is authenticated to my Google account via OAuth 2.0 under a strictly read-only scope. The system displays 17,129 total messages in the mailbox, and the frozen machine learning model is pre-warmed in memory with over 66,000 vocabulary features."*

---

### Step 2: Live Ingestion & Triage Matrix (0:30 – 1:15)
- **Action:** Select **"20 Emails"** from the count dropdown and click the blue **"Sync Inbox"** button.
- **What Happens:** The progress bar animates, contacts the Gmail API, decodes MIME payloads, runs linear inference in ~12ms, and populates the inbox list.
- **Spoken Narration:**
  > *"When I click 'Sync Inbox', the system connects to the Gmail API, retrieves the latest 20 message threads, recursively parses their multipart MIME structures, and runs them through our frozen TF-IDF and Logistic Regression model. Notice the top triage bar: it immediately visualizes the operational distribution across our four priority tiers: P1 Critical, P2 Important, P3 Routine, and P4 Promotional."*

---

### Step 3: Priority Filtering & Interactive Triage (1:15 – 2:00)
- **Action:** Click the **"P4 Low / Noise"** tab, then the **"P2 Important"** tab, then the **"P1 Critical"** tab (or **"All"**).
- **What Happens:** The list instantly updates using reactive client-side filtering.
- **Spoken Narration:**
  > *"The dashboard enables instant triage. Clicking 'P4 Low' isolates promotional mail, marketing newsletters, and automated platform digests from senders like Coursera or Kaggle. Clicking 'P2 Important' isolates actionable business correspondence, project updates, and direct requests that require attention within 24 to 48 hours."*

---

### Step 4: Real-Time Keyword Search (2:00 – 2:30)
- **Action:** Type a keyword like `"Google"` or `"course"` or `"update"` into the live search input.
- **What Happens:** The email list filters in real time as keys are pressed. Clear the search box.
- **Spoken Narration:**
  > *"We also provide live client-side search. As I type in the search bar, the UI immediately filters across subjects, senders, and content snippets without requiring redundant server roundtrips."*

---

### Step 5: Model Explainability & Signal Attribution (2:30 – 3:30)
- **Action:** Click on an email card in the list to open the detail inspection view. Point to the **Model Confidence** and **Contributing Feature Signals** chips.
- **What Happens:** The detail panel displays the sender, subject, date, priority badge, confidence score, and top positive lexical signals (e.g., `['org', 'link', 'now']`).
- **Spoken Narration:**
  > *"Here is our model-grounded explainability system. When we inspect this email, we don't just see a black-box priority label. The system displays the exact model confidence calculated via the softmax probability. Furthermore, below the text, we display 'Top Contributing Signals'. These tokens are derived mathematically by multiplying the TF-IDF feature values by the learned logistic regression weights: $X_{0,j} 	imes 	heta_{k,j}$. This tells the user exactly which terms drove the model's decision."*

---

### Step 6: Low-Confidence Handling & Wrap-up (3:30 – 4:00)
- **Action:** Point out the confidence tier (High / Moderate / Low). Mention the low-confidence advisory note.
- **Spoken Narration:**
  > *"If an email's confidence falls below 40%, the interface displays an amber warning advisory recommending human review. This ensures the system acts as an intelligent co-pilot rather than an unquestioned authority. The entire system is backed by 31 passing automated tests and a strictly frozen test benchmark. That concludes the live demonstration."*

---

## 3. Fallback & Contingency Procedures

### Contingency A: Google OAuth Token Expired or Network Disconnected
If Google services are unreachable during the live demo:
1. Open terminal and run the self-contained mock test suite:
   ```powershell
   python tests/test_dashboard_api.py
   ```
2. Explain: *"The test suite includes mock unit tests that validate the entire inference pipeline, parameter bounds, and UI endpoints against simulated Gmail API payloads."*

### Contingency B: Port 8000 Already in Use
If port 8000 is occupied:
1. Identify and release the process:
   ```powershell
   Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
   ```
2. Or run on an alternative port:
   ```powershell
   uvicorn src.app:app --host 127.0.0.1 --port 8080
   ```

### Contingency C: Live Browser Inspection Alternative
If live sync is slow due to local WiFi:
1. Open the API documentation page: `http://127.0.0.1:8000/docs`
2. Execute `GET /api/model-info` to show the pre-warmed 66,526 vocabulary features and model state.
