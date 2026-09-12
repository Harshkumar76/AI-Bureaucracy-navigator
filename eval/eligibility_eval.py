"""
eval/eligibility_eval.py

Runs your REAL rules.evaluate() against each case's expected verdicts.
Since evaluate() is deterministic, accuracy here should always be 100% --
any failure is a genuine bug, never noise.
"""
from __future__ import annotations
from backend.rules import evaluate


def evaluate_eligibility_case(profile, scheme_data: dict, expected_status: str) -> dict:
    rules = scheme_data.get("rules", {})
    status, reasons, unknowns = evaluate(profile, rules)
    return {
        "scheme_id": scheme_data.get("id"),
        "expected": expected_status,
        "actual": status,
        "correct": status == expected_status,
        "reasons": reasons,
        "unknown_fields": unknowns,
    }


def evaluate_eligibility_for_case(conn, profile, expected_eligibility: dict[str, str]) -> list[dict]:
    results = []
    with conn.cursor() as cur:
        for scheme_id, expected_status in expected_eligibility.items():
            cur.execute("SELECT data FROM schemes WHERE id = %s", (scheme_id,))
            row = cur.fetchone()
            if row is None:
                results.append({
                    "scheme_id": scheme_id,
                    "expected": expected_status,
                    "actual": "MISSING_SCHEME",
                    "correct": False,
                    "reasons": [f"Scheme '{scheme_id}' not found in database"],
                    "unknown_fields": [],
                })
                continue
            results.append(evaluate_eligibility_case(profile, row["data"], expected_status))
    return results