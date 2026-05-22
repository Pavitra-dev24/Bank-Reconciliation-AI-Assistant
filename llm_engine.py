import json
import os

from dotenv import load_dotenv
from prompts import render, SUMMARY_PROMPT, CLASSIFY_PROMPT, NL_TO_SQL_PROMPT

load_dotenv()
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


class LLMEngine:

    def __init__(self):
        self.provider = LLM_PROVIDER

    def summarise(self, stats: dict) -> str:
        prompt = render(SUMMARY_PROMPT, stats=json.dumps(stats, indent=2))
        return self._call(prompt)

    def classify(self, row: dict) -> dict:
        prompt = render(CLASSIFY_PROMPT, **{
            "reference_no": row.get("reference_no", "N/A"),
            "status":       row.get("status", "N/A"),
            "bank_amount":  row.get("bank_amount", "N/A"),
            "gl_amount":    row.get("gl_amount", "N/A"),
            "discrepancy":  row.get("discrepancy", "N/A"),
            "category":     row.get("category", "N/A"),
            "is_outlier":   row.get("is_outlier", False),
        })
        raw = self._call(prompt)
        try:
            clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
            return json.loads(clean)
        except json.JSONDecodeError:
            return {"anomaly_type": "OTHER", "severity": "MEDIUM",
                    "reason": raw[:200], "action": "Manual review required."}

    def nl_to_sql(self, question: str) -> str:
        prompt = render(NL_TO_SQL_PROMPT, question=question)
        return self._call(prompt)

    def _call(self, prompt: str) -> str:
        if self.provider == "groq":
            return self._groq(prompt)
        return self._mock(prompt)

    def _groq(self, prompt: str) -> str:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()

    def _mock(self, prompt: str) -> str:
        p = prompt.lower()
        if "anomaly_type" in p:
            return json.dumps({
                "anomaly_type": "AMOUNT_ERROR",
                "severity":     "MEDIUM",
                "reason":       "GL amount differs from bank by a small delta, likely a manual entry error.",
                "action":       "Ask the AP team to verify the original invoice and repost if needed."
            })
        if "sql" in p or "select" in p:
            return (
                "SELECT category, COUNT(*) AS exceptions, "
                "ROUND(SUM(ABS(discrepancy)), 2) AS total_discrepancy "
                "FROM recon_results r "
                "LEFT JOIN bank_transactions b ON r.reference_no = b.reference_no "
                "WHERE r.status != 'MATCHED' "
                "GROUP BY category ORDER BY total_discrepancy DESC LIMIT 50;"
            )
        return (
            "The reconciliation completed with an 87.3% match rate. "
            "VENDOR_PAYMENT has the highest exception exposure. "
            "Recommended action: review the 15 unmatched vendor payments "
            "with the AP team before period close."
        )
