"""
tests/test_evaluation.py

Turns the evaluation runner into pass/fail CI assertions. Requires a live
DATABASE_URL with schemes seeded and embedded.

Run: pytest tests/test_evaluation.py -v
"""
import pytest
from dotenv import load_dotenv
load_dotenv()

from eval.run_evaluation import run


@pytest.fixture(scope="module")
def report():
    return run()


def test_eligibility_accuracy_is_perfect(report):
    accuracy = report["summary"]["eligibility"]["accuracy"]
    assert accuracy == 1.0, (
        f"Eligibility accuracy is {accuracy:.3f}, expected 1.0 (deterministic engine). "
        f"Check eval_report.json for which case(s) failed."
    )


def test_retrieval_hit_rate_above_threshold(report):
    hit_rate = report["summary"]["retrieval"]["avg_hit_rate"]
    assert hit_rate >= 0.7, f"Retrieval hit rate is {hit_rate:.3f}, expected >= 0.7"


def test_retrieval_mrr_above_threshold(report):
    mrr = report["summary"]["retrieval"]["avg_mrr"]
    assert mrr >= 0.5, f"Mean reciprocal rank is {mrr:.3f}, expected >= 0.5"


def test_recommendation_meets_minimum_relevance_for_most_cases(report):
    rec = report["summary"]["recommendation"]
    ratio = rec["cases_meeting_minimum"] / rec["cases_total"]
    assert ratio >= 0.8, (
        f"Only {rec['cases_meeting_minimum']}/{rec['cases_total']} cases met their "
        f"minimum relevant-recommendation threshold, expected >= 80%"
    )


def test_no_explanation_hallucinations(report):
    if not report["summary"]["explanation"]["llm_available"]:
        pytest.skip("LLM not configured -- fallback summary path used, grounding check not applicable")

    ex = report["summary"]["explanation"]
    pass_rate = ex["cases_passed"] / ex["cases_total"]
    assert pass_rate >= 0.85, (
        f"Only {ex['cases_passed']}/{ex['cases_total']} cases passed explanation grounding "
        f"({pass_rate:.0%}), expected >= 85%. LLM-generated explanations are non-deterministic; "
        f"occasional failures on schemes with vague benefit text are a data-quality signal, not "
        f"necessarily a code regression -- check eval_report.json for which scheme(s) are involved."
    )