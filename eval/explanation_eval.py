"""
eval/explanation_eval.py

Validates the LLM's natural-language summary against the actual findings
AND profile data it was given -- grounding checks, since LLM output is
non-deterministic and can't be asserted exactly.
"""
from __future__ import annotations
import re
from backend import llm

_RUPEE_DIGIT_RE = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)")
_LAKH_CRORE_RE = re.compile(r"₹\s?([\d,]+(?:\.\d+)?)\s*(lakh|crore)", re.IGNORECASE)
_RANGE_RE = re.compile(
    r"₹\s?([\d,]+(?:\.\d+)?)\s*[–\-]\s*₹?\s?([\d,]+(?:\.\d+)?)\s*(lakh|crore)",
    re.IGNORECASE,
)


def _extract_rupee_figures(text: str) -> set[float]:
    """
    Returns amounts as normalized numeric values, so '₹2,00,000', '₹2 lakh',
    and '₹1.2 – ₹1.3 lakh' are all recognized correctly rather than compared
    as raw strings.
    """
    figures = set()

    # Ranges like "₹1.2 – ₹1.3 lakh" -- BOTH numbers share the trailing unit
    for low, high, unit in _RANGE_RE.findall(text):
        multiplier = 100_000 if unit.lower() == "lakh" else 10_000_000
        figures.add(round(float(low.replace(",", "")) * multiplier))
        figures.add(round(float(high.replace(",", "")) * multiplier))
    remaining_text = _RANGE_RE.sub("", text)

    for amount_str, unit in _LAKH_CRORE_RE.findall(remaining_text):
        multiplier = 100_000 if unit.lower() == "lakh" else 10_000_000
        figures.add(round(float(amount_str.replace(",", "")) * multiplier))
    remaining_text = _LAKH_CRORE_RE.sub("", remaining_text)

    for amount_str in _RUPEE_DIGIT_RE.findall(remaining_text):
        figures.add(round(float(amount_str.replace(",", ""))))

    return figures


def evaluate_explanation_case(profile_dict: dict, findings: list[dict]) -> dict:
    result = {
        "llm_available": llm.available(),
        "summary": None,
        "grounding_checked": False,
        "ungrounded_rupee_figures": [],
        "passed": True,
        "notes": [],
    }

    if not llm.available():
        result["notes"].append("LLM not configured -- fallback summary path used, skipping grounding check")
        return result

    summary = llm.summarize(profile_dict, findings)
    result["summary"] = summary

    if summary is None:
        result["notes"].append("summarize() returned None despite LLM being available -- treat as a failure")
        result["passed"] = False
        return result

    result["grounding_checked"] = True

    # Known figures = anything from the findings' benefit text (what the
    # LLM was told about schemes) UNION anything from the user's own
    # profile (the LLM is allowed to restate what the user told IT).
    all_benefit_text = " ".join(f.get("benefit", "") for f in findings)
    known_figures = _extract_rupee_figures(all_benefit_text)

    annual_income = profile_dict.get("annual_income")
    if annual_income is not None:
        known_figures.add(round(annual_income))

    summary_figures = _extract_rupee_figures(summary)
    ungrounded = summary_figures - known_figures
    if ungrounded:
        result["ungrounded_rupee_figures"] = list(ungrounded)
        result["passed"] = False
        result["notes"].append(
            f"Summary states rupee figure(s) {ungrounded} not present in any finding's benefit text "
            f"or the user's own profile -- possible hallucination"
        )

    word_count = len(summary.split())
    if word_count > 250:
        result["passed"] = False
        result["notes"].append(f"Summary is {word_count} words -- expected a short summary")

    if not result["notes"]:
        result["notes"].append("Grounding checks passed")

    return result