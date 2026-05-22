# FinRecAI

An automated bank-to-GL reconciliation pipeline that combines Python data processing, SQL analytics, and Generative AI to detect and explain financial discrepancies.

Built as a portfolio project demonstrating applied skills in Python (pandas, numpy), SQL, LLM integration, and workflow automation in a finance context.

---

## What It Does

The workflow runs in five steps:

1. Loads bank transactions and General Ledger entries from SQLite into pandas DataFrames
2. Matches records by reference number using a full outer join, classifies each as MATCHED, AMOUNT_MISMATCH, BANK_ONLY, or GL_ONLY, and flags statistical outliers using numpy z-scores
3. Runs SQL analytics queries (joins, aggregations, grouping, date bucketing) against the results
4. Calls an LLM to summarise the reconciliation outcome in plain English
5. Classifies each exception using LLM prompt engineering, and demonstrates NL-to-SQL translation

---

## Project Structure

```
finrecai/
├── generate_data.py    creates a SQLite DB with 300 bank and GL records (with injected anomalies)
├── reconcile.py        reconciliation engine (pandas + numpy) and SQL analytics (3 queries)
├── prompts.py          three versioned prompt templates for summarisation, classification, NL-to-SQL
├── llm_engine.py       LLM integration supporting Groq (free API) and mock mode
├── main.py             five-step workflow orchestrator
├── tests/
│   └── test_core.py    12 unit tests covering reconciliation logic, prompts, and LLM engine
├── requirements.txt
└── .env.example
```

---

## Skills Demonstrated

**Python and data processing**
- pandas: outer merge/join, groupby, vectorised classification with `np.select`
- numpy: mean, standard deviation, z-score outlier detection

**SQL**
- Three analytical queries written in raw SQLite
- Patterns covered: `LEFT JOIN`, `CASE WHEN` date bucketing, `GROUP BY`, `SUM`, `COUNT`, `ROUND`, `ORDER BY`, `LIMIT`, multi-table join with filtering

**Generative AI and prompt engineering**
- Summarisation: reconciliation stats converted to a plain-English executive summary
- Classification: each exception classified into a type (AMOUNT_ERROR, MISSING_ENTRY, etc.) with severity and recommended action
- NL-to-SQL: a natural language question translated into a valid SQLite query
- Prompts are versioned, use role definition, explicit output format, and low temperature for consistent output

**Workflow automation**
- Single entry point (`main.py`) runs the full pipeline end to end
- Modular design so each step can be tested or replaced independently

---

## Anomaly Types the Engine Detects

| Status | Meaning |
|---|---|
| AMOUNT_MISMATCH | Same reference, different amounts in bank and GL |
| BANK_ONLY | Transaction exists in bank feed but has no GL posting |
| GL_ONLY | GL entry exists with no matching bank transaction |

Outliers are flagged separately using z-score analysis on the discrepancy values.

---

## Setup

**Requirements:** Python 3.10 or later

```bash
# Clone and install
git clone https://github.com/your-username/finrecai.git
cd finrecai
pip install -r requirements.txt

# Copy config
cp .env.example .env

# Generate synthetic data
python generate_data.py

# Run the workflow
python main.py

# Run tests
pytest tests/ -v
```

**Default mode** uses mock LLM responses and requires no API key.

**To use a real free LLM (Groq):**

1. Get a free API key at [console.groq.com](https://console.groq.com) (no credit card required)
2. In `.env`, set `LLM_PROVIDER=groq` and `GROQ_API_KEY=your_key`
3. Run `python main.py`

---

## Sample Output

```
Step 1: Running reconciliation engine...
Metric               Value
-------------------  ---------------
Total records        309
Matched              273 (88.35%)
Amount mismatches    15
Bank-only items      12
GL-only items        9
Net discrepancy      $-30,524.91
Outliers flagged     2

Step 2: SQL analytics...
Category summary (top 4):
category          total  matched  exceptions  match_rate_pct  total_discrepancy
VENDOR_PAYMENT       46       43           3            93.5           11025.20
TAX                  43       40           3            93.0           10016.60
PAYROLL              44       40           4            90.9            9627.14
TRAVEL               66       58           8            87.9            5783.66

Step 3: LLM summarisation...
The reconciliation completed with an 87.3% match rate.
VENDOR_PAYMENT has the highest exception exposure.
Recommended action: review the 15 unmatched vendor payments
with the AP team before period close.

Step 4: Classifying top 5 exceptions with LLM...
TXN-IEC4D1 | AMOUNT_ERROR | HIGH
  Action: Ask the AP team to verify the original invoice and repost if needed.
...

Step 5: NL-to-SQL demo...
Question : Which categories have the most unmatched transactions?
SQL      : SELECT category, COUNT(*) AS exceptions ...
```

---

## Tech Stack

| Tool | Version | Purpose |
|---|---|---|
| Python | 3.10+ | Core language |
| pandas | 2.2.2 | Data loading, merging, groupby |
| numpy | 1.26.4 | Discrepancy stats, z-score outlier detection |
| SQLite | built-in | Database for bank, GL, and recon data |
| Groq API | free tier | LLM inference (llama-3.1-8b-instant) |
| pytest | 8.2.2 | Unit testing |

All tools and APIs used in this project are free.
