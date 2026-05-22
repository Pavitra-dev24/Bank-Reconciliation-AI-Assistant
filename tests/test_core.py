import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from reconcile import ReconciliationEngine
from llm_engine import LLMEngine
from prompts import render, SUMMARY_PROMPT


@pytest.fixture
def bank():
    return pd.DataFrame([
        {"reference_no": "T001", "amount": 1000.00, "category": "PAYROLL",         "txn_date": "2024-01-10"},
        {"reference_no": "T002", "amount":  500.00, "category": "VENDOR_PAYMENT",  "txn_date": "2024-01-11"},
        {"reference_no": "T003", "amount": 2500.00, "category": "REVENUE",         "txn_date": "2024-01-12"},
        {"reference_no": "T004", "amount":  750.00, "category": "UTILITIES",       "txn_date": "2024-01-13"},
    ])


@pytest.fixture
def gl_clean(bank):
    df = bank.copy().rename(columns={"txn_date": "entry_date"})
    df["account_code"] = "1001"
    df["account_name"] = "Operating Account"
    return df


@pytest.fixture
def gl_with_anomalies(gl_clean):
    df = gl_clean.copy()
    df.loc[df["reference_no"] == "T002", "amount"] = 400.00
    df = df[df["reference_no"] != "T004"].reset_index(drop=True)
    extra = pd.DataFrame([{
        "reference_no": "T-GLONLY", "amount": 800.00, "category": "TAX",
        "entry_date": "2024-01-15", "account_code": "2301", "account_name": "Tax Payable"
    }])
    return pd.concat([df, extra], ignore_index=True)


@pytest.fixture
def engine():
    return ReconciliationEngine()


class TestReconciliation:

    def _run(self, engine, bank, gl):
        merged = engine._merge_and_classify(bank, gl)
        return engine._flag_outliers(merged)

    def test_all_matched(self, engine, bank, gl_clean):
        merged = self._run(engine, bank, gl_clean)
        assert (merged["status"] == "MATCHED").all()

    def test_anomalies_detected(self, engine, bank, gl_with_anomalies):
        merged = self._run(engine, bank, gl_with_anomalies)
        assert (merged["status"] == "AMOUNT_MISMATCH").sum() == 1
        assert (merged["status"] == "BANK_ONLY").sum()       == 1
        assert (merged["status"] == "GL_ONLY").sum()         == 1

    def test_within_tolerance_is_matched(self, engine, bank, gl_clean):
        gl = gl_clean.copy()
        gl.loc[0, "amount"] = bank.iloc[0]["amount"] + 0.005
        merged = self._run(engine, bank, gl)
        assert (merged["status"] == "MATCHED").sum() == len(bank)

    def test_above_tolerance_is_mismatch(self, engine, bank, gl_clean):
        gl = gl_clean.copy()
        gl.loc[0, "amount"] = bank.iloc[0]["amount"] + 50.00
        merged = self._run(engine, bank, gl)
        assert (merged["status"] == "AMOUNT_MISMATCH").sum() == 1

    def test_discrepancy_value(self, engine, bank, gl_with_anomalies):
        merged = self._run(engine, bank, gl_with_anomalies)
        row = merged[merged["reference_no"] == "T002"].iloc[0]
        assert abs(row["discrepancy"]) == pytest.approx(100.00, abs=0.01)

    def test_outlier_detection(self, engine):
        bank = pd.DataFrame([
            {"reference_no": f"T{i}", "amount": 100.0,
             "category": "PAYROLL", "txn_date": "2024-01-01"}
            for i in range(20)
        ])
        gl = bank.copy().rename(columns={"txn_date": "entry_date"})
        gl["account_code"] = "1001"
        gl["account_name"] = "Test"
        gl.loc[0, "amount"] = 100.0 + 9999.0
        for i in range(1, 20):
            gl.loc[i, "amount"] = 100.0 + (i * 0.50)
        merged = engine._merge_and_classify(bank, gl)
        merged = engine._flag_outliers(merged)
        assert merged["is_outlier"].sum() >= 1


class TestPrompts:

    def test_render_substitutes_values(self):
        result = render(SUMMARY_PROMPT, stats='{"match_rate": 90}')
        assert '{"match_rate": 90}' in result

    def test_render_raises_on_missing_key(self):
        with pytest.raises((KeyError, ValueError)):
            render(SUMMARY_PROMPT)


class TestLLMEngine:

    @pytest.fixture
    def llm(self):
        return LLMEngine()

    def test_classify_returns_required_keys(self, llm):
        row = {"reference_no": "T002", "status": "AMOUNT_MISMATCH",
               "bank_amount": 500, "gl_amount": 400, "discrepancy": 100,
               "category": "VENDOR_PAYMENT", "is_outlier": False}
        result = llm.classify(row)
        for key in ("anomaly_type", "severity", "reason", "action"):
            assert key in result

    def test_classify_severity_is_valid(self, llm):
        row = {"reference_no": "T001", "status": "BANK_ONLY",
               "bank_amount": 5000, "gl_amount": None, "discrepancy": 5000,
               "category": "PAYROLL", "is_outlier": True}
        assert llm.classify(row)["severity"] in ("HIGH", "MEDIUM", "LOW")

    def test_summarise_returns_string(self, llm):
        result = llm.summarise({"match_rate": 88, "net_disc": 1200})
        assert isinstance(result, str) and len(result) > 0

    def test_nl_to_sql_returns_string(self, llm):
        result = llm.nl_to_sql("Show me all unmatched transactions over $500")
        assert isinstance(result, str) and len(result) > 0
