import os
from pathlib import Path

from tabulate import tabulate

from reconcile import ReconciliationEngine, SQLAnalytics
from llm_engine import LLMEngine, LLM_PROVIDER

DB_PATH = "finrec.db"


def main():
    print("\n=== FinRecAI - Reconciliation Workflow ===")
    print(f"LLM provider: {LLM_PROVIDER}\n")

    if not Path(DB_PATH).exists():
        print("Database not found. Run generate_data.py first.")
        return

    print("Step 1: Running reconciliation engine...")
    engine = ReconciliationEngine()
    result = engine.run(DB_PATH)

    print(tabulate([
        ["Total records",     result["total"]],
        ["Matched",           f"{result['matched']} ({result['match_rate']}%)"],
        ["Amount mismatches", result["mismatched"]],
        ["Bank-only items",   result["bank_only"]],
        ["GL-only items",     result["gl_only"]],
        ["Net discrepancy",   f"${result['net_disc']:,.2f}"],
        ["Outliers flagged",  result["outliers"]],
    ], headers=["Metric", "Value"], tablefmt="simple"))

    print("\nStep 2: SQL analytics...")
    analytics = SQLAnalytics(DB_PATH)
    analytics.save_results(result["detail"], DB_PATH)

    cat_df = analytics.category_summary()
    print("\n  Category summary (top 4):")
    print(tabulate(cat_df.head(4), headers="keys",
                   tablefmt="simple", showindex=False))

    top_df = analytics.top_exceptions(n=5)
    print("\n  Top 5 exceptions by discrepancy:")
    print(tabulate(top_df, headers="keys", tablefmt="simple", showindex=False))

    print("\nStep 3: LLM summarisation...")
    llm = LLMEngine()
    stats_for_llm = {k: v for k, v in result.items() if k != "detail"}
    summary = llm.summarise(stats_for_llm)
    print(f"\n  {summary}\n")

    print("Step 4: Classifying top 5 exceptions with LLM...")
    exceptions = (
        result["detail"][result["detail"]["status"] != "MATCHED"]
        .sort_values("discrepancy", key=lambda s: s.abs(), ascending=False)
        .head(5)
        .to_dict(orient="records")
    )
    for row in exceptions:
        c = llm.classify(row)
        print(f"  {row.get('reference_no','')} | {c.get('anomaly_type','')} | {c.get('severity','')}")
        print(f"    Action: {c.get('action','')}")

    print("\nStep 5: NL-to-SQL demo...")
    question = "Which categories have the most unmatched transactions?"
    sql = llm.nl_to_sql(question)
    print(f"  Question : {question}")
    print(f"  SQL      : {sql}\n")

    print("Done. All steps completed.")


if __name__ == "__main__":
    main()
