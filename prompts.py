PROMPT_VERSION = "1.0"

SUMMARY_PROMPT = """\
You are a finance analyst summarising a bank-to-GL reconciliation run.
Write a 3-4 sentence plain English summary for a business audience.
Mention the match rate, biggest risk area, and one recommended action.
Do not invent numbers. Use only the data provided below.

<data>
{stats}
</data>

Summary:
"""

CLASSIFY_PROMPT = """\
You are an accounting assistant classifying a reconciliation exception.
Return ONLY a JSON object with these keys (no extra text, no code fences):
{{
  "anomaly_type": "<DUPLICATE | TIMING | AMOUNT_ERROR | MISSING_ENTRY | OTHER>",
  "severity": "<HIGH | MEDIUM | LOW>",
  "reason": "<one sentence>",
  "action": "<one sentence recommended next step>"
}}

Severity guide: HIGH = discrepancy over $1000 or fully missing entry,
MEDIUM = $100-$1000 or date shift, LOW = under $100.

<transaction>
Reference  : {reference_no}
Status     : {status}
Bank amount: {bank_amount}
GL amount  : {gl_amount}
Discrepancy: {discrepancy}
Category   : {category}
Outlier    : {is_outlier}
</transaction>
"""

NL_TO_SQL_PROMPT = """\
You are a SQL assistant. Convert the question below into a valid SQLite query.
Return ONLY the SQL, nothing else.

Tables available:
  bank_transactions(reference_no, txn_date, description, amount, category)
  gl_entries(reference_no, entry_date, description, amount, account_code, account_name)
  recon_results(reference_no, status, bank_amount, gl_amount, discrepancy, is_outlier)

Always add LIMIT 50 unless the query is an aggregation.

Question: {question}

SQL:
"""


def render(template, **kwargs):
    return template.format(**kwargs)
