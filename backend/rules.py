"""Deterministic eligibility rule engine.

Each scheme carries a JSON `rules` object. Every condition evaluates to
pass / fail / unknown against the nullable user profile:

  - any condition fails    -> "ineligible"
  - any condition unknown  -> "possible"  (we list the fields to confirm)
  - all conditions pass    -> "eligible"

The LLM never decides eligibility — it only explains these results.
That keeps outcomes consistent, explainable, and cheap.
"""
from typing import Optional, Tuple

FIELD_LABELS = {
    "age": "your age",
    "annual_income": "your annual family income",
    "gender": "your gender",
    "category": "your social category",
    "occupation": "your occupation",
    "residence": "rural/urban residence",
    "education_level": "your education level",
    "religion": "your religion",
    "disability_pct": "your disability percentage",
    "marital_status": "your marital status",
    "has_bpl_card": "whether you hold a BPL/priority ration card",
    "owns_cultivable_land": "whether your family owns cultivable land",
    "owns_pucca_house": "whether your family owns a pucca house",
    "has_girl_child_under_10": "whether you have a girl child under 10",
}

EDUCATION_LABELS = {
    "below_10th": "below 10th", "10th_pass": "10th pass", "12th_pass": "12th pass",
    "ug": "undergraduate", "pg": "postgraduate", "not_studying": "not studying",
}


def _inr(n: int) -> str:
    return f"₹{n:,}"


def _check(profile, key: str, expected) -> Tuple[Optional[bool], str, str]:
    """Returns (result, reason, profile_field). result None means unknown."""
    p = profile

    if key == "min_age":
        if p.age is None:
            return None, f"needs age ≥ {expected}", "age"
        ok = p.age >= expected
        return ok, f"age {p.age} {'meets' if ok else 'is below'} the minimum of {expected}", "age"

    if key == "max_age":
        if p.age is None:
            return None, f"needs age ≤ {expected}", "age"
        ok = p.age <= expected
        return ok, f"age {p.age} {'is within' if ok else 'exceeds'} the limit of {expected}", "age"

    if key == "max_income":
        if p.annual_income is None:
            return None, f"needs family income ≤ {_inr(expected)}", "annual_income"
        ok = p.annual_income <= expected
        return ok, (f"income {_inr(p.annual_income)} is under the {_inr(expected)} limit" if ok
                    else f"income {_inr(p.annual_income)} exceeds the {_inr(expected)} limit"), "annual_income"

    if key == "gender":
        if p.gender is None:
            return None, f"is for {expected} applicants", "gender"
        ok = p.gender == expected
        return ok, (f"open to {expected} applicants" if ok
                    else f"only for {expected} applicants"), "gender"

    if key == "category_in":
        if p.category is None:
            return None, f"is for {'/'.join(expected)} category", "category"
        ok = p.category in expected
        return ok, (f"{p.category} category qualifies" if ok
                    else f"only for {'/'.join(expected)} category (you selected {p.category})"), "category"

    if key == "occupation_in":
        if p.occupation is None:
            return None, f"is for {'/'.join(expected)}", "occupation"
        ok = p.occupation in expected
        return ok, (f"occupation '{p.occupation}' qualifies" if ok
                    else f"meant for {'/'.join(expected)}"), "occupation"

    if key == "residence":
        if p.residence is None:
            return None, f"is for {expected} areas", "residence"
        ok = p.residence == expected
        return ok, (f"{expected} residence qualifies" if ok
                    else f"only for {expected} areas"), "residence"

    if key == "education_in":
        labels = "/".join(EDUCATION_LABELS.get(e, e) for e in expected)
        if p.education_level is None:
            return None, f"is for {labels} students", "education_level"
        ok = p.education_level in expected
        return ok, (f"education level qualifies" if ok
                    else f"meant for {labels} students"), "education_level"

    if key == "religion_in":
        if p.religion is None:
            return None, f"is for {'/'.join(expected)} communities", "religion"
        ok = p.religion in expected
        return ok, (f"{p.religion} community qualifies" if ok
                    else f"only for notified minority communities ({'/'.join(expected)})"), "religion"

    if key == "min_disability_pct":
        if p.disability_pct is None:
            return None, f"needs benchmark disability ≥ {expected}%", "disability_pct"
        ok = p.disability_pct >= expected
        return ok, (f"disability {p.disability_pct}% meets the {expected}% benchmark" if ok
                    else f"needs ≥ {expected}% benchmark disability"), "disability_pct"

    if key == "marital_status_in":
        if p.marital_status is None:
            return None, f"is for {'/'.join(expected)} applicants", "marital_status"
        ok = p.marital_status in expected
        return ok, (f"marital status qualifies" if ok
                    else f"only for {'/'.join(expected)} applicants"), "marital_status"

    # boolean requirements: requires_bpl_card, requires_cultivable_land, ...
    BOOL_RULES = {
        "requires_bpl_card": ("has_bpl_card", True, "a BPL/priority ration card"),
        "requires_cultivable_land": ("owns_cultivable_land", True, "cultivable land in the family's name"),
        "requires_no_pucca_house": ("owns_pucca_house", False, "not owning a pucca house"),
        "requires_girl_child_under_10": ("has_girl_child_under_10", True, "a girl child under 10 years"),
    }
    if key in BOOL_RULES:
        field, want, label = BOOL_RULES[key]
        val = getattr(p, field)
        if val is None:
            return None, f"requires {label}", field
        ok = val is want
        return ok, (f"requirement met: {label}" if ok else f"requires {label}"), field

    # unrecognised rule keys are treated as unknown, never silently passed
    return None, f"has an unrecognised condition '{key}'", key


def evaluate(profile, rules: dict):
    """-> (status, reasons[], unknown_fields[])"""
    reasons, unknowns = [], []
    failed = False
    for key, expected in rules.items():
        result, reason, field = _check(profile, key, expected)
        if result is True:
            reasons.append("✓ " + reason)
        elif result is False:
            failed = True
            reasons.append("✗ " + reason)
        else:
            unknowns.append(field)
            reasons.append("? " + reason + f" — tell us {FIELD_LABELS.get(field, field)}")
    if failed:
        return "ineligible", reasons, unknowns
    if unknowns:
        return "possible", reasons, unknowns
    return "eligible", reasons, unknowns
