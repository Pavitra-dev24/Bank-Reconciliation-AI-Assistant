import sqlite3
import random
import string
from datetime import date, timedelta

import numpy as np
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()
RANDOM_SEED = int(os.getenv("RANDOM_SEED", 42))
NUM_TRANSACTIONS = int(os.getenv("NUM_TRANSACTIONS", 300))
DB_PATH = "finrec.db"

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

CATEGORIES = ["PAYROLL", "VENDOR_PAYMENT", "REVENUE", "TAX", "UTILITIES", "TRAVEL"]

AMOUNT_RANGES = {
    "PAYROLL":        (3000, 15000),
    "VENDOR_PAYMENT": (500,   8000),
    "REVENUE":        (1000, 50000),
    "TAX":            (800,  12000),
    "UTILITIES":      (200,   2000),
    "TRAVEL":         (100,   3000),
}

ACCOUNT_MAP = {
    "PAYROLL":        ("6001", "Salaries and Wages"),
    "VENDOR_PAYMENT": ("2101", "Accounts Payable"),
    "REVENUE":        ("4001", "Sales Revenue"),
    "TAX":            ("2301", "Tax Payable"),
    "UTILITIES":      ("6101", "Utilities Expense"),
    "TRAVEL":         ("6201", "Travel and Entertainment"),
}


def random_ref():
    return "TXN-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))


def build_datasets(n):
    start, end = date(2024, 1, 1), date(2024, 12, 31)
    refs = list({random_ref() for _ in range(n * 2)})[:n]

    records = []
    for ref in refs:
        cat = random.choice(CATEGORIES)
        lo, hi = AMOUNT_RANGES[cat]
        records.append({
            "reference_no": ref,
            "txn_date":     random_date(start, end).isoformat(),
            "description":  f"{cat.replace('_', ' ').title()} - {ref}",
            "amount":       round(random.uniform(lo, hi), 2),
            "category":     cat,
        })

    df_bank = pd.DataFrame(records)
    df_gl = df_bank.copy()
    df_gl["account_code"] = df_gl["category"].map(lambda c: ACCOUNT_MAP[c][0])
    df_gl["account_name"] = df_gl["category"].map(lambda c: ACCOUNT_MAP[c][1])

    n_records = len(df_gl)
    all_idx = list(range(n_records))
    random.shuffle(all_idx)

    for i in all_idx[:int(n_records * 0.05)]:
        delta = round(random.uniform(10, 300) * random.choice([-1, 1]), 2)
        df_gl.at[i, "amount"] = round(df_gl.at[i, "amount"] + delta, 2)

    drop_idx = all_idx[int(n_records * 0.05): int(n_records * 0.09)]
    df_gl = df_gl.drop(index=drop_idx).reset_index(drop=True)

    for _ in range(int(n_records * 0.03)):
        cat = random.choice(CATEGORIES)
        lo, hi = AMOUNT_RANGES[cat]
        df_gl = pd.concat([df_gl, pd.DataFrame([{
            "reference_no": random_ref() + "-G",
            "txn_date":     random_date(start, end).isoformat(),
            "description":  f"GL-ONLY entry - {cat}",
            "amount":       round(random.uniform(lo, hi), 2),
            "category":     cat,
            "account_code": ACCOUNT_MAP[cat][0],
            "account_name": ACCOUNT_MAP[cat][1],
        }])], ignore_index=True)

    df_gl = df_gl.rename(columns={"txn_date": "entry_date"})
    return df_bank, df_gl


def save_to_db(df_bank, df_gl):
    conn = sqlite3.connect(DB_PATH)
    df_bank.to_sql("bank_transactions", conn, if_exists="replace", index=False)
    df_gl.to_sql("gl_entries", conn, if_exists="replace", index=False)
    conn.close()


if __name__ == "__main__":
    print(f"Generating {NUM_TRANSACTIONS} transactions...")
    df_bank, df_gl = build_datasets(NUM_TRANSACTIONS)
    save_to_db(df_bank, df_gl)
    print(f"Bank rows : {len(df_bank)}")
    print(f"GL rows   : {len(df_gl)}")
    print(f"Saved to  : {DB_PATH}")
