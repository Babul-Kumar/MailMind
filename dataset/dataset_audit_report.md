# Comprehensive Dataset Audit Report: Enron Email Corpus & Email Importance Dataset

**Audit Date:** September 24, 2026  
**Audited Datasets:**
1. `dataset/emails.csv` — Large Enron raw email corpus
2. `dataset/email_importance.csv` — Labeled email importance dataset (derived from `Dc-4nderson/email-importance`)

---

## 1. Executive Summary

This report delivers a comprehensive audit of both the large-scale Enron raw email corpus (`emails.csv`) and the labeled email-importance dataset (`email_importance.csv`). Both source files have been verified, processed in read-only streaming mode, and maintained in an untouched state in accordance with project constraints.

### Key Audit Findings at a Glance

| Metric / Dimension | Enron Corpus (`dataset/emails.csv`) | Email Importance (`dataset/email_importance.csv`) |
| :--- | :--- | :--- |
| **Total Rows** | **517,401** emails | **250** emails |
| **File Size on Disk** | 1,426,122,219 bytes (~1.33 GB) | 211,801 bytes (~207 KB) |
| **Schema** | `file` (string), `message` (raw RFC-822 MIME) | `text` (string), `label_id` (integer) |
| **Missing Values in CSV** | 0 missing fields (`file` or `message`) | 0 missing fields (`text` or `label_id`) |
| **Parsing Failures** | **0** (100% parsed successfully via RFC-822) | **0** (CSV conforms to RFC-4180) |
| **Duplicate Entries** | 0 raw message string duplicates; 262,981 duplicate content tuples | 25 exact row duplicates (225 unique entries) |
| **Class / Label Structure** | Unlabeled raw corporate email corpus | Binary: `0` (45.2%, n=113) vs `1` (54.8%, n=137) |
| **Content Domain** | Corporate energy trading & operations (1999–2002) | Hybrid: Modern synthetic/consumer + Enron enterprise |
| **Critical Provenance Discovery**| Source corpus from which 185 emails were extracted | **185 of 250 rows (74.0%) are sampled directly from Enron** |

---

## 2. Detailed Audit: Enron Email Corpus (`dataset/emails.csv`)

### 2.1 File & Structural Characteristics
- **Total Record Count:** **517,401** emails across 150 individual custodian mailboxes.
- **Underlying Format:** Two-column tabular CSV (`file`, `message`).
  - `file`: Path identifying the custodian mailbox, folder structure, and internal message number (e.g., `allen-p/_sent_mail/1.`).
  - `message`: Complete RFC-822 / MIME formatted email message containing standard email headers, boundary markers, and email body payloads.

### 2.2 Header Parsing & Extraction Capabilities
All 517,401 records were parsed using standard Python MIME/RFC-822 parsers. Headers extracted from the raw messages consistently exhibit the following schema:
- Primary headers: `Message-ID`, `Date`, `From`, `To`, `Subject`, `Mime-Version`, `Content-Type`, `Content-Transfer-Encoding`
- Custom Enron X-headers: `X-From`, `X-To`, `X-cc`, `X-bcc`, `X-Folder`, `X-Origin`, `X-FileName`

```
+----------------------------------------------------------------------------------------------------+
|                                    Raw Enron Message Structure                                      |
|                                                                                                    |
|  file:    allen-p/_sent_mail/1.                                                                    |
|  Headers: Message-ID: <18782981.1075855378110.JavaMail.evans@thyme>                                |
|           Date: Mon, 14 May 2001 16:39:00 -0700 (PDT)                                              |
|           From: phillip.allen@enron.com                                                            |
|           To: tim.belden@enron.com                                                                 |
|           Subject:                                                                                 |
|           X-Folder: \Phillip_Allen_Jan2002_1\Allen, Phillip K.'Sent Mail                          |
|  Body:    Here is our forecast ...                                                                 |
+----------------------------------------------------------------------------------------------------+
```

### 2.3 Parsing Failures & Missing Values Analysis
- **Parsing Failures:** **0** (0.0%). Every single message string conforms to RFC-822 formatting and yielded valid header mappings and body extractions.
- **Missing Value Breakdown:**

| Field | Missing (Null) | Empty String / Whitespace | Total Unusable | % of Total | Notes & Observations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `file` | 0 | 0 | 0 | 0.00% | Full path present for all rows |
| `message` | 0 | 0 | 0 | 0.00% | No empty payloads in the CSV |
| `Date` (parsed) | 0 | 0 | 0 | 0.00% | All messages contain date stamps |
| `From` (parsed) | 0 | 0 | 0 | 0.00% | 100% of messages have sender addresses |
| `To` (parsed) | 21,847 | 0 | 21,847 | **4.22%** | Omitted in system announcements, BCC-only, or draft folders |
| `Subject` (parsed)| 0 | 19,187 | 19,187 | **3.71%** | Subject header is present, but value is blank/whitespace |
| `Body` (parsed) | 0 | 0 | 0 | 0.00% | 100% of emails contain non-empty body content |

### 2.4 Duplicate Analysis
- **Exact File Paths:** 517,401 unique paths (0 duplicate paths).
- **Exact Raw Message Strings:** 517,401 unique strings (0 duplicates). Every raw string has a unique `Message-ID` or unique `X-FileName` assigned by the Lotus Notes export agent.
- **Content-Level Duplication (`From`, `Subject`, `Date`, `Body`):**
  - **Duplicate Content Tuples:** **262,981** (50.83% of the dataset).
  - **Unique Content Tuples:** **254,420** unique emails.
  - *Root Cause:* In corporate email systems, emails sent to multiple recipients appear in the sender's `sent` folder as well as the `inbox` of every internal recipient. Furthermore, custodians frequently filed the same message in `all_documents`, `discussion_threads`, and specialized subfolders.

### 2.5 Senders & Network Analysis
- **Unique Senders:** **20,328** distinct email addresses.
- **Internal vs. External Distribution:**
  - Enron Internal (`@enron.com`): **427,785** emails (**82.68%**)
  - External Organizations / Senders: **89,616** emails (**17.32%**)

#### Top 15 Senders by Email Volume
| Rank | Sender Address | Email Count | % of Corpus | Role / Notes |
| :---: | :--- | :---: | :---: | :--- |
| 1 | `kay.mann@enron.com` | 16,735 | 3.23% | Legal Counsel (high contract transaction volume) |
| 2 | `vince.kaminski@enron.com` | 14,368 | 2.78% | Managing Director, Research / Quantitative Modeling |
| 3 | `jeff.dasovich@enron.com` | 11,411 | 2.21% | Government Relations / Regulatory Affairs |
| 4 | `pete.davis@enron.com` | 9,149 | 1.77% | Automated Schedule Crawler / System notifications |
| 5 | `chris.germany@enron.com` | 8,801 | 1.70% | Gas Trading Desk |
| 6 | `sara.shackleton@enron.com` | 8,777 | 1.70% | VP & Assistant General Counsel |
| 7 | `enron.announcements@enron.com`| 8,587 | 1.66% | Company-wide automated broadcast announcements |
| 8 | `tana.jones@enron.com` | 8,490 | 1.64% | Legal / Financial Contracts |
| 9 | `steven.kean@enron.com` | 6,759 | 1.31% | Executive VP & Chief of Staff |
| 10 | `kate.symes@enron.com` | 5,438 | 1.05% | West Power Trading Desk |
| 11 | `matthew.lenhart@enron.com` | 5,265 | 1.02% | Trading Desk |
| 12 | `eric.bass@enron.com` | 5,158 | 1.00% | Gas Trading Desk |
| 13 | `no.address@enron.com` | 5,112 | 0.99% | System generated / automated gateway placeholder |
| 14 | `debra.perlingiere@enron.com` | 4,387 | 0.85% | Legal Specialist |
| 15 | `sally.beck@enron.com` | 4,343 | 0.84% | Chief Operating Officer, Energy Services |

### 2.6 Email Length Statistics
The body text length exhibits a heavily right-skewed distribution, typical of real-world communications containing everything from brief one-line confirmations to massive tabular data dumps and legal contracts.

| Metric | Body Character Length | Body Word Length | Subject Character Length | Subject Word Length |
| :--- | :---: | :---: | :---: | :---: |
| **Minimum** | 1 | 1 | 0 | 0 |
| **25th Percentile (Q1)** | 287 | 45 | 15 | 2 |
| **50th Percentile (Median)** | **768** | **114** | **25** | **4** |
| **Mean** | 1,842.8 | 262.0 | 28.4 | 4.5 |
| **75th Percentile (Q3)** | 1,753 | 256 | 38 | 6 |
| **90th Percentile** | 3,652 | 532 | 52 | 8 |
| **95th Percentile** | 5,900 | 852 | 62 | 10 |
| **99th Percentile** | 16,220 | 2,188 | 84 | 14 |
| **Maximum** | 2,011,422 | 64,024 | 258 | 49 |
| **Standard Deviation** | 8,179.1 | 822.5 | 17.6 | 2.9 |

### 2.7 Folder & Custodian Distribution
The Enron dataset spans **150 unique custodian mailboxes**.
- **Top 5 Custodians by Total Stored Volume:**
  1. `kaminski-v` (Vince Kaminski): 28,465 emails
  2. `dasovich-j` (Jeff Dasovich): 28,234 emails
  3. `kean-s` (Steven Kean): 25,351 emails
  4. `mann-k` (Kay Mann): 23,381 emails
  5. `jones-t` (Tana Jones): 19,950 emails

- **Top 10 Folder Types (extracted from path):**
  1. `all_documents`: 128,103 emails (24.76%) — Default Lotus Notes aggregate repository
  2. `discussion_threads`: 58,609 emails (11.33%) — Clustered conversation threads
  3. `sent`: 57,653 emails (11.14%) — Outgoing communications
  4. `deleted_items`: 51,356 emails (9.93%) — Trash / discarded messages
  5. `inbox`: 44,859 emails (8.67%) — Direct incoming mail
  6. `sent_items`: 37,921 emails (7.33%) — Outgoing communications (secondary naming)
  7. `notes_inbox`: 36,665 emails (7.09%) — Lotus Notes incoming mail
  8. `_sent_mail`: 30,109 emails (5.82%) — Early client sent mail folder
  9. `calendar`: 6,133 emails (1.19%) — Meeting invites and calendar notices
  10. `archiving`: 4,477 emails (0.87%) — Saved long-term archives

### 2.8 Temporal Distribution (Date Analysis)
Over 97% of emails originate from the critical corporate activity period between 1999 and 2002:
- **1999:** 11,144 emails (2.15%)
- **2000:** 196,101 emails (37.90%)
- **2001:** 272,819 emails (52.73%) — Peak trading & regulatory scrutiny
- **2002:** 35,847 emails (6.93%) — Post-bankruptcy filing / collapse
- **Anomalies / Corrupt Timestamps:** 522 emails with year 1979 (Unix epoch offset artifact), 437 in 1997, 177 in 1998, and 7 minor future years (e.g. 2024, 2044) due to misconfigured client clocks.

---

## 3. Detailed Audit: Email Importance Dataset (`dataset/email_importance.csv`)

### 3.1 Overview & Schema
- **Total Record Count:** **250** rows.
- **Source:** Hugging Face dataset `Dc-4nderson/email-importance`.
- **Columns:**
  - `text` (string): Text content of the email.
  - `label_id` (integer): Binary target indicator (`0` or `1`).
- **Missing Values:** **0** missing values across both columns.

### 3.2 Label Distribution
The dataset is well-balanced across binary classes:
- **Label `1` (Important / Actionable):** **137** rows (**54.80%**)
- **Label `0` (Not Important / Noise / Promotional):** **113** rows (**45.20%**)

```
Label Distribution in email_importance.csv:
[█████████████████████████                     ] Label 0: 45.2% (n=113)
[██████████████████████████████                ] Label 1: 54.8% (n=137)
```

### 3.3 Duplicate Analysis
- **Exact Duplicate Rows (`text` and `label_id` identical):** **25** duplicates (**10.0%**).
- **Unique Records:** **225** distinct emails.
- **Conflicting Labels:** **0**. No identical text string is mapped to conflicting labels.

### 3.4 Text Length Statistics

#### Length Comparison by Label Class
| Group | Metric | Mean | Std Dev | Min | 25% | Median | 75% | Max |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **All Records (N=250)** | Char Length | 840.6 | 1,459.7 | 126 | 192.0 | 283.0 | 792.3 | 9,665 |
| | Word Length | 120.5 | 209.2 | 15 | 30.0 | 44.5 | 110.0 | 1,443 |
| **Label 0 (Not Important)** | Char Length | 783.5 | 1,595.6 | 143 | 191.0 | 256.0 | 363.0 | 9,665 |
| | Word Length | 112.9 | 233.1 | 18 | 30.0 | 37.0 | 56.0 | 1,443 |
| **Label 1 (Important)** | Char Length | 887.6 | 1,340.2 | 126 | 193.0 | 310.0 | 1,029.0| 7,370 |
| | Word Length | 126.7 | 187.3 | 15 | 30.0 | 50.0 | 149.0 | 1,061 |

*Observation:* Important emails (Label 1) have slightly higher median character (+21%) and word (+35%) counts than Not Important emails, reflecting the presence of substantive business discussions, salary schedules, and project instructions.

### 3.5 Exact Meaning of Label `0` and `1`

Based directly on both empirical analysis of every row and the official Hugging Face dataset card specification (`Dc-4nderson/email-importance`), the labels represent:

#### **Label `0`: Not Important (Noise / Promotional / Low-Priority / Casual)**
- **Definition:** Low-priority, automated, promotional, or casual content that does not require immediate attention or business decision-making.
- **Composition in Dataset:**
  - **Modern Synthetic Inbound Noise (65 rows, 57.5%):**
    - Marketing blasts and retail sales (e.g. *"Huge Winter Blowout Sale! Up to 70% Off"*).
    - Streaming/Media recommendations (e.g. Netflix *"Top Picks for Dequan - The Space Between Us"*).
    - Newsletters and digest subscriptions (e.g. *"NYT Cooking: Your Tuesday Morning Briefing"*).
    - Cold commercial prospecting (e.g. SEO agency outreach *"Question about your website ranking"*).
    - Social media platform alerts (e.g. LinkedIn *"You missed a message from a recruiter"*).
    - Minor automated receipts (e.g. Apple Services *$0.99 iCloud storage subscription*).
  - **Trivial / Casual Enron Correspondence (48 rows, 42.5%):**
    - Casual personal chitchat (e.g. discussing CPAs: *"I think Fletch has a good CPA. I am still doing my own"*).
    - Forwarded internal routine surveys without individual actions required.
    - One-line link shares without actionable requests.

#### **Label `1`: Important (Actionable / High-Priority / Work Correspondence)**
- **Definition:** High-priority, personal, or transactional content requiring active attention, immediate operational response, scheduling, or critical business decisions.
- **Composition in Dataset:**
  - **100% Enron Operational & Management Communications (137 rows, 100%):**
    - Salary and compensation reviews (e.g. *"Can you send me a schedule of the salary and level of everyone in the scheduling group... Patti S for example"*).
    - Meeting scheduling and critical confirmations (e.g. *"Let's shoot for Tuesday at 11:45"*).
    - Trading desk instructions and distribution list updates.
    - System deployment tests (e.g. *"test successful. way to go!!!"*).
    - Regulatory compliance notices and energy contract terms.

---

## 4. Representative Examples from Each Label

### 4.1 Representative Examples: Label `0` (Not Important)

#### Example 0.1: Consumer Entertainment Recommendation (Modern Synthetic)
```text
Top Picks for Dequan

Netflix

We added a movie you might like: 'The Space Between Us'.
98% Match

[Play Now]

Also trending now:
- Stranger Things
- The Crown

Manage emails settings.
```

#### Example 0.2: Content Newsletter (Modern Synthetic)
```text
Your Tuesday Morning Briefing

NYT Cooking

What to cook this week:
1. Sheet-Pan Chicken with Potatoes
2. Creamy Mushroom Pasta
3. The Best Chocolate Chip Cookies

Read the full recipes (https://cooking.nytimes.com)

Subscribe to access 10,000+ recipes.
```

#### Example 0.3: Cold Sales Outreach (Modern Synthetic)
```text
Question about your website ranking

Hi,
I was checking your site and noticed you aren't ranking for some key terms in your industry.
We help businesses like yours get to page 1 of Google.
Are you available for a quick chat this week?

Best,
Jim
SEO Ninja
```

#### Example 0.4: Casual Personal Banter (Enron Corporate Origin)
```text
Date: Tue, 3 Oct 2000 03:17:00 -0700 (PDT)
From: phillip.allen@enron.com
To: stouchstone@natsource.com
Subject: Re: Not business related..
Body: 
I think Fletch has a good CPA. I am still doing my own.
```

---

### 4.2 Representative Examples: Label `1` (Important)

#### Example 1.1: Management & Compensation Review Request
```text
Date: Mon, 23 Oct 2000 06:13:00 -0700 (PDT)
From: phillip.allen@enron.com
To: randall.gay@enron.com
Subject: 
Body: 
Randy,
 Can you send me a schedule of the salary and level of everyone in the 
scheduling group. Plus your thoughts on any changes that need to be made. 
(Patti S for example)
Phill
```

#### Example 1.2: Meeting Scheduling & Time-Sensitive Coordination
```text
Date: Thu, 31 Aug 2000 05:07:00 -0700 (PDT)
From: phillip.allen@enron.com
To: greg.piper@enron.com
Subject: Re: Hello
Body: 
Let's shoot for Tuesday at 11:45.
```

#### Example 1.3: Direct Operational Instruction & Distribution Update
```text
Date: Tue, 22 Aug 2000 07:44:00 -0700 (PDT)
From: phillip.allen@enron.com
To: david.l.johnson@enron.com, john.shafer@enron.com
Subject: 
Body: 
Please cc the following distribution list with updates:
Phillip Allen (pallen@enron.com)
Mike Grigsby (mike.grigsby@enron.com)
Keith Holst (kholst@enron.com)
```

---

## 5. Critical Comparative Insights & Provenance Connection

A crucial finding of this audit is the **unannounced direct structural lineage** connecting the two datasets:

1. **Formatting Discrepancy:**
   - The 185 Enron-derived records in `email_importance.csv` have explicit header tags embedded inside the text column (`Date: ...
From: ...
To: ...
Subject: ...
Body: ...`).
   - The 65 synthetic noise emails in `email_importance.csv` do **not** have header tags; they start with raw subject lines or marketing headers (e.g. `Top Picks for Dequan

Netflix...`).
2. **Sampling Bias in Seed Dataset:**
   - 100% of Label 1 in `email_importance.csv` comes from a single Enron custodian (`phillip.allen@enron.com`). A classifier trained naively on `email_importance.csv` could overfit to Phillip Allen's style or Enron domain tokens rather than learning generalized email importance.
3. **Data Leakage Risk:**
   - Because 185 emails in `email_importance.csv` are verbatim copies of rows in `emails.csv`, training on `emails.csv` and testing on `email_importance.csv` without strict hash-based deduplication will cause catastrophic test-set leakage.

---

## 6. Generated Samples Documentation

Two stratified sample files have been generated and saved to `dataset/samples/`:

1. **`dataset/samples/enron_parsed_sample.csv` (1,000 records)**:
   - Systematically sampled across all 517,401 Enron emails to ensure coverage across all 150 custodians and top folders.
   - Fully parsed schema: `file`, `user`, `folder`, `date`, `sender`, `recipient`, `subject`, `body`, `body_char_length`, `body_word_length`.
2. **`dataset/samples/importance_sample.csv` (50 records)**:
   - Deduplicated, balanced sample (25 records from Label 0, 25 records from Label 1).
   - Rich schema: `text`, `label_id`, `label_name`, `char_length`, `word_length`.

---

## 7. Architecture Recommendation: 4-Class Email Priority Classification

### 7.1 Defining the 4 Priority Classes
To transform this binary/unlabeled setup into a production-grade 4-class email priority engine, we define an intuitive, mutually exclusive hierarchy:

| Priority Level | Class Name | Target Description | Representative Examples |
| :---: | :--- | :--- | :--- |
| **P1 (Class 3)** | **Critical / Urgent** | Urgent, time-sensitive emails requiring action within hours; escalations, critical legal/financial notices, security alerts (2FA), deal blockers. | Trading emergency notices, regulatory subpoenas, system outages, immediate contract execution requests. |
| **P2 (Class 2)** | **Important / Actionable** | Core workplace requests, direct colleague communication, project deliverables, meeting scheduling, task delegations. | Salary schedules, review requests, meeting coordination (`Let's shoot for Tuesday`), project feedback. |
| **P3 (Class 1)** | **Routine / Informational** | Operational status reports, company-wide announcements, meeting minutes, newsletters, calendar receipts, system digests. | `enron.announcements@enron.com` broadcasts, weekly schedule crawler dumps, IT maintenance notices. |
| **P4 (Class 0)** | **Low / Promotional / Noise**| External cold sales outreach, commercial advertisements, streaming entertainment recommendations, spam, social platform pings. | Netflix recommendations, NYT Cooking newsletters, SEO sales pitches, LinkedIn notifications, retail discounts. |

### 7.2 How to Bridge Both Datasets Together

- **`email_importance.csv` as a Gold Standard Evaluation & Benchmark Set:**
  - Because it contains clean human/curated labels distinguishing modern consumer noise from work tasks, reserve its unique records (deduplicated to 225 rows) for few-shot prompt validation and gold benchmark evaluation.
  - Its binary labels map cleanly: Label 0 maps to P4 (or P3 for internal surveys), and Label 1 maps to P2 (or P1 for urgent requests).
- **`emails.csv` as the High-Capacity Pre-Training & Silver-Supervision Reservoir:**
  - 517,401 emails provide rich corporate domain knowledge and lexical variety.
  - Using programmatic weak supervision (Snorkel or rule-based labeling functions) combined with metadata filters (folders, broadcast sender addresses, and lexical urgency markers), curate a high-quality silver training set of 30,000–50,000 emails across all 4 classes.

### 7.3 Step-by-Step Implementation Roadmap

1. **Strict Content Deduplication & Leakage Prevention:**
   - Compute hash signatures for the 185 Enron emails in `email_importance.csv`.
   - Exclude these 185 emails and any exact duplicate content tuples from the training split of `emails.csv`.
2. **Text Representation Normalization:**
   - Standardize input formatting across both datasets:
     `[SUBJECT]: <Subject line>
[FROM]: <Sender>
[BODY]: <Body text>`
3. **Weak Supervision Programmatic Labeling Functions (LFs):**
   - **P1 (Critical):** Lexical urgency keywords (`urgent`, `immediate`, `deadline`, `asap`, `emergency`) + direct peer sender + short concise body.
   - **P2 (Important):** Direct internal correspondence (`@enron.com`), recipient count <= 3, presence of question marks, action request verbs (`schedule`, `review`, `approve`).
   - **P3 (Routine):** Broadcast senders (`enron.announcements@enron.com`, `pete.davis@enron.com`), folders (`all_documents`, `calendar`, `archiving`).
   - **P4 (Low/Noise):** External domains, high hyperlink density, promotional tokens (`sale`, `discount`, `click here`, `unsubscribe`), `deleted_items` with external senders.
4. **Modeling Strategy:**
   - Fine-tune a lightweight transformer (`microsoft/deberta-v3-small` or `distilroberta-base`).
   - Train on the silver-supervised corpus, validate on a stratified 4-class evaluation set, and benchmark against the gold test set.
