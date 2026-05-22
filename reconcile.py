import sqlite3

import numpy as np
import pandas as pd

DB_PATH = "finrec.db"
AMOUNT_TOLERANCE = 0.01
OUTLIER_THRESHOLD = 2.5


class ReconciliationEngine:

    def run(self, db_path=DB_PATH):
        df_bank, df_gl = self._load(db_path)
        merged = self._merge_and_classify(df_bank, df_gl)
        merged = self._flag_outliers(merged)
        return {
            "detail":      merged,
            "total":       len(merged),
            "matched":     int((merged["status"] == "MATCHED").sum()),
            "mismatched":  int((merged["status"] == "AMOUNT_MISMATCH").sum()),
            "bank_only":   int((merged["status"] == "BANK_ONLY").sum()),
            "gl_only":     int((merged["status"] == "GL_ONLY").sum()),
            "match_rate":  round((merged["status"] == "MATCHED").mean() * 100, 2),
            "net_disc":    round(float(merged["discrepancy"].sum()), 2),
            "max_disc":    round(float(merged["discrepancy"].abs().max()), 2),
            "outliers":    int(merged["is_outlier"].sum()),
            "bank_total":  round(float(merged["bank_amount"].fillna(0).sum()), 2),
            "gl_total":    round(float(merged["gl_amount"].fillna(0).sum()), 2),
        }

    def _load(self, db_path):
        conn = sqlite3.connect(db_path)
        df_bank = pd.read_sql_query("SELECT * FROM bank_transactions", conn)
        df_gl   = pd.read_sql_query("SELECT * FROM gl_entries", conn)
        conn.close()
        return df_bank, df_gl

    def _merge_and_classify(self, df_bank, df_gl):
        bank = df_bank[["reference_no", "amount", "category", "txn_date"]].rename(
            columns={"amount": "bank_amount", "txn_date": "bank_date"}
        )
        gl = df_gl[["reference_no", "amount", "entry_date"]].rename(
            columns={"amount": "gl_amount", "entry_date": "gl_date"}
        )
        merged = pd.merge(bank, gl, on="reference_no", how="outer")

        conditions = [
            merged["gl_amount"].isna(),
            merged["bank_amount"].isna(),
            (merged["bank_amount"] - merged["gl_amount"]).abs() <= AMOUNT_TOLERANCE,
        ]
        choices = ["BANK_ONLY", "GL_ONLY", "MATCHED"]
        merged["status"] = np.select(conditions, choices, default="AMOUNT_MISMATCH")

        merged["discrepancy"] = np.where(
            merged["status"] == "BANK_ONLY",  merged["bank_amount"],
            np.where(
            merged["status"] == "GL_ONLY",   -merged["gl_amount"],
            merged["bank_amount"] - merged["gl_amount"]
        )).round(2)
        merged["discrepancy"] = merged["discrepancy"].fillna(0)

        return merged

    def _flag_outliers(self, df):
        non_zero = df.loc[df["discrepancy"] != 0, "discrepancy"].abs()
        if len(non_zero) < 2:
            df["is_outlier"] = False
            return df
        mu, sigma = float(non_zero.mean()), float(non_zero.std(ddof=1))
        if sigma == 0:
            df["is_outlier"] = False
            return df
        z = (df["discrepancy"].abs() - mu) / sigma
        df["is_outlier"] = z > OUTLIER_THRESHOLD
        return df


class SQLAnalytics:

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def category_summary(self):
        sql = """
        SELECT
            b.category,
            COUNT(*)                                        AS total,
            SUM(CASE WHEN r.status = 'MATCHED'       THEN 1 ELSE 0 END) AS matched,
            SUM(CASE WHEN r.status != 'MATCHED'      THEN 1 ELSE 0 END) AS exceptions,
            ROUND(100.0 * SUM(CASE WHEN r.status = 'MATCHED' THEN 1 ELSE 0 END)
                  / COUNT(*), 1)                            AS match_rate_pct,
            ROUND(SUM(ABS(r.discrepancy)), 2)               AS total_discrepancy
        FROM bank_transactions b
        LEFT JOIN recon_results r ON b.reference_no = r.reference_no
        GROUP BY b.category
        ORDER BY total_discrepancy DESC
        """
        return self._run(sql)

    def aging_analysis(self, as_of="2024-12-31"):
        sql = f"""
        SELECT
            CASE
                WHEN julianday('{as_of}') - julianday(b.txn_date) <= 30 THEN '0-30 days'
                WHEN julianday('{as_of}') - julianday(b.txn_date) <= 60 THEN '31-60 days'
                WHEN julianday('{as_of}') - julianday(b.txn_date) <= 90 THEN '61-90 days'
                ELSE '90+ days'
            END                     AS aging_bucket,
            COUNT(*)                AS items,
            ROUND(SUM(b.amount), 2) AS exposure
        FROM bank_transactions b
        LEFT JOIN recon_results r ON b.reference_no = r.reference_no
        WHERE r.status IS NULL OR r.status != 'MATCHED'
        GROUP BY aging_bucket
        ORDER BY MIN(julianday('{as_of}') - julianday(b.txn_date))
        """
        return self._run(sql)

    def top_exceptions(self, n=10):
        sql = f"""
        SELECT
            r.reference_no,
            b.category,
            b.txn_date          AS bank_date,
            r.bank_amount,
            r.gl_amount,
            r.discrepancy,
            r.status,
            CASE r.is_outlier WHEN 1 THEN 'YES' ELSE 'No' END AS outlier
        FROM recon_results r
        LEFT JOIN bank_transactions b ON r.reference_no = b.reference_no
        WHERE r.status != 'MATCHED'
        ORDER BY ABS(r.discrepancy) DESC
        LIMIT {n}
        """
        return self._run(sql)

    def _run(self, sql):
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(sql, conn)

    def save_results(self, detail_df, db_path=DB_PATH):
        rows = detail_df[["reference_no", "status",
                           "bank_amount", "gl_amount",
                           "discrepancy", "is_outlier"]].copy()
        rows["is_outlier"] = rows["is_outlier"].astype(int)
        with sqlite3.connect(db_path) as conn:
            rows.to_sql("recon_results", conn, if_exists="replace", index=False)
