"""
eval/run_evaluation.py

Runs every case in eval/cases.json through retrieval, eligibility,
recommendation, and explanation evaluation, then writes an aggregated
JSON report.

Usage:
    python -m eval.run_evaluation
"""
from __future__ import annotations
import time  
import json
from pathlib import Path
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from backend.database import db_connection
from backend.models import UserProfile

from eval.retrieval_eval import evaluate_retrieval_case
from eval.eligibility_eval import evaluate_eligibility_for_case
from eval.recommendation_eval import evaluate_recommendation_case
from eval.explanation_eval import evaluate_explanation_case
from eval.metrics import aggregate

CASES_PATH = Path(__file__).parent / "cases.json"
REPORT_PATH = Path(__file__).parent / "eval_report.json"


def _build_findings_for_explanation(conn, profile, recommended_ids: list[str]) -> list[dict]:
    from backend.rules import evaluate as evaluate_rules

    findings = []
    with conn.cursor() as cur:
        for scheme_id in recommended_ids:
            cur.execute("SELECT data FROM schemes WHERE id = %s", (scheme_id,))
            row = cur.fetchone()
            if not row:
                continue
            scheme = row["data"]
            status, reasons, unknowns = evaluate_rules(profile, scheme.get("rules", {}))
            findings.append({
                "scheme_id": scheme_id,
                "name": scheme["name"],
                "benefit": scheme["benefit"],
                "status": status,
                "reasons": reasons,
                "unknown_fields": unknowns,
            })
    return findings


def run():
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    case_results = []

    with db_connection() as conn:
        for case in cases:
            profile = UserProfile(**case["profile"])

            retrieval_result = evaluate_retrieval_case(
                conn, profile.extra_info, case["expected_retrieval_scheme_ids"],
            )

            eligibility_results = evaluate_eligibility_for_case(
                conn, profile, case.get("expected_eligibility", {})
            )

            recommendation_result = evaluate_recommendation_case(
                conn, profile,
                case["expected_retrieval_scheme_ids"],
                case["min_relevant_in_top_k"],
            )

            findings = _build_findings_for_explanation(conn, profile, recommendation_result["recommended_ids"])
            explanation_result = evaluate_explanation_case(
                profile.model_dump(exclude_none=True), findings
            )

            eligibility_correct = all(r["correct"] for r in eligibility_results) if eligibility_results else True

            case_results.append({
                "id": case["id"],
                "description": case["description"],
                "retrieval": retrieval_result,
                "eligibility": eligibility_results,
                "eligibility_all_correct": eligibility_correct,
                "recommendation": recommendation_result,
                "explanation": explanation_result,
            })
            time.sleep(3)  # respects Groq free-tier TPM limit across back-to-back eval calls

    non_skipped_retrieval = [c["retrieval"] for c in case_results if not c["retrieval"]["skipped"]]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(case_results),
        "retrieval": {
            "cases_evaluated": len(non_skipped_retrieval),
            "avg_precision_at_k": aggregate([r["precision_at_k"] for r in non_skipped_retrieval]),
            "avg_recall_at_k": aggregate([r["recall_at_k"] for r in non_skipped_retrieval]),
            "avg_mrr": aggregate([r["reciprocal_rank"] for r in non_skipped_retrieval]),
            "avg_hit_rate": aggregate([r["hit_rate"] for r in non_skipped_retrieval]),
        },
        "eligibility": {
            "cases_all_correct": sum(1 for c in case_results if c["eligibility_all_correct"]),
            "cases_total": len(case_results),
            "accuracy": aggregate([1.0 if c["eligibility_all_correct"] else 0.0 for c in case_results]),
        },
        "recommendation": {
            "cases_meeting_minimum": sum(1 for c in case_results if c["recommendation"]["meets_minimum"]),
            "cases_total": len(case_results),
            "avg_precision": aggregate([c["recommendation"]["precision"] for c in case_results]),
            "avg_recall": aggregate([c["recommendation"]["recall"] for c in case_results]),
        },
        "explanation": {
            "llm_available": case_results[0]["explanation"]["llm_available"] if case_results else False,
            "cases_passed": sum(1 for c in case_results if c["explanation"]["passed"]),
            "cases_total": len(case_results),
        },
    }

    report = {"summary": summary, "cases": case_results}
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    _print_summary(summary)
    print(f"\nFull report written to {REPORT_PATH}")
    return report


def _print_summary(summary: dict):
    print("=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total cases: {summary['total_cases']}")
    print("\nRetrieval:")
    r = summary["retrieval"]
    print(f"  Precision@k: {r['avg_precision_at_k']:.3f}  Recall@k: {r['avg_recall_at_k']:.3f}")
    print(f"  MRR: {r['avg_mrr']:.3f}  Hit rate: {r['avg_hit_rate']:.3f}")
    print("\nEligibility:")
    e = summary["eligibility"]
    print(f"  Accuracy: {e['accuracy']:.3f}  ({e['cases_all_correct']}/{e['cases_total']} cases fully correct)")
    print("\nRecommendation:")
    rec = summary["recommendation"]
    print(f"  Meeting minimum relevance: {rec['cases_meeting_minimum']}/{rec['cases_total']}")
    print(f"  Avg precision: {rec['avg_precision']:.3f}  Avg recall: {rec['avg_recall']:.3f}")
    print("\nExplanation:")
    ex = summary["explanation"]
    print(f"  LLM available: {ex['llm_available']}")
    print(f"  Passed grounding checks: {ex['cases_passed']}/{ex['cases_total']}")
    print("=" * 60)


if __name__ == "__main__":
    run()