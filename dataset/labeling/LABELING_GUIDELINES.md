# Email Priority Classification: Human Annotation Guidelines

**Version:** 1.0  
**Project:** CSE472 - Email Priority Labeling Pipeline  
**Target:** 4-Class Email Priority Classification (`P1`, `P2`, `P3`, `P4`)  

---

## 1. Core Annotation Philosophy

The goal of this labeling project is to classify incoming emails into **actionable operational priority levels for the recipient**.

> [!IMPORTANT]
> **Priority reflects urgency, required action, and operational consequence to the recipient — NOT whether the email is merely work-related or sent by a colleague.**

An email from the CEO about the annual corporate picnic is **work-related**, but its operational urgency is **Routine (P3)**. Conversely, an automated email from an external server notifying you that your cloud database credentials have been compromised is an automated system email, but its operational priority is **Critical (P1)**.

### Dispelling False Heuristics (What NOT to Assume)
Reviewers must actively avoid the following common cognitive shortcuts:

1. **DO NOT assume `deleted_items` = Low Priority (P4):**
   Employees routinely delete emails after resolving critical emergencies, or delete sensitive legal/financial emails after reading. Treat the content on its merits.
2. **DO NOT assume `calendar` = Routine (P3):**
   An emergency meeting called for 30 minutes from now to address a trading disaster is **P1**, not routine.
3. **DO NOT assume Internal Sender (`@enron.com`) = Important (P1/P2):**
   Internal senders routinely send casual chitchat, fantasy sports banter, lost-and-found notices, and mass corporate spam.
4. **DO NOT assume External Sender = Low Priority (P4):**
   Crucial communications come from external clients, outside legal counsel, regulatory bodies (FERC, SEC), counterparty brokers, and escrow agents.

---

## 2. Priority Class Definitions & Decision Matrix

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                Priority Decision Matrix                                │
├─────────┬──────────────────────┬──────────────────────┬────────────────────────────────┤
│ Priority│ Label Name           │ Time Horizon / SLA   │ Required Action                │
├─────────┼──────────────────────┼──────────────────────┼────────────────────────────────┤
│ P1      │ Critical / Urgent    │ Immediate (< 4 hrs)  │ Immediate intervention, crisis │
│         │                      │ or Hard Deadline     │ resolution, executive blocker. │
├─────────┼──────────────────────┼──────────────────────┼────────────────────────────────┤
│ P2      │ Important / Actionable│ Within 1–2 days     │ Active response, review, task  │
│         │                      │                      │ completion, meeting scheduling.│
├─────────┼──────────────────────┼──────────────────────┼────────────────────────────────┤
│ P3      │ Routine / Memos      │ No immediate action  │ Read for awareness, archive,   │
│         │                      │ (FYI / Reference)    │ status monitoring, recurring.  │
├─────────┼──────────────────────┼──────────────────────┼────────────────────────────────┤
│ P4      │ Low / Promotional    │ None                 │ Discard, ignore, unsubscribe,  │
│         │ / Noise              │                      │ non-work casual banter.        │
└─────────┴──────────────────────┴──────────────────────┴────────────────────────────────┘
```

---

## 3. Detailed Class Guidelines with Positive & Negative Examples

### 3.1 Class P1: Critical / Urgent
**Core Definition:** Emails that demand immediate attention, emergency intervention, immediate decisions under tight time constraints (same day / within hours), or communicate critical security, operational, or legal crises.

#### Criteria for P1:
- Explicit time-critical deadlines occurring today, within hours, or by close-of-business (COB/EOD).
- Trading desk outages, system crashes, power grid curtailments, or pipeline interruptions.
- Emergency regulatory or legal demands (court orders, subpoenas, imminent breach notices).
- Direct executive escalations requiring immediate sign-off to unblock business operations.

#### Positive Examples (Correctly P1):
* **Example 1.1 (Operational Emergency):**
  > *"URGENT: California power scheduling feed down at SP15. CAISO cut-off is in 45 minutes (14:00 PPT). Need manual deal override entered immediately or we face severe imbalance penalties."*  
  > **Why P1:** High financial consequence, immediate operational failure, tight hard deadline (<45 minutes).
* **Example 1.2 (Security / Access Incident):**
  > *"Security Alert: Multiple unauthorized login attempts detected on your trading terminal from IP 198.51.100.24. Your account has been temporarily restricted. Reply immediately to IT Security to verify your identity and restore access before market open."*  
  > **Why P1:** Blocking operational access, security breach risk, requires immediate verification.
* **Example 1.3 (Executive Deal Blocker):**
  > *"Phillip - Citibank is threatening to pull the credit facility if the signed guarantee is not wired by 3:00 PM today. Please execute the attached signature page and fax back now."*  
  > **Why P1:** Immediate deadline (today 3 PM), existential business/credit impact, requires immediate action.

#### Negative Examples (NOT P1):
* **Example 1.4 (False Urgency / Subject Trap):**
  > *"Subject: URGENT!!! Read our weekly newsletter on gas industry trends"*  
  > **Correct Label:** **P3 (or P4)**. The content is marketing/informational with artificial sensationalism.
* **Example 1.5 (Important but Not Critical):**
  > *"Please review the 40-page draft contract for the Duke Energy deal when you have time this week and send comments by next Monday."*  
  > **Correct Label:** **P2**. Substantive and important, but lacks immediate crisis urgency.

---

### 3.2 Class P2: Important / Actionable
**Core Definition:** Substantive, direct work requests, collaboration, and communications that require an active response, task execution, review, or decision within a normal business timeframe (typically 1–3 business days).

#### Criteria for P2:
- Direct inquiries from managers, direct reports, or project collaborators asking specific questions.
- Document review requests (contracts, models, drafts, presentations, budgets).
- Meeting scheduling, interview coordination, or agenda planning.
- Task delegation or operational handoffs requiring follow-through.

#### Positive Examples (Correctly P2):
* **Example 2.1 (Direct Task Request):**
  > *"Randy - Can you prepare a schedule of the salary and grade levels for everyone in the gas scheduling group? I need your thoughts on adjustments by Thursday so we can finalize the Q3 budget."*  
  > **Why P2:** Direct managerial request, actionable task, specific delivery timeline (Thursday).
* **Example 2.2 (Meeting Coordination):**
  > *"Greg - Following up on our discussion yesterday regarding the pipeline capacity allocation. Let's shoot for a 30-minute sync Tuesday at 11:45 AM. Does that time work for you?"*  
  > **Why P2:** Direct interpersonal scheduling, requires confirmation, essential for project progress.
* **Example 2.3 (Contract Review):**
  > *"Mark, attached is the revised master swap agreement with Morgan Stanley reflecting our terms on credit thresholds. Please review section 4.2 and let me know if legal approves the language."*  
  > **Why P2:** Core business workflow, requires substantive legal review and affirmative feedback.

#### Negative Examples (NOT P2):
* **Example 2.4 (FYI Information Dump):**
  > *"Attached is the completed Q2 financial report for your records. No action needed on your end."*  
  > **Correct Label:** **P3**. Explicitly states no action is needed; purely for reference.
* **Example 2.5 (Automated System Notice):**
  > *"Your timesheet has been automatically approved by the system."*  
  > **Correct Label:** **P3**. Informational transactional receipt, no action required.

---

### 3.3 Class P3: Routine / Informational / Memos
**Core Definition:** Standard, recurring, broadcast, or informational communications that do not require an active response or decision from the recipient. These emails are read for awareness, kept for reference, or processed automatically.

#### Criteria for P3:
- Company-wide announcements, HR bulletins, and executive town hall notifications.
- Automated daily/weekly reports, data logs, schedule crawler dumps, and system status summaries.
- Meeting minutes, post-mortem notes, and informational slide distributions sent "FYI".
- Standard calendar invitations, accepted/declined auto-replies, and routine transactional receipts.

#### Positive Examples (Correctly P3):
* **Example 3.1 (Company Broadcast):**
  > *"From: enron.announcements@enron.com\nSubject: Open Enrollment for 2002 Benefits\n\nOpen enrollment for health, dental, and life insurance benefits will begin on November 1st. Please visit the HR intranet portal to review plan changes."*  
  > **Why P3:** Broadcast communication sent to thousands of employees; informational for future planning.
* **Example 3.2 (Automated Daily Crawler Report):**
  > *"From: pete.davis@enron.com\nSubject: Schedule Crawler: 10/24/2001 Successful Run\n\nThe schedule crawler ran successfully at 06:00:02. 1,452 transactions processed across all active control areas. 0 errors encountered."*  
  > **Why P3:** Automated machine log; standard operational telemetry requiring zero response.
* **Example 3.3 (Post-Meeting Minutes / FYI):**
  > *"Hi team, thanks for attending today's risk committee meeting. Attached are the minutes and action items discussed for your records."*  
  > **Why P3:** Informational summary of past events.

#### Negative Examples (NOT P3):
* **Example 3.4 (Announcement with Specific Action):**
  > *"ALL TRADERS: Due to FERC audit requirements, you MUST submit your trading logs by 5:00 PM today or trading credentials will be revoked."*  
  > **Correct Label:** **P1**. Broadcast format, but contains an immediate high-consequence mandatory action.
* **Example 3.5 (Commercial External Newsletter):**
  > *"Energy Tech Weekly: Top 10 solar startups disrupt traditional power utilities. Click here to read more."*  
  > **Correct Label:** **P4**. External third-party marketing newsletter, not internal routine operations.

---

### 3.4 Class P4: Low / Promotional / Noise
**Core Definition:** Content that is irrelevant to the recipient's core professional duties, promotional marketing, commercial solicitation, unsolicited prospecting, platform notifications, spam, or casual social/personal banter.

#### Criteria for P4:
- Commercial marketing blasts, discounts, vendor promotions, and retail advertisements.
- Cold sales pitches (e.g. SEO services, software consulting, recruiters, external conferences).
- Consumer platform alerts (Netflix recommendations, Domino's receipts, social media alerts).
- Unsolicited junk mail, spam, and non-business personal banter/chatter between acquaintances.

#### Positive Examples (Correctly P4):
* **Example 4.1 (Consumer Platform Notification):**
  > *"Top Picks for Dequan - Netflix. We added a movie you might like: 'The Space Between Us'. 98% Match. [Play Now]. Also trending now: Stranger Things."*  
  > **Why P4:** Pure consumer entertainment recommendation; complete noise in an operational inbox.
* **Example 4.2 (Cold Commercial Outreach):**
  > *"Hi, I noticed your website isn't ranking on page 1 of Google for key energy search terms. We help businesses like yours double organic traffic. Are you free for a 15-minute demo this Thursday?"*  
  > **Why P4:** Unsolicited commercial solicitation / cold sales pitch.
* **Example 4.3 (Casual Non-Work Banter):**
  > *"Hey, did you catch the Cowboys game on Sunday? What a terrible fourth quarter. Let me know if you want to grab drinks at the pub Friday."*  
  > **Why P4:** Purely personal social banter unrelated to operational business objectives.

#### Negative Examples (NOT P4):
* **Example 4.4 (External Vendor Renewal Notice):**
  > *"From: subscriptions@bloomberg.net\nSubject: Overdue Notice: Trading Floor Terminal #4\n\nYour account is 30 days past due. Terminal data feeds will terminate tomorrow unless payment is confirmed."*  
  > **Correct Label:** **P1/P2**. Commercial external vendor, but mission-critical to trading operations.

---

## 4. Annotation Decision Workflow for Reviewers

When evaluating each email in `human_review.csv`, follow this four-step decision tree:

```
                          [Incoming Email]
                                 │
                                 ▼
                 Is it marketing, commercial noise,
                 social notification, or casual chat?
                     ├── YES ───> [ P4: Low / Noise ]
                     └── NO
                          │
                          ▼
                 Does the email require an active, direct
                 response, decision, or action by recipient?
                     ├── NO ────> [ P3: Routine / Memo ]
                     └── YES
                          │
                          ▼
                 Does it involve an immediate deadline (<4h / COB),
                 emergency outage, security risk, or legal blocker?
                     ├── YES ───> [ P1: Critical / Urgent ]
                     └── NO ────> [ P2: Important / Actionable ]
```

---

## 5. Reviewer Data Entry Instructions

In `dataset/labeling/human_review.csv`:
1. **`reviewer_label`**: Enter exactly one of `P1`, `P2`, `P3`, or `P4`.
2. **`reviewer_notes`**: Optional field. Use for:
   - Borderline/ambiguous cases (e.g., *"Borderline P1/P2 due to tight deadline but low apparent business impact"*).
   - Identifying OCR/parsing corruption.
   - Noting conflicting signals (e.g., *"Subject says urgent, but body is pure FYI status report"*).
